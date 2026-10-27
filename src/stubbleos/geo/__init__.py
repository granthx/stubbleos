"""Geospatial module: STAC client, NASA FIRMS client, Open-Meteo weather client, and raster utilities."""

from stubbleos.geo.client import CachedResponse, CachingGeoClient
from stubbleos.geo.firms import FirmsFireHit, FirmsSearchResult, NasaFirmsClient
from stubbleos.geo.indices import (
    compute_bsi,
    compute_nbr,
    compute_ndvi,
    detect_index_change,
)
from stubbleos.geo.raster import (
    RasterGrid,
    compute_zonal_stats,
    create_synthetic_field_raster,
)
from stubbleos.geo.stac import (
    Sentinel2Scene,
    Sentinel2StacClient,
    Sentinel2StacSearchResult,
)
from stubbleos.geo.weather import (
    DailyWeatherForecast,
    OpenMeteoClient,
    WeatherForecastResult,
)

__all__ = [
    "CachedResponse",
    "CachingGeoClient",
    "DailyWeatherForecast",
    "FirmsFireHit",
    "FirmsSearchResult",
    "NasaFirmsClient",
    "OpenMeteoClient",
    "RasterGrid",
    "Sentinel2Scene",
    "Sentinel2StacClient",
    "Sentinel2StacSearchResult",
    "WeatherForecastResult",
    "compute_bsi",
    "compute_nbr",
    "compute_ndvi",
    "compute_zonal_stats",
    "create_synthetic_field_raster",
    "detect_index_change",
]
