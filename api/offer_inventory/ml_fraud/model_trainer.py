# api/offer_inventory/ml_fraud/model_trainer.py
"""
Fraud Model Trainer — Train and retrain the ML fraud detection model.
Runs nightly as a Celery beat task.
Uses: Isolation Forest (unsupervised anomaly detection, no labels needed).
"""
import logging
from datetime import timedelta
from django.utils import timezone
from .feature_builder import FraudFeatureBuilder
from .ml_scorer import MLFraudScorer

logger = logging.getLogger(__name__)


class FraudModelTrainer:
    """
    Train Isolation Forest on historical click data.
    No labeled data needed — learns what "normal" looks like,
    then flags deviations as fraud.
    """

    @staticmethod
    def train(days: int = 30, n_estimators: int = 100,
               contamination: float = 0.1) -> dict:
        """
        Train model on last N days of click data.
        contamination: estimated fraction of fraudulent clicks (0.0–0.5).
        """
        try:
            import numpy as np
            from sklearn.ensemble import IsolationForest
            from sklearn.preprocessing import StandardScaler
            from django.core.cache import cache
        except ImportError:
            return {
                'success': False,
                'error'  : (
                    'scikit-learn not installed. '
                    'Run: pip install scikit-learn numpy'
                ),
            }

        from api.offer_inventory.models import Click
        since  = timezone.now() - timedelta(days=days)
        clicks = list(
            Click.objects.filter(created_at__gte=since)
            .select_related('user')
            [:50000]
        )

        if len(clicks) < 100:
            return {
                'success': False,
                'error'  : f'Need ≥100 samples, found {len(clicks)}.',
            }

        logger.info(f'ML training started: {len(clicks)} clicks, {days} days')

        # Build feature matrix
        X       = []
        skipped = 0
        for click in clicks:
            try:
                features = FraudFeatureBuilder.extract(
                    click.ip_address or '',
                    click.user,
                    click.user_agent or '',
                )
                X.append(features)
            except Exception:
                skipped += 1

        if len(X) < 100:
            return {
                'success': False,
                'error'  : f'Feature extraction failed for most samples. Got {len(X)}.',
            }

        # Scale + train
        X_arr    = np.array(X, dtype=float)
        scaler   = StandardScaler()
        X_scaled = scaler.fit_transform(X_arr)

        model    = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state =42,
            n_jobs       =-1,
        )
        model.fit(X_scaled)

        # Store in Redis cache (24h TTL)
        cache.set(MLFraudScorer.MODEL_CACHE_KEY,  model,  86400)
        cache.set(MLFraudScorer.SCALER_CACHE_KEY, scaler, 86400)

        # Score a small validation set
        sample = X_arr[:min(100, len(X_arr))]
        scores = model.decision_function(scaler.transform(sample))
        anomaly_pct = round((scores < 0).sum() / len(scores) * 100, 1)

        result = {
            'success'       : True,
            'samples_used'  : len(X),
            'samples_skipped': skipped,
            'n_estimators'  : n_estimators,
            'contamination' : contamination,
            'features'      : len(FraudFeatureBuilder.FEATURE_NAMES),
            'validation_anomaly_pct': anomaly_pct,
            'trained_at'    : timezone.now().isoformat(),
        }
        logger.info(f'ML fraud model trained: {result}')
        return result

    @staticmethod
    def evaluate(test_clicks: list) -> dict:
        """Evaluate model on a test set."""
        from .ml_scorer import MLFraudScorer
        if not MLFraudScorer.is_model_ready():
            return {'error': 'Model not trained'}

        results = []
        for click in test_clicks[:500]:
            score = MLFraudScorer.score(
                ip             =click.ip_address or '',
                user           =click.user,
                user_agent     =click.user_agent or '',
                rule_based_score=0.0,
            )
            results.append({
                'is_fraud'    : click.is_fraud,
                'ml_score'    : score['ml_score'],
                'is_anomaly'  : score['is_anomaly'],
            })

        if not results:
            return {'error': 'No results'}

        true_fraud     = [r for r in results if r['is_fraud']]
        true_clean     = [r for r in results if not r['is_fraud']]
        true_positives = sum(1 for r in true_fraud if r['is_anomaly'])
        false_positives= sum(1 for r in true_clean if r['is_anomaly'])

        recall    = true_positives / max(len(true_fraud), 1)
        precision = true_positives / max(true_positives + false_positives, 1)
        f1        = 2 * precision * recall / max(precision + recall, 0.0001)

        return {
            'test_samples'   : len(results),
            'fraud_samples'  : len(true_fraud),
            'clean_samples'  : len(true_clean),
            'true_positives' : true_positives,
            'false_positives': false_positives,
            'precision'      : round(precision, 3),
            'recall'         : round(recall, 3),
            'f1_score'       : round(f1, 3),
        }
