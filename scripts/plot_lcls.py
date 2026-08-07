"""Figure 1: agent-orchestrated FEL tuning on the LCLS hard X-ray line.

    a  every archived run of the 26 June 2026 shift, by time of day
    b  the staged campaign of 22:08-22:27, evaluation by evaluation
    c  the beam-loss monitor carried as a soft constraint over the same run

    python scripts/plot_lcls.py [-o figures/lcls_autotune_campaign.pdf]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator

from agentic_runs import lcls
from agentic_runs.style import GRID, INK, INK2, MUTED, SERIES, WARN, recolour_legend, tidy, use_paper_style


def hour_of_day(run):
    """Decimal hour, with after-midnight runs continuing past 24."""
    t = run.created
    h = t.hour + t.minute / 60 + t.second / 3600
    return h + 24 if h < 12 else h


def panel_shift(ax, runs):
    """Best value of every archived run, against the time it started."""
    runs = sorted(runs, key=hour_of_day)
    ax.step([hour_of_day(r) for r in runs], lcls.running_best([r.best for r in runs]),
            where="post", color=SERIES, linewidth=1.6, zorder=3)

    for r in runs:
        size = 12 + 34 * (min(r.n_evaluations, 140) / 140) ** 0.6
        if r.launched_by_agent:
            ax.scatter(hour_of_day(r), r.best, s=size, color=INK2, zorder=5, linewidths=0)
        else:
            ax.scatter(hour_of_day(r), r.best, s=size, facecolor="white",
                       edgecolor=MUTED, linewidth=0.9, zorder=4)

    ax.axvspan(18.0, 19.0, color=GRID, alpha=0.55, zorder=0)
    ax.annotate("operator baseline\n(manual section sweep)", xy=(18.5, 0.30),
                ha="center", va="bottom", fontsize=6.8, color=INK2, linespacing=1.3)
    ax.annotate("staged campaign\n(panels b, c)", xy=(22.36, 1.83), xytext=(23.25, 1.99),
                fontsize=6.8, color=INK, ha="left", va="top", linespacing=1.3,
                arrowprops=dict(arrowstyle="-", lw=0.7, color=MUTED, shrinkA=2, shrinkB=3))

    ax.set_xlim(17.8, 24.3)
    ax.set_ylim(0.0, 2.05)
    ax.set_xticks(range(18, 25))
    ax.set_xticklabels(["18:00", "19:00", "20:00", "21:00", "22:00", "23:00", "00:00"])
    ax.yaxis.set_major_locator(MultipleLocator(0.5))
    ax.set_ylabel("best of each run (mJ)")
    ax.set_xlabel("time of day, 26 June 2026", labelpad=2)
    tidy(ax)

    recolour_legend(ax.legend(
        [Line2D([], [], marker="o", ls="none", ms=4.4, color=INK2),
         Line2D([], [], marker="o", ls="none", ms=4.4, mfc="white", mec=MUTED),
         Line2D([], [], color=SERIES, lw=1.6)],
        ["agent-launched run", "control-room Badger run", "best so far"],
        loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=3, frameon=False,
        fontsize=7, handlelength=1.3, handletextpad=0.5, columnspacing=1.8))


def panel_campaign(ax, stages, baseline):
    values = [v for s in stages for v in s.values]
    x = range(1, len(values) + 1)
    boundary = stages[0].n

    ax.scatter(x, values, s=13, facecolor="white", edgecolor=MUTED,
               linewidth=0.7, zorder=3, label="individual evaluation")
    ax.plot(x, lcls.running_best(values), color=SERIES, linewidth=2.0,
            zorder=4, label="best so far")
    ax.axhline(baseline, color=INK2, linewidth=0.8, linestyle=(0, (1.5, 2)), zorder=2)
    ax.annotate("best of the operator's own sweep earlier in the shift, %.2f" % baseline,
                xy=(3, 1.90), fontsize=6.8, color=INK2, ha="left", va="center")

    ax.annotate("%.2f" % values[0], xy=(1, values[0]), xytext=(2.5, 0.22),
                color=INK, fontsize=8, ha="left", va="center")
    peak = max(values)
    ax.annotate("%.2f" % peak, xy=(values.index(peak) + 1, peak),
                xytext=(values.index(peak) + 3, 1.94),
                color=INK, fontsize=8, ha="left", va="center")

    # Stage banners sit in the headroom above the axes.
    for stage, centre in zip(stages, (boundary / 2 + 0.5,
                                      boundary + (len(values) - boundary) / 2 + 0.5)):
        ax.annotate(stage.label, xy=(centre, 1.16), xycoords=("data", "axes fraction"),
                    ha="center", va="baseline", fontsize=8.5, fontweight="bold",
                    color=INK, annotation_clip=False)
        ax.annotate("%s\n%s, %d evaluations" % (stage.generator, stage.knobs, stage.n),
                    xy=(centre, 1.03), xycoords=("data", "axes fraction"),
                    ha="center", va="baseline", fontsize=7.2, color=INK2,
                    linespacing=1.35, annotation_clip=False)

    ax.set_ylabel("FEL pulse intensity (mJ)")
    ax.set_ylim(-0.05, 2.05)
    ax.yaxis.set_major_locator(MultipleLocator(0.5))
    ax.tick_params(labelbottom=False)
    tidy(ax)
    recolour_legend(ax.legend(loc="lower right", frameon=False, fontsize=7.5,
                              handletextpad=0.6, borderpad=0.2, labelspacing=0.35,
                              bbox_to_anchor=(1.0, -0.03)))
    return boundary, len(values)


def panel_constraint(ax, stages, n_total):
    loss = [v for s in stages for v in s.loss]
    x = range(1, len(loss) + 1)
    ax.axhline(lcls.CONSTRAINT_FLOOR, color=WARN, linewidth=1.2,
               linestyle=(0, (3, 2)), zorder=2)
    ax.text(n_total - 0.5, lcls.CONSTRAINT_FLOOR + 3, "soft constraint  $> %.0f$ mV"
            % lcls.CONSTRAINT_FLOOR, ha="right", va="bottom", fontsize=7, color=WARN)
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
    runs = lcls.shift()
    stages = lcls.campaign()
    baseline = lcls.operator_baseline(runs)

    fig = plt.figure(figsize=(6.9, 5.95))
    outer = fig.add_gridspec(2, 1, height_ratios=[1.42, 2.30], hspace=0.55,
                             left=0.105, right=0.985, top=0.905, bottom=0.075)
    inner = outer[1].subgridspec(2, 1, height_ratios=[1.62, 0.62], hspace=0.20)

    ax_shift = fig.add_subplot(outer[0])
    ax_campaign = fig.add_subplot(inner[0])
    ax_loss = fig.add_subplot(inner[1], sharex=ax_campaign)

    panel_shift(ax_shift, runs)
    boundary, n_total = panel_campaign(ax_campaign, stages, baseline)
    panel_constraint(ax_loss, stages, n_total)

    for ax in (ax_campaign, ax_loss):
        ax.axvline(boundary + 0.5, color=MUTED, linewidth=0.8,
                   linestyle=(0, (4, 3)), zorder=1)
    for ax, label in ((ax_shift, "a"), (ax_campaign, "b"), (ax_loss, "c")):
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
