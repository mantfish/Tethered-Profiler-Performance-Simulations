"""Shared job runner for the paper sweeps (scripts/run_*_sweep.py)."""
from __future__ import annotations

import argparse
import multiprocessing as mp
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.job import Job, run_job  # noqa: E402

DAT_TEMPLATE = ROOT / "data/template.dat"   # EA 1.8e5 N, CdAx 0.01, MoorDyn line output off
WAMIT_DIRS = [ROOT / "data/wamit/ArgoSubmergedBox",   # K_S
              ROOT / "data/wamit/ArgoBoxStiffness"]   # K_L
DT = 5e-4              # max solver step, every speed
SAVE_INTERVAL = 0.2    # s
START_POS = "end"      # start at the stretched tether position


def task(job: Job, wamit: Path, out: Path, dat_outdir: Path) -> tuple[Job, dict]:
    wave_tag = job.wave_path.stem if job.wave_path is not None else "None"
    # every job gets its own dat/out folder, so concurrent jobs never share MoorDyn files
    return job, dict(dat_template=DAT_TEMPLATE, dat_outdir=dat_outdir / wamit.name / wave_tag,
                     output_dir=out / wamit.name, wamit_dir=wamit)


def _run(t):
    job, paths = t
    return run_job(job, **paths, n=2, density=1025.0, clean_temp_files=True, skip_existing=True,
                   quiet_moordyn=True, steady_state_tol=1e-5, safety_factor=0.1, show_progress=False)


def main(tasks: list[tuple[Job, dict]], description: str) -> int:
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 1))
    ap.add_argument("--dry-run", action="store_true", help="list the jobs and exit")
    args = ap.parse_args()

    # longest first so long jobs don't form a tail at the end
    tasks = sorted(tasks, key=lambda t: -t[0].simulation_time)
    print(f"{len(tasks)} jobs, {args.workers} workers", flush=True)
    if args.dry_run:
        for job, paths in tasks:
            wave = job.wave_path.name if job.wave_path is not None else "None"
            print(f"{paths['wamit_dir'].name} {job.depth}m {job.current_speed}ms T{job.simulation_time:g}s {wave}")
        return 0

    ok = fail = 0
    t0 = time.time()
    with mp.get_context("spawn").Pool(args.workers) as pool:
        for i, (good, msg) in enumerate(pool.imap_unordered(_run, tasks, chunksize=1), 1):
            ok += good
            fail += not good
            print(f"[{i}/{len(tasks)} {(time.time()-t0)/3600:.2f} h] {msg}", flush=True)
    print(f"Done. OK={ok} FAIL={fail}", flush=True)
    return 0 if fail == 0 else 1
