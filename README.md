# Context Wiki

A system for building a personal knowledge base maintained by an LLM. You curate the sources; the LLM writes, updates, and cross-references the wiki.

This repo is a working implementation you can clone and start using.

## How it works

1. **Export** your meeting transcripts (Granola) and coding sessions (Claude Code) to markdown
2. **Ingest** the raw files into a structured wiki — the LLM reads each source and updates project, topic, person, and weekly pages
3. **Query** the wiki by asking your LLM questions — it reads the index, finds relevant pages, and synthesizes answers

The wiki compounds over time. Each source gets integrated once, cross-referenced, and kept current. You never write the wiki yourself.

## Setup

### 1. Clone and configure

```bash
git clone <this-repo> ~/llm-wiki
cd ~/llm-wiki

# Add your Anthropic API key (used by export scripts for AI summaries)
cp scripts/.env.example scripts/.env
# Edit scripts/.env with your key
```

### 2. Install the Claude Code skill and command

The wiki-ingest skill and content-sync command tell Claude Code how to operate on your wiki.

```bash
# Skill (user-level — available in all projects)
mkdir -p ~/.claude/skills/wiki-ingest
cp skills/wiki-ingest/SKILL.md ~/.claude/skills/wiki-ingest/SKILL.md

# Command (project-level — available when you're in this repo)
mkdir -p .claude/commands
cp commands/content-sync.md .claude/commands/content-sync.md
```

### 3. Export your sources

```bash
# Granola meeting transcripts (requires Granola desktop app installed)
pip install anthropic
python3 scripts/granola-api-export.py --days 14

# Claude Code sessions
python3 scripts/claude-code-export.py --days 14

# Use --all for full history, --resummarize to regenerate summaries
```

### 4. Ingest into the wiki

Open Claude Code in this directory and run:

```
/content-sync          # Export + ingest in one step
```

Or separately:

```
ingest the wiki        # Just the wiki-ingest step
```

### 5. Query

Ask questions in Claude Code while in this directory:

```
What decisions did we make about X last week?
Summarize the project status for Y.
What topics came up in meetings with Z?
```

The LLM reads `wiki/index.md` to find relevant pages, then reads those pages to answer.

## Directory structure

```
llm-wiki/
├── CLAUDE.md                  # Schema pointer — loaded every conversation
├── wiki-schema.md             # Full page templates, operations, conventions
├── commands/
│   └── content-sync.md        # /content-sync slash command
├── skills/
│   └── wiki-ingest/
│       └── SKILL.md           # Wiki ingest skill
├── scripts/
│   ├── claude-code-export.py  # Export Claude Code sessions to markdown
│   ├── granola-api-export.py  # Export Granola transcripts to markdown
│   └── .env.example           # API key template
├── raw/                       # Raw source files (gitignored)
│   ├── granola/               # Exported meeting transcripts
│   ├── claude-code/           # Exported coding sessions
│   └── drops/                 # Manually added files
└── wiki/                      # LLM-maintained wiki pages
    ├── index.md               # Master catalog
    ├── log.md                 # Chronological activity record
    ├── projects/              # One page per project/initiative
    ├── topics/                # Concepts, frameworks, themes
    ├── people/                # Key individuals
    └── weekly/                # Weekly digests
```

## Three layers

1. **Raw sources** (`raw/`) — Immutable. The LLM reads but never modifies. Gitignored because they contain private data.
2. **The wiki** (`wiki/`) — LLM-maintained markdown. The LLM owns this layer entirely.
3. **The schema** (`CLAUDE.md` + `wiki-schema.md`) — How the wiki is structured. You and the LLM co-evolve this.

## Customization

This is a starting point. You'll want to adapt:

- **Page types** in `wiki-schema.md` — add or remove types that fit your domain
- **Export scripts** — the Granola script reads from the Granola desktop app's local auth; the Claude Code script reads from `~/.claude/projects/`. Both output markdown to `raw/`.
- **Ingest filters** — the skill skips files matching certain patterns (interviews, conference rooms). Edit these in the SKILL.md.

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (CLI or desktop app)
- Python 3.8+
- `anthropic` Python package (`pip install anthropic`)
- An Anthropic API key (for AI-generated summaries in export scripts)
- [Granola](https://granola.ai) desktop app (for meeting transcript export only)
- Optional: [Obsidian](https://obsidian.md) for browsing the wiki with graph view

## License

MIT
