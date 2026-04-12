# api/offer_inventory/optimization_scale/bandwidth_monitor.py
"""Bandwidth Monitor — Track API response sizes and data transfer."""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

WINDOW = 3600   # 1-hour rolling window


class BandwidthMonitor:
    """Monitor API bandwidth usage per endpoint."""

    @staticmethod
    def record_response(endpoint: str, size_bytes: int):
        """Record an API response size."""
        key   = f'bw:{endpoint}'
        stats = cache.get(key) or {'total_bytes': 0, 'count': 0, 'max_bytes': 0}
        stats['total_bytes'] += size_bytes
        stats['count']       += 1
        stats['max_bytes']    = max(stats['max_bytes'], size_bytes)
        stats['avg_bytes']    = stats['total_bytes'] // max(stats['count'], 1)
        cache.set(key, stats, WINDOW)

    @staticmethod
    def get_stats(endpoint: str = None) -> dict:
        """Get bandwidth stats for an endpoint."""
        if endpoint:
            return cache.get(f'bw:{endpoint}') or {}
        total = cache.get('bw:_total') or {'total_bytes': 0}
        return {
            'total_bytes_hour': total.get('total_bytes', 0),
            'total_mb'        : round(total.get('total_bytes', 0) / 1024 / 1024, 2),
        }

    @staticmethod
    def is_large_response(size_bytes: int,
                           threshold_mb: float = 1.0) -> bool:
        """Flag responses larger than threshold."""
        return size_bytes > threshold_mb * 1024 * 1024

    @staticmethod
    def get_top_bandwidth_endpoints(limit: int = 10) -> list:
        """Endpoints consuming the most bandwidth (from cache keys)."""
        # This is a simplified implementation — full impl needs Redis SCAN
        known_endpoints = [
            'offer_list', 'conversion_report', 'user_earnings',
            'fraud_report', 'revenue_report', 'network_comparison',
        ]
        results = []
        for ep in known_endpoints:
            stats = cache.get(f'bw:{ep}')
            if stats:
                results.append({'endpoint': ep, **stats})
        return sorted(results, key=lambda x: x.get('total_bytes', 0), reverse=True)[:limit]
