"""
Gamification Celery Beat Configuration — Scheduled tasks for gamification system.

This module defines Celery beat schedules for gamification background tasks,
including daily challenges, leaderboard updates, and maintenance tasks.
"""

from __future__ import annotations
from django.utils import timezone

import logging
from datetime import datetime, timedelta

from celery.schedules import crontab
from celery import Celery

from api.gamification.background_jobs import background_job_manager
from api.gamification.caching import cache_warmer
from api.gamification.analytics import report_generator
from api.gamification.webhooks import WebhookService
from api.gamification.exceptions import GamificationServiceError

logger = logging.getLogger(__name__)

# Celery app instance
app = Celery('gamification')


# Beat Schedule Configuration
beat_schedule = {
    # Daily tasks
    'gamification-daily-challenge-reset': {
        'task': 'api.gamification.tasks.reset_daily_challenges',
        'schedule': crontab(hour=0, minute=0),  # Every day at midnight
        'options': {'queue': 'gamification'}
    },
    
    'gamification-daily-leaderboard-update': {
        'task': 'api.gamification.tasks.update_daily_leaderboards',
        'schedule': crontab(hour=1, minute=0),  # Every day at 1 AM
        'options': {'queue': 'gamification'}
    },
    
    'gamification-daily-report-generation': {
        'task': 'api.gamification.tasks.generate_daily_reports',
        'schedule': crontab(hour=2, minute=0),  # Every day at 2 AM
        'options': {'queue': 'gamification'}
    },
    
    'gamification-daily-cache-warmup': {
        'task': 'api.gamification.tasks.warm_daily_cache',
        'schedule': crontab(hour=3, minute=0),  # Every day at 3 AM
        'options': {'queue': 'gamification'}
    },
    
    # Hourly tasks
    'gamification-hourly-streak-check': {
        'task': 'api.gamification.tasks.check_expiring_streaks',
        'schedule': crontab(minute=0),  # Every hour at minute 0
        'options': {'queue': 'gamification'}
    },
    
    'gamification-hourly-webhook-retry': {
        'task': 'api.gamification.tasks.retry_failed_webhooks',
        'schedule': crontab(minute=30),  # Every hour at minute 30
        'options': {'queue': 'gamification'}
    },
    
    # Weekly tasks
    'gamification-weekly-report-generation': {
        'task': 'api.gamification.tasks.generate_weekly_reports',
        'schedule': crontab(hour=1, minute=0, day_of_week=1),  # Monday at 1 AM
        'options': {'queue': 'gamification'}
    },
    
    'gamification-weekly-leaderboard-reset': {
        'task': 'api.gamification.tasks.reset_weekly_leaderboards',
        'schedule': crontab(hour=0, minute=0, day_of_week=1),  # Monday at midnight
        'options': {'queue': 'gamification'}
    },
    
    # Monthly tasks
    'gamification-monthly-report-generation': {
        'task': 'api.gamification.tasks.generate_monthly_reports',
        'schedule': crontab(hour=2, minute=0, day=1),  # 1st of month at 2 AM
        'options': {'queue': 'gamification'}
    },
    
    'gamification-monthly-data-cleanup': {
        'task': 'api.gamification.tasks.cleanup_expired_data',
        'schedule': crontab(hour=3, minute=0, day=1),  # 1st of month at 3 AM
        'options': {'queue': 'gamification'}
    },
    
    # Maintenance tasks
    'gamification-cache-cleanup': {
        'task': 'api.gamification.tasks.cleanup_cache',
        'schedule': crontab(hour=4, minute=0),  # Every day at 4 AM
        'options': {'queue': 'gamification'}
    },
    
    'gamification-analytics-processing': {
        'task': 'api.gamification.tasks.process_analytics_data',
        'schedule': crontab(minute=15),  # Every hour at minute 15
        'options': {'queue': 'gamification'}
    },
    
    'gamification-system-health-check': {
        'task': 'api.gamification.tasks.system_health_check',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
        'options': {'queue': 'gamification'}
    },
    
    # New tasks for enhanced gamification models
    'gamification-points-expiry-check': {
        'task': 'api.gamification.tasks.check_points_expiry',
        'schedule': crontab(minute=0, hour=2),  # Daily at 2 AM
        'options': {'queue': 'gamification'}
    },
    
    'gamification-streak-freeze-cleanup': {
        'task': 'api.gamification.tasks.cleanup_expired_freezes',
        'schedule': crontab(minute=30, hour=2),  # Daily at 2:30 AM
        'options': {'queue': 'gamification'}
    },
    
    'gamification-contest-participant-cleanup': {
        'task': 'api.gamification.tasks.cleanup_contest_participants',
        'schedule': crontab(minute=0, hour=3),  # Daily at 3 AM
        'options': {'queue': 'gamification'}
    },
    
    'gamification-insight-generation': {
        'task': 'api.gamification.tasks.generate_daily_insights',
        'schedule': crontab(minute=0, hour=4),  # Daily at 4 AM
        'options': {'queue': 'gamification'}
    },
    
    'gamification-config-sync': {
        'task': 'api.gamification.tasks.sync_gamification_config',
        'schedule': crontab(minute=30, hour=4),  # Daily at 4:30 AM
        'options': {'queue': 'gamification'}
    },
    
    'gamification-points-transaction-reconciliation': {
        'task': 'api.gamification.tasks.reconcile_points_transactions',
        'schedule': crontab(minute=0, hour=5),  # Daily at 5 AM
        'options': {'queue': 'gamification'}
    }
}

app.conf.beat_schedule = beat_schedule


# Celery Task Definitions
@app.task(bind=True, name='api.gamification.tasks.reset_daily_challenges')
def reset_daily_challenges(self) -> dict:
    """Reset daily challenges and create new ones for the day."""
    try:
        logger.info("Starting daily challenge reset task")
        
        # Enqueue background job for challenge reset
        job_id = background_job_manager.enqueue_job(
            'process_challenges',
            {'action': 'reset_daily'},
            priority='high'
        )
        
        # Process the job immediately
        result = background_job_manager.process_jobs()
        
        logger.info(f"Daily challenge reset completed: {result}")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'job_id': job_id,
            'processed_jobs': result['processed_count'],
            'failed_jobs': result['failed_count'],
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in daily challenge reset task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.update_daily_leaderboards')
def update_daily_leaderboards(self) -> dict:
    """Update daily leaderboards."""
    try:
        logger.info("Starting daily leaderboard update task")
        
        # Enqueue background job for leaderboard calculation
        job_id = background_job_manager.enqueue_job(
            'calculate_leaderboards',
            {'scope': 'daily'},
            priority='normal'
        )
        
        # Process the job
        result = background_job_manager.process_jobs()
        
        logger.info(f"Daily leaderboard update completed: {result}")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'job_id': job_id,
            'processed_jobs': result['processed_count'],
            'failed_jobs': result['failed_count'],
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in daily leaderboard update task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.generate_daily_reports')
def generate_daily_reports(self) -> dict:
    """Generate daily gamification reports."""
    try:
        logger.info("Starting daily report generation task")
        
        # Generate daily report
        report = report_generator.generate_daily_report()
        
        # Enqueue background job for report processing
        job_id = background_job_manager.enqueue_job(
            'generate_reports',
            {'report_type': 'daily'},
            priority='low'
        )
        
        # Process the job
        result = background_job_manager.process_jobs()
        
        logger.info(f"Daily report generation completed: {result}")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'job_id': job_id,
            'report_data': report,
            'processed_jobs': result['processed_count'],
            'failed_jobs': result['failed_count'],
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in daily report generation task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.warm_daily_cache')
def warm_daily_cache(self) -> dict:
    """Warm up daily cache."""
    try:
        logger.info("Starting daily cache warmup task")
        
        # Enqueue background job for cache warmup
        job_id = background_job_manager.enqueue_job(
            'cache_warmup',
            {'warmup_type': 'system'},
            priority='low'
        )
        
        # Process the job
        result = background_job_manager.process_jobs()
        
        logger.info(f"Daily cache warmup completed: {result}")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'job_id': job_id,
            'processed_jobs': result['processed_count'],
            'failed_jobs': result['failed_count'],
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in daily cache warmup task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.check_expiring_streaks')
def check_expiring_streaks(self) -> dict:
    """Check for expiring streaks and send notifications."""
    try:
        logger.info("Starting expiring streaks check task")
        
        # Enqueue background job for streak notifications
        job_id = background_job_manager.enqueue_job(
            'send_notifications',
            {
                'template_id': 'streak_expiring',
                'context': {}
            },
            priority='high'
        )
        
        # Process the job
        result = background_job_manager.process_jobs()
        
        logger.info(f"Expiring streaks check completed: {result}")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'job_id': job_id,
            'processed_jobs': result['processed_count'],
            'failed_jobs': result['failed_count'],
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in expiring streaks check task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.retry_failed_webhooks')
def retry_failed_webhooks(self) -> dict:
    """Retry failed webhook deliveries."""
    try:
        logger.info("Starting failed webhook retry task")
        
        # Get webhook service and retry failed deliveries
        webhook_service = WebhookService()
        retry_results = webhook_service.retry_failed_deliveries()
        
        # Enqueue background job for webhook processing
        job_id = background_job_manager.enqueue_job(
            'process_webhooks',
            {'action': 'retry_failed'},
            priority='normal'
        )
        
        # Process the job
        result = background_job_manager.process_jobs()
        
        logger.info(f"Failed webhook retry completed: {result}")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'job_id': job_id,
            'retry_results': retry_results,
            'processed_jobs': result['processed_count'],
            'failed_jobs': result['failed_count'],
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in failed webhook retry task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.generate_weekly_reports')
def generate_weekly_reports(self) -> dict:
    """Generate weekly gamification reports."""
    try:
        logger.info("Starting weekly report generation task")
        
        # Generate weekly report
        report = report_generator.generate_weekly_report()
        
        # Enqueue background job for report processing
        job_id = background_job_manager.enqueue_job(
            'generate_reports',
            {'report_type': 'weekly'},
            priority='low'
        )
        
        # Process the job
        result = background_job_manager.process_jobs()
        
        logger.info(f"Weekly report generation completed: {result}")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'job_id': job_id,
            'report_data': report,
            'processed_jobs': result['processed_count'],
            'failed_jobs': result['failed_count'],
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in weekly report generation task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.reset_weekly_leaderboards')
def reset_weekly_leaderboards(self) -> dict:
    """Reset weekly leaderboards."""
    try:
        logger.info("Starting weekly leaderboard reset task")
        
        # Enqueue background job for leaderboard reset
        job_id = background_job_manager.enqueue_job(
            'calculate_leaderboards',
            {'scope': 'weekly', 'reset': True},
            priority='normal'
        )
        
        # Process the job
        result = background_job_manager.process_jobs()
        
        logger.info(f"Weekly leaderboard reset completed: {result}")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'job_id': job_id,
            'processed_jobs': result['processed_count'],
            'failed_jobs': result['failed_count'],
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in weekly leaderboard reset task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.generate_monthly_reports')
def generate_monthly_reports(self) -> dict:
    """Generate monthly gamification reports."""
    try:
        logger.info("Starting monthly report generation task")
        
        # Generate monthly report
        report = report_generator.generate_monthly_report()
        
        # Enqueue background job for report processing
        job_id = background_job_manager.enqueue_job(
            'generate_reports',
            {'report_type': 'monthly'},
            priority='low'
        )
        
        # Process the job
        result = background_job_manager.process_jobs()
        
        logger.info(f"Monthly report generation completed: {result}")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'job_id': job_id,
            'report_data': report,
            'processed_jobs': result['processed_count'],
            'failed_jobs': result['failed_count'],
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in monthly report generation task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.cleanup_expired_data')
def cleanup_expired_data(self) -> dict:
    """Clean up expired data."""
    try:
        logger.info("Starting expired data cleanup task")
        
        # Enqueue background job for data cleanup
        job_id = background_job_manager.enqueue_job(
            'cleanup_expired_data',
            {'cleanup_type': 'all', 'days_old': 30},
            priority='low'
        )
        
        # Process the job
        result = background_job_manager.process_jobs()
        
        logger.info(f"Expired data cleanup completed: {result}")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'job_id': job_id,
            'processed_jobs': result['processed_count'],
            'failed_jobs': result['failed_count'],
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in expired data cleanup task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.cleanup_cache')
def cleanup_cache(self) -> dict:
    """Clean up cache."""
    try:
        logger.info("Starting cache cleanup task")
        
        # Get cache statistics before cleanup
        from api.gamification.caching import gamification_cache
        cache_stats_before = gamification_cache.get_cache_stats()
        
        # Enqueue background job for cache cleanup
        job_id = background_job_manager.enqueue_job(
            'cleanup_expired_data',
            {'cleanup_type': 'cache'},
            priority='low'
        )
        
        # Process the job
        result = background_job_manager.process_jobs()
        
        # Get cache statistics after cleanup
        cache_stats_after = gamification_cache.get_cache_stats()
        
        logger.info(f"Cache cleanup completed: {result}")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'job_id': job_id,
            'processed_jobs': result['processed_count'],
            'failed_jobs': result['failed_count'],
            'cache_stats_before': cache_stats_before,
            'cache_stats_after': cache_stats_after,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in cache cleanup task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.process_analytics_data')
def process_analytics_data(self) -> dict:
    """Process analytics data."""
    try:
        logger.info("Starting analytics data processing task")
        
        # Enqueue background job for analytics processing
        job_id = background_job_manager.enqueue_job(
            'user_analytics',
            {'analytics_type': 'engagement'},
            priority='low'
        )
        
        # Process the job
        result = background_job_manager.process_jobs()
        
        logger.info(f"Analytics data processing completed: {result}")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'job_id': job_id,
            'processed_jobs': result['processed_count'],
            'failed_jobs': result['failed_count'],
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in analytics data processing task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.system_health_check')
def system_health_check(self) -> dict:
    """Perform system health check."""
    try:
        logger.info("Starting system health check task")
        
        # Get system health status
        from api.gamification.monitoring import monitoring_service
        health_status = monitoring_service.run_health_checks()
        
        # Get system status
        system_status = background_job_manager.get_system_status()
        
        # Log any critical issues
        if health_status['overall_status'] == 'critical':
            logger.critical(f"System health check found critical issues: {health_status}")
        elif health_status['overall_status'] == 'warning':
            logger.warning(f"System health check found warnings: {health_status}")
        
        logger.info(f"System health check completed: {health_status['overall_status']}")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'health_status': health_status,
            'system_status': system_status,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in system health check task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.check_points_expiry')
def check_points_expiry(self) -> dict:
    """Check for expired points and handle expiry."""
    try:
        logger.info("Starting points expiry check task")
        
        # Import models here to avoid circular imports
        from api.gamification.models import UserPoints, PointsTransaction
        from api.gamification.services import expire_user_points
        
        # Get users with expiring points
        expiring_users = UserPoints.objects.filter(
            points_expiry_date__lte=timezone.now(),
            total_points__gt=0
        )
        
        expired_count = 0
        for user_points in expiring_users:
            try:
                # Expire points and create transaction
                expire_user_points(user_points.user_id)
                expired_count += 1
            except Exception as e:
                logger.error(f"Error expiring points for user {user_points.user_id}: {e}")
        
        logger.info(f"Points expiry check completed: {expired_count} users processed")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'expired_count': expired_count,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in points expiry check task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.cleanup_expired_freezes')
def cleanup_expired_freezes(self) -> dict:
    """Clean up expired streak freezes."""
    try:
        logger.info("Starting expired streak freezes cleanup task")
        
        from api.gamification.models import StreakFreeze
        
        # Get expired freezes
        expired_freezes = StreakFreeze.objects.filter(
            expires_at__lte=timezone.now(),
            is_active=True
        )
        
        cleaned_count = 0
        for freeze in expired_freezes:
            try:
                freeze.is_active = False
                freeze.save(update_fields=['is_active'])
                cleaned_count += 1
            except Exception as e:
                logger.error(f"Error cleaning up freeze {freeze.id}: {e}")
        
        logger.info(f"Expired streak freezes cleanup completed: {cleaned_count} freezes cleaned")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'cleaned_count': cleaned_count,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in expired streak freezes cleanup task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.cleanup_contest_participants')
def cleanup_contest_participants(self) -> dict:
    """Clean up old contest participants."""
    try:
        logger.info("Starting contest participants cleanup task")
        
        from api.gamification.models import ContestParticipant
        
        # Get participants from contests that ended more than 30 days ago
        cutoff_date = timezone.now() - timedelta(days=30)
        old_participants = ContestParticipant.objects.filter(
            contest_cycle__end_date__lt=cutoff_date
        )
        
        cleaned_count = old_participants.count()
        old_participants.delete()
        
        logger.info(f"Contest participants cleanup completed: {cleaned_count} participants cleaned")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'cleaned_count': cleaned_count,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in contest participants cleanup task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.generate_daily_insights')
def generate_daily_insights(self) -> dict:
    """Generate daily gamification insights."""
    try:
        logger.info("Starting daily insights generation task")
        
        from api.gamification.models import GamificationInsight
        from api.gamification.services import calculate_daily_insights
        
        # Get yesterday's date
        yesterday = timezone.now().date() - timedelta(days=1)
        
        # Check if insight already exists
        if GamificationInsight.objects.filter(date=yesterday).exists():
            logger.info(f"Insight for {yesterday} already exists, skipping")
            return {
                'success': True,
                'task_id': self.request.id,
                'message': 'Insight already exists',
                'timestamp': datetime.now().isoformat()
            }
        
        # Generate insights
        insights_data = calculate_daily_insights(yesterday)
        
        # Create insight record
        insight = GamificationInsight.objects.create(
            date=yesterday,
            metric_type='daily_summary',
            value=insights_data.get('total_users', 0),
            metadata=insights_data
        )
        
        logger.info(f"Daily insights generation completed: {insight.id}")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'insight_id': str(insight.id),
            'insights_data': insights_data,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in daily insights generation task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.sync_gamification_config')
def sync_gamification_config(self) -> dict:
    """Sync gamification configuration across tenants."""
    try:
        logger.info("Starting gamification config sync task")
        
        from api.gamification.models import GamificationConfig
        from api.gamification.services import sync_tenant_configs
        
        # Get all configs that need syncing
        configs_to_sync = GamificationConfig.objects.filter(
            last_synced_at__lt=timezone.now() - timedelta(hours=1)
        )
        
        synced_count = 0
        for config in configs_to_sync:
            try:
                sync_tenant_configs(config.tenant_id)
                config.last_synced_at = timezone.now()
                config.save(update_fields=['last_synced_at'])
                synced_count += 1
            except Exception as e:
                logger.error(f"Error syncing config for tenant {config.tenant_id}: {e}")
        
        logger.info(f"Gamification config sync completed: {synced_count} configs synced")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'synced_count': synced_count,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in gamification config sync task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


@app.task(bind=True, name='api.gamification.tasks.reconcile_points_transactions')
def reconcile_points_transactions(self) -> dict:
    """Reconcile points transactions for consistency."""
    try:
        logger.info("Starting points transaction reconciliation task")
        
        from api.gamification.models import UserPoints, PointsTransaction
        from django.db.models import Sum
        
        # Get all users
        users_with_points = UserPoints.objects.all()
        
        reconciled_count = 0
        discrepancies = []
        
        for user_points in users_with_points:
            try:
                # Calculate sum of all transactions
                transaction_sum = PointsTransaction.objects.filter(
                    user_id=user_points.user_id
                ).aggregate(total=Sum('amount'))['total'] or 0
                
                # Check if totals match
                if transaction_sum != user_points.total_points:
                    discrepancies.append({
                        'user_id': user_points.user_id,
                        'expected': transaction_sum,
                        'actual': user_points.total_points,
                        'difference': transaction_sum - user_points.total_points
                    })
                    
                    # Update the user points to match transactions
                    user_points.total_points = transaction_sum
                    user_points.save(update_fields=['total_points'])
                    reconciled_count += 1
                    
            except Exception as e:
                logger.error(f"Error reconciling transactions for user {user_points.user_id}: {e}")
        
        logger.info(f"Points transaction reconciliation completed: {reconciled_count} reconciled, {len(discrepancies)} discrepancies found")
        
        return {
            'success': True,
            'task_id': self.request.id,
            'reconciled_count': reconciled_count,
            'discrepancies': discrepancies,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in points transaction reconciliation task: {e}")
        return {
            'success': False,
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': datetime.now().isoformat()
        }


# Utility functions for managing schedules
def get_schedule_info() -> dict:
    """Get information about all scheduled tasks."""
    return {
        'total_schedules': len(beat_schedule),
        'schedules': {
            name: {
                'task': schedule['task'],
                'schedule': str(schedule['schedule']),
                'options': schedule.get('options', {}),
                'enabled': True
            }
            for name, schedule in beat_schedule.items()
        },
        'last_updated': datetime.now().isoformat()
    }


def enable_schedule(schedule_name: str) -> bool:
    """Enable a specific schedule."""
    if schedule_name in beat_schedule:
        beat_schedule[schedule_name]['enabled'] = True
        logger.info(f"Enabled schedule: {schedule_name}")
        return True
    return False


def disable_schedule(schedule_name: str) -> bool:
    """Disable a specific schedule."""
    if schedule_name in beat_schedule:
        beat_schedule[schedule_name]['enabled'] = False
        logger.info(f"Disabled schedule: {schedule_name}")
        return True
    return False


def update_schedule(schedule_name: str, new_schedule: dict) -> bool:
    """Update a specific schedule."""
    if schedule_name in beat_schedule:
        beat_schedule[schedule_name].update(new_schedule)
        logger.info(f"Updated schedule: {schedule_name}")
        return True
    return False


def add_custom_schedule(name: str, task: str, schedule: str, **kwargs) -> bool:
    """Add a custom schedule."""
    try:
        beat_schedule[name] = {
            'task': task,
            'schedule': schedule,
            'options': kwargs.get('options', {}),
            'enabled': kwargs.get('enabled', True)
        }
        logger.info(f"Added custom schedule: {name}")
        return True
    except Exception as e:
        logger.error(f"Error adding custom schedule {name}: {e}")
        return False


def remove_schedule(schedule_name: str) -> bool:
    """Remove a schedule."""
    if schedule_name in beat_schedule:
        del beat_schedule[schedule_name]
        logger.info(f"Removed schedule: {schedule_name}")
        return True
    return False


# Configuration validation
def validate_schedule_config() -> dict:
    """Validate the schedule configuration."""
    validation_result = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'total_schedules': len(beat_schedule)
    }
    
    for name, schedule in beat_schedule.items():
        # Check required fields
        if 'task' not in schedule:
            validation_result['valid'] = False
            validation_result['errors'].append(f"Schedule {name} missing 'task' field")
        
        if 'schedule' not in schedule:
            validation_result['valid'] = False
            validation_result['errors'].append(f"Schedule {name} missing 'schedule' field")
        
        # Check task format
        if 'task' in schedule and not schedule['task'].startswith('api.gamification.tasks.'):
            validation_result['warnings'].append(f"Schedule {name} task may not be in correct format")
    
    return validation_result


# Initialize beat schedule
app.conf.beat_schedule = beat_schedule
logger.info(f"Initialized {len(beat_schedule)} Celery beat schedules for gamification")
