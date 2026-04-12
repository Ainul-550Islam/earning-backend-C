"""
api/monetization_tools/models.py
==================================
PRODUCTION-READY — Billion-Request Monetization System
=======================================================

Architecture decisions:
  • Every money field → DecimalField. ZERO floats.
  • Every counter → BigIntegerField (overflow-safe at scale).
  • UUID surrogates — uuid4, editable=False.
  • Composite DB indexes on every hot query path.
  • Atomic constraint enforcement (UniqueConstraint, CheckConstraint).
  • Multi-tenant isolation via TenantScopedModel abstract base.
  • related_name pattern: %(app_label)s_%(class)s_<field> — zero conflicts.

Sections
--------
  1.  Base / Abstract
  2.  Ad Core            AdNetwork · AdCampaign · AdUnit · AdPlacement
  3.  Ad Performance     AdPerformanceHourly · AdPerformanceDaily · AdNetworkDailyStat
  4.  Offerwall          Offerwall · Offer · OfferCompletion
  5.  Reward             RewardTransaction · PointLedgerSnapshot
  6.  Revenue Logs       ImpressionLog · ClickLog · ConversionLog · RevenueDailySummary
  7.  Subscription       SubscriptionPlan · UserSubscription · InAppPurchase
  8.  Payment            PaymentTransaction · RecurringBilling
  9.  Gamification       UserLevel · Achievement · LeaderboardRank · SpinWheelLog
  10. Optimization       ABTest · ABTestAssignment · WaterfallConfig · FloorPriceConfig
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import CheckConstraint, F, Q, UniqueConstraint
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ============================================================================
# § 0  HELPERS
# ============================================================================

def _list():
    return []


def _dict():
    return {}


# ============================================================================
# § 1  ABSTRACT BASE
# ============================================================================

class TenantScopedModel(models.Model):
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_index=True,
        related_name='%(app_label)s_%(class)s_tenant',
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ============================================================================
# § 2  AD CORE
# ============================================================================

class AdNetwork(TenantScopedModel):
    class NetworkType(models.TextChoices):
        ADMOB      = 'admob',      _('Google AdMob')
        FACEBOOK   = 'facebook',   _('Facebook AN')
        APPLOVIN   = 'applovin',   _('AppLovin MAX')
        IRONSOURCE = 'ironsource', _('IronSource')
        UNITY      = 'unity',      _('Unity Ads')
        VUNGLE     = 'vungle',     _('Vungle / Liftoff')
        CHARTBOOST = 'chartboost', _('Chartboost')
        TAPJOY     = 'tapjoy',     _('Tapjoy')
        FYBER      = 'fyber',      _('Fyber / Digital Turbine')
        MINTEGRAL  = 'mintegral',  _('Mintegral')
        PANGLE     = 'pangle',     _('Pangle (TikTok)')
        INMOBI     = 'inmobi',     _('InMobi')
        ADCOLONY   = 'adcolony',   _('AdColony')
        MOLOCO     = 'moloco',     _('Moloco')
        AMAZON     = 'amazon',     _('Amazon Publisher Services')
        PUBMATIC   = 'pubmatic',   _('PubMatic')
        CRITEO     = 'criteo',     _('Criteo')
        CUSTOM     = 'custom',     _('Custom / In-House')

    network_id   = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    network_type = models.CharField(max_length=30, choices=NetworkType.choices, null=True, blank=True)
    display_name = models.CharField(max_length=120, null=True, blank=True)
    description  = models.TextField(blank=True, null=True)
    logo_url     = models.URLField(blank=True, null=True)

    # Credentials — encrypted at rest in production
    app_id            = models.CharField(max_length=255, blank=True, null=True)
    api_key           = models.CharField(max_length=512, blank=True, null=True)
    secret_key        = models.CharField(max_length=512, blank=True, null=True)
    reporting_api_key = models.CharField(max_length=512, blank=True, null=True)
    postback_url      = models.URLField(blank=True, null=True)
    postback_secret   = models.CharField(max_length=256, blank=True, null=True)

    # Mediation
    is_active  = models.BooleanField(default=True, db_index=True)
    is_bidding = models.BooleanField(default=False, help_text=_("Header-bidding participant"))
    priority   = models.PositiveSmallIntegerField(default=100)

    # Financial — Decimal, never Float
    floor_ecpm   = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    revenue_share = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0.7000'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
    )
    timeout_ms        = models.PositiveIntegerField(default=5000)
    max_retry         = models.PositiveSmallIntegerField(default=2)
    countries_served  = models.JSONField(default=_list, blank=True)
    extra_config      = models.JSONField(default=_dict, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_ad_networks'
        verbose_name = _('Ad Network')
        verbose_name_plural = _('Ad Networks')
        ordering = ['priority', 'display_name']
        constraints = [
            UniqueConstraint(fields=['tenant', 'network_type'], name='mt_adnetwork_unique_type_per_tenant'),
            CheckConstraint(check=Q(floor_ecpm__gte=0),         name='mt_adnetwork_floor_non_neg'),
            CheckConstraint(check=Q(revenue_share__gte=0) & Q(revenue_share__lte=1), name='mt_adnetwork_revshare_range'),
        ]
        indexes = [
            models.Index(fields=['network_type', 'is_active'], name='mt_an_type_active_idx'),
            models.Index(fields=['priority', 'is_active'],     name='mt_an_priority_idx'),
        ]

    def __str__(self):
        return f"{self.display_name} [{self.network_type}]"


class AdCampaign(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT    = 'draft',    _('Draft')
        ACTIVE   = 'active',   _('Active')
        PAUSED   = 'paused',   _('Paused')
        ENDED    = 'ended',    _('Ended')
        ARCHIVED = 'archived', _('Archived')

    class PricingModel(models.TextChoices):
        CPM  = 'cpm',  _('CPM')
        CPC  = 'cpc',  _('CPC')
        CPA  = 'cpa',  _('CPA')
        CPI  = 'cpi',  _('CPI')
        CPE  = 'cpe',  _('CPE')
        FLAT = 'flat', _('Flat Rate')

    campaign_id      = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name             = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    description      = models.TextField(blank=True, null=True)
    advertiser_name  = models.CharField(max_length=200, blank=True, null=True)
    advertiser_email = models.EmailField(blank=True, null=True)
    external_id      = models.CharField(max_length=200, blank=True, null=True, db_index=True)

    pricing_model = models.CharField(max_length=10, choices=PricingModel.choices, default=PricingModel.CPM, null=True, blank=True)
    bid_amount    = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0.0000'))

    # Budget — ALL Decimal, zero floats
    total_budget  = models.DecimalField(max_digits=16, decimal_places=4,
                                         validators=[MinValueValidator(Decimal('0.0001'))])
    daily_budget  = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)
    hourly_budget = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    spent_budget  = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))
    daily_spent   = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))

    # Targeting
    target_countries = models.JSONField(default=_list, blank=True)
    target_cities    = models.JSONField(default=_list, blank=True)
    target_languages = models.JSONField(default=_list, blank=True)
    target_devices   = models.JSONField(default=_list, blank=True)
    target_os        = models.JSONField(default=_list, blank=True)
    target_age_min   = models.PositiveSmallIntegerField(null=True, blank=True)
    target_age_max   = models.PositiveSmallIntegerField(null=True, blank=True)
    excluded_sites   = models.JSONField(default=_list, blank=True)

    start_date = models.DateTimeField(db_index=True)
    end_date   = models.DateTimeField(null=True, blank=True, db_index=True)
    status     = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True, null=True, blank=True)

    # Denormalised counters — updated via F() expressions (atomic, no race)
    total_impressions = models.BigIntegerField(default=0)
    total_clicks      = models.BigIntegerField(default=0)
    total_conversions = models.BigIntegerField(default=0)
    total_installs    = models.BigIntegerField(default=0)

    freq_cap_per_user_day  = models.PositiveSmallIntegerField(default=0)
    freq_cap_per_user_hour = models.PositiveSmallIntegerField(default=0)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_ad_campaigns'
        verbose_name = _('Ad Campaign')
        verbose_name_plural = _('Ad Campaigns')
        ordering = ['-created_at']
        constraints = [
            CheckConstraint(check=Q(total_budget__gt=0), name='mt_campaign_budget_positive'),
            CheckConstraint(
                check=Q(end_date__isnull=True) | Q(end_date__gt=F('start_date')),
                name='mt_campaign_end_after_start',
            ),
            CheckConstraint(
                check=Q(daily_budget__isnull=True) | Q(daily_budget__lte=F('total_budget')),
                name='mt_campaign_daily_lte_total',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'start_date', 'end_date'], name='mt_camp_status_schedule_idx'),
            models.Index(fields=['tenant', 'status'],                 name='mt_camp_tenant_status_idx'),
            models.Index(fields=['campaign_id'],                      name='mt_camp_uuid_idx'),
        ]

    def __str__(self):
        return f"{self.name} [{self.status}]"

    @property
    def remaining_budget(self) -> Decimal:
        return self.total_budget - self.spent_budget

    @property
    def budget_utilisation_pct(self) -> Decimal:
        if not self.total_budget:
            return Decimal('0.00')
        return (self.spent_budget / self.total_budget * 100).quantize(Decimal('0.01'))

    @property
    def ctr(self) -> Decimal:
        if not self.total_impressions:
            return Decimal('0.0000')
        return (Decimal(self.total_clicks) / Decimal(self.total_impressions) * 100).quantize(Decimal('0.0001'))

    @property
    def cvr(self) -> Decimal:
        if not self.total_clicks:
            return Decimal('0.0000')
        return (Decimal(self.total_conversions) / Decimal(self.total_clicks) * 100).quantize(Decimal('0.0001'))

    @property
    def ecpm(self) -> Decimal:
        if not self.total_impressions:
            return Decimal('0.0000')
        return (self.spent_budget / Decimal(self.total_impressions) * 1000).quantize(Decimal('0.0001'))

    @property
    def is_budget_exhausted(self) -> bool:
        return self.spent_budget >= self.total_budget

    def clean(self):
        errors = {}
        if self.end_date and self.end_date <= self.start_date:
            errors['end_date'] = _("End date must be after start date.")
        if self.daily_budget and self.daily_budget > self.total_budget:
            errors['daily_budget'] = _("Daily budget cannot exceed total budget.")
        if self.target_age_min and self.target_age_max and self.target_age_min > self.target_age_max:
            errors['target_age_min'] = _("Min age cannot exceed max age.")
        if errors:
            raise ValidationError(errors)


class AdUnit(TenantScopedModel):
    class AdFormat(models.TextChoices):
        BANNER         = 'banner',         _('Banner')
        INTERSTITIAL   = 'interstitial',   _('Interstitial')
        REWARDED_VIDEO = 'rewarded_video', _('Rewarded Video')
        NATIVE         = 'native',         _('Native Ad')
        PLAYABLE       = 'playable',       _('Playable Ad')
        CAROUSEL       = 'carousel',       _('Carousel')
        AUDIO          = 'audio',          _('Audio Ad')
        OFFERWALL      = 'offerwall',      _('Offerwall Ad')
        INSTREAM_VIDEO = 'instream_video', _('Instream Video')
        OUTSTREAM      = 'outstream',      _('Outstream Video')

    unit_id  = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name     = models.CharField(max_length=255, null=True, blank=True)

    # Relations — campaign owner + network serving
    campaign   = models.ForeignKey(AdCampaign, on_delete=models.CASCADE,
                                    related_name='%(app_label)s_%(class)s_campaign')
    ad_network = models.ForeignKey(AdNetwork, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='%(app_label)s_%(class)s_ad_network')

    ad_format       = models.CharField(max_length=20, choices=AdFormat.choices, default=AdFormat.BANNER, db_index=True, null=True, blank=True)
    width           = models.PositiveSmallIntegerField(null=True, blank=True)
    height          = models.PositiveSmallIntegerField(null=True, blank=True)
    creative_url    = models.URLField(max_length=2048, blank=True, null=True)
    creative_type   = models.CharField(max_length=30, blank=True, null=True)
    destination_url = models.URLField(max_length=2048, blank=True, null=True)
    cta_text        = models.CharField(max_length=100, blank=True, null=True)
    vast_tag_url    = models.URLField(max_length=2048, blank=True, null=True)

    # Unit-level floor overrides network floor
    floor_ecpm = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    is_active  = models.BooleanField(default=True, db_index=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date   = models.DateTimeField(null=True, blank=True)

    # Denormalised perf counters
    impressions = models.BigIntegerField(default=0)
    clicks      = models.BigIntegerField(default=0)
    revenue     = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_ad_units'
        verbose_name = _('Ad Unit')
        verbose_name_plural = _('Ad Units')
        ordering = ['-created_at']
        constraints = [
            CheckConstraint(
                check=Q(floor_ecpm__isnull=True) | Q(floor_ecpm__gte=0),
                name='mt_adunit_floor_non_negative',
            ),
        ]
        indexes = [
            models.Index(fields=['campaign', 'ad_format', 'is_active'], name='mt_unit_camp_format_idx'),
            models.Index(fields=['ad_network', 'ad_format'],            name='mt_unit_network_format_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.ad_format})"

    @property
    def effective_floor_ecpm(self) -> Decimal:
        if self.floor_ecpm is not None:
            return self.floor_ecpm
        if self.ad_network_id:
            return self.ad_network.floor_ecpm
        return Decimal('0.0000')

    @property
    def ctr(self) -> Decimal:
        if not self.impressions:
            return Decimal('0.0000')
        return (Decimal(self.clicks) / Decimal(self.impressions) * 100).quantize(Decimal('0.0001'))


class AdPlacement(TenantScopedModel):
    class Position(models.TextChoices):
        TOP          = 'top',          _('Top')
        BOTTOM       = 'bottom',       _('Bottom')
        MID_CONTENT  = 'mid_content',  _('Mid-Content')
        FULLSCREEN   = 'fullscreen',   _('Fullscreen / Interstitial')
        SIDEBAR      = 'sidebar',      _('Sidebar')
        AFTER_ACTION = 'after_action', _('After User Action')
        ON_EXIT      = 'on_exit',      _('On Exit Intent')
        IN_FEED      = 'in_feed',      _('In-Feed / Native')

    # The critical three-way join: AdUnit → AdPlacement ← AdNetwork
    ad_unit    = models.ForeignKey(AdUnit, on_delete=models.CASCADE,
                                    related_name='%(app_label)s_%(class)s_ad_unit')
    ad_network = models.ForeignKey(AdNetwork, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='%(app_label)s_%(class)s_ad_network')

    screen_name   = models.CharField(max_length=200, db_index=True, null=True, blank=True)
    position      = models.CharField(max_length=20, choices=Position.choices, default=Position.BOTTOM, null=True, blank=True)
    placement_key = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    refresh_rate  = models.PositiveSmallIntegerField(default=30)
    frequency_cap = models.PositiveSmallIntegerField(default=0)
    is_active     = models.BooleanField(default=True, db_index=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_ad_placements'
        verbose_name = _('Ad Placement')
        verbose_name_plural = _('Ad Placements')
        ordering = ['screen_name', 'position']
        constraints = [
            UniqueConstraint(
                fields=['tenant', 'placement_key'],
                condition=Q(placement_key__isnull=False),
                name='mt_placement_unique_key_per_tenant',
            ),
        ]
        indexes = [
            models.Index(fields=['screen_name', 'position', 'is_active'], name='mt_place_screen_pos_idx'),
        ]

    def __str__(self):
        return f"{self.screen_name} / {self.position}"


# ============================================================================
# § 3  AD PERFORMANCE — Pre-aggregated analytics for O(1) dashboard reads
# ============================================================================

class AdPerformanceHourly(TenantScopedModel):
    """
    Hourly rollup per (ad_unit, network, country, device).
    eCPM / FillRate / CTR stored pre-computed — no GROUP BY on reads.
    Written by background worker, NOT on the request path.
    """

    ad_unit    = models.ForeignKey(AdUnit, on_delete=models.CASCADE,
                                    related_name='%(app_label)s_%(class)s_ad_unit')
    ad_network = models.ForeignKey(AdNetwork, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='%(app_label)s_%(class)s_ad_network')

    hour_bucket = models.DateTimeField(db_index=True, help_text="Truncated to hour (UTC)")
    country     = models.CharField(max_length=2,  blank=True, null=True)
    device_type = models.CharField(max_length=15, blank=True, null=True)
    os          = models.CharField(max_length=15, blank=True, null=True)

    requests    = models.BigIntegerField(default=0)
    impressions = models.BigIntegerField(default=0)
    clicks      = models.BigIntegerField(default=0)
    conversions = models.BigIntegerField(default=0)
    installs    = models.BigIntegerField(default=0)

    revenue_usd      = models.DecimalField(max_digits=16, decimal_places=6, default=Decimal('0.000000'))
    advertiser_spend = models.DecimalField(max_digits=16, decimal_places=6, default=Decimal('0.000000'))

    # Pre-computed KPIs — core scalability feature
    ecpm             = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    fill_rate        = models.DecimalField(max_digits=7,  decimal_places=4, default=Decimal('0.0000'))
    ctr              = models.DecimalField(max_digits=7,  decimal_places=4, default=Decimal('0.0000'))
    cvr              = models.DecimalField(max_digits=7,  decimal_places=4, default=Decimal('0.0000'))
    viewability_rate = models.DecimalField(max_digits=7,  decimal_places=4, default=Decimal('0.0000'))

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_ad_performance_hourly'
        verbose_name = _('Ad Performance (Hourly)')
        verbose_name_plural = _('Ad Performance (Hourly)')
        ordering = ['-hour_bucket']
        constraints = [
            UniqueConstraint(
                fields=['tenant', 'ad_unit', 'ad_network', 'hour_bucket', 'country', 'device_type'],
                name='mt_perf_hourly_unique_bucket',
            ),
        ]
        indexes = [
            models.Index(fields=['ad_unit', 'hour_bucket'],           name='mt_ph_unit_hour_idx'),
            models.Index(fields=['ad_network', 'hour_bucket'],        name='mt_ph_network_hour_idx'),
            models.Index(fields=['hour_bucket', 'country'],           name='mt_ph_hour_country_idx'),
            models.Index(fields=['tenant', 'hour_bucket'],            name='mt_ph_tenant_hour_idx'),
        ]

    def __str__(self):
        return f"Hourly | {self.ad_unit_id} | {self.hour_bucket} | eCPM={self.ecpm}"

    @classmethod
    def recompute_kpis(cls, obj: 'AdPerformanceHourly') -> None:
        """Recompute eCPM, fill_rate, CTR, CVR in-memory before save."""
        q = Decimal('0.0001')
        if obj.impressions:
            obj.ecpm = (obj.revenue_usd / Decimal(obj.impressions) * 1000).quantize(q)
            obj.ctr  = (Decimal(obj.clicks) / Decimal(obj.impressions) * 100).quantize(q)
        else:
            obj.ecpm = Decimal('0.0000')
            obj.ctr  = Decimal('0.0000')
        if obj.requests:
            obj.fill_rate = (Decimal(obj.impressions) / Decimal(obj.requests) * 100).quantize(q)
        else:
            obj.fill_rate = Decimal('0.0000')
        if obj.clicks:
            obj.cvr = (Decimal(obj.conversions) / Decimal(obj.clicks) * 100).quantize(q)
        else:
            obj.cvr = Decimal('0.0000')


class AdPerformanceDaily(TenantScopedModel):
    """Daily rollup aggregated from AdPerformanceHourly. Source of truth for billing."""

    ad_unit    = models.ForeignKey(AdUnit,     on_delete=models.CASCADE,
                                    related_name='%(app_label)s_%(class)s_ad_unit')
    ad_network = models.ForeignKey(AdNetwork,  on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='%(app_label)s_%(class)s_ad_network')
    campaign   = models.ForeignKey(AdCampaign, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='%(app_label)s_%(class)s_campaign')

    date        = models.DateField(db_index=True)
    country     = models.CharField(max_length=2, blank=True, null=True)
    device_type = models.CharField(max_length=15, blank=True, null=True)

    requests    = models.BigIntegerField(default=0)
    impressions = models.BigIntegerField(default=0)
    clicks      = models.BigIntegerField(default=0)
    conversions = models.BigIntegerField(default=0)
    installs    = models.BigIntegerField(default=0)

    revenue_cpm      = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))
    revenue_cpc      = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))
    revenue_cpa      = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))
    revenue_cpi      = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))
    total_revenue    = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))
    advertiser_spend = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))

    # Pre-computed KPIs
    ecpm      = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    fill_rate = models.DecimalField(max_digits=7,  decimal_places=4, default=Decimal('0.0000'))
    ctr       = models.DecimalField(max_digits=7,  decimal_places=4, default=Decimal('0.0000'))
    cvr       = models.DecimalField(max_digits=7,  decimal_places=4, default=Decimal('0.0000'))
    rpm       = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_ad_performance_daily'
        verbose_name = _('Ad Performance (Daily)')
        verbose_name_plural = _('Ad Performance (Daily)')
        ordering = ['-date']
        constraints = [
            UniqueConstraint(
                fields=['tenant', 'ad_unit', 'ad_network', 'campaign', 'date', 'country', 'device_type'],
                name='mt_perf_daily_unique_bucket',
            ),
        ]
        indexes = [
            models.Index(fields=['date', 'total_revenue'],  name='mt_pd_date_rev_idx'),
            models.Index(fields=['ad_network', 'date'],     name='mt_pd_network_date_idx'),
            models.Index(fields=['campaign', 'date'],       name='mt_pd_camp_date_idx'),
            models.Index(fields=['tenant', 'date'],         name='mt_pd_tenant_date_idx'),
        ]

    def __str__(self):
        return f"Daily | {self.date} | eCPM={self.ecpm} | Rev=${self.total_revenue}"


class AdNetworkDailyStat(TenantScopedModel):
    """Network-reported stats — used for revenue reconciliation."""

    ad_network           = models.ForeignKey(AdNetwork, on_delete=models.CASCADE,
                                              related_name='%(app_label)s_%(class)s_ad_network')
    date                 = models.DateField(db_index=True)
    reported_revenue     = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))
    reported_ecpm        = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    reported_impressions = models.BigIntegerField(default=0)
    reported_clicks      = models.BigIntegerField(default=0)
    fill_rate            = models.DecimalField(max_digits=7,  decimal_places=4, default=Decimal('0.0000'))
    discrepancy_pct      = models.DecimalField(max_digits=7,  decimal_places=4, default=Decimal('0.0000'))
    raw_response         = models.JSONField(default=_dict, blank=True)
    fetched_at           = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_ad_network_daily_stats'
        verbose_name = _('Ad Network Daily Stat')
        verbose_name_plural = _('Ad Network Daily Stats')
        ordering = ['-date']
        constraints = [
            UniqueConstraint(fields=['ad_network', 'date'], name='mt_an_daily_stat_unique'),
        ]

    def __str__(self):
        return f"{self.ad_network} | {self.date} | ${self.reported_revenue}"


# ============================================================================
# § 4  OFFERWALL
# ============================================================================

class Offerwall(TenantScopedModel):
    network     = models.ForeignKey(AdNetwork, on_delete=models.CASCADE,
                                     related_name='%(app_label)s_%(class)s_network')
    name        = models.CharField(max_length=200, null=True, blank=True)
    slug        = models.SlugField(max_length=200, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    logo_url    = models.URLField(blank=True, null=True)
    embed_url   = models.URLField(blank=True, null=True)
    is_active   = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False)
    sort_order  = models.PositiveSmallIntegerField(default=0)
    config      = models.JSONField(default=_dict, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_offerwalls'
        verbose_name = _('Offerwall')
        verbose_name_plural = _('Offerwalls')
        ordering = ['sort_order', 'name']
        constraints = [
            UniqueConstraint(fields=['tenant', 'slug'], name='mt_offerwall_slug_per_tenant'),
        ]

    def __str__(self):
        return self.name


class Offer(TenantScopedModel):
    class OfferType(models.TextChoices):
        APP_INSTALL  = 'app_install',  _('App Install')
        SURVEY       = 'survey',       _('Survey')
        QUIZ         = 'quiz',         _('Quiz')
        VIDEO        = 'video',        _('Video Ad')
        TRIAL        = 'trial',        _('Free Trial')
        SUBSCRIPTION = 'subscription', _('Subscription')
        PURCHASE     = 'purchase',     _('Purchase')
        SOCIAL       = 'social',       _('Social Action')
        GAME_PLAY    = 'game_play',    _('Game Play')
        REGISTRATION = 'registration', _('Registration')
        OTHER        = 'other',        _('Other')

    class Status(models.TextChoices):
        ACTIVE  = 'active',  _('Active')
        PAUSED  = 'paused',  _('Paused')
        EXPIRED = 'expired', _('Expired')
        PENDING = 'pending', _('Pending Approval')
        DRAFT   = 'draft',   _('Draft')

    offerwall = models.ForeignKey(Offerwall, on_delete=models.CASCADE,
                                   related_name='%(app_label)s_%(class)s_offerwall')

    external_offer_id = models.CharField(max_length=200, db_index=True, null=True, blank=True)
    title             = models.CharField(max_length=300, null=True, blank=True)
    description       = models.TextField(blank=True, null=True)
    requirements      = models.TextField(blank=True, null=True)
    offer_type        = models.CharField(max_length=20, choices=OfferType.choices,
                                          default=OfferType.OTHER, db_index=True, null=True, blank=True)
    status            = models.CharField(max_length=10, choices=Status.choices,
                                          default=Status.ACTIVE, db_index=True, null=True, blank=True)

    # Financials — Decimal only
    payout_usd       = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    point_value      = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    bonus_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'))
    currency         = models.CharField(max_length=5, default='USD', null=True, blank=True)

    target_countries         = models.JSONField(default=_list, blank=True)
    target_devices           = models.JSONField(default=_list, blank=True)
    target_os                = models.JSONField(default=_list, blank=True)
    min_age                  = models.PositiveSmallIntegerField(default=13)
    max_completions_per_user = models.PositiveSmallIntegerField(default=1)

    thumbnail_url = models.URLField(max_length=2048, blank=True, null=True)
    tracking_url  = models.URLField(max_length=2048, blank=True, null=True)
    preview_url   = models.URLField(max_length=2048, blank=True, null=True)

    is_featured   = models.BooleanField(default=False)
    is_hot        = models.BooleanField(default=False)
    is_exclusive  = models.BooleanField(default=False)

    available_from = models.DateTimeField(null=True, blank=True)
    expiry_date    = models.DateTimeField(null=True, blank=True, db_index=True)

    # Denormalised stats (F() atomic updates)
    total_completions = models.BigIntegerField(default=0)
    total_revenue_usd = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))
    conversion_rate   = models.DecimalField(max_digits=7,  decimal_places=4, default=Decimal('0.0000'))

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_offers'
        verbose_name = _('Offer')
        verbose_name_plural = _('Offers')
        ordering = ['-is_featured', '-is_hot', '-point_value']
        constraints = [
            CheckConstraint(check=Q(payout_usd__gte=0),      name='mt_offer_payout_non_neg'),
            CheckConstraint(check=Q(point_value__gte=0),      name='mt_offer_points_non_neg'),
            CheckConstraint(check=Q(bonus_multiplier__gte=1), name='mt_offer_multiplier_gte_1'),
            UniqueConstraint(
                fields=['offerwall', 'external_offer_id'],
                name='mt_offer_unique_external_per_wall',
            ),
        ]
        indexes = [
            models.Index(fields=['offerwall', 'status'],   name='mt_off_wall_status_idx'),
            models.Index(fields=['offer_type', 'status'],  name='mt_off_type_status_idx'),
            models.Index(fields=['expiry_date', 'status'], name='mt_off_expiry_idx'),
            models.Index(fields=['is_featured', 'is_hot'], name='mt_off_featured_idx'),
        ]

    def __str__(self):
        return f"{self.title} [{self.point_value} pts]"

    @property
    def effective_point_value(self) -> Decimal:
        return (self.point_value * self.bonus_multiplier).quantize(Decimal('0.01'))

    @property
    def is_available(self) -> bool:
        if self.status != self.Status.ACTIVE:
            return False
        now = timezone.now()
        if self.available_from and now < self.available_from:
            return False
        if self.expiry_date and now > self.expiry_date:
            return False
        return True


class OfferCompletion(TenantScopedModel):
    """
    IMMUTABLE completion record. Append-only — never updated after approval.

    Double-credit protection:
      1. transaction_id UUID — DB unique constraint.
      2. Partial UniqueConstraint: only one 'approved' record per (user, offer).
      3. network_transaction_id unique per offer (postback dedup).
    """

    class Status(models.TextChoices):
        PENDING    = 'pending',    _('Pending Verification')
        APPROVED   = 'approved',   _('Approved & Credited')
        REJECTED   = 'rejected',   _('Rejected')
        CANCELLED  = 'cancelled',  _('Cancelled')
        FRAUD      = 'fraud',      _('Fraud Detected')
        CHARGEBACK = 'chargeback', _('Chargeback')

    user  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name='%(app_label)s_%(class)s_user')
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE,
                               related_name='%(app_label)s_%(class)s_offer')

    # Primary dedup key — UUID, globally unique, DB-enforced
    transaction_id = models.UUIDField(
        default=uuid.uuid4, unique=True, db_index=True, editable=False,
    )
    network_transaction_id = models.CharField(max_length=200, blank=True, null=True, db_index=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING, db_index=True, null=True, blank=True)

    # Financial snapshot — Decimal, immutable after write
    reward_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    payout_amount = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    bonus_amount  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    # Device / network context — immutable audit trail
    ip_address         = models.GenericIPAddressField(db_index=True)
    ip_hash            = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    device_id          = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    device_fingerprint = models.CharField(max_length=128, blank=True, null=True)
    user_agent         = models.TextField(blank=True, null=True)
    country            = models.CharField(max_length=2, blank=True, null=True)
    device_type        = models.CharField(max_length=15, blank=True, null=True)
    os                 = models.CharField(max_length=20, blank=True, null=True)

    # Fraud — immutable once written
    fraud_score   = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)], db_index=True)
    fraud_signals = models.JSONField(default=_list, blank=True)
    fraud_reason  = models.TextField(blank=True, null=True)
    is_vpn        = models.BooleanField(default=False)
    is_proxy      = models.BooleanField(default=False)
    is_datacenter = models.BooleanField(default=False)

    # Timeline
    clicked_at   = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    approved_at  = models.DateTimeField(null=True, blank=True)
    credited_at  = models.DateTimeField(null=True, blank=True)

    rejection_reason = models.TextField(blank=True, null=True)
    reviewed_by      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                          null=True, blank=True,
                                          related_name='%(app_label)s_%(class)s_reviewed_by')
    network_response = models.JSONField(default=_dict, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_offer_completions'
        verbose_name = _('Offer Completion')
        verbose_name_plural = _('Offer Completions')
        ordering = ['-created_at']
        constraints = [
            # Prevent double-approval for same user+offer
            UniqueConstraint(
                fields=['user', 'offer'],
                condition=Q(status='approved'),
                name='mt_completion_one_approval_per_user_offer',
            ),
            # Network postback dedup
            UniqueConstraint(
                fields=['offer', 'network_transaction_id'],
                condition=Q(network_transaction_id__isnull=False),
                name='mt_completion_unique_network_txn',
            ),
            CheckConstraint(check=Q(fraud_score__lte=100), name='mt_completion_fraud_max_100'),
            CheckConstraint(check=Q(reward_amount__gte=0), name='mt_completion_reward_non_neg'),
            CheckConstraint(check=Q(payout_amount__gte=0), name='mt_completion_payout_non_neg'),
        ]
        indexes = [
            models.Index(fields=['transaction_id'],           name='mt_oc_txn_idx'),
            models.Index(fields=['user', 'status'],           name='mt_oc_user_status_idx'),
            models.Index(fields=['offer', 'status'],          name='mt_oc_offer_status_idx'),
            models.Index(fields=['fraud_score', 'status'],    name='mt_oc_fraud_status_idx'),
            models.Index(fields=['ip_address', 'created_at'], name='mt_oc_ip_time_idx'),
            models.Index(fields=['device_id', 'created_at'],  name='mt_oc_device_time_idx'),
            models.Index(fields=['clicked_at'],               name='mt_oc_clicked_idx'),
            models.Index(fields=['network_transaction_id'],   name='mt_oc_net_txn_idx'),
        ]

    def __str__(self):
        return f"Completion {self.transaction_id} | {self.user_id} | {self.status}"

    @property
    def processing_time_seconds(self):
        if self.completed_at and self.clicked_at:
            return (self.completed_at - self.clicked_at).total_seconds()
        return None

    @property
    def total_reward(self) -> Decimal:
        return self.reward_amount + self.bonus_amount


# ============================================================================
# § 5  REWARD — Immutable double-entry ledger
# ============================================================================

class RewardTransaction(TenantScopedModel):
    """
    Append-only ledger. NEVER updated after creation.

    Ledger invariant: balance_before + amount == balance_after (DB-enforced).
    """

    class TxnType(models.TextChoices):
        OFFER_REWARD   = 'offer_reward',   _('Offer Reward')
        REFERRAL_BONUS = 'referral_bonus', _('Referral Commission')
        STREAK_REWARD  = 'streak_reward',  _('Daily Streak')
        SPIN_WHEEL     = 'spin_wheel',     _('Spin Wheel Win')
        SCRATCH_CARD   = 'scratch_card',   _('Scratch Card Win')
        ACHIEVEMENT    = 'achievement',    _('Achievement Bonus')
        LEVEL_UP       = 'level_up',       _('Level-Up Bonus')
        PROMOTION      = 'promotion',      _('Promotional Grant')
        ADMIN_GRANT    = 'admin_grant',    _('Admin Manual Grant')
        ADMIN_DEDUCT   = 'admin_deduct',   _('Admin Manual Deduction')
        WITHDRAWAL     = 'withdrawal',     _('Withdrawal / Cashout')
        EXPIRY_DEDUCT  = 'expiry_deduct',  _('Points Expiry')
        REFUND         = 'refund',         _('Reversal / Refund')
        SUBSCRIPTION   = 'subscription',   _('Subscription Benefit')

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='%(app_label)s_%(class)s_user')

    transaction_id   = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    transaction_type = models.CharField(max_length=25, choices=TxnType.choices, db_index=True, null=True, blank=True)

    # Ledger triple — ALL Decimal
    amount         = models.DecimalField(max_digits=16, decimal_places=2, help_text="+ credit / - debit", null=True, blank=True)
    balance_before = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    balance_after  = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)

    description      = models.CharField(max_length=500, blank=True, null=True)
    reference_id     = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    offer_completion = models.OneToOneField(OfferCompletion, on_delete=models.SET_NULL,
                                             null=True, blank=True,
                                             related_name='%(app_label)s_%(class)s_offer_completion')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata   = models.JSONField(default=_dict, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_reward_transactions'
        verbose_name = _('Reward Transaction')
        verbose_name_plural = _('Reward Transactions')
        ordering = ['-created_at']
        constraints = [
            # Core ledger invariant
            CheckConstraint(
                check=Q(balance_after=F('balance_before') + F('amount')),
                name='mt_reward_txn_ledger_invariant',
            ),
            CheckConstraint(check=Q(balance_before__gte=0), name='mt_reward_txn_balance_before_non_neg'),
            CheckConstraint(check=Q(balance_after__gte=0),  name='mt_reward_txn_balance_after_non_neg'),
        ]
        indexes = [
            models.Index(fields=['transaction_id'],      name='mt_rt_txn_uuid_idx'),
            models.Index(fields=['user', '-created_at'], name='mt_rt_user_time_idx'),
            models.Index(fields=['transaction_type'],    name='mt_rt_type_idx'),
            models.Index(fields=['reference_id'],        name='mt_rt_ref_idx'),
        ]

    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f"{self.user_id} | {self.transaction_type} | {sign}{self.amount}"

    def clean(self):
        if self.balance_after != self.balance_before + self.amount:
            raise ValidationError(_("Ledger invariant: balance_before + amount must equal balance_after."))
        if self.balance_before < 0:
            raise ValidationError(_("balance_before cannot be negative."))
        if self.balance_after < 0:
            raise ValidationError(_("balance_after cannot be negative."))


class PointLedgerSnapshot(TenantScopedModel):
    """Daily balance snapshot — fast balance-at-date without full ledger replay."""

    user          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                       related_name='%(app_label)s_%(class)s_user')
    snapshot_date = models.DateField(db_index=True)
    balance       = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    total_earned  = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))
    total_spent   = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_point_ledger_snapshots'
        verbose_name = _('Point Ledger Snapshot')
        verbose_name_plural = _('Point Ledger Snapshots')
        constraints = [
            UniqueConstraint(fields=['user', 'snapshot_date'], name='mt_ledger_snap_unique'),
        ]
        indexes = [
            models.Index(fields=['user', 'snapshot_date'], name='mt_snap_user_date_idx'),
        ]

    def __str__(self):
        return f"{self.user_id} | {self.snapshot_date} | {self.balance}"


# ============================================================================
# § 6  REVENUE LOGS
# ============================================================================

class ImpressionLog(TenantScopedModel):
    """
    High-volume — one row per impression.
    Partition by month in PostgreSQL. Keep 90 days raw; aggregate into hourly rollup.
    """

    ad_unit    = models.ForeignKey(AdUnit,     on_delete=models.CASCADE,
                                    related_name='%(app_label)s_%(class)s_ad_unit')
    placement  = models.ForeignKey(AdPlacement, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='%(app_label)s_%(class)s_placement')
    ad_network = models.ForeignKey(AdNetwork,  on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='%(app_label)s_%(class)s_ad_network')
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name='%(app_label)s_%(class)s_user')

    session_id  = models.CharField(max_length=64, blank=True, null=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    country     = models.CharField(max_length=2,  blank=True, null=True, db_index=True)
    device_type = models.CharField(max_length=15, blank=True, null=True)
    os          = models.CharField(max_length=15, blank=True, null=True)

    # Financial — 8 decimal places for micro-CPM accuracy
    ecpm    = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal('0.000000'))
    revenue = models.DecimalField(max_digits=12, decimal_places=8, default=Decimal('0.00000000'))

    is_viewable     = models.BooleanField(default=True)
    is_bot          = models.BooleanField(default=False)
    viewability_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    logged_at       = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_impression_logs'
        verbose_name = _('Impression Log')
        verbose_name_plural = _('Impression Logs')
        ordering = ['-logged_at']
        indexes = [
            models.Index(fields=['ad_unit', 'logged_at'],    name='mt_il_unit_time_idx'),
            models.Index(fields=['ad_network', 'logged_at'], name='mt_il_net_time_idx'),
            models.Index(fields=['country', 'logged_at'],    name='mt_il_country_time_idx'),
            models.Index(fields=['is_bot', 'logged_at'],     name='mt_il_bot_time_idx'),
        ]

    def __str__(self):
        return f"Impression | unit={self.ad_unit_id} | {self.logged_at}"


class ClickLog(TenantScopedModel):
    ad_unit    = models.ForeignKey(AdUnit, on_delete=models.CASCADE,
                                    related_name='%(app_label)s_%(class)s_ad_unit')
    impression = models.OneToOneField(ImpressionLog, on_delete=models.SET_NULL,
                                       null=True, blank=True,
                                       related_name='%(app_label)s_%(class)s_impression')
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name='%(app_label)s_%(class)s_user')

    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    country     = models.CharField(max_length=2, blank=True, null=True, db_index=True)
    device_type = models.CharField(max_length=15, blank=True, null=True)
    revenue     = models.DecimalField(max_digits=12, decimal_places=8, default=Decimal('0.00000000'))
    is_valid    = models.BooleanField(default=True, db_index=True)
    clicked_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_click_logs'
        verbose_name = _('Click Log')
        verbose_name_plural = _('Click Logs')
        ordering = ['-clicked_at']
        indexes = [
            models.Index(fields=['ad_unit', 'clicked_at'],  name='mt_cl_unit_time_idx'),
            models.Index(fields=['is_valid', 'clicked_at'], name='mt_cl_valid_time_idx'),
        ]

    def __str__(self):
        return f"Click | unit={self.ad_unit_id} | valid={self.is_valid}"


class ConversionLog(TenantScopedModel):
    class ConversionType(models.TextChoices):
        INSTALL      = 'install',      _('App Install')
        SIGNUP       = 'signup',       _('Sign Up')
        PURCHASE     = 'purchase',     _('Purchase')
        LEAD         = 'lead',         _('Lead')
        ENGAGEMENT   = 'engagement',   _('Engagement')
        SUBSCRIPTION = 'subscription', _('Subscription')
        RETENTION    = 'retention',    _('Re-Engagement')

    campaign = models.ForeignKey(AdCampaign, on_delete=models.CASCADE,
                                  related_name='%(app_label)s_%(class)s_campaign')
    click    = models.ForeignKey(ClickLog, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='%(app_label)s_%(class)s_click')
    user     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                  null=True, blank=True,
                                  related_name='%(app_label)s_%(class)s_user')

    conversion_type          = models.CharField(max_length=20, choices=ConversionType.choices, db_index=True, null=True, blank=True)
    payout                   = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal('0.000000'))
    is_verified              = models.BooleanField(default=False, db_index=True)
    converted_at             = models.DateTimeField(auto_now_add=True, db_index=True)
    attribution_window_hours = models.PositiveSmallIntegerField(default=24)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_conversion_logs'
        verbose_name = _('Conversion Log')
        verbose_name_plural = _('Conversion Logs')
        ordering = ['-converted_at']
        constraints = [
            CheckConstraint(check=Q(payout__gte=0), name='mt_conv_payout_non_neg'),
        ]
        indexes = [
            models.Index(fields=['campaign', 'conversion_type'],  name='mt_cnv_camp_type_idx'),
            models.Index(fields=['is_verified', 'converted_at'],  name='mt_cnv_verified_time_idx'),
        ]

    def __str__(self):
        return f"Conversion | {self.conversion_type} | campaign={self.campaign_id}"


class RevenueDailySummary(TenantScopedModel):
    """Pre-aggregated daily billing table. Source of truth for invoicing."""

    ad_network = models.ForeignKey(AdNetwork, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='%(app_label)s_%(class)s_ad_network')
    campaign   = models.ForeignKey(AdCampaign, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='%(app_label)s_%(class)s_campaign')

    date    = models.DateField(db_index=True)
    country = models.CharField(max_length=2, blank=True, null=True)

    impressions = models.BigIntegerField(default=0)
    clicks      = models.BigIntegerField(default=0)
    conversions = models.BigIntegerField(default=0)
    installs    = models.BigIntegerField(default=0)

    revenue_cpm   = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))
    revenue_cpc   = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))
    revenue_cpa   = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))
    revenue_cpi   = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))
    total_revenue = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))

    ecpm      = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    fill_rate = models.DecimalField(max_digits=7,  decimal_places=4, default=Decimal('0.0000'))
    ctr       = models.DecimalField(max_digits=7,  decimal_places=4, default=Decimal('0.0000'))

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_revenue_daily_summary'
        verbose_name = _('Revenue Daily Summary')
        verbose_name_plural = _('Revenue Daily Summaries')
        ordering = ['-date']
        constraints = [
            UniqueConstraint(
                fields=['tenant', 'ad_network', 'campaign', 'date', 'country'],
                name='mt_rev_daily_unique',
            ),
        ]
        indexes = [
            models.Index(fields=['date', 'total_revenue'], name='mt_rds_date_rev_idx'),
            models.Index(fields=['tenant', 'date'],        name='mt_rds_tenant_date_idx'),
        ]

    def __str__(self):
        return f"{self.date} | ${self.total_revenue} | eCPM={self.ecpm}"


# ============================================================================
# § 7  SUBSCRIPTION & PAYMENT
# ============================================================================

class SubscriptionPlan(TenantScopedModel):
    class Interval(models.TextChoices):
        DAILY    = 'daily',    _('Daily')
        WEEKLY   = 'weekly',   _('Weekly')
        MONTHLY  = 'monthly',  _('Monthly')
        YEARLY   = 'yearly',   _('Yearly')
        LIFETIME = 'lifetime', _('Lifetime')

    plan_id     = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name        = models.CharField(max_length=100, null=True, blank=True)
    slug        = models.SlugField(max_length=100, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    price       = models.DecimalField(max_digits=12, decimal_places=2,
                                       validators=[MinValueValidator(Decimal('0.00'))])
    currency    = models.CharField(max_length=5, default='BDT', null=True, blank=True)
    interval    = models.CharField(max_length=10, choices=Interval.choices, default=Interval.MONTHLY, null=True, blank=True)
    trial_days  = models.PositiveSmallIntegerField(default=0)
    features    = models.JSONField(default=_list, blank=True)
    is_active   = models.BooleanField(default=True, db_index=True)
    is_popular  = models.BooleanField(default=False)
    sort_order  = models.PositiveSmallIntegerField(default=0)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_subscription_plans'
        verbose_name = _('Subscription Plan')
        verbose_name_plural = _('Subscription Plans')
        ordering = ['sort_order', 'price']
        constraints = [
            UniqueConstraint(fields=['tenant', 'slug'], name='mt_plan_slug_per_tenant'),
            CheckConstraint(check=Q(price__gte=0),      name='mt_plan_price_non_neg'),
        ]

    def __str__(self):
        return f"{self.name} — {self.price} {self.currency}/{self.interval}"


class UserSubscription(TenantScopedModel):
    class Status(models.TextChoices):
        TRIAL     = 'trial',     _('Free Trial')
        ACTIVE    = 'active',    _('Active')
        PAST_DUE  = 'past_due',  _('Past Due')
        CANCELLED = 'cancelled', _('Cancelled')
        EXPIRED   = 'expired',   _('Expired')
        PAUSED    = 'paused',    _('Paused')

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='%(app_label)s_%(class)s_user')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT,
                              related_name='%(app_label)s_%(class)s_plan')

    subscription_id         = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    status                  = models.CharField(max_length=12, choices=Status.choices,
                                                default=Status.TRIAL, db_index=True, null=True, blank=True)
    started_at              = models.DateTimeField()
    trial_end_at            = models.DateTimeField(null=True, blank=True)
    current_period_start    = models.DateTimeField()
    current_period_end      = models.DateTimeField(db_index=True)
    cancelled_at            = models.DateTimeField(null=True, blank=True)
    cancellation_reason     = models.TextField(blank=True, null=True)
    is_auto_renew           = models.BooleanField(default=True)
    gateway_subscription_id = models.CharField(max_length=300, blank=True, null=True, db_index=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_user_subscriptions'
        verbose_name = _('User Subscription')
        verbose_name_plural = _('User Subscriptions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status'],          name='mt_usub_user_status_idx'),
            models.Index(fields=['current_period_end'],      name='mt_usub_period_end_idx'),
            models.Index(fields=['status', 'is_auto_renew'], name='mt_usub_renew_idx'),
        ]

    def __str__(self):
        return f"Sub {self.subscription_id} | {self.user_id} | {self.status}"

    @property
    def is_currently_active(self) -> bool:
        return (self.status in (self.Status.TRIAL, self.Status.ACTIVE)
                and timezone.now() <= self.current_period_end)


class InAppPurchase(TenantScopedModel):
    class Status(models.TextChoices):
        PENDING   = 'pending',   _('Pending')
        COMPLETED = 'completed', _('Completed')
        REFUNDED  = 'refunded',  _('Refunded')
        FAILED    = 'failed',    _('Failed')

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='%(app_label)s_%(class)s_user')

    purchase_id   = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    product_id    = models.CharField(max_length=200, db_index=True, null=True, blank=True)
    product_name  = models.CharField(max_length=300, null=True, blank=True)
    amount        = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency      = models.CharField(max_length=5, default='BDT', null=True, blank=True)
    status        = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True, null=True, blank=True)
    gateway       = models.CharField(max_length=30, blank=True, null=True)
    gateway_ref   = models.CharField(max_length=300, blank=True, null=True, db_index=True)
    coins_granted = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))
    purchased_at  = models.DateTimeField(auto_now_add=True)
    fulfilled_at  = models.DateTimeField(null=True, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_in_app_purchases'
        verbose_name = _('In-App Purchase')
        verbose_name_plural = _('In-App Purchases')
        ordering = ['-purchased_at']
        constraints = [
            CheckConstraint(check=Q(amount__gte=0),        name='mt_iap_amount_non_neg'),
            CheckConstraint(check=Q(coins_granted__gte=0), name='mt_iap_coins_non_neg'),
        ]
        indexes = [
            models.Index(fields=['user', 'status'], name='mt_iap_user_status_idx'),
        ]

    def __str__(self):
        return f"{self.product_name} | {self.amount} {self.currency} | {self.status}"


class PaymentTransaction(TenantScopedModel):
    class Gateway(models.TextChoices):
        STRIPE     = 'stripe',     _('Stripe')
        PAYPAL     = 'paypal',     _('PayPal')
        BKASH      = 'bkash',      _('bKash')
        NAGAD      = 'nagad',      _('Nagad')
        ROCKET     = 'rocket',     _('Rocket')
        SSLCOMMERZ = 'sslcommerz', _('SSLCommerz')
        RAZORPAY   = 'razorpay',   _('Razorpay')
        PAYONEER   = 'payoneer',   _('Payoneer')
        CRYPTO     = 'crypto',     _('Crypto')
        MANUAL     = 'manual',     _('Manual / Bank')

    class Status(models.TextChoices):
        INITIATED = 'initiated', _('Initiated')
        PENDING   = 'pending',   _('Pending')
        SUCCESS   = 'success',   _('Success')
        FAILED    = 'failed',    _('Failed')
        CANCELLED = 'cancelled', _('Cancelled')
        REFUNDED  = 'refunded',  _('Refunded')
        DISPUTED  = 'disputed',  _('Disputed')

    class Purpose(models.TextChoices):
        SUBSCRIPTION = 'subscription', _('Subscription')
        IN_APP       = 'in_app',       _('In-App Purchase')
        DEPOSIT      = 'deposit',      _('Wallet Deposit')
        WITHDRAWAL   = 'withdrawal',   _('Withdrawal')
        OTHER        = 'other',        _('Other')

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='%(app_label)s_%(class)s_user')

    txn_id            = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    gateway           = models.CharField(max_length=15, choices=Gateway.choices, db_index=True, null=True, blank=True)
    gateway_txn_id    = models.CharField(max_length=300, blank=True, null=True, db_index=True)
    amount            = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    currency          = models.CharField(max_length=5, default='BDT', null=True, blank=True)
    status            = models.CharField(max_length=12, choices=Status.choices,
                                          default=Status.INITIATED, db_index=True, null=True, blank=True)
    purpose           = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.OTHER, null=True, blank=True)
    related_object_id = models.CharField(max_length=100, blank=True, null=True)
    gateway_response  = models.JSONField(default=_dict, blank=True)
    failure_reason    = models.TextField(blank=True, null=True)
    initiated_at      = models.DateTimeField(auto_now_add=True, null=True)
    completed_at      = models.DateTimeField(null=True, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_payment_transactions'
        verbose_name = _('Payment Transaction')
        verbose_name_plural = _('Payment Transactions')
        ordering = ['-initiated_at']
        constraints = [
            CheckConstraint(check=Q(amount__gt=0), name='mt_pay_amount_positive'),
            UniqueConstraint(
                fields=['gateway', 'gateway_txn_id'],
                condition=Q(gateway_txn_id__isnull=False),
                name='mt_pay_unique_gateway_txn',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'status'],    name='mt_pay_user_status_idx'),
            models.Index(fields=['gateway', 'status'], name='mt_pay_gw_status_idx'),
        ]

    def __str__(self):
        return f"{self.gateway} | {self.amount} {self.currency} | {self.status}"


class RecurringBilling(TenantScopedModel):
    class Status(models.TextChoices):
        SCHEDULED  = 'scheduled',  _('Scheduled')
        PROCESSING = 'processing', _('Processing')
        SUCCESS    = 'success',    _('Success')
        FAILED     = 'failed',     _('Failed')
        SKIPPED    = 'skipped',    _('Skipped')

    subscription        = models.ForeignKey(UserSubscription, on_delete=models.CASCADE,
                                             related_name='%(app_label)s_%(class)s_subscription')
    payment_transaction = models.ForeignKey(PaymentTransaction, on_delete=models.SET_NULL,
                                             null=True, blank=True,
                                             related_name='%(app_label)s_%(class)s_payment_transaction')

    scheduled_at   = models.DateTimeField(db_index=True)
    amount         = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency       = models.CharField(max_length=5, default='BDT', null=True, blank=True)
    status         = models.CharField(max_length=12, choices=Status.choices,
                                       default=Status.SCHEDULED, db_index=True, null=True, blank=True)
    attempt_count  = models.PositiveSmallIntegerField(default=0)
    max_attempts   = models.PositiveSmallIntegerField(default=3)
    last_attempt   = models.DateTimeField(null=True, blank=True)
    next_attempt   = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, null=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_recurring_billing'
        verbose_name = _('Recurring Billing')
        verbose_name_plural = _('Recurring Billings')
        ordering = ['scheduled_at']
        constraints = [
            CheckConstraint(check=Q(amount__gt=0), name='mt_bill_amount_positive'),
        ]
        indexes = [
            models.Index(fields=['scheduled_at', 'status'], name='mt_bill_sched_status_idx'),
            models.Index(fields=['status', 'next_attempt'],  name='mt_bill_status_next_idx'),
        ]

    def __str__(self):
        return f"Billing | sub={self.subscription_id} | {self.scheduled_at:%Y-%m-%d} | {self.status}"


# ============================================================================
# § 8  GAMIFICATION
# ============================================================================

class UserLevel(TenantScopedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name='%(app_label)s_%(class)s_user')

    current_level    = models.PositiveSmallIntegerField(default=1)
    current_xp       = models.PositiveBigIntegerField(default=0)
    total_xp_earned  = models.PositiveBigIntegerField(default=0)
    xp_to_next_level = models.PositiveBigIntegerField(default=100)
    level_title      = models.CharField(max_length=100, default='Newcomer', null=True, blank=True)
    badges_count     = models.PositiveSmallIntegerField(default=0)
    prestige_level   = models.PositiveSmallIntegerField(default=0)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_user_levels'
        verbose_name = _('User Level')
        verbose_name_plural = _('User Levels')

    def __str__(self):
        return f"Lvl {self.current_level} | {self.user_id}"

    def add_xp(self, amount: int) -> bool:
        levelled_up = False
        self.current_xp      += amount
        self.total_xp_earned += amount
        while self.current_xp >= self.xp_to_next_level:
            self.current_xp       -= self.xp_to_next_level
            self.current_level    += 1
            self.xp_to_next_level  = int(self.xp_to_next_level * 1.5)
            levelled_up = True
        self.save(update_fields=['current_xp', 'current_level', 'xp_to_next_level',
                                  'total_xp_earned', 'updated_at'])
        return levelled_up


class Achievement(TenantScopedModel):
    class Category(models.TextChoices):
        EARNING  = 'earning',  _('Earning')
        REFERRAL = 'referral', _('Referral')
        STREAK   = 'streak',   _('Streak')
        OFFER    = 'offer',    _('Offer Completion')
        SOCIAL   = 'social',   _('Social')
        SPECIAL  = 'special',  _('Special Event')

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='%(app_label)s_%(class)s_user')

    achievement_key = models.CharField(max_length=100, db_index=True, null=True, blank=True)
    title           = models.CharField(max_length=200, null=True, blank=True)
    description     = models.TextField(blank=True, null=True)
    category        = models.CharField(max_length=20, choices=Category.choices, db_index=True, null=True, blank=True)
    icon_url        = models.URLField(blank=True, null=True)
    xp_reward       = models.PositiveIntegerField(default=0)
    coin_reward     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    unlocked_at     = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_achievements'
        verbose_name = _('Achievement')
        verbose_name_plural = _('Achievements')
        ordering = ['-unlocked_at']
        constraints = [
            UniqueConstraint(fields=['user', 'achievement_key'], name='mt_ach_unique_per_user'),
            CheckConstraint(check=Q(coin_reward__gte=0),         name='mt_ach_coin_non_neg'),
        ]
        indexes = [
            models.Index(fields=['user', 'category'], name='mt_ach_user_cat_idx'),
        ]

    def __str__(self):
        return f"{self.user_id} | {self.title}"


class LeaderboardRank(TenantScopedModel):
    class Scope(models.TextChoices):
        GLOBAL  = 'global',  _('Global')
        COUNTRY = 'country', _('Country')
        WEEKLY  = 'weekly',  _('Weekly')
        MONTHLY = 'monthly', _('Monthly')

    class BoardType(models.TextChoices):
        EARNINGS  = 'earnings',  _('Total Earnings')
        REFERRALS = 'referrals', _('Referrals')
        OFFERS    = 'offers',    _('Offers Completed')
        STREAK    = 'streak',    _('Longest Streak')

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='%(app_label)s_%(class)s_user')

    scope        = models.CharField(max_length=10, choices=Scope.choices,     default=Scope.GLOBAL,      db_index=True, null=True, blank=True)
    board_type   = models.CharField(max_length=15, choices=BoardType.choices, default=BoardType.EARNINGS, db_index=True, null=True, blank=True)
    period_label = models.CharField(max_length=20, blank=True, null=True, db_index=True)
    rank         = models.PositiveIntegerField(db_index=True)
    score        = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    country      = models.CharField(max_length=2, blank=True, null=True)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_leaderboard_ranks'
        verbose_name = _('Leaderboard Rank')
        verbose_name_plural = _('Leaderboard Ranks')
        ordering = ['rank']
        constraints = [
            UniqueConstraint(
                fields=['user', 'scope', 'board_type', 'period_label'],
                name='mt_lb_unique_user_position',
            ),
        ]
        indexes = [
            models.Index(fields=['scope', 'board_type', 'rank'], name='mt_lb_scope_type_rank_idx'),
        ]

    def __str__(self):
        return f"#{self.rank} | {self.user_id} | {self.board_type}"


class SpinWheelLog(TenantScopedModel):
    class LogType(models.TextChoices):
        SPIN_WHEEL   = 'spin_wheel',   _('Spin Wheel')
        SCRATCH_CARD = 'scratch_card', _('Scratch Card')

    class PrizeType(models.TextChoices):
        COINS      = 'coins',      _('Coins')
        XP         = 'xp',         _('XP Points')
        NO_PRIZE   = 'no_prize',   _('No Prize')
        MULTIPLIER = 'multiplier', _('Earning Multiplier')
        VOUCHER    = 'voucher',    _('Voucher Code')

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='%(app_label)s_%(class)s_user')

    log_type     = models.CharField(max_length=15, choices=LogType.choices,   default=LogType.SPIN_WHEEL, db_index=True, null=True, blank=True)
    prize_type   = models.CharField(max_length=15, choices=PrizeType.choices, default=PrizeType.NO_PRIZE, null=True, blank=True)
    prize_value  = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    result_label = models.CharField(max_length=100, blank=True, null=True)
    is_credited  = models.BooleanField(default=False, db_index=True)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    played_at    = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_spin_wheel_logs'
        verbose_name = _('Spin Wheel Log')
        verbose_name_plural = _('Spin Wheel Logs')
        ordering = ['-played_at']
        constraints = [
            CheckConstraint(check=Q(prize_value__gte=0), name='mt_spin_prize_non_neg'),
        ]
        indexes = [
            models.Index(fields=['user', 'log_type', 'played_at'], name='mt_spin_user_type_time_idx'),
        ]

    def __str__(self):
        return f"{self.user_id} | {self.log_type} | {self.prize_type} {self.prize_value}"


# ============================================================================
# § 9  OPTIMIZATION
# ============================================================================

class ABTest(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT     = 'draft',     _('Draft')
        RUNNING   = 'running',   _('Running')
        PAUSED    = 'paused',    _('Paused')
        COMPLETED = 'completed', _('Completed')
        ARCHIVED  = 'archived',  _('Archived')

    class WinnerCriteria(models.TextChoices):
        CTR     = 'ctr',     _('Click-Through Rate')
        CVR     = 'cvr',     _('Conversion Rate')
        REVENUE = 'revenue', _('Revenue')
        ECPM    = 'ecpm',    _('eCPM')
        ARPU    = 'arpu',    _('ARPU')

    test_id          = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name             = models.CharField(max_length=255, null=True, blank=True)
    description      = models.TextField(blank=True, null=True)
    status           = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True, null=True, blank=True)
    winner_criteria  = models.CharField(max_length=10, choices=WinnerCriteria.choices, default=WinnerCriteria.CTR, null=True, blank=True)
    variants         = models.JSONField(default=_list)
    traffic_split    = models.PositiveSmallIntegerField(default=50,
                                                         validators=[MinValueValidator(1), MaxValueValidator(100)])
    confidence_level = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('95.00'),
                                            validators=[MinValueValidator(Decimal('50')),
                                                        MaxValueValidator(Decimal('99.99'))])
    winner_variant   = models.CharField(max_length=100, blank=True, null=True)
    results_summary  = models.JSONField(default=_dict, blank=True)
    started_at       = models.DateTimeField(null=True, blank=True)
    ended_at         = models.DateTimeField(null=True, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_ab_tests'
        verbose_name = _('A/B Test')
        verbose_name_plural = _('A/B Tests')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status'], name='mt_ab_status_idx'),
        ]

    def __str__(self):
        return f"{self.name} [{self.status}]"


class ABTestAssignment(TenantScopedModel):
    """Consistent user-to-variant bucketing — written once, read many."""

    test = models.ForeignKey(ABTest, on_delete=models.CASCADE,
                              related_name='%(app_label)s_%(class)s_test')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='%(app_label)s_%(class)s_user')

    variant_name = models.CharField(max_length=50, null=True, blank=True)
    assigned_at  = models.DateTimeField(auto_now_add=True)
    converted    = models.BooleanField(default=False)
    converted_at = models.DateTimeField(null=True, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_ab_test_assignments'
        verbose_name = _('A/B Test Assignment')
        verbose_name_plural = _('A/B Test Assignments')
        constraints = [
            UniqueConstraint(fields=['test', 'user'], name='mt_ab_assign_unique'),
        ]
        indexes = [
            models.Index(fields=['test', 'variant_name'], name='mt_ab_assign_variant_idx'),
        ]

    def __str__(self):
        return f"{self.test_id} | {self.user_id} → {self.variant_name}"


class WaterfallConfig(TenantScopedModel):
    ad_unit    = models.ForeignKey(AdUnit,     on_delete=models.CASCADE,
                                    related_name='%(app_label)s_%(class)s_ad_unit')
    ad_network = models.ForeignKey(AdNetwork,  on_delete=models.CASCADE,
                                    related_name='%(app_label)s_%(class)s_ad_network')

    priority          = models.PositiveSmallIntegerField(default=1)
    floor_ecpm        = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    timeout_ms        = models.PositiveIntegerField(default=5000)
    is_active         = models.BooleanField(default=True, db_index=True)
    is_header_bidding = models.BooleanField(default=False)
    bid_floor         = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_waterfall_configs'
        verbose_name = _('Waterfall Config')
        verbose_name_plural = _('Waterfall Configs')
        ordering = ['ad_unit', 'priority']
        constraints = [
            UniqueConstraint(fields=['ad_unit', 'ad_network'], name='mt_wf_unique_unit_network'),
            CheckConstraint(check=Q(floor_ecpm__gte=0),        name='mt_wf_floor_non_neg'),
        ]
        indexes = [
            models.Index(fields=['ad_unit', 'priority', 'is_active'], name='mt_wf_unit_prio_idx'),
        ]

    def __str__(self):
        return f"[P{self.priority}] unit={self.ad_unit_id} → {self.ad_network}"


class FloorPriceConfig(TenantScopedModel):
    """
    Granular floor price rules.
    Most-specific match wins:
      (network, unit, country, device, format) > (network, None, country) > (network, None, None).
    """

    ad_network  = models.ForeignKey(AdNetwork, on_delete=models.CASCADE,
                                     related_name='%(app_label)s_%(class)s_ad_network')
    ad_unit     = models.ForeignKey(AdUnit, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='%(app_label)s_%(class)s_ad_unit')

    country     = models.CharField(max_length=2,  blank=True, null=True)
    device_type = models.CharField(max_length=15, blank=True, null=True)
    ad_format   = models.CharField(max_length=25, blank=True, null=True)
    os          = models.CharField(max_length=15, blank=True, null=True)

    floor_ecpm = models.DecimalField(max_digits=10, decimal_places=4,
                                      validators=[MinValueValidator(Decimal('0.0000'))])
    is_active  = models.BooleanField(default=True, db_index=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_floor_price_configs'
        verbose_name = _('Floor Price Config')
        verbose_name_plural = _('Floor Price Configs')
        ordering = ['-floor_ecpm']
        constraints = [
            CheckConstraint(check=Q(floor_ecpm__gte=0), name='mt_floor_non_neg'),
        ]
        indexes = [
            models.Index(fields=['ad_network', 'country', 'is_active'], name='mt_fp_net_country_idx'),
            models.Index(fields=['ad_unit', 'is_active'],               name='mt_fp_unit_idx'),
        ]

    def __str__(self):
        return (f"{self.ad_network} | {self.country or 'ALL'} | "
                f"{self.device_type or 'ALL'} | ${self.floor_ecpm}")


# ============================================================================
# § 10  MONETIZATION CONFIG  (per-tenant runtime settings)
# ============================================================================

class MonetizationConfig(TenantScopedModel):
    """
    Per-tenant monetization configuration.
    Single row per tenant — use get_or_create.
    All feature flags and limits configurable without deploy.
    """

    # Coin economy
    coins_per_usd           = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('100.00'))
    min_withdrawal_coins    = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('1000.00'))
    max_withdrawal_coins    = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('100000.00'))
    min_withdrawal_usd      = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    coin_expiry_days        = models.PositiveSmallIntegerField(default=365)

    # Feature flags
    offerwall_enabled       = models.BooleanField(default=True)
    subscription_enabled    = models.BooleanField(default=True)
    spin_wheel_enabled      = models.BooleanField(default=True)
    scratch_card_enabled    = models.BooleanField(default=True)
    referral_enabled        = models.BooleanField(default=True)
    ab_testing_enabled      = models.BooleanField(default=True)
    flash_sale_enabled      = models.BooleanField(default=True)
    coupon_enabled          = models.BooleanField(default=True)
    daily_streak_enabled    = models.BooleanField(default=True)

    # Limits
    max_offers_per_day      = models.PositiveSmallIntegerField(default=50)
    spin_wheel_daily_limit  = models.PositiveSmallIntegerField(default=3)
    scratch_card_daily_limit = models.PositiveSmallIntegerField(default=5)
    max_pending_withdrawals = models.PositiveSmallIntegerField(default=3)

    # Fraud thresholds
    fraud_auto_reject_score = models.PositiveSmallIntegerField(default=70)
    fraud_flag_score        = models.PositiveSmallIntegerField(default=50)
    max_devices_per_user    = models.PositiveSmallIntegerField(default=3)
    postback_secret         = models.CharField(max_length=256, blank=True, null=True)

    # Currency & locale
    default_currency        = models.CharField(max_length=5, default='BDT', null=True, blank=True)
    supported_gateways      = models.JSONField(default=_list, blank=True)
    supported_countries     = models.JSONField(default=_list, blank=True)

    # Referral defaults
    referral_commission_pct  = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'))
    referral_bonus_coins     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('100.00'))
    referral_max_levels      = models.PositiveSmallIntegerField(default=3)

    extra                    = models.JSONField(default=_dict, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_monetization_config'
        verbose_name        = _('Monetization Config')
        verbose_name_plural = _('Monetization Configs')
        constraints = [
            UniqueConstraint(fields=['tenant'], name='mt_config_one_per_tenant'),
        ]

    def __str__(self):
        return f"Config | tenant={self.tenant_id}"


# ============================================================================
# § 11  AD CREATIVE
# ============================================================================

class AdCreative(TenantScopedModel):
    """
    Creative asset attached to an AdUnit.
    Supports image, video, HTML5, and audio creatives.
    """

    class CreativeType(models.TextChoices):
        IMAGE    = 'image',    _('Image (JPG/PNG/GIF/WebP)')
        VIDEO    = 'video',    _('Video (MP4/WebM)')
        HTML5    = 'html5',    _('HTML5 Rich Media')
        AUDIO    = 'audio',    _('Audio (MP3/OGG)')
        VAST     = 'vast',     _('VAST XML Tag')
        MRAID    = 'mraid',    _('MRAID Interactive')
        NATIVE   = 'native',   _('Native Asset Bundle')

    class Status(models.TextChoices):
        DRAFT     = 'draft',     _('Draft')
        PENDING   = 'pending',   _('Pending Review')
        APPROVED  = 'approved',  _('Approved')
        REJECTED  = 'rejected',  _('Rejected')
        ARCHIVED  = 'archived',  _('Archived')

    ad_unit       = models.ForeignKey(
        'AdUnit', on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_ad_unit',
    )
    creative_id   = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name          = models.CharField(max_length=255, null=True, blank=True)
    creative_type = models.CharField(max_length=10, choices=CreativeType.choices, db_index=True, null=True, blank=True)
    status        = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True, null=True, blank=True)

    # Asset URLs
    asset_url     = models.URLField(max_length=2048, null=True, blank=True)
    preview_url   = models.URLField(max_length=2048, blank=True, null=True)
    landing_url   = models.URLField(max_length=2048, blank=True, null=True)
    tracking_pixel = models.URLField(max_length=2048, blank=True, null=True)

    # Dimensions
    width         = models.PositiveSmallIntegerField(null=True, blank=True)
    height        = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_sec  = models.PositiveSmallIntegerField(null=True, blank=True, help_text="For video/audio")
    file_size_kb  = models.PositiveIntegerField(null=True, blank=True)
    mime_type     = models.CharField(max_length=60, blank=True, null=True)

    # Native asset fields
    headline      = models.CharField(max_length=200, blank=True, null=True)
    body_text     = models.TextField(blank=True, null=True)
    cta_text      = models.CharField(max_length=50, blank=True, null=True)
    advertiser_name = models.CharField(max_length=100, blank=True, null=True)
    icon_url      = models.URLField(max_length=2048, blank=True, null=True)

    # Performance counters
    impressions   = models.BigIntegerField(default=0)
    clicks        = models.BigIntegerField(default=0)
    revenue       = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))

    rejection_reason = models.TextField(blank=True, null=True)
    reviewed_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_reviewed_by',
    )
    is_active        = models.BooleanField(default=True, db_index=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_ad_creatives'
        verbose_name        = _('Ad Creative')
        verbose_name_plural = _('Ad Creatives')
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['ad_unit', 'status', 'is_active'], name='mt_creative_unit_status_idx'),
            models.Index(fields=['creative_type', 'status'],        name='mt_creative_type_status_idx'),
        ]

    def __str__(self):
        return f"{self.name} [{self.creative_type}] [{self.status}]"

    @property
    def ctr(self) -> Decimal:
        if not self.impressions:
            return Decimal('0.0000')
        return (Decimal(self.clicks) / Decimal(self.impressions) * 100).quantize(Decimal('0.0001'))


# ============================================================================
# § 12  USER SEGMENT  (Audience)
# ============================================================================

class UserSegment(TenantScopedModel):
    """
    Named audience segment used for targeting campaigns and offers.
    Members computed by scheduled task or manual assignment.
    """

    class SegmentType(models.TextChoices):
        MANUAL     = 'manual',     _('Manual — admin assigned')
        RFM        = 'rfm',        _('RFM — Recency/Frequency/Monetary')
        BEHAVIORAL = 'behavioral', _('Behavioral — activity-based')
        GEO        = 'geo',        _('Geographic')
        DEVICE     = 'device',     _('Device / Platform')
        CUSTOM_SQL = 'custom_sql', _('Custom SQL query')

    name          = models.CharField(max_length=200, db_index=True, null=True, blank=True)
    slug          = models.SlugField(max_length=200, null=True, blank=True)
    description   = models.TextField(blank=True, null=True)
    segment_type  = models.CharField(max_length=15, choices=SegmentType.choices, default=SegmentType.MANUAL, null=True, blank=True)
    rules         = models.JSONField(default=_dict, blank=True,
                                      help_text="Segment rule definition (JSON DSL)")
    is_active     = models.BooleanField(default=True, db_index=True)
    is_dynamic    = models.BooleanField(default=False, help_text="Re-evaluated automatically")
    member_count  = models.PositiveIntegerField(default=0)
    last_computed = models.DateTimeField(null=True, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_user_segments'
        verbose_name        = _('User Segment')
        verbose_name_plural = _('User Segments')
        ordering            = ['name']
        constraints = [
            UniqueConstraint(fields=['tenant', 'slug'], name='mt_segment_slug_per_tenant'),
        ]

    def __str__(self):
        return f"{self.name} [{self.segment_type}] ({self.member_count} members)"


class UserSegmentMembership(TenantScopedModel):
    """Many-to-many: User ↔ UserSegment with metadata."""

    segment    = models.ForeignKey(UserSegment, on_delete=models.CASCADE,
                                    related_name='%(app_label)s_%(class)s_segment')
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name='%(app_label)s_%(class)s_user')
    added_at   = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    score      = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.0000'),
                                      help_text="Segment relevance score")
    meta       = models.JSONField(default=_dict, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_user_segment_memberships'
        verbose_name        = _('User Segment Membership')
        verbose_name_plural = _('User Segment Memberships')
        constraints = [
            UniqueConstraint(fields=['segment', 'user'], name='mt_seg_membership_unique'),
        ]
        indexes = [
            models.Index(fields=['user', 'segment'],     name='mt_segmem_user_seg_idx'),
            models.Index(fields=['segment', 'expires_at'], name='mt_segmem_expires_idx'),
        ]

    def __str__(self):
        return f"{self.user_id} → {self.segment.name}"


# ============================================================================
# § 13  POSTBACK LOG  (Ad network callback audit)
# ============================================================================

class PostbackLog(TenantScopedModel):
    """
    Immutable record of every postback/callback received from ad networks.
    Used for fraud detection, debugging, and reconciliation.
    Never deleted — append-only audit trail.
    """

    class ProcessStatus(models.TextChoices):
        RECEIVED    = 'received',    _('Received')
        PROCESSING  = 'processing',  _('Processing')
        ACCEPTED    = 'accepted',    _('Accepted')
        REJECTED    = 'rejected',    _('Rejected — Validation Failed')
        DUPLICATE   = 'duplicate',   _('Duplicate — Already Processed')
        FRAUD       = 'fraud',       _('Rejected — Fraud Detected')
        ERROR       = 'error',       _('Processing Error')

    ad_network      = models.ForeignKey(
        'AdNetwork', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_ad_network',
    )
    offer_completion = models.ForeignKey(
        'OfferCompletion', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_offer_completion',
    )

    # Request metadata
    postback_id         = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    network_txn_id      = models.CharField(max_length=300, blank=True, null=True, db_index=True)
    network_name        = models.CharField(max_length=50, blank=True, null=True)
    http_method         = models.CharField(max_length=10, default='GET', null=True, blank=True)
    endpoint_path       = models.CharField(max_length=500, null=True, blank=True)
    source_ip           = models.GenericIPAddressField(db_index=True)
    user_agent          = models.TextField(blank=True, null=True)

    # Payload
    query_params        = models.JSONField(default=_dict, blank=True)
    body_raw            = models.TextField(blank=True, null=True)
    body_parsed         = models.JSONField(default=_dict, blank=True)
    headers             = models.JSONField(default=_dict, blank=True)

    # Validation
    signature_valid     = models.BooleanField(null=True, blank=True)
    signature_received  = models.CharField(max_length=256, blank=True, null=True)
    signature_computed  = models.CharField(max_length=256, blank=True, null=True)

    # Processing
    status              = models.CharField(max_length=15, choices=ProcessStatus.choices,
                                            default=ProcessStatus.RECEIVED, db_index=True, null=True, blank=True)
    rejection_reason    = models.TextField(blank=True, null=True)
    processing_error    = models.TextField(blank=True, null=True)
    processing_time_ms  = models.PositiveIntegerField(null=True, blank=True)
    received_at         = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at        = models.DateTimeField(null=True, blank=True)

    # Financial payload (extracted)
    reward_amount       = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    payout_usd          = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_postback_logs'
        verbose_name        = _('Postback Log')
        verbose_name_plural = _('Postback Logs')
        ordering            = ['-received_at']
        indexes = [
            models.Index(fields=['network_txn_id'],        name='mt_pb_net_txn_idx'),
            models.Index(fields=['status', 'received_at'], name='mt_pb_status_time_idx'),
            models.Index(fields=['source_ip', 'received_at'], name='mt_pb_ip_time_idx'),
            models.Index(fields=['ad_network', 'received_at'], name='mt_pb_net_time_idx'),
        ]

    def __str__(self):
        return f"Postback {self.postback_id} | {self.network_name} | {self.status}"


# ============================================================================
# § 14  PAYOUT  (User withdrawal system)
# ============================================================================

class PayoutMethod(TenantScopedModel):
    """
    A saved payout destination for a user.
    e.g. bKash number, bank account, PayPal email.
    """

    class MethodType(models.TextChoices):
        BKASH     = 'bkash',     _('bKash')
        NAGAD     = 'nagad',     _('Nagad')
        ROCKET    = 'rocket',    _('Rocket')
        UPAY      = 'upay',      _('Upay')
        BANK      = 'bank',      _('Bank Transfer')
        PAYPAL    = 'paypal',    _('PayPal')
        PAYONEER  = 'payoneer',  _('Payoneer')
        CRYPTO    = 'crypto',    _('Cryptocurrency')
        GIFT_CARD = 'gift_card', _('Gift Card')

    user          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                       related_name='%(app_label)s_%(class)s_user')
    method_type   = models.CharField(max_length=15, choices=MethodType.choices, db_index=True, null=True, blank=True)
    account_name  = models.CharField(max_length=200, blank=True, null=True)
    account_number = models.CharField(max_length=100, null=True, blank=True)
    account_email  = models.EmailField(blank=True, null=True)
    bank_name      = models.CharField(max_length=100, blank=True, null=True)
    branch_name    = models.CharField(max_length=100, blank=True, null=True)
    routing_number = models.CharField(max_length=50, blank=True, null=True)
    currency       = models.CharField(max_length=5, default='BDT', null=True, blank=True)
    is_default     = models.BooleanField(default=False)
    is_verified    = models.BooleanField(default=False)
    verified_at    = models.DateTimeField(null=True, blank=True)
    is_active      = models.BooleanField(default=True, db_index=True)
    extra          = models.JSONField(default=_dict, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_payout_methods'
        verbose_name        = _('Payout Method')
        verbose_name_plural = _('Payout Methods')
        ordering            = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['user', 'method_type', 'is_active'], name='mt_pm_user_type_idx'),
        ]

    def __str__(self):
        return f"{self.user_id} | {self.method_type} | {self.account_number[:4]}****"


class PayoutRequest(TenantScopedModel):
    """
    User-initiated withdrawal request.
    Coins deducted immediately; cash transferred by admin or automation.
    """

    class Status(models.TextChoices):
        PENDING    = 'pending',    _('Pending Review')
        APPROVED   = 'approved',   _('Approved')
        PROCESSING = 'processing', _('Processing Payment')
        PAID       = 'paid',       _('Paid')
        REJECTED   = 'rejected',   _('Rejected')
        CANCELLED  = 'cancelled',  _('Cancelled by User')
        FAILED     = 'failed',     _('Payment Failed')

    user          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                       related_name='%(app_label)s_%(class)s_user')
    payout_method = models.ForeignKey(PayoutMethod, on_delete=models.PROTECT,
                                       related_name='%(app_label)s_%(class)s_payout_method')

    request_id     = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    coins_deducted = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    amount_usd     = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    amount_local   = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency       = models.CharField(max_length=5, default='BDT', null=True, blank=True)
    exchange_rate  = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal('1.000000'))
    processing_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    net_amount     = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status         = models.CharField(max_length=15, choices=Status.choices,
                                       default=Status.PENDING, db_index=True, null=True, blank=True)

    admin_note        = models.TextField(blank=True, null=True)
    rejection_reason  = models.TextField(blank=True, null=True)
    gateway_reference = models.CharField(max_length=300, blank=True, null=True)
    reviewed_by       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                           null=True, blank=True,
                                           related_name='%(app_label)s_%(class)s_reviewed_by')
    reviewed_at       = models.DateTimeField(null=True, blank=True)
    paid_at           = models.DateTimeField(null=True, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_payout_requests'
        verbose_name        = _('Payout Request')
        verbose_name_plural = _('Payout Requests')
        ordering            = ['-created_at']
        constraints = [
            CheckConstraint(check=Q(coins_deducted__gt=0),  name='mt_payout_coins_positive'),
            CheckConstraint(check=Q(amount_usd__gt=0),      name='mt_payout_usd_positive'),
            CheckConstraint(check=Q(net_amount__gte=0),     name='mt_payout_net_non_neg'),
        ]
        indexes = [
            models.Index(fields=['user', 'status'],   name='mt_payout_user_status_idx'),
            models.Index(fields=['status', 'created_at'], name='mt_payout_status_time_idx'),
        ]

    def __str__(self):
        return f"Payout {self.request_id} | {self.user_id} | {self.amount_local} {self.currency} | {self.status}"


# ============================================================================
# § 15  REFERRAL SYSTEM
# ============================================================================

class ReferralProgram(TenantScopedModel):
    """
    Configuration for the referral program.
    One active program per tenant at a time.
    Multi-level (up to 5 levels) commission support.
    """

    name              = models.CharField(max_length=200, null=True, blank=True)
    slug              = models.SlugField(max_length=200, null=True, blank=True)
    description       = models.TextField(blank=True, null=True)
    is_active         = models.BooleanField(default=True, db_index=True)

    # Rewards
    referrer_bonus_coins  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('100.00'))
    referee_bonus_coins   = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('50.00'))

    # Multi-level commission (L1–L5 %)
    l1_commission_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'))
    l2_commission_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    l3_commission_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('2.00'))
    l4_commission_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'))
    l5_commission_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.50'))
    max_levels        = models.PositiveSmallIntegerField(default=3)

    # Eligibility
    min_referrals_for_payout = models.PositiveSmallIntegerField(default=1)
    require_verified_referee = models.BooleanField(default=True)
    commission_on_offer_only = models.BooleanField(default=False)

    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    terms       = models.TextField(blank=True, null=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_referral_programs'
        verbose_name        = _('Referral Program')
        verbose_name_plural = _('Referral Programs')
        constraints = [
            UniqueConstraint(fields=['tenant', 'slug'], name='mt_refprog_slug_per_tenant'),
            CheckConstraint(check=Q(l1_commission_pct__gte=0) & Q(l1_commission_pct__lte=100),
                            name='mt_refprog_l1_range'),
        ]

    def __str__(self):
        return f"{self.name} [{'active' if self.is_active else 'inactive'}]"


class ReferralLink(TenantScopedModel):
    """Unique referral link per user per program."""

    program   = models.ForeignKey(ReferralProgram, on_delete=models.CASCADE,
                                   related_name='%(app_label)s_%(class)s_program')
    user      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name='%(app_label)s_%(class)s_user')
    code      = models.CharField(max_length=30, unique=True, db_index=True, null=True, blank=True)
    short_url = models.URLField(max_length=500, blank=True, null=True)

    # Stats
    total_clicks      = models.PositiveIntegerField(default=0)
    total_signups     = models.PositiveIntegerField(default=0)
    total_conversions = models.PositiveIntegerField(default=0)
    total_earned      = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    is_active  = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_referral_links'
        verbose_name        = _('Referral Link')
        verbose_name_plural = _('Referral Links')
        constraints = [
            UniqueConstraint(fields=['program', 'user'], name='mt_reflink_unique_per_user_prog'),
        ]
        indexes = [
            models.Index(fields=['code'], name='mt_reflink_code_idx'),
        ]

    def __str__(self):
        return f"{self.user_id} | code={self.code} | earned={self.total_earned}"


class ReferralCommission(TenantScopedModel):
    """
    One record per commission event.
    Immutable — never update after creation.
    """

    class CommissionType(models.TextChoices):
        SIGNUP       = 'signup',       _('Signup Bonus')
        OFFER_EARN   = 'offer_earn',   _('Offer Earning Commission')
        PURCHASE     = 'purchase',     _('Purchase Commission')
        SUBSCRIPTION = 'subscription', _('Subscription Commission')
        MILESTONE    = 'milestone',    _('Milestone Bonus')

    referrer         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                          related_name='%(app_label)s_%(class)s_referrer')
    referee          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                          related_name='%(app_label)s_%(class)s_referee')
    program          = models.ForeignKey(ReferralProgram, on_delete=models.PROTECT,
                                          related_name='%(app_label)s_%(class)s_program')
    referral_link    = models.ForeignKey(ReferralLink, on_delete=models.SET_NULL,
                                          null=True, blank=True,
                                          related_name='%(app_label)s_%(class)s_referral_link')

    level            = models.PositiveSmallIntegerField(default=1, help_text="1=direct, 2=indirect…")
    commission_type  = models.CharField(max_length=20, choices=CommissionType.choices, db_index=True, null=True, blank=True)
    base_amount      = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    commission_pct   = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    commission_coins = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    is_paid          = models.BooleanField(default=False, db_index=True)
    paid_at          = models.DateTimeField(null=True, blank=True)
    reference_id     = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_referral_commissions'
        verbose_name        = _('Referral Commission')
        verbose_name_plural = _('Referral Commissions')
        ordering            = ['-created_at']
        constraints = [
            CheckConstraint(check=Q(level__gte=1) & Q(level__lte=5), name='mt_refcomm_level_range'),
            CheckConstraint(check=Q(commission_coins__gte=0),         name='mt_refcomm_coins_non_neg'),
        ]
        indexes = [
            models.Index(fields=['referrer', 'is_paid'],  name='mt_refcomm_referrer_paid_idx'),
            models.Index(fields=['referee', 'level'],     name='mt_refcomm_referee_level_idx'),
        ]

    def __str__(self):
        return f"L{self.level} | {self.referrer_id}→{self.referee_id} | {self.commission_coins} coins"


# ============================================================================
# § 16  DAILY STREAK
# ============================================================================

class DailyStreak(TenantScopedModel):
    """
    Tracks daily login streak per user.
    OneToOne with User — single row, updated daily.
    """

    user             = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                             related_name='%(app_label)s_%(class)s_user')
    current_streak   = models.PositiveIntegerField(default=0)
    longest_streak   = models.PositiveIntegerField(default=0)
    last_login_date  = models.DateField(null=True, blank=True)
    streak_start_date = models.DateField(null=True, blank=True)
    total_logins     = models.PositiveBigIntegerField(default=0)
    today_claimed    = models.BooleanField(default=False)

    # Milestones achieved
    milestone_7      = models.BooleanField(default=False)
    milestone_14     = models.BooleanField(default=False)
    milestone_30     = models.BooleanField(default=False)
    milestone_60     = models.BooleanField(default=False)
    milestone_90     = models.BooleanField(default=False)
    milestone_180    = models.BooleanField(default=False)
    milestone_365    = models.BooleanField(default=False)

    total_streak_coins = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    last_reward_date   = models.DateField(null=True, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_daily_streaks'
        verbose_name        = _('Daily Streak')
        verbose_name_plural = _('Daily Streaks')
        indexes = [
            models.Index(fields=['current_streak'], name='mt_streak_current_idx'),
            models.Index(fields=['last_login_date'], name='mt_streak_last_login_idx'),
        ]

    def __str__(self):
        return f"{self.user_id} | streak={self.current_streak}d | longest={self.longest_streak}d"

    def check_and_update(self) -> dict:
        """Update streak on login. Returns dict with coins_awarded and levelled_up."""
        from django.utils import timezone as tz
        today = tz.now().date()
        coins_awarded = Decimal('0.00')
        streak_broken = False

        if not self.last_login_date:
            self.current_streak = 1
            self.streak_start_date = today
        elif self.last_login_date == today:
            return {'coins_awarded': coins_awarded, 'streak_broken': False, 'already_claimed': True}
        else:
            diff = (today - self.last_login_date).days
            if diff == 1:
                self.current_streak += 1
            else:
                if self.current_streak > self.longest_streak:
                    self.longest_streak = self.current_streak
                self.current_streak = 1
                self.streak_start_date = today
                streak_broken = True

        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak

        self.last_login_date = today
        self.today_claimed = True
        self.total_logins += 1
        self.save()
        return {'coins_awarded': coins_awarded, 'streak_broken': streak_broken, 'already_claimed': False}


# ============================================================================
# § 17  SPIN WHEEL CONFIG  (Prize pool definition)
# ============================================================================

class SpinWheelConfig(TenantScopedModel):
    """Configuration for spin wheel / scratch card prize pool."""

    class WheelType(models.TextChoices):
        SPIN_WHEEL   = 'spin_wheel',   _('Spin Wheel')
        SCRATCH_CARD = 'scratch_card', _('Scratch Card')

    name         = models.CharField(max_length=200, null=True, blank=True)
    wheel_type   = models.CharField(max_length=15, choices=WheelType.choices, default=WheelType.SPIN_WHEEL, null=True, blank=True)
    is_active    = models.BooleanField(default=True, db_index=True)
    daily_limit  = models.PositiveSmallIntegerField(default=3)
    cooldown_hours = models.PositiveSmallIntegerField(default=0)
    min_level_required = models.PositiveSmallIntegerField(default=1)
    cost_per_spin  = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'),
                                          help_text="Coins to spend per spin (0=free)")
    valid_from   = models.DateTimeField(null=True, blank=True)
    valid_until  = models.DateTimeField(null=True, blank=True)
    description  = models.TextField(blank=True, null=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_spin_wheel_configs'
        verbose_name        = _('Spin Wheel Config')
        verbose_name_plural = _('Spin Wheel Configs')
        constraints = [
            CheckConstraint(check=Q(cost_per_spin__gte=0), name='mt_swconfig_cost_non_neg'),
        ]

    def __str__(self):
        return f"{self.name} [{self.wheel_type}]"


class PrizeConfig(TenantScopedModel):
    """Individual prize in a spin wheel / scratch card pool."""

    class PrizeType(models.TextChoices):
        COINS      = 'coins',      _('Coins')
        XP         = 'xp',         _('XP Points')
        NO_PRIZE   = 'no_prize',   _('No Prize / Miss')
        MULTIPLIER = 'multiplier', _('Earning Multiplier')
        COUPON     = 'coupon',     _('Coupon Code')
        GIFT       = 'gift',       _('Physical Gift')

    wheel_config  = models.ForeignKey(SpinWheelConfig, on_delete=models.CASCADE,
                                       related_name='%(app_label)s_%(class)s_wheel_config')
    prize_type    = models.CharField(max_length=15, choices=PrizeType.choices, null=True, blank=True)
    label         = models.CharField(max_length=100, null=True, blank=True)
    icon_url      = models.URLField(blank=True, null=True)
    prize_value   = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    weight        = models.PositiveSmallIntegerField(default=10, help_text="Relative probability weight")
    max_per_day   = models.PositiveSmallIntegerField(default=0, help_text="0=unlimited")
    is_jackpot    = models.BooleanField(default=False)
    is_active     = models.BooleanField(default=True)
    color         = models.CharField(max_length=7, default='#4CAF50', help_text="Hex color for wheel segment", null=True, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_prize_configs'
        verbose_name        = _('Prize Config')
        verbose_name_plural = _('Prize Configs')
        ordering            = ['-weight']
        constraints = [
            CheckConstraint(check=Q(weight__gte=1),       name='mt_prize_weight_positive'),
            CheckConstraint(check=Q(prize_value__gte=0),  name='mt_prize_value_non_neg'),
        ]

    def __str__(self):
        return f"{self.label} | {self.prize_type} {self.prize_value} | weight={self.weight}"


# ============================================================================
# § 18  FLASH SALE & PROMOTIONS
# ============================================================================

class FlashSale(TenantScopedModel):
    """
    Time-limited promotional event.
    Can boost offer rewards, grant bonus coins, or reduce subscription price.
    """

    class SaleType(models.TextChoices):
        OFFER_BOOST    = 'offer_boost',    _('Offer Reward Multiplier')
        COIN_BONUS     = 'coin_bonus',     _('Bonus Coin Grant')
        SUBSCRIPTION   = 'subscription',   _('Subscription Discount')
        DOUBLE_POINTS  = 'double_points',  _('Double Points Event')
        FREE_SPIN      = 'free_spin',      _('Extra Free Spins')

    name          = models.CharField(max_length=200, null=True, blank=True)
    slug          = models.SlugField(max_length=200, null=True, blank=True)
    sale_type     = models.CharField(max_length=20, choices=SaleType.choices, db_index=True, null=True, blank=True)
    description   = models.TextField(blank=True, null=True)
    banner_url    = models.URLField(blank=True, null=True)

    # Timing
    starts_at     = models.DateTimeField(db_index=True)
    ends_at       = models.DateTimeField(db_index=True)
    is_active     = models.BooleanField(default=True, db_index=True)

    # Effect
    multiplier    = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'))
    bonus_coins   = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_pct  = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    extra_spins   = models.PositiveSmallIntegerField(default=0)

    # Eligibility
    target_segments  = models.ManyToManyField(UserSegment, blank=True,
                                               related_name='%(app_label)s_%(class)s_target_segments')
    min_user_level   = models.PositiveSmallIntegerField(default=1)
    target_offer_types = models.JSONField(default=_list, blank=True)
    target_countries   = models.JSONField(default=_list, blank=True)

    # Stats
    total_participants = models.PositiveIntegerField(default=0)
    total_coins_given  = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_flash_sales'
        verbose_name        = _('Flash Sale')
        verbose_name_plural = _('Flash Sales')
        ordering            = ['-starts_at']
        constraints = [
            CheckConstraint(check=Q(ends_at__gt=F('starts_at')), name='mt_flash_end_after_start'),
            CheckConstraint(check=Q(multiplier__gte=1),           name='mt_flash_multiplier_gte_1'),
            CheckConstraint(check=Q(discount_pct__gte=0) & Q(discount_pct__lte=100),
                            name='mt_flash_discount_range'),
            UniqueConstraint(fields=['tenant', 'slug'], name='mt_flash_slug_per_tenant'),
        ]
        indexes = [
            models.Index(fields=['is_active', 'starts_at', 'ends_at'], name='mt_flash_active_schedule_idx'),
        ]

    def __str__(self):
        return f"{self.name} | {self.starts_at:%Y-%m-%d %H:%M} → {self.ends_at:%Y-%m-%d %H:%M}"

    @property
    def is_live(self) -> bool:
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.ends_at


# ============================================================================
# § 19  COUPON / PROMO CODE
# ============================================================================

class Coupon(TenantScopedModel):
    """
    Discount / bonus coupon code.
    Can grant coins, discount subscriptions, or boost offers.
    """

    class CouponType(models.TextChoices):
        COIN_GRANT      = 'coin_grant',      _('Coin Grant')
        SUBSCRIPTION    = 'subscription',    _('Subscription Discount')
        OFFER_BOOST     = 'offer_boost',     _('Offer Boost')
        FREE_PREMIUM    = 'free_premium',    _('Free Premium Days')

    code            = models.CharField(max_length=50, unique=True, db_index=True, null=True, blank=True)
    name            = models.CharField(max_length=200, null=True, blank=True)
    description     = models.TextField(blank=True, null=True)
    coupon_type     = models.CharField(max_length=20, choices=CouponType.choices, db_index=True, null=True, blank=True)
    is_active       = models.BooleanField(default=True, db_index=True)

    # Value
    coin_amount     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_pct    = models.DecimalField(max_digits=5,  decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    free_days       = models.PositiveSmallIntegerField(default=0)
    multiplier      = models.DecimalField(max_digits=5,  decimal_places=2, default=Decimal('1.00'))

    # Limits
    max_uses        = models.PositiveIntegerField(default=0, help_text="0=unlimited")
    max_uses_per_user = models.PositiveSmallIntegerField(default=1)
    current_uses    = models.PositiveIntegerField(default=0)
    min_user_level  = models.PositiveSmallIntegerField(default=1)
    valid_from      = models.DateTimeField(null=True, blank=True)
    valid_until     = models.DateTimeField(null=True, blank=True, db_index=True)

    # Targeting
    target_plan     = models.ForeignKey('SubscriptionPlan', on_delete=models.SET_NULL,
                                         null=True, blank=True,
                                         related_name='%(app_label)s_%(class)s_target_plan')
    single_use      = models.BooleanField(default=False)
    first_time_only = models.BooleanField(default=False)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_coupons'
        verbose_name        = _('Coupon')
        verbose_name_plural = _('Coupons')
        ordering            = ['-created_at']
        constraints = [
            CheckConstraint(check=Q(coin_amount__gte=0),    name='mt_coupon_coins_non_neg'),
            CheckConstraint(check=Q(discount_pct__gte=0) & Q(discount_pct__lte=100),
                            name='mt_coupon_discount_range'),
            CheckConstraint(check=Q(multiplier__gte=1),     name='mt_coupon_multiplier_gte_1'),
        ]

    def __str__(self):
        return f"[{self.code}] {self.name} | {self.coupon_type}"

    @property
    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_uses and self.current_uses >= self.max_uses:
            return False
        return True


class CouponUsage(TenantScopedModel):
    """Records each coupon redemption. Immutable after creation."""

    coupon     = models.ForeignKey(Coupon, on_delete=models.CASCADE,
                                    related_name='%(app_label)s_%(class)s_coupon')
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name='%(app_label)s_%(class)s_user')
    used_at    = models.DateTimeField(auto_now_add=True)
    coins_granted = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_applied = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    reference_id  = models.CharField(max_length=100, blank=True, null=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_coupon_usages'
        verbose_name        = _('Coupon Usage')
        verbose_name_plural = _('Coupon Usages')
        ordering            = ['-used_at']
        constraints = [
            UniqueConstraint(
                fields=['coupon', 'user'],
                name='mt_coupon_usage_uniq'
            ),
        ]
        indexes = [
            models.Index(fields=['coupon', 'user'],  name='mt_coup_usage_idx'),
            models.Index(fields=['user', 'used_at'], name='mt_coupon_usage_user_time_idx'),
        ]

    def __str__(self):
        return f"{self.user_id} | {self.coupon.code} | {self.used_at:%Y-%m-%d}"


# ============================================================================
# § 20  FRAUD ALERT
# ============================================================================

class FraudAlert(TenantScopedModel):
    """
    System-generated fraud alert for review.
    Created automatically when fraud_score exceeds threshold.
    """

    class AlertType(models.TextChoices):
        HIGH_FRAUD_SCORE   = 'high_fraud_score',   _('High Fraud Score Completion')
        DUPLICATE_DEVICE   = 'duplicate_device',   _('Duplicate Device Detected')
        VPN_PROXY          = 'vpn_proxy',          _('VPN/Proxy Detected')
        VELOCITY_BREACH    = 'velocity_breach',    _('Velocity Limit Breached')
        IP_BLACKLIST       = 'ip_blacklist',       _('Blacklisted IP')
        UNUSUAL_PATTERN    = 'unusual_pattern',    _('Unusual Earnings Pattern')
        MULTIPLE_ACCOUNTS  = 'multiple_accounts',  _('Possible Multiple Accounts')
        POSTBACK_MISMATCH  = 'postback_mismatch',  _('Postback Signature Mismatch')

    class Severity(models.TextChoices):
        LOW      = 'low',      _('Low')
        MEDIUM   = 'medium',   _('Medium')
        HIGH     = 'high',     _('High')
        CRITICAL = 'critical', _('Critical')

    class Resolution(models.TextChoices):
        OPEN      = 'open',      _('Open')
        REVIEWING = 'reviewing', _('Under Review')
        CLEARED   = 'cleared',   _('Cleared — False Positive')
        CONFIRMED = 'confirmed', _('Confirmed — Action Taken')
        AUTO_RESOLVED = 'auto_resolved', _('Auto-Resolved')

    user           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                        related_name='%(app_label)s_%(class)s_user')
    alert_id       = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    alert_type     = models.CharField(max_length=25, choices=AlertType.choices, db_index=True, null=True, blank=True)
    severity       = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM, db_index=True, null=True, blank=True)
    resolution     = models.CharField(max_length=15, choices=Resolution.choices, default=Resolution.OPEN, db_index=True, null=True, blank=True)

    fraud_score    = models.PositiveSmallIntegerField(default=0)
    description    = models.TextField()
    evidence       = models.JSONField(default=_dict, blank=True)

    # Related objects
    offer_completion = models.ForeignKey('OfferCompletion', on_delete=models.SET_NULL,
                                          null=True, blank=True,
                                          related_name='%(app_label)s_%(class)s_offer_completion')
    postback_log   = models.ForeignKey('PostbackLog', on_delete=models.SET_NULL,
                                        null=True, blank=True,
                                        related_name='%(app_label)s_%(class)s_postback_log')
    ip_address     = models.GenericIPAddressField(null=True, blank=True)

    # Resolution
    resolved_by    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                        null=True, blank=True,
                                        related_name='%(app_label)s_%(class)s_resolved_by')
    resolved_at    = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True, null=True)

    # Auto-action taken
    user_blocked   = models.BooleanField(default=False)
    completion_rejected = models.BooleanField(default=False)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_fraud_alerts'
        verbose_name        = _('Fraud Alert')
        verbose_name_plural = _('Fraud Alerts')
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'severity', 'resolution'], name='mt_fraud_user_sev_res_idx'),
            models.Index(fields=['alert_type', 'resolution'],        name='mt_fraud_type_res_idx'),
            models.Index(fields=['severity', 'resolution'],          name='mt_fraud_sev_res_idx'),
        ]

    def __str__(self):
        return f"Alert {self.alert_id} | {self.alert_type} | {self.severity} | {self.resolution}"


# ============================================================================
# § 21  REVENUE GOAL  (Business targets)
# ============================================================================

class RevenueGoal(TenantScopedModel):
    """
    Monthly / quarterly / yearly revenue targets.
    Used for dashboard progress bars and alerting.
    """

    class Period(models.TextChoices):
        DAILY     = 'daily',     _('Daily')
        WEEKLY    = 'weekly',    _('Weekly')
        MONTHLY   = 'monthly',   _('Monthly')
        QUARTERLY = 'quarterly', _('Quarterly')
        YEARLY    = 'yearly',    _('Yearly')

    class GoalType(models.TextChoices):
        TOTAL_REVENUE = 'total_revenue', _('Total Revenue')
        AD_REVENUE    = 'ad_revenue',    _('Ad Network Revenue')
        OFFER_REVENUE = 'offer_revenue', _('Offerwall Revenue')
        SUBSCRIPTIONS = 'subscriptions', _('Subscription Revenue')
        NEW_USERS     = 'new_users',     _('New User Registrations')
        ACTIVE_USERS  = 'active_users',  _('Daily Active Users')

    name         = models.CharField(max_length=200, null=True, blank=True)
    period       = models.CharField(max_length=15, choices=Period.choices, db_index=True, null=True, blank=True)
    goal_type    = models.CharField(max_length=20, choices=GoalType.choices, db_index=True, null=True, blank=True)
    target_value = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    current_value = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))
    currency     = models.CharField(max_length=5, default='USD', null=True, blank=True)
    period_start = models.DateField(db_index=True)
    period_end   = models.DateField(db_index=True)
    is_active    = models.BooleanField(default=True)
    notes        = models.TextField(blank=True, null=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_revenue_goals'
        verbose_name        = _('Revenue Goal')
        verbose_name_plural = _('Revenue Goals')
        ordering            = ['-period_start']
        constraints = [
            CheckConstraint(check=Q(target_value__gt=0),              name='mt_goal_target_positive'),
            CheckConstraint(check=Q(period_end__gt=F('period_start')), name='mt_goal_end_after_start'),
        ]

    def __str__(self):
        return f"{self.name} | {self.period} | target={self.target_value}"

    @property
    def progress_pct(self) -> Decimal:
        if not self.target_value:
            return Decimal('0.00')
        return (self.current_value / self.target_value * 100).quantize(Decimal('0.01'))

    @property
    def is_achieved(self) -> bool:
        return self.current_value >= self.target_value


# ============================================================================
# § 22  PUBLISHER ACCOUNT  (Advertiser/Publisher management)
# ============================================================================

class PublisherAccount(TenantScopedModel):
    """
    Represents an advertiser or publisher account.
    Linked to one or more AdCampaigns.
    """

    class AccountType(models.TextChoices):
        ADVERTISER = 'advertiser', _('Advertiser')
        PUBLISHER  = 'publisher',  _('Publisher')
        AGENCY     = 'agency',     _('Agency')
        NETWORK    = 'network',    _('Network Partner')

    class Status(models.TextChoices):
        PENDING   = 'pending',   _('Pending Approval')
        ACTIVE    = 'active',    _('Active')
        SUSPENDED = 'suspended', _('Suspended')
        BANNED    = 'banned',    _('Banned')
        CLOSED    = 'closed',    _('Closed')

    account_id    = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    account_type  = models.CharField(max_length=15, choices=AccountType.choices, db_index=True, null=True, blank=True)
    company_name  = models.CharField(max_length=300, null=True, blank=True)
    contact_name  = models.CharField(max_length=200, null=True, blank=True)
    email         = models.EmailField(db_index=True)
    phone         = models.CharField(max_length=30, blank=True, null=True)
    website       = models.URLField(blank=True, null=True)
    country       = models.CharField(max_length=2, blank=True, null=True)
    status        = models.CharField(max_length=12, choices=Status.choices,
                                      default=Status.PENDING, db_index=True, null=True, blank=True)

    # Billing
    billing_email      = models.EmailField(blank=True, null=True)
    payment_terms_days = models.PositiveSmallIntegerField(default=30)
    credit_limit_usd   = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    current_balance_usd = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_spend_usd    = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))
    total_revenue_usd  = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))

    # Revenue share override (overrides AdNetwork.revenue_share for this account)
    custom_rev_share   = models.DecimalField(max_digits=5, decimal_places=4,
                                              null=True, blank=True,
                                              validators=[MinValueValidator(Decimal('0')),
                                                          MaxValueValidator(Decimal('1'))])

    # KYC / verification
    is_verified        = models.BooleanField(default=False)
    verified_at        = models.DateTimeField(null=True, blank=True)
    tax_id             = models.CharField(max_length=50, blank=True, null=True)
    contract_signed    = models.BooleanField(default=False)
    contract_signed_at = models.DateTimeField(null=True, blank=True)

    account_manager    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                            null=True, blank=True,
                                            related_name='%(app_label)s_%(class)s_account_manager')
    notes              = models.TextField(blank=True, null=True)
    extra              = models.JSONField(default=_dict, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_publisher_accounts'
        verbose_name        = _('Publisher Account')
        verbose_name_plural = _('Publisher Accounts')
        ordering            = ['-created_at']
        constraints = [
            CheckConstraint(check=Q(credit_limit_usd__gte=0),   name='mt_pub_credit_non_neg'),
            CheckConstraint(check=Q(current_balance_usd__gte=0), name='mt_pub_balance_non_neg'),
            CheckConstraint(
                check=Q(custom_rev_share__isnull=True) |
                      (Q(custom_rev_share__gte=0) & Q(custom_rev_share__lte=1)),
                name='mt_pub_revshare_range',
            ),
        ]
        indexes = [
            models.Index(fields=['account_type', 'status'], name='mt_pub_type_status_idx'),
            models.Index(fields=['email'],                  name='mt_pub_email_idx'),
        ]

    def __str__(self):
        return f"{self.company_name} [{self.account_type}] [{self.status}]"


# ============================================================================
# § 23  NOTIFICATION TEMPLATE  (Monetization notifications)
# ============================================================================

class MonetizationNotificationTemplate(TenantScopedModel):
    """
    Re-usable notification templates for monetization events.
    Variables like {{user_name}}, {{amount}} replaced at send time.
    """

    class EventType(models.TextChoices):
        OFFER_APPROVED      = 'offer_approved',      _('Offer Approved')
        OFFER_REJECTED      = 'offer_rejected',      _('Offer Rejected')
        REWARD_CREDITED     = 'reward_credited',     _('Reward Credited')
        WITHDRAWAL_APPROVED = 'withdrawal_approved', _('Withdrawal Approved')
        WITHDRAWAL_REJECTED = 'withdrawal_rejected', _('Withdrawal Rejected')
        SUBSCRIPTION_START  = 'subscription_start',  _('Subscription Started')
        SUBSCRIPTION_EXPIRE = 'subscription_expire', _('Subscription Expiring')
        REFERRAL_JOINED     = 'referral_joined',     _('Referral Joined')
        REFERRAL_EARNED     = 'referral_earned',     _('Referral Commission Earned')
        LEVEL_UP            = 'level_up',            _('Level Up')
        STREAK_MILESTONE    = 'streak_milestone',    _('Streak Milestone')
        FLASH_SALE_START    = 'flash_sale_start',    _('Flash Sale Started')
        FRAUD_ALERT         = 'fraud_alert',         _('Fraud Alert')
        COUPON_EXPIRY       = 'coupon_expiry',       _('Coupon Expiring Soon')
        GOAL_ACHIEVED       = 'goal_achieved',       _('Revenue Goal Achieved')

    class Channel(models.TextChoices):
        IN_APP = 'in_app', _('In-App')
        EMAIL  = 'email',  _('Email')
        SMS    = 'sms',    _('SMS')
        PUSH   = 'push',   _('Push Notification')

    event_type    = models.CharField(max_length=30, choices=EventType.choices, db_index=True, null=True, blank=True)
    channel       = models.CharField(max_length=10, choices=Channel.choices, default=Channel.IN_APP, null=True, blank=True)
    name          = models.CharField(max_length=200, null=True, blank=True)
    subject       = models.CharField(max_length=300, blank=True, null=True)
    body_template = models.TextField()
    variables     = models.JSONField(default=_list, blank=True,
                                      help_text="List of variable names used in template")
    is_active     = models.BooleanField(default=True, db_index=True)
    language      = models.CharField(max_length=10, default='bn', db_index=True, null=True, blank=True)

    class Meta(TenantScopedModel.Meta):
        db_table = 'mt_notification_templates'
        verbose_name        = _('Notification Template')
        verbose_name_plural = _('Notification Templates')
        ordering            = ['event_type', 'channel']
        constraints = [
            UniqueConstraint(
                fields=['tenant', 'event_type', 'channel', 'language'],
                name='mt_notif_unique_per_event_channel_lang',
            ),
        ]

    def __str__(self):
        return f"{self.event_type} | {self.channel} | {self.language}"

    def render(self, context: dict) -> str:
        """Replace {{variable}} placeholders with context values."""
        body = self.body_template
        for key, value in context.items():
            body = body.replace(f"{{{{{key}}}}}", str(value))
        return body
