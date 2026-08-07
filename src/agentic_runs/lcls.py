"""The LCLS hard X-ray shift of 26 June 2026.

Two views of the same evening:

  shift()     every archived run, used for the time-of-day panel
  campaign()  the two stages of the agent-orchestrated campaign that ran
              between 22:08 and 22:27

The campaign stages are identified by their archive timestamps rather than by
their routine names, because several routines that evening share a name.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .badger import BadgerRun, read_archive

ARCHIVE = Path("data/lcls/badger-archive/2026-06-26")

#: The two rounds of campaign pulse_intensity_p80-2026-06-26-220828.
CAMPAIGN_STAGES = (
    ("Stage 1", "lcls-2026-06-26-220917.yaml",
     "upper confidence bound ($\\beta = 2.0$)", "4 LTUH matching quadrupoles"),
    ("Stage 2", "lcls-2026-06-26-222040.yaml",
     "expected improvement", "8 LI26 transport quadrupoles"),
)

#: Beam-loss monitor carried as a soft constraint, and its floor in mV.
CONSTRAINT_CHANNEL = "CBLM:UNDH:1375:I1_LOSS"
CONSTRAINT_FLOOR = -30.0

#: The objective the paper reports. Three early runs used a different channel
#: and cannot share a y-axis with the rest; they are dropped from the shift view.
OBJECTIVE = "pulse_intensity_p80"


@dataclass
class Stage:
    label: str
    generator: str
    knobs: str
    values: list[float]
    loss: list[float]

    @property
    def n(self) -> int:
        return len(self.values)


def shift(archive: str | Path = ARCHIVE) -> list[BadgerRun]:
    """Every run of the shift that optimized the reported objective."""
    return [r for r in read_archive(archive) if r.objective == OBJECTIVE]


def campaign(archive: str | Path = ARCHIVE) -> list[Stage]:
    """The campaign's stages, in order."""
    archive = Path(archive)
    stages = []
    for label, filename, generator, knobs in CAMPAIGN_STAGES:
        from .badger import read_run

        run = read_run(archive / filename)
        if run is None:
            raise FileNotFoundError(f"campaign stage missing: {filename}")
        stages.append(Stage(
            label=label,
            generator=generator,
            knobs=knobs,
            values=run.values,
            loss=run.columns.get(CONSTRAINT_CHANNEL, [float("nan")] * run.n_evaluations),
        ))
    return stages


def running_best(values: list[float]) -> list[float]:
    """Best-so-far envelope for a maximization objective."""
    best, out = float("-inf"), []
    for v in values:
        best = max(best, v)
        out.append(best)
    return out


def operator_baseline(runs: list[BadgerRun], before_hour: int = 19) -> float:
    """Best value the operators reached on their own, before the agent ran."""
    early = [r for r in runs if not r.launched_by_agent and r.created.hour < before_hour]
    return max(r.best for r in early)
