"""
repository.py
──────────────
Repository pattern layer for Postback Engine.
Abstracts all DB queries away from business logic (services.py).
Each repository class handles one model's DB operations.
Enables easy mocking in tests and swapping DB backends.
"""
from __future__ import annotations
import logging
from decimal import Decimal
from datetime import date, timedelta
from typing import List, Optional
from django.db import models as django_models
from django.utils import timezone
from .models import (
    AdNetworkConfig, ClickLog, Conversion, ConversionDeduplication,
    FraudAttemptLog, HourlyStat, IPBlacklist, NetworkPerformance,
    PostbackQueue, PostbackRawLog, RetryLog,
)
from .enums import (
    ConversionStatus, NetworkStatus, PostbackStatus,
    QueueStatus, BlacklistType,
)

logger = logging.getLogger(__name__)


# ── AdNetworkConfig Repository ─────────────────────────────────────────────────

class NetworkRepository:

    def get_by_key(self, network_key: str) -> Optional[AdNetworkConfig]:
        return AdNetworkConfig.objects.get_by_key(network_key)

    def get_by_key_or_raise(self, network_key: str) -> AdNetworkConfig:
        return AdNetworkConfig.objects.get_by_key_or_raise(network_key)

    def get_all_active(self) -> django_models.QuerySet:
        return AdNetworkConfig.objects.active().select_related("tenant")

    def get_by_id(self, pk) -> Optional[AdNetworkConfig]:
        try:
            return AdNetworkConfig.objects.get(pk=pk)
        except AdNetworkConfig.DoesNotExist:
            return None

    def create(self, **kwargs) -> AdNetworkConfig:
        return AdNetworkConfig.objects.create(**kwargs)

    def update(self, network: AdNetworkConfig, **kwargs) -> AdNetworkConfig:
        for key, value in kwargs.items():
            setattr(network, key, value)
        network.save()
        return network

    def count_active(self) -> int:
        return AdNetworkConfig.objects.active().count()


# ── PostbackRawLog Repository ──────────────────────────────────────────────────

class PostbackRawLogRepository:

    def create(self, **kwargs) -> PostbackRawLog:
        return PostbackRawLog.objects.create(**kwargs)

    def get_by_id(self, pk) -> Optional[PostbackRawLog]:
        try:
            return PostbackRawLog.objects.select_related("network", "resolved_user").get(pk=pk)
        except PostbackRawLog.DoesNotExist:
            return None

    def get_due_for_retry(self, limit: int = 100) -> django_models.QuerySet:
        return PostbackRawLog.objects.due_for_retry().select_related("network")[:limit]

    def get_failed(self, network_key: str = None, limit: int = 500) -> django_models.QuerySet:
        qs = PostbackRawLog.objects.failed()
        if network_key:
            qs = qs.filter(network__network_key=network_key)
        return qs[:limit]

    def count_by_status(self, status: str, hours: int = 24) -> int:
        cutoff = timezone.now() - timedelta(hours=hours)
        return PostbackRawLog.objects.filter(
            status=status, received_at__gte=cutoff
        ).count()

    def get_recent(self, network=None, limit: int = 100) -> django_models.QuerySet:
        qs = PostbackRawLog.objects.select_related("network", "resolved_user")
        if network:
            qs = qs.filter(network=network)
        return qs.order_by("-received_at")[:limit]


# ── Conversion Repository ──────────────────────────────────────────────────────

class ConversionRepository:

    def create(self, **kwargs) -> Conversion:
        return Conversion.objects.create(**kwargs)

    def get_by_id(self, pk) -> Optional[Conversion]:
        try:
            return Conversion.objects.select_related("user", "network", "raw_log").get(pk=pk)
        except Conversion.DoesNotExist:
            return None

    def get_by_transaction_id(self, transaction_id: str) -> Optional[Conversion]:
        return Conversion.objects.filter(transaction_id=transaction_id).first()

    def get_for_user(self, user, days: int = 30) -> django_models.QuerySet:
        cutoff = timezone.now() - timedelta(days=days)
        return Conversion.objects.filter(
            user=user, converted_at__gte=cutoff
        ).order_by("-converted_at")

    def get_pending(self) -> django_models.QuerySet:
        return Conversion.objects.pending().select_related("user", "network")

    def get_uncredited(self) -> django_models.QuerySet:
        return Conversion.objects.not_credited().select_related("user", "network")

    def count_for_user_offer(self, user, offer_id: str) -> int:
        return Conversion.objects.filter(
            user=user, offer_id=offer_id,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        ).count()

    def total_revenue(self, days: int = 30, network=None) -> Decimal:
        from django.db.models import Sum
        cutoff = timezone.now() - timedelta(days=days)
        qs = Conversion.objects.filter(
            converted_at__gte=cutoff,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        )
        if network:
            qs = qs.filter(network=network)
        result = qs.aggregate(total=Sum("actual_payout"))
        return result["total"] or Decimal("0")


# ── ClickLog Repository ────────────────────────────────────────────────────────

class ClickRepository:

    def create(self, **kwargs) -> ClickLog:
        return ClickLog.objects.create(**kwargs)

    def get_by_click_id(self, click_id: str) -> Optional[ClickLog]:
        return ClickLog.objects.get_by_click_id(click_id)

    def get_for_user(self, user, limit: int = 100) -> django_models.QuerySet:
        return ClickLog.objects.filter(user=user).order_by("-clicked_at")[:limit]

    def get_valid_for_offer(self, offer_id: str, user=None) -> django_models.QuerySet:
        qs = ClickLog.objects.valid().filter(offer_id=offer_id)
        if user:
            qs = qs.filter(user=user)
        return qs

    def count_for_ip(self, ip: str, hours: int = 1) -> int:
        cutoff = timezone.now() - timedelta(hours=hours)
        return ClickLog.objects.filter(
            ip_address=ip, clicked_at__gte=cutoff
        ).count()


# ── ConversionDeduplication Repository ───────────────────────────────────────

class DeduplicationRepository:

    def exists(self, network, lead_id: str) -> bool:
        return ConversionDeduplication.objects.filter(
            network=network, lead_id=lead_id
        ).exists()

    def create(self, network, lead_id: str, **kwargs) -> ConversionDeduplication:
        obj, _ = ConversionDeduplication.objects.get_or_create(
            network=network, lead_id=lead_id, defaults=kwargs
        )
        return obj

    def delete(self, network, lead_id: str) -> None:
        ConversionDeduplication.objects.filter(
            network=network, lead_id=lead_id
        ).delete()


# ── IPBlacklist Repository ─────────────────────────────────────────────────────

class BlacklistRepository:

    def is_blacklisted(self, value: str, blacklist_type: str) -> bool:
        return IPBlacklist.objects.is_blacklisted(value, blacklist_type)

    def add(self, value: str, blacklist_type: str = BlacklistType.IP, **kwargs) -> IPBlacklist:
        obj, _ = IPBlacklist.objects.get_or_create(
            blacklist_type=blacklist_type,
            value=value,
            defaults={"is_active": True, **kwargs},
        )
        return obj

    def get_active_ips(self) -> set:
        return IPBlacklist.objects.get_active_ips()

    def deactivate(self, value: str, blacklist_type: str) -> None:
        IPBlacklist.objects.filter(
            blacklist_type=blacklist_type, value=value
        ).update(is_active=False)


# ── FraudAttemptLog Repository ─────────────────────────────────────────────────

class FraudRepository:

    def create(self, **kwargs) -> FraudAttemptLog:
        return FraudAttemptLog.objects.create(**kwargs)

    def get_unreviewed(self, limit: int = 100) -> django_models.QuerySet:
        return FraudAttemptLog.objects.unreviewed().order_by("-detected_at")[:limit]

    def count_for_ip(self, ip: str, hours: int = 24) -> int:
        return FraudAttemptLog.objects.recent_count_for_ip(ip, hours)


# ── PostbackQueue Repository ───────────────────────────────────────────────────

class QueueRepository:

    def enqueue(self, raw_log, priority: int = 3, process_after=None) -> PostbackQueue:
        return PostbackQueue.objects.enqueue(raw_log, priority=priority, process_after=process_after)

    def get_claimable(self, limit: int = 50) -> django_models.QuerySet:
        return PostbackQueue.objects.claimable(limit=limit)

    def get_stats(self) -> dict:
        from django.db.models import Count
        breakdown = dict(
            PostbackQueue.objects.values("status")
            .annotate(cnt=Count("id"))
            .values_list("status", "cnt")
        )
        return {s: breakdown.get(s, 0) for s in QueueStatus.values}


# ── Analytics Repository ───────────────────────────────────────────────────────

class AnalyticsRepository:

    def get_or_create_hourly_stat(self, network) -> HourlyStat:
        return HourlyStat.objects.get_or_create_current(network)

    def get_network_performance(self, network, target_date: date) -> Optional[NetworkPerformance]:
        return NetworkPerformance.objects.filter(network=network, date=target_date).first()

    def get_hourly_series(self, network, hours: int = 24) -> django_models.QuerySet:
        cutoff = timezone.now() - timedelta(hours=hours)
        return HourlyStat.objects.filter(
            network=network
        ).order_by("-date", "-hour")[:hours]


# ── Module-level repository instances ─────────────────────────────────────────

network_repo       = NetworkRepository()
postback_repo      = PostbackRawLogRepository()
conversion_repo    = ConversionRepository()
click_repo         = ClickRepository()
dedup_repo         = DeduplicationRepository()
blacklist_repo     = BlacklistRepository()
fraud_repo         = FraudRepository()
queue_repo         = QueueRepository()
analytics_repo     = AnalyticsRepository()
