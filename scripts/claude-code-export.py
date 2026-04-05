#!/usr/bin/env python3
"""
Export Claude Code conversation history to readable markdown with AI-generated summaries.
Reads JSONL session files from ~/.claude/projects/ and writes one file per session.
Generates a 2-3 sentence summary at the top of each file using the Anthropic API.

Usage:
    python3 claude-code-export.py                  # Export last 7 days
    python3 claude-code-export.py --days 30        # Export last 30 days
    python3 claude-code-export.py --all            # Export everything
    python3 claude-code-export.py --resummarize    # Re-generate summaries for existing files
"""

import json
import os
import re
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

CLAUDE_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "raw", "claude-code")
SUMMARY_MARKER = "**Summary:**"


def slugify(text, max_len=50):
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    return text[:max_len]


def project_name_from_path(encoded_path):
    """Convert encoded project dir name back to readable form."""
    parts = encoded_path.split("-")
    meaningful = []
    found_users = False
    for part in parts:
        if not part:
            continue
        if not found_users:
            if part == "Users":
                found_users = True
            continue
        # Skip the username and common path segments
        if part in ("Documents", "Desktop", "Projects", "repos", "src"):
            meaningful = []  # Reset — start after these common dirs
            continue
        meaningful.append(part)
    return " / ".join(meaningful) if meaningful else encoded_path


def extract_text_content(message):
    """Pull readable text from a message's content field."""
    if not message:
        return ""
    content = message.get("content", [])
    if isinstance(content, str):
        return content
    texts = []
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text":
                texts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool = block.get("name", "unknown_tool")
                texts.append(f"[Used tool: {tool}]")
    return "\n".join(texts)


def parse_session(filepath):
    """Parse a JSONL session file into structured conversation data."""
    messages = []
    session_id = None
    cwd = None

    with open(filepath) as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type", "")
            if not session_id:
                session_id = entry.get("sessionId")
            if not cwd:
                cwd = entry.get("cwd")

            if entry_type in ("user", "assistant"):
                msg = entry.get("message", {})
                role = msg.get("role", entry_type)
                text = extract_text_content(msg)
                if text.strip():
                    messages.append({
                        "role": role,
                        "text": text[:2000],
                    })

    return {
        "session_id": session_id,
        "cwd": cwd,
        "messages": messages,
    }


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


def generate_summary(messages, project_name):
    """Generate a 2-3 sentence summary of the session using the Anthropic API."""
    condensed = []
    user_count = 0
    for msg in messages:
        if msg["role"] == "user":
            text = msg["text"].strip()
            if any(skip in text.lower() for skip in [
                "navigate to", "navigate here", "command-name",
                "command-message", "nimbalyst_system", "open_file_instructions",
                "base directory for this skill", "<local-command"
            ]):
                continue
            condensed.append(f"User: {text[:200]}")
            user_count += 1
            if user_count >= 8:
                break
        elif msg["role"] == "assistant" and len(condensed) > 0:
            text = msg["text"].strip()
            if text.startswith("[Used tool:"):
                continue
            condensed.append(f"Assistant: {text[:300]}")

    if not condensed or user_count < 1:
        return None

    conversation_text = "\n".join(condensed)

    prompt = f"""Summarize this Claude Code session in 2-3 sentences. Focus on WHAT was accomplished or discussed, not how. Be specific about topics, decisions, and outputs. If it's just navigation or setup, say "Setup/navigation session."

Project: {project_name}

{conversation_text}

Summary (2-3 sentences, no preamble):"""

    try:
        client = get_anthropic_client()
        if not client:
            return None
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        return None


def file_has_summary(filepath):
    """Check if an exported file already has a real summary (not a placeholder)."""
    try:
        with open(filepath) as f:
            content = f.read(500)
            if SUMMARY_MARKER not in content:
                return False
            if "Summary not available." in content:
                return False
            return True
    except Exception:
        return False


def add_summary_to_file(filepath, summary):
    """Insert or replace the summary line in an existing exported file. Deduplicates."""
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


def export_sessions(days=7, resummarize=False):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if resummarize:
        # Just regenerate summaries for existing files that don't have them
        existing_files = sorted(Path(OUTPUT_DIR).glob("*.md"))
        needs_summary = [f for f in existing_files if not file_has_summary(f)]
        print(f"Found {len(needs_summary)} files needing summaries out of {len(existing_files)} total.")

        for i, filepath in enumerate(needs_summary):
            session_data = None
            # Re-parse from the exported markdown to get messages
            messages = []
            with open(filepath) as f:
                project_name = "Unknown"
                for line in f:
                    if line.startswith("**Project:**"):
                        project_name = line.replace("**Project:**", "").strip()
                    if line.startswith("**User:**"):
                        messages.append({"role": "user", "text": line.replace("**User:**", "").strip()})
                    elif line.startswith("**Assistant:**"):
                        messages.append({"role": "assistant", "text": line.replace("**Assistant:**", "").strip()})

            if len(messages) < 2:
                continue

            summary = generate_summary(messages, project_name)
            if summary:
                add_summary_to_file(str(filepath), summary)
                print(f"  [{i+1}/{len(needs_summary)}] Summarized: {filepath.name}")
            else:
                # Mark as setup/nav so we don't retry
                add_summary_to_file(str(filepath), "Setup/navigation session.")
                print(f"  [{i+1}/{len(needs_summary)}] Skipped (no substance): {filepath.name}")

        print(f"\nDone. Summarized {len(needs_summary)} files.")
        return

    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_ts = cutoff.timestamp()
    else:
        cutoff_ts = None

    exported = 0
    skipped = 0
    summarized = 0

    for project_dir in sorted(Path(CLAUDE_PROJECTS_DIR).iterdir()):
        if not project_dir.is_dir():
            continue

        project_name = project_name_from_path(project_dir.name)

        for session_file in project_dir.glob("*.jsonl"):
            mtime = session_file.stat().st_mtime
            if cutoff_ts and mtime < cutoff_ts:
                skipped += 1
                continue

            if "subagent" in str(session_file):
                skipped += 1
                continue

            session = parse_session(session_file)
            messages = session["messages"]

            if len(messages) < 2:
                skipped += 1
                continue

            date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
            first_msg = ""
            for m in messages:
                if m["role"] == "user":
                    first_msg = m["text"][:80]
                    break
            slug = slugify(first_msg) if first_msg else session_file.stem[:20]
            filename = f"{date_str}_{slug}.md"
            filepath = os.path.join(OUTPUT_DIR, filename)

            if os.path.exists(filepath):
                skipped += 1
                continue

            # Generate summary
            summary = generate_summary(messages, project_name)
            summary_text = summary or "Summary not available."

            # Build markdown
            lines = [
                f"# Claude Code Session: {project_name}",
                f"",
                f"**Date:** {date_str}",
                f"**Project:** {project_name}",
                f"**Working Directory:** {session['cwd'] or 'Unknown'}",
                f"**Messages:** {len(messages)}",
                f"",
                f"---",
                f"",
                f"{SUMMARY_MARKER} {summary_text}",
                f"",
                f"---",
                f"",
            ]

            for msg in messages:
                role_label = "User" if msg["role"] == "user" else "Assistant"
                text = msg["text"].strip()
                if msg["role"] == "assistant" and len(text) > 1000:
                    text = text[:1000] + "\n\n[...truncated...]"
                lines.append(f"**{role_label}:** {text}")
                lines.append("")

            with open(filepath, "w") as f:
                f.write("\n".join(lines))
            exported += 1
            if summary:
                summarized += 1
            print(f"  Exported: {filename}")

    print(f"\nDone. Exported {exported} sessions ({summarized} with summaries), skipped {skipped}.")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Claude Code sessions")
    parser.add_argument("--days", type=int, default=7, help="Days to look back (default: 7)")
    parser.add_argument("--all", action="store_true", help="Export all sessions")
    parser.add_argument("--resummarize", action="store_true",
                        help="Re-generate summaries for existing exported files that lack them")
    args = parser.parse_args()

    if args.resummarize:
        export_sessions(resummarize=True)
    else:
        days = None if args.all else args.days
        export_sessions(days=days)
