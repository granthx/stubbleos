# Field Monitor Agent (Phase 4 Skeleton)

## Purpose
The Field Monitor agent ingests optical satellite imagery (Sentinel-2 NDVI) and thermal fire anomaly feeds (NASA FIRMS / VIIRS) to detect harvest progression and stubble burn incidents across agricultural fields.

## Typed Contract
- Input: `FieldMonitorInput` (district, field IDs, observation window).
- Output: `FieldMonitorOutput` (satellite observations, counts of newly harvested and burned fields).
- State: `FieldMonitorState`.

## Tools
- `sentinel2_harvest_detector_mock`: Simulates vegetative index changes indicating crop harvest.
- `firms_thermal_anomaly_detector_mock`: Simulates thermal hotspot detection for burn tracking.
