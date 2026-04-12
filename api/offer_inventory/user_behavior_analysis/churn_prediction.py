# api/offer_inventory/user_behavior_analysis/churn_prediction.py
"""
Churn Prediction — ML-inspired churn probability scoring.
Identifies users at risk of leaving the platform.
"""
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)

CHURN_WEIGHTS = {
    'days_since_last_click'      : 0.35,
    'days_since_last_conversion' : 0.30,
    'declining_frequency'        : 0.20,
    'low_earnings'               : 0.15,
}


class ChurnPredictor:
    """Predict which users are at risk of churning."""

    @classmethod
    def predict_score(cls, user) -> float:
        """
        Calculate churn probability (0.0 – 1.0).
        Higher = more likely to churn.
        """
        from api.offer_inventory.models import Click, Conversion
        score = 0.0
        now   = timezone.now()

        # Days since last click
        last_click = (
            Click.objects.filter(user=user, is_fraud=False)
            .order_by('-created_at').first()
        )
        if last_click:
            days_since = (now - last_click.created_at).days
            score += min(1.0, days_since / 30) * CHURN_WEIGHTS['days_since_last_click']
        else:
            score += CHURN_WEIGHTS['days_since_last_click']

        # Days since last conversion
        last_conv = (
            Conversion.objects.filter(user=user, status__name='approved')
            .order_by('-created_at').first()
        )
        if last_conv:
            days_since = (now - last_conv.created_at).days
            score += min(1.0, days_since / 45) * CHURN_WEIGHTS['days_since_last_conversion']
        else:
            score += CHURN_WEIGHTS['days_since_last_conversion']

        # Declining activity frequency
        week1 = Click.objects.filter(
            user=user, created_at__gte=now - timedelta(days=7)
        ).count()
        week2 = Click.objects.filter(
            user=user,
            created_at__gte=now - timedelta(days=14),
            created_at__lt =now - timedelta(days=7),
        ).count()
        if week2 > 0 and week1 < week2 * 0.5:
            score += CHURN_WEIGHTS['declining_frequency']

        # Low earnings
        from django.db.models import Sum
        earnings_30d = Conversion.objects.filter(
            user=user,
            status__name='approved',
            created_at__gte=now - timedelta(days=30),
        ).aggregate(t=Sum('reward_amount'))['t'] or Decimal('0')
        if earnings_30d < Decimal('10'):
            score += CHURN_WEIGHTS['low_earnings'] * float(1 - float(earnings_30d) / 10)

        return min(1.0, round(score, 4))

    @classmethod
    def update_all_churn_scores(cls, limit: int = 5000) -> int:
        """Batch compute and save churn scores for all active users."""
        from api.offer_inventory.models import ChurnRecord, Click
        from django.contrib.auth import get_user_model

        User  = get_user_model()
        count = 0
        for user in User.objects.filter(is_active=True)[:limit]:
            try:
                score = cls.predict_score(user)
                last_click = (
                    Click.objects.filter(user=user).order_by('-created_at').first()
                )
                days_inactive = (
                    (timezone.now() - last_click.created_at).days
                    if last_click else 9999
                )
                ChurnRecord.objects.update_or_create(
                    user=user,
                    defaults={
                        'churn_probability': score,
                        'days_inactive'    : days_inactive,
                        'last_active'      : last_click.created_at if last_click else None,
                        'is_churned'       : score > 0.8,
                    }
                )
                count += 1
            except Exception as e:
                logger.error(f'Churn score error user={user.id}: {e}')
        return count

    @staticmethod
    def get_high_risk_users(threshold: float = 0.7, limit: int = 1000) -> list:
        """Get user IDs with high churn probability."""
        from api.offer_inventory.models import ChurnRecord
        return list(
            ChurnRecord.objects.filter(
                churn_probability__gte=threshold,
                is_churned=False,
            )
            .order_by('-churn_probability')
            .values('user_id', 'churn_probability', 'days_inactive')
            [:limit]
        )

    @staticmethod
    def get_churn_stats() -> dict:
        """Platform-wide churn statistics."""
        from api.offer_inventory.models import ChurnRecord
        from django.db.models import Avg, Count
        agg = ChurnRecord.objects.aggregate(
            avg_prob  =Avg('churn_probability'),
            churned   =Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(is_churned=True)),
            total     =Count('id'),
            reactivated=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(reactivated_at__isnull=False)),
        )
        return {
            'avg_churn_probability': round(float(agg['avg_prob'] or 0), 3),
            'churned_users'        : agg['churned'],
            'total_tracked'        : agg['total'],
            'reactivated'          : agg['reactivated'],
            'churn_rate_pct'       : round(agg['churned'] / max(agg['total'], 1) * 100, 1),
        }
