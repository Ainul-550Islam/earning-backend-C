"""
DATABASE_MODELS/ad_unit_model.py
==================================
QuerySet + Manager for AdUnit and AdCreative.
"""
from __future__ import annotations
from decimal import Decimal
from django.db import models
from django.db.models import Avg, BigIntegerField, Count, DecimalField, ExpressionWrapper, F, Q, Sum


class AdUnitQuerySet(models.QuerySet):

    def active(self):
        return self.filter(is_active=True)

    def for_campaign(self, campaign_id):
        return self.filter(campaign_id=campaign_id)

    def for_network(self, network_id):
        return self.filter(ad_network_id=network_id)

    def by_format(self, ad_format: str):
        return self.filter(ad_format=ad_format)

    def with_ctr(self):
        from django.db.models import Case, Value, When
        return self.annotate(
            computed_ctr=Case(
                When(impressions__gt=0,
                     then=ExpressionWrapper(
                         F('clicks') * Value(Decimal('100.0')) / F('impressions'),
                         output_field=DecimalField(max_digits=7, decimal_places=4),
                     )),
                default=Value(Decimal('0.0000')),
                output_field=DecimalField(max_digits=7, decimal_places=4),
            )
        )

    def with_ecpm(self):
        from django.db.models import Case, Value, When
        return self.annotate(
            computed_ecpm=Case(
                When(impressions__gt=0,
                     then=ExpressionWrapper(
                         F('revenue') / F('impressions') * Value(Decimal('1000')),
                         output_field=DecimalField(max_digits=10, decimal_places=4),
                     )),
                default=Value(Decimal('0.0000')),
                output_field=DecimalField(max_digits=10, decimal_places=4),
            )
        )

    def performance_summary(self):
        return self.aggregate(
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_revenue=Sum('revenue'),
        )

    def top_performers(self, limit: int = 10):
        return self.active().order_by('-revenue')[:limit]


class AdUnitManager(models.Manager):
    def get_queryset(self):
        return AdUnitQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def for_campaign(self, campaign_id):
        return self.get_queryset().active().for_campaign(campaign_id)

    def top_by_revenue(self, limit: int = 10):
        return self.get_queryset().with_ctr().with_ecpm().top_performers(limit)


class AdCreativeQuerySet(models.QuerySet):

    def approved(self):
        return self.filter(status='approved', is_active=True)

    def pending_review(self):
        return self.filter(status='pending')

    def for_unit(self, ad_unit_id):
        return self.filter(ad_unit_id=ad_unit_id)

    def by_type(self, creative_type: str):
        return self.filter(creative_type=creative_type)

    def top_by_ctr(self, limit: int = 10):
        return (
            self.approved()
                .filter(impressions__gt=0)
                .annotate(
                    ctr=ExpressionWrapper(
                        F('clicks') * Decimal('100.0') / F('impressions'),
                        output_field=DecimalField(max_digits=7, decimal_places=4),
                    )
                )
                .order_by('-ctr')[:limit]
        )


class AdCreativeManager(models.Manager):
    def get_queryset(self):
        return AdCreativeQuerySet(self.model, using=self._db)

    def approved(self):
        return self.get_queryset().approved()

    def pending(self):
        return self.get_queryset().pending_review()
