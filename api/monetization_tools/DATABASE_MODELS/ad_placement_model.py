"""
DATABASE_MODELS/ad_placement_model.py
=======================================
QuerySet + Manager for AdPlacement and WaterfallConfig.
"""
from __future__ import annotations
from decimal import Decimal
from django.db import models
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Prefetch


class AdPlacementQuerySet(models.QuerySet):

    def active(self):
        return self.filter(is_active=True)

    def for_screen(self, screen_name: str):
        return self.filter(screen_name=screen_name)

    def for_network(self, network_id):
        return self.filter(ad_network_id=network_id)

    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

    def by_position(self, position: str):
        return self.filter(position=position)

    def with_ad_units(self):
        """Prefetch related ad units for bulk operations."""
        return self.select_related('ad_unit', 'ad_unit__campaign', 'ad_network')

    def fullscreen_placements(self):
        return self.filter(position='fullscreen', is_active=True)

    def with_frequency_cap(self):
        return self.filter(frequency_cap__gt=0)

    def refreshable(self):
        """Placements that auto-refresh."""
        return self.filter(refresh_rate__gt=0)

    def by_placement_key(self, key: str):
        return self.filter(placement_key=key, is_active=True).first()


class AdPlacementManager(models.Manager):
    def get_queryset(self):
        return AdPlacementQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def for_screen(self, screen_name: str, tenant=None):
        qs = self.get_queryset().active().for_screen(screen_name).with_ad_units()
        if tenant:
            qs = qs.for_tenant(tenant)
        return qs

    def get_by_key(self, placement_key: str, tenant=None):
        qs = self.get_queryset().active()
        if tenant:
            qs = qs.for_tenant(tenant)
        return qs.filter(placement_key=placement_key).select_related(
            'ad_unit', 'ad_unit__campaign', 'ad_network'
        ).first()


class WaterfallConfigQuerySet(models.QuerySet):

    def active(self):
        return self.filter(is_active=True)

    def for_ad_unit(self, ad_unit_id):
        return self.filter(ad_unit_id=ad_unit_id)

    def ordered_waterfall(self, ad_unit_id):
        """Return waterfall entries in priority order — used by mediation engine."""
        return (
            self.active()
                .for_ad_unit(ad_unit_id)
                .select_related('ad_network')
                .order_by('priority')
        )

    def above_floor(self, ecpm: Decimal):
        return self.filter(floor_ecpm__lte=ecpm)

    def bidding_partners(self):
        return self.filter(is_header_bidding=True, is_active=True)


class WaterfallConfigManager(models.Manager):
    def get_queryset(self):
        return WaterfallConfigQuerySet(self.model, using=self._db)

    def get_waterfall(self, ad_unit_id):
        """Main entry point for mediation — returns ordered, active waterfall."""
        return self.get_queryset().ordered_waterfall(ad_unit_id)

    def get_bidders(self, ad_unit_id):
        return self.get_queryset().for_ad_unit(ad_unit_id).bidding_partners()
