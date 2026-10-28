# api/admin_panel/fraud_ml.py
"""ML-based fraud detection integration — calls api.ai_engine."""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class FraudMLAdmin:
    """Admin control for ML fraud detection models."""

    @classmethod
    def get_ml_fraud_models(cls) -> List[Dict]:
        try:
            from api.ai_engine.models import AIModel
            return list(AIModel.objects.filter(
                model_type__in=['fraud_detection', 'risk_scoring', 'anomaly_detection'],
                is_active=True
            ).values('id', 'name', 'model_type', 'version', 'accuracy', 'last_trained_at'))
        except Exception as e:
            return []

    @classmethod
    def run_fraud_prediction(cls, user_id: Any) -> Dict:
        """Run ML fraud prediction for a user via ai_engine."""
        cache_key = f'admin_panel:fraud_ml:{user_id}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            from api.ai_engine.models import PredictionLog, AIModel
            from django.db.models import Avg
            # Get latest fraud prediction
            latest = PredictionLog.objects.filter(
                entity_id=str(user_id),
                model_name__contains='fraud'
            ).order_by('-created_at').first()
            if latest:
                result = {
                    'user_id': user_id,
                    'fraud_score': getattr(latest, 'confidence_score', 0),
                    'prediction': getattr(latest, 'prediction_result', 'unknown'),
                    'model': latest.model_name,
                    'predicted_at': latest.created_at.isoformat(),
                }
                cache.set(cache_key, result, 300)
                return result
            return {'user_id': user_id, 'fraud_score': 0, 'prediction': 'no_prediction'}
        except Exception as e:
            from api.admin_panel.logic import calculate_user_risk_score
            risk = calculate_user_risk_score(user_id)
            return {'user_id': user_id, 'fraud_score': risk['score'],
                    'prediction': risk['level'], 'method': 'rule_based'}

    @classmethod
    def trigger_fraud_model_retrain(cls, model_id: Any, actor) -> Dict:
        try:
            from api.ai_engine.models import AIModel, TrainingJob
            model = AIModel.objects.get(pk=model_id)
            job = TrainingJob.objects.create(
                model=model, status='queued',
                triggered_by=actor,
            )
            from celery import current_app
            current_app.send_task('api.ai_engine.tasks.run_training_job', args=[job.pk])
            return {'success': True, 'job_id': job.pk, 'model': model.name}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def get_ml_performance_metrics(cls, days: int = 7) -> Dict:
        try:
            from api.ai_engine.models import ModelMetric
            from django.db.models import Avg
            cutoff = timezone.now() - __import__('datetime').timedelta(days=days)
            metrics = ModelMetric.objects.filter(
                created_at__gte=cutoff,
                model__model_type='fraud_detection'
            ).aggregate(avg_accuracy=Avg('accuracy'), avg_precision=Avg('precision'))
            return {'period_days': days, **metrics}
        except Exception as e:
            return {'error': str(e)}

fraud_ml_admin = FraudMLAdmin()