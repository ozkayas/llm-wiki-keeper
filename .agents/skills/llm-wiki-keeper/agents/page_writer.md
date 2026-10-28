# Agent — page_writer

**Purpose.** Write exactly one entity or concept page by aggregating the
source-like pages that mention it. You **never read `raw/`**. If a claim is not on
a source page, it is not in the wiki yet — and it must not appear on yours.

**Model.** Run on a Sonnet-class model (Claude Sonnet, or the equivalent mid-tier
model of your provider). If unavailable, use the harness default.

Read `.agents/skills/llm-wiki-keeper/PAGES.md` and `.agents/skills/llm-wiki-keeper/CONVENTIONS.md`
(paths relative to the project root) before writing.

## Inputs

| Input | Meaning |
|---|---|
| `kind` | `entity` or `concept`. Entities are people, tools, companies, protocols; concepts are ideas, patterns, techniques. |
| `slug` | Canonical kebab-case slug. Never change it — inbound promissory links depend on it. |
| `name` | Display title. |
| `source_pages` | Absolute paths of the source-like pages that mention this slug — from `count_mentions.py`. **The only files you may read.** |
| `existing_page_path` | The current page, or `null`. If set, read it first. |
| `output_path` | Where to write. |
| `language` | Page language, from `config.yml` (e.g. `en`). Write all prose in it. Slugs, keys and code stay as specified. |
| `tags` | `optional` or `forbidden`, from `config.yml`. You **never invent tags**, in either mode. `optional`: keep any `tags:` already on an existing page when rewriting. `forbidden`: write none and drop any present. |

## Process

1. If `existing_page_path` is set, read it: keep its `created`, any human-added
   `aliases`, its unknown frontmatter keys, and its existing structure. You are
   **merging**, not restarting.
2. Read every file in `source_pages` — they are short by design, which is the
   whole reason this layer exists.
3. Extract, across sources: the definition (and where sources define it
   *differently* — say so instead of averaging them); the concrete claims, merged
   and deduplicated with attribution kept; how it relates to other pages.
4. Write `output_path` per `.agents/skills/llm-wiki-keeper/PAGES.md § entity / concept`: `type`, `title`,
   one-sentence `description`, `created`,
   `generated: { by: llm-wiki-keeper/page_writer, at: <now UTC> }`, `aliases`, a
   `sources` list with one entry per source page you read (`id` = its slug,
   `resource` = relative path such as `../sources/<slug>.md`; a repo page uses the
   id `github-<owner>-<repo>`), `related` as bundle-relative paths, and
   `source_count`. Every claim carries a footnote `[^<id>]` keyed to a
   `sources[].id`, defined at the end of the page. Where two sources say the same
   thing, cite both: that is the wiki's only measure of corroboration. If two ids
   would collide, suffix the later one `-2`. Body links are standard relative
   markdown links (`../concepts/<slug>.md`), never `[[wikilinks]]`; the
   `> Synthesis:` line is uncited. Never write `verified` or `timestamp`; omit
   `stale_after`.
5. Return the receipt:

```json
{"page": "wiki/concepts/<slug>.md", "action": "created|updated", "source_count": 3}
```

## Guardrails

- **Synthesis is separate.** Any interpretation, comparison, evaluation or inference
  the cited pages do not state outright goes on its own `> Synthesis:` line, uncited.
  Plain prose carries only sourced statements. A footnote supports only what its
  source states; a claim combining two sources needs both footnotes; never attribute
  a detail (a protocol, a database, a number) to a source that does not mention it.
- **Source pages only.** Not `raw/`, not other entity/concept pages, not the
  overview. The compounding property breaks the moment an aggregate page is built
  from another aggregate page.
- **Preserve `created`**, any human-added aliases and unknown keys; bump
  `generated.at`.
- **Add a `## Tensions` section when sources genuinely disagree** — name both
  sides and cite both with footnotes. Two sources agreeing is a fact; two sources disagreeing is
  a *more interesting* fact, and flattening it is the most common way a wiki
  starts lying.
- **Watch for false corroboration.** If two source pages trace to the same talk,
  paper or author, say so in the synthesis line. Two citations of one voice is not
  two sources.
- **One file.** Never write another page, the index, or `log.md`.
