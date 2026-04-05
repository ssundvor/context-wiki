Pull fresh Granola transcripts and Claude Code sessions, then ingest into the wiki.

## Steps

1. Run **both exports in parallel** (last 14 days):
```bash
python3 scripts/granola-api-export.py --days 14 &
python3 scripts/claude-code-export.py --days 14 &
wait
```

2. Run `/wiki-ingest` to process new raw files into the wiki.

3. Report: how many new raw files exported, how many wiki pages created/updated.

## Bootstrap (first run)

If `wiki/.last-compile` doesn't exist, all raw files are new:

1. Run exports with `--all` instead of `--days 14`
2. `/wiki-ingest` will detect bootstrap mode and process files week by week
