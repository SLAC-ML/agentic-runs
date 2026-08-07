# Agentic tuning run data: LCLS and FACET-II

Raw optimizer output from two agent-orchestrated accelerator tuning campaigns
at SLAC, and the code that turns it into the figures and tables of the
accompanying paper.

- **LCLS, 26 June 2026.** An evening shift on the hard X-ray line. 30 archived
  optimization runs, 972 machine evaluations, including the two-stage campaign
  the agent planned and ran on its own, which is what the figure shows.
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

`plot_facet.py` takes about twenty seconds: it bootstraps the emittance
uncertainty from the raw quadrupole scans rather than reading a cached number.
See "Error bars" below.

## Layout

```
data/
  lcls/badger-archive/2026-06-26/   one YAML per optimization run, as Badger wrote it
  facet/campaigns/<campaign>/       one directory per campaign
    <NN>_<phase>/
      workflow.yaml                 the step the agent composed
      automatic_workflow_xopt_*.yaml  the Xopt serialization, if the step ran
      worker.log                    the runner log: timings, errors
  facet/emittance-scans/<campaign>/  the quadrupole scan behind each emittance
      emittance_scan_<stamp>.h5      evaluation, named in the dump's save_filename
src/agentic_runs/
  badger.py    read one Badger archive file
  lcls.py      the 26 June shift, and the campaign inside it
  facet.py     the FACET-II campaigns, phase by phase
  emitscan.py  the quadrupole scans, refitted, and how uncertain they are
  style.py     shared figure style
scripts/
  summarize.py    print the headline numbers
  plot_lcls.py    figure 1
  plot_facet.py   figure 2
  make_tables.py  the two tables
  collect_emittance_scans.sh   how the scan files got here; SLAC-only, not
                               needed to use the data
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

## Error bars

The optimizer dumps record a fitted emittance and nothing about how well it was
determined. The scan behind each one is in `data/facet/emittance-scans/`, so
the uncertainty is recovered from the raw measurement.

`emitscan.py` refits the beam matrix the way the control room did, then runs a
residual bootstrap: hold the quadrupole settings fixed, resample the fit
residuals onto the fitted curve, refit, and take the spread. That is the error
bar in figure 2b, and it is per point rather than uniform.

Two things are worth knowing before reusing this.

**The fit is not least squares.** Following lcls-tools `compute_emit_bmag`, it
minimizes the sum of absolute residuals in beam *size*, over a parameterization
(`sig11 = l1^2`, `sig12 = l1*l2*c`, `sig22 = l2^2`, `|c| < 1`) that cannot
return an unphysical beam matrix. `emitscan.verify()` checks the
reimplementation against the fit stored in each file: 91 of 102 agree to seven
digits. The rest are cases where the loss surface is flat enough that two
descents end up in different places, which is itself a sign the measurement is
weak. The single descent is deliberate; restarting from perturbed guesses finds
lower-loss solutions, but that would no longer be the estimator that produced
the published numbers.

**Bootstrapping the points would be wrong.** A point bootstrap drops about a
third of the distinct scan steps, and those steps are not a random sample: the
optimizer placed them, several near the waist where the fit gets its leverage.
Dropping them models a scan that was never run, and roughly doubles the
apparent uncertainty.

The result: about 3% on a scan that brought the beam cleanly through a waist,
and 40% or worse on one that did not. The wide bars in the 2000 and 2200 pC
campaigns are real. On those scans the horizontal spot size varies by as little
as 10% across the whole quadrupole range, the residuals stay at 2%, and the
emittance is simply not pinned down by the data.

The energy-spread phase saved no equivalent raw data, so figure 2c falls back
on `facet.repeatability()`: the RMS difference between the selected best point
and its re-evaluation, 1.7 um from five samples. That estimate is not directly
comparable to a fit uncertainty, since it also contains whatever the machine did
between the two measurements. For emittance the same measure gives 1.0 um,
larger than the typical fit error, which is the expected ordering.

## How agent runs are told apart from operator runs

Badger records its own version in every archive file. The agent ran a
development build reporting `1.5.5.dev45...`; the control room's own install
reports `0.0.0`. That field is what `BadgerRun.launched_by_agent` uses, which
is more reliable than guessing from routine names or time windows.

## Provenance

The raw files were collected from the two control-room hosts, `lcls-srv01` and
`facet-srv20`, after the shifts. The optimizer dumps and runner logs are
unmodified. The FACET-II campaign directories also held BAX posterior maps;
those are not needed by any figure here and were left out to keep the
repository small.

The emittance scans are the one exception to "unmodified". On the control-room
host they are 35 GB, because every scan point stores a full 1038x1388 camera
frame and its background. The copies here have the pixel arrays removed, along
with the camera and image-processor configuration that was re-serialized
identically at every scan point. What is kept is everything the emittance fit
reads and everything needed to reproduce it: the measured RMS spot sizes and
their signal-to-noise ratios, the quadrupole focusing strengths and setpoints,
the transport matrix, the beam energy, the fitted beam matrix and emittance,
and the optimizer's own evaluation table. That is 14 MB. Each file records what
was dropped in its root attributes, and `original_path` points at the source.

Anyone who needs the images has to go back to `facet-srv20`.
