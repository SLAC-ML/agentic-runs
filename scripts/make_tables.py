"""Generate the two FACET-II tables in the paper, as LaTeX fragments.

    tables/facet_phases.tex  the six phases, medians across the five campaigns
    tables/facet_detail.tex  per-campaign detail for the three scalar phases

    python scripts/make_tables.py [--check]

--check prints the numbers as plain text instead of writing LaTeX, which is
the quickest way to confirm the extraction still agrees with the manuscript.
"""

import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentic_runs import facet

TCAV_PHASE, EMITTANCE_PHASE, ENERGY_SPREAD_PHASE = 6, 5, 4


def mmss(seconds: float) -> str:
    """Minutes and seconds, rounded to the nearest second."""
    total = int(round(seconds))
    return "%d:%02d" % (total // 60, total % 60)


def spread(values, fmt="%d"):
    """One value if they all agree, otherwise a low--high range."""
    lo, hi = min(values), max(values)
    return fmt % lo if lo == hi else "%s--%s" % (fmt % lo, fmt % hi)


def phase_rows(campaigns):
    """One row per phase: evaluations and wall time across the five campaigns."""
    rows = []
    for number in sorted(facet.PHASES):
        phase_info = facet.PHASES[number]
        phases = [c.phase(number) for c in campaigns]
        evals = [p.n_evaluations for p in phases]
        times = [p.seconds or 0.0 for p in phases]
        rows.append({
            "number": number,
            "label": phase_info["label"],
            "algorithm": phase_info["algorithm"],
            "evals": spread(evals),
            # A range only where the phase genuinely varies between campaigns;
            # otherwise the median, which is what the manuscript table reports.
            "time": ("%s--%s" % (mmss(min(times)), mmss(max(times)))
                     if max(times) > 1.5 * max(min(times), 1e-9)
                     else mmss(statistics.median(times))),
        })
    return rows


def detail_rows(campaigns):
    """Per-campaign start, best and re-evaluation for the three scalar phases."""
    rows = []
    for c in campaigns:
        emit = c.phase(EMITTANCE_PHASE)
        spread_ = c.phase(ENERGY_SPREAD_PHASE)
        tcav = c.phase(TCAV_PHASE)
        rows.append({
            "tag": c.tag, "charge": c.charge_pc,
            "emit_n": emit.n_evaluations,
            "emit_start": emit.search[0], "emit_best": emit.best,
            "emit_reeval": emit.reevaluation,
            "emit_bmag": emit.constraint[emit.search.index(emit.best)],
            "spread_start": spread_.search[0], "spread_best": spread_.best,
            "spread_reeval": spread_.reevaluation,
            "tcav_start": tcav.values[0], "tcav_best": min(tcav.values),
        })
    return rows


def write_phases(rows, out: Path) -> None:
    lines = [r"\begin{tabular}{@{}llrl@{}}", r"\toprule",
             r"Phase & Algorithm & Evals & Time \\", r"\midrule"]
    for r in rows:
        lines.append(r"%d\ \ %s & %s & %s & %s \\"
                     % (r["number"], r["label"], r["algorithm"], r["evals"], r["time"]))
    lines += [r"\bottomrule", r"\end{tabular}"]
    out.write_text("\n".join(lines) + "\n")
    print("wrote %s" % out)


def write_detail(rows, out: Path) -> None:
    lines = [r"\begin{tabular}{@{}llrrrrrrrrr@{}}", r"\toprule",
             r"Camp. & pC & evals & start & best & re-eval"
             r" & start & best & re-eval & start & best \\", r"\midrule"]
    for r in rows:
        lines.append(
            "%s & %d & %d & %.2f & %.2f & %.2f & %.1f & %.1f & %.1f & %.4g & %.4g \\\\"
            % (r["tag"], r["charge"], r["emit_n"], r["emit_start"], r["emit_best"],
               r["emit_reeval"], r["spread_start"], r["spread_best"],
               r["spread_reeval"], r["tcav_start"], r["tcav_best"]))
    lines += [r"\bottomrule", r"\end{tabular}"]
    out.write_text("\n".join(lines) + "\n")
    print("wrote %s" % out)


def check(campaigns) -> None:
    print("six phases (medians / ranges across the five campaigns)")
    for r in phase_rows(campaigns):
        print("  %d %-20s %-18s evals=%-8s time=%s"
              % (r["number"], r["label"], r["algorithm"], r["evals"], r["time"]))
    print()
    print("per-campaign detail")
    print("  %-4s %5s %6s %27s %22s %18s"
          % ("camp", "pC", "evals", "emittance (um)", "dispersive size (um)", "TCAV (mm^2)"))
    print("  %-4s %5s %6s %8s %8s %9s %7s %7s %7s %8s %8s"
          % ("", "", "", "start", "best", "re-eval", "start", "best", "re-eval", "start", "best"))
    for r in detail_rows(campaigns):
        print("  %-4s %5d %6d %8.2f %8.2f %9.2f %7.1f %7.1f %7.1f %8.4g %8.4g"
              % (r["tag"], r["charge"], r["emit_n"], r["emit_start"], r["emit_best"],
                 r["emit_reeval"], r["spread_start"], r["spread_best"],
                 r["spread_reeval"], r["tcav_start"], r["tcav_best"]))
    print()
    print("  bmag at the best feasible emittance point: %s"
          % ", ".join("%.2f" % r["emit_bmag"] for r in detail_rows(campaigns)))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="print numbers instead of writing LaTeX")
    ap.add_argument("-d", "--out-dir", type=Path, default=Path("tables"))
    args = ap.parse_args()

    campaigns = facet.read_all()
    if args.check:
        check(campaigns)
        return
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_phases(phase_rows(campaigns), args.out_dir / "facet_phases.tex")
    write_detail(detail_rows(campaigns), args.out_dir / "facet_detail.tex")


if __name__ == "__main__":
    main()
