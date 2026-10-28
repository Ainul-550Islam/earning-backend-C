# api/admin_panel/churn_predictor.py
"""User churn prediction and intervention admin control."""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class ChurnPredictorAdmin:
    """Admin interface for churn prediction and re-engagement."""

    @classmethod
    def get_at_risk_users(cls, threshold: float = 0.7, limit: int = 100) -> List[Dict]:
        """Get users at high churn risk."""
        try:
            from api.ai_engine.models import ChurnRiskProfile
            return list(ChurnRiskProfile.objects.filter(
                churn_probability__gte=threshold
            ).values('user_id', 'churn_probability', 'risk_factors', 'predicted_at')
            .order_by('-churn_probability')[:limit])
        except Exception as e:
            # Fallback: find inactive users
            cutoff = timezone.now() - timedelta(days=30)
            from django.contrib.auth import get_user_model
            User = get_user_model()
            users = User.objects.filter(
                is_active=True, last_login__lt=cutoff
            ).values('id', 'username', 'last_login')[:limit]
            return [{'user_id': u['id'], 'churn_probability': 0.8,
                     'risk_factors': ['inactive_30d'], 'predicted_at': None} for u in users]

    @classmethod
    def trigger_reengagement_campaign(cls, user_ids: List[Any], actor) -> Dict:
        """Send re-engagement push/email to at-risk users."""
        sent = 0
        try:
            from api.admin_panel.notifications_push import push_manager
            from api.admin_panel.models.config import SystemConfig
            bonus = SystemConfig.objects.filter(key='churn_reengagement_bonus').first()
            bonus_amount = int(bonus.value) if bonus else 0
            title = "We miss you! 🎁"
            body = f"Come back and earn! Complete a task today."
            if bonus_amount:
                body += f" Exclusive bonus: {bonus_amount} points waiting for you!"
            for uid in user_ids[:500]:
                r = push_manager.send_to_user(uid, title, body)
                sent += r.get('sent', 0)
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=actor, action='churn_reengagement_campaign',
                              changes={'user_count': len(user_ids), 'sent': sent})
        except Exception as e:
            logger.error(f"[ChurnPredictor.reengagement] {e}")
        return {'success': True, 'targeted': len(user_ids), 'sent': sent}

    @classmethod
    def run_churn_prediction(cls) -> Dict:
        """Trigger churn prediction model via ai_engine."""
        try:
            from celery import current_app
            current_app.send_task('api.ai_engine.tasks.predict_churn')
            return {'success': True, 'queued': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def get_churn_rate(cls, days: int = 30) -> Dict:
        """Calculate actual churn rate for period."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        cutoff = timezone.now() - timedelta(days=days)
        total_start = User.objects.filter(date_joined__lt=cutoff).count()
        active_end  = User.objects.filter(last_login__gte=cutoff, is_active=True).count()
        churned = max(0, total_start - active_end)
        rate = churned / max(total_start, 1) * 100
        return {'period_days': days, 'total_users': total_start,
                'active': active_end, 'churned': churned, 'churn_rate_pct': round(rate, 2)}

churn_predictor_admin = ChurnPredictorAdmin()