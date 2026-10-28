# engagement/background_jobs.py
"""
Background job system for engagement gamification.
Provides asynchronous task processing and job management.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import traceback
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Job status types."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class JobPriority(Enum):
    """Job priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Job:
    """Background job definition."""
    id: str
    name: str
    function: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
    max_retries: int = 3
    retry_count: int = 0
    created_at: datetime = field(default_factory=timezone.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status.value,
            'priority': self.priority.value,
            'max_retries': self.max_retries,
            'retry_count': self.retry_count,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'metadata': self.metadata
        }


class BaseJobProcessor(ABC):
    """Base job processor class."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def process_job(self, job: Job) -> Any:
        """Process a background job."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if processor is available."""
        pass


class CeleryJobProcessor(BaseJobProcessor):
    """Celery job processor."""
    
    def __init__(self):
        super().__init__("celery")
        self.celery_app = None
    
    def process_job(self, job: Job) -> Any:
        """Process job using Celery."""
        try:
            from celery import current_app
            
            if self.celery_app is None:
                self.celery_app = current_app
            
            # Execute the job function
            result = job.function(*job.args, **job.kwargs)
            return result
            
        except Exception as exc:
            self.logger.error(f"Failed to process Celery job {job.id}: {exc}")
            raise
    
    def is_available(self) -> bool:
        """Check if Celery is available."""
        try:
            from celery import current_app
            return current_app is not None
        except ImportError:
            return False


class ThreadJobProcessor(BaseJobProcessor):
    """Thread-based job processor."""
    
    def __init__(self, max_workers: int = 4):
        super().__init__("thread")
        self.max_workers = max_workers
        self.active_jobs = {}
    
    def process_job(self, job: Job) -> Any:
        """Process job in a thread."""
        try:
            import threading
            import queue
            
            def execute_job():
                try:
                    job.status = JobStatus.RUNNING
                    job.started_at = timezone.now()
                    
                    result = job.function(*job.args, **job.kwargs)
                    
                    job.status = JobStatus.COMPLETED
                    job.completed_at = timezone.now()
                    job.result = result
                    
                    return result
                    
                except Exception as exc:
                    job.status = JobStatus.FAILED
                    job.completed_at = timezone.now()
                    job.error_message = str(exc)
                    self.logger.error(f"Thread job {job.id} failed: {exc}")
                    raise
                finally:
                    if job.id in self.active_jobs:
                        del self.active_jobs[job.id]
            
            # Check if we have available workers
            if len(self.active_jobs) >= self.max_workers:
                raise Exception("Maximum workers reached")
            
            # Execute job in thread
            thread = threading.Thread(target=execute_job)
            self.active_jobs[job.id] = thread
            thread.start()
            
            # Wait for completion (simplified)
            thread.join()
            
            return job.result
            
        except Exception as exc:
            self.logger.error(f"Failed to process thread job {job.id}: {exc}")
            raise
    
    def is_available(self) -> bool:
        """Check if thread processor is available."""
        return len(self.active_jobs) < self.max_workers


class BackgroundJobManager:
    """Manager for background jobs."""
    
    def __init__(self):
        self.processors = {
            'celery': CeleryJobProcessor(),
            'thread': ThreadJobProcessor(),
        }
        self.job_queue = []
        self.completed_jobs = []
        self.max_queue_size = 1000
        self._setup_processors()
    
    def _setup_processors(self):
        """Setup job processors."""
        # Check which processors are available
        available_processors = []
        
        for name, processor in self.processors.items():
            if processor.is_available():
                available_processors.append(name)
                logger.info(f"Job processor '{name}' is available")
            else:
                logger.warning(f"Job processor '{name}' is not available")
        
        if not available_processors:
            logger.warning("No job processors available")
    
    def submit_job(self, name: str, function: Callable, args: tuple = (), 
                   kwargs: Dict[str, Any] = None, priority: JobPriority = JobPriority.NORMAL,
                   max_retries: int = 3, metadata: Dict[str, Any] = None) -> str:
        """Submit a background job."""
        if len(self.job_queue) >= self.max_queue_size:
            raise Exception("Job queue is full")
        
        job_id = self._generate_job_id()
        
        job = Job(
            id=job_id,
            name=name,
            function=function,
            args=args,
            kwargs=kwargs or {},
            priority=priority,
            max_retries=max_retries,
            metadata=metadata or {}
        )
        
        self.job_queue.append(job)
        
        # Sort queue by priority
        self.job_queue.sort(key=lambda j: self._priority_value(j.priority), reverse=True)
        
        logger.info(f"Submitted job {job_id}: {name}")
        return job_id
    
    def process_next_job(self) -> Optional[Job]:
        """Process the next job in the queue."""
        if not self.job_queue:
            return None
        
        job = self.job_queue.pop(0)
        
        try:
            # Try to process with available processor
            for processor_name, processor in self.processors.items():
                if processor.is_available():
                    result = processor.process_job(job)
                    job.result = result
                    break
            else:
                # No processors available
                job.status = JobStatus.FAILED
                job.error_message = "No processors available"
                logger.error(f"No processors available for job {job.id}")
            
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            logger.error(f"Failed to process job {job.id}: {exc}")
            
            # Check if we should retry
            if job.retry_count < job.max_retries:
                job.retry_count += 1
                job.status = JobStatus.RETRYING
                job.error_message = f"Retry {job.retry_count}/{job.max_retries}: {str(exc)}"
                
                # Add back to queue with lower priority
                self.job_queue.append(job)
                logger.info(f"Retrying job {job.id} ({job.retry_count}/{job.max_retries})")
        
        # Move to completed jobs
        self.completed_jobs.append(job)
        
        # Limit completed jobs history
        if len(self.completed_jobs) > 1000:
            self.completed_jobs = self.completed_jobs[-1000:]
        
        return job
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status by ID."""
        # Check queue
        for job in self.job_queue:
            if job.id == job_id:
                return job.to_dict()
        
        # Check completed jobs
        for job in self.completed_jobs:
            if job.id == job_id:
                return job.to_dict()
        
        return None
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        # Check queue
        for i, job in enumerate(self.job_queue):
            if job.id == job_id:
                job.status = JobStatus.CANCELLED
                self.completed_jobs.append(self.job_queue.pop(i))
                logger.info(f"Cancelled job {job_id}")
                return True
        
        return False
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get queue status."""
        status_counts = {}
        
        for status in JobStatus:
            status_counts[status.value] = 0
        
        # Count jobs in queue
        for job in self.job_queue:
            status_counts[job.status.value] += 1
        
        # Count completed jobs
        for job in self.completed_jobs:
            status_counts[job.status.value] += 1
        
        return {
            'queue_size': len(self.job_queue),
            'completed_jobs': len(self.completed_jobs),
            'status_counts': status_counts,
            'max_queue_size': self.max_queue_size,
            'processors': {
                name: processor.is_available()
                for name, processor in self.processors.items()
            }
        }
    
    def _generate_job_id(self) -> str:
        """Generate unique job ID."""
        import uuid
        return str(uuid.uuid4())
    
    def _priority_value(self, priority: JobPriority) -> int:
        """Convert priority to numeric value."""
        priority_values = {
            JobPriority.LOW: 1,
            JobPriority.NORMAL: 2,
            JobPriority.HIGH: 3,
            JobPriority.URGENT: 4,
        }
        return priority_values.get(priority, 2)


# Global job manager instance
background_job_manager = BackgroundJobManager()


# ── Predefined Jobs ─────────────────────────────────────────────────────

class EngagementJobs:
    """Predefined engagement jobs."""
    
    @staticmethod
    def process_daily_checkins():
        """Process daily check-ins for all users."""
        from .models.checkin import DailyCheckIn
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        today = timezone.now().date()
        
        # Get users who haven't checked in today
        checked_in_users = DailyCheckIn.objects.filter(
            date=today
        ).values_list('user_id', flat=True)
        
        all_users = User.objects.filter(is_active=True)
        missing_users = all_users.exclude(id__in=checked_in_users)
        
        # Send reminders to missing users
        for user in missing_users:
            try:
                from .notifications_push import NotificationTemplates, push_notification_manager
                from .services.checkin_service import CheckInService
                
                # Get current streak
                current_streak = CheckInService.get_current_streak(user)
                
                # Send reminder notification
                notification = NotificationTemplates.reminder(user, {
                    'current_streak': current_streak,
                    'last_checkin': (today - timedelta(days=1)).isoformat()
                })
                
                push_notification_manager.send_notification(
                    notification, 
                    user, 
                    ['push', 'email']
                )
                
            except Exception as exc:
                logger.error(f"Failed to send reminder to user {user.id}: {exc}")
        
        return {
            'total_users': all_users.count(),
            'checked_in_users': len(checked_in_users),
            'missing_users': missing_users.count(),
            'reminders_sent': missing_users.count()
        }
    
    @staticmethod
    def update_leaderboard():
        """Update daily leaderboard."""
        from .models.leaderboard import Leaderboard
        from .models.checkin import DailyCheckIn
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        today = timezone.now().date()
        
        # Get user statistics for today
        user_stats = {}
        
        # Check-ins
        checkins = DailyCheckIn.objects.filter(date=today)
        for checkin in checkins:
            user_id = checkin.user_id
            if user_id not in user_stats:
                user_stats[user_id] = {
                    'coins_earned': 0,
                    'xp_earned': 0
                }
            user_stats[user_id]['coins_earned'] += checkin.coins_earned
            user_stats[user_id]['xp_earned'] += checkin.xp_earned
        
        # Spins
        from .models.spinwheel import SpinWheel
        spins = SpinWheel.objects.filter(spun_at__date=today)
        for spin in spins:
            user_id = spin.user_id
            if user_id not in user_stats:
                user_stats[user_id] = {
                    'coins_earned': 0,
                    'xp_earned': 0
                }
            user_stats[user_id]['coins_earned'] += spin.coins_won
            user_stats[user_id]['xp_earned'] += spin.xp_earned
        
        # Create leaderboard entries
        rank = 1
        sorted_users = sorted(
            user_stats.items(),
            key=lambda x: (x[1]['coins_earned'], x[1]['xp_earned']),
            reverse=True
        )
        
        for user_id, stats in sorted_users:
            Leaderboard.objects.update_or_create(
                user_id=user_id,
                date=today,
                defaults={
                    'rank': rank,
                    'total_coins_earned': stats['coins_earned'],
                    'total_xp_earned': stats['xp_earned']
                }
            )
            rank += 1
        
        return {
            'date': today.isoformat(),
            'total_users': len(user_stats),
            'leaderboard_entries': len(sorted_users)
        }
    
    @staticmethod
    def cleanup_old_data():
        """Clean up old engagement data."""
        from .models.analytics import EngagementEvent
        from django.utils import timezone
        
        # Delete events older than 90 days
        cutoff_date = timezone.now() - timedelta(days=90)
        deleted_count = EngagementEvent.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        return {
            'cutoff_date': cutoff_date.isoformat(),
            'deleted_count': deleted_count
        }
    
    @staticmethod
    def generate_analytics_report():
        """Generate daily analytics report."""
        from .analytics import analytics_manager
        from datetime import timedelta
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=1)
        
        try:
            dashboard_data = analytics_manager.get_dashboard_data(
                period='daily',
                days=1
            )
            
            # Store report in cache
            cache.set(
                'daily_analytics_report',
                dashboard_data,
                timeout=86400  # 24 hours
            )
            
            return {
                'date': end_date.date().isoformat(),
                'report_data': dashboard_data
            }
            
        except Exception as exc:
            logger.error(f"Failed to generate analytics report: {exc}")
            return {
                'date': end_date.date().isoformat(),
                'error': str(exc)
            }
    
    @staticmethod
    def send_weekly_digest():
        """Send weekly digest to users."""
        from .notifications_push import NotificationTasks
        from datetime import timedelta
        
        try:
            NotificationTasks.send_weekly_digest()
            return {
                'status': 'completed',
                'timestamp': timezone.now().isoformat()
            }
        except Exception as exc:
            logger.error(f"Failed to send weekly digest: {exc}")
            return {
                'status': 'failed',
                'error': str(exc),
                'timestamp': timezone.now().isoformat()
            }
    
    @staticmethod
    def process_expired_quests():
        """Process expired quests."""
        from .models.quest import UserQuest
        from django.utils import timezone
        
        today = timezone.now().date()
        expired_quests = UserQuest.objects.filter(
            status__in=['available', 'active'],
            period_date__lt=today
        )
        
        # Mark as expired
        expired_count = expired_quests.update(status='expired')
        
        return {
            'expired_count': expired_count,
            'timestamp': timezone.now().isoformat()
        }
    
    @staticmethod
    def update_achievement_progress():
        """Update achievement progress for all users."""
        from .models.achievement import UserAchievement
        from .services.achievement_service import AchievementService
        
        updated_count = 0
        
        # Get all user achievements that aren't fully completed
        incomplete_achievements = UserAchievement.objects.filter(
            progress__lt=100,
            unlocked_at__isnull=True
        )
        
        for user_achievement in incomplete_achievements:
            try:
                # Recalculate progress
                progress = AchievementService.get_progress(
                    user_achievement.user,
                    user_achievement.achievement
                )
                
                if progress['progress'] != user_achievement.progress:
                    user_achievement.progress = progress['progress']
                    user_achievement.save()
                    updated_count += 1
                    
                    # Check if achievement is now unlocked
                    if progress['progress'] >= 100:
                        user_achievement.unlocked_at = timezone.now()
                        user_achievement.save()
                        
            except Exception as exc:
                logger.error(f"Failed to update achievement progress for user {user_achievement.user_id}: {exc}")
        
        return {
            'updated_count': updated_count,
            'timestamp': timezone.now().isoformat()
        }


# ── Job Decorators ─────────────────────────────────────────────────────

def background_job(name: str = None, priority: JobPriority = JobPriority.NORMAL, 
                   max_retries: int = 3):
    """Decorator to run function as background job."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            job_name = name or f"{func.__module__}.{func.__name__}"
            
            job_id = background_job_manager.submit_job(
                name=job_name,
                function=func,
                args=args,
                kwargs=kwargs,
                priority=priority,
                max_retries=max_retries
            )
            
            return job_id
        
        return wrapper
    return decorator


def async_job(name: str = None, priority: JobPriority = JobPriority.NORMAL):
    """Decorator to run function asynchronously."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            job_name = name or f"{func.__module__}.{func.__name__}"
            
            # Submit job and return immediately
            job_id = background_job_manager.submit_job(
                name=job_name,
                function=func,
                args=args,
                kwargs=kwargs,
                priority=priority
            )
            
            return {
                'job_id': job_id,
                'status': 'submitted',
                'name': job_name
            }
        
        return wrapper
    return decorator


# ── Job Scheduler ─────────────────────────────────────────────────────

class JobScheduler:
    """Scheduler for recurring jobs."""
    
    def __init__(self):
        self.scheduled_jobs = {}
        self.running = False
    
    def schedule_job(self, job_name: str, function: Callable, 
                    schedule: str, **kwargs):
        """Schedule a recurring job."""
        self.scheduled_jobs[job_name] = {
            'function': function,
            'schedule': schedule,
            'kwargs': kwargs,
            'last_run': None,
            'next_run': None
        }
    
    def run_scheduled_jobs(self):
        """Run jobs that are due."""
        from datetime import datetime, timedelta
        import re
        
        now = timezone.now()
        
        for job_name, job_info in self.scheduled_jobs.items():
            schedule = job_info['schedule']
            
            # Calculate next run time
            if job_info['next_run'] is None:
                job_info['next_run'] = self._calculate_next_run(schedule, now)
            
            # Check if job is due
            if now >= job_info['next_run']:
                try:
                    # Submit job
                    job_id = background_job_manager.submit_job(
                        name=job_name,
                        function=job_info['function'],
                        kwargs=job_info['kwargs']
                    )
                    
                    # Update schedule
                    job_info['last_run'] = now
                    job_info['next_run'] = self._calculate_next_run(schedule, now)
                    
                    logger.info(f"Scheduled job '{job_name}' executed (ID: {job_id})")
                    
                except Exception as exc:
                    logger.error(f"Failed to run scheduled job '{job_name}': {exc}")
    
    def _calculate_next_run(self, schedule: str, from_time: datetime) -> datetime:
        """Calculate next run time from schedule."""
        # Simple cron-like parsing
        # Format: "0 0 * * *" (minute hour day month weekday)
        parts = schedule.split()
        
        if len(parts) != 5:
            # Default to daily at midnight
            return from_time + timedelta(days=1)
        
        minute, hour, day, month, weekday = parts
        
        # Simplified calculation - just add 1 day for now
        # In practice, you'd want a proper cron parser
        return from_time + timedelta(days=1)
    
    def start(self):
        """Start the scheduler."""
        self.running = True
        logger.info("Job scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        self.running = False
        logger.info("Job scheduler stopped")


# Global scheduler instance
job_scheduler = JobScheduler()

# Setup default scheduled jobs
job_scheduler.schedule_job(
    'daily_checkins',
    EngagementJobs.process_daily_checkins,
    '0 9 * * *',  # 9 AM daily
)

job_scheduler.schedule_job(
    'leaderboard_update',
    EngagementJobs.update_leaderboard,
    '0 1 * * *',  # 1 AM daily
)

job_scheduler.schedule_job(
    'cleanup_old_data',
    EngagementJobs.cleanup_old_data,
    '0 2 * * 0',  # 2 AM on Sundays
)

job_scheduler.schedule_job(
    'analytics_report',
    EngagementJobs.generate_analytics_report,
    '0 8 * * *',  # 8 AM daily
)

job_scheduler.schedule_job(
    'weekly_digest',
    EngagementJobs.send_weekly_digest,
    '0 10 * * 1',  # 10 AM on Mondays
)

job_scheduler.schedule_job(
    'process_expired_quests',
    EngagementJobs.process_expired_quests,
    '0 */6 * * *',  # Every 6 hours
)

job_scheduler.schedule_job(
    'update_achievement_progress',
    EngagementJobs.update_achievement_progress,
    '0 3 * * *',  # 3 AM daily
)
