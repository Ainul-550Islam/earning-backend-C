# api/cms/background_jobs.py
"""Background job management for CMS."""
from celery import shared_task
import logging
from typing import Any, Dict, List, Optional, Union, Callable
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.conf import settings
import threading
import queue
import time
import uuid

from api.cms.abstracts import BaseService
from api.cms.monitoring import CMSMetrics
from api.cms.caching import CMSCache

logger = logging.getLogger(__name__)
User = get_user_model()


# ── Original Background Jobs (Preserved) ─────────────────────────────────────

class BackgroundJobRunner:
    """
    Job runner that tracks progress and handles failures gracefully.
    """
    @staticmethod
    def run_with_progress(job_name: str, items: List[Any],
                           processor_fn, batch_size: int = 100) -> Dict:
        total = len(items)
        processed = 0
        failed = 0
        errors = []
        for i in range(0, total, batch_size):
            batch = items[i:i + batch_size]
            for item in batch:
                try:
                    processor_fn(item)
                    processed += 1
                except Exception as e:
                    failed += 1
                    errors.append(str(e))
                    logger.warning(f"[Job:{job_name}] item failed: {e}")
        logger.info(f"[Job:{job_name}] complete: {processed}/{total} processed, {failed} failed")
        return {'job': job_name, 'total': total, 'processed': processed,
                'failed': failed, 'errors': errors[:10]}


@shared_task(name='cms.jobs.bulk_award_coins', bind=True, max_retries=2)
def bulk_award_coins_job(self, user_ids: List[int], coins_each: float,
                          reason: str = 'Bulk bonus') -> Dict:
    """Award coins to multiple users in bulk."""
    from api.cms.services_new.CPALeadService import VirtualCurrencyService
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    User = get_user_model()
    results = {'awarded': 0, 'failed': 0}
    for user_id in user_ids:
        try:
            user = User.objects.get(id=user_id, is_active=True)
            VirtualCurrencyService.award_coins(
                user=user, amount=Decimal(str(coins_each)),
                reason=reason, tx_type='earn_bonus',
            )
            results['awarded'] += 1
        except Exception as e:
            results['failed'] += 1
            logger.warning(f"[BulkAward] user {user_id} failed: {e}")
    return results


@shared_task(name='cms.jobs.batch_send_notifications', bind=True, max_retries=2)
def batch_send_notifications_job(self, user_ids: List[int], title: str,
                                   body: str, notif_type: str = 'system') -> Dict:
    """Send notifications to multiple users."""
    from api.cms.repositories import NotificationRepository
    from django.contrib.auth import get_user_model
    User = get_user_model()
    sent = 0
    for user_id in user_ids:
        try:
            user = User.objects.get(id=user_id, is_active=True)
            NotificationRepository.create(user, notif_type, title, body)
            sent += 1
        except Exception as e:
            logger.debug(f"[BatchNotify] user {user_id} failed: {e}")
    return {'sent': sent, 'total': len(user_ids)}


@shared_task(name='cms.jobs.recalculate_all_levels')
def recalculate_all_user_levels_job() -> Dict:
    """Recalculate levels for all users. Run weekly."""
    from api.cms.services_new.WithdrawalService import UserProfileService
    from api.cms.models_new.withdrawal import UserProfile
    updated = 0
    for profile in UserProfile.objects.select_related('user').all():
        try:
            old = profile.level
            new_level = UserProfileService.update_level(profile.user)
            if old != new_level:
                updated += 1
        except Exception:
            pass
    logger.info(f"[Job] Recalculated levels: {updated} users updated")
    return {'updated': updated}


@shared_task(name='cms.jobs.expire_quiz_attempts')
def expire_incomplete_quiz_attempts_job() -> Dict:
    """Cancel quiz attempts that were abandoned (>1 hour old, incomplete)."""
    from api.cms.models_new.quiz import QuizAttempt
    from django.utils import timezone
    import datetime
    cutoff = timezone.now() - datetime.timedelta(hours=1)
    deleted, _ = QuizAttempt.objects.filter(
        is_completed=False, created_at__lt=cutoff
    ).delete()
    return {'expired': deleted}


@shared_task(name='cms.jobs.sync_leaderboard_to_cache')
def sync_leaderboard_cache_job() -> Dict:
    """Sync leaderboard data to Redis cache for fast reads."""
    from api.cms.services_new.LeaderboardService import LeaderboardService
    synced = 0
    for period in ['daily', 'weekly', 'monthly']:
        for cat in ['earnings', 'coins', 'offers']:
            try:
                count = LeaderboardService.refresh_ranks(period, cat)
                synced += count
            except Exception as e:
                logger.warning(f"[Job] Leaderboard sync failed {period}/{cat}: {e}")
    return {'synced': synced}


@shared_task(name='cms.jobs.cleanup_orphaned_media')
def cleanup_orphaned_media_job(dry_run: bool = True) -> Dict:
    """Find and optionally delete orphaned media files."""
    import os
    from django.conf import settings
    media_root = getattr(settings, 'MEDIA_ROOT', '')
    if not media_root or not os.path.exists(media_root):
        return {'error': 'MEDIA_ROOT not configured'}
    count = 0
    for root, dirs, files in os.walk(media_root):
        for fname in files:
            fpath = os.path.join(root, fname)
            # Add DB check here in production
            count += 1
    return {'files_found': count, 'dry_run': dry_run}


@shared_task(name='cms.jobs.generate_weekly_report')
def generate_weekly_report_job() -> Dict:
    """Generate weekly analytics report for admin."""
    from api.cms.analytics import CMSAnalyticsDashboard
    report = CMSAnalyticsDashboard.get_full_dashboard(days=7)
    logger.info(f"[Job] Weekly report generated: {report.get('revenue', {})}")
    return report


@shared_task(name='cms.jobs.warm_caches')
def warm_caches_job() -> Dict:
    """Pre-warm all critical caches."""
    from api.cms.caching import CMSCache
    results = CMSCache.warmup()
    return {'results': results}


# ── Enhanced Background Job Classes ─────────────────────────────────────

class BaseBackgroundJob(BaseService):
    """Base background job class with common functionality."""
    
    def __init__(self):
        """Initialize background job."""
        super().__init__()
        self.metrics = CMSMetrics
        self.cache = CMSCache
        self.job_id = str(uuid.uuid4())
    
    def validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input data."""
        return data
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute background job."""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def on_success(self, result: Any):
        """Handle successful job execution."""
        self.metrics.increment('background_jobs_success')
        logger.info(f"Background job {self.job_id} completed successfully")
    
    def on_failure(self, error: Exception):
        """Handle failed job execution."""
        self.metrics.increment('background_jobs_failure')
        logger.error(f"Background job {self.job_id} failed: {error}")
    
    def on_retry(self, attempt: int, error: Exception):
        """Handle job retry."""
        logger.warning(f"Background job {self.job_id} retry {attempt}: {error}")


class JobQueue:
    """Simple in-memory job queue."""
    
    def __init__(self):
        """Initialize job queue."""
        self._queue = queue.Queue()
        self._workers = []
        self._running = False
        self.logger = logging.getLogger(f"{__name__}.queue")
    
    def add_job(self, job: BaseBackgroundJob, priority: int = 0) -> str:
        """Add job to queue."""
        job_item = {
            'job': job,
            'priority': priority,
            'added_at': timezone.now()
        }
        self._queue.put(job_item)
        self.logger.info(f"Job {job.job_id} added to queue with priority {priority}")
        return job.job_id
    
    def start_workers(self, num_workers: int = 2):
        """Start worker threads."""
        if self._running:
            return
        
        self._running = True
        for i in range(num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"BackgroundWorker-{i}",
                daemon=True
            )
            worker.start()
            self._workers.append(worker)
        
        self.logger.info(f"Started {num_workers} background job workers")
    
    def stop_workers(self):
        """Stop worker threads."""
        self._running = False
        for worker in self._workers:
            worker.join(timeout=5)
        self._workers.clear()
        self.logger.info("Stopped background job workers")
    
    def _worker_loop(self):
        """Worker thread main loop."""
        while self._running:
            try:
                # Get job with timeout
                job_item = self._queue.get(timeout=1)
                
                if job_item:
                    job = job_item['job']
                    priority = job_item['priority']
                    
                    try:
                        # Execute job
                        result = job.execute()
                        job.on_success(result)
                    except Exception as e:
                        job.on_failure(e)
                    
                    self._queue.task_done()
                    
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Worker error: {e}")
                time.sleep(1)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        return {
            'queue_size': self._queue.qsize(),
            'active_workers': len(self._workers),
            'is_running': self._running
        }


# ── Enhanced Background Job Manager ─────────────────────────────────────

class EnhancedBackgroundJobManager:
    """Manager for handling background jobs."""
    
    def __init__(self):
        """Initialize background job manager."""
        self.queue = JobQueue()
        self.logger = logging.getLogger(f"{__name__}.manager")
        
        # Start workers
        num_workers = getattr(settings, 'BACKGROUND_JOB_WORKERS', 2)
        self.queue.start_workers(num_workers)
    
    def schedule_job(self, job: BaseBackgroundJob, priority: int = 0, delay: int = 0) -> str:
        """Schedule a background job."""
        if delay > 0:
            # Schedule for later execution
            import threading
            timer = threading.Timer(
                delay,
                self.queue.add_job,
                args=[job, priority]
            )
            timer.start()
            self.logger.info(f"Job {job.job_id} scheduled with {delay}s delay")
        else:
            # Add to queue immediately
            job_id = self.queue.add_job(job, priority)
            self.logger.info(f"Job {job_id} scheduled immediately")
        
        return job.job_id
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        return self.queue.get_queue_status()
    
    def get_job_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get job execution statistics."""
        try:
            # This would query actual job statistics from database
            return {
                'period_days': days,
                'total_jobs': 0,
                'successful_jobs': 0,
                'failed_jobs': 0,
                'success_rate': 0.0,
                'average_execution_time': 0.0
            }
        except Exception as e:
            self.logger.error(f"Error getting job statistics: {e}")
            return {
                'period_days': days,
                'total_jobs': 0,
                'successful_jobs': 0,
                'failed_jobs': 0,
                'success_rate': 0.0,
                'average_execution_time': 0.0,
                'error': str(e)
            }
    
    def shutdown(self):
        """Shutdown background job manager."""
        self.queue.stop_workers()
        self.logger.info("Background job manager shutdown")


# Global enhanced background job manager
enhanced_background_job_manager = EnhancedBackgroundJobManager()
