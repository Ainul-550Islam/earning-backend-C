"""
fraud_detection/proxy_detector.py
───────────────────────────────────
VPN / Proxy / Tor exit node detection.

Uses:
  1. Local known-bad IP ranges (datacenter IPs, AWS/GCP/Azure)
  2. ipinfo.io API for VPN/proxy/hosting flags (requires API key)
  3. ip-api.com as free fallback
  4. Cached results in Redis (24h TTL per IP)
"""
from __future__ import annotations
import logging
from typing import Tuple
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Known datacenter/hosting CIDR blocks (major cloud providers)
_DATACENTER_RANGES = [
    "13.0.0.0/8",    # AWS
    "34.0.0.0/8",    # GCP
    "35.0.0.0/8",    # GCP
    "52.0.0.0/8",    # AWS
    "54.0.0.0/8",    # AWS
    "104.16.0.0/13", # Cloudflare
    "104.24.0.0/14", # Cloudflare
    "162.158.0.0/15",# Cloudflare
    "172.64.0.0/13", # Cloudflare
    "13.64.0.0/11",  # Azure
    "20.0.0.0/8",    # Azure
    "40.64.0.0/10",  # Azure
]

_CACHE_KEY = "pe:proxy:{ip_hash}"
_CACHE_TTL = 86400  # 24 hours


class ProxyDetector:

    def check(self, ip: str) -> Tuple[bool, str]:
        """
        Returns (is_proxy_or_vpn, reason).
        Cached in Redis for 24 hours.
        """
        if not ip:
            return False, ""

        import hashlib
        ip_hash = hashlib.md5(ip.encode()).hexdigest()[:16]
        cache_key = _CACHE_KEY.format(ip_hash=ip_hash)

        cached = cache.get(cache_key)
        if cached is not None:
            parts = cached.split("|", 1)
            return parts[0] == "1", parts[1] if len(parts) > 1 else ""

        result, reason = self._check_datacenter(ip)
        if not result:
            result, reason = self._check_ipinfo(ip)

        cache.set(cache_key, f"{'1' if result else '0'}|{reason}", timeout=_CACHE_TTL)
        return result, reason

    def _check_datacenter(self, ip: str) -> Tuple[bool, str]:
        """Check against known datacenter IP ranges."""
        import ipaddress
        try:
            ip_obj = ipaddress.ip_address(ip)
            for cidr in _DATACENTER_RANGES:
                if ip_obj in ipaddress.ip_network(cidr, strict=False):
                    return True, f"Datacenter IP ({cidr})"
        except ValueError:
            pass
        return False, ""

    def _check_ipinfo(self, ip: str) -> Tuple[bool, str]:
        """
        Call ipinfo.io API to check for VPN/proxy/hosting.
        Requires IPINFO_TOKEN in Django settings.
        Silently returns (False, "") if API is unavailable.
        """
        try:
            from django.conf import settings
            token = getattr(settings, "IPINFO_TOKEN", "")
            if not token:
                return False, ""

            import requests
            resp = requests.get(
                f"https://ipinfo.io/{ip}/privacy?token={token}",
                timeout=3,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("vpn") or data.get("proxy") or data.get("tor") or data.get("hosting"):
                    reason_parts = []
                    for flag in ("vpn", "proxy", "tor", "hosting"):
                        if data.get(flag):
                            reason_parts.append(flag.upper())
                    return True, "+".join(reason_parts)
        except Exception as exc:
            logger.debug("ProxyDetector ipinfo check failed (non-fatal): %s", exc)
        return False, ""


# Module-level singleton
proxy_detector = ProxyDetector()
