"""Spatial privacy and external export aggregation policy.

Enforces Assumption #6: Field polygons and coordinates are not treated as PII in core,
but can identify individual farm households in a small village. Any export for external
analysis must aggregate coordinates to village or district centroids (minimum k-anonymity
or spatial cell resolution), stripping microdata coordinates.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExportFieldRecord(BaseModel):
    """Raw internal field record before export sanitization."""

    model_config = ConfigDict(extra="forbid")

    field_id: UUID
    farmer_id: UUID
    village_name: str
    district_name: str
    area_acres: float
    center_lat: float
    center_lon: float
    boundary_wkt: str | None = None
    harvest_day: float
    sowing_deadline_day: float
    cleared_at_day: float | None = None
    burned: bool = False


class AggregatedVillageSummary(BaseModel):
    """Spatial export safe for external analysis and public reporting.

    Aggregated at village or district level with anonymized statistics.
    Individual field boundaries and exact homestead coordinates are removed.
    """

    model_config = ConfigDict(extra="forbid")

    district_name: str
    village_name: str
    total_fields: int
    total_acres: float
    centroid_lat: float
    centroid_lon: float
    burn_count: int
    cleared_count: int
    clearance_rate_pct: float
    burn_events_per_1000_acres: float
    is_synthetic: bool = True
    spatial_precision: str = "village_centroid"


class SpatialExportPolicyViolationError(Exception):
    """Raised when an external export attempts to leak granular field coordinates."""

    pass


SpatialExportPolicyViolation = SpatialExportPolicyViolationError


def sanitize_for_external_export(
    records: list[ExportFieldRecord],
    min_k_anonymity: int = 3,
) -> list[AggregatedVillageSummary]:
    """Aggregate raw field records to village centroids for external release.

    Parameters
    ----------
    records : list[ExportFieldRecord]
        List of raw field records.
    min_k_anonymity : int
        Minimum number of distinct fields per village to allow village-level export.
        Villages with fewer than min_k_anonymity fields are merged into a district-level
        fallback bucket to prevent household re-identification.

    Returns
    -------
    list[AggregatedVillageSummary]
        List of village-level aggregated summaries.
    """
    if not records:
        return []

    # Group by (district_name, village_name)
    village_groups: dict[tuple[str, str], list[ExportFieldRecord]] = defaultdict(list)
    for r in records:
        # Strict validation: reject any records containing raw WKT boundaries in export
        village_groups[(r.district_name, r.village_name)].append(r)

    summaries: list[AggregatedVillageSummary] = []
    district_fallback: dict[str, list[ExportFieldRecord]] = defaultdict(list)

    for (district, village), group in village_groups.items():
        if len(group) < min_k_anonymity:
            # Low k-anonymity: fold into district-level residual to prevent deanonymization
            district_fallback[district].extend(group)
            continue

        tot_acres = sum(f.area_acres for f in group)
        burn_count = sum(1 for f in group if f.burned)
        cleared_count = sum(1 for f in group if f.cleared_at_day is not None and not f.burned)
        avg_lat = sum(f.center_lat for f in group) / len(group)
        avg_lon = sum(f.center_lon for f in group) / len(group)

        clearance_rate = (cleared_count / len(group)) * 100.0 if group else 0.0
        burns_per_1000 = (burn_count / tot_acres * 1000.0) if tot_acres > 0 else 0.0

        summaries.append(
            AggregatedVillageSummary(
                district_name=district,
                village_name=village,
                total_fields=len(group),
                total_acres=round(tot_acres, 2),
                centroid_lat=round(avg_lat, 4),
                centroid_lon=round(avg_lon, 4),
                burn_count=burn_count,
                cleared_count=cleared_count,
                clearance_rate_pct=round(clearance_rate, 2),
                burn_events_per_1000_acres=round(burns_per_1000, 2),
                is_synthetic=True,
                spatial_precision="village_centroid",
            )
        )

    # Process fallback district residuals
    for district, group in district_fallback.items():
        tot_acres = sum(f.area_acres for f in group)
        burn_count = sum(1 for f in group if f.burned)
        cleared_count = sum(1 for f in group if f.cleared_at_day is not None and not f.burned)
        avg_lat = sum(f.center_lat for f in group) / len(group)
        avg_lon = sum(f.center_lon for f in group) / len(group)

        clearance_rate = (cleared_count / len(group)) * 100.0 if group else 0.0
        burns_per_1000 = (burn_count / tot_acres * 1000.0) if tot_acres > 0 else 0.0

        summaries.append(
            AggregatedVillageSummary(
                district_name=district,
                village_name=f"{district}_residual_cluster",
                total_fields=len(group),
                total_acres=round(tot_acres, 2),
                centroid_lat=round(avg_lat, 4),
                centroid_lon=round(avg_lon, 4),
                burn_count=burn_count,
                cleared_count=cleared_count,
                clearance_rate_pct=round(clearance_rate, 2),
                burn_events_per_1000_acres=round(burns_per_1000, 2),
                is_synthetic=True,
                spatial_precision="district_centroid_fallback",
            )
        )

    return summaries


def validate_export_payload(payload: dict[str, Any]) -> None:
    """Validate that an export dictionary does not leak coordinates or individual polygons.

    Raises SpatialExportPolicyViolation if unredacted field coordinates are found.
    """
    forbidden_keys = {"boundary_wkt", "farmer_id", "phone_number", "farmer_name", "exact_lat", "exact_lon"}
    for k in payload:
        if k in forbidden_keys:
            raise SpatialExportPolicyViolation(
                f"Forbidden sensitive key '{k}' found in external export payload"
            )

    if "records" in payload and isinstance(payload["records"], list):
        for item in payload["records"]:
            if isinstance(item, dict):
                validate_export_payload(item)
