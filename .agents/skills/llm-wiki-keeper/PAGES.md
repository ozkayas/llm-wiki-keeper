# PAGES — page contracts

One section per page `type`: the frontmatter, the body skeleton, the length
budget, and the **receipt** — the small JSON blob that describes what was
written. In layer 01 the orchestrator writes the pages itself and the receipt is
just the set of facts it must keep in mind for the ingest tail. From layer 02 on,
subagents write the pages and return that receipt literally.

<!-- changed in keeper: OKF 0.2 -->
Shared rules (frontmatter keys, `generated`, `sources` + footnote citations,
relative markdown links, one-sentence `description`, ISO-8601 instants) live in
`CONVENTIONS.md` §5-§6 — they are not repeated here. In every template below:

- `generated: { by: llm-wiki-keeper/<agent>, at: <ISO-8601 UTC> }` replaces the old
  `timestamp`; bump `at` on every meaningful change. `created` is preserved.
- Timestamps come from `date -u +%Y-%m-%dT%H:%M:%SZ` run at write time, never typed by hand (`CONVENTIONS.md` §5).
- Never write `verified`, and never invent `tags`. Preserve unknown keys on rewrite.
- Frontmatter page-reference keys (`entities`, `concepts`, `related`, `answer_doc`, `sources_cited`,
  `spawned_by_question`, `repo`) hold quoted wikilinks relative to the bundle root, no leading slash,
  no `.md`: `"[[concepts/mcp]]"`. `sources[].resource` is not one of them and stays a relative path or URL.
  Body links stay standard markdown, relative to the page (`../concepts/mcp.md`); no wikilinks in bodies.
- Claims carry a footnote `[^id]` whose id is a `sources[].id`; `> Synthesis:` lines carry none.
- **Synthesis.** Any interpretation, comparison, evaluation or inference that the cited material does not state outright goes on its own line starting `> Synthesis:`, on every page type including overview and notes. Plain prose carries only sourced statements. A footnote supports only what its source states; a claim that combines two sources needs both footnotes; never attribute a detail (a protocol, a database, a number) to a source that does not mention it.
- **Relationship bullets.** A Relationships / Connections / Related bullet is a link and nothing else: `- [MCP](../concepts/mcp.md)`. A label such as `- [MCP](../concepts/mcp.md): protocol it speaks` is not allowed, because it asserts something the sources must support. A relationship bullet names the target and nothing else. If you want to say HOW two things relate, put it in one `> Synthesis:` line under the list, or write a sourced sentence with a footnote in the body.
- **Definition blockquote.** On entity, concept, repo and repo_note pages the single `> <definition>` line right after the H1 mirrors the frontmatter `description`; it needs no footnote because the cited Definition section follows. It must be exactly one line, and it is the only uncited blockquote besides `> Synthesis:` and metadata lines.
- **Anchors point at the heading text, percent-encoded, as Obsidian expects** (not a GitHub slug): `../../raw/my-note.md#6.%20Building%20the%20Server`. Spaces become `%20`, other characters stay as in the heading, and `)` and `%` are encoded too (`%29`, `%25`).
- Receipts keep their field names. They never held wikilinks or timestamps, so none changed.
  `page` is a path relative to `wiki-<slug>/`.

---

<!-- changed in keeper: OKF 0.2 -->
## `source` — `wiki/sources/<slug>.md`

The LLM's reading of exactly one ingested artifact. Written once, from `raw/`.
Written by `source_writer` (layer 01: the orchestrator, `generated.by: llm-wiki-keeper/orchestrator`).

```markdown
---
type: source
title: <the note's H1, else its filename stem>
description: <ONE sentence — the sharpest gist of this source>
created: <ISO-8601 UTC>
generated: { by: llm-wiki-keeper/source_writer, at: <ISO-8601 UTC> }
origin: local
original_path: <path as given, relative to the project root>
source_url: null
authors: []
published_date: null
raw_file: raw/<slug>.md
sources:
  - id: raw
    resource: ../../raw/<slug>.md
    title: <title>
  # article origin only, a second entry:
  # - { id: web, resource: <url>, title: <title>, author: <name>, last_modified: <date if known> }
entities:
  - "[[entities/<slug>]]"
concepts:
  - "[[concepts/<slug>]]"
---

# <title>

> [Raw](../../raw/<slug>.md) · local

## Summary

<2–3 paragraphs in the author's own framing — what this note argues, explains or
demonstrates. Not a generic restatement of the topic. Every paragraph ends with
a footnote.[^raw]>

## Key claims

- <concrete, citable assertion>.[^raw]
- ... (3–6 bullets)

## Notable quotes

> "<verbatim, ≤3 sentences>"
> — [<heading>](../../raw/<slug>.md#<Heading%20text>)

## Connections

- [<Name>](../entities/<slug>.md)
- [<Name>](../concepts/<slug>.md)

> Synthesis: <one line — how this note sits against the rest of the wiki>

[^raw]: [<title>, "<heading>"](../../raw/<slug>.md#<Heading%20text>)
```

Several claims from the same heading reuse `[^raw]`. For claims from different
headings, keep the single label and list the anchors inside its one definition:
`[^raw]: [Section 3](../../raw/<slug>.md#3.%20X), [Section 5](../../raw/<slug>.md#5.%20Y)`.
The label stays unique.

**Large notes.** When the raw file is longer than about 15 KB or has more than 6
top-level headings, the page must cover **every** top-level section in at least one
sentence, and cite each claim with a footnote anchored at the section it came from.
The 300–600 word budget stretches as far as that needs, no further.

**Budget** 300–600 words. A thin note gets a thin page; padding is worse than brevity.
**Only the source page may read `raw/`.** Everything downstream reads this page instead.

**Worked example**

```markdown
---
type: source
title: Agent loops in practice
description: A practitioner's account of why agent loops fail without a stop condition.
created: 2026-10-28T09:00:00Z
generated: { by: llm-wiki-keeper/source_writer, at: 2026-10-28T09:00:00Z }
origin: local
original_path: notes/agent-loops.md
source_url: null
authors: []
published_date: null
raw_file: raw/agent-loops.md
sources:
  - id: raw
    resource: ../../raw/agent-loops.md
    title: Agent loops in practice
entities:
  - "[[entities/claude-code]]"
concepts:
  - "[[concepts/agent-loop]]"
  - "[[concepts/mcp]]"
---

# Agent loops in practice

> [Raw](../../raw/agent-loops.md) · local

## Summary

The author argues that an agent loop is only as good as its exit condition, and
shows three runs where a missing budget turned a ten-minute task into an hour.[^raw]

## Key claims

- A loop without a step budget will retry a failing tool indefinitely.[^raw]
- Tool errors should be returned to the model, not swallowed.[^raw]

## Notable quotes

> "The loop is not the hard part. Knowing when to stop is."
> — [Stopping](../../raw/agent-loops.md#Stopping)

## Connections

- [Claude Code](../entities/claude-code.md)
- [Agent loop](../concepts/agent-loop.md)
- [MCP](../concepts/mcp.md)

> Synthesis: Complements the MCP note by showing where tool errors surface in the loop.

[^raw]: [Agent loops in practice, "Stopping"](../../raw/agent-loops.md#Stopping)
```

**Receipt**

```json
{
  "page": "wiki/sources/<slug>.md",
  "original_path": "<path as given>",
  "entities_referenced": ["<slug>"],
  "concepts_referenced": ["<slug>"],
  "suggested_new": [{"kind": "concept", "slug": "<slug>", "name": "<Name>", "why": "<one line>"}]
}
```

`*_referenced` are the slugs actually listed in the frontmatter wikilinks (promissory
ones included) — this is what the ≥2 threshold counts. Be conservative: a passing
mention is not an engagement.

---

<!-- changed in keeper: OKF 0.2 -->
## `entity` / `concept` — `wiki/entities/<slug>.md`, `wiki/concepts/<slug>.md`

Same contract, two kinds of subject: an **entity** is a person, tool, company or
framework; a **concept** is an idea, pattern or technique. Written by
`page_writer` by aggregating the source-like pages that mention it — **never** by
re-reading `raw/`.

```markdown
---
type: <entity|concept>
title: <canonical display name>
description: <ONE sentence definition>
created: <ISO-8601 UTC — preserved from the existing page>
generated: { by: llm-wiki-keeper/page_writer, at: <ISO-8601 UTC> }
aliases: []
sources:
  - id: <source-slug>
    resource: ../sources/<source-slug>.md
    title: <source title>
  - id: <source-slug-2>
    resource: ../sources/<source-slug-2>.md
    title: <source title>
related:
  - "[[concepts/<slug>]]"
source_count: <int>
---

# <name>

> <one-line definition, or "Multiple framings — see Definition">

## Definition

<1–2 paragraphs. Where sources disagree, lay the framings side by side and cite
each one — do not average them into mush.>

## Key claims

- <claim>.[^<source-slug>][^<source-slug-2>]
- ...

## Relationships

- [<Name>](../concepts/<slug>.md)

> Synthesis: <one line — how this fits the wiki as a whole>

[^<source-slug>]: [<source title>](../sources/<source-slug>.md)
[^<source-slug-2>]: [<source title>](../sources/<source-slug-2>.md)
```

A repo page that contributes is listed like any source: `id: <repo-page-slug>`,
`resource: ../repos/github-<owner>-<repo>/ARCHITECTURE.md`. Use the directory slug
`github-<owner>-<repo>` as the id.

**Budget** 200–500 words.
**Updating an existing page**: preserve `created`, `verified` (if a human added
it), any human-added `aliases` and unknown keys; merge new claims into the
existing structure instead of rewriting from zero.

**Worked example**

```markdown
---
type: concept
title: MCP
description: An open protocol that lets an agent harness discover and call external tools.
created: 2026-10-28T09:05:00Z
generated: { by: llm-wiki-keeper/page_writer, at: 2026-10-28T09:05:00Z }
aliases: [Model Context Protocol]
sources:
  - id: agent-loops
    resource: ../sources/agent-loops.md
    title: Agent loops in practice
  - id: tool-servers
    resource: ../sources/tool-servers.md
    title: Writing tool servers
related:
  - "[[concepts/agent-loop]]"
source_count: 2
---

# MCP

> An open protocol for connecting an agent harness to external tools and data.

## Definition

Both notes treat MCP as the harness side of tool use: the harness, not the model,
connects to servers and exposes their tools.[^agent-loops][^tool-servers]

## Key claims

- Tool errors from an MCP server return to the model as results.[^agent-loops]
- A server declares its tools; the client lists them at start-up.[^tool-servers]

## Relationships

- [Agent loop](../concepts/agent-loop.md)

> Synthesis: The loop is where MCP results are consumed, which is why tool errors are the model's problem to read.

[^agent-loops]: [Agent loops in practice](../sources/agent-loops.md)
[^tool-servers]: [Writing tool servers](../sources/tool-servers.md)
```

**Receipt**

```json
{"page": "wiki/concepts/<slug>.md", "action": "created|updated", "source_count": 3}
```

---

<!-- changed in keeper: OKF 0.2 -->
## `overview` — `wiki/overview.md`

The one page a newcomer reads first. Navigation, not argument. Written by `overview_writer`.

```markdown
---
type: overview
title: <slug> — Overview
description: <ONE sentence — what this wiki covers>
created: <ISO-8601 UTC — preserved>
generated: { by: llm-wiki-keeper/overview_writer, at: <ISO-8601 UTC> }
sources:
  - id: <page-slug>
    resource: sources/<page-slug>.md     # or concepts/..., entities/...
    title: <page title>
---

# <slug> — Overview

## Themes

<2–4 clusters that the wiki has actually organized around — derived from
co-citation (which pages get cited together), not invented. Each theme: one
short paragraph with footnotes, 1–3 linked entity/concept pages, and the 1–2
source pages that make the case best. Which pages cluster is observed; why, or
what they have in common, goes on a `> Synthesis:` line.>

## Index

### Entities (N)
- [<Name>](entities/<slug>.md) — <one line>

### Concepts (N)
- [<Name>](concepts/<slug>.md) — <one line>

### Repos (N)   <!-- only when wiki/repos/ exists -->
- [<owner>/<repo>](repos/github-<owner>-<repo>/ARCHITECTURE.md) — <one line>

## Health

- Sources: N · Entities: N · Concepts: N
- Slugs at 1 mention (waiting for a second): [<slug>](concepts/<slug>.md), [<slug>](entities/<slug>.md)
```

The overview must **link** every waiting slug it lists (a promissory link is fine),
so each shows as a hollow node in the graph. The overview carries no page total
(it would go stale, and the overview is counted while it is being written); the
`## Health` section keeps the per-type counts, in body text only. No `total_*` key, ever, in the frontmatter.

`sources` lists the pages the theme paragraphs actually cite through footnotes
(not every page that appears in the Index or Health lists); each id has a
`[^id]: [Title](<dir>/<slug>.md)` definition at the end of the page.

**Budget** 300–600 words. Written from a **frontmatter walk** plus at most 5 full
page reads:

```bash
for f in wiki-<slug>/wiki/sources/*.md; do awk '/^---$/{c++; next} c==1' "$f"; echo "---END---"; done
```

The "slugs at 1 mention" line is the wiki telling you what it is about to learn —
those are the pages that materialize as soon as one more source arrives.

**Worked example**

```markdown
---
type: overview
title: ai-notes — Overview
description: Notes on agent harnesses, tool protocols and the loops that tie them together.
created: 2026-10-28T09:10:00Z
generated: { by: llm-wiki-keeper/overview_writer, at: 2026-10-28T09:10:00Z }
sources:
  - id: agent-loops
    resource: sources/agent-loops.md
    title: Agent loops in practice
  - id: tool-servers
    resource: sources/tool-servers.md
    title: Writing tool servers
---

# ai-notes — Overview

## Themes

**Tools and loops.** One note covers the loop and its exit condition.[^agent-loops]
The other covers how a server declares its tools.[^tool-servers] The wiki
organizes around [MCP](concepts/mcp.md) and the [Agent loop](concepts/agent-loop.md).

> Synthesis: Both notes place the loop and the tool connection in the harness.

## Index

### Entities (1)
- [Claude Code](entities/claude-code.md) — A coding agent harness.

### Concepts (2)
- [MCP](concepts/mcp.md) — A protocol for connecting a harness to external tools.
- [Agent loop](concepts/agent-loop.md) — The cycle of model call, tool call and result.

## Health

- Sources: 2 · Entities: 1 · Concepts: 2
- Slugs at 1 mention (waiting for a second): [context-window](concepts/context-window.md)

[^agent-loops]: [Agent loops in practice](sources/agent-loops.md)
[^tool-servers]: [Writing tool servers](sources/tool-servers.md)
```

Paths on this page are relative to `wiki/` (no `../`).

---

<!-- added in 02 -->

<!-- changed in keeper: OKF 0.2 -->
## `repo` — `wiki/repos/github-<owner>-<repo>/ARCHITECTURE.md`

The page that exists so nobody re-reads the clone. Written by `repo_writer` in
`architecture` mode; a **source-like page**, so its `entities:` / `concepts:`
count toward the ≥2 threshold.

```markdown
---
type: repo
title: <repo>
description: <ONE sentence — what this codebase is and does>
created: <ISO-8601 UTC>
generated: { by: llm-wiki-keeper/repo_writer, at: <ISO-8601 UTC> }
original_path: github://<owner>/<repo>
source_url: https://github.com/<owner>/<repo>/tree/<commit_sha>
repo_url: https://github.com/<owner>/<repo>
commit_sha: <full sha>
branch: main
clone_path: raw/repos/.github-<owner>-<repo>
sources:
  - id: repo
    resource: https://github.com/<owner>/<repo>/tree/<commit_sha>
    title: <owner>/<repo>
entities: []
concepts: []
---

# <repo> — Architecture

> Clone: `raw/repos/.github-<owner>-<repo>/` · [<owner>/<repo>](<repo_url>) @ `<sha[:7]>`

(The clone is a *directory*, so it is shown as a path in code formatting, not a
link — a link to a directory does not resolve in Obsidian.)

> Scope: <one sentence — what this page covers and what it deliberately skips>

## 1. Bird's-eye view

<1–2 paragraphs, then a mermaid flowchart of the whole system.>

## 2. Layout

<Top-level directories, one line each. Plain bullets — this is a map, not prose.>

## 3. Entry flow

<How the program starts and dispatches. Mermaid flowchart.>

## 4. Core loop

<The subsystem that makes this codebase what it is. Mermaid sequenceDiagram.>

## 5–6. <One or two more subsystems that earn a section>

## Reading order

1. `<file>` — <why start here>
2. ...

## Connections

- [<Name>](../../entities/<slug>.md)
- [<Name>](../../concepts/<slug>.md)

> Synthesis: <one line — what this codebase demonstrates that the notes only assert>
```

Code claims cite a commit-pinned permalink inline or via `[^repo]`:
`[^repo]: [src/agent.py:10-28](https://github.com/<owner>/<repo>/blob/<sha>/src/agent.py#L10-L28)`.
Links from this page into the bundle go up two levels (`../../`).

**Budget** ≤300 lines, 4–6 numbered sections, code snippets ≤20 lines with
commit-pinned permalinks (`.../blob/<sha>/<path>#L10-L28`).
**Scope** `src/` + `README` + `docs/`; skip `assets/`, `tests/`, `evals/` unless a
section is unreadable without them.
**Receipt** identical to `§ source`, with `original_path: github://<owner>/<repo>`.

**Worked example**

```markdown
---
type: repo
title: tinyagent
description: A 600-line Python agent harness that runs a model-and-tools loop from the command line.
created: 2026-10-28T10:00:00Z
generated: { by: llm-wiki-keeper/repo_writer, at: 2026-10-28T10:00:00Z }
original_path: github://acme/tinyagent
source_url: https://github.com/acme/tinyagent/tree/9f2c1ab7d3e4f5061728394a5b6c7d8e9f001122
repo_url: https://github.com/acme/tinyagent
commit_sha: 9f2c1ab7d3e4f5061728394a5b6c7d8e9f001122
branch: main
clone_path: raw/repos/.github-acme-tinyagent
sources:
  - id: repo
    resource: https://github.com/acme/tinyagent/tree/9f2c1ab7d3e4f5061728394a5b6c7d8e9f001122
    title: acme/tinyagent
entities: []
concepts:
  - "[[concepts/agent-loop]]"
---

# tinyagent — Architecture

> Clone: `raw/repos/.github-acme-tinyagent/` · [acme/tinyagent](https://github.com/acme/tinyagent) @ `9f2c1ab`

> Scope: `src/` and `README`; skips `tests/`.

## 1. Bird's-eye view

One module owns the loop; tools are plain functions registered in a dict.

## 4. Core loop

`run()` calls the model, executes tool calls, appends results, and stops at a step budget.[^repo]

## Connections

- [Agent loop](../../concepts/agent-loop.md)

> Synthesis: The code enforces the step budget the notes only recommend.

[^repo]: [src/agent.py:10-28](https://github.com/acme/tinyagent/blob/9f2c1ab7d3e4f5061728394a5b6c7d8e9f001122/src/agent.py#L10-L28)
```

---

<!-- added in 03 -->

<!-- changed in keeper: OKF 0.2 -->
## `question` — `wiki/questions/YYYY-MM-DD-<slug>.md`

A pointer, not an answer. It exists so "what have I already asked?" is answerable
without re-reading any answers. Written by the orchestrator.

```markdown
---
type: question
title: <the user's question, verbatim, no editorializing>
description: <ONE sentence — why this mattered>
created: <ISO-8601 UTC>
generated: { by: llm-wiki-keeper/orchestrator, at: <ISO-8601 UTC> }
asked_on: <YYYY-MM-DD>
answer_doc: "[[notes/<slug>]]"     # or a repo note, or null
sources_cited:
  - "[[concepts/<slug>]]"
  - "[[sources/<slug>]]"
---

# <question, verbatim>

> Asked on <date> · answered from <N> wiki pages

## Answer

Full answer: [<note title>](../notes/<slug>.md)

- <3–6 bullets, ≤12 words each, one per section of the note>

<!-- when answer_doc is null, replace the above with a ≤5-line inline summary -->
<!-- when the wiki does not cover the question: sources_cited lists the pages read to establish that, answer_doc stays null, and the open question is recorded -->

## Why this matters

<one sentence>
```

`answer_doc` and `sources_cited` hold quoted wikilinks (like `entities:`),
so no `sources` list and no footnotes here.

**Budget** ≤25 lines. **No diagrams, no code, no per-claim citations** — if you are
writing those, they belong in the note.

**Worked example**

```markdown
---
type: question
title: Why do agent loops need a step budget?
description: Checking whether the notes explain runaway tool retries.
created: 2026-10-28T11:00:00Z
generated: { by: llm-wiki-keeper/orchestrator, at: 2026-10-28T11:00:00Z }
asked_on: 2026-10-28
answer_doc: "[[notes/agent-loop-stop-conditions]]"
sources_cited:
  - "[[concepts/agent-loop]]"
  - "[[sources/agent-loops]]"
---

# Why do agent loops need a step budget?

> Asked on 2026-10-28 · answered from 2 wiki pages

## Answer

Full answer: [Agent loop stop conditions](../notes/agent-loop-stop-conditions.md)

- Without a budget, failing tools are retried forever.
- The harness, not the model, owns the budget.

## Why this matters

It decides what the next video demo must show.
```

<!-- changed in keeper: OKF 0.2 -->
## `note` — `wiki/notes/<slug>.md`

Where the knowledge actually lands. Written by the orchestrator.

```markdown
---
type: note
title: <topic, not the question>
description: <ONE sentence>
created: <ISO-8601 UTC — preserved across enrichment>
generated: { by: llm-wiki-keeper/orchestrator, at: <ISO-8601 UTC> }
spawned_by_question:
  - "[[questions/<date>-<slug>]]"
sources:
  - id: <page-slug>
    resource: ../concepts/<page-slug>.md     # or ../sources/..., ../entities/...
    title: <page title>
related:
  - "[[concepts/<slug>]]"
---

# <title>

<the answer, with every claim citing a wiki page through a footnote. Mermaid is
welcome when the answer is structural.>

> Synthesis: <one line — what would extend or revise this note>

[^<page-slug>]: [<page title>](../concepts/<page-slug>.md)
```

**Budget** 300–800 words. **Idempotent**: a same-topic question enriches this page
in place, appends to `spawned_by_question`, adds new `sources` entries, bumps
`generated.at`, and preserves `created`.
Notes cite **wiki pages**, never `raw/` — they sit on top of the wiki, not beside it.

**Worked example**

```markdown
---
type: note
title: Agent loop stop conditions
description: Why an agent loop needs a step budget and what the notes say about retries.
created: 2026-10-28T11:00:00Z
generated: { by: llm-wiki-keeper/orchestrator, at: 2026-10-28T11:00:00Z }
spawned_by_question:
  - "[[questions/2026-10-28-why-agent-loops-need-a-step-budget]]"
sources:
  - id: agent-loop
    resource: ../concepts/agent-loop.md
    title: Agent loop
  - id: agent-loops
    resource: ../sources/agent-loops.md
    title: Agent loops in practice
related:
  - "[[concepts/mcp]]"
---

# Agent loop stop conditions

A loop without a step budget retries a failing tool indefinitely.[^agent-loops]
The budget belongs to the harness, which is where the loop runs.[^agent-loop]

> Synthesis: A budget plus a visible tool error is the minimum demo of a safe loop.

[^agent-loop]: [Agent loop](../concepts/agent-loop.md)
[^agent-loops]: [Agent loops in practice](../sources/agent-loops.md)
```

<!-- changed in keeper: OKF 0.2 -->
## `repo_note` — `wiki/repos/github-<owner>-<repo>/<question-slug>.md`

A question answered against the code. **Source-like**: it carries `entities:` /
`concepts:` and counts toward the ≥2 threshold, so it runs the ingest tail.
Written by `repo_writer` in `question` mode.

```markdown
---
type: repo_note
title: <what the note answers>
description: <ONE sentence>
created: <ISO-8601 UTC>
generated: { by: llm-wiki-keeper/repo_writer, at: <ISO-8601 UTC> }
original_path: github://<owner>/<repo>#<question-slug>
repo: "[[repos/github-<owner>-<repo>/ARCHITECTURE]]"
commit_sha: <full sha>
question: <the user's question, verbatim>
spawned_by_question: "[[questions/<date>-<slug>]]"
sources:
  - id: repo
    resource: https://github.com/<owner>/<repo>/tree/<commit_sha>
    title: <owner>/<repo>
entities: []
concepts: []
---

# <title>

> Answers [<question>](../../questions/<date>-<slug>.md) against `<repo>` @ `<sha[:7]>`

## Answer

<prose; ≤2 mermaid diagrams when the answer is structural>

## Evidence

- `path/to/file.py:120-138` — <what it shows>.[^repo]

## Connections

- [<Name>](../../entities/<slug>.md)
- [<Name>](../../concepts/<slug>.md)

> Synthesis: <one line>

[^repo]: [path/to/file.py:120-138](https://github.com/<owner>/<repo>/blob/<sha>/path/to/file.py#L120-L138)
```

Each distinct evidence line may use its own permalink: define one footnote per
file, labelled `repo` for the first and `repo-2`, `repo-3` for the rest, each with
a matching extra `sources` entry (`{ id: repo-2, resource: <permalink>, title: <file> }`).

**Budget** ≤200 lines. Cite only code you actually opened.

**Worked example**

```markdown
---
type: repo_note
title: How tinyagent stops its loop
description: tinyagent stops on a fixed step budget checked once per model call.
created: 2026-10-28T11:30:00Z
generated: { by: llm-wiki-keeper/repo_writer, at: 2026-10-28T11:30:00Z }
original_path: github://acme/tinyagent#how-it-stops
repo: "[[repos/github-acme-tinyagent/ARCHITECTURE]]"
commit_sha: 9f2c1ab7d3e4f5061728394a5b6c7d8e9f001122
question: How does tinyagent decide to stop the loop?
spawned_by_question: "[[questions/2026-10-28-how-does-tinyagent-stop]]"
sources:
  - id: repo
    resource: https://github.com/acme/tinyagent/blob/9f2c1ab7d3e4f5061728394a5b6c7d8e9f001122/src/agent.py#L10-L28
    title: src/agent.py
entities: []
concepts:
  - "[[concepts/agent-loop]]"
---

# How tinyagent stops its loop

> Answers [How does tinyagent decide to stop the loop?](../../questions/2026-10-28-how-does-tinyagent-stop.md) against `tinyagent` @ `9f2c1ab`

## Answer

`run()` counts model calls and exits when the count reaches `MAX_STEPS`.

## Evidence

- `src/agent.py:10-28` — the loop and the budget check.[^repo]

## Connections

- [Agent loop](../../concepts/agent-loop.md)

> Synthesis: A hard budget, no semantic stop condition.

[^repo]: [src/agent.py:10-28](https://github.com/acme/tinyagent/blob/9f2c1ab7d3e4f5061728394a5b6c7d8e9f001122/src/agent.py#L10-L28)
```

<!-- changed in keeper: OKF 0.2 -->
## `open_question` — `wiki/open-questions.md`

Written by the orchestrator.

```markdown
---
type: open_question
title: Open questions
description: Questions the wiki cannot answer yet, and gaps worth ingesting for.
created: <ISO-8601 UTC>
generated: { by: llm-wiki-keeper/orchestrator, at: <ISO-8601 UTC> }
---

# Open questions

## <YYYY-MM-DD>

- <the question> — from [<question title>](questions/<date>-<slug>.md)
- <the question> — flagged by the user
```

Append-only, newest section last, `generated.at` bumped on each append. Nothing is
resolved automatically: the next ingest *reports* which ones its new sources appear
to address, and a human decides. (The page sits in `wiki/`, so links into
`questions/` have no `../`.)

**Worked example**

```markdown
---
type: open_question
title: Open questions
description: Questions the wiki cannot answer yet, and gaps worth ingesting for.
created: 2026-10-28T11:00:00Z
generated: { by: llm-wiki-keeper/orchestrator, at: 2026-10-28T11:05:00Z }
---

# Open questions

## 2026-10-28

- Does the step budget differ between harnesses? — from [Why do agent loops need a step budget?](questions/2026-10-28-why-agent-loops-need-a-step-budget.md)
- Is there a note on context-window limits? — flagged by the user
```

<!-- added in lint -->
## `lint_report` — `wiki/lint/YYYY-MM-DD.md`

Written by the orchestrator (`LINT.md` L.5). A second run on the same day overwrites it.
It **reports and cites nothing**: no `sources` list, no footnotes, no `> Synthesis:`
lines. Every finding is written as `path:line`, the finding id, and a **paraphrased**
one-line message, never the script's text pasted in. Any literal markdown-looking text
from a message or hint (footnote syntax, links) goes inside backticks, never bare, or
the report would parse as having broken footnotes and links itself. Links from the
report to wiki pages are relative to `wiki/lint/` (`../sources/x.md`), computed by the
orchestrator.

```markdown
---
type: lint_report
title: Lint report <YYYY-MM-DD>
description: <ONE sentence: counts by severity>
created: <ISO-8601 UTC>
generated: { by: llm-wiki-keeper/orchestrator, at: <ISO-8601 UTC> }
---

# Lint report <YYYY-MM-DD>

| Severity | Count |
|---|---|
| error | <n> |
| warn | <n> |
| info | <n> |

## Errors
- **<id> <name>**: [<path>:<line>](../<path>.md). <paraphrased message> Fix: <paraphrased fix_hint>

## Warnings
- ...

## Info
- ...

## Trust tiers
<One paragraph from L12: counts per tier and per status.>

## Suggested next ingests
- <slug>: <why a second source would help (C04)>
- Open questions: <n> added to open-questions.md, <m> already there.
```

Omit a severity section when it is empty. **Budget:** no cap, but one line per finding.

**Worked example**

```markdown
---
type: lint_report
title: Lint report 2026-10-30
description: 1 error, 2 warnings and 2 info findings across 7 pages.
created: 2026-10-30T14:20:00Z
generated: { by: llm-wiki-keeper/orchestrator, at: 2026-10-30T14:20:00Z }
---

# Lint report 2026-10-30

| Severity | Count |
|---|---|
| error | 1 |
| warn | 2 |
| info | 2 |

## Errors

- **L02 empty-stub**: [entities/claude-code](../entities/claude-code.md) has no content. Fix: delete it, or ingest a second source that mentions Claude Code.

## Warnings

- **C05 interpretation-in-prose**: [agent-loop](../concepts/agent-loop.md) line 14. "Claude Code is a better fit than Cursor for long refactors." is a comparison the source does not state. Fix: move it to a `> Synthesis:` line.
- **L07 orphan**: [notes/old-draft](../notes/old-draft.md) has no inbound link. Fix: link it from a question page or leave it.

## Info

- **C03 missing-cross-reference**: [agent-loops](../sources/agent-loops.md) line 9 names MCP without linking [mcp](../concepts/mcp.md). Fix: add the link on the next ingest.
- **L14 config-missing**: no `config.yml`; defaults were used.

## Trust tiers

All 7 pages are unverified (machine-written, never human-reviewed); none is machine-confirmed or human-reviewed. Status: 7 stable, 0 draft, 0 deprecated.

## Suggested next ingests

- tool-use: waiting at 1 mention, one more source would earn it a page.
- step-budget: the open question "Does the step budget differ between harnesses?" may now be answered by [agent-loop](../concepts/agent-loop.md).
```
