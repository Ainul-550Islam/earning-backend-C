"""
api/ai_engine/tasks.py
=======================
AI Engine — Celery Async Tasks।
Background এ চলা সব AI jobs এখানে।
"""

import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# TRAINING TASKS
# ══════════════════════════════════════════════════════════════════════

@shared_task(bind=True, queue='ai_tasks', max_retries=3, default_retry_delay=60)
def task_train_model(self, ai_model_id: str, dataset_path: str, hyperparams: dict = None, user_id=None):
    """
    Background এ model training চালাও।
    Usage: task_train_model.delay(ai_model_id, dataset_path)
    """
    from .services import TrainingService
    from .ML_MODELS.model_trainer import ModelTrainer

    logger.info(f"[TASK] Starting training for model: {ai_model_id}")
    start = timezone.now()

    try:
        job = TrainingService.start_training(ai_model_id, dataset_path, hyperparams or {})
        trainer = ModelTrainer(ai_model_id)
        result = trainer.train(dataset_path, hyperparams or {})

        duration = (timezone.now() - start).total_seconds()
        TrainingService.complete_training(str(job.job_id), result['version_data'], duration)
        logger.info(f"[TASK] Training complete: {ai_model_id} in {duration:.1f}s")
        return {'status': 'completed', 'duration': duration}

    except Exception as exc:
        logger.error(f"[TASK] Training failed: {ai_model_id} — {exc}")
        try:
            TrainingService.fail_training(ai_model_id, str(exc))
        except Exception:
            pass
        raise self.retry(exc=exc)


@shared_task(queue='ai_tasks')
def task_retrain_all_models():
    """
    Data drift detect হলে সব production models retrain করো।
    Schedule: daily cron।
    """
    from .models import AIModel
    from .repository import DriftRepository

    models = AIModel.objects.filter(status='deployed', is_production=True)
    retrained = 0
    for model in models:
        if DriftRepository.needs_retrain(str(model.id)):
            task_train_model.delay(str(model.id), dataset_path='auto')
            retrained += 1
            logger.info(f"[TASK] Queued retrain: {model.name}")

    return {'retrained_count': retrained}


# ══════════════════════════════════════════════════════════════════════
# PREDICTION TASKS
# ══════════════════════════════════════════════════════════════════════

@shared_task(queue='ai_tasks')
def task_batch_churn_prediction(tenant_id=None):
    """
    সব users এর churn risk update করো।
    Schedule: প্রতিদিন রাত 2 টায়।
    """
    from django.contrib.auth import get_user_model
    from .services import ChurnPredictionService

    User = get_user_model()
    users = User.objects.filter(is_active=True)
    if tenant_id:
        users = users.filter(tenant_id=tenant_id)

    user_ids = list(users.values_list('id', flat=True))
    logger.info(f"[TASK] Batch churn prediction for {len(user_ids)} users")

    ChurnPredictionService.bulk_predict_churn(user_ids, tenant_id)
    return {'processed': len(user_ids)}


@shared_task(queue='ai_tasks')
def task_update_user_embeddings(tenant_id=None):
    """
    User embeddings refresh করো।
    Schedule: প্রতি 6 ঘণ্টায়।
    """
    from django.contrib.auth import get_user_model
    from .ML_MODELS.feature_engineering import FeatureEngineer

    User = get_user_model()
    users = User.objects.filter(is_active=True)
    if tenant_id:
        users = users.filter(tenant_id=tenant_id)

    updated = 0
    engineer = FeatureEngineer(feature_type='behavioral')
    for user in users[:500]:  # batch limit
        try:
            engineer.extract({'user_id': str(user.id)})
            updated += 1
        except Exception as e:
            logger.error(f"Embedding update error for {user.id}: {e}")

    logger.info(f"[TASK] Updated {updated} user embeddings")
    return {'updated': updated}


# ══════════════════════════════════════════════════════════════════════
# RECOMMENDATION TASKS
# ══════════════════════════════════════════════════════════════════════

@shared_task(queue='ai_tasks')
def task_precompute_recommendations(tenant_id=None):
    """
    Active users এর recommendations pre-compute করো।
    Schedule: প্রতি 4 ঘণ্টায়।
    """
    from django.contrib.auth import get_user_model
    from .services import RecommendationService
    from datetime import timedelta

    User = get_user_model()
    since = timezone.now() - timedelta(days=7)
    users = User.objects.filter(is_active=True, last_login__gte=since)
    if tenant_id:
        users = users.filter(tenant_id=tenant_id)

    computed = 0
    for user in users[:200]:
        try:
            RecommendationService.get_recommendations(user, tenant_id=tenant_id)
            computed += 1
        except Exception as e:
            logger.error(f"Pre-compute rec error for {user.id}: {e}")

    logger.info(f"[TASK] Pre-computed recommendations for {computed} users")
    return {'computed': computed}


# ══════════════════════════════════════════════════════════════════════
# ANALYTICS & INSIGHT TASKS
# ══════════════════════════════════════════════════════════════════════

@shared_task(queue='ai_tasks')
def task_generate_daily_insights(tenant_id=None):
    """
    Daily AI insights generate করো।
    Schedule: প্রতিদিন সকাল 7 টায়।
    """
    from .services import InsightGenerationService

    insights = InsightGenerationService.generate_daily_insights(tenant_id)
    logger.info(f"[TASK] Generated {len(insights)} insights")
    return {'insights_generated': len(insights)}


@shared_task(queue='ai_tasks')
def task_refresh_user_segments(tenant_id=None):
    """
    User segments re-cluster করো।
    Schedule: প্রতিদিন রাত 3 টায়।
    """
    from .PERSONALIZATION.user_segmentation import UserSegmentationEngine

    engine = UserSegmentationEngine()
    result = engine.run_segmentation(tenant_id=tenant_id)
    logger.info(f"[TASK] Segments refreshed: {result}")
    return result


# ══════════════════════════════════════════════════════════════════════
# DRIFT DETECTION TASKS
# ══════════════════════════════════════════════════════════════════════

@shared_task(queue='ai_tasks')
def task_detect_data_drift(tenant_id=None):
    """
    Production models এর data drift check করো।
    Schedule: প্রতি 12 ঘণ্টায়।
    """
    from .models import AIModel
    from .ML_PIPELINES.drift_detection_pipeline import DriftDetectionPipeline

    models = AIModel.objects.filter(status='deployed', is_production=True)
    if tenant_id:
        models = models.filter(tenant_id=tenant_id)

    results = []
    for model in models:
        try:
            pipeline = DriftDetectionPipeline(model)
            result = pipeline.run()
            results.append({'model': model.name, **result})
        except Exception as e:
            logger.error(f"Drift detection error for {model.name}: {e}")

    return {'checked': len(results), 'results': results}


# ══════════════════════════════════════════════════════════════════════
# CLEANUP TASKS
# ══════════════════════════════════════════════════════════════════════

@shared_task(queue='ai_tasks')
def task_cleanup_old_predictions(days: int = 90):
    """
    পুরনো prediction logs delete করো।
    Schedule: সপ্তাহে একবার।
    """
    from .models import PredictionLog
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = PredictionLog.objects.filter(created_at__lt=cutoff).delete()
    logger.info(f"[TASK] Deleted {deleted} old prediction logs (older than {days} days)")
    return {'deleted': deleted}


@shared_task(queue='ai_tasks')
def task_cleanup_old_anomalies(days: int = 180):
    """পুরনো resolved anomaly logs clean up।"""
    from .models import AnomalyDetectionLog
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = AnomalyDetectionLog.objects.filter(
        status__in=['resolved', 'false_positive'],
        created_at__lt=cutoff
    ).delete()
    logger.info(f"[TASK] Deleted {deleted} old anomaly logs")
    return {'deleted': deleted}
