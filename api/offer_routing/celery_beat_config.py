"""
Celery Beat Configuration for Offer Routing System

This module contains scheduled tasks configuration for the offer routing system,
including periodic tasks for cache management, performance monitoring,
and data cleanup.
"""

import logging
from celery import Celery
from celery.schedules import crontab
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Get Celery app instance
from .celery_config import app

# Beat Schedule Configuration
beat_schedule = {
    # Cache Management Tasks
    'clear-expired-cache': {
        'task': 'offer_routing.tasks.clear_expired_cache',
        'schedule': crontab(minute=0, hour='*/2'),  # Every 2 hours
        'options': {'queue': 'cache_management'}
    },
    'refresh-performance-cache': {
        'task': 'offer_routing.tasks.refresh_performance_cache',
        'schedule': crontab(minute=15, hour='*/6'),  # Every 6 hours at minute 15
        'options': {'queue': 'performance_monitoring'}
    },
    'cleanup-orphaned-cache': {
        'task': 'offer_routing.tasks.cleanup_orphaned_cache',
        'schedule': crontab(minute=30, hour=2),  # Daily at 2:30 AM
        'options': {'queue': 'maintenance'}
    },
    
    # Performance Monitoring Tasks
    'collect-routing-metrics': {
        'task': 'offer_routing.tasks.collect_routing_metrics',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'options': {'queue': 'analytics'}
    },
    'generate-performance-reports': {
        'task': 'offer_routing.tasks.generate_performance_reports',
        'schedule': crontab(minute=0, hour=6),  # Daily at 6:00 AM
        'options': {'queue': 'reporting'}
    },
    'analyze-routing-patterns': {
        'task': 'offer_routing.tasks.analyze_routing_patterns',
        'schedule': crontab(minute=0, hour=1, day_of_week=1),  # Weekly on Monday at 1:00 AM
        'options': {'queue': 'analytics'}
    },
    
    # Data Maintenance Tasks
    'cleanup-old-routing-logs': {
        'task': 'offer_routing.tasks.cleanup_old_routing_logs',
        'schedule': crontab(minute=0, hour=3),  # Daily at 3:00 AM
        'options': {'queue': 'maintenance'}
    },
    'archive-historical-data': {
        'task': 'offer_routing.tasks.archive_historical_data',
        'schedule': crontab(minute=30, hour=4, day_of_month=1),  # Monthly on 1st at 4:30 AM
        'options': {'queue': 'maintenance'}
    },
    'cleanup-expired-sessions': {
        'task': 'offer_routing.tasks.cleanup_expired_sessions',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
        'options': {'queue': 'maintenance'}
    },
    
    # Fraud Detection Tasks
    'analyze-fraud-patterns': {
        'task': 'offer_routing.tasks.analyze_fraud_patterns',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
        'options': {'queue': 'fraud_detection'}
    },
    'update-fraud-scores': {
        'task': 'offer_routing.tasks.update_fraud_scores',
        'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours
        'options': {'queue': 'fraud_detection'}
    },
    'generate-fraud-reports': {
        'task': 'offer_routing.tasks.generate_fraud_reports',
        'schedule': crontab(minute=0, hour=8),  # Daily at 8:00 AM
        'options': {'queue': 'reporting'}
    },
    
    # Quality Score Tasks
    'update-offer-quality-scores': {
        'task': 'offer_routing.tasks.update_offer_quality_scores',
        'schedule': crontab(minute=0, hour='*/3'),  # Every 3 hours
        'options': {'queue': 'quality_management'}
    },
    'recalculate-personalization-weights': {
        'task': 'offer_routing.tasks.recalculate_personalization_weights',
        'schedule': crontab(minute=0, hour=2, day_of_week=0),  # Weekly on Sunday at 2:00 AM
        'options': {'queue': 'personalization'}
    },
    'optimize-routing-algorithms': {
        'task': 'offer_routing.tasks.optimize_routing_algorithms',
        'schedule': crontab(minute=30, hour=1, day_of_week=6),  # Weekly on Saturday at 1:30 AM
        'options': {'queue': 'optimization'}
    },
    
    # A/B Testing Tasks
    'evaluate-ab-test-results': {
        'task': 'offer_routing.tasks.evaluate_ab_test_results',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'options': {'queue': 'ab_testing'}
    },
    'finalize-completed-tests': {
        'task': 'offer_routing.tasks.finalize_completed_tests',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
        'options': {'queue': 'ab_testing'}
    },
    
    # Notification Tasks
    'send-performance-alerts': {
        'task': 'offer_routing.tasks.send_performance_alerts',
        'schedule': crontab(minute='*/20'),  # Every 20 minutes
        'options': {'queue': 'notifications'}
    },
    'send-daily-reports': {
        'task': 'offer_routing.tasks.send_daily_reports',
        'schedule': crontab(minute=0, hour=9),  # Daily at 9:00 AM
        'options': {'queue': 'notifications'}
    },
    'cleanup-old-notifications': {
        'task': 'offer_routing.tasks.cleanup_old_notifications',
        'schedule': crontab(minute=0, hour=5),  # Daily at 5:00 AM
        'options': {'queue': 'maintenance'}
    },
    
    # Health Check Tasks
    'system-health-check': {
        'task': 'offer_routing.tasks.system_health_check',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'options': {'queue': 'health_monitoring'}
    },
    'database-optimization': {
        'task': 'offer_routing.tasks.database_optimization',
        'schedule': crontab(minute=0, hour=0, day_of_week=3),  # Weekly on Wednesday at midnight
        'options': {'queue': 'maintenance'}
    },
}

# Configure Celery Beat
app.conf.beat_schedule = beat_schedule
app.conf.timezone = getattr(settings, 'TIME_ZONE', 'UTC')
app.conf.enable_utc = True


class BeatScheduler:
    """
    Custom beat scheduler for offer routing system.
    
    Provides additional functionality for dynamic scheduling
    and task management.
    """
    
    def __init__(self):
        self.app = app
        self.logger = logging.getLogger(__name__)
    
    def add_periodic_task(self, name, task, schedule, **kwargs):
        """Add a new periodic task dynamically."""
        try:
            self.app.conf.beat_schedule[name] = {
                'task': task,
                'schedule': schedule,
                **kwargs
            }
            self.logger.info(f"Added periodic task: {name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to add periodic task {name}: {str(e)}")
            return False
    
    def remove_periodic_task(self, name):
        """Remove a periodic task dynamically."""
        try:
            if name in self.app.conf.beat_schedule:
                del self.app.conf.beat_schedule[name]
                self.logger.info(f"Removed periodic task: {name}")
                return True
            else:
                self.logger.warning(f"Periodic task not found: {name}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to remove periodic task {name}: {str(e)}")
            return False
    
    def update_task_schedule(self, name, new_schedule):
        """Update schedule for an existing periodic task."""
        try:
            if name in self.app.conf.beat_schedule:
                self.app.conf.beat_schedule[name]['schedule'] = new_schedule
                self.logger.info(f"Updated schedule for task: {name}")
                return True
            else:
                self.logger.warning(f"Periodic task not found: {name}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to update schedule for task {name}: {str(e)}")
            return False
    
    def list_tasks(self):
        """List all configured periodic tasks."""
        return list(self.app.conf.beat_schedule.keys())
    
    def get_task_info(self, name):
        """Get information about a specific periodic task."""
        return self.app.conf.beat_schedule.get(name)


# Create global scheduler instance
scheduler = BeatScheduler()


def setup_beat_schedule():
    """
    Setup and configure the beat schedule.
    
    This function is called when the Celery beat starts
    to ensure all scheduled tasks are properly configured.
    """
    try:
        # Apply any environment-specific overrides
        if hasattr(settings, 'OFFER_ROUTING_BEAT_OVERRIDES'):
            for task_name, task_config in settings.OFFER_ROUTING_BEAT_OVERRIDES.items():
                if task_config.get('enabled', True):
                    app.conf.beat_schedule[task_name] = task_config
                elif task_name in app.conf.beat_schedule:
                    del app.conf.beat_schedule[task_name]
        
        # Log configured tasks
        logger.info(f"Configured {len(app.conf.beat_schedule)} periodic tasks")
        
        # Validate task configurations
        for task_name, task_config in app.conf.beat_schedule.items():
            if 'task' not in task_config:
                logger.error(f"Task {task_name} missing 'task' field")
            elif 'schedule' not in task_config:
                logger.error(f"Task {task_name} missing 'schedule' field")
        
        logger.info("Celery beat schedule setup completed")
        
    except Exception as e:
        logger.error(f"Failed to setup beat schedule: {str(e)}")
        raise


def get_next_run_time(task_name):
    """Get the next run time for a specific task."""
    try:
        task_config = app.conf.beat_schedule.get(task_name)
        if task_config:
            schedule = task_config['schedule']
            return schedule.now()
        return None
    except Exception as e:
        logger.error(f"Failed to get next run time for {task_name}: {str(e)}")
        return None


def enable_task(task_name):
    """Enable a specific periodic task."""
    if task_name in app.conf.beat_schedule:
        app.conf.beat_schedule[task_name]['enabled'] = True
        logger.info(f"Enabled task: {task_name}")
        return True
    return False


def disable_task(task_name):
    """Disable a specific periodic task."""
    if task_name in app.conf.beat_schedule:
        app.conf.beat_schedule[task_name]['enabled'] = False
        logger.info(f"Disabled task: {task_name}")
        return True
    return False


# Export the scheduler for use in other modules
__all__ = [
    'app',
    'beat_schedule',
    'scheduler',
    'setup_beat_schedule',
    'get_next_run_time',
    'enable_task',
    'disable_task',
]

# -----------------------------------------------------------------------
# CELERY_BEAT_SCHEDULE – complete list of all required periodic tasks
# -----------------------------------------------------------------------
CELERY_BEAT_SCHEDULE = {
    # ── Personalization ────────────────────────────────────────────────
    'update-user-preferences': {
        'task': 'offer_routing.tasks.personalization.update_user_preferences',
        'schedule': 3600.0,
        'options': {'queue': 'personalization'},
    },
    'update-affinity-scores': {
        'task': 'offer_routing.tasks.personalization.update_affinity_scores',
        'schedule': 3600.0,
        'options': {'queue': 'personalization'},
    },
    'update-collaborative-filtering': {
        'task': 'offer_routing.tasks.personalization.update_collaborative_filtering',
        'schedule': 86400.0,
        'options': {'queue': 'personalization'},
    },
    'optimize-personalization-configs': {
        'task': 'offer_routing.tasks.personalization.optimize_personalization_configs',
        'schedule': 86400.0,
        'options': {'queue': 'personalization'},
    },
    'process-contextual-signals': {
        'task': 'offer_routing.tasks.personalization.process_contextual_signals',
        'schedule': 1800.0,
        'options': {'queue': 'personalization'},
    },
    'cleanup-expired-signals': {
        'task': 'offer_routing.tasks.personalization.cleanup_expired_signals',
        'schedule': 3600.0,
        'options': {'queue': 'maintenance'},
    },
    'calculate-personalization-metrics': {
        'task': 'offer_routing.tasks.personalization.calculate_personalization_metrics',
        'schedule': 3600.0,
        'options': {'queue': 'analytics'},
    },
    'train-ml-models': {
        'task': 'offer_routing.tasks.personalization.train_ml_models',
        'schedule': 604800.0,   # weekly
        'options': {'queue': 'ml'},
    },
    'update-real-time-personalization': {
        'task': 'offer_routing.tasks.personalization.update_real_time_personalization',
        'schedule': 300.0,
        'options': {'queue': 'personalization'},
    },

    # ── Scoring ────────────────────────────────────────────────────────
    'update-all-offer-scores': {
        'task': 'offer_routing.tasks.scoring.update_all_offer_scores',
        'schedule': 3600.0,
        'options': {'queue': 'scoring'},
    },
    'optimize-score-weights': {
        'task': 'offer_routing.tasks.scoring.optimize_score_weights',
        'schedule': 86400.0,
        'options': {'queue': 'scoring'},
    },
    'calculate-user-affinity-scores': {
        'task': 'offer_routing.tasks.scoring.calculate_user_affinity_scores',
        'schedule': 3600.0,
        'options': {'queue': 'scoring'},
    },
    'update-user-offer-history': {
        'task': 'offer_routing.tasks.scoring.update_user_offer_history',
        'schedule': 3600.0,
        'options': {'queue': 'scoring'},
    },
    'refresh-score-cache': {
        'task': 'offer_routing.tasks.scoring.refresh_score_cache',
        'schedule': 300.0,
        'options': {'queue': 'cache_management'},
    },
    'analyze-score-performance': {
        'task': 'offer_routing.tasks.scoring.analyze_score_performance',
        'schedule': 3600.0,
        'options': {'queue': 'analytics'},
    },
    'update-epc-data': {
        'task': 'offer_routing.tasks.scoring.update_epc_data',
        'schedule': 3600.0,
        'options': {'queue': 'scoring'},
    },
    'calculate-conversion-rates': {
        'task': 'offer_routing.tasks.scoring.calculate_conversion_rates',
        'schedule': 3600.0,
        'options': {'queue': 'analytics'},
    },
    'update-global-rankings': {
        'task': 'offer_routing.tasks.scoring.update_global_rankings',
        'schedule': 3600.0,
        'options': {'queue': 'scoring'},
    },

    # ── Cap management ─────────────────────────────────────────────────
    'optimize-cap-configuration': {
        'task': 'offer_routing.tasks.services.cap.optimize_cap_configuration',
        'schedule': 86400.0,
        'options': {'queue': 'cap_management'},
    },
    'cleanup-old-cap-data': {
        'task': 'offer_routing.tasks.services.cap.cleanup_old_cap_data',
        'schedule': 86400.0,
        'options': {'queue': 'maintenance'},
    },
    'generate-cap-reports': {
        'task': 'offer_routing.tasks.services.cap.generate_cap_reports',
        'schedule': 86400.0,
        'options': {'queue': 'reporting'},
    },
    'update-cap-usage-statistics': {
        'task': 'offer_routing.tasks.services.cap.update_cap_usage_statistics',
        'schedule': 3600.0,
        'options': {'queue': 'cap_management'},
    },

    # ── A/B testing ────────────────────────────────────────────────────
    'check-test-duration': {
        'task': 'offer_routing.tasks.services.ab_test.check_test_duration',
        'schedule': 3600.0,
        'options': {'queue': 'ab_testing'},
    },
    'update-test-assignments': {
        'task': 'offer_routing.tasks.services.ab_test.update_test_assignments',
        'schedule': 1800.0,
        'options': {'queue': 'ab_testing'},
    },
    'generate-test-reports': {
        'task': 'offer_routing.tasks.services.ab_test.generate_test_reports',
        'schedule': 86400.0,
        'options': {'queue': 'reporting'},
    },
    'optimize-test-configuration': {
        'task': 'offer_routing.tasks.services.ab_test.optimize_test_configuration',
        'schedule': 86400.0,
        'options': {'queue': 'ab_testing'},
    },

    # ── Fallback / health ──────────────────────────────────────────────
    'check-fallback-health': {
        'task': 'offer_routing.tasks.services.fallback.check_fallback_health',
        'schedule': 300.0,
        'options': {'queue': 'health_checks'},
    },
    'update-offer-pools': {
        'task': 'offer_routing.tasks.services.fallback.update_offer_pools',
        'schedule': 3600.0,
        'options': {'queue': 'fallback'},
    },
    'update-fallback-rules': {
        'task': 'offer_routing.tasks.services.fallback.update_fallback_rules',
        'schedule': 3600.0,
        'options': {'queue': 'fallback'},
    },
    'generate-fallback-analytics': {
        'task': 'offer_routing.tasks.services.fallback.generate_fallback_analytics',
        'schedule': 86400.0,
        'options': {'queue': 'analytics'},
    },

    # ── Monitoring ─────────────────────────────────────────────────────
    'perform-health-check': {
        'task': 'offer_routing.tasks.monitoring.perform_health_check',
        'schedule': 300.0,
        'options': {'queue': 'health_checks'},
    },
    'check-service-dependencies': {
        'task': 'offer_routing.tasks.monitoring.check_service_dependencies',
        'schedule': 300.0,
        'options': {'queue': 'health_checks'},
    },
    'collect-performance-metrics': {
        'task': 'offer_routing.tasks.monitoring.collect_performance_metrics',
        'schedule': 60.0,
        'options': {'queue': 'performance_monitoring'},
    },
    'check-resource-usage': {
        'task': 'offer_routing.tasks.monitoring.check_resource_usage',
        'schedule': 60.0,
        'options': {'queue': 'performance_monitoring'},
    },
    'generate-monitoring-report': {
        'task': 'offer_routing.tasks.monitoring.generate_monitoring_report',
        'schedule': 86400.0,
        'options': {'queue': 'reporting'},
    },

    # ── Legacy / existing tasks (keep for backwards compat) ───────────
    'update-routing-cache': {
        'task': 'offer_routing.tasks.update_routing_cache_task',
        'schedule': 300.0,
        'options': {'queue': 'cache_management'},
    },
    'update-offer-scores': {
        'task': 'offer_routing.tasks.update_offer_scores_task',
        'schedule': 3600.0,
        'options': {'queue': 'scoring'},
    },
    'cleanup-routing-logs': {
        'task': 'offer_routing.tasks.cleanup_routing_logs_task',
        'schedule': 86400.0,
        'options': {'queue': 'maintenance'},
    },
    'fraud-batch-scan': {
        'task': 'offer_routing.tasks.run_fraud_batch_scan',
        'schedule': 3600.0,
        'options': {'queue': 'fraud_detection'},
    },
    'offer-quality-recalculate': {
        'task': 'offer_routing.tasks.recalculate_offer_quality_scores',
        'schedule': 86400.0,
        'options': {'queue': 'scoring'},
    },
    'network-perf-refresh': {
        'task': 'offer_routing.tasks.refresh_network_performance_cache',
        'schedule': 600.0,
        'options': {'queue': 'cache_management'},
    },
    'journey-cleanup': {
        'task': 'offer_routing.tasks.cleanup_old_journey_steps',
        'schedule': 604800.0,
        'options': {'queue': 'maintenance'},
    },
    'tenant-billing': {
        'task': 'offer_routing.tasks.generate_tenant_billing',
        'schedule': 2592000.0,
        'options': {'queue': 'billing'},
    },
}
