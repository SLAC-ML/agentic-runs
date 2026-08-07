"""Print a plain-text summary of both data sets.

Run this first: it reads the raw files and reports the numbers that appear in
the paper, so you can check the extraction before making any figures.

    python scripts/summarize.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentic_runs import emitscan, facet, lcls


def summarize_lcls() -> None:
    runs = lcls.shift()
    agent = [r for r in runs if r.launched_by_agent]
    print("LCLS, 26 June 2026")
    print("  archived runs on the reported objective : %d" % len(runs))
    print("    launched by the agent                 : %d" % len(agent))
    print("    driven by operators                   : %d" % (len(runs) - len(agent)))
    print("  total machine evaluations               : %d" % sum(r.n_evaluations for r in runs))
    print("  operator baseline before 19:00          : %.3f" % lcls.operator_baseline(runs))
    print("  best of the shift                       : %.4f" % max(r.best for r in runs))

    stages = lcls.campaign()
    values = [v for s in stages for v in s.values]
    loss = [v for s in stages for v in s.loss]
    print("  campaign")
    for s in stages:
        print("    %-8s %-22s n=%-4d %.4f -> %.4f" %
              (s.label, s.generator.split(" (")[0], s.n, s.values[0], max(s.values)))
    print("    total evaluations                     : %d" % len(values))
    print("    objective                             : %.4f -> %.4f (%+.1f%%)" %
          (values[0], max(values), 100 * (max(values) / values[0] - 1)))
    print("    worst constraint excursion            : %.2f mV (floor %.0f)" %
          (min(v for v in loss if v == v), lcls.CONSTRAINT_FLOOR))


def summarize_facet() -> None:
    print()
    print("FACET-II, 1-2 July 2026")
    total_evals = total_seconds = 0
    for c in facet.read_all():
        total_evals += c.n_evaluations
        total_seconds += c.runner_seconds
        passed = sum(1 for n in facet.PHASES if c.phase(n) and c.phase(n).passed)
        print("  %-3s %4d pC  evals=%-4d runner=%5.1f min  phases %d/6%s" %
              (c.tag, c.charge_pc, c.n_evaluations, c.runner_seconds / 60,
               passed, "  (1 retry)" if c.retried else ""))
    print("  total: %d evaluations, %.0f h %.0f min of runner time" %
          (total_evals, total_seconds // 3600, (total_seconds % 3600) // 60))


def check_emittance_fit() -> None:
    """Confirm the refit still reproduces the fits stored in the scan files.

    If this drifts, the error bars in figure 2b are no longer the uncertainty of
    the measurement that was actually published.
    """
    print()
    print("Emittance refit vs. the fit stored in each scan file")
    result = emitscan.verify()
    print("  plane fits checked                      : %d" % result["n"])
    print("  agreeing to 1 part in 10^4              : %d" % result["agreeing"])
    print("  median relative difference              : %.1e" % result["median"])
    print("  largest                                 : %.1e" % result["worst"])
    print("  (see README: the stragglers are flat-optimum scans, not a bug)")


if __name__ == "__main__":
    summarize_lcls()
    summarize_facet()
    check_emittance_fit()
