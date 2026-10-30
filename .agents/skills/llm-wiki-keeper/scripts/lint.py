# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Deterministic lint for a wiki bundle (OKF v0.2, MIGRATION section 16.1, checks L01-L15).

Read-only: nothing is written to the wiki, no network. L10 and L13 run `build_index_md.py`
(sibling script, subprocess) on a temporary COPY of `wiki/`.

Output: JSON on stdout
  {findings: [{id, severity, file, line, message, fix_hint}], summary: {error, warn, info},
   config, checked_pages}
and a human table on stderr (suppressed by --json-only). Exit 1 when any `error` exists.
Findings are ordered by (severity, file, line, id); `file` is relative to --wiki-dir.

Usage:
  uv run --script lint.py --wiki-dir wiki-<slug>
  uv run --script lint.py --wiki-dir wiki-<slug> --now 2026-10-30T00:00:00Z --json-only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import yaml

RESERVED = {"index.md", "log.md"}
CHECKED_TYPES = {"source", "entity", "concept", "overview", "note", "repo", "repo_note"}
KINDS = ("entities", "concepts")
SOURCE_LIKE_GLOBS = ["sources/*.md", "repos/*/*.md"]
REFERENCE_KEYS = ("entities", "concepts", "related", "answer_doc", "sources_cited", "spawned_by_question", "repo")
ALLOWED_TOP = {"config.yml", "raw", "wiki", ".obsidian"}
IGNORED_TOP = {".DS_Store"}
DEFAULT_CONFIG = {"language": "en", "tags": "optional", "stale_after_days": 60}
SEV_RANK = {"error": 0, "warn": 1, "info": 2}

MD_LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(\s*<?([^)\s>]+)>?(?:\s+[^)]*)?\)")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
HR_RE = re.compile(r"^\s{0,3}(([-*_])(\s*\2){2,}|=+)\s*$")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
FOOT_DEF_RE = re.compile(r"^\s{0,3}\[\^([^\]\s]+)\]:")
FOOT_REF_RE = re.compile(r"\[\^([^\]\s]+)\](?!:)")
META_BQ_RE = re.compile(r"^>\s*\**[A-Za-z][\w /-]{0,30}\**:")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
BLOCK_ID_RE = re.compile(r"^(\^|L\d+(-L?\d+)?$)")


class _Loader(yaml.SafeLoader):
    """SafeLoader that keeps timestamps as strings (same idea as build_index_md.py)."""


_Loader.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


# ---------------------------------------------------------------- model ---


@dataclass
class Page:
    path: Path
    rel: str  # relative to wiki-dir, posix
    lines: list[str]
    state: str  # ok | absent | unparseable
    fm: dict[str, Any]
    body_start: int  # 0-based index of first body line

    @property
    def type(self) -> str:
        return str(self.fm.get("type") or "").strip()

    @property
    def reserved(self) -> bool:
        return self.path.name in RESERVED

    def body(self) -> list[tuple[int, str]]:
        """(1-based line number, line) for the body."""
        return [(i + 1, self.lines[i]) for i in range(self.body_start, len(self.lines))]

    def fm_line(self, needle: str | re.Pattern[str]) -> int | None:
        for i in range(min(self.body_start, len(self.lines))):
            line = self.lines[i]
            if (needle.search(line) if isinstance(needle, re.Pattern) else needle in line):
                return i + 1
        return None


@dataclass
class Ctx:
    wiki_dir: Path
    bundle: Path
    now: datetime
    config: dict[str, Any]
    pages: list[Page] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    headings_cache: dict[Path, set[str]] = field(default_factory=dict)

    def add(self, fid: str, sev: str, file: str | None, line: int | None, message: str, hint: str) -> None:
        self.findings.append(
            {"id": fid, "severity": sev, "file": file, "line": line, "message": message, "fix_hint": hint}
        )

    def rel(self, path: Path) -> str:
        try:
            return path.relative_to(self.wiki_dir).as_posix()
        except ValueError:
            return str(path)


def parse_page(path: Path, wiki_dir: Path) -> Page:
    text = path.read_text(errors="replace")
    lines = text.splitlines()
    state, fm, body_start = "absent", {}, 0
    if text.startswith("---"):
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is not None:
            body_start = end + 1
            try:
                data = yaml.load("\n".join(lines[1:end]), Loader=_Loader)
            except yaml.YAMLError:
                data = None
                state = "unparseable"
            if isinstance(data, dict):
                state, fm = "ok", data
            elif state != "unparseable":
                state = "unparseable"
    return Page(path, path.relative_to(wiki_dir).as_posix(), lines, state, fm, body_start)


def parse_ts(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime(value.year, value.month, value.day)
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.strip())
        except ValueError:
            return None
    else:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def references(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [leaf for item in value for leaf in references(item)]
    return [value]


def ref_parts(reference: Any) -> tuple[str, str]:
    """(bundle-relative path without .md, anchor) for a wikilink / legacy path reference."""
    text = str(reference).strip()
    if text.startswith("[["):
        text = text[2:]
    if text.endswith("]]"):
        text = text[:-2]
    text = text.split("|", 1)[0].strip()
    text, _, anchor = text.partition("#")
    text = text.strip().lstrip("/")
    if text.startswith("wiki/"):
        text = text[5:]
    if text.endswith(".md"):
        text = text[:-3]
    return text, anchor.strip()


def slug_of(reference: Any) -> str:
    """Same slug rule as count_mentions.py: last path segment of the reference."""
    text = str(reference).strip().strip("[]").split("|")[0].strip()
    if text.endswith(".md"):
        text = text[:-3]
    return text.rsplit("/", 1)[-1]


def norm_heading(text: str) -> str:
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`]", "", text)
    return " ".join(text.split()).lower()


def code_free_lines(page: Page) -> list[tuple[int, str]]:
    """Body lines outside fenced blocks, inline code removed."""
    out: list[tuple[int, str]] = []
    in_fence = False
    for n, line in page.body():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append((n, INLINE_CODE_RE.sub("", line)))
    return out


def headings_of(ctx: Ctx, path: Path) -> set[str]:
    if path not in ctx.headings_cache:
        found: set[str] = set()
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            lines = []
        in_fence = False
        for line in lines:
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            m = None if in_fence else HEADING_RE.match(line)
            if m:
                found.add(norm_heading(m.group(1)))
        ctx.headings_cache[path] = found
    return ctx.headings_cache[path]


# ------------------------------------------------------------- mentions ---


def collect_mentions(ctx: Ctx) -> dict[str, dict[str, set[str]]]:
    """count_mentions.py rule: {kind: {slug: {source-like pages}}}."""
    mentions: dict[str, dict[str, set[str]]] = {k: {} for k in KINDS}
    for page in ctx.pages:
        rel_b = page.path.relative_to(ctx.bundle).as_posix()
        parts = rel_b.split("/")
        source_like = (len(parts) == 2 and parts[0] == "sources") or (len(parts) == 3 and parts[0] == "repos")
        if not source_like or page.reserved:
            continue
        for kind in KINDS:
            for ref in references(page.fm.get(kind)):
                slug = slug_of(ref)
                if slug:
                    mentions[kind].setdefault(slug, set()).add(page.rel)
    return mentions


# ----------------------------------------------------------------- links ---


@dataclass
class Link:
    page: Page
    line: int | None
    target: Path  # resolved path (may not exist)
    anchor: str
    shown: str


def outgoing_links(ctx: Ctx, page: Page) -> list[Link]:
    out: list[Link] = []
    for n, line in code_free_lines(page):
        for m in MD_LINK_RE.finditer(line):
            raw = m.group(1)
            if raw.startswith("#"):
                out.append(Link(page, n, page.path, unquote(raw[1:]), raw))
                continue
            if SCHEME_RE.match(raw) or raw.startswith("//") or raw.startswith("/"):
                continue
            path_part, _, anchor = raw.partition("#")
            path_part = unquote(path_part.split("?", 1)[0])
            if not path_part:
                continue
            target = Path(os.path.normpath(page.path.parent / path_part))
            out.append(Link(page, n, target, unquote(anchor), raw))
    for key in REFERENCE_KEYS:
        for item in references(page.fm.get(key)):
            text, anchor = ref_parts(item)
            if not text:
                continue
            target = Path(os.path.normpath(ctx.bundle / (text + ".md")))
            out.append(Link(page, page.fm_line(str(item).strip().strip("[]").split("|")[0]) or page.fm_line(f"{key}:"), target, anchor, str(item)))
    return out


def local_resources(ctx: Ctx, page: Page) -> list[tuple[int | None, str, Path]]:
    """(line, resource string, resolved path) for each local sources[].resource."""
    out = []
    for entry in sources_entries(page):
        res = entry.get("resource") if isinstance(entry, dict) else None
        if not isinstance(res, str) or not res.strip() or SCHEME_RE.match(res.strip()):
            continue
        p = unquote(res.strip().split("#", 1)[0])
        out.append((page.fm_line(res.strip()), res.strip(), Path(os.path.normpath(page.path.parent / p))))
    return out


def sources_entries(page: Page) -> list[Any]:
    value = page.fm.get("sources")
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


# --------------------------------------------------------------- checks ---


def check_l01(ctx: Ctx) -> None:
    for page in ctx.pages:
        if page.reserved or page.type not in CHECKED_TYPES:
            continue
        units: list[dict[str, Any]] = []
        cur: dict[str, Any] | None = None
        in_fence = in_foot = False

        def flush() -> None:
            nonlocal cur
            if cur:
                units.append(cur)
            cur = None

        for n, line in page.body():
            if FENCE_RE.match(line):
                flush()
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            stripped = line.strip()
            if not stripped:
                flush()
                in_foot = False
                continue
            if in_foot and line[0] in " \t":
                continue
            in_foot = False
            if FOOT_DEF_RE.match(line):
                flush()
                in_foot = True
                continue
            if HEADING_RE.match(line) or HR_RE.match(line) or stripped.startswith(("|", "<")):
                flush()
                continue
            m = LIST_RE.match(line)
            if m:
                flush()
                cur = {"line": n, "text": m.group(3), "kind": "list"}
            elif stripped.startswith(">"):
                if cur and cur["kind"] == "quote":
                    cur["text"] += " " + stripped.lstrip(">").strip()
                else:
                    flush()
                    cur = {"line": n, "text": stripped, "kind": "quote"}
            elif cur:
                cur["text"] += " " + stripped
            else:
                cur = {"line": n, "text": stripped, "kind": "para"}
        flush()

        for u in units:
            text = u["text"]
            if FOOT_REF_RE.search(text):
                continue
            if u["kind"] == "quote" and META_BQ_RE.match(text):
                continue
            residue = re.sub(r"!?\[[^\]]*\]\([^)]*\)|\[\[[^\]]*\]\]|https?://\S+", "", text)
            if u["kind"] == "list" and not re.search(r"[^\W_]", residue):
                continue  # links-only item
            if not re.search(r"[^\W\d_]", residue):
                continue  # no words at all
            snippet = " ".join(text.split())[:80]
            ctx.add(
                "L01", "warn", page.rel, u["line"], f'uncited prose: "{snippet}"',
                "add a [^id] footnote that is listed in sources, or move the judgment to a `> Synthesis:` line",
            )


def check_l02_l03(ctx: Ctx) -> None:
    for path in sorted(ctx.wiki_dir.rglob("*.md")):
        rel = path.relative_to(ctx.wiki_dir)
        if rel.parts[0] in ("raw", ".obsidian"):
            continue
        if not path.read_text(errors="replace").strip():
            ctx.add(
                "L02", "error", rel.as_posix(), None,
                "empty stub: file has no content (Obsidian creates these when a hollow link is clicked)",
                "delete the file, or write the page; promissory links stay hollow until 2 sources mention the slug",
            )
    for entry in sorted(ctx.wiki_dir.iterdir()):
        if entry.name in ALLOWED_TOP or entry.name in IGNORED_TOP:
            continue
        kind = "folder" if entry.is_dir() else "file"
        ctx.add(
            "L03", "warn", entry.name, None,
            f"stray {kind} outside the bundle: only config.yml, raw/, wiki/ and .obsidian/ belong in wiki-<slug>/",
            "move it into wiki/ if it is a page, otherwise delete it (often created by clicking a hollow link)",
        )


def resolve_page_link(link: Link, ctx: Ctx, mentions: dict[str, dict[str, set[str]]]) -> str | None:
    """Return an L04 message when the link is broken, else None."""
    t = link.target
    if t.is_dir():
        return None  # reported by build_index_md (L13)
    if not t.exists():
        try:
            parts = t.relative_to(ctx.bundle).parts
        except ValueError:
            parts = ()
        if len(parts) == 2 and parts[0] in KINDS and t.suffix == ".md":
            if len(mentions[parts[0]].get(t.stem, ())) < 2:
                return None  # promissory
        return f"broken link `{link.shown}`: target does not exist"
    if link.anchor and t.suffix == ".md" and not BLOCK_ID_RE.match(link.anchor):
        if norm_heading(link.anchor) not in headings_of(ctx, t):
            return f"broken anchor `{link.shown}`: no heading with that text in the target"
    return None


def check_l04(ctx: Ctx, links: dict[str, list[Link]], mentions: dict[str, dict[str, set[str]]]) -> None:
    for page in ctx.pages:
        for link in links[page.rel]:
            msg = resolve_page_link(link, ctx, mentions)
            if msg:
                ctx.add(
                    "L04", "error", page.rel, link.line, msg,
                    "fix the path or heading text; links to entities/concepts with fewer than 2 mentions may stay hollow",
                )


def check_l05_l06(ctx: Ctx, mentions: dict[str, dict[str, set[str]]]) -> None:
    for kind in KINDS:
        for slug, pages in sorted(mentions[kind].items()):
            if len(pages) >= 2 and not (ctx.bundle / kind / f"{slug}.md").is_file():
                ctx.add(
                    "L05", "error", f"wiki/{kind}/{slug}.md", None,
                    f"missing page: `{slug}` is mentioned by {len(pages)} source-like pages ({', '.join(sorted(pages))}) but has no page",
                    f"write wiki/{kind}/{slug}.md with a page_writer (next ingest or user-confirmed fix)",
                )
        d = ctx.bundle / kind
        for p in sorted(d.glob("*.md")) if d.is_dir() else []:
            if p.name in RESERVED:
                continue
            if len(mentions[kind].get(p.stem, ())) < 2:
                ctx.add(
                    "L06", "warn", ctx.rel(p), None,
                    f"premature page: `{p.stem}` has {len(mentions[kind].get(p.stem, ()))} source mention(s), threshold is 2",
                    "keep it if a human wrote it on purpose; otherwise it waits for a second source",
                )


def check_l07_l08_links(ctx: Ctx, links: dict[str, list[Link]]) -> None:
    by_path = {p.path: p for p in ctx.pages}
    inbound: dict[str, list[tuple[Page, int | None]]] = {p.rel: [] for p in ctx.pages}
    for page in ctx.pages:
        if page.path.name == "index.md":
            continue  # generated indexes list everything; they would make L07 vacuous
        targets = [(link.target, link.line) for link in links[page.rel]]
        targets += [(t, ln) for ln, _, t in local_resources(ctx, page)]
        for target, line in targets:
            other = by_path.get(target)
            if other is not None and other is not page:
                inbound[other.rel].append((page, line))
    exempt = {"overview.md", "open-questions.md"}
    for page in ctx.pages:
        if page.reserved or page.path.relative_to(ctx.bundle).as_posix() in exempt:
            continue
        if not inbound[page.rel]:
            ctx.add(
                "L07", "warn", page.rel, None, "orphan: no other page links here",
                "link it from a related page (or from the overview), or delete it",
            )
        if page.fm.get("status") == "deprecated":
            for linker, line in inbound[page.rel]:
                if linker.fm.get("status") != "deprecated" and not linker.reserved:
                    ctx.add(
                        "L08", "warn", linker.rel, line,
                        f"links to deprecated page `{page.rel}`",
                        "update the link to the replacement, or mark this page deprecated too",
                    )


def check_l08_time(ctx: Ctx) -> None:
    days = ctx.config["stale_after_days"]
    for page in ctx.pages:
        if page.reserved or page.state != "ok":
            continue
        stale = parse_ts(page.fm.get("stale_after"))
        if stale is not None and stale <= ctx.now:
            ctx.add(
                "L08", "warn", page.rel, page.fm_line("stale_after"),
                f"stale: stale_after {page.fm.get('stale_after')} has passed",
                "re-ingest the source or have a human re-verify, then update the page",
            )
        gen = page.fm.get("generated")
        at = parse_ts(gen.get("at")) if isinstance(gen, dict) else None
        external = any(
            isinstance(e, dict) and isinstance(e.get("resource"), str) and re.match(r"https?://", e["resource"])
            for e in sources_entries(page)
        )
        if external and at is not None and isinstance(days, (int, float)) and at < ctx.now - timedelta(days=days):
            ctx.add(
                "L08", "info", page.rel, page.fm_line("at:"),
                f"generated.at is older than stale_after_days ({days}) and the source is a web article or a repo",
                "consider re-fetching the source",
            )


def check_l09(ctx: Ctx) -> None:
    for page in ctx.pages:
        if page.reserved:
            continue
        refs: dict[str, int] = {}
        defs: dict[str, int] = {}
        for n, line in code_free_lines(page):
            m = FOOT_DEF_RE.match(line)
            if m:
                defs.setdefault(m.group(1), n)
                line = line[m.end():]
            for r in FOOT_REF_RE.finditer(line):
                refs.setdefault(r.group(1), n)
        ids = {str(e.get("id")) for e in sources_entries(page) if isinstance(e, dict) and e.get("id") is not None}
        for fid, n in sorted(refs.items(), key=lambda kv: kv[1]):
            if fid not in defs:
                ctx.add("L09", "error", page.rel, n, f"footnote [^{fid}] is referenced but has no definition",
                        f"add `[^{fid}]: [title](path)` at the end of the page")
            if fid not in ids:
                ctx.add("L09", "error", page.rel, n, f"footnote id `{fid}` is not in sources[].id",
                        f"add a sources entry with id: {fid}, or use an existing id")
        for fid, n in sorted(defs.items(), key=lambda kv: kv[1]):
            if fid not in refs:
                ctx.add("L09", "error", page.rel, n, f"footnote definition [^{fid}] is never used",
                        "remove the definition or cite it in the text")
        for entry in sources_entries(page):
            if not isinstance(entry, dict) or not str(entry.get("resource") or "").strip():
                ctx.add("L09", "error", page.rel, page.fm_line("sources:"), "sources entry without `resource`",
                        "every sources entry needs a resource (relative path or URL)")
        for line, res, target in local_resources(ctx, page):
            if not target.exists():
                ctx.add("L09", "error", page.rel, line, f"sources[].resource `{res}` points at a missing local file",
                        "fix the relative path (raw/ lives outside wiki/, e.g. ../../raw/x.md)")


def run_build_index(ctx: Ctx) -> tuple[Path | None, dict[str, Any] | None, str]:
    script = Path(__file__).resolve().parent / "build_index_md.py"
    tmp = Path(tempfile.mkdtemp(prefix="lint-"))
    try:
        work = tmp / ctx.wiki_dir.name
        shutil.copytree(ctx.bundle, work / "wiki")
    except OSError as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        return None, None, f"could not copy wiki/ to a temp dir: {exc}"
    if not script.is_file():
        shutil.rmtree(tmp, ignore_errors=True)
        return None, None, "build_index_md.py not found next to lint.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--wiki-dir", str(work)], capture_output=True, text=True
    )
    data = None
    try:
        data = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        pass
    return tmp, data, proc.stderr.strip() if data is None else ""


def check_l10_l13(ctx: Ctx) -> None:
    tmp, data, failure = run_build_index(ctx)
    if tmp is None or data is None:
        ctx.add("L13", "error" if tmp is not None else "warn", None, None,
                f"build_index_md.py did not produce a result: {failure or 'unknown failure'}",
                "run build_index_md.py by hand and read its stderr")
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
        return
    try:
        work_bundle = tmp / ctx.wiki_dir.name / "wiki"
        real = {p.relative_to(ctx.bundle).as_posix() for p in ctx.bundle.rglob("index.md")}
        fresh = {p.relative_to(work_bundle).as_posix() for p in work_bundle.rglob("index.md")}
        for rel in sorted(real | fresh):
            real_p, fresh_p = ctx.bundle / rel, work_bundle / rel
            file = f"wiki/{rel}"
            hint = "re-run build_index_md.py (user-confirmed fix)"
            if rel not in real:
                ctx.add("L10", "warn", file, None, "index drift: this index.md is missing", hint)
            elif rel not in fresh:
                ctx.add("L10", "warn", file, None, "index drift: this index.md would no longer be generated", hint)
            elif real_p.read_bytes() != fresh_p.read_bytes():
                a = real_p.read_text(errors="replace").splitlines()
                b = fresh_p.read_text(errors="replace").splitlines()
                first = next((i + 1 for i in range(max(len(a), len(b)))
                              if (a[i] if i < len(a) else None) != (b[i] if i < len(b) else None)), None)
                ctx.add("L10", "warn", file, first, "index drift: differs from what build_index_md.py would write now", hint)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    pat = re.compile(r"^(?P<file>[^:\n]+?)(?::(?P<line>\d+))?: (?P<msg>.*)$", re.S)
    for sev, key in (("error", "errors"), ("warn", "warnings")):
        for text in data.get(key, []):
            m = pat.match(text)
            file, line, msg = (m["file"], int(m["line"]) if m["line"] else None, m["msg"]) if m else (None, None, text)
            ctx.add("L13", sev, file, line, f"conformance: {msg}", "see MIGRATION-OKF-0.2.md / CONVENTIONS.md for the rule")


def check_l11(ctx: Ctx) -> None:
    if ctx.config["tags"] != "forbidden":
        return
    for page in ctx.pages:
        if not page.reserved and page.fm.get("tags"):
            ctx.add("L11", "warn", page.rel, page.fm_line("tags"), "`tags` present but config.yml says tags: forbidden",
                    "remove the tags key")


def check_l12(ctx: Ctx) -> None:
    trust = {"unverified": 0, "machine-confirmed": 0, "human-reviewed": 0}
    status: dict[str, int] = {}
    for page in ctx.pages:
        if page.reserved or page.state != "ok":
            continue
        ver = [v for v in references(page.fm.get("verified")) if isinstance(v, dict)]
        if any(str(v.get("by") or "").startswith("human:") for v in ver):
            trust["human-reviewed"] += 1
        elif ver:
            trust["machine-confirmed"] += 1
        else:
            trust["unverified"] += 1
        s = str(page.fm.get("status") or "stable")
        status[s] = status.get(s, 0) + 1
    t = ", ".join(f"{k} {v}" for k, v in trust.items())
    s = ", ".join(f"{k} {v}" for k, v in sorted(status.items())) or "none"
    ctx.add("L12", "info", None, None, f"trust: {t}; status: {s}", "informational only")


def check_l15(ctx: Ctx) -> None:
    for page in ctx.pages:
        if page.reserved or page.state != "ok":
            continue
        created = parse_ts(page.fm.get("created"))
        gen = page.fm.get("generated")
        at = parse_ts(gen.get("at")) if isinstance(gen, dict) else None
        if created is not None and created > ctx.now:
            ctx.add("L15", "warn", page.rel, page.fm_line(re.compile(r"^created:")), "`created` is in the future",
                    "fix the timestamp (date -u +%Y-%m-%dT%H:%M:%SZ)")
        if at is not None and at > ctx.now:
            ctx.add("L15", "warn", page.rel, page.fm_line(re.compile(r"\bat:")), "`generated.at` is in the future",
                    "fix the timestamp (date -u +%Y-%m-%dT%H:%M:%SZ)")
        if created is not None and at is not None and created > at:
            ctx.add("L15", "warn", page.rel, page.fm_line(re.compile(r"^created:")), "`created` is later than `generated.at`",
                    "created never changes; generated.at must be equal or later")


# ------------------------------------------------------------------ main ---


def load_config(wiki_dir: Path) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    path = wiki_dir / "config.yml"
    cfg["source"] = "defaults"
    if path.is_file():
        try:
            data = yaml.safe_load(path.read_text())
        except yaml.YAMLError:
            data = None
        if isinstance(data, dict):
            cfg.update({k: data[k] for k in DEFAULT_CONFIG if k in data})
        cfg["source"] = "config.yml"
    return cfg


def lint(wiki_dir: Path, now: datetime) -> tuple[list[dict[str, Any]], dict[str, Any], int]:
    bundle = wiki_dir / "wiki"
    ctx = Ctx(wiki_dir, bundle, now, load_config(wiki_dir))
    ctx.pages = [parse_page(p, wiki_dir) for p in sorted(bundle.rglob("*.md"))]
    if ctx.config["source"] == "defaults":
        ctx.add("L14", "info", "config.yml", None, "config.yml is missing; defaults were used (language en, tags optional, stale_after_days 60)",
                "optional: create config.yml (the skill writes it on first run)")
    mentions = collect_mentions(ctx)
    links = {p.rel: outgoing_links(ctx, p) for p in ctx.pages}
    check_l01(ctx)
    check_l02_l03(ctx)
    check_l04(ctx, links, mentions)
    check_l05_l06(ctx, mentions)
    check_l07_l08_links(ctx, links)
    check_l08_time(ctx)
    check_l09(ctx)
    check_l10_l13(ctx)
    check_l11(ctx)
    check_l12(ctx)
    check_l15(ctx)
    seen, unique = set(), []
    for f in ctx.findings:
        key = json.dumps(f, sort_keys=True)
        if key not in seen:
            seen.add(key)
            unique.append(f)
    unique.sort(key=lambda f: (SEV_RANK[f["severity"]], f["file"] or "", f["line"] or 0, f["id"], f["message"]))
    config = {k: ctx.config[k] for k in ("language", "tags", "stale_after_days", "source")}
    checked = sum(1 for p in ctx.pages if not p.reserved)
    return unique, config, checked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-dir", required=True, help="Path to wiki-<slug>/ (the dir holding raw/ and wiki/).")
    parser.add_argument("--now", help="ISO 8601 instant used for staleness and future-timestamp checks (default: now, UTC).")
    parser.add_argument("--json-only", action="store_true", help="JSON only: suppress the table on stderr.")
    args = parser.parse_args()

    wiki_dir = Path(args.wiki_dir).expanduser().resolve()
    if not (wiki_dir / "wiki").is_dir():
        raise SystemExit(f"not a wiki dir (no wiki/ inside): {wiki_dir}")
    now = parse_ts(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        raise SystemExit(f"--now is not an ISO 8601 instant: {args.now!r}")

    findings, config, checked = lint(wiki_dir, now)
    summary = {s: sum(1 for f in findings if f["severity"] == s) for s in ("error", "warn", "info")}
    if not args.json_only:
        for f in findings:
            loc = (f["file"] or "-") + (f":{f['line']}" if f["line"] else "")
            print(f"{f['id']}  {f['severity']:<5}  {loc}  {f['message']}", file=sys.stderr)
        print(f"{summary['error']} error, {summary['warn']} warn, {summary['info']} info ({checked} pages)", file=sys.stderr)
    print(json.dumps({"findings": findings, "summary": summary, "config": config, "checked_pages": checked}, indent=2))
    if summary["error"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
