# api/publisher_tools/site_management/site_analytics.py
"""
Site Analytics — Site traffic, audience, ও performance analytics।
"""
from decimal import Decimal
from datetime import date, timedelta
from typing import Dict, List
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from core.models import TimeStampedModel
from django.db import models
from django.utils.translation import gettext_lazy as _


class SiteTrafficData(TimeStampedModel):
    """
    Site-এর daily traffic data।
    Google Analytics বা server logs থেকে sync হয়।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_sitetraffic_tenant', db_index=True,
    )

    site = models.ForeignKey(
        'publisher_tools.Site',
        on_delete=models.CASCADE,
        related_name='traffic_data',
        verbose_name=_("Site"),
        db_index=True,
    )
    date = models.DateField(verbose_name=_("Date"), db_index=True)

    # ── Core Traffic ──────────────────────────────────────────────────────────
    sessions           = models.BigIntegerField(default=0, verbose_name=_("Sessions"))
    users              = models.BigIntegerField(default=0, verbose_name=_("Users"))
    new_users          = models.BigIntegerField(default=0, verbose_name=_("New Users"))
    pageviews          = models.BigIntegerField(default=0, verbose_name=_("Pageviews"))
    unique_pageviews   = models.BigIntegerField(default=0, verbose_name=_("Unique Pageviews"))
    bounce_rate        = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Bounce Rate (%)"))
    avg_session_duration = models.IntegerField(default=0, verbose_name=_("Avg Session Duration (seconds)"))
    pages_per_session  = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    # ── Traffic Sources ────────────────────────────────────────────────────────
    organic_traffic    = models.BigIntegerField(default=0, verbose_name=_("Organic Search"))
    direct_traffic     = models.BigIntegerField(default=0, verbose_name=_("Direct"))
    referral_traffic   = models.BigIntegerField(default=0, verbose_name=_("Referral"))
    social_traffic     = models.BigIntegerField(default=0, verbose_name=_("Social"))
    email_traffic      = models.BigIntegerField(default=0, verbose_name=_("Email"))
    paid_traffic       = models.BigIntegerField(default=0, verbose_name=_("Paid / CPC"))
    other_traffic      = models.BigIntegerField(default=0, verbose_name=_("Other"))

    # ── Device Breakdown ──────────────────────────────────────────────────────
    mobile_sessions    = models.BigIntegerField(default=0, verbose_name=_("Mobile Sessions"))
    desktop_sessions   = models.BigIntegerField(default=0, verbose_name=_("Desktop Sessions"))
    tablet_sessions    = models.BigIntegerField(default=0, verbose_name=_("Tablet Sessions"))

    # ── Geographic ────────────────────────────────────────────────────────────
    top_countries = models.JSONField(
        default=list, blank=True,
        verbose_name=_("Top Countries"),
        help_text=_("[{'country': 'BD', 'sessions': 5000, 'pct': 60.5}, ...]"),
    )
    top_cities = models.JSONField(
        default=list, blank=True,
        verbose_name=_("Top Cities"),
    )

    # ── Content ───────────────────────────────────────────────────────────────
    top_pages = models.JSONField(
        default=list, blank=True,
        verbose_name=_("Top Pages"),
        help_text=_("[{'path': '/article/1', 'pageviews': 1000}, ...]"),
    )
    top_landing_pages = models.JSONField(default=list, blank=True)
    top_exit_pages    = models.JSONField(default=list, blank=True)

    # ── Data Source ───────────────────────────────────────────────────────────
    data_source = models.CharField(
        max_length=30,
        choices=[
            ('google_analytics', 'Google Analytics'),
            ('google_analytics_4', 'Google Analytics 4'),
            ('matomo', 'Matomo'),
            ('server_logs', 'Server Logs'),
            ('manual', 'Manually Entered'),
        ],
        default='manual',
        verbose_name=_("Data Source"),
    )
    is_estimated = models.BooleanField(default=False, verbose_name=_("Estimated Data"))

    class Meta:
        db_table = 'publisher_tools_site_traffic_data'
        verbose_name = _('Site Traffic Data')
        verbose_name_plural = _('Site Traffic Data')
        unique_together = [['site', 'date']]
        ordering = ['-date']
        indexes = [
            models.Index(fields=['site', 'date']),
        ]

    def __str__(self):
        return f"{self.site.domain} — {self.date} — {self.sessions:,} sessions"

    @property
    def mobile_pct(self):
        total = self.sessions or 1
        return round(self.mobile_sessions / total * 100, 1)

    @property
    def desktop_pct(self):
        total = self.sessions or 1
        return round(self.desktop_sessions / total * 100, 1)

    @property
    def return_visitor_pct(self):
        if self.users > 0:
            return round((1 - self.new_users / self.users) * 100, 1)
        return 0.0


class SiteAudienceProfile(TimeStampedModel):
    """
    Site-এর audience demographics।
    Monthly snapshot of audience characteristics।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_siteaudience_tenant', db_index=True,
    )

    site = models.ForeignKey(
        'publisher_tools.Site',
        on_delete=models.CASCADE,
        related_name='audience_profiles',
        verbose_name=_("Site"),
        db_index=True,
    )
    month = models.DateField(verbose_name=_("Month (first day of month)"), db_index=True)

    # ── Demographics ──────────────────────────────────────────────────────────
    age_18_24_pct  = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    age_25_34_pct  = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    age_35_44_pct  = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    age_45_54_pct  = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    age_55_plus_pct= models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    male_pct   = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    female_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    other_pct  = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    # ── Geographic ────────────────────────────────────────────────────────────
    primary_country    = models.CharField(max_length=100, blank=True)
    primary_country_pct= models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    geo_distribution   = models.JSONField(default=list, blank=True, help_text=_("[{'country': 'BD', 'pct': 60.5}, ...]"))

    # ── Interests ─────────────────────────────────────────────────────────────
    top_interests = models.JSONField(
        default=list, blank=True,
        verbose_name=_("Top Interest Categories"),
        help_text=_("['Technology', 'Sports', 'Entertainment']"),
    )

    # ── Device Preferences ────────────────────────────────────────────────────
    primary_device  = models.CharField(max_length=20, choices=[('mobile','Mobile'),('desktop','Desktop'),('tablet','Tablet')], default='mobile')
    android_pct     = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    ios_pct         = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    windows_pct     = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    mac_pct         = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    # ── Browser ───────────────────────────────────────────────────────────────
    chrome_pct  = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    firefox_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    safari_pct  = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    edge_pct    = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    other_browser_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    # ── Engagement ────────────────────────────────────────────────────────────
    avg_session_minutes = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    repeat_visitor_pct  = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        db_table = 'publisher_tools_site_audience_profiles'
        verbose_name = _('Site Audience Profile')
        verbose_name_plural = _('Site Audience Profiles')
        unique_together = [['site', 'month']]
        ordering = ['-month']

    def __str__(self):
        return f"{self.site.domain} Audience — {self.month.strftime('%B %Y')}"


def get_site_performance_summary(site, days: int = 30) -> Dict:
    """
    Site-এর comprehensive performance summary।
    Traffic + Revenue + Quality সব একসাথে।
    """
    from ..models import PublisherEarning, SiteQualityMetric

    start = timezone.now().date() - timedelta(days=days)
    end   = timezone.now().date()

    # Traffic
    traffic = SiteTrafficData.objects.filter(
        site=site, date__gte=start,
    ).aggregate(
        sessions=Sum('sessions'),
        pageviews=Sum('pageviews'),
        users=Sum('users'),
        avg_bounce=Avg('bounce_rate'),
        avg_duration=Avg('avg_session_duration'),
    )

    # Revenue
    revenue = PublisherEarning.objects.filter(
        site=site, date__gte=start,
    ).aggregate(
        total=Sum('publisher_revenue'),
        impressions=Sum('impressions'),
        clicks=Sum('clicks'),
    )

    rev_total = revenue.get('total') or Decimal('0')
    impressions = revenue.get('impressions') or 0

    # Latest quality metric
    latest_quality = SiteQualityMetric.objects.filter(
        site=site
    ).order_by('-date').first()

    return {
        'site_id':   site.site_id,
        'domain':    site.domain,
        'period':    {'start': str(start), 'end': str(end), 'days': days},
        'traffic': {
            'sessions':   traffic.get('sessions') or 0,
            'pageviews':  traffic.get('pageviews') or 0,
            'users':      traffic.get('users') or 0,
            'avg_bounce': float(traffic.get('avg_bounce') or 0),
            'avg_duration_sec': traffic.get('avg_duration') or 0,
        },
        'revenue': {
            'total':      float(rev_total),
            'impressions': impressions,
            'clicks':     revenue.get('clicks') or 0,
            'ecpm':       float((rev_total / impressions * 1000) if impressions > 0 else 0),
            'rpm':        float((rev_total / (traffic.get('pageviews') or 1) * 1000)),
        },
        'quality': {
            'score':          latest_quality.overall_quality_score if latest_quality else site.quality_score,
            'viewability':    float(latest_quality.viewability_rate) if latest_quality else 0,
            'ivt_pct':        float(latest_quality.invalid_traffic_percentage) if latest_quality else 0,
            'has_alerts':     latest_quality.has_alerts if latest_quality else False,
            'ads_txt_valid':  site.ads_txt_verified,
        },
    }
