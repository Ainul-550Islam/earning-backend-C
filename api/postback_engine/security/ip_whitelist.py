"""
security/ip_whitelist.py
─────────────────────────
IP whitelist management for network-level access control.
Supports both exact IPs and CIDR ranges.
Redis-cached for performance.
"""
from __future__ import annotations
import ipaddress
import json
import logging
from typing import List, Tuple
from django.core.cache import cache

logger = logging.getLogger(__name__)
_CACHE_KEY = "pe:wl:{network_id}"
_CACHE_TTL = 600  # 10 minutes


class IPWhitelistManager:

    def check(self, ip: str, network) -> bool:
        """
        Check if IP is in network's whitelist.
        Returns True if allowed (whitelist empty = allow all).
        """
        whitelist = self._get_whitelist(network)
        if not whitelist:
            return True
        if not ip:
            return False
        return self._is_in_list(ip, whitelist)

    def _get_whitelist(self, network) -> list:
        network_id = str(getattr(network, "id", ""))
        cache_key = _CACHE_KEY.format(network_id=network_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        whitelist = getattr(network, "ip_whitelist", []) or []
        cache.set(cache_key, whitelist, timeout=_CACHE_TTL)
        return whitelist

    def invalidate_cache(self, network) -> None:
        network_id = str(getattr(network, "id", ""))
        cache.delete(_CACHE_KEY.format(network_id=network_id))

    def _is_in_list(self, ip: str, whitelist: list) -> bool:
        try:
            ip_obj = ipaddress.ip_address(ip)
            for entry in whitelist:
                s = str(entry).strip()
                if "/" in s:
                    if ip_obj in ipaddress.ip_network(s, strict=False):
                        return True
                else:
                    if ip_obj == ipaddress.ip_address(s):
                        return True
        except ValueError as exc:
            logger.warning("IPWhitelistManager: IP parse error %s: %s", ip, exc)
        return False

    def validate_entries(self, entries: list) -> Tuple[bool, List[str]]:
        """Validate a list of IP/CIDR entries. Returns (is_valid, errors)."""
        errors = []
        for entry in entries:
            s = str(entry).strip()
            try:
                if "/" in s:
                    ipaddress.ip_network(s, strict=False)
                else:
                    ipaddress.ip_address(s)
            except ValueError:
                errors.append(f"Invalid IP/CIDR: {s!r}")
        return len(errors) == 0, errors


ip_whitelist_manager = IPWhitelistManager()
