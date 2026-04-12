"""IP Whitelist Intelligence — full CRUD and lookup wrapper."""
from ..models import IPWhitelist


class IPWhitelistIntelligence:
    @staticmethod
    def check(ip_address: str, tenant=None) -> bool:
        qs = IPWhitelist.objects.filter(ip_address=ip_address, is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.exists()

    @staticmethod
    def check_detail(ip_address: str, tenant=None) -> dict:
        qs = IPWhitelist.objects.filter(ip_address=ip_address, is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        entry = qs.first()
        return {
            'ip_address': ip_address,
            'is_whitelisted': entry is not None,
            'label': entry.label if entry else '',
            'description': entry.description if entry else '',
        }

    @staticmethod
    def add(ip_address: str, label: str, tenant=None,
            added_by=None, description: str = '') -> tuple:
        entry, created = IPWhitelist.objects.get_or_create(
            ip_address=ip_address, tenant=tenant,
            defaults={'label': label, 'description': description,
                      'is_active': True, 'added_by': added_by}
        )
        try:
            from ..cache import PICache
            PICache.invalidate_whitelist(ip_address)
        except Exception:
            pass
        return entry, created

    @staticmethod
    def remove(ip_address: str, tenant=None) -> int:
        qs = IPWhitelist.objects.filter(ip_address=ip_address)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.update(is_active=False)

    @staticmethod
    def get_all(tenant=None):
        qs = IPWhitelist.objects.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('label')
