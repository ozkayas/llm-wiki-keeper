# LINT: the health-check path

Companion to `SKILL.md`. Loaded when Step 1 selected **lint** mode. Lint is the
third operation: ingest adds sources, query adds answers, lint checks that what is
there still holds together.

**Two tiers.** `scripts/lint.py` is deterministic and read-only. `agents/lint_reviewer.md`
is an LLM review for what a script cannot judge, also read-only, one agent per group of pages.
You merge both into one report.

**The write regime** (`CONVENTIONS.md` §13):

| Regime | Pages | In lint mode |
|---|---|---|
| ingest-owned | `raw/`, `sources/`, `entities/`, `concepts/`, `overview.md`, `repos/` | **read-only** |
| interaction-owned | `questions/`, `notes/`, `open-questions.md`, `lint/` | read-only, except the report page and the `open-questions.md` append below |

Lint never edits an ingest-owned or interaction-owned page except the new report
(`wiki/lint/YYYY-MM-DD.md`), `open-questions.md` (append only) and, after an
explicit yes, stub deletion and an index rebuild (L.8). Content findings are never
auto-fixed: they go to the next ingest or to a human edit.

---

## L.1: Locate the wiki

Same as `SKILL.md` Step 0. No wiki: say so and stop. Read `wiki-<slug>/config.yml`
(a missing one means the defaults) and write the report in its `language`.

## L.2: Run the script

```bash
uv run --script .agents/skills/llm-wiki-keeper/scripts/lint.py --wiki-dir wiki-<slug> --json-only 2>/dev/null
```

Keep the JSON: `{findings, summary, config, checked_pages}`. Exit code 1 only means
an `error` exists; it is not a failure of the run. You read this output and nothing
else from the wiki at this point.

### Deterministic checks (`lint.py`)

| id | name | severity | rule |
|---|---|---|---|
| L01 | uncited-prose | warn | On source, entity, concept, overview, note, repo and repo_note pages: a paragraph or list item with no `[^id]` and not a `> Synthesis:` line. Headings, tables, code, footnote definitions, metadata quotes and link-only items are exempt. |
| L02 | empty-stub | error | A `.md` file (outside `raw/` and `.obsidian/`) with no content, or no frontmatter and no body. Typical cause: a click on a hollow link. |
| L03 | stray-outside-bundle | warn | Anything in `wiki-<slug>/` that is not `config.yml`, `raw/`, `wiki/` or `.obsidian/`. |
| L04 | broken-link | error | A relative link or frontmatter wikilink whose target is missing and not promissory (an `entities/` or `concepts/` slug under 2 mentions). Heading anchors are checked. |
| L05 | missing-page | error | A slug with 2 or more mentions and no page. |
| L06 | premature-page | warn | An entity or concept page whose slug has fewer than 2 mentions. |
| L07 | orphan | warn | A page (not index, log, overview) with no inbound link. |
| L08 | stale | warn | `stale_after` reached, or a deprecated page still linked from a live one. Also info: a web or repo page older than `stale_after_days`. |
| L09 | footnote-integrity | error | A `[^id]` without definition, an unused definition, an id missing from `sources[].id`, or a `sources[].resource` pointing at a missing local file. |
| L10 | index-drift | warn | A generated `index.md` that differs from what `build_index_md.py` would write now. |
| L11 | tags-policy | warn | Any `tags` while `config.yml` says `tags: forbidden`. |
| L12 | trust-summary | info | Counts per trust tier (unverified, machine-confirmed, human-reviewed) and per `status`. |
| L13 | conformance | error/warn | The conformance results of `build_index_md.py`, severities kept. |
| L14 | config-missing | info | No `config.yml`: defaults were used. |
| L15 | timestamp-sanity | warn | `created` or `generated.at` in the future, or `created` later than `generated.at`. |

## L.3: Review in groups

Take `checked_pages`. Group them: at most **6 pages per group**, grouped by
directory, `sources/` first (a source page is where claims are most likely to
drift). A directory with more than 6 pages is split in order. Skip `index.md`,
`log.md` and `lint/`.

Spawn one `agents/lint_reviewer.md` per group, in parallel, on a Sonnet-class
model (the spawning rules in `SKILL.md` apply). Pass:

- `group`: the page paths,
- `deterministic_findings`: the findings from L.2 whose `file` is in the group (an empty list is fine),
- `wiki_dir`, and `language` from `config.yml`.

Expect exactly one JSON receipt per reviewer. You never read the pages yourself.

### LLM checks (`lint_reviewer`)

| id | name | severity | rule |
|---|---|---|---|
| C01 | contradiction | warn | Two pages assert incompatible things about the same subject. Both quoted, with paths. |
| C02 | unsupported-claim | warn | A footnoted claim the cited source or raw note does not state. At least 4 claims spot-checked per page. |
| C03 | missing-cross-reference | info | A page names an entity or concept that has a page, without linking it. |
| C04 | data-gap | info | Waiting slugs worth a second source; open questions the current pages now answer (report only). |
| C05 | interpretation-in-prose | warn | Interpretation, comparison or inference stated as sourced fact outside a `> Synthesis:` line. The judgment version of L01. |

## L.4: Merge

1. Concatenate the script findings and every reviewer's `findings`.
2. **Dedupe L01 against C05**: when both name the same file and line (or the same
   passage), keep C05, which carries the better message, and drop the L01.
3. Rank: `error`, then `warn`, then `info`; inside a severity, by file path, then line.
4. Count per severity for the summary. Take the trust-tier counts from L12.

## L.5: Write the report

Run `date -u +%Y-%m-%dT%H:%M:%SZ` once and use it for `created` and `generated.at`;
the file name is its date part. Write `wiki/lint/YYYY-MM-DD.md` per
`.agents/skills/llm-wiki-keeper/PAGES.md § lint_report`. A second run on the same
day overwrites the file (keep `created` of the first run if you can read it from the
old file; otherwise use the new instant). The report cites nothing: it reports.

## L.6: Open questions

Only if there are C04 findings: append them to `wiki/open-questions.md` as dated
bullets, as in `QUERY.md` Q.7 (append-only, bump `generated.at`, creating the file
with `type: open_question` frontmatter on first use). If there are none, do not touch
the file. Nothing else outside `lint/` is written.

## L.7: Log and index

```bash
uv run --script .agents/skills/llm-wiki-keeper/scripts/append_log.py --wiki-dir wiki-<slug> --op Lint \
  --text "Lint: <E> errors, <W> warnings, <I> info across <N> pages. Report: [<YYYY-MM-DD>](lint/<YYYY-MM-DD>.md)."
uv run --script .agents/skills/llm-wiki-keeper/scripts/build_index_md.py --wiki-dir wiki-<slug>
```

The link is relative to `wiki/log.md`. The index rebuild gives `lint/` its generated
`index.md` and lists the new report.

## L.8: Present

Tell the user, briefly:

- counts by severity and the report path,
- the **top 5 findings** (errors first) with their file paths and one line each,
- the fixes you can make **only after a yes**:
  1. delete empty stubs (L02, and empty folders from L03): list them first, delete only what the user confirms,
  2. rebuild the indexes (L10): re-run `build_index_md.py`.

Everything else (L01, C01, C02, C05, missing pages) is for the next ingest or a human
edit. Do not offer to fix it now.
