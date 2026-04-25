# api/publisher_tools/site_management/site_blacklist.py
"""Site Blacklist — Domain and content blocking for sites."""
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class SiteBlacklistEntry(TimeStampedModel):
    """Site-level ad blacklist entries."""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_sitebl_tenant', db_index=True)
    site            = models.ForeignKey('publisher_tools.Site', on_delete=models.CASCADE, related_name='blacklist_entries', db_index=True)
    entry_type      = models.CharField(max_length=20, choices=[
        ('advertiser','Advertiser'),('domain','Ad Domain'),
        ('category','Content Category'),('keyword','Keyword'),('ip','IP Address'),
    ], db_index=True)
    value           = models.CharField(max_length=500)
    reason          = models.TextField(blank=True)
    is_active       = models.BooleanField(default=True, db_index=True)
    expires_at      = models.DateTimeField(null=True, blank=True)
    added_by        = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        db_table = 'publisher_tools_site_blacklist_entries'
        verbose_name = _('Site Blacklist Entry')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['site', 'entry_type', 'is_active'], name='idx_site_entry_type_is_act_7c8'),
        ]

    def __str__(self):
        return f"{self.site.domain} — Block {self.entry_type}: {self.value[:50]}"

    @property
    def is_effective(self):
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True
