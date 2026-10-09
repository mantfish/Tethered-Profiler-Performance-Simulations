from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import numpy as np
import xarray as xr


@dataclass(frozen=True)
class BathyGrid:
    lon: np.ndarray        # 1D
    lat: np.ndarray        # 1D
    elevation: np.ndarray  # 2D (lat, lon), meters. negative = sea, positive = land
    units: str = "m"

    def depth_and_landmask(self) -> tuple[np.ndarray, np.ndarray]:
        """
        Returns:
          depth_m: 2D positive depth in meters (sea only)
          land:    2D boolean mask where elevation > 0
        """
        land = self.elevation > 0
        depth = -self.elevation.astype(np.float32)
        return depth, land


def _pick_lon_lat_names(ds: xr.Dataset) -> tuple[str, str]:
    lon_candidates = ["lon", "longitude", "x", "LONGITUDE"]
    lat_candidates = ["lat", "latitude", "y", "LATITUDE"]
    lon = next((c for c in lon_candidates if c in ds.coords), None)
    lat = next((c for c in lat_candidates if c in ds.coords), None)
    if lon is None or lat is None:
        raise KeyError(f"Could not find lon/lat coords. coords={list(ds.coords)}")
    return lon, lat


def _require_1d_lonlat(lon: np.ndarray, lat: np.ndarray, label: str):
    if lon.ndim != 1 or lat.ndim != 1:
        raise ValueError(
            f"{label}: expected 1D lon/lat. Got lon.ndim={lon.ndim}, lat.ndim={lat.ndim}. "
            "If you have curvilinear grids (2D lon/lat), you need regridding tools (xESMF)."
        )


def load_emodnet_tile(path: Path, *, var: str = "elevation") -> BathyGrid:
    """
    Load an EMODnet DTM tile NetCDF (or similar) that contains 'elevation'.
    Assumes lon/lat are 1D.
    """
    ds = xr.open_dataset(path)

    lon_name, lat_name = _pick_lon_lat_names(ds)
    if var not in ds.data_vars:
        raise KeyError(f"{path}: expected data var '{var}'. vars={list(ds.data_vars)}")

    lon = ds[lon_name].values
    lat = ds[lat_name].values
    _require_1d_lonlat(lon, lat, f"{path}")

    elev = ds[var].values
    if elev.shape != (lat.size, lon.size):
        raise ValueError(
            f"{path}: {var} shape {elev.shape} does not match (lat,lon)=({lat.size},{lon.size})"
        )

    units = getattr(ds[var], "units", "m")
    ds.close()
    return BathyGrid(lon=lon, lat=lat, elevation=elev, units=units)


def subset_bbox(
    grid: BathyGrid,
    *,
    lon_min: float,
    lon_max: float,
    lat_min: float,
    lat_max: float,
) -> BathyGrid:
    """
    Subset by bbox using coordinate slicing. Handles lat descending by sorting.
    """
    da = xr.DataArray(
        grid.elevation,
        dims=("lat", "lon"),
        coords={"lon": grid.lon, "lat": grid.lat},
        name="elevation",
    )

    # Ensure ascending latitude for slice semantics
    if da["lat"].values[0] > da["lat"].values[-1]:
        da = da.sortby("lat")

    da_sub = da.sel(lon=slice(lon_min, lon_max), lat=slice(lat_min, lat_max))
    return BathyGrid(
        lon=da_sub["lon"].values,
        lat=da_sub["lat"].values,
        elevation=da_sub.values,
        units=grid.units,
    )


def downsample(grid: BathyGrid, *, max_nx: int = 900, max_ny: int = 900) -> BathyGrid:
    """
    Downsample regular grid using block-mean coarsen.
    Intended for plotting / lightweight processing.
    """
    da = xr.DataArray(
        grid.elevation,
        dims=("lat", "lon"),
        coords={"lon": grid.lon, "lat": grid.lat},
        name="elevation",
    )

    nx = da.sizes["lon"]
    ny = da.sizes["lat"]

    fx = max(1, int(np.ceil(nx / max_nx)))
    fy = max(1, int(np.ceil(ny / max_ny)))

    if fx == 1 and fy == 1:
        return grid

    da_ds = da.coarsen(lat=fy, lon=fx, boundary="trim").mean()
    return BathyGrid(
        lon=da_ds["lon"].values,
        lat=da_ds["lat"].values,
        elevation=da_ds.values,
        units=grid.units,
    )


def merge_primary_fallback(primary: BathyGrid, fallback: BathyGrid) -> BathyGrid:
    """
    Merge two grids: primary wins where it has finite values, fallback fills NaNs.
    If grids differ, aligns on outer lon/lat.
    """
    da1 = xr.DataArray(primary.elevation, dims=("lat", "lon"), coords={"lon": primary.lon, "lat": primary.lat})
    da2 = xr.DataArray(fallback.elevation, dims=("lat", "lon"), coords={"lon": fallback.lon, "lat": fallback.lat})

    da1a, da2a = xr.align(da1, da2, join="outer")
    merged = da1a.combine_first(da2a)

    return BathyGrid(
        lon=merged["lon"].values,
        lat=merged["lat"].values,
        elevation=merged.values,
        units=primary.units,
    )
