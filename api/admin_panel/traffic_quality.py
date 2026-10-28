# api/admin_panel/traffic_quality.py
"""Traffic quality scoring and publisher quality index."""
from __future__ import annotations
import logging
from typing import Any, Dict
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class TrafficQualityEngine:
    """Score traffic quality per publisher/placement."""

    @classmethod
    def calculate_publisher_quality_score(cls, publisher_id: Any, days: int = 30) -> Dict:
        cache_key = f'admin_panel:tq_score:{publisher_id}:{days}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        score = 100
        signals = []
        cutoff = timezone.now() - timedelta(days=days)

        # Fraud rate
        try:
            from api.fraud_detection.models import FraudAttempt
            from api.promotions.models import TaskSubmission
            from django.db.models import Count
            total_subs = TaskSubmission.objects.filter(
                worker__publisher_id=publisher_id, created_at__gte=cutoff
            ).count()
            fraud_subs = FraudAttempt.objects.filter(
                user__publisher_id=publisher_id, created_at__gte=cutoff
            ).count()
            if total_subs > 0:
                fraud_rate = fraud_subs / total_subs
                if fraud_rate > 0.1:
                    penalty = int(fraud_rate * 100)
                    score -= penalty
                    signals.append({'signal': 'high_fraud_rate', 'value': f'{fraud_rate:.1%}', 'penalty': penalty})
        except Exception:
            pass

        # Rejection rate
        try:
            from api.promotions.models import TaskSubmission
            from django.db.models import Count, Q
            stats = TaskSubmission.objects.filter(
                worker__publisher_id=publisher_id, created_at__gte=cutoff
            ).aggregate(
                total=Count('id'),
                rejected=Count('id', filter=Q(status='rejected')),
            )
            if stats['total'] > 0:
                rejection_rate = stats['rejected'] / stats['total']
                if rejection_rate > 0.3:
                    penalty = int(rejection_rate * 50)
                    score -= penalty
                    signals.append({'signal': 'high_rejection_rate', 'value': f'{rejection_rate:.1%}', 'penalty': penalty})
        except Exception:
            pass

        score = max(0, min(100, score))
        grade = 'A' if score >= 90 else 'B' if score >= 70 else 'C' if score >= 50 else 'D' if score >= 30 else 'F'
        result = {'publisher_id': publisher_id, 'score': score, 'grade': grade,
                  'signals': signals, 'period_days': days,
                  'calculated_at': timezone.now().isoformat()}
        cache.set(cache_key, result, 3600)
        return result

    @classmethod
    def get_top_quality_publishers(cls, limit: int = 20) -> list:
        try:
            from api.publisher_tools.models import Publisher
            from django.db.models import Count
            publishers = Publisher.objects.filter(is_active=True).values_list('id', flat=True)[:100]
            scored = []
            for pid in publishers:
                s = cls.calculate_publisher_quality_score(pid, days=7)
                scored.append(s)
            return sorted(scored, key=lambda x: x['score'], reverse=True)[:limit]
        except Exception:
            return []

    @classmethod
    def flag_low_quality(cls, threshold: int = 40, actor=None) -> Dict:
        """Flag publishers with quality score below threshold."""
        flagged = []
        try:
            from api.publisher_tools.models import Publisher
            for pub in Publisher.objects.filter(is_active=True)[:200]:
                score_data = cls.calculate_publisher_quality_score(pub.pk, days=7)
                if score_data.get('score', 100) < threshold:
                    flagged.append({'publisher_id': pub.pk, 'score': score_data['score']})
        except Exception as e:
            logger.error(f"[TrafficQuality.flag_low_quality] {e}")
        return {'flagged': flagged, 'count': len(flagged), 'threshold': threshold}


traffic_quality = TrafficQualityEngine()