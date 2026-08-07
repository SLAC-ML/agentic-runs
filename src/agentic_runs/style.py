"""Shared plot style, so both figures look like they came from one paper."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SERIES = "#2a78d6"   # the one accent colour
INK = "#0b0b0b"      # primary text
INK2 = "#52514e"     # secondary text and data points
MUTED = "#8a8985"    # axes, open markers
GRID = "#e3e2de"     # gridlines
WARN = "#e34948"     # limits and re-evaluations

#: Sequential shades for the six FACET-II phases, light to dark.
PHASE_SHADES = ["#cfe0f5", "#a9c8ee", "#82afe6", "#5b96dd", "#2a78d6", "#1a5399"]


def use_paper_style() -> None:
    """Apply the manuscript's figure style. Call once before plotting."""
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 8,
        "axes.linewidth": 0.6,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK,
        "xtick.color": INK2, "ytick.color": INK2,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "xtick.major.size": 3, "ytick.major.size": 3,
        "pdf.fonttype": 42, "ps.fonttype": 42,   # editable text in the PDF
    })


def tidy(ax, ygrid: bool = True) -> None:
    """Drop the top and right spines and put a light grid behind the data."""
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if ygrid:
        ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def recolour_legend(legend) -> None:
    """Legend text in secondary ink rather than black."""
    for text in legend.get_texts():
        text.set_color(INK2)
