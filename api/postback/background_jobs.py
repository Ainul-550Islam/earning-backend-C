"""
background_jobs.py – Background job system for postback module.

Provides comprehensive background job functionality including:
- Job scheduling and execution
- Job queue management
- Job monitoring and logging
- Error handling and retry logic
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import threading
import time
import queue
import uuid
import traceback
from concurrent.futures import ThreadPoolExecutor, Future

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from .integ_exceptions import IntegrationException

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class JobPriority(Enum):
    """Job priority enumeration."""
    LOWEST = 1
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100


class JobType(Enum):
    """Job type enumeration."""
    POSTBACK_PROCESSING = "postback_processing"
    DATA_SYNC = "data_sync"
    ANALYTICS_CALCULATION = "analytics_calculation"
    EMAIL_SENDING = "email_sending"
    WEBHOOK_SENDING = "webhook_sending"
    CLEANUP = "cleanup"
    REPORT_GENERATION = "report_generation"
    CUSTOM = "custom"


@dataclass
class Job:
    """Background job data structure."""
    id: str
    name: str
    job_type: JobType
    function: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: JobPriority = JobPriority.NORMAL
    max_retries: int = 3
    retry_delay: int = 60
    timeout: int = 300
    created_at: datetime = field(default_factory=timezone.now)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: JobStatus = JobStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'job_type': self.job_type.value,
            'priority': self.priority.value,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'timeout': self.timeout,
            'created_at': self.created_at.isoformat(),
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status.value,
            'result': str(self.result) if self.result is not None else None,
            'error': self.error,
            'retry_count': self.retry_count,
            'metadata': self.metadata,
        }
    
    def should_retry(self) -> bool:
        """Check if job should be retried."""
        return self.retry_count < self.max_retries
    
    def is_ready(self) -> bool:
        """Check if job is ready to run."""
        if self.scheduled_at:
            return timezone.now() >= self.scheduled_at
        return True


@dataclass
class JobResult:
    """Job result data structure."""
    job_id: str
    status: JobStatus
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    started_at: datetime = field(default_factory=timezone.now)
    completed_at: datetime = field(default_factory=timezone.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'job_id': self.job_id,
            'status': self.status.value,
            'result': str(self.result) if self.result is not None else None,
            'error': self.error,
            'execution_time': self.execution_time,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat(),
        }


class JobQueue:
    """
    Job queue for background jobs.
    
    Handles job queuing with priority support.
    """
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.queue = queue.PriorityQueue(maxsize=max_size)
        self.jobs: Dict[str, Job] = {}
        self.lock = threading.Lock()
    
    def enqueue(self, job: Job) -> bool:
        """
        Enqueue job.
        
        Args:
            job: Job to enqueue
            
        Returns:
            True if enqueued successfully
        """
        with self.lock:
            if len(self.jobs) >= self.max_size:
                return False
            
            # Priority queue uses inverse priority (higher priority = lower number)
            priority_value = 100 - job.priority.value
            self.queue.put((priority_value, job.created_at, job.id))
            self.jobs[job.id] = job
            
            return True
    
    def dequeue(self, timeout: float = 1.0) -> Optional[Job]:
        """
        Dequeue job.
        
        Args:
            timeout: Dequeue timeout
            
        Returns:
            Job or None
        """
        try:
            priority, created_at, job_id = self.queue.get(timeout=timeout)
            
            with self.lock:
                job = self.jobs.get(job_id)
                if job:
                    del self.jobs[job_id]
                return job
        
        except queue.Empty:
            return None
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        with self.lock:
            return self.jobs.get(job_id)
    
    def size(self) -> int:
        """Get queue size."""
        return len(self.jobs)
    
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self.jobs) == 0
    
    def get_jobs_by_status(self, status: JobStatus) -> List[Job]:
        """Get jobs by status."""
        with self.lock:
            return [job for job in self.jobs.values() if job.status == status]
    
    def get_jobs_by_type(self, job_type: JobType) -> List[Job]:
        """Get jobs by type."""
        with self.lock:
            return [job for job in self.jobs.values() if job.job_type == job_type]


class JobExecutor:
    """
    Job executor for running background jobs.
    
    Handles job execution with timeout and error handling.
    """
    
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running_jobs: Dict[str, Future] = {}
        self.lock = threading.Lock()
    
    def execute(self, job: Job) -> JobResult:
        """
        Execute job.
        
        Args:
            job: Job to execute
            
        Returns:
            Job result
        """
        start_time = time.time()
        result = JobResult(job_id=job.id, status=JobStatus.RUNNING)
        
        try:
            # Update job status
            job.status = JobStatus.RUNNING
            job.started_at = timezone.now()
            
            # Execute job with timeout
            future = self.executor.submit(self._execute_with_timeout, job)
            
            with self.lock:
                self.running_jobs[job.id] = future
            
            # Wait for result
            job_result = future.result(timeout=job.timeout)
            
            # Update result
            result.status = JobStatus.COMPLETED
            result.result = job_result
            result.execution_time = time.time() - start_time
            result.completed_at = timezone.now()
            
            # Update job
            job.status = JobStatus.COMPLETED
            job.completed_at = timezone.now()
            job.result = job_result
            
            return result
        
        except Exception as e:
            # Update result
            result.status = JobStatus.FAILED
            result.error = str(e)
            result.execution_time = time.time() - start_time
            result.completed_at = timezone.now()
            
            # Update job
            job.status = JobStatus.FAILED
            job.completed_at = timezone.now()
            job.error = str(e)
            
            return result
        
        finally:
            # Clean up running jobs
            with self.lock:
                if job.id in self.running_jobs:
                    del self.running_jobs[job.id]
    
    def _execute_with_timeout(self, job: Job) -> Any:
        """Execute job function with timeout."""
        return job.function(*job.args, **job.kwargs)
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel running job.
        
        Args:
            job_id: Job ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        with self.lock:
            future = self.running_jobs.get(job_id)
            if future:
                cancelled = future.cancel()
                if cancelled:
                    del self.running_jobs[job_id]
                return cancelled
        return False
    
    def get_running_jobs(self) -> List[str]:
        """Get list of running job IDs."""
        with self.lock:
            return list(self.running_jobs.keys())
    
    def shutdown(self, wait: bool = True):
        """Shutdown executor."""
        self.executor.shutdown(wait=wait)


class JobScheduler:
    """
    Job scheduler for background jobs.
    
    Handles job scheduling, execution, and lifecycle management.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.job_queue = JobQueue()
        self.job_executor = JobExecutor(
            max_workers=getattr(settings, 'BACKGROUND_JOB_WORKERS', 5)
        )
        self.completed_jobs: Dict[str, JobResult] = {}
        self.running = False
        self.worker_threads: List[threading.Thread] = []
        self.max_history = 10000
        self._setup_scheduler()
    
    def _setup_scheduler(self):
        """Setup scheduler."""
        self.logger.info("Job scheduler initialized")
    
    def start(self):
        """Start job scheduler."""
        if self.running:
            return
        
        self.running = True
        
        # Start worker threads
        for i in range(self.job_executor.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"job_worker_{i}",
                daemon=True
            )
            worker.start()
            self.worker_threads.append(worker)
        
        self.logger.info(f"Job scheduler started with {len(self.worker_threads)} workers")
    
    def stop(self):
        """Stop job scheduler."""
        if not self.running:
            return
        
        self.running = False
        
        # Wait for workers to finish
        for worker in self.worker_threads:
            worker.join(timeout=5)
        
        # Shutdown executor
        self.job_executor.shutdown()
        
        self.worker_threads.clear()
        self.logger.info("Job scheduler stopped")
    
    def _worker_loop(self):
        """Worker thread loop."""
        while self.running:
            try:
                # Get job from queue
                job = self.job_queue.dequeue(timeout=1.0)
                if not job:
                    continue
                
                # Check if job is ready
                if not job.is_ready():
                    # Re-queue job
                    self.job_queue.enqueue(job)
                    time.sleep(1)
                    continue
                
                # Execute job
                result = self.job_executor.execute(job)
                
                # Store result
                self.completed_jobs[job.id] = result
                
                # Handle retries
                if result.status == JobStatus.FAILED and job.should_retry():
                    self._schedule_retry(job)
                
                # Clean up history
                self._cleanup_history()
                
            except Exception as e:
                self.logger.error(f"Worker loop error: {str(e)}")
                time.sleep(1)
    
    def submit_job(self, name: str, function: Callable, *args,
                  job_type: JobType = JobType.CUSTOM,
                  priority: JobPriority = JobPriority.NORMAL,
                  max_retries: int = 3,
                  retry_delay: int = 60,
                  timeout: int = 300,
                  scheduled_at: datetime = None,
                  **kwargs) -> str:
        """
        Submit job for execution.
        
        Args:
            name: Job name
            function: Function to execute
            *args: Function arguments
            job_type: Job type
            priority: Job priority
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries
            timeout: Job timeout
            scheduled_at: Scheduled execution time
            **kwargs: Function keyword arguments
            
        Returns:
            Job ID
        """
        job = Job(
            id=f"job_{uuid.uuid4().hex[:12]}",
            name=name,
            job_type=job_type,
            function=function,
            args=args,
            kwargs=kwargs,
            priority=priority,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
            scheduled_at=scheduled_at
        )
        
        if self.job_queue.enqueue(job):
            self.logger.info(f"Job submitted: {job.id} - {name}")
            return job.id
        else:
            raise IntegrationException("Job queue is full")
    
    def submit_delayed_job(self, name: str, function: Callable, delay: timedelta,
                           *args, **kwargs) -> str:
        """
        Submit delayed job.
        
        Args:
            name: Job name
            function: Function to execute
            delay: Delay before execution
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Job ID
        """
        scheduled_at = timezone.now() + delay
        return self.submit_job(
            name=name,
            function=function,
            *args,
            scheduled_at=scheduled_at,
            **kwargs
        )
    
    def _schedule_retry(self, job: Job):
        """Schedule job retry."""
        job.retry_count += 1
        job.status = JobStatus.RETRYING
        
        # Calculate retry delay with exponential backoff
        retry_delay = job.retry_delay * (2 ** (job.retry_count - 1))
        scheduled_at = timezone.now() + timedelta(seconds=retry_delay)
        
        # Create new job for retry
        retry_job = Job(
            id=f"job_{uuid.uuid4().hex[:12]}",
            name=f"{job.name}_retry_{job.retry_count}",
            job_type=job.job_type,
            function=job.function,
            args=job.args,
            kwargs=job.kwargs,
            priority=job.priority,
            max_retries=job.max_retries,
            retry_delay=job.retry_delay,
            timeout=job.timeout,
            scheduled_at=scheduled_at,
            retry_count=job.retry_count,
            metadata=job.metadata
        )
        
        if self.job_queue.enqueue(retry_job):
            self.logger.info(f"Job retry scheduled: {retry_job.id}")
    
    def _cleanup_history(self):
        """Clean up job history."""
        if len(self.completed_jobs) > self.max_history:
            # Remove oldest entries
            oldest_keys = sorted(
                self.completed_jobs.keys(),
                key=lambda k: self.completed_jobs[k].completed_at
            )[:len(self.completed_jobs) - self.max_history]
            
            for key in oldest_keys:
                del self.completed_jobs[key]
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return self.job_queue.get_job(job_id)
    
    def get_job_result(self, job_id: str) -> Optional[JobResult]:
        """Get job result."""
        return self.completed_jobs.get(job_id)
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel job."""
        # Try to cancel running job
        if self.job_executor.cancel_job(job_id):
            return True
        
        # Remove from queue if pending
        job = self.get_job(job_id)
        if job and job.status == JobStatus.PENDING:
            job.status = JobStatus.CANCELLED
            return True
        
        return False
    
    def get_jobs(self, status: JobStatus = None, job_type: JobType = None,
                limit: int = 100) -> List[Dict[str, Any]]:
        """Get jobs."""
        jobs = []
        
        # Get jobs from queue
        queue_jobs = list(self.job_queue.jobs.values())
        
        # Add completed jobs
        for job_id, result in self.completed_jobs.items():
            job = self.job_queue.get_job(job_id)
            if job:
                jobs.append(job)
        
        # Filter by status
        if status:
            jobs = [job for job in jobs if job.status == status]
        
        # Filter by type
        if job_type:
            jobs = [job for job in jobs if job.job_type == job_type]
        
        # Sort by created time
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        
        # Limit results
        jobs = jobs[:limit]
        
        return [job.to_dict() for job in jobs]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get job statistics."""
        total_jobs = len(self.completed_jobs) + len(self.job_queue.jobs)
        
        # Count by status
        status_counts = {}
        for job in self.job_queue.jobs.values():
            status = job.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        for result in self.completed_jobs.values():
            status = result.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Count by type
        type_counts = {}
        for job in self.job_queue.jobs.values():
            job_type = job.job_type.value
            type_counts[job_type] = type_counts.get(job_type, 0) + 1
        
        for result in self.completed_jobs.values():
            job = self.job_queue.get_job(result.job_id)
            if job:
                job_type = job.job_type.value
                type_counts[job_type] = type_counts.get(job_type, 0) + 1
        
        return {
            'total_jobs': total_jobs,
            'queue_size': self.job_queue.size(),
            'running_jobs': len(self.job_executor.get_running_jobs()),
            'completed_jobs': len(self.completed_jobs),
            'status_counts': status_counts,
            'type_counts': type_counts,
            'scheduler_running': self.running,
            'worker_threads': len(self.worker_threads),
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        stats = self.get_statistics()
        
        health_status = {
            'overall': 'healthy',
            'scheduler_running': self.running,
            'queue_size': stats['queue_size'],
            'running_jobs': stats['running_jobs'],
            'worker_threads': stats['worker_threads'],
            'issues': [],
        }
        
        # Check queue size
        if stats['queue_size'] > 1000:
            health_status['overall'] = 'degraded'
            health_status['issues'].append(f"High queue size: {stats['queue_size']}")
        
        # Check failed jobs
        failed_count = stats['status_counts'].get('failed', 0)
        if failed_count > 100:
            health_status['overall'] = 'unhealthy'
            health_status['issues'].append(f"High failure count: {failed_count}")
        
        # Check if scheduler is running
        if not self.running:
            health_status['overall'] = 'unhealthy'
            health_status['issues'].append("Scheduler is not running")
        
        return health_status


# Global job scheduler instance
job_scheduler = JobScheduler()


# Decorators for background jobs
def background_job(name: str = None, job_type: JobType = JobType.CUSTOM,
                   priority: JobPriority = JobPriority.NORMAL,
                   max_retries: int = 3, retry_delay: int = 60,
                   timeout: int = 300):
    """
    Decorator for background job execution.
    
    Args:
        name: Job name
        job_type: Job type
        priority: Job priority
        max_retries: Maximum retry attempts
        retry_delay: Delay between retries
        timeout: Job timeout
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            job_name = name or f"{func.__module__}.{func.__name__}"
            
            # Submit job
            job_id = job_scheduler.submit_job(
                name=job_name,
                function=func,
                job_type=job_type,
                priority=priority,
                max_retries=max_retries,
                retry_delay=retry_delay,
                timeout=timeout,
                args=args,
                kwargs=kwargs
            )
            
            return job_id
        
        return wrapper
    return decorator


def delayed_job(delay: timedelta, name: str = None, job_type: JobType = JobType.CUSTOM):
    """
    Decorator for delayed background job execution.
    
    Args:
        delay: Delay before execution
        name: Job name
        job_type: Job type
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            job_name = name or f"{func.__module__}.{func.__name__}"
            
            # Submit delayed job
            job_id = job_scheduler.submit_delayed_job(
                name=job_name,
                function=func,
                delay=delay,
                job_type=job_type,
                args=args,
                kwargs=kwargs
            )
            
            return job_id
        
        return wrapper
    return decorator


# Convenience functions
def submit_background_job(name: str, function: Callable, *args,
                         job_type: JobType = JobType.CUSTOM,
                         priority: JobPriority = JobPriority.NORMAL,
                         max_retries: int = 3, retry_delay: int = 60,
                         timeout: int = 300, **kwargs) -> str:
    """Submit background job."""
    return job_scheduler.submit_job(
        name=name,
        function=function,
        *args,
        job_type=job_type,
        priority=priority,
        max_retries=max_retries,
        retry_delay=retry_delay,
        timeout=timeout,
        **kwargs
    )


def submit_delayed_job(name: str, function: Callable, delay: timedelta,
                      *args, **kwargs) -> str:
    """Submit delayed background job."""
    return job_scheduler.submit_delayed_job(
        name=name,
        function=function,
        delay=delay,
        *args,
        **kwargs
    )


def get_job_status(job_id: str) -> Optional[JobStatus]:
    """Get job status."""
    job = job_scheduler.get_job(job_id)
    return job.status if job else None


def get_job_result(job_id: str) -> Optional[JobResult]:
    """Get job result."""
    return job_scheduler.get_job_result(job_id)


def cancel_background_job(job_id: str) -> bool:
    """Cancel background job."""
    return job_scheduler.cancel_job(job_id)


def get_job_statistics() -> Dict[str, Any]:
    """Get job statistics."""
    return job_scheduler.get_statistics()


def start_job_scheduler():
    """Start job scheduler."""
    job_scheduler.start()


def stop_job_scheduler():
    """Stop job scheduler."""
    job_scheduler.stop()


def perform_job_health_check() -> Dict[str, Any]:
    """Perform job health check."""
    return job_scheduler.health_check()
