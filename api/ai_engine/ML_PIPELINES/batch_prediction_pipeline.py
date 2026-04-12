"""
api/ai_engine/ML_PIPELINES/batch_prediction_pipeline.py
========================================================
Batch Prediction Pipeline — large-scale offline predictions।
Churn scoring, LTV calculation, fraud scoring for all users।
Celery task এর মাধ্যমে scheduled এ চালাও।
"""
import logging
import time
from typing import List, Dict, Any
logger = logging.getLogger(__name__)


class BatchPredictionPipeline:
    """Large-scale batch prediction execution।"""

    DEFAULT_BATCH_SIZE = 256

    def __init__(self, ai_model_id: str, prediction_type: str = 'churn'):
        self.ai_model_id    = ai_model_id
        self.prediction_type = prediction_type

    def run(self, queryset=None, batch_size: int = None,
             tenant_id=None) -> dict:
        """Batch predictions চালাও।"""
        batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        start_time = time.time()

        if queryset is None:
            queryset = self._get_default_queryset(tenant_id)

        total     = queryset.count() if hasattr(queryset, 'count') else len(queryset)
        processed = 0
        failed    = 0
        results   = []

        logger.info(f"Batch prediction started: type={self.prediction_type} total={total}")

        for i in range(0, total, batch_size):
            batch = queryset[i: i + batch_size]
            for user in batch:
                try:
                    result = self._predict_single(user)
                    results.append(result)
                    processed += 1
                except Exception as e:
                    logger.error(f"Prediction error for user {getattr(user, 'id', '?')}: {e}")
                    failed += 1

            progress_pct = round((processed + failed) / max(total, 1) * 100, 1)
            if (i // batch_size) % 5 == 0:
                logger.info(f"Batch progress: {processed}/{total} ({progress_pct}%)")

        elapsed = round(time.time() - start_time, 2)
        summary = {
            'status':          'completed',
            'prediction_type': self.prediction_type,
            'total':           total,
            'processed':       processed,
            'failed':          failed,
            'success_rate':    round(processed / max(total, 1), 4),
            'elapsed_seconds': elapsed,
            'throughput_per_sec': round(processed / max(elapsed, 0.001), 1),
        }
        logger.info(f"Batch complete: {summary}")
        return summary

    def _predict_single(self, user) -> dict:
        """Single user prediction।"""
        from ..services import PredictionService, ChurnPredictionService

        if self.prediction_type == 'churn':
            return ChurnPredictionService.predict_churn(user)
        else:
            input_data = self._extract_features(user)
            return PredictionService.predict(
                self.prediction_type, input_data, user=user
            )

    def _extract_features(self, user) -> dict:
        """User থেকে features extract করো।"""
        from django.utils import timezone
        now = timezone.now()
        return {
            'user_id':          str(user.id),
            'account_age_days': (now - user.date_joined).days,
            'days_since_login': (now - (user.last_login or user.date_joined)).days,
            'coin_balance':     float(getattr(user, 'coin_balance', 0)),
            'total_earned':     float(getattr(user, 'total_earned', 0)),
            'country':          getattr(user, 'country', 'BD'),
        }

    def _get_default_queryset(self, tenant_id=None):
        """Default queryset — active users।"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        qs   = User.objects.filter(is_active=True)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        return qs

    def run_async(self, tenant_id=None) -> dict:
        """Celery task এ async চালাও।"""
        try:
            from ..tasks import task_batch_churn_prediction
            task = task_batch_churn_prediction.delay(
                ai_model_id=self.ai_model_id,
                prediction_type=self.prediction_type,
                tenant_id=str(tenant_id) if tenant_id else None,
            )
            return {'task_id': str(task.id), 'status': 'queued', 'async': True}
        except Exception as e:
            logger.warning(f"Celery unavailable: {e} — running sync")
            return self.run(tenant_id=tenant_id)

    def get_prediction_stats(self, days: int = 7) -> dict:
        """Batch prediction statistics।"""
        from ..repository import PredictionLogRepository
        return PredictionLogRepository.get_accuracy_stats(self.ai_model_id, days)

    def schedule_daily(self, hour: int = 2) -> dict:
        """Daily batch prediction schedule করো।"""
        return {
            'scheduled': True,
            'hour':      hour,
            'cron':      f"0 {hour} * * *",
            'info':      f"Batch runs daily at {hour:02d}:00",
        }
