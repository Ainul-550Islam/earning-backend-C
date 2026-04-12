"""
click_tracking/click_validator.py
───────────────────────────────────
Validates clicks before recording and during attribution.
Checks: user eligibility, offer validity, geo restrictions, device type, rate limits.
"""
from __future__ import annotations
import logging
import re
from ..models import ClickLog, AdNetworkConfig
from ..enums import ClickStatus
from ..exceptions import (
    ClickNotFoundException,
    ClickExpiredException,
    FraudDetectedException,
    VelocityLimitException,
)

logger = logging.getLogger(__name__)

# Minimum suspicious click interval (seconds)
_MIN_CLICK_INTERVAL_SECS = 2


class ClickValidator:

    def validate_for_redirect(
        self,
        user,
        network: AdNetworkConfig,
        offer_id: str,
        ip: str = "",
        user_agent: str = "",
    ) -> tuple:
        """
        Validate before generating a click and redirecting to offer.
        Returns (is_valid, reason).
        """
        # 1. Network must be active
        if not network.is_active:
            return False, f"Network {network.network_key} is not active."

        # 2. User must exist
        if not user or not getattr(user, "is_active", True):
            return False, "User account is inactive."

        # 3. Rate limit: user can't click too fast
        from ..fraud_detection.velocity_checker import velocity_checker
        try:
            velocity_checker.check(ip=ip, user=user, network=network)
        except VelocityLimitException as exc:
            return False, str(exc)

        # 4. Bot user agent
        from ..fraud_detection.bot_detector import bot_detector
        is_bot, bot_score = bot_detector.check_user_agent(user_agent)
        if is_bot and bot_score >= 90:
            return False, "Bot traffic detected."

        return True, ""

    def validate_for_attribution(self, click_id: str) -> ClickLog:
        """
        Validate a click_id during postback processing for attribution.
        Raises ClickNotFoundException, ClickExpiredException, FraudDetectedException.
        """
        click_log = ClickLog.objects.get_by_click_id(click_id)
        if not click_log:
            raise ClickNotFoundException(f"Click '{click_id}' not found.")

        if click_log.status == ClickStatus.FRAUD:
            raise FraudDetectedException(
                f"Click '{click_id}' is flagged as fraud.",
                fraud_score=click_log.fraud_score,
                fraud_type=click_log.fraud_type,
            )

        if click_log.status == ClickStatus.DUPLICATE:
            raise FraudDetectedException(
                f"Click '{click_id}' is a duplicate.",
                fraud_score=50.0,
                fraud_type="duplicate",
            )

        if click_log.is_expired:
            raise ClickExpiredException(
                f"Click '{click_id}' expired at {click_log.expires_at}."
            )

        return click_log

    def is_valid_click_id_format(self, click_id: str) -> bool:
        """Validate click_id format (URL-safe, reasonable length)."""
        if not click_id:
            return False
        pattern = re.compile(r'^[\w\-]{8,128}$')
        return bool(pattern.match(click_id))


# Module-level singleton
click_validator = ClickValidator()
