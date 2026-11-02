# llm-wiki-keeper

An agent skill that builds, queries and lints an LLM-maintained wiki (ingest, query, lint), in OKF v0.2.

This is a derivative of **03-llm-wiki-interactive** from the
[LLM Wiki Workshop](https://github.com/decodingai-magazine/llm-wiki-workshop)
by [Decoding AI Magazine](https://github.com/decodingai-magazine), released under the
MIT License. The idea behind it is Andrej Karpathy's
["LLM Wiki"](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) pattern.

- Upstream path: `03-llm-wiki-interactive/.agents/skills/03-llm-wiki-interactive`
- Upstream commit this fork started from: `623e658bfcce862bb0d68636ae817d373004967c` (2026-09-18)
- License: MIT, original copyright notice kept in `LICENSE`.
- `UPSTREAM-CHANGES-FROM-LAYER-02.md` is the upstream's own `CHANGES-FROM-PREVIOUS.md`, kept for reference.

## Changes from upstream

The first commit is the unmodified upstream skill, so `git diff` shows every change made here.

1. Wiki format moved from OKF v0.1 to OKF v0.2 (`generated`, `sources` + footnotes, `status`, newest-first log, standard markdown links, wikilinks in frontmatter path lists).
2. Added a `lint` mode (Karpathy's third operation): deterministic `scripts/lint.py` plus LLM `lint_reviewer` agents; see `LINT.md`.
3. First run asks for preferences once and stores them in `wiki-<slug>/config.yml`.

Every decision and its reason is recorded in `MIGRATION-OKF-0.2.md`.

## Layout

```
.agents/skills/llm-wiki-keeper/           # the skill (SKILL.md is the entry point)
.claude/skills -> ../.agents/skills       # symlink so Claude Code finds it
```
