"""Mock ground-level context contracts for bi-temporal change regions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MOCK_GROUND_DISCLOSURE = (
    "This ground-level context is demonstration data and is not real Street View imagery."
)

GroundSceneCategory = Literal[
    "vegetation_loss",
    "built_up_increase",
    "water_shrinkage",
    "flood",
    "generic_change",
]


class GroundContextLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float
    longitude: float


class GroundContextScene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: GroundSceneCategory
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    features: list[str] = Field(min_length=1)


class GroundContextImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    alt: str = Field(min_length=1)


class GroundContextProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["mock_ground_context"] = "mock_ground_context"
    source_type: Literal["mock"] = "mock"
    status: Literal["demonstration_data"] = "demonstration_data"
    real_world_imagery: Literal[False] = False
    disclosure: str = MOCK_GROUND_DISCLOSURE


class GroundContextResult(BaseModel):
    """Deterministic mock ground context — contextual demo data, not authoritative evidence."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    region_id: str
    location: GroundContextLocation
    heading: float = Field(ge=0, lt=360)
    capture_date: str
    scene: GroundContextScene
    image: GroundContextImage
    provenance: GroundContextProvenance
