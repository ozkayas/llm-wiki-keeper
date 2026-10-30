# Migration to OKF v0.2: decisions

Decision record for moving the skill from OKF v0.1 (upstream) to OKF v0.2.
Spec read: `GoogleCloudPlatform/open-knowledge-format` `SPEC.md` ("Version 0.2", last commit 2026-08-21).
A local copy used while working is not part of this repo; section numbers (§) below refer to that SPEC.

Everything here is **binding** for the files that implement it. Where the old text of a file
contradicts this document, this document wins.

## 1. What the user decided (2026-10-28)

| Topic | Decision |
|---|---|
| Name | `llm-wiki-keeper` |
| Links | Standard markdown links, not `[[wikilinks]]`. Must still render in Obsidian (graph + backlinks). |
| Log order | OKF standard: newest first. |
| `tags` | Optional (OKF's own position). The old "no `tags:` anywhere" ban is dropped. |
| Preferences | Asked once on first run, stored in `wiki-<slug>/config.yml` (§7). |
| Lint | Separate later phase. Not part of this migration, but nothing here may block it. |

## 2. Layout changes

```
wiki-<slug>/
├── config.yml          # NEW. User preferences. Outside the bundle: not an OKF concept.
├── raw/                # unchanged, immutable
└── wiki/               # the OKF bundle
    ├── index.md        # GENERATED. Only file with frontmatter: okf_version: "0.2"
    ├── log.md          # MOVED here from wiki-<slug>/log.md (reserved name inside the bundle)
    ├── overview.md
    ├── sources/ entities/ concepts/ repos/ questions/ notes/
    └── open-questions.md
```

`index.md` and `log.md` are reserved filenames (§3.1). `config.yml` is not markdown and lives next to `raw/`.

## 3. Frontmatter (every page in `wiki/` except `index.md` and `log.md`)

```yaml
---
type: source                       # REQUIRED (OKF). Existing values kept: source, entity, concept, overview, repo, question, note, open_question
title: ...                         # required by this skill
description: One sentence.         # required by this skill; the only thing the index shows
created: 2026-10-28T09:00:00Z      # producer-defined key, preserved across rewrites (OKF allows extra keys)
generated: { by: llm-wiki-keeper/source_writer, at: 2026-10-28T09:00:00Z }
sources: [...]                     # see §4
entities:                          # unchanged meaning (the >=2 threshold); values are quoted wikilinks, see §14
  - "[[entities/claude-code]]"
concepts:
  - "[[concepts/mcp]]"
status: stable                     # optional: draft | stable | deprecated. Absent means stable.
stale_after: 2027-01-01T00:00:00Z  # optional, absolute instant. Writers omit it unless the source is time-sensitive.
tags: [a, b]                       # optional. Writers never invent tags (config tags: optional).
---
```

Rules:

- `timestamp` is **removed**; `generated.at` replaces it (§13.1). `generated.at` is bumped on every meaningful change; `created` never changes.
- `generated.by` follows the actor convention (§7): `llm-wiki-keeper/<agent>`, where `<agent>` is `source_writer`, `repo_writer`, `page_writer`, `overview_writer`, or `orchestrator` for pages the query path writes.
- `verified` is **never written by an LLM writer.** It records a human or a process confirming content. Only a person (`human:<id>`) or a named process may add it. A writer that adds `verified` is lying about trust.
- All timestamps are ISO 8601 with an explicit offset; this skill writes `Z` (UTC): `date -u +%Y-%m-%dT%H:%M:%SZ`.
- Quote any YAML value containing `: ` (unchanged from upstream).
- Unknown keys must be preserved when a page is rewritten (OKF §4.1).

## 4. Provenance: `sources` and footnotes (replaces `# Citations` and `[[raw/x#h|cite]]`)

`sources` is a frontmatter list; each entry has `resource` (required) and optionally `id`, `title`, `author`, `last_modified`.
`usage_count` / `usage_window` are not used by this skill.

**Source page** (written from one raw file): one entry for the raw file.

```yaml
sources:
  - id: raw
    resource: ../../raw/my-note.md       # relative to the page; raw/ lives outside wiki/
    title: My note
```

Per-claim attribution in the body is a footnote whose label is a `sources[].id`:

```markdown
The index is rebuilt after every ingest.[^raw]

[^raw]: [My note, "Rebuild"](../../raw/my-note.md#Rebuild)
```

The label is the join key into `sources`. Put the heading anchor in the footnote text, not in the label.
Several claims from the same raw file reuse `[^raw]`.

**Entity / concept / repo / overview pages** (written from other wiki pages): one `sources` entry per source-like page
it draws from, `id` = that page's slug, `resource` = relative path to it:

```yaml
sources:
  - id: my-note
    resource: ../sources/my-note.md
    title: My note
```

and claims use `[^my-note]`. LLM judgment stays on its own line prefixed `> Synthesis:` and carries no footnote.

**Article sources** (fetched URL): the `sources` entry for the raw file may also carry the original URL as
a second entry `{ id: web, resource: https://..., title: ..., author: ..., last_modified: <published date if known> }`.
Repo pages: `{ id: repo, resource: https://github.com/<owner>/<repo>/tree/<sha>, title: ... }`; code claims keep their permalink style.

## 5. Links: standard markdown, relative

- **Wiki to wiki and wiki to raw:** standard markdown links with a **relative path** and the `.md` extension:
  `[MCP](../concepts/mcp.md)`, `[note](../../raw/my-note.md#Heading%20Text)`.
  Why relative and not OKF's recommended bundle-absolute `/concepts/mcp.md`: Obsidian resolves `/` against the vault
  root, and the vault is often the project root, not `wiki/`. A relative link works from either.
- **Frontmatter reference keys** (`entities`, `concepts`, ...) hold quoted wikilinks, not paths. Superseded by §14.
- **Promissory links** are allowed: a link to `../concepts/<slug>.md` before the page exists. OKF §6.1 tolerates
  broken links. Slug discipline is unchanged (lowercase kebab-case ASCII, max 60 chars).
- **External links:** `[title](https://...)`, unchanged.
- No `[[wikilinks]]` in page bodies. The only wikilinks are the frontmatter reference keys of §14.
- Link text is a human title, not the path.

## 6. Index and log

**`wiki/index.md`** (generated):

```markdown
---
okf_version: "0.2"
---

# Sources

* [Title](sources/my-note.md) - description
* [Subdirectory](concepts/index.md) - 12 pages
```

Subdirectory `index.md` files have **no frontmatter at all**. Entries use `* [Title](relative-path) - description`, and every link targets a file (§15).
Same input gives the same bytes. Deleting every `index.md` and re-running the script restores them.

**`wiki/log.md`**: newest first, date-grouped, ISO dates (§9):

```markdown
# Log

## 2026-10-28
* **Ingest**: 3 notes from `notes/`; skipped 1 (already present). Sources: [a](sources/a.md), [b](sources/b.md).
* **Query**: "what is X?" answered from [x](concepts/x.md).

## 2026-10-27
* **Creation**: Initialized the wiki.
```

- The bold word is one of `Creation`, `Ingest`, `Query`, `Lint`, `Update`. It is a convention in OKF; this skill always writes one.
- New entries go **at the top of the current day's group**; a new day opens a new `## YYYY-MM-DD` heading directly under `# Log`.
- Entries are append-only in spirit: never edit or delete an old one.
- Because newest-first insertion is easy to get wrong by hand, a script (`scripts/append_log.py`) does it. Agents call it instead of editing `log.md`.

## 7. `config.yml`

Created on first run (ingest mode, when the wiki is created, after confirming the slug). The orchestrator asks the user
once (ask-user capability), writes the answers, and never asks again. Later runs read it first (Step 0).

```yaml
# wiki-<slug>/config.yml   (owned by the user; the skill changes it only when the user asks)
language: en            # language wiki pages are written in
tags: optional          # optional | forbidden. optional = allowed if present, writers never invent them. forbidden = lint flags any tag.
stale_after_days: 60    # how old a time-sensitive page may get before lint calls it stale
```

Log order, link style and OKF version are **not** configurable; they are fixed by this document.
If the user answers nothing, the defaults above apply and the file is still written, so the question is not asked again.
A missing `config.yml` on an existing wiki is treated as the defaults and is not an error (old wikis keep working).

## 8. Write regimes (unchanged from upstream §13)

`config.yml` is user-owned. `log.md` is written by the orchestrator only through `append_log.py`. Everything else keeps
the ingest-owned / interaction-owned / repo-note split from upstream.

## 9. Compatibility with upstream and v0.1

A v0.1 bundle (with `timestamp`, `# Citations`, wikilinks, oldest-first log at `wiki-<slug>/log.md`) is **not** migrated
automatically. The skill may read it, but anything it rewrites follows this document. A migration script is out of scope.

## 10. Not in this migration

- Lint (a later phase; will use `status`, `stale_after`, `verified`, link and threshold checks).
- OKF §10 Attested Computations: irrelevant to a knowledge wiki.
- Writing `usage_count` / `usage_window`.

## 11. Gaps found during the first pass, now decided

1. `repo_note` is a valid `type` value (the type list in §3 is not exhaustive).
2. Old path-valued keys (`related`, `answer_doc`, `sources_cited`, `spawned_by_question`, `repo`) hold bundle-relative `/x.md` paths, like `entities:` / `concepts:`.
3. Footnote ids are unique **within one page's `sources`**. If two source-like pages share a slug (for example a note and a repo), suffix the later one: `slug-2`.
4. An overview or note lists in `sources` the pages it actually cites, not every page it read.
5. An overview rewrite logs as `**Update**`.
6. A log entry may have several bullets. `append_log.py` takes `--text` repeatedly and writes the bullets in the given order as one block at the top of the day's group. Each bullet starts with the same bold op word.
7. A repo note with several permalinks lists them as `repo`, `repo-2`, `repo-3` in `sources`.
8. Root `index.md` layout is the script's: `# Pages` (overview, open-questions) and `# Browse` (one line per subdirectory). Subdirectory indexes carry no frontmatter and no marker comment.
9. `verified[].by` accepts `human:<id>`, `process:<id>` or `<producer>/<version>`.
10. Timestamps must be full ISO 8601 datetimes with an offset. A date-only `created` is a warning.

## 12. Decisions after the first end-to-end run

These supersede any earlier text in this file or elsewhere.

1. **Anchors are heading text, percent-encoded** (Obsidian-first), not GitHub slugs: `../../raw/my-note.md#6.%20Building%20the%20Server`. Spaces become `%20`, other characters stay, `)` and `%` are encoded. `build_index_md.py` has no anchor check, so nothing changed there.
2. **Synthesis is separate on every page type** (overview and notes included). Interpretation, comparison, evaluation or inference the cited material does not state goes on its own `> Synthesis:` line. Plain prose carries only sourced statements. A footnote supports only what its source states; a claim combining two sources needs both footnotes; no detail is attributed to a source that does not mention it.
3. **Large notes** (raw file over about 15 KB or more than 6 top-level headings): the source page covers every top-level section in at least one sentence and anchors each footnote at its section. One `[^raw]` label may list several anchors inside its single definition. Every summary paragraph on a source page carries a footnote.
4. **Slug rule:** lowercase; every run of non-alphanumeric characters (dots and punctuation included) becomes one `-`; strip leading and trailing `-`; ASCII only; at most 60 characters, truncated at a `-` boundary. `CLAUDE.md` is `claude-md`.
5. **Orchestration:** (a) with no ask-user capability, Step 0 uses the defaults, writes `config.yml` and says so in the report; (b) the dedup command is `ls wiki-<slug>/raw/ 2>/dev/null; ls wiki-<slug>/raw/repos/ 2>/dev/null`; (c) `metadata` keys are optional for local notes, the writer derives the title from the first H1, else the filename stem, and the local-note receipt is only `original_path` and the raw path; (d) agent prompts name `PAGES.md` and `CONVENTIONS.md` by full path `.agents/skills/llm-wiki-keeper/...`, relative to the project root; (e) the orchestrator may pass an agent file's path plus inputs instead of pasting the body when the subagent can read files; (f) run `count_mentions.py` with `2>/dev/null` when only the JSON is needed; (g) several `--text` give one bullet per `--text` under one op word, and the overview rewrite is a separate `Update` call after `Ingest`, so it sits above it; (h) the overview's `total_pages` counts every non-reserved `.md` in `wiki/`, `overview.md` included, and the overview links the slugs waiting at 1 mention.
6. **Known limitations** are listed at the end of `CONVENTIONS.md`: Properties panel and nested YAML, provenance per section, text anchors not scrolling on GitHub.

## 13. Decisions after the second end-to-end run

These supersede any earlier text, including §12 item 5(h) on `total_pages`.

1. **`total_pages` is removed** from the overview template, examples and `overview_writer.md`. It is derived data that goes stale, and the overview is counted while it is being written. `## Health` keeps its per-type counts.
2. **Clock.** No agent types a timestamp by hand. Every page-writing agent, including the orchestrator for question, note and open-questions pages, runs `date -u +%Y-%m-%dT%H:%M:%SZ` at write time, one call per page. Spawned writers receive no `now` input and run `date` themselves (`CONVENTIONS.md` §5, each `agents/*.md`, `QUERY.md` Q.5).
3. **Context discipline by mode** (`CONVENTIONS.md` §12): in ingest the orchestrator reads receipts and script output only; in query mode it also reads `wiki/index.md`, subdirectory indexes and the pages the disclosure ladder (Q.3) names, never `raw/` except where `QUERY.md` says so.
4. **Path wording.** Agent prompts and `SKILL.md` name `.agents/skills/llm-wiki-keeper/PAGES.md` (and `CONVENTIONS.md`) exactly, and add: if that path does not exist, look in the directory of this skill file. "Relative to the project root" is dropped.
5. **First run lists.** When `wiki/entities` and `wiki/concepts` are empty, `SKILL.md` 1.3 says to pass an empty list, not to skip the input.
6. **`mentions_json`** may be inline or a path to a file holding the script's JSON; the agent reads the file when given a path. The orchestrator may save the script output to a scratch file (`SKILL.md` 1.5).
7. **"The wiki does not cover this"** (`QUERY.md` Q.5, question template): `sources_cited` lists the wiki pages read to establish that, `answer_doc` stays null, and the open question is recorded.
8. **No-ask-user fallback** is the first bullet under "Creating a wiki" in `SKILL.md` Step 0, with the exact sentence: "No ask-user capability (for example you are a subagent): write config.yml with the defaults and say so in your report." It is repeated in the Harness notes table.

## 14. Frontmatter reference keys are wikilinks

Decision (user, 2026-10-30). Supersedes §5 "Frontmatter lists", §11 item 2 and the `/x/y.md` path form everywhere.

**Keys.** These page-reference keys hold quoted Obsidian wikilinks, as one string or a list of strings:
`entities`, `concepts`, `related`, `answer_doc`, `sources_cited`, `spawned_by_question`, `repo`.
Reading `PAGES.md` found no others: `original_path`, `source_url`, `repo_url`, `clone_path` are not page references,
and `sources[].resource` is OKF-defined (a relative path or URL) and does not change.

**Form.** `"[[concepts/mcp]]"`: the path relative to the bundle root (`wiki/`), no leading slash, no `.md`, no `wiki/` prefix.
Obsidian resolves wikilinks by path suffix, so this works whether the vault is the project root, `wiki-<slug>/` or `wiki/`.
Always quote: an unquoted `[[x]]` parses as a nested YAML list. `count_mentions.py` takes the last path segment as the slug.
Legacy `/x/y.md` and `[[wiki/x/y]]` are still counted; `build_index_md.py` warns about the legacy path form as a migration hint.

**Reason.** Obsidian's Properties panel makes only `[[wikilinks]]` clickable; plain paths and markdown links are not.

**Cost.** These keys are the one place the skill emits wikilinks. The body rule is unchanged: bodies use standard relative
markdown links and `[[wikilinks]]` stay forbidden there. This is a producer-defined extension; OKF §4.1 allows extra keys,
so the bundle stays conformant. Receipts still return slugs.

## 15. Index links point at files

**Bug.** `build_index_md.py` wrote subdirectory entries as directory links, for example `* [Sources](sources/) - 4 pages`
in `wiki/index.md` and `[repo](repo/)` in the repos index. Obsidian does not understand a link to a folder: clicking it
creates an empty note named `sources` at the vault root. A real user hit this.

**Fix.** Every link in a generated `index.md` points at a file: `* [Sources](sources/index.md) - 4 pages`, and
`repos/index.md` links `github-x-y/index.md`. OKF 0.2 §8 allows it, since an `index.md` is a normal file link.
`build_index_md.py` also warns about any markdown link in any wiki page or index whose relative target ends with `/` or
resolves to an existing directory: "link points at a directory; Obsidian creates an empty note when it is clicked;
link the folder's index.md instead".

**Reason.** A link that Obsidian cannot resolve is not harmless: a click writes a stray note outside the bundle.
Linking the folder's `index.md` resolves to a real file and keeps the output deterministic.

## 16. Lint (Karpathy's third operation): design

Decided 2026-10-30. Promissory links stay (user chose option A), so lint must handle hollow links and the empty stubs
Obsidian creates when one is clicked.

**Two tiers.** A deterministic script (`scripts/lint.py`, read-only) and an LLM review (`agents/lint_reviewer.md`, read-only,
Sonnet-class, one per page group) for what a script cannot judge. The orchestrator merges both into one report.

### 16.1 Deterministic checks (`lint.py`)

Output: JSON `{findings: [{id, severity, file, line, message, fix_hint}], summary: {error, warn, info}, config, checked_pages}` on stdout,
a human table on stderr, exit 1 when any `error` exists. Flags: `--wiki-dir`, `--now <ISO>` (for tests), `--json-only`.

| id | name | severity | rule |
|---|---|---|---|
| L01 | uncited-prose | warn | On pages of type source, entity, concept, overview, note, repo, repo_note: any paragraph or list item that has no `[^id]` reference and is not a `> Synthesis:` line. Exempt: headings, tables, fenced code and mermaid blocks, footnote definitions, blockquote metadata lines, list items consisting only of links, frontmatter, and the first blockquote after the H1 on entity, concept, repo and repo_note pages when it is exactly one line (§17). question, open_question, index and log pages are not checked. |
| L02 | empty-stub | error | A `.md` file (outside `raw/` and `.obsidian/`) with no non-whitespace content, or with no frontmatter and no body. Typical cause: a click on a hollow link. |
| L03 | stray-outside-bundle | warn | Anything in `wiki-<slug>/` that is not `config.yml`, `raw/`, `wiki/` or `.obsidian/` (for example the `entities/` folder Obsidian creates). |
| L04 | broken-link | error | A relative markdown link or a frontmatter reference wikilink whose target does not exist and is not promissory. Promissory = target under `entities/` or `concepts/` whose slug has fewer than 2 source mentions. Heading anchors are checked against heading text. |
| L05 | missing-page | error | A slug with 2 or more mentions (the `count_mentions.py` rule) and no page. |
| L06 | premature-page | warn | An entity or concept page whose slug has fewer than 2 mentions. |
| L07 | orphan | warn | A page (not index, log, overview) with no inbound link from any other page. |
| L08 | stale | warn | `stale_after` is at or before now; or a `status: deprecated` page still linked from a page that is not deprecated. |
| L09 | footnote-integrity | error | A `[^id]` reference without definition, a definition never used, an id missing from `sources[].id`, a `sources[].resource` that points at a missing local file. |
| L10 | index-drift | warn | A generated `index.md` that differs from what `build_index_md.py` would write now (computed in memory or in a temp copy; lint never writes). |
| L11 | tags-policy | warn | Any `tags` present while `config.yml` says `tags: forbidden`. |
| L12 | trust-summary | info | Counts per trust tier (unverified, machine-confirmed, human-reviewed, OKF §5.3) and per `status`. Never a failure. |
| L13 | conformance | error/warn | The conformance results of `build_index_md.py` (run as a subprocess, results merged, severities kept). |
| L14 | config-missing | info | No `config.yml`: defaults were used. |
| L15 | timestamp-sanity | warn | `created` or `generated.at` in the future, or `created` later than `generated.at`. |

Lint never fixes anything by itself.

### 16.2 LLM review (`agents/lint_reviewer.md`)

One reviewer per group of at most 6 pages, read-only, returns one JSON receipt of findings. It may read the cited source pages and,
for the spot check, the single raw file a source page cites. Checks:

| id | name | severity | rule |
|---|---|---|---|
| C01 | contradiction | warn | Two pages assert incompatible things about the same subject. Quote both, with paths. |
| C02 | unsupported-claim | warn | A footnoted claim that the cited source (or raw note) does not state. Spot check at least 4 claims per page. |
| C03 | missing-cross-reference | info | A page names an entity or concept that has a page, without linking it. |
| C04 | data-gap | info | Waiting slugs worth ingesting a second source for; open questions that the current pages now answer (report only; a human decides). |
| C05 | interpretation-in-prose | warn | Interpretation, comparison or inference stated as sourced fact outside a `> Synthesis:` line (the judgment version of L01). |

### 16.3 Regimes, report and log

- Lint is **read-only on all ingest-owned and interaction-owned pages** (same rule as query mode).
- It writes one report page `wiki/lint/YYYY-MM-DD.md` (type `lint_report`, `generated.by: llm-wiki-keeper/orchestrator`; a second run on the same day overwrites it). `lint/` is an interaction-owned folder with a generated `index.md`.
- Log: one `**Lint**` bullet via `append_log.py`: counts by severity and a link to the report.
- Findings C04 may be appended to `open-questions.md` as dated bullets (append-only, as in query mode); nothing else is written outside `lint/`.
- Fixes are a separate, user-confirmed step: the orchestrator may (a) delete empty stubs (L02, L03 folders that are empty), after listing them and getting a yes, (b) re-run `build_index_md.py` (L10). Content findings are never auto-fixed; they go to the next ingest or to a human edit.
- `build_index_md.py` must treat `lint/` like any other subdirectory: generate `lint/index.md` (no frontmatter) and list it in the root index as `* [Lint](lint/index.md) - N pages`, reading each report's `title` and `description`. `lint_report` is a known `type`. (Script not edited here.)
- Mode detection: lint iff the user says lint, health check, audit, "check the wiki" or similar. Ambiguity resolves to query, as before.
- `config.yml` keys used: `tags`, `stale_after_days` (L08 also reports a page whose `generated.at` is older than `stale_after_days` and whose source is a web article or a repo, as info).

## 17. Decisions after the first lint run

The first lint run on a real generated wiki gave 60 L01 warnings. Two shapes dominated, with different verdicts.

1. **Relationship bullets are links, never claims (template fix).** Bullets such as
   `- **MCP**: the delivery mechanism through which memory tools reach the agent. [MCP](../concepts/mcp.md)` carry an
   uncited claim, so lint was right and the template was wrong. A Relationships / Connections / Related bullet now names
   the target and nothing else: `- [MCP](../concepts/mcp.md)`. To say how two things relate, use one `> Synthesis:` line
   under the list, or a sourced sentence with a footnote in the body. Changed: every template and worked example in
   `PAGES.md` (the bold `**Entities**:` and `**Concepts**:` labels are gone too), `CONVENTIONS.md`, and the writer prompts
   `page_writer.md`, `source_writer.md`, `repo_writer.md`, `overview_writer.md`.
2. **Definition blockquote is exempt (lint fix).** The one-line `> <definition>` after the H1 on entity, concept, repo and
   repo_note pages mirrors the frontmatter `description`, and the cited Definition section follows. L01 skips the first
   blockquote after the H1 on those page types, only when it is exactly one line. A second uncited blockquote, or a
   multi-line first one, still fails. Tests added in `tests/test_lint.py`.

## 18. Decisions after the first lint-mode run

The first end-to-end lint run produced friction in four places. These decisions supersede earlier text where they differ.

1. **Report self-errors.** The orchestrator copied `message` and `fix_hint` verbatim into the report, so literal footnote and link syntax in them parsed as real refs and links (7 errors on the report itself). (a) `LINT.md` L.5 and the `PAGES.md` `lint_report` template: a finding is `path:line`, the id and a paraphrased one-line message; literal markdown-looking text goes inside backticks; links are relative to `wiki/lint/` (`../sources/x.md`) and computed by the orchestrator. (b) `lint.py`: L09 skips `lint_report` pages entirely (L01 never checked that type); `[^id]` inside code spans or fences and links inside code spans or fences are ignored on every page (this was already how code stripping worked for single-line spans; now pinned). (c) Tests added for all three.
2. **JSON `pages`.** `lint.py` output gains `pages`, the sorted list of checked page paths; `checked_pages` stays the integer. `LINT.md` L.3 groups from `pages`. Findings with `file: null` (L12, L14) belong to no group and go straight to the summary. Small directories may be merged into one group up to 6 pages, sources first. The orchestrator saves a group's deterministic findings to a scratch file and passes its path (inline for tiny groups); `lint_reviewer.md` says so.
3. **L01 false positives.** Exempt now: list items under `## Index` and `## Health` of the overview; a list item of the exact shape `[Name](path) - description` (hyphen or em-dash) under an `## Index` heading on any page; the `> [Raw](...) · local` pointer line of a source page; a verbatim quote whose last line is an em-dash attribution link (`> — [heading](raw link)`), which is the cited-by-link shape of "Notable quotes". Still reported: a theme sentence in the overview body, and placeholder prose such as "No entities or concepts are engaged by this note." in a Connections section (harmless wording, but a writer-invented claim line; left to the writer prompts, not the linter).
4. **Derived counts removed.** `total_sources` is gone from the overview template, the worked example, `overview_writer.md` and its receipt; no `total_*` key anywhere. `## Health` keeps per-type counts in body text only. (`source_count` on entity and concept pages is unchanged; it is per page, not a wiki total.)
5. **`LINT.md` wording.** (a) The L.7 index rebuild only has to index the new report and is part of writing it; the rebuild L.8 offers is for pre-existing L10 drift only. (b) Log counts read "N errors, N warnings, N info" and include every finding after dedupe. (c) The orchestrator may read only the frontmatter `created` line of an earlier same-day report (grep); `CONVENTIONS.md` §12 carries that one exception. (d) L.4 dedupe key: same file and same line, or same file and the same quoted passage. (e) L.6 restates the open-questions bullet format so the file stands alone.
6. **`SKILL.md`.** (a) Step 0 ingest row: with no ask-user capability, use the proposed slug and say so. (b) 1.1: if the 60-character cut lands inside a word, go back to the previous `-`. (c) 1.4: slugs at 1 mention get no page; they are listed as waiting. (d) 1.6/1.7: `build_index_md.py` runs once, after the log entries.
