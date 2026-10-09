"""Build the tables the figures read, from a folder of sweep pickles.

  lut     -> lookup_table.csv  (depth_m,current_ms,Hs_m,Tp_s,frac_submerged)
             copy to results/lookup_<WAMIT>.csv; read by maps/ (Figs 3, 4) and shown in Fig S2
  summary -> <depth>m_summary.csv (depth_m,current_ms,Hs_m,Tp_s,Fp_Hz,frac_submerged)
             predicted outcomes for the deployment conditions (Fig 7)

Metric: fraction of the last 60 s with (heave - eta) < -0.20 m, i.e. the top of the foam block more
than 0.20 m below the instantaneous water surface. Speeds are snapped to the sweep values, so
0.125 / 0.175 m/s are not written as 0.12 / 0.17 (the filenames use 2 decimals).

Usage (from the repo root):
  python scripts/make_tables.py lut     results/lut_sweep/ArgoSubmergedBox
  python scripts/make_tables.py summary results/validation_sweep/ArgoBoxStiffness
"""
from __future__ import annotations

import pickle
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

Z_THRESHOLD = -0.20
WINDOW = 60.0
SWEEP_SPEEDS = np.array([0.05, 0.10, 0.125, 0.15, 0.175, 0.20, 0.25, 0.30])
FNAME = re.compile(r"^(?P<d>\d+)m_(?P<cs>[\d.]+)ms_dt[^_]+_T\d+s__"
                   r"(?:None|Hs_(?P<hs>[\d.]+)m_Fp_(?P<fp>[\d.]+)Hz_eta)\.pkl$")


def frac_submerged(res: dict) -> float | None:
    t = np.asarray(res["time_hist"])
    if t[-1] <= 100:
        return None
    heave = np.asarray(res["state_hist"])[:, 2]
    waves = np.asarray(res.get("waves", np.zeros_like(t)))
    i0 = int(np.argmin(np.abs(t - (t[-1] - WINDOW))))
    return float(np.mean((heave[i0:] - waves[i0:]) < Z_THRESHOLD))


def collect(folder: Path) -> pd.DataFrame:
    rows = []
    for p in sorted(folder.glob("*.pkl")):
        m = FNAME.match(p.name)
        if not m:
            continue
        with open(p, "rb") as f:
            frac = frac_submerged(pickle.load(f))
        if frac is None:
            continue
        cs = float(m["cs"])
        cs = float(SWEEP_SPEEDS[np.argmin(np.abs(SWEEP_SPEEDS - cs))])
        hs = float(m["hs"]) if m["hs"] else 0.0
        fp = float(m["fp"]) if m["fp"] else 0.0
        rows.append(dict(depth_m=float(m["d"]), current_ms=cs, Hs_m=hs, Tp_s=1.0 / fp if fp else 0.0,
                         Fp_Hz=fp, frac_submerged=frac))
    if not rows:
        raise SystemExit(f"no pickles in {folder}")
    return pd.DataFrame(rows).sort_values(["depth_m", "current_ms", "Hs_m", "Tp_s"])


def main() -> None:
    kind, folder = sys.argv[1], Path(sys.argv[2])
    df = collect(folder)
    if kind == "lut":
        out = folder / "lookup_table.csv"
        df.drop(columns="Fp_Hz").to_csv(out, index=False)
        print(f"wrote {out} ({len(df)} rows)")
    elif kind == "summary":
        for depth, sub in df.groupby("depth_m"):
            out = folder / f"{int(depth)}m_summary.csv"
            sub.to_csv(out, index=False, float_format="%.6g")
            print(f"wrote {out} ({len(sub)} rows)")
    else:
        raise SystemExit("kind must be 'lut' or 'summary'")


if __name__ == "__main__":
    main()
