# plot_output.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

USE_CARTOPY = True
try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
except Exception:
    USE_CARTOPY = False


@dataclass(frozen=True)
class Grid:
    lon: np.ndarray      # 1D
    lat: np.ndarray      # 1D
    values: np.ndarray   # 2D (lat, lon)


def load_parquet(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    needed = {"lon", "lat", "percent"}
    missing = needed - set(df.columns)
    if missing:
        raise KeyError(f"{path}: missing columns {missing}. Have {list(df.columns)}")
    return df


def df_to_grid(df: pd.DataFrame, value_col: str = "percent") -> Grid:
    """
    Convert long-form table with columns lon, lat, value_col to a regular 2D grid.

    Assumptions:
      - lon/lat form a full regular grid (as produced by your pipeline)
      - duplicates don't exist
    """
    # sort unique coordinates
    lon = np.sort(df["lon"].unique())
    lat = np.sort(df["lat"].unique())

    # map coords -> indices
    lon_i = pd.Index(lon)
    lat_i = pd.Index(lat)

    # allocate and fill
    Z = np.full((lat.size, lon.size), np.nan, dtype=np.float32)

    # vectorized index lookup
    ix = lon_i.get_indexer(df["lon"].to_numpy())
    iy = lat_i.get_indexer(df["lat"].to_numpy())
    vals = df[value_col].to_numpy(dtype=np.float32)

    Z[iy, ix] = vals
    return Grid(lon=lon, lat=lat, values=Z)


def _apply_extent(ax, lon: np.ndarray, lat: np.ndarray):
    lon_min, lon_max = float(np.nanmin(lon)), float(np.nanmax(lon))
    lat_min, lat_max = float(np.nanmin(lat)), float(np.nanmax(lat))
    if USE_CARTOPY:
        ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())
    else:
        ax.set_xlim(lon_min, lon_max)
        ax.set_ylim(lat_min, lat_max)


def plot_grid(
    grid: Grid,
    *,
    units: str = "%",
    cmap: str = "RdYlBu",
    vmin: float | None = -15.0,
    vmax: float | None = 100.0,
    cbar_min: float | None = 0.0,
    cbar_max: float | None = 100.0,
    show: bool = True,
    save: Path | None = None,
):
    """
    Simple map plot using pcolormesh.
    """
    # pcolormesh prefers 2D coordinates; build them from 1D.
    LON, LAT = np.meshgrid(grid.lon, grid.lat)

    if USE_CARTOPY:
        fig, ax = plt.subplots(figsize=(10, 7), subplot_kw={"projection": ccrs.PlateCarree()})
        transform = ccrs.PlateCarree()
    else:
        fig, ax = plt.subplots(figsize=(10, 7))
        transform = None

    mesh = ax.pcolormesh(
        LON,
        LAT,
        grid.values,
        shading="auto",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        transform=transform,
    )
    _apply_extent(ax, grid.lon, grid.lat)

    cb = plt.colorbar(mesh, ax=ax, shrink=0.75)
    cb.set_label(units)
    if vmin is not None and vmax is not None:
        mesh.set_clim(vmin, vmax)
    if cbar_min is not None and cbar_max is not None:
        cb.ax.set_ylim(cbar_min, cbar_max)
        cb.set_ticks(np.linspace(cbar_min, cbar_max, 6))

    if USE_CARTOPY:
        ax.coastlines(resolution="10m", linewidth=0.6)
        ax.add_feature(cfeature.LAND.with_scale("10m"), facecolor="white")
        ax.gridlines(draw_labels=True, linewidth=0.2, alpha=0.0)

    fig.tight_layout()

    if save is not None:
        save.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save, dpi=300)

    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_percent_and_counts(parquet_path: Path, *, basin_name: str | None = None):
    """
    Convenience: plot percent and count_valid if present.
    """
    df = load_parquet(parquet_path)
    basin = basin_name or (df["basin"].iloc[0] if "basin" in df.columns else parquet_path.stem)

    # Percent
    g_percent = df_to_grid(df, "percent")
    plot_grid(g_percent, units=" Percentage of Successful Hourly Transmissions (%)", save=parquet_path.parent / f"{basin}_FULL_YEAR_percent.png")

    # Count valid (optional)
    if "count_valid" in df.columns:
        g_cnt = df_to_grid(df, "count_valid")
        plot_grid(
            g_cnt,
            units="hours",
            vmin=None,
            vmax=None,
            cmap="magma",
        )


if __name__ == "__main__":
    # Fig 3: annual percentage of successful hourly transmissions, from the files main.py writes
    outputs = Path(__file__).resolve().parent / "outputs"
    plot_percent_and_counts(outputs / "baltic_percent.parquet", basin_name="Baltic")
    plot_percent_and_counts(outputs / "nws_percent.parquet", basin_name="NWS")
