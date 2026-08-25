from __future__ import annotations

from app.adapters.semantic.base import SemanticAnalyzer
from app.adapters.semantic.factory import get_semantic_analyzer
from app.schemas.domain import SemanticAnalysisInput, SemanticAnalysisOutput
from app.tools.registry import Tool


class AnalyzeSemanticsTool(Tool[SemanticAnalysisInput, SemanticAnalysisOutput]):
    name = "analyze_semantics"
    description = "Analyze semantic/object evidence for specialist query profiles."
    input_model = SemanticAnalysisInput
    output_model = SemanticAnalysisOutput

    def __init__(self, analyzer: SemanticAnalyzer | None = None) -> None:
        self._analyzer = analyzer

    async def execute(self, payload: SemanticAnalysisInput) -> SemanticAnalysisOutput:
        analyzer = self._analyzer or get_semantic_analyzer(payload.imagery.mode)
        return await analyzer.analyze(payload)
