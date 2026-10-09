"""Lookup-table sweep (paper Figs 3, 4 and S2): both heave-stiffness cases.

Grid: depths [20, 30, 50, 75, 100] m x surface currents [0.05, 0.10, 0.125, 0.15, 0.175, 0.20, 0.30] m/s
x {no waves + the 4 sea states in data/waves/lut_sweep} x 2 WAMIT cases = 350 jobs.
T = 300 s, except 1000 s for 0.30 m/s at >= 50 m (still sinking at 300 s).

Writes results/lut_sweep/<WAMIT>/*.pkl (+ .log). Then build the tables with
  python scripts/make_tables.py lut results/lut_sweep/ArgoBoxStiffness
  python scripts/make_tables.py lut results/lut_sweep/ArgoSubmergedBox

Run from the repo root:  python scripts/run_lut_sweep.py --workers 12
"""
from __future__ import annotations

from _sweep import DT, ROOT, SAVE_INTERVAL, START_POS, WAMIT_DIRS, main, task
from experiments.job import Job
from sim.waves import list_wave_files

OUT = ROOT / "results/lut_sweep"
DAT_OUTDIR = ROOT / "data/dat_files/_generated_lut_sweep"
WAVE_DIR = ROOT / "data/waves/lut_sweep"

DEPTHS = [20, 30, 50, 75, 100]
SPEEDS = [0.05, 0.10, 0.125, 0.15, 0.175, 0.20, 0.30]


def sim_time(depth: int, cs: float) -> float:
    return 1000.0 if (cs >= 0.30 and depth >= 50) else 300.0


def build_tasks():
    waves = [None] + list_wave_files(WAVE_DIR)
    return [task(Job(depth=d, current_speed=cs, wave_path=w, dt=DT, simulation_time=sim_time(d, cs),
                     save_interval=SAVE_INTERVAL, start_pos=START_POS), wamit, OUT, DAT_OUTDIR)
            for wamit in WAMIT_DIRS for d in DEPTHS for cs in SPEEDS for w in waves]


if __name__ == "__main__":
    raise SystemExit(main(build_tasks(), __doc__))
