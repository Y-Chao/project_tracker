#!/usr/bin/env python3
"""Validate project tracker structure and required fields."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

REQUIRED_FIELDS = [
    "Status",
    "Period",
    "Last Updated",
    "Notes",
    "TOC",
    "Graphic Abstract",
]

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


def validate_project_readme(readme_path: Path) -> list[str]:
    text = readme_path.read_text(encoding="utf-8")
    issues = []

    for field in REQUIRED_FIELDS:
        pattern = re.compile(rf"^-\s+\*\*{re.escape(field)}\*\*:\s*.+$", re.MULTILINE)
        if not pattern.search(text):
            issues.append(f"Missing field '{field}' in {readme_path}")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strict", action="store_true", help="Exit non-zero on any issue"
    )
    parser.add_argument("--root", default=".", help="Repository root path")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    issues: list[str] = []

    dirs = project_dirs(root)
    if not dirs:
        print("No project directories found — nothing to validate.")
        return 0

    for d in dirs:
        readme = d / "README.md"
        issues.extend(validate_project_readme(readme))

    if issues:
        print("Validation issues found:")
        for item in issues:
            print(f"- {item}")
        return 1 if args.strict else 0

    print("Project tracker validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
