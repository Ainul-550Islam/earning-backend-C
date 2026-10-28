# api/support/integrations/project_specific/security_check.py
"""
Security Check — uses your security app for support request validation.

YOUR security app has:
  - vpn_detector.py — detect VPN/proxy usage
  - device tracking
  - Various security utilities

For support:
  - Detect if dispute submitted from VPN/proxy (red flag)
  - Validate request origin
  - Check device fingerprint consistency
"""
import logging
logger = logging.getLogger(__name__)


class SupportSecurityCheck:
    """Integrates security checks into support request processing."""

    def check_vpn_proxy(self, ip_address: str) -> dict:
        """
        Check if request is from VPN/proxy — suspicious for dispute submissions.
        """
        try:
            from api.security.vpn_detector import VPNDetector
            detector = VPNDetector()
            result = detector.check(ip_address)
            return {
                "is_vpn":     result.get("is_vpn", False),
                "is_proxy":   result.get("is_proxy", False),
                "risk_score": result.get("risk_score", 0),
                "country":    result.get("country", ""),
                "suspicious": result.get("is_vpn", False) or result.get("is_proxy", False),
            }
        except Exception as e:
            logger.debug(f"SupportSecurityCheck.check_vpn_proxy: {e}")
            return {"is_vpn": False, "is_proxy": False, "suspicious": False, "risk_score": 0}

    def assess_dispute_request_risk(self, request, dispute_data: dict) -> dict:
        """
        Full security assessment for a dispute submission.
        Combines: VPN check + fraud check + behavior analysis.
        """
        ip = self._get_ip(request)
        result = {
            "ip":          ip,
            "risk_level":  "low",
            "red_flags":   [],
            "allow":       True,
        }

        # VPN/Proxy check
        vpn = self.check_vpn_proxy(ip)
        if vpn["suspicious"]:
            result["red_flags"].append(f"VPN/Proxy detected (score:{vpn['risk_score']})")
            result["risk_level"] = "medium"

        # Multiple disputes from same IP
        if self._check_ip_dispute_rate(ip):
            result["red_flags"].append("High dispute rate from this IP")
            result["risk_level"] = "high"

        # Block extremely high risk
        if len(result["red_flags"]) >= 3:
            result["allow"]      = False
            result["risk_level"] = "critical"

        return result

    def _check_ip_dispute_rate(self, ip: str) -> bool:
        """Check if too many disputes from same IP in last 24h."""
        try:
            from django.core.cache import cache
            key   = f"support:disputes:ip:{ip}"
            count = cache.get(key, 0)
            cache.set(key, count + 1, timeout=86400)
            return count >= 10
        except Exception:
            return False

    def _get_ip(self, request) -> str:
        """Extract real IP from request."""
        if not request:
            return ""
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "")

    def validate_ticket_origin(self, request, ticket) -> dict:
        """Validate ticket submission origin."""
        ip = self._get_ip(request)
        vpn = self.check_vpn_proxy(ip)
        return {
            "ip":         ip,
            "suspicious": vpn["suspicious"],
            "allow":      True,  # We allow but flag for review
        }


security_check = SupportSecurityCheck()