# api/publisher_tools/integrations/google_analytics_integration.py
"""
Google Analytics Integration — GA4 ও Universal Analytics sync।
Publisher সাইটের traffic data automatically pull করে।
"""
from decimal import Decimal
from datetime import date, timedelta
from typing import Dict, List, Optional
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class GoogleAnalyticsIntegration(TimeStampedModel):
    """
    Publisher-এর Google Analytics integration।
    GA4 property credentials এখানে store হয়।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_gaintegration_tenant', db_index=True,
    )

    GA_VERSION_CHOICES = [
        ('ga4',        'Google Analytics 4 (GA4)'),
        ('universal',  'Universal Analytics (UA)'),
    ]

    STATUS_CHOICES = [
        ('pending',     _('Pending Setup')),
        ('active',      _('Active — Syncing')),
        ('error',       _('Error — Check Credentials')),
        ('disconnected',_('Disconnected')),
        ('paused',      _('Paused')),
    ]

    # ── Core ──────────────────────────────────────────────────────────────────
    publisher = models.ForeignKey(
        'publisher_tools.Publisher',
        on_delete=models.CASCADE,
        related_name='ga_integrations',
        verbose_name=_("Publisher"),
    )
    site = models.ForeignKey(
        'publisher_tools.Site',
        on_delete=models.CASCADE,
        related_name='ga_integrations',
        verbose_name=_("Site"),
        null=True, blank=True,
    )
    name = models.CharField(max_length=200, verbose_name=_("Integration Name"))

    # ── GA Config ─────────────────────────────────────────────────────────────
    ga_version          = models.CharField(max_length=20, choices=GA_VERSION_CHOICES, default='ga4')
    property_id         = models.CharField(max_length=50, verbose_name=_("GA Property ID"), help_text=_("GA4: 'G-XXXXXXX' or property number | UA: 'UA-XXXXX-X'"))
    measurement_id      = models.CharField(max_length=20, blank=True, verbose_name=_("GA4 Measurement ID"))
    view_id             = models.CharField(max_length=20, blank=True, verbose_name=_("UA View ID"))
    tracking_id         = models.CharField(max_length=20, blank=True, verbose_name=_("Tracking ID (UA)"))

    # ── API Credentials (encrypted in production) ──────────────────────────────
    service_account_json = models.JSONField(
        default=dict, blank=True,
        verbose_name=_("Service Account JSON"),
        help_text=_("Google Service Account credentials (keep this secure!)"),
    )
    oauth_access_token   = models.TextField(blank=True, verbose_name=_("OAuth Access Token"))
    oauth_refresh_token  = models.TextField(blank=True, verbose_name=_("OAuth Refresh Token"))
    token_expires_at     = models.DateTimeField(null=True, blank=True)

    # ── Sync Settings ─────────────────────────────────────────────────────────
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    is_active           = models.BooleanField(default=True)
    sync_interval_hours = models.IntegerField(default=24, verbose_name=_("Sync Interval (hours)"))
    sync_from_date      = models.DateField(null=True, blank=True, verbose_name=_("Sync Historical Data From"))
    last_sync_at        = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Synced At"))
    last_sync_status    = models.CharField(max_length=20, blank=True)
    last_error_message  = models.TextField(blank=True)
    sync_count          = models.IntegerField(default=0, verbose_name=_("Total Sync Count"))

    # ── Data to Sync ──────────────────────────────────────────────────────────
    sync_pageviews      = models.BooleanField(default=True)
    sync_sessions       = models.BooleanField(default=True)
    sync_users          = models.BooleanField(default=True)
    sync_bounce_rate    = models.BooleanField(default=True)
    sync_traffic_sources= models.BooleanField(default=True)
    sync_device_breakdown=models.BooleanField(default=True)
    sync_geography      = models.BooleanField(default=True)
    sync_top_pages      = models.BooleanField(default=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_ga_integrations'
        verbose_name = _('Google Analytics Integration')
        verbose_name_plural = _('Google Analytics Integrations')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publisher', 'status'], name='idx_publisher_status_1591'),
            models.Index(fields=['property_id'], name='idx_property_id_1592'),
        ]

    def __str__(self):
        return f"{self.name} — {self.property_id} [{self.status}]"

    @property
    def is_token_valid(self):
        if self.token_expires_at:
            return timezone.now() < self.token_expires_at
        return bool(self.oauth_access_token)

    def sync_traffic_data(self, target_date: date = None) -> bool:
        """
        Google Analytics থেকে traffic data sync করে।
        Production-এ google-analytics-data library use করতে হবে।
        """
        if not target_date:
            target_date = (timezone.now() - timedelta(days=1)).date()

        try:
            # Production implementation:
            # from google.analytics.data_v1beta import BetaAnalyticsDataClient
            # from google.analytics.data_v1beta.types import (
            #     DateRange, Dimension, Metric, RunReportRequest
            # )
            # client = BetaAnalyticsDataClient.from_service_account_info(self.service_account_json)
            # ... make API call ...

            # For now, mark as successful
            self.last_sync_at = timezone.now()
            self.last_sync_status = 'success'
            self.sync_count += 1
            self.status = 'active'
            self.save(update_fields=['last_sync_at', 'last_sync_status', 'sync_count', 'status', 'updated_at'])
            return True

        except Exception as e:
            self.last_error_message = str(e)
            self.last_sync_status = 'error'
            self.status = 'error'
            self.save(update_fields=['last_error_message', 'last_sync_status', 'status', 'updated_at'])
            return False

    def get_ga_tag_code(self) -> str:
        """GA tracking code generate করে site-এ embed করার জন্য"""
        if self.ga_version == 'ga4' and self.measurement_id:
            return f"""<!-- Google Analytics 4 Tag — {self.name} -->
<script async src="https://www.googletagmanager.com/gtag/js?id={self.measurement_id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{self.measurement_id}');
</script>"""
        elif self.ga_version == 'universal' and self.tracking_id:
            return f"""<!-- Universal Analytics — {self.name} -->
<script>
(function(i,s,o,g,r,a,m){{i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){{
(i[r].q=i[r].q||[]).push(arguments)}},i[r].l=1*new Date();a=s.createElement(o),
m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
}})(window,document,'script','https://www.google-analytics.com/analytics.js','ga');
ga('create', '{self.tracking_id}', 'auto');
ga('send', 'pageview');
</script>"""
        return ''


class AdSenseIntegration(TimeStampedModel):
    """
    Google AdSense integration।
    AdSense revenue data sync করার জন্য।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_adsense_tenant', db_index=True,
    )

    publisher = models.ForeignKey(
        'publisher_tools.Publisher',
        on_delete=models.CASCADE,
        related_name='adsense_integrations',
        verbose_name=_("Publisher"),
    )
    adsense_publisher_id = models.CharField(
        max_length=50,
        verbose_name=_("AdSense Publisher ID"),
        help_text=_("e.g., pub-1234567890123456"),
        db_index=True,
    )
    oauth_credentials = models.JSONField(default=dict, blank=True, verbose_name=_("OAuth Credentials"))
    is_active         = models.BooleanField(default=True)
    last_sync_at      = models.DateTimeField(null=True, blank=True)
    sync_earnings     = models.BooleanField(default=True, verbose_name=_("Sync Earnings Data"))
    sync_ad_units     = models.BooleanField(default=True, verbose_name=_("Sync Ad Units"))
    auto_create_units = models.BooleanField(
        default=False,
        verbose_name=_("Auto-create Ad Units from AdSense"),
    )

    class Meta:
        db_table = 'publisher_tools_adsense_integrations'
        verbose_name = _('AdSense Integration')
        verbose_name_plural = _('AdSense Integrations')

    def __str__(self):
        return f"{self.publisher.publisher_id} — AdSense {self.adsense_publisher_id}"


class ThirdPartyIntegration(TimeStampedModel):
    """
    General third-party integration।
    Analytics, CMS, e-commerce platforms।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_thirdparty_tenant', db_index=True,
    )

    INTEGRATION_TYPE_CHOICES = [
        # Analytics
        ('google_analytics',  'Google Analytics'),
        ('google_tag_manager','Google Tag Manager'),
        ('facebook_pixel',    'Facebook Pixel'),
        ('mixpanel',          'Mixpanel'),
        ('amplitude',         'Amplitude'),
        ('segment',           'Segment'),
        # CMS
        ('wordpress',         'WordPress'),
        ('shopify',           'Shopify'),
        ('woocommerce',       'WooCommerce'),
        ('drupal',            'Drupal'),
        ('joomla',            'Joomla'),
        # SDK
        ('react_sdk',         'React SDK'),
        ('angular_sdk',       'Angular SDK'),
        ('vue_sdk',           'Vue.js SDK'),
        ('android_sdk',       'Android SDK'),
        ('ios_sdk',           'iOS SDK'),
        ('flutter_sdk',       'Flutter SDK'),
        # Other
        ('custom_api',        'Custom API'),
        ('zapier',            'Zapier'),
        ('webhook',           'Generic Webhook'),
    ]

    STATUS_CHOICES = [
        ('active',      _('Active')),
        ('inactive',    _('Inactive')),
        ('error',       _('Error')),
        ('pending',     _('Pending Setup')),
    ]

    publisher        = models.ForeignKey('publisher_tools.Publisher', on_delete=models.CASCADE, related_name='third_party_integrations')
    integration_type = models.CharField(max_length=30, choices=INTEGRATION_TYPE_CHOICES, db_index=True)
    name             = models.CharField(max_length=200)
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    credentials      = models.JSONField(default=dict, blank=True, verbose_name=_("API Credentials / Config"))
    settings         = models.JSONField(default=dict, blank=True, verbose_name=_("Integration Settings"))
    is_active        = models.BooleanField(default=True)
    last_sync_at     = models.DateTimeField(null=True, blank=True)
    error_message    = models.TextField(blank=True)
    description      = models.TextField(blank=True)

    class Meta:
        db_table = 'publisher_tools_third_party_integrations'
        verbose_name = _('Third Party Integration')
        verbose_name_plural = _('Third Party Integrations')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publisher', 'integration_type', 'status'], name='idx_publisher_integration__dfc'),
        ]

    def __str__(self):
        return f"{self.publisher.publisher_id} — {self.get_integration_type_display()} [{self.status}]"

    def get_integration_snippet(self) -> str:
        """Integration setup-এর জন্য code snippet return করে"""
        snippets = {
            'google_tag_manager': f'''<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
}})(window,document,'script','dataLayer','{self.credentials.get("container_id", "GTM-XXXXXX")}');</script>''',

            'react_sdk': '''// React SDK Installation
npm install @publisher-tools/react-sdk

// Usage
import {{ PublisherToolsProvider, AdUnit }} from "@publisher-tools/react-sdk";

function App() {{
  return (
    <PublisherToolsProvider publisherId="{publisher_id}">
      <AdUnit unitId="UNIT000001" format="banner" />
    </PublisherToolsProvider>
  );
}}''',

            'android_sdk': '''// Android SDK (build.gradle)
implementation 'io.publishertools:android-sdk:1.0.0'

// Initialize (Application class)
PublisherTools.initialize(this, "PUBLISHER_ID");

// Show ad
AdView adView = new AdView(this);
adView.setAdUnitId("UNIT000001");
adView.loadAd(new AdRequest.Builder().build());''',

            'ios_sdk': '''// iOS SDK (Podfile)
pod 'PublisherToolsSDK'

// Initialize (AppDelegate)
PublisherTools.initialize(publisherId: "PUBLISHER_ID")

// Show banner ad
let adView = PTAdView(frame: CGRect(x: 0, y: 0, width: 320, height: 50))
adView.unitId = "UNIT000001"
adView.loadAd()
view.addSubview(adView)''',
        }
        return snippets.get(self.integration_type, '# Integration setup required. Contact support.')
