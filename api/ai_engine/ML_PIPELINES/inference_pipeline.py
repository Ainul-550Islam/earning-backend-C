"""
api/ai_engine/ML_PIPELINES/inference_pipeline.py
=================================================
Inference Pipeline — production prediction pipeline।
"""

import logging
import time
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class InferencePipeline:
    """
    Production inference pipeline।
    Input validation → Feature extraction → Model inference → Post-processing → Log।
    """

    def __init__(self, ai_model_id: str):
        self.ai_model_id = ai_model_id

    def run(self, input_data: dict, user=None) -> Dict:
        start = time.time()
        ctx = {'input': input_data, 'user': user, 'errors': []}

        steps = [
            ('input_validation',    self._validate_input),
            ('feature_extraction',  self._extract_features),
            ('model_inference',     self._run_inference),
            ('post_processing',     self._post_process),
            ('logging',             self._log_result),
        ]

        for step_name, fn in steps:
            try:
                ctx = fn(ctx)
            except Exception as e:
                logger.error(f"Inference pipeline [{step_name}]: {e}")
                ctx['errors'].append(str(e))
                if step_name in ('feature_extraction', 'model_inference'):
                    ctx['prediction'] = {'confidence': 0.5, 'method': 'fallback'}
                break

        ctx['inference_ms'] = round((time.time() - start) * 1000, 2)
        return ctx.get('prediction', {})

    def _validate_input(self, ctx: dict) -> dict:
        if not ctx.get('input'):
            raise ValueError("Empty input data")
        return ctx

    def _extract_features(self, ctx: dict) -> dict:
        from ..ML_MODELS.feature_engineering import FeatureEngineer
        engineer = FeatureEngineer()
        ctx['features'] = engineer.extract(ctx['input'])
        return ctx

    def _run_inference(self, ctx: dict) -> dict:
        from ..ML_MODELS.model_predictor import ModelPredictor
        from ..models import ModelVersion
        version = ModelVersion.objects.filter(
            ai_model_id=self.ai_model_id, is_active=True
        ).first()
        path = version.model_file_path if version else ''
        predictor = ModelPredictor(path)
        ctx['prediction'] = predictor.predict(ctx['features'])
        return ctx

    def _post_process(self, ctx: dict) -> dict:
        pred = ctx.get('prediction', {})
        pred['ai_model_id'] = self.ai_model_id
        ctx['prediction'] = pred
        return ctx

    def _log_result(self, ctx: dict) -> dict:
        return ctx


"""
api/ai_engine/ML_PIPELINES/drift_detection_pipeline.py
=======================================================
Drift Detection Pipeline।
"""


class DriftDetectionPipeline:
    """Model data drift detection।"""

    def __init__(self, ai_model):
        self.ai_model = ai_model

    def run(self) -> dict:
        from ..utils import calculate_psi
        from ..models import DataDriftLog
        from django.utils import timezone

        # Placeholder — production এ reference vs current distribution compare করো
        psi_score  = 0.05   # < 0.1 = no drift
        ks_stat    = 0.04
        drift_score = max(psi_score, ks_stat)

        if drift_score >= 0.2:
            status = 'critical'
        elif drift_score >= 0.1:
            status = 'warning'
        else:
            status = 'normal'

        log = DataDriftLog.objects.create(
            ai_model=self.ai_model,
            drift_type='feature',
            status=status,
            drift_score=drift_score,
            psi_score=psi_score,
            ks_statistic=ks_stat,
            retrain_recommended=(status == 'critical'),
            detected_at=timezone.now(),
        )

        return {
            'status':              status,
            'drift_score':         drift_score,
            'psi_score':           psi_score,
            'retrain_recommended': status == 'critical',
        }


"""
api/ai_engine/ML_PIPELINES/monitoring_pipeline.py
=================================================
Model Monitoring Pipeline — production metrics tracking।
"""


class MonitoringPipeline:
    """Monitor production model performance।"""

    def run(self, ai_model_id: str, tenant_id=None) -> dict:
        from ..repository import PredictionLogRepository, DriftRepository
        from ..models import AIModel

        accuracy_stats = PredictionLogRepository.get_accuracy_stats(ai_model_id, days=7)
        drift_status   = DriftRepository.get_latest(ai_model_id)

        health_score = 1.0
        alerts = []

        if accuracy_stats['accuracy'] < 0.70:
            health_score -= 0.3
            alerts.append(f"Low accuracy: {accuracy_stats['accuracy']:.1%}")

        if drift_status and drift_status.status == 'critical':
            health_score -= 0.4
            alerts.append("Critical data drift detected")

        health = 'healthy' if health_score >= 0.7 else 'degraded' if health_score >= 0.4 else 'unhealthy'

        return {
            'ai_model_id':   ai_model_id,
            'health':        health,
            'health_score':  round(health_score, 3),
            'accuracy_7d':   accuracy_stats['accuracy'],
            'drift_status':  drift_status.status if drift_status else 'unknown',
            'alerts':        alerts,
        }


"""
api/ai_engine/ML_PIPELINES/batch_prediction_pipeline.py
=======================================================
Batch Prediction Pipeline — large-scale offline predictions।
"""


class BatchPredictionPipeline:
    """Batch prediction for large datasets।"""

    BATCH_SIZE = 256

    def __init__(self, ai_model_id: str, prediction_type: str):
        self.ai_model_id     = ai_model_id
        self.prediction_type = prediction_type

    def run(self, items: List[dict], tenant_id=None) -> dict:
        from ..services import PredictionService
        from ..utils import chunk_list

        results = []
        failed  = 0
        batches = chunk_list(items, self.BATCH_SIZE)

        for batch in batches:
            for item in batch:
                try:
                    res = PredictionService.predict(self.prediction_type, item, tenant_id=tenant_id)
                    results.append({'input': item, 'prediction': res, 'status': 'ok'})
                except Exception as e:
                    results.append({'input': item, 'error': str(e), 'status': 'failed'})
                    failed += 1

        return {
            'total':     len(items),
            'success':   len(items) - failed,
            'failed':    failed,
            'results':   results,
        }
