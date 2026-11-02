"""Tests for append_open_questions.py (MIGRATION-OKF-0.2.md section 19).

Run from the repo root:  uv run --with pytest --with pyyaml pytest tests/
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".agents/skills/llm-wiki-keeper/scripts/append_open_questions.py"
NOW = "2026-10-30T14:20:00Z"
LATER = "2026-10-31T08:00:00Z"

EXISTING = """---
type: open_question
title: Open questions
description: Questions the wiki cannot answer yet, and gaps worth ingesting for.
created: 2026-10-28T11:00:00Z
generated: { by: llm-wiki-keeper/orchestrator, at: 2026-10-28T11:05:00Z }
---

# Open questions

## 2026-10-28

- Does the step budget differ between harnesses? — flagged by the user
"""


def c04(message: str, file: str | None = None) -> dict:
    return {"id": "C04", "severity": "info", "file": file, "line": None, "quote": "q", "message": message, "fix_hint": "h"}


@pytest.fixture
def wiki(tmp_path: Path) -> Path:
    (tmp_path / "wiki-x/wiki/concepts").mkdir(parents=True)
    (tmp_path / "wiki-x/wiki/concepts/mcp.md").write_text("---\ntype: concept\ntitle: MCP\n---\n\n# MCP\n")
    return tmp_path / "wiki-x"


def run(wiki: Path, findings: list, now: str = NOW, name: str = "r.json") -> dict:
    f = wiki.parent / name
    f.write_text(json.dumps(findings))
    proc = subprocess.run([sys.executable, str(SCRIPT), "--wiki-dir", str(wiki), "--findings", str(f), "--now", now],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def oq(wiki: Path) -> Path:
    return wiki / "wiki/open-questions.md"


def test_creates_missing_file_with_frontmatter(wiki: Path):
    out = run(wiki, {"findings": [c04("Is tool-use worth a second source?"), {"id": "C05", "message": "ignored"}]})
    assert (out["added"], out["created"], out["c04"]) == (1, True, 1)
    text = oq(wiki).read_text()
    assert text.startswith("---\ntype: open_question\ntitle: Open questions\n")
    assert "created: 2026-10-30T14:20:00Z\ngenerated: { by: llm-wiki-keeper/orchestrator, at: 2026-10-30T14:20:00Z }" in text
    assert "# Open questions\n\n## 2026-10-30\n\n- Is tool-use worth a second source? — flagged by lint (C04)\n" in text
    assert "ignored" not in text


def test_idempotent_second_run_changes_nothing(wiki: Path):
    run(wiki, [c04("Gap one?")])
    first = oq(wiki).read_text()
    out = run(wiki, [c04("  gap   ONE? ")], now=LATER)
    assert (out["added"], out["skipped"]) == (0, 1)
    assert oq(wiki).read_text() == first


def test_existing_content_preserved_and_generated_bumped(wiki: Path):
    oq(wiki).write_text(EXISTING)
    out = run(wiki, [c04("Does the step budget differ between harnesses?"), c04("New gap?", "wiki/concepts/mcp.md")])
    assert (out["added"], out["skipped"], out["created"]) == (1, 1, False)
    text = oq(wiki).read_text()
    assert text.startswith(EXISTING.replace("at: 2026-10-28T11:05:00Z", "at: 2026-10-30T14:20:00Z").rstrip("\n"))
    assert "created: 2026-10-28T11:00:00Z" in text
    assert text.endswith("## 2026-10-30\n\n- New gap? — from [MCP](concepts/mcp.md)\n")


def test_same_day_reuses_section_newest_last(wiki: Path):
    run(wiki, [c04("First?")])
    run(wiki, [c04("Second?")], now="2026-10-30T18:00:00Z", name="r2.json")
    text = oq(wiki).read_text()
    assert text.count("## 2026-10-30") == 1
    assert text.index("First?") < text.index("Second?")
    run(wiki, [c04("Third?")], now=LATER, name="r3.json")
    assert oq(wiki).read_text().index("## 2026-10-31") > text.index("Second?")


def test_no_c04_writes_nothing(wiki: Path):
    out = run(wiki, [{"id": "C01", "message": "x"}])
    assert out["added"] == 0 and not oq(wiki).exists()
    oq(wiki).write_text(EXISTING)
    run(wiki, [], now=LATER)
    assert oq(wiki).read_text() == EXISTING


def test_missing_page_falls_back_and_duplicates_in_batch(wiki: Path):
    out = run(wiki, [c04("Gap?", "wiki/concepts/nope.md"), c04("Gap?")])
    assert (out["added"], out["skipped"]) == (1, 1)
    assert "- Gap? — flagged by lint (C04)" in oq(wiki).read_text()
