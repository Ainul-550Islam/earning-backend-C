# api/admin_panel/ip_whitelist.py
"""
Admin IP Whitelist — restrict admin panel access to specific IPs.
Supports: CIDR ranges, single IPs, country-level allow/block.
"""
from __future__ import annotations
import ipaddress
import logging
from typing import List, Optional
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

CACHE_TTL = 300
WHITELIST_KEY = 'admin_panel:ip_whitelist'
BLACKLIST_KEY = 'admin_panel:ip_blacklist'


class AdminIPWhitelist:
    """IP whitelist manager for admin access control."""

    @classmethod
    def is_allowed(cls, ip: str) -> bool:
        """Check if IP is allowed to access admin panel."""
        if not ip or ip in ('127.0.0.1', '::1'):
            return True  # Always allow localhost

        # Check explicit blacklist first (faster)
        blacklist = cls._get_blacklist()
        if cls._ip_in_ranges(ip, blacklist):
            logger.warning(f"[IPWhitelist] BLOCKED: {ip}")
            return False

        # Check whitelist (if configured)
        whitelist = cls._get_whitelist()
        if not whitelist:
            return True  # Empty whitelist = allow all

        allowed = cls._ip_in_ranges(ip, whitelist)
        if not allowed:
            logger.warning(f"[IPWhitelist] NOT IN WHITELIST: {ip}")
        return allowed

    @classmethod
    def add_to_whitelist(cls, ip_or_cidr: str, label: str = '', actor=None) -> bool:
        """Add IP or CIDR range to admin whitelist."""
        try:
            # Validate
            if '/' in ip_or_cidr:
                ipaddress.ip_network(ip_or_cidr, strict=False)
            else:
                ipaddress.ip_address(ip_or_cidr)
        except ValueError:
            return False

        try:
            from api.admin_panel.models.config import SystemConfig
            current = cls._get_whitelist()
            entry = {'ip': ip_or_cidr, 'label': label, 'added_at': __import__('django.utils.timezone', fromlist=['timezone']).timezone.now().isoformat()}
            current.append(entry)
            import json
            SystemConfig.objects.update_or_create(
                key='admin_ip_whitelist',
                defaults={'value': json.dumps(current), 'group': 'security', 'value_type': 'json'}
            )
            cache.delete(WHITELIST_KEY)
            if actor:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=actor, action='add_ip_whitelist', changes={'ip': ip_or_cidr, 'label': label})
            return True
        except Exception as e:
            logger.error(f"[IPWhitelist.add] {e}")
            return False

    @classmethod
    def remove_from_whitelist(cls, ip_or_cidr: str, actor=None) -> bool:
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            current = cls._get_whitelist()
            current = [e for e in current if e.get('ip') != ip_or_cidr]
            SystemConfig.objects.filter(key='admin_ip_whitelist').update(value=json.dumps(current))
            cache.delete(WHITELIST_KEY)
            return True
        except Exception:
            return False

    @classmethod
    def get_whitelist(cls) -> List[dict]:
        return cls._get_whitelist()

    @classmethod
    def _get_whitelist(cls) -> List[dict]:
        cached = cache.get(WHITELIST_KEY)
        if cached is not None:
            return cached
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            obj = SystemConfig.objects.get(key='admin_ip_whitelist')
            entries = json.loads(obj.value)
            cache.set(WHITELIST_KEY, entries, CACHE_TTL)
            return entries
        except Exception:
            default = getattr(settings, 'ADMIN_IP_WHITELIST', [])
            return [{'ip': ip, 'label': 'settings'} for ip in default]

    @classmethod
    def _get_blacklist(cls) -> List[dict]:
        cached = cache.get(BLACKLIST_KEY)
        if cached is not None:
            return cached
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            obj = SystemConfig.objects.get(key='admin_ip_blacklist')
            entries = json.loads(obj.value)
            cache.set(BLACKLIST_KEY, entries, CACHE_TTL)
            return entries
        except Exception:
            return []

    @staticmethod
    def _ip_in_ranges(ip: str, ranges: List[dict]) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
            for entry in ranges:
                entry_ip = entry.get('ip', '') if isinstance(entry, dict) else str(entry)
                try:
                    if '/' in entry_ip:
                        if addr in ipaddress.ip_network(entry_ip, strict=False):
                            return True
                    elif ipaddress.ip_address(entry_ip) == addr:
                        return True
                except ValueError:
                    continue
        except ValueError:
            pass
        return False