from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import shutil
import uuid

import copernicusmarine as cm


@dataclass(frozen=True)
class BBox:
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float


@dataclass(frozen=True)
class TimeRange:
    start: str  # ISO8601 with Z, e.g. "2024-01-01T00:00:00Z"
    end: str    # end exclusive for hourly slices


class CMEMSDownloader:
    """
    Downloads CMEMS subsets into a run directory.
    Use as:

        with CMEMSDownloader(...) as dl:
            files = dl.download(TimeRange(...), keys=["nws_waves", ...])
            # do work
        # directory auto-deleted
    """

    def __init__(
        self,
        *,
        base_outdir: Path,
        bbox: BBox,
        datasets: dict[str, str],
        variables: dict[str, list[str]],
        keep: bool = False,
    ):
        self.base_outdir = Path(base_outdir)
        self.bbox = bbox
        self.datasets = datasets
        self.variables = variables
        self.keep = keep

        self.run_dir: Path | None = None

        # Basic validation early
        missing = [k for k in datasets if k not in variables]
        if missing:
            raise KeyError(f"Missing variables for keys: {missing}")

    def __enter__(self) -> "CMEMSDownloader":
        self.base_outdir.mkdir(parents=True, exist_ok=True)
        rid = uuid.uuid4().hex[:10]
        self.run_dir = self.base_outdir / f"cmems_run_{rid}"
        self.run_dir.mkdir(parents=True, exist_ok=False)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.keep:
            return
        if self.run_dir and self.run_dir.exists():
            shutil.rmtree(self.run_dir, ignore_errors=True)

    def download(
            self,
            tr: TimeRange,
            keys: Iterable[str] | None = None,
            bbox_by_key: dict[str, BBox] | None = None,
            file_format: str = "zarr",  # "zarr" or "netcdf"
    ) -> dict[str, Path]:
        if self.run_dir is None:
            raise RuntimeError("Use CMEMSDownloader in a 'with' block.")

        keys = list(keys) if keys is not None else list(self.datasets.keys())
        out: dict[str, Path] = {}

        for key in keys:
            bbox = (bbox_by_key or {}).get(key, self.bbox)
            out[key] = self._subset(key, tr, bbox=bbox, file_format=file_format)

        return out

    def _subset(self, key: str, tr: TimeRange, *, bbox: BBox, file_format: str) -> Path:
        if self.run_dir is None:
            raise RuntimeError("Run directory not initialized.")
        if key not in self.datasets:
            raise KeyError(f"Unknown key '{key}'")

        ds_id = self.datasets[key]
        vars_ = self.variables[key]

        tag = tr.start.replace(":", "").replace("-", "").replace("T", "T").replace("Z", "Z")

        # IMPORTANT: Zarr output should end with .zarr
        suffix = ".zarr" if file_format == "zarr" else ".nc"
        out_path = self.run_dir / f"{key}_{tag}{suffix}"

        cm.subset(
            dataset_id=ds_id,
            variables=vars_,
            minimum_longitude=bbox.lon_min,
            maximum_longitude=bbox.lon_max,
            minimum_latitude=bbox.lat_min,
            maximum_latitude=bbox.lat_max,
            start_datetime=tr.start,
            end_datetime=tr.end,
            output_directory=str(self.run_dir),
            output_filename=out_path.name,
            file_format=file_format,  # <-- key change
        )
        return out_path
