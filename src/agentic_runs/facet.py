"""The FACET-II injector start-up campaigns of 1-2 July 2026.

Each campaign is a directory of numbered phase directories. A phase holds:

  workflow.yaml                      the step list the agent composed
  automatic_workflow_xopt_<ts>.yaml  the Xopt serialization, if the step ran
  worker.log                         the runner log, with timings and errors

A phase that failed before serialization has no Xopt dump; its outcome has to
be read out of the log. Retries appear as sibling directories with a _retryN
suffix.

Two conventions in this data are easy to get wrong and are handled here:

  * The LAST row of an emittance or energy-spread step is a re-evaluation of
    the point the optimizer selected, not an optimization evaluation. Anything
    computed over the search must exclude it.
  * The emittance phase carries a matching constraint, so the best value is the
    lowest one that satisfies it, which is not always the lowest overall.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CAMPAIGNS_DIR = Path("data/facet/campaigns")

#: The five complete six-phase start-ups, with the charge each ran at.
FULL_CAMPAIGNS = (
    ("A", "full-auto-2026-07-01", 1600),
    ("B", "full-start-to-end-2026-07-01", 1600),
    ("C1", "full-bringup-2026-07-01", 2000),
    ("C2", "2200pC-bringup-2026-07-01", 2200),
    ("D", "start_to_end-2026-07-02", 1600),
)

#: The six phases, in the order they run.
#:
#: `algorithm` is the table wording and names the acquisition function;
#: `legend` is the figure wording and says what an evaluation involves. The
#: paper uses both, at two levels of detail, so both are spelled out here
#: rather than derived from one another.
PHASES = {
    1: dict(label="Laser steering",     algorithm="BAX",
            legend="1 laser steering — BAX"),
    2: dict(label="Schottky timing",    algorithm="amortized BOED",
            legend="2 Schottky timing — amortized BOED"),
    3: dict(label="Beam steering",      algorithm="extremum seeking",
            legend="3 beam steering — extremum seeking"),
    4: dict(label="Energy spread",      algorithm="Bayesian (EI)",
            legend="4 energy spread — Bayesian"),
    5: dict(label="Injector emittance", algorithm="Bayesian",
            legend="5 injector emittance — Bayesian + quad scan"),
    6: dict(label="TCAV phasing",       algorithm="Bayesian (EI)",
            legend="6 TCAV phasing — Bayesian"),
}

#: Matching constraint on the emittance phase.
BMAG_LIMIT = 1.5


def repeatability(campaigns, number: int) -> float:
    """Empirical measurement repeatability for a phase, in the objective's units.

    Every campaign re-measures the point the optimizer selected, so the RMS of
    those in-scan-versus-re-evaluated differences says how much a repeated
    measurement moves. It is coarse (n = 5) but it includes drift of the machine
    between the two measurements, which a fit uncertainty cannot see.

    This is what the energy-spread phase has to use. The emittance phase saved
    its raw quadrupole scans, so it gets a real per-measurement uncertainty
    instead; see emitscan.relative_uncertainty.
    """
    import math

    diffs = []
    for campaign in campaigns:
        phase = campaign.phase(number)
        if phase and phase.best is not None and phase.reevaluation is not None:
            diffs.append(abs(phase.best - phase.reevaluation))
    return math.sqrt(sum(d * d for d in diffs) / len(diffs)) if diffs else 0.0

_STEP_DONE = re.compile(r"Completed workflow step: (\S+).*? in ([\d.]+) s")
_STAMP = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+")
_ERROR = re.compile(r"^(\w*(?:Error|Exception)): (.+)$", re.M)


@dataclass
class Phase:
    """One phase of one campaign."""

    number: int
    directory: Path
    step_type: str | None
    objective: str | None
    values: list[float] = field(default_factory=list)
    constraint: list[float] = field(default_factory=list)
    #: For the emittance phase, the quadrupole scan behind each evaluation.
    #: See emitscan.py; empty for every other phase.
    scans: list[str] = field(default_factory=list)
    n_rows: int = 0
    started: dt.datetime | None = None
    ended: dt.datetime | None = None
    seconds: float | None = None
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.error is None and self.step_type is not None

    @property
    def is_retry(self) -> bool:
        return "_retry" in self.directory.name

    @property
    def n_evaluations(self) -> int:
        """Rows in the optimizer table. Two phases declare no objective but
        still evaluate the machine, so this cannot come from `values`."""
        return self.n_rows

    @property
    def search(self) -> list[float]:
        """Optimization evaluations, excluding the best-point re-evaluation."""
        return self.values[:-1] if self.has_reevaluation else self.values

    @property
    def has_reevaluation(self) -> bool:
        return self.step_type in ("minimize_injector_emittance", "minimize_energy_spread")

    @property
    def reevaluation(self) -> float | None:
        return self.values[-1] if self.has_reevaluation and self.values else None

    @property
    def feasible(self) -> list[bool]:
        """Per-evaluation constraint satisfaction, for phases that have one."""
        if not self.constraint:
            return [True] * len(self.search)
        return [c < BMAG_LIMIT for c in self.constraint[:len(self.search)]]

    @property
    def best(self) -> float | None:
        """Lowest value of the search that satisfies the constraint."""
        ok = [v for v, good in zip(self.search, self.feasible) if good]
        return min(ok) if ok else None


@dataclass
class Campaign:
    tag: str
    directory: Path
    charge_pc: int
    phases: list[Phase]

    def phase(self, number: int) -> Phase | None:
        """The phase that counts for this number: the last passing attempt."""
        tries = [p for p in self.phases if p.number == number]
        passing = [p for p in tries if p.passed]
        return passing[-1] if passing else (tries[-1] if tries else None)

    @property
    def runner_seconds(self) -> float:
        """Sum of the per-step durations the runner reported."""
        return sum(p.seconds or 0.0 for p in self.phases)

    @property
    def span_seconds(self) -> float | None:
        """Wall clock from the first phase starting to the last one ending,
        which includes the agent's pre-checks and reporting between phases."""
        starts = [p.started for p in self.phases if p.started]
        ends = [p.ended for p in self.phases if p.ended]
        if not starts or not ends:
            return None
        return (max(ends) - min(starts)).total_seconds()

    @property
    def n_evaluations(self) -> int:
        return sum(p.n_evaluations for p in self.phases)

    @property
    def retried(self) -> bool:
        return any(p.is_retry for p in self.phases)


def _read_log(directory: Path) -> tuple[dt.datetime | None, dt.datetime | None, float | None, str | None]:
    """Start, end, step duration and error text, from the runner log."""
    logs = sorted(directory.glob("*.log"))
    if not logs:
        return None, None, None, None
    text = "\n".join(p.read_text(errors="replace") for p in logs)

    stamps = [dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
              for m in (_STAMP.match(line) for line in text.splitlines()) if m]
    done = _STEP_DONE.search(text)
    seconds = float(done.group(2)) if done else None

    error = None
    if not done:
        hit = _ERROR.search(text)
        error = f"{hit.group(1)}: {hit.group(2)}".strip() if hit else "failed"
    first, last = (stamps[0], stamps[-1]) if stamps else (None, None)
    if seconds is None and first and last:
        seconds = (last - first).total_seconds()
    return first, last, seconds, error


def read_phase(directory: str | Path) -> Phase:
    """Read one phase directory."""
    directory = Path(directory)
    number = int(directory.name.split("_", 1)[0])
    started, ended, seconds, error = _read_log(directory)

    dumps = sorted(directory.glob("automatic_workflow_xopt_*.yaml"))
    if not dumps:
        return Phase(number=number, directory=directory, step_type=None,
                     objective=None, started=started, ended=ended,
                     seconds=seconds, error=error or "no optimizer dump")

    doc = yaml.safe_load(dumps[-1].read_text())
    step_type, handlers = next(iter(doc["task_handlers"].items()))
    xopt = handlers[0]["xopt"]
    table = xopt["data"]
    vocs = xopt["generator"].get("vocs") or {}

    def column(name):
        col = table[name]
        return [col[k] for k in sorted(col, key=int)]

    objective = next(iter(vocs.get("objectives") or {}), None)
    constraint = next(iter(vocs.get("constraints") or {}), None)
    n_rows = len(next(iter(table.values()))) if table else 0
    # Recorded as "./emittance_scan_<stamp>.h5"; the bare name is the key.
    scans = [Path(p).name for p in column("save_filename")] if "save_filename" in table else []
    return Phase(
        number=number,
        directory=directory,
        step_type=step_type,
        objective=objective,
        values=column(objective) if objective else [],
        constraint=column(constraint) if constraint and constraint in table else [],
        scans=scans,
        n_rows=n_rows,
        started=started, ended=ended, seconds=seconds, error=error,
    )


def read_campaign(tag: str, directory: str | Path, charge_pc: int) -> Campaign:
    """Read one campaign directory, phases in numeric order."""
    directory = Path(directory)
    phases = [read_phase(p) for p in sorted(directory.iterdir()) if p.is_dir()]
    return Campaign(tag=tag, directory=directory, charge_pc=charge_pc, phases=phases)


def read_all(root: str | Path = CAMPAIGNS_DIR) -> list[Campaign]:
    """The five complete six-phase campaigns, in the order they ran."""
    root = Path(root)
    return [read_campaign(tag, root / name, charge) for tag, name, charge in FULL_CAMPAIGNS]
