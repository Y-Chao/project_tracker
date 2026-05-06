#!/usr/bin/env python3
"""Generate project list table in root README.md."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

try:
    import yaml  # PyYAML

    _YAML_OK = True
except ModuleNotFoundError:
    _YAML_OK = False

EXCLUDED_DIRS = {
    ".git",
    ".github",
    "assets",
    "scripts",
    "templates",
    "__pycache__",
}

START = "<!-- PROJECT_TABLE_START -->"
END = "<!-- PROJECT_TABLE_END -->"

TOOLS_START = "<!-- TOOLS_START -->"
TOOLS_END = "<!-- TOOLS_END -->"

STATUS_COLORS: dict[str, str] = {
    "in progress": "blue",
    "completed": "brightgreen",
    "on hold": "lightgrey",
    "cancelled": "red",
    "planned": "yellow",
}


def project_dirs(root: Path) -> list[Path]:
    dirs = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith(".") or child.name in EXCLUDED_DIRS:
            continue
        if (child / "README.md").exists():
            dirs.append(child)
    return dirs


def read_field(text: str, field: str) -> str:
    pattern = re.compile(rf"^-\s+\*\*{re.escape(field)}\*\*:\s*(.+)$", re.MULTILINE)
    m = pattern.search(text)
    if not m:
        return "N/A"
    return m.group(1).strip()


def _badge(status: str) -> str:
    color = STATUS_COLORS.get(status.lower(), "informational")
    label = status.replace(" ", "%20")
    return (
        f'<img src="https://img.shields.io/badge/{label}-{color}?style=flat-square" />'
    )


def _days_left_bar(period: str) -> str:
    """Return a colored badge + ASCII progress bar for days remaining."""
    match = re.search(
        r"(\d{4}[-/]\d{2}[-/]\d{2})\s*[-\u2192]+\s*(\d{4}[-/]\d{2}[-/]\d{2}|TBD)",
        period,
    )
    if not match:
        return "<code>N/A</code>"
    start_raw, end_raw = match.group(1), match.group(2)
    if end_raw.upper() == "TBD":
        return (
            '<img src="https://img.shields.io/badge/TBD-lightgrey?style=flat-square" />'
        )
    today = dt.date.today()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            start = dt.datetime.strptime(start_raw, fmt).date()
            end = dt.datetime.strptime(end_raw, fmt).date()
            break
        except ValueError:
            continue
    else:
        return "<code>N/A</code>"
    total = max((end - start).days, 1)
    elapsed = min(max((today - start).days, 0), total)
    remaining = (end - today).days
    if remaining < 0:
        color, label = "red", f"{abs(remaining)}d%20overdue"
    elif remaining < 30:
        color, label = "orange", f"{remaining}d%20left"
    elif remaining < 90:
        color, label = "yellow", f"{remaining}d%20left"
    else:
        color, label = "brightgreen", f"{remaining}d%20left"
    filled = round(elapsed / total * 10)
    bar = "\u2588" * filled + "\u2591" * (10 - filled)
    badge = (
        f'<img src="https://img.shields.io/badge/{label}-{color}?style=flat-square" />'
    )
    return f"{badge}<br/><sub><code>{bar}</code></sub>"


def build_table(root: Path) -> str:
    header = "| Project | Status | Period | Days Left | Last Updated | Notes |"
    sep = "|:---|:---:|:---:|:---:|:---:|:---|"
    rows = [header, sep]

    for d in project_dirs(root):
        readme = d / "README.md"
        text = readme.read_text(encoding="utf-8")
        status = read_field(text, "Status")
        period = read_field(text, "Period")
        updated = read_field(text, "Last Updated")
        notes = read_field(text, "Notes")
        repo = read_field(text, "Repo")
        period_fmt = period.replace(" - ", " → ") if period != "N/A" else period
        # Project cell: name + optional GitHub icon link
        repo_icon = ""
        if repo and "<owner>" not in repo and repo.startswith("http"):
            repo_icon = (
                f' <a href="{repo}">'
                '<img src="https://img.shields.io/badge/repo-grey?style=flat-square&logo=github" />'
                "</a>"
            )
        project_cell = f"[**{d.name}**]({d.name}/README.md){repo_icon}"
        rows.append(
            f"| {project_cell} "
            f"| {_badge(status)} "
            f"| {period_fmt} "
            f"| {_days_left_bar(period)} "
            f"| {updated} "
            f"| {notes} |"
        )

    return "\n".join(rows)


def build_tools_footer(root: Path) -> str:
    """Read .github/tools.yml and return an HTML fragment for the README footer."""
    tools_file = root / ".github" / "tools.yml"
    if not tools_file.exists():
        return ""

    if not _YAML_OK:
        # Fallback: minimal regex parse for simple key: value lines
        raw = tools_file.read_text(encoding="utf-8")
        tools = []
        current: dict = {}
        for line in raw.splitlines():
            m = re.match(r"^\s+-\s+name:\s+(.+)$", line)
            if m:
                if current:
                    tools.append(current)
                current = {"name": m.group(1).strip()}
            for key in ("url", "logo", "color", "note"):
                km = re.match(rf"^\s+{key}:\s+(.+)$", line)
                if km:
                    current[key] = km.group(1).strip().strip('"')
        if current:
            tools.append(current)
    else:
        data = yaml.safe_load(tools_file.read_text(encoding="utf-8"))
        tools = data.get("tools", []) if data else []

    if not tools:
        return ""

    badges = []
    for t in tools:
        name = t.get("name", "Tool")
        url = t.get("url", "#")
        logo = t.get("logo", "")
        color = t.get("color", "grey")
        note = t.get("note", "")
        label = name.replace(" ", "%20").replace("-", "--")
        logo_part = f"&logo={logo}" if logo else ""
        badge_url = (
            f"https://img.shields.io/badge/{label}-{color}"
            f"?style=flat-square{logo_part}&logoColor=white"
        )
        tip = f' title="{note}"' if note else ""
        badges.append(f'<a href="{url}"{tip}><img src="{badge_url}" /></a>')

    inner = "\n".join(f"  {b}" for b in badges)
    return f'<div align="right">\n<sub>Assisted by:</sub><br/>\n{inner}\n</div>'


def main() -> int:
    root = Path(".").resolve()
    readme_path = root / "README.md"

    text = readme_path.read_text(encoding="utf-8")

    # ── Project table ──────────────────────────────────────────────────────
    table = build_table(root)
    table_block = f"{START}\n{table}\n{END}"

    if START in text and END in text:
        text = re.sub(
            rf"{re.escape(START)}.*?{re.escape(END)}",
            table_block,
            text,
            flags=re.DOTALL,
        )
    else:
        block = f"\n{table_block}\n"
        marker = "## Project List"
        if marker in text:
            text = text.replace(marker, f"{marker}{block}")
        else:
            text = f"{text.rstrip()}\n\n## Projects\n{block}"

    # ── Tools footer ───────────────────────────────────────────────────────
    footer = build_tools_footer(root)
    if footer:
        tools_block = f"{TOOLS_START}\n{footer}\n{TOOLS_END}"
        if TOOLS_START in text and TOOLS_END in text:
            text = re.sub(
                rf"{re.escape(TOOLS_START)}.*?{re.escape(TOOLS_END)}",
                tools_block,
                text,
                flags=re.DOTALL,
            )
        else:
            # Replace old static sub line if present, otherwise append
            old_static = re.compile(r"\n---\n\n<sub>Assisted by.*?</sub>\n?", re.DOTALL)
            if old_static.search(text):
                text = old_static.sub(f"\n---\n\n{tools_block}\n", text)
            else:
                text = f"{text.rstrip()}\n\n---\n\n{tools_block}\n"

    readme_path.write_text(text, encoding="utf-8")
    print("README project table generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
