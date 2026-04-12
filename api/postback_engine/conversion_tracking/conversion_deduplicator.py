"""
conversion_tracking/conversion_deduplicator.py
────────────────────────────────────────────────
Production-grade idempotency enforcement for conversions.

Two-layer deduplication to eliminate double payouts:
  Layer 1 → Redis SETNX lock   (fast, in-memory, handles burst traffic)
  Layer 2 → DB UNIQUE constraint (permanent, survives Redis restarts)

Prevents:
  • Same lead_id from same network being processed twice
  • Same transaction_id across any network being credited twice
  • Race conditions under concurrent postback delivery

Redis key schema:
  pe:dedup:lead:{network_id}:{lead_id}           → "1" (TTL = dedup_window)
  pe:dedup:txn:{transaction_id}                  → "1" (TTL = 30 days)
  pe:dedup:lock:{network_id}:{lead_id}           → "1" (TTL = 30s, processing lock)
"""
from __future__ import annotations

import hashlib
import logging
from datetime import timedelta
from typing import Optional, Tuple

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from ..constants import DEDUP_WINDOW_MAP, DEDUP_CACHE_TTL
from ..exceptions import DuplicateLeadException, DuplicateConversionException
from ..models import AdNetworkConfig, ConversionDeduplication, PostbackRawLog

logger = logging.getLogger(__name__)

# Cache key templates
_KEY_LEAD   = "pe:dedup:lead:{network_id}:{lead_hash}"
_KEY_TXN    = "pe:dedup:txn:{txn_hash}"
_KEY_LOCK   = "pe:dedup:lock:{network_id}:{lead_hash}"

# Processing lock TTL (seconds) — a postback should never take longer than this
_LOCK_TTL = 30

# Fallback TTL when Redis is unavailable (use DB only)
_FALLBACK_TTL = DEDUP_CACHE_TTL   # 30 days in seconds


class ConversionDeduplicator:
    """
    Idempotency guard for postback conversions.

    Usage:
        deduplicator.assert_not_duplicate(
            network=network_config,
            lead_id="abc123",
            transaction_id="txn_xyz",
            raw_log=raw_log,
        )

    Raises DuplicateLeadException or DuplicateConversionException if already seen.
    """

    # ── Main entry point ───────────────────────────────────────────────────────

    def assert_not_duplicate(
        self,
        network: AdNetworkConfig,
        lead_id: str,
        transaction_id: str,
        raw_log: Optional[PostbackRawLog] = None,
    ) -> None:
        """
        Full two-layer deduplication check + atomic record creation.

        Raises:
            DuplicateLeadException       — same lead_id seen before for this network
            DuplicateConversionException — same transaction_id seen before (any network)
        """
        # ── Layer 1: Redis fast-path ───────────────────────────────────────────
        lead_hash = self._hash(lead_id)
        txn_hash  = self._hash(transaction_id)
        network_id = str(network.id)

        lead_key = _KEY_LEAD.format(network_id=network_id, lead_hash=lead_hash)
        txn_key  = _KEY_TXN.format(txn_hash=txn_hash)
        lock_key = _KEY_LOCK.format(network_id=network_id, lead_hash=lead_hash)

        # Check lead_id in Redis
        if cache.get(lead_key):
            logger.info(
                "Dedup: Redis hit for lead=%s network=%s",
                lead_id[:16], network.network_key,
            )
            raise DuplicateLeadException(
                f"Lead '{lead_id}' already processed for network '{network.network_key}'.",
            )

        # Check transaction_id in Redis
        if transaction_id and cache.get(txn_key):
            logger.info(
                "Dedup: Redis hit for transaction_id=%s", transaction_id[:20]
            )
            raise DuplicateConversionException(
                f"Transaction '{transaction_id}' already recorded."
            )

        # Acquire processing lock (prevents race-condition duplicates)
        lock_acquired = self._acquire_lock(lock_key)

        # ── Layer 2: DB check (authoritative) ─────────────────────────────────
        existing = ConversionDeduplication.objects.filter(
            network=network,
            lead_id=lead_id,
        ).first()
        if existing:
            # Backfill Redis so next check is fast
            self._set_redis_keys(lead_key, txn_key, network)
            if lock_acquired:
                self._release_lock(lock_key)
            raise DuplicateLeadException(
                f"Lead '{lead_id}' first seen at {existing.first_seen_at}.",
                first_seen_at=existing.first_seen_at,
            )

        # DB check by transaction_id (across all networks)
        if transaction_id:
            txn_exists = ConversionDeduplication.objects.filter(
                transaction_id=transaction_id,
            ).exclude(lead_id="").exists()
            if txn_exists:
                self._set_redis_txn_key(txn_key, network)
                if lock_acquired:
                    self._release_lock(lock_key)
                raise DuplicateConversionException(
                    f"Transaction '{transaction_id}' already recorded."
                )

        # ── Atomic DB write ────────────────────────────────────────────────────
        # Use get_or_create with SELECT FOR UPDATE to handle concurrent requests
        try:
            with transaction.atomic():
                obj, created = ConversionDeduplication.objects.select_for_update(
                    nowait=False
                ).get_or_create(
                    network=network,
                    lead_id=lead_id,
                    defaults={
                        "transaction_id": transaction_id,
                        "raw_log": raw_log,
                        "tenant": network.tenant,
                    },
                )
                if not created:
                    # Lost the race — another worker inserted first
                    if lock_acquired:
                        self._release_lock(lock_key)
                    raise DuplicateLeadException(
                        f"Lead '{lead_id}' recorded by concurrent request."
                    )
        except IntegrityError:
            if lock_acquired:
                self._release_lock(lock_key)
            raise DuplicateLeadException(
                f"Lead '{lead_id}' UNIQUE constraint violation (concurrent)."
            )

        # ── Backfill Redis after successful DB write ───────────────────────────
        self._set_redis_keys(lead_key, txn_key, network)

        # Release lock
        if lock_acquired:
            self._release_lock(lock_key)

        logger.debug(
            "Dedup: recorded lead=%s txn=%s network=%s",
            lead_id[:16], transaction_id[:16] if transaction_id else "—",
            network.network_key,
        )

    def link_conversion(
        self,
        network: AdNetworkConfig,
        lead_id: str,
        conversion,
    ) -> None:
        """Update the dedup record with the created Conversion FK."""
        ConversionDeduplication.objects.filter(
            network=network, lead_id=lead_id
        ).update(conversion=conversion)

    def is_duplicate(
        self,
        network: AdNetworkConfig,
        lead_id: str,
        transaction_id: str = "",
    ) -> bool:
        """
        Non-raising check. Returns True if already seen, False otherwise.
        Use for read-only checks (e.g. admin dashboard queries).
        """
        # Redis fast path
        lead_hash  = self._hash(lead_id)
        network_id = str(network.id)
        lead_key   = _KEY_LEAD.format(network_id=network_id, lead_hash=lead_hash)

        if cache.get(lead_key):
            return True

        return ConversionDeduplication.objects.filter(
            network=network, lead_id=lead_id
        ).exists()

    def invalidate(self, network: AdNetworkConfig, lead_id: str, transaction_id: str = "") -> None:
        """
        Remove a dedup record (e.g. for reversal / re-processing).
        Also clears Redis keys.
        """
        lead_hash  = self._hash(lead_id)
        network_id = str(network.id)

        ConversionDeduplication.objects.filter(
            network=network, lead_id=lead_id
        ).delete()

        cache.delete(_KEY_LEAD.format(network_id=network_id, lead_hash=lead_hash))
        if transaction_id:
            cache.delete(_KEY_TXN.format(txn_hash=self._hash(transaction_id)))

        logger.info(
            "Dedup: invalidated lead=%s network=%s", lead_id[:16], network.network_key
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _hash(value: str) -> str:
        """SHA-256 hash lead_id / txn_id before using as cache key (avoid key length issues)."""
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]

    @staticmethod
    def _get_ttl(network: AdNetworkConfig) -> int:
        """Return the cache TTL in seconds based on network's dedup_window setting."""
        from ..constants import DEDUP_WINDOW_MAP
        delta = DEDUP_WINDOW_MAP.get(network.dedup_window)
        if delta is None:
            return _FALLBACK_TTL   # "forever" → use the 30-day fallback
        return int(delta.total_seconds())

    def _set_redis_keys(self, lead_key: str, txn_key: str, network: AdNetworkConfig) -> None:
        ttl = self._get_ttl(network)
        try:
            cache.set(lead_key, "1", timeout=ttl)
            if txn_key:
                cache.set(txn_key, "1", timeout=_FALLBACK_TTL)
        except Exception as exc:
            logger.warning("Dedup: Redis set failed (non-fatal): %s", exc)

    def _set_redis_txn_key(self, txn_key: str, network: AdNetworkConfig) -> None:
        try:
            cache.set(txn_key, "1", timeout=_FALLBACK_TTL)
        except Exception as exc:
            logger.warning("Dedup: Redis txn set failed (non-fatal): %s", exc)

    def _acquire_lock(self, lock_key: str) -> bool:
        """
        Try to acquire a short-lived Redis lock (SETNX pattern).
        Returns True if lock was acquired, False if already held (non-fatal).
        """
        try:
            # add() is atomic SETNX equivalent in Django cache
            acquired = cache.add(lock_key, "1", timeout=_LOCK_TTL)
            if not acquired:
                logger.debug("Dedup: lock already held for key=%s", lock_key)
            return acquired
        except Exception as exc:
            logger.warning("Dedup: lock acquire failed (non-fatal): %s", exc)
            return False

    def _release_lock(self, lock_key: str) -> None:
        try:
            cache.delete(lock_key)
        except Exception as exc:
            logger.warning("Dedup: lock release failed (non-fatal): %s", exc)


# ── Module-level singleton ─────────────────────────────────────────────────────
conversion_deduplicator = ConversionDeduplicator()
