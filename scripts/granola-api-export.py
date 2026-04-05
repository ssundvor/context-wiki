#!/usr/bin/env python3
"""
Export Granola meeting transcripts via the Granola API.
Includes Granola's AI-generated notes as a summary at the top of each file.

Requires: Granola desktop app installed (reads auth token from local storage).

Usage:
    python3 granola-api-export.py                  # Export last 7 days
    python3 granola-api-export.py --days 60        # Export last 60 days
    python3 granola-api-export.py --all            # Export everything
    python3 granola-api-export.py --resummarize    # Add summaries to existing files
"""

import json
import os
import re
import gzip
import argparse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SUPABASE_FILE = os.path.expanduser(
    "~/Library/Application Support/Granola/supabase.json"
)
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "raw", "granola")
SUMMARY_MARKER = "**Summary:**"


def get_token():
    with open(SUPABASE_FILE) as f:
        data = json.load(f)
    workos = json.loads(data.get("workos_tokens", "{}"))
    return workos["access_token"]


def api_post(endpoint, body=None, token=None):
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(
        f"https://api.granola.ai/v1/{endpoint}",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip",
        },
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=30)
    raw = resp.read()
    try:
        raw = gzip.decompress(raw)
    except Exception:
        pass
    return json.loads(raw)


def slugify(text, max_len=60):
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    return text[:max_len]


def format_transcript(segments):
    if not segments:
        return ""
    lines = []
    current_source = None
    current_buffer = []

    for seg in segments:
        source = seg.get("source", "unknown")
        text = seg.get("text", "").strip()
        if not text:
            continue
        if source != current_source:
            if current_buffer:
                label = "You" if current_source == "microphone" else "Other"
                lines.append(f"**{label}:** {' '.join(current_buffer)}")
                lines.append("")
            current_source = source
            current_buffer = [text]
        else:
            current_buffer.append(text)

    if current_buffer:
        label = "You" if current_source == "microphone" else "Other"
        lines.append(f"**{label}:** {' '.join(current_buffer)}")

    return "\n".join(lines)


def get_anthropic_client():
    """Load API key from .env and return an Anthropic client."""
    import anthropic
    script_dir = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
    env_path = os.path.join(script_dir, ".env")
    api_key = None
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("ANTHROPIC_API_KEY="):
                    api_key = line.strip().split("=", 1)[1]
    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


def generate_summary_via_claude(segments, title):
    """Generate a 2-3 sentence summary by sending the full transcript to Haiku."""
    if not segments:
        return None

    # Build full transcript text from segments
    lines = []
    current_source = None
    current_buffer = []

    for seg in segments:
        source = seg.get("source", "unknown")
        text = seg.get("text", "").strip()
        if not text:
            continue
        if source != current_source:
            if current_buffer:
                label = "You" if current_source == "microphone" else "Other"
                lines.append(f"{label}: {' '.join(current_buffer)}")
            current_source = source
            current_buffer = [text]
        else:
            current_buffer.append(text)

    if current_buffer:
        label = "You" if current_source == "microphone" else "Other"
        lines.append(f"{label}: {' '.join(current_buffer)}")

    if not lines:
        return None

    full_transcript = "\n".join(lines)

    # Cap at ~150K chars to stay well within Haiku's context window
    if len(full_transcript) > 150000:
        full_transcript = full_transcript[:150000] + "\n[...transcript truncated...]"

    prompt = f"""Summarize this meeting transcript in 2-3 sentences. Focus on WHAT was discussed and any decisions made. Be specific about topics, names of projects, and key takeaways. If it's genuinely just small talk with no substance, say "Casual conversation, no substantive topics."

Meeting title: {title}

{full_transcript}

Summary (2-3 sentences, no preamble):"""

    try:
        client = get_anthropic_client()
        if not client:
            return None
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        return None


def extract_panel_text(node):
    """Recursively extract text from a Granola panel's structured content."""
    texts = []
    if isinstance(node, dict):
        if "text" in node:
            texts.append(node["text"])
        if "content" in node and isinstance(node["content"], list):
            for child in node["content"]:
                texts.extend(extract_panel_text(child))
    return texts


def fetch_granola_panel_summary(doc_id, token):
    """Fetch AI-generated panel summary from Granola's get-document-panels endpoint."""
    try:
        panels = api_post("get-document-panels", {"document_id": doc_id}, token=token)
        for panel in panels:
            content = panel.get("content")
            if content and isinstance(content, dict) and content.get("content"):
                text = " ".join(extract_panel_text(content))
                if len(text) > 50:
                    return text
    except Exception:
        pass
    return None


def build_summary(doc, segments, title, token):
    """Build a summary from Granola's AI panels, user notes, or LLM fallback."""
    # 1. Prefer Granola's AI-generated panel summary
    panel_text = fetch_granola_panel_summary(doc["id"], token)
    if panel_text:
        return f"[Granola AI] {panel_text}"

    # 2. Fallback: generate via Anthropic API
    llm_summary = generate_summary_via_claude(segments, title)
    if llm_summary:
        return f"[AI summary] {llm_summary}"

    return None


def file_has_summary(filepath):
    """Check if an exported file already has a summary."""
    try:
        with open(filepath) as f:
            content = f.read(1000)
            return SUMMARY_MARKER in content
    except Exception:
        return False


def add_summary_to_existing_file(filepath, summary):
    """Insert or replace the summary line in an existing file. Deduplicates."""
    with open(filepath) as f:
        content = f.read()

    lines = content.split("\n")

    # Strip ALL existing summary lines first
    lines = [l for l in lines if not l.startswith(SUMMARY_MARKER)]

    # Insert one summary after the first ---
    new_lines = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        if line.strip() == "---" and not inserted:
            new_lines.append("")
            new_lines.append(f"{SUMMARY_MARKER} {summary}")
            inserted = True

    with open(filepath, "w") as f:
        f.write("\n".join(new_lines))


def has_real_summary(filepath):
    """Check if file has a Granola AI panel or LLM-generated summary."""
    try:
        with open(filepath) as f:
            content = f.read(1500)
            if SUMMARY_MARKER not in content:
                return False
            if "[Granola AI]" in content or "[AI summary]" in content:
                return True
            return False  # Has a summary marker but it's old format (notes/excerpt)
    except Exception:
        return False


def resummarize_existing(token):
    """Add or replace summaries for existing exported files."""
    existing_files = sorted(Path(OUTPUT_DIR).glob("*.md"))
    needs_summary = [f for f in existing_files if not has_real_summary(f)]
    print(f"Found {len(needs_summary)} files needing summaries out of {len(existing_files)} total.")

    # Fetch all docs from API to get notes
    docs = api_post("get-documents", token=token)
    docs_by_title = {}
    for d in docs:
        slug = slugify(d.get("title") or "unknown")
        date_prefix = (d.get("created_at") or "")[:10]
        key = f"{date_prefix}_{slug}"
        docs_by_title[key] = d

    updated = 0
    for i, filepath in enumerate(needs_summary):
        stem = filepath.stem
        doc = docs_by_title.get(stem)

        # Try Granola AI panel first
        if doc:
            panel_text = fetch_granola_panel_summary(doc["id"], token)
            if panel_text:
                summary = f"[Granola AI] {panel_text}"
                add_summary_to_existing_file(str(filepath), summary)
                updated += 1
                print(f"  [{i+1}/{len(needs_summary)}] Summarized (Granola AI): {filepath.name}")
                continue


        # Fallback: generate via Anthropic API from the file content
        with open(filepath) as f:
            content = f.read()

        # Extract title from first line
        title = "Unknown"
        for line in content.split("\n"):
            if line.startswith("# "):
                title = line[2:].strip()
                break

        # Extract the full transcript text from the file
        transcript_lines = []
        in_transcript = False
        for line in content.split("\n"):
            if line.startswith("**You:**") or line.startswith("**Other:**"):
                in_transcript = True
            if in_transcript:
                transcript_lines.append(line)

        if not transcript_lines:
            continue

        full_transcript = "\n".join(transcript_lines)
        # Cap at ~150K chars for Haiku's context window
        if len(full_transcript) > 150000:
            full_transcript = full_transcript[:150000] + "\n[...truncated...]"

        conversation_text = full_transcript
        prompt = f"""Summarize this meeting transcript in 2-3 sentences. Focus on WHAT was discussed and any decisions made. Be specific about topics. If it's just small talk, say "Casual conversation, no substantive topics."

Meeting: {title}

{conversation_text}

Summary (2-3 sentences, no preamble):"""

        try:
            client = get_anthropic_client()
            if client:
                response = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=200,
                    messages=[{"role": "user", "content": prompt}],
                )
                ai_text = response.content[0].text.strip()
                if ai_text:
                    summary = f"[AI summary] {ai_text}"
                    add_summary_to_existing_file(str(filepath), summary)
                    updated += 1
                    print(f"  [{i+1}/{len(needs_summary)}] Summarized (AI): {filepath.name}")
                    continue
        except Exception:
            pass

        print(f"  [{i+1}/{len(needs_summary)}] Failed: {filepath.name}")

    print(f"\nDone. Updated {updated} files with summaries.")


def export_transcripts(days=7):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    token = get_token()

    docs = api_post("get-documents", token=token)
    print(f"Total documents from API: {len(docs)}")

    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        docs = [
            d for d in docs
            if d.get("created_at")
            and datetime.fromisoformat(d["created_at"].replace("Z", "+00:00")) >= cutoff
        ]
    print(f"Documents in range: {len(docs)}")

    exported = 0
    skipped = 0
    errors = 0

    for doc in docs:
        title = doc.get("title") or "Unknown Meeting"
        created = doc.get("created_at", "")
        doc_id = doc["id"]

        date_prefix = created[:10] if created else "unknown-date"
        slug = slugify(title)
        filename = f"{date_prefix}_{slug}.md"
        filepath = os.path.join(OUTPUT_DIR, filename)

        if os.path.exists(filepath):
            skipped += 1
            continue

        try:
            segments = api_post("get-document-transcript", {"document_id": doc_id}, token=token)
        except Exception as e:
            print(f"  Error fetching transcript for {title}: {e}")
            errors += 1
            continue

        if not segments or not isinstance(segments, list) or len(segments) == 0:
            skipped += 1
            continue

        first_ts = segments[0].get("start_timestamp", "")[:16]
        last_ts = segments[-1].get("end_timestamp", "")[:16]

        people = doc.get("people", {})
        attendees = []
        if isinstance(people, dict):
            for key in ["attendees", "participants"]:
                if key in people:
                    for a in people[key]:
                        name = a.get("name", "") if isinstance(a, dict) else str(a)
                        if name and "Video Conferencing" not in name and "Gem Scheduling" not in name:
                            attendees.append(name)

        transcript_text = format_transcript(segments)
        summary = build_summary(doc, segments, title, token)

        summary_block = ""
        if summary:
            summary_block = f"""
{SUMMARY_MARKER} {summary}

---
"""

        content = f"""# {title}

**Date:** {created[:16].replace('T', ' ')} UTC
**Duration:** {first_ts[11:16] if len(first_ts) > 11 else '?'} to {last_ts[11:16] if len(last_ts) > 11 else '?'} UTC
**Attendees:** {', '.join(attendees) if attendees else 'Not recorded'}
**Segments:** {len(segments)}

---
{summary_block}
{transcript_text}
"""

        with open(filepath, "w") as f:
            f.write(content)
        exported += 1
        print(f"  Exported: {filename}")

    print(f"\nDone. Exported {exported}, skipped {skipped}, errors {errors}.")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Granola transcripts via API")
    parser.add_argument("--days", type=int, default=7, help="Days to look back (default: 7)")
    parser.add_argument("--all", action="store_true", help="Export all transcripts")
    parser.add_argument("--resummarize", action="store_true",
                        help="Add summaries to existing exported files")
    args = parser.parse_args()

    if args.resummarize:
        token = get_token()
        resummarize_existing(token)
    else:
        days = None if args.all else args.days
        export_transcripts(days=days)
