"""
fraud_detection/ip_blacklist_checker.py
─────────────────────────────────────────
IP blacklist / CIDR range checker with Redis cache.
"""
from __future__ import annotations
import ipaddress
import logging
from typing import Optional, Tuple
from django.core.cache import cache
from ..enums import BlacklistType, BlacklistReason
from ..constants import CACHE_TTL_BLACKLIST

logger = logging.getLogger(__name__)
_CACHE_KEY = "pe:bl:ip:{ip_hash}"


class IPBlacklistChecker:

    def is_blacklisted(self, ip: str) -> Tuple[bool, str]:
        """
        Check if an IP is blacklisted (exact match or CIDR).
        Returns (is_blacklisted, reason_or_empty).
        Uses Redis cache for fast lookups; falls back to DB.
        """
        if not ip:
            return False, ""

        import hashlib
        ip_hash = hashlib.md5(ip.encode()).hexdigest()[:16]
        cache_key = _CACHE_KEY.format(ip_hash=ip_hash)

        cached = cache.get(cache_key)
        if cached is not None:
            return cached == "1", ""

        result = self._db_check(ip)
        cache.set(cache_key, "1" if result else "0", timeout=CACHE_TTL_BLACKLIST)
        return result, ""

    def _db_check(self, ip: str) -> bool:
        from ..models import IPBlacklist
        if IPBlacklist.objects.active().ip_entries().filter(value=ip).exists():
            return True
        # CIDR check
        try:
            ip_obj = ipaddress.ip_address(ip)
            for entry in IPBlacklist.objects.active().cidr_entries():
                try:
                    if ip_obj in ipaddress.ip_network(entry.value, strict=False):
                        return True
                except ValueError:
                    continue
        except ValueError:
            pass
        return False

    def add(self, ip: str, reason: str = BlacklistReason.FRAUD, added_by=None, notes: str = "") -> None:
        from ..models import IPBlacklist
        IPBlacklist.objects.get_or_create(
            blacklist_type=BlacklistType.IP,
            value=ip,
            defaults={
                "reason": reason,
                "is_active": True,
                "added_by": added_by,
                "added_by_system": (added_by is None),
                "notes": notes,
            },
        )
        # Invalidate cache
        import hashlib
        ip_hash = hashlib.md5(ip.encode()).hexdigest()[:16]
        cache.delete(_CACHE_KEY.format(ip_hash=ip_hash))

    def increment_hit(self, ip: str) -> None:
        from ..models import IPBlacklist
        IPBlacklist.objects.active().filter(
            blacklist_type=BlacklistType.IP, value=ip
        ).first()


ip_blacklist_checker = IPBlacklistChecker()
