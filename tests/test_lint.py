"""Tests for lint.py (MIGRATION-OKF-0.2.md section 16.1, checks L01-L15).

Run from the repo root:  uv run --with pytest --with pyyaml pytest tests/

`fixtures/wiki-lint-clean` is a wiki that lints with no error and no warning (only the L12 info line).
`fixtures/wiki-demo` is NOT clean on purpose (hollow links, a missing page, an uncited note, a
broken raw anchor); one test pins what lint says about it. Every defect test copies the clean
fixture to a tmp dir, injects exactly one defect and asserts the finding id appears there
and not in the clean copy.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LINT = ROOT / ".agents/skills/llm-wiki-keeper/scripts/lint.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLEAN = FIXTURES / "wiki-lint-clean"
DEMO = FIXTURES / "wiki-demo"
NOW = "2026-10-30T00:00:00Z"


def lint(wiki: Path, *extra: str, now: str | None = NOW, json_only: bool = True):
    args = [sys.executable, str(LINT), "--wiki-dir", str(wiki)]
    if now:
        args += ["--now", now]
    if json_only:
        args.append("--json-only")
    proc = subprocess.run([*args, *extra], capture_output=True, text=True)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"no JSON on stdout: {proc.stdout!r} / {proc.stderr!r}")
    return proc, data


def ids(data) -> set[str]:
    return {f["id"] for f in data["findings"]}


def of(data, fid: str) -> list[dict]:
    return [f for f in data["findings"] if f["id"] == fid]


@pytest.fixture
def wiki(tmp_path: Path) -> Path:
    dest = tmp_path / "wiki-lint-clean"
    shutil.copytree(CLEAN, dest)
    return dest


def edit(wiki: Path, rel: str, old: str, new: str) -> Path:
    p = wiki / rel
    text = p.read_text()
    assert old in text, f"{old!r} not in {rel}"
    p.write_text(text.replace(old, new, 1))
    return p


def write(wiki: Path, rel: str, text: str) -> Path:
    p = wiki / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def page(type_: str = "note", extra_fm: str = "", body: str = "Body text.") -> str:
    return (
        f"---\ntype: {type_}\ntitle: T\ndescription: D\ncreated: 2026-10-28T09:00:00Z\n"
        f"generated: {{ by: llm-wiki-keeper/orchestrator, at: 2026-10-28T09:00:00Z }}\n{extra_fm}---\n\n{body}\n"
    )


def assert_only_defect(wiki: Path, fid: str, baseline=None):
    """The clean copy has no `fid`; after the edit it does."""
    _, data = lint(wiki)
    assert fid in ids(data), data["findings"]
    return data


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        h.update(str(p.relative_to(root)).encode())
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


# ------------------------------------------------------------ baseline ---


def test_clean_fixture_has_only_the_trust_summary(wiki: Path):
    proc, data = lint(wiki)
    assert proc.returncode == 0
    assert ids(data) == {"L12"}
    assert data["summary"] == {"error": 0, "warn": 0, "info": 1}


def test_clean_fixture_has_zero_l01_and_documented_demo_has_one(wiki: Path):
    # wiki-demo's notes/scratch.md ("Nothing here.") is real uncited prose, so demo is not L01-clean;
    # the clean fixture exists for that reason.
    _, clean = lint(wiki)
    _, demo = lint(DEMO)
    assert of(clean, "L01") == []
    assert [f["file"] for f in of(demo, "L01")] == ["wiki/notes/scratch.md"]


def test_demo_fixture_findings_are_pinned():
    proc, data = lint(DEMO)
    assert proc.returncode == 1
    assert {"L04", "L05", "L07", "L01", "L12", "L14"} <= ids(data)
    assert [f["file"] for f in of(data, "L05")] == ["wiki/entities/solo-tool.md"]
    assert [f["id"] for f in of(data, "L14")] == ["L14"]


# -------------------------------------------------------- output contract ---


def test_json_shape(wiki: Path):
    _, data = lint(wiki)
    assert set(data) == {"findings", "summary", "config", "checked_pages", "pages"}
    assert set(data["summary"]) == {"error", "warn", "info"}
    assert data["config"]["tags"] == "optional" and data["config"]["stale_after_days"] == 60
    assert data["checked_pages"] == 7
    for f in data["findings"]:
        assert set(f) == {"id", "severity", "file", "line", "message", "fix_hint"}
        assert f["severity"] in {"error", "warn", "info"}


def test_exit_code_1_on_error_0_otherwise(wiki: Path):
    assert lint(wiki)[0].returncode == 0
    write(wiki, "wiki/entities/ghost.md", "")
    proc, data = lint(wiki)
    assert proc.returncode == 1 and data["summary"]["error"] >= 1


def test_warnings_alone_do_not_fail(wiki: Path):
    write(wiki, "wiki/notes/loose.md", page("note", body="Plain unsourced text."))
    proc, data = lint(wiki)
    assert proc.returncode == 0 and data["summary"]["warn"] >= 1


def test_stderr_table_and_json_only(wiki: Path):
    write(wiki, "wiki/entities/ghost.md", "")
    proc, _ = lint(wiki, json_only=False)
    assert "L02" in proc.stderr and "error" in proc.stderr
    proc, _ = lint(wiki, json_only=True)
    assert proc.stderr == ""


def test_findings_sorted_by_severity_file_line_id(wiki: Path):
    write(wiki, "wiki/entities/ghost.md", "")
    write(wiki, "wiki/notes/loose.md", page("note", body="Plain unsourced text."))
    _, data = lint(wiki)
    rank = {"error": 0, "warn": 1, "info": 2}
    keys = [(rank[f["severity"]], f["file"] or "", f["line"] or 0, f["id"]) for f in data["findings"]]
    assert keys == sorted(keys)


def test_deterministic_output(wiki: Path):
    write(wiki, "wiki/notes/loose.md", page("note", body="Plain unsourced text."))
    a = lint(wiki)[0].stdout
    b = lint(wiki)[0].stdout
    assert a == b


def test_lint_writes_nothing(wiki: Path):
    write(wiki, "wiki/entities/ghost.md", "")
    edit(wiki, "wiki/concepts/index.md", "MCP", "Changed")  # index drift: lint must not repair it
    before = tree_hash(wiki)
    lint(wiki)
    lint(wiki, json_only=False)
    assert tree_hash(wiki) == before


def test_not_a_wiki_dir(tmp_path: Path):
    proc = subprocess.run([sys.executable, str(LINT), "--wiki-dir", str(tmp_path)], capture_output=True, text=True)
    assert proc.returncode != 0 and "not a wiki dir" in proc.stderr


def test_bad_now_rejected(wiki: Path):
    proc = subprocess.run([sys.executable, str(LINT), "--wiki-dir", str(wiki), "--now", "yesterday"], capture_output=True, text=True)
    assert proc.returncode != 0


# ------------------------------------------------------------------ L01 ---


def test_l01_uncited_paragraph_reports_line_and_80_chars(wiki: Path):
    long = "An unsourced statement " * 6
    p = wiki / "wiki/concepts/mcp.md"
    text = p.read_text()
    p.write_text(text.replace("[^alpha]: [Alpha", f"{long.strip()}\n\n[^alpha]: [Alpha", 1))
    _, data = lint(wiki)
    (f,) = of(data, "L01")
    assert f["file"] == "wiki/concepts/mcp.md"
    assert f["line"] == p.read_text().splitlines().index(long.strip()) + 1
    assert f["message"] == f'uncited prose: "{" ".join(long.split())[:80]}"'


def test_l01_each_list_item_is_its_own_unit(wiki: Path):
    p = edit(wiki, "wiki/concepts/mcp.md", "\n[^alpha]:", "\n- cited item.[^alpha]\n- bare item one\n- bare item two\n\n[^alpha]:")
    _, data = lint(wiki)
    found = of(data, "L01")
    assert [f["message"] for f in found] == ['uncited prose: "bare item one"', 'uncited prose: "bare item two"']
    lines = p.read_text().splitlines()
    assert [f["line"] for f in found] == [lines.index("- bare item one") + 1, lines.index("- bare item two") + 1]


def test_l01_multiline_paragraph_is_one_unit(wiki: Path):
    edit(wiki, "wiki/concepts/mcp.md", "\n[^alpha]:", "\nFirst line has nothing\nsecond line has the cite.[^beta]\n\n[^alpha]:")
    _, data = lint(wiki)
    assert of(data, "L01") == []
    edit(wiki, "wiki/concepts/mcp.md", "has the cite.[^beta]", "has no cite")
    _, data = lint(wiki)
    assert len(of(data, "L01")) == 1


def test_l01_exemptions(wiki: Path):
    body = """
# Heading

| a | b |
|---|---|
| x | y |

```python
not prose, no cite
```

```mermaid
graph TD; A-->B
```

* [Alpha](../sources/alpha.md)
* [Beta](../sources/beta.md), [Claude Code](../entities/claude-code.md)

> Synthesis: both sources agree.
> Clone: https://example.com/x.git
> Commit: abc123

> Clone: https://example.com/y.git

Cited.[^alpha]

[^alpha]: [Alpha note](../sources/alpha.md)
    continuation of the definition
[^beta]: [Beta note](../sources/beta.md)
"""
    write(wiki, "wiki/concepts/mcp.md", (wiki / "wiki/concepts/mcp.md").read_text().split("---\n\n# MCP")[0] + "---\n" + body + "Servers.[^beta]\n")
    _, data = lint(wiki)
    assert of(data, "L01") == [], of(data, "L01")


def test_l01_definition_blockquote_after_h1_is_exempt(wiki: Path):
    edit(wiki, "wiki/concepts/mcp.md", "# MCP\n\n", "# MCP\n\n> An open protocol for tool access.\n\n")
    _, data = lint(wiki)
    assert of(data, "L01") == [], of(data, "L01")


def test_l01_second_blockquote_still_fails(wiki: Path):
    edit(wiki, "wiki/concepts/mcp.md", "\n[^alpha]:", "\n> An open protocol for tool access.\n\n> It is the best protocol.\n\n[^alpha]:")
    _, data = lint(wiki)
    found = of(data, "L01")
    assert len(found) == 1 and "best protocol" in found[0]["message"]


def test_l01_two_line_first_blockquote_fails(wiki: Path):
    edit(wiki, "wiki/concepts/mcp.md", "\n[^alpha]:", "\n> Line one.\n> Line two.\n\n[^alpha]:")
    _, data = lint(wiki)
    assert len(of(data, "L01")) == 1


def test_l01_relationship_bullet_with_claim_fails_link_only_passes(wiki: Path):
    edit(wiki, "wiki/concepts/mcp.md", "\n[^alpha]:",
         "\n## Relationships\n\n- **MCP**: the delivery mechanism through which memory tools reach the agent. [MCP](../concepts/mcp.md)\n\n[^alpha]:")
    _, data = lint(wiki)
    assert len(of(data, "L01")) == 1
    edit(wiki, "wiki/concepts/mcp.md", "- **MCP**: the delivery mechanism through which memory tools reach the agent. [MCP](../concepts/mcp.md)",
         "- [MCP](../concepts/mcp.md)\n- [Claude Code](../entities/claude-code.md)")
    _, data = lint(wiki)
    assert of(data, "L01") == [], of(data, "L01")


def test_l01_skips_question_and_unchecked_types(wiki: Path):
    write(wiki, "wiki/questions/q2.md", page("question", body="No footnote here."))
    write(wiki, "wiki/notes/log-link.md", page("open_question", body="Nothing cited."))
    _, data = lint(wiki)
    assert of(data, "L01") == []


# ------------------------------------------------------------------ L02 ---


def test_l02_empty_stub(wiki: Path):
    write(wiki, "wiki/entities/ghost.md", "  \n\n")
    _, data = lint(wiki)
    (f,) = of(data, "L02")
    assert f["severity"] == "error" and f["file"] == "wiki/entities/ghost.md"


def test_l02_ignores_raw_and_obsidian_and_scans_outside_bundle(wiki: Path):
    write(wiki, "raw/empty.md", "")
    write(wiki, ".obsidian/x.md", "")
    _, data = lint(wiki)
    assert "L02" not in ids(data)
    write(wiki, "entities/stub.md", "")  # outside wiki/, inside wiki-<slug>/
    _, data = lint(wiki)
    assert [f["file"] for f in of(data, "L02")] == ["entities/stub.md"]


# ------------------------------------------------------------------ L03 ---


def test_l03_stray_outside_bundle(wiki: Path):
    (wiki / "entities").mkdir()
    write(wiki, "scratch.txt", "x")
    _, data = lint(wiki)
    assert sorted(f["file"] for f in of(data, "L03")) == ["entities", "scratch.txt"]
    assert all(f["severity"] == "warn" for f in of(data, "L03"))


# ------------------------------------------------------------------ L04 ---


def test_l04_broken_relative_link(wiki: Path):
    edit(wiki, "wiki/overview.md", "entities/claude-code.md)", "sources/nope.md)")
    _, data = lint(wiki)
    (f,) = of(data, "L04")
    assert f["severity"] == "error" and f["file"] == "wiki/overview.md" and f["line"] == 15


def test_l04_promissory_link_is_allowed_but_hollow_link_with_2_mentions_is_not(wiki: Path):
    edit(wiki, "wiki/overview.md", "entities/claude-code.md)", "entities/future-tool.md)")
    _, data = lint(wiki)
    assert "L04" not in ids(data)
    # two source pages now mention it: no longer promissory (L05 fires too)
    for src in ("alpha", "beta"):
        edit(wiki, f"wiki/sources/{src}.md", 'entities:\n', 'entities:\n  - "[[entities/future-tool]]"\n')
    _, data = lint(wiki)
    assert {"L04", "L05"} <= ids(data)


def test_l04_broken_frontmatter_wikilink(wiki: Path):
    edit(wiki, "wiki/questions/what-is-mcp.md", "entities:", 'related: "[[sources/gone]]"\nentities:')
    _, data = lint(wiki)
    (f,) = of(data, "L04")
    assert f["file"] == "wiki/questions/what-is-mcp.md" and "[[sources/gone]]" in f["message"] and f["line"] == 7


def test_l04_legacy_reference_forms_resolve(wiki: Path):
    edit(wiki, "wiki/questions/what-is-mcp.md", "entities:", 'related:\n  - "/concepts/mcp.md"\n  - "[[wiki/concepts/mcp|MCP]]"\nentities:')
    _, data = lint(wiki)
    assert "L04" not in ids(data)


def test_l04_heading_anchor_checked_against_heading_text(wiki: Path):
    edit(wiki, "wiki/sources/alpha.md", "raw/alpha.md#Rebuild", "raw/alpha.md#Missing%20Part")
    _, data = lint(wiki)
    assert any("anchor" in f["message"] for f in of(data, "L04"))


def test_l04_percent_encoded_anchor_matches_heading(wiki: Path):
    (wiki / "raw/alpha.md").write_text("# Alpha note\n\n## Rebuild\nx\n\n## 6. Building the Server\ny\n")
    edit(wiki, "wiki/sources/alpha.md", "raw/alpha.md#Rebuild", "raw/alpha.md#6.%20Building%20the%20Server")
    _, data = lint(wiki)
    assert "L04" not in ids(data)


# ------------------------------------------------------------------ L05 ---


def test_l05_missing_page_with_two_mentions(wiki: Path):
    for src in ("alpha", "beta"):
        edit(wiki, f"wiki/sources/{src}.md", "concepts:\n", 'concepts:\n  - "[[concepts/rising]]"\n')
    _, data = lint(wiki)
    (f,) = of(data, "L05")
    assert f["severity"] == "error" and f["file"] == "wiki/concepts/rising.md"


def test_l05_questions_and_notes_do_not_count(wiki: Path):
    write(wiki, "wiki/notes/n.md", page("note", 'entities:\n  - "[[entities/never]]"\n'))
    write(wiki, "wiki/questions/q2.md", page("question", 'entities:\n  - "[[entities/never]]"\n'))
    _, data = lint(wiki)
    assert "L05" not in ids(data)


# ------------------------------------------------------------------ L06 ---


def test_l06_premature_page(wiki: Path):
    write(wiki, "wiki/entities/lonely.md", page("entity"))
    _, data = lint(wiki)
    assert [f["file"] for f in of(data, "L06")] == ["wiki/entities/lonely.md"]


# ------------------------------------------------------------------ L07 ---


def test_l07_orphan(wiki: Path):
    write(wiki, "wiki/notes/loose.md", page("note", body="Plain.[^x]\n\n[^x]: y").replace("---\n\nPlain", 'sources:\n  - id: x\n    resource: https://example.com\n---\n\nPlain', 1))
    _, data = lint(wiki)
    assert [f["file"] for f in of(data, "L07")] == ["wiki/notes/loose.md"]


def test_l07_index_links_do_not_count_log_links_do(wiki: Path):
    # what-is-mcp is only linked from log.md in the clean fixture and is not an orphan
    assert "L07" not in ids(lint(wiki)[1])
    edit(wiki, "wiki/log.md", "[What is MCP?](questions/what-is-mcp.md)", "What is MCP?")
    assert [f["file"] for f in of(lint(wiki)[1], "L07")] == ["wiki/questions/what-is-mcp.md"]


# ------------------------------------------------------------------ L08 ---


def test_l08_stale_after_passed(wiki: Path):
    edit(wiki, "wiki/concepts/mcp.md", "sources:", "stale_after: 2026-10-29T00:00:00Z\nsources:")
    _, data = lint(wiki)
    (f,) = of(data, "L08")
    assert f["severity"] == "warn" and f["file"] == "wiki/concepts/mcp.md"
    # not yet stale at an earlier --now
    assert "L08" not in ids(lint(wiki, now="2026-10-28T00:00:00Z")[1])


def test_l08_deprecated_page_still_linked(wiki: Path):
    edit(wiki, "wiki/concepts/mcp.md", "sources:", "status: deprecated\nsources:")
    _, data = lint(wiki)
    files = {f["file"] for f in of(data, "L08")}
    assert "wiki/entities/claude-code.md" in files and "wiki/concepts/mcp.md" not in files


def test_l08_old_web_or_repo_source_is_info(wiki: Path):
    assert "L08" not in ids(lint(wiki)[1])
    _, data = lint(wiki, now="2027-06-01T00:00:00Z")
    (f,) = of(data, "L08")
    assert f["severity"] == "info" and f["file"] == "wiki/repos/demo-repo/overview.md"


# ------------------------------------------------------------------ L09 ---


def test_l09_reference_without_definition(wiki: Path):
    edit(wiki, "wiki/overview.md", "Claude Code](entities/claude-code.md).[^alpha]", "Claude Code](entities/claude-code.md).[^alpha][^alpha2]")
    _, data = lint(wiki)
    msgs = [f["message"] for f in of(data, "L09")]
    assert any("alpha2" in m and "no definition" in m for m in msgs)


def test_l09_definition_never_used(wiki: Path):
    p = wiki / "wiki/overview.md"
    p.write_text(p.read_text() + "[^extra]: [x](sources/alpha.md)\n")
    _, data = lint(wiki)
    assert any("never used" in f["message"] and "extra" in f["message"] for f in of(data, "L09"))


def test_l09_id_missing_from_sources(wiki: Path):
    edit(wiki, "wiki/overview.md", "    title: Alpha note\n", "    title: Alpha note\n  - id: other\n    resource: sources/beta.md\n")
    edit(wiki, "wiki/overview.md", "- id: alpha", "- id: renamed")
    _, data = lint(wiki)
    assert any("not in sources[].id" in f["message"] for f in of(data, "L09"))


def test_l09_missing_local_resource(wiki: Path):
    edit(wiki, "wiki/sources/beta.md", "../../raw/beta.md\n", "../../raw/nope.md\n")
    _, data = lint(wiki)
    (f,) = [f for f in of(data, "L09") if "missing local file" in f["message"]]
    assert f["file"] == "wiki/sources/beta.md" and f["line"] == 9


# ------------------------------------------------------------------ L10 ---


def test_l10_index_drift(wiki: Path):
    edit(wiki, "wiki/concepts/index.md", "Protocol connecting agents to tools.", "Edited by hand.")
    _, data = lint(wiki)
    (f,) = of(data, "L10")
    assert f["severity"] == "warn" and f["file"] == "wiki/concepts/index.md" and f["line"] == 3


def test_l10_missing_index_and_new_page(wiki: Path):
    (wiki / "wiki/sources/index.md").unlink()
    _, data = lint(wiki)
    assert [f["file"] for f in of(data, "L10")] == ["wiki/sources/index.md"]


# ------------------------------------------------------------------ L11 ---


def test_l11_tags_forbidden(wiki: Path):
    edit(wiki, "wiki/concepts/mcp.md", "sources:", "tags: [a]\nsources:")
    assert "L11" not in ids(lint(wiki)[1])  # optional: allowed
    (wiki / "config.yml").write_text("language: en\ntags: forbidden\nstale_after_days: 60\n")
    _, data = lint(wiki)
    assert [f["file"] for f in of(data, "L11")] == ["wiki/concepts/mcp.md"]


# ------------------------------------------------------------------ L12 ---


def test_l12_trust_and_status_counts(wiki: Path):
    edit(wiki, "wiki/concepts/mcp.md", "sources:", "status: draft\nverified:\n  - { by: 'human:suat', at: 2026-10-29T00:00:00Z }\nsources:")
    edit(wiki, "wiki/entities/claude-code.md", "sources:", "verified:\n  - { by: 'process:checker', at: 2026-10-29T00:00:00Z }\nsources:")
    _, data = lint(wiki)
    (f,) = of(data, "L12")
    assert f["severity"] == "info"
    assert "unverified 5, machine-confirmed 1, human-reviewed 1" in f["message"] and "draft 1" in f["message"] and "stable 6" in f["message"]


# ------------------------------------------------------------------ L13 ---


def test_l13_conformance_error_and_warn_merged(wiki: Path):
    edit(wiki, "wiki/concepts/mcp.md", "type: concept\n", "")
    edit(wiki, "wiki/entities/claude-code.md", "created:", "timestamp: 2026-10-28T09:00:00Z\ncreated:")
    _, data = lint(wiki)
    by = {(f["file"], f["severity"]) for f in of(data, "L13")}
    assert ("wiki/concepts/mcp.md", "error") in by and ("wiki/entities/claude-code.md", "warn") in by


# ------------------------------------------------------------------ L14 ---


def test_l14_config_missing(wiki: Path):
    (wiki / "config.yml").unlink()
    proc, data = lint(wiki)
    (f,) = of(data, "L14")
    assert f["severity"] == "info" and proc.returncode == 0
    assert data["config"]["source"] == "defaults"


# ------------------------------------------------------------------ L15 ---


def test_l15_future_timestamps(wiki: Path):
    edit(wiki, "wiki/concepts/mcp.md", "created: 2026-10-28T09:00:00Z", "created: 2026-12-01T09:00:00Z")
    _, data = lint(wiki)
    msgs = [f["message"] for f in of(data, "L15")]
    assert any("`created` is in the future" in m for m in msgs)


def test_l15_created_after_generated_at(wiki: Path):
    edit(wiki, "wiki/concepts/mcp.md", "created: 2026-10-28T09:00:00Z", "created: 2026-10-28T10:00:00Z")
    _, data = lint(wiki)
    (f,) = of(data, "L15")
    assert "later than" in f["message"] and f["severity"] == "warn"


# --- lint report self-errors, overview Index/Health, `pages` (MIGRATION section 18) ---


def test_json_pages_is_sorted_list_of_checked_pages(wiki: Path):
    _, data = lint(wiki)
    assert data["pages"] == sorted(data["pages"])
    assert data["checked_pages"] == len(data["pages"])
    assert "wiki/sources/alpha.md" in data["pages"]
    assert not any(p.endswith("index.md") or p.endswith("log.md") for p in data["pages"])


REPORT_BODY = """
# Lint report

- **L09**: `[^id]` is referenced but has no definition. Fix: add `[^id]: [title](path)`.
- **L04**: broken link `[x](sources/y.md)`.

```markdown
Fenced: [^other] and [z](sources/none.md)
```
"""


def test_report_page_with_code_quoted_syntax_has_no_l04_l09(wiki: Path):
    write(wiki, "wiki/lint/2026-10-30.md", page("lint_report", body=REPORT_BODY))
    _, data = lint(wiki)
    bad = [f for f in data["findings"] if f["id"] in ("L04", "L09", "L01") and f["file"] == "wiki/lint/2026-10-30.md"]
    assert bad == [], bad


def test_l04_ignores_links_in_code_spans_and_fences_on_any_page(wiki: Path):
    write(wiki, "wiki/notes/scratch.md", page("note", body="Sample `[x](sources/nope.md)` text.[^alpha]\n\n```\n[y](sources/nope2.md)\n```\n\n[^alpha]: [Alpha](../sources/alpha.md)"))
    _, data = lint(wiki)
    assert [f for f in of(data, "L04") if f["file"] == "wiki/notes/scratch.md"] == []


def test_l09_still_fires_on_bare_footnote_in_a_normal_page(wiki: Path):
    write(wiki, "wiki/notes/scratch.md", page("note", body="Bare [^ghost] ref."))
    _, data = lint(wiki)
    assert any(f["file"] == "wiki/notes/scratch.md" for f in of(data, "L09"))


def test_l09_skips_lint_report_pages_entirely(wiki: Path):
    write(wiki, "wiki/lint/2026-10-30.md", page("lint_report", body="Bare [^ghost] ref.\n\n[^unused]: x"))
    _, data = lint(wiki)
    assert [f for f in of(data, "L09") if f["file"].startswith("wiki/lint/")] == []


def test_l01_overview_index_and_health_items_exempt_but_theme_prose_not(wiki: Path):
    p = wiki / "wiki/overview.md"
    p.write_text(p.read_text().replace("[^alpha]: [Alpha note](sources/alpha.md)", "") + """
Uncited theme sentence.

## Index

### Entities (1)
- [Claude Code](entities/claude-code.md) - A coding agent harness.

## Health

- Sources: 2 · Entities: 1 · Concepts: 1
- Slugs waiting: [mongosh](entities/mongosh.md)

[^alpha]: [Alpha note](sources/alpha.md)
""")
    _, data = lint(wiki)
    lines = [f["line"] for f in of(data, "L01") if f["file"] == "wiki/overview.md"]
    assert len(lines) == 1, of(data, "L01")


def test_l01_index_item_shape_exempt_only_in_index_section(wiki: Path):
    body = """
## Index

- [Alpha](../sources/alpha.md) - A short description.
- [Beta](../sources/beta.md) — Another description.
- [Beta](../sources/beta.md) with a loose claim in an index.

## Other

- [Alpha](../sources/alpha.md) - Same shape outside an Index section.
"""
    write(wiki, "wiki/notes/scratch.md", page("note", body=body))
    _, data = lint(wiki)
    msgs = [f["message"] for f in of(data, "L01") if f["file"] == "wiki/notes/scratch.md"]
    assert len(msgs) == 2, msgs
    assert any("loose claim" in m for m in msgs) and any("Same shape" in m for m in msgs)


def test_l01_raw_pointer_and_attributed_quote_exempt(wiki: Path):
    body = """
> [Raw](../../raw/alpha.md) · local

> "A verbatim sentence."
> — [Heading](../../raw/alpha.md#Heading)

> "A quote with no attribution link."
"""
    write(wiki, "wiki/notes/scratch.md", page("note", body=body))
    _, data = lint(wiki)
    msgs = [f["message"] for f in of(data, "L01") if f["file"] == "wiki/notes/scratch.md"]
    assert len(msgs) == 1 and "no attribution" in msgs[0], msgs
