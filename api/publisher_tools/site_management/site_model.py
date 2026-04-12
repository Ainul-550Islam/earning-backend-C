# api/publisher_tools/site_management/site_model.py
"""Site Model extensions — additional site-related models."""
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class SiteContentPolicy(TimeStampedModel):
    """Site content policy compliance tracking।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_sitecontentpolicy_tenant', db_index=True)
    site = models.OneToOneField('publisher_tools.Site', on_delete=models.CASCADE, related_name='content_policy')
    has_privacy_policy       = models.BooleanField(default=False)
    has_terms_of_service     = models.BooleanField(default=False)
    has_cookie_consent       = models.BooleanField(default=False)
    has_gdpr_compliance      = models.BooleanField(default=False)
    has_ccpa_compliance      = models.BooleanField(default=False)
    privacy_policy_url       = models.URLField(blank=True)
    terms_url                = models.URLField(blank=True)
    cookie_policy_url        = models.URLField(blank=True)
    content_prohibits_adult  = models.BooleanField(default=True)
    content_prohibits_gambling= models.BooleanField(default=True)
    content_prohibits_hate   = models.BooleanField(default=True)
    content_prohibits_violence= models.BooleanField(default=True)
    last_policy_review       = models.DateField(null=True, blank=True)
    policy_score             = models.IntegerField(default=0)

    class Meta:
        db_table = 'publisher_tools_site_content_policies'
        verbose_name = _('Site Content Policy')

    def __str__(self):
        return f"Policy: {self.site.domain}"

    def calculate_score(self):
        checks = [self.has_privacy_policy, self.has_terms_of_service, self.has_cookie_consent,
                  self.has_gdpr_compliance, self.content_prohibits_adult]
        self.policy_score = sum(20 for c in checks if c)
        self.save(update_fields=['policy_score', 'updated_at'])
        return self.policy_score


class SiteTechnology(TimeStampedModel):
    """Site technology stack detection।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_sitetech_tenant', db_index=True)
    site = models.OneToOneField('publisher_tools.Site', on_delete=models.CASCADE, related_name='technology')
    cms              = models.CharField(max_length=50, blank=True, help_text='WordPress, Drupal, etc.')
    server_type      = models.CharField(max_length=50, blank=True, help_text='nginx, Apache, etc.')
    cdn_provider     = models.CharField(max_length=50, blank=True, help_text='Cloudflare, AWS, etc.')
    analytics_tools  = models.JSONField(default=list, blank=True)
    ad_networks_used = models.JSONField(default=list, blank=True)
    has_https        = models.BooleanField(default=True)
    has_amp          = models.BooleanField(default=False)
    has_pwa          = models.BooleanField(default=False)
    page_load_speed  = models.CharField(max_length=10, choices=[('fast','Fast'),('medium','Medium'),('slow','Slow')], default='medium')
    detected_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'publisher_tools_site_technologies'
        verbose_name = _('Site Technology')

    def __str__(self):
        return f"Tech: {self.site.domain} — {self.cms or 'Unknown CMS'}"
