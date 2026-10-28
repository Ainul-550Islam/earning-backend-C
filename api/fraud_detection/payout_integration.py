"""
api/fraud_detection/payout_integration.py
==========================================
Fraud detection bridge for api.payout_queue.

HOW IT WORKS
------------
services._create_single_payout_item() calls get_payout_risk_score() for
every item when PAYOUT_FRAUD_CHECK_ENABLED=True.

If score > PAYOUT_FRAUD_RISK_THRESHOLD (default 0.75), the item is blocked
with a PayoutQueueError and the entire add_payout_items() call fails.

SCORE CONTRACT
--------------
get_payout_risk_score() must return a float between 0.0 and 1.0:
  0.0 = no risk (allow)
  1.0 = maximum risk (block)
  > PAYOUT_FRAUD_RISK_THRESHOLD (0.75) = blocked

SIGNALS CHECKED (examples — implement based on your fraud_detection app)
------------------------------------------------------------------------
  - Velocity: how many payouts has this user attempted in the last 24h?
  - Account change: did the account_number change from the last payout?
  - IP/device risk: is the user's last login from a flagged IP?
  - Amount anomaly: is this amount significantly higher than the user's avg?
  - Blacklist: is the account_number on a known fraud list?

DISABLE IN DEVELOPMENT
-----------------------
    PAYOUT_FRAUD_CHECK_ENABLED=False  (in .env / settings/local.py)
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


def get_payout_risk_score(
    user_id: Any,
    amount: Decimal,
    account_number: str,
) -> float:
    """
    Returns a fraud risk score between 0.0 (safe) and 1.0 (high risk).

    Called by: api.payout_queue.services._create_single_payout_item()

    Args:
        user_id:        PK of the user requesting the payout.
        amount:         Gross payout amount (Decimal, BDT).
        account_number: Recipient wallet/bank account number.

    Returns:
        float between 0.0 and 1.0.
        payout_queue blocks if score > PAYOUT_FRAUD_RISK_THRESHOLD.

    Implementation note:
        This function calls your existing fraud detection logic.
        Replace the stub body below with a real call to your
        RiskProfile or FraudEngine model/service.
    """
    if user_id is None:
        logger.warning("get_payout_risk_score: user_id is None — returning 1.0 (block)")
        return 1.0

    try:
        score = _calculate_risk(user_id=user_id, amount=amount, account_number=account_number)
        logger.debug(
            "get_payout_risk_score: user=%s amount=%s account=%s score=%.3f",
            user_id, amount, account_number, score,
        )
        return float(max(0.0, min(1.0, score)))  # clamp to [0.0, 1.0]
    except Exception as exc:
        logger.error(
            "get_payout_risk_score: error for user=%s: %s — returning 0.0 (allow).",
            user_id, exc,
        )
        # On error: fail-open (allow) to prevent blocking legitimate payouts.
        # Change to return 1.0 to fail-closed (stricter but safer).
        return 0.0


def _calculate_risk(user_id: Any, amount: Decimal, account_number: str) -> float:
    """
    Internal risk calculation. Replace with your real fraud detection logic.

    Example checks implemented below:
      1. Velocity: more than 5 payout attempts in 24h → high risk
      2. Blacklist: account on known bad list → block
      3. Amount anomaly: amount 10× user's historical average → elevated risk

    Integrate with your existing api.fraud_detection models:
        from api.fraud_detection.models import RiskProfile, BlacklistedAccount
        from api.fraud_detection.engines import VelocityEngine, AnomalyEngine
    """
    risk_score = 0.0

    # ── Check 1: Account blacklist ────────────────────────────────────────────
    try:
        from api.fraud_detection.models import BlacklistedAccount
        if BlacklistedAccount.objects.filter(
            account_number=account_number, is_active=True
        ).exists():
            logger.warning(
                "_calculate_risk: account %s is blacklisted — score=1.0",
                account_number,
            )
            return 1.0
    except ImportError:
        pass  # BlacklistedAccount model not present — skip check

    # ── Check 2: Payout velocity (last 24 hours) ──────────────────────────────
    try:
        from api.fraud_detection.models import FraudSignal
        from django.utils import timezone
        from datetime import timedelta
        recent_count = FraudSignal.objects.filter(
            user_id=user_id,
            signal_type="PAYOUT_ATTEMPT",
            created_at__gte=timezone.now() - timedelta(hours=24),
        ).count()
        if recent_count >= 10:
            risk_score = max(risk_score, 0.90)  # very high velocity
        elif recent_count >= 5:
            risk_score = max(risk_score, 0.60)  # elevated velocity
    except ImportError:
        pass  # FraudSignal model not present — skip check

    # ── Check 3: RiskProfile score (if your app builds user risk profiles) ────
    try:
        from api.fraud_detection.models import RiskProfile
        profile = RiskProfile.objects.filter(user_id=user_id).first()
        if profile is not None:
            profile_score = getattr(profile, "payout_risk_score", 0.0) or 0.0
            risk_score = max(risk_score, float(profile_score))
    except ImportError:
        pass  # RiskProfile model not present — skip check

    # ── Check 4: Amount anomaly ───────────────────────────────────────────────
    try:
        from api.payout_queue.models import PayoutItem
        from django.db.models import Avg
        avg = PayoutItem.objects.filter(
            user_id=user_id,
            status="SUCCESS",
        ).aggregate(avg=Avg("gross_amount"))["avg"]
        if avg and avg > 0 and amount > avg * 10:
            risk_score = max(risk_score, 0.70)  # 10× historical average
            logger.info(
                "_calculate_risk: amount %s is %.1f× user=%s historical avg %s",
                amount, float(amount / avg), user_id, avg,
            )
    except Exception:
        pass

    return risk_score


def record_payout_attempt(user_id: Any, amount: Decimal, account_number: str) -> None:
    """
    Record a payout attempt as a fraud signal for velocity tracking.

    Call this from services.add_payout_items() after successful item creation
    if you want to track payout velocity per user.

    Not called by payout_queue automatically — wire it up if needed.
    """
    try:
        from api.fraud_detection.models import FraudSignal
        FraudSignal.objects.create(
            user_id=user_id,
            signal_type="PAYOUT_ATTEMPT",
            metadata={
                "amount":         str(amount),
                "account_number": account_number,
            },
        )
    except Exception as exc:
        logger.warning("record_payout_attempt: failed to record signal: %s", exc)
