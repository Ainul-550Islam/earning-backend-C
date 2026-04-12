"""
api/ai_engine/PREDICTION_ENGINES/churn_predictor.py
====================================================
Churn Predictor — user departure probability prediction।
Multi-signal churn scoring: recency, frequency, monetary, engagement।
Earning platform এর সবচেয়ে গুরুত্বপূর্ণ retention tool।
"""

import logging
import math
from typing import Dict, List, Optional

from ..utils import days_since, get_churn_risk_level, normalize_score, safe_ratio

logger = logging.getLogger(__name__)


class ChurnPredictor:
    """
    Multi-signal churn probability prediction।
    RFM + engagement + behavioral signals combine করো।
    """

    # Signal weights
    WEIGHTS = {
        'recency':    0.35,
        'engagement': 0.25,
        'monetary':   0.20,
        'behavioral': 0.20,
    }

    # Risk thresholds
    THRESHOLDS = {
        'very_high': 0.80,
        'high':      0.60,
        'medium':    0.40,
        'low':       0.20,
    }

    def predict(self, user, extra_data: dict = None) -> dict:
        """
        User churn probability predict করো।
        Returns probability (0.0-1.0) এবং risk level।
        """
        extra_data = extra_data or {}

        # Individual signal scores
        recency_score    = self._recency_score(user, extra_data)
        engagement_score = self._engagement_score(user, extra_data)
        monetary_score   = self._monetary_score(user, extra_data)
        behavioral_score = self._behavioral_score(user, extra_data)

        # Weighted combination
        churn_prob = (
            recency_score    * self.WEIGHTS['recency'] +
            engagement_score * self.WEIGHTS['engagement'] +
            monetary_score   * self.WEIGHTS['monetary'] +
            behavioral_score * self.WEIGHTS['behavioral']
        )
        churn_prob = max(0.0, min(1.0, churn_prob))
        risk_level = get_churn_risk_level(churn_prob)

        # Top contributing factors
        factors = {
            'recency':    round(recency_score, 4),
            'engagement': round(engagement_score, 4),
            'monetary':   round(monetary_score, 4),
            'behavioral': round(behavioral_score, 4),
        }
        top_factors = sorted(factors.items(), key=lambda x: x[1], reverse=True)[:3]

        return {
            'user_id':           str(user.id),
            'churn_probability': round(churn_prob, 4),
            'risk_level':        risk_level,
            'days_since_login':  days_since(user.last_login),
            'days_since_earn':   extra_data.get('days_since_earn', days_since(user.last_login)),
            'signal_scores':     factors,
            'top_factors':       dict(top_factors),
            'retention_actions': self._retention_actions(risk_level, top_factors),
            'confidence':        0.75,
            'method':            'multi_signal_weighted',
        }

    def _recency_score(self, user, data: dict) -> float:
        """Login recency — longest gap → highest churn risk।"""
        days_inactive = days_since(user.last_login)
        # Exponential decay: after 30 days → very high risk
        score = 1.0 - math.exp(-days_inactive / 15)
        return round(min(1.0, score), 4)

    def _engagement_score(self, user, data: dict) -> float:
        """Engagement level — low engagement → high churn।"""
        offers_7d  = data.get('offers_completed_7d', 0)
        sessions_7d = data.get('sessions_7d', 0)
        streak      = data.get('streak_days', 0)

        # High engagement → low churn score
        offer_factor   = max(0.0, 1.0 - offers_7d * 0.1)
        session_factor = max(0.0, 1.0 - sessions_7d * 0.05)
        streak_factor  = max(0.0, 1.0 - streak * 0.03)

        return round((offer_factor + session_factor + streak_factor) / 3, 4)

    def _monetary_score(self, user, data: dict) -> float:
        """Monetary value — high earners less likely to churn।"""
        total_earned = float(getattr(user, 'total_earned', 0))
        coin_balance = float(getattr(user, 'coin_balance', 0))
        account_age  = max(1, days_since(user.date_joined))

        avg_daily = safe_ratio(total_earned, account_age)

        # High balance + high earning rate → low churn
        earned_factor  = max(0.0, 1.0 - normalize_score(total_earned, 0, 10000))
        balance_factor = max(0.0, 1.0 - normalize_score(coin_balance, 0, 5000))
        daily_factor   = max(0.0, 1.0 - normalize_score(avg_daily, 0, 100))

        return round((earned_factor + balance_factor + daily_factor) / 3, 4)

    def _behavioral_score(self, user, data: dict) -> float:
        """Behavioral signals — declining activity patterns।"""
        # Check if activity is declining
        ctr_trend     = data.get('ctr_trend', 'stable')
        referral_count = data.get('referral_count', 0)
        notifications_enabled = data.get('notifications_enabled', True)
        app_version_outdated  = data.get('app_version_outdated', False)

        score = 0.5  # base

        if ctr_trend == 'decreasing':    score += 0.25
        elif ctr_trend == 'increasing':  score -= 0.20

        if referral_count >= 5:          score -= 0.15
        elif referral_count == 0:        score += 0.10

        if not notifications_enabled:    score += 0.15
        if app_version_outdated:         score += 0.10

        return round(max(0.0, min(1.0, score)), 4)

    def _retention_actions(self, risk_level: str,
                            top_factors: list) -> List[str]:
        """Risk level অনুযায়ী retention actions suggest করো।"""
        base_actions = {
            'very_high': [
                'Urgent win-back: Send 50% bonus offer immediately',
                'Personal SMS outreach from support team',
                'Limited-time exclusive offer (24h validity)',
                'Free premium feature unlock for 7 days',
                'Referral bonus double incentive',
            ],
            'high': [
                'Send re-engagement email with new offer highlights',
                'Push notification: "আপনার জন্য বিশেষ অফার!"',
                'Daily streak restart bonus',
                'Show top earning opportunities on next login',
                'Targeted discount coupon',
            ],
            'medium': [
                'Weekly digest email with earnings summary',
                'Introduce new offer categories',
                'Leaderboard competition invitation',
                'Referral program reminder',
            ],
            'low': [
                'Continue normal engagement flow',
                'Show streak milestone rewards',
            ],
            'very_low': [
                'No intervention needed — maintain current engagement',
            ],
        }

        actions = base_actions.get(risk_level, [])

        # Add factor-specific actions
        for factor, score in top_factors:
            if factor == 'recency' and score >= 0.70:
                actions.insert(0, 'PRIORITY: User inactive — immediate outreach required')
            elif factor == 'monetary' and score >= 0.70:
                actions.append('Highlight earning potential and pending rewards')

        return actions[:5]  # Top 5 actions

    def predict_cohort(self, users: list, tenant_id=None) -> dict:
        """Multiple users এর churn prediction একসাথে।"""
        results = []
        risk_distribution = {'very_low': 0, 'low': 0, 'medium': 0, 'high': 0, 'very_high': 0}

        for user in users:
            try:
                result = self.predict(user)
                results.append(result)
                risk_level = result.get('risk_level', 'medium')
                risk_distribution[risk_level] = risk_distribution.get(risk_level, 0) + 1
            except Exception as e:
                logger.error(f"Churn predict error for {user.id}: {e}")

        total = len(results)
        high_risk_count = risk_distribution.get('high', 0) + risk_distribution.get('very_high', 0)
        avg_prob = sum(r.get('churn_probability', 0) for r in results) / max(total, 1)

        return {
            'total_users':        total,
            'avg_churn_probability': round(avg_prob, 4),
            'high_risk_users':    high_risk_count,
            'high_risk_pct':      round(high_risk_count / max(total, 1) * 100, 2),
            'risk_distribution':  risk_distribution,
            'results':            results,
            'immediate_action_needed': high_risk_count > 0,
        }

    def update_model_with_feedback(self, user_id: str,
                                    actually_churned: bool,
                                    predicted_prob: float):
        """Feedback loop — prediction accuracy track করো।"""
        try:
            from ..repository import PredictionLogRepository
            from ..models import PredictionLog

            logs = PredictionLog.objects.filter(
                prediction_type='churn',
            ).order_by('-created_at')[:1]

            if logs:
                actual = 'churned' if actually_churned else 'retained'
                is_correct = (actually_churned and predicted_prob >= 0.5) or \
                             (not actually_churned and predicted_prob < 0.5)
                logger.info(
                    f"Churn feedback: user={user_id} "
                    f"predicted={predicted_prob:.2f} "
                    f"actual={actual} "
                    f"correct={is_correct}"
                )
        except Exception as e:
            logger.error(f"Feedback update error: {e}")
