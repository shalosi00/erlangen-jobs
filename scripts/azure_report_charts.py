#!/usr/bin/env python3
"""Charts for the Azure demand justification report (DM-1 palette derived)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# DM-1 table accent (darkened) for bars, per design-system dark-cover->light-table rule
ACCENT = "#1B6B7A"
ACCENT2 = "#D4875A"  # GO-1 warm contrast for the baseline bar
GRID = "#E0E0E0"
TEXT = "#333333"
OUT = "/home/z/my-project/data/azure_demand"


def save(fig, path):
    fig.savefig(path, dpi=200, facecolor="white", edgecolor="none")
    plt.close(fig)
    print("saved", path)


# ── Chart 1: requirement profile of the 77 active FISI postings ──
cats = ["Azure (explicit)", "Microsoft stack\n(WS/AD/M365/Intune)", "Cloud (any)",
        "Linux", "Virtualization", "Network", "Entry-level signals"]
vals = [3.9, 10.4, 13.0, 14.3, 16.9, 33.8, 40.3]
ns = [3, 8, 10, 11, 13, 26, 31]

fig, ax = plt.subplots(figsize=(9.5, 5.2), constrained_layout=True)
bars = ax.barh(cats, vals, color=ACCENT, height=0.62, edgecolor="white")
bars[-1].set_color(ACCENT2)  # entry-level highlighted (applicant suitability)
for bar, v, n in zip(bars, vals, ns):
    ax.text(bar.get_width() + 0.7, bar.get_y() + bar.get_height() / 2,
            f"{v:.1f}%  (n={n})", va="center", fontsize=10, color=TEXT)
ax.set_xlim(0, 47)
ax.set_xlabel("Share of the 77 active postings (%)", fontsize=11, color=TEXT)
ax.set_title("Requirement profile - 77 active Systemintegration postings (Erlangen 50 km, 2026-10-30)",
             fontsize=12.5, pad=12, color=TEXT)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="x", alpha=0.3, color=GRID)
ax.tick_params(labelsize=10)
save(fig, f"{OUT}/chart1_profile_now.png")

# ── Chart 2: concentration effect (baseline vs FISI target corpus) ──
cats2 = ["All regional postings\n(all professions, n=1,977)",
         "FISI-relevant titles\nwithin baseline (n=76)",
         "Active FISI pipeline\npostings (n=77)"]
vals2 = [3.4, 14.5, 23.4]
cols2 = ["#9AAFB5", "#5F8F98", ACCENT]

fig, ax = plt.subplots(figsize=(9.0, 4.6), constrained_layout=True)
bars = ax.bar(cats2, vals2, color=cols2, width=0.55, edgecolor="white")
for bar, v in zip(bars, vals2):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.6,
            f"{v:.1f}%", ha="center", va="bottom", fontsize=12, color=TEXT, fontweight="bold")
ax.set_ylabel("Share of postings requiring Azure, cloud\nor Microsoft-stack skills (%)",
              fontsize=10.5, color=TEXT)
ax.set_title("Cloud/Microsoft demand concentrates sharply on Systemintegration roles",
             fontsize=12.5, pad=12, color=TEXT)
ax.set_ylim(0, 27)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", alpha=0.3, color=GRID)
ax.tick_params(labelsize=10)
save(fig, f"{OUT}/chart2_concentration.png")
