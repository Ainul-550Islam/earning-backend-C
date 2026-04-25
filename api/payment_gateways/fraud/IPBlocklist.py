# api/payment_gateways/fraud/IPBlocklist.py
# FILE 79 of 257 — IP address blocklist management

import ipaddress
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

CACHE_KEY  = 'fraud:ip_blocklist'
CACHE_TTL  = 60 * 5   # 5 minutes


class IPBlocklist:
    """
    Check IP addresses against a DB-backed blocklist.
    Results are cached in Redis for 5 minutes for performance.
    """

    def check(self, ip_address: str) -> dict:
        if not ip_address:
            return {'blocked': False}

        # Normalize
        try:
            ip = str(ipaddress.ip_address(ip_address))
        except ValueError:
            return {'blocked': False}

        # Check cache first
        cache_key = f'fraud:ip:{ip}'
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached

        result = self._check_db(ip)
        cache.set(cache_key, result, CACHE_TTL)
        return result

    def _check_db(self, ip: str) -> dict:
        try:
            from .models import BlockedIP
            entry = BlockedIP.objects.filter(ip_address=ip, is_active=True).first()
            if entry:
                return {'blocked': True, 'reason': entry.reason, 'since': str(entry.created_at)}
            return {'blocked': False}
        except Exception as e:
            logger.warning(f'IPBlocklist DB check error: {e}')
            return {'blocked': False}

    def block(self, ip_address: str, reason: str, blocked_by=None):
        """Add an IP to the blocklist."""
        from .models import BlockedIP
        entry, created = BlockedIP.objects.get_or_create(
            ip_address=ip_address,
            defaults={'reason': reason, 'blocked_by': blocked_by, 'is_active': True},
        )
        if not created:
            entry.is_active = True
            entry.reason    = reason
            entry.save()
        cache.delete(f'fraud:ip:{ip_address}')
        logger.info(f'IP {ip_address} blocked: {reason}')
        return entry

    def unblock(self, ip_address: str):
        """Remove an IP from the blocklist."""
        from .models import BlockedIP
        BlockedIP.objects.filter(ip_address=ip_address).update(is_active=False)
        cache.delete(f'fraud:ip:{ip_address}')
        logger.info(f'IP {ip_address} unblocked')

    def auto_block_on_threshold(self, ip_address: str, threshold: int = 10):
        """Auto-block an IP that has triggered too many fraud alerts."""
        from .models import FraudAlert
        from django.utils import timezone
        from datetime import timedelta

        count = FraudAlert.objects.filter(
            ip_address=ip_address,
            action='block',
            created_at__gte=timezone.now() - timedelta(hours=24),
        ).count()

        if count >= threshold:
            self.block(
                ip_address,
                reason=f'Auto-blocked: {count} critical fraud alerts in 24h',
            )
            return True
        return False
