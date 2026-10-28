"""
services.py – Backward-compatibility shim for the postback services package.

New code should import directly from the services sub-package:
    from api.postback.services import PostbackInsightService
    from api.postback.services import receive_postback

This shim re-exports everything so that legacy imports (e.g. from endpoint.py,
webhooks.py, admin scripts) continue to work without modification.
"""

from .services import (  # noqa: F401
    # Named service classes
    PostbackInsightService,
    TemplateService,
    RateLimitService,
    PostbackHealthService,

    # Core ingestion
    receive_postback,
    process_postback_sync,

    # Internal pipeline helpers
    _check_rate_limit,
    _check_ip_enhanced,
    _check_duplicate_lead,
    _update_analytics,
    _resolve_user,
    _run_validators,
    _generate_integrity_hash,
    _verify_signature,
    _extract_request_data,
)

__all__ = [
    "PostbackInsightService",
    "TemplateService",
    "RateLimitService",
    "PostbackHealthService",
    "receive_postback",
    "process_postback_sync",
    "_check_rate_limit",
    "_check_ip_enhanced",
    "_check_duplicate_lead",
    "_update_analytics",
    "_resolve_user",
    "_run_validators",
    "_generate_integrity_hash",
    "_verify_signature",
    "_extract_request_data",
]
