"""
click_tracking/click_ip_tracker.py
────────────────────────────────────
IP-based click tracking and analysis.
Tracks click patterns per IP for fraud detection and geo analysis.
"""
from __future__ import annotations
import logging
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Count
from ..models import ClickLog

logger = logging.getLogger(__name__)
_IP_CLICK_KEY = "pe:ip:clicks:{ip_hash}:{window}"


class ClickIPTracker:

    def record(self, ip: str) -> None:
        """Increment click counter for this IP."""
        if not ip:
            return
        import hashlib
        ip_hash = hashlib.md5(ip.encode()).hexdigest()[:16]
        for window, ttl in [("1m", 60), ("1h", 3600), ("24h", 86400)]:
            key = _IP_CLICK_KEY.format(ip_hash=ip_hash, window=window)
            try:
                try:
                    cache.incr(key)
                except ValueError:
                    cache.add(key, 1, timeout=ttl)
            except Exception:
                pass

    def get_click_count(self, ip: str, window: str = "1h") -> int:
        """Get click count for an IP in the given window (1m/1h/24h)."""
        import hashlib
        ip_hash = hashlib.md5(ip.encode()).hexdigest()[:16]
        key = _IP_CLICK_KEY.format(ip_hash=ip_hash, window=window)
        try:
            return int(cache.get(key) or 0)
        except Exception:
            return 0

    def get_ips_for_offer(self, offer_id: str, hours: int = 24) -> list:
        """Return unique IPs that clicked a specific offer in last N hours."""
        cutoff = timezone.now() - timedelta(hours=hours)
        return list(
            ClickLog.objects.filter(offer_id=offer_id, clicked_at__gte=cutoff)
            .exclude(ip_address=None)
            .values_list("ip_address", flat=True)
            .distinct()
        )


click_ip_tracker = ClickIPTracker()
