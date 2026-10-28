# =============================================================================
# fraud_detection/celery_beat_config.py
# =============================================================================
"""
Celery Beat Configuration for Fraud Detection System.

Provides scheduled task configuration for periodic fraud detection
processes, maintenance tasks, and automated workflows.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from celery.schedules import crontab

from django.conf import settings


logger = logging.getLogger(__name__)


# Celery Beat Schedule Configuration
CELERY_BEAT_SCHEDULE = {
    # Daily tasks
    'fraud-detection-daily-summary': {
        'task': 'api.fraud_detection.background_jobs.generate_daily_analytics',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1:00 AM
        'options': {
            'queue': 'fraud_low_priority',
            'priority': 5,
        }
    },
    
    'fraud-detection-daily-report': {
        'task': 'api.fraud_detection.background_jobs.generate_compliance_report',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2:00 AM
        'kwargs': {
            'report_type': 'daily_summary',
            'period_days': 1
        },
        'options': {
            'queue': 'fraud_low_priority',
            'priority': 5,
        }
    },
    
    'fraud-detection-weekly-report': {
        'task': 'api.fraud_detection.background_jobs.generate_compliance_report',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),  # Weekly on Monday at 3:00 AM
        'kwargs': {
            'report_type': 'weekly_trends',
            'period_days': 7
        },
        'options': {
            'queue': 'fraud_low_priority',
            'priority': 5,
        }
    },
    
    'fraud-detection-monthly-report': {
        'task': 'api.fraud_detection.background_jobs.generate_compliance_report',
        'schedule': crontab(hour=4, minute=0, day_of_month=1),  # Monthly on 1st at 4:00 AM
        'kwargs': {
            'report_type': 'monthly_comprehensive',
            'period_days': 30
        },
        'options': {
            'queue': 'fraud_low_priority',
            'priority': 5,
        }
    },
    
    # Hourly tasks
    'fraud-detection-hourly-metrics': {
        'task': 'api.fraud_detection.background_jobs.update_fraud_metrics',
        'schedule': crontab(minute=0),  # Every hour at minute 0
        'options': {
            'queue': 'fraud_medium_priority',
            'priority': 6,
        }
    },
    
    'fraud-detection-cache-cleanup': {
        'task': 'api.fraud_detection.background_jobs.cleanup_old_cache_entries',
        'schedule': crontab(minute=30),  # Every hour at minute 30
        'options': {
            'queue': 'fraud_low_priority',
            'priority': 3,
        }
    },
    
    # Every 6 hours
    'fraud-detection-threat-intelligence': {
        'task': 'api.fraud_detection.background_jobs.update_external_threat_intelligence',
        'schedule': crontab(hour='*/6', minute=15),  # Every 6 hours at minute 15
        'options': {
            'queue': 'fraud_medium_priority',
            'priority': 6,
        }
    },
    
    'fraud-detection-risk-profile-sync': {
        'task': 'api.fraud_detection.background_jobs.sync_risk_profiles',
        'schedule': crontab(hour='*/6', minute=45),  # Every 6 hours at minute 45
        'options': {
            'queue': 'fraud_medium_priority',
            'priority': 6,
        }
    },
    
    # Every 15 minutes
    'fraud-detection-alert-processing': {
        'task': 'api.fraud_detection.background_jobs.process_pending_alerts',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'options': {
            'queue': 'fraud_high_priority',
            'priority': 8,
        }
    },
    
    'fraud-detection-case-escalation': {
        'task': 'api.fraud_detection.background_jobs.check_case_escalations',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'options': {
            'queue': 'fraud_high_priority',
            'priority': 8,
        }
    },
    
    # Every 5 minutes
    'fraud-detection-real-time-monitoring': {
        'task': 'api.fraud_detection.background_jobs.update_monitoring_metrics',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'options': {
            'queue': 'fraud_high_priority',
            'priority': 9,
        }
    },
    
    'fraud-detection-system-health': {
        'task': 'api.fraud_detection.background_jobs.check_system_health',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'options': {
            'queue': 'fraud_medium_priority',
            'priority': 7,
        }
    },
    
    # Every minute (for critical real-time tasks)
    'fraud-detection-critical-alerts': {
        'task': 'api.fraud_detection.background_jobs.process_critical_alerts',
        'schedule': crontab(minute='*'),  # Every minute
        'options': {
            'queue': 'fraud_critical_priority',
            'priority': 10,
        }
    },
    
    # Database maintenance tasks
    'fraud-detection-database-cleanup': {
        'task': 'api.fraud_detection.background_jobs.cleanup_old_records',
        'schedule': crontab(hour=0, minute=0, day_of_week=0),  # Weekly on Sunday at midnight
        'kwargs': {
            'days_to_keep': 90
        },
        'options': {
            'queue': 'fraud_low_priority',
            'priority': 2,
        }
    },
    
    'fraud-detection-index-optimization': {
        'task': 'api.fraud_detection.background_jobs.optimize_database_indexes',
        'schedule': crontab(hour=0, minute=30, day_of_week=0),  # Weekly on Sunday at 12:30 AM
        'options': {
            'queue': 'fraud_low_priority',
            'priority': 2,
        }
    },
    
    # Cache warming tasks
    'fraud-detection-cache-warmup': {
        'task': 'api.fraud_detection.background_jobs.warmup_cache',
        'schedule': crontab(hour=0, minute=5),  # Daily at 12:05 AM
        'kwargs': {
            'user_batch_size': 1000,
            'max_users': 10000
        },
        'options': {
            'queue': 'fraud_low_priority',
            'priority': 4,
        }
    },
    
    # External integrations
    'fraud-detection-sync-external-databases': {
        'task': 'api.fraud_detection.background_jobs.sync_external_fraud_databases',
        'schedule': crontab(hour='*/4', minute=0),  # Every 4 hours
        'options': {
            'queue': 'fraud_medium_priority',
            'priority': 6,
        }
    },
    
    'fraud-detection-update-sanctions-lists': {
        'task': 'api.fraud_detection.background_jobs.update_sanctions_lists',
        'schedule': crontab(hour=6, minute=0),  # Daily at 6:00 AM
        'options': {
            'queue': 'fraud_medium_priority',
            'priority': 6,
        }
    },
    
    # Notification tasks
    'fraud-detection-daily-summary-notification': {
        'task': 'api.fraud_detection.background_jobs.send_daily_summary_notifications',
        'schedule': crontab(hour=8, minute=0),  # Daily at 8:00 AM
        'options': {
            'queue': 'fraud_medium_priority',
            'priority': 6,
        }
    },
    
    'fraud-detection-weekly-digest': {
        'task': 'api.fraud_detection.background_jobs.send_weekly_digest',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),  # Weekly on Monday at 9:00 AM
        'options': {
            'queue': 'fraud_medium_priority',
            'priority': 6,
        }
    },
    
    # Machine learning tasks
    'fraud-detection-model-training': {
        'task': 'api.fraud_detection.background_jobs.train_fraud_models',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),  # Weekly on Sunday at 2:00 AM
        'options': {
            'queue': 'fraud_low_priority',
            'priority': 3,
        }
    },
    
    'fraud-detection-model-evaluation': {
        'task': 'api.fraud_detection.background_jobs.evaluate_model_performance',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Weekly on Sunday at 3:00 AM
        'options': {
            'queue': 'fraud_low_priority',
            'priority': 3,
        }
    },
    
    # Compliance tasks
    'fraud-detection-sar-filing': {
        'task': 'api.fraud_detection.background_jobs.check_sar_filing_requirements',
        'schedule': crontab(hour=10, minute=0),  # Daily at 10:00 AM
        'options': {
            'queue': 'fraud_high_priority',
            'priority': 8,
        }
    },
    
    'fraud-detection-ctr-reporting': {
        'task': 'api.fraud_detection.background_jobs.check_ctr_reporting_requirements',
        'schedule': crontab(hour=11, minute=0),  # Daily at 11:00 AM
        'options': {
            'queue': 'fraud_high_priority',
            'priority': 8,
        }
    },
    
    # Performance monitoring
    'fraud-detection-performance-metrics': {
        'task': 'api.fraud_detection.background_jobs.collect_performance_metrics',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
        'options': {
            'queue': 'fraud_medium_priority',
            'priority': 7,
        }
    },
    
    'fraud-detection-alert-performance': {
        'task': 'api.fraud_detection.background_jobs.analyze_alert_performance',
        'schedule': crontab(hour='*/2', minute=0),  # Every 2 hours
        'options': {
            'queue': 'fraud_medium_priority',
            'priority': 6,
        }
    },
}


def get_celery_beat_schedule() -> dict:
    """
    Get the complete Celery Beat schedule configuration.
    
    Returns:
        Dictionary containing all scheduled tasks
    """
    # Get custom schedule from settings if available
    custom_schedule = getattr(settings, 'FRAUD_DETECTION_CELERY_BEAT_SCHEDULE', {})
    
    # Merge with default schedule
    merged_schedule = CELERY_BEAT_SCHEDULE.copy()
    merged_schedule.update(custom_schedule)
    
    # Log scheduled tasks
    logger.info(f"Configured {len(merged_schedule)} scheduled tasks for fraud detection")
    
    return merged_schedule


def get_task_queue_config() -> dict:
    """
    Get task queue configuration for fraud detection.
    
    Returns:
        Dictionary containing queue settings
    """
    return {
        'task_routes': {
            'api.fraud_detection.background_jobs.process_critical_alerts': {
                'queue': 'fraud_critical_priority',
                'priority': 10,
            },
            'api.fraud_detection.background_jobs.process_fraud_detection': {
                'queue': 'fraud_high_priority',
                'priority': 8,
            },
            'api.fraud_detection.background_jobs.process_sanctions_screening': {
                'queue': 'fraud_high_priority',
                'priority': 8,
            },
            'api.fraud_detection.background_jobs.batch_risk_assessment': {
                'queue': 'fraud_medium_priority',
                'priority': 6,
            },
            'api.fraud_detection.background_jobs.generate_compliance_report': {
                'queue': 'fraud_low_priority',
                'priority': 5,
            },
            'api.fraud_detection.background_jobs.cleanup_old_cache_entries': {
                'queue': 'fraud_low_priority',
                'priority': 3,
            },
            'api.fraud_detection.background_jobs.train_fraud_models': {
                'queue': 'fraud_low_priority',
                'priority': 2,
            },
        },
        'task_default_queue': 'fraud_default',
        'task_default_priority': 5,
        'task_queues': {
            'fraud_critical_priority': {
                'exchange': 'fraud_detection',
                'routing_key': 'critical',
                'queue_arguments': {
                    'x-max-priority': 10,
                },
            },
            'fraud_high_priority': {
                'exchange': 'fraud_detection',
                'routing_key': 'high',
                'queue_arguments': {
                    'x-max-priority': 8,
                },
            },
            'fraud_medium_priority': {
                'exchange': 'fraud_detection',
                'routing_key': 'medium',
                'queue_arguments': {
                    'x-max-priority': 6,
                },
            },
            'fraud_low_priority': {
                'exchange': 'fraud_detection',
                'routing_key': 'low',
                'queue_arguments': {
                    'x-max-priority': 4,
                },
            },
            'fraud_default': {
                'exchange': 'fraud_detection',
                'routing_key': 'default',
                'queue_arguments': {
                    'x-max-priority': 5,
                },
            },
        },
    }


def get_worker_config() -> dict:
    """
    Get worker configuration for fraud detection tasks.
    
    Returns:
        Dictionary containing worker settings
    """
    return {
        'worker_concurrency': getattr(settings, 'FRAUD_DETECTION_WORKER_CONCURRENCY', 4),
        'worker_prefetch_multiplier': getattr(settings, 'FRAUD_DETECTION_WORKER_PREFETCH_MULTIPLIER', 1),
        'worker_max_tasks_per_child': getattr(settings, 'FRAUD_DETECTION_WORKER_MAX_TASKS_PER_CHILD', 1000),
        'worker_disable_rate_limits': getattr(settings, 'FRAUD_DETECTION_WORKER_DISABLE_RATE_LIMITS', False),
        'worker_log_format': getattr(settings, 'FRAUD_DETECTION_WORKER_LOG_FORMAT', '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'),
        'worker_task_log_format': getattr(settings, 'FRAUD_DETECTION_WORKER_TASK_LOG_FORMAT', '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'),
        'worker_pool_restarts': getattr(settings, 'FRAUD_DETECTION_WORKER_POOL_RESTARTS', False),
        'worker_max_memory_per_child': getattr(settings, 'FRAUD_DETECTION_WORKER_MAX_MEMORY_MB', 200000),  # 200MB
    }


def get_schedule_config() -> dict:
    """
    Get schedule configuration for Celery Beat.
    
    Returns:
        Dictionary containing schedule settings
    """
    return {
        'beat_schedule': get_celery_beat_schedule(),
        'beat_scheduler': getattr(settings, 'CELERY_BEAT_SCHEDULER', 'django_celery_beat.schedulers:DatabaseScheduler'),
        'beat_sync_every': getattr(settings, 'CELERY_BEAT_SYNC_EVERY', 0),  # Don't sync every time
        'beat_max_loop_interval': getattr(settings, 'CELERY_BEAT_MAX_LOOP_INTERVAL', 60),  # 1 minute
        'beat_logfile': getattr(settings, 'CELERY_BEAT_LOGFILE', None),
        'beat_schedule_filename': getattr(settings, 'CELERY_BEAT_SCHEDULE_FILENAME', 'celerybeat-schedule'),
    }


# Task priorities
TASK_PRIORITIES = {
    'critical': 10,
    'high': 8,
    'medium': 6,
    'normal': 5,
    'low': 4,
    'maintenance': 3,
    'background': 2,
}


# Queue priorities
QUEUE_PRIORITIES = {
    'fraud_critical_priority': 10,
    'fraud_high_priority': 8,
    'fraud_medium_priority': 6,
    'fraud_default': 5,
    'fraud_low_priority': 4,
}


def get_task_priority(task_name: str) -> int:
    """
    Get priority for a specific task.
    
    Args:
        task_name: Name of the task
        
    Returns:
        Priority level
    """
    # Map task names to priorities
    task_priority_map = {
        'process_critical_alerts': TASK_PRIORITIES['critical'],
        'process_fraud_detection': TASK_PRIORITIES['high'],
        'process_sanctions_screening': TASK_PRIORITIES['high'],
        'batch_risk_assessment': TASK_PRIORITIES['medium'],
        'generate_compliance_report': TASK_PRIORITIES['normal'],
        'cleanup_old_cache_entries': TASK_PRIORITIES['low'],
        'train_fraud_models': TASK_PRIORITIES['background'],
    }
    
    return task_priority_map.get(task_name, TASK_PRIORITIES['normal'])


def validate_schedule_config() -> bool:
    """
    Validate the Celery Beat schedule configuration.
    
    Returns:
        True if configuration is valid
    """
    try:
        schedule = get_celery_beat_schedule()
        
        # Check for duplicate task names
        task_names = list(schedule.keys())
        if len(task_names) != len(set(task_names)):
            logger.error("Duplicate task names found in Celery Beat schedule")
            return False
        
        # Validate schedule formats
        for task_name, task_config in schedule.items():
            if 'task' not in task_config:
                logger.error(f"Task '{task_name}' missing 'task' field")
                return False
            
            if 'schedule' not in task_config:
                logger.error(f"Task '{task_name}' missing 'schedule' field")
                return False
        
        logger.info("Celery Beat schedule configuration is valid")
        return True
        
    except Exception as e:
        logger.error(f"Error validating Celery Beat schedule: {e}")
        return False


# Initialize and validate configuration
if not validate_schedule_config():
    logger.warning("Celery Beat schedule configuration has issues")
else:
    logger.info("Celery Beat schedule configuration loaded successfully")


# =============================================================================
# WIRING ENTRY POINT — called by apps.py FraudDetectionConfig.ready()
# WAS FLOATING: CELERY_BEAT_SCHEDULE dict existed but was never registered.
# =============================================================================

def register_fraud_beat_schedule() -> None:
    """
    Merge fraud detection beat schedule into Django Celery Beat's database
    scheduler (or the in-memory schedule if django_celery_beat is not installed).
    Called once from FraudDetectionConfig.ready().
    """
    schedule = get_celery_beat_schedule()

    # ── Option A: django_celery_beat installed → persist to DB ───────────────
    try:
        from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
        import json as _json

        for name, cfg in schedule.items():
            task_name = cfg.get("task", "")
            sched     = cfg.get("schedule")

            try:
                if isinstance(sched, crontab):
                    cron, _ = CrontabSchedule.objects.get_or_create(
                        minute=str(sched._orig_minute),
                        hour=str(sched._orig_hour),
                        day_of_week=str(sched._orig_day_of_week),
                        day_of_month=str(sched._orig_day_of_month),
                        month_of_year=str(sched._orig_month_of_year),
                    )
                    PeriodicTask.objects.update_or_create(
                        name=name,
                        defaults={
                            "task":       task_name,
                            "crontab":    cron,
                            "enabled":    True,
                            "kwargs":     _json.dumps(cfg.get("kwargs", {})),
                        },
                    )
                elif isinstance(sched, timedelta):
                    interval, _ = IntervalSchedule.objects.get_or_create(
                        every=int(sched.total_seconds()),
                        period=IntervalSchedule.SECONDS,
                    )
                    PeriodicTask.objects.update_or_create(
                        name=name,
                        defaults={
                            "task":     task_name,
                            "interval": interval,
                            "enabled":  True,
                            "kwargs":   _json.dumps(cfg.get("kwargs", {})),
                        },
                    )
            except Exception as inner:
                logger.warning("Could not register beat task %s: %s", name, inner)

        logger.info("Fraud beat schedule registered via django_celery_beat (%d tasks)", len(schedule))
        return

    except ImportError:
        pass  # django_celery_beat not installed — fall through

    # ── Option B: merge directly into Django's CELERY_BEAT_SCHEDULE setting ──
    try:
        from django.conf import settings
        existing = getattr(settings, "CELERY_BEAT_SCHEDULE", {})
        existing.update(schedule)
        settings.CELERY_BEAT_SCHEDULE = existing
        logger.info("Fraud beat schedule merged into settings.CELERY_BEAT_SCHEDULE (%d tasks)", len(schedule))
    except Exception as exc:
        logger.error("Failed to register fraud beat schedule: %s", exc)


# SLA auto-escalation task (added by sla_manager.py integration)
_SLA_SCHEDULE = {
    "fraud.sla.auto_escalate_breached": {
        "task":     "fraud.sla.auto_escalate_breached",
        "schedule": crontab(minute="*/15"),   # every 15 min
    },
}


def get_sla_beat_schedule() -> dict:
    return _SLA_SCHEDULE


# =============================================================================
# NEW BEAT SCHEDULES — SLA, Reports, KYC, Chargeback
# =============================================================================
_NEW_SCHEDULES = {
    # SLA auto-escalation every 15 minutes
    "fraud.sla.auto_escalate_breached": {
        "task":     "fraud.sla.auto_escalate_breached",
        "schedule": crontab(minute="*/15"),
    },
    # Daily fraud report at 00:05 every day
    "fraud.reports.run_daily": {
        "task":     "fraud.reports.run_daily",
        "schedule": crontab(minute=5, hour=0),
    },
    # Weekly summary every Monday at 06:00
    "fraud.reports.run_weekly": {
        "task":     "fraud.reports.run_weekly",
        "schedule": crontab(minute=0, hour=6, day_of_week=1),
    },
    # Monthly executive report on 1st of each month at 07:00
    "fraud.reports.run_monthly": {
        "task":     "fraud.reports.run_monthly",
        "schedule": crontab(minute=0, hour=7, day_of_month=1),
    },
    # Daily KYC expiry check at 01:00
    "fraud.kyc.process_expired": {
        "task":     "fraud.kyc.process_expired",
        "schedule": crontab(minute=0, hour=1),
    },
    # Daily chargeback stats at 02:00
    "fraud.chargeback.daily_stats": {
        "task":     "fraud.chargeback.daily_stats",
        "schedule": crontab(minute=0, hour=2),
    },
}


def get_all_beat_schedules() -> dict:
    """Return combined schedule of all modules — single source of truth."""
    base = get_celery_beat_schedule() if 'get_celery_beat_schedule' in dir() else {}
    return {**base, **_NEW_SCHEDULES}
