from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import xarray as xr

from bathy import BathyGrid


@dataclass(frozen=True)
class BasinConfig:
    name: str
    key_curr: str           # key in downloaded files dict, e.g. "nws_currents"
    key_wav: str            # key in downloaded files dict, e.g. "nws_waves"
    u_name: str             # "uo" or "u0"
    v_name: str             # "vo" or "v0"
    hs_name: str = "VHM0"
    tp_name: str = "VTPK"


@dataclass()
class BasinAccum:
    name: str
    lon: np.ndarray           # 1D
    lat: np.ndarray           # 1D
    sum_score: np.ndarray     # 2D float32 (lat, lon)
    count_valid: np.ndarray   # 2D uint32 (lat, lon)


def _time_name(ds: xr.Dataset) -> str:
    for t in ("time", "TIME", "t", "time_counter"):
        if t in ds.coords:
            return t
    raise KeyError(f"Could not find time coord. coords={list(ds.coords)}")


def _lonlat_names(ds: xr.Dataset) -> tuple[str, str]:
    lon_candidates = ["longitude", "lon", "LONGITUDE", "x", "nav_lon"]
    lat_candidates = ["latitude", "lat", "LATITUDE", "y", "nav_lat"]
    lon = next((c for c in lon_candidates if c in ds.coords), None)
    lat = next((c for c in lat_candidates if c in ds.coords), None)
    if lon is None or lat is None:
        raise KeyError(f"Could not find lon/lat coords. coords={list(ds.coords)}")
    return lon, lat


def _require_1d(lon: np.ndarray, lat: np.ndarray, label: str) -> None:
    if lon.ndim != 1 or lat.ndim != 1:
        raise ValueError(
            f"{label}: expected 1D lon/lat. Got lon.ndim={lon.ndim}, lat.ndim={lat.ndim}. "
            "If this dataset uses 2D lon/lat, you need xESMF regridding (not implemented here)."
        )


def _classify_to_score(frac_a: np.ndarray, frac_b: np.ndarray, threshold: float) -> np.ndarray:
    """
    frac_* are 1D arrays for valid points
      success: both < thr => 1.0
      maybe:   one < thr  => 0.5
      failure: both >=thr => 0.0
    """
    a_fail = frac_a >= threshold
    b_fail = frac_b >= threshold
    score = np.empty(frac_a.shape, dtype=np.float32)
    score[~a_fail & ~b_fail] = 1.0
    score[a_fail & b_fail] = 0.0
    mid = (~(a_fail & b_fail)) & (~(~a_fail & ~b_fail))
    score[mid] = 0.5
    return score


class DataProcessor:
    """
    Processes one downloaded chunk (one dict of paths) into accumulators per basin.
    Lookup interpolators must be callables:
        y = lut(X)  where X is (N,4) = [depth_m, current_ms, Hs_m, Tp_s].
    """

    def __init__(
        self,
        *,
        lut_a,
        lut_b,
        threshold: float = 0.20,
    ):
        self.lut_a = lut_a
        self.lut_b = lut_b
        self.threshold = threshold

    def process_chunk_two_basins(
        self,
        files: dict[str, Path],
        *,
        bathy_by_basin: dict[str, BathyGrid],
        nws_cfg: BasinConfig,
        bal_cfg: BasinConfig,
    ) -> tuple[BasinAccum, BasinAccum]:
        a = self.process_chunk_basin(files, bathy_by_basin=bathy_by_basin, cfg=nws_cfg)
        b = self.process_chunk_basin(files, bathy_by_basin=bathy_by_basin, cfg=bal_cfg)
        return a, b

    def process_chunk_basin(
        self,
        files: dict[str, Path],
        *,
        bathy_by_basin: dict[str, BathyGrid],
        cfg: BasinConfig,
    ) -> BasinAccum:
        curr_path = files[cfg.key_curr]
        wav_path = files[cfg.key_wav]

        ds_c = xr.open_dataset(curr_path, chunks={})
        ds_w = xr.open_dataset(wav_path, chunks={})

        t_c = _time_name(ds_c)
        t_w = _time_name(ds_w)

        lonw_name, latw_name = _lonlat_names(ds_w)
        lon_w = ds_w[lonw_name].values
        lat_w = ds_w[latw_name].values
        _require_1d(lon_w, lat_w, f"{cfg.name} wave grid")

        # --- bathy -> elevation on wave grid (static for this chunk) ---
        if cfg.name not in bathy_by_basin:
            raise KeyError(f"Missing bathy grid for basin '{cfg.name}'. Have {list(bathy_by_basin)}")

        bathy = bathy_by_basin[cfg.name]
        _require_1d(bathy.lon, bathy.lat, f"{cfg.name} bathy grid")

        elev_da = xr.DataArray(
            bathy.elevation,
            dims=("lat", "lon"),
            coords={"lon": bathy.lon, "lat": bathy.lat},
        ).interp(lon=lon_w, lat=lat_w, method="linear")

        elev_on_wave = elev_da.values.astype(np.float32)
        depth_m = -elev_on_wave
        land = elev_on_wave > 0

        ny, nx = depth_m.shape

        # --- currents and waves as DataArrays, then align times robustly ---
        hs_da = ds_w[cfg.hs_name]
        tp_da = ds_w[cfg.tp_name]

        u_da = ds_c[cfg.u_name]
        v_da = ds_c[cfg.v_name]

        # surface slice if needed
        for depth_name in ["depth", "depthu", "depthv", "lev", "z"]:
            if depth_name in u_da.dims:
                u_da = u_da.isel({depth_name: 0})
            if depth_name in v_da.dims:
                v_da = v_da.isel({depth_name: 0})

        # compute speed as DataArray
        speed_da = xr.apply_ufunc(
            np.hypot, u_da, v_da,
            dask="allowed",
            output_dtypes=[np.float32],
        )

        # If current grid differs from wave grid, interpolate speed to wave grid
        lonc_name, latc_name = _lonlat_names(ds_c)
        lon_c = ds_c[lonc_name].values
        lat_c = ds_c[latc_name].values
        _require_1d(lon_c, lat_c, f"{cfg.name} current grid")

        if (not np.array_equal(lon_c, lon_w)) or (not np.array_equal(lat_c, lat_w)) or (speed_da.shape[-2:] != (ny, nx)):
            speed_da = speed_da.interp({lonc_name: lon_w, latc_name: lat_w}, method="linear")

        # Now align times by inner join on the time coordinate values
        # Rename time dims to a consistent name to make align easier
        hs_da = hs_da.rename({t_w: "time"})
        tp_da = tp_da.rename({t_w: "time"})
        speed_da = speed_da.rename({t_c: "time"})

        hs_da, tp_da, speed_da = xr.align(hs_da, tp_da, speed_da, join="inner")

        ntime = hs_da.sizes["time"]

        sum_score = np.zeros((ny, nx), dtype=np.float32)
        count_valid = np.zeros((ny, nx), dtype=np.uint32)

        for ti in range(ntime):
            hs = hs_da.isel(time=ti).load().values.astype(np.float32)
            tp = tp_da.isel(time=ti).load().values.astype(np.float32)
            speed = speed_da.isel(time=ti).load().values.astype(np.float32)

            valid = (
                np.isfinite(depth_m)
                & np.isfinite(speed)
                & np.isfinite(hs)
                & np.isfinite(tp)
                & (~land)
            )

            if not np.any(valid):
                continue

            Xv = np.column_stack([
                depth_m[valid],
                speed[valid],
                hs[valid],
                tp[valid],
            ])

            # lookup
            fa = self.lut_a(Xv)
            fb = self.lut_b(Xv)

            # score for valid points
            score_v = _classify_to_score(fa, fb, self.threshold)

            # accumulate
            sum_score[valid] += score_v
            count_valid[valid] += 1

        ds_c.close()
        ds_w.close()

        return BasinAccum(
            name=cfg.name,
            lon=lon_w,
            lat=lat_w,
            sum_score=sum_score,
            count_valid=count_valid,
        )

    @staticmethod
    def finalize_percent(acc: BasinAccum) -> tuple[np.ndarray, np.ndarray]:
        """
        Returns:
          percent (2D float32, 0..100, NaN where no valid)
          count_valid (2D uint32)
        """
        percent = np.full(acc.sum_score.shape, np.nan, dtype=np.float32)
        ok = acc.count_valid > 0
        percent[ok] = 100.0 * acc.sum_score[ok] / acc.count_valid[ok]
        return percent, acc.count_valid
