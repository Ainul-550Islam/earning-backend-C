"""
managers.py – Custom QuerySet and Manager classes for Postback Engine.
"""
from django.db import models
from django.utils import timezone

from .enums import (
    NetworkStatus,
    PostbackStatus,
    ConversionStatus,
    ClickStatus,
    QueueStatus,
    QueuePriority,
    BlacklistType,
    FraudType,
)
from .exceptions import NetworkNotFoundException, NetworkInactiveException


# ── AdNetworkConfig ───────────────────────────────────────────────────────────

class AdNetworkConfigQuerySet(models.QuerySet):

    def active(self):
        return self.filter(status=NetworkStatus.ACTIVE)

    def by_type(self, network_type):
        return self.filter(network_type=network_type)

    def with_test_mode(self):
        return self.filter(is_test_mode=True)

    def without_test_mode(self):
        return self.filter(is_test_mode=False)


class AdNetworkConfigManager(models.Manager):

    def get_queryset(self):
        return AdNetworkConfigQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def get_by_key(self, network_key: str):
        """Returns None if not found."""
        try:
            return self.get_queryset().get(network_key=network_key)
        except self.model.DoesNotExist:
            return None

    def get_by_key_or_raise(self, network_key: str):
        """Raises appropriate exception if not found or inactive."""
        try:
            config = self.get_queryset().get(network_key=network_key)
        except self.model.DoesNotExist:
            raise NetworkNotFoundException(
                f"No network config for key '{network_key}'."
            )
        if config.status in (NetworkStatus.INACTIVE, NetworkStatus.SUSPENDED, NetworkStatus.DEPRECATED):
            raise NetworkInactiveException(
                f"Network '{network_key}' is {config.get_status_display().lower()}."
            )
        return config


# ── PostbackRawLog ────────────────────────────────────────────────────────────

class PostbackRawLogQuerySet(models.QuerySet):

    def pending(self):
        return self.filter(status=PostbackStatus.RECEIVED)

    def failed(self):
        return self.filter(status=PostbackStatus.FAILED)

    def due_for_retry(self):
        return self.filter(
            status=PostbackStatus.FAILED,
            next_retry_at__lte=timezone.now(),
        )

    def rejected(self):
        return self.filter(status=PostbackStatus.REJECTED)

    def rewarded(self):
        return self.filter(status=PostbackStatus.REWARDED)

    def for_network(self, network):
        return self.filter(network=network)

    def in_date_range(self, start, end):
        return self.filter(received_at__gte=start, received_at__lte=end)

    def from_ip(self, ip):
        return self.filter(source_ip=ip)


class PostbackRawLogManager(models.Manager):

    def get_queryset(self):
        return PostbackRawLogQuerySet(self.model, using=self._db)

    def due_for_retry(self):
        return self.get_queryset().due_for_retry()

    def failed(self):
        return self.get_queryset().failed()

    def for_network(self, network):
        return self.get_queryset().for_network(network)


# ── ClickLog ──────────────────────────────────────────────────────────────────

class ClickLogQuerySet(models.QuerySet):

    def valid(self):
        return self.filter(status=ClickStatus.VALID)

    def not_converted(self):
        return self.filter(converted=False)

    def converted(self):
        return self.filter(converted=True)

    def expired(self):
        return self.filter(
            status=ClickStatus.VALID,
            expires_at__lt=timezone.now(),
            converted=False,
        )

    def for_user(self, user):
        return self.filter(user=user)

    def for_offer(self, offer_id):
        return self.filter(offer_id=offer_id)

    def fraud(self):
        return self.filter(is_fraud=True)

    def high_fraud_score(self, threshold=60):
        return self.filter(fraud_score__gte=threshold)


class ClickLogManager(models.Manager):

    def get_queryset(self):
        return ClickLogQuerySet(self.model, using=self._db)

    def valid(self):
        return self.get_queryset().valid()

    def get_by_click_id(self, click_id: str):
        try:
            return self.get_queryset().get(click_id=click_id)
        except self.model.DoesNotExist:
            return None


# ── Conversion ────────────────────────────────────────────────────────────────

class ConversionQuerySet(models.QuerySet):

    def pending(self):
        return self.filter(status=ConversionStatus.PENDING)

    def approved(self):
        return self.filter(status=ConversionStatus.APPROVED)

    def paid(self):
        return self.filter(status=ConversionStatus.PAID)

    def not_credited(self):
        return self.filter(wallet_credited=False, status=ConversionStatus.APPROVED)

    def for_user(self, user):
        return self.filter(user=user)

    def for_offer(self, offer_id):
        return self.filter(offer_id=offer_id)

    def for_network(self, network):
        return self.filter(network=network)

    def reversed(self):
        return self.filter(is_reversed=True)

    def in_date_range(self, start, end):
        return self.filter(converted_at__gte=start, converted_at__lte=end)


class ConversionManager(models.Manager):

    def get_queryset(self):
        return ConversionQuerySet(self.model, using=self._db)

    def pending(self):
        return self.get_queryset().pending()

    def approved(self):
        return self.get_queryset().approved()

    def for_user(self, user):
        return self.get_queryset().for_user(user)

    def not_credited(self):
        return self.get_queryset().not_credited()


# ── ConversionDeduplication ───────────────────────────────────────────────────

class ConversionDeduplicationManager(models.Manager):

    def is_duplicate(self, network, lead_id: str) -> bool:
        """Fast existence check — the hot path for dedup."""
        return self.filter(network=network, lead_id=lead_id).exists()

    def record(self, network, lead_id: str, raw_log=None, transaction_id: str = ""):
        """
        Atomic create — returns (obj, created).
        Uses get_or_create to handle race conditions safely.
        """
        obj, created = self.get_or_create(
            network=network,
            lead_id=lead_id,
            defaults={
                "raw_log": raw_log,
                "transaction_id": transaction_id,
            }
        )
        return obj, created


# ── IPBlacklist ───────────────────────────────────────────────────────────────

class IPBlacklistQuerySet(models.QuerySet):

    def active(self):
        return self.filter(is_active=True).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
        )

    def ip_entries(self):
        return self.filter(blacklist_type=BlacklistType.IP)

    def cidr_entries(self):
        return self.filter(blacklist_type=BlacklistType.CIDR)


class IPBlacklistManager(models.Manager):

    def get_queryset(self):
        return IPBlacklistQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def is_blacklisted(self, value: str, blacklist_type: str) -> bool:
        return self.active().filter(
            blacklist_type=blacklist_type, value=value
        ).exists()

    def get_active_ips(self):
        """Returns set of active blacklisted IP strings for fast lookups."""
        return set(
            self.active().ip_entries().values_list("value", flat=True)
        )


# ── PostbackQueue ─────────────────────────────────────────────────────────────

class PostbackQueueQuerySet(models.QuerySet):

    def pending(self):
        return self.filter(status=QueueStatus.PENDING)

    def claimable(self):
        """Items that can be picked up by a worker."""
        now = timezone.now()
        return self.filter(
            status=QueueStatus.PENDING,
            process_after__lte=now,
        ).filter(
            models.Q(lock_expires_at__isnull=True) | models.Q(lock_expires_at__lt=now)
        ).order_by("priority", "enqueued_at")

    def stale_locks(self):
        """Items locked by dead workers (lock expired)."""
        return self.filter(
            status=QueueStatus.PROCESSING,
            lock_expires_at__lt=timezone.now(),
        )

    def dead_letters(self):
        return self.filter(status=QueueStatus.DEAD)


class PostbackQueueManager(models.Manager):

    def get_queryset(self):
        return PostbackQueueQuerySet(self.model, using=self._db)

    def claimable(self, limit=100):
        return self.get_queryset().claimable()[:limit]

    def enqueue(self, raw_log, priority=QueuePriority.NORMAL, process_after=None):
        return self.create(
            raw_log=raw_log,
            priority=priority,
            process_after=process_after or timezone.now(),
        )


# ── HourlyStat ────────────────────────────────────────────────────────────────

class HourlyStatManager(models.Manager):

    def get_or_create_current(self, network):
        """Get or create the current hour's stat record."""
        now = timezone.now()
        obj, _ = self.get_or_create(
            network=network,
            date=now.date(),
            hour=now.hour,
            defaults={"tenant": network.tenant},
        )
        return obj


# ── FraudAttemptLog ───────────────────────────────────────────────────────────

class FraudAttemptLogQuerySet(models.QuerySet):

    def unreviewed(self):
        return self.filter(is_reviewed=False)

    def auto_blocked(self):
        return self.filter(is_auto_blocked=True)

    def by_type(self, fraud_type):
        return self.filter(fraud_type=fraud_type)

    def high_score(self, threshold=80):
        return self.filter(fraud_score__gte=threshold)

    def for_ip(self, ip):
        return self.filter(source_ip=ip)


class FraudAttemptLogManager(models.Manager):

    def get_queryset(self):
        return FraudAttemptLogQuerySet(self.model, using=self._db)

    def unreviewed(self):
        return self.get_queryset().unreviewed()

    def recent_count_for_ip(self, ip: str, hours: int = 24) -> int:
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return self.get_queryset().filter(
            source_ip=ip, detected_at__gte=cutoff
        ).count()
