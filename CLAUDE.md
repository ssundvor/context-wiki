# Wiki

This is your personal wiki. The LLM maintains it; you curate sources and ask questions.

Read `wiki-schema.md` before any wiki operation (ingest, query, lint, or creating/editing wiki pages).

## Three Layers

1. **Raw sources** (`raw/`) — Immutable. The LLM reads but never modifies.
2. **The wiki** (`wiki/`) — LLM-maintained markdown files.
3. **The schema** (`wiki-schema.md`) — Page templates, operations, and conventions.

## Wiki Structure

- `wiki/projects/` — One page per active project or initiative
- `wiki/topics/` — Concepts, frameworks, recurring themes
- `wiki/people/` — Key individuals, roles, interaction history
- `wiki/weekly/` — Weekly digests
- `wiki/index.md` — Master catalog of all pages
- `wiki/log.md` — Chronological activity record

## Scripts

Export scripts live in `scripts/`. Both require `scripts/.env` with `ANTHROPIC_API_KEY`.

- **Granola export:** `python3 scripts/granola-api-export.py --days 14`
- **Claude Code export:** `python3 scripts/claude-code-export.py --days 14`
- Use `--all` for full history, `--resummarize` to regenerate summaries on existing files.
