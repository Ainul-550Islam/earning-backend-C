"""
conversion_tracking/conversion_api.py
───────────────────────────────────────
Public API for conversion operations. Centralises all conversion
CRUD operations behind a clean interface for views and services to call.
"""
from __future__ import annotations
import logging
from decimal import Decimal
from typing import Optional, List
from django.db.models import QuerySet
from ..models import Conversion, AdNetworkConfig
from ..enums import ConversionStatus

logger = logging.getLogger(__name__)


class ConversionAPI:

    def get(self, conversion_id: str) -> Optional[Conversion]:
        try:
            return Conversion.objects.select_related("user", "network", "raw_log").get(pk=conversion_id)
        except Conversion.DoesNotExist:
            return None

    def get_for_user(self, user, days: int = 30) -> QuerySet:
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return Conversion.objects.filter(
            user=user,
            converted_at__gte=cutoff,
        ).order_by("-converted_at")

    def get_pending(self) -> QuerySet:
        return Conversion.objects.pending().select_related("user", "network")

    def get_uncredited(self) -> QuerySet:
        """Approved conversions not yet credited to wallet."""
        return Conversion.objects.not_credited().select_related("user", "network")

    def approve(self, conversion_id: str) -> Optional[Conversion]:
        conv = self.get(conversion_id)
        if conv and conv.status == ConversionStatus.PENDING:
            conv.approve()
            logger.info("API: conversion approved %s", conversion_id)
        return conv

    def reject(self, conversion_id: str, reason: str = "") -> Optional[Conversion]:
        conv = self.get(conversion_id)
        if conv:
            conv.reject(reason=reason)
            logger.info("API: conversion rejected %s reason=%s", conversion_id, reason)
        return conv

    def reverse(self, conversion_id: str, reason: str = "") -> Optional[Conversion]:
        from .conversion_manager import conversion_manager
        conv = self.get(conversion_id)
        if conv:
            conversion_manager.reverse_conversion(conv, reason=reason)
        return conv

    def bulk_approve(self, conversion_ids: List[str]) -> int:
        """Bulk approve pending conversions. Returns count approved."""
        count = Conversion.objects.filter(
            pk__in=conversion_ids,
            status=ConversionStatus.PENDING,
        ).update(status=ConversionStatus.APPROVED)
        logger.info("API: bulk approved %d conversions", count)
        return count

    def get_stats(self, user=None, network=None, days: int = 30) -> dict:
        from django.db.models import Sum, Count, Avg
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        qs = Conversion.objects.filter(
            converted_at__gte=cutoff,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        )
        if user:
            qs = qs.filter(user=user)
        if network:
            qs = qs.filter(network=network)
        agg = qs.aggregate(
            total=Count("id"),
            total_payout=Sum("actual_payout"),
            total_points=Sum("points_awarded"),
            avg_payout=Avg("actual_payout"),
        )
        return {
            "total_conversions": agg["total"] or 0,
            "total_payout_usd":  float(agg["total_payout"] or 0),
            "total_points":      agg["total_points"] or 0,
            "avg_payout_usd":    float(agg["avg_payout"] or 0),
            "period_days":       days,
        }


# Module-level singleton
conversion_api = ConversionAPI()
