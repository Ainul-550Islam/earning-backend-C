"""IP Whitelist model helpers and managers."""
from django.db import models


class IPWhitelistManager(models.Manager):
    def active(self, tenant=None):
        qs = self.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def is_whitelisted(self, ip_address: str, tenant=None) -> bool:
        qs = self.active(tenant).filter(ip_address=ip_address)
        return qs.exists()

    def add_ip(self, ip_address: str, label: str, tenant=None,
               added_by=None, description: str = ''):
        from ..models import IPWhitelist
        entry, created = IPWhitelist.objects.get_or_create(
            ip_address=ip_address, tenant=tenant,
            defaults={
                'label':       label,
                'description': description,
                'is_active':   True,
                'added_by':    added_by,
            }
        )
        return entry, created

    def remove_ip(self, ip_address: str, tenant=None) -> int:
        qs = self.filter(ip_address=ip_address)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.update(is_active=False)

    def search(self, query: str, tenant=None):
        from django.db.models import Q
        return self.active(tenant).filter(
            Q(ip_address__icontains=query) |
            Q(label__icontains=query) |
            Q(description__icontains=query)
        )

    def stats(self, tenant=None) -> dict:
        from django.db.models import Count
        qs = self.active(tenant)
        return {
            'total_active': qs.count(),
            'added_by_user': qs.exclude(added_by=None).count(),
            'no_attribution': qs.filter(added_by=None).count(),
        }
