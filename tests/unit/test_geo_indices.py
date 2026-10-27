"""Unit tests for remote sensing vegetation, soil, and burn indices with hand-computed verification."""

from __future__ import annotations

import numpy as np
import pytest
from shapely.geometry import Polygon

from stubbleos.geo.indices import (
    compute_bsi,
    compute_nbr,
    compute_ndvi,
    detect_index_change,
)
from stubbleos.geo.raster import (
    compute_zonal_stats,
    create_synthetic_field_raster,
)


def test_ndvi_hand_computed_values() -> None:
    """Tests NDVI calculation on small 2x2 raster with hand-computed exact values.

    Formula: (NIR - Red) / (NIR + Red)
    """
    # 2x2 pixel grid
    nir = np.array([[0.70, 0.35], [0.80, 0.00]], dtype=np.float64)
    red = np.array([[0.10, 0.30], [0.20, 0.00]], dtype=np.float64)

    # Hand-computed:
    # (0, 0): (0.7 - 0.1) / (0.7 + 0.1) = 0.6 / 0.8 = 0.750000 (Dense green canopy)
    # (0, 1): (0.35 - 0.3) / (0.35 + 0.3) = 0.05 / 0.65 = 0.076923 (Harvested / stubble)
    # (1, 0): (0.8 - 0.2) / (0.8 + 0.2) = 0.6 / 1.0 = 0.600000 (Vegetation)
    # (1, 1): 0 / 0 = 0.000000 (Zero denominator handling)
    expected = np.array(
        [[0.75, 0.05 / 0.65], [0.60, 0.0]],
        dtype=np.float64,
    )

    result = compute_ndvi(nir, red)
    assert np.allclose(result, expected, atol=1e-6)
    assert result[0, 0] == pytest.approx(0.75, abs=1e-5)
    assert result[0, 1] == pytest.approx(0.076923, abs=1e-5)
    assert result[1, 1] == 0.0


def test_bsi_hand_computed_values() -> None:
    """Tests Bare Soil Index on 2x2 raster with hand-computed exact values.

    Formula: ((SWIR + Red) - (NIR + Blue)) / ((SWIR + Red) + (NIR + Blue))
    """
    swir = np.array([[0.20, 0.50], [0.60, 0.00]], dtype=np.float64)
    red = np.array([[0.10, 0.30], [0.25, 0.00]], dtype=np.float64)
    nir = np.array([[0.70, 0.35], [0.15, 0.00]], dtype=np.float64)
    blue = np.array([[0.05, 0.15], [0.10, 0.00]], dtype=np.float64)

    # Hand-computed:
    # (0, 0): soil = 0.2+0.1=0.3; veg = 0.7+0.05=0.75;
    #         (0.3 - 0.75) / (0.3 + 0.75) = -0.45 / 1.05 = -0.428571 (Dense crop)
    # (0, 1): soil = 0.5+0.3=0.8; veg = 0.35+0.15=0.5;
    #         (0.8 - 0.5) / (0.8 + 0.5) = 0.3 / 1.3 = 0.230769 (Bare cleared soil)
    # (1, 0): soil = 0.6+0.25=0.85; veg = 0.15+0.1=0.25;
    #         (0.85 - 0.25) / (0.85 + 0.25) = 0.6 / 1.1 = 0.545455 (Dry tilled soil)
    # (1, 1): 0 / 0 = 0.000000 (Zero denominator)
    expected = np.array(
        [
            [-0.45 / 1.05, 0.3 / 1.3],
            [0.6 / 1.1, 0.0],
        ],
        dtype=np.float64,
    )

    result = compute_bsi(swir, red, nir, blue)
    assert np.allclose(result, expected, atol=1e-6)
    assert result[0, 0] == pytest.approx(-0.428571, abs=1e-5)
    assert result[0, 1] == pytest.approx(0.230769, abs=1e-5)
    assert result[1, 0] == pytest.approx(0.545455, abs=1e-5)


def test_nbr_hand_computed_values() -> None:
    """Tests Normalized Burn Ratio: (NIR - SWIR) / (NIR + SWIR)."""
    nir = np.array([[0.75, 0.15]], dtype=np.float64)
    swir = np.array([[0.25, 0.60]], dtype=np.float64)

    # (0, 0): (0.75 - 0.25) / (0.75 + 0.25) = 0.5 / 1.0 = 0.500000 (Unburned)
    # (0, 1): (0.15 - 0.60) / (0.15 + 0.60) = -0.45 / 0.75 = -0.600000 (Burned stubble)
    expected = np.array([[0.50, -0.60]], dtype=np.float64)
    result = compute_nbr(nir, swir)
    assert np.allclose(result, expected, atol=1e-6)


def test_detect_index_change() -> None:
    """Tests temporal change detection between pre-harvest and post-harvest."""
    pre_ndvi = np.array([0.75, 0.70])
    post_ndvi = np.array([0.25, 0.68])

    abs_change, rel_drop = detect_index_change(pre_ndvi, post_ndvi)

    # Pixel 0: dropped from 0.75 to 0.25 (abs: -0.50, rel_drop: 0.50 / 0.75 = 0.666667)
    assert abs_change[0] == pytest.approx(-0.50, abs=1e-6)
    assert rel_drop[0] == pytest.approx(0.666667, abs=1e-5)

    # Pixel 1: small variation 0.70 to 0.68 (abs: -0.02, rel_drop: 0.02 / 0.70 = 0.028571)
    assert abs_change[1] == pytest.approx(-0.02, abs=1e-6)
    assert rel_drop[1] == pytest.approx(0.028571, abs=1e-5)


def test_compute_zonal_stats_and_synthetic_raster() -> None:
    """Tests zonal statistics aggregation over synthetic raster within polygon bounds."""
    grid = create_synthetic_field_raster(
        shape=(10, 10),
        bounds=(75.80, 30.20, 75.90, 30.30),
        ndvi_base=0.72,
        seed=42,
    )

    ndvi_arr = compute_ndvi(grid.bands["nir"], grid.bands["red"])

    # Define polygon matching the central area of the raster
    field_poly = Polygon(
        [
            (75.82, 30.22),
            (75.88, 30.22),
            (75.88, 30.28),
            (75.82, 30.28),
            (75.82, 30.22),
        ]
    )

    stats = compute_zonal_stats(ndvi_arr, grid.bounds, field_poly)
    assert stats["count"] > 0
    assert 0.65 <= stats["mean"] <= 0.80
    assert stats["min"] <= stats["mean"] <= stats["max"]
    assert stats["std"] >= 0.0

    # Non-intersecting polygon returns zero stats
    outside_poly = Polygon([(76.5, 31.0), (76.6, 31.0), (76.6, 31.1), (76.5, 31.0)])
    outside_stats = compute_zonal_stats(ndvi_arr, grid.bounds, outside_poly)
    assert outside_stats["count"] == 0.0
    assert outside_stats["mean"] == 0.0
