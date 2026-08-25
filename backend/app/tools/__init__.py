from app.tools.evidence.generate_evidence import GenerateEvidenceTool
from app.tools.imagery.fetch_imagery import FetchImageryTool
from app.tools.registry import ToolRegistry
from app.tools.temporal.detect_change import DetectChangeTool


def build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(FetchImageryTool())
    registry.register(DetectChangeTool())
    registry.register(GenerateEvidenceTool())
    return registry
