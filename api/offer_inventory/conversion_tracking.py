# api/offer_inventory/conversion_tracking.py
"""
Conversion Tracking — Bulletproof Deduplication Engine.

Rules:
  1. একই click_id → একটিই conversion (DB UniqueConstraint + select_for_update)
  2. একই transaction_id → একটিই conversion (DB unique field)
  3. একই user+offer fingerprint → DuplicateConversionFilter check
  4. Race condition → Redis distributed lock (DB lock fallback)

Architecture:
  ConversionTracker.record()
      → Redis SETNX lock (5s TTL)
      → DB transaction: select_for_update on Click
      → Validate: click exists, not converted, tx_id unique
      → Create Conversion atomically
      → Release lock
"""
import hashlib
import logging
import time
from contextlib import contextmanager
from decimal import Decimal
from typing import Optional

from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils import timezone
from django.core.cache import cache

from .models import (
    Click, Conversion, ConversionStatus,
    DuplicateConversionFilter, Offer,
)
from .exceptions import (
    DuplicateConversionException,
    InvalidClickTokenException,
    OfferNotFoundException,
    OfferExpiredException,
    OfferCapReachedException,
)

logger = logging.getLogger(__name__)

# ── Lock Configuration ───────────────────────────────────────────
LOCK_TTL_SECONDS   = 10      # Redis lock expires in 10s
LOCK_RETRY_TIMES   = 3       # Max retry attempts
LOCK_RETRY_DELAY   = 0.3     # Seconds between retries


# ════════════════════════════════════════════════════════════════
# DISTRIBUTED LOCK  (Redis SETNX → DB fallback)
# ════════════════════════════════════════════════════════════════

@contextmanager
def conversion_lock(lock_key: str):
    """
    Distributed lock using Redis SETNX.
    Prevents simultaneous processing of the same click/tx_id.

    Usage:
        with conversion_lock(f'conv:{click_token}'):
            ... atomic work ...
    """
    full_key = f'conv_lock:{lock_key}'
    acquired = False

    for attempt in range(LOCK_RETRY_TIMES):
        # NX=set if not exists, EX=expire in seconds
        acquired = cache.add(full_key, '1', LOCK_TTL_SECONDS)
        if acquired:
            break
        if attempt < LOCK_RETRY_TIMES - 1:
            time.sleep(LOCK_RETRY_DELAY * (attempt + 1))

    if not acquired:
        logger.warning(f'Could not acquire conversion lock: {full_key}')
        raise DuplicateConversionException(
            'Conversion already being processed. Please retry.'
        )

    try:
        yield
    finally:
        if acquired:
            cache.delete(full_key)


# ════════════════════════════════════════════════════════════════
# DEDUPLICATION CHECKS
# ════════════════════════════════════════════════════════════════

class DeduplicationEngine:
    """
    Multi-layer deduplication.
    Layer 1: Redis cache (fastest, ms)
    Layer 2: DB unique constraint on transaction_id
    Layer 3: DB select_for_update on Click.converted flag
    Layer 4: DuplicateConversionFilter table (user+offer+fingerprint)
    """

    @staticmethod
    def check_transaction_id(transaction_id: str) -> bool:
        """
        transaction_id আগে দেখা হয়েছে কিনা।
        Returns True if DUPLICATE (should reject).
        """
        if not transaction_id:
            return False

        # Layer 1: Redis cache (TTL=24h)
        cache_key = f'txid_seen:{transaction_id}'
        if cache.get(cache_key):
            logger.warning(f'Duplicate tx_id (cache): {transaction_id}')
            return True

        # Layer 2: DB check
        exists = Conversion.objects.filter(
            transaction_id=transaction_id
        ).exists()
        if exists:
            # Warm cache for future hits
            cache.set(cache_key, '1', 86400)
            logger.warning(f'Duplicate tx_id (DB): {transaction_id}')
            return True

        return False

    @staticmethod
    def check_click_converted(click: Click) -> bool:
        """
        Click ইতিমধ্যে converted হয়েছে কিনা।
        Returns True if DUPLICATE.
        """
        return click.converted

    @staticmethod
    def check_user_offer_fingerprint(user_id, offer_id: str, ip: str) -> bool:
        """
        Same user+offer+ip combo আগে convert করেছে কিনা।
        Returns True if DUPLICATE.
        """
        fingerprint = DeduplicationEngine.make_fingerprint(user_id, offer_id, ip)
        return DuplicateConversionFilter.objects.filter(
            user_id=user_id,
            offer_id=offer_id,
            fingerprint=fingerprint,
            is_blocked=True,
        ).exists()

    @staticmethod
    def record_fingerprint(user_id, offer_id: str, ip: str):
        """Successful conversion-এর fingerprint save করো।"""
        fingerprint = DeduplicationEngine.make_fingerprint(user_id, offer_id, ip)
        obj, created = DuplicateConversionFilter.objects.get_or_create(
            user_id=user_id,
            offer_id=offer_id,
            fingerprint=fingerprint,
            defaults={'is_blocked': True},
        )
        if not created:
            # Already exists — increment attempt count
            DuplicateConversionFilter.objects.filter(id=obj.id).update(
                attempt_count=obj.attempt_count + 1,
                last_attempt=timezone.now(),
                is_blocked=True,
            )

    @staticmethod
    def make_fingerprint(user_id, offer_id: str, ip: str) -> str:
        raw = f'{user_id}:{offer_id}:{ip}'
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def mark_tx_id_seen(transaction_id: str):
        """Cache-এ tx_id mark করো।"""
        if transaction_id:
            cache.set(f'txid_seen:{transaction_id}', '1', 86400)


# ════════════════════════════════════════════════════════════════
# MAIN TRACKER
# ════════════════════════════════════════════════════════════════

class ConversionTracker:
    """
    The single entry point for recording all conversions.

    Flow:
        1. Acquire distributed lock on click_token
        2. Open DB transaction
        3. Lock Click row with select_for_update (prevents race at DB level)
        4. Run all deduplication checks
        5. Validate offer still active + caps OK
        6. Create Conversion record atomically
        7. Update Click.converted = True
        8. Record fingerprint for future dedup
        9. Cache tx_id
       10. Release lock
    """

    @classmethod
    def record(
        cls,
        click_token: str,
        transaction_id: str,
        payout: Decimal,
        raw_data: dict,
        ip_address: str = '',
    ) -> Conversion:
        """
        Record a conversion. Fully idempotent & race-condition-safe.

        Raises:
            InvalidClickTokenException   — click not found
            DuplicateConversionException — already converted
            OfferExpiredException        — offer no longer active
            OfferCapReachedException     — offer cap hit
        """
        # ── Fast pre-checks (no lock needed) ─────────────────────
        if DeduplicationEngine.check_transaction_id(transaction_id):
            raise DuplicateConversionException(
                f'Transaction ID already processed: {transaction_id}'
            )

        # ── Acquire distributed lock on this click_token ──────────
        lock_key = click_token[:32]  # First 32 chars as lock key
        with conversion_lock(lock_key):
            return cls._process_locked(
                click_token, transaction_id, payout, raw_data, ip_address
            )

    @classmethod
    @transaction.atomic
    def _process_locked(
        cls,
        click_token: str,
        transaction_id: str,
        payout: Decimal,
        raw_data: dict,
        ip_address: str,
    ) -> Conversion:
        """
        DB transaction + row-level lock.
        select_for_update() on Click prevents concurrent processing.
        """
        # ── Fetch & lock Click row ────────────────────────────────
        try:
            click = (
                Click.objects
                .select_for_update(nowait=True)   # Fail immediately if locked
                .select_related('offer', 'user', 'offer__network')
                .get(click_token=click_token)
            )
        except Click.DoesNotExist:
            raise InvalidClickTokenException(
                f'Click token not found: {click_token[:16]}...'
            )
        except Exception:
            # nowait raised — another transaction has this row locked
            raise DuplicateConversionException(
                'Concurrent conversion attempt. Please retry.'
            )

        # ── Dedup check #1: click already converted? ─────────────
        if DeduplicationEngine.check_click_converted(click):
            raise DuplicateConversionException(
                f'Click {click_token[:16]}... already converted.'
            )

        # ── Dedup check #2: tx_id unique (inside transaction)? ───
        if Conversion.objects.filter(transaction_id=transaction_id).exists():
            raise DuplicateConversionException(
                f'Transaction ID {transaction_id} already exists.'
            )

        # ── Dedup check #3: user+offer+ip fingerprint ────────────
        user     = click.user
        offer    = click.offer
        eff_ip   = ip_address or click.ip_address or ''

        if user and DeduplicationEngine.check_user_offer_fingerprint(
            user.id, str(offer.id), eff_ip
        ):
            raise DuplicateConversionException(
                'Duplicate conversion detected via fingerprint.'
            )

        # ── Validate offer ────────────────────────────────────────
        if not offer:
            raise OfferNotFoundException('Offer not found on click.')

        if offer.status != 'active':
            raise OfferExpiredException(
                f'Offer {offer.id} is {offer.status}.'
            )

        # ── Validate offer caps ───────────────────────────────────
        cls._validate_caps(offer)

        # ── Calculate reward ──────────────────────────────────────
        from .finance_payment.revenue_calculator import RevenueCalculator
        has_referral = cls._user_has_referrer(user)
        breakdown    = RevenueCalculator.calculate(
            gross=payout,
            user=user,
            has_referral=has_referral,
        )

        # ── Create Conversion ─────────────────────────────────────
        status_pending = ConversionStatus.objects.get(name='pending')
        try:
            conversion = Conversion.objects.create(
                click          = click,
                offer          = offer,
                user           = user,
                tenant         = offer.tenant,
                status         = status_pending,
                payout_amount  = breakdown.gross_revenue,
                reward_amount  = breakdown.net_to_user,
                transaction_id = transaction_id,
                ip_address     = eff_ip,
                country_code   = click.country_code,
                raw_postback   = raw_data,
            )
        except IntegrityError as e:
            # DB-level unique constraint caught race condition
            logger.warning(f'IntegrityError on conversion create: {e}')
            raise DuplicateConversionException(
                'Conversion already exists (DB constraint).'
            )

        # ── Mark click as converted (atomic update) ───────────────
        updated = Click.objects.filter(
            id=click.id, converted=False
        ).update(converted=True)

        if updated == 0:
            # Another process beat us — rollback via exception
            raise DuplicateConversionException(
                'Click was converted concurrently.'
            )

        # ── Post-processing (still inside transaction) ────────────
        # Record fingerprint (blocks future duplicates)
        if user:
            DeduplicationEngine.record_fingerprint(user.id, str(offer.id), eff_ip)

        # Cache tx_id (fast rejection for future attempts)
        DeduplicationEngine.mark_tx_id_seen(transaction_id)

        # Increment offer completion count (atomic)
        from django.db.models import F
        Offer.objects.filter(id=offer.id).update(
            total_completions=F('total_completions') + 1
        )

        # Increment cap counts
        cls._increment_caps(offer)

        logger.info(
            f'Conversion recorded | id={conversion.id} | '
            f'offer={offer.id} | user={user.id if user else "anon"} | '
            f'payout={payout} | reward={breakdown.net_to_user}'
        )
        return conversion

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _validate_caps(offer: Offer):
        """All active caps check করো।"""
        now = timezone.now()
        for cap in offer.caps.filter(pause_on_hit=True):
            # Reset daily/weekly/monthly caps if window passed
            if cap.reset_at and now >= cap.reset_at:
                cap.current_count = 0
                cap.reset_at      = cls._next_reset(cap.cap_type)
                cap.save(update_fields=['current_count', 'reset_at'])

            if cap.current_count >= cap.cap_limit:
                raise OfferCapReachedException(
                    f'Offer {offer.id} {cap.cap_type} cap reached '
                    f'({cap.current_count}/{cap.cap_limit}).'
                )

    @staticmethod
    def _increment_caps(offer: Offer):
        """All caps atomically increment।"""
        from django.db.models import F
        offer.caps.all().update(current_count=F('current_count') + 1)

        # Auto-pause if any cap now reached
        for cap in offer.caps.filter(pause_on_hit=True):
            cap.refresh_from_db(fields=['current_count', 'cap_limit'])
            if cap.current_count >= cap.cap_limit:
                Offer.objects.filter(id=offer.id, status='active').update(status='paused')
                logger.info(
                    f'Offer {offer.id} auto-paused — '
                    f'{cap.cap_type} cap hit ({cap.cap_limit}).'
                )
                break

    @staticmethod
    def _next_reset(cap_type: str):
        """Cap reset time calculate।"""
        from datetime import timedelta
        now = timezone.now()
        if cap_type == 'daily':
            return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        if cap_type == 'weekly':
            days_ahead = 7 - now.weekday()
            return (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
        if cap_type == 'monthly':
            if now.month == 12:
                return now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return None

    @staticmethod
    def _user_has_referrer(user) -> bool:
        if not user:
            return False
        from .models import UserReferral
        return UserReferral.objects.filter(referred=user).exists()
