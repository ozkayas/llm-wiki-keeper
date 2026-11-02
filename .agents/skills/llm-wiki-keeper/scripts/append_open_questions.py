# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Append lint's C04 findings to wiki/open-questions.md (MIGRATION section 19, LINT.md L.6).

Reads one or more JSON files holding reviewer findings: a `lint_reviewer` receipt
(`{findings: [...]}`), a bare list of findings, or a list of receipts. Only findings with
`"id": "C04"` count. Each becomes one bullet under a `## <YYYY-MM-DD>` heading (newest section
last; today's is reused):

  - <message> — from [<page title>](<path relative to wiki/>)     (finding has an existing `file`)
  - <message> — flagged by lint (C04)                             (otherwise)

Idempotent: a bullet whose question text (the part before the ` — ` attribution, case and
whitespace folded) already appears anywhere in the file is skipped, so a re-run adds nothing.
Append-only: existing text is never changed. `generated.at` is bumped only when something was
added. A missing file is created with `type: open_question` frontmatter (PAGES.md). Nothing is
written when there is no C04 finding.

Prints one JSON line: {file, date, c04, added, skipped, created}.

Usage:
  uv run --script append_open_questions.py --wiki-dir wiki-<slug> --findings /scratch/receipt1.json [--findings ...]
  ... --now 2026-10-30T14:20:00Z      (tests; default: current UTC instant)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

DATE_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")
SEP = " — "
NEW_FILE = """---
type: open_question
title: Open questions
description: Questions the wiki cannot answer yet, and gaps worth ingesting for.
created: {at}
generated: {{ by: llm-wiki-keeper/orchestrator, at: {at} }}
---

# Open questions
"""


def fold(text: str) -> str:
    return " ".join(text.split()).casefold()


def question_of(bullet: str) -> str:
    body = bullet.strip()
    if body.startswith(("- ", "* ")):
        body = body[2:]
    return fold(body.split(SEP)[0])


def c04_findings(data: object) -> list[dict]:
    if isinstance(data, dict):
        if isinstance(data.get("findings"), list):
            return c04_findings(data["findings"])
        return [data] if data.get("id") == "C04" else []
    if isinstance(data, list):
        return [f for item in data for f in c04_findings(item)]
    return []


def page_title(bundle: Path, file: str) -> tuple[str, str] | None:
    """(title, path relative to wiki/) when the finding's file is a page of this wiki."""
    rel = file[len("wiki/"):] if file.startswith("wiki/") else file
    path = bundle / rel
    if not rel.endswith(".md") or not path.is_file():
        return None
    text = path.read_text(errors="replace")
    title = None
    if text.startswith("---"):
        end = text.find("\n---", 3)
        try:
            fm = yaml.safe_load(text[3:end]) if end > 0 else None
        except yaml.YAMLError:
            fm = None
        if isinstance(fm, dict) and fm.get("title"):
            title = " ".join(str(fm["title"]).split())
    return (title or Path(rel).stem, rel)


def bullet_for(bundle: Path, finding: dict) -> tuple[str, str] | None:
    question = " ".join(str(finding.get("message") or "").split())
    if not question:
        return None
    question = question.rstrip()
    found = page_title(bundle, str(finding["file"])) if finding.get("file") else None
    tail = f"from [{found[0]}]({found[1]})" if found else "flagged by lint (C04)"
    return question, f"- {question}{SEP}{tail}"


def bump_generated(text: str, at: str) -> str:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            break
        if lines[i].startswith("generated:") and re.search(r"\bat:\s*\S+", lines[i]):
            lines[i] = re.sub(r"(\bat:\s*)[^\s,}]+", rf"\g<1>{at}", lines[i], count=1)
            break
    return "\n".join(lines)


def add_bullets(text: str, day: str, bullets: list[str]) -> str:
    lines = text.rstrip("\n").split("\n")
    heads = [i for i, l in enumerate(lines) if DATE_HEADING.match(l)]
    today = next((i for i in heads if DATE_HEADING.match(lines[i]).group(1) == day), None)
    if today is None:
        lines += ["", f"## {day}", ""] + bullets
    else:
        nxt = next((i for i in heads if i > today), len(lines))
        end = nxt
        while end > today + 1 and not lines[end - 1].strip():
            end -= 1
        lines[end:end] = bullets
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-dir", required=True, help="Path to wiki-<slug>/ (the dir holding raw/ and wiki/).")
    parser.add_argument("--findings", required=True, action="append", help="JSON file with reviewer findings or receipts. Repeatable.")
    parser.add_argument("--now", help="ISO 8601 UTC instant (default: now). Gives the section date and generated.at.")
    args = parser.parse_args()

    bundle = Path(args.wiki_dir).expanduser().resolve() / "wiki"
    if not bundle.is_dir():
        raise SystemExit(f"not a wiki dir (no wiki/ inside): {Path(args.wiki_dir).resolve()}")
    if args.now:
        try:
            now = datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            raise SystemExit(f"--now is not an ISO 8601 instant: {args.now!r}")
    else:
        now = datetime.now(timezone.utc)
    at, day = now.strftime("%Y-%m-%dT%H:%M:%SZ"), now.strftime("%Y-%m-%d")

    findings: list[dict] = []
    for name in args.findings:
        try:
            findings += c04_findings(json.loads(Path(name).expanduser().read_text()))
        except (OSError, json.JSONDecodeError) as e:
            raise SystemExit(f"cannot read findings file {name}: {e}")

    target = bundle / "open-questions.md"
    existing = target.read_text() if target.is_file() else None
    known = {question_of(l) for l in (existing or "").splitlines() if l.lstrip().startswith(("- ", "* "))}
    fresh: list[str] = []
    skipped = 0
    for f in findings:
        made = bullet_for(bundle, f)
        if made is None or fold(made[0]) in known:
            skipped += 1
            continue
        known.add(fold(made[0]))
        fresh.append(made[1])

    created = False
    if fresh:
        created = existing is None
        base = NEW_FILE.format(at=at) if created else bump_generated(existing, at)
        target.write_text(add_bullets(base, day, fresh))
    print(json.dumps({"file": str(target), "date": day, "c04": len(findings), "added": len(fresh),
                      "skipped": skipped, "created": created}))


if __name__ == "__main__":
    main()
