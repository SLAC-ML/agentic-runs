"""Read a single Badger archive file.

Badger writes one YAML per optimization run. The bits we care about are the
routine's identity, the generator it used, and the evaluation table, which is
stored column-wise as {column_name: {row_index: value}} with STRING row keys.
Those keys sort lexicographically ("10" < "2"), so they always have to be
sorted numerically before use.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import yaml

#: Objective channels seen on the LCLS hard X-ray line, best first.
OBJECTIVE_PREFERENCE = ("pulse_intensity_p80", "pulse_intensity_mean")

#: Badger reports its own version. The agent ran a development build; the
#: control room's own install reports 0.0.0. That is how we tell the two apart.
AGENT_BADGER_PREFIX = "1.5.5"


@dataclass
class BadgerRun:
    """One archived optimization run."""

    path: Path
    name: str
    created: dt.datetime
    generator: str
    badger_version: str
    xopt_version: str
    objective: str
    values: list[float]
    columns: dict[str, list[float]] = field(repr=False, default_factory=dict)

    @property
    def launched_by_agent(self) -> bool:
        return str(self.badger_version).startswith(AGENT_BADGER_PREFIX)

    @property
    def n_evaluations(self) -> int:
        return len(self.values)

    @property
    def best(self) -> float:
        return max(self.values)

    @property
    def variables(self) -> list[str]:
        return [c for c in self.columns if ":" in c and not c.startswith("CBLM")]


def _column(table: dict, name: str) -> list[float]:
    """Pull one column out of Badger's column-wise table, in evaluation order."""
    col = table[name]
    return [col[k] for k in sorted(col, key=int)]


def read_run(path: str | Path) -> BadgerRun | None:
    """Read one archive file. Returns None if it holds no recognised objective."""
    path = Path(path)
    doc = yaml.safe_load(path.read_text())
    table = doc.get("data") or {}

    objective = next((o for o in OBJECTIVE_PREFERENCE if o in table), None)
    if objective is None:
        return None

    columns = {name: _column(table, name) for name in table}
    return BadgerRun(
        path=path,
        name=doc.get("name", path.stem),
        created=dt.datetime.strptime(doc["creation_ts"], "%Y-%m-%d-%H%M%S"),
        generator=(doc.get("generator") or {}).get("name", "unknown"),
        badger_version=str(doc.get("badger_version", "")),
        xopt_version=str(doc.get("xopt_version", "")),
        objective=objective,
        values=columns[objective],
        columns=columns,
    )


def read_archive(directory: str | Path) -> list[BadgerRun]:
    """Read every run in one archive day, ordered by creation time."""
    runs = [read_run(p) for p in sorted(Path(directory).glob("*.yaml"))]
    return sorted((r for r in runs if r), key=lambda r: r.created)
