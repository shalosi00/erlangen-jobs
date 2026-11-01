#!/usr/bin/env python3
"""Chart for the certificate roadmap: skill-stack demand in the 77 active FISI postings.
DM-1 palette, consistent with azure_report_charts.py."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ACCENT = "#1B6B7A"
ACCENT2 = "#D4875A"
GRID = "#E0E0E0"
TEXT = "#333333"
OUT = "/home/z/my-project/data/azure_demand"

# values from cert_stats_20261030-1111.json (now corpus, n=77)
rows = [
    ("Network (Cisco/FortiGate/VPN/LAN)\n→ CompTIA Network+ / CCNA", 26, 33.8),
    ("IT security (Datenschutz/DSGVO/ISO 27001)\n→ CompTIA Security+", 16, 20.8),
    ("IT service management (ticketing/ITIL)\n→ ITIL 4 Foundation", 14, 18.2),
    ("Virtualization (VMware/Hyper-V/Proxmox)\n→ AZ-104 / AZ-800 / VCP", 12, 15.6),
    ("Linux (Debian/Ubuntu/RHEL)\n→ LPIC-1 (optional)", 11, 14.3),
    ("Cloud (any provider)\n→ AZ-900 / AZ-104", 10, 13.0),
    ("Microsoft 365 / Intune / endpoint\n→ MD-102", 5, 6.5),
    ("Windows Server + AD/Entra\n→ AZ-104 / AZ-800", 8, 10.4),
]
# union rows must not be double-counted visually; use separate (non-additive) bars
labels = [r[0] for r in rows]
vals = [r[2] for r in rows]
ns = [r[1] for r in rows]

fig, ax = plt.subplots(figsize=(9.8, 5.6), constrained_layout=True)
colors = [ACCENT] * len(rows)
colors[0] = ACCENT2          # highlight the single largest demand: network
colors[5] = ACCENT2          # highlight cloud (voucher core)
bars = ax.barh(labels, vals, color=colors, height=0.62, edgecolor="white")
for bar, v, n in zip(bars, vals, ns):
    ax.text(bar.get_width() + 0.7, bar.get_y() + bar.get_height() / 2,
            f"{v:.1f}%  (n={n})", va="center", fontsize=10, color=TEXT)
ax.invert_yaxis()
ax.set_xlim(0, 41)
ax.set_xlabel("Share of the 77 active postings mentioning the stack (%)", fontsize=11, color=TEXT)
ax.set_title("Skill stacks demanded by the 77 active Systemintegration postings\n"
             "(Erlangen 50 km, 2026-10-30) with the certificate that maps to each",
             fontsize=12.5, pad=12, color=TEXT)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="x", alpha=0.3, color=GRID)
ax.tick_params(labelsize=9.5)
fig.savefig(f"{OUT}/chart3_skill_stacks.png", dpi=200, facecolor="white", edgecolor="none")
plt.close(fig)
print("saved", f"{OUT}/chart3_skill_stacks.png")
