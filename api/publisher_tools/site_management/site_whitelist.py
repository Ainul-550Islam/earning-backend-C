# api/publisher_tools/site_management/site_whitelist.py
"""Site Whitelist — Approved advertisers and content for sites."""
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class SiteWhitelistEntry(TimeStampedModel):
    """Site-level ad whitelist — only approved advertisers."""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_sitewl_tenant', db_index=True)
    site            = models.ForeignKey('publisher_tools.Site', on_delete=models.CASCADE, related_name='whitelist_entries', db_index=True)
    entry_type      = models.CharField(max_length=20, choices=[
        ('advertiser','Advertiser'),('domain','Ad Domain'),
        ('category','Preferred Category'),('network','Ad Network'),
    ], db_index=True)
    value           = models.CharField(max_length=500)
    priority        = models.IntegerField(default=0)
    is_preferred    = models.BooleanField(default=False, help_text=_("Show ads from this entity preferentially"))
    is_active       = models.BooleanField(default=True, db_index=True)
    reason          = models.TextField(blank=True)
    floor_price_override = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True, help_text=_("Custom floor price for whitelisted entity"))
    added_by        = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        db_table = 'publisher_tools_site_whitelist_entries'
        verbose_name = _('Site Whitelist Entry')
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['site', 'entry_type', 'is_active'], name='idx_site_entry_type_is_act_02a'),
        ]

    def __str__(self):
        return f"{self.site.domain} — Allow {self.entry_type}: {self.value[:50]}"
