"""
DATABASE_MODELS/offerwall_model.py
=====================================
QuerySet + Manager for Offerwall, Offer, OfferCompletion.
"""
from __future__ import annotations
from decimal import Decimal
from datetime import date, timedelta

from django.db import models
from django.db.models import (
    Avg, BigIntegerField, Count, DecimalField,
    ExpressionWrapper, F, Q, Sum,
)
from django.utils import timezone


class OfferwallQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def featured(self):
        return self.filter(is_active=True, is_featured=True)

    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

    def for_network(self, network_id):
        return self.filter(network_id=network_id)

    def ordered(self):
        return self.order_by('sort_order', 'name')


class OfferwallManager(models.Manager):
    def get_queryset(self):
        return OfferwallQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active().ordered()

    def featured(self):
        return self.get_queryset().featured().ordered()


class OfferQuerySet(models.QuerySet):
    def active(self):
        now = timezone.now()
        return self.filter(
            status='active',
        ).filter(
            Q(available_from__isnull=True) | Q(available_from__lte=now)
        ).filter(
            Q(expiry_date__isnull=True) | Q(expiry_date__gt=now)
        )

    def for_offerwall(self, offerwall_id):
        return self.filter(offerwall_id=offerwall_id)

    def for_user(self, user):
        """Exclude already-completed offers for this user."""
        from ..models import OfferCompletion
        completed = OfferCompletion.objects.filter(
            user=user, status='approved'
        ).values_list('offer_id', flat=True)
        return self.exclude(id__in=completed)

    def for_country(self, country: str):
        return self.filter(
            Q(target_countries=[]) | Q(target_countries__contains=[country.upper()])
        )

    def for_device(self, device_type: str):
        return self.filter(
            Q(target_devices=[]) | Q(target_devices__contains=[device_type.lower()])
        )

    def by_type(self, offer_type: str):
        return self.filter(offer_type=offer_type)

    def featured(self):
        return self.filter(is_featured=True)

    def hot(self):
        return self.filter(is_hot=True)

    def expiring_soon(self, hours: int = 24):
        cutoff = timezone.now() + timedelta(hours=hours)
        return self.active().filter(expiry_date__lte=cutoff)

    def high_value(self, min_points: Decimal = Decimal('500.00')):
        return self.active().filter(point_value__gte=min_points)

    def with_completion_stats(self):
        return self.annotate(
            completion_count=Count(
                'monetization_tools_offercompletion_offer',
                filter=Q(monetization_tools_offercompletion_offer__status='approved'),
            )
        )

    def recommended(self, user, country: str = None, device_type: str = None):
        """Personalised offer list for a user."""
        qs = self.active().for_user(user)
        if country:
            qs = qs.for_country(country)
        if device_type:
            qs = qs.for_device(device_type)
        return qs.order_by('-is_featured', '-is_hot', '-point_value')


class OfferManager(models.Manager):
    def get_queryset(self):
        return OfferQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def for_user(self, user, country: str = None, device_type: str = None):
        return self.get_queryset().active().for_user(user)

    def recommended(self, user, country: str = None, device_type: str = None):
        return self.get_queryset().recommended(user, country, device_type)

    def expiring_soon(self, hours: int = 24):
        return self.get_queryset().expiring_soon(hours)


class OfferCompletionQuerySet(models.QuerySet):

    def for_user(self, user):
        return self.filter(user=user)

    def for_offer(self, offer_id):
        return self.filter(offer_id=offer_id)

    def pending(self):
        return self.filter(status='pending')

    def approved(self):
        return self.filter(status='approved')

    def fraud(self):
        return self.filter(status='fraud')

    def high_fraud(self, threshold: int = 70):
        return self.filter(fraud_score__gte=threshold, status='pending')

    def today_for_user(self, user):
        return self.filter(user=user, created_at__date=timezone.now().date())

    def in_date_range(self, start: date, end: date):
        return self.filter(created_at__date__gte=start, created_at__date__lte=end)

    def pending_value(self):
        return self.pending().aggregate(
            count=Count('id'),
            total_reward=Sum('reward_amount'),
            total_payout=Sum('payout_amount'),
        )

    def daily_approvals(self, days: int = 30):
        from django.db.models.functions import TruncDate
        return (
            self.approved()
                .filter(approved_at__gte=timezone.now() - timedelta(days=days))
                .annotate(day=TruncDate('approved_at'))
                .values('day')
                .annotate(count=Count('id'), total_reward=Sum('reward_amount'))
                .order_by('day')
        )

    def top_networks(self, limit: int = 10):
        return (
            self.approved()
                .values('offer__offerwall__network__display_name')
                .annotate(count=Count('id'), total=Sum('payout_amount'))
                .order_by('-total')[:limit]
        )

    def fraud_summary(self):
        return self.aggregate(
            total=Count('id'),
            fraud=Count('id', filter=Q(status='fraud')),
            high_score=Count('id', filter=Q(fraud_score__gte=70)),
            vpn=Count('id', filter=Q(is_vpn=True)),
            proxy=Count('id', filter=Q(is_proxy=True)),
        )


class OfferCompletionManager(models.Manager):
    def get_queryset(self):
        return OfferCompletionQuerySet(self.model, using=self._db)

    def pending(self):
        return self.get_queryset().pending().select_related('user', 'offer')

    def high_fraud_pending(self, threshold: int = 70):
        return self.get_queryset().high_fraud(threshold).select_related('user', 'offer')

    def for_user(self, user):
        return self.get_queryset().for_user(user).select_related('offer').order_by('-created_at')

    def today_count(self, user) -> int:
        return self.get_queryset().today_for_user(user).count()

    def fraud_summary(self):
        return self.get_queryset().fraud_summary()
