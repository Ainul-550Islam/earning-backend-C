"""
services.py – Core business logic for Postback Engine.

Processing Pipeline (per incoming postback):
  1. Network Resolution   → get AdNetworkConfig
  2. IP Whitelist Check   → reject if not allowed
  3. Signature Verify     → reject if HMAC invalid
  4. Schema Validation    → reject if required fields missing
  5. Fraud Pre-Check      → fast blacklist / velocity check
  6. Deduplication        → reject if lead_id seen before
  7. User Resolution      → find user from click_id or user_id
  8. Payout Cap           → reject if exceeds safety limit
  9. Conversion Create    → write Conversion record
  10. Reward Dispatch     → credit user's wallet
"""
import hashlib
import hmac
import logging
import secrets
import uuid
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from .constants import (
    MAX_PAYOUT_PER_POSTBACK,
    MAX_PAYOUT_USD_PER_CONVERSION,
    CLICK_ID_LENGTH,
    CLICK_EXPIRY_HOURS,
    FIELD_CLICK_ID,
    FIELD_LEAD_ID,
    FIELD_OFFER_ID,
    FIELD_PAYOUT,
    FIELD_CURRENCY,
    FIELD_TRANSACTION_ID,
    FIELD_USER_ID,
)
from .enums import (
    ClickStatus,
    ConversionStatus,
    PostbackStatus,
    RejectionReason,
    NetworkStatus,
    QueuePriority,
)
from .exceptions import (
    BlacklistedSourceException,
    ClickExpiredException,
    ClickNotFoundException,
    DuplicateConversionException,
    DuplicateLeadException,
    FraudDetectedException,
    IPNotWhitelistedException,
    InvalidSignatureException,
    MaxRetriesExceededException,
    MissingRequiredFieldsException,
    NetworkInactiveException,
    NetworkNotFoundException,
    OfferInactiveException,
    PayoutLimitExceededException,
    PostbackProcessingException,
    RewardDispatchException,
    SchemaValidationException,
    SignatureExpiredException,
    UserNotFoundException,
    UserResolutionException,
)
from .models import (
    AdNetworkConfig,
    ClickLog,
    Conversion,
    ConversionDeduplication,
    FraudAttemptLog,
    HourlyStat,
    NetworkPerformance,
    PostbackQueue,
    PostbackRawLog,
    RetryLog,
)
from .signals import (
    postback_received,
    postback_validated,
    postback_rejected,
    postback_rewarded,
    postback_duplicate,
    postback_failed,
    conversion_created,
    click_tracked,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# ══════════════════════════════════════════════════════════════════════════════
# Postback Reception & Processing
# ══════════════════════════════════════════════════════════════════════════════

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
) -> PostbackRawLog:
    """
    Entry point: receive and log an incoming postback.

    Creates a PostbackRawLog immediately (so nothing is lost),
    then queues async processing via Celery.

    Returns the raw log so the view can respond immediately.
    """
    safe_headers = _sanitise_headers(request_headers)

    # Step 1: resolve network config (fast path — may fail)
    try:
        network = AdNetworkConfig.objects.get_by_key_or_raise(network_key)
    except (NetworkNotFoundException, NetworkInactiveException) as exc:
        logger.warning(
            "Postback for unknown/inactive network_key=%r from ip=%s",
            network_key, source_ip,
        )
        # Create a minimal log even without a known network
        raw_log = PostbackRawLog.objects.create(
            network_id=None,
            raw_payload=raw_payload,
            http_method=method,
            query_string=query_string,
            request_headers=safe_headers,
            source_ip=source_ip,
            status=PostbackStatus.REJECTED,
            rejection_reason=RejectionReason.SCHEMA_VALIDATION,
            rejection_detail=str(exc),
        )
        return raw_log

    # Step 2: extract standard fields via adapter mapping
    lead_id = network.get_mapped_field(FIELD_LEAD_ID, raw_payload) or ""
    click_id = network.get_mapped_field(FIELD_CLICK_ID, raw_payload) or ""
    offer_id = network.get_mapped_field(FIELD_OFFER_ID, raw_payload) or ""
    transaction_id = (
        network.get_mapped_field(FIELD_TRANSACTION_ID, raw_payload)
        or str(uuid.uuid4())
    )
    payout_raw = network.get_mapped_field(FIELD_PAYOUT, raw_payload) or "0"
    currency = network.get_mapped_field(FIELD_CURRENCY, raw_payload) or "USD"

    try:
        payout = Decimal(str(payout_raw))
    except (InvalidOperation, TypeError):
        payout = Decimal("0")

    # Step 3: create raw log (write-once audit record)
    raw_log = PostbackRawLog.objects.create(
        tenant=network.tenant,
        network=network,
        raw_payload=raw_payload,
        http_method=method,
        query_string=query_string,
        request_headers=safe_headers,
        source_ip=source_ip,
        lead_id=lead_id,
        click_id=click_id,
        offer_id=offer_id,
        transaction_id=transaction_id,
        payout=payout,
        currency=currency,
        status=PostbackStatus.RECEIVED,
    )

    # Fire signal
    postback_received.send(sender=PostbackRawLog, raw_log=raw_log)

    # Step 4: dispatch async processing
    from .tasks import process_postback_task
    process_postback_task.apply_async(
        args=[str(raw_log.id)],
        kwargs={"signature": signature, "timestamp_str": timestamp_str, "nonce": nonce},
        countdown=0,
    )

    logger.info(
        "Postback received: raw_log=%s network=%s lead=%s",
        raw_log.id, network_key, lead_id,
    )
    return raw_log


def process_postback(
    raw_log: PostbackRawLog,
    *,
    signature: str = "",
    timestamp_str: str = "",
    nonce: str = "",
) -> Optional[Conversion]:
    """
    Full validation and reward pipeline.
    Called asynchronously by Celery worker.

    Returns a Conversion on success, None on rejection.
    Raises PostbackProcessingException on unexpected errors.
    """
    network = raw_log.network
    raw_log.mark_processing()

    try:
        # ── Gate 1: IP Whitelist ──────────────────────────────────────────────
        _check_ip_whitelist(network, raw_log.source_ip)
        raw_log.ip_whitelisted = True
        raw_log.save(update_fields=["ip_whitelisted"])

        # ── Gate 2: Signature ─────────────────────────────────────────────────
        _verify_signature(
            network=network,
            raw_payload=raw_log.raw_payload,
            signature=signature,
            timestamp_str=timestamp_str,
            nonce=nonce,
        )
        raw_log.signature_verified = True
        raw_log.save(update_fields=["signature_verified"])

        # ── Gate 3: Required Fields ───────────────────────────────────────────
        _validate_required_fields(network, raw_log.raw_payload)

        # ── Gate 4: Blacklist Check ───────────────────────────────────────────
        _check_blacklist(raw_log.source_ip, network)

        # ── Gate 5: Deduplication ─────────────────────────────────────────────
        _check_deduplication(network, raw_log.lead_id, raw_log)

        # ── Gate 6: User Resolution ───────────────────────────────────────────
        user = _resolve_user(network, raw_log)

        # ── Gate 7: Payout Cap ────────────────────────────────────────────────
        _check_payout_cap(raw_log.payout)

        # ── Gate 8: Create Conversion ─────────────────────────────────────────
        conversion = _create_conversion(raw_log=raw_log, user=user, network=network)

        # ── Gate 9: Dispatch Reward ───────────────────────────────────────────
        _dispatch_reward(conversion=conversion, network=network)

        # Mark raw log as rewarded
        raw_log.mark_rewarded(
            points=conversion.points_awarded,
            usd=conversion.actual_payout,
        )
        raw_log.resolved_user = user
        raw_log.save(update_fields=["resolved_user"])

        postback_rewarded.send(
            sender=PostbackRawLog,
            raw_log=raw_log,
            conversion=conversion,
        )

        # ── Update Analytics ──────────────────────────────────────────────────
        _update_hourly_stats(network, conversion)

        logger.info(
            "Postback rewarded: raw_log=%s user=%s points=%d",
            raw_log.id, user.id, conversion.points_awarded,
        )
        return conversion

    except DuplicateLeadException as exc:
        raw_log.mark_duplicate()
        postback_duplicate.send(sender=PostbackRawLog, raw_log=raw_log)
        return None

    except (
        IPNotWhitelistedException,
        InvalidSignatureException,
        SignatureExpiredException,
        MissingRequiredFieldsException,
        BlacklistedSourceException,
        FraudDetectedException,
        PayoutLimitExceededException,
        UserResolutionException,
        UserNotFoundException,
        OfferInactiveException,
        SchemaValidationException,
    ) as exc:
        reason = _map_exception_to_rejection_reason(exc)
        raw_log.mark_rejected(reason=reason, detail=str(exc))
        postback_rejected.send(
            sender=PostbackRawLog, raw_log=raw_log, reason=reason, exc=exc,
        )
        logger.warning(
            "Postback rejected: raw_log=%s reason=%s detail=%s",
            raw_log.id, reason, str(exc),
        )
        return None

    except Exception as exc:
        raw_log.mark_failed(error=str(exc))
        postback_failed.send(sender=PostbackRawLog, raw_log=raw_log, exc=exc)
        logger.exception("Unexpected error processing postback=%s", raw_log.id)
        raise PostbackProcessingException(detail=str(exc)) from exc


# ══════════════════════════════════════════════════════════════════════════════
# Click Tracking
# ══════════════════════════════════════════════════════════════════════════════

def generate_click(
    *,
    user,
    network: AdNetworkConfig,
    offer_id: str,
    offer_name: str = "",
    ip_address: str = "",
    user_agent: str = "",
    device_type: str = "unknown",
    country: str = "",
    sub_id: str = "",
    referrer: str = "",
    metadata: dict = None,
) -> ClickLog:
    """
    Generate a new ClickLog when a user clicks an offer.
    Returns the ClickLog with a unique click_id.
    """
    click_id = _generate_click_id()
    expiry = timezone.now() + timezone.timedelta(hours=CLICK_EXPIRY_HOURS)

    click_log = ClickLog.objects.create(
        tenant=network.tenant,
        click_id=click_id,
        user=user,
        network=network,
        offer_id=offer_id,
        offer_name=offer_name,
        ip_address=ip_address or None,
        user_agent=user_agent,
        device_type=device_type,
        country=country,
        sub_id=sub_id,
        referrer=referrer,
        expires_at=expiry,
        status=ClickStatus.VALID,
        metadata=metadata or {},
    )

    click_tracked.send(sender=ClickLog, click_log=click_log)

    logger.debug("Click generated: %s | user=%s | offer=%s", click_id, user.id, offer_id)
    return click_log


def resolve_click(click_id: str) -> ClickLog:
    """
    Fetch and validate a ClickLog for conversion attribution.
    Raises ClickNotFoundException or ClickExpiredException.
    """
    click_log = ClickLog.objects.get_by_click_id(click_id)
    if click_log is None:
        raise ClickNotFoundException(f"No click found with id '{click_id}'.")
    if click_log.is_expired:
        raise ClickExpiredException(
            f"Click '{click_id}' expired at {click_log.expires_at}."
        )
    if click_log.is_fraud:
        raise FraudDetectedException(
            f"Click '{click_id}' is flagged as fraud.",
            fraud_type=click_log.fraud_type,
        )
    return click_log


# ══════════════════════════════════════════════════════════════════════════════
# Signature Utilities
# ══════════════════════════════════════════════════════════════════════════════

def generate_signature(
    network: AdNetworkConfig,
    payload: dict,
    timestamp: str = "",
    nonce: str = "",
) -> str:
    """Generate an HMAC signature for a postback payload."""
    message = _build_signature_message(payload, timestamp, nonce)
    return _compute_hmac(network.secret_key, message, network.signature_algorithm)


def verify_signature(
    network: AdNetworkConfig,
    payload: dict,
    provided_signature: str,
    timestamp: str = "",
    nonce: str = "",
) -> bool:
    """Constant-time HMAC signature verification."""
    expected = generate_signature(network, payload, timestamp, nonce)
    return hmac.compare_digest(
        expected.encode("utf-8"),
        provided_signature.encode("utf-8"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Analytics Helpers
# ══════════════════════════════════════════════════════════════════════════════

def get_network_stats(network: AdNetworkConfig, date=None) -> dict:
    """Return aggregated stats for a network on a given date."""
    from .models import NetworkPerformance
    date = date or timezone.now().date()
    try:
        perf = NetworkPerformance.objects.get(network=network, date=date)
        return {
            "date": str(perf.date),
            "clicks": perf.total_clicks,
            "conversions": perf.approved_conversions,
            "conversion_rate": round(perf.conversion_rate, 2),
            "revenue_usd": float(perf.total_payout_usd),
            "fraud_rate": round(perf.fraud_rate, 2),
        }
    except NetworkPerformance.DoesNotExist:
        return {
            "date": str(date),
            "clicks": 0,
            "conversions": 0,
            "conversion_rate": 0.0,
            "revenue_usd": 0.0,
            "fraud_rate": 0.0,
        }


# ══════════════════════════════════════════════════════════════════════════════
# Private Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _check_ip_whitelist(network: AdNetworkConfig, source_ip: str):
    """Reject if network has IP whitelist and source_ip is not in it."""
    if not network.ip_whitelist:
        return  # empty = allow all
    if not source_ip:
        raise IPNotWhitelistedException("No source IP provided.")
    import ipaddress
    try:
        ip_obj = ipaddress.ip_address(source_ip)
        for entry in network.ip_whitelist:
            if "/" in entry:
                if ip_obj in ipaddress.ip_network(entry, strict=False):
                    return
            else:
                if ip_obj == ipaddress.ip_address(entry):
                    return
    except ValueError:
        raise IPNotWhitelistedException(f"Invalid IP address: {source_ip}")
    raise IPNotWhitelistedException(
        f"Source IP {source_ip} not in whitelist for network {network.network_key}."
    )


def _verify_signature(
    network: AdNetworkConfig,
    raw_payload: dict,
    signature: str,
    timestamp_str: str,
    nonce: str,
):
    """HMAC signature validation with replay attack prevention."""
    from .enums import SignatureAlgorithm
    if network.signature_algorithm == SignatureAlgorithm.NONE:
        return  # IP-only networks skip signature check

    if not signature:
        raise InvalidSignatureException("No signature provided.")

    # Timestamp replay check
    if timestamp_str:
        from .constants import SIGNATURE_TOLERANCE_SECONDS
        try:
            ts = float(timestamp_str)
            age = abs(timezone.now().timestamp() - ts)
            if age > SIGNATURE_TOLERANCE_SECONDS:
                raise SignatureExpiredException(
                    f"Timestamp is {age:.0f}s old (max {SIGNATURE_TOLERANCE_SECONDS}s)."
                )
        except (ValueError, TypeError):
            raise InvalidSignatureException("Invalid timestamp format.")

    expected = generate_signature(network, raw_payload, timestamp_str, nonce)
    if not hmac.compare_digest(
        expected.encode("utf-8"),
        signature.encode("utf-8"),
    ):
        raise InvalidSignatureException("Signature mismatch.")


def _validate_required_fields(network: AdNetworkConfig, payload: dict):
    """Check all required fields are present in the payload."""
    missing = []
    for field in network.required_fields:
        mapped = network.field_mapping.get(field, field)
        if not payload.get(mapped):
            missing.append(field)
    if missing:
        raise MissingRequiredFieldsException(
            f"Missing required fields: {', '.join(missing)}",
            missing_fields=missing,
        )


def _check_blacklist(source_ip: str, network: AdNetworkConfig):
    """Check source IP against blacklist."""
    if not source_ip:
        return
    from .models import IPBlacklist
    from .enums import BlacklistType
    if IPBlacklist.objects.is_blacklisted(source_ip, BlacklistType.IP):
        raise BlacklistedSourceException(f"IP {source_ip} is blacklisted.")


def _check_deduplication(network: AdNetworkConfig, lead_id: str, raw_log: PostbackRawLog):
    """Atomic deduplication check using SELECT FOR UPDATE."""
    if not lead_id:
        return
    with transaction.atomic():
        _, created = ConversionDeduplication.objects.record(
            network=network,
            lead_id=lead_id,
            raw_log=raw_log,
            transaction_id=raw_log.transaction_id,
        )
        if not created:
            raise DuplicateLeadException(
                f"Lead '{lead_id}' already processed for network '{network.network_key}'."
            )


def _resolve_user(network: AdNetworkConfig, raw_log: PostbackRawLog):
    """
    Try to find the user this conversion belongs to.
    Resolution order:
      1. click_id → ClickLog.user
      2. user_id / sub_id from payload
    """
    # 1. Try via click_id
    if raw_log.click_id:
        click_log = ClickLog.objects.get_by_click_id(raw_log.click_id)
        if click_log and click_log.user:
            return click_log.user

    # 2. Try via user_id in payload
    user_id = network.get_mapped_field("user_id", raw_log.raw_payload)
    if user_id:
        try:
            return User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError):
            pass

    # 3. sub_id might be user.id in some networks
    sub_id = network.get_mapped_field("sub_id", raw_log.raw_payload)
    if sub_id:
        try:
            return User.objects.get(pk=sub_id)
        except (User.DoesNotExist, ValueError):
            pass

    raise UserResolutionException(
        f"Cannot resolve user for postback {raw_log.id}. "
        f"click_id={raw_log.click_id!r}, user_id={user_id!r}"
    )


def _check_payout_cap(payout: Decimal):
    """Reject if payout exceeds safety cap."""
    if payout > MAX_PAYOUT_USD_PER_CONVERSION:
        raise PayoutLimitExceededException(
            f"Payout {payout} exceeds cap {MAX_PAYOUT_USD_PER_CONVERSION}.",
            payout=payout,
            limit=MAX_PAYOUT_USD_PER_CONVERSION,
        )


@transaction.atomic
def _create_conversion(
    raw_log: PostbackRawLog,
    user,
    network: AdNetworkConfig,
) -> Conversion:
    """Create the authoritative Conversion record."""
    reward = network.get_reward_for_offer(raw_log.offer_id)
    points = reward.get("points", 0)
    reward_usd = Decimal(str(reward.get("usd", raw_log.payout)))

    # Resolve attribution
    click_log = None
    time_to_convert = None
    if raw_log.click_id:
        click_log = ClickLog.objects.get_by_click_id(raw_log.click_id)
        if click_log:
            delta = timezone.now() - click_log.clicked_at
            time_to_convert = int(delta.total_seconds())

    try:
        conversion = Conversion.objects.create(
            tenant=network.tenant,
            raw_log=raw_log,
            click_log=click_log,
            network=network,
            user=user,
            lead_id=raw_log.lead_id,
            click_id=raw_log.click_id,
            offer_id=raw_log.offer_id,
            transaction_id=raw_log.transaction_id,
            network_payout=raw_log.payout,
            actual_payout=reward_usd,
            currency=raw_log.currency,
            points_awarded=points,
            time_to_convert_seconds=time_to_convert,
            source_ip=raw_log.source_ip,
            status=ConversionStatus.APPROVED,
            approved_at=timezone.now(),
        )
    except IntegrityError:
        raise DuplicateConversionException(
            f"Conversion for transaction_id={raw_log.transaction_id} already exists."
        )

    # Mark click as converted
    if click_log:
        click_log.mark_converted()

    # Record dedup
    ConversionDeduplication.objects.filter(
        network=network, lead_id=raw_log.lead_id
    ).update(conversion=conversion)

    conversion_created.send(sender=Conversion, conversion=conversion)
    return conversion


def _dispatch_reward(conversion: Conversion, network: AdNetworkConfig):
    """
    Credit the user's wallet.
    Wrapped in try-except so a wallet error doesn't lose the conversion record.
    """
    if network.is_test_mode:
        logger.info("TEST MODE: skipping reward for conversion=%s", conversion.id)
        return

    try:
        from api.wallet.services import credit_from_conversion
        wallet_tx = credit_from_conversion(
            user=conversion.user,
            amount=conversion.actual_payout,
            points=conversion.points_awarded,
            source="postback_engine",
            ref_id=str(conversion.id),
            description=f"CPA Reward: {conversion.offer_id} via {conversion.network.name}",
        )
        conversion.mark_wallet_credited(wallet_transaction_id=wallet_tx.id)
    except Exception as exc:
        # Don't fail the whole pipeline for a wallet error — queue for retry
        logger.error(
            "Wallet credit failed for conversion=%s: %s", conversion.id, exc,
        )
        RetryLog.objects.create(
            retry_type="reward",
            object_id=conversion.id,
            attempt_number=1,
            error_message=str(exc),
        )
        raise RewardDispatchException(
            f"Wallet credit failed: {exc}", detail=str(exc)
        ) from exc


def _update_hourly_stats(network: AdNetworkConfig, conversion: Conversion):
    """Increment hourly counters (non-blocking; failure is logged not raised)."""
    try:
        stat = HourlyStat.objects.get_or_create_current(network)
        HourlyStat.objects.filter(pk=stat.pk).update(
            conversions=models.F("conversions") + 1,
            payout_usd=models.F("payout_usd") + conversion.actual_payout,
            points_awarded=models.F("points_awarded") + conversion.points_awarded,
        )
    except Exception as exc:
        logger.warning("Failed to update hourly stats: %s", exc)


def _generate_click_id() -> str:
    """Generate a cryptographically secure click ID."""
    return secrets.token_urlsafe(CLICK_ID_LENGTH)


def _build_signature_message(payload: dict, timestamp: str, nonce: str) -> str:
    """Build the message string to sign."""
    import urllib.parse
    sorted_params = sorted(payload.items())
    query = urllib.parse.urlencode(sorted_params)
    parts = [query]
    if timestamp:
        parts.append(f"ts={timestamp}")
    if nonce:
        parts.append(f"nonce={nonce}")
    return "&".join(parts)


def _compute_hmac(secret: str, message: str, algorithm: str) -> str:
    """Compute HMAC with the given algorithm."""
    from .enums import SignatureAlgorithm
    algo_map = {
        SignatureAlgorithm.HMAC_SHA256: hashlib.sha256,
        SignatureAlgorithm.HMAC_SHA512: hashlib.sha512,
        SignatureAlgorithm.HMAC_MD5:    hashlib.md5,
        SignatureAlgorithm.MD5:         hashlib.md5,
    }
    algo = algo_map.get(algorithm, hashlib.sha256)
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        algo,
    ).hexdigest()


def _sanitise_headers(headers: dict) -> dict:
    """Remove sensitive headers before storage."""
    REDACT_KEYS = {
        "authorization", "x-postback-signature", "x-api-key",
        "cookie", "x-auth-token", "x-secret",
    }
    return {
        k: ("***REDACTED***" if k.lower() in REDACT_KEYS else v)
        for k, v in headers.items()
    }


def _map_exception_to_rejection_reason(exc: Exception) -> str:
    """Map a raised exception to a RejectionReason string."""
    from .exceptions import (
        IPNotWhitelistedException, InvalidSignatureException,
        SignatureExpiredException, MissingRequiredFieldsException,
        BlacklistedSourceException, FraudDetectedException,
        PayoutLimitExceededException, UserResolutionException,
        UserNotFoundException, OfferInactiveException,
        SchemaValidationException,
    )
    mapping = {
        IPNotWhitelistedException:   RejectionReason.IP_NOT_WHITELISTED,
        InvalidSignatureException:   RejectionReason.INVALID_SIGNATURE,
        SignatureExpiredException:   RejectionReason.SIGNATURE_EXPIRED,
        MissingRequiredFieldsException: RejectionReason.MISSING_FIELDS,
        BlacklistedSourceException:  RejectionReason.BLACKLISTED,
        FraudDetectedException:      RejectionReason.FRAUD_DETECTED,
        PayoutLimitExceededException: RejectionReason.PAYOUT_LIMIT_EXCEEDED,
        UserResolutionException:     RejectionReason.USER_NOT_FOUND,
        UserNotFoundException:       RejectionReason.USER_NOT_FOUND,
        OfferInactiveException:      RejectionReason.OFFER_INACTIVE,
        SchemaValidationException:   RejectionReason.SCHEMA_VALIDATION,
    }
    for exc_type, reason in mapping.items():
        if isinstance(exc, exc_type):
            return reason
    return RejectionReason.INTERNAL_ERROR


# needed for F() in _update_hourly_stats
from django.db import models
