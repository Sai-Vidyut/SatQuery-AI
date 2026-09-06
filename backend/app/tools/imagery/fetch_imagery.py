from app.adapters.imagery.factory import get_imagery_provider
from app.schemas.domain import FetchImageryInput, FetchImageryOutput, ImageryRequest
from app.tools.registry import Tool


class FetchImageryTool(Tool[FetchImageryInput, FetchImageryOutput]):
    name = "fetch_imagery"
    description = "Acquire satellite imagery metadata for an AOI and date range."
    input_model = FetchImageryInput
    output_model = FetchImageryOutput

    async def execute(self, payload: FetchImageryInput) -> FetchImageryOutput:
        provider = get_imagery_provider(demo_mode=payload.request.demo_mode)
        result = await provider.fetch(payload.request)
        return FetchImageryOutput(result=result)


async def fetch_imagery(request: ImageryRequest) -> FetchImageryOutput:
    tool = FetchImageryTool()
    return await tool.execute(FetchImageryInput(request=request))
