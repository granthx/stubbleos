"""Remote sensing vegetation, soil, and burn index mathematics and change detection."""

from __future__ import annotations

import numpy as np


def compute_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Calculates Normalized Difference Vegetation Index: (NIR - Red) / (NIR + Red).

    Range: [-1.0, 1.0]. High values (>0.5) indicate dense green canopy;
    a sudden drop indicates harvest.
    """
    nir_f = np.asarray(nir, dtype=np.float64)
    red_f = np.asarray(red, dtype=np.float64)
    denominator = nir_f + red_f
    numerator = nir_f - red_f

    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = np.where(denominator != 0.0, numerator / denominator, 0.0)
    return np.clip(ndvi, -1.0, 1.0)


def compute_bsi(
    swir: np.ndarray,
    red: np.ndarray,
    nir: np.ndarray,
    blue: np.ndarray,
) -> np.ndarray:
    """Calculates Bare Soil Index: ((SWIR + Red) - (NIR + Blue)) / ((SWIR + Red) + (NIR + Blue)).

    Range: [-1.0, 1.0]. Positive values (>0.15) indicate exposed bare soil
    after residue clearance or deep tillage.
    """
    swir_f = np.asarray(swir, dtype=np.float64)
    red_f = np.asarray(red, dtype=np.float64)
    nir_f = np.asarray(nir, dtype=np.float64)
    blue_f = np.asarray(blue, dtype=np.float64)

    soil_term = swir_f + red_f
    veg_term = nir_f + blue_f
    denominator = soil_term + veg_term
    numerator = soil_term - veg_term

    with np.errstate(divide="ignore", invalid="ignore"):
        bsi = np.where(denominator != 0.0, numerator / denominator, 0.0)
    return np.clip(bsi, -1.0, 1.0)


def compute_nbr(nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """Calculates Normalized Burn Ratio: (NIR - SWIR) / (NIR + SWIR).

    Range: [-1.0, 1.0]. Lower values indicate burned vegetation and charcoal residue.
    """
    nir_f = np.asarray(nir, dtype=np.float64)
    swir_f = np.asarray(swir, dtype=np.float64)
    denominator = nir_f + swir_f
    numerator = nir_f - swir_f

    with np.errstate(divide="ignore", invalid="ignore"):
        nbr = np.where(denominator != 0.0, numerator / denominator, 0.0)
    return np.clip(nbr, -1.0, 1.0)


def detect_index_change(
    pre_index: np.ndarray,
    post_index: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Calculates absolute and relative change between two temporal observations.

    Returns:
        (absolute_change, relative_drop) where:
        absolute_change = post_index - pre_index
        relative_drop = (pre_index - post_index) / max(0.001, pre_index)
    """
    pre = np.asarray(pre_index, dtype=np.float64)
    post = np.asarray(post_index, dtype=np.float64)
    abs_change = post - pre

    safe_pre = np.where(pre > 0.001, pre, 0.001)
    relative_drop = (pre - post) / safe_pre
    return abs_change, relative_drop
