[![](https://img.shields.io/badge/Project%20Tracker-v1.0-blue)](#) [![](https://img.shields.io/badge/Status-Active-green)](#) [![](https://img.shields.io/badge/Last%20Updated-2026--05--06-yellow)](#)
<h1 align="center">Project Tracker <img src="assets/icon_pt.png" alt="Project Tracker Icon" height="75" style="vertical-align: middle;" /></h1>

Development guide for the Project Tracker repository. For the live project list, see [README.md](README.md).

## Adding a New Project

### Primary flow — GitHub Issue (recommended)

1. Open a new Issue using the **Add New Project** template.
2. Fill in the required fields:

   | Field | Required | Notes |
   |---|:---:|---|
   | **Project Name** | ✅ | Directory name (no spaces) |
   | **GitHub Repository URL** | ✅ | Full URL, e.g. `https://github.com/owner/repo` |
   | **Status** | ✅ | `In Progress` / `Planned` / `On Hold` / `Completed` |
   | **Start Date / End Date** | ✅ | `YYYY-MM-DD`; use `TBD` for open-ended end date |

3. Submit the issue. GitHub automatically applies the `add-project` label.
4. `issue-to-project.yml` detects the label and runs the full scaffold pipeline:
   - Parses issue fields
   - Creates project directory from template
   - Pushes a branch and opens a PR
   - Pre-fetches the linked repo README via PAT (first 2000 chars, works for private repos)
   - Posts `@claude[agent]` comment using PAT (so it appears as user action, not bot)
5. Claude GitHub App sees the `@claude[agent]` mention, reads the comment + pre-fetched README context, fills in `Notes` and `Goals`, and commits to the PR branch.
6. Review and merge the PR. `tracker-sync.yml` runs immediately and regenerates the root `README.md` table.

> **Private repos:** The workflow pre-fetches README content via PAT and embeds it in the comment. Claude App cannot access private repos directly — the context is passed through the comment.

> **Tip:** Add a `tracker.yml` file to your linked repo's `.github/` directory to control what appears in the tracker (description, goals, pinned status). See `.github/templates/tracker.yml` for the schema.

### Alternative flow — manual PR

Open a PR directly with at least `Repo`, `Status`, and `Period` filled in. `new-project.yml` is now **disabled from auto-running** (workflow_dispatch only) — you'll need to scaffold files manually or copy from the template.

## CI/CD Pipelines

| Workflow | Trigger | Purpose |
|---|---|---|
| `issue-to-project.yml` | Issue labeled `add-project` | Full scaffold + Claude enrichment pipeline |
| `tracker-sync.yml` | Push to `main` (project READMEs) | Calls `sync_from_upstream.py`, regenerates table |
| `upstream-sync.yml` | Daily 03:00 UTC | Fetches commits/PRs/changelog from linked repos, updates `Last Updated` and `Progress Log` |
| `tracker-check.yml` | Push / PR | Validates required fields; fails CI if missing |
| `stale-reminder.yml` | Every Monday 02:00 UTC | Creates/updates reminder issue for stale projects |
| `new-project.yml` | `workflow_dispatch` only | Legacy scaffold fallback — disabled |

### Claude enrichment

This project uses the **Claude GitHub App** (not `claude-code-action`):
- Installed once on the repo — no API key configuration needed
- Responds to `@claude[agent]` mentions in PR/issue comments
- `issue-to-project.yml` posts the enrichment request comment using PAT_TOKEN so the mention appears as a user action (GITHUB_TOKEN comments do not trigger the App)

### Progress tracking

`sync_from_upstream.py` tracks three sources from linked repos:
1. **Commits** — recent commits with SHA links
2. **Merged PRs** — recently merged pull requests with PR links
3. **Changelog** — entries from README sections matching `Changelog / What's New / Updates / Release Notes / History`

All three are merged into the `Progress Log` section, sorted newest-first, deduplicated.

## Directory Structure
```.  
├── README.md  
├── development.md  
├── helper.md  ← local only, not tracked
├── .issues.log  ← local only, not tracked
├── <project_name>/
│   ├── README.md
│   ├── graphic_abstract.png
│   └── ...
├── scripts/
│   ├── generate_project_index.py
│   ├── stale_report.py
│   ├── sync_from_upstream.py
│   ├── validate_tracker.py
│   └── _gen_workflow_diagram.py
├── assets/
│   ├── icon_pt.png
│   └── workflow.png
├── .gitignore
└── .github/
    ├── CODEOWNERS
    ├── ISSUE_TEMPLATE/
    │   └── add_project.yml
    ├── PULL_REQUEST_TEMPLATE.md
    ├── templates/
    │   ├── project_template/
    │   │   ├── README.md
    │   │   └── graphic_abstract.png
    │   └── tracker.yml  ← copy to linked repo's .github/ for rich sync
    ├── tools.yml
    └── workflows/
        ├── issue-to-project.yml
        ├── tracker-sync.yml
        ├── upstream-sync.yml
        ├── tracker-check.yml
        ├── stale-reminder.yml
        └── new-project.yml  ← disabled (workflow_dispatch only)
```

## Required Secrets

| Secret | Scope | Usage |
|---|---|---|
| `PAT_TOKEN` | All Y-Chao repos — Contents+Metadata read, Pull requests read/write | Private repo README fetch; posting `@claude[agent]` as user; PR creation |
| `ANTHROPIC_API_KEY` | — | Not currently used; reserved for future direct API integration |
