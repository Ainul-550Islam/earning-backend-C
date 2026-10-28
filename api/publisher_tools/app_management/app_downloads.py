# publisher_tools/app_management/app_downloads.py
"""
App Downloads — Download count tracking and analytics.

CHANGE LOG (v2):
  - Field `date` renamed to `snapshot_date` (db_column='date' — no DB column change, safe migration).
  - Added properties: `total_downloads` (alias for cumulative_downloads),
    `daily_active_users` (alias for active_installs).
  - All original logic preserved.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class AppDownloadSnapshot(TimeStampedModel):
    """Daily app download count snapshot."""

    PLATFORM_ANDROID = 'android'
    PLATFORM_IOS     = 'ios'

    PLATFORM_CHOICES = [
        (PLATFORM_ANDROID, 'Android'),
        (PLATFORM_IOS,     'iOS'),
    ]

    SOURCE_MANUAL     = 'manual'
    SOURCE_PLAY_STORE = 'play_store'
    SOURCE_APP_STORE  = 'app_store'
    SOURCE_API        = 'api'

    SOURCE_CHOICES = [
        (SOURCE_MANUAL,     'Manual'),
        (SOURCE_PLAY_STORE, 'Play Store API'),
        (SOURCE_APP_STORE,  'App Store API'),
        (SOURCE_API,        'External API'),
    ]

    # ── Fields ────────────────────────────────────────────────────────────────
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='publisher_tools_appdownload_tenant', db_index=True,
    )
    app = models.ForeignKey(
        'publisher_tools.App', on_delete=models.CASCADE,
        related_name='download_snapshots', db_index=True,
    )

    # NOTE: Python name changed from `date` → `snapshot_date`.
    #       db_column='date' keeps the actual DB column name unchanged.
    #       Migration 0008 uses SeparateDatabaseAndState → no ALTER TABLE.
    snapshot_date = models.DateField(
        db_column='date',
        db_index=True,
        verbose_name=_('Snapshot Date'),
    )

    new_downloads        = models.IntegerField(default=0,  verbose_name=_('New Downloads'))
    cumulative_downloads = models.BigIntegerField(default=0, verbose_name=_('Cumulative Downloads'))
    new_installs         = models.IntegerField(default=0,  verbose_name=_('New Installs'))
    uninstalls           = models.IntegerField(default=0,  verbose_name=_('Uninstalls'))
    net_installs         = models.IntegerField(default=0,  verbose_name=_('Net Installs'))
    active_installs      = models.BigIntegerField(default=0, verbose_name=_('Active Installs'))
    country_breakdown    = models.JSONField(default=list, blank=True)
    platform             = models.CharField(
        max_length=10, choices=PLATFORM_CHOICES, default=PLATFORM_ANDROID,
    )
    source = models.CharField(
        max_length=30, choices=SOURCE_CHOICES, default=SOURCE_MANUAL,
    )

    # ── Meta ──────────────────────────────────────────────────────────────────
    class Meta:
        app_label  = 'publisher_tools'
        db_table   = 'publisher_tools_app_download_snapshots'
        verbose_name        = _('App Download Snapshot')
        verbose_name_plural = _('App Download Snapshots')
        unique_together = [['app', 'snapshot_date', 'platform']]
        ordering        = ['-snapshot_date']
        indexes = [
            models.Index(fields=['app', 'snapshot_date'], name='idx_app_date_1538'),
        ]

    def __str__(self):
        return (
            f"{self.app.name} — {self.snapshot_date} "
            f"— {self.new_downloads:,} downloads"
        )

    # ── Properties (view-compatibility aliases) ───────────────────────────────

    @property
    def total_downloads(self) -> int:
        """Alias for cumulative_downloads — used by views_app_management_full.py."""
        return self.cumulative_downloads

    @property
    def daily_active_users(self) -> int:
        """Alias for active_installs — used by views_app_management_full.py."""
        return self.active_installs

    # ── Helpers ───────────────────────────────────────────────────────────────

    def compute_net_installs(self):
        """net_installs recalculate করে save করে।"""
        self.net_installs = self.new_installs - self.uninstalls
        self.save(update_fields=['net_installs', 'updated_at'])
        return self.net_installs

    @classmethod
    def latest_for_app(cls, app) -> 'AppDownloadSnapshot | None':
        """App-এর সর্বশেষ snapshot।"""
        return cls.objects.filter(app=app).order_by('-snapshot_date').first()

    @classmethod
    def range_for_app(cls, app, since, until=None):
        """Date range-এর snapshot queryset।"""
        qs = cls.objects.filter(app=app, snapshot_date__gte=since)
        if until:
            qs = qs.filter(snapshot_date__lte=until)
        return qs.order_by('snapshot_date')
