"""
api/ai_engine/ML_PIPELINES/retraining_pipeline.py
==================================================
Retraining Pipeline — auto retrain on drift/schedule।
"""

import logging
logger = logging.getLogger(__name__)


class RetrainingPipeline:
    """Automatic model retraining trigger।"""

    def should_retrain(self, ai_model_id: str) -> bool:
        from ..repository import DriftRepository
        from ..models import ModelVersion
        from django.utils import timezone
        from datetime import timedelta

        if DriftRepository.needs_retrain(ai_model_id):
            return True

        latest = ModelVersion.objects.filter(
            ai_model_id=ai_model_id, is_active=True
        ).first()
        if latest and latest.trained_at:
            age_days = (timezone.now() - latest.trained_at).days
            return age_days >= 30

        return False

    def run(self, ai_model_id: str, dataset_path: str = 'auto') -> dict:
        if not self.should_retrain(ai_model_id):
            return {'status': 'skipped', 'reason': 'No retraining needed'}

        from .training_pipeline import TrainingPipeline
        try:
            pipeline = TrainingPipeline(ai_model_id)
            result = pipeline.run(dataset_path)
            return {'status': 'completed', **result}
        except Exception as e:
            logger.error(f"Retraining error [{ai_model_id}]: {e}")
            return {'status': 'failed', 'error': str(e)}


"""
api/ai_engine/ML_PIPELINES/evaluation_pipeline.py
==================================================
Evaluation Pipeline — model performance evaluation।
"""


class EvaluationPipeline:
    """Comprehensive model evaluation।"""

    def run(self, ai_model_id: str, eval_dataset_path: str = None) -> dict:
        from ..models import ModelVersion, ModelMetric

        version = ModelVersion.objects.filter(
            ai_model_id=ai_model_id, is_active=True
        ).first()

        if not version:
            return {'status': 'no_active_version'}

        metrics = {
            'accuracy': version.accuracy,
            'precision': version.precision,
            'recall': version.recall,
            'f1_score': version.f1_score,
            'auc_roc': version.auc_roc,
        }

        passed = (
            metrics['f1_score'] >= 0.70 and
            metrics['auc_roc'] >= 0.75
        )

        return {
            'status':    'passed' if passed else 'failed',
            'metrics':   metrics,
            'version':   version.version,
            'passed':    passed,
        }


"""
api/ai_engine/ML_PIPELINES/real_time_prediction_pipeline.py
============================================================
Real-Time Prediction Pipeline — ultra-low latency।
"""

import time


class RealTimePredictionPipeline:
    """<100ms prediction pipeline।"""

    def __init__(self, ai_model_id: str):
        self.ai_model_id = ai_model_id
        self._pipeline   = None

    def predict(self, input_data: dict) -> dict:
        start = time.time()
        if self._pipeline is None:
            from .inference_pipeline import InferencePipeline
            self._pipeline = InferencePipeline(self.ai_model_id)
        result = self._pipeline.run(input_data)
        result['latency_ms'] = round((time.time() - start) * 1000, 2)
        return result


"""
api/ai_engine/ML_PIPELINES/feature_pipeline.py
===============================================
Feature Pipeline — feature computation ও storage।
"""


class FeaturePipeline:
    """Compute ও store features for all entities।"""

    def run_for_user(self, user_id: str, tenant_id=None) -> dict:
        from ..repository import FeatureRepository
        from ..ML_MODELS.feature_engineering import FeatureEngineer

        engineer = FeatureEngineer(feature_type='behavioral')
        features = engineer.extract({'user_id': user_id})

        obj, created = FeatureRepository.upsert(
            entity_id=user_id,
            feature_type='behavioral',
            features=features,
            entity_type='user',
            tenant_id=tenant_id,
        )
        return {'feature_count': len(features), 'created': created}


"""
api/ai_engine/ML_PIPELINES/deployment_pipeline.py
==================================================
Deployment Pipeline — model promotion to production।
"""


class DeploymentPipeline:
    """Model deployment pipeline।"""

    def deploy(self, ai_model_id: str, version_id: str) -> dict:
        from ..repository import ModelVersionRepository
        from ..services import ModelManagementService

        try:
            version = ModelVersionRepository.promote_to_production(version_id)
            ModelManagementService.deploy_model(ai_model_id)
            return {
                'status':   'deployed',
                'version':  version.version,
                'stage':    version.stage,
            }
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
