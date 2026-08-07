"""Figure 1: the agent-orchestrated tuning campaign on the LCLS hard X-ray line.

    a  the campaign of 22:08-22:27 on 26 June 2026, evaluation by evaluation
    b  the beam-loss monitor carried as a soft constraint over the same run

    python scripts/plot_lcls.py [-o figures/lcls_autotune_campaign.pdf]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

from agentic_runs import lcls
from agentic_runs.style import (GRID, INK, INK2, MUTED, SERIES, WARN,
                                recolour_legend, tidy, use_paper_style)


def stage_banner(ax, stage, centre):
    """Stage name and its configuration, in the headroom above the axes."""
    ax.annotate(stage.label, xy=(centre, 1.30), xycoords=("data", "axes fraction"),
                ha="center", va="baseline", fontsize=8.5, fontweight="bold",
                color=INK, annotation_clip=False)
    ax.annotate("%s\n%s\n%d evaluations" % (stage.generator, stage.knobs, stage.n),
                xy=(centre, 1.04), xycoords=("data", "axes fraction"),
                ha="center", va="baseline", fontsize=7.2, color=INK2,
                linespacing=1.45, annotation_clip=False)


def panel_campaign(ax, stages, baseline):
    values = [v for s in stages for v in s.values]
    x = list(range(1, len(values) + 1))
    boundary = stages[0].n

    # A light wash behind the second stage separates the two without needing a
    # rule, and ties each banner to the evaluations it describes.
    ax.axvspan(boundary + 0.5, len(values) + 1, color=GRID, alpha=0.45, zorder=0)

    ax.scatter(x, values, s=13, facecolor="white", edgecolor=MUTED,
               linewidth=0.7, zorder=3, label="individual evaluation")
    # Best-so-far holds flat until an improvement arrives, then steps up to it.
    ax.step(x, lcls.running_best(values), where="post", color=SERIES,
            linewidth=2.0, zorder=4, label="best so far")

    ax.axhline(baseline, color=INK2, linewidth=0.8, linestyle=(0, (1.5, 2)), zorder=2)
    # Sits above the plateau so it does not cross the best-so-far line.
    ax.annotate("best of the operator's own sweep earlier in the shift, %.2f" % baseline,
                xy=(2, 1.94), fontsize=6.8, color=INK2, ha="left", va="center")

    ax.annotate("%.2f" % values[0], xy=(1, values[0]), xytext=(2.5, 0.22),
                color=INK, fontsize=8, ha="left", va="center")
    peak = max(values)
    ax.annotate("%.2f" % peak, xy=(values.index(peak) + 1, peak),
                xytext=(values.index(peak) + 3, peak + 0.11),
                color=INK, fontsize=8, ha="left", va="center")

    for stage, centre in zip(stages, (boundary / 2 + 0.5,
                                      boundary + (len(values) - boundary) / 2 + 0.5)):
        stage_banner(ax, stage, centre)

    ax.set_ylabel("FEL pulse intensity (mJ)")
    ax.set_ylim(-0.05, 2.05)
    ax.yaxis.set_major_locator(MultipleLocator(0.5))
    ax.tick_params(labelbottom=False)
    tidy(ax)
    recolour_legend(ax.legend(loc="lower right", frameon=False, fontsize=7.5,
                              handletextpad=0.6, borderpad=0.2, labelspacing=0.35,
                              bbox_to_anchor=(1.0, -0.03)))
    return boundary, len(values)


def panel_constraint(ax, stages, boundary, n_total):
    loss = [v for s in stages for v in s.loss]
    x = list(range(1, len(loss) + 1))

    ax.axvspan(boundary + 0.5, n_total + 1, color=GRID, alpha=0.45, zorder=0)
    ax.axhline(lcls.CONSTRAINT_FLOOR, color=WARN, linewidth=1.2,
               linestyle=(0, (3, 2)), zorder=2)
    ax.text(n_total - 0.5, lcls.CONSTRAINT_FLOOR + 3,
            "soft constraint  $> %.0f$ mV" % lcls.CONSTRAINT_FLOOR,
            ha="right", va="bottom", fontsize=7, color=WARN)
    ax.plot(x, loss, color=INK2, linewidth=1.0, zorder=3)
    ax.scatter(x, loss, s=6, color=INK2, zorder=4, linewidths=0)

    ax.set_ylabel("beam loss (mV)")
    ax.set_ylim(-38, 9)
    ax.yaxis.set_major_locator(MultipleLocator(15))
    ax.set_xlabel("machine evaluation")
    ax.set_xlim(0, n_total + 1)
    ax.xaxis.set_major_locator(MultipleLocator(10))
    tidy(ax)


def main(out: Path) -> None:
    use_paper_style()
    stages = lcls.campaign()
    baseline = lcls.operator_baseline(lcls.shift())

    fig = plt.figure(figsize=(6.9, 4.15))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.70, 0.62], hspace=0.20,
                          left=0.105, right=0.985, top=0.775, bottom=0.105)

    ax_campaign = fig.add_subplot(gs[0])
    ax_loss = fig.add_subplot(gs[1], sharex=ax_campaign)

    boundary, n_total = panel_campaign(ax_campaign, stages, baseline)
    panel_constraint(ax_loss, stages, boundary, n_total)

    for ax, label in ((ax_campaign, "a"), (ax_loss, "b")):
        ax.text(-0.088, 1.0, label, transform=ax.transAxes, fontsize=10,
                fontweight="bold", color=INK, va="bottom", ha="right")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, pad_inches=0.02)
    print("wrote %s" % out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--out", type=Path,
                    default=Path("figures/lcls_autotune_campaign.pdf"))
    main(ap.parse_args().out)
