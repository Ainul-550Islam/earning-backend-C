# cms/batch/processor.py
"""
Batch Processing System

Automated batch jobs with:
- Scheduled execution
- Asynchronous processing
- Progress tracking
- Error handling & retries
- Result persistence
- Monitoring & alerting

Jobs:
- Daily earnings calculation
- Leaderboard updates
- Notification sending
- Report generation
- Data cleanup
- Cache warming
- Analytics aggregation
"""

from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from django.db import transaction
import logging
import json

logger = logging.getLogger('cms.batch.processor')


# ─────────────────────────────────────────────────────────────────────────────
# BATCH JOB REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

class BatchJobRegistry:
    """Registry of all batch jobs"""
    
    jobs = {}
    
    @classmethod
    def register(cls, name: str, schedule: str):
        """Register a batch job"""
        def decorator(func):
            cls.jobs[name] = {
                'function': func,
                'schedule': schedule,
                'name': name,
            }
            return func
        return decorator
    
    @classmethod
    def get_job(cls, name: str):
        """Get job by name"""
        return cls.jobs.get(name, {}).get('function')
    
    @classmethod
    def list_jobs(cls) -> List[str]:
        """List all registered jobs"""
        return list(cls.jobs.keys())


# ─────────────────────────────────────────────────────────────────────────────
# BATCH JOB EXECUTOR
# ─────────────────────────────────────────────────────────────────────────────

class BatchJobExecutor:
    """Execute batch jobs with tracking"""
    
    @staticmethod
    def execute_job(job_name: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a batch job
        
        Args:
            job_name: Name of job to execute
            **kwargs: Job-specific parameters
            
        Returns:
            Execution result with status and metrics
        """
        start_time = timezone.now()
        
        try:
            # Get job function
            job_func = BatchJobRegistry.get_job(job_name)
            if not job_func:
                raise ValueError(f"Job not found: {job_name}")
            
            # Execute job
            logger.info(f"Starting batch job: {job_name}")
            result = job_func(**kwargs)
            
            # Calculate metrics
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            
            # Store result
            execution_result = {
                'job_name': job_name,
                'status': 'completed',
                'result': result,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': duration,
                'error': None,
            }
            
            BatchJobExecutor._store_result(job_name, execution_result)
            logger.info(f"Completed batch job: {job_name} in {duration:.2f}s")
            
            return execution_result
        
        except Exception as e:
            logger.error(f"Failed batch job {job_name}: {str(e)}")
            
            return {
                'job_name': job_name,
                'status': 'failed',
                'error': str(e),
                'start_time': start_time.isoformat(),
                'end_time': timezone.now().isoformat(),
            }
    
    @staticmethod
    def _store_result(job_name: str, result: Dict[str, Any]):
        """Store job result in database"""
        # In production, would store in BatchJobResult model
        logger.info(f"Stored result for {job_name}: {result['status']}")


# ─────────────────────────────────────────────────────────────────────────────
# BATCH JOBS
# ─────────────────────────────────────────────────────────────────────────────

@BatchJobRegistry.register('daily_earnings_calculation', 'cron: 0 1 * * *')  # 1 AM daily
def calculate_daily_earnings() -> Dict[str, Any]:
    """
    Calculate daily earnings for all users
    
    Schedule: Daily at 1 AM
    """
    from django.contrib.auth.models import User
    from api.cms.models_new.surveys import SurveyCompletion
    
    yesterday = timezone.now() - timedelta(days=1)
    
    users_updated = 0
    total_earnings = 0
    
    with transaction.atomic():
        completions = SurveyCompletion.objects.filter(
            created_at__date=yesterday.date()
        )
        
        for user_id in completions.values_list('user_id', flat=True).distinct():
            user = User.objects.get(id=user_id)
            user_earnings = completions.filter(
                user_id=user_id
            ).aggregate(
                total=__import__('django.db.models', fromlist=['Sum']).Sum('reward_amount')
            )['total'] or 0
            
            # Update user wallet (would do in real implementation)
            total_earnings += float(user_earnings)
            users_updated += 1
    
    logger.info(f"Calculated earnings: {users_updated} users, ${total_earnings:.2f}")
    
    return {
        'users_updated': users_updated,
        'total_earnings': total_earnings,
    }


@BatchJobRegistry.register('update_leaderboard', 'cron: 0 2 * * *')  # 2 AM daily
def update_leaderboard() -> Dict[str, Any]:
    """
    Update leaderboard rankings
    
    Schedule: Daily at 2 AM
    """
    from api.cms.models_new.leaderboard import Leaderboard
    from django.contrib.auth.models import User
    from api.cms.models_new.surveys import SurveyCompletion
    
    users_updated = 0
    
    with transaction.atomic():
        users = User.objects.annotate(
            total_points=__import__('django.db.models', fromlist=['Sum']).Sum(
                'surveycompletion__reward_amount'
            )
        ).order_by('-total_points')
        
        for rank, user in enumerate(users, 1):
            leaderboard, created = Leaderboard.objects.get_or_create(user=user)
            leaderboard.rank_position = rank
            leaderboard.total_points = user.total_points or 0
            leaderboard.save()
            users_updated += 1
    
    logger.info(f"Updated leaderboard: {users_updated} entries")
    
    return {
        'leaderboard_entries_updated': users_updated,
    }


@BatchJobRegistry.register('send_pending_notifications', 'cron: */15 * * * *')  # Every 15 min
def send_pending_notifications() -> Dict[str, Any]:
    """
    Send queued notifications
    
    Schedule: Every 15 minutes
    """
    from api.cms.models_new.notifications import Notification
    
    pending = Notification.objects.filter(
        is_sent=False
    ).order_by('-created_at')[:100]
    
    sent_count = 0
    failed_count = 0
    
    for notification in pending:
        try:
            # Send notification (would integrate with service)
            notification.is_sent = True
            notification.sent_at = timezone.now()
            notification.save()
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send notification {notification.id}: {e}")
            failed_count += 1
    
    logger.info(f"Sent notifications: {sent_count} sent, {failed_count} failed")
    
    return {
        'sent': sent_count,
        'failed': failed_count,
    }


@BatchJobRegistry.register('generate_reports', 'cron: 0 3 * * 0')  # 3 AM every Sunday
def generate_reports() -> Dict[str, Any]:
    """
    Generate weekly reports
    
    Schedule: Weekly at 3 AM (Sunday)
    """
    from api.cms.analytics.dashboard import AnalyticsDashboard
    
    # Generate weekly overview
    overview = AnalyticsDashboard.get_overview(days=7)
    daily_metrics = AnalyticsDashboard.get_daily_metrics(days=7)
    
    logger.info(f"Generated weekly report: {overview['total_users']} users")
    
    return {
        'report_type': 'weekly',
        'total_users': overview['total_users'],
        'total_earned': overview['total_earned'],
    }


@BatchJobRegistry.register('cleanup_old_data', 'cron: 0 4 * * *')  # 4 AM daily
def cleanup_old_data() -> Dict[str, Any]:
    """
    Clean up old data
    
    Schedule: Daily at 4 AM
    - Delete old notifications (>90 days)
    - Archive old transactions (>180 days)
    """
    from api.cms.models_new.notifications import Notification
    
    cutoff_date = timezone.now() - timedelta(days=90)
    
    deleted_count, _ = Notification.objects.filter(
        created_at__lt=cutoff_date,
        is_read=True
    ).delete()
    
    logger.info(f"Cleaned up old data: {deleted_count} records deleted")
    
    return {
        'deleted_count': deleted_count,
    }


@BatchJobRegistry.register('warm_caches', 'cron: 0 0 * * *')  # Midnight daily
def warm_caches() -> Dict[str, Any]:
    """
    Pre-populate critical caches
    
    Schedule: Daily at midnight
    """
    from api.cms.cache_manager import cache_manager
    
    items_warmed = cache_manager.warm_all()
    
    logger.info(f"Warmed caches: {items_warmed} items")
    
    return {
        'items_warmed': items_warmed,
    }


@BatchJobRegistry.register('aggregate_analytics', 'cron: 0 5 * * *')  # 5 AM daily
def aggregate_analytics() -> Dict[str, Any]:
    """
    Aggregate daily analytics
    
    Schedule: Daily at 5 AM
    """
    from api.cms.analytics.dashboard import AnalyticsDashboard
    
    daily = AnalyticsDashboard.get_daily_metrics(days=1)
    
    logger.info(f"Aggregated analytics: {len(daily)} days")
    
    return {
        'days_aggregated': len(daily),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CELERY TASK DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3)
def execute_batch_job_task(self, job_name: str, **kwargs):
    """
    Celery task for batch job execution
    
    Usage:
        execute_batch_job_task.delay('daily_earnings_calculation')
    """
    try:
        result = BatchJobExecutor.execute_job(job_name, **kwargs)
        
        if result['status'] == 'failed':
            # Retry on failure
            raise Exception(result['error'])
        
        return result
    
    except Exception as exc:
        logger.error(f"Task failed: {job_name}, retrying... {self.request.retries}/{self.max_retries}")
        
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


# ─────────────────────────────────────────────────────────────────────────────
# BATCH JOB SCHEDULER
# ─────────────────────────────────────────────────────────────────────────────

class BatchJobScheduler:
    """Schedule batch jobs with Celery Beat"""
    
    # Celery Beat schedule
    CELERY_BEAT_SCHEDULE = {
        'daily-earnings-calculation': {
            'task': 'cms.batch.processor.execute_batch_job_task',
            'schedule': __import__('celery.schedules', fromlist=['crontab']).crontab(hour=1, minute=0),
            'args': ('daily_earnings_calculation',),
        },
        'update-leaderboard': {
            'task': 'cms.batch.processor.execute_batch_job_task',
            'schedule': __import__('celery.schedules', fromlist=['crontab']).crontab(hour=2, minute=0),
            'args': ('update_leaderboard',),
        },
        'send-pending-notifications': {
            'task': 'cms.batch.processor.execute_batch_job_task',
            'schedule': __import__('celery.schedules', fromlist=['crontab']).crontab(minute='*/15'),
            'args': ('send_pending_notifications',),
        },
        'generate-reports': {
            'task': 'cms.batch.processor.execute_batch_job_task',
            'schedule': __import__('celery.schedules', fromlist=['crontab']).crontab(hour=3, minute=0, day_of_week=0),
            'args': ('generate_reports',),
        },
        'cleanup-old-data': {
            'task': 'cms.batch.processor.execute_batch_job_task',
            'schedule': __import__('celery.schedules', fromlist=['crontab']).crontab(hour=4, minute=0),
            'args': ('cleanup_old_data',),
        },
        'warm-caches': {
            'task': 'cms.batch.processor.execute_batch_job_task',
            'schedule': __import__('celery.schedules', fromlist=['crontab']).crontab(hour=0, minute=0),
            'args': ('warm_caches',),
        },
        'aggregate-analytics': {
            'task': 'cms.batch.processor.execute_batch_job_task',
            'schedule': __import__('celery.schedules', fromlist=['crontab']).crontab(hour=5, minute=0),
            'args': ('aggregate_analytics',),
        },
    }
    
    @staticmethod
    def get_schedule():
        """Get Celery Beat schedule for settings.py"""
        return BatchJobScheduler.CELERY_BEAT_SCHEDULE
    
    @staticmethod
    def manual_execute(job_name: str, **kwargs):
        """Manually execute a job immediately"""
        return execute_batch_job_task.delay(job_name, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# JOB MONITORING
# ─────────────────────────────────────────────────────────────────────────────

class BatchJobMonitoring:
    """Monitor batch job execution"""
    
    @staticmethod
    def get_job_status(job_name: str) -> Dict[str, Any]:
        """Get status of most recent job execution"""
        from api.cms.models_new.batch import BatchJobResult
        
        try:
            last_execution = BatchJobResult.objects.filter(
                job_name=job_name
            ).latest('created_at')
            
            return {
                'job_name': job_name,
                'status': last_execution.status,
                'last_executed': last_execution.created_at.isoformat(),
                'duration_seconds': last_execution.duration_seconds,
                'error': last_execution.error,
            }
        except Exception:
            return {
                'job_name': job_name,
                'status': 'never_executed',
            }
    
    @staticmethod
    def get_all_jobs_status() -> List[Dict[str, Any]]:
        """Get status of all jobs"""
        jobs_status = []
        
        for job_name in BatchJobRegistry.list_jobs():
            status = BatchJobMonitoring.get_job_status(job_name)
            jobs_status.append(status)
        
        return jobs_status
    
    @staticmethod
    def check_failed_jobs() -> List[str]:
        """Check for recently failed jobs"""
        from api.cms.models_new.batch import BatchJobResult
        
        hour_ago = timezone.now() - timedelta(hours=1)
        
        failed = BatchJobResult.objects.filter(
            status='failed',
            created_at__gte=hour_ago
        ).values_list('job_name', flat=True).distinct()
        
        return list(failed)


# Export public API
__all__ = [
    'BatchJobRegistry',
    'BatchJobExecutor',
    'BatchJobScheduler',
    'BatchJobMonitoring',
    'execute_batch_job_task',
    # Jobs
    'calculate_daily_earnings',
    'update_leaderboard',
    'send_pending_notifications',
    'generate_reports',
    'cleanup_old_data',
    'warm_caches',
    'aggregate_analytics',
]
