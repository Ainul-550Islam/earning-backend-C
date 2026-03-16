# api/promotions/governance/trust_score.py
# Trust Score Engine — Multi-factor user trust calculation
import logging
from decimal import Decimal
from django.core.cache import cache
logger = logging.getLogger('governance.trust')
CACHE_KEY = 'gov:trust:{}'

class TrustScoreEngine:
    """
    0-100 trust score calculation.
    Factors: submission quality, account age, fraud history, verification.
    """
    WEIGHTS = {
        'approval_rate':      0.35,
        'account_age_days':   0.15,
        'verification_level': 0.20,
        'fraud_score':        0.20,    # Inverted — lower fraud = higher trust
        'dispute_rate':       0.10,
    }
    MAX_AGE_DAYS = 365

    def calculate(self, user_id: int) -> float:
        cache_key = CACHE_KEY.format(user_id)
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached

        score  = self._compute(user_id)
        cache.set(cache_key, score, timeout=3600)
        return score

    def recalculate_and_save(self, user_id: int) -> float:
        """Trust score recalculate করে DB তে save করে।"""
        cache.delete(CACHE_KEY.format(user_id))
        score = self.calculate(user_id)
        try:
            from api.promotions.models import UserReputation
            UserReputation.objects.filter(user_id=user_id).update(trust_score=score)
        except Exception as e:
            logger.error(f'Trust score save failed: {e}')
        return score

    def get_trust_level(self, score: float) -> str:
        if score >= 80: return 'trusted'
        if score >= 60: return 'good'
        if score >= 40: return 'fair'
        if score >= 20: return 'poor'
        return 'untrusted'

    def _compute(self, user_id: int) -> float:
        try:
            from api.promotions.models import TaskSubmission, UserReputation, FraudReport
            from api.promotions.choices import SubmissionStatus
            from django.contrib.auth import get_user_model
            from django.utils import timezone
            from django.db.models import Count, Q
            User = get_user_model()

            user = User.objects.get(pk=user_id)
            age  = (timezone.now() - user.date_joined).days

            subs      = TaskSubmission.objects.filter(worker_id=user_id)
            total     = subs.count()
            approved  = subs.filter(status=SubmissionStatus.APPROVED).count()
            app_rate  = approved / max(total, 1)

            fraud_cnt = FraudReport.objects.filter(user_id=user_id).count()
            fraud_score = min(1.0, fraud_cnt * 0.25)

            try:
                rep   = UserReputation.objects.get(user_id=user_id)
                v_lvl = {'none': 0, 'email': 0.3, 'phone': 0.6, 'id': 1.0}.get(getattr(rep, 'verification_level', 'none'), 0)
            except Exception:
                v_lvl = 0.3

            score = (
                app_rate                          * self.WEIGHTS['approval_rate']      * 100 +
                min(1.0, age/self.MAX_AGE_DAYS)   * self.WEIGHTS['account_age_days']   * 100 +
                v_lvl                             * self.WEIGHTS['verification_level'] * 100 +
                (1.0 - fraud_score)               * self.WEIGHTS['fraud_score']        * 100 +
                (1.0 - 0)                         * self.WEIGHTS['dispute_rate']       * 100
            )
            return round(min(100.0, max(0.0, score)), 2)
        except Exception as e:
            logger.error(f'Trust compute failed for user {user_id}: {e}')
            return 50.0
