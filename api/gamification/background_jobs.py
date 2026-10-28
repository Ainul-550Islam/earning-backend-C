"""
Gamification Background Jobs — Asynchronous task processing.

This module provides background job processing capabilities for the gamification
system, including task queues, scheduled jobs, and async operations.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from api.gamification.models import (
    Badge, UserBadge, DailyChallenge, UserDailyChallenge,
    Streak, LevelConfig, ContestCycle, UserAchievement,
    WebhookEndpoint, WebhookEvent, WebhookDelivery
)
from api.gamification.choices import (
    BadgeRarity, BadgeCriteriaType, ChallengeAction,
    ContestCycleStatus, AchievementType, WebhookStatus, WebhookEventType
)
from api.gamification.exceptions import GamificationServiceError
from api.gamification.repositories import (
    BadgeRepository, UserBadgeRepository, StreakRepository,
    UserAchievementRepository, WebhookDeliveryRepository
)
from api.gamification.helpers import CacheHelper
from api.gamification.interactors import (
    BadgeInteractor, StreakInteractor, ChallengeInteractor,
    LevelInteractor, ContestInteractor, GamificationInteractor
)
from api.gamification.analytics import analytics_tracker
from api.gamification.caching import gamification_cache, cache_invalidator

User = get_user_model()
logger = logging.getLogger(__name__)


class BackgroundJob:
    """Represents a background job."""
    
    def __init__(self, job_id: str, job_type: str, payload: Dict[str, Any],
                 priority: str = "normal", max_retries: int = 3,
                 delay: Optional[int] = None, created_at: Optional[datetime] = None):
        self.job_id = job_id
        self.job_type = job_type
        self.payload = payload
        self.priority = priority  # low, normal, high, critical
        self.max_retries = max_retries
        self.retry_count = 0
        self.delay = delay  # Delay in seconds before execution
        self.created_at = created_at or timezone.now()
        self.scheduled_at = self.created_at + timedelta(seconds=delay) if delay else self.created_at
        self.status = "pending"  # pending, running, completed, failed, cancelled
        self.result = None
        self.error = None
        self.started_at = None
        self.completed_at = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary."""
        return {
            'job_id': self.job_id,
            'job_type': self.job_type,
            'payload': self.payload,
            'priority': self.priority,
            'max_retries': self.max_retries,
            'retry_count': self.retry_count,
            'delay': self.delay,
            'created_at': self.created_at.isoformat(),
            'scheduled_at': self.scheduled_at.isoformat(),
            'status': self.status,
            'result': self.result,
            'error': self.error,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class JobQueue:
    """Job queue manager."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.queues = {
            'low': [],
            'normal': [],
            'high': [],
            'critical': []
        }
        self.running_jobs = {}
        self.completed_jobs = {}
        self.failed_jobs = {}
    
    def enqueue(self, job: BackgroundJob) -> bool:
        """Add job to queue."""
        try:
            self.queues[job.priority].append(job)
            self.logger.info(f"Job {job.job_id} enqueued in {job.priority} priority queue")
            return True
        except Exception as e:
            self.logger.error(f"Error enqueuing job {job.job_id}: {e}")
            return False
    
    def dequeue(self) -> Optional[BackgroundJob]:
        """Get next job from queue (highest priority first)."""
        try:
            # Check queues in priority order
            for priority in ['critical', 'high', 'normal', 'low']:
                if self.queues[priority]:
                    job = self.queues[priority].pop(0)
                    return job
            return None
        except Exception as e:
            self.logger.error(f"Error dequeuing job: {e}")
            return None
    
    def get_ready_jobs(self) -> List[BackgroundJob]:
        """Get jobs that are ready to run."""
        ready_jobs = []
        now = timezone.now()
        
        for priority in ['critical', 'high', 'normal', 'low']:
            queue_jobs = []
            for job in self.queues[priority]:
                if job.scheduled_at <= now:
                    queue_jobs.append(job)
                else:
                    # Keep jobs that aren't ready yet
                    queue_jobs.append(job)
            
            self.queues[priority] = queue_jobs
            ready_jobs.extend(queue_jobs)
        
        return ready_jobs
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            'pending_jobs': {
                'critical': len(self.queues['critical']),
                'high': len(self.queues['high']),
                'normal': len(self.queues['normal']),
                'low': len(self.queues['low']),
                'total': sum(len(queue) for queue in self.queues.values())
            },
            'running_jobs': len(self.running_jobs),
            'completed_jobs': len(self.completed_jobs),
            'failed_jobs': len(self.failed_jobs),
            'generated_at': timezone.now().isoformat()
        }


class JobProcessor:
    """Job processor for executing background jobs."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.handlers = {}
        self._register_handlers()
    
    def _register_handlers(self):
        """Register job handlers."""
        self.handlers = {
            'award_badges': self._handle_award_badges,
            'update_streaks': self._handle_update_streaks,
            'process_challenges': self._handle_process_challenges,
            'calculate_leaderboards': self._handle_calculate_leaderboards,
            'send_notifications': self._handle_send_notifications,
            'process_webhooks': self._handle_process_webhooks,
            'cleanup_expired_data': self._handle_cleanup_expired_data,
            'generate_reports': self._handle_generate_reports,
            'cache_warmup': self._handle_cache_warmup,
            'user_analytics': self._handle_user_analytics
        }
    
    def process_job(self, job: BackgroundJob) -> Dict[str, Any]:
        """Process a single job."""
        try:
            job.status = "running"
            job.started_at = timezone.now()
            
            handler = self.handlers.get(job.job_type)
            if not handler:
                raise ValueError(f"No handler found for job type: {job.job_type}")
            
            self.logger.info(f"Processing job {job.job_id} of type {job.job_type}")
            
            # Execute the job
            result = handler(job.payload)
            
            job.status = "completed"
            job.result = result
            job.completed_at = timezone.now()
            
            self.logger.info(f"Job {job.job_id} completed successfully")
            
            return {
                'success': True,
                'result': result,
                'job_id': job.job_id
            }
            
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            job.completed_at = timezone.now()
            job.retry_count += 1
            
            self.logger.error(f"Job {job.job_id} failed: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'job_id': job.job_id,
                'retry_count': job.retry_count
            }
    
    def _handle_award_badges(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle badge awarding job."""
        user_id = payload.get('user_id')
        metadata = payload.get('metadata', {})
        
        badge_interactor = BadgeInteractor()
        result = badge_interactor.award_badges_with_notifications(user_id, metadata)
        
        # Track analytics
        analytics_tracker.track_badge_earned(
            user_id, result.get('badge_id', ''), 
            result.get('badge_name', ''), result.get('badge_rarity', ''),
            result.get('points_bonus', 0)
        )
        
        return result
    
    def _handle_update_streaks(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle streak update job."""
        user_id = payload.get('user_id')
        activity_date = payload.get('activity_date')
        if activity_date:
            activity_date = datetime.fromisoformat(activity_date).date()
        
        metadata = payload.get('metadata', {})
        
        streak_interactor = StreakInteractor()
        result = streak_interactor.update_streak_with_milestones(user_id, activity_date, metadata)
        
        # Track analytics
        analytics_tracker.track_streak_updated(user_id, result['streak']['current_days'], result['was_extended'])
        
        # Invalidate cache
        cache_invalidator.invalidate_on_streak_update(user_id)
        
        return result
    
    def _handle_process_challenges(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle challenge processing job."""
        user_id = payload.get('user_id')
        challenge_id = payload.get('challenge_id')
        increment_amount = payload.get('increment_amount', 1)
        action_metadata = payload.get('action_metadata', {})
        
        challenge_interactor = ChallengeInteractor()
        result = challenge_interactor.complete_challenge_with_rewards(
            user_id, challenge_id, increment_amount, action_metadata
        )
        
        # Track analytics
        analytics_tracker.track_challenge_completed(
            user_id, challenge_id, result.get('challenge_title', ''),
            result.get('bonus_points', 0)
        )
        
        # Invalidate cache
        cache_invalidator.invalidate_on_challenge_completion(user_id, challenge_id)
        
        return result
    
    def _handle_calculate_leaderboards(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle leaderboard calculation job."""
        scope = payload.get('scope', 'global')
        limit = payload.get('limit', 100)
        
        from api.gamification.helpers import LeaderboardHelper
        leaderboard = LeaderboardHelper.get_leaderboard(scope, limit)
        
        # Update cache
        from api.gamification.caching import set_cached_leaderboard
        set_cached_leaderboard(scope, leaderboard, limit)
        
        return {
            'scope': scope,
            'limit': limit,
            'leaderboard': leaderboard,
            'updated_at': timezone.now().isoformat()
        }
    
    def _handle_send_notifications(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle notification sending job."""
        user_id = payload.get('user_id')
        template_id = payload.get('template_id')
        context = payload.get('context', {})
        provider = payload.get('provider')
        
        from api.gamification.notifications_push import push_notification_service
        result = push_notification_service.send_notification(user_id, template_id, context, provider)
        
        return result
    
    def _handle_process_webhooks(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle webhook processing job."""
        webhook_id = payload.get('webhook_id')
        event_id = payload.get('event_id')
        
        from api.gamification.webhooks import WebhookService
        webhook_service = WebhookService()
        
        # Process webhook delivery
        delivery = webhook_service.process_webhook_delivery(webhook_id, event_id)
        
        return {
            'webhook_id': webhook_id,
            'event_id': event_id,
            'delivery_id': str(delivery.id) if delivery else None,
            'status': delivery.status if delivery else 'failed'
        }
    
    def _handle_cleanup_expired_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle expired data cleanup job."""
        cleanup_type = payload.get('cleanup_type', 'all')
        days_old = payload.get('days_old', 30)
        
        results = {}
        
        if cleanup_type in ['all', 'webhook_events']:
            # Clean up old webhook events
            from api.gamification.webhooks import WebhookService
            webhook_service = WebhookService()
            deleted_events = webhook_service.cleanup_old_events(days_old)
            results['webhook_events_deleted'] = deleted_events
        
        if cleanup_type in ['all', 'cache']:
            # Clean up expired cache entries
            from api.gamification.caching import gamification_cache
            cache_stats = gamification_cache.get_cache_stats()
            results['cache_stats'] = cache_stats
        
        if cleanup_type in ['all', 'logs']:
            # Clean up old log entries (if applicable)
            results['logs_cleaned'] = "Not implemented"
        
        return {
            'cleanup_type': cleanup_type,
            'days_old': days_old,
            'results': results,
            'completed_at': timezone.now().isoformat()
        }
    
    def _handle_generate_reports(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle report generation job."""
        report_type = payload.get('report_type', 'daily')
        date = payload.get('date')
        if date:
            date = datetime.fromisoformat(date).date()
        
        from api.gamification.analytics import report_generator
        
        if report_type == 'daily':
            report = report_generator.generate_daily_report(date)
        elif report_type == 'weekly':
            start_date = payload.get('start_date')
            if start_date:
                start_date = datetime.fromisoformat(start_date).date()
            report = report_generator.generate_weekly_report(start_date)
        elif report_type == 'monthly':
            year = payload.get('year')
            month = payload.get('month')
            report = report_generator.generate_monthly_report(year, month)
        else:
            raise ValueError(f"Unknown report type: {report_type}")
        
        return report
    
    def _handle_cache_warmup(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cache warmup job."""
        warmup_type = payload.get('warmup_type', 'system')
        
        from api.gamification.caching import cache_warmer
        
        if warmup_type == 'system':
            results = cache_warmer.warm_system_cache()
        elif warmup_type == 'user':
            user_id = payload.get('user_id')
            results = cache_warmer.warm_user_cache(user_id)
        elif warmup_type == 'leaderboard':
            scope = payload.get('scope', 'global')
            limit = payload.get('limit', 100)
            results = cache_warmer.warm_leaderboard_cache(scope, limit)
        else:
            raise ValueError(f"Unknown warmup type: {warmup_type}")
        
        return results
    
    def _handle_user_analytics(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user analytics job."""
        user_id = payload.get('user_id')
        analytics_type = payload.get('analytics_type', 'engagement')
        
        from api.gamification.analytics import UserAnalytics
        user_analytics = UserAnalytics(user_id)
        
        if analytics_type == 'engagement':
            days = payload.get('days', 30)
            result = user_analytics.get_user_engagement_summary(days)
        elif analytics_type == 'progression':
            result = user_analytics.get_user_progression_analysis()
        elif analytics_type == 'behavior':
            result = user_analytics.get_user_behavior_patterns()
        else:
            raise ValueError(f"Unknown analytics type: {analytics_type}")
        
        return result


class JobScheduler:
    """Job scheduler for managing scheduled and recurring jobs."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.scheduled_jobs = {}
        self.recurring_jobs = {}
        self._register_scheduled_jobs()
    
    def _register_scheduled_jobs(self):
        """Register scheduled jobs."""
        # Daily jobs
        self.recurring_jobs['daily_challenge_reset'] = {
            'schedule': '0 0 * * *',  # Daily at midnight
            'job_type': 'process_challenges',
            'payload': {'action': 'reset_daily'},
            'enabled': True
        }
        
        self.recurring_jobs['daily_cleanup'] = {
            'schedule': '0 2 * * *',  # Daily at 2 AM
            'job_type': 'cleanup_expired_data',
            'payload': {'cleanup_type': 'all', 'days_old': 30},
            'enabled': True
        }
        
        self.recurring_jobs['daily_report'] = {
            'schedule': '0 1 * * *',  # Daily at 1 AM
            'job_type': 'generate_reports',
            'payload': {'report_type': 'daily'},
            'enabled': True
        }
        
        # Weekly jobs
        self.recurring_jobs['weekly_report'] = {
            'schedule': '0 1 * * 0',  # Sunday at 1 AM
            'job_type': 'generate_reports',
            'payload': {'report_type': 'weekly'},
            'enabled': True
        }
        
        self.recurring_jobs['weekly_leaderboard'] = {
            'schedule': '0 0 * * 1',  # Monday at midnight
            'job_type': 'calculate_leaderboards',
            'payload': {'scope': 'weekly'},
            'enabled': True
        }
        
        # Hourly jobs
        self.recurring_jobs['hourly_cache_warmup'] = {
            'schedule': '0 * * * *',  # Every hour
            'job_type': 'cache_warmup',
            'payload': {'warmup_type': 'leaderboard'},
            'enabled': True
        }
        
        # Monthly jobs
        self.recurring_jobs['monthly_report'] = {
            'schedule': '0 1 1 * *',  # 1st of month at 1 AM
            'job_type': 'generate_reports',
            'payload': {'report_type': 'monthly'},
            'enabled': True
        }
    
    def get_due_jobs(self) -> List[BackgroundJob]:
        """Get jobs that are due to run."""
        due_jobs = []
        now = timezone.now()
        
        for job_name, job_config in self.recurring_jobs.items():
            if not job_config['enabled']:
                continue
            
            # Simple schedule check (in production, use a proper cron library)
            if self._is_job_due(job_config['schedule'], now):
                job_id = f"scheduled_{job_name}_{int(now.timestamp())}"
                
                job = BackgroundJob(
                    job_id=job_id,
                    job_type=job_config['job_type'],
                    payload=job_config['payload'],
                    priority='normal'
                )
                
                due_jobs.append(job)
        
        return due_jobs
    
    def _is_job_due(self, schedule: str, now: datetime) -> bool:
        """Check if job is due based on cron schedule."""
        # Simplified cron parsing - in production, use a proper cron library
        # For now, just check basic patterns
        
        parts = schedule.split()
        if len(parts) != 5:
            return False
        
        minute, hour, day, month, weekday = parts
        
        # Check minute
        if minute != '*' and int(minute) != now.minute:
            return False
        
        # Check hour
        if hour != '*' and int(hour) != now.hour:
            return False
        
        # Check day
        if day != '*' and int(day) != now.day:
            return False
        
        # Check month
        if month != '*' and int(month) != now.month:
            return False
        
        # Check weekday (0=Sunday, 6=Saturday)
        if weekday != '*' and int(weekday) != now.weekday():
            return False
        
        return True
    
    def schedule_job(self, job: BackgroundJob, delay: Optional[int] = None) -> bool:
        """Schedule a job for future execution."""
        if delay:
            job.delay = delay
            job.scheduled_at = timezone.now() + timedelta(seconds=delay)
        
        self.scheduled_jobs[job.job_id] = job
        
        self.logger.info(f"Job {job.job_id} scheduled for {job.scheduled_at}")
        
        return True
    
    def cancel_scheduled_job(self, job_id: str) -> bool:
        """Cancel a scheduled job."""
        if job_id in self.scheduled_jobs:
            job = self.scheduled_jobs[job_id]
            job.status = "cancelled"
            del self.scheduled_jobs[job_id]
            
            self.logger.info(f"Scheduled job {job_id} cancelled")
            return True
        
        return False
    
    def get_scheduled_jobs(self) -> List[BackgroundJob]:
        """Get all scheduled jobs."""
        return list(self.scheduled_jobs.values())


class BackgroundJobManager:
    """Main manager for background jobs."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.queue = JobQueue()
        self.processor = JobProcessor()
        self.scheduler = JobScheduler()
        self.is_running = False
        self.worker_count = getattr(settings, 'GAMIFICATION_JOB_WORKERS', 2)
        self.job_timeout = getattr(settings, 'GAMIFICATION_JOB_TIMEOUT', 300)  # 5 minutes
    
    def start_workers(self) -> None:
        """Start background job workers."""
        if self.is_running:
            self.logger.warning("Background job workers are already running")
            return
        
        self.is_running = True
        self.logger.info(f"Starting {self.worker_count} background job workers")
        
        # In a real implementation, this would start actual worker threads/processes
        # For now, we'll simulate the workers
        for i in range(self.worker_count):
            self.logger.info(f"Worker {i+1} started")
    
    def stop_workers(self) -> None:
        """Stop background job workers."""
        if not self.is_running:
            self.logger.warning("Background job workers are not running")
            return
        
        self.is_running = False
        self.logger.info("Stopping background job workers")
    
    def enqueue_job(self, job_type: str, payload: Dict[str, Any],
                    priority: str = "normal", delay: Optional[int] = None,
                    max_retries: int = 3) -> str:
        """Enqueue a background job."""
        import uuid
        
        job_id = str(uuid.uuid4())
        
        job = BackgroundJob(
            job_id=job_id,
            job_type=job_type,
            payload=payload,
            priority=priority,
            max_retries=max_retries,
            delay=delay
        )
        
        if self.queue.enqueue(job):
            return job_id
        else:
            raise GamificationServiceError("Failed to enqueue job")
    
    def process_jobs(self) -> Dict[str, Any]:
        """Process pending jobs (simulated worker loop)."""
        processed_count = 0
        failed_count = 0
        
        try:
            # Get scheduled jobs
            scheduled_jobs = self.scheduler.get_due_jobs()
            for job in scheduled_jobs:
                self.queue.enqueue(job)
            
            # Process jobs from queue
            while True:
                job = self.queue.dequeue()
                if not job:
                    break
                
                # Check if job is ready
                if job.scheduled_at > timezone.now():
                    # Put it back in queue
                    self.queue.enqueue(job)
                    break
                
                # Process the job
                result = self.processor.process_job(job)
                
                if result['success']:
                    processed_count += 1
                    self.queue.completed_jobs[job.job_id] = job
                else:
                    failed_count += 1
                    
                    # Retry logic
                    if job.retry_count < job.max_retries:
                        job.retry_count += 1
                        job.status = "pending"
                        job.scheduled_at = timezone.now() + timedelta(minutes=2 ** job.retry_count)
                        self.queue.enqueue(job)
                        self.logger.info(f"Job {job.job_id} scheduled for retry {job.retry_count}")
                    else:
                        self.queue.failed_jobs[job.job_id] = job
                        self.logger.error(f"Job {job.job_id} failed permanently after {job.max_retries} retries")
        
        except Exception as e:
            self.logger.error(f"Error processing jobs: {e}")
        
        return {
            'processed_count': processed_count,
            'failed_count': failed_count,
            'queue_stats': self.queue.get_queue_stats()
        }
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific job."""
        # Check all job collections
        for job_collection in [self.queue.completed_jobs, self.queue.failed_jobs, self.scheduler.scheduled_jobs]:
            if job_id in job_collection:
                return job_collection[job_id].to_dict()
        
        # Check running jobs
        if job_id in self.queue.running_jobs:
            return self.queue.running_jobs[job_id].to_dict()
        
        return None
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        # Try to cancel scheduled job
        if self.scheduler.cancel_scheduled_job(job_id):
            return True
        
        # Try to cancel queued job
        for priority in ['critical', 'high', 'normal', 'low']:
            queue = self.queue.queues[priority]
            for i, job in enumerate(queue):
                if job.job_id == job_id:
                    job.status = "cancelled"
                    queue.pop(i)
                    self.logger.info(f"Job {job_id} cancelled from queue")
                    return True
        
        return False
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get background job system status."""
        return {
            'is_running': self.is_running,
            'worker_count': self.worker_count,
            'queue_stats': self.queue.get_queue_stats(),
            'scheduled_jobs_count': len(self.scheduler.get_scheduled_jobs()),
            'recurring_jobs_count': len(self.scheduler.recurring_jobs),
            'system_status': 'healthy' if self.is_running else 'stopped'
        }


# Global instance
background_job_manager = BackgroundJobManager()


# Convenience functions
def enqueue_background_job(job_type: str, payload: Dict[str, Any],
                         priority: str = "normal", delay: Optional[int] = None,
                         max_retries: int = 3) -> str:
    """Enqueue a background job."""
    return background_job_manager.enqueue_job(job_type, payload, priority, delay, max_retries)


def process_background_jobs() -> Dict[str, Any]:
    """Process pending background jobs."""
    return background_job_manager.process_jobs()


def get_background_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Get status of a background job."""
    return background_job_manager.get_job_status(job_id)


def cancel_background_job(job_id: str) -> bool:
    """Cancel a background job."""
    return background_job_manager.cancel_job(job_id)


def get_background_job_system_status() -> Dict[str, Any]:
    """Get background job system status."""
    return background_job_manager.get_system_status()


# Predefined job functions
def award_badges_async(user_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """Enqueue badge awarding job."""
    return enqueue_background_job(
        'award_badges',
        {'user_id': user_id, 'metadata': metadata or {}},
        priority='high'
    )


def update_streak_async(user_id: str, activity_date: Optional[datetime.date] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> str:
    """Enqueue streak update job."""
    return enqueue_background_job(
        'update_streaks',
        {
            'user_id': user_id,
            'activity_date': activity_date.isoformat() if activity_date else None,
            'metadata': metadata or {}
        },
        priority='normal'
    )


def complete_challenge_async(user_id: str, challenge_id: str,
                           increment_amount: int = 1,
                           action_metadata: Optional[Dict[str, Any]] = None) -> str:
    """Enqueue challenge completion job."""
    return enqueue_background_job(
        'process_challenges',
        {
            'user_id': user_id,
            'challenge_id': challenge_id,
            'increment_amount': increment_amount,
            'action_metadata': action_metadata or {}
        },
        priority='normal'
    )


def calculate_leaderboard_async(scope: str = "global", limit: int = 100) -> str:
    """Enqueue leaderboard calculation job."""
    return enqueue_background_job(
        'calculate_leaderboards',
        {'scope': scope, 'limit': limit},
        priority='low'
    )


def send_notification_async(user_id: str, template_id: str,
                         context: Optional[Dict[str, Any]] = None) -> str:
    """Enqueue notification sending job."""
    return enqueue_background_job(
        'send_notifications',
        {
            'user_id': user_id,
            'template_id': template_id,
            'context': context or {}
        },
        priority='normal'
    )


def generate_report_async(report_type: str, **kwargs) -> str:
    """Enqueue report generation job."""
    payload = {'report_type': report_type}
    payload.update(kwargs)
    
    return enqueue_background_job(
        'generate_reports',
        payload,
        priority='low'
    )


def cleanup_expired_data_async(days_old: int = 30) -> str:
    """Enqueue data cleanup job."""
    return enqueue_background_job(
        'cleanup_expired_data',
        {'cleanup_type': 'all', 'days_old': days_old},
        priority='low'
    )


def warm_cache_async(warmup_type: str = "system", **kwargs) -> str:
    """Enqueue cache warmup job."""
    payload = {'warmup_type': warmup_type}
    payload.update(kwargs)
    
    return enqueue_background_job(
        'cache_warmup',
        payload,
        priority='low'
    )
