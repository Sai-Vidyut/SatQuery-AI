"""Groq-backed general assistant for non-geospatial region chat follow-ups."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

import httpx

from app.core.config import get_settings
from app.core.errors import SatQueryError
from app.services.session_store import ConversationTurn

_GREETING_RE = re.compile(r"^(hi|hello|hey|good (?:morning|afternoon|evening))\b", re.I)

GROQ_DEMO_FALLBACK_CODES = frozenset(
    {
        "groq_not_configured",
        "groq_service_timeout",
        "groq_service_error",
        "groq_misconfigured",
    }
)

GROQ_API_BASE = "https://api.groq.com/openai/v1"

GROQ_SYSTEM_PROMPT = (
    "You are the general-purpose assistant for SatQuery-AI.\n"
    "Reply in clear, natural language.\n\n"
    "Handle general knowledge, programming concepts, writing help, and ordinary conversational questions.\n\n"
    "If the user asks about the selected satellite region, satellite imagery, detected changes, evidence, "
    "confidence, before/after imagery, or other geospatial analysis, do NOT pretend to know the answer. "
    "Tell them that satellite-region questions are handled by the GeoChat evidence assistant in SatQuery-AI.\n\n"
    "Do not claim to have inspected satellite imagery or authoritative change detection output."
)

GENERAL_ASSISTANT_PROVENANCE = (
    "SatQuery general assistant via Groq — no satellite evidence supplied for this turn."
)


@dataclass(frozen=True)
class GroqCompletionResult:
    answer: str
    model_name: str
    model_version: str
    provenance: str
    inference_metadata: dict[str, object]


class DevelopmentGroqAssistant:
    """Deterministic general assistant for local development and automated tests."""

    provider_kind = "groq"

    async def complete(
        self,
        message: str,
        *,
        prior_turns: list[ConversationTurn],
    ) -> GroqCompletionResult:
        settings = get_settings()
        cleaned = message.strip()
        if _GREETING_RE.search(cleaned):
            answer = (
                "Hi! I'm the general assistant for SatQuery. I can help with everyday questions. "
                "For questions about the selected satellite region or its evidence, ask GeoChat."
            )
        else:
            snippet = cleaned[:120]
            answer = (
                f"[development mock — not Groq API] General assistant reply for: {snippet}. "
                "This response is not grounded in satellite imagery."
            )
        return GroqCompletionResult(
            answer=answer,
            model_name=settings.groq_model,
            model_version="0.0.0-dev",
            provenance=GENERAL_ASSISTANT_PROVENANCE + " [development mock]",
            inference_metadata={
                "groq_called": False,
                "development_mock": True,
                "prior_turn_count": len(prior_turns),
            },
        )


class GroqApiAssistant:
    """Production Groq OpenAI-compatible chat completions client."""

    provider_kind = "groq"

    async def complete(
        self,
        message: str,
        *,
        prior_turns: list[ConversationTurn],
    ) -> GroqCompletionResult:
        settings = get_settings()
        if not settings.groq_api_key:
            raise SatQueryError(
                "groq_not_configured",
                "Groq is not configured. Set GROQ_API_KEY in backend/.env for general assistant questions.",
                status_code=503,
            )

        messages: list[dict[str, str]] = [{"role": "system", "content": GROQ_SYSTEM_PROMPT}]
        for turn in prior_turns:
            messages.append({"role": "user", "content": turn.user_message})
            messages.append({"role": "assistant", "content": turn.assistant_answer})
        messages.append({"role": "user", "content": message.strip()})

        payload = {
            "model": settings.groq_model,
            "messages": messages,
            "temperature": 0.4,
        }

        try:
            async with httpx.AsyncClient(timeout=settings.groq_timeout_s) as client:
                response = await client.post(
                    f"{GROQ_API_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise SatQueryError(
                "groq_service_timeout",
                "Groq general assistant request timed out.",
                status_code=504,
            ) from exc
        except httpx.HTTPError as exc:
            raise SatQueryError(
                "groq_service_error",
                "Groq general assistant request failed.",
                status_code=502,
            ) from exc

        if response.status_code >= 400:
            raise SatQueryError(
                "groq_service_error",
                "Groq general assistant returned an error.",
                status_code=502 if response.status_code < 500 else 503,
            )

        try:
            body = response.json()
            answer = body["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise SatQueryError(
                "groq_service_error",
                "Groq general assistant returned a malformed response.",
                status_code=502,
            ) from exc

        if not answer:
            raise SatQueryError(
                "groq_service_error",
                "Groq general assistant returned an empty answer.",
                status_code=502,
            )

        return GroqCompletionResult(
            answer=answer,
            model_name=settings.groq_model,
            model_version=str(body.get("model") or settings.groq_model),
            provenance=GENERAL_ASSISTANT_PROVENANCE,
            inference_metadata={
                "groq_called": True,
                "development_mock": False,
                "prior_turn_count": len(prior_turns),
            },
        )


async def complete_general_assistant(
    message: str,
    *,
    prior_turns: list[ConversationTurn],
) -> GroqCompletionResult:
    """Use Groq when configured; otherwise deterministic demo mock without surfacing provider errors."""
    assistant = get_groq_assistant()
    if isinstance(assistant, DevelopmentGroqAssistant):
        return await assistant.complete(message, prior_turns=prior_turns)
    try:
        return await assistant.complete(message, prior_turns=prior_turns)
    except SatQueryError as exc:
        if exc.code not in GROQ_DEMO_FALLBACK_CODES:
            raise
        fallback = await DevelopmentGroqAssistant().complete(message, prior_turns=prior_turns)
        return GroqCompletionResult(
            answer=fallback.answer,
            model_name=fallback.model_name,
            model_version=fallback.model_version,
            provenance=fallback.provenance,
            inference_metadata={
                **fallback.inference_metadata,
                "groq_fallback": True,
                "groq_error_code": exc.code,
            },
        )


@lru_cache
def get_groq_assistant() -> DevelopmentGroqAssistant | GroqApiAssistant:
    settings = get_settings()
    provider = settings.groq_provider.lower()
    if provider == "development":
        return DevelopmentGroqAssistant()
    if provider == "groq_api":
        return GroqApiAssistant()
    raise SatQueryError(
        "groq_misconfigured",
        f"Unsupported GROQ_PROVIDER: {settings.groq_provider}. Use development or groq_api.",
        status_code=500,
    )
