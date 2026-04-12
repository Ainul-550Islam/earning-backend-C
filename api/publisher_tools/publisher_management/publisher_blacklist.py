# api/publisher_tools/publisher_management/publisher_blacklist.py
"""Publisher Blacklist — Advertiser, content, domain, keyword blacklists।"""
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class PublisherBlacklistEntry(TimeStampedModel):
    """Publisher-এর blacklist/whitelist entries।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_blacklist_tenant', db_index=True)

    LIST_TYPE_CHOICES = [
        ('advertiser_block',  _('Advertiser Block')),
        ('advertiser_allow',  _('Advertiser Allowlist')),
        ('category_block',    _('Content Category Block')),
        ('keyword_block',     _('Keyword Block')),
        ('domain_block',      _('Ad Domain Block')),
        ('competitor_block',  _('Competitor Brand Block')),
        ('geo_block',         _('Geographic Block')),
        ('ip_block',          _('IP Address Block')),
    ]

    publisher   = models.ForeignKey('publisher_tools.Publisher', on_delete=models.CASCADE, related_name='blacklist_entries', db_index=True)
    list_type   = models.CharField(max_length=30, choices=LIST_TYPE_CHOICES, db_index=True)
    value       = models.CharField(max_length=500, verbose_name=_("Blocked / Allowed Value"))
    reason      = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True, db_index=True)
    expires_at  = models.DateTimeField(null=True, blank=True)
    created_by  = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    metadata    = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'publisher_tools_publisher_blacklists'
        verbose_name = _('Blacklist Entry')
        verbose_name_plural = _('Blacklist Entries')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publisher', 'list_type', 'is_active']),
            models.Index(fields=['value']),
        ]

    def __str__(self):
        return f"{self.publisher.publisher_id} — {self.list_type}: {self.value[:50]}"

    @property
    def is_expired(self):
        return bool(self.expires_at and timezone.now() > self.expires_at)

    @property
    def is_effective(self):
        return self.is_active and not self.is_expired


class GlobalBlacklist(TimeStampedModel):
    """Platform-wide global blacklist। সব publishers-এর জন্য apply হয়।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_globalbl_tenant', db_index=True)

    ENTRY_TYPE_CHOICES = [
        ('domain',    _('Ad Domain')),
        ('advertiser',_('Advertiser ID')),
        ('category',  _('Content Category')),
        ('keyword',   _('Keyword')),
        ('ip_range',  _('IP Range / CIDR')),
    ]

    entry_type  = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES, db_index=True)
    value       = models.CharField(max_length=500)
    reason      = models.CharField(max_length=500)
    severity    = models.CharField(max_length=10, choices=[('low','Low'),('medium','Medium'),('high','High'),('critical','Critical')], default='medium')
    is_active   = models.BooleanField(default=True, db_index=True)
    added_by    = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    expires_at  = models.DateTimeField(null=True, blank=True)
    source      = models.CharField(max_length=100, blank=True, help_text=_("Where this came from (IAS, DoubleVerify, manual, etc.)"))

    class Meta:
        db_table = 'publisher_tools_global_blacklists'
        verbose_name = _('Global Blacklist Entry')
        verbose_name_plural = _('Global Blacklist Entries')
        unique_together = [['entry_type', 'value']]
        ordering = ['-created_at']

    def __str__(self):
        return f"Global {self.entry_type}: {self.value[:60]} [{self.severity}]"
