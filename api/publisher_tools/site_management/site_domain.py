# api/publisher_tools/site_management/site_domain.py
"""Site Domain — Domain management, WHOIS, SSL verification।"""
import re
from typing import Dict, Optional
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


DOMAIN_REGEX = re.compile(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$')


def clean_domain(raw: str) -> str:
    raw = raw.strip().lower()
    for prefix in ['https://', 'http://', 'www.']:
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
    return raw.rstrip('/')


def is_valid_domain(domain: str) -> bool:
    return bool(DOMAIN_REGEX.match(domain))


def get_root_domain(domain: str) -> str:
    parts = domain.split('.')
    return '.'.join(parts[-2:]) if len(parts) > 2 else domain


def check_domain_available(domain: str) -> bool:
    """Domain already registered কিনা check করে।"""
    from api.publisher_tools.models import Site
    return not Site.objects.filter(domain=domain).exists()


def get_domain_info(domain: str) -> Dict:
    """Domain basic info।"""
    return {
        'domain': domain,
        'root_domain': get_root_domain(domain),
        'tld': domain.split('.')[-1],
        'is_subdomain': len(domain.split('.')) > 2,
        'ads_txt_url': f"https://{domain}/ads.txt",
        'robots_txt_url': f"https://{domain}/robots.txt",
        'sitemap_url': f"https://{domain}/sitemap.xml",
    }


class SiteDomainVerificationToken(TimeStampedModel):
    """Domain verification token store।"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='publisher_tools_domaintoken_tenant', db_index=True)
    site        = models.ForeignKey('publisher_tools.Site', on_delete=models.CASCADE, related_name='domain_tokens')
    token       = models.CharField(max_length=64, unique=True)
    method      = models.CharField(max_length=20)
    is_used     = models.BooleanField(default=False)
    expires_at  = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'publisher_tools_domain_verification_tokens'
        verbose_name = _('Domain Verification Token')

    def __str__(self):
        return f"{self.site.domain} — {self.method} [{'verified' if self.is_used else 'pending'}]"
