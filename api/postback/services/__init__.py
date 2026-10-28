"""
api.postback.services - Service layer for postback module.

This package provides business logic services for:
- Daily analytics and insights
- Rate limiting management
- Template processing and rendering
- Health monitoring and success rate tracking

Main services:
- PostbackInsightService: Daily analytics aggregation and anomaly detection
- RateLimitService: Per-network rate limiting and violation tracking
- TemplateService: Postback template management and rendering
- PostbackHealthService: Success rate monitoring and health metrics
"""

from .postback_insight_service import PostbackInsightService
from .rate_limit_service import RateLimitService
from .template_service import TemplateService
from .postback_health_service import PostbackHealthService

__all__ = [
    "PostbackInsightService",
    "RateLimitService", 
    "TemplateService",
    "PostbackHealthService",
]

# ── Core ingestion functions ───────────────────────────────────────────────────
# These live here (not in a sub-service) because they touch multiple models
# and are the main entry points called by webhooks.py and tasks.py.

import logging as _logging
_svc_logger = _logging.getLogger(__name__)


def receive_postback(
    network_key: str,
    raw_payload: dict,
    method: str,
    query_string: str,
    request_headers: dict,
    source_ip: str,
    signature: str,
    timestamp_str: str,
    nonce: str,
    body_bytes: bytes,
    path: str,
    query_params: dict,
):
    """
    Create a PostbackLog and dispatch to the Celery processing task.
    Returns the newly-created PostbackLog instance.

    This is the single entry-point called by PostbackWebhookView.
    All heavy validation/reward logic runs asynchronously in process_postback().
    """
    from ..models import NetworkPostbackConfig, PostbackLog
    from ..choices import PostbackStatus
    from ..exceptions import NetworkNotFoundException, NetworkInactiveException
    from ..tasks import process_postback as _task

    try:
        network = NetworkPostbackConfig.objects.get(network_key=network_key, status="active")
    except NetworkPostbackConfig.DoesNotExist:
        try:
            NetworkPostbackConfig.objects.get(network_key=network_key)
            raise NetworkInactiveException(f"Network '{network_key}' is inactive.")
        except NetworkPostbackConfig.DoesNotExist:
            raise NetworkNotFoundException(f"Network '{network_key}' not found.")


    # ── Sandbox mode guard ──────────────────────────────────────────────────
    if network.is_sandbox:
        log = PostbackLog.objects.create(
            network=network,
            status=PostbackStatus.VALIDATED,
            raw_payload=raw_payload,
            method=method,
            query_string=query_string,
            request_headers=request_headers,
            source_ip=source_ip,
            signature_verified=False,
            processing_error="SANDBOX MODE — reward and S2S callback suppressed",
        )
        _svc_logger.info(
            "Sandbox postback logged (no reward): log=%s network=%s",
            log.pk, network_key,
        )
        return log

    log = PostbackLog.objects.create(
        network=network,
        status=PostbackStatus.RECEIVED,
        raw_payload=raw_payload,
        method=method,
        query_string=query_string,
        request_headers=request_headers,
        source_ip=source_ip,
        signature_verified=False,
    )

    _task.delay(
        log_id=str(log.pk),
        signature=signature,
        timestamp_str=timestamp_str,
        nonce=nonce,
        body_bytes_hex=body_bytes.hex(),
        path=path,
        query_params=query_params,
    )

    _svc_logger.info("PostbackLog %s created for network=%s, task queued.", log.pk, network_key)
    return log


def process_postback_sync(log_id: str, **kwargs):
    """Synchronous version of the processing pipeline (used in tests / admin retry)."""
    from ..models import PostbackLog
    try:
        log = PostbackLog.objects.select_related("network").get(pk=log_id)
    except PostbackLog.DoesNotExist:
        _svc_logger.error("process_postback_sync: PostbackLog %s not found.", log_id)
        return None

    # Delegate to the full pipeline logic
    from ..logic import PostbackProcessingLogic
    processor = PostbackProcessingLogic()
    result = processor.process(log, **kwargs)
    return result


# ── Internal pipeline helpers (re-exported for backwards compatibility) ────────

def _check_rate_limit(network, source_ip: str) -> bool:
    """Return True if the request is within rate limits."""
    from ..models import PostbackRateLimit
    rl_configs = PostbackRateLimit.objects.filter(network=network, is_active=True)
    for rl in rl_configs:
        if rl.is_rate_exceeded(rl.current_count):
            return False
    return True


def _check_ip_enhanced(network, source_ip: str) -> bool:
    """Return True if source_ip passes whitelist check."""
    from ..models import PostbackIPWhitelist
    rules = PostbackIPWhitelist.objects.filter(network=network, is_active=True)
    if not rules.exists():
        return True  # No whitelist = allow all
    return any(rule.is_ip_allowed(source_ip) for rule in rules)


def _check_duplicate_lead(network, lead_id: str) -> bool:
    """Return True if this lead_id has already been processed (is a duplicate)."""
    from ..models import DuplicateLeadCheck
    from django.utils import timezone
    import datetime
    window_hours = network.dedup_window or 24
    since = timezone.now() - datetime.timedelta(hours=window_hours)
    return DuplicateLeadCheck.objects.filter(
        network=network, lead_id=lead_id, created_at__gte=since
    ).exists()


def _update_analytics(network, date=None):
    """Trigger async analytics aggregation for the given network+date."""
    from ..services import PostbackInsightService
    from django.utils import timezone
    PostbackInsightService.recalculate_daily_insight(network, date or timezone.now().date())


def _resolve_user(payload: dict, network):
    """Resolve the user from the postback payload field mapping."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user_field = network.field_mapping.get("user_id", "user_id")
    user_id = payload.get(user_field)
    if not user_id:
        return None
    try:
        return User.objects.get(pk=user_id)
    except (User.DoesNotExist, ValueError):
        return None


def _run_validators(log, network, payload: dict) -> list:
    """Run all LeadValidator rules for the network. Return list of rejection reasons."""
    from ..models import LeadValidator
    from ..choices import ValidatorStatus
    rejections = []
    for v in LeadValidator.objects.filter(network=network, status=ValidatorStatus.ACTIVE):
        passed, reason = v.evaluate(payload)
        if not passed:
            rejections.append(reason)
            if v.is_blocking:
                break
    return rejections


def _generate_integrity_hash(log) -> str:
    """Compute and return the integrity hash for a PostbackLog."""
    return log.generate_integrity_hash()


def _verify_signature(body_bytes: bytes, signature: str, network) -> bool:
    """Verify the HMAC/other signature for the incoming postback."""
    from ..utils.signature_validator import verify_signature
    return verify_signature(body_bytes, signature, network)


def _extract_request_data(request) -> dict:
    """Extract normalised payload from a Django request object."""
    import json
    if request.method == "POST":
        try:
            return json.loads(request.body)
        except Exception:
            return dict(request.POST)
    return dict(request.GET)
