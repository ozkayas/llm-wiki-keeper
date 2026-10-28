# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Insert one entry into wiki/log.md, newest first (OKF v0.2, MIGRATION §6).

Entry format: `* **<Op>**: <text>`. It goes at the top of its date's `## YYYY-MM-DD`
group; a missing group is created at its chronological place (newest first), directly
under `# Log` when it is the newest. wiki/log.md is created when missing.

Repeat --text for several bullets: they are written as one block, in the given order.

Usage:
  uv run --script append_log.py --wiki-dir wiki-<slug> --op Ingest --text "3 notes from `notes/`."
  uv run --script append_log.py --wiki-dir wiki-<slug> --op Update --text "..." --date 2026-10-01
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date as Date
from pathlib import Path

OPS = ["Creation", "Ingest", "Query", "Lint", "Update"]
DATE_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")


def insert_entry(text: str, day: str, entry: str) -> str:
    lines = text.splitlines()
    first = next((i for i, l in enumerate(lines) if DATE_HEADING.match(l)), len(lines))
    head = lines[:first] or ["# Log"]
    groups: list[tuple[str, list[str]]] = []
    for line in lines[first:]:
        m = DATE_HEADING.match(line)
        if m:
            groups.append((m.group(1), []))
        else:
            groups[-1][1].append(line)
    groups = [(d, body) for d, body in groups]
    cleaned = []
    for d, body in groups:
        while body and not body[-1].strip():
            body.pop()
        while body and not body[0].strip():
            body.pop(0)
        cleaned.append((d, body))
    groups = cleaned

    for i, (d, body) in enumerate(groups):
        if d == day:
            body.insert(0, entry)
            break
    else:
        pos = next((i for i, (d, _) in enumerate(groups) if d < day), len(groups))
        groups.insert(pos, (day, [entry]))

    while head and not head[-1].strip():
        head.pop()
    out = "\n".join(head) + "\n"
    for d, body in groups:
        out += f"\n## {d}\n" + "\n".join(body) + "\n"
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-dir", required=True, help="Path to wiki-<slug>/ (the dir holding raw/ and wiki/).")
    parser.add_argument("--op", required=True, help="One of: " + ", ".join(OPS))
    parser.add_argument("--text", required=True, action="append", help="Bullet text (markdown allowed). Repeat for several bullets: written as one block, in the given order.")
    parser.add_argument("--date", help="YYYY-MM-DD (default: today, local). For backfill/testing.")
    args = parser.parse_args()

    if args.op not in OPS:
        raise SystemExit(f"unknown --op {args.op!r}; expected one of: {', '.join(OPS)}")
    try:
        day = Date.fromisoformat(args.date).isoformat() if args.date else Date.today().isoformat()
    except ValueError:
        raise SystemExit(f"--date must be YYYY-MM-DD, got {args.date!r}")
    texts = [" ".join(t.split()) for t in args.text]
    if not all(texts):
        raise SystemExit("--text is empty")

    bundle = Path(args.wiki_dir).expanduser().resolve() / "wiki"
    if not bundle.is_dir():
        raise SystemExit(f"not a wiki dir (no wiki/ inside): {Path(args.wiki_dir).resolve()}")
    log = bundle / "log.md"
    created = not log.is_file()
    existing = "# Log\n" if created else log.read_text()
    entry = "\n".join(f"* **{args.op}**: {t}" for t in texts)
    log.write_text(insert_entry(existing, day, entry))
    print(json.dumps({"log": str(log), "date": day, "op": args.op, "entry": entry, "created": created, "bullets": len(texts)}))


if __name__ == "__main__":
    main()
