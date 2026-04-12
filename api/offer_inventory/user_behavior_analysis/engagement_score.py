# api/offer_inventory/user_behavior_analysis/engagement_score.py
"""
Engagement Score Calculator — RFM-based user engagement scoring (0–100).
Recency × Frequency × Monetary + Loyalty bonus.
"""
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class EngagementScoreCalculator:
    """
    Calculate composite engagement score (0–100).
    Grade: A (80+) B (60+) C (40+) D (20+) F (<20)
    """

    @classmethod
    def calculate(cls, user) -> dict:
        """Full engagement score with RFM breakdown."""
        from api.offer_inventory.models import Click, Conversion
        now    = timezone.now()
        scores = {}

        # ── Recency (30 pts max) ────────────────────────────────
        last = (
            Click.objects.filter(user=user, is_fraud=False)
            .order_by('-created_at').first()
        )
        if last:
            days_ago       = (now - last.created_at).days
            scores['recency'] = max(0.0, 30.0 - days_ago * 1.5)
        else:
            scores['recency'] = 0.0

        # ── Frequency (25 pts max) ──────────────────────────────
        since30           = now - timedelta(days=30)
        click_count_30d   = Click.objects.filter(
            user=user, created_at__gte=since30, is_fraud=False
        ).count()
        scores['frequency'] = min(25.0, click_count_30d * 1.25)

        # ── Monetary (30 pts max) ────────────────────────────────
        from django.db.models import Sum
        earnings_30d = Conversion.objects.filter(
            user=user, created_at__gte=since30, status__name='approved'
        ).aggregate(t=Sum('reward_amount'))['t'] or Decimal('0')
        scores['monetary'] = min(30.0, float(earnings_30d) * 3.0)

        # ── Loyalty tier bonus (15 pts max) ─────────────────────
        try:
            from api.offer_inventory.models import UserProfile
            profile    = UserProfile.objects.select_related('loyalty_level').get(user=user)
            tier_bonus = {
                'Bronze'  : 3.0,
                'Silver'  : 7.0,
                'Gold'    : 11.0,
                'Platinum': 15.0,
            }
            tier_name = profile.loyalty_level.name if profile.loyalty_level else 'Bronze'
            scores['loyalty'] = tier_bonus.get(tier_name, 3.0)
        except Exception:
            scores['loyalty'] = 0.0

        total = sum(scores.values())
        return {
            'total'     : round(total, 1),
            'grade'     : cls._grade(total),
            'breakdown' : {k: round(v, 1) for k, v in scores.items()},
            'max_score' : 100,
        }

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 80: return 'A'
        if score >= 60: return 'B'
        if score >= 40: return 'C'
        if score >= 20: return 'D'
        return 'F'

    @classmethod
    def get_platform_avg_score(cls) -> float:
        """Average engagement score across all users."""
        from api.offer_inventory.models import UserProfile
        from django.db.models import Avg
        prefs = UserProfile.objects.exclude(notification_prefs=None).values_list(
            'notification_prefs', flat=True
        )
        scores = []
        for pref in prefs:
            if isinstance(pref, dict) and 'engagement_score' in pref:
                scores.append(float(pref['engagement_score']))
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 1)

    @classmethod
    def get_score_distribution(cls) -> dict:
        """Distribution of users by engagement grade."""
        from api.offer_inventory.models import UserProfile
        distribution = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        for pref in UserProfile.objects.values_list('notification_prefs', flat=True):
            if isinstance(pref, dict):
                score = float(pref.get('engagement_score', 0))
                grade = cls._grade(score)
                distribution[grade] = distribution.get(grade, 0) + 1
        return distribution
