"""GeoChat single-image VQA specialist tool."""

from __future__ import annotations

from app.adapters.imagery.uploaded.factory import get_uploaded_imagery_provider
from app.adapters.rsvlm.base import RemoteSensingVLM
from app.adapters.rsvlm.factory import get_geochat_vlm
from app.schemas.vqa import GeoChatVQAInput, GeoChatVQAOutput


class GeoChatVQATool:
    name = "geochat_vqa"
    description = "Run remote-sensing VQA on a single uploaded image via GeoChat-7B."

    def __init__(self, vlm: RemoteSensingVLM | None = None) -> None:
        self._vlm = vlm

    @property
    def vlm(self) -> RemoteSensingVLM:
        return self._vlm or get_geochat_vlm()

    async def execute(self, payload: GeoChatVQAInput) -> GeoChatVQAOutput:
        provider = get_uploaded_imagery_provider()
        image = provider.get(payload.image.id)
        result = await self.vlm.run_vqa(
            image=image,
            question=payload.question,
            parameters=payload.parameters,
        )
        return GeoChatVQAOutput(result=result)
