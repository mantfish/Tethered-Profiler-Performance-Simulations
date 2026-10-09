# Tethered Profiler Simulations

<!-- Replace XXXXXXX with the Zenodo DOI after the first release is archived -->
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXXXX)

Code, model inputs and lookup tables for

> O'Brien-Møller, D., Toftegård, B., Bingham, H., Galeazzi, R., Stedmon, C., Mariani, P.
> *Feasibility of Tethered Profiling Floats for Coastal Observations.* (submitted)

The repository simulates a profiling float (NKE ARVOR) tethered to a seabed anchor in steady current and
irregular waves, and estimates how often the float can surface far enough to transmit data. It contains what is
needed to reproduce the simulation results of the paper:

| Paper item | Produced by | Inputs |
|---|---|---|
| Table 2 (model parameters) | `data/template.dat`, `data/wamit/`, `sim/` | — |
| Lookup tables (Fig S2) | `scripts/run_lut_sweep.py` → `scripts/make_tables.py lut` | `data/waves/lut_sweep/` → `results/lookup_*.csv` |
| Figs 3 and 4 (annual and hourly surfacing maps) | `maps/main.py` → `maps/plotter.py` | `results/lookup_*.csv` + Copernicus Marine and EMODnet data ([download](#external-data-not-included)) |
| Fig 7 (predicted outcome of the deployment transmissions) | `scripts/run_validation_sweep.py` → `scripts/make_tables.py summary` | `data/waves/validation_sweep/` |
| Figs 6 and 8 (deployment time series, tether sensor depths) | — (measured data) | `data/deployments/` |
| Fig S1, Table S2 (ADCP current profiles) | — (measured data) | `data/adcp/` |

The measured data from the two deployments and the ADCP are in [`data/deployments/` and `data/adcp/`](#measured-data).

---

## Model

The float is a 5-DOF rigid body (surge, sway, heave, roll, pitch; yaw neglected) whose mass, added mass and
hydrostatic restoring come from WAMIT. The tether is a lumped-mass line in [MoorDyn](https://moordyn.readthedocs.io/).
At each solver step MoorDyn returns the tether force on the float, and

```
(M + A) ẍ = F_restoring(+ wave) + F_drag + F_tether
```

is integrated with SciPy RK45 (`sim/simulate.py`). The current is linear in depth, zero at the seabed and
`current_speed` at the surface, and is passed to MoorDyn through its external-kinematics interface, so it loads both
the tether and the float. Waves enter as a JONSWAP surface-elevation time series η(t) that shifts the hydrostatic
restoring force in heave (`sim/waves.py`).

Where the parameters of paper Table 2 live:

| Parameter | Value in this repo | Where |
|---|---|---|
| Mass, added mass (at the heave resonance), hydrostatic restoring | case K_L: heave stiffness ≈ 640 N/m; case K_S: ≈ 13 N/m | `data/wamit/ArgoBoxStiffness/` (K_L) and `data/wamit/ArgoSubmergedBox/` (K_S), read by `sim/ArgoMover.py` |
| Float damping | diag [82.5, 82.5, 3.0, 4.4, 4.4]; quadratic in surge/sway, linear in heave/roll/pitch | `sim/ArgoMover.py::estimated_viscous_damping`, applied in `sim/simulate.py::_hydro_forces` |
| Maximum restoring force (fully inflated bladder) | 3.8 N in heave | clip in `sim/simulate.py::_hydro_forces` |
| Tether diameter, mass per metre | 4 mm, 0.013 kg/m | `data/template.dat`, line type `neutral4mm` |
| Tether axial stiffness EA | 1.8 × 10⁵ N | `data/template.dat` |
| Tether normal drag Cd / added mass Ca / axial drag CdAx | 1.2 / 1.0 / 0.01 | `data/template.dat` |
| Tether length | 2 × water depth | `n: 2` in `config.yaml`, `n=2` in `scripts/_sweep.py` |
| Water density | 1025 kg/m³ | same |
| Transmission failure | foam top > 0.20 m below the surface for > 20 % of the window | `scripts/make_tables.py` (0.20 m), `maps/main.py` (`THRESHOLD = 0.20`) |

---

## Repository layout

```
.
├── main.py, config.yaml        # generic sweep runner + quick-start example config
├── sim/                        # physics
│   ├── ArgoMover.py            #   float model from WAMIT output
│   ├── simulate.py             #   MoorDyn coupling and time integration
│   ├── waves.py                #   JONSWAP wave generation, wave-record reader
│   └── helpers.py              #   .dat templating, linear current profile
├── experiments/                # config loader, job builder, single-job runner
├── scripts/                    # the exact sweeps of the paper
│   ├── run_lut_sweep.py        #   lookup-table sweep (350 runs)
│   ├── run_validation_sweep.py #   15 / 25 m deployment-conditions sweep (504 runs)
│   ├── _sweep.py               #   settings shared by both sweeps
│   └── make_tables.py          #   run outputs -> lookup table / per-depth summary CSVs
├── maps/                       # annual surfacing maps (Figs 3, 4)
├── data/                       # model inputs and measured data (below)
└── results/                    # lookup tables used in the paper (below)
```

---

## Data files

### `data/`

| Path | Contents |
|---|---|
| `template.dat` | MoorDyn input template for the tether. `DEPTH`, `WTR_DEPTH`, `LENGTH` and `DENSITY` are filled in per run by `sim/helpers.py::edit_dat_file`. One 4 mm Dyneema line (`neutral4mm`: EA 1.8e5 N, Cd 1.2, Ca 1.0, CdAx 0.01, 15 segments) from a fixed anchor to a coupled body (the float). MoorDyn file output is off. |
| `wamit/ArgoBoxStiffness/` | WAMIT run for the **large heave stiffness case K_L** (waterline through the foam block). `ArgoMover` reads `argo.out` (header, geometry), `argo.hst` (hydrostatic restoring), `argo.mmx` (mass matrix), `argo.1` (added mass and damping vs frequency) and `argo.json` (physical constants). The other files are the WAMIT inputs (`.gdf` geometry, `.pot`, `.frc`, `.cfg`, `config.wam`, `fnames.wam`), WAMIT logs, and the MATLAB / Mathematica scripts used to build the geometry. |
| `wamit/ArgoSubmergedBox/` | The same for the **small heave stiffness case K_S** (waterline above the foam block, on the antenna and sensors). |
| `waves/lut_sweep/Hs_<Hs>m_Fp_<Fp>Hz_eta.csv` | The four sea states of the lookup-table sweep, equidistant on the first principal component of the observed (Tp, Hs) distribution (paper Fig 2d): Hs / Tp = 0.49 m / 3.05 s, 0.97 m / 4.87 s, 1.46 m / 6.68 s, 1.94 m / 8.50 s. Columns `t_s, eta_m`, dt = 0.01 s. |
| `waves/validation_sweep/Hs_<Hs>m_Fp_<Fp>Hz_eta.dat` | The 20 sea states of the validation sweep: Hs ∈ {0.25, 0.5, 0.75, 1.0} m × Fp ∈ {1.00, 0.67, 0.50, 0.40, 0.33} Hz (Tp 1.0, 1.49, 2.0, 2.5, 3.03 s). Plain-text η series with a short header (`0 0.01 1` = start time, dt, ...). |

All wave files are surface-elevation records synthesised from a one-sided JONSWAP spectrum normalised to Hs²/16
with random phases (`sim/waves.py::WaveGenerator`). A run reads them with `WaveRecord`, looping the record if the
run is longer.

### Measured data

Instrument exports as recorded, except where noted below. Positions and dates are in paper Table 1 and the
Deployments section.

| Path | Contents |
|---|---|
| `deployments/sound/argo.txt` | Sound deployment (55.74° N, 12.67° E, 14 m, 7–14 March 2025): profiling-float CTD export, `;`-separated. Columns `N, cycle, phase, day, hh:mm:ss, Pressure, Temperature, Salinity, C1Ph, C2Ph, Tempe_opt, decim flag`, as integer instrument counts (C1Ph / C2Ph are the oxygen optode phases); profiling cycles 2–24, `day` counted from deployment. |
| `deployments/sound/{A,B,C}.CSV` | Sound deployment: the three micro-CTDs (Star-Oddi DST CTD) on the tether, 2 min interval. Distance from the anchor: C 4.0 m, B 11.4 m, A 18.8 m. `;`-separated: `Number; Date-Time (dd.mm.yyyy hh:mm:ss); Temp (°C); Depth (m); Salinity (psu); Conduct (mS/cm); Velocity (m/s, sound speed)`. |
| `deployments/lillebaelt/argo.csv` | Lillebælt deployment (55.20° N, 9.75° E, 26 m): processed float profiles of deployment 4 (9 April – 2 June 2025) and deployment 5 (3 June – 19 July 2025). Columns `Deployment_no, Profile, Profile_no, Datetime_org, Datetime, Stage, PRES (dbar), TEMP (°C), PSAL, rho (kg/m³), DO_mgL, DO_umolKg, AOU, pO2`. `Datetime_org` is the time stamp sent by the float (`NaT` where it was filled in), `Stage` is the float's phase code. |
| `deployments/lillebaelt/float_profiles.csv` | Lillebælt deployment: the same processed float profiles over the whole deployment, deployment 4 (9 April – 2 June 2025) and deployment 5 (3 June 2025 – retrieval on 17 February 2026). Same columns as `argo.csv`, plus `Depth` (m) and `DO_sat` (%). |
| `deployments/lillebaelt/{A,B,C}.CSV` | Lillebælt deployment: tether micro-CTDs, 3 min interval, 9 April – 10 June 2025. Distance from the anchor: C 12.5 m, B 25.0 m, A 37.5 m. Same format as for the Sound; `A.CSV` is Latin-1 encoded, the others UTF-8. |
| `adcp/lillebaelt_adcp.csv` | Nortek Eco ADCP export, Lillebælt test site (55.2010° N, 9.7521° E, instrument depth 23 m), 13 April – 23 June 2026, 5 min interval. Header lines start with `%` (30 lines; the Nortek account `Data ID` and `User ID` values have been removed); then local time (UTC+2), speed (m/s) and direction (°) in the upper (10.2 m), middle (14.5 m) and lower (18.8 m) layers, temperature, depth, tilt and a flag. |

The Copernicus Marine conditions and wind for each transmission (Fig 7, Fig S3) are not included; the products are
listed under [External data](#external-data-not-included) and wind came from the Open-Meteo Weather API.

### `results/`

| Path | Contents |
|---|---|
| `lookup_ArgoBoxStiffness.csv` | Lookup table for case K_L (175 rows). |
| `lookup_ArgoSubmergedBox.csv` | Lookup table for case K_S (175 rows). |

| Column | Meaning |
|---|---|
| `depth_m` | Water depth (m): 20, 30, 50, 75, 100. Tether length is twice this. |
| `current_ms` | Surface current speed (m/s): 0.05, 0.10, 0.125, 0.15, 0.175, 0.20, 0.30. Linear profile to zero at the seabed. |
| `Hs_m`, `Tp_s` | Significant wave height and peak period; `0, 0` means no waves. |
| `frac_submerged` | Fraction of the last 60 s of the run in which the top of the foam block is more than 0.20 m below the instantaneous water surface (heave − η < −0.20 m). |

Runs last 300 s (1000 s for 0.30 m/s at ≥ 50 m, which were still sinking at 300 s), start with the tether stretched,
use a maximum solver step of 5 × 10⁻⁴ s and save every 0.2 s. The raw run outputs (one `.pkl` per run, ~300 MB in
total) are not included; `scripts/run_lut_sweep.py` regenerates them.

The maps interpolate the tables linearly in 4-D (depth, current, Hs, Tp), with nearest-neighbour fallback outside
the convex hull and inputs clipped to the table range (`maps/lookup_interp.py`). Each hour and grid cell scores 1 if
both cases have `frac_submerged` < 0.20, 0.5 if only one does (marginal), and 0 otherwise
(`maps/data_processor.py::_classify_to_score`). The annual map shows the mean score in percent.

---

## External data (not included)

### Copernicus Marine Service

The maps use hourly surface currents (`uo`, `vo`, top model level) and wave parameters (`VHM0` = Hs,
`VTPK` = Tp) for **2024-01-01 → 2025-01-08** over **6–15.5° E, 54–58.8° N**. `maps/main.py` downloads them
itself, one day at a time, and deletes each day after processing.

| Used for | Product | Dataset ID in `maps/main.py` | Variables | DOI |
|---|---|---|---|---|
| Baltic currents (Figs 3, 4) | Baltic Sea Physics Analysis and Forecast (`BALTICSEA_ANALYSISFORECAST_PHY_003_006`) | `cmems_mod_bal_phy_anfc_PT1H-i` | uo, vo | [10.48670/moi-00010](https://doi.org/10.48670/moi-00010) |
| Baltic waves (Figs 3, 4) | Baltic Sea Wave Hindcast (`BALTICSEA_MULTIYEAR_WAV_003_015`) | `cmems_mod_bal_wav_my_PT1H-i` | VHM0, VTPK | [10.48670/moi-00014](https://doi.org/10.48670/moi-00014) |
| North Sea currents (NWS map, not shown in the paper) | Atlantic – European North West Shelf – Ocean Physics Reanalysis (`NWSHELF_MULTIYEAR_PHY_004_009`) | `cmems_mod_nws_phy-uv_my_7km-2D_PT1H-i` | uo, vo | [10.48670/moi-00059](https://doi.org/10.48670/moi-00059) |
| North Sea waves (NWS map) | Atlantic – European North West Shelf – Wave Physics Reanalysis (`NWSHELF_REANALYSIS_WAV_004_015`) | `MetO-NWS-WAV-RAN` | VHM0, VTPK | [10.48670/moi-00060](https://doi.org/10.48670/moi-00060) |

The other products in paper Table S1 were used for the environmental statistics of Fig 2 and for the conditions
during the deployments (Fig 7), not by code in this repository: Baltic Sea Physics Reanalysis
([moi-00013](https://doi.org/10.48670/moi-00013)), Baltic Sea Wave Analysis and Forecast
([moi-00011](https://doi.org/10.48670/moi-00011)), Baltic Sea In Situ Near Real Time Observations
([moi-00032](https://doi.org/10.48670/moi-00032)) and Atlantic – European North West Shelf – Ocean Physics Analysis
and Forecast ([moi-00054](https://doi.org/10.48670/moi-00054)).

To download:

1. Create a free account at <https://data.marine.copernicus.eu/register>.
2. Install the map dependencies and log in once (this stores credentials in `~/.copernicusmarine/`):
   ```bash
   uv sync --extra maps
   uv run copernicusmarine login
   ```
3. Run `maps/main.py` (step 4 of [Reproducing the results](#reproducing-the-results)), which calls
   `copernicusmarine.subset` for each dataset and day. To download a dataset by hand instead, e.g. one day of
   Baltic currents:
   ```bash
   uv run copernicusmarine subset --dataset-id cmems_mod_bal_phy_anfc_PT1H-i \
     --variable uo --variable vo \
     --minimum-longitude 6 --maximum-longitude 15.5 --minimum-latitude 54 --maximum-latitude 58.8 \
     --start-datetime 2024-01-01T00:00:00 --end-datetime 2024-01-02T00:00:00 \
     --output-directory maps/cmems_tmp
   ```

This study has been conducted using E.U. Copernicus Marine Service Information.

### EMODnet bathymetry

Water depth per grid cell comes from the EMODnet Digital Terrain Model tiles **D5** (North Sea, Skagerrak) and
**D6** (western Baltic) in NetCDF format. Download them from the EMODnet portal
(<https://emodnet.ec.europa.eu/geoviewer/>, Bathymetry → download DTM tiles) and save them as

```
maps/data/bathymetry/D5_2022.nc    # tile D5 (2022 release was used)
maps/data/bathymetry/D6_2024.nc    # tile D6, DTM 2024, doi:10.12770/cf51df64-56f9-4a99-b1aa-36b8d7b743a1
```

or change `BATHY_NWS` / `BATHY_BAL` in `maps/main.py`. The Baltic grid uses D6 and fills gaps from D5.

---

## Installation

Python 3.12 or 3.13 (MoorDyn has no wheels for 3.14 yet). With [uv](https://github.com/astral-sh/uv):

```bash
uv sync                 # simulations
uv sync --extra maps    # + map pipeline (Copernicus client, xarray, cartopy, ...)
```

or `pip install -e .` / `pip install -e ".[maps]"`. MoorDyn is installed from PyPI (`moordyn`).

Quick check, two 30 s runs (one per stiffness case) written to `results/example/`:

```bash
uv run python main.py --config config.yaml
```

---

## Reproducing the results

Run from the repository root.

**1. Lookup-table sweep** (350 runs, ≈ 28 h on 12 workers):

```bash
uv run python scripts/run_lut_sweep.py --workers 12      # --dry-run lists the jobs
```

This writes `results/lut_sweep/<WAMIT case>/*.pkl` plus a `.log` per run. Re-running skips finished runs.

**2. Lookup tables:**

```bash
for W in ArgoBoxStiffness ArgoSubmergedBox; do
  uv run python scripts/make_tables.py lut results/lut_sweep/$W
  cp results/lut_sweep/$W/lookup_table.csv results/lookup_$W.csv
done
```

**3. Validation sweep** for the deployment conditions (504 runs, ≈ 36 h on 12 workers):

```bash
uv run python scripts/run_validation_sweep.py --workers 12
for W in ArgoBoxStiffness ArgoSubmergedBox; do
  uv run python scripts/make_tables.py summary results/validation_sweep/$W   # -> 15m_summary.csv, 25m_summary.csv
done
```

**4. Annual surfacing maps** (needs the [external data](#external-data-not-included); downloading a year of hourly
data takes several hours):

```bash
cd maps
uv run python main.py      # -> outputs/baltic_percent.parquet, outputs/nws_percent.parquet
uv run python plotter.py   # -> outputs/Baltic_FULL_YEAR_percent.png (Fig 3), outputs/NWS_FULL_YEAR_percent.png
```

The lookup tables cover depths 20–100 m and Tp 3.05–8.5 s; shallower water and shorter-period seas are clipped to
those edges.

`main.py` with `config.yaml` runs any other grid of depths, current speeds and wave files with the same model
(see the comments in `config.yaml`).

---

## Citation

Please cite the paper above and the archived release of this repository:

> O'Brien-Møller, D. (2026). *Tethered Profiler Simulations* (v1.0.0) [Software]. Zenodo.
> https://doi.org/10.5281/zenodo.XXXXXXX

Citation metadata is in `CITATION.cff`. The code is released under the MIT License (`LICENSE`).
