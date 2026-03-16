# api/promotions/security_vault/ip_whitelist.py
ip_whitelist.py
# IP Whitelist — শুধু নির্দিষ্ট IP থেকে sensitive API access
# =============================================================================

import ipaddress
import logging
from typing import Union

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

logger = logging.getLogger('security_vault.ip_whitelist')

CACHE_KEY_WHITELIST = 'security:ip_whitelist'
CACHE_TTL_WHITELIST = 300  # 5 minutes


class IPWhitelistManager:
    """
    IP Whitelist management।
    settings.py অথবা DB থেকে whitelist নিতে পারে।

    settings.py তে:
        ADMIN_IP_WHITELIST = ['192.168.1.0/24', '10.0.0.1', '203.0.113.5']
    """

    def __init__(self, whitelist: list = None):
        self._static_whitelist = whitelist or getattr(settings, 'ADMIN_IP_WHITELIST', [])

    def is_allowed(self, ip: str) -> bool:
        """IP address allowed কিনা check করে।"""
        if not ip:
            return False

        # Whitelist empty হলে সব allow করো (optional — আপনার policy অনুযায়ী)
        if not self._static_whitelist:
            return True

        try:
            client_ip = ipaddress.ip_address(ip.strip())
        except ValueError:
            logger.warning(f'Invalid IP address format: {ip}')
            return False

        for entry in self._get_effective_whitelist():
            try:
                if '/' in entry:
                    # CIDR range check
                    if client_ip in ipaddress.ip_network(entry, strict=False):
                        return True
                else:
                    # Exact IP check
                    if client_ip == ipaddress.ip_address(entry):
                        return True
            except ValueError:
                logger.warning(f'Invalid whitelist entry: {entry}')
                continue

        logger.warning(f'IP not in whitelist: {ip}')
        return False

    def _get_effective_whitelist(self) -> list:
        """Static list + DB/cache whitelist combine করে।"""
        cached = cache.get(CACHE_KEY_WHITELIST)
        if cached:
            return self._static_whitelist + cached

        # DB থেকে dynamic whitelist (optional)
        db_whitelist = self._load_from_db()
        if db_whitelist:
            cache.set(CACHE_KEY_WHITELIST, db_whitelist, timeout=CACHE_TTL_WHITELIST)

        return self._static_whitelist + (db_whitelist or [])

    @staticmethod
    def _load_from_db() -> list:
        """DB থেকে whitelist load করে (optional)।"""
        try:
            # আপনার IPWhitelist model থাকলে এখানে load করুন
            # from .models import IPWhitelistEntry
            # return list(IPWhitelistEntry.objects.filter(is_active=True).values_list('ip_cidr', flat=True))
            return []
        except Exception:
            return []

    def add_to_whitelist(self, ip_or_cidr: str) -> bool:
        """Runtime এ IP add করে।"""
        try:
            if '/' in ip_or_cidr:
                ipaddress.ip_network(ip_or_cidr, strict=False)
            else:
                ipaddress.ip_address(ip_or_cidr)
            self._static_whitelist.append(ip_or_cidr)
            cache.delete(CACHE_KEY_WHITELIST)
            return True
        except ValueError:
            return False

    def remove_from_whitelist(self, ip_or_cidr: str) -> bool:
        """Whitelist থেকে IP remove করে।"""
        if ip_or_cidr in self._static_whitelist:
            self._static_whitelist.remove(ip_or_cidr)
            cache.delete(CACHE_KEY_WHITELIST)
            return True
        return False


class IPWhitelistPermission(BasePermission):
    """
    DRF Permission — শুধু whitelisted IP থেকে access দেয়।

    Usage:
        class AdminOnlyView(APIView):
            permission_classes = [IsAdminUser, IPWhitelistPermission]
    """
    message = 'Access denied from this IP address.'

    _manager = IPWhitelistManager()

    def has_permission(self, request, view) -> bool:
        ip = self._get_ip(request)
        if not self._manager.is_allowed(ip):
            logger.warning(
                f'IP whitelist blocked: ip={ip}, user={getattr(request.user, "pk", "anon")}, '
                f'path={request.path}'
            )
            raise PermissionDenied(self.message)
        return True

    @staticmethod
    def _get_ip(request) -> str:
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
