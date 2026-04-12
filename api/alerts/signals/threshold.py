"""
Threshold Signals
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
        # Set default values if not provided
        if not instance.threshold_type:
            instance.threshold_type = 'static'
        
        if not instance.operator:
            instance.operator = 'greater_than'
        
        if not instance.time_window_minutes:
            instance.time_window_minutes = 60
        
        # Validate threshold type
        valid_types = ['static', 'dynamic', 'adaptive', 'composite']
        if instance.threshold_type not in valid_types:
            logger.warning(f"Invalid threshold type '{instance.threshold_type}' for ThresholdConfig {instance.id}")
        
        # Validate operator
        valid_operators = ['greater_than', 'less_than', 'equals', 'greater_than_or_equal', 'less_than_or_equal']
        if instance.operator not in valid_operators:
            logger.warning(f"Invalid operator '{instance.operator}' for ThresholdConfig {instance.id}")
            
    except Exception as e:
        logger.error(f"Error in threshold_config_pre_save: {e}")


@receiver(post_save, sender=ThresholdConfig)
def threshold_config_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving ThresholdConfig"""
    try:
        if created:
            logger.info(f"Created new ThresholdConfig: {instance.threshold_type} for rule {instance.alert_rule.name}")
            
            # Create initial threshold history if adaptive
            if instance.threshold_type in ['adaptive', 'dynamic']:
                ThresholdHistory.objects.create(
                    adaptive_threshold=None,
                    change_type='created',
                    old_threshold=0,
                    new_threshold=instance.primary_threshold,
                    reason="Initial configuration"
                )
        else:
            logger.debug(f"Updated ThresholdConfig: {instance.id}")
            
    except Exception as e:
        logger.error(f"Error in threshold_config_post_save: {e}")


@receiver(pre_save, sender=ThresholdBreach)
def threshold_breach_pre_save(sender, instance, **kwargs):
    """Signal handler before saving ThresholdBreach"""
    try:
        # Set default values if not provided
        if not instance.detected_at:
            instance.detected_at = timezone.now()
        
        if not instance.severity:
            # Calculate severity based on breach percentage
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
        
        # Calculate breach percentage if not set
        if not instance.breach_percentage and instance.threshold_value and instance.breach_value:
            instance.breach_percentage = ((instance.breach_value - instance.threshold_value) / instance.threshold_value) * 100
            
    except Exception as e:
        logger.error(f"Error in threshold_breach_pre_save: {e}")


@receiver(post_save, sender=ThresholdBreach)
def threshold_breach_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving ThresholdBreach"""
    try:
        if created:
            logger.info(f"Created new ThresholdBreach: {instance.severity} severity, {instance.breach_percentage:.1f}% breach")
            
            # Trigger alert escalation if critical
            if instance.severity == 'critical':
                from ..tasks.core import escalate_alerts
                escalate_alerts.delay()
                
            # Update adaptive threshold if applicable
            if instance.threshold_config.threshold_type == 'adaptive':
                from ..tasks.intelligence import update_anomaly_thresholds
                update_anomaly_thresholds.delay()
                
        else:
            logger.debug(f"Updated ThresholdBreach: {instance.id}")
            
    except Exception as e:
        logger.error(f"Error in threshold_breach_post_save: {e}")


@receiver(pre_save, sender=AdaptiveThreshold)
def adaptive_threshold_pre_save(sender, instance, **kwargs):
    """Signal handler before saving AdaptiveThreshold"""
    try:
        # Set default values if not provided
        if not instance.adaptation_method:
            instance.adaptation_method = 'statistical'
        
        if not instance.learning_period_days:
            instance.learning_period_days = 30
        
        if not instance.min_samples:
            instance.min_samples = 100
        
        if not instance.confidence_threshold:
            instance.confidence_threshold = 0.95
        
        if not instance.adaptation_frequency:
            instance.adaptation_frequency = 'daily'
        
        # Validate adaptation method
        valid_methods = ['statistical', 'ml_linear', 'ml_tree', 'time_series', 'ensemble']
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
            
            # Trigger initial training
            from ..tasks.intelligence import train_prediction_models
            train_prediction_models.delay()
            
        else:
            logger.debug(f"Updated AdaptiveThreshold: {instance.id}")
            
    except Exception as e:
        logger.error(f"Error in adaptive_threshold_post_save: {e}")


@receiver(pre_save, sender=ThresholdHistory)
def threshold_history_pre_save(sender, instance, **kwargs):
    """Signal handler before saving ThresholdHistory"""
    try:
        # Set default values if not provided
        if not instance.created_at:
            instance.created_at = timezone.now()
        
        # Calculate change percentage if not set
        if not instance.change_percentage and instance.old_threshold and instance.new_threshold:
            instance.change_percentage = ((instance.new_threshold - instance.old_threshold) / instance.old_threshold) * 100
            
    except Exception as e:
        logger.error(f"Error in threshold_history_pre_save: {e}")


@receiver(post_save, sender=ThresholdHistory)
def threshold_history_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving ThresholdHistory"""
    try:
        if created:
            logger.info(f"Created ThresholdHistory: {instance.change_type} - {instance.change_percentage:.1f}% change")
            
            # Update adaptive threshold if applicable
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
        # Set default values if not provided
        if not instance.profile_type:
            instance.profile_type = 'general'
        
        if not instance.is_default:
            instance.is_default = False
        
        if not instance.is_active:
            instance.is_active = True
        
        # Validate profile type
        valid_types = ['general', 'performance', 'security', 'business', 'infrastructure']
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
            
            # If this is default, unset other defaults
            if instance.is_default:
                ThresholdProfile.objects.filter(
                    profile_type=instance.profile_type,
                    is_default=True
                ).exclude(id=instance.id).update(is_default=False)
                
        else:
            logger.debug(f"Updated ThresholdProfile: {instance.name}")
            
    except Exception as e:
        logger.error(f"Error in threshold_profile_post_save: {e}")


# Custom signal handlers for threshold business logic
def trigger_threshold_adaptation(threshold_config, breach_data):
    """Custom function to trigger threshold adaptation"""
    try:
        if threshold_config.threshold_type == 'adaptive':
            adaptive_threshold = threshold_config.adaptive_thresholds.first()
            if adaptive_threshold:
                # Trigger adaptation task
                from ..tasks.intelligence import train_correlation_model
                train_correlation_model.delay(adaptive_threshold.id)
                
                logger.info(f"Triggered adaptation for threshold config {threshold_config.id}")
                
    except Exception as e:
        logger.error(f"Error in trigger_threshold_adaptation: {e}")


def trigger_threshold_breach_notification(threshold_breach):
    """Custom function to trigger threshold breach notification"""
    try:
        logger.info(f"Triggering notification for threshold breach {threshold_breach.id}")
        
        # Create notification for threshold breach
        from ..models.core import Notification
        from ..models.threshold import ThresholdConfig
        
        notification = Notification.objects.create(
            alert_log=threshold_breach.alert_log,
            notification_type='email',
            recipient="threshold_team",  # Would be resolved by routing
            subject=f"Threshold Breach Alert: {threshold_breach.threshold_config.name}",
            message=f"Threshold breach detected: {threshold_breach.breach_value} > {threshold_breach.threshold_value} ({threshold_breach.breach_percentage:.1f}%)",
            status='pending'
        )
        
        # Trigger notification sending
        from ..tasks.notification import send_pending_notifications
        send_pending_notifications.delay()
        
        return notification
        
    except Exception as e:
        logger.error(f"Error in trigger_threshold_breach_notification: {e}")
        return None


def trigger_threshold_profile_application(threshold_config, threshold_profile):
    """Custom function to trigger threshold profile application"""
    try:
        logger.info(f"Applying threshold profile {threshold_profile.name} to config {threshold_config.id}")
        
        # Update threshold config with profile settings
        effective_settings = threshold_profile.get_effective_settings(threshold_config.alert_rule.alert_type)
        
        if effective_settings:
            threshold_config.primary_threshold = effective_settings.get('primary_threshold', threshold_config.primary_threshold)
            threshold_config.secondary_threshold = effective_settings.get('secondary_threshold', threshold_config.secondary_threshold)
            threshold_config.save(update_fields=['primary_threshold', 'secondary_threshold'])
            
            # Create history record
            ThresholdHistory.objects.create(
                adaptive_threshold=None,
                change_type='profile_applied',
                old_threshold=threshold_config.primary_threshold,
                new_threshold=effective_settings.get('primary_threshold'),
                reason=f"Applied profile: {threshold_profile.name}"
            )
            
            logger.info(f"Successfully applied threshold profile {threshold_profile.name}")
            
    except Exception as e:
        logger.error(f"Error in trigger_threshold_profile_application: {e}")


def trigger_threshold_analysis(threshold_config):
    """Custom function to trigger threshold analysis"""
    try:
        logger.info(f"Triggering analysis for threshold config {threshold_config.id}")
        
        # Analyze recent breaches and suggest optimizations
        from ..tasks.intelligence import optimize_noise_filters
        optimize_noise_filters.delay()
        
        # Generate threshold performance report
        from ..tasks.reporting import generate_performance_reports
        generate_performance_reports.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_threshold_analysis: {e}")


def trigger_threshold_cleanup():
    """Custom function to trigger threshold data cleanup"""
    try:
        # Clean up old threshold history
        from ..tasks.intelligence import cleanup_old_intelligence_data
        cleanup_old_intelligence_data.delay()
        
        logger.info("Triggered threshold data cleanup")
        
    except Exception as e:
        logger.error(f"Error in trigger_threshold_cleanup: {e}")


# Signal registration
def register_threshold_signals():
    """Register all threshold signals"""
    try:
        logger.info("Threshold signals registered successfully")
    except Exception as e:
        logger.error(f"Error registering threshold signals: {e}")


# Auto-register signals when module is imported
register_threshold_signals()
