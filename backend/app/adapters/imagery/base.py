from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.domain import ImageryRequest, ImageryResult


class ImageryProvider(ABC):
  """Boundary for satellite imagery acquisition (Earth Engine, dev adapter, etc.)."""

  @property
  @abstractmethod
  def name(self) -> str:
    ...

  @abstractmethod
  async def fetch(self, request: ImageryRequest) -> ImageryResult:
    ...
