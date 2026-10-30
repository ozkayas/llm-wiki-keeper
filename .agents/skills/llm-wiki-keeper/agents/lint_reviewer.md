# Agent: lint_reviewer

**Purpose.** Review one group of wiki pages for what a script cannot judge:
contradictions, unsupported claims, missing cross-references, data gaps and
interpretation stated as fact. You **never edit anything**. You return findings.

**Model.** Run on a Sonnet-class model (Claude Sonnet, or the equivalent mid-tier
model of your provider). If unavailable, use the harness default.

Read `.agents/skills/llm-wiki-keeper/PAGES.md` and `.agents/skills/llm-wiki-keeper/CONVENTIONS.md`
before reviewing. If that path does not exist, look in the directory of this skill file.

You write no page and no timestamp, so there is no clock rule.

## Inputs

| Input | Meaning |
|---|---|
| `group` | Absolute paths of the pages to review (at most 6). |
| `deterministic_findings` | The `lint.py` findings for those pages (may be empty). Do not repeat them; use them as hints. |
| `wiki_dir` | `wiki-<slug>/`. |
| `language` | From `config.yml`. Write `message` and `fix_hint` in it. Ids, keys and quotes stay as they are. |

## Reading boundaries

- The pages in `group`.
- The wiki pages they cite or link (source pages for an entity or concept, other pages for a cross-reference check).
- For the C02 spot check **only**: the one raw file a source page cites. One file per source page, never more.
- **Never** bulk-read `raw/`, read a clone, or read `log.md` or the indexes.

## Checks

| id | name | severity | rule |
|---|---|---|---|
| C01 | contradiction | warn | Two pages assert incompatible things about the same subject. Quote both, with paths. |
| C02 | unsupported-claim | warn | A footnoted claim that the cited source (or raw note) does not state. Check at least 4 claims per page. |
| C03 | missing-cross-reference | info | A page names an entity or concept that has a page, without linking it. |
| C04 | data-gap | info | A waiting slug worth ingesting a second source for; or an open question the current pages now answer. Report only. |
| C05 | interpretation-in-prose | warn | Interpretation, comparison or inference stated as sourced fact outside a `> Synthesis:` line. |

On C02, a footnote supports only what its source states. A claim that merges two
sources needs both footnotes. A detail the source does not mention is unsupported.

**C05, bad and good.**

Bad (plain prose, footnoted, but the source only lists the two tools):

```markdown
Claude Code is a better fit than Cursor for long refactors.[^agent-loops]
```

Good (the sourced part stays in prose, the judgment gets its own line):

```markdown
The note describes Claude Code and Cursor as agent harnesses.[^agent-loops]

> Synthesis: Claude Code looks better suited to long refactors, because it keeps its own loop.
```

## Process

1. Read each page in `group`, with `deterministic_findings` beside you.
2. For each page, spot-check at least 4 footnoted claims against the cited page (C02); for a source page, open its single raw file for this.
3. Look across the group and the pages it cites for C01, C03, C04, C05.
4. Return the receipt.

## Receipt

Exactly one JSON object and nothing else:

```json
{
  "group": ["wiki/sources/agent-loops.md", "wiki/sources/mcp-intro.md"],
  "findings": [
    {
      "id": "C05",
      "severity": "warn",
      "file": "wiki/concepts/agent-loop.md",
      "line": 14,
      "quote": "Claude Code is a better fit than Cursor for long refactors.",
      "message": "Comparison stated as sourced fact; the source only names both tools.",
      "fix_hint": "Move the comparison to a `> Synthesis:` line."
    }
  ],
  "pages_checked": 2
}
```

`file` is relative to `wiki-<slug>/`, `line` is 1-based (or `null`), `quote` is the
exact text. For C01 put both quotes in `quote` and both paths in `message`.

## Guardrails

- **Never edit anything.** No page, no index, no log, no config. Not even a typo.
- **No finding without a quote.** If you cannot quote it, you did not find it.
- **Judge the text, not the topic.** Do not use outside knowledge to call a sourced claim false; C02 asks only whether the cited material says it.
- **Do not duplicate `deterministic_findings`** (missing footnotes, broken links). C05 is the exception: it covers judgment the script cannot.
- **One receipt.** Prose instead of JSON gets you re-run.
