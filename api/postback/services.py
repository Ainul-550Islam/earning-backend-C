"""
services.py – Postback module business logic.

Security-first design:
  • Every incoming postback runs through a fixed validation pipeline:
      1. IP check (if whitelist configured)
      2. Signature verification (HMAC)
      3. Required-field check
      4. Custom LeadValidator chain
      5. Deduplication check
      6. Payout cap enforcement
      7. User resolution
      8. Reward dispatch

  • Failures at any stage are logged to PostbackLog with a rejection reason
    and return a 200 OK to the network (prevent enumeration via status codes).
    The actual outcome is encoded in the response body.

  • SELECT FOR UPDATE is used when writing DuplicateLeadCheck to prevent
    race-condition duplicates.
"""
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from .choices import PostbackStatus, RejectionReason
from .constants import (
    MAX_PAYOUT_PER_POSTBACK,
    POSTBACK_RETRY_COUNTDOWN_SECONDS,
    STANDARD_FIELD_LEAD_ID,
    STANDARD_FIELD_OFFER_ID,
    STANDARD_FIELD_PAYOUT,
    STANDARD_FIELD_USER_ID,
    STANDARD_FIELD_TRANSACTION_ID,
    STANDARD_FIELD_CURRENCY,
)
from .exceptions import (
    DuplicateLeadException,
    FraudDetectedException,
    IPNotWhitelistedException,
    InvalidSignatureException,
    MissingRequiredFieldsException,
    NetworkInactiveException,
    NetworkNotFoundException,
    PayoutLimitExceededException,
    PostbackAlreadyProcessedException,
    RateLimitExceededException,
    SchemaValidationException,
    UserResolutionException,
)
from .models import DuplicateLeadCheck, NetworkPostbackConfig, PostbackLog
from .signals import (
    postback_received,
    postback_validated,
    postback_rejected,
    postback_rewarded,
    postback_duplicate,
    postback_failed,
)
from .validators import validate_required_postback_fields

logger = logging.getLogger(__name__)
User = get_user_model()


# ── Entry Point ───────────────────────────────────────────────────────────────

def receive_postback(
    *,
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
) -> PostbackLog:
    """
    Entry point – called synchronously from the webhook view.
    Creates a PostbackLog immediately, then dispatches async processing.
    Returns the log entry so the view can reply.
    """
    # Sanitise headers before persisting (strip auth/signature values)
    safe_headers = _sanitise_headers(request_headers)

    try:
        network = NetworkPostbackConfig.objects.get_by_key_or_raise(network_key)
    except (NetworkNotFoundException, NetworkInactiveException) as exc:
        logger.warning("Postback for unknown/inactive network_key=%r from ip=%s", network_key, source_ip)
        # Create a minimal rejected log even with no known network
        raise exc

    log = PostbackLog.objects.create(
        network=network,
        status=PostbackStatus.RECEIVED,
        raw_payload=raw_payload,
        method=method,
        query_string=query_string,
        request_headers=safe_headers,
        source_ip=source_ip or None,
        received_at=timezone.now(),
    )

    postback_received.send(sender=PostbackLog, instance=log)

    # Dispatch async processing
    from .tasks import process_postback
    process_postback.delay(
        str(log.pk),
        signature=signature,
        timestamp_str=timestamp_str,
        nonce=nonce,
        body_bytes_hex=body_bytes.hex(),
        path=path,
        query_params=query_params,
    )

    return log


def process_postback_sync(
    log: PostbackLog,
    *,
    signature: str,
    timestamp_str: str,
    nonce: str,
    body_bytes: bytes,
    path: str,
    query_params: dict,
) -> PostbackLog:
    """
    Synchronous processing pipeline. Called by the Celery task.
    Runs all validation stages in order.
    Any exception marks the log as rejected/failed and returns.
    """
    network = log.network
    payload = log.raw_payload

    try:
        # ─ Stage 1: IP Check ─────────────────────────────────────────────────
        ip_ok = _check_ip(log.source_ip, network)
        log.ip_whitelisted = ip_ok

        # ─ Stage 2: Signature ─────────────────────────────────────────────────
        if network.signature_algorithm != "none":
            _verify_signature(
                network=network,
                signature=signature,
                timestamp_str=timestamp_str,
                nonce=nonce,
                body_bytes=body_bytes,
                path=path,
                query_params=query_params,
            )
        log.signature_verified = True
        log.save(update_fields=["ip_whitelisted", "signature_verified", "updated_at"])

        # ─ Stage 3: Required Fields ───────────────────────────────────────────
        missing = validate_required_postback_fields(payload, network.required_fields)
        if missing:
            raise MissingRequiredFieldsException(missing_fields=missing)

        # ─ Stage 4: Extract Standard Fields ──────────────────────────────────
        lead_id = str(network.get_field(STANDARD_FIELD_LEAD_ID, payload) or "")
        offer_id = str(network.get_field(STANDARD_FIELD_OFFER_ID, payload) or "")
        user_id_raw = network.get_field(STANDARD_FIELD_USER_ID, payload)
        payout_raw = network.get_field(STANDARD_FIELD_PAYOUT, payload) or 0
        currency = str(network.get_field(STANDARD_FIELD_CURRENCY, payload) or "USD")
        transaction_id = str(network.get_field(STANDARD_FIELD_TRANSACTION_ID, payload) or "")

        try:
            payout = Decimal(str(payout_raw))
        except InvalidOperation:
            raise SchemaValidationException(errors={"payout": f"Invalid decimal: {payout_raw!r}"})

        # Update extracted fields on the log
        log.lead_id = lead_id
        log.offer_id = offer_id
        log.transaction_id = transaction_id
        log.payout = payout
        log.currency = currency
        log.save(update_fields=[
            "lead_id", "offer_id", "transaction_id", "payout", "currency", "updated_at"
        ])

        # ─ Stage 5: Custom LeadValidator Chain ───────────────────────────────
        _run_validators(network, payload, payout)

        # ─ Stage 6: Payout Cap ────────────────────────────────────────────────
        if payout > MAX_PAYOUT_PER_POSTBACK:
            raise PayoutLimitExceededException(
                detail=f"Payout {payout} exceeds cap of {MAX_PAYOUT_PER_POSTBACK}."
            )

        # ─ Stage 7: Duplicate Check ───────────────────────────────────────────
        if lead_id:
            _check_duplicate(log, network, lead_id)

        log.mark_validated()
        postback_validated.send(sender=PostbackLog, instance=log)

        # ─ Stage 8: User Resolution ───────────────────────────────────────────
        user = _resolve_user(user_id_raw, payload)
        log.resolved_user = user
        log.save(update_fields=["resolved_user", "updated_at"])

        # ─ Stage 9: Reward ────────────────────────────────────────────────────
        _dispatch_reward(log, network, offer_id, user)

    except (
        IPNotWhitelistedException,
        InvalidSignatureException,
        MissingRequiredFieldsException,
        SchemaValidationException,
        FraudDetectedException,
        PayoutLimitExceededException,
        UserResolutionException,
    ) as exc:
        reason = _exc_to_reason(exc)
        log.mark_rejected(reason=reason, detail=str(exc.detail))
        postback_rejected.send(sender=PostbackLog, instance=log, reason=reason)
        logger.warning(
            "Postback %s rejected: %s – %s", log.pk, reason, exc.detail
        )

    except DuplicateLeadException:
        log.mark_duplicate()
        postback_duplicate.send(sender=PostbackLog, instance=log)
        logger.info("Postback %s duplicate lead_id=%s", log.pk, log.lead_id)

    except Exception as exc:
        error_str = f"{type(exc).__name__}: {exc}"
        retry_idx = min(log.retry_count, len(POSTBACK_RETRY_COUNTDOWN_SECONDS) - 1)
        next_retry = timezone.now() + timezone.timedelta(
            seconds=POSTBACK_RETRY_COUNTDOWN_SECONDS[retry_idx]
        )
        log.mark_failed(error=error_str, next_retry_at=next_retry)
        postback_failed.send(sender=PostbackLog, instance=log, error=error_str)
        logger.exception("Postback %s failed with unexpected error: %s", log.pk, error_str)
        raise  # Re-raise so Celery can retry

    return log


# ── Private Helpers ───────────────────────────────────────────────────────────

def _sanitise_headers(headers: dict) -> dict:
    """Remove sensitive headers before persisting."""
    sensitive_prefixes = ("authorization", "x-postback-signature", "cookie", "x-api-key")
    return {
        k: v if not any(k.lower().startswith(p) for p in sensitive_prefixes) else "[REDACTED]"
        for k, v in headers.items()
    }


def _check_ip(source_ip: Optional[str], network: NetworkPostbackConfig) -> bool:
    """
    Return True if IP passes whitelist check.
    Raises IPNotWhitelistedException if whitelist is configured and IP is not in it.
    """
    from .utils.ip_checker import is_ip_in_whitelist
    whitelist = network.ip_whitelist
    if not whitelist:
        return True  # No whitelist = allow all
    if not source_ip:
        raise IPNotWhitelistedException(detail="Source IP could not be determined.")
    if not is_ip_in_whitelist(source_ip, whitelist):
        raise IPNotWhitelistedException(
            detail=f"IP {source_ip} is not in the whitelist for network '{network.network_key}'."
        )
    return True


def _verify_signature(
    *,
    network: NetworkPostbackConfig,
    signature: str,
    timestamp_str: str,
    nonce: str,
    body_bytes: bytes,
    path: str,
    query_params: dict,
) -> None:
    """Full signature + timestamp + nonce validation."""
    from .utils.signature_validator import validate_full_request
    validate_full_request(
        provided_signature=signature,
        timestamp_str=timestamp_str,
        nonce=nonce if network.require_nonce else "NONONCE",
        secret=network.secret_key,
        network_id=str(network.pk),
        algorithm=network.signature_algorithm,
        method="POST",
        path=path,
        query_params=query_params,
        body=body_bytes,
    )


def _run_validators(network: NetworkPostbackConfig, payload: dict, payout: Decimal) -> None:
    """Run the ordered LeadValidator chain. Raises on blocking failures."""
    validators = (
        network.lead_validators.filter(is_active=True).order_by("sort_order")
    )
    for validator in validators:
        try:
            _execute_validator(validator, payload, payout)
        except Exception as exc:
            if validator.is_blocking:
                reason = validator.failure_reason or RejectionReason.SCHEMA_VALIDATION
                raise SchemaValidationException(
                    errors={validator.name: str(exc)}
                ) from exc
            else:
                logger.warning(
                    "Non-blocking validator '%s' failed for network %s: %s",
                    validator.name, network.network_key, exc,
                )


def _execute_validator(validator, payload: dict, payout: Decimal) -> None:
    """Dispatch a single LeadValidator by type."""
    vtype = validator.validator_type
    params = validator.params or {}

    if vtype == "field_present":
        field = params.get("field", "")
        if not payload.get(field):
            raise ValueError(f"Required field '{field}' is missing or empty.")

    elif vtype == "field_regex":
        field = params.get("field", "")
        pattern = params.get("pattern", "")
        value = str(payload.get(field, ""))
        if not re.fullmatch(pattern, value):
            raise ValueError(
                f"Field '{field}' value {value!r} does not match pattern {pattern!r}."
            )

    elif vtype == "payout_range":
        min_p = Decimal(str(params.get("min", 0)))
        max_p = Decimal(str(params.get("max", MAX_PAYOUT_PER_POSTBACK)))
        if not (min_p <= payout <= max_p):
            raise ValueError(
                f"Payout {payout} is outside allowed range [{min_p}, {max_p}]."
            )

    elif vtype == "offer_whitelist":
        allowed = params.get("allowed_offers", [])
        offer = payload.get("offer_id") or payload.get("campaign_id", "")
        if allowed and str(offer) not in [str(o) for o in allowed]:
            raise ValueError(f"Offer '{offer}' is not in the allowed list.")

    elif vtype == "user_must_exist":
        user_field = params.get("field", STANDARD_FIELD_USER_ID)
        user_val = payload.get(user_field)
        if user_val and not User.objects.filter(pk=user_val).exists():
            raise ValueError(f"User '{user_val}' not found.")

    else:
        logger.debug("Unknown validator type '%s' – skipping.", vtype)


@transaction.atomic
def _check_duplicate(log: PostbackLog, network: NetworkPostbackConfig, lead_id: str) -> None:
    """
    Check dedup table. Raises DuplicateLeadException if already seen.
    Inserts a record if first time (SELECT FOR UPDATE + INSERT to avoid races).
    """
    # Fast path: check managers layer first (no lock)
    if DuplicateLeadCheck.objects.is_duplicate(network, lead_id):
        raise DuplicateLeadException(
            detail=f"Lead '{lead_id}' already processed for network '{network.network_key}'."
        )

    # Slow path: lock and re-check + insert atomically
    try:
        DuplicateLeadCheck.objects.select_for_update().get(
            network=network, lead_id=lead_id
        )
        # If we get here, it was inserted between our check and the lock
        raise DuplicateLeadException(
            detail=f"Lead '{lead_id}' duplicate (race condition caught)."
        )
    except DuplicateLeadCheck.DoesNotExist:
        DuplicateLeadCheck.objects.create(
            network=network,
            lead_id=lead_id,
            postback_log=log,
        )


def _resolve_user(user_id_raw, payload: dict):
    """
    Attempt to find the Django user from user_id_raw.
    Returns the user or raises UserResolutionException.
    """
    if user_id_raw is None:
        return None  # Optional user resolution
    try:
        return User.objects.get(pk=user_id_raw)
    except (User.DoesNotExist, ValueError, TypeError):
        raise UserResolutionException(
            detail=f"Could not resolve user from value: {user_id_raw!r}"
        )


def _dispatch_reward(
    log: PostbackLog,
    network: NetworkPostbackConfig,
    offer_id: str,
    user,
) -> None:
    """Award points and/or items based on the network's reward rules."""
    if user is None:
        log.mark_rejected(
            reason=RejectionReason.USER_NOT_FOUND,
            detail="No user resolved; cannot award reward.",
        )
        return

    reward_config = network.get_reward_for_offer(offer_id)
    points = reward_config.get("points", 0)
    item_id = reward_config.get("item_id")

    inventory_id = None

    if item_id:
        try:
            from inventory.services import award_item_to_user
            from inventory.choices import DeliveryMethod
            inv = award_item_to_user(
                user=user,
                item_id=item_id,
                delivery_method=DeliveryMethod.IN_APP,
                postback_reference=str(log.pk),
            )
            inventory_id = inv.pk
        except Exception as exc:
            logger.error(
                "Failed to award item %s for postback %s: %s", item_id, log.pk, exc
            )

    log.mark_rewarded(points=points, inventory_id=inventory_id)
    postback_rewarded.send(sender=PostbackLog, instance=log, points=points)
    logger.info(
        "Postback %s rewarded user %s with %d points (offer=%s)",
        log.pk, user.pk, points, offer_id,
    )


def _exc_to_reason(exc) -> str:
    """Map exception type to a RejectionReason choice value."""
    from .exceptions import (
        IPNotWhitelistedException, InvalidSignatureException,
        MissingRequiredFieldsException, SchemaValidationException,
        FraudDetectedException, PayoutLimitExceededException, UserResolutionException,
        SignatureExpiredException,
    )
    mapping = {
        IPNotWhitelistedException: RejectionReason.IP_NOT_WHITELISTED,
        InvalidSignatureException: RejectionReason.INVALID_SIGNATURE,
        SignatureExpiredException: RejectionReason.SIGNATURE_EXPIRED,
        MissingRequiredFieldsException: RejectionReason.MISSING_FIELDS,
        SchemaValidationException: RejectionReason.SCHEMA_VALIDATION,
        FraudDetectedException: RejectionReason.FRAUD_DETECTED,
        PayoutLimitExceededException: RejectionReason.PAYOUT_LIMIT_EXCEEDED,
        UserResolutionException: RejectionReason.USER_NOT_FOUND,
    }
    return mapping.get(type(exc), RejectionReason.INTERNAL_ERROR)
