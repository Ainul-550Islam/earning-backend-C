"""
api/users/profile/reputation_manager.py
User reputation score — বিভিন্ন activity থেকে score তৈরি হয়
"""
import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)


class ReputationManager:
    """
    Reputation score = trust score।
    Publisher/advertiser দেখতে পারবে।
    Score বাড়লে বেশি offer access পাবে।
    """

    # Score weights
    WEIGHTS = {
        'account_age_days':    0.15,
        'kyc_verified':        0.25,
        'email_verified':      0.10,
        'phone_verified':      0.10,
        'total_earned':        0.20,
        'completion_rate':     0.15,
        'fraud_flags':        -0.30,  # negative
        'days_active':         0.05,
    }

    MAX_SCORE = 100

    def calculate(self, user) -> int:
        """0-100 reputation score calculate করো"""
        score = 0.0

        # Account age (max 15 pts — 1 year = full)
        age_days = (timezone.now() - user.created_at).days if hasattr(user, 'created_at') else 0
        score   += min(age_days / 365, 1.0) * 15

        # KYC (25 pts)
        if self._is_kyc_verified(user):
            score += 25

        # Email verified (10 pts)
        if getattr(user, 'is_email_verified', False) or getattr(user, 'is_verified', False):
            score += 10

        # Phone verified (10 pts)
        if getattr(user, 'is_phone_verified', False):
            score += 10

        # Total earned (max 20 pts — $100 = full)
        earned = float(getattr(user, 'total_earned', 0) or 0)
        score += min(earned / 100, 1.0) * 20

        # Completion rate from api.fraud_detection
        cr     = self._get_completion_rate(user)
        score += cr * 15

        # Fraud flags (negative)
        fraud_count = self._get_fraud_flag_count(user)
        score      -= min(fraud_count * 10, 30)

        final = max(0, min(int(score), self.MAX_SCORE))
        return final

    def get_level(self, score: int) -> str:
        """Score → level label"""
        if score >= 80: return 'Excellent'
        if score >= 60: return 'Good'
        if score >= 40: return 'Fair'
        if score >= 20: return 'Low'
        return 'Very Low'

    def get_profile_summary(self, user) -> dict:
        score = self.calculate(user)
        return {
            'score':  score,
            'level':  self.get_level(score),
            'max':    self.MAX_SCORE,
            'pct':    round(score / self.MAX_SCORE * 100, 1),
        }

    # ─────────────────────────────────────
    # PRIVATE — অন্য app থেকে data নেওয়া
    # ─────────────────────────────────────
    def _is_kyc_verified(self, user) -> bool:
        try:
            from django.apps import apps
            KYC = apps.get_model('kyc', 'KYCVerification')
            return KYC.objects.filter(user=user, status='approved').exists()
        except Exception:
            return getattr(user, 'is_verified', False)

    def _get_completion_rate(self, user) -> float:
        """api.fraud_detection বা api.ad_networks থেকে"""
        try:
            from django.apps import apps
            Stats = apps.get_model('users', 'UserStatistics')
            stats = Stats.objects.get(user=user)
            if stats.total_clicks > 0:
                return min(stats.total_completions / stats.total_clicks, 1.0)
        except Exception:
            pass
        return 0.5  # default

    def _get_fraud_flag_count(self, user) -> int:
        """api.fraud_detection থেকে"""
        try:
            from django.apps import apps
            FraudLog = apps.get_model('fraud_detection', 'FraudDetectionLog')
            return FraudLog.objects.filter(user=user, resolved=False).count()
        except Exception:
            return 0


# Singleton
reputation_manager = ReputationManager()
