"""Quadrupole-scan emittance measurements, and how uncertain they are.

Every evaluation of the FACET-II emittance phase is a quadrupole scan: QE04 is
stepped, the beam is imaged on a downstream screen at each step, and a beam
matrix is fitted to the resulting spot sizes. The optimizer records only the
fitted emittance. The scan behind it is in data/facet/emittance-scans/, one
file per evaluation, named in the dump's `save_filename` column.

The measurement carries no stated error, so this module estimates one. It
refits the beam matrix the same way the control-room code did, then bootstraps
over the scan points: resample the steps with replacement, refit, and take the
spread of the resulting emittances. That spread is what the figure's error bars
show.

The fit follows lcls-tools `compute_emit_bmag`. It is not a least-squares fit
of sigma^2. It minimizes the sum of absolute residuals in beam *size*, over a
parameterization that cannot produce an unphysical beam matrix:

    sig11 = l1^2,  sig12 = l1*l2*c,  sig22 = l2^2,  with |c| < 1

Reproducing it rather than importing lcls-tools keeps this repository free of
the control-system stack. `verify()` checks the reimplementation against the
fits stored in the files themselves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np
from scipy.optimize import minimize

SCANS_DIR = Path("data/facet/emittance-scans")

#: Guards the square roots and keeps the correlation strictly inside (-1, 1),
#: matching lcls-tools.
EPS = 1.0e-6

#: Electron rest mass, in eV, as lcls-tools rounds it when normalizing. Using
#: the exact value, or beta*gamma instead of gamma, disagrees with the published
#: numbers in the sixth digit. Kept here so the arithmetic matches the dumps.
ELECTRON_MASS_EV = 511000.0

X, Y = 0, 1


def quad_rmat(k: float, length: float) -> np.ndarray:
    """Thick-quadrupole transfer matrix in the plane where `k` is signed."""
    if abs(k) < 1e-12:
        return np.array([[1.0, length], [0.0, 1.0]])
    w = math.sqrt(abs(k))
    if k > 0:                                   # focusing
        return np.array([[math.cos(w * length), math.sin(w * length) / w],
                         [-w * math.sin(w * length), math.cos(w * length)]])
    return np.array([[math.cosh(w * length), math.sinh(w * length) / w],
                     [w * math.sinh(w * length), math.cosh(w * length)]])


def _beam_matrix(params: np.ndarray) -> np.ndarray:
    """(l1, l2, c) -> (sig11, sig12, sig22)."""
    return np.array([params[0] ** 2, params[0] * params[1] * params[2], params[1] ** 2])


def _d_beam_matrix(params: np.ndarray) -> np.ndarray:
    """Jacobian of the above, d(sig)/d(params)."""
    l1, l2, c = params
    return np.array([[2 * l1, l2 * c, 0.0],
                     [0.0, l1 * c, 2 * l2],
                     [0.0, l1 * l2, 0.0]])


def fit_beam_matrix(amat: np.ndarray, sizes_sq: np.ndarray) -> np.ndarray:
    """Fit (sig11, sig12, sig22) to squared spot sizes. Units are the caller's."""
    measured = np.sqrt(sizes_sq)

    def loss(params):
        return np.nansum(np.abs(np.sqrt(amat @ _beam_matrix(params)) - measured))

    def jac(params):
        modelled = np.sqrt(amat @ _beam_matrix(params))
        with np.errstate(invalid="ignore", divide="ignore"):
            weights = np.sign(modelled - measured) / (2.0 * modelled)
        return _d_beam_matrix(params) @ (amat.T @ np.nan_to_num(weights))

    # Pseudo-inverse of the linear problem, which ignores positive-definiteness,
    # is a good enough starting point to project onto the parameterization.
    guess = np.linalg.pinv(amat) @ sizes_sq
    l1 = math.sqrt(max(guess[0], EPS))
    l2 = math.sqrt(max(guess[2], EPS))
    c = float(np.clip(guess[1] / (l1 * l2), -1 + EPS, 1 - EPS))
    bounds = [(None, None), (None, None), (-1 + EPS, 1 - EPS)]

    # One descent from one starting point, which is what the control room ran.
    # Restarting from perturbed guesses does find lower-loss solutions on some
    # scans, but that would be a different estimator than the one that produced
    # the published numbers, so it is deliberately not done here. That such
    # solutions exist at all is a symptom of how flat this optimum is, and it is
    # the bootstrap below, not a better optimizer, that reports the consequence.
    result = minimize(loss, np.array([l1, l2, c]), jac=jac, bounds=bounds)
    return _beam_matrix(result.x)


def emittance_of(beam_matrix: np.ndarray) -> float:
    """Geometric emittance from (sig11, sig12, sig22)."""
    determinant = beam_matrix[0] * beam_matrix[2] - beam_matrix[1] ** 2
    return math.sqrt(determinant) if determinant > 0 else float("nan")


@dataclass
class Scan:
    """One quadrupole scan: the two planes are fitted independently."""

    path: Path
    #: Focusing strengths actually used by each plane's fit, in 1/m^2.
    k: tuple[np.ndarray, np.ndarray]
    #: Measured RMS spot sizes, in mm, one array per plane.
    sizes: tuple[np.ndarray, np.ndarray]
    #: Transport from the quadrupole exit to the screen, per plane.
    drift: np.ndarray
    quad_length: float
    energy_ev: float
    #: The geometric emittance the control room fitted and recorded.
    stored: tuple[float, float]

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def campaign(self) -> str:
        return self.path.parent.name

    def amat(self, plane: int) -> np.ndarray:
        """Rows of (r11^2, 2 r11 r12, r12^2), one per scan point."""
        rmats = [self.drift[plane] @ quad_rmat(k, self.quad_length) for k in self.k[plane]]
        r11 = np.array([r[0, 0] for r in rmats])
        r12 = np.array([r[0, 1] for r in rmats])
        return np.stack([r11 ** 2, 2.0 * r11 * r12, r12 ** 2], axis=1)

    def emittance(self, plane: int) -> float:
        """Refit this plane from scratch."""
        return emittance_of(fit_beam_matrix(self.amat(plane), self.sizes[plane] ** 2))

    def normalized(self, plane: int) -> float:
        """The stored emittance in normalized units, in micrometres.

        This is the `emittance_x` / `emittance_y` the optimizer recorded, and
        reproduces it to nine digits.
        """
        return self.stored[plane] * self.energy_ev / ELECTRON_MASS_EV


def read_scan(path: str | Path) -> Scan:
    """Read one scan file."""
    path = Path(path)
    with h5py.File(path, "r") as f:
        meta = f["metadata"]
        return Scan(
            path=path,
            k=tuple(np.array(f["quadrupole_focusing_strengths"][str(p)]) for p in (X, Y)),
            # Stored in metres; the fit works in mm and mrad, which makes the
            # emittance come out in mm-mrad, that is, micrometres.
            sizes=tuple(np.array(f["rms_beamsizes"][str(p)]) * 1e3 for p in (X, Y)),
            drift=np.array(meta["rmat"]),
            quad_length=float(meta["magnet"]["metadata"]["l_eff"][()]),
            energy_ev=float(meta["energy"][()]),
            stored=tuple(np.array(f["emittance"]).ravel().tolist()),
        )


def read_all(root: str | Path = SCANS_DIR) -> list[Scan]:
    """Every scan on disk, campaign by campaign."""
    return [read_scan(p) for p in sorted(Path(root).glob("*/emittance_scan_*.h5"))]


def plane_uncertainty(scan: Scan, plane: int, n_resamples: int = 120,
                      seed: int = 0) -> float:
    """Fractional 1-sigma uncertainty on one plane's emittance.

    Residual bootstrap: hold the quadrupole settings fixed, resample the fit
    residuals and add them back to the fitted curve, refit, and take the spread
    of the refits.

    Resampling the scan *points* instead would be wrong here. A bootstrap
    sample omits about a third of the distinct points, and these points are not
    a random sample: the optimizer placed them, several of them near the waist
    where the fit gets its leverage. Dropping those does not represent
    measurement noise, it represents a scan that was never run, and it inflates
    the spread by roughly a factor of two.
    """
    rng = np.random.default_rng(seed)
    amat, measured = scan.amat(plane), scan.sizes[plane]
    fitted = np.sqrt(amat @ fit_beam_matrix(amat, measured ** 2))
    residuals = measured - fitted
    residuals = residuals - residuals.mean()

    draws = []
    for _ in range(n_resamples):
        resampled = fitted + rng.choice(residuals, size=len(residuals), replace=True)
        value = emittance_of(fit_beam_matrix(amat, np.clip(resampled, 1e-9, None) ** 2))
        if np.isfinite(value):
            draws.append(value)
    if len(draws) < 2:
        return float("nan")
    draws = np.array(draws)
    return float(np.std(draws, ddof=1) / np.mean(draws))


def relative_uncertainty(scan: Scan, n_resamples: int = 120,
                         seed: int = 0) -> tuple[float, float, float]:
    """Fractional 1-sigma uncertainty on (eps_x, eps_y, sqrt(eps_x eps_y)).

    Returned as a fraction, so a caller can apply it to whichever emittance it
    publishes, geometric or normalized, without having to agree on the
    normalization.

    The last entry propagates the two planes into the geometric mean the
    optimizer minimized, treating them as independent. They share the same
    images, so that is an approximation, but the two fits use different subsets
    of the scan and different transfer matrices.
    """
    x = plane_uncertainty(scan, X, n_resamples, seed)
    y = plane_uncertainty(scan, Y, n_resamples, seed + 1)
    return x, y, 0.5 * math.hypot(x, y)


def uncertainty_for(campaign: str, scan_names, n_resamples: int = 120,
                    root: str | Path = SCANS_DIR) -> list[float]:
    """Fractional uncertainty on the mean emittance of each named scan.

    Takes the campaign directory name and the `save_filename` entries the
    optimizer recorded, so the caller does not have to know the layout on disk.
    A scan with no file on disk comes back as nan and should be drawn without a
    bar rather than with a bar of zero length.
    """
    out = []
    for name in scan_names:
        path = Path(root) / campaign / Path(name).name
        out.append(relative_uncertainty(read_scan(path), n_resamples)[2]
                   if path.exists() else float("nan"))
    return out


def verify(scans: list[Scan] | None = None, tolerance: float = 1e-4) -> dict:
    """Check the refit against the fit each file already carries.

    A mismatch means the reimplementation has drifted from the control-room
    code, and any uncertainty derived from it is not trustworthy.
    """
    scans = read_all() if scans is None else scans
    errors = []
    for scan in scans:
        for plane in (X, Y):
            stored = scan.stored[plane]
            errors.append(abs(scan.emittance(plane) - stored) / stored)
    errors = np.array(errors)
    return dict(n=len(errors), median=float(np.median(errors)),
                worst=float(errors.max()), agreeing=int((errors < tolerance).sum()))
