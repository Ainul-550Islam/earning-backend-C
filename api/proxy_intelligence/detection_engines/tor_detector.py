"""
Tor Exit Node Detector
======================
Detects Tor network usage by checking against the official Tor Project exit node list.
"""
import logging
import requests
from django.core.cache import cache
from django.utils import timezone
from ..constants import TOR_EXIT_NODE_LIST_URL

logger = logging.getLogger(__name__)

TOR_CACHE_KEY = "pi:tor_exit_nodes"
TOR_LIST_TTL = 3600 * 6  # Refresh every 6 hours


class TorDetector:
    """
    Detects if an IP address is a known Tor exit node.
    Uses the Tor Project's bulk exit node list.
    """

    @classmethod
    def _get_exit_nodes(cls) -> set:
        """Load exit nodes from cache or fetch from Tor Project."""
        nodes = cache.get(TOR_CACHE_KEY)
        if nodes is not None:
            return nodes

        try:
            resp = requests.get(TOR_EXIT_NODE_LIST_URL, timeout=10)
            resp.raise_for_status()
            nodes = set(line.strip() for line in resp.text.splitlines()
                        if line.strip() and not line.startswith('#'))
            cache.set(TOR_CACHE_KEY, nodes, TOR_LIST_TTL)
            return nodes
        except Exception as e:
            logger.error(f"Failed to fetch Tor exit node list: {e}")
            return cls._get_from_db()

    @classmethod
    def _get_from_db(cls) -> set:
        """Fallback: load from database."""
        from ..models import TorExitNode
        return set(TorExitNode.objects.filter(is_active=True).values_list('ip_address', flat=True))

    @classmethod
    def is_tor_exit(cls, ip_address: str) -> bool:
        """Check if a single IP is a Tor exit node."""
        cache_key = f"pi:tor_check:{ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        nodes = cls._get_exit_nodes()
        result = ip_address in nodes
        cache.set(cache_key, result, 1800)  # Cache individual result 30 min
        return result

    @classmethod
    def sync_exit_nodes(cls) -> int:
        """Sync Tor exit nodes from Tor Project into the database. Returns count."""
        from ..models import TorExitNode

        try:
            resp = requests.get(TOR_EXIT_NODE_LIST_URL, timeout=15)
            resp.raise_for_status()
            ips = [line.strip() for line in resp.text.splitlines()
                   if line.strip() and not line.startswith('#')]

            now = timezone.now()
            created_count = 0
            for ip in ips:
                _, created = TorExitNode.objects.update_or_create(
                    ip_address=ip,
                    defaults={'is_active': True, 'last_seen': now}
                )
                if created:
                    created_count += 1

            # Mark IPs not in current list as inactive
            TorExitNode.objects.exclude(ip_address__in=ips).update(is_active=False)

            # Invalidate cache
            cache.delete(TOR_CACHE_KEY)
            logger.info(f"Tor sync complete. {len(ips)} nodes, {created_count} new.")
            return len(ips)

        except Exception as e:
            logger.error(f"Tor sync failed: {e}")
            raise

    @classmethod
    def detect(cls, ip_address: str) -> dict:
        """Full detection result with metadata."""
        is_tor = cls.is_tor_exit(ip_address)
        return {
            'ip_address': ip_address,
            'is_tor': is_tor,
            'confidence': 0.98 if is_tor else 0.0,
            'detection_method': 'tor_project_list',
        }
