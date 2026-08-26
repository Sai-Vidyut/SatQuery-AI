"""GeoChat single-image scene description / caption specialist tool."""

from __future__ import annotations

from app.adapters.imagery.uploaded.factory import get_uploaded_imagery_provider
from app.adapters.rsvlm.base import RemoteSensingVLM
from app.adapters.rsvlm.factory import get_geochat_vlm
from app.schemas.vqa import GeoChatCaptionInput, GeoChatCaptionOutput


class GeoChatCaptionTool:
    name = "geochat_caption"
    description = "Run remote-sensing scene description on a single uploaded image via GeoChat-7B."

    def __init__(self, vlm: RemoteSensingVLM | None = None) -> None:
        self._vlm = vlm

    @property
    def vlm(self) -> RemoteSensingVLM:
        return self._vlm or get_geochat_vlm()

    async def execute(self, payload: GeoChatCaptionInput) -> GeoChatCaptionOutput:
        provider = get_uploaded_imagery_provider()
        image = provider.get(payload.image.id)
        result = await self.vlm.run_caption(
            image=image,
            user_request=payload.user_request,
            parameters=payload.parameters,
        )
        return GeoChatCaptionOutput(result=result)
