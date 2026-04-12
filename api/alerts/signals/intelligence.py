"""
Intelligence Signals
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
        # Set default values if not provided
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
            instance.model_type = 'statistical'
        
        # Validate correlation type
        valid_types = ['temporal', 'pattern', 'causal', 'statistical', 'ml_based']
        if instance.correlation_type not in valid_types:
            logger.warning(f"Invalid correlation type '{instance.correlation_type}' for AlertCorrelation {instance.id}")
        
        # Validate status
        valid_statuses = ['pending', 'analyzing', 'confirmed', 'rejected', 'expired']
        if instance.status not in valid_statuses:
            logger.warning(f"Invalid status '{instance.status}' for AlertCorrelation {instance.id}")
        
        # Validate model type
        valid_models = ['statistical', 'ml_linear', 'ml_tree', 'ml_neural', 'ensemble']
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
            
            # Trigger correlation analysis
            from ..tasks.intelligence import analyze_all_correlations
            analyze_all_correlations.delay()
            
        else:
            logger.debug(f"Updated AlertCorrelation: {instance.name}")
            
            # Re-analyze if configuration changed
            if instance.status == 'pending':
                from ..tasks.intelligence import train_correlation_model
                train_correlation_model.delay(instance.id)
            
    except Exception as e:
        logger.error(f"Error in alert_correlation_post_save: {e}")


@receiver(pre_save, sender=AlertPrediction)
def alert_prediction_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertPrediction"""
    try:
        # Set default values if not provided
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
        
        # Validate prediction type
        valid_types = ['volume', 'severity', 'frequency', 'trend', 'anomaly']
        if instance.prediction_type not in valid_types:
            logger.warning(f"Invalid prediction type '{instance.prediction_type}' for AlertPrediction {instance.id}")
        
        # Validate model type
        valid_models = ['linear_regression', 'arima', 'lstm', 'prophet', 'ensemble']
        if instance.model_type not in valid_models:
            logger.warning(f"Invalid model type '{instance.model_type}' for AlertPrediction {instance.id}")
        
        # Validate training status
        valid_statuses = ['pending', 'training', 'completed', 'failed', 'updating']
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
            
            # Trigger model training
            from ..tasks.intelligence import train_prediction_models
            train_prediction_models.delay()
            
        else:
            logger.debug(f"Updated AlertPrediction: {instance.name}")
            
            # Retrain if configuration changed
            if instance.training_status == 'pending':
                from ..tasks.intelligence import test_prediction_model
                test_prediction_model.delay(instance.id)
            
    except Exception as e:
        logger.error(f"Error in alert_prediction_post_save: {e}")


@receiver(pre_save, sender=AnomalyDetectionModel)
def anomaly_detection_model_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AnomalyDetectionModel"""
    try:
        # Set default values if not provided
        if not instance.detection_method:
            instance.detection_method = 'statistical'
        
        if not instance.sensitivity:
            instance.sensitivity = 0.95
        
        if not instance.window_size_minutes:
            instance.window_size_minutes = 60
        
        if not instance.baseline_days:
            instance.baseline_days = 30
        
        if not instance.anomaly_threshold:
            instance.anomaly_threshold = 3.0  # 3 standard deviations
        
        if not instance.min_alert_count:
            instance.min_alert_count = 5
        
        if not instance.is_active:
            instance.is_active = True
        
        # Validate detection method
        valid_methods = ['statistical', 'ml_isolation_forest', 'ml_one_class_svm', 'time_series', 'threshold_based']
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
            
            # Trigger anomaly detection
            from ..tasks.intelligence import detect_anomalies
            detect_anomalies.delay()
            
        else:
            logger.debug(f"Updated AnomalyDetectionModel: {instance.name}")
            
            # Update thresholds if sensitivity changed
            if instance.is_active:
                from ..tasks.intelligence import update_anomaly_thresholds
                update_anomaly_thresholds.delay()
            
    except Exception as e:
        logger.error(f"Error in anomaly_detection_model_post_save: {e}")


@receiver(pre_save, sender=AlertNoise)
def alert_noise_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AlertNoise"""
    try:
        # Set default values if not provided
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
        
        # Validate noise type
        valid_types = ['repeated', 'low_priority', 'known_issue', 'maintenance', 'test_environment', 'configuration_error']
        if instance.noise_type not in valid_types:
            logger.warning(f"Invalid noise type '{instance.noise_type}' for AlertNoise {instance.id}")
        
        # Validate action
        valid_actions = ['suppress', 'group', 'delay', 'escalate', 'filter']
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
            
            # Trigger noise filter optimization
            from ..tasks.intelligence import optimize_noise_filters
            optimize_noise_filters.delay()
            
        else:
            logger.debug(f"Updated AlertNoise: {instance.name}")
            
            # Update effectiveness if configuration changed
            if instance.is_active:
                from ..tasks.intelligence import update_noise_effectiveness
                update_noise_effectiveness.delay()
            
    except Exception as e:
        logger.error(f"Error in alert_noise_post_save: {e}")


@receiver(pre_save, sender=RootCauseAnalysis)
def root_cause_analysis_pre_save(sender, instance, **kwargs):
    """Signal handler before saving RootCauseAnalysis"""
    try:
        # Set default values if not provided
        if not instance.analysis_method:
            instance.analysis_method = '5_whys'
        
        if not instance.confidence_level:
            instance.confidence_level = 'medium'
        
        if not instance.status:
            instance.status = 'draft'
        
        if not instance.internal_only:
            instance.internal_only = True
        
        # Validate analysis method
        valid_methods = ['5_whys', 'fishbone', 'fault_tree', 'pareto', 'statistical', 'ml_based']
        if instance.analysis_method not in valid_methods:
            logger.warning(f"Invalid analysis method '{instance.analysis_method}' for RootCauseAnalysis {instance.id}")
        
        # Validate confidence level
        valid_levels = ['low', 'medium', 'high', 'very_high']
        if instance.confidence_level not in valid_levels:
            logger.warning(f"Invalid confidence level '{instance.confidence_level}' for RootCauseAnalysis {instance.id}")
        
        # Validate status
        valid_statuses = ['draft', 'in_progress', 'completed', 'submitted_for_review', 'approved', 'rejected']
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
            
            # Trigger RCA analysis
            from ..tasks.intelligence import create_rca_for_incidents
            create_rca_for_incidents.delay()
            
        else:
            logger.debug(f"Updated RootCauseAnalysis: {instance.title}")
            
            # Generate recommendations if completed
            if instance.status == 'completed':
                from ..tasks.intelligence import generate_intelligence_dashboard_data
                generate_intelligence_dashboard_data.delay()
            
    except Exception as e:
        logger.error(f"Error in root_cause_analysis_post_save: {e}")


# Custom signal handlers for intelligence business logic
def trigger_correlation_analysis(alert_log):
    """Custom function to trigger correlation analysis for an alert"""
    try:
        logger.info(f"Triggering correlation analysis for alert {alert_log.id}")
        
        # Get active correlations that might match this alert
        from ..models.intelligence import AlertCorrelation
        
        correlations = AlertCorrelation.objects.filter(
            status='confirmed',
            primary_rules=alert_log.rule
        )
        
        for correlation in correlations:
            if correlation.predict_correlation(alert_log):
                # Create correlation event
                from ..models.core import Notification
                
                notification = Notification.objects.create(
                    notification_type='email',
                    recipient="intelligence_team",  # Would be resolved by routing
                    subject=f"Alert Correlation Detected: {correlation.name}",
                    message=f"Alert {alert_log.id} correlates with pattern: {correlation.name}",
                    status='pending'
                )
                
                # Trigger notification sending
                from ..tasks.notification import send_pending_notifications
                send_pending_notifications.delay()
                
    except Exception as e:
        logger.error(f"Error in trigger_correlation_analysis: {e}")


def trigger_prediction_update(prediction_model):
    """Custom function to trigger prediction model update"""
    try:
        logger.info(f"Triggering prediction update for model {prediction_model.name}")
        
        # Retrain the model
        from ..tasks.intelligence import train_prediction_models
        train_prediction_models.delay()
        
        # Update accuracy metrics
        from ..tasks.intelligence import update_prediction_accuracy_metrics
        update_prediction_accuracy_metrics.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_prediction_update: {e}")


def trigger_anomaly_detection(anomaly_model, alert_data):
    """Custom function to trigger anomaly detection"""
    try:
        logger.info(f"Triggering anomaly detection for model {anomaly_model.name}")
        
        # Run anomaly detection
        from ..tasks.intelligence import detect_anomalies
        detect_anomalies.delay()
        
        # Generate anomaly report
        from ..tasks.intelligence import generate_anomaly_report
        generate_anomaly_report.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_anomaly_detection: {e}")


def trigger_noise_filter_evaluation(noise_filter, alert_log):
    """Custom function to trigger noise filter evaluation"""
    try:
        logger.info(f"Evaluating noise filter {noise_filter.name} for alert {alert_log.id}")
        
        # Process alert through noise filter
        result = noise_filter.process_alert(alert_log)
        
        if result:
            # Create noise filter event
            from ..models.core import Notification
            
            notification = Notification.objects.create(
                notification_type='email',
                recipient="intelligence_team",  # Would be resolved by routing
                subject=f"Noise Filter Applied: {noise_filter.name}",
                message=f"Alert {alert_log.id} processed by noise filter: {result['action']} - {result.get('reason', '')}",
                status='pending'
            )
            
            # Trigger notification sending
            from ..tasks.notification import send_pending_notifications
            send_pending_notifications.delay()
            
    except Exception as e:
        logger.error(f"Error in trigger_noise_filter_evaluation: {e}")


def trigger_rca_analysis(incident, analysis_data=None):
    """Custom function to trigger RCA analysis"""
    try:
        logger.info(f"Triggering RCA analysis for incident {incident.title}")
        
        # Create or update RCA
        from ..tasks.intelligence import create_rca_for_incidents
        rca_id = create_rca_for_incidents.delay(incident.id, analysis_data or {})
        
        # Generate intelligence dashboard update
        from ..tasks.intelligence import generate_intelligence_dashboard_data
        generate_intelligence_dashboard_data.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_rca_analysis: {e}")


def trigger_intelligence_pipeline():
    """Custom function to trigger complete intelligence pipeline"""
    try:
        logger.info("Triggering complete intelligence pipeline")
        
        # Run pipeline
        from ..tasks.intelligence import run_intelligence_pipeline
        run_intelligence_pipeline.delay()
        
        # Generate dashboard data
        from ..tasks.intelligence import generate_intelligence_dashboard_data
        generate_intelligence_dashboard_data.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_intelligence_pipeline: {e}")


def trigger_model_optimization():
    """Custom function to trigger model optimization"""
    try:
        logger.info("Triggering intelligence model optimization")
        
        # Optimize all models
        from ..tasks.intelligence import optimize_intelligence_models
        optimize_intelligence_models.delay()
        
        # Update accuracy metrics
        from ..tasks.intelligence import update_prediction_accuracy_metrics
        update_prediction_accuracy_metrics.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_model_optimization: {e}")


def trigger_intelligence_cleanup():
    """Custom function to trigger intelligence data cleanup"""
    try:
        logger.info("Triggering intelligence data cleanup")
        
        # Clean up old data
        from ..tasks.intelligence import cleanup_old_intelligence_data
        cleanup_old_intelligence_data.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_intelligence_cleanup: {e}")


# Signal registration
def register_intelligence_signals():
    """Register all intelligence signals"""
    try:
        logger.info("Intelligence signals registered successfully")
    except Exception as e:
        logger.error(f"Error registering intelligence signals: {e}")


# Auto-register signals when module is imported
register_intelligence_signals()
