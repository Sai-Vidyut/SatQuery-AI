from __future__ import annotations

import asyncio

from app.adapters.imagery.base import ImageryProvider
from app.adapters.imagery.earth_engine.client import EarthEngineClient
from app.adapters.imagery.earth_engine.constants import (
    SELECTION_POLICY_VERSION,
    SENTINEL1_GRD_COLLECTION,
    SENTINEL1_POLARIZATIONS,
    SENTINEL1_RESOLUTION_M,
    SENTINEL1_SELECTION_POLICY_VERSION,
    SENTINEL2_RESOLUTION_M,
    SENTINEL2_SR_COLLECTION,
)
from app.adapters.imagery.earth_engine.geometry import bbox_from_geometry, geojson_to_ee_geometry
from app.adapters.imagery.earth_engine.seasonality import build_seasonality_provenance
from app.adapters.imagery.earth_engine.sentinel1 import (
    query_sentinel1_scenes,
    scene_has_polarizations,
    select_s1_anchor_scenes,
)
from app.adapters.imagery.earth_engine.selection import select_anchor_scenes
from app.adapters.imagery.earth_engine.sentinel2 import SceneCandidate, query_sentinel2_scenes
from app.core.errors import SatQueryError
from app.schemas.domain import (
    DataMode,
    ImageryRequest,
    ImageryResult,
    ImageryScene,
    SensorType,
    SpatialMetadata,
)


class EarthEngineProvider(ImageryProvider):
    """
    Google Earth Engine adapter for Sentinel-2 and Sentinel-1 imagery acquisition.
    All EE-specific logic stays in app.adapters.imagery.earth_engine.*.
    """

    def __init__(self, client: EarthEngineClient | None = None) -> None:
        self._client = client

    @property
    def name(self) -> str:
        return "earth_engine"

    def _get_client(self) -> EarthEngineClient:
        if self._client is None:
            self._client = EarthEngineClient.initialize()
        return self._client

    async def fetch(self, request: ImageryRequest) -> ImageryResult:
        if request.sensor not in (SensorType.SENTINEL_2, SensorType.SENTINEL_1):
            raise SatQueryError(
                "unsupported_sensor",
                f"Earth Engine provider supports Sentinel-1 and Sentinel-2 only. "
                f"Requested: {request.sensor.value}.",
                status_code=400,
                field="sensor",
            )

        return await asyncio.to_thread(self._fetch_sync, request)

    def _fetch_sync(self, request: ImageryRequest) -> ImageryResult:
        if request.sensor == SensorType.SENTINEL_2:
            return self._fetch_sentinel2(request)
        return self._fetch_sentinel1(request)

    def _fetch_sentinel2(self, request: ImageryRequest) -> ImageryResult:
        client = self._get_client()
        ee = client.ee

        aoi_geom = geojson_to_ee_geometry(ee, request.aoi.geometry)
        bbox = bbox_from_geometry(request.aoi.geometry)

        candidates = query_sentinel2_scenes(
            client=client,
            ee=ee,
            aoi_geometry=aoi_geom,
            start_date=request.start_date,
            end_date=request.end_date,
            cloud_cover_max=request.preferences.cloud_cover_max,
        )

        selected = select_anchor_scenes(
            candidates,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        scenes = [_candidate_to_scene(c) for c in selected]
        seasonality = build_seasonality_provenance(
            requested_start=request.start_date,
            requested_end=request.end_date,
            selected_dates=[s.acquisition_date for s in scenes],
            selection_policy=SELECTION_POLICY_VERSION,
        )

        return ImageryResult(
            source="google-earth-engine",
            mode=DataMode.EARTH_ENGINE,
            sensor=SensorType.SENTINEL_2,
            collection_id=SENTINEL2_SR_COLLECTION,
            scenes=scenes,
            spatial=SpatialMetadata(bbox=bbox, resolution_m=SENTINEL2_RESOLUTION_M),
            provider_metadata={
                "provider": "earth_engine",
                "project": client.project,
                "selection_policy": SELECTION_POLICY_VERSION,
                "candidate_count": len(candidates),
                "selected_count": len(scenes),
                "cloud_cover_max": request.preferences.cloud_cover_max,
                "seasonality": seasonality,
            },
            message=None,
        )

    def _fetch_sentinel1(self, request: ImageryRequest) -> ImageryResult:
        client = self._get_client()
        ee = client.ee

        aoi_geom = geojson_to_ee_geometry(ee, request.aoi.geometry)
        bbox = bbox_from_geometry(request.aoi.geometry)

        candidates = query_sentinel1_scenes(
            client=client,
            ee=ee,
            aoi_geometry=aoi_geom,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        selected = select_s1_anchor_scenes(
            candidates,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        scenes = [_candidate_to_scene(c) for c in selected]
        polarization_availability = {
            pol: all(scene_has_polarizations(s).get(pol, False) for s in selected)
            for pol in SENTINEL1_POLARIZATIONS
        }
        relative_orbit = selected[0].metadata.get("relative_orbit") if selected else None

        return ImageryResult(
            source="google-earth-engine",
            mode=DataMode.EARTH_ENGINE,
            sensor=SensorType.SENTINEL_1,
            collection_id=SENTINEL1_GRD_COLLECTION,
            scenes=scenes,
            spatial=SpatialMetadata(bbox=bbox, resolution_m=SENTINEL1_RESOLUTION_M),
            provider_metadata={
                "provider": "earth_engine",
                "project": client.project,
                "selection_policy": SENTINEL1_SELECTION_POLICY_VERSION,
                "candidate_count": len(candidates),
                "selected_count": len(scenes),
                "relative_orbit": relative_orbit,
                "polarizations": list(SENTINEL1_POLARIZATIONS),
                "polarization_availability": polarization_availability,
            },
            message=None,
        )


def _candidate_to_scene(candidate: SceneCandidate) -> ImageryScene:
    return ImageryScene(
        scene_id=candidate.scene_id,
        acquisition_date=candidate.acquisition_date,
        cloud_cover_percent=round(candidate.cloud_cover_percent, 2),
        preview_url=None,
        platform_id=candidate.platform_id,
        metadata=candidate.metadata,
    )
