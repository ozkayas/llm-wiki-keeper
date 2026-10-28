"""Tests for build_index_md.py, count_mentions.py and append_log.py.

Run from the repo root:  uv run --with pytest --with pyyaml pytest tests/
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / ".agents/skills/llm-wiki-keeper/scripts"
FIXTURE = Path(__file__).resolve().parent / "fixtures/wiki-demo"


def run(script: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True
    )
    if check:
        assert proc.returncode == 0, proc.stderr
    return proc


@pytest.fixture
def wiki(tmp_path: Path) -> Path:
    dest = tmp_path / "wiki-demo"
    shutil.copytree(FIXTURE, dest)
    return dest


def snapshot(bundle: Path) -> dict[str, bytes]:
    return {str(p.relative_to(bundle)): p.read_bytes() for p in sorted(bundle.rglob("index.md"))}


def write_page(wiki: Path, rel: str, text: str) -> Path:
    p = wiki / "wiki" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


GOOD = "---\ntype: note\ntitle: T\ndescription: D\n---\n\nBody\n"


# ------------------------------------------------------------ build index ---


def test_fixture_is_clean(wiki: Path):
    proc = run("build_index_md.py", "--wiki-dir", str(wiki))
    assert proc.stderr == ""
    assert json.loads(proc.stdout)["errors"] == []


def test_index_deterministic_and_restorable(wiki: Path):
    bundle = wiki / "wiki"
    run("build_index_md.py", "--wiki-dir", str(wiki))
    first = snapshot(bundle)
    run("build_index_md.py", "--wiki-dir", str(wiki))
    assert snapshot(bundle) == first
    for p in bundle.rglob("index.md"):
        p.unlink()
    run("build_index_md.py", "--wiki-dir", str(wiki))
    assert snapshot(bundle) == first


def test_okf_version_only_in_root(wiki: Path):
    run("build_index_md.py", "--wiki-dir", str(wiki))
    bundle = wiki / "wiki"
    assert (bundle / "index.md").read_text().startswith('---\nokf_version: "0.2"\n---\n')
    for p in bundle.rglob("index.md"):
        if p != bundle / "index.md":
            assert not p.read_text().startswith("---"), p
            assert "okf_version" not in p.read_text()


def test_entry_format(wiki: Path):
    run("build_index_md.py", "--wiki-dir", str(wiki))
    bundle = wiki / "wiki"
    sources = (bundle / "sources/index.md").read_text()
    assert sources.startswith("# Sources\n\n")
    assert "* [Alpha note](alpha.md) - Summary of the Alpha note raw note.\n" in sources
    root = (bundle / "index.md").read_text()
    assert "* [Concepts](concepts/) - 1 page\n" in root
    assert "* [Repos](repos/) - 1 page\n" in root
    assert "[[" not in root
    assert "index.md" not in sources and "log.md" not in root.replace("log.md)", "")
    assert "* [demo-repo overview](overview.md)" in (bundle / "repos/demo-repo/index.md").read_text()


def test_reserved_files_not_listed(wiki: Path):
    run("build_index_md.py", "--wiki-dir", str(wiki))
    for p in (wiki / "wiki").rglob("index.md"):
        assert "](log.md)" not in p.read_text()
    assert "Log" not in (wiki / "wiki/index.md").read_text()


def test_error_missing_type(wiki: Path):
    write_page(wiki, "notes/bad.md", "---\ntitle: X\ndescription: D\n---\n")
    proc = run("build_index_md.py", "--wiki-dir", str(wiki), check=False)
    assert proc.returncode == 1
    assert "ERROR" in proc.stderr and "type" in proc.stderr


def test_error_no_frontmatter(wiki: Path):
    write_page(wiki, "notes/bare.md", "# Just text\n")
    proc = run("build_index_md.py", "--wiki-dir", str(wiki), check=False)
    assert proc.returncode == 1
    assert "ERROR" in proc.stderr and "bare.md" in proc.stderr


@pytest.mark.parametrize(
    "text,needle",
    [
        ("---\ntype: note\ntitle: T\n---\n", "missing `description`"),
        ("---\ntype: note\ndescription: D\ntimestamp: 2026-10-28T09:00:00Z\n---\n", "superseded by generated.at"),
        ("---\ntype: note\ndescription: D\n---\n# Citations\n", "Citations"),
        ("---\ntype: note\ndescription: D\n---\nSee [[wiki/x]].\n", "wikilink"),
        ("---\ntype: note\ndescription: D\ngenerated: { at: 2026-10-28T09:00:00Z }\n---\n", "generated.by"),
        ("---\ntype: note\ndescription: D\nstatus: wip\n---\n", "status"),
        ("---\ntype: note\ndescription: D\ncreated: 2026-10-28\n---\n", "`created`"),
        ("---\ntype: note\ndescription: D\ncreated: 2026-10-28T09:00:00\n---\n", "`created`"),
        ("---\ntype: note\ndescription: D\nstale_after: 2027-01-01\n---\n", "`stale_after`"),
        ("---\ntype: note\ndescription: D\ngenerated: { by: a/b, at: 2026-10-28 }\n---\n", "generated.at"),
        ("---\ntype: note\ndescription: D\nverified:\n  - { by: bob, at: 2026-10-28T09:00:00Z }\n---\n", "verified[].by"),
        ("---\ntype: note\ndescription: D\nverified:\n  - { by: human:bob, at: 2026-10-28 }\n---\n", "verified[].at"),
    ],
)
def test_warnings_do_not_fail(wiki: Path, text: str, needle: str):
    write_page(wiki, "notes/w.md", text)
    proc = run("build_index_md.py", "--wiki-dir", str(wiki))
    assert f"WARN:" in proc.stderr and needle in proc.stderr
    assert "ERROR" not in proc.stderr


def test_valid_verified_and_offsets_accepted(wiki: Path):
    write_page(
        wiki,
        "notes/ok.md",
        "---\ntype: note\ndescription: D\ncreated: 2026-10-28T09:00:00+02:00\nstatus: draft\n"
        "stale_after: 2027-01-01T00:00:00Z\ngenerated: { by: llm-wiki-keeper/orchestrator, at: 2026-10-28T09:00:00Z }\n"
        "verified:\n  - { by: human:suat, at: 2026-10-28T09:00:00Z }\n  - { by: process:ci, at: 2026-10-28T09:00:00Z }\n"
        "  - { by: some-tool/1.2, at: 2026-10-28T09:00:00Z }\n---\n",
    )
    assert run("build_index_md.py", "--wiki-dir", str(wiki)).stderr == ""


def test_log_warnings(wiki: Path):
    (wiki / "wiki/log.md").write_text(
        "# Log\n\n## 2026-10-01\n* **Query**: a\n\n## 2026-10-02\n* **Query**: b\n\n## Today\n"
    )
    proc = run("build_index_md.py", "--wiki-dir", str(wiki))
    assert "newest first" in proc.stderr
    assert "## YYYY-MM-DD" in proc.stderr
    assert "ERROR" not in proc.stderr


# --------------------------------------------------------- count mentions ---


def mentions(wiki: Path, *extra: str) -> dict:
    return json.loads(run("count_mentions.py", "--wiki-dir", str(wiki), "--json", *extra).stdout)


def test_threshold_new_path_form(wiki: Path):
    out = mentions(wiki)
    assert out["threshold"] == 2
    assert out["qualifying"] == {"entities": ["claude-code", "solo-tool"], "concepts": ["mcp"]}
    assert set(out) == {"wiki_dir", "threshold", "source_like_pages", "entities", "concepts", "qualifying"}


def test_threshold_legacy_wikilink_form(wiki: Path):
    for name in ("alpha", "beta"):
        p = wiki / f"wiki/sources/{name}.md"
        p.write_text(
            p.read_text()
            # v0.1 wikis quoted wikilinks (an unquoted `[[x]]` is a nested YAML list)
            .replace("/entities/claude-code.md", '"[[wiki/entities/legacy-ent]]"')
            .replace("/concepts/mcp.md", '"[[wiki/concepts/legacy-con|label]]"')
        )
    out = mentions(wiki)
    assert "legacy-ent" in out["qualifying"]["entities"]
    assert "legacy-con" in out["qualifying"]["concepts"]


def test_single_mention_does_not_qualify(wiki: Path):
    out = mentions(wiki)
    assert "repo-only" in out["entities"] and "repo-only" not in out["qualifying"]["entities"]


def test_repos_counted(wiki: Path):
    out = mentions(wiki)
    assert "wiki/repos/demo-repo/overview.md" in out["entities"]["solo-tool"]
    assert out["source_like_pages"] == 3


def test_questions_and_notes_not_counted(wiki: Path):
    out = mentions(wiki)
    for slug in ("question-only", "note-only"):
        assert slug not in out["entities"] and slug not in out["concepts"]
    assert all("questions/" not in p and "notes/" not in p for v in out["entities"].values() for p in v)
    assert out["entities"]["claude-code"] == ["wiki/sources/alpha.md", "wiki/sources/beta.md"]


def test_threshold_flag_and_stderr_table(wiki: Path):
    proc = run("count_mentions.py", "--wiki-dir", str(wiki), "--threshold", "3")
    assert "kind" in proc.stderr and "claude-code" in proc.stderr
    assert json.loads(proc.stdout)["qualifying"] == {"entities": [], "concepts": ["mcp"]}


# ------------------------------------------------------------- append log ---


def log(wiki: Path, op: str, text: str, date: str | None = None, check: bool = True):
    args = ["--wiki-dir", str(wiki), "--op", op, "--text", text]
    if date:
        args += ["--date", date]
    return run("append_log.py", *args, check=check)


def test_log_created_when_missing(tmp_path: Path):
    (tmp_path / "wiki").mkdir()
    proc = log(tmp_path, "Creation", "Initialized the wiki.", "2026-10-27")
    assert (tmp_path / "wiki/log.md").read_text() == "# Log\n\n## 2026-10-27\n* **Creation**: Initialized the wiki.\n"
    assert json.loads(proc.stdout)["created"] is True


def test_log_same_day_goes_on_top(wiki: Path):
    log(wiki, "Update", "later entry", "2026-10-28")
    text = (wiki / "wiki/log.md").read_text()
    day = text.split("## 2026-10-28\n")[1].split("\n\n")[0].splitlines()
    assert day[0] == "* **Update**: later entry"
    assert day[1].startswith("* **Query**")


def test_log_new_day_opens_group_under_header(wiki: Path):
    log(wiki, "Lint", "checked `x`", "2026-10-29")
    text = (wiki / "wiki/log.md").read_text()
    assert text.startswith("# Log\n\n## 2026-10-29\n* **Lint**: checked `x`\n\n## 2026-10-28\n")


def test_log_backfill_older_date(wiki: Path):
    log(wiki, "Ingest", "between", "2026-10-27")  # existing group, top
    log(wiki, "Update", "middle", "2026-10-27")
    log(wiki, "Ingest", "ancient", "2026-09-01")  # oldest: appended last
    log(wiki, "Query", "gap", "2026-10-15")  # between 10-27 and 09-01
    text = (wiki / "wiki/log.md").read_text()
    heads = [l[3:] for l in text.splitlines() if l.startswith("## ")]
    assert heads == ["2026-10-28", "2026-10-27", "2026-10-15", "2026-09-01"]
    assert text.index("middle") < text.index("between") < text.index("Initialized")
    assert run("build_index_md.py", "--wiki-dir", str(wiki)).stderr == ""


def log_multi(wiki: Path, op: str, texts: list[str], date: str | None = None):
    args = ["--wiki-dir", str(wiki), "--op", op]
    for t in texts:
        args += ["--text", t]
    if date:
        args += ["--date", date]
    return run("append_log.py", *args)


def test_log_multi_bullet_order(tmp_path: Path):
    (tmp_path / "wiki").mkdir()
    proc = log_multi(tmp_path, "Ingest", ["one", "two\nlines", "three"], "2026-10-27")
    assert (tmp_path / "wiki/log.md").read_text() == (
        "# Log\n\n## 2026-10-27\n* **Ingest**: one\n* **Ingest**: two lines\n* **Ingest**: three\n"
    )
    assert json.loads(proc.stdout)["bullets"] == 3


def test_log_multi_bullet_existing_day(wiki: Path):
    log_multi(wiki, "Update", ["a", "b"], "2026-10-28")
    day = (wiki / "wiki/log.md").read_text().split("## 2026-10-28\n")[1].split("\n\n")[0].splitlines()
    assert day[:2] == ["* **Update**: a", "* **Update**: b"]
    assert day[2].startswith("* **Query**")


def test_log_multi_bullet_backfill(wiki: Path):
    log_multi(wiki, "Ingest", ["x", "y"], "2026-09-01")
    text = (wiki / "wiki/log.md").read_text()
    assert text.rstrip().endswith("## 2026-09-01\n* **Ingest**: x\n* **Ingest**: y")
    log_multi(wiki, "Lint", ["p", "q"], "2026-10-15")
    heads = [l[3:] for l in (wiki / "wiki/log.md").read_text().splitlines() if l.startswith("## ")]
    assert heads == ["2026-10-28", "2026-10-27", "2026-10-15", "2026-09-01"]


def test_log_single_bullet_unchanged(tmp_path: Path):
    (tmp_path / "wiki").mkdir()
    proc = log(tmp_path, "Query", "  spaced\n out ", "2026-10-27")
    assert (tmp_path / "wiki/log.md").read_text() == "# Log\n\n## 2026-10-27\n* **Query**: spaced out\n"
    out = json.loads(proc.stdout)
    assert out["entry"] == "* **Query**: spaced out" and out["bullets"] == 1


def test_log_default_date_is_today(tmp_path: Path):
    from datetime import date

    (tmp_path / "wiki").mkdir()
    out = json.loads(log(tmp_path, "Query", "q").stdout)
    assert out["date"] == date.today().isoformat()


def test_log_rejects_unknown_op(wiki: Path):
    proc = log(wiki, "Bogus", "x", check=False)
    assert proc.returncode != 0
    assert "unknown --op" in proc.stderr and "Ingest" in proc.stderr
