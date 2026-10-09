"""15 / 25 m validation sweep (paper Fig 7): conditions of the Sound and Lillebaelt deployments.

Grid: depths [15, 25] m x surface currents [0.05, 0.10, 0.15, 0.20, 0.25, 0.30] m/s
x {no waves + Hs [0.25, 0.5, 0.75, 1.0] m x Tp [1.0, 1.49, 2.0, 2.5, 3.03] s} x 2 WAMIT cases = 504 jobs.
T = 300 s. Wave inputs are in data/waves/validation_sweep.

Writes results/validation_sweep/<WAMIT>/*.pkl (+ .log). Then build the per-depth tables with
  python scripts/make_tables.py summary results/validation_sweep/ArgoBoxStiffness
  python scripts/make_tables.py summary results/validation_sweep/ArgoSubmergedBox

Run from the repo root:  python scripts/run_validation_sweep.py --workers 12
"""
from __future__ import annotations

from _sweep import DT, ROOT, SAVE_INTERVAL, START_POS, WAMIT_DIRS, main, task
from experiments.job import Job

OUT = ROOT / "results/validation_sweep"
DAT_OUTDIR = ROOT / "data/dat_files/_generated_validation_sweep"
WAVE_DIR = ROOT / "data/waves/validation_sweep"

DEPTHS = [15, 25]
SPEEDS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
HS = ["0.25", "0.50", "0.75", "1.00"]
FP = ["1.00", "0.67", "0.50", "0.40", "0.33"]  # Tp 1.0, 1.49, 2.0, 2.5, 3.03 s
SIM_TIME = 300.0


def build_tasks():
    waves = [None] + [WAVE_DIR / f"Hs_{h}m_Fp_{f}Hz_eta.dat" for h in HS for f in FP]
    missing = [w for w in waves if w is not None and not w.exists()]
    if missing:
        raise SystemExit(f"missing wave files: {missing}")
    return [task(Job(depth=d, current_speed=cs, wave_path=w, dt=DT, simulation_time=SIM_TIME,
                     save_interval=SAVE_INTERVAL, start_pos=START_POS), wamit, OUT, DAT_OUTDIR)
            for wamit in WAMIT_DIRS for d in DEPTHS for cs in SPEEDS for w in waves]


if __name__ == "__main__":
    raise SystemExit(main(build_tasks(), __doc__))
