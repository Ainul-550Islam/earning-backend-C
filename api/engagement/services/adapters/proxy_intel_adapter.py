"""
ProxyIntelAdapter
=================
Wraps api.proxy_intelligence for engagement.

Called before:
    - Crediting referral registration (VPN/proxy = fraud signal)
    - Spin / checkin reward (Tor/datacenter IP = suspicious)
    - First task completion

Risk levels from proxy intelligence:
    clean      → proceed
    suspicious → flag in anti-cheat
    proxy/vpn  → reduce reward or block
    tor        → block reward
    datacenter → flag
"""

import logging
logger = logging.getLogger("engagement.adapters.proxy_intel")

# IP types that block rewards
BLOCK_IP_TYPES = {"tor", "malicious", "blacklisted"}
# IP types that flag but allow
FLAG_IP_TYPES = {"proxy", "vpn", "datacenter", "hosting"}


class ProxyIntelAdapter:

    @staticmethod
    def check_ip(ip: str) -> dict:
        """
        Check IP reputation before rewarding.

        Returns:
            {
                "ip": str,
                "is_proxy": bool,
                "is_vpn": bool,
                "is_tor": bool,
                "is_datacenter": bool,
                "country_code": str,
                "risk_score": int,          # 0-100
                "ip_type": str,             # "clean" | "proxy" | "vpn" | "tor" | etc.
                "should_block": bool,
                "should_flag": bool,
                "source": str,
            }
        """
        if not ip:
            return ProxyIntelAdapter._clean_result(ip or "")

        try:
            from api.proxy_intelligence.services import ProxyIntelligenceService
            svc = ProxyIntelligenceService()
            result = svc.check_ip(ip)

            # Normalise result dict or object
            if hasattr(result, "__dict__"):
                result = result.__dict__

            ip_type = result.get("ip_type", "clean") or "clean"
            risk_score = int(result.get("risk_score", 0) or 0)

            return {
                "ip": ip,
                "is_proxy":      result.get("is_proxy", False),
                "is_vpn":        result.get("is_vpn", False),
                "is_tor":        result.get("is_tor", False),
                "is_datacenter": result.get("is_datacenter", False),
                "country_code":  result.get("country_code", ""),
                "risk_score":    risk_score,
                "ip_type":       ip_type,
                "should_block":  ip_type in BLOCK_IP_TYPES or risk_score >= 90,
                "should_flag":   ip_type in FLAG_IP_TYPES or risk_score >= 60,
                "source":        "proxy_intel_app",
            }
        except Exception as e:
            logger.debug(f"ProxyIntelAdapter.check_ip {ip}: {e}")
            return ProxyIntelAdapter._clean_result(ip)

    @staticmethod
    def _clean_result(ip: str) -> dict:
        return {
            "ip": ip, "is_proxy": False, "is_vpn": False,
            "is_tor": False, "is_datacenter": False,
            "country_code": "", "risk_score": 0, "ip_type": "clean",
            "should_block": False, "should_flag": False, "source": "unavailable",
        }

    @staticmethod
    def check_before_reward(ip: str, action: str = "reward") -> dict:
        """
        Quick gate-check: should we block this reward based on IP?
        Returns {"allow": bool, "reason": str, "country_code": str}
        """
        result = ProxyIntelAdapter.check_ip(ip)
        if result["should_block"]:
            return {"allow": False, "reason": result["ip_type"],
                    "country_code": result["country_code"]}
        return {"allow": True, "reason": "ok", "country_code": result["country_code"]}

    @staticmethod
    def get_country(ip: str) -> str:
        """Fast country lookup for GEO multipliers."""
        result = ProxyIntelAdapter.check_ip(ip)
        return result.get("country_code", "")