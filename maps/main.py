from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from cmems_downloader import CMEMSDownloader, BBox, TimeRange
from bathy import load_emodnet_tile, subset_bbox, merge_primary_fallback
from lookup_interp import build_lookup_interpolator
from data_processor import DataProcessor, BasinConfig, BasinAccum


# ------------------------ CONFIG ------------------------

HERE = Path(__file__).resolve().parent

OUTDIR = HERE / "outputs"
OUTDIR.mkdir(parents=True, exist_ok=True)

TMP_BASE = HERE / "cmems_tmp"

# Geographic range
BBOX = BBox(lon_min=6.0, lon_max=15.5, lat_min=54.0, lat_max=58.8)

# Temporal range (UTC Z, end exclusive)
START = "2024-01-01T00:00:00Z"
END   = "2025-01-08T00:00:00Z"

# Chunking: 24 hours per download/process cycle
CHUNK_HOURS = 24

DATASETS = {
    "nws_currents": "cmems_mod_nws_phy-uv_my_7km-2D_PT1H-i",
    "nws_waves":    "MetO-NWS-WAV-RAN",
    "bal_currents": "cmems_mod_bal_phy_anfc_PT1H-i",
    "bal_waves":    "cmems_mod_bal_wav_my_PT1H-i",
}
VARS = {
    "nws_currents": ["uo", "vo"],
    "nws_waves":    ["VHM0", "VTPK"],
    "bal_currents": ["uo", "vo"],   # important
    "bal_waves":    ["VHM0", "VTPK"],
}

LOOKUP_A = HERE.parent / "results/lookup_ArgoBoxStiffness.csv"   # K_L
LOOKUP_B = HERE.parent / "results/lookup_ArgoSubmergedBox.csv"   # K_S
THRESHOLD = 0.20

# EMODnet DTM tiles, see README "External data"
BATHY_NWS = HERE / "data/bathymetry/D5_2022.nc"
BATHY_BAL = HERE / "data/bathymetry/D6_2024.nc"

# -------------------------------------------------------


def parse_utc_z(s: str) -> datetime:
    if not s.endswith("Z"):
        raise ValueError(f"Expected time ending with 'Z': {s}")
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def fmt_utc_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iter_timeranges(start: str, end: str, chunk_hours: int):
    t0 = parse_utc_z(start)
    t1 = parse_utc_z(end)
    if t1 <= t0:
        raise ValueError("END must be after START")

    cur = t0
    step = timedelta(hours=chunk_hours)
    while cur < t1:
        nxt = min(cur + step, t1)
        yield TimeRange(start=fmt_utc_z(cur), end=fmt_utc_z(nxt))
        cur = nxt


def init_global_acc(acc: BasinAccum) -> BasinAccum:
    return BasinAccum(
        name=acc.name,
        lon=acc.lon,
        lat=acc.lat,
        sum_score=np.zeros_like(acc.sum_score, dtype=np.float32),
        count_valid=np.zeros_like(acc.count_valid, dtype=np.uint32),
    )


def accumulate_global(global_acc: BasinAccum, chunk_acc: BasinAccum) -> None:
    # basic shape checks
    if global_acc.sum_score.shape != chunk_acc.sum_score.shape:
        raise ValueError(f"Shape mismatch for {global_acc.name}: {global_acc.sum_score.shape} vs {chunk_acc.sum_score.shape}")
    global_acc.sum_score += chunk_acc.sum_score
    global_acc.count_valid += chunk_acc.count_valid


def grid_to_dataframe(name: str, lon_1d: np.ndarray, lat_1d: np.ndarray, percent_2d: np.ndarray, count_2d: np.ndarray) -> pd.DataFrame:
    LON, LAT = np.meshgrid(lon_1d, lat_1d)  # (lat, lon)
    return pd.DataFrame(
        {
            "basin": name,
            "lon": LON.ravel(),
            "lat": LAT.ravel(),
            "percent": percent_2d.astype(np.float32).ravel(),
            "count_valid": count_2d.astype(np.uint32).ravel(),
        }
    )


def main():
    # --- lookup interpolators ---
    lut_a = build_lookup_interpolator(LOOKUP_A)
    lut_b = build_lookup_interpolator(LOOKUP_B)

    # --- bathy: load once, subset once, merge once ---
    nws_bathy = load_emodnet_tile(BATHY_NWS)
    bal_bathy = load_emodnet_tile(BATHY_BAL)

    # Subset bathy to bbox with a small margin (optional). Here: exact bbox.
    nws_bathy = subset_bbox(
        nws_bathy,
        lon_min=BBOX.lon_min, lon_max=BBOX.lon_max,
        lat_min=BBOX.lat_min, lat_max=BBOX.lat_max,
    )
    bal_bathy = subset_bbox(
        bal_bathy,
        lon_min=BBOX.lon_min, lon_max=BBOX.lon_max,
        lat_min=BBOX.lat_min, lat_max=BBOX.lat_max,
    )

    # Merge: Baltic preferred, fill missing with NWS
    bal_bathy = merge_primary_fallback(bal_bathy, nws_bathy)

    bathy_by_basin = {
        "NWS": nws_bathy,
        "Baltic": bal_bathy,
    }

    # --- processor ---
    proc = DataProcessor(lut_a=lut_a, lut_b=lut_b, threshold=THRESHOLD)

    nws_cfg = BasinConfig(name="NWS", key_curr="nws_currents", key_wav="nws_waves", u_name="uo", v_name="vo")
    bal_cfg = BasinConfig(name="Baltic", key_curr="bal_currents", key_wav="bal_waves", u_name="uo", v_name="vo")

    # --- global accumulators (initialized after first chunk) ---
    global_nws: BasinAccum | None = None
    global_bal: BasinAccum | None = None

    # --- download + process loop ---
    with CMEMSDownloader(
        base_outdir=TMP_BASE,
        bbox=BBOX,
        datasets=DATASETS,
        variables=VARS,
        keep=False,
    ) as dl:
        for tr in iter_timeranges(START, END, CHUNK_HOURS):
            files = dl.download(tr)

            chunk_nws, chunk_bal = proc.process_chunk_two_basins(
                files,
                bathy_by_basin=bathy_by_basin,
                nws_cfg=nws_cfg,
                bal_cfg=bal_cfg,
            )

            if global_nws is None:
                global_nws = init_global_acc(chunk_nws)
                global_bal = init_global_acc(chunk_bal)

            accumulate_global(global_nws, chunk_nws)
            accumulate_global(global_bal, chunk_bal)

    if global_nws is None or global_bal is None:
        raise RuntimeError("No chunks processed. Check START/END or downloads.")

    # --- finalize percent grids ---
    nws_percent, nws_count = proc.finalize_percent(global_nws)
    bal_percent, bal_count = proc.finalize_percent(global_bal)

    # --- create dataframes ---
    df_nws = grid_to_dataframe("NWS", global_nws.lon, global_nws.lat, nws_percent, nws_count)
    df_bal = grid_to_dataframe("Baltic", global_bal.lon, global_bal.lat, bal_percent, bal_count)

    # Save
    out_nws = OUTDIR / "nws_percent.parquet"
    out_bal = OUTDIR / "baltic_percent.parquet"
    df_nws.to_parquet(out_nws, index=False)
    df_bal.to_parquet(out_bal, index=False)

    print(f"Wrote: {out_nws} rows={len(df_nws):,}")
    print(f"Wrote: {out_bal} rows={len(df_bal):,}")


if __name__ == "__main__":
    main()
