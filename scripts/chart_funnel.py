#!/usr/bin/env python3
"""chart_funnel.py — base-rate funnel chart for the Task 21 methodology report.

Data: The Interview Guys 2025 avg (via askcruit d1): 32 applications -> 4
interviews -> 1 offer. Horizontal bars per charts.md: no top/right spines,
dashed grid 20% opacity, values at bar ends, no internal title (caption lives
in the PDF). Palette: cascade ACCENT / ACCENT_2.
"""
import matplotlib
import matplotlib.font_manager as fm

fm.fontManager.addfont('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')

import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Noto Sans SC']
plt.rcParams['axes.unicode_minus'] = False

ACCENT = '#96771c'
ACCENT_2 = '#5537b0'
TEXT = '#22211f'
MUTED = '#87857d'
BORDER = '#c2beb0'

labels = ['Applications\nper offer', 'Interviews\nper offer', 'Offers']
values = [32, 4, 1]
colors_ = [ACCENT, ACCENT, ACCENT_2]

fig, ax = plt.subplots(figsize=(7.0, 2.9), dpi=200, constrained_layout=True)
bars = ax.barh(labels[::-1], values[::-1], color=colors_[::-1], height=0.56,
               edgecolor='none', zorder=3)

for spine in ('top', 'right', 'left'):
    ax.spines[spine].set_visible(False)
ax.spines['bottom'].set_color(BORDER)
ax.spines['bottom'].set_linewidth(0.8)
ax.tick_params(axis='y', length=0, labelsize=11, colors=TEXT)
ax.tick_params(axis='x', length=0, labelbottom=False)
ax.grid(axis='x', linestyle='--', linewidth=0.5, alpha=0.2, zorder=0)
ax.set_axisbelow(True)
ax.set_xlim(0, 36)

for bar, v in zip(bars, values[::-1]):
    ax.text(bar.get_width() + 0.7, bar.get_y() + bar.get_height() / 2,
            str(v), va='center', ha='left', fontsize=12, color=TEXT,
            fontweight='bold', zorder=4)

fig.savefig('/home/z/my-project/scripts/out/funnel_base_rates.png',
            facecolor='white')
print('chart saved')
