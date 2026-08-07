# Agentic tuning run data: LCLS and FACET-II

Raw optimizer output from two agent-orchestrated accelerator tuning campaigns
at SLAC, and the code that turns it into the figures and tables of the
accompanying paper.

- **LCLS, 26 June 2026.** An evening shift on the hard X-ray line. 30 archived
  optimization runs, 972 machine evaluations, including a two-stage campaign
  the agent planned and ran on its own.
- **FACET-II, 1–2 July 2026.** Five complete six-phase injector start-ups back
  to back, 1006 machine evaluations, at three beam charges.

Everything in `figures/` and `tables/` is generated. Nothing is hand-edited,
and every number traces back to a file under `data/`.

## Quick start

```sh
pip install -r requirements.txt

python scripts/summarize.py      # read the raw data, print the headline numbers
python scripts/plot_lcls.py      # -> figures/lcls_autotune_campaign.pdf
python scripts/plot_facet.py     # -> figures/facet_campaigns.pdf
python scripts/make_tables.py    # -> tables/*.tex
```

Run `summarize.py` first. It parses everything and prints the numbers that
appear in the paper, so you can confirm the extraction works before making
figures. `make_tables.py --check` does the same for the per-campaign detail.

## Layout

```
data/
  lcls/badger-archive/2026-06-26/   one YAML per optimization run, as Badger wrote it
  facet/campaigns/<campaign>/       one directory per campaign
    <NN>_<phase>/
      workflow.yaml                 the step the agent composed
      automatic_workflow_xopt_*.yaml  the Xopt serialization, if the step ran
      worker.log                    the runner log: timings, errors
src/agentic_runs/
  badger.py    read one Badger archive file
  lcls.py      the 26 June shift, and the campaign inside it
  facet.py     the FACET-II campaigns, phase by phase
  style.py     shared figure style
scripts/
  summarize.py    print the headline numbers
  plot_lcls.py    figure 1
  plot_facet.py   figure 2
  make_tables.py  the two tables
```

The `src/` modules do the reading and the arithmetic; the `scripts/` do the
drawing. If you want the numbers for something else, import from
`agentic_runs` and ignore the scripts entirely.

## Four things about this data that are easy to get wrong

These caught us, and the code handles them. If you write your own analysis,
handle them too.

**Row keys are strings.** Both Badger and Xopt store evaluation tables
column-wise as `{column: {row_index: value}}` with string keys, so a plain sort
gives `"1", "10", "11", "2"`. Sort numerically or the series comes out
scrambled.

**The last row is often not an evaluation.** The FACET-II emittance and
energy-spread steps re-measure the point the optimizer selected and append it
to the table. Anything computed over the search has to exclude it. The gap
between the two is the measurement repeatability, and for the emittance phase
it is large enough to matter.

**The best value is not the minimum.** The emittance phase carries a matching
constraint. Two of the lowest values of the shift violate it, so the best
result is the lowest *feasible* value, not the lowest one.

**The energy-spread start value is not the machine's state.** That routine
searches a window around the phase it finds and seeds it randomly, so its first
row is a random sample of its own search, not the setpoint it inherited. An
improvement measured against it is progress within the scan.

## How agent runs are told apart from operator runs

Badger records its own version in every archive file. The agent ran a
development build reporting `1.5.5.dev45...`; the control room's own install
reports `0.0.0`. That field is what `BadgerRun.launched_by_agent` uses, which
is more reliable than guessing from routine names or time windows.

## Provenance

The raw files were collected from the two control-room hosts, `lcls-srv01` and
`facet-srv20`, after the shifts. They are unmodified. The FACET-II campaign
directories also held quad-scan fit images and BAX posterior maps; those are
not needed by any figure here and were left out to keep the repository small.
