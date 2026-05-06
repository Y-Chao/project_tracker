#!/usr/bin/env python3
"""Report stale projects based on Last Updated field in project README.md."""

from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

EXCLUDED_DIRS = {
    ".git",
    ".github",
    "assets",
    "scripts",
    "templates",
    "__pycache__",
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


def read_last_updated(readme_text: str) -> str | None:
    m = re.search(
        r"^-\s+\*\*Last Updated\*\*:\s*(.+)$", readme_text, flags=re.MULTILINE
    )
    return m.group(1).strip() if m else None


def parse_date(value: str) -> dt.date | None:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="stale_report.md")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    cutoff = dt.date.today() - dt.timedelta(days=args.days)
    stale_items: list[str] = []

    for d in project_dirs(root):
        text = (d / "README.md").read_text(encoding="utf-8")
        raw = read_last_updated(text)
        if not raw:
            stale_items.append(f"- {d.name}: missing Last Updated field")
            continue

        parsed = parse_date(raw)
        if not parsed:
            stale_items.append(f"- {d.name}: invalid Last Updated format ({raw})")
            continue

        if parsed <= cutoff:
            stale_items.append(f"- {d.name}: last updated on {parsed.isoformat()}")

    if stale_items:
        body = [
            f"## Stale Project Reminder (>{args.days} days)",
            "",
            *stale_items,
            "",
            "Please update project status and notes if needed.",
        ]
    else:
        body = [
            "## Stale Project Reminder",
            "",
            "No stale projects found.",
        ]

    output_path = root / args.output
    output_path.write_text("\n".join(body) + "\n", encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
