#!/usr/bin/env python3
"""Sync project metadata from linked GitHub repositories via the GitHub API.

For each project directory whose README.md contains a `Repo` field pointing
to a GitHub repository (https://github.com/<owner>/<repo>), this script:

  - Fetches the latest commit date  → updates **Last Updated**
  - Fetches the repo description    → updates **Notes** (only when Notes is
                                       still the template placeholder)
  - Fetches open issues count       → appends to **Notes** as "(N open issues)"
  - Derives **Status** from activity:
      - last commit < STALE_DAYS ago and current status is "In Progress"
        → status is left as-is (do not auto-downgrade; just report)
      - If the repo is archived      → sets status to "Completed"

Requires the GITHUB_TOKEN environment variable (read:repo scope is enough for
public repos; repo scope for private repos).

Usage:
    python scripts/sync_from_upstream.py [--root .] [--dry-run]
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

EXCLUDED_DIRS = {
    ".git",
    ".github",
    "assets",
    "scripts",
    "templates",
    "__pycache__",
}

GITHUB_API = "https://api.github.com"
STALE_DAYS = 90  # days without a commit before flagging as stale


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _headers() -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN", "")
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub API error {exc.code} for {url}") from exc


def _parse_repo_url(url: str) -> tuple[str, str] | None:
    """Return (owner, repo) from a github.com URL, or None."""
    m = re.search(r"github\.com/([^/\s]+)/([^/\s#]+?)(?:\.git)?/?$", url)
    if not m:
        return None
    return m.group(1), m.group(2)


def _read_field(text: str, field: str) -> str:
    m = re.search(rf"^-\s+\*\*{re.escape(field)}\*\*:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _set_field(text: str, field: str, value: str) -> str:
    """Replace existing field value in-place."""
    return re.sub(
        rf"^(-\s+\*\*{re.escape(field)}\*\*:\s*)(.+)$",
        rf"\g<1>{value}",
        text,
        flags=re.MULTILINE,
    )


def _read_section(text: str, title: str) -> str:
    """Return the body of a ## Section (between header and next ## or EOF)."""
    m = re.search(
        rf"^##\s+{re.escape(title)}\s*\n(.*?)(?=^##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return m.group(1) if m else ""


def _set_section(text: str, title: str, content: str) -> str:
    """Replace the body of a ## Section, keeping the trailing blank line."""
    return re.sub(
        rf"(^##\s+{re.escape(title)}\s*\n).*?(?=^##\s|\Z)",
        lambda m: m.group(1) + content.rstrip("\n") + "\n\n",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )


def _parse_tracker_yml(text: str) -> dict:
    """Minimal stdlib-only parser for tracker.yml (scalar strings + string lists)."""
    result: dict = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        m = re.match(r"^(\w+):\s*(.*)", line)
        if m:
            key, val = m.group(1), m.group(2).strip().strip('"').strip("'")
            if val == "":  # list follows
                items: list[str] = []
                i += 1
                while i < len(lines):
                    lm = re.match(r"^\s+-\s+(.*)", lines[i])
                    if not lm:
                        break
                    items.append(lm.group(1).strip().strip('"').strip("'"))
                    i += 1
                result[key] = items
                continue
            else:
                result[key] = val
        i += 1
    return result


def _fetch_tracker_yml(owner: str, repo: str) -> dict:
    """Fetch and parse tracker.yml from the linked repo.

    Looks in .github/tracker.yml first (preferred location), then falls back
    to tracker.yml at the repo root for backward compatibility.
    Returns {} if the file does not exist or cannot be parsed.
    Priority fields: description (str), goals (list[str]), status (str).
    """
    for path in (".github/tracker.yml", "tracker.yml"):
        try:
            data = _get(f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}")
            if not isinstance(data, dict) or "content" not in data:
                continue
            raw = base64.b64decode(data["content"]).decode("utf-8")
            parsed = _parse_tracker_yml(raw)
            print(f"    tracker.yml found at {path} — fields: {list(parsed.keys())}")
            return parsed
        except RuntimeError:
            continue
    return {}


def _fetch_milestones(owner: str, repo: str) -> list[str]:
    """Return titles of open milestones, or [] on failure."""
    try:
        data = _get(
            f"{GITHUB_API}/repos/{owner}/{repo}/milestones?state=open&per_page=10"
        )
        return [m["title"] for m in data if isinstance(m, dict) and "title" in m]
    except RuntimeError:
        return []


def _fetch_commits(owner: str, repo: str, branch: str, n: int = 20) -> list[dict]:
    """Return the N most recent commits on branch, or [] on failure."""
    try:
        data = _get(
            f"{GITHUB_API}/repos/{owner}/{repo}/commits?sha={branch}&per_page={n}"
        )
        return data if isinstance(data, list) else []
    except RuntimeError:
        return []


def _fetch_merged_prs(owner: str, repo: str, n: int = 15) -> list[dict]:
    """Return recently merged PRs from the linked repo, or [] on failure."""
    try:
        data = _get(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls"
            f"?state=closed&per_page={n}&sort=updated&direction=desc"
        )
        if not isinstance(data, list):
            return []
        return [pr for pr in data if pr.get("merged_at")]
    except RuntimeError:
        return []


def _fetch_upstream_changelog(owner: str, repo: str) -> list[dict]:
    """Extract changelog / release-notes entries from the upstream README.

    Looks for a section whose heading matches common changelog patterns
    (Changelog, What's New, Updates, Release Notes, History) and returns
    up to 10 bullet entries, each as {"date": str, "text": str}.
    Returns [] when no such section is found.
    """
    try:
        data = _get(f"{GITHUB_API}/repos/{owner}/{repo}/readme")
        if not isinstance(data, dict) or "content" not in data:
            return []
        readme = base64.b64decode(data["content"]).decode("utf-8")
    except (RuntimeError, Exception):
        return []

    m = re.search(
        r"^#{1,3}\s+(?:changelog|change\s*log|what'?s?\s+new|updates?|release\s*notes?|history)\s*\n"
        r"(.*?)(?=^#{1,3}\s|\Z)",
        readme,
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    if not m:
        return []

    entries: list[dict] = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or not re.match(r"^[-*]|\d{4}", line):
            continue
        date_m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", line)
        date = date_m.group(1) if date_m else ""
        text = re.sub(r"^[-*\d.]+\s*", "", line).strip()
        # Strip inline markdown links to get clean text
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        entries.append({"date": date, "text": text})
        if len(entries) >= 10:
            break
    return entries


_GOAL_PLACEHOLDERS = frozenset(
    {
        "- Goal 1",
        "- Goal 2",
        "- (auto-populated from GitHub milestones on next sync)",
        "- _auto-filled by Claude on first sync_",
    }
)

_LOG_PLACEHOLDER = "_commits auto-populated on next sync_"


def _merge_progress_log(
    text: str,
    commits: list[dict],
    prs: list[dict] | None = None,
    changelog: list[dict] | None = None,
) -> str:
    """Prepend new events (commits, merged PRs, changelog entries) to Progress Log.

    Each source is deduplicated against what is already in the section:
    - commits  : matched by 7-char SHA
    - PRs      : matched by '#<number>'
    - changelog: matched by entry text (first 40 chars)
    Events are sorted newest-first before insertion.
    """
    section = _read_section(text, "Progress Log")

    # Build a unified events list: (date, sort_key, formatted_line)
    events: list[tuple[str, str, str]] = []

    for c in commits:
        sha7 = c["sha"][:7]
        if sha7 in section:
            continue
        date = (c.get("commit", {}).get("committer", {}).get("date", "") or "")[:10]
        msg = (c.get("commit", {}).get("message", "") or "").splitlines()[0].strip()
        url = c.get("html_url", "")
        events.append((date, sha7, f"- {date}: {msg} ([`{sha7}`]({url}))"))

    for pr in prs or []:
        number = pr.get("number", "")
        key = f"#{number}"
        if key in section:
            continue
        date = (pr.get("merged_at") or "")[:10]
        title = (pr.get("title") or "").strip()
        url = pr.get("html_url", "")
        events.append((date, key, f"- {date}: [PR] {title} ([{key}]({url}))"))

    for entry in changelog or []:
        snippet = entry["text"][:40]
        if snippet in section:
            continue
        date = entry.get("date", "")
        events.append((date, snippet, f"- {date}: [changelog] {entry['text']}"))

    if not events:
        return text

    # Sort newest-first (empty date sorts last)
    events.sort(key=lambda e: e[0] or "0000", reverse=True)

    new_lines = [line for _, _, line in events]
    # Remove placeholder line if present, then prepend new entries
    cleaned = re.sub(rf".*{re.escape(_LOG_PLACEHOLDER)}.*\n?", "", section)
    new_section = "\n".join(new_lines) + (
        "\n" + cleaned.lstrip("\n") if cleaned.strip() else ""
    )
    return _set_section(text, "Progress Log", new_section)


def _project_dirs(root: Path) -> list[Path]:
    return [
        child
        for child in sorted(root.iterdir())
        if child.is_dir()
        and not child.name.startswith(".")
        and child.name not in EXCLUDED_DIRS
        and (child / "README.md").exists()
    ]


# ---------------------------------------------------------------------------
# Per-project sync
# ---------------------------------------------------------------------------


def sync_project(readme_path: Path, dry_run: bool) -> bool:
    """Return True if the file was (or would be) modified."""
    text = readme_path.read_text(encoding="utf-8")

    repo_url = _read_field(text, "Repo")
    if not repo_url or "<owner>" in repo_url:
        print(f"  [skip] {readme_path.parent.name}: no valid Repo field")
        return False

    parsed = _parse_repo_url(repo_url)
    if not parsed:
        print(f"  [skip] {readme_path.parent.name}: cannot parse repo URL '{repo_url}'")
        return False

    owner, repo = parsed
    print(f"  [sync] {readme_path.parent.name} ← github.com/{owner}/{repo}")

    # ── tracker.yml (highest priority source) ──────────────────────────────
    tracker = _fetch_tracker_yml(owner, repo)

    # ── Repo metadata ──────────────────────────────────────────────────────
    repo_data = _get(f"{GITHUB_API}/repos/{owner}/{repo}")

    # ── Latest commits, merged PRs, and upstream changelog ─────────────────
    branch = repo_data.get("default_branch", "main")
    commits = _fetch_commits(owner, repo, branch, n=20)
    prs = _fetch_merged_prs(owner, repo, n=15)
    changelog = _fetch_upstream_changelog(owner, repo)

    last_commit_iso = ""
    if commits:
        last_commit_iso = (
            commits[0].get("commit", {}).get("committer", {}).get("date", "")[:10]
        )

    # ── Derive values ───────────────────────────────────────────────────────
    new_updated = last_commit_iso or dt.date.today().isoformat()

    description = (repo_data.get("description") or "").strip()
    open_issues = repo_data.get("open_issues_count", 0)
    is_archived = repo_data.get("archived", False)

    # Build new Notes — tracker.yml → GitHub description → keep existing
    current_notes = _read_field(text, "Notes")
    placeholder_notes = {
        "Fill in project notes.",
        "Brief summary of current progress.",
        "(auto-populated from repo description on next sync)",
        "_auto-filled by Claude on first sync_",
    }
    if tracker.get("description"):
        base_notes = tracker["description"]
    elif current_notes in placeholder_notes and description:
        base_notes = description
    else:
        base_notes = re.sub(r"\s*\(\d+ open issues?\)", "", current_notes).strip()
    new_notes = (
        f"{base_notes} ({open_issues} open issue{'s' if open_issues != 1 else ''})"
        if open_issues
        else base_notes
    )

    # Status — tracker.yml can pin status; otherwise archived → Completed
    current_status = _read_field(text, "Status")
    if is_archived:
        new_status = "Completed"
    elif tracker.get("status"):
        new_status = tracker["status"]
    else:
        new_status = current_status

    # Goals — tracker.yml → milestones → topics → keep placeholder
    goals_body = _read_section(text, "Goals")
    goals_lines = {ln.strip() for ln in goals_body.splitlines() if ln.strip()}
    new_goals: str | None = None
    goals_source = ""
    if tracker.get("goals"):
        new_goals = "\n".join(f"- {g}" for g in tracker["goals"])
        goals_source = "tracker.yml"
    elif goals_lines and goals_lines.issubset(_GOAL_PLACEHOLDERS):
        milestones = _fetch_milestones(owner, repo)
        if milestones:
            new_goals = "\n".join(f"- {m}" for m in milestones)
            goals_source = "milestones"
        elif repo_data.get("topics"):
            new_goals = "\n".join(f"- {t}" for t in repo_data["topics"])
            goals_source = "topics"

    # ── Apply ───────────────────────────────────────────────────────────────
    original = text
    text = _set_field(text, "Last Updated", new_updated)
    if new_notes:
        text = _set_field(text, "Notes", new_notes)
    if new_status != current_status:
        text = _set_field(text, "Status", new_status)
        print(f"    status: {current_status} → {new_status}")
    if new_goals:
        text = _set_section(text, "Goals", new_goals)
        print(f"    goals: populated from {goals_source}")
    text = _merge_progress_log(text, commits, prs=prs, changelog=changelog)

    print(f"    last updated: {new_updated}  |  issues: {open_issues}")

    if text == original:
        print(f"    no changes")
        return False

    if not dry_run:
        readme_path.write_text(text, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root path")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print changes without writing"
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    changed: list[str] = []

    for d in _project_dirs(root):
        try:
            if sync_project(d / "README.md", args.dry_run):
                changed.append(d.name)
        except RuntimeError as exc:
            print(f"  [error] {d.name}: {exc}")

    if changed:
        print(f"\nUpdated: {', '.join(changed)}")
    else:
        print("\nNo projects updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
