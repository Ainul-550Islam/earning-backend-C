"""
postback_handlers/base_handler.py
──────────────────────────────────
Abstract base class for all postback handlers.

Every CPA network's postback flows through this pipeline:
  1. resolve_network()      → Load AdNetworkConfig
  2. parse_raw_payload()    → Normalise + expand macros
  3. validate_security()    → IP whitelist + HMAC signature
  4. validate_schema()      → Pydantic model check → 422 on bad data
  5. check_fraud_pre()      → Blacklist + velocity check
  6. check_deduplication()  → Redis + DB idempotency lock
  7. resolve_user()         → click_id / sub_id / user_id lookup
  8. validate_business()    → Payout cap + offer active + conv window
  9. create_conversion()    → Atomic DB write
  10. dispatch_reward()     → Wallet credit
  11. post_process()        → Analytics + webhooks + signals
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone

from ..constants import (
    FRAUD_SCORE_THRESHOLD_FLAG,
    MAX_PAYOUT_USD_PER_CONVERSION,
)
from ..enums import (
    PostbackStatus,
    RejectionReason,
)
from ..exceptions import (
    BlacklistedSourceException,
    DuplicateLeadException,
    FraudDetectedException,
    IPNotWhitelistedException,
    InvalidSignatureException,
    MissingRequiredFieldsException,
    NetworkInactiveException,
    NetworkNotFoundException,
    OfferInactiveException,
    PayoutLimitExceededException,
    PostbackProcessingException,
    RewardDispatchException,
    SchemaValidationException,
    UserResolutionException,
    VelocityLimitException,
)
from ..models import AdNetworkConfig, PostbackRawLog
from ..signals import (
    postback_duplicate,
    postback_failed,
    postback_received,
    postback_rejected,
    postback_rewarded,
)

logger = logging.getLogger(__name__)


# ── Typed result container ─────────────────────────────────────────────────────

@dataclass
class PostbackContext:
    """
    Mutable context object passed through the entire handler pipeline.
    Each stage reads from and writes to this object.
    """
    # Inputs (set at entry)
    network_key: str = ""
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    method: str = "GET"
    query_string: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    source_ip: str = ""
    signature: str = ""
    timestamp_str: str = ""
    nonce: str = ""
    body_bytes: bytes = b""

    # Resolved during pipeline
    network: Optional[AdNetworkConfig] = None
    raw_log: Optional[PostbackRawLog] = None
    normalised: Dict[str, Any] = field(default_factory=dict)

    # Extracted standard fields
    lead_id: str = ""
    click_id: str = ""
    offer_id: str = ""
    transaction_id: str = ""
    payout: Decimal = Decimal("0")
    currency: str = "USD"
    goal_id: str = ""
    status_raw: str = ""          # raw status value from network (e.g. "1", "approved")
    status_normalised: str = ""   # our normalised status (e.g. "approved", "rejected")

    # Resolution results
    user: Any = None              # Django User instance
    click_log: Any = None

    # Security results
    ip_whitelisted: bool = False
    signature_verified: bool = False

    # Fraud results
    fraud_score: float = 0.0
    fraud_signals: list = field(default_factory=list)

    # Output
    conversion: Any = None
    rejection_reason: str = ""
    rejection_detail: str = ""


@dataclass
class HandlerResult:
    success: bool
    status: str              # "rewarded" | "rejected" | "duplicate" | "failed"
    raw_log_id: Optional[str] = None
    conversion_id: Optional[str] = None
    rejection_reason: str = ""
    detail: str = ""


# ── Base Handler ───────────────────────────────────────────────────────────────

class BasePostbackHandler(ABC):
    """
    Abstract base class. Subclasses override adapter-specific methods.
    The execute() method is the single public entry point.
    """

    # ── Override these in subclasses ──────────────────────────────────────────

    @property
    @abstractmethod
    def network_key(self) -> str:
        """The network key this handler handles (e.g. 'cpalead')."""

    @abstractmethod
    def get_adapter(self):
        """Return the network adapter instance."""

    # ── Optional hooks (override for custom network behaviour) ────────────────

    def pre_validate_hook(self, ctx: PostbackContext) -> None:
        """Called before security validation. Override to add custom checks."""

    def post_reward_hook(self, ctx: PostbackContext) -> None:
        """Called after successful reward dispatch."""

    def on_rejection_hook(self, ctx: PostbackContext) -> None:
        """Called on any rejection."""

    # ── Main entry point ──────────────────────────────────────────────────────

    def execute(
        self,
        raw_payload: dict,
        method: str,
        query_string: str,
        headers: dict,
        source_ip: str,
        signature: str = "",
        timestamp_str: str = "",
        nonce: str = "",
        body_bytes: bytes = b"",
    ) -> HandlerResult:
        """
        Run the full 11-step processing pipeline.
        Always returns a HandlerResult — never raises to the caller.
        """
        ctx = PostbackContext(
            network_key=self.network_key,
            raw_payload=raw_payload,
            method=method,
            query_string=query_string,
            headers=headers,
            source_ip=source_ip,
            signature=signature,
            timestamp_str=timestamp_str,
            nonce=nonce,
            body_bytes=body_bytes,
        )

        try:
            # Step 1: Resolve network config
            self._resolve_network(ctx)

            # Step 2: Parse + normalise payload (macros, field mapping, status)
            self._parse_raw_payload(ctx)

            # Step 3: Create raw audit log immediately (before any validation)
            self._create_raw_log(ctx)

            # Fire received signal
            postback_received.send(sender=PostbackRawLog, raw_log=ctx.raw_log)

            # Step 4: Custom pre-validate hook
            self.pre_validate_hook(ctx)

            # Step 5: Security gates
            self._validate_security(ctx)

            # Step 6: Schema validation (Pydantic)
            self._validate_schema(ctx)

            # Step 7: Pre-check fraud (blacklist + velocity)
            self._check_fraud_pre(ctx)

            # Step 8: Idempotency / deduplication
            self._check_deduplication(ctx)

            # Step 9: Resolve user
            self._resolve_user(ctx)

            # Step 10: Business rules (payout cap, offer active, conv window)
            self._validate_business(ctx)

            # Step 11: Atomic conversion + reward
            with transaction.atomic():
                self._create_conversion(ctx)
                self._dispatch_reward(ctx)

            # Step 12: Post-processing (non-blocking)
            self._post_process(ctx)

            # Step 13: Custom post-reward hook
            self.post_reward_hook(ctx)

            ctx.raw_log.mark_rewarded(
                points=ctx.conversion.points_awarded if ctx.conversion else 0,
                usd=ctx.conversion.actual_payout if ctx.conversion else Decimal("0"),
            )

            postback_rewarded.send(
                sender=PostbackRawLog,
                raw_log=ctx.raw_log,
                conversion=ctx.conversion,
            )

            return HandlerResult(
                success=True,
                status="rewarded",
                raw_log_id=str(ctx.raw_log.id),
                conversion_id=str(ctx.conversion.id) if ctx.conversion else None,
            )

        except DuplicateLeadException as exc:
            return self._handle_duplicate(ctx, exc)

        except (
            IPNotWhitelistedException,
            InvalidSignatureException,
            MissingRequiredFieldsException,
            BlacklistedSourceException,
            FraudDetectedException,
            VelocityLimitException,
            PayoutLimitExceededException,
            UserResolutionException,
            OfferInactiveException,
            SchemaValidationException,
        ) as exc:
            return self._handle_rejection(ctx, exc)

        except NetworkNotFoundException as exc:
            logger.warning("Network not found: %s | ip=%s", self.network_key, source_ip)
            return HandlerResult(
                success=False,
                status="rejected",
                rejection_reason=RejectionReason.SCHEMA_VALIDATION,
                detail=str(exc),
            )

        except Exception as exc:
            return self._handle_failure(ctx, exc)

    # ── Pipeline Steps ─────────────────────────────────────────────────────────

    def _resolve_network(self, ctx: PostbackContext):
        from ..models import AdNetworkConfig
        ctx.network = AdNetworkConfig.objects.get_by_key_or_raise(ctx.network_key)

    def _parse_raw_payload(self, ctx: PostbackContext):
        """Normalise payload + expand macros + map status values."""
        adapter = self.get_adapter()
        ctx.normalised = adapter.normalise(ctx.raw_payload)

        # Extract standard fields using the adapter's field map
        ctx.lead_id        = str(ctx.normalised.get("lead_id", "")).strip()
        ctx.click_id       = str(ctx.normalised.get("click_id", "")).strip()
        ctx.offer_id       = str(ctx.normalised.get("offer_id", "")).strip()
        ctx.transaction_id = str(ctx.normalised.get("transaction_id", "")).strip()
        ctx.goal_id        = str(ctx.normalised.get("goal_id", "")).strip()
        ctx.currency       = str(ctx.normalised.get("currency", "USD")).upper().strip() or "USD"
        ctx.status_raw     = str(ctx.normalised.get("status", "")).strip()

        # Normalise status (e.g. "1" → "approved", "0" → "rejected")
        ctx.status_normalised = adapter.normalise_status(ctx.status_raw)

        # Parse payout
        ctx.payout = adapter.parse_payout(ctx.normalised.get("payout", "0"))

        # If lead_id empty, fall back to click_id
        if not ctx.lead_id and ctx.click_id:
            ctx.lead_id = ctx.click_id

        # Ensure transaction_id always has a value
        if not ctx.transaction_id:
            import uuid
            ctx.transaction_id = str(uuid.uuid4())

    def _create_raw_log(self, ctx: PostbackContext):
        from ..security.signature_generator import mask_secret
        safe_headers = {
            k: "***" if k.lower() in {
                "authorization", "x-postback-signature",
                "x-api-key", "cookie", "x-auth-token",
            } else v
            for k, v in ctx.headers.items()
        }
        ctx.raw_log = PostbackRawLog.objects.create(
            tenant=ctx.network.tenant,
            network=ctx.network,
            raw_payload=ctx.raw_payload,
            http_method=ctx.method,
            query_string=ctx.query_string,
            request_headers=safe_headers,
            source_ip=ctx.source_ip or None,
            lead_id=ctx.lead_id,
            click_id=ctx.click_id,
            offer_id=ctx.offer_id,
            transaction_id=ctx.transaction_id,
            payout=ctx.payout,
            currency=ctx.currency,
            status=PostbackStatus.RECEIVED,
            nonce=ctx.nonce,
        )

    def _validate_security(self, ctx: PostbackContext):
        from ..validation_engines.request_validator import request_validator
        from ..security.signature_generator import (
            build_postback_signature_message,
            verify_hmac,
        )
        from ..enums import SignatureAlgorithm
        from ..constants import SIGNATURE_TOLERANCE_SECONDS
        from ..exceptions import SignatureExpiredException

        # IP whitelist
        if ctx.network.ip_whitelist:
            request_validator.validate_ip_whitelist(
                ctx.source_ip, ctx.network.ip_whitelist
            )
        ctx.ip_whitelisted = True

        # Signature (skip for NONE algorithm)
        if ctx.network.signature_algorithm != SignatureAlgorithm.NONE:
            if not ctx.signature:
                raise InvalidSignatureException("No X-Postback-Signature provided.")

            # Replay window
            if ctx.timestamp_str:
                try:
                    ts = float(ctx.timestamp_str)
                    age = abs(timezone.now().timestamp() - ts)
                    if age > SIGNATURE_TOLERANCE_SECONDS:
                        raise SignatureExpiredException(
                            f"Timestamp {age:.0f}s old (max {SIGNATURE_TOLERANCE_SECONDS}s)."
                        )
                except (ValueError, TypeError):
                    raise InvalidSignatureException("Malformed timestamp.")

            msg = build_postback_signature_message(
                ctx.raw_payload, ctx.timestamp_str, ctx.nonce
            )
            if not verify_hmac(
                ctx.network.secret_key,
                msg,
                ctx.signature,
                ctx.network.signature_algorithm,
            ):
                raise InvalidSignatureException("HMAC signature mismatch.")

        ctx.signature_verified = True
        PostbackRawLog.objects.filter(pk=ctx.raw_log.pk).update(
            signature_verified=True,
            ip_whitelisted=ctx.ip_whitelisted,
        )

    def _validate_schema(self, ctx: PostbackContext):
        """Pydantic schema validation — raises SchemaValidationException on failure."""
        from ..schemas import validate_postback_payload
        validate_postback_payload(ctx.normalised, network_key=ctx.network_key)

    def _check_fraud_pre(self, ctx: PostbackContext):
        """Fast blacklist + velocity check before any DB writes."""
        from ..fraud_detection.fraud_detector import scan_postback
        from ..fraud_detection.velocity_checker import velocity_checker

        # Blacklist check
        if ctx.source_ip:
            from ..models import IPBlacklist
            from ..enums import BlacklistType
            if IPBlacklist.objects.is_blacklisted(ctx.source_ip, BlacklistType.IP):
                raise BlacklistedSourceException(
                    f"IP {ctx.source_ip} is blacklisted."
                )

        # Velocity check
        velocity_checker.check(
            ip=ctx.source_ip,
            user=None,
            network=ctx.network,
        )

        # Full fraud scan
        is_fraud, ctx.fraud_score, ctx.fraud_signals = scan_postback(ctx.raw_log)
        if is_fraud and ctx.fraud_score >= FRAUD_SCORE_THRESHOLD_FLAG:
            raise FraudDetectedException(
                f"Fraud score {ctx.fraud_score:.1f} exceeds threshold.",
                fraud_score=ctx.fraud_score,
            )

    def _check_deduplication(self, ctx: PostbackContext):
        from ..conversion_tracking.conversion_deduplicator import conversion_deduplicator
        conversion_deduplicator.assert_not_duplicate(
            network=ctx.network,
            lead_id=ctx.lead_id,
            transaction_id=ctx.transaction_id,
            raw_log=ctx.raw_log,
        )

    def _resolve_user(self, ctx: PostbackContext):
        from django.contrib.auth import get_user_model
        from ..models import ClickLog
        User = get_user_model()

        # 1. Try via click_id → ClickLog
        if ctx.click_id:
            click = ClickLog.objects.get_by_click_id(ctx.click_id)
            if click and click.user_id:
                ctx.click_log = click
                ctx.user = click.user
                return

        # 2. Try via user_id in normalised payload
        user_id = ctx.normalised.get("user_id") or ctx.normalised.get("sub_id")
        if user_id:
            try:
                ctx.user = User.objects.get(pk=user_id)
                return
            except (User.DoesNotExist, ValueError, TypeError):
                pass

        raise UserResolutionException(
            f"Cannot resolve user: click_id={ctx.click_id!r} "
            f"user_id={ctx.normalised.get('user_id')!r}"
        )

    def _validate_business(self, ctx: PostbackContext):
        """Payout cap, offer active, conversion window."""
        if ctx.payout > MAX_PAYOUT_USD_PER_CONVERSION:
            raise PayoutLimitExceededException(
                f"Payout {ctx.payout} > cap {MAX_PAYOUT_USD_PER_CONVERSION}.",
                payout=ctx.payout,
                limit=MAX_PAYOUT_USD_PER_CONVERSION,
            )

        # Conversion window (if we have a click_log)
        if ctx.click_log:
            from ..conversion_tracking.conversion_manager import conversion_manager
            conversion_manager.validate_conversion_window(ctx.click_log, ctx.network)

    def _create_conversion(self, ctx: PostbackContext):
        from ..services import _create_conversion
        ctx.conversion = _create_conversion(
            raw_log=ctx.raw_log,
            user=ctx.user,
            network=ctx.network,
        )

    def _dispatch_reward(self, ctx: PostbackContext):
        from ..services import _dispatch_reward
        _dispatch_reward(conversion=ctx.conversion, network=ctx.network)

    def _post_process(self, ctx: PostbackContext):
        """Fire async tasks: analytics, webhooks, stats. Non-blocking."""
        from ..tasks import (
            process_conversion_task,
            send_webhook_notification,
            update_hourly_stats,
        )
        try:
            process_conversion_task.apply_async(
                args=[str(ctx.conversion.id)], countdown=2
            )
            send_webhook_notification.apply_async(
                args=[str(ctx.conversion.id)], countdown=3
            )
        except Exception as exc:
            logger.warning("post_process task dispatch failed: %s", exc)

    # ── Rejection / Failure Handlers ──────────────────────────────────────────

    def _handle_duplicate(self, ctx: PostbackContext, exc: Exception) -> HandlerResult:
        if ctx.raw_log:
            ctx.raw_log.mark_duplicate()
            postback_duplicate.send(sender=PostbackRawLog, raw_log=ctx.raw_log)
        logger.info("Duplicate postback: network=%s lead=%s", ctx.network_key, ctx.lead_id)
        return HandlerResult(
            success=False,
            status="duplicate",
            raw_log_id=str(ctx.raw_log.id) if ctx.raw_log else None,
            rejection_reason=RejectionReason.DUPLICATE_LEAD,
            detail=str(exc),
        )

    def _handle_rejection(self, ctx: PostbackContext, exc: Exception) -> HandlerResult:
        from ..services import _map_exception_to_rejection_reason
        reason = _map_exception_to_rejection_reason(exc)
        ctx.rejection_reason = reason
        ctx.rejection_detail = str(exc)

        if ctx.raw_log:
            ctx.raw_log.mark_rejected(reason=reason, detail=str(exc))
            postback_rejected.send(
                sender=PostbackRawLog, raw_log=ctx.raw_log, reason=reason, exc=exc
            )

        self.on_rejection_hook(ctx)
        logger.warning(
            "Postback rejected: network=%s lead=%s reason=%s detail=%s",
            ctx.network_key, ctx.lead_id, reason, str(exc),
        )
        return HandlerResult(
            success=False,
            status="rejected",
            raw_log_id=str(ctx.raw_log.id) if ctx.raw_log else None,
            rejection_reason=reason,
            detail=str(exc),
        )

    def _handle_failure(self, ctx: PostbackContext, exc: Exception) -> HandlerResult:
        if ctx.raw_log:
            ctx.raw_log.mark_failed(error=str(exc))
            postback_failed.send(sender=PostbackRawLog, raw_log=ctx.raw_log, exc=exc)
        logger.exception(
            "Postback processing error: network=%s lead=%s",
            ctx.network_key, ctx.lead_id,
        )
        return HandlerResult(
            success=False,
            status="failed",
            raw_log_id=str(ctx.raw_log.id) if ctx.raw_log else None,
            detail=str(exc),
        )
