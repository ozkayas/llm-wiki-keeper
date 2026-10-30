# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Rebuild the `index.md` family of a wiki bundle (OKF v0.2, MIGRATION §6).

The index is a derived cache: frontmatter is canonical. Delete every index.md,
re-run, and you get byte-identical files back.

Writes:
  wiki/index.md               only file with frontmatter: `okf_version: "0.2"`
  wiki/<subdir>/index.md      no frontmatter; `* [Title](file.md) - description`; links always target files
  wiki/repos/index.md         one entry per repo dir, linking to `<repo>/index.md`
  wiki/repos/<repo>/index.md  that repo's pages

Also runs an OKF conformance check: ERRORs (exit 1) and WARNings go to stderr.
index.md and log.md are reserved names and never listed as concepts.

Usage:
  uv run --script build_index_md.py --wiki-dir wiki-<slug>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import yaml

OKF_VERSION = "0.2"
RESERVED = {"index.md", "log.md"}

SUBDIRS: list[tuple[str, str]] = [
    ("sources", "Sources"),
    ("entities", "Entities"),
    ("concepts", "Concepts"),
    ("questions", "Questions"),
    ("notes", "Notes"),
]
NESTED_SUBDIRS: list[tuple[str, str]] = [("repos", "Repos")]
SINGLETONS: list[tuple[str, str]] = [("overview.md", "Overview"), ("open-questions.md", "Open questions")]

LOG_HEADING_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")
ISO_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})$")
BY_RE = re.compile(r"^((human|process):\S+|[\w.-]+/[\w.-]+)$")
STATUSES = {"draft", "stable", "deprecated"}
# Page-reference keys: quoted wikilinks relative to the bundle root, e.g. "[[concepts/mcp]]" (MIGRATION section 14).
REFERENCE_KEYS = ("entities", "concepts", "related", "answer_doc", "sources_cited", "spawned_by_question", "repo")
WIKILINK_VALUE_RE = re.compile(r"^\[\[[^\[\]\n]+\]\]$")
MD_LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(\s*<?([^)\s>]+)>?(?:\s+[^)]*)?\)")
EXTERNAL_RE = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//|#|/)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
DIR_LINK_MSG = (
    "link points at a directory; Obsidian creates an empty note when it is clicked; "
    "link the folder's index.md instead"
)


class _Loader(yaml.SafeLoader):
    """SafeLoader that keeps timestamps as strings so offsets can be validated."""


_Loader.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


# ---------------------------------------------------------------- helpers ---


def one_line(value: Any, limit: int = 200) -> str:
    if not value:
        return ""
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def split_frontmatter(path: Path) -> tuple[str, dict[str, Any], str]:
    """(state, frontmatter, body); state is "ok", "absent" or "unparseable"."""
    try:
        text = path.read_text()
    except OSError:
        return "absent", {}, ""
    if not text.startswith("---"):
        return "absent", {}, text
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return "absent", {}, text
    body = "\n".join(lines[end + 1 :])
    try:
        data = yaml.load("\n".join(lines[1:end]), Loader=_Loader)
    except yaml.YAMLError:
        return "unparseable", {}, body
    return ("ok", data, body) if isinstance(data, dict) else ("unparseable", {}, body)


def page_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix == ".md" and p.name not in RESERVED)


def repo_dirs(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(d for d in directory.iterdir() if d.is_dir() and page_files(d))


def page_meta(path: Path) -> tuple[str, str]:
    _, fm, _ = split_frontmatter(path)
    return str(fm.get("title") or path.stem), one_line(fm.get("description"))


def entry(title: str, target: str, description: str) -> str:
    title = title.replace("[", "(").replace("]", ")")
    return f"* [{title}]({target}) - {description}" if description else f"* [{title}]({target})"


def plural(n: int) -> str:
    return f"{n} page" + ("" if n == 1 else "s")


# ------------------------------------------------------------- rendering ---


def render_pages_index(files: list[Path], heading: str) -> str | None:
    if not files:
        return None
    lines = [entry(*(lambda m: (m[0], f.name, m[1]))(page_meta(f))) for f in files]
    return f"# {heading}\n\n" + "\n".join(lines) + "\n"


def render_repos_index(root: Path, heading: str) -> str | None:
    dirs = repo_dirs(root)
    if not dirs:
        return None
    lines = [entry(d.name, f"{d.name}/index.md", plural(len(page_files(d)))) for d in dirs]
    return f"# {heading}\n\n" + "\n".join(lines) + "\n"


def render_root_index(bundle: Path) -> str:
    blocks: list[str] = []
    singles = []
    for name, label in SINGLETONS:
        if (bundle / name).is_file():
            title, desc = page_meta(bundle / name)
            singles.append(entry(title if title != Path(name).stem else label, name, desc))
    if singles:
        blocks.append("# Pages\n\n" + "\n".join(singles))
    browse = [
        entry(heading, f"{subdir}/index.md", plural(len(page_files(bundle / subdir))))
        for subdir, heading in SUBDIRS
        if page_files(bundle / subdir)
    ]
    browse += [
        entry(heading, f"{subdir}/index.md", plural(sum(len(page_files(d)) for d in repo_dirs(bundle / subdir))))
        for subdir, heading in NESTED_SUBDIRS
        if repo_dirs(bundle / subdir)
    ]
    if browse:
        blocks.append("# Browse\n\n" + "\n".join(browse))
    body = "\n\n".join(blocks) + "\n" if blocks else ""
    return f'---\nokf_version: "{OKF_VERSION}"\n---\n\n{body}'


def write_or_drop(target: Path, content: str | None, written: list[Path]) -> None:
    if content is None:
        if target.is_file():
            target.unlink()  # index.md is reserved and generated: drop it when its dir is empty
        return
    target.write_text(content)
    written.append(target)


def write_indexes(bundle: Path) -> list[Path]:
    written: list[Path] = []
    for subdir, heading in SUBDIRS:
        write_or_drop(bundle / subdir / "index.md", render_pages_index(page_files(bundle / subdir), heading), written)
    for subdir, heading in NESTED_SUBDIRS:
        base = bundle / subdir
        write_or_drop(base / "index.md", render_repos_index(base, heading), written)
        if base.is_dir():
            for d in sorted(p for p in base.iterdir() if p.is_dir()):
                write_or_drop(d / "index.md", render_pages_index(page_files(d), d.name), written)
    root = bundle / "index.md"
    root.write_text(render_root_index(bundle))
    written.append(root)
    return written


# ----------------------------------------------------------- conformance ---


def _ts_problem(label: str, value: Any, rel: Path, out: list[str]) -> None:
    if not (isinstance(value, str) and ISO_TS_RE.match(value.strip())):
        out.append(f"{rel}: `{label}` is not ISO 8601 with an explicit offset (e.g. 2026-10-28T09:00:00Z): {value!r}")


def check_page(rel: Path, state: str, fm: dict[str, Any], body: str, fatal: list[str], warn: list[str]) -> None:
    if state != "ok":
        fatal.append(f"{rel}: {state} YAML frontmatter")
        return
    if not str(fm.get("type") or "").strip():
        fatal.append(f"{rel}: missing a non-empty `type`")
    if not str(fm.get("description") or "").strip():
        warn.append(f"{rel}: missing `description` - its index entry will be bare")
    if "timestamp" in fm:
        warn.append(f"{rel}: legacy `timestamp` key - superseded by generated.at")
    if re.search(r"^#+\s+Citations\s*$", body, re.M):
        warn.append(f"{rel}: legacy `# Citations` heading - use `sources` + footnotes")
    if re.search(r"\[\[[^\]\n]+\]\]", body):  # body only: frontmatter reference keys are wikilinks on purpose
        warn.append(f"{rel}: [[wikilink]] in body - this skill emits standard markdown links")
    for key in REFERENCE_KEYS:
        value = fm.get(key)
        for item in value if isinstance(value, list) else [value]:
            if item is None:
                continue
            if not (isinstance(item, str) and WIKILINK_VALUE_RE.match(item.strip())):
                warn.append(
                    f'{rel}: `{key}` holds {item!r}, not a quoted wikilink - migration hint: write "[[concepts/x]]" '
                    "(bundle-relative, no leading slash, no .md, quoted)"
                )
    gen = fm.get("generated")
    if gen is not None:
        if not isinstance(gen, dict) or not str(gen.get("by") or "").strip():
            warn.append(f"{rel}: `generated` present without `generated.by`")
        if isinstance(gen, dict) and "at" in gen:
            _ts_problem("generated.at", gen["at"], rel, warn)
    if "status" in fm and fm["status"] not in STATUSES:
        warn.append(f"{rel}: `status` must be draft|stable|deprecated, got {fm['status']!r}")
    for key in ("created", "stale_after"):
        if key in fm:
            _ts_problem(key, fm[key], rel, warn)
    verified = fm.get("verified")
    if verified is not None:
        for v in verified if isinstance(verified, list) else [verified]:
            if not isinstance(v, dict):
                warn.append(f"{rel}: `verified` entry is not a mapping: {v!r}")
                continue
            if not BY_RE.match(str(v.get("by") or "")):
                warn.append(f"{rel}: `verified[].by` must be human:<id>, process:<name> or <producer>/<version>: {v.get('by')!r}")
            if "at" in v:
                _ts_problem("verified[].at", v["at"], rel, warn)


def check_dir_links(path: Path, rel: Path, warn: list[str]) -> None:
    """Warn on every markdown link whose relative target is a directory."""
    in_fence = False
    for n, line in enumerate(path.read_text(errors="replace").splitlines(), start=1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for m in MD_LINK_RE.finditer(re.sub(r"`[^`\n]*`", "", line)):
            target = m.group(1)
            if EXTERNAL_RE.match(target):
                continue
            raw = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if raw and (raw.endswith("/") or (path.parent / raw).is_dir()):
                warn.append(f"{rel}:{n}: `{target}`: {DIR_LINK_MSG}")


def check_log(log: Path, rel: Path, warn: list[str]) -> None:
    dates: list[str] = []
    for n, line in enumerate(log.read_text(errors="replace").splitlines(), start=1):
        if line.startswith("## "):
            m = LOG_HEADING_RE.match(line)
            if not m:
                warn.append(f"{rel}:{n}: heading must be `## YYYY-MM-DD`: {line.strip()!r}")
            else:
                if dates and m.group(1) >= dates[-1]:
                    warn.append(f"{rel}:{n}: {m.group(1)} is not older than the previous heading {dates[-1]} (log is newest first)")
                dates.append(m.group(1))


def check_conformance(wiki_dir: Path, bundle: Path) -> tuple[list[str], list[str]]:
    fatal: list[str] = []
    warn: list[str] = []
    for path in sorted(bundle.rglob("*.md")):
        rel = path.relative_to(wiki_dir)
        check_dir_links(path, rel, warn)
        if path.name == "index.md":
            if path != bundle / "index.md" and path.read_text().startswith("---"):
                warn.append(f"{rel}: a non-root index.md must not carry frontmatter")
            continue
        if path.name == "log.md":
            continue
        state, fm, body = split_frontmatter(path)
        check_page(rel, state, fm, body, fatal, warn)
    log = bundle / "log.md"
    if log.is_file():
        check_log(log, log.relative_to(wiki_dir), warn)
    return fatal, warn


# ------------------------------------------------------------------ main ---


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-dir", required=True, help="Path to wiki-<slug>/ (the dir holding raw/ and wiki/).")
    args = parser.parse_args()

    wiki_dir = Path(args.wiki_dir).expanduser().resolve()
    bundle = wiki_dir / "wiki"
    if not bundle.is_dir():
        raise SystemExit(f"not a wiki dir (no wiki/ inside): {wiki_dir}")

    written = write_indexes(bundle)
    fatal, warnings = check_conformance(wiki_dir, bundle)
    for line in fatal:
        print(f"ERROR: {line}", file=sys.stderr)
    for line in warnings:
        print(f"WARN:  {line}", file=sys.stderr)

    pages = sum(len(page_files(bundle / s)) for s, _ in SUBDIRS) + sum(
        len(page_files(d)) for s, _ in NESTED_SUBDIRS for d in repo_dirs(bundle / s)
    )
    print(
        json.dumps(
            {
                "wiki_dir": str(wiki_dir),
                "indexes_written": [str(p.relative_to(wiki_dir)) for p in written],
                "pages": pages,
                "errors": fatal,
                "warnings": warnings,
            },
            indent=2,
        )
    )
    if fatal:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
