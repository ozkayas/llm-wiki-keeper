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
entities:                          # unchanged meaning (the >=2 threshold); values are now paths, see §5
  - /entities/claude-code.md
concepts:
  - /concepts/mcp.md
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
- **Frontmatter lists** `entities:` / `concepts:` hold the bundle-relative path (starts with `/`, ends in `.md`).
  They are data for the threshold script, not links a reader follows; the path is the identity and `count_mentions.py`
  derives the slug from it.
- **Promissory links** are allowed: a link to `../concepts/<slug>.md` before the page exists. OKF §6.1 tolerates
  broken links. Slug discipline is unchanged (lowercase kebab-case ASCII, max 60 chars).
- **External links:** `[title](https://...)`, unchanged.
- No `[[wikilinks]]` anywhere in the skill's output.
- Link text is a human title, not the path.

## 6. Index and log

**`wiki/index.md`** (generated):

```markdown
---
okf_version: "0.2"
---

# Sources

* [Title](sources/my-note.md) - description
* [Subdirectory](concepts/) - 12 pages
```

Subdirectory `index.md` files have **no frontmatter at all**. Entries use `* [Title](relative-path) - description`.
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
