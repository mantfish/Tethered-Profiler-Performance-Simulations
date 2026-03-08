# Tethered Profiler Simulations

A Python simulation framework for modelling the dynamics of a tethered Argo float subject to ocean currents and surface waves. The code runs parameter sweeps over tether depth, current speed, and wave conditions, and computes metrics such as the fraction of time the float spends submerged.

Two pre-computed lookup tables are available in `results/` (see [Lookup Tables](#lookup-tables) below).

---

## Overview

An Argo float is a free-drifting oceanographic profiler. This repository simulates a variant where the float is tethered to the seabed, constraining its horizontal displacement while allowing it to profile vertically. The simulation couples:

- **Float hydrodynamics** — mass, added mass, hydrostatic restoring, and viscous drag, derived from WAMIT panel-code outputs.
- **Mooring line dynamics** — the tether is modelled in [MoorDyn](https://moordyn.readthedocs.io/), a lumped-mass mooring library.
- **Environmental forcing** — a linearly-sheared current profile and optional irregular surface waves described by a JONSWAP spectrum.

The equations of motion (5 DOF: surge, sway, heave, roll, pitch) are integrated in time using SciPy's adaptive RK45 solver. Each simulation run is saved as a pickle file. A parameter sweep across multiple depths, current speeds, and wave files is managed by a job-queue runner with optional multiprocessing.

---

## Repository Structure

```
.
├── main.py                   # Entry point — parses config and starts the sweep
├── config.yaml               # Sweep and runtime configuration
├── pyproject.toml            # Python project metadata and dependencies
│
├── sim/
│   ├── ArgoMover.py          # Argo float equations of motion (WAMIT-based)
│   ├── simulate.py           # Core time-integration loop (MoorDyn + scipy)
│   ├── waves.py              # JONSWAP wave generation and wave-record reader
│   └── helpers.py            # DAT file templating, linear current profile
│
├── experiments/
│   ├── config.py             # Config dataclasses and YAML loader
│   ├── job.py                # Job dataclass and single-job runner
│   └── runner.py             # Sweep builder and parallel job dispatcher
│
├── data/                     # Example input data (included in repo)
│   ├── template.dat          # MoorDyn DAT template with placeholder tokens
│   ├── Hs_3.00m_Fp_0.11Hz_eta.dat   # Example wave time-series file
│   └── wamit/
│       ├── ArgoBoxStiffness/ # WAMIT outputs — tether stiffness configuration 1
│       └── ArgoSubmergedBox/ # WAMIT outputs — tether stiffness configuration 2
│
└── results/
    ├── lookup_table_stiffness1.csv   # Lookup table — tether configuration 1
    └── lookup_table_stiffness2.csv   # Lookup table — tether configuration 2
```

---

## How It Works

### 1. Configuration (`config.yaml`)

All sweep parameters are defined in `config.yaml`:

- **`paths`** — location of the MoorDyn DAT template, generated DAT files, wave files, and output directory.
- **`system`** — tether multiplier `n`, seawater density, and one or more WAMIT data directories (one per tether stiffness configuration to sweep over).
- **`sweep`** — lists of depths (m), current speeds (m/s), and wave conditions to combine into jobs.
- **`timing`** — simulation duration, save interval, steady-state tolerance, and a speed-indexed timestep table.
- **`runner`** — number of parallel workers and whether to skip already-completed outputs.

### 2. Float Hydrodynamics (`sim/ArgoMover.py`)

`ArgoMover` reads WAMIT output files (`.out`, `.hst`, `.mmx`, `.1`, `.json`) from a results folder and constructs:

- **Mass matrix** `M` — scaled from the normalised WAMIT `.mmx` file.
- **Added mass** `M_res` — taken at the heave resonance frequency from the WAMIT `.1` file.
- **Hydrostatic restoring matrix** `C` — read from the `.hst` file and dimensionalised.
- **Viscous damping** — a fixed diagonal matrix with quadratic drag in surge/sway and linear drag in heave/roll/pitch.

Total inertia is `M_tot = M + M_res`. At each timestep the acceleration is solved from:

```
M_tot * xdd = F_hydro + F_moor
```

where `F_hydro` combines hydrostatic restoring (with optional wave excitation in heave) and viscous drag in the body-fixed frame.

### 3. Time Integration (`sim/simulate.py`)

`run_simulation` drives the coupled MoorDyn + float model:

1. A MoorDyn system is initialised from a generated `.dat` file (derived from a template by substituting depth, density, and tether length).
2. At each solver evaluation, the current velocity profile (linear shear from zero at the seabed to `current_speed` at the surface) is passed to MoorDyn via its external wave kinematics API, and MoorDyn returns the tether tension forces.
3. SciPy `solve_ivp` (RK45) integrates the 10-element state vector `[x, xd]` with an adaptive timestep bounded by the value from the config timestep table.
4. A steady-state event terminates the simulation early if both the tension change and state change fall below `steady_state_tol` after 20 s of simulated time.
5. Results (time history, state, tension, mooring node positions, optional wave elevation) are saved to a pickle file.

### 4. Wave Conditions (`sim/waves.py`)

- **`WaveGenerator`** — synthesises irregular sea-surface elevation η(t) from a JONSWAP spectrum given significant wave height `Hs` and peak frequency `Fp`, and writes the time series to CSV.
- **`WaveRecord`** — reads a pre-generated wave CSV and provides a circular lookup `height(t)` used during integration.
- **`find_wave_files`** — filters a directory of wave CSVs by `Hs` and `Fp` token lists (matched from filenames like `Hs_0.25m_Fp_0.33Hz_eta.csv`).

### 5. Sweep Runner (`experiments/runner.py`, `experiments/job.py`)

`build_jobs` constructs a flat list of `Job` objects from the Cartesian product of depths × current speeds × wave files. `run_all` dispatches these jobs, once for each WAMIT directory listed in the config, either sequentially (with a `tqdm` progress bar) or in parallel via `multiprocessing.Pool`.

Each job:
1. Generates a MoorDyn `.dat` file from the template.
2. Calls `run_simulation`.
3. Saves the result dict as a pickle file named after the run parameters.
4. Writes a timestamped `.log` file alongside the pickle.
5. Optionally cleans up the temporary `.dat` file.

---

## Lookup Tables

Two lookup tables are provided in `results/`, corresponding to two tether stiffness configurations:

| File | Configuration |
|------|--------------|
| `lookup_table_stiffness1.csv` | WAMIT model: `ArgoBoxStiffness` |
| `lookup_table_stiffness2.csv` | WAMIT model: `ArgoSubmergedBox` |

Each table has the following columns:

| Column | Description |
|--------|-------------|
| `depth_m` | Tether anchor depth (m) |
| `current_ms` | Surface current speed (m/s) |
| `Hs_m` | Significant wave height (m) |
| `Tp_s` | Peak wave period (s) |
| `frac_submerged` | Fraction of simulation time the float is submerged |

These tables can be used directly to look up expected submersion fractions for a given set of environmental conditions and tether configuration, without running new simulations.

---

## Installation

Dependencies are managed with [uv](https://github.com/astral-sh/uv) (recommended) or pip.

```bash
# With uv
uv sync

# Or with pip
pip install -e .
```

Required packages: `numpy`, `scipy`, `matplotlib`, `moordyn`, `pyyaml`, `tqdm`, `pandas`.

Python ≥ 3.12 is required.

---

## Running a Sweep

Example data is included in `data/` so the sweep can be run immediately after installation. Update `config.yaml` to point `paths.wave_dir` at your wave files if you want to use a different set, then run:

```bash
python main.py --config config.yaml
```

The default `config.yaml` already points `system.wamit_dir` at both WAMIT folders in `data/wamit/`. Increase `runner.workers` to use multiprocessing.

---

## Example Data

The `data/` directory contains the minimum inputs needed to run a simulation:

- **`data/template.dat`** — MoorDyn DAT template. The runner substitutes the tokens `DEPTH`, `DENSITY`, `LENGTH`, and `WTR_DEPTH` for each job before passing the file to MoorDyn.
- **`data/Hs_3.00m_Fp_0.11Hz_eta.dat`** — an example irregular wave time-series (Hs = 3 m, peak frequency = 0.11 Hz) generated from a JONSWAP spectrum. Additional wave files can be generated with `WaveGenerator` in `sim/waves.py` and placed in the same directory.
- **`data/wamit/ArgoBoxStiffness/`** and **`data/wamit/ArgoSubmergedBox/`** — WAMIT panel-code output folders for the two tether stiffness configurations. Each folder contains the files read by `ArgoMover`: `argo.out`, `argo.hst`, `argo.mmx`, `argo.1`, and `argo.json`, as well as the WAMIT input files (`.gdf`, `.pot`, `.frc`, etc.) used to produce them.
