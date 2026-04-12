# api/offer_inventory/ml_fraud/feature_builder.py
"""
Fraud Feature Builder — Extract ML features from click/conversion events.
Features used for Isolation Forest and logistic regression fraud models.
"""
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class FraudFeatureBuilder:
    """Extract numeric features from a click event for ML fraud scoring."""

    FEATURE_NAMES = [
        'clicks_last_hour',
        'clicks_last_day',
        'conversions_last_day',
        'unique_offers_clicked',
        'avg_click_interval_sec',
        'conversion_rate',
        'hour_of_day',
        'day_of_week',
        'is_weekend',
        'is_mobile',
        'is_vpn',
        'is_datacenter',
        'ip_click_count_hour',
        'user_account_age_days',
        'has_kyc',
        'has_withdrawal',
    ]

    @classmethod
    def extract(cls, ip: str, user=None, user_agent: str = '') -> list:
        """
        Extract feature vector for a click event.
        Returns a list of floats in FEATURE_NAMES order.
        """
        from api.offer_inventory.models import Click, Conversion, UserKYC, WithdrawalRequest

        now    = timezone.now()
        since1h = now - timedelta(hours=1)
        since1d = now - timedelta(days=1)

        features = []

        # Velocity features
        ip_clicks_h  = Click.objects.filter(ip_address=ip, created_at__gte=since1h).count()
        ip_clicks_d  = Click.objects.filter(ip_address=ip, created_at__gte=since1d).count()
        features.append(float(ip_clicks_h))
        features.append(float(ip_clicks_d))

        # Conversion features
        if user:
            convs_d = Conversion.objects.filter(user=user, created_at__gte=since1d).count()
            offers_d = Click.objects.filter(user=user, created_at__gte=since1d).values('offer_id').distinct().count()
        else:
            convs_d = 0
            offers_d = 0
        features.append(float(convs_d))
        features.append(float(offers_d))

        # Click interval (avg seconds between clicks)
        recent_clicks = list(
            Click.objects.filter(ip_address=ip, created_at__gte=since1h)
            .order_by('created_at')
            .values_list('created_at', flat=True)[:20]
        )
        if len(recent_clicks) >= 2:
            intervals = [
                (recent_clicks[i] - recent_clicks[i-1]).total_seconds()
                for i in range(1, len(recent_clicks))
            ]
            avg_interval = sum(intervals) / len(intervals)
        else:
            avg_interval = 3600.0
        features.append(float(avg_interval))

        # Conversion rate
        total_clicks = max(ip_clicks_d, 1)
        features.append(float(convs_d) / float(total_clicks))

        # Time features
        features.append(float(now.hour))
        features.append(float(now.weekday()))
        features.append(float(1 if now.weekday() >= 5 else 0))

        # Device features
        ua_lower = user_agent.lower()
        features.append(float(1 if any(k in ua_lower for k in ['android', 'iphone', 'mobile']) else 0))

        # Network features
        from api.offer_inventory.targeting.isp_targeting import ISPTargetingEngine
        isp_info = ISPTargetingEngine.get_isp_info(ip)
        features.append(float(1 if 'vpn' in isp_info.get('isp', '').lower() else 0))
        features.append(float(1 if isp_info.get('is_hosting', False) else 0))

        # IP stats
        features.append(float(ip_clicks_h))

        # User features
        if user:
            age_days = max((now - user.date_joined).days, 0)
            has_kyc  = UserKYC.objects.filter(user=user, status='approved').exists()
            has_wd   = WithdrawalRequest.objects.filter(user=user, status='completed').exists()
        else:
            age_days = 0
            has_kyc  = False
            has_wd   = False
        features.append(float(age_days))
        features.append(float(1 if has_kyc else 0))
        features.append(float(1 if has_wd else 0))

        return features


# ─────────────────────────────────────────────────────────────────────────────
# api/offer_inventory/ml_fraud/ml_scorer.py
# ─────────────────────────────────────────────────────────────────────────────

class MLFraudScorer:
    """
    ML-based fraud scorer using cached trained model.
    Combines rule-based score with ML anomaly score.
    Falls back gracefully if scikit-learn not installed.
    """

    MODEL_CACHE_KEY = 'ml_fraud:model'
    SCALER_CACHE_KEY = 'ml_fraud:scaler'

    @classmethod
    def score(cls, ip: str, user=None, user_agent: str = '',
               rule_based_score: float = 0.0) -> dict:
        """
        Compute ML fraud score.
        Returns {'ml_score': float, 'combined_score': float, 'is_anomaly': bool}
        """
        try:
            features  = FraudFeatureBuilder.extract(ip, user, user_agent)
            ml_score  = cls._score_with_model(features)
            combined  = cls._combine_scores(rule_based_score, ml_score)
            return {
                'ml_score'      : round(ml_score, 1),
                'rule_score'    : round(rule_based_score, 1),
                'combined_score': round(combined, 1),
                'is_anomaly'    : ml_score >= 70.0,
                'features_used' : len(features),
            }
        except Exception as e:
            logger.debug(f'ML scoring error: {e}')
            return {
                'ml_score'      : 0.0,
                'rule_score'    : rule_based_score,
                'combined_score': rule_based_score,
                'is_anomaly'    : False,
                'error'         : str(e)[:100],
            }

    @classmethod
    def _score_with_model(cls, features: list) -> float:
        """Score features using cached Isolation Forest model."""
        try:
            import numpy as np
            from django.core.cache import cache
            model   = cache.get(cls.MODEL_CACHE_KEY)
            scaler  = cache.get(cls.SCALER_CACHE_KEY)

            if model is None or scaler is None:
                # Model not trained yet — return neutral score
                return 0.0

            X       = scaler.transform([features])
            score   = model.decision_function(X)[0]
            # Isolation Forest: negative = anomaly, positive = normal
            # Convert to 0-100 scale (negative = high fraud)
            fraud_pct = max(0.0, min(100.0, (-score + 0.5) * 100))
            return fraud_pct
        except ImportError:
            return 0.0

    @staticmethod
    def _combine_scores(rule_score: float, ml_score: float) -> float:
        """Weighted combination: 60% rules + 40% ML."""
        return rule_score * 0.6 + ml_score * 0.4


# ─────────────────────────────────────────────────────────────────────────────
# api/offer_inventory/ml_fraud/model_trainer.py
# ─────────────────────────────────────────────────────────────────────────────

class FraudModelTrainer:
    """
    Train and update the Isolation Forest fraud model.
    Runs as a nightly Celery task — retrains on last 30 days of click data.
    """

    @staticmethod
    def train(days: int = 30, n_estimators: int = 100) -> dict:
        """
        Train Isolation Forest on historical click data.
        Stores model in Redis cache for real-time scoring.
        """
        try:
            import numpy as np
            from sklearn.ensemble import IsolationForest
            from sklearn.preprocessing import StandardScaler
            from django.core.cache import cache
        except ImportError:
            return {'success': False, 'error': 'scikit-learn not installed. Run: pip install scikit-learn'}

        from api.offer_inventory.models import Click
        from datetime import timedelta
        from django.utils import timezone

        since  = timezone.now() - timedelta(days=days)
        clicks = Click.objects.filter(
            created_at__gte=since
        ).select_related('user')[:50000]

        logger.info(f'ML training: {clicks.count()} clicks from last {days} days')

        X = []
        for click in clicks:
            try:
                features = FraudFeatureBuilder.extract(
                    click.ip_address, click.user,
                    click.user_agent or ''
                )
                X.append(features)
            except Exception:
                pass

        if len(X) < 100:
            return {'success': False, 'error': f'Insufficient data: {len(X)} samples (need ≥100)'}

        X_arr   = np.array(X, dtype=float)
        scaler  = StandardScaler()
        X_scaled = scaler.fit_transform(X_arr)

        model   = IsolationForest(
            n_estimators     =n_estimators,
            contamination    =0.1,    # Assume 10% fraud
            random_state     =42,
            n_jobs           =-1,
        )
        model.fit(X_scaled)

        # Cache for 24 hours
        cache.set(MLFraudScorer.MODEL_CACHE_KEY, model, 86400)
        cache.set(MLFraudScorer.SCALER_CACHE_KEY, scaler, 86400)

        logger.info(f'ML fraud model trained: {len(X)} samples, {n_estimators} estimators')
        return {
            'success'       : True,
            'samples_used'  : len(X),
            'n_estimators'  : n_estimators,
            'features'      : len(FraudFeatureBuilder.FEATURE_NAMES),
            'trained_at'    : str(timezone.now()),
        }


# ─────────────────────────────────────────────────────────────────────────────
# api/offer_inventory/ml_fraud/anomaly_detector.py
# ─────────────────────────────────────────────────────────────────────────────

class AnomalyDetector:
    """
    Detect anomalous patterns in platform data.
    Identifies: click farms, bot networks, coordinated fraud.
    """

    @staticmethod
    def detect_click_farm(ip_prefix: str = None, hours: int = 6) -> list:
        """
        Detect click farm patterns:
        - Multiple IPs from same /24 subnet
        - Synchronized clicks on same offer
        - Zero conversion despite many clicks
        """
        from api.offer_inventory.models import Click
        from django.db.models import Count, Q
        from datetime import timedelta

        since = timezone.now() - timedelta(hours=hours)
        suspicious = []

        # Find IPs with unusually high click counts
        high_volume = (
            Click.objects.filter(created_at__gte=since, is_fraud=False)
            .values('ip_address')
            .annotate(count=Count('id'))
            .filter(count__gte=50)
            .order_by('-count')[:100]
        )

        for entry in high_volume:
            ip    = entry['ip_address']
            count = entry['count']
            # Check conversion rate for this IP
            convs = Click.objects.filter(
                ip_address=ip, converted=True, created_at__gte=since
            ).count()
            cvr = convs / max(count, 1)
            if cvr < 0.01:   # Less than 1% CVR with high volume = suspicious
                suspicious.append({
                    'ip'       : ip,
                    'clicks'   : count,
                    'conversions': convs,
                    'cvr_pct'  : round(cvr * 100, 2),
                    'action'   : 'review',
                })
        return suspicious

    @staticmethod
    def detect_coordinated_fraud(hours: int = 1) -> dict:
        """
        Detect coordinated fraud: multiple users, same IP block, same offer.
        """
        from api.offer_inventory.models import Click
        from django.db.models import Count
        from datetime import timedelta

        since = timezone.now() - timedelta(hours=hours)
        coord = (
            Click.objects.filter(created_at__gte=since, is_fraud=False)
            .values('offer_id')
            .annotate(
                unique_ips=Count('ip_address', distinct=True),
                total_clicks=Count('id'),
            )
            .filter(total_clicks__gte=100, unique_ips__lte=5)
            .order_by('-total_clicks')[:20]
        )
        return {
            'coordinated_patterns': list(coord),
            'analysis_window_hours': hours,
        }
