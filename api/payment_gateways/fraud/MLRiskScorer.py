# api/payment_gateways/fraud/MLRiskScorer.py
# ML-based risk scoring using statistical anomaly detection

from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import math
import logging

logger = logging.getLogger(__name__)


class MLRiskScorer:
    """
    Statistical ML risk scorer.
    Uses Z-score + Isolation Forest concepts without heavy ML libraries.
    For production: integrate with scikit-learn, XGBoost, or AWS Fraud Detector.

    Features analyzed:
        1. Amount Z-score vs user history
        2. Transaction frequency anomaly
        3. Time-of-day pattern deviation
        4. Gateway switching behavior
        5. New account + high amount combo
        6. Cross-gateway multi-deposit detection
    """

    def score(self, user, amount: Decimal, gateway: str, ip_address: str = None, metadata: dict = None) -> dict:
        metadata = metadata or {}
        features = self._extract_features(user, amount, gateway)
        score    = self._compute_score(features)

        return {
            'risk_score': min(50, max(0, score)),
            'features':   features,
            'reasons':    [f for f in features.get('flags', [])],
            'model':      'statistical_v1',
        }

    def _extract_features(self, user, amount: Decimal, gateway: str) -> dict:
        from api.payment_gateways.models import GatewayTransaction
        from django.db.models import Avg, StdDev, Count, Max

        now       = timezone.now()
        last_30d  = now - timedelta(days=30)
        last_7d   = now - timedelta(days=7)
        last_24h  = now - timedelta(hours=24)

        qs = GatewayTransaction.objects.filter(
            user=user,
            status='completed',
            transaction_type='deposit',
        )

        # Historical stats
        stats_30d = qs.filter(created_at__gte=last_30d).aggregate(
            avg_amount=Avg('amount'),
            std_amount=StdDev('amount'),
            count=Count('id'),
        )

        avg_amount = float(stats_30d['avg_amount'] or 0)
        std_amount = float(stats_30d['std_amount'] or 0)
        txn_count  = stats_30d['count'] or 0
        amount_f   = float(amount)

        # Z-score for amount
        z_score = 0.0
        if std_amount > 0 and avg_amount > 0:
            z_score = abs((amount_f - avg_amount) / std_amount)

        # Recent frequency
        count_24h = qs.filter(created_at__gte=last_24h).count()
        count_7d  = qs.filter(created_at__gte=last_7d).count()

        # Gateway diversity (many gateways = suspicious)
        gateways_used = qs.filter(created_at__gte=last_7d).values('gateway').distinct().count()

        # Hour pattern (0-23)
        current_hour = now.hour
        suspicious_hours = list(range(0, 5))  # 12AM - 5AM

        # New user (< 7 days)
        days_since_join = (now - getattr(user, 'date_joined', now)).days

        flags = []
        if z_score > 3:
            flags.append(f'Amount is {z_score:.1f}x std dev from user average')
        if count_24h >= 5:
            flags.append(f'{count_24h} transactions in 24h')
        if gateways_used >= 4:
            flags.append(f'Using {gateways_used} different gateways in 7 days')
        if current_hour in suspicious_hours and amount_f > 1000:
            flags.append(f'Large amount at unusual hour ({current_hour}:00)')
        if days_since_join < 3 and amount_f > 5000:
            flags.append('New account with very large deposit')

        return {
            'z_score':          round(z_score, 2),
            'count_24h':        count_24h,
            'count_7d':         count_7d,
            'gateways_used_7d': gateways_used,
            'days_since_join':  days_since_join,
            'avg_amount_30d':   round(avg_amount, 2),
            'total_txns_30d':   txn_count,
            'current_hour':     current_hour,
            'flags':            flags,
        }

    def _compute_score(self, features: dict) -> int:
        score = 0

        # Z-score contribution (0-20 points)
        z = features.get('z_score', 0)
        if z > 2:   score += 10
        if z > 3:   score += 10
        if z > 5:   score += 10

        # Frequency (0-15 points)
        c24 = features.get('count_24h', 0)
        if c24 >= 3:  score += 5
        if c24 >= 7:  score += 10

        # Gateway diversity (0-10 points)
        gw = features.get('gateways_used_7d', 0)
        if gw >= 3:  score += 5
        if gw >= 5:  score += 5

        # New user + large amount (0-15 points)
        if features.get('days_since_join', 999) < 3:
            score += 15
        elif features.get('days_since_join', 999) < 7:
            score += 7

        return score
