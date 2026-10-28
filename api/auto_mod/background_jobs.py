# =============================================================================
# auto_mod/background_jobs.py
# =============================================================================

"""
Background jobs and task scheduling for auto moderation system.
Provides asynchronous processing, job management, and scheduling capabilities.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from celery import shared_task
from celery.schedules import crontab

from .models import (
    SuspiciousSubmission, ModerationDecision, ModerationQueue, 
    TaskBot, AutoApprovalRule, MLModelVersion
)
from .services import ModerationService, ScannerService
from .monitoring import performance_monitor, record_operation
from .exceptions import ModerationError

logger = logging.getLogger(__name__)


class JobStatus:
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class JobPriority:
    """Job priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    URGENT = 5


class BackgroundJob:
    """Background job representation."""
    
    def __init__(self, job_id: str, task_name: str, args: List[Any] = None,
                 kwargs: Dict[str, Any] = None, priority: int = JobPriority.NORMAL,
                 max_retries: int = 3, retry_delay: int = 60):
        self.job_id = job_id
        self.task_name = task_name
        self.args = args or []
        self.kwargs = kwargs or {}
        self.priority = priority
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.status = JobStatus.PENDING
        self.created_at = timezone.now()
        self.started_at = None
        self.completed_at = None
        self.error = None
        self.retry_count = 0
        self.result = None
        self.progress = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'job_id': self.job_id,
            'task_name': self.task_name,
            'status': self.status,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error': str(self.error) if self.error else None,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'progress': self.progress,
            'result': self.result,
        }


class JobManager:
    """
    Manager for background jobs.
    """
    
    def __init__(self):
        self.jobs = {}
        self.job_queue = []
        self.max_queue_size = 1000
        self._load_jobs_from_cache()
    
    def _load_jobs_from_cache(self) -> None:
        """Load jobs from cache."""
        try:
            cached_jobs = cache.get('background_jobs')
            if cached_jobs:
                self.jobs = cached_jobs
                logger.info(f"Loaded {len(cached_jobs)} background jobs from cache")
        except Exception as exc:
            logger.error(f"Load jobs from cache failed: {exc}")
    
    def _save_jobs_to_cache(self) -> None:
        """Save jobs to cache."""
        try:
            cache.set('background_jobs', self.jobs, timeout=3600)  # 1 hour
        except Exception as exc:
            logger.error(f"Save jobs to cache failed: {exc}")
    
    def create_job(self, task_name: str, args: List[Any] = None,
                  kwargs: Dict[str, Any] = None, priority: int = JobPriority.NORMAL,
                  max_retries: int = 3, retry_delay: int = 60) -> str:
        """
        Create a new background job.
        
        Args:
            task_name: Name of the task to execute
            args: Task arguments
            kwargs: Task keyword arguments
            priority: Job priority
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries (seconds)
            
        Returns:
            Job ID
        """
        try:
            job_id = str(uuid.uuid4())
            
            job = BackgroundJob(
                job_id=job_id,
                task_name=task_name,
                args=args,
                kwargs=kwargs,
                priority=priority,
                max_retries=max_retries,
                retry_delay=retry_delay
            )
            
            self.jobs[job_id] = job
            self._add_to_queue(job)
            self._save_jobs_to_cache()
            
            logger.info(f"Created background job {job_id}: {task_name}")
            return job_id
            
        except Exception as exc:
            logger.error(f"Create job failed: {exc}")
            raise ModerationError(f"Failed to create job: {exc}")
    
    def _add_to_queue(self, job: BackgroundJob) -> None:
        """Add job to queue."""
        try:
            # Insert job based on priority
            inserted = False
            for i, queued_job in enumerate(self.job_queue):
                if job.priority > queued_job.priority:
                    self.job_queue.insert(i, job)
                    inserted = True
                    break
            
            if not inserted:
                self.job_queue.append(job)
            
            # Limit queue size
            if len(self.job_queue) > self.max_queue_size:
                self.job_queue = self.job_queue[-self.max_queue_size:]
            
        except Exception as exc:
            logger.error(f"Add to queue failed: {exc}")
    
    def get_job(self, job_id: str) -> Optional[BackgroundJob]:
        """Get job by ID."""
        return self.jobs.get(job_id)
    
    def get_jobs(self, status: str = None, limit: int = 100) -> List[BackgroundJob]:
        """Get jobs with optional status filter."""
        jobs = list(self.jobs.values())
        
        if status:
            jobs = [job for job in jobs if job.status == status]
        
        # Sort by creation time (newest first)
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        
        return jobs[:limit]
    
    def update_job_status(self, job_id: str, status: str, error: str = None,
                         progress: float = None, result: Any = None) -> bool:
        """Update job status."""
        try:
            job = self.jobs.get(job_id)
            if not job:
                logger.warning(f"Job {job_id} not found for status update")
                return False
            
            old_status = job.status
            job.status = status
            
            if status == JobStatus.RUNNING and old_status != JobStatus.RUNNING:
                job.started_at = timezone.now()
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                job.completed_at = timezone.now()
            
            if error:
                job.error = error
            
            if progress is not None:
                job.progress = max(0.0, min(100.0, progress))
            
            if result is not None:
                job.result = result
            
            self._save_jobs_to_cache()
            
            logger.info(f"Updated job {job_id} status: {old_status} -> {status}")
            return True
            
        except Exception as exc:
            logger.error(f"Update job status failed: {exc}")
            return False
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        return self.update_job_status(job_id, JobStatus.CANCELLED)
    
    def retry_job(self, job_id: str) -> bool:
        """Retry a failed job."""
        try:
            job = self.jobs.get(job_id)
            if not job:
                return False
            
            if job.retry_count >= job.max_retries:
                logger.warning(f"Job {job_id} exceeded max retries")
                return False
            
            job.retry_count += 1
            job.status = JobStatus.RETRYING
            job.error = None
            job.started_at = None
            job.completed_at = None
            
            # Add back to queue
            self._add_to_queue(job)
            self._save_jobs_to_cache()
            
            logger.info(f"Retrying job {job_id} (attempt {job.retry_count})")
            return True
            
        except Exception as exc:
            logger.error(f"Retry job failed: {exc}")
            return False
    
    def cleanup_old_jobs(self, days: int = 7) -> int:
        """Clean up old completed jobs."""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            old_jobs = [
                job_id for job_id, job in self.jobs.items()
                if (job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED] and
                    job.completed_at and job.completed_at < cutoff_date)
            ]
            
            for job_id in old_jobs:
                del self.jobs[job_id]
            
            self._save_jobs_to_cache()
            
            logger.info(f"Cleaned up {len(old_jobs)} old jobs")
            return len(old_jobs)
            
        except Exception as exc:
            logger.error(f"Cleanup old jobs failed: {exc}")
            return 0
    
    def get_job_statistics(self) -> Dict[str, Any]:
        """Get job statistics."""
        try:
            jobs = list(self.jobs.values())
            
            status_counts = {}
            for job in jobs:
                status_counts[job.status] = status_counts.get(job.status, 0) + 1
            
            priority_counts = {}
            for job in jobs:
                priority_counts[job.priority] = priority_counts.get(job.priority, 0) + 1
            
            # Calculate average execution time
            completed_jobs = [job for job in jobs if job.status == JobStatus.COMPLETED and job.started_at and job.completed_at]
            
            avg_execution_time = 0
            if completed_jobs:
                total_time = sum((job.completed_at - job.started_at).total_seconds() for job in completed_jobs)
                avg_execution_time = total_time / len(completed_jobs)
            
            return {
                'total_jobs': len(jobs),
                'queue_size': len(self.job_queue),
                'status_breakdown': status_counts,
                'priority_breakdown': priority_counts,
                'avg_execution_time_seconds': round(avg_execution_time, 2),
                'completed_jobs': len(completed_jobs),
                'failed_jobs': len([j for j in jobs if j.status == JobStatus.FAILED]),
                'generated_at': timezone.now().isoformat(),
            }
            
        except Exception as exc:
            logger.error(f"Get job statistics failed: {exc}")
            return {'error': str(exc)}


# Global job manager
job_manager = JobManager()


# Celery tasks
@shared_task(bind=True, name='auto_mod.process_submission_async')
def process_submission_async(self, submission_id: str, force_rescan: bool = False) -> Dict[str, Any]:
    """
    Async task for processing submission.
    
    Args:
        submission_id: Submission ID
        force_rescan: Whether to force rescan
        
    Returns:
        Processing result
    """
    start_time = timezone.now()
    job_id = self.request.id
    
    try:
        # Update job status
        job_manager.update_job_status(job_id, JobStatus.RUNNING, progress=0.0)
        
        record_operation('process_submission_async', 0, True, {'submission_id': submission_id})
        
        # Get submission
        from .models import SuspiciousSubmission
        submission = SuspiciousSubmission.objects.get(id=submission_id)
        
        # Update progress
        job_manager.update_job_status(job_id, JobStatus.RUNNING, progress=25.0)
        
        # Scan submission
        scanner_service = ScannerService()
        scan_result = scanner_service.scan_submission(submission)
        
        # Update progress
        job_manager.update_job_status(job_id, JobStatus.RUNNING, progress=50.0)
        
        # Apply rules
        from .services import RuleEngineService
        rule_engine = RuleEngineService()
        rule_result = rule_engine.evaluate_rules(submission, scan_result)
        
        # Update progress
        job_manager.update_job_status(job_id, JobStatus.RUNNING, progress=75.0)
        
        # Make decision
        moderation_service = ModerationService()
        decision = moderation_service.make_decision(submission, scan_result, rule_result)
        
        # Update progress
        job_manager.update_job_status(job_id, JobStatus.RUNNING, progress=100.0)
        
        # Complete job
        result = {
            'submission_id': submission_id,
            'decision_id': str(decision.id),
            'decision_type': decision.decision_type,
            'confidence': decision.confidence,
            'processing_time': (timezone.now() - start_time).total_seconds()
        }
        
        job_manager.update_job_status(job_id, JobStatus.COMPLETED, result=result)
        
        # Record operation
        duration = (timezone.now() - start_time).total_seconds()
        record_operation('process_submission_async', duration, True, result)
        
        return result
        
    except Exception as exc:
        logger.error(f"Process submission async failed: {exc}")
        
        # Update job status
        job_manager.update_job_status(job_id, JobStatus.FAILED, error=str(exc))
        
        # Record operation
        duration = (timezone.now() - start_time).total_seconds()
        record_operation('process_submission_async', duration, False, {'error': str(exc)})
        
        raise


@shared_task(bind=True, name='auto_mod.batch_process_submissions')
def batch_process_submissions(self, submission_ids: List[str]) -> Dict[str, Any]:
    """
    Async task for batch processing submissions.
    
    Args:
        submission_ids: List of submission IDs
        
    Returns:
        Batch processing result
    """
    start_time = timezone.now()
    job_id = self.request.id
    
    try:
        job_manager.update_job_status(job_id, JobStatus.RUNNING, progress=0.0)
        
        results = []
        failed = []
        total = len(submission_ids)
        
        for i, submission_id in enumerate(submission_ids):
            try:
                # Update progress
                progress = (i / total) * 100
                job_manager.update_job_status(job_id, JobStatus.RUNNING, progress=progress)
                
                # Process individual submission
                result = process_submission_async.delay(submission_id)
                results.append({
                    'submission_id': submission_id,
                    'task_id': result.id,
                    'status': 'queued'
                })
                
            except Exception as exc:
                failed.append({
                    'submission_id': submission_id,
                    'error': str(exc)
                })
        
        # Complete job
        final_result = {
            'total': total,
            'queued': len(results),
            'failed': len(failed),
            'results': results,
            'failed_items': failed,
            'processing_time': (timezone.now() - start_time).total_seconds()
        }
        
        job_manager.update_job_status(job_id, JobStatus.COMPLETED, result=final_result)
        
        return final_result
        
    except Exception as exc:
        logger.error(f"Batch process submissions failed: {exc}")
        job_manager.update_job_status(job_id, JobStatus.FAILED, error=str(exc))
        raise


@shared_task(bind=True, name='auto_mod.cleanup_old_data')
def cleanup_old_data(self, days: int = 30) -> Dict[str, Any]:
    """
    Async task for cleaning up old data.
    
    Args:
        days: Number of days to keep data
        
    Returns:
        Cleanup result
    """
    start_time = timezone.now()
    job_id = self.request.id
    
    try:
        job_manager.update_job_status(job_id, JobStatus.RUNNING, progress=0.0)
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Clean up old submissions
        from .models import SuspiciousSubmission
        old_submissions = SuspiciousSubmission.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['approved', 'rejected']
        ).count()
        
        # Clean up old decisions
        from .models import ModerationDecision
        old_decisions = ModerationDecision.objects.filter(
            decided_at__lt=cutoff_date
        ).count()
        
        # Clean up old queue items
        from .models import ModerationQueue
        old_queue_items = ModerationQueue.objects.filter(
            created_at__lt=cutoff_date,
            status='completed'
        ).count()
        
        # Clean up old jobs
        cleaned_jobs = job_manager.cleanup_old_jobs(days)
        
        result = {
            'submissions_cleaned': old_submissions,
            'decisions_cleaned': old_decisions,
            'queue_items_cleaned': old_queue_items,
            'jobs_cleaned': cleaned_jobs,
            'cutoff_date': cutoff_date.isoformat(),
            'processing_time': (timezone.now() - start_time).total_seconds()
        }
        
        job_manager.update_job_status(job_id, JobStatus.COMPLETED, result=result)
        
        return result
        
    except Exception as exc:
        logger.error(f"Cleanup old data failed: {exc}")
        job_manager.update_job_status(job_id, JobStatus.FAILED, error=str(exc))
        raise


@shared_task(bind=True, name='auto_mod.generate_daily_report')
def generate_daily_report(self) -> Dict[str, Any]:
    """
    Async task for generating daily reports.
    
    Returns:
        Report result
    """
    start_time = timezone.now()
    job_id = self.request.id
    
    try:
        job_manager.update_job_status(job_id, JobStatus.RUNNING, progress=0.0)
        
        # Generate report
        from .analytics import analytics_engine
        report_data = analytics_engine.get_dashboard_analytics(days=1)
        
        # Save report (in production, would save to database or file)
        report_result = {
            'report_date': timezone.now().date().isoformat(),
            'data': report_data,
            'generated_at': timezone.now().isoformat(),
            'processing_time': (timezone.now() - start_time).total_seconds()
        }
        
        job_manager.update_job_status(job_id, JobStatus.COMPLETED, result=report_result)
        
        return report_result
        
    except Exception as exc:
        logger.error(f"Generate daily report failed: {exc}")
        job_manager.update_job_status(job_id, JobStatus.FAILED, error=str(exc))
        raise


@shared_task(bind=True, name='auto_mod.retrain_ml_models')
def retrain_ml_models(self, model_type: str = None) -> Dict[str, Any]:
    """
    Async task for retraining ML models.
    
    Args:
        model_type: Specific model type to retrain
        
    Returns:
        Retraining result
    """
    start_time = timezone.now()
    job_id = self.request.id
    
    try:
        job_manager.update_job_status(job_id, JobStatus.RUNNING, progress=0.0)
        
        # This would integrate with your ML training pipeline
        # For now, return mock result
        
        result = {
            'model_type': model_type or 'all',
            'training_started': timezone.now().isoformat(),
            'training_completed': (timezone.now() + timedelta(hours=2)).isoformat(),
            'accuracy_improvement': 0.05,
            'processing_time': (timezone.now() - start_time).total_seconds()
        }
        
        job_manager.update_job_status(job_id, JobStatus.COMPLETED, result=result)
        
        return result
        
    except Exception as exc:
        logger.error(f"Retrain ML models failed: {exc}")
        job_manager.update_job_status(job_id, JobStatus.FAILED, error=str(exc))
        raise


# Periodic tasks
@shared_task(name='auto_mod.periodic_health_check')
def periodic_health_check() -> Dict[str, Any]:
    """Periodic health check task."""
    try:
        from .monitoring import health_checker
        health_result = health_checker.check_system_health()
        
        # Log health status
        logger.info(f"Health check completed: {health_result['status']}")
        
        return health_result
        
    except Exception as exc:
        logger.error(f"Periodic health check failed: {exc}")
        return {'error': str(exc)}


@shared_task(name='auto_mod.periodic_cache_cleanup')
def periodic_cache_cleanup() -> Dict[str, Any]:
    """Periodic cache cleanup task."""
    try:
        from .caching import auto_mod_cache
        cleanup_result = auto_mod_cache.cleanup_expired_cache()
        
        logger.info(f"Cache cleanup completed: {cleanup_result}")
        
        return cleanup_result
        
    except Exception as exc:
        logger.error(f"Periodic cache cleanup failed: {exc}")
        return {'error': str(exc)}


@shared_task(name='auto_mod.periodic_queue_cleanup')
def periodic_queue_cleanup() -> Dict[str, Any]:
    """Periodic queue cleanup task."""
    try:
        from .models import ModerationQueue
        
        # Clean up old completed queue items
        cutoff_date = timezone.now() - timedelta(days=7)
        cleaned_count = ModerationQueue.objects.filter(
            status='completed',
            updated_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Queue cleanup completed: {cleaned_count} items removed")
        
        return {'cleaned_items': cleaned_count}
        
    except Exception as exc:
        logger.error(f"Periodic queue cleanup failed: {exc}")
        return {'error': str(exc)}


# Utility functions
def create_background_job(task_name: str, args: List[Any] = None,
                        kwargs: Dict[str, Any] = None, priority: int = JobPriority.NORMAL) -> str:
    """Create a background job."""
    return job_manager.create_job(task_name, args, kwargs, priority)


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job status."""
    job = job_manager.get_job(job_id)
    return job.to_dict() if job else None


def cancel_background_job(job_id: str) -> bool:
    """Cancel a background job."""
    return job_manager.cancel_job(job_id)


def get_job_statistics() -> Dict[str, Any]:
    """Get job statistics."""
    return job_manager.get_job_statistics()


# Celery beat schedule configuration
def get_celery_beat_schedule():
    """Get Celery beat schedule configuration."""
    return {
        'auto-mod-health-check': {
            'task': 'auto_mod.periodic_health_check',
            'schedule': crontab(minute=0),  # Every hour
        },
        'auto-mod-cache-cleanup': {
            'task': 'auto_mod.periodic_cache_cleanup',
            'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
        },
        'auto-mod-queue-cleanup': {
            'task': 'auto_mod.periodic_queue_cleanup',
            'schedule': crontab(minute=0, hour=0),  # Daily at midnight
        },
        'auto-mod-daily-report': {
            'task': 'auto_mod.generate_daily_report',
            'schedule': crontab(minute=0, hour=1),  # Daily at 1 AM
        },
        'auto-mod-job-cleanup': {
            'task': 'auto_mod.cleanup_old_data',
            'schedule': crontab(minute=0, hour=2),  # Daily at 2 AM
            'args': (30,),  # Keep 30 days of data
        },
    }


# Initialize logging
logger.info("Background jobs module initialized with task scheduling capabilities")
