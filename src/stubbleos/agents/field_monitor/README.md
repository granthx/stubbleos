# Field Monitor Agent

The **Field Monitor Agent** analyzes Sentinel-2 L2A optical satellite imagery and NASA FIRMS active fire detections to determine the real-time ground state of agricultural fields throughout the paddy harvesting and wheat sowing season.

## Responsibilities
- Classifies each field into one of four mutually exclusive states:
  - `NOT_HARVESTED`: Standing green crop.
  - `HARVESTED_RESIDUE_PRESENT`: Significant drop in NDVI indicating harvest with straw on field.
  - `CLEARED`: High Bare Soil Index (BSI) indicating baling, raking, or in-situ sowing completed.
  - `BURN_DETECTED`: Active thermal anomaly detected by satellite (VIIRS/MODIS) or steep burn ratio drop.
- Calculates an empirical confidence score for each observation.
- Escalates ambiguous or low-confidence observations ($< \text{threshold}$) to the human coordinator's approval queue.
- Emits typed `FieldStateChanged` and `BurnDetected` events on the event bus.

## Remote Sensing Pipeline
- **STAC Client**: Sentinel-2 L2A scene metadata via Earth Search / Planetary Computer with automatic offline fallback to committed fixtures.
- **NASA FIRMS Client**: Active fire thermal hotspots with spatial polygon buffering.
- **Indices**:
  - $\text{NDVI} = \frac{\text{NIR} - \text{Red}}{\text{NIR} + \text{Red}}$
  - $\text{BSI} = \frac{(\text{SWIR} + \text{Red}) - (\text{NIR} + \text{Blue})}{(\text{SWIR} + \text{Red}) + (\text{NIR} + \text{Blue})}$
  - $\text{NBR} = \frac{\text{NIR} - \text{SWIR}}{\text{NIR} + \text{SWIR}}$
