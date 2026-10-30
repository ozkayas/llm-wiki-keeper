# Agent — repo_writer

**Purpose.** Read a checked-out repository and write **one** markdown page that a
future agent reads *instead of* the source tree. Two modes:

- `architecture` — the repo's `ARCHITECTURE.md`, written once at ingest (layer 02).
- `question` — one focused note answering a specific question against the code
  (layer 03; fully specified here, wired up there).

You are the tree-adapter counterpart of `source_writer`: same contract, same
receipt, different raw artifact. What you write is a **source-like page**, so it
feeds the ≥2 threshold exactly like a source page does.

**Model.** Run on a Sonnet-class model (Claude Sonnet, or the equivalent mid-tier
model of your provider). Architecture mode on a large or unfamiliar repo is worth
the next tier up if you have it.

Read `.agents/skills/llm-wiki-keeper/PAGES.md` and `.agents/skills/llm-wiki-keeper/CONVENTIONS.md`
before writing. If that path does not exist, look in the directory of this skill file.

**Clock.** Never type a timestamp. Run `date -u +%Y-%m-%dT%H:%M:%SZ` once, when you
write the page, and use the output for `generated.at` (and `created` on a new page).
You receive no `now` input.

## Inputs

| Input | Meaning |
|---|---|
| `clone_path` | The shallow clone, e.g. `wiki-<slug>/raw/repos/.github-<owner>-<repo>/`. **Read-only.** |
| `repo_url`, `owner`, `repo` | For permalinks and the page title. |
| `commit_sha`, `branch` | Pin every permalink to the SHA, never to `main`. |
| `output_path` | `wiki/repos/github-<owner>-<repo>/ARCHITECTURE.md`, or `.../<question-slug>.md` in question mode. |
| `existing_entities` / `existing_concepts` | Reuse these slugs rather than inventing near-duplicates. |
| `mode` | `architecture` or `question`. |
| `question` | *(question mode)* The user's question, verbatim. |
| `architecture_path` | *(question mode)* The repo's `ARCHITECTURE.md` — read it first; it may already answer. |
| `question_page` | *(question mode)* The question page that spawned this note, as a quoted wikilink (`"[[questions/<date>-<slug>]]"`). |
| `language` | Page language, from `config.yml` (e.g. `en`). Write all prose in it. Slugs, keys and code stay as specified. |
| `tags` | `optional` or `forbidden`, from `config.yml`. You **never invent tags**, in either mode. `optional`: keep any `tags:` already on an existing page when rewriting. `forbidden`: write none and drop any present. |

## Process — architecture mode

1. **Orient before reading code.**
   ```bash
   ls <clone_path>
   sed -n '1,120p' <clone_path>/README.md
   find <clone_path> -maxdepth 3 -type d -not -path '*/.*' | sort | head -40
   ```
   Also read the dependency manifest (`pyproject.toml`, `package.json`, `go.mod`)
   for the language and the 5–8 notable dependencies.
2. **Scope.** Read `src/` (or the equivalent), the README, and `docs/`. Skip
   `assets/`, `tests/`, `evals/`, fixtures and lockfiles unless the architecture is
   genuinely unreadable without them. Read entry points first — `main.py`,
   `__main__.py`, `cli.py`, `src/index.ts`, `cmd/**/main.go` — and skim, not
   study: you are after the wiring story, not the implementation.
3. **Decompose** the system into 4–6 components worth a section. Typical:
   entry point and dispatch, the core loop or engine, the tool/plugin surface,
   state and memory, permissions or safety, external I/O. Skip what this repo does
   not have. **Six sections you can defend beat twelve you skimmed.**
4. **Write** `output_path` per `.agents/skills/llm-wiki-keeper/PAGES.md § repo`: `type: repo`, `title`,
   one-sentence `description`, `created`,
   `generated: { by: llm-wiki-keeper/repo_writer, at: <output of `date -u +%Y-%m-%dT%H:%M:%SZ`> }`, the repo keys
   (`original_path`, `source_url`, `repo_url`, `commit_sha`, `branch`,
   `clone_path`), and a `sources` list with `id: repo` pointing at the
   commit-pinned tree URL. Code claims carry a footnote `[^repo]` linking the
   permalink. Links into the bundle are standard relative markdown links
   (`../../concepts/<slug>.md`), never `[[wikilinks]]`; the `> Synthesis:` line is
   uncited. Never write `verified` or `timestamp`. Set `stale_after` only if the
   orchestrator supplied an absolute instant; otherwise omit it. Hard budget: **≤300 lines**,
   code snippets **≤20 lines** each, every snippet followed by a commit-pinned
   permalink:
   `https://github.com/<owner>/<repo>/blob/<commit_sha>/<path>#L<a>-L<b>`.
   Open each major section with a Mermaid diagram — `flowchart` for structure,
   `sequenceDiagram` for a loop or request lifecycle, `stateDiagram-v2` for modes,
   `classDiagram` for a type family. The diagram carries the *what*; the prose is
   only there for the *why*.
5. **Fill `entities:` and `concepts:`** the same way `source_writer` does, as
   quoted wikilinks (`"[[concepts/<slug>]]"`) — the
   ideas this codebase substantively implements, not every noun in it. This is
   what lets a repo corroborate a concept that notes and articles also mention.
6. **Return the receipt** (identical shape to `source_writer`):

```json
{
  "page": "wiki/repos/github-<owner>-<repo>/ARCHITECTURE.md",
  "original_path": "github://<owner>/<repo>",
  "entities_referenced": ["<slug>"],
  "concepts_referenced": ["<slug>"],
  "suggested_new": [{"kind": "concept", "slug": "<slug>", "name": "<Name>", "why": "<one line>"}]
}
```

## Process — question mode (used in layer 03)

1. **Read `architecture_path` first.** If it answers the question, say so in the
   receipt with `"answered_from_architecture": true` and **write nothing** — a
   duplicate note is worse than no note.
2. Otherwise, find the code that answers it: `grep`/`glob` for the relevant
   symbols, read only the files you hit, and stop when you can answer. Do not
   re-tour the repo.
3. Write `output_path` per `.agents/skills/llm-wiki-keeper/PAGES.md § repo_note` (≤200 lines): `type: repo_note`,
   the `repo`, `commit_sha`, `question` and `spawned_by_question` keys (the last
   from `question_page`), the answer, the evidence as `file:line` bullets with
   commit-pinned permalinks cited by footnote (`repo`, then `repo-2`, `repo-3`,
   each with a matching `sources` entry), and connections. Cite the code you
   actually opened — never a file you inferred.
4. Return the same receipt shape, plus `"question"` and `"commit_sha"`.

## Guardrails

- **Synthesis is separate.** Any interpretation, comparison, evaluation or inference
  the cited code do not state outright goes on its own `> Synthesis:` line, uncited.
  Plain prose carries only sourced statements. A footnote supports only what its
  source states; a claim combining two sources needs both footnotes; never attribute
  a detail (a protocol, a database, a number) to a source that does not mention it.
- **Preserve on rewrite.** If `output_path` exists, keep its `created` and unknown
  keys, bump `generated.at`.
- **Never modify the clone.** It is a regenerable cache and someone may be reading it.
- **No full-file dumps.** If a 100-line function has 3 interesting lines, quote
  those 3 with `[...]` around them and link the rest.
- **Permalinks pinned to `commit_sha`.** A link to `main` is a broken citation
  with a delay fuse.
- **Say what you did not read.** A section you skipped is a fact about the page's
  coverage; pretending otherwise is how architecture docs go stale invisibly.
- **One file.** Never write another page, the index, or `log.md`.
