# fraud_detection/detectors/VPNProxyDetector.py
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.core.cache import cache

logger = logging.getLogger(__name__)

class VPNProxyDetector:
    """
    VPN / Proxy / Tor exit-node detector.
    Uses cached IP data + ASN heuristics + known datacenter ranges.
    """

    # Common datacenter/hosting ASN prefixes that indicate VPN/proxy
    _DC_PREFIXES = [
        "104.16", "104.17", "104.18", "104.19",  # Cloudflare
        "185.", "194.", "195.",                    # Common European DC ranges
        "45.33", "45.79", "45.56",                 # Linode
        "167.88", "167.89",                        # Digital Ocean
        "34.", "35.", "52.", "54.",                 # AWS/GCP
    ]

    _KNOWN_TOR_EXIT_CACHE_KEY = "vpn:tor_exits"

    def __init__(self):
        self._cfg = {
            "fraud_score_threshold":   70,
            "vpn_risk_addition":       60,
            "proxy_risk_addition":     55,
            "tor_risk_addition":       80,
            "datacenter_risk_addition": 40,
            "cache_ttl":               3600,
        }

    def detect(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.check_vpn_proxy(data.get("ip_address", ""))

    def check_vpn_proxy(self, ip: str) -> Dict[str, Any]:
        if not ip:
            return {"error": "ip_address required", "risk_score": 0}

        cache_key = f"vpn:check:{ip}"
        cached    = cache.get(cache_key)
        if cached:
            return {**cached, "cached": True}

        risk = 0; is_vpn = False; is_proxy = False; is_tor = False
        threat_types = []; reasons = []

        # 1. Datacenter prefix heuristic
        if any(ip.startswith(p) for p in self._DC_PREFIXES):
            risk += self._cfg["datacenter_risk_addition"]
            threat_types.append("datacenter"); reasons.append("datacenter_ip")

        # 2. Known Tor exits (loaded from DB / cache)
        try:
            from api.fraud_detection.models import IPReputation
            rec = IPReputation.objects.filter(ip_address=ip).first()
            if rec:
                if rec.is_tor:   is_tor   = True; risk += self._cfg["tor_risk_addition"];   threat_types.append("tor")
                if rec.is_vpn:   is_vpn   = True; risk += self._cfg["vpn_risk_addition"];   threat_types.append("vpn")
                if rec.is_proxy: is_proxy = True; risk += self._cfg["proxy_risk_addition"]; threat_types.append("proxy")
                risk = max(risk, rec.fraud_score)
        except Exception as exc:
            logger.debug("VPNProxyDetector DB lookup failed: %s", exc)

        # 3. IPv6 rapid rotation check
        if ":" in ip and ip.count(":") > 4:
            risk += 20; reasons.append("ipv6_possible_rotation")

        risk = min(risk, 100)
        result = {
            "ip_address":    ip,
            "risk_score":    risk,
            "is_vpn":        is_vpn,
            "is_proxy":      is_proxy,
            "is_tor":        is_tor,
            "is_blacklisted": risk >= 80,
            "threat_types":  list(set(threat_types)),
            "reasons":       reasons,
            "blacklist_reason": ", ".join(threat_types) if threat_types else "",
        }
        cache.set(cache_key, result, timeout=self._cfg["cache_ttl"])
        return result

    def batch_detect(self, ip_list: List[Dict]) -> List[Dict]:
        return [self.check_vpn_proxy(
            item.get("ip_address", "") if isinstance(item, dict) else str(item)
        ) for item in ip_list]
