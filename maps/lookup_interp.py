from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator


LOOKUP_COLS = ["depth_m", "current_ms", "Hs_m", "Tp_s"]
Y_COL = "frac_submerged"


@dataclass
class LookupInterp:
    """Linear interpolation with nearest-neighbor fallback."""
    linear: LinearNDInterpolator
    nearest: NearestNDInterpolator
    mins: np.ndarray  # shape (4,)
    maxs: np.ndarray  # shape (4,)

    def __call__(self, X: np.ndarray) -> np.ndarray:
        """
        X: (N,4) = [depth_m, current_ms, Hs_m, Tp_s]
        Returns: (N,) frac_submerged in [0,1] (clipped)
        """
        # clip to LUT bounds (prevents insane extrapolation requests)
        Xc = np.clip(X, self.mins, self.maxs)

        y = self.linear(Xc)
        # LinearNDInterpolator returns nan outside convex hull
        nan = np.isnan(y)
        if np.any(nan):
            y[nan] = self.nearest(Xc[nan])

        return np.clip(y, 0.0, 1.0)


def build_lookup_interpolator(csv_path: Path) -> LookupInterp:
    df = pd.read_csv(csv_path)

    # Ensure numeric
    for c in LOOKUP_COLS + [Y_COL]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=LOOKUP_COLS + [Y_COL])

    X = df[LOOKUP_COLS].to_numpy(float)
    y = df[Y_COL].to_numpy(float)

    mins = X.min(axis=0)
    maxs = X.max(axis=0)

    lin = LinearNDInterpolator(X, y)      # piecewise linear in 4D
    nn  = NearestNDInterpolator(X, y)     # fallback outside hull

    return LookupInterp(linear=lin, nearest=nn, mins=mins, maxs=maxs)


def classify(
    frac_a: np.ndarray,
    frac_b: np.ndarray,
    threshold: float = 0.20,
) -> np.ndarray:
    """
    Returns int codes:
      0 = success (both < threshold)
      1 = maybe   (one <, one >=)
      2 = failure (both >=)
    """
    a_fail = frac_a >= threshold
    b_fail = frac_b >= threshold

    out = np.full(frac_a.shape, 1, dtype=np.uint8)  # default maybe
    out[~a_fail & ~b_fail] = 0
    out[a_fail & b_fail] = 2
    return out


def evaluate_grid(
    depth_m: np.ndarray,
    current_ms: np.ndarray,
    hs_m: np.ndarray,
    tp_s: np.ndarray,
    lut_a: LookupInterp,
    lut_b: LookupInterp,
    threshold: float = 0.20,
    land_mask: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Inputs are 2D arrays on the same grid (ny,nx).
    Returns:
      frac_a (ny,nx), frac_b (ny,nx), class_code (ny,nx)
    """

    ny, nx = depth_m.shape
    N = ny * nx

    X = np.column_stack([
        depth_m.reshape(N),
        current_ms.reshape(N),
        hs_m.reshape(N),
        tp_s.reshape(N),
    ])

    frac_a = lut_a(X).reshape(ny, nx)
    frac_b = lut_b(X).reshape(ny, nx)

    cls = classify(frac_a, frac_b, threshold=threshold)

    # Optional mask (e.g., land) => set to NaN and code to 255
    if land_mask is not None:
        frac_a = frac_a.astype(float)
        frac_b = frac_b.astype(float)
        frac_a[land_mask] = np.nan
        frac_b[land_mask] = np.nan
        cls = cls.astype(np.uint8)
        cls[land_mask] = 255  # nodata

    return frac_a, frac_b, cls
