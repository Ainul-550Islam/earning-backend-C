"""
api/ai_engine/signals.py
=========================
AI Engine — Django Signals।
Model save/delete events এ auto-actions।
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import (
    AIModel, TrainingJob, PredictionLog,
    AnomalyDetectionLog, ChurnRiskProfile,
)
from . import cache as ai_cache

logger = logging.getLogger(__name__)


# ── AI Model Signals ─────────────────────────────────────────────────

@receiver(post_save, sender=AIModel)
def on_ai_model_save(sender, instance, created, **kwargs):
    """Model save হলে cache invalidate করো।"""
    ai_cache.invalidate_model_meta(str(instance.id))
    if created:
        logger.info(f"New AI Model created: {instance.name} [{instance.id}]")


@receiver(post_delete, sender=AIModel)
def on_ai_model_delete(sender, instance, **kwargs):
    ai_cache.invalidate_model_meta(str(instance.id))


# ── Training Job Signals ─────────────────────────────────────────────

@receiver(post_save, sender=TrainingJob)
def on_training_job_save(sender, instance, created, **kwargs):
    """Training complete হলে model status update।"""
    if instance.status == 'completed':
        logger.info(f"Training job completed: {instance.job_id}")
    elif instance.status == 'failed':
        logger.error(f"Training job failed: {instance.job_id} — {instance.error_message}")


# ── Anomaly Signals ──────────────────────────────────────────────────

@receiver(post_save, sender=AnomalyDetectionLog)
def on_anomaly_created(sender, instance, created, **kwargs):
    """Critical anomaly হলে alert পাঠাও।"""
    if created and instance.severity == 'critical':
        logger.critical(
            f"CRITICAL ANOMALY: {instance.anomaly_type} "
            f"score={instance.anomaly_score:.2f} "
            f"user={instance.user_id}"
        )
        # production এ: send_alert_notification.delay(str(instance.id))


# ── Churn Risk Signals ───────────────────────────────────────────────

@receiver(post_save, sender=ChurnRiskProfile)
def on_churn_profile_save(sender, instance, created, **kwargs):
    """Churn risk high হলে retention task queue করো।"""
    if instance.risk_level in ('high', 'very_high'):
        logger.info(
            f"High churn risk: user={instance.user_id} "
            f"prob={instance.churn_probability:.1%} "
            f"level={instance.risk_level}"
        )
        # production এ: trigger_retention_campaign.delay(str(instance.user_id))
