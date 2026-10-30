# CONVENTIONS — the data contract

Everything in this file is shared by all three workshop layers. Layers 02 and 03
**append** to it (look for `<!-- added in 02 -->` / `<!-- added in 03 -->`); they
never rewrite what is here. Sections marked `<!-- changed in keeper: OKF 0.2 -->`
were rewritten when the skill moved from OKF v0.1 to v0.2; the decisions behind
them are in `MIGRATION-OKF-0.2.md` at the repo root, which wins over any older text.

Page templates live in `PAGES.md`. The orchestration steps live in `SKILL.md`.

---

<!-- changed in keeper: OKF 0.2 -->
## 1. Directory layout

One wiki per project, in the project root, named `wiki-<slug>/`:

```
wiki-<slug>/
├── config.yml                   # user preferences (§10a); NOT part of the bundle
├── raw/                         # immutable copies of what was ingested
│   ├── <slug>.md                # one file per ingested note
│   └── assets/                  # the images and transcripts those notes embed
└── wiki/                        # the knowledge bundle — every .md carries a `type`
    ├── index.md                 # GENERATED bundle root (only file with frontmatter: okf_version)
    ├── log.md                   # reserved name; newest first (§9)
    ├── overview.md              # type: overview
    ├── sources/
    │   ├── index.md             # GENERATED
    │   └── <slug>.md            # type: source — one per raw file
    ├── entities/ { index.md, <slug>.md }   # type: entity
    └── concepts/ { index.md, <slug>.md }   # type: concept
```

Two halves, and the split is the whole point:

- `raw/` is **what was said** — never edited, never summarized in place.
- `wiki/` is **what we know** — written by the LLM, rewritten as sources accumulate.

`index.md` and `log.md` are reserved filenames inside the bundle. `config.yml` is
not markdown and sits next to `raw/`, outside the bundle.

## 2. Three-layer progressive disclosure

Any agent reading the wiki walks down this ladder and **stops as soon as the
question is answered**:

1. `wiki/index.md` → the relevant `wiki/<subdir>/index.md` — one
   `[Title](path) - description` bullet per page. This is the cheap map.
2. The wiki page itself (source / entity / concept). ~1 page of curated prose.
3. `raw/` — only when a wiki page is genuinely insufficient. **Never bulk-read raw.**

Layer 2 exists so that layer 3 almost never has to be read. A wiki that forces
every reader back into `raw/` has failed at its job.

<!-- changed in keeper: OKF 0.2 -->
## 3. Source-like pages and the ≥2 threshold

A **source-like page** is a page written directly from one ingested artifact.
In layer 01 that is exactly `wiki/sources/*.md`.

Every source-like page declares, in its frontmatter, the pages it substantively
engages with, as **quoted wikilinks relative to the bundle root** (no leading slash, no `.md`, no `wiki/` prefix):

```yaml
entities:
  - "[[entities/claude-code]]"
concepts:
  - "[[concepts/mcp]]"
```

> **An entity or concept page exists if and only if ≥2 distinct source-like
> pages list it.**

`scripts/count_mentions.py` is the single source of truth for that count — never
eyeball it. It derives the slug from the last path segment (`"[[concepts/mcp]]"` gives `mcp`).
These keys are wikilinks so they are clickable in Obsidian's Properties panel (MIGRATION §14);
the path is the identity. One note mentioning something is a fact about that note; two notes
mentioning it is a fact about your knowledge, and that is what earns a page.

**Promissory links.** A source-like page may link `[MCP](../concepts/<slug>.md)`
in its body before the page exists (OKF tolerates broken links). Obsidian renders
the unresolved target and it resolves the day the second mention lands. The price
is **slug discipline**: lowercase; every run of non-alphanumeric characters
(dots and punctuation included) becomes one `-`; strip leading and trailing `-`;
ASCII only; at most 60 characters, truncated at a `-` boundary. This is the slug
the eventual page will use. `agent-loop`, not `Agent Loops` or `agentic_loop`;
`CLAUDE.md` is `claude-md`.

## 4. Identity and dedup

**Identity is the raw artifact path.** Every ingested input maps to one
deterministic path under `raw/`; if that path already exists, the input has
already been ingested.

| Input | Raw path | Slug from |
|---|---|---|
| local note | `raw/<slug>.md` | the filename stem |

Dedup is therefore an `ls`, not a frontmatter walk: compute the raw path, check
whether it exists, done.

**Attachments travel with their note.** A note that embeds `![[assets/x.png]]`
is only half a note without the image, so ingest copies the files it references
into `raw/assets/`, keeping the filename. Because `raw/assets/` is then a sibling
of `raw/<slug>.md`, the embed keeps resolving inside the wiki exactly as it did in
the source folder — no link rewriting, and `raw/` stays a verbatim copy. (Raw files
are verbatim, so Obsidian embeds inside them are fine; the no-wikilink rule in §6
applies to page bodies the skill writes under `wiki/`.)

Attachments are **not sources**: no wiki page, no `entities:`/`concepts:`, no
count toward the ≥2 threshold. They are payload the source page may point at.
Identity is the filename, so the same image referenced by five notes is copied
once and skipped four times. Only `*.md` is ingested *as a source* — which is why
an embedded `.srt` transcript lands in `raw/assets/` and stays unread until
someone writes an adapter for it.

`original_path` on a source page records **provenance, not identity** — the path
as it was given, normalized relative to the project root
(`../data_input_examples/notes/01-easy/foo.md` becomes
`data_input_examples/notes/01-easy/foo.md`). The same note reached through two
different directories is one source, ingested once, and the wiki remembers the
first path it came from.

- Already-ingested input → **skipped**, reported by name with its existing `original_path`.
- Same slug, different content → **still skipped**, with a warning naming both
  paths. Renaming the incoming file is the fix; silently overwriting `raw/` is not.

<!-- changed in keeper: OKF 0.2 -->
## 5. Frontmatter rules

Every page in `wiki/` except `index.md` and `log.md`:

```yaml
---
type: source                       # REQUIRED. source|entity|concept|overview|repo|repo_note|question|note|open_question
title: ...                         # required by this skill
description: One sentence.         # required by this skill; the only thing the index shows
created: 2026-10-28T09:00:00Z      # extra key (OKF allows them); set once, preserved across rewrites
generated: { by: llm-wiki-keeper/source_writer, at: 2026-10-28T09:00:00Z }
sources: [...]                     # §6
entities: ["[[entities/claude-code]]"]   # source-like pages only (§3)
concepts: ["[[concepts/mcp]]"]           # source-like pages only (§3)
status: stable                     # optional: draft | stable | deprecated. Absent means stable.
stale_after: 2027-01-01T00:00:00Z  # optional, absolute instant
tags: [a, b]                       # optional
---
```

- `type` is required and non-empty. `title` and `description` are required by this
  skill. `description` is **one sentence**; it is the only thing the index shows,
  so it is the single highest-leverage line on the page.
- **`timestamp` does not exist any more.** `generated.at` replaces it and is bumped
  on every meaningful change; `created` never changes. `generated.by` is
  `llm-wiki-keeper/<agent>` with `<agent>` one of `source_writer`, `repo_writer`,
  `page_writer`, `overview_writer`, or `orchestrator` (pages the query path writes).
- **`verified` is never written by an LLM writer.** It records a human (`human:<id>`)
  or a named process confirming the content. A writer that adds it is lying about
  trust. If a page already has it, preserve it.
- `status` and `stale_after` are optional. Writers omit `stale_after` unless the
  source is time-sensitive (prices, versions, release state).
- `tags` are optional. Writers **never invent tags**; with `tags: optional` in
  `config.yml` a tag already on a page is preserved, with `tags: forbidden` lint
  flags any tag.
- All instants are ISO 8601 with an explicit offset; this skill writes `Z` (UTC):
  `date -u +%Y-%m-%dT%H:%M:%SZ`.
- **No agent types a timestamp by hand.** Every page-writing agent, the orchestrator
  included (question, note and open-questions pages), runs
  `date -u +%Y-%m-%dT%H:%M:%SZ` at write time, one call per page, and uses the
  output for `generated.at` (and `created` on a new page). Writers spawned by the
  orchestrator receive no `now` input; they run `date` themselves.
- **Quote any value containing `: `** — a colon followed by a space makes YAML read
  the rest as a mapping, and the page silently stops parsing. This bites
  `description` first, because one-sentence gists like
  `description: "The rule: quote it"` are natural to write. `build_index_md.py`
  catches it as an `unparseable YAML frontmatter` error.
- **Unknown keys are preserved** when a page is rewritten (`aliases`, `related`,
  human additions).
- Frontmatter page-reference keys (`entities`, `concepts`, `related`, `answer_doc`,
  `sources_cited`, `spawned_by_question`, `repo`) hold **quoted wikilinks**, as a string or a
  list of strings: `"[[concepts/mcp]]"`. The path is relative to the bundle root (`wiki/`), with no
  leading slash, no `.md` and no `wiki/` prefix; Obsidian resolves by path suffix, so it works
  whatever the vault root is. Quote them: unquoted `[[x]]` is a nested YAML list. `sources[].resource`
  is OKF-defined and stays a relative path or URL.

Full per-type contracts: `PAGES.md`.

<!-- changed in keeper: OKF 0.2 -->
## 6. Linking and citations

**Links** are standard markdown, never `[[wikilinks]]`:

- Wiki → wiki and wiki → raw use a **relative path with the `.md` extension**,
  resolved from the page that contains the link: `[MCP](../concepts/mcp.md)`,
  `[note](../../raw/foo.md#Heading%20Text)`. Relative, not OKF's bundle-absolute form,
  because Obsidian resolves `/` against the vault root and the vault is often the
  project root, not `wiki/`. A relative link works from either.
- Link text is a human title, never the path.
- **Anchors point at the heading text, percent-encoded, as Obsidian expects** (not a GitHub slug): `../../raw/my-note.md#6.%20Building%20the%20Server`. Spaces become `%20`, other characters stay as in the heading, and `)` and `%` are encoded too (`%29`, `%25`).
- External links: `[title](https://...)`.
- Frontmatter reference keys (§5) are the one place the skill emits wikilinks; bodies never do.

**Provenance** is the frontmatter `sources` list plus footnotes in the body.

`sources` entries have `resource` (required) and optionally `id`, `title`, `author`,
`last_modified`. (`usage_count` / `usage_window` are not used.) The `id` is the join
key: a footnote label must equal a `sources[].id`.

- **Source page** (one raw file): one entry `id: raw`, `resource: ../../raw/<slug>.md`.
  An article adds a second entry `id: web` with the original URL (and `author`,
  `last_modified` when known). Claims are footnotes `[^raw]`, with the heading
  anchor in the footnote text, not the label:

  ```markdown
  The index is rebuilt after every ingest.[^raw]

  [^raw]: [My note, "Rebuild"](../../raw/my-note.md#Rebuild)
  ```

  Several claims from one raw file reuse `[^raw]`. When the one label must point
  at several sections, list the anchors inside the single definition:
  `[^raw]: [Section 3](../../raw/my-note.md#3.%20X), [Section 5](../../raw/my-note.md#5.%20Y)`.
  The label stays unique. For a large raw file, `source_writer` cites each claim at
  the section it came from (`PAGES.md § source`).
- **Entity / concept / repo / overview / note pages**: one entry per page drawn
  from, `id` = that page's slug, `resource` = relative path
  (`../sources/my-note.md`). Claims are `[^my-note]` with the definition
  `[^my-note]: [My note](../sources/my-note.md)`.
- **Repo pages**: entry `{ id: repo, resource: https://github.com/<owner>/<repo>/tree/<sha>, title }`;
  code claims keep their commit-pinned permalink style.
- LLM judgment is never laundered as a sourced claim. It goes on its own line,
  prefixed `> Synthesis:`, and carries no footnote, on every page type.
- A relationship bullet (Relationships, Connections, Related) names the target and
  nothing else: `- [MCP](../concepts/mcp.md)`. If you want to say HOW two things
  relate, put it in one `> Synthesis:` line under the list, or write a sourced
  sentence with a footnote in the body. A label that asserts something is an
  uncited claim.
- The one-line `> <definition>` blockquote right after the H1 on entity, concept,
  repo and repo_note pages mirrors `description` and needs no footnote; a second
  uncited blockquote does.
- A footnote supports only what its source states. A claim that combines two
  sources needs both footnotes. Never attribute a detail (a protocol, a database,
  a number) to a source that does not mention it.
- Every footnote label resolves to a `sources` entry and every `sources` entry is
  cited at least once. Only entity/concept cross-references may be promissory (§3).

## 7. Immutability and write regimes

- `raw/` is **immutable**. Re-ingesting a note does not overwrite it (§4).
- `wiki/` is **LLM-owned**. A human may edit it, but the next ingest may rewrite
  what they wrote — deliberate edits belong in `raw/` or in a note the pipeline
  does not own.
- All `index.md` files are **generated**. Never hand-edit one; run
  `build_index_md.py`.
<!-- changed in keeper: OKF 0.2 -->
- `wiki/log.md` is **append-only in spirit**, newest first, written only through
  `scripts/append_log.py` (§9). `config.yml` is user-owned.

## 8. The ingest tail

Whenever a new source-like page lands, the same five steps run — this workshop
calls them the **ingest tail**, and every layer reuses them verbatim:

1. `count_mentions.py` — recount mentions across all source-like pages.
2. Write/update every entity/concept page whose slug is now ≥2 **and** appears in
   one of the new pages. (A slug at ≥2 that no new page touched is already
   written and unchanged — skip it.)
3. Rewrite `overview.md`.
4. `build_index_md.py` — regenerate the index cache.
<!-- changed in keeper: OKF 0.2 -->
5. Append one entry via `scripts/append_log.py`.

<!-- changed in keeper: OKF 0.2 -->
## 9. `log.md`

`wiki/log.md`, created on init with `# Log` and a first `Creation` entry. Newest
first, grouped by ISO date:

```markdown
# Log

## 2026-10-28
* **Ingest**: 3 notes from `notes/`; skipped 1 (already present). Sources: [a](sources/a.md), [b](sources/b.md).
* **Query**: "what is X?" answered from [x](concepts/x.md).

## 2026-10-27
* **Creation**: Initialized the wiki.
```

- The bold word is one of `Creation`, `Ingest`, `Query`, `Lint`, `Update`. OKF treats
  it as a convention; this skill **always** writes one.
- Entry links are relative to `wiki/log.md` (`sources/a.md`, no leading `..`).
- New entries go **at the top of the current day's group**; a new day opens a new
  `## YYYY-MM-DD` heading directly under `# Log`. Never edit or delete an old entry.
- Agents never edit `log.md` by hand; `scripts/append_log.py` does the insertion.
- One call with several `--text` produces one bullet line per `--text`, all under
  the same bold op word, in the given order.
- The overview rewrite is logged by a separate `Update` call made after the
  `Ingest` call, so `Update` sits above `Ingest` in a newest-first log. That is expected.
- Greppable: `grep -E '^## [0-9]{4}-' wiki/log.md`.

<!-- changed in keeper: OKF 0.2 -->
## 10. OKF alignment (why the layout looks like this)

`wiki/` is an [Open Knowledge Format](https://openknowledgeformat.org) **v0.2**
bundle. The parts we honour:

- markdown documents with YAML frontmatter; **path is identity**;
- every non-reserved file carries a non-empty `type`;
- `index.md` and `log.md` are **reserved**: navigation and history, not content;
- only the bundle root `wiki/index.md` has frontmatter, and it declares
  `okf_version: "0.2"`; subdirectory indexes have none, entries read
  `* [Title](relative-path) - description`, and a subdirectory entry reads
  `* [Name](dir/index.md) - N pages` (a link to a folder is never written: Obsidian
  creates an empty note when it is clicked);
- provenance via `sources`, `generated`, optional `status` / `stale_after` /
  `verified`; `timestamp` is gone;
- log newest first, date-grouped, bold operation word;
- frontmatter is canonical, the index is a **rebuildable cache** (delete every
  `index.md`, re-run the script, get the same bytes back).

Divergences that remain, deliberately:

1. `created` is an extra, producer-defined key (OKF allows extra keys).
2. Links are **relative** (`../concepts/x.md`), not OKF's recommended bundle-absolute
   `/concepts/x.md`, so they resolve in Obsidian whatever the vault root is.
   Frontmatter page-reference keys (`entities`, `concepts`, `related`, `answer_doc`,
   `sources_cited`, `spawned_by_question`, `repo`) are the exception: they are quoted
   Obsidian wikilinks (`"[[concepts/x]]"`) so the Properties panel can click them.
   A producer-defined extension, allowed by OKF §4.1 (MIGRATION §14).
3. The bold operation word in the log is always written (OKF: convention).
4. `raw/` lives outside the bundle and is linked into it by `../../raw/...`.
5. `config.yml` lives outside the bundle; it is not an OKF concept.
6. Promissory links to pages that do not exist yet are used on purpose (OKF tolerates them).
7. The frontmatter page-reference keys hold quoted wikilinks, the only place this skill emits
   them (see item 2 and MIGRATION §14).

`build_index_md.py` checks conformance on every run: a page with no `type` is an
error (non-zero exit), a missing `description` or a malformed log heading is a
warning on stderr. A reference key holding a legacy path (`/x/y.md`) instead of a quoted
wikilink is a warning too, worded as a migration hint.

<!-- changed in keeper: OKF 0.2 -->
## 10a. `config.yml`

`wiki-<slug>/config.yml` holds the user's preferences. It is created on the first
run (ingest mode, when the wiki is created, after the slug is confirmed): the
orchestrator asks the user **once** with the ask-user capability, writes the
answers, and never asks again. Every later run reads it first (SKILL.md Step 0).

```yaml
# wiki-<slug>/config.yml   (owned by the user; the skill changes it only when the user asks)
language: en            # language wiki pages are written in
tags: optional          # optional | forbidden. optional = allowed if present, writers never invent them. forbidden = lint flags any tag.
stale_after_days: 60    # how old a time-sensitive page may get before lint calls it stale
```

- If the user answers nothing, the defaults above apply and the file is still
  written, so the question is not asked again.
- A missing `config.yml` on an existing wiki means the defaults and is not an error.
- Log order, link style and OKF version are **not** configurable; this document fixes them.

---

<!-- added in 02 -->

<!-- changed in keeper: OKF 0.2 -->
## 11. Repos as sources (added in 02)

A repository is a source like any other; only its raw artifact is a directory
instead of a file.

```
wiki-<slug>/
├── raw/
│   ├── <slug>.md                                # local note (01)
│   ├── article-<slug>.md                        # fetched article (02)
│   ├── youtube-<slug>.md                        # transcript (02 — skeleton adapter)
│   └── repos/
│       └── .github-<owner>-<repo>/              # shallow clone, --depth 1
└── wiki/
    └── repos/
        ├── index.md                             # GENERATED — grouped by repo
        └── github-<owner>-<repo>/
            └── ARCHITECTURE.md                  # type: repo
```

**Origin prefixes** keep `raw/` self-describing at a glance: no prefix = a local
note, `article-` = fetched from the web, `youtube-` = a transcript. The prefix is
part of the identity, so the same slug from two origins never collides.

**The clone is dot-prefixed** (`.github-…`) for one reason worth stating: Obsidian
ignores dot-directories, so a 100 MB checkout stays out of the vault, the graph
view and search with zero configuration. It is also gitignored — clones are
regenerable, and nobody should review a vendored copy of someone else's repo in a
pull request.

**Source-like pages now include `wiki/repos/*/*.md`.** A repo page carries the same
`entities:` / `concepts:` frontmatter as a source page and counts toward the ≥2
threshold identically. This is the point: a concept mentioned in one note and
implemented in one codebase has two independent witnesses, and materializes.

**Repos refresh instead of skipping.** Re-ingesting a repo runs `git fetch` plus
`reset --hard`, rewrites `ARCHITECTURE.md`, bumps `commit_sha` and `generated.at`,
and re-runs the ingest tail. Every other origin is immutable once ingested (§7); a
repo is a moving target, and pretending otherwise would leave permalinks pointing
at code that no longer exists.

## 12. Context discipline (added in 02)

Layer 01's ten-source cap came from a single fact: the orchestrator read every
note. This layer removes the cap by making sure nothing ever reads everything.

| Who | May read | Never reads |
|---|---|---|
| orchestrator, ingest mode | receipts, script output, `wiki/log.md` | `raw/`, wiki pages |
| orchestrator, query mode | `wiki/index.md`, subdirectory indexes, and the wiki pages the disclosure ladder (`QUERY.md` Q.3) tells it to read | `raw/`, except where `QUERY.md` says so |
| orchestrator, lint mode | script JSON from `lint.py`, reviewer receipts, the report it writes, and one exception: the frontmatter `created` line of an earlier same-day report (grep only) | `raw/`, wiki pages |
| `lint_reviewer` | its group of pages, the pages they cite, and for the C02 spot check one raw file per source page | other raw files, clones |
| `source_writer` | **one** raw file | any other raw file, any wiki page |
| `repo_writer` | one clone | other clones, source pages |
| `page_writer` | the source-like pages for its slug | `raw/`, other aggregate pages |
| `overview_writer` | frontmatter; ≤5 full pages | `raw/` |

Each raw file is read **exactly once, ever** — after that, the wiki is the
interface. That is what makes the wiki compound: the expensive read happens on
ingest, and every future question is answered from pages that already exist.

---

<!-- added in 03 -->

## 13. Write regimes (added in 03)

Once querying the wiki can also write to it, "who owns this page" stops being
obvious. Three regimes, and the boundary between them is the layer's whole safety
story:

| Regime | Pages | Written by | Rewritten when |
|---|---|---|---|
| **ingest-owned** | `raw/`, `sources/`, `entities/`, `concepts/`, `overview.md`, `repos/*/ARCHITECTURE.md` | the ingest path | a source is added or a repo refreshed |
| **interaction-owned** | `questions/`, `notes/`, `open-questions.md` | the query path | a question is asked or answered |
| **interaction-owned** | `lint/` | the lint path, one report per day | a lint run; the same day overwrites |
| **repo notes** | `repos/<repo>/<question-slug>.md` | `repo_writer` in `question` mode, from the query path | never — they are appended, then flow through the ingest tail |

The rule that follows: **query mode never edits an ingest-owned page.** Reading a
source cannot change what the wiki says the source means, or the same question
asked twice would leave two different wikis behind.

When an answer reveals that an ingest-owned page is wrong, thin or stale, that is
information — record it in `open-questions.md` and let the next ingest fold it in.

### The one crossing point

A repo note *is* a source-like page: it carries `entities:` / `concepts:` and it
counts toward the ≥2 threshold. So after one is written, the query path runs the
**ingest tail** (§8) — recount, update the qualifying pages, rewrite the overview,
regenerate the index, append the log. That is the only way an answer reaches an
ingest-owned page, and it goes through the same machinery an ingest would.

`questions/` and `notes/` are deliberately **not** source-like. They are written
*from* wiki pages, so counting them would let the wiki cite itself into existence —
one note about a concept would be enough to keep that concept's page alive. That
is why `count_mentions.py` is unchanged in this layer.

## 14. The interaction layer (added in 03)

```
wiki-<slug>/wiki/
├── questions/                          # type: question — slim pointers, ≤25 lines
│   ├── index.md                        # GENERATED
│   └── YYYY-MM-DD-<slug>.md
├── notes/                              # type: note — the actual synthesized answers
│   ├── index.md                        # GENERATED
│   └── <slug>.md
├── lint/                               # type: lint_report — one report per day
│   ├── index.md                        # GENERATED
│   └── YYYY-MM-DD.md
└── open-questions.md                   # type: open_question — append-only, dated (lint appends C04 findings too)
```

Three rules keep this layer from turning into a chat log:

1. **Always write the question page; write a note only when the answer earned it** —
   ≥2 wiki pages cited, or the user asked to save it.
2. **The question page never holds the answer.** It is a pointer with a one-line
   why-this-matters, so `questions/index.md` stays cheap to scan.
3. **One note per topic.** A repeat question enriches the existing note and adds a
   second question page pointing at it — never a second note.

<!-- changed in keeper: OKF 0.2 -->
Query-path pages (`questions/`, `notes/`, `open-questions.md`) carry
`generated.by: llm-wiki-keeper/orchestrator`; a repo note carries
`llm-wiki-keeper/repo_writer`. Each query appends one `**Query**` entry to the log.
A lint report carries `llm-wiki-keeper/orchestrator` and each run appends one `**Lint**` entry.
Lint never edits an ingest-owned or interaction-owned page except its own report and the `open-questions.md` append.

---

## 15. Known limitations

1. Obsidian's Properties panel cannot edit nested YAML such as `generated` and
   `sources`. The YAML is valid and the bundle conforms to OKF 0.2; edit those keys
   in source mode.
2. Provenance is per section, not per sentence.
3. Text anchors do not scroll on GitHub. They do in Obsidian.
4. Obsidian's Properties panel cannot render nested YAML (`generated`, `sources`): they show as
   raw orange JSON.
5. Standard markdown links and plain paths are not clickable in frontmatter; only wikilinks are.
   That is why the reference keys use wikilinks.
6. `sources[].resource` paths in frontmatter are therefore not clickable either, by design,
   because OKF defines them.
7. Clicking a link to a page that does not exist yet (a promissory link) makes Obsidian create an empty note, in the vault root under the path written in the link, which is outside wiki/ when the vault root is wiki-<slug>/. Do not click hollow graph nodes or unresolved links; lint should flag empty stub notes.

The Obsidian setting Settings > Editor > "Properties in document" = Hidden or Source removes
the visual noise.
