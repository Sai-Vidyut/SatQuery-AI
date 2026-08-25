from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.domain import ChangeDetectionInput, ChangeDetectionOutput


class ChangeDetector(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def detect(self, payload: ChangeDetectionInput) -> ChangeDetectionOutput:
        ...
