"""Raster and vector spatial utilities for cropping, zonal statistics, and synthetic grids."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from shapely.geometry import Polygon, box


@dataclass
class RasterGrid:
    """In-memory 2D or multiband raster with bounding box."""

    bands: dict[str, np.ndarray]  # e.g., "red", "nir", "blue", "swir"
    bounds: tuple[float, float, float, float]  # minx, miny, maxx, maxy
    nodata: float = -9999.0

    @property
    def shape(self) -> tuple[int, int]:
        first_band = next(iter(self.bands.values()))
        return first_band.shape


def compute_zonal_stats(
    raster_array: np.ndarray,
    bounds: tuple[float, float, float, float],
    field_geom: Polygon | Any,
) -> dict[str, float]:
    """Calculates zonal statistics (mean, median, min, max, std) of a raster inside a polygon.

    Supports shapely Polygon or bounding-box-based geometric sampling.
    """
    arr = np.asarray(raster_array, dtype=np.float64)
    minx, miny, maxx, maxy = bounds
    nrows, ncols = arr.shape

    # Determine bounding box intersection of field with raster
    if hasattr(field_geom, "bounds"):
        f_minx, f_miny, f_maxx, f_maxy = field_geom.bounds
    else:
        # Fallback assuming bounds tuple
        f_minx, f_miny, f_maxx, f_maxy = minx, miny, maxx, maxy

    # Check for non-overlapping geometry
    raster_poly = box(minx, miny, maxx, maxy)
    if hasattr(field_geom, "intersects") and not field_geom.intersects(raster_poly):
        return {"mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0, "std": 0.0, "count": 0.0}

    # Map geographic coordinates to pixel indices
    x_res = (maxx - minx) / max(1, ncols)
    y_res = (maxy - miny) / max(1, nrows)

    col_start = int(np.clip(int((f_minx - minx) / x_res), 0, ncols - 1))
    col_end = int(np.clip(int(np.ceil((f_maxx - minx) / x_res)), col_start + 1, ncols))
    row_start = int(np.clip(int((maxy - f_maxy) / y_res), 0, nrows - 1))
    row_end = int(np.clip(int(np.ceil((maxy - f_miny) / y_res)), row_start + 1, nrows))

    window = arr[row_start:row_end, col_start:col_end]
    valid_mask = ~np.isnan(window) & ~np.isinf(window) & (window != -9999.0)
    valid_pixels = window[valid_mask]

    if len(valid_pixels) == 0:
        return {"mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0, "std": 0.0, "count": 0.0}

    return {
        "mean": float(np.mean(valid_pixels)),
        "median": float(np.median(valid_pixels)),
        "min": float(np.min(valid_pixels)),
        "max": float(np.max(valid_pixels)),
        "std": float(np.std(valid_pixels)),
        "count": float(len(valid_pixels)),
    }


def create_synthetic_field_raster(
    shape: tuple[int, int] = (10, 10),
    bounds: tuple[float, float, float, float] = (75.80, 30.20, 75.90, 30.30),
    *,
    ndvi_base: float = 0.70,
    bsi_base: float = -0.30,
    noise_std: float = 0.02,
    seed: int = 42,
) -> RasterGrid:
    """Generates a synthetic multiband raster for testing remote sensing workflows."""
    rng = np.random.default_rng(seed)
    nrows, ncols = shape

    # Solve for approximate NIR and Red to yield ndvi_base
    # NDVI = (NIR - Red) / (NIR + Red)
    # Let NIR + Red = 0.8 => NIR = 0.8 * (1 + NDVI) / 2
    nir_val = 0.8 * (1.0 + ndvi_base) / 2.0
    red_val = 0.8 - nir_val

    # Solve for approximate SWIR to yield bsi_base with Blue=0.08
    blue_val = 0.08
    # BSI approx = ((SWIR + Red) - (NIR + Blue)) / ((SWIR + Red) + (NIR + Blue))
    # Let denom = 1.0 => (SWIR + Red) = 0.5 * (1 + BSI)
    swir_val = max(0.05, 0.5 * (1.0 + bsi_base) - red_val)

    nir = np.clip(rng.normal(nir_val, noise_std, size=(nrows, ncols)), 0.01, 1.0)
    red = np.clip(rng.normal(red_val, noise_std, size=(nrows, ncols)), 0.01, 1.0)
    blue = np.clip(rng.normal(blue_val, noise_std, size=(nrows, ncols)), 0.01, 1.0)
    swir = np.clip(rng.normal(swir_val, noise_std, size=(nrows, ncols)), 0.01, 1.0)

    return RasterGrid(
        bands={"nir": nir, "red": red, "blue": blue, "swir": swir},
        bounds=bounds,
    )
