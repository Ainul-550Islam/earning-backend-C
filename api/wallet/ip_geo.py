# api/wallet/ip_geo.py
"""
IPGeoService — Auto-detect country from IP for GEO rate multipliers.

Uses ipapi.co (free tier: 1000 req/day) with Redis cache (24h TTL).
Falls back to ip-api.com if primary fails.
Circuit-breaker protected. No PII stored.
"""
import logging
from decimal import Decimal

from django.core.cache import cache

logger = logging.getLogger("wallet.ip_geo")

_CACHE_TTL = 86400   # 24 hours — IPs rarely change country


class IPGeoService:
    """Geo-locate an IP address to a country code (ISO 3166-1 alpha-2)."""

    @classmethod
    def get_country(cls, ip_address: str) -> str:
        """
        Return ISO country code for IP (e.g. "BD", "US", "GB").
        Returns "" on failure or private/local IPs.
        """
        if not ip_address or cls._is_private(ip_address):
            return ""

        cache_key = f"wallet_ip_geo:{ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        country = cls._lookup_primary(ip_address)
        if not country:
            country = cls._lookup_fallback(ip_address)

        cache.set(cache_key, country or "", timeout=_CACHE_TTL)
        return country or ""

    @classmethod
    def get_geo_multiplier(cls, ip_address: str) -> Decimal:
        """
        Convenience: return GEO rate multiplier for an IP.
        Looks up country then delegates to GeoRate model.
        """
        country = cls.get_country(ip_address)
        if not country:
            return Decimal("1.00")
        try:
            from .models_cpalead_extra import GeoRate
            geo = GeoRate.objects.filter(
                country_code=country, is_active=True
            ).first()
            return geo.rate_multiplier if geo else Decimal("1.00")
        except Exception:
            return Decimal("1.00")

    @staticmethod
    def _is_private(ip: str) -> bool:
        """True for loopback, private, and link-local IPs."""
        private_prefixes = (
            "127.", "10.", "192.168.", "::1",
            "fc00:", "fd", "fe80:",
        )
        return any(ip.startswith(p) for p in private_prefixes) or ip in ("localhost",)

    @staticmethod
    def _lookup_primary(ip: str) -> str:
        """ipapi.co — free 1000/day, returns JSON."""
        try:
            import requests
            resp = requests.get(
                f"https://ipapi.co/{ip}/country/",
                timeout=3,
                headers={"User-Agent": "WalletEngine/2.0"},
            )
            if resp.status_code == 200 and len(resp.text.strip()) == 2:
                return resp.text.strip().upper()
        except Exception as e:
            logger.debug(f"IPGeo primary failed for {ip}: {e}")
        return ""

    @staticmethod
    def _lookup_fallback(ip: str) -> str:
        """ip-api.com — free, no key needed, 45 req/min."""
        try:
            import requests
            resp = requests.get(
                f"http://ip-api.com/json/{ip}?fields=countryCode",
                timeout=3,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    return data.get("countryCode", "").upper()
        except Exception as e:
            logger.debug(f"IPGeo fallback failed for {ip}: {e}")
        return ""
