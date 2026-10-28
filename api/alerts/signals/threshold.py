"""
Threshold Signals  — FIXED: threshold_breach_created now triggers alert pipeline + process_pending_alerts
"""
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
import logging

from ..models.threshold import (
    ThresholdConfig, ThresholdBreach, AdaptiveThreshold,
    ThresholdHistory, ThresholdProfile
)

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=ThresholdConfig)
def threshold_config_pre_save(sender, instance, **kwargs):
    """Signal handler before saving ThresholdConfig"""
    try:
        if not instance.threshold_type:
            instance.threshold_type = 'static'
        if not getattr(instance, 'comparison_operator', None):
            instance.comparison_operator = 'gt'
        valid_types = [c[0] for c in ThresholdConfig._meta.get_field('threshold_type').choices]
        if instance.threshold_type not in valid_types:
            logger.warning(f"Invalid threshold type '{instance.threshold_type}' for ThresholdConfig {instance.id}")
        valid_operators = ['gt', 'gte', 'lt', 'lte', 'eq', 'ne', 'range', 'outside_range']
        cmp = getattr(instance, 'comparison_operator', 'gt')
        if cmp not in valid_operators:
            logger.warning(f"Invalid operator '{cmp}' for ThresholdConfig {instance.id}")
    except Exception as e:
        logger.error(f"Error in threshold_config_pre_save: {e}")


@receiver(post_save, sender=ThresholdConfig)
def threshold_config_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving ThresholdConfig"""
    try:
        if created:
            logger.info(f"Created new ThresholdConfig: {instance.threshold_type} for rule {instance.alert_rule.name}")
            if instance.threshold_type in ['adaptive', 'dynamic']:
                pass  # ThresholdHistory is only created when AdaptiveThreshold exists
        else:
            logger.debug(f"Updated ThresholdConfig: {instance.id}")
    except Exception as e:
        logger.error(f"Error in threshold_config_post_save: {e}")


@receiver(pre_save, sender=ThresholdBreach)
def threshold_breach_pre_save(sender, instance, **kwargs):
    """Signal handler before saving ThresholdBreach"""
    try:
        if not instance.detected_at:
            instance.detected_at = timezone.now()
        if not instance.severity:
            if instance.breach_percentage:
                if instance.breach_percentage > 200:
                    instance.severity = 'critical'
                elif instance.breach_percentage > 100:
                    instance.severity = 'high'
                elif instance.breach_percentage > 50:
                    instance.severity = 'medium'
                else:
                    instance.severity = 'low'
            else:
                instance.severity = 'medium'
        if not instance.breach_percentage and instance.threshold_value and instance.breach_value:
            instance.breach_percentage = (
                (instance.breach_value - instance.threshold_value) / instance.threshold_value
            ) * 100
    except Exception as e:
        logger.error(f"Error in threshold_breach_pre_save: {e}")


@receiver(post_save, sender=ThresholdBreach)
def threshold_breach_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving ThresholdBreach"""
    try:
        if created:
            logger.info(f"Created new ThresholdBreach: {instance.severity} severity, {instance.breach_percentage:.1f}% breach")
            if instance.severity == 'critical':
                from ..tasks.core import escalate_alerts
                escalate_alerts.delay()
            if instance.threshold_config.threshold_type == 'adaptive':
                from ..tasks.intelligence import update_anomaly_thresholds
                update_anomaly_thresholds.delay()
            # FIXED: trigger the alert pipeline so the breach produces a real-time alert
            from ..tasks.core import process_pending_alerts
            process_pending_alerts.delay()
            # FIXED: trigger breach notification immediately
            trigger_threshold_breach_notification(instance)
        else:
            logger.debug(f"Updated ThresholdBreach: {instance.id}")
    except Exception as e:
        logger.error(f"Error in threshold_breach_post_save: {e}")


@receiver(pre_save, sender=AdaptiveThreshold)
def adaptive_threshold_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AdaptiveThreshold"""
    try:
        if not instance.adaptation_method:
            instance.adaptation_method = 'exponential_smoothing'
        if not getattr(instance, 'adaptation_window_days', None):
            instance.adaptation_window_days = 30
        valid_methods = [c[0] for c in AdaptiveThreshold._meta.get_field('adaptation_method').choices]
        if instance.adaptation_method not in valid_methods:
            logger.warning(f"Invalid adaptation method '{instance.adaptation_method}' for AdaptiveThreshold {instance.id}")
    except Exception as e:
        logger.error(f"Error in adaptive_threshold_pre_save: {e}")


@receiver(post_save, sender=AdaptiveThreshold)
def adaptive_threshold_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AdaptiveThreshold"""
    try:
        if created:
            logger.info(f"Created new AdaptiveThreshold: {instance.adaptation_method} for config {instance.threshold_config.name}")
            from ..tasks.intelligence import train_prediction_models
            train_prediction_models.delay()
        else:
            logger.debug(f"Updated AdaptiveThreshold: {instance.id}")
            # FIXED: when threshold value changes, re-evaluate active rules immediately
            from ..tasks.adaptive_threshold_tasks import recalculate_adaptive_thresholds
            recalculate_adaptive_thresholds.delay()
    except Exception as e:
        logger.error(f"Error in adaptive_threshold_post_save: {e}")


@receiver(pre_save, sender=ThresholdHistory)
def threshold_history_pre_save(sender, instance, **kwargs):
    """Signal handler before saving ThresholdHistory"""
    try:
        if not instance.created_at:
            instance.created_at = timezone.now()
        if not instance.change_percentage and instance.old_threshold and instance.new_threshold:
            instance.change_percentage = (
                (instance.new_threshold - instance.old_threshold) / instance.old_threshold
            ) * 100
    except Exception as e:
        logger.error(f"Error in threshold_history_pre_save: {e}")


@receiver(post_save, sender=ThresholdHistory)
def threshold_history_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving ThresholdHistory"""
    try:
        if created:
            logger.info(f"Created ThresholdHistory: {instance.change_type} - {instance.change_percentage:.1f}% change")
            from api.alerts.signals.threshold import threshold_history_created
            threshold_history_created.send(sender=sender, instance=instance)
            if instance.adaptive_threshold:
                instance.adaptive_threshold.last_adaptation = instance.created_at
                instance.adaptive_threshold.adaptation_count += 1
                instance.adaptive_threshold.save(update_fields=['last_adaptation', 'adaptation_count'])
        else:
            logger.debug(f"Updated ThresholdHistory: {instance.id}")
    except Exception as e:
        logger.error(f"Error in threshold_history_post_save: {e}")


@receiver(pre_save, sender=ThresholdProfile)
def threshold_profile_pre_save(sender, instance, **kwargs):
    """Signal handler before saving ThresholdProfile"""
    try:
        if not instance.profile_type:
            instance.profile_type = 'general'
        if not instance.is_default:
            instance.is_default = False
        if not instance.is_active:
            instance.is_active = True
        valid_types = [c[0] for c in ThresholdProfile._meta.get_field('profile_type').choices]
        if instance.profile_type not in valid_types:
            logger.warning(f"Invalid profile type '{instance.profile_type}' for ThresholdProfile {instance.id}")
    except Exception as e:
        logger.error(f"Error in threshold_profile_pre_save: {e}")


@receiver(post_save, sender=ThresholdProfile)
def threshold_profile_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving ThresholdProfile"""
    try:
        if created:
            logger.info(f"Created new ThresholdProfile: {instance.name} ({instance.profile_type})")
            if instance.is_default:
                ThresholdProfile.objects.filter(
                    profile_type=instance.profile_type,
                    is_default=True
                ).exclude(id=instance.id).update(is_default=False)
        else:
            logger.debug(f"Updated ThresholdProfile: {instance.name}")
    except Exception as e:
        logger.error(f"Error in threshold_profile_post_save: {e}")


# ── Helper functions ─────────────────────────────────────────────────────────

def trigger_threshold_adaptation(threshold_config, breach_data):
    """Trigger adaptive threshold retraining when a breach occurs."""
    try:
        if threshold_config.threshold_type == 'adaptive':
            adaptive_threshold = threshold_config.adaptive_thresholds.first()
            if adaptive_threshold:
                from ..tasks.intelligence import train_correlation_model
                train_correlation_model.delay(adaptive_threshold.id)
                logger.info(f"Triggered adaptation for threshold config {threshold_config.id}")
    except Exception as e:
        logger.error(f"Error in trigger_threshold_adaptation: {e}")


def trigger_threshold_breach_notification(threshold_breach):
    """Create and send a notification for a threshold breach."""
    try:
        logger.info(f"Triggering notification for threshold breach {threshold_breach.id}")
        from ..models.core import Notification
        notification = Notification.objects.create(
            alert_log=threshold_breach.alert_log,
            notification_type='email',
            recipient="threshold_team",
            subject=f"Threshold Breach Alert: {threshold_breach.threshold_config.name}",
            message=(
                f"Threshold breach detected: {threshold_breach.breach_value} > "
                f"{threshold_breach.threshold_value} ({threshold_breach.breach_percentage:.1f}%)"
            ),
            status='pending'
        )
        from ..tasks.notification import send_pending_notifications
        send_pending_notifications.delay()
        return notification
    except Exception as e:
        logger.error(f"Error in trigger_threshold_breach_notification: {e}")
        return None


def trigger_threshold_profile_application(threshold_config, threshold_profile):
    """Apply a profile's settings to a ThresholdConfig and record the history."""
    try:
        logger.info(f"Applying threshold profile {threshold_profile.name} to config {threshold_config.id}")
        effective_settings = threshold_profile.get_effective_settings(threshold_config.alert_rule.alert_type)
        if effective_settings:
            old_primary = threshold_config.primary_threshold
            threshold_config.primary_threshold = effective_settings.get('primary_threshold', threshold_config.primary_threshold)
            threshold_config.secondary_threshold = effective_settings.get('secondary_threshold', threshold_config.secondary_threshold)
            threshold_config.save(update_fields=['primary_threshold', 'secondary_threshold'])
            ThresholdHistory.objects.create(
                adaptive_threshold=None,
                change_type='profile_applied',
                old_threshold=old_primary,
                new_threshold=effective_settings.get('primary_threshold'),
                reason=f"Applied profile: {threshold_profile.name}"
            )
            logger.info(f"Successfully applied threshold profile {threshold_profile.name}")
    except Exception as e:
        logger.error(f"Error in trigger_threshold_profile_application: {e}")


def trigger_threshold_analysis(threshold_config):
    """Analyse recent breaches and regenerate performance reports."""
    try:
        logger.info(f"Triggering analysis for threshold config {threshold_config.id}")
        from ..tasks.intelligence import optimize_noise_filters
        optimize_noise_filters.delay()
        from ..tasks.reporting import generate_performance_reports
        generate_performance_reports.delay()
    except Exception as e:
        logger.error(f"Error in trigger_threshold_analysis: {e}")


def trigger_threshold_cleanup():
    """Clean up stale threshold history records."""
    try:
        from ..tasks.intelligence import cleanup_old_intelligence_data
        cleanup_old_intelligence_data.delay()
        logger.info("Triggered threshold data cleanup")
    except Exception as e:
        logger.error(f"Error in trigger_threshold_cleanup: {e}")


def register_threshold_signals():
    """Register all threshold signals"""
    try:
        logger.info("Threshold signals registered successfully")
    except Exception as e:
        logger.error(f"Error registering threshold signals: {e}")


register_threshold_signals()


from django.dispatch import Signal

threshold_config_created   = Signal()
threshold_config_updated   = Signal()
threshold_breach_created   = Signal()
threshold_breach_resolved  = Signal()
threshold_breach_acknowledged = Signal()
adaptive_threshold_created = Signal()
adaptive_threshold_updated = Signal()
threshold_history_created  = Signal()
threshold_profile_created  = Signal()
threshold_profile_applied  = Signal()

from django.db.models.signals import post_save as _post_save

def _fire_config(sender, instance, created, **kw):
    (threshold_config_created if created else threshold_config_updated).send(sender=sender, instance=instance)

def _fire_breach(sender, instance, created, **kw):
    if created:
        threshold_breach_created.send(sender=sender, instance=instance)
    elif getattr(instance, 'status', '') == 'resolved':
        threshold_breach_resolved.send(sender=sender, instance=instance)

try:
    from ..models.threshold import ThresholdConfig as _TC, ThresholdBreach as _TB
    from ..models.threshold import AdaptiveThreshold as _AT, ThresholdProfile as _TP
    _post_save.connect(_fire_config, sender=_TC, weak=False)
    _post_save.connect(_fire_breach, sender=_TB, weak=False)
    _post_save.connect(lambda sender, instance, created, **kw: adaptive_threshold_created.send(sender=sender, instance=instance) if created else adaptive_threshold_updated.send(sender=sender, instance=instance), sender=_AT, weak=False)
    _post_save.connect(lambda sender, instance, created, **kw: threshold_profile_created.send(sender=sender, instance=instance) if created else None, sender=_TP, weak=False)
except Exception:
    pass
