from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.domain import SemanticAnalysisInput, SemanticAnalysisOutput


class SemanticAnalyzer(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def supported_claims(self) -> list[str]:
        ...

    @abstractmethod
    async def analyze(self, payload: SemanticAnalysisInput) -> SemanticAnalysisOutput:
        ...
