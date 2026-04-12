"""
DATABASE_MODELS/ad_campaign_model.py
=====================================
Standalone querysets, managers, and annotation helpers for AdCampaign.
Keeps advanced ORM logic out of models.py (single-responsibility).
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import (
    BigIntegerField, Case, DecimalField, ExpressionWrapper, F,
    OuterRef, Q, Subquery, Sum, Value, When,
)
from django.utils import timezone


# ============================================================================
# Queryset
# ============================================================================

class AdCampaignQuerySet(models.QuerySet):

    def active(self):
        now = timezone.now()
        return self.filter(
            status='active',
            start_date__lte=now,
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=now))

    def with_budget_remaining(self):
        return self.annotate(
            budget_remaining=ExpressionWrapper(
                F('total_budget') - F('spent_budget'),
                output_field=DecimalField(max_digits=16, decimal_places=4),
            )
        )

    def with_ctr(self):
        return self.annotate(
            computed_ctr=Case(
                When(
                    total_impressions__gt=0,
                    then=ExpressionWrapper(
                        F('total_clicks') * Value(Decimal('100.0')) / F('total_impressions'),
                        output_field=DecimalField(max_digits=7, decimal_places=4),
                    ),
                ),
                default=Value(Decimal('0.0000')),
                output_field=DecimalField(max_digits=7, decimal_places=4),
            )
        )

    def with_ecpm(self):
        return self.annotate(
            computed_ecpm=Case(
                When(
                    total_impressions__gt=0,
                    then=ExpressionWrapper(
                        F('spent_budget') / F('total_impressions') * Value(Decimal('1000')),
                        output_field=DecimalField(max_digits=10, decimal_places=4),
                    ),
                ),
                default=Value(Decimal('0.0000')),
                output_field=DecimalField(max_digits=10, decimal_places=4),
            )
        )

    def budget_exhausted(self):
        return self.filter(spent_budget__gte=F('total_budget'))

    def ending_within_hours(self, hours: int = 24):
        now   = timezone.now()
        limit = now + timezone.timedelta(hours=hours)
        return self.filter(
            status='active',
            end_date__isnull=False,
            end_date__gte=now,
            end_date__lte=limit,
        )

    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

    def revenue_summary(self):
        return self.aggregate(
            total_spent=Sum('spent_budget'),
            total_imp=Sum('total_impressions'),
            total_clk=Sum('total_clicks'),
            total_cvr=Sum('total_conversions'),
        )


class AdCampaignManager(models.Manager):
    def get_queryset(self):
        return AdCampaignQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def with_full_kpis(self):
        return (
            self.get_queryset()
                .with_budget_remaining()
                .with_ctr()
                .with_ecpm()
        )
