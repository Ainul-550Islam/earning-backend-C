"""
Celery Beat Configuration with Heartbeat Monitoring and Task Tracking
"""
from celery.schedules import crontab
from celery import Celery, shared_task
import os
import json
import time
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class CeleryHeartbeatMonitor:
    """Monitor Celery worker and beat health with heartbeat tracking"""
    
    def __init__(self):
        self.heartbeat_key_prefix = "celery_heartbeat"
        self.task_stats_key_prefix = "celery_task_stats"
        self.worker_stats_key_prefix = "celery_worker_stats"
    
    def record_worker_heartbeat(self, worker_name, status='active', **kwargs):
        """Record worker heartbeat status"""
        heartbeat_data = {
            'worker_name': worker_name,
            'status': status,
            'timestamp': timezone.now().isoformat(),
            'last_seen': timezone.now().isoformat(),
            **kwargs
        }
        
        key = f"{self.heartbeat_key_prefix}_{worker_name}"
        cache.set(key, heartbeat_data, timeout=300)  # 5 minutes timeout
        
        logger.info(f"Recorded heartbeat for worker {worker_name}: {status}")
    
    def record_task_execution(self, task_name, task_id, status, execution_time=None, **kwargs):
        """Record task execution statistics"""
        task_stats_key = f"{self.task_stats_key_prefix}_{task_name}"
        
        # Get existing stats
        stats = cache.get(task_stats_key, {
            'total_runs': 0,
            'success_count': 0,
            'failure_count': 0,
            'avg_execution_time': 0,
            'last_run': None,
            'last_success': None,
            'last_failure': None,
            'recent_failures': []
        })
        
        # Update stats
        stats['total_runs'] += 1
        stats['last_run'] = timezone.now().isoformat()
        
        if status == 'success':
            stats['success_count'] += 1
            stats['last_success'] = timezone.now().isoformat()
            
            if execution_time:
                # Update average execution time
                current_avg = stats['avg_execution_time']
                total_success = stats['success_count']
                stats['avg_execution_time'] = ((current_avg * (total_success - 1)) + execution_time) / total_success
                
        elif status == 'failure':
            stats['failure_count'] += 1
            stats['last_failure'] = timezone.now().isoformat()
            
            # Track recent failures
            failure_info = {
                'task_id': task_id,
                'timestamp': timezone.now().isoformat(),
                'error': kwargs.get('error', 'Unknown error')
            }
            stats['recent_failures'].append(failure_info)
            
            # Keep only last 10 failures
            stats['recent_failures'] = stats['recent_failures'][-10:]
        
        # Calculate success rate
        if stats['total_runs'] > 0:
            stats['success_rate'] = (stats['success_count'] / stats['total_runs']) * 100
        else:
            stats['success_rate'] = 0
        
        # Store updated stats
        cache.set(task_stats_key, stats, timeout=86400)  # 24 hours timeout
        
        logger.info(f"Recorded task stats for {task_name}: {status}, success_rate: {stats['success_rate']:.1f}%")
    
    def get_worker_status(self, worker_name):
        """Get worker status from heartbeat"""
        key = f"{self.heartbeat_key_prefix}_{worker_name}"
        heartbeat_data = cache.get(key)
        
        if not heartbeat_data:
            return {'status': 'unknown', 'last_seen': None}
        
        # Check if heartbeat is stale (older than 5 minutes)
        last_seen = datetime.fromisoformat(heartbeat_data['last_seen'])
        if timezone.now() - last_seen > timedelta(minutes=5):
            return {'status': 'stale', 'last_seen': heartbeat_data['last_seen']}
        
        return heartbeat_data
    
    def get_task_stats(self, task_name):
        """Get task execution statistics"""
        task_stats_key = f"{self.task_stats_key_prefix}_{task_name}"
        return cache.get(task_stats_key, {})
    
    def get_all_workers_status(self):
        """Get status of all workers"""
        all_keys = cache.keys(f"{self.heartbeat_key_prefix}_*")
        workers = {}
        
        for key in all_keys:
            worker_name = key.replace(f"{self.heartbeat_key_prefix}_", "")
            workers[worker_name] = self.get_worker_status(worker_name)
        
        return workers
    
    def get_all_task_stats(self):
        """Get statistics for all tasks"""
        all_keys = cache.keys(f"{self.task_stats_key_prefix}_*")
        tasks = {}
        
        for key in all_keys:
            task_name = key.replace(f"{self.task_stats_key_prefix}_", "")
            tasks[task_name] = self.get_task_stats(task_name)
        
        return tasks


# Initialize heartbeat monitor
heartbeat_monitor = CeleryHeartbeatMonitor()


# Heartbeat monitoring tasks
@shared_task(bind=True, name='celery_worker_heartbeat')
def celery_worker_heartbeat(self):
    """Heartbeat task for Celery workers"""
    try:
        worker_name = self.request.hostname
        heartbeat_monitor.record_worker_heartbeat(
            worker_name=worker_name,
            status='active',
            task_id=self.request.id,
            queue=self.request.delivery_info.get('routing_key', 'default')
        )
        
        # Also update beat heartbeat
        cache.set("celery_beat_last_check", timezone.now().isoformat(), timeout=300)
        
        return {'status': 'success', 'worker': worker_name, 'timestamp': timezone.now().isoformat()}
        
    except Exception as e:
        logger.error(f"Worker heartbeat failed: {e}")
        heartbeat_monitor.record_worker_heartbeat(
            worker_name=getattr(self.request, 'hostname', 'unknown'),
            status='error',
            error=str(e)
        )
        raise


@shared_task(bind=True, name='celery_beat_heartbeat')
def celery_beat_heartbeat(self):
    """Heartbeat task for Celery Beat scheduler"""
    try:
        heartbeat_monitor.record_worker_heartbeat(
            worker_name='celery_beat',
            status='active',
            task_id=self.request.id,
            scheduler='beat'
        )
        
        # Update beat last check timestamp
        cache.set("celery_beat_last_check", timezone.now().isoformat(), timeout=300)
        
        return {'status': 'success', 'service': 'celery_beat', 'timestamp': timezone.now().isoformat()}
        
    except Exception as e:
        logger.error(f"Beat heartbeat failed: {e}")
        heartbeat_monitor.record_worker_heartbeat(
            worker_name='celery_beat',
            status='error',
            error=str(e)
        )
        raise


# Task tracking decorator
def track_task_execution(task_name):
    """Decorator to track task execution statistics"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            task_id = kwargs.get('task_id', 'unknown')
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                heartbeat_monitor.record_task_execution(
                    task_name=task_name,
                    task_id=task_id,
                    status='success',
                    execution_time=execution_time
                )
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                
                heartbeat_monitor.record_task_execution(
                    task_name=task_name,
                    task_id=task_id,
                    status='failure',
                    execution_time=execution_time,
                    error=str(e)
                )
                
                logger.error(f"Task {task_name} failed: {e}")
                raise
        
        return wrapper
    return decorator


# Enhanced task definitions with tracking
@shared_task(bind=True, name='process_pending_alerts_tracked')
@track_task_execution('process_pending_alerts')
def process_pending_alerts_tracked(self):
    """Enhanced process_pending_alerts with tracking"""
    from .celery_tasks import process_pending_alerts
    return process_pending_alerts()


@shared_task(bind=True, name='send_notifications_tracked')
@track_task_execution('send_notifications')
def send_notifications_tracked(self):
    """Enhanced send_notifications with tracking"""
    from .celery_tasks import send_notifications
    return send_notifications()


@shared_task(bind=True, name='escalate_alerts_tracked')
@track_task_execution('escalate_alerts')
def escalate_alerts_tracked(self):
    """Enhanced escalate_alerts with tracking"""
    from .celery_tasks import escalate_alerts
    return escalate_alerts()


@shared_task(bind=True, name='check_system_health_tracked')
@track_task_execution('check_system_health')
def check_system_health_tracked(self):
    """Enhanced check_system_health with tracking"""
    from .celery_tasks import check_system_health
    return check_system_health()


@shared_task(bind=True, name='generate_daily_analytics_tracked')
@track_task_execution('generate_daily_analytics')
def generate_daily_analytics_tracked(self):
    """Enhanced generate_daily_analytics with tracking"""
    from .celery_tasks import generate_daily_analytics
    return generate_daily_analytics()


@shared_task(bind=True, name='send_group_alerts_tracked')
@track_task_execution('send_group_alerts')
def send_group_alerts_tracked(self):
    """Enhanced send_group_alerts with tracking"""
    from .celery_tasks import send_group_alerts
    return send_group_alerts()


@shared_task(bind=True, name='cleanup_old_data_tracked')
@track_task_execution('cleanup_old_data')
def cleanup_old_data_tracked(self):
    """Enhanced cleanup_old_data with tracking"""
    from .celery_tasks import cleanup_old_data
    return cleanup_old_data()


@shared_task(bind=True, name='update_alert_group_caches_tracked')
@track_task_execution('update_alert_group_caches')
def update_alert_group_caches_tracked(self):
    """Enhanced update_alert_group_caches with tracking"""
    from .celery_tasks import update_alert_group_caches
    return update_alert_group_caches()


@shared_task(bind=True, name='expire_suppressions_tracked')
@track_task_execution('expire_suppressions')
def expire_suppressions_tracked(self):
    """Enhanced expire_suppressions with tracking"""
    from .celery_tasks import expire_suppressions
    return expire_suppressions()


# Monitoring and maintenance tasks
@shared_task(name='cleanup_task_statistics')
def cleanup_task_statistics():
    """Clean up old task statistics to prevent memory bloat"""
    try:
        # Clean up stats older than 7 days
        cutoff_time = timezone.now() - timedelta(days=7)
        
        # Get all task stats keys
        all_keys = cache.keys(f"{heartbeat_monitor.task_stats_key_prefix}_*")
        
        cleaned_count = 0
        for key in all_keys:
            stats = cache.get(key)
            if stats and stats.get('last_run'):
                last_run = datetime.fromisoformat(stats['last_run'])
                if last_run < cutoff_time:
                    cache.delete(key)
                    cleaned_count += 1
        
        logger.info(f"Cleaned up {cleaned_count} old task statistics")
        return {'cleaned_count': cleaned_count}
        
    except Exception as e:
        logger.error(f"Error cleaning up task statistics: {e}")
        return {'cleaned_count': 0, 'error': 'Operation failed'}


@shared_task(name='generate_celery_health_report')
def generate_celery_health_report():
    """Generate comprehensive Celery health report"""
    try:
        workers_status = heartbeat_monitor.get_all_workers_status()
        tasks_stats = heartbeat_monitor.get_all_task_stats()
        
        # Calculate overall health metrics
        active_workers = len([w for w in workers_status.values() if w.get('status') == 'active'])
        total_workers = len(workers_status)
        
        # Task health metrics
        total_tasks = len(tasks_stats)
        healthy_tasks = len([t for t in tasks_stats.values() if t.get('success_rate', 0) > 90])
        
        report = {
            'timestamp': timezone.now().isoformat(),
            'workers': {
                'total': total_workers,
                'active': active_workers,
                'stale': len([w for w in workers_status.values() if w.get('status') == 'stale']),
                'unknown': len([w for w in workers_status.values() if w.get('status') == 'unknown']),
                'details': workers_status
            },
            'tasks': {
                'total': total_tasks,
                'healthy': healthy_tasks,
                'unhealthy': total_tasks - healthy_tasks,
                'details': tasks_stats
            },
            'overall_health': {
                'worker_health_ratio': active_workers / total_workers if total_workers > 0 else 0,
                'task_health_ratio': healthy_tasks / total_tasks if total_tasks > 0 else 0,
                'overall_status': 'healthy' if (active_workers == total_workers and healthy_tasks == total_tasks) else 'degraded'
            }
        }
        
        # Store report for monitoring
        cache.set('celery_health_report', report, timeout=3600)  # 1 hour
        
        logger.info(f"Generated Celery health report: {report['overall_health']['overall_status']}")
        return report
        
    except Exception as e:
        logger.error(f"Error generating Celery health report: {e}")
        return {'error': 'Operation failed', 'timestamp': timezone.now().isoformat()}


# Celery Beat Schedule Configuration  — FIXED: all production tasks scheduled
CELERY_BEAT_SCHEDULE = {
    # ── Heartbeat ──────────────────────────────────────────────────────────
    'celery-worker-heartbeat': {
        'task': 'celery_worker_heartbeat',
        'schedule': 300.0,
    },
    'celery-beat-heartbeat': {
        'task': 'celery_beat_heartbeat',
        'schedule': 300.0,
    },
    'generate-celery-health-report': {
        'task': 'generate_celery_health_report',
        'schedule': crontab(minute='*/5'),
    },

    # ── Every 1 minute — core alert pipeline ──────────────────────────────
    'process-pending-alerts': {
        'task': 'api.alerts.tasks.core.process_pending_alerts',
        'schedule': crontab(minute='*/1'),
        'options': {'queue': 'alerts'},
    },

    # ── Every 2 minutes — notifications ────────────────────────────────────
    'send-pending-notifications': {
        'task': 'api.alerts.tasks.notification.send_pending_notifications',
        'schedule': crontab(minute='*/2'),
        'options': {'queue': 'notifications'},
    },
    'process-notification-queue': {
        'task': 'api.alerts.tasks.notification.process_notification_queue',
        'schedule': crontab(minute='*/2'),
        'options': {'queue': 'notifications'},
    },

    # ── Every 5 minutes — escalation & incidents ───────────────────────────
    'escalate-alerts': {
        'task': 'api.alerts.tasks.core.escalate_alerts',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'alerts'},
    },
    'check-incident-escalations': {
        'task': 'api.alerts.tasks.incident.check_incident_escalations',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'incidents'},
    },
    'check-sla-breaches': {
        'task': 'api.alerts.tasks.reporting.check_sla_breaches',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'reporting'},
    },
    'check-system-health': {
        'task': 'api.alerts.tasks.core.check_system_health',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'monitoring'},
    },

    # ── Every 10 minutes ───────────────────────────────────────────────────
    'retry-failed-notifications': {
        'task': 'api.alerts.tasks.notification.retry_failed_notifications',
        'schedule': crontab(minute='*/10'),
        'options': {'queue': 'notifications'},
    },
    'expire-suppressions': {
        'task': 'api.alerts.tasks.core.expire_suppressions',
        'schedule': crontab(minute='*/10'),
        'options': {'queue': 'alerts'},
    },
    'detect-anomalies': {
        'task': 'api.alerts.tasks.intelligence.detect_anomalies',
        'schedule': crontab(minute='*/10'),
        'options': {'queue': 'intelligence'},
    },

    # ── Every 15 minutes ───────────────────────────────────────────────────
    'send-group-alerts': {
        'task': 'send_group_alerts_tracked',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'alerts'},
    },
    'check-unacknowledged-alerts': {
        'task': 'api.alerts.tasks.oncall_notify_tasks.check_and_notify_unacknowledged_alerts',  # check_unacknowledged
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'incidents'},
    },
    'run-intelligence-pipeline': {
        'task': 'api.alerts.tasks.intelligence.run_intelligence_pipeline',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'intelligence'},
    },

    # ── Every 30 minutes ───────────────────────────────────────────────────
    'update-alert-group-caches': {
        'task': 'update_alert_group_caches_tracked',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'alerts'},
    },
    'update-recipient-availability': {
        'task': 'api.alerts.tasks.notification.update_recipient_availability',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'notifications'},
    },
    'run-due-recurring-reports': {
        'task': 'api.alerts.tasks.report_generation_tasks.run_due_recurring_reports',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'reporting'},
    },
    'distribute-reports': {
        'task': 'api.alerts.tasks.reporting.distribute_reports',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'reporting'},
    },

    # ── Every 1 hour ───────────────────────────────────────────────────────
    'recalculate-adaptive-thresholds': {
        'task': 'api.alerts.tasks.adaptive_threshold_tasks.recalculate_adaptive_thresholds',
        'schedule': crontab(minute=0),
        'options': {'queue': 'intelligence'},
    },
    'correlate-recent-alerts': {
        'task': 'api.alerts.tasks.correlation_tasks.correlate_recent_alerts',
        'schedule': crontab(minute=0),
        'options': {'queue': 'intelligence'},
    },
    'auto-resolve-low-priority-incidents': {
        'task': 'api.alerts.tasks.incident.auto_resolve_low_priority_incidents',
        'schedule': crontab(minute=0),
        'options': {'queue': 'incidents'},
    },

    # ── Every 6 hours ──────────────────────────────────────────────────────
    'update-on-call-schedules': {
        'task': 'api.alerts.tasks.incident.update_on_call_schedules',
        'schedule': crontab(minute=0, hour='*/6'),
        'options': {'queue': 'incidents'},
    },
    'compute-channel-delivery-rates': {
        'task': 'api.alerts.tasks.channel_health_tasks.compute_channel_delivery_rates',
        'schedule': crontab(minute=0, hour='*/6'),
        'options': {'queue': 'monitoring'},
    },
    'check-all-channel-health': {
        'task': 'api.alerts.tasks.channel_health_tasks.check_all_channel_health',
        'schedule': crontab(minute=0, hour='*/6'),
        'options': {'queue': 'monitoring'},
    },
    'collect-system-metrics': {
        'task': 'api.alerts.tasks.collect_system_metrics.collect_system_metrics',
        'schedule': crontab(minute=0, hour='*/6'),
        'options': {'queue': 'monitoring'},
    },

    # ── Daily ──────────────────────────────────────────────────────────────
    'generate-daily-analytics': {
        'task': 'api.alerts.tasks.core.generate_daily_analytics',
        'schedule': crontab(hour=1, minute=0),
        'options': {'queue': 'reporting'},
    },
    'calculate-mttr-metrics': {
        'task': 'api.alerts.tasks.reporting.calculate_mttr_metrics',
        'schedule': crontab(hour=1, minute=30),
        'options': {'queue': 'reporting'},
    },
    'calculate-mttd-metrics': {
        'task': 'api.alerts.tasks.reporting.calculate_mttd_metrics',
        'schedule': crontab(hour=1, minute=45),
        'options': {'queue': 'reporting'},
    },
    'cleanup-old-alerts': {
        'task': 'api.alerts.tasks.core.cleanup_old_alerts',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'maintenance'},
    },
    'cleanup-old-data': {
        'task': 'cleanup_old_data_tracked',
        'schedule': crontab(hour=2, minute=30),
        'options': {'queue': 'maintenance'},
    },
    'cleanup-task-statistics': {
        'task': 'cleanup_task_statistics',
        'schedule': crontab(hour=3, minute=0),
        'options': {'queue': 'maintenance'},
    },
    'train-prediction-models': {
        'task': 'api.alerts.tasks.intelligence.train_prediction_models',
        'schedule': crontab(hour=3, minute=30),
        'options': {'queue': 'intelligence'},
    },
    'optimize-noise-filters': {
        'task': 'api.alerts.tasks.intelligence.optimize_noise_filters',
        'schedule': crontab(hour=4, minute=0),
        'options': {'queue': 'intelligence'},
    },
    'generate-daily-reports': {
        'task': 'api.alerts.tasks.report_generation_tasks.generate_daily_reports',
        'schedule': crontab(hour=6, minute=0),
        'options': {'queue': 'reporting'},
    },
    'check-post-mortem-deadlines': {
        'task': 'api.alerts.tasks.incident.check_post_mortem_deadlines',
        'schedule': crontab(hour=9, minute=0),
        'options': {'queue': 'incidents'},
    },
}

# Task routing configuration for better performance
CELERY_TASK_ROUTES = {
    'celery_worker_heartbeat': {'queue': 'monitoring'},
    'celery_beat_heartbeat': {'queue': 'monitoring'},
    'generate_celery_health_report': {'queue': 'monitoring'},
    'cleanup_task_statistics': {'queue': 'maintenance'},
    
    'process_pending_alerts_tracked': {'queue': 'alerts'},
    'send_notifications_tracked': {'queue': 'notifications'},
    'escalate_alerts_tracked': {'queue': 'alerts'},
    'check_system_health_tracked': {'queue': 'monitoring'},
    
    'generate_daily_analytics_tracked': {'queue': 'analytics'},
    'send_group_alerts_tracked': {'queue': 'notifications'},
    'cleanup_old_data_tracked': {'queue': 'maintenance'},
    'update_alert_group_caches_tracked': {'queue': 'maintenance'},
    'expire_suppressions_tracked': {'queue': 'maintenance'},
}

# Task priority configuration
CELERY_TASK_PRIORITY_MAPPING = {
    'process_pending_alerts_tracked': 9,
    'send_notifications_tracked': 8,
    'escalate_alerts_tracked': 10,
    'celery_worker_heartbeat': 5,
    'celery_beat_heartbeat': 5,
    'generate_celery_health_report': 3,
}

# Worker configuration for optimal performance
CELERY_WORKER_CONCURRENCY = 4
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000
CELERY_WORKER_DISABLE_RATE_LIMITS = False
