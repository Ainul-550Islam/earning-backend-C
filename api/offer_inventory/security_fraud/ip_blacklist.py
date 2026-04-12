# api/offer_inventory/security_fraud/ip_blacklist.py
"""
IP Blacklist Manager.
Supports exact IPs, CIDR ranges, auto-blocking with TTL,
and geo-based blocking.
"""
import ipaddress
import logging
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

CACHE_TTL_BLOCK  = 300    # 5 min cache per IP check
CACHE_TTL_LIST   = 60     # 1 min cache for full list


class IPBlacklistManager:
    """Full lifecycle IP blacklist management."""

    # ── Read ──────────────────────────────────────────────────────

    @staticmethod
    def is_blocked(ip: str, tenant=None) -> bool:
        """
        Check if IP is blocked.
        Cache → DB (exact) → DB (CIDR scan).
        """
        if not ip:
            return False

        cache_key = f'ip_bl:{ip}:{tenant}'
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached

        from api.offer_inventory.models import BlacklistedIP
        from django.db.models import Q

        now = timezone.now()
        qs  = BlacklistedIP.objects.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        )
        if tenant:
            qs = qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True))

        # Fast: exact match in DB
        if qs.filter(ip_address=ip).exists():
            cache.set(cache_key, True, CACHE_TTL_BLOCK)
            return True

        # CIDR ranges: load all and check
        blocked = IPBlacklistManager._check_cidr(ip, qs)
        cache.set(cache_key, blocked, CACHE_TTL_BLOCK)
        return blocked

    @staticmethod
    def _check_cidr(ip: str, qs) -> bool:
        """Check if IP falls within any blocked CIDR range."""
        try:
            ip_obj  = ipaddress.ip_address(ip)
            ranges  = qs.exclude(ip_range='').values_list('ip_range', flat=True)
            for cidr in ranges:
                try:
                    if ip_obj in ipaddress.ip_network(cidr.strip(), strict=False):
                        return True
                except ValueError:
                    continue
        except ValueError:
            pass
        return False

    # ── Write ─────────────────────────────────────────────────────

    @staticmethod
    def block(ip: str, reason: str, tenant=None,
              hours: int = 24, permanent: bool = False,
              source: str = 'auto', blocked_by=None) -> object:
        """Block an IP."""
        from api.offer_inventory.models import BlacklistedIP
        expires = None if permanent else timezone.now() + timedelta(hours=hours)

        obj, created = BlacklistedIP.objects.get_or_create(
            ip_address=ip,
            defaults={
                'reason'      : reason,
                'tenant'      : tenant,
                'is_permanent': permanent,
                'expires_at'  : expires,
                'source'      : source,
                'blocked_by'  : blocked_by,
            }
        )
        if not created and obj.expires_at and obj.expires_at < timezone.now():
            # Renew expired block
            obj.expires_at   = expires
            obj.is_permanent = permanent
            obj.reason       = reason
            obj.save(update_fields=['expires_at', 'is_permanent', 'reason'])

        cache.delete(f'ip_bl:{ip}:{tenant}')
        logger.info(f'IP blocked: {ip} | reason={reason} | permanent={permanent}')
        return obj

    @staticmethod
    def unblock(ip: str, tenant=None):
        """Remove IP from blacklist."""
        from api.offer_inventory.models import BlacklistedIP
        deleted, _ = BlacklistedIP.objects.filter(ip_address=ip).delete()
        cache.delete(f'ip_bl:{ip}:{tenant}')
        logger.info(f'IP unblocked: {ip} | records_deleted={deleted}')
        return deleted

    @staticmethod
    def bulk_block(ips: list, reason: str, tenant=None, hours: int = 24):
        """Block multiple IPs at once."""
        from api.offer_inventory.models import BlacklistedIP
        expires = timezone.now() + timedelta(hours=hours)
        objs    = [
            BlacklistedIP(
                ip_address=ip, reason=reason, tenant=tenant,
                expires_at=expires, source='bulk'
            )
            for ip in ips
        ]
        BlacklistedIP.objects.bulk_create(objs, ignore_conflicts=True)
        # Invalidate cache for each
        for ip in ips:
            cache.delete(f'ip_bl:{ip}:{tenant}')
        return len(ips)

    @staticmethod
    def cleanup_expired():
        """Remove expired blocks from DB."""
        from api.offer_inventory.models import BlacklistedIP
        deleted, _ = BlacklistedIP.objects.filter(
            is_permanent=False,
            expires_at__lt=timezone.now()
        ).delete()
        return deleted
