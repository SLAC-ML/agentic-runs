"""Figure 2: five autonomous six-phase injector start-ups at FACET-II.

    a  cumulative runner time per phase, one row per campaign
    b  the injector-emittance phase, one small multiple per campaign
    c  the energy-spread phase, same layout

    python scripts/plot_facet.py [-o figures/facet_campaigns.pdf]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator

from agentic_runs import emitscan, facet
from agentic_runs.style import (GRID, INK, INK2, MUTED, PHASE_SHADES, SERIES,
                                WARN, recolour_legend, tidy, use_paper_style)

EMITTANCE_PHASE, ENERGY_SPREAD_PHASE = 5, 4


def panel_timeline(ax, campaigns):
    """One stacked bar per campaign, segments in phase order."""
    for row, campaign in enumerate(campaigns):
        left = 0.0
        for number in sorted(facet.PHASES):
            attempts = [p for p in campaign.phases if p.number == number]
            seconds = sum(p.seconds or 0.0 for p in attempts)
            ax.barh(row, seconds / 60, left=left / 60, height=0.58,
                    color=PHASE_SHADES[number - 1], edgecolor="white",
                    linewidth=1.1, zorder=3)
            if any(p.is_retry or not p.passed for p in attempts):
                ax.plot(left / 60 + seconds / 120, row - 0.46, marker="v", ms=4.5,
                        color=WARN, zorder=6, clip_on=False)
            left += seconds
        ax.text(left / 60 + 0.3, row, "%.0f min" % (left / 60),
                va="center", ha="left", fontsize=7, color=INK2)

    ax.set_yticks(range(len(campaigns)))
    ax.set_yticklabels(["%s  ·  %d pC" % (c.tag, c.charge_pc) for c in campaigns],
                       fontsize=7.5, color=INK)
    ax.invert_yaxis()
    ax.set_xlabel("cumulative runner time within the campaign (min)", labelpad=2)
    ax.set_xlim(0, 27)
    ax.xaxis.set_major_locator(MultipleLocator(5))
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)

    labels = [facet.PHASES[n]["legend"] for n in sorted(facet.PHASES)]
    recolour_legend(ax.legend(
        [plt.Rectangle((0, 0), 1, 1, color=PHASE_SHADES[n - 1]) for n in sorted(facet.PHASES)]
        + [Line2D([], [], marker="v", ls="none", ms=4.5, color=WARN)],
        labels + ["step failed; agent retried autonomously"],
        loc="lower center", bbox_to_anchor=(0.5, 1.06), ncol=3, frameon=False,
        fontsize=6.8, handlelength=1.1, handletextpad=0.5,
        columnspacing=1.2, labelspacing=0.5))


def error_bars(campaign, phase, search):
    """One-sigma bar for every evaluation of the emittance phase.

    Each evaluation is a quadrupole scan whose raw data is on disk, so the bar
    is that scan's own fit uncertainty and varies from point to point. Scans
    taken when the beam was hard to image lose points to the size and
    signal-to-noise cutoffs, and come out visibly less certain.
    """
    fractions = emitscan.uncertainty_for(campaign.directory.name,
                                         phase.scans[:len(search)])
    return [f * v for f, v in zip(fractions, search)]


def panel_phase(fig, gridspec, row, campaigns, number, ylabel, ylim, ytick, sigma=None):
    """One small multiple per campaign for a single phase.

    `sigma` is either a single number, drawn as the same bar on every point, or
    a function (campaign, phase, search) returning one bar per point.
    """
    axes = []
    for column, campaign in enumerate(campaigns):
        ax = fig.add_subplot(gridspec[row, column])
        axes.append(ax)
        phase = campaign.phase(number)
        search, feasible = phase.search, phase.feasible
        x = list(range(1, len(search) + 1))
        yerr = sigma(campaign, phase, search) if callable(sigma) else sigma

        # Best-so-far holds flat until an improvement arrives, then steps up to
        # it, so this is a staircase rather than a line through the points.
        best, envelope = float("inf"), []
        for value, ok in zip(search, feasible):
            if ok:
                best = min(best, value)
            envelope.append(best if best < float("inf") else float("nan"))
        ax.step(x, envelope, where="post", color=SERIES, linewidth=1.6, zorder=3)

        if yerr is not None:
            ax.errorbar(x, search, yerr=yerr, fmt="none", ecolor=MUTED,
                        elinewidth=0.7, capsize=1.6, capthick=0.7, zorder=2)
        ax.scatter([i for i, ok in zip(x, feasible) if ok],
                   [v for v, ok in zip(search, feasible) if ok],
                   s=15, color=INK2, zorder=4, linewidths=0)
        if not all(feasible):
            ax.scatter([i for i, ok in zip(x, feasible) if not ok],
                       [v for v, ok in zip(search, feasible) if not ok],
                       s=15, facecolor="white", edgecolor=MUTED, linewidth=0.8, zorder=4)
        if phase.reevaluation is not None:
            ax.scatter([len(search) + 1], [phase.reevaluation], marker="x", s=24,
                       color=WARN, linewidth=1.4, zorder=5, clip_on=False)

        ax.set_ylim(*ylim)
        ax.set_xlim(0.3, max(len(search) + 1, 10) + 0.7)
        ax.yaxis.set_major_locator(MultipleLocator(ytick))
        tidy(ax)
        ax.set_title("%s · %d pC" % (campaign.tag, campaign.charge_pc),
                     fontsize=7.5, color=INK, pad=3)
        ax.set_ylabel(ylabel, fontsize=7.5) if column == 0 else ax.set_yticklabels([])
        ax.set_xlabel("evaluation", fontsize=7, labelpad=1.5)
        ax.xaxis.set_major_locator(MultipleLocator(5))
    return axes


def main(out: Path) -> None:
    use_paper_style()
    campaigns = facet.read_all()

    fig = plt.figure(figsize=(7.1, 6.1))
    gs = fig.add_gridspec(3, 5, height_ratios=[1.30, 1.0, 0.82], hspace=0.70,
                          wspace=0.26, left=0.105, right=0.985, top=0.885, bottom=0.135)

    ax_timeline = fig.add_subplot(gs[0, :])
    panel_timeline(ax_timeline, campaigns)

    # The emittance phase saved its raw scans, so each point gets its own fit
    # uncertainty. The energy-spread phase saved no equivalent, so it falls back
    # to how far a repeated measurement moved.
    spread_sigma = facet.repeatability(campaigns, ENERGY_SPREAD_PHASE)
    ax_emit = panel_phase(fig, gs, 1, campaigns, EMITTANCE_PHASE,
                          "injector emittance\n" + r"$\varepsilon_{\mathrm{mean}}$ ($\mu$m)",
                          # Wide enough that no error bar runs off the panel.
                          (1.7, 8.6), 2, sigma=error_bars)
    ax_spread = panel_phase(fig, gs, 2, campaigns, ENERGY_SPREAD_PHASE,
                            "dispersive size\n" + r"$\mathrm{rms}_x$ ($\mu$m)",
                            (168, 292), 40, sigma=spread_sigma)

    recolour_legend(fig.legend(
        [Line2D([], [], marker="o", ls="none", ms=4.0, color=INK2),
         Line2D([], [], marker="o", ls="none", ms=4.0, mfc="white", mec=MUTED),
         Line2D([], [], color=SERIES, lw=1.6),
         Line2D([], [], marker="x", ls="none", ms=5, color=WARN, mew=1.4),
         Line2D([], [], color=MUTED, lw=0.7, marker="_", ms=5, mew=0.7)],
        ["matching preserved ($b_{\\mathrm{mag}} < %.1f$)" % facet.BMAG_LIMIT,
         "matching violated", "best feasible so far",
         "re-evaluation of the selected best point",
         "$1\\sigma$: quad-scan fit (b), repeatability $\\pm%.1f\\,\\mu$m (c)"
         % spread_sigma],
        loc="lower center", bbox_to_anchor=(0.545, 0.005), ncol=3, frameon=False,
        fontsize=6.8, handlelength=1.4, handletextpad=0.5,
        columnspacing=1.8, labelspacing=0.45))

    ax_timeline.text(-0.075, 1.0, "a", transform=ax_timeline.transAxes, fontsize=10,
                     fontweight="bold", color=INK, va="bottom", ha="right")
    for ax, label in ((ax_emit[0], "b"), (ax_spread[0], "c")):
        ax.text(-0.52, 1.02, label, transform=ax.transAxes, fontsize=10,
                fontweight="bold", color=INK, va="bottom", ha="right")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, pad_inches=0.02)
    print("wrote %s" % out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--out", type=Path, default=Path("figures/facet_campaigns.pdf"))
    main(ap.parse_args().out)
