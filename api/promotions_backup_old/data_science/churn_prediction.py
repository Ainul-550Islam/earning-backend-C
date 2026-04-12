# =============================================================================
# api/promotions/data_science/churn_prediction.py
# Churn Prediction — কোন user প্ল্যাটফর্ম ছেড়ে যাবে তা আগে predict করা
# RFM Analysis + Logistic Regression (pure Python)
# =============================================================================

import logging
import math
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('data_science.churn')
CACHE_PREFIX_CHURN = 'ds:churn:{}'


@dataclass
class ChurnScore:
    user_id:          int
    churn_probability: float     # 0.0 - 1.0
    risk_level:       str        # 'low', 'medium', 'high', 'critical'
    days_since_active: int
    submission_trend: str        # 'increasing', 'stable', 'declining', 'stopped'
    key_factors:      list       # Why this score?
    recommended_action: str      # What to do?
    ltv_at_risk_usd:  float


@dataclass
class ChurnReport:
    total_users:        int
    critical_risk:      int      # Probability > 0.80
    high_risk:          int      # 0.60 - 0.80
    medium_risk:        int      # 0.40 - 0.60
    low_risk:           int      # < 0.40
    avg_churn_prob:     float
    at_risk_ltv_usd:    float
    top_churn_users:    list     # Top 20 highest risk


class ChurnPredictor:
    """
    User churn prediction using RFM Analysis।

    RFM:
    - Recency:   কতদিন আগে last active ছিল
    - Frequency: কতটা task submit করেছে
    - Monetary:  কত টাকা earn করেছে

    Additional signals:
    - Submission decline rate
    - Rejection rate (frustrated users churn)
    - Login frequency drop
    - Withdrawal pattern

    No sklearn needed — pure logistic regression।
    """

    # Feature weights (from domain knowledge)
    WEIGHTS = {
        'recency_days':      -0.08,   # বেশি দিন inactive → churn বেশি
        'frequency_drop':    -0.15,   # Submission কমে যাওয়া
        'rejection_rate':    -0.12,   # বেশি rejection → frustrated
        'earnings_drop':     -0.10,   # কম earn করছে
        'days_since_payout': -0.05,   # পেমেন্ট পায়নি → চলে যাবে
        'login_frequency':    0.08,   # বেশি login → ভালো
        'tasks_completed':    0.06,   # বেশি tasks → engaged
    }

    def predict_user_churn(self, user_id: int) -> ChurnScore:
        """একটি user এর churn probability calculate করে।"""
        cache_key = CACHE_PREFIX_CHURN.format(f'user:{user_id}')
        cached    = cache.get(cache_key)
        if cached:
            return ChurnScore(**cached)

        features = self._extract_features(user_id)
        prob     = self._logistic_predict(features)
        score    = self._build_score(user_id, prob, features)

        cache.set(cache_key, score.__dict__, timeout=3600 * 6)
        return score

    def batch_predict(self, user_ids: list) -> list:
        """Multiple users এর churn score একসাথে।"""
        return [self.predict_user_churn(uid) for uid in user_ids]

    def generate_churn_report(self, days: int = 30) -> ChurnReport:
        """Platform-wide churn risk report।"""
        cache_key = CACHE_PREFIX_CHURN.format(f'report:{days}')
        cached    = cache.get(cache_key)
        if cached:
            return ChurnReport(**cached)

        try:
            from api.promotions.models import TaskSubmission
            from api.promotions.choices import UserRole
            from django.contrib.auth import get_user_model
            User = get_user_model()

            since    = timezone.now() - timedelta(days=days)
            user_ids = list(
                TaskSubmission.objects
                .filter(submitted_at__gte=since)
                .values_list('worker_id', flat=True)
                .distinct()[:500]   # Limit for performance
            )
        except Exception:
            user_ids = []

        scores = self.batch_predict(user_ids)
        if not scores:
            return ChurnReport(0, 0, 0, 0, 0, 0.0, 0.0, [])

        critical = sum(1 for s in scores if s.churn_probability >= 0.80)
        high     = sum(1 for s in scores if 0.60 <= s.churn_probability < 0.80)
        medium   = sum(1 for s in scores if 0.40 <= s.churn_probability < 0.60)
        low      = sum(1 for s in scores if s.churn_probability < 0.40)
        avg_prob = sum(s.churn_probability for s in scores) / len(scores)
        at_risk  = sum(s.ltv_at_risk_usd for s in scores if s.churn_probability >= 0.60)
        top20    = sorted(scores, key=lambda s: s.churn_probability, reverse=True)[:20]

        report = ChurnReport(
            total_users=len(scores), critical_risk=critical, high_risk=high,
            medium_risk=medium, low_risk=low,
            avg_churn_prob=round(avg_prob, 3),
            at_risk_ltv_usd=round(at_risk, 2),
            top_churn_users=[{'user_id': s.user_id, 'prob': s.churn_probability, 'action': s.recommended_action} for s in top20],
        )
        cache.set(cache_key, report.__dict__, timeout=3600 * 3)
        return report

    def get_retention_actions(self, user_id: int) -> list:
        """User retain করার জন্য suggested actions।"""
        score   = self.predict_user_churn(user_id)
        actions = []

        if score.churn_probability >= 0.80:
            actions.append({'type': 'bonus_offer',   'message': 'Exclusive 20% bonus on next 5 tasks!'})
            actions.append({'type': 'personal_msg',  'message': 'We miss you! Come back and earn.'})
        elif score.churn_probability >= 0.60:
            actions.append({'type': 'email_nudge',   'message': 'New high-paying tasks available for you!'})
            actions.append({'type': 'push_notif',    'message': '3 tasks matching your skills!'})
        elif score.churn_probability >= 0.40:
            actions.append({'type': 'recommendation', 'message': 'Try these new campaign types.'})

        return actions

    # ── Feature Extraction ────────────────────────────────────────────────────

    def _extract_features(self, user_id: int) -> dict:
        features = {
            'recency_days': 999, 'frequency_drop': 0.0, 'rejection_rate': 0.0,
            'earnings_drop': 0.0, 'days_since_payout': 999, 'login_frequency': 0.0,
            'tasks_completed': 0, 'total_earnings': 0.0,
        }
        try:
            from api.promotions.models import TaskSubmission, PromotionTransaction
            from api.promotions.choices import SubmissionStatus
            from django.db.models import Count, Sum, Avg

            now   = timezone.now()
            last  = TaskSubmission.objects.filter(worker_id=user_id).order_by('-submitted_at').first()

            if last:
                features['recency_days'] = (now - last.submitted_at).days

            # 30-day vs 60-day submission comparison
            subs_30 = TaskSubmission.objects.filter(worker_id=user_id, submitted_at__gte=now - timedelta(days=30)).count()
            subs_60 = TaskSubmission.objects.filter(worker_id=user_id, submitted_at__gte=now - timedelta(days=60), submitted_at__lt=now - timedelta(days=30)).count()
            if subs_60 > 0:
                features['frequency_drop'] = max(0, (subs_60 - subs_30) / subs_60)

            # Rejection rate
            total    = TaskSubmission.objects.filter(worker_id=user_id).count()
            rejected = TaskSubmission.objects.filter(worker_id=user_id, status=SubmissionStatus.REJECTED).count()
            features['rejection_rate']  = rejected / max(total, 1)
            features['tasks_completed'] = total

            # Earnings
            earnings = PromotionTransaction.objects.filter(
                user_id=user_id, created_at__gte=now - timedelta(days=30)
            ).aggregate(total=Sum('amount_usd'))['total'] or 0
            features['total_earnings'] = float(earnings)

        except Exception as e:
            logger.debug(f'Churn feature extraction failed for user={user_id}: {e}')

        return features

    def _logistic_predict(self, features: dict) -> float:
        """Logistic regression — σ(w·x + b)।"""
        score = 0.0
        score += features.get('recency_days', 0) * self.WEIGHTS['recency_days']
        score += features.get('frequency_drop', 0) * self.WEIGHTS['frequency_drop'] * 10
        score += features.get('rejection_rate', 0) * self.WEIGHTS['rejection_rate'] * 10
        score += features.get('earnings_drop', 0) * self.WEIGHTS['earnings_drop'] * 10
        score += features.get('tasks_completed', 0) * self.WEIGHTS['tasks_completed'] * 0.1
        score += 3.0   # Bias

        # Sigmoid
        return round(1 / (1 + math.exp(-score)), 4)

    def _build_score(self, user_id: int, prob: float, features: dict) -> ChurnScore:
        if prob >= 0.80:   risk = 'critical'
        elif prob >= 0.60: risk = 'high'
        elif prob >= 0.40: risk = 'medium'
        else:              risk = 'low'

        sub_drop = features.get('frequency_drop', 0)
        trend    = 'stopped' if features['recency_days'] > 14 else 'declining' if sub_drop > 0.3 else 'stable'

        factors = []
        if features['recency_days'] > 7:  factors.append(f'{features["recency_days"]} days inactive')
        if features['rejection_rate'] > 0.4: factors.append(f'{features["rejection_rate"]:.0%} rejection rate')
        if sub_drop > 0.3: factors.append(f'Submissions dropped {sub_drop:.0%}')

        if risk == 'critical':   action = 'send_bonus_offer'
        elif risk == 'high':     action = 'send_email_nudge'
        elif risk == 'medium':   action = 'send_recommendation'
        else:                    action = 'monitor'

        ltv_at_risk = features.get('total_earnings', 0) * 12 * prob

        return ChurnScore(
            user_id=user_id, churn_probability=prob, risk_level=risk,
            days_since_active=features['recency_days'],
            submission_trend=trend, key_factors=factors,
            recommended_action=action, ltv_at_risk_usd=round(ltv_at_risk, 2),
        )
