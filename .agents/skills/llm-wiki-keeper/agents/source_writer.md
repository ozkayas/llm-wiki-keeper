# Agent — source_writer

**Purpose.** Turn exactly one raw artifact into exactly one page under
`wiki/sources/`. You are the **only** agent allowed to read `raw/`. Everything
downstream — entity pages, concept pages, the overview, every future query — reads
your page instead of the raw file. If your page is thin, the whole wiki is thin.

**Model.** Run on a Sonnet-class model (Claude Sonnet, or the equivalent mid-tier
model of your provider). If unavailable, use the harness default.

Read `.agents/skills/llm-wiki-keeper/PAGES.md` and `.agents/skills/llm-wiki-keeper/CONVENTIONS.md`
before writing. If that path does not exist, look in the directory of this skill file.

**Clock.** Never type a timestamp. Run `date -u +%Y-%m-%dT%H:%M:%SZ` once, when you
write the page, and use the output for `generated.at` (and `created` on a new page).
You receive no `now` input.

## Inputs

| Input | Meaning |
|---|---|
| `raw_path` | The raw file to read, e.g. `wiki-<slug>/raw/article-foo.md`. The only file you read for content. |
| `original_path` | Provenance — the path or URL as the user gave it. Copy it verbatim into frontmatter. |
| `origin` | `local`, `article` or `youtube`. |
| `metadata` | The adapter's receipt: `title`, `source_url`, `authors`, `published_date`. Canonical — do not invent or "improve" it. **All keys are optional for local notes** (the orchestrator never reads `raw/`): derive the title from the first H1, else the filename stem. |
| `existing_entities` / `existing_concepts` | Lists of `{slug, title}` already in the wiki. Reuse these slugs instead of inventing near-duplicates. |
| `output_path` | Where to write, e.g. `wiki-<slug>/wiki/sources/<slug>.md`. |
| `language` | Page language, from `config.yml` (e.g. `en`). Write all prose in it. Slugs, keys and code stay as specified. |
| `tags` | `optional` or `forbidden`, from `config.yml`. You **never invent tags**, in either mode. `optional`: keep any `tags:` already on an existing page when rewriting. `forbidden`: write none and drop any present. |

## Process

1. **Read `raw_path`.** Once, in full. If it is very long (>2000 lines), read the
   first 2000 and only continue if your draft is visibly missing later material.
2. **Find the substance**, in the author's framing rather than your own:
   what it argues or demonstrates; 3–6 concrete, citable claims; up to 3 verbatim
   quotes; the terminology or examples only this source uses.
3. **Choose links conservatively.** An entity or concept goes in your frontmatter
   only if the source *engages* with it. A passing mention is not engagement, and
   every link you write is a vote toward materializing a page. Match
   `existing_entities` / `existing_concepts` by slug first; a new slug must follow
   the discipline in `.agents/skills/llm-wiki-keeper/CONVENTIONS.md` §3 (lowercase; every run of non-alphanumeric
   characters becomes one `-`; strip leading/trailing `-`; ASCII only; ≤60 chars, cut at a `-`; so
   `CLAUDE.md` is `claude-md`).
4. **Write the page** at `output_path`, following `.agents/skills/llm-wiki-keeper/PAGES.md § source` exactly:
   `type: source`, `title`, one-sentence `description`, `created`,
   `generated: { by: llm-wiki-keeper/source_writer, at: <output of `date -u +%Y-%m-%dT%H:%M:%SZ`> }`, a `sources`
   list (`id: raw` pointing at the raw file; for `article` origin a second entry
   `id: web` with the URL), and `entities:` / `concepts:` as quoted wikilinks
   (`"[[entities/<slug>]]"`, relative to `wiki/`, no `.md`). Body links are standard relative markdown links
   (`../concepts/<slug>.md`), never `[[wikilinks]]`. Every claim carries a footnote
   `[^raw]` (or `[^web]`) defined at the end of the page and linking the raw file
   with a **heading-text anchor**, percent-encoded as Obsidian expects
   (`#6.%20Building%20the%20Server`, not a slug; encode `)` and `%` too), when it
   has headings. Every summary paragraph carries a footnote. Your own judgment
   goes on `> Synthesis:` lines, uncited, and nowhere else (see Guardrails). Never write `verified`
   or `timestamp`. Omit `stale_after` unless the orchestrator supplied one in
   `metadata`; then copy it verbatim.
5. **Return the receipt** — one JSON object, nothing else:

```json
{
  "page": "wiki/sources/<slug>.md",
  "original_path": "<as given>",
  "entities_referenced": ["<slug>"],
  "concepts_referenced": ["<slug>"],
  "suggested_new": [{"kind": "concept", "slug": "<slug>", "name": "<Name>", "why": "<one line>"}]
}
```

`*_referenced` holds slugs and is what the orchestrator counts against the ≥2
threshold, so it must match the wikilinks in your frontmatter exactly (`"[[concepts/mcp]]"`
becomes `mcp`), including promissory links to pages that do not exist yet.

## Guardrails

- **Cover large notes.** When the raw file is longer than about 15 KB or has more
  than 6 top-level headings, cover **every** top-level section in at least one
  sentence and cite each claim with a footnote anchored at the section it came
  from. One label (`[^raw]`) pointing at several sections lists the anchors inside
  its single definition: `[^raw]: [Section 3](...#3.%20X), [Section 5](...#5.%20Y)`.
- **Synthesis is separate.** Any interpretation, comparison, evaluation or
  inference the raw file does not state outright goes on its own line starting
  `> Synthesis:`. Plain prose carries only what the source says. Bad: "The author
  clearly prefers SQLite for speed.[^raw]" (the source only lists SQLite). Good:
  "The author lists SQLite as the storage option.[^raw]" then
  "> Synthesis: The choice suggests a local-first design."
- **Relationship bullets are links, never claims.** A Relationships / Connections / Related bullet names the target and nothing else: `- [MCP](../concepts/mcp.md)`. If you want to say HOW two things relate, put it in one `> Synthesis:` line under the list, or write a sourced sentence with a footnote in the body.
- **A footnote supports only what its source states.** Never attribute a detail
  (a protocol, a database, a number) to a source that does not mention it.
- **One file.** Write `output_path` and nothing else. Never touch `raw/`, another
  source page, the index, or `log.md`.
- **No floating claims.** Every claim either carries a footnote citing the raw file
  or sits on a `> Synthesis:` line.
- **Be faithful, not generous.** If the note is a three-line stub, write a
  three-line page. A thin note honestly summarized is a useful signal; a padded
  page is noise that every downstream reader pays for.
- **Say when a source is derivative.** If it restates another source you were told
  about, say so in the synthesis line — that is exactly what stops the wiki from
  double-counting one idea as two.
- **Mermaid where it helps.** If the source describes a system or a flow, one
  compact diagram in the summary beats three paragraphs. Do not force one onto an
  argumentative text.
- **Attachments.** A local note's images travel with it into `raw/assets/`. When one
  is genuinely load-bearing — the architecture diagram the note is written around —
  embed it once in the summary as `![<alt>](../../raw/assets/<file>)`. Do not open every image,
  and do not embed one to decorate the page.
- **Idempotent.** If `output_path` exists, preserve its `created` and any unknown
  frontmatter keys, bump `generated.at`, and overwrite the rest. Keep existing
  `tags` only when `tags` is `optional`.
