"""Generate assets/workflow.png — Project Tracker automation diagram.

Run:
    /tmp/pt_venv/bin/python scripts/_gen_workflow_diagram.py
    # or if matplotlib is globally available:
    python3 scripts/_gen_workflow_diagram.py
"""

import os
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# ── Colour palette ────────────────────────────────────────────────────────────
C_HUMAN = "#4A90D9"  # blue  — human / external action
C_ACTION = "#27AE60"  # green — GitHub Actions workflow step
C_CLAUDE = "#8E44AD"  # purple— Claude GitHub App
C_SYNC = "#E67E22"  # orange— scheduled / daily sync
C_BG = "#F8F9FA"  # light grey background

ALPHA = 0.92


def box(ax, x, y, w, h, label, color, fontsize=8.5, wrap=None):
    rect = FancyBboxPatch(
        (x - w / 2, y - h / 2),
        w,
        h,
        boxstyle="round,pad=0.04",
        linewidth=1.2,
        edgecolor="white",
        facecolor=color,
        alpha=ALPHA,
        zorder=3,
    )
    ax.add_patch(rect)
    display = wrap if wrap else label
    ax.text(
        x,
        y,
        display,
        ha="center",
        va="center",
        fontsize=fontsize,
        color="white",
        fontweight="bold",
        zorder=4,
        wrap=True,
        multialignment="center",
    )
    return rect


def arrow(ax, x0, y0, x1, y1, color="#555555", style="->"):
    ax.annotate(
        "",
        xy=(x1, y1),
        xytext=(x0, y0),
        arrowprops=dict(
            arrowstyle=style,
            color=color,
            lw=1.4,
            connectionstyle="arc3,rad=0.0",
        ),
        zorder=2,
    )


def arrow_curve(ax, x0, y0, x1, y1, rad=0.25, color="#555555"):
    ax.annotate(
        "",
        xy=(x1, y1),
        xytext=(x0, y0),
        arrowprops=dict(
            arrowstyle="->",
            color=color,
            lw=1.4,
            connectionstyle=f"arc3,rad={rad}",
        ),
        zorder=2,
    )


def label_arrow(ax, x, y, text, fontsize=7, color="#444444"):
    ax.text(
        x,
        y,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        color=color,
        style="italic",
        zorder=5,
        bbox=dict(fc="white", ec="none", alpha=0.75, pad=1),
    )


# ── Canvas ────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 10))
ax.set_xlim(0, 14)
ax.set_ylim(0, 10)
ax.set_aspect("equal")
ax.axis("off")
fig.patch.set_facecolor(C_BG)
ax.set_facecolor(C_BG)

# ── Column x-positions ───────────────────────────────────────────────────────
X_USER = 1.5  # human actions
X_ISSUE = 4.2  # issue-to-project workflow
X_PR = 7.0  # PR / branch
X_CLAUDE = 9.8  # Claude App
X_SYNC = 12.5  # daily sync

BW, BH = 2.2, 0.55  # default box width/height

# ── Row y-positions ───────────────────────────────────────────────────────────
Y = {
    "user_issue": 9.0,
    "label": 8.2,
    "parse": 7.3,
    "scaffold": 6.4,
    "push_pr": 5.5,
    "fetch_readme": 4.6,
    "post_claude": 3.7,
    "claude_reads": 3.7,  # same row, different column
    "claude_commit": 2.8,
    "merge": 2.0,
    "tracker_sync": 1.1,
    "daily_sync": 4.6,  # right column
    "daily_update": 3.4,
    "daily_regen": 2.2,
}


# ── Section headers ──────────────────────────────────────────────────────────
def section_header(ax, x, y, text, color):
    ax.text(
        x,
        y,
        text,
        ha="center",
        va="bottom",
        fontsize=8,
        color=color,
        fontweight="bold",
        alpha=0.9,
        zorder=5,
    )


section_header(ax, X_USER, 9.55, "① Human", C_HUMAN)
section_header(ax, X_ISSUE, 9.55, "② issue-to-project.yml", C_ACTION)
section_header(ax, X_PR, 9.55, "③ PR Branch", C_ACTION)
section_header(ax, X_CLAUDE, 9.55, "④ Claude App", C_CLAUDE)
section_header(ax, X_SYNC, 9.55, "⑤ Daily Sync", C_SYNC)

# ── Column dividers ──────────────────────────────────────────────────────────
for xd in [2.8, 5.6, 8.4, 11.1]:
    ax.axvline(xd, color="#CCCCCC", lw=0.8, ls="--", zorder=1)

# ── Nodes ─────────────────────────────────────────────────────────────────────
box(
    ax,
    X_USER,
    Y["user_issue"],
    BW,
    BH,
    "Create Issue\n(add-project label)",
    C_HUMAN,
    wrap="Create Issue\n(add-project label)",
)
box(
    ax,
    X_ISSUE,
    Y["label"],
    BW,
    BH,
    "Detect label\nadd-project",
    C_ACTION,
    wrap="Detect label\nadd-project",
)
box(
    ax,
    X_ISSUE,
    Y["parse"],
    BW,
    BH,
    "Parse Issue fields\n(name/repo/dates)",
    C_ACTION,
    wrap="Parse Issue fields\n(name/repo/dates)",
)
box(
    ax,
    X_ISSUE,
    Y["scaffold"],
    BW,
    BH,
    "Scaffold project dir\nfrom template",
    C_ACTION,
    wrap="Scaffold project dir\nfrom template",
)
box(
    ax,
    X_PR,
    Y["push_pr"],
    BW,
    BH,
    "git push branch\nOpen PR",
    C_ACTION,
    wrap="git push branch\nOpen PR",
)
box(
    ax,
    X_ISSUE,
    Y["fetch_readme"],
    BW,
    BH,
    "Fetch linked repo\nREADME via PAT",
    C_ACTION,
    wrap="Fetch linked repo\nREADME via PAT",
)
box(
    ax,
    X_ISSUE,
    Y["post_claude"],
    BW,
    BH,
    "Post @claude[agent]\ncomment (PAT)",
    C_ACTION,
    wrap="Post @claude[agent]\ncomment (PAT)",
)
box(
    ax,
    X_CLAUDE,
    Y["claude_reads"],
    BW,
    BH,
    "Claude App reads\ncomment + context",
    C_CLAUDE,
    wrap="Claude App reads\ncomment + context",
)
box(
    ax,
    X_CLAUDE,
    Y["claude_commit"],
    BW,
    BH,
    "Fill Notes & Goals\nCommit to PR",
    C_CLAUDE,
    wrap="Fill Notes & Goals\nCommit to PR",
)
box(ax, X_USER, Y["merge"], BW, BH, "Review & Merge PR", C_HUMAN)
box(
    ax,
    X_PR,
    Y["tracker_sync"],
    BW,
    BH,
    "tracker-sync.yml\nregen table",
    C_ACTION,
    wrap="tracker-sync.yml\nregen table",
)

# Daily sync column
box(
    ax,
    X_SYNC,
    Y["daily_sync"],
    BW,
    BH,
    "upstream-sync.yml\n(daily 03:00 UTC)",
    C_SYNC,
    wrap="upstream-sync.yml\n(daily 03:00 UTC)",
)
box(
    ax,
    X_SYNC,
    Y["daily_update"],
    BW,
    BH,
    "Fetch commits/PRs\n& changelog",
    C_SYNC,
    wrap="Fetch commits/PRs\n& changelog",
)
box(
    ax,
    X_SYNC,
    Y["daily_regen"],
    BW,
    BH,
    "Update Last Updated\n& Progress Log",
    C_SYNC,
    wrap="Update Last Updated\n& Progress Log",
)

# ── Arrows: main flow ─────────────────────────────────────────────────────────
arrow(ax, X_USER, Y["user_issue"] - BH / 2, X_ISSUE, Y["label"] + BH / 2)
arrow(ax, X_ISSUE, Y["label"] - BH / 2, X_ISSUE, Y["parse"] + BH / 2)
arrow(ax, X_ISSUE, Y["parse"] - BH / 2, X_ISSUE, Y["scaffold"] + BH / 2)
arrow(ax, X_ISSUE, Y["scaffold"] - BH / 2, X_PR, Y["push_pr"] + BH / 2)
# after push PR, fetch README
arrow(ax, X_PR, Y["push_pr"] - BH / 2, X_ISSUE, Y["fetch_readme"] + BH / 2)
arrow(ax, X_ISSUE, Y["fetch_readme"] - BH / 2, X_ISSUE, Y["post_claude"] + BH / 2)
# post → Claude
arrow(ax, X_ISSUE, Y["post_claude"], X_CLAUDE, Y["claude_reads"], color=C_CLAUDE)
label_arrow(ax, (X_ISSUE + X_CLAUDE) / 2, Y["post_claude"] + 0.18, "@claude[agent]")
arrow(
    ax,
    X_CLAUDE,
    Y["claude_reads"] - BH / 2,
    X_CLAUDE,
    Y["claude_commit"] + BH / 2,
    color=C_CLAUDE,
)
# Claude commit back to PR
arrow_curve(
    ax,
    X_CLAUDE,
    Y["claude_commit"] - BH / 2,
    X_PR,
    Y["push_pr"] - BH / 2 - 0.1,
    rad=0.3,
    color=C_CLAUDE,
)
label_arrow(
    ax, (X_CLAUDE + X_PR) / 2 + 0.2, Y["claude_commit"] - 0.5, "commit to branch"
)
# merge
arrow(ax, X_PR, Y["push_pr"] - BH / 2 - 0.5, X_USER, Y["merge"] + BH / 2)
arrow(ax, X_USER, Y["merge"] - BH / 2, X_PR, Y["tracker_sync"] + BH / 2)

# ── Arrows: daily sync ────────────────────────────────────────────────────────
arrow(
    ax,
    X_SYNC,
    Y["daily_sync"] - BH / 2,
    X_SYNC,
    Y["daily_update"] + BH / 2,
    color=C_SYNC,
)
arrow(
    ax,
    X_SYNC,
    Y["daily_update"] - BH / 2,
    X_SYNC,
    Y["daily_regen"] + BH / 2,
    color=C_SYNC,
)
# daily sync writes to project READMEs (points toward PR column)
arrow_curve(
    ax,
    X_SYNC - BW / 2,
    Y["daily_regen"],
    X_PR + BW / 2,
    Y["tracker_sync"] + 0.1,
    rad=-0.3,
    color=C_SYNC,
)
label_arrow(ax, (X_SYNC + X_PR) / 2, Y["daily_regen"] + 0.35, "write project READMEs")

# ── Legend ────────────────────────────────────────────────────────────────────
legend_items = [
    mpatches.Patch(color=C_HUMAN, label="Human / External"),
    mpatches.Patch(color=C_ACTION, label="GitHub Actions"),
    mpatches.Patch(color=C_CLAUDE, label="Claude GitHub App"),
    mpatches.Patch(color=C_SYNC, label="Scheduled Sync"),
]
ax.legend(
    handles=legend_items,
    loc="lower left",
    fontsize=8,
    framealpha=0.9,
    edgecolor="#CCCCCC",
)

# ── Title ─────────────────────────────────────────────────────────────────────
ax.set_title(
    "Project Tracker — Automation Workflow",
    fontsize=13,
    fontweight="bold",
    color="#2C3E50",
    pad=10,
)

# ── Save ──────────────────────────────────────────────────────────────────────
out = os.path.join(os.path.dirname(__file__), "..", "assets", "workflow.png")
out = os.path.normpath(out)
plt.tight_layout()
plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=C_BG)
print(f"Saved: {out}")
