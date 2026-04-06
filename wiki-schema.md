# Wiki Schema — Page Types, Operations, and Conventions

## Page Types

### Project (`wiki/projects/{slug}.md`)

One page per active project or initiative. Tracks status, decisions, and evolution over time.

```markdown
---
type: project
status: active | paused | completed
last_updated: YYYY-MM-DD
---
# {Project Name}

{What this project is, its goal, current phase. 2-3 sentences.}

## Status

{Current state. What's happening right now. What's next.}

## Key Decisions

### YYYY-MM-DD: {Decision title}
{What was decided and why. Include context and alternatives considered.}

## Open Questions

- {Question that needs resolution}

## Timeline

### Week of YYYY-MM-DD
{What happened this week. Written as narrative, not bullets.
Reference which meeting or session the info came from.}
```

### Topic (`wiki/topics/{slug}.md`)

Concepts, frameworks, and recurring themes. Topics should be descriptive and general — knowledge categories, not narrative angles.

```markdown
---
type: topic
last_updated: YYYY-MM-DD
---
# {Topic Name}

{What this topic is and why it matters. 2-3 sentences.}

## Current Thinking

{Your evolving position or understanding. Updated as new information arrives.}

## Key Points

{Organized by subtopic. Specific observations, patterns, and data points.}

## Related

- Projects: {links to related project pages}
- People: {links to related people pages}
```

### Person (`wiki/people/{slug}.md`)

Lightweight pages for key individuals. Just enough context to jog memory before a meeting.

```markdown
---
type: person
role: {their role}
org: {their organization}
last_updated: YYYY-MM-DD
---
# {Name}

{Role, relationship to you, key context. 1-2 sentences.}

## Recent Interactions

### YYYY-MM-DD: {Meeting or session title}
{Key points from this interaction. 2-4 sentences.}
```

### Weekly Digest (`wiki/weekly/YYYY-wWW.md`)

What happened each week. The go-to page for "what did I do last week?"

```markdown
---
type: weekly
week: YYYY-wWW
date_range: Mon DD - Sun DD
---
# Week of YYYY-MM-DD

## What Happened

{3-5 paragraph narrative. What was the main focus?
What moved forward? What was surprising?}

## Key Decisions

- {Decision 1}
- {Decision 2}

## Projects Active

- [{Project}](../projects/slug.md): {one-line update}

## Sources

- {List of raw files processed for this week}
```

## Operations

### Ingest

Process new raw sources into the wiki. Run via `/wiki-ingest` or `/content-sync`.

1. **Identify new files.** Compare modification times in `raw/granola/`, `raw/claude-code/`, and `raw/drops/` against `wiki/.last-compile`. Any file modified after that timestamp is new. If `.last-compile` doesn't exist, all files are new (bootstrap mode).

2. **Filter.** Skip files matching patterns you configure (e.g., interviews, conference room names). Edit the filter list in the wiki-ingest skill.

3. **Read each file in full.** Use the LLM's full context window. Don't sample or truncate. For each file, extract:
   - Summary (2-3 sentences)
   - Projects discussed (match to existing project pages or propose new ones)
   - People involved (match to existing people pages or create new ones for key individuals)
   - Topics covered (match to existing topic pages or propose new ones)
   - Decisions made
   - Week assignment (ISO week based on date in filename)

4. **Update project pages.** For existing projects, append to the Timeline section and update Status. For new projects, create a new page. Update Key Decisions if any decisions were made.

5. **Update topic pages.** For existing topics, update Key Points and Current Thinking if the new material adds or changes anything. For new topics, create a new page.

6. **Update people pages.** Add a Recent Interactions entry for people who meaningfully participated — not just 1:1s, but also recurring leadership meetings (exec huddles, staff meetings, team weeklies) and any meeting where the person spoke substantively or a decision was made about them. People pages should accumulate interactions over time. Create new person pages for people who come up frequently and don't have one yet.

   **Always update `last_updated` in frontmatter** when editing any wiki page — not just when creating it.

7. **Update weekly digest.** Create or update the relevant week's page. Add to the narrative, decisions, and sources list.

8. **Update index.** Regenerate `wiki/index.md` with the current catalog of all pages.

9. **Append to log.** Add an entry to `wiki/log.md`:
   ```
   ## [YYYY-MM-DD] ingest | {count} files
   Sources: {list of filenames}
   Pages created: {list}
   Pages updated: {list}
   ```

10. **Update timestamp.** Write the current ISO timestamp to `wiki/.last-compile`.

### Query

Ask questions against the wiki. The LLM reads `wiki/index.md` first to find relevant pages, then reads those pages to synthesize an answer.

When a query produces a valuable result (a comparison, analysis, or synthesis), consider filing it back into the wiki as a new or updated topic page. Explorations should compound in the knowledge base.

### Lint

Periodically health-check the wiki. Look for:
- Contradictions between pages
- Stale claims that newer sources have superseded
- Orphan pages with no inbound links
- Important concepts mentioned but lacking their own page
- Missing cross-references between related pages
- Projects that should be marked paused or completed
- People pages that are too thin to be useful (merge or remove)

## Conventions

- **Filenames:** lowercase, hyphen-separated slugs. `product-discovery.md`, not `Product Discovery.md`.
- **Cross-references:** Use relative markdown links: `[Product Discovery](../projects/product-discovery.md)`. Prefer linking to page names rather than inline descriptions.
- **Frontmatter:** Every wiki page has YAML frontmatter with at least `type` and `last_updated`.
- **Narrative over bullets:** Prefer prose in Timeline and What Happened sections. Bullets are fine for decisions, open questions, and source lists.
- **One source, many pages:** A single meeting might update 3 projects, 2 people, and 1 topic. That's normal.
- **Propose, don't proliferate:** When uncertain whether something deserves its own page, note it in the log as a proposed page. Create it once there's enough material from multiple sources.
