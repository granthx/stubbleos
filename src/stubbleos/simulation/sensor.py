"""Synthetic satellite and thermal sensor model with controllable noise for Field Monitor evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import numpy as np

from stubbleos.agents.field_monitor.schemas import FieldObservationRequest
from stubbleos.core.types import FieldState


@dataclass
class SensorConfig:
    """Noise parameters for synthetic satellite and thermal fire sensing."""

    cloud_cover_prob: float = 0.10
    thermal_false_positive_prob: float = 0.02
    thermal_false_negative_prob: float = 0.05
    ndvi_noise_std: float = 0.02
    bsi_noise_std: float = 0.02


@dataclass
class SyntheticObservation:
    field_id: UUID
    ground_truth_state: FieldState
    observed_ndvi: float | None
    observed_bsi: float | None
    has_thermal_hotspot: bool
    firms_confidence_pct: float
    is_cloud_obscured: bool


class DistrictSensorModel:
    """Simulates satellite passes and FIRMS detections over fields with controllable noise."""

    def __init__(self, config: SensorConfig | None = None) -> None:
        self.config = config or SensorConfig()

    def generate_observation(
        self,
        field_id: UUID,
        ground_truth_state: FieldState,
        rng: np.random.Generator,
    ) -> SyntheticObservation:
        """Generates noisy optical reflectance and thermal signals from ground truth."""
        cfg = self.config
        is_cloud_obscured = bool(rng.uniform() < cfg.cloud_cover_prob)

        # Baseline ground truth spectral characteristics
        if ground_truth_state == FieldState.NOT_HARVESTED:
            true_ndvi = 0.72
            true_bsi = -0.25
        elif ground_truth_state == FieldState.HARVESTED_RESIDUE_PRESENT:
            true_ndvi = 0.30
            true_bsi = 0.02
        elif ground_truth_state == FieldState.CLEARED:
            true_ndvi = 0.20
            true_bsi = 0.26
        elif ground_truth_state == FieldState.BURN_DETECTED:
            true_ndvi = 0.12
            true_bsi = 0.28
        else:
            true_ndvi = 0.50
            true_bsi = 0.0

        if is_cloud_obscured:
            obs_ndvi = None
            obs_bsi = None
        else:
            obs_ndvi = float(np.clip(rng.normal(true_ndvi, cfg.ndvi_noise_std), -1.0, 1.0))
            obs_bsi = float(np.clip(rng.normal(true_bsi, cfg.bsi_noise_std), -1.0, 1.0))

        # Thermal fire detection model
        has_thermal = False
        firms_conf = 0.0

        if ground_truth_state == FieldState.BURN_DETECTED:
            # True fire event: detected unless false negative
            if rng.uniform() >= cfg.thermal_false_negative_prob:
                has_thermal = True
                firms_conf = float(np.clip(rng.normal(88.0, 6.0), 55.0, 99.0))
        else:
            # Non-fire event: false positive thermal noise (e.g. brick kiln or industrial heat)
            if rng.uniform() < cfg.thermal_false_positive_prob:
                has_thermal = True
                firms_conf = float(np.clip(rng.normal(62.0, 10.0), 50.0, 85.0))

        return SyntheticObservation(
            field_id=field_id,
            ground_truth_state=ground_truth_state,
            observed_ndvi=obs_ndvi,
            observed_bsi=obs_bsi,
            has_thermal_hotspot=has_thermal,
            firms_confidence_pct=firms_conf,
            is_cloud_obscured=is_cloud_obscured,
        )

    def to_observation_request(
        self,
        obs: SyntheticObservation,
        previous_state: FieldState = FieldState.NOT_HARVESTED,
    ) -> FieldObservationRequest:
        """Converts sensor observation into Field Monitor request schema."""
        return FieldObservationRequest(
            field_id=obs.field_id,
            previous_state=previous_state,
            pre_harvest_ndvi=0.72,
            current_ndvi=obs.observed_ndvi,
            current_bsi=obs.observed_bsi,
            has_firms_hotspot=obs.has_thermal_hotspot,
            firms_confidence_pct=obs.firms_confidence_pct,
            source="sensor_model_synthetic",
        )

    @staticmethod
    def calculate_accuracy_metrics(
        ground_truth: list[FieldState],
        detected: list[FieldState],
    ) -> dict[str, float]:
        """Calculates multi-class accuracy, plus burn-detection precision, recall, and F1."""
        if len(ground_truth) != len(detected) or not ground_truth:
            return {"overall_accuracy": 0.0, "burn_precision": 0.0, "burn_recall": 0.0, "burn_f1": 0.0}

        total = len(ground_truth)
        correct = sum(1 for gt, dt in zip(ground_truth, detected, strict=False) if gt == dt)
        overall_accuracy = correct / total

        # Burn detection confusion matrix
        tp = sum(
            1
            for gt, dt in zip(ground_truth, detected, strict=False)
            if gt == FieldState.BURN_DETECTED and dt == FieldState.BURN_DETECTED
        )
        fp = sum(
            1
            for gt, dt in zip(ground_truth, detected, strict=False)
            if gt != FieldState.BURN_DETECTED and dt == FieldState.BURN_DETECTED
        )
        fn = sum(
            1
            for gt, dt in zip(ground_truth, detected, strict=False)
            if gt == FieldState.BURN_DETECTED and dt != FieldState.BURN_DETECTED
        )

        burn_precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        burn_recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        burn_f1 = (
            (2 * burn_precision * burn_recall) / (burn_precision + burn_recall)
            if (burn_precision + burn_recall) > 0
            else 0.0
        )

        return {
            "overall_accuracy": round(overall_accuracy, 4),
            "burn_precision": round(burn_precision, 4),
            "burn_recall": round(burn_recall, 4),
            "burn_f1": round(burn_f1, 4),
            "true_positives": float(tp),
            "false_positives": float(fp),
            "false_negatives": float(fn),
        }
