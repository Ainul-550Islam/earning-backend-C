# api/wallet/credit_score.py
"""
Credit Score — wallet-based credit assessment.
2026: Bangladesh Bank mandating credit bureau for all fintechs.

How it works:
  - Score calculated from wallet behavior (0-850 range)
  - Factors: earnings consistency, withdrawal patterns, account age,
             KYC level, referral performance, dispute history
  - Used for: BNPL eligibility, higher withdrawal limits, premium features

No external bureau needed — self-contained scoring.
Add external bureau (CIBIL-BD equivalent) when Bangladesh launches it.
"""
import logging
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger("wallet.credit_score")

# Score weights (must sum to 100)
SCORE_WEIGHTS = {
    "account_age":           10,   # Older = better
    "kyc_level":             20,   # Higher KYC = better
    "earnings_consistency":  25,   # Regular earnings = better
    "withdrawal_behavior":   15,   # Not withdrawing everything = better
    "total_earned":          15,   # Higher total = better
    "dispute_history":       10,   # No disputes = better
    "referral_performance":  5,    # Active referrals = better
}


class CreditScoreService:
    """Calculate and manage wallet-based credit scores."""

    @staticmethod
    def calculate(user_id: int) -> dict:
        """
        Calculate credit score for a user.
        Returns score 0-850 (similar to FICO scale).
        """
        from django.contrib.auth import get_user_model
        from .models.core import Wallet, WalletTransaction
        from django.db.models import Sum, Count, StdDev

        try:
            User   = get_user_model()
            user   = User.objects.get(id=user_id)
            wallet = Wallet.objects.filter(user=user).first()
            if not wallet:
                return {"score": 0, "grade": "N/A", "error": "No wallet found"}

            score     = 0
            breakdown = {}
            now       = timezone.now()

            # 1. Account age (0-10 points)
            age_days = max((now - wallet.created_at).days, 0)
            age_score = min(10, age_days / 36.5)  # max at 1 year
            score += age_score
            breakdown["account_age"] = round(age_score, 2)

            # 2. KYC level (0-20 points)
            try:
                from .models_cpalead_extra import KYCVerification
                kyc = KYCVerification.objects.filter(
                    user=user, status="approved"
                ).order_by("-level").first()
                kyc_level = kyc.level if kyc else 0
                kyc_score = kyc_level * 6.67  # Level 3 = 20 points
            except Exception:
                kyc_score = 0
            score += min(20, kyc_score)
            breakdown["kyc_level"] = round(min(20, kyc_score), 2)

            # 3. Earnings consistency (0-25 points) — how many of last 30 days earned
            last_30 = now - timedelta(days=30)
            earning_days = WalletTransaction.objects.filter(
                wallet=wallet,
                type__in=["earning","reward","cpa","cpi"],
                status__in=["approved","completed"],
                created_at__gte=last_30,
            ).dates("created_at", "day").count()
            consistency_score = min(25, earning_days * 0.83)
            score += consistency_score
            breakdown["earnings_consistency"] = round(consistency_score, 2)

            # 4. Withdrawal behavior (0-15 points) — save rate
            total_earned = float(wallet.total_earned or 0)
            total_withdrawn = float(wallet.total_withdrawn or 0)
            if total_earned > 0:
                save_rate = max(0, 1 - total_withdrawn / total_earned)
                withdraw_score = save_rate * 15
            else:
                withdraw_score = 0
            score += withdraw_score
            breakdown["withdrawal_behavior"] = round(withdraw_score, 2)

            # 5. Total earned (0-15 points)
            earn_score = min(15, total_earned / 666.67)  # 10,000 BDT = max points
            score += earn_score
            breakdown["total_earned"] = round(earn_score, 2)

            # 6. Dispute history (0-10 points) — no disputes = full points
            try:
                from .models_cpalead_extra import DisputeCase
                disputes = DisputeCase.objects.filter(user=user).count()
                dispute_score = max(0, 10 - disputes * 5)
            except Exception:
                dispute_score = 10
            score += dispute_score
            breakdown["dispute_history"] = round(dispute_score, 2)

            # 7. Referral performance (0-5 points)
            try:
                from .models_cpalead_extra import ReferralProgram
                refs = ReferralProgram.objects.filter(referrer=user, is_active=True).count()
                referral_score = min(5, refs * 0.5)
            except Exception:
                referral_score = 0
            score += referral_score
            breakdown["referral_performance"] = round(referral_score, 2)

            # Convert to 0-850 scale
            final_score = min(850, int(score * 8.5))

            grade = (
                "A+" if final_score >= 750 else
                "A"  if final_score >= 700 else
                "B"  if final_score >= 650 else
                "C"  if final_score >= 600 else
                "D"  if final_score >= 550 else
                "F"
            )

            bnpl_limit = (
                Decimal("50000") if final_score >= 750 else
                Decimal("20000") if final_score >= 700 else
                Decimal("10000") if final_score >= 650 else
                Decimal("5000")  if final_score >= 600 else
                Decimal("2000")
            )

            logger.info(f"Credit score: user={user_id} score={final_score} grade={grade}")
            return {
                "user_id":    user_id,
                "score":      final_score,
                "max_score":  850,
                "grade":      grade,
                "breakdown":  breakdown,
                "bnpl_limit": str(bnpl_limit),
                "calculated": timezone.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Credit score error user={user_id}: {e}")
            return {"score": 0, "grade": "N/A", "error": str(e)}

    @staticmethod
    def get_cached(user_id: int) -> dict:
        """Get cached credit score (recalculate daily)."""
        from django.core.cache import cache
        cached = cache.get(f"credit_score:{user_id}")
        if cached:
            return cached
        score = CreditScoreService.calculate(user_id)
        cache.set(f"credit_score:{user_id}", score, 86400)  # 24h cache
        return score

    @staticmethod
    def is_eligible_for_bnpl(user_id: int, amount: Decimal) -> dict:
        """Check BNPL eligibility based on credit score."""
        score = CreditScoreService.get_cached(user_id)
        limit = Decimal(score.get("bnpl_limit", "0"))
        return {
            "eligible": score.get("score", 0) >= 600 and limit >= amount,
            "score":    score.get("score", 0),
            "grade":    score.get("grade", "N/A"),
            "limit":    str(limit),
            "amount":   str(amount),
        }
