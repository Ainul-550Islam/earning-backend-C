# engagement/services/adapters/security_adapter.py
"""
SecurityAdapter
===============
Wraps api.security for engagement.

Used for:
    - Bot detection before spin/checkin reward
    - Device trust verification
    - Click-fraud check on CPA completion
    - Trusted device registration on login
"""

import logging
logger = logging.getLogger("engagement.adapters.security")


class SecurityAdapter:

    @staticmethod
    def check_bot(user, ip: str = None, user_agent: str = None,
                  fingerprint: str = None) -> dict:
        """
        Run bot detection before rewarding user.

        Returns:
            {"is_bot": bool, "confidence": float, "reason": str}
        """
        try:
            from api.security.services.BotDetectionML import BotDetectionML
            detector = BotDetectionML()
            result = detector.analyze(
                user_id=user.pk,
                ip_address=ip,
                user_agent=user_agent or "",
                fingerprint=fingerprint or "",
            )
            is_bot = getattr(result, "is_bot", False) or result.get("is_bot", False)
            confidence = getattr(result, "confidence", 0.0) or result.get("confidence", 0.0)
            reason = getattr(result, "reason", "") or result.get("reason", "")
            logger.debug(
                f"SecurityAdapter.check_bot user={user.pk} is_bot={is_bot} conf={confidence}"
            )
            return {"is_bot": bool(is_bot), "confidence": float(confidence),
                    "reason": reason, "source": "security_app"}
        except Exception as e:
            logger.debug(f"SecurityAdapter.check_bot unavailable: {e}")
            return {"is_bot": False, "confidence": 0.0, "reason": "", "source": "unavailable"}

    @staticmethod
    def is_trusted_device(user, device_fingerprint: str) -> bool:
        """Check if device is trusted for this user."""
        try:
            from api.security.services.TrustedDeviceService import TrustedDeviceService
            return TrustedDeviceService().is_trusted(user, device_fingerprint)
        except Exception:
            return True  # Fail open

    @staticmethod
    def register_device(user, device_fingerprint: str, ip: str = None) -> bool:
        """Register a trusted device after successful engagement action."""
        try:
            from api.security.services.TrustedDeviceService import TrustedDeviceService
            TrustedDeviceService().register(user, device_fingerprint, ip=ip)
            return True
        except Exception:
            return False

    @staticmethod
    def check_click_fraud(user, offer_id: str, ip: str = None,
                           click_id: str = None) -> dict:
        """
        Check CPA lead completion for click fraud.

        Returns:
            {"is_fraud": bool, "pattern": str, "action": str}
        """
        try:
            from api.security.services.ClickFraudEngine import ClickFraudEngine
            engine = ClickFraudEngine()
            result = engine.analyze(
                user_id=user.pk,
                offer_id=offer_id,
                ip_address=ip or "",
                click_id=click_id or "",
            )
            is_fraud = getattr(result, "is_fraud", False) or result.get("is_fraud", False)
            pattern = getattr(result, "pattern", "") or result.get("pattern", "")
            return {
                "is_fraud": bool(is_fraud),
                "pattern": str(pattern),
                "action": "block" if is_fraud else "allow",
                "source": "security_app",
            }
        except Exception as e:
            logger.debug(f"SecurityAdapter.check_click_fraud: {e}")
            return {"is_fraud": False, "pattern": "", "action": "allow", "source": "unavailable"}

    @staticmethod
    def get_security_insights(user) -> dict:
        """Get security summary for a user — used in admin panel."""
        try:
            from api.security.services.SecurityInsightService import SecurityInsightService
            return SecurityInsightService().get_user_insights(user)
        except Exception:
            return {}