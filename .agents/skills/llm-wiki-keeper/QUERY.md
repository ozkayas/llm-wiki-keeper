# QUERY — the interaction path

Companion to `SKILL.md`. Loaded when Step 1 selected **query** mode. This is where
layer 03 differs from the earlier layers: querying the wiki can now *add* to it.

**The three write regimes** (`CONVENTIONS.md` §13) decide what you may touch:

| Regime | Pages | In query mode |
|---|---|---|
| ingest-owned | `raw/`, `sources/`, `entities/`, `concepts/`, `overview.md`, `repos/*/ARCHITECTURE.md` | **read-only** |
| interaction-owned | `questions/`, `notes/`, `open-questions.md` | you write these |
| repo notes | `repos/<repo>/<slug>.md` | written by an agent, then fed through the ingest tail |

Reading a source can never change what the wiki says that source means. If an
answer reveals that an ingest-owned page is wrong or thin, you do **not** edit it —
you record it in `open-questions.md` and the next ingest folds it in.

---

## Q.1 — Locate the wiki

Same as `SKILL.md` Step 0. No wiki → say so and stop; do not create one to answer
a question. Read `wiki-<slug>/config.yml` (a missing one means the defaults) and
write every page in its `language`; never add `tags` unless the user gave them.

## Q.2 — Load the map

Read `wiki/index.md`, then the one or two `wiki/<subdir>/index.md` files that look
relevant. In this layer the root index also lists `Questions`, `Notes` and
`Open questions` — check them: a question may already have been answered, and
enriching an existing note beats writing a second one.

## Q.3 — Walk the disclosure ladder

Index → page → `raw/` only if a page genuinely does not answer it. Prefer
entity/concept pages (already synthesized across sources) over source pages
(one source's view). Never bulk-read `raw/`, and never read a clone.

## Q.4 — Classify the question

| Class | Signal | Path |
|---|---|---|
| **repo-scoped** | names an ingested repo, or asks how some code works | Q.6 |
| **general** | everything else | Q.5 |

## Q.5 — General path

Answer from the wiki pages you read. Then decide what to keep:

1. **Always write the slim question page** — `wiki/questions/YYYY-MM-DD-<slug>.md`,
   per `PAGES.md § question`. Interaction-owned pages use v0.2 frontmatter
   (`type`, `title`, `description`, `created`, `generated`) with
   `generated.by: llm-wiki-keeper/orchestrator`; write instants with
   `date -u +%Y-%m-%dT%H:%M:%SZ`. It is a pointer, not an answer: the verbatim
   question, what it was answered from, and a relative markdown link to the
   knowledge if there is any. Cap it at ~25 lines.
2. **Write or enrich a note only when the answer earned it** — the answer cited
   **≥2 wiki pages**, or the user said "save this". Otherwise the question page
   alone is the record. Most questions are conversational and should not compound.
3. **Synthesis stays separate.** In notes, plain prose carries only statements a
   cited wiki page makes, with footnotes. Any interpretation, comparison, evaluation
   or inference goes on its own `> Synthesis:` line. A claim combining two pages
   needs both footnotes. See `.agents/skills/llm-wiki-keeper/PAGES.md`.
4. **Idempotency**: if a note on the same topic exists, *enrich it in place* —
   append to `spawned_by_question`, merge the new material into the existing
   structure, add `sources` entries (and footnotes) for newly cited pages, bump
   `generated.at`, keep `created`. A repeat question produces a second
   question page and **one** note, never a second note.

If the answer implies an ingest-owned page is wrong, stale or missing something:
say so in your reply, add it to `open-questions.md` (Q.7), and change nothing else.

## Q.6 — Repo path

1. **Read `wiki/repos/<repo>/ARCHITECTURE.md` first.** It exists so nobody has to
   read the clone. If it answers the question, you are on the general path (Q.5) —
   the note lands in `wiki/notes/` and links out to the repo page.
2. Only if the answer needs code the architecture page does not cover, check that
   the clone exists at the `clone_path` in `ARCHITECTURE.md`'s frontmatter. Clones
   are regenerable and never committed, so a copied wiki arrives without one. **If
   it is missing, clone it yourself — never ask the user to:**

   ```bash
   uv run --script .agents/skills/llm-wiki-keeper/scripts/clone_repo.py \
     --repo "<repo_url from ARCHITECTURE.md>" --wiki-dir wiki-<slug>
   ```

   If it already exists, use it as is — do not run the script (it would refresh
   the code under an ingest-owned page). Pass on the `commit_sha` from the receipt,
   or from the clone (`git -C <clone_path> rev-parse HEAD`). If it differs from the
   one in `ARCHITECTURE.md`, say so in the answer; you do not rewrite that page in
   query mode — suggest re-ingesting the repo.
   Then spawn `agents/repo_writer.md` with `mode: question`, passing `clone_path`,
   `commit_sha`, `branch`, the verbatim `question`, the `architecture_path`, the
   `question_page` path, and `language` and `tags` from `config.yml`. It writes
   `wiki/repos/<repo>/<question-slug>.md` (`PAGES.md § repo_note`) and returns a
   receipt. If its receipt says `"answered_from_architecture": true`, it wrote
   nothing — fall back to Q.5.
3. A repo note is a **source-like page**, so it must go through the **ingest tail**
   (`CONVENTIONS.md` §8), exactly as an ingested source would:

   ```bash
   uv run --script .agents/skills/llm-wiki-keeper/scripts/count_mentions.py --wiki-dir wiki-<slug>
   ```

   → spawn one `page_writer` per qualifying slug the new note touched →
   `overview_writer` → `build_index_md.py`.
4. Then write the slim question page with `answer_doc` pointing at the repo note
   (bundle-relative path, `/repos/<repo>/<question-slug>.md`).

This is the only way query mode reaches an ingest-owned page: **through the tail,
never by hand.**

## Q.7 — Open questions

Append to `wiki/open-questions.md` (creating it with `type: open_question`
frontmatter on first use; bump `generated.at` on every append) when
either is true:

- the user flags one ("log this as open", "we should look into that"), or
- **the wiki cannot answer** — say that plainly first. An honest "the wiki doesn't
  cover this" is the most useful answer a knowledge base can give, because it is
  the only one that tells you what to ingest next.

The file is append-only and dated. Nothing resolves it automatically; the next
ingest reports which open questions its new sources appear to address, and a human
decides.

## Q.8 — Log and present

Append one entry through the script; never edit `log.md` by hand. Op `Query`,
one `--text` per bullet (written in order, as one block at the top of the day):

```bash
uv run --script .agents/skills/llm-wiki-keeper/scripts/append_log.py --wiki-dir wiki-<slug> --op Query \
  --text "Question: \"<verbatim, ≤200 chars>\"." \
  --text "Pages used: <count> ([<title>](concepts/<slug>.md), ...)." \
  --text "Saved: [<title>](questions/<file>.md) + [<title>](notes/<file>.md), or question page only." \
  --text "Tail: <pages updated by the ingest tail, or omit>." \
  --text "Open question logged: <one line, or omit>."
```

Links in log text are relative to `wiki/log.md`. If the ingest tail ran (repo
path), its own `Ingest`/`Update` entries are logged as in `SKILL.md` 1.7. Several
`--text` give one bullet each, under the same op word.

Then answer the user:

```
## <question as a topic line>

<the answer, with standard relative links ([title](wiki/concepts/x.md)) to every page it rests on>

Pages used: [title](...), [title](...)
Saved: wiki/questions/<file> · wiki/notes/<file>        (or: question page only)
```

Never present a saved note as if the user asked for it — one line is enough.

---

## What this layer is actually teaching

The wiki now has two ways to grow. **Ingestion** adds what other people wrote.
**Interaction** adds what you asked and what the wiki worked out in reply — and
because a repo note re-enters through the same tail as a source, that second path
compounds exactly like the first. The question log is the cheap part: it makes
"what have I already asked?" answerable without re-answering anything.
