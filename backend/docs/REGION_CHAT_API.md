# Region Chat API — Frontend Contract

Evidence-scoped conversational follow-up for an **already-detected** bi-temporal change region.

GeoChat interprets supplied Before/After evidence. It does **not** run new detection.

---

## Endpoint

```
POST /api/v1/query/{session_id}/regions/{region_id}/chat
```

### Path parameters

| Name | Description |
|------|-------------|
| `session_id` | Analysis session from `POST /api/v1/query/submit` |
| `region_id` | Selected `EvidenceRegion.id` from the session result |

### Request body

Only the user message is accepted. **Do not send** detector, geometry, confidence, dates, or image IDs.

```json
{
  "message": "Why do you think this is vegetation loss?"
}
```

Validation:
- `message`: required, 1–4000 characters
- extra fields rejected (`422`)

### Success response

```json
{
  "success": true,
  "data": {
    "chat": {
      "task": "bi_temporal_region_chat",
      "answer": "...",
      "session_id": "...",
      "region_id": "change-region-01",
      "conversation_id": "...",
      "turn_id": "...",
      "turn_index": 0,
      "message": "Why do you think this is vegetation loss?",
      "detector": "uploaded_bi_temporal",
      "region_confidence": 0.47,
      "confidence_kind": "histogram_separability",
      "change_direction_hint": "vegetation_loss",
      "model_name": "development-mock-geochat",
      "model_version": "0.0.0-dev",
      "provider": "development",
      "provenance": "...",
      "confidence_available": false,
      "inference_metadata": {
        "evidence_inputs": "before_after_composite_crop",
        "preview_bbox_wgs84": "...",
        "geochat_called": true,
        "scope_guard": false
      },
      "preview_bbox_wgs84": "...",
      "evidence_inputs": "before_after_composite_crop",
      "scope_limited": false,
      "conversation": {
        "conversation_id": "...",
        "session_id": "...",
        "region_id": "change-region-01",
        "turns": [
          {
            "turn_id": "...",
            "turn_index": 0,
            "user_message": "...",
            "assistant_answer": "...",
            "created_at": "2026-09-08T09:00:00Z"
          }
        ]
      }
    },
    "trace_step": {
      "tool_name": "geochat_region_chat",
      "metadata": {
        "session_id": "...",
        "region_id": "...",
        "conversation_id": "...",
        "turn_id": "...",
        "provider": "development",
        "model_name": "...",
        "evidence_inputs": "before_after_composite_crop"
      }
    }
  }
}
```

---

## Provider badge mapping

| `provider` | UI badge |
|------------|----------|
| `development` | **DEVELOPMENT MOCK** |
| `geochat_service` | **REAL GeoChat-7B** |

Use `inference_metadata.geochat_called`:
- `false` + `scope_limited=true` → scope guard answer (no GeoChat inference)
- `true` → normal GeoChat turn

Never infer provider from answer text alone.

---

## Conversation semantics

- Scoped to **`session_id + region_id`**
- First message creates `conversation_id`
- Follow-up messages append turns in order (`turn_index` 0-based)
- Different region → independent conversation
- New analysis session → new `session_id` → no shared history
- In-memory only (lost on backend restart)
- Limits: **10 turns** / region, **8000 chars** total history

---

## Region scoping / out-of-scope messages

Requests like “find other changed areas”, “analyze the whole city”, or “what happened somewhere else?” return:

- `scope_limited: true`
- `inference_metadata.geochat_called: false`
- A clear message that a **new analysis** is required

Deterministic detection, evidence regions, and Before/After previews are unchanged.

---

## Errors

| HTTP | Code | Meaning |
|------|------|---------|
| 404 | `session_not_found` | Unknown session |
| 404 | `region_not_found` | Region not in session evidence |
| 422 | `not_bi_temporal_session` | Session is not bi-temporal upload |
| 422 | `invalid_chat_message` | Empty/invalid message |
| 422 | `conversation_history_too_large` | Turn/history limit exceeded |
| 502 | `geochat_service_error` | Remote GeoChat error |
| 504 | `geochat_service_timeout` | Remote GeoChat timeout |
| 502 | `geochat_malformed_response` | Remote GeoChat malformed payload |
| 500 | `geochat_vqa_misconfigured` | Real provider selected without URL |
| 500 | `conversation_not_found` | Internal conversation state loss |

AI failures do **not** modify `evidence[]`, detection metrics, or Before/After data.

---

## Example — first turn

```http
POST /api/v1/query/{session_id}/regions/change-region-01/chat
Content-Type: application/json

{
  "message": "Why do you think this is vegetation loss?"
}
```

---

## Example — follow-up turn

Same endpoint/path. Backend loads prior turns automatically.

```json
{
  "message": "Does the change look concentrated along field edges?"
}
```

Response includes full `conversation.turns` history for UI rendering.

---

## Related endpoint

One-shot interpretation (non-conversational):

```
POST /api/v1/query/{session_id}/regions/{region_id}/interpret
```

Use **interpret** for the first structured answer button; use **chat** for follow-up conversation.
