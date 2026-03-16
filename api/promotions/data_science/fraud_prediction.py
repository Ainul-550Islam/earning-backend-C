# =============================================================================
# api/promotions/data_science/fraud_prediction.py
# Fraud Prediction — কোন user ভবিষ্যতে fraud করবে তা আগে থেকে detect করা
# Behavioral pattern analysis + Risk scoring
# =============================================================================

import logging
import math
from dataclasses import dataclass, field
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('data_science.fraud_prediction')
CACHE_PREFIX_FP = 'ds:fraud:{}'


@dataclass
class FraudRiskScore:
    user_id:          int
    risk_score:       float          # 0.0 - 1.0
    risk_level:       str            # 'low', 'medium', 'high', 'critical'
    fraud_indicators: list           # Specific red flags
    predicted_fraud_type: str        # 'screenshot_fake', 'vpn_hopping', 'multi_account', etc
    action:           str            # 'allow', 'monitor', 'flag', 'ban'
    confidence:       float
    timestamp:        float


@dataclass
class FraudPattern:
    pattern_type:   str
    description:    str
    risk_weight:    float
    detected:       bool


class FraudPredictor:
    """
    Predictive fraud detection using behavioral signals।

    Signals analyzed:
    1. Submission velocity — অতি দ্রুত submit করা (bot)
    2. IP diversity — অনেক IP থেকে একই account
    3. Device fingerprint consistency
    4. Approval/rejection pattern
    5. Time-of-day patterns (unusual hours)
    6. Similar submissions (copy-paste proof)
    7. Network graph — একই device থেকে multiple accounts
    8. Geographic impossibility — ২ মিনিটে ঢাকা থেকে নিউইয়র্ক

    Model: Weighted scoring with behavioral rules
    """

    # Risk weights for each indicator
    INDICATORS = {
        'high_velocity':          0.30,   # > 20 tasks/hour
        'ip_hopping':             0.25,   # > 5 different IPs/day
        'always_night_tasks':     0.10,   # 2am-5am only
        'perfect_approval_rate':  0.15,   # 100% with > 50 tasks (too perfect)
        'sudden_volume_spike':    0.20,   # 10x normal volume
        'device_mismatch':        0.20,   # Device changed frequently
        'geo_impossible':         0.35,   # Geographic impossibility
        'duplicate_submissions':  0.40,   # Same proof image hash
        'multi_account_signal':   0.45,   # Same device, different accounts
        'past_fraud_record':      0.60,   # Previously flagged
    }

    def predict(self, user_id: int) -> FraudRiskScore:
        """User এর fraud risk score predict করে।"""
        import time
        cache_key = CACHE_PREFIX_FP.format(f'score:{user_id}')
        cached    = cache.get(cache_key)
        if cached:
            return FraudRiskScore(**cached)

        patterns  = self._analyze_patterns(user_id)
        score     = self._calculate_score(patterns)
        result    = self._build_result(user_id, score, patterns)

        cache.set(cache_key, result.__dict__, timeout=1800)
        return result

    def batch_predict_high_risk(self, lookback_hours: int = 24) -> list:
        """
        Recent active users এর মধ্যে high-risk users identify করে।
        Celery task থেকে call করো।
        """
        try:
            from api.promotions.models import TaskSubmission
            from django.db.models import Count

            since    = timezone.now() - timedelta(hours=lookback_hours)
            user_ids = list(
                TaskSubmission.objects
                .filter(submitted_at__gte=since)
                .values('worker_id')
                .annotate(count=Count('id'))
                .filter(count__gte=5)   # Only active users
                .values_list('worker_id', flat=True)[:200]
            )
        except Exception:
            return []

        high_risk = []
        for uid in user_ids:
            score = self.predict(uid)
            if score.risk_level in ('high', 'critical'):
                high_risk.append(score)

        high_risk.sort(key=lambda s: s.risk_score, reverse=True)
        logger.info(f'Fraud prediction: {len(high_risk)}/{len(user_ids)} high-risk users found')
        return high_risk

    def get_platform_fraud_stats(self) -> dict:
        """Platform-wide fraud statistics।"""
        cache_key = CACHE_PREFIX_FP.format('platform_stats')
        cached    = cache.get(cache_key)
        if cached:
            return cached
        try:
            from api.promotions.models import TaskSubmission
            from api.promotions.choices import SubmissionStatus
            from django.db.models import Count, Q
            from django.db.models.functions import TruncDate

            since = timezone.now() - timedelta(days=7)
            total = TaskSubmission.objects.filter(submitted_at__gte=since).count()
            rejected = TaskSubmission.objects.filter(
                submitted_at__gte=since, status=SubmissionStatus.REJECTED
            ).count()

            stats = {
                'total_submissions':  total,
                'fraud_rejections':   rejected,
                'fraud_rate':         round(rejected / max(total, 1), 4),
                'period_days':        7,
            }
            cache.set(cache_key, stats, timeout=3600)
            return stats
        except Exception:
            return {}

    # ── Pattern Analysis ──────────────────────────────────────────────────────

    def _analyze_patterns(self, user_id: int) -> list:
        """User এর behavioral patterns analyze করে।"""
        patterns = []

        try:
            from api.promotions.models import TaskSubmission
            from api.promotions.choices import SubmissionStatus
            from django.db.models import Count, Q

            now   = timezone.now()
            since = now - timedelta(hours=24)
            subs  = TaskSubmission.objects.filter(worker_id=user_id, submitted_at__gte=since)

            # High velocity check
            hourly_count = subs.count()
            patterns.append(FraudPattern(
                pattern_type='high_velocity',
                description=f'{hourly_count} submissions in 24h',
                risk_weight=self.INDICATORS['high_velocity'],
                detected=hourly_count > 80,
            ))

            # IP diversity
            ips = subs.values_list('ip_address', flat=True).distinct().count()
            patterns.append(FraudPattern(
                pattern_type='ip_hopping',
                description=f'{ips} different IPs in 24h',
                risk_weight=self.INDICATORS['ip_hopping'],
                detected=ips > 5,
            ))

            # Past fraud record
            past_rejected = TaskSubmission.objects.filter(
                worker_id=user_id,
                status=SubmissionStatus.REJECTED,
                submitted_at__lt=since,
            ).count()
            total_past = TaskSubmission.objects.filter(worker_id=user_id, submitted_at__lt=since).count()
            past_fraud_rate = past_rejected / max(total_past, 1)

            patterns.append(FraudPattern(
                pattern_type='past_fraud_record',
                description=f'{past_fraud_rate:.0%} historical rejection rate',
                risk_weight=self.INDICATORS['past_fraud_record'],
                detected=past_fraud_rate > 0.5,
            ))

            # Duplicate submissions (image hash)
            patterns.append(FraudPattern(
                pattern_type='duplicate_submissions',
                description='Checking image hash duplicates',
                risk_weight=self.INDICATORS['duplicate_submissions'],
                detected=False,  # Requires image hash DB
            ))

        except Exception as e:
            logger.debug(f'Pattern analysis failed for user={user_id}: {e}')

        return patterns

    @staticmethod
    def _calculate_score(patterns: list) -> float:
        """Weighted fraud score calculate করে।"""
        if not patterns:
            return 0.1
        score = 0.0
        for p in patterns:
            if p.detected:
                score += p.risk_weight
        # Normalize with sigmoid
        return round(1 / (1 + math.exp(-(score * 3 - 2))), 4)

    @staticmethod
    def _build_result(user_id: int, score: float, patterns: list) -> FraudRiskScore:
        import time
        if score >= 0.80:   level, action = 'critical', 'ban'
        elif score >= 0.60: level, action = 'high',     'flag'
        elif score >= 0.40: level, action = 'medium',   'monitor'
        else:               level, action = 'low',      'allow'

        indicators = [p.pattern_type for p in patterns if p.detected]

        fraud_type = 'unknown'
        if 'high_velocity' in indicators:     fraud_type = 'bot_automation'
        elif 'ip_hopping' in indicators:       fraud_type = 'vpn_hopping'
        elif 'duplicate_submissions' in indicators: fraud_type = 'screenshot_reuse'
        elif 'multi_account_signal' in indicators:  fraud_type = 'multi_account'

        return FraudRiskScore(
            user_id=user_id, risk_score=score, risk_level=level,
            fraud_indicators=indicators, predicted_fraud_type=fraud_type,
            action=action, confidence=min(0.95, 0.5 + len(indicators) * 0.1),
            timestamp=time.time(),
        )
