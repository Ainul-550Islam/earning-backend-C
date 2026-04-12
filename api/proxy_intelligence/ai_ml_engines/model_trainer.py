"""Model Trainer — orchestrates ML model training and version management."""
import logging
from django.utils import timezone
logger = logging.getLogger(__name__)

class ModelTrainer:
    """Trains, evaluates, and registers ML models in MLModelMetadata."""

    def __init__(self, model_type: str = 'risk_scoring', tenant=None):
        self.model_type = model_type
        self.tenant = tenant

    def prepare_training_data(self, days: int = 90) -> tuple:
        """Pull labeled fraud data from DB for training."""
        from ..models import FraudAttempt, IPIntelligence
        from datetime import timedelta

        since = timezone.now() - timedelta(days=days)
        attempts = FraudAttempt.objects.filter(
            created_at__gte=since,
            status__in=['confirmed', 'false_positive']
        ).select_related('user')[:10000]

        X, y = [], []
        for attempt in attempts:
            intel = IPIntelligence.objects.filter(
                ip_address=attempt.ip_address
            ).first()
            if intel:
                X.append([
                    int(intel.is_vpn), int(intel.is_proxy), int(intel.is_tor),
                    int(intel.is_datacenter), intel.risk_score,
                    intel.abuse_confidence_score, intel.fraud_score,
                ])
                y.append(1 if attempt.status == 'confirmed' else 0)

        return X, y

    def train_and_register(self, save_path: str = '/tmp/pi_model.pkl') -> dict:
        """Full training pipeline with DB registration."""
        X, y = self.prepare_training_data()
        if len(X) < 100:
            return {'error': f'Insufficient training data: {len(X)} samples (need ≥100)'}

        from .supervised_learning import SupervisedFraudClassifier
        clf = SupervisedFraudClassifier()
        metrics = clf.train(X, y)

        if 'error' in metrics:
            return metrics

        # Save model file
        saved_path = clf.save(save_path)

        # Register in DB
        try:
            from ..models import MLModelMetadata
            import datetime
            version = timezone.now().strftime('%Y%m%d%H%M')
            meta = MLModelMetadata.objects.create(
                name=f'fraud_classifier_{self.model_type}',
                version=version,
                model_type=self.model_type,
                accuracy=metrics.get('accuracy'),
                precision=metrics.get('precision'),
                recall=metrics.get('recall'),
                f1_score=metrics.get('f1_score'),
                auc_roc=metrics.get('auc_roc'),
                training_data_size=metrics.get('training_samples', len(X)),
                trained_at=timezone.now(),
                model_file_path=saved_path or '',
                is_active=False,
            )
            metrics['model_id'] = str(meta.id)
            metrics['version'] = version
        except Exception as e:
            logger.error(f"Model registration failed: {e}")

        return metrics
