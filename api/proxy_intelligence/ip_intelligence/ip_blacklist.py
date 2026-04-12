"""IP Blacklist Intelligence — full CRUD and lookup wrapper."""
from django.utils import timezone
from django.db.models import Count
from ..models import IPBlacklist


class IPBlacklistIntelligence:
    @staticmethod
    def check(ip_address: str, tenant=None) -> dict:
        qs = IPBlacklist.objects.filter(ip_address=ip_address, is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        entries = [e for e in qs if not e.is_expired()]
        return {
            'ip_address': ip_address,
            'is_blacklisted': len(entries) > 0,
            'entry_count': len(entries),
            'reasons': list({e.reason for e in entries}),
            'sources': list({e.source for e in entries}),
            'has_permanent': any(e.is_permanent for e in entries),
            'entries': [{'reason': e.reason, 'source': e.source,
                         'is_permanent': e.is_permanent,
                         'expires_at': str(e.expires_at)} for e in entries],
        }

    @staticmethod
    def add(ip_address: str, reason: str, tenant=None, is_permanent: bool = False,
            blocked_by=None, description: str = '', source: str = 'manual',
            expires_hours: int = None) -> IPBlacklist:
        from datetime import timedelta
        expires_at = None
        if not is_permanent and expires_hours:
            expires_at = timezone.now() + timedelta(hours=expires_hours)
        entry, _ = IPBlacklist.objects.update_or_create(
            ip_address=ip_address, tenant=tenant,
            defaults={'reason': reason, 'is_permanent': is_permanent,
                      'is_active': True, 'expires_at': expires_at,
                      'blocked_by': blocked_by, 'description': description,
                      'source': source}
        )
        try:
            from ..cache import PICache
            PICache.invalidate_all_for_ip(ip_address)
        except Exception:
            pass
        return entry

    @staticmethod
    def remove(ip_address: str, tenant=None) -> int:
        qs = IPBlacklist.objects.filter(ip_address=ip_address)
        if tenant:
            qs = qs.filter(tenant=tenant)
        count = qs.update(is_active=False)
        try:
            from ..cache import PICache
            PICache.invalidate_blacklist(ip_address)
        except Exception:
            pass
        return count

    @staticmethod
    def get_all_active(tenant=None, limit: int = 1000):
        qs = IPBlacklist.objects.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-created_at')[:limit]

    @staticmethod
    def bulk_add(ip_list: list, reason: str, tenant=None, source: str = 'bulk') -> int:
        created = 0
        for ip in ip_list:
            try:
                IPBlacklist.objects.update_or_create(
                    ip_address=ip, tenant=tenant,
                    defaults={'reason': reason, 'is_active': True, 'source': source}
                )
                created += 1
            except Exception:
                pass
        return created

    @staticmethod
    def stats(tenant=None) -> dict:
        qs = IPBlacklist.objects.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return {
            'total_active': qs.count(),
            'permanent': qs.filter(is_permanent=True).count(),
            'temporary': qs.filter(is_permanent=False).count(),
            'by_reason': list(qs.values('reason').annotate(n=Count('id')).order_by('-n')),
            'by_source': list(qs.values('source').annotate(n=Count('id')).order_by('-n')),
        }
