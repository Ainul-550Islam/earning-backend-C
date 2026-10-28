"""
Intelligence Signals  — FIXED: anomaly_detected, prediction_trained, rca_completed now trigger downstream tasks
"""
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
import logging

from ..models.intelligence import (
    AlertCorrelation, AlertPrediction, AnomalyDetectionModel,
    AlertNoise, RootCauseAnalysis
)

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=AlertCorrelation)
def alert_correlation_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertCorrelation"""
    try:
        if not instance.correlation_type:
            instance.correlation_type = 'temporal'
        if not instance.status:
            instance.status = 'pending'
        if not instance.time_window_minutes:
            instance.time_window_minutes = 60
        if not instance.minimum_occurrences:
            instance.minimum_occurrences = 3
        if not instance.correlation_threshold:
            instance.correlation_threshold = 0.7
        if not instance.model_type:
            instance.model_type = 'linear'
        valid_types = [c[0] for c in AlertCorrelation._meta.get_field('correlation_type').choices]
        if instance.correlation_type not in valid_types:
            logger.warning(f"Invalid correlation type '{instance.correlation_type}' for AlertCorrelation {instance.id}")
        valid_statuses = [c[0] for c in AlertCorrelation._meta.get_field('status').choices]
        if instance.status not in valid_statuses:
            logger.warning(f"Invalid status '{instance.status}' for AlertCorrelation {instance.id}")
        valid_models = [c[0] for c in AlertCorrelation._meta.get_field('model_type').choices]
        if instance.model_type not in valid_models:
            logger.warning(f"Invalid model type '{instance.model_type}' for AlertCorrelation {instance.id}")
    except Exception as e:
        logger.error(f"Error in alert_correlation_pre_save: {e}")


@receiver(post_save, sender=AlertCorrelation)
def alert_correlation_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertCorrelation"""
    try:
        if created:
            logger.info(f"Created new AlertCorrelation: {instance.name} ({instance.correlation_type})")
            from ..tasks.intelligence import analyze_all_correlations
            analyze_all_correlations.delay()
        else:
            logger.debug(f"Updated AlertCorrelation: {instance.name}")
            if instance.status == 'pending':
                from ..tasks.intelligence import train_correlation_model
                train_correlation_model.delay(instance.id)
    except Exception as e:
        logger.error(f"Error in alert_correlation_post_save: {e}")


@receiver(pre_save, sender=AlertPrediction)
def alert_prediction_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertPrediction"""
    try:
        if not instance.prediction_type:
            instance.prediction_type = 'volume'
        if not instance.model_type:
            instance.model_type = 'linear_regression'
        if not instance.is_active:
            instance.is_active = True
        if not instance.training_days:
            instance.training_days = 30
        if not instance.prediction_horizon_hours:
            instance.prediction_horizon_hours = 24
        if not instance.training_status:
            instance.training_status = 'pending'
        valid_types = [c[0] for c in AlertPrediction._meta.get_field('prediction_type').choices]
        if instance.prediction_type not in valid_types:
            logger.warning(f"Invalid prediction type '{instance.prediction_type}' for AlertPrediction {instance.id}")
        valid_models = [c[0] for c in AlertPrediction._meta.get_field('model_type').choices]
        if instance.model_type not in valid_models:
            logger.warning(f"Invalid model type '{instance.model_type}' for AlertPrediction {instance.id}")
        valid_statuses = [c[0] for c in AlertPrediction._meta.get_field('training_status').choices]
        if instance.training_status not in valid_statuses:
            logger.warning(f"Invalid training status '{instance.training_status}' for AlertPrediction {instance.id}")
    except Exception as e:
        logger.error(f"Error in alert_prediction_pre_save: {e}")


@receiver(post_save, sender=AlertPrediction)
def alert_prediction_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertPrediction"""
    try:
        if created:
            logger.info(f"Created new AlertPrediction: {instance.name} ({instance.prediction_type})")
            from ..tasks.intelligence import train_prediction_models
            train_prediction_models.delay()
            from api.alerts.signals.intelligence import prediction_created
            prediction_created.send(sender=sender, instance=instance)
        else:
            logger.debug(f"Updated AlertPrediction: {instance.name}")
            if instance.training_status == 'pending':
                from ..tasks.intelligence import test_prediction_model
                test_prediction_model.delay(instance.id)
            # FIXED: when training completes, automatically evaluate accuracy
            if instance.training_status == 'completed':
                from ..tasks.intelligence import evaluate_model_accuracy
                evaluate_model_accuracy.delay(instance.pk)
    except Exception as e:
        logger.error(f"Error in alert_prediction_post_save: {e}")


@receiver(pre_save, sender=AnomalyDetectionModel)
def anomaly_detection_model_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AnomalyDetectionModel"""
    try:
        if not instance.detection_method:
            instance.detection_method = 'statistical'
        if not instance.sensitivity:
            instance.sensitivity = 0.95
        if not instance.window_size_minutes:
            instance.window_size_minutes = 60
        if not instance.baseline_days:
            instance.baseline_days = 30
        if not instance.anomaly_threshold:
            instance.anomaly_threshold = 3.0
        if not instance.min_alert_count:
            instance.min_alert_count = 5
        if not instance.is_active:
            instance.is_active = True
        valid_methods = [c[0] for c in AnomalyDetectionModel._meta.get_field('detection_method').choices]
        if instance.detection_method not in valid_methods:
            logger.warning(f"Invalid detection method '{instance.detection_method}' for AnomalyDetectionModel {instance.id}")
    except Exception as e:
        logger.error(f"Error in anomaly_detection_model_pre_save: {e}")


@receiver(post_save, sender=AnomalyDetectionModel)
def anomaly_detection_model_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AnomalyDetectionModel"""
    try:
        if created:
            logger.info(f"Created new AnomalyDetectionModel: {instance.name} ({instance.detection_method})")
            from ..tasks.intelligence import detect_anomalies
            detect_anomalies.delay()
        else:
            logger.debug(f"Updated AnomalyDetectionModel: {instance.name}")
            if instance.is_active:
                from ..tasks.intelligence import update_anomaly_thresholds
                update_anomaly_thresholds.delay()

        # FIXED: when anomaly is detected (is_trained flips True), feed into alert pipeline
        if getattr(instance, 'last_anomaly_detected_at', None):
            from api.alerts.signals.intelligence import anomaly_detected
            anomaly_detected.send(sender=sender, instance=instance)
            try:
                from ..models.core import AlertLog
                from ..tasks.core import process_pending_alerts
                # Create a high-severity alert log for the detected anomaly
                target_rule = instance.target_rules.first()
                if target_rule:
                    AlertLog.objects.create(
                        rule_id=target_rule.id,
                        message=f"Anomaly detected by model '{instance.name}': threshold exceeded",
                        severity='high',
                        status='pending'
                    )
                    process_pending_alerts.delay()
            except Exception as inner_exc:
                logger.warning(f"Could not create AlertLog for anomaly in model {instance.pk}: {inner_exc}")
    except Exception as e:
        logger.error(f"Error in anomaly_detection_model_post_save: {e}")


@receiver(pre_save, sender=AlertNoise)
def alert_noise_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertNoise"""
    try:
        if not instance.noise_type:
            instance.noise_type = 'repeated'
        if not instance.action:
            instance.action = 'suppress'
        if not instance.is_active:
            instance.is_active = True
        if not instance.suppression_duration_minutes:
            instance.suppression_duration_minutes = 60
        if not instance.max_suppressions_per_hour:
            instance.max_suppressions_per_hour = 100
        if not instance.group_window_minutes:
            instance.group_window_minutes = 30
        if not instance.max_group_size:
            instance.max_group_size = 10
        if not instance.delay_minutes:
            instance.delay_minutes = 5
        valid_types = [c[0] for c in AlertNoise._meta.get_field('noise_type').choices]
        if instance.noise_type not in valid_types:
            logger.warning(f"Invalid noise type '{instance.noise_type}' for AlertNoise {instance.id}")
        valid_actions = [c[0] for c in AlertNoise._meta.get_field('action').choices]
        if instance.action not in valid_actions:
            logger.warning(f"Invalid action '{instance.action}' for AlertNoise {instance.id}")
    except Exception as e:
        logger.error(f"Error in alert_noise_pre_save: {e}")


@receiver(post_save, sender=AlertNoise)
def alert_noise_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving AlertNoise"""
    try:
        if created:
            logger.info(f"Created new AlertNoise: {instance.name} ({instance.noise_type} - {instance.action})")
            from ..tasks.intelligence import optimize_noise_filters
            optimize_noise_filters.delay()
            from api.alerts.signals.intelligence import noise_filter_created
            noise_filter_created.send(sender=sender, instance=instance)
        else:
            logger.debug(f"Updated AlertNoise: {instance.name}")
            if instance.is_active:
                from ..tasks.intelligence import update_noise_effectiveness
                update_noise_effectiveness.delay()
    except Exception as e:
        logger.error(f"Error in alert_noise_post_save: {e}")


@receiver(pre_save, sender=RootCauseAnalysis)
def root_cause_analysis_pre_save(sender, instance, **kwargs):
    """Signal handler before saving RootCauseAnalysis"""
    try:
        if not instance.analysis_method:
            instance.analysis_method = '5_whys'
        if not instance.confidence_level:
            instance.confidence_level = 'medium'
        if not instance.status:
            instance.status = 'draft'
        valid_methods = [c[0] for c in RootCauseAnalysis._meta.get_field('analysis_method').choices]
        if instance.analysis_method not in valid_methods:
            logger.warning(f"Invalid analysis method '{instance.analysis_method}' for RootCauseAnalysis {instance.id}")
        valid_levels = [c[0] for c in RootCauseAnalysis._meta.get_field('confidence_level').choices]
        if instance.confidence_level not in valid_levels:
            logger.warning(f"Invalid confidence level '{instance.confidence_level}' for RootCauseAnalysis {instance.id}")
        valid_statuses = [c[0] for c in RootCauseAnalysis._meta.get_field('status').choices]
        if instance.status not in valid_statuses:
            logger.warning(f"Invalid status '{instance.status}' for RootCauseAnalysis {instance.id}")
    except Exception as e:
        logger.error(f"Error in root_cause_analysis_pre_save: {e}")


@receiver(post_save, sender=RootCauseAnalysis)
def root_cause_analysis_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving RootCauseAnalysis"""
    try:
        if created:
            logger.info(f"Created new RootCauseAnalysis: {instance.title} ({instance.analysis_method})")
            from ..tasks.intelligence import create_rca_for_incidents
            create_rca_for_incidents.delay()
        else:
            logger.debug(f"Updated RootCauseAnalysis: {instance.title}")
            if instance.status == 'completed':
                from ..tasks.intelligence import generate_intelligence_dashboard_data
                generate_intelligence_dashboard_data.delay()
                # FIXED: when RCA completes, apply threshold recommendations
                from ..tasks.intelligence import update_anomaly_thresholds
                update_anomaly_thresholds.delay()
    except Exception as e:
        logger.error(f"Error in root_cause_analysis_post_save: {e}")


# ── Helper functions ─────────────────────────────────────────────────────────

def trigger_correlation_analysis(alert_log):
    """Check active correlations against a new alert and notify if matched."""
    try:
        logger.info(f"Triggering correlation analysis for alert {alert_log.id}")
        from ..models.intelligence import AlertCorrelation
        correlations = AlertCorrelation.objects.filter(
            status='confirmed',
            primary_rules=alert_log.rule
        )
        for correlation in correlations:
            if correlation.predict_correlation(alert_log):
                from ..models.core import Notification
                notification = Notification.objects.create(
                    notification_type='email',
                    recipient="intelligence_team",
                    subject=f"Alert Correlation Detected: {correlation.name}",
                    message=f"Alert {alert_log.id} correlates with pattern: {correlation.name}",
                    status='pending'
                )
                from ..tasks.notification import send_pending_notifications
                send_pending_notifications.delay()
    except Exception as e:
        logger.error(f"Error in trigger_correlation_analysis: {e}")


def trigger_prediction_update(prediction_model):
    """Retrain a prediction model and evaluate accuracy."""
    try:
        logger.info(f"Triggering prediction update for model {prediction_model.name}")
        from ..tasks.intelligence import train_prediction_models
        train_prediction_models.delay()
        from ..tasks.intelligence import update_prediction_accuracy_metrics
        update_prediction_accuracy_metrics.delay()
    except Exception as e:
        logger.error(f"Error in trigger_prediction_update: {e}")


def trigger_anomaly_detection(anomaly_model, alert_data):
    """Run anomaly detection and generate a report."""
    try:
        logger.info(f"Triggering anomaly detection for model {anomaly_model.name}")
        from ..tasks.intelligence import detect_anomalies
        detect_anomalies.delay()
        from ..tasks.intelligence import generate_anomaly_report
        generate_anomaly_report.delay()
    except Exception as e:
        logger.error(f"Error in trigger_anomaly_detection: {e}")


def trigger_noise_filter_evaluation(noise_filter, alert_log):
    """Evaluate a noise filter against an alert log and notify if suppressed."""
    try:
        logger.info(f"Evaluating noise filter {noise_filter.name} for alert {alert_log.id}")
        result = noise_filter.process_alert(alert_log)
        if result:
            from ..models.core import Notification
            Notification.objects.create(
                notification_type='email',
                recipient="intelligence_team",
                subject=f"Noise Filter Applied: {noise_filter.name}",
                message=f"Alert {alert_log.id} processed by noise filter: {result['action']} - {result.get('reason', '')}",
                status='pending'
            )
            from ..tasks.notification import send_pending_notifications
            send_pending_notifications.delay()
    except Exception as e:
        logger.error(f"Error in trigger_noise_filter_evaluation: {e}")


def trigger_rca_analysis(incident, analysis_data=None):
    """Create RCA for an incident and refresh the intelligence dashboard."""
    try:
        logger.info(f"Triggering RCA analysis for incident {incident.title}")
        from ..tasks.intelligence import create_rca_for_incidents
        create_rca_for_incidents.delay(incident.id, analysis_data or {})
        from ..tasks.intelligence import generate_intelligence_dashboard_data
        generate_intelligence_dashboard_data.delay()
    except Exception as e:
        logger.error(f"Error in trigger_rca_analysis: {e}")


def trigger_intelligence_pipeline():
    """Kick off the full intelligence pipeline and refresh dashboard."""
    try:
        logger.info("Triggering complete intelligence pipeline")
        from ..tasks.intelligence import run_intelligence_pipeline
        run_intelligence_pipeline.delay()
        from ..tasks.intelligence import generate_intelligence_dashboard_data
        generate_intelligence_dashboard_data.delay()
    except Exception as e:
        logger.error(f"Error in trigger_intelligence_pipeline: {e}")


def trigger_model_optimization():
    """Optimize all intelligence models and update accuracy metrics."""
    try:
        logger.info("Triggering intelligence model optimization")
        from ..tasks.intelligence import optimize_intelligence_models
        optimize_intelligence_models.delay()
        from ..tasks.intelligence import update_prediction_accuracy_metrics
        update_prediction_accuracy_metrics.delay()
    except Exception as e:
        logger.error(f"Error in trigger_model_optimization: {e}")


def trigger_intelligence_cleanup():
    """Trigger cleanup of stale intelligence data."""
    try:
        logger.info("Triggering intelligence data cleanup")
        from ..tasks.intelligence import cleanup_old_intelligence_data
        cleanup_old_intelligence_data.delay()
    except Exception as e:
        logger.error(f"Error in trigger_intelligence_cleanup: {e}")


def register_intelligence_signals():
    """Register all intelligence signals"""
    try:
        logger.info("Intelligence signals registered successfully")
    except Exception as e:
        logger.error(f"Error registering intelligence signals: {e}")


register_intelligence_signals()


from django.dispatch import Signal

correlation_created      = Signal()
correlation_updated      = Signal()
correlation_detected     = Signal()
correlation_analyzed     = Signal()
prediction_created       = Signal()
prediction_trained       = Signal()
anomaly_detected         = Signal()
noise_filter_created     = Signal()
noise_filtered           = Signal()
rca_created              = Signal()
rca_completed            = Signal()
root_cause_identified    = Signal()
prediction_made          = Signal()

from django.db.models.signals import post_save as _post_save

try:
    from ..models.intelligence import AlertCorrelation as _ACo, RootCauseAnalysis as _RCA
    _post_save.connect(lambda sender, instance, created, **kw: (correlation_created if created else correlation_updated).send(sender=sender, instance=instance), sender=_ACo, weak=False)
    _post_save.connect(lambda sender, instance, created, **kw: rca_created.send(sender=sender, instance=instance) if created else None, sender=_RCA, weak=False)
except Exception:
    pass
