"""User-facing error messages keyed by machine-readable SatQuery error codes."""

from __future__ import annotations

USER_FACING_MESSAGES: dict[str, str] = {
    "no_imagery_found": (
        "No usable satellite imagery was found for the requested dates and AOI. "
        "Try different dates, widen the range, or adjust cloud-cover preferences."
    ),
    "no_imagery_after_cloud_filter": (
        "All candidate scenes were rejected by cloud filtering. "
        "Increase cloud_cover_max or choose different dates."
    ),
    "invalid_date_range": (
        "The earlier and later dates are not valid for this analysis. "
        "Ensure the earlier date is before the later date and both are after Sentinel-2 launch (2015-06-23)."
    ),
    "unsupported_date": (
        "One or both dates are outside the supported Sentinel-2 catalog range."
    ),
    "insufficient_valid_observations": (
        "Not enough valid observations were available to run change detection."
    ),
    "imagery_policy_unsupported": (
        "Imagery policy does not support this analysis mode for the selected dates."
    ),
    "policy_rejection": (
        "The request was rejected by imagery or analysis policy."
    ),
    "analysis_failed": (
        "Processing failed before a result could be produced. Check the execution trace for details."
    ),
    "input_validation_failed": (
        "Uploaded imagery did not pass validation. Review file format, overlap, and acquisition dates."
    ),
    "image_not_found": (
        "The referenced uploaded image was not found. Re-upload or check the image id."
    ),
    "change_detector_misconfigured": (
        "Change detector configuration is inconsistent with the imagery provider."
    ),
    "session_not_found": (
        "Analysis session not found. Submit a new query."
    ),
    "invalid_request": (
        "The request is missing required fields or uses an unsupported combination of inputs."
    ),
    "catalog_sar_unsupported": (
        "Catalog AOI optical+SAR fusion requires Earth Engine imagery. "
        "In development mode, use the Cross-modal upload workflow with separate optical and SAR images."
    ),
    "invalid_preview_bbox": "Preview bbox must be minx,miny,maxx,maxy in WGS84 degrees.",
    "preview_bbox_no_intersection": "The preview area does not overlap this image.",
    "invalid_preview_size": "Preview max_size must be between 64 and 2048.",
    "preview_render_failed": "Could not render an image preview for this crop.",
    "region_not_found": "The selected change region was not found in this analysis session.",
    "not_bi_temporal_session": "Region interpretation is only available for bi-temporal upload analyses.",
    "geochat_service_error": "GeoChat interpretation service returned an error.",
    "geochat_service_timeout": "GeoChat interpretation service timed out.",
    "geochat_vqa_misconfigured": "GeoChat interpretation is not configured for this environment.",
    "invalid_chat_message": "Chat message must not be empty.",
    "conversation_history_too_large": "This region conversation has reached its history limit.",
    "conversation_not_found": "Conversation state for this region was not found.",
    "geochat_malformed_response": "GeoChat returned a malformed response.",
}


def user_facing_message(code: str, fallback: str | None = None) -> str:
    return USER_FACING_MESSAGES.get(code, fallback or "Analysis failed.")
