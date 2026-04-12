"""
click_tracking/click_geo_tracker.py
─────────────────────────────────────
Geographic click tracking.
Enriches clicks with geo data and checks for geo anomalies
(e.g. click from BD but conversion from US = suspicious).
"""
from __future__ import annotations
import logging
from ..models import ClickLog, Conversion

logger = logging.getLogger(__name__)


class ClickGeoTracker:

    def enrich_with_geo(self, click_log: ClickLog) -> bool:
        """
        Enrich ClickLog with country/region/city/ISP data from IP.
        Uses ip-api.com free tier (no API key needed, max 45 req/min).
        Returns True if enrichment succeeded.
        """
        if not click_log.ip_address or click_log.country:
            return False  # Already has geo or no IP

        try:
            import requests
            resp = requests.get(
                f"http://ip-api.com/json/{click_log.ip_address}"
                "?fields=status,country,countryCode,region,city,isp",
                timeout=3,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    ClickLog.objects.filter(pk=click_log.pk).update(
                        country=data.get("countryCode", ""),
                        region=data.get("region", ""),
                        city=data.get("city", ""),
                        isp=data.get("isp", ""),
                    )
                    click_log.country = data.get("countryCode", "")
                    return True
        except Exception as exc:
            logger.debug("Geo enrichment failed (non-fatal): %s", exc)
        return False

    def check_geo_mismatch(
        self,
        click_log: ClickLog,
        conversion_ip: str,
    ) -> bool:
        """
        Check if click country differs from conversion country.
        Returns True if mismatch detected (suspicious).
        """
        if not click_log.country or not conversion_ip:
            return False
        # This requires a geo lookup on conversion_ip — expensive, do async
        # For now: return False (can be enhanced with async enrichment)
        return False

    def get_click_distribution_by_country(
        self, network=None, days: int = 7
    ) -> list:
        """Return click distribution by country."""
        from datetime import timedelta
        from django.utils import timezone
        from django.db.models import Count

        cutoff = timezone.now() - timedelta(days=days)
        qs = ClickLog.objects.filter(clicked_at__gte=cutoff).exclude(country="")
        if network:
            qs = qs.filter(network=network)
        rows = (
            qs.values("country")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        return [{"country": r["country"], "clicks": r["count"]} for r in rows]


click_geo_tracker = ClickGeoTracker()
