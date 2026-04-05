---
name: wiki-ingest
description: "Process new raw sources into the wiki. Creates and updates project, topic, person, and weekly pages. TRIGGERS: 'ingest the wiki', 'update the wiki', 'wiki ingest', 'process new files'."
---

# Wiki Ingest

You maintain a personal wiki. The wiki root is the current project directory.

Before starting, read:
- `CLAUDE.md` — overview, structure, script locations
- `wiki-schema.md` — page templates, operations, conventions

Your job: read new raw files and integrate their knowledge into the wiki.

## Step 1: Identify New Files

Run this to find new files since last compile:

```bash
LAST=$(cat wiki/.last-compile 2>/dev/null || echo "1970-01-01")
find raw -name "*.md" -newer wiki/.last-compile 2>/dev/null | sort
# If .last-compile doesn't exist, all files are new (bootstrap mode)
```

## Step 2: Filter

Skip files whose filename contains (case-insensitive):
- "interview"
- Any patterns you've configured (e.g., conference room names)

Use a single bash command to list and filter:

```bash
find raw -name "*.md" -newer wiki/.last-compile | \
  grep -iv "interview" | sort
```

## Step 3: Read Files

**Read files in parallel batches of 4-6 using the Read tool.** This is the single biggest speed lever — do NOT read files one at a time.

**Claude Code sessions:** Always read in full (at least 200 lines). Summaries are generated from the first few user messages and often say "setup/navigation session" when the real substance comes later. Sessions frequently start with navigation or git-sync but then continue into substantive work. Do not skip or skim Claude Code files based on their summary alone.

**Granola transcripts under 10K tokens:** Read in full.

**Large Granola transcripts (300+ lines, over 10K tokens):** The embedded `**Summary:**` section near the top is comprehensive (often 500+ words with specific decisions, names, and data). Read the summary section plus the first ~200 lines of transcript for context.

**Read the existing wiki pages first** (index.md, then relevant project/topic/people pages) so you know what to update vs create.

## Step 4: Extract and Accumulate

As you read each file, accumulate:
- Which **projects** were discussed (match to existing pages or flag new)
- Which **people** were meaningfully involved (not just silent attendees)
- Which **topics/concepts** came up
- What **decisions** were made (with context and rationale)
- **Week assignment** (ISO week from date in filename)

Don't write wiki pages one-at-a-time while reading. Accumulate across all files first, then write in bulk. This avoids reading and re-reading pages for every file.

## Step 5: Write Wiki Pages (in parallel)

After processing all files, write/update wiki pages in parallel batches:

**Projects** — Create new pages or update existing ones (append to Timeline, update Status, add Key Decisions). Use the template from wiki-schema.md.

**Topics** — Update Key Points and Current Thinking. Create new pages when there's enough substance. Topics should be descriptive and general.

**People** — Add Recent Interactions entries. Create new pages for recurring contacts. Keep concise: 2-4 sentences per interaction.

**Weekly digest** — Create or update with narrative summary, decisions, active projects, source list.

**Write multiple pages in a single tool-call batch** to maximize parallelism.

## Step 6: Update Index, Log, and Timestamp

In a final batch:
1. **Regenerate `wiki/index.md`** — full catalog of all pages with links, status, last_updated
2. **Append to `wiki/log.md`**:
   ```
   ## [YYYY-MM-DD] ingest | {count} files
   Sources: {list}
   Pages created: {list}
   Pages updated: {list}
   ```
3. **Write current ISO timestamp** to `wiki/.last-compile`

## Incremental Mode (normal weekly runs)

This is the typical case — 10-30 new files from the last 1-2 weeks.

1. Identify new files (Step 1-2): ~5 seconds
2. Read all new files in parallel batches of 4-6: ~2-3 rounds of reads
3. Read existing wiki pages that need updating: 1 round
4. Write all updated pages in parallel: 1-2 rounds of writes
5. Update index/log/timestamp: 1 round

**Target: complete an incremental ingest in under 5 minutes.**

## Bootstrap Mode (first run)

When `.last-compile` doesn't exist, all files are new. Process one ISO week at a time, oldest first:

1. List all files, filter, sort, group by ISO week
2. For each week: read all files (parallel batches of 4-6), then write all wiki pages
3. After all weeks: final index regeneration and log entry
4. Set `.last-compile`

## Important Notes

- **Parallel reads are critical.** Always batch 4-6 Read calls per round. Never read one file at a time.
- **One source, many pages.** A single meeting might update 3 projects, 2 people, and 1 topic.
- **Narrative over bullets.** Timeline and What Happened sections should read as prose.
- **Propose, don't proliferate.** When uncertain, note in the log. Create the page once there's material from multiple sources.
- **Cross-reference liberally.** Use relative markdown links between pages.
- **Keep people pages lightweight.** For jogging memory before a meeting, not documenting relationships.
- **Report at the end.** Files processed, pages created/updated, any proposed new topics.
