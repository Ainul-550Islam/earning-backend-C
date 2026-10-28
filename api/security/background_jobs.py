"""
Security Background Jobs Module
Background job processing for security operations
"""

import logging
import threading
import time
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings

from .models import SecurityLog, SecurityIncident, ThreatIntelligence, UserBan
from .repositories import SecurityUnitOfWork
from .utils import SecurityUtils
from .helpers import TimeHelper
from .monitoring import monitoring_manager
from .sanctions import sanction_manager
from .encryption import encryption_service
from .analytics import security_analytics

User = get_user_model()
logger = logging.getLogger('security.background_jobs')


class JobStatus:
    """Job status constants"""
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class JobPriority:
    """Job priority constants"""
    LOW = 'low'
    NORMAL = 'normal'
    HIGH = 'high'
    CRITICAL = 'critical'


class BackgroundJob:
    """Base background job class"""
    
    def __init__(self, job_id: str, name: str, priority: str = JobPriority.NORMAL):
        self.job_id = job_id
        self.name = name
        self.priority = priority
        self.status = JobStatus.PENDING
        self.created_at = timezone.now()
        self.started_at = None
        self.completed_at = None
        self.error_message = None
        self.result = None
        self.progress = 0
        self.max_retries = 3
        self.retry_count = 0
        self.timeout = 3600  # 1 hour default
    
    def execute(self) -> Any:
        """Execute the job - override in subclasses"""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def on_success(self, result: Any):
        """Called when job succeeds"""
        self.status = JobStatus.COMPLETED
        self.completed_at = timezone.now()
        self.result = result
        logger.info(f"Job {self.job_id} completed successfully")
    
    def on_failure(self, error: Exception):
        """Called when job fails"""
        self.status = JobStatus.FAILED
        self.error_message = str(error)
        self.completed_at = timezone.now()
        logger.error(f"Job {self.job_id} failed: {error}")
    
    def on_progress(self, progress: int, message: str = None):
        """Update job progress"""
        self.progress = max(0, min(100, progress))
        if message:
            logger.info(f"Job {self.job_id} progress: {self.progress}% - {message}")
    
    def can_retry(self) -> bool:
        """Check if job can be retried"""
        return self.retry_count < self.max_retries
    
    def should_timeout(self) -> bool:
        """Check if job should timeout"""
        if self.started_at:
            elapsed = (timezone.now() - self.started_at).total_seconds()
            return elapsed > self.timeout
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary"""
        return {
            'job_id': self.job_id,
            'name': self.name,
            'priority': self.priority,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'progress': self.progress,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries
        }


class SecurityLogCleanupJob(BackgroundJob):
    """Job to clean up old security logs"""
    
    def __init__(self, job_id: str, days_to_keep: int = 90):
        super().__init__(job_id, "Security Log Cleanup", JobPriority.LOW)
        self.days_to_keep = days_to_keep
    
    def execute(self) -> Dict[str, Any]:
        """Execute log cleanup"""
        cutoff_date = timezone.now() - timedelta(days=self.days_to_keep)
        
        # Delete old logs
        deleted_count, _ = SecurityLog.objects.filter(
            created_at__lt=cutoff_date
        ).delete()
        
        self.on_progress(100, f"Deleted {deleted_count} old security logs")
        
        return {
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat()
        }


class ThreatIntelligenceUpdateJob(BackgroundJob):
    """Job to update threat intelligence"""
    
    def __init__(self, job_id: str, sources: List[str] = None):
        super().__init__(job_id, "Threat Intelligence Update", JobPriority.HIGH)
        self.sources = sources or []
    
    def execute(self) -> Dict[str, Any]:
        """Execute threat intelligence update"""
        updated_threats = []
        
        # This would integrate with external threat intelligence sources
        # For now, simulate the process
        total_sources = len(self.sources) if self.sources else 5
        
        for i, source in enumerate(self.sources if self.sources else ['source1', 'source2', 'source3', 'source4', 'source5']):
            self.on_progress((i + 1) / total_sources * 100, f"Updating from {source}")
            
            # Simulate API call delay
            time.sleep(1)
            
            # Simulate threat data
            threat_data = {
                'source': source,
                'threat_type': 'malware',
                'indicator': f'192.168.1.{i + 1}',
                'confidence': 0.8,
                'severity': 'medium'
            }
            
            updated_threats.append(threat_data)
        
        return {
            'updated_threats': updated_threats,
            'total_sources': total_sources
        }


class SecurityReportGenerationJob(BackgroundJob):
    """Job to generate security reports"""
    
    def __init__(self, job_id: str, report_type: str, period: str, recipients: List[str] = None):
        super().__init__(job_id, f"Security Report: {report_type}", JobPriority.NORMAL)
        self.report_type = report_type
        self.period = period
        self.recipients = recipients or []
    
    def execute(self) -> Dict[str, Any]:
        """Execute report generation"""
        self.on_progress(25, "Gathering security data")
        
        # Get analytics data
        if self.report_type == 'overview':
            report_data = security_analytics.get_overview_statistics(days=30)
        elif self.report_type == 'user_behavior':
            report_data = security_analytics.get_user_behavior_analytics(days=30)
        elif self.report_type == 'threat_intelligence':
            report_data = security_analytics.get_threat_intelligence_analytics(days=30)
        elif self.report_type == 'incidents':
            report_data = security_analytics.get_incident_analytics(days=30)
        elif self.report_type == 'compliance':
            report_data = security_analytics.get_compliance_analytics(days=30)
        else:
            report_data = {'error': f'Unknown report type: {self.report_type}'}
        
        self.on_progress(75, "Generating report")
        
        # Generate report (simplified)
        report = {
            'report_type': self.report_type,
            'period': self.period,
            'generated_at': timezone.now().isoformat(),
            'data': report_data,
            'summary': f"Security report for {self.report_type} covering {self.period}"
        }
        
        self.on_progress(100, "Report generated successfully")
        
        return report


class UserRiskAssessmentJob(BackgroundJob):
    """Job to assess user security risk"""
    
    def __init__(self, job_id: str, user_id: Union[int, str]):
        super().__init__(job_id, f"User Risk Assessment: {user_id}", JobPriority.NORMAL)
        self.user_id = user_id
    
    def execute(self) -> Dict[str, Any]:
        """Execute user risk assessment"""
        try:
            user = User.objects.get(id=self.user_id)
        except User.DoesNotExist:
            raise ValueError(f"User not found: {self.user_id}")
        
        self.on_progress(25, "Analyzing user activity")
        
        # Get user security data
        from .selectors import SecurityLogSelector
        log_selector = SecurityLogSelector()
        
        recent_logs = log_selector.filter_by_user(user).filter_recent(days=30)
        
        self.on_progress(50, "Calculating risk factors")
        
        # Calculate risk factors
        total_logs = recent_logs.count()
        failed_attempts = recent_logs.filter_failed_attempts().count()
        high_risk_logs = recent_logs.filter_high_risk().count()
        unique_ips = recent_logs.values('ip_address').distinct().count()
        
        risk_factors = {
            'failed_attempt_rate': (failed_attempts / max(1, total_logs)) * 100,
            'high_risk_rate': (high_risk_logs / max(1, total_logs)) * 100,
            'ip_diversity': unique_ips,
            'total_activity': total_logs
        }
        
        self.on_progress(75, "Calculating risk score")
        
        # Calculate risk score
        from .helpers import SecurityMetrics
        risk_score = SecurityMetrics.calculate_risk_score(risk_factors)
        
        self.on_progress(100, "Risk assessment completed")
        
        return {
            'user_id': self.user_id,
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'assessment_date': timezone.now().isoformat()
        }


class IncidentEscalationJob(BackgroundJob):
    """Job to escalate security incidents"""
    
    def __init__(self, job_id: str, incident_id: Union[int, str]):
        super().__init__(job_id, f"Incident Escalation: {incident_id}", JobPriority.HIGH)
        self.incident_id = incident_id
    
    def execute(self) -> Dict[str, Any]:
        """Execute incident escalation"""
        try:
            incident = SecurityIncident.objects.get(id=self.incident_id)
        except SecurityIncident.DoesNotExist:
            raise ValueError(f"Incident not found: {self.incident_id}")
        
        self.on_progress(25, "Analyzing incident severity")
        
        # Check if escalation is needed
        escalation_needed = (
            incident.priority == 'critical' or
            incident.severity == 'critical' or
            (timezone.now() - incident.opened_at).total_seconds() > 86400  # 24 hours
        )
        
        if not escalation_needed:
            return {
                'incident_id': self.incident_id,
                'escalated': False,
                'reason': 'No escalation needed'
            }
        
        self.on_progress(50, "Escalating incident")
        
        # Escalate incident
        current_priority = incident.priority
        priority_order = ['low', 'medium', 'high', 'critical']
        
        try:
            current_index = priority_order.index(current_priority)
            if current_index < len(priority_order) - 1:
                new_priority = priority_order[current_index + 1]
                incident.priority = new_priority
                incident.status = 'investigating'
                incident.save()
                
                # Log escalation
                SecurityLog.objects.create(
                    security_type='incident_escalated',
                    severity='high',
                    description=f'Incident escalated from {current_priority} to {new_priority}',
                    metadata={
                        'incident_id': str(incident.id),
                        'old_priority': current_priority,
                        'new_priority': new_priority
                    }
                )
        except ValueError:
            raise ValueError(f"Unknown incident priority: {current_priority}")
        
        self.on_progress(100, "Incident escalated")
        
        return {
            'incident_id': self.incident_id,
            'escalated': True,
            'old_priority': current_priority,
            'new_priority': incident.priority
        }


class SanctionEnforcementJob(BackgroundJob):
    """Job to enforce security sanctions"""
    
    def __init__(self, job_id: str):
        super().__init__(job_id, "Sanction Enforcement", JobPriority.HIGH)
    
    def execute(self) -> Dict[str, Any]:
        """Execute sanction enforcement"""
        self.on_progress(25, "Processing expired sanctions")
        
        # Process expired sanctions
        expired_count = sanction_manager.process_expired_sanctions()
        
        self.on_progress(50, "Evaluating policies")
        
        # Evaluate policies for active users
        recent_users = User.objects.filter(
            last_login__gte=timezone.now() - timedelta(days=1)
        )
        
        applied_sanctions = []
        total_users = recent_users.count()
        
        for i, user in enumerate(recent_users):
            self.on_progress(50 + (i / total_users * 40), f"Evaluating user {i + 1}/{total_users}")
            
            user_sanctions = sanction_manager.evaluate_policies(user)
            applied_sanctions.extend(user_sanctions)
        
        self.on_progress(100, "Sanction enforcement completed")
        
        return {
            'expired_sanctions': expired_count,
            'applied_sanctions': len(applied_sanctions),
            'evaluated_users': total_users
        }


class CacheWarmingJob(BackgroundJob):
    """Job to warm security caches"""
    
    def __init__(self, job_id: str):
        super().__init__(job_id, "Cache Warming", JobPriority.LOW)
    
    def execute(self) -> Dict[str, Any]:
        """Execute cache warming"""
        from .caching import cache_warmer
        
        self.on_progress(25, "Warming user cache")
        
        # Warm user cache for recent users
        recent_users = User.objects.filter(
            last_login__gte=timezone.now() - timedelta(days=7)
        )
        
        user_ids = [str(user.id) for user in recent_users[:100]]  # Limit to 100 users
        cache_warmer.warm_user_cache(user_ids)
        
        self.on_progress(50, "Warming statistics cache")
        
        # Warm statistics cache
        cache_warmer.warm_stats_cache()
        
        self.on_progress(75, "Warming threat cache")
        
        # Warm threat cache
        cache_warmer.warm_threat_cache()
        
        self.on_progress(100, "Cache warming completed")
        
        return {
            'warmed_users': len(user_ids),
            'warmed_stats': True,
            'warmed_threats': True
        }


class JobQueue:
    """Job queue management"""
    
    def __init__(self):
        self.jobs = {}
        self.running_jobs = {}
        self.completed_jobs = {}
        self.max_concurrent_jobs = getattr(settings, 'SECURITY_MAX_CONCURRENT_JOBS', 5)
    
    def enqueue(self, job: BackgroundJob) -> str:
        """Enqueue a job"""
        self.jobs[job.job_id] = job
        logger.info(f"Enqueued job: {job.job_id}")
        return job.job_id
    
    def dequeue(self) -> Optional[BackgroundJob]:
        """Get next job to execute"""
        if len(self.running_jobs) >= self.max_concurrent_jobs:
            return None
        
        # Get jobs by priority
        priority_order = {
            JobPriority.CRITICAL: 0,
            JobPriority.HIGH: 1,
            JobPriority.NORMAL: 2,
            JobPriority.LOW: 3
        }
        
        # Sort jobs by priority and creation time
        pending_jobs = [
            job for job in self.jobs.values()
            if job.status == JobStatus.PENDING
        ]
        
        if not pending_jobs:
            return None
        
        pending_jobs.sort(key=lambda j: (priority_order[j.priority], j.created_at))
        
        return pending_jobs[0]
    
    def get_job(self, job_id: str) -> Optional[BackgroundJob]:
        """Get job by ID"""
        return self.jobs.get(job_id)
    
    def get_jobs(self, status: str = None) -> List[BackgroundJob]:
        """Get jobs by status"""
        jobs = list(self.jobs.values())
        
        if status:
            jobs = [job for job in jobs if job.status == status]
        
        return jobs
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        job = self.get_job(job_id)
        if job and job.status == JobStatus.PENDING:
            job.status = JobStatus.CANCELLED
            logger.info(f"Cancelled job: {job_id}")
            return True
        return False
    
    def retry_job(self, job_id: str) -> bool:
        """Retry a failed job"""
        job = self.get_job(job_id)
        if job and job.status == JobStatus.FAILED and job.can_retry():
            job.status = JobStatus.PENDING
            job.retry_count += 1
            job.error_message = None
            logger.info(f"Retrying job: {job_id} (attempt {job.retry_count})")
            return True
        return False
    
    def cleanup_completed_jobs(self, hours: int = 24) -> int:
        """Clean up completed jobs"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        completed_jobs = [
            job_id for job_id, job in self.jobs.items()
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
            and job.completed_at and job.completed_at < cutoff_time
        ]
        
        for job_id in completed_jobs:
            del self.jobs[job_id]
        
        logger.info(f"Cleaned up {len(completed_jobs)} completed jobs")
        return len(completed_jobs)
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        jobs = list(self.jobs.values())
        
        stats = {
            'total_jobs': len(jobs),
            'pending': len([j for j in jobs if j.status == JobStatus.PENDING]),
            'running': len([j for j in jobs if j.status == JobStatus.RUNNING]),
            'completed': len([j for j in jobs if j.status == JobStatus.COMPLETED]),
            'failed': len([j for j in jobs if j.status == JobStatus.FAILED]),
            'cancelled': len([j for j in jobs if j.status == JobStatus.CANCELLED]),
            'by_priority': {
                priority: len([j for j in jobs if j.priority == priority])
                for priority in [JobPriority.CRITICAL, JobPriority.HIGH, JobPriority.NORMAL, JobPriority.LOW]
            }
        }
        
        return stats


class JobExecutor:
    """Job execution engine"""
    
    def __init__(self, job_queue: JobQueue):
        self.job_queue = job_queue
        self.running = False
        self.worker_thread = None
    
    def start(self):
        """Start the job executor"""
        if self.running:
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        logger.info("Job executor started")
    
    def stop(self):
        """Stop the job executor"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        
        logger.info("Job executor stopped")
    
    def _worker_loop(self):
        """Main worker loop"""
        while self.running:
            try:
                # Get next job
                job = self.job_queue.dequeue()
                
                if job:
                    self._execute_job(job)
                else:
                    # No jobs available, wait
                    time.sleep(1)
                
            except Exception as e:
                logger.error(f"Job executor error: {e}")
                time.sleep(5)
    
    def _execute_job(self, job: BackgroundJob):
        """Execute a single job"""
        job.status = JobStatus.RUNNING
        job.started_at = timezone.now()
        
        try:
            logger.info(f"Executing job: {job.job_id}")
            
            # Check for timeout
            if job.should_timeout():
                raise TimeoutError(f"Job {job.job_id} timed out")
            
            # Execute the job
            result = job.execute()
            
            # Mark as completed
            job.on_success(result)
            
        except Exception as e:
            logger.error(f"Job {job.job_id} execution error: {e}")
            job.on_failure(e)
            
            # Retry if possible
            if job.can_retry():
                job.status = JobStatus.PENDING
                logger.info(f"Job {job.job_id} will be retried")
        
        finally:
            # Remove from running jobs
            if job.job_id in self.job_queue.running_jobs:
                del self.job_queue.running_jobs[job.job_id]


class JobScheduler:
    """Job scheduler for recurring jobs"""
    
    def __init__(self, job_queue: JobQueue):
        self.job_queue = job_queue
        self.scheduled_jobs = {}
        self.running = False
        self.scheduler_thread = None
    
    def schedule_job(self, job_class: Type[BackgroundJob], schedule: str, **kwargs) -> str:
        """Schedule a recurring job"""
        job_id = SecurityUtils.generate_uuid()
        
        scheduled_job = {
            'job_id': job_id,
            'job_class': job_class,
            'schedule': schedule,  # cron-like schedule (simplified)
            'kwargs': kwargs,
            'last_run': None,
            'next_run': self._calculate_next_run(schedule),
            'enabled': True
        }
        
        self.scheduled_jobs[job_id] = scheduled_job
        logger.info(f"Scheduled job: {job_id} with schedule: {schedule}")
        
        return job_id
    
    def unschedule_job(self, job_id: str) -> bool:
        """Unschedule a job"""
        if job_id in self.scheduled_jobs:
            del self.scheduled_jobs[job_id]
            logger.info(f"Unscheduled job: {job_id}")
            return True
        return False
    
    def start(self):
        """Start the scheduler"""
        if self.running:
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("Job scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        logger.info("Job scheduler stopped")
    
    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                now = timezone.now()
                
                for job_id, scheduled_job in list(self.scheduled_jobs.items()):
                    if not scheduled_job['enabled']:
                        continue
                    
                    # Check if it's time to run
                    if now >= scheduled_job['next_run']:
                        # Create and enqueue job
                        job = scheduled_job['job_class'](
                            scheduled_job['job_id'],
                            **scheduled_job['kwargs']
                        )
                        
                        self.job_queue.enqueue(job)
                        
                        # Update schedule
                        scheduled_job['last_run'] = now
                        scheduled_job['next_run'] = self._calculate_next_run(scheduled_job['schedule'])
                        
                        logger.info(f"Scheduled job {job_id} enqueued")
                
                # Sleep for 1 minute
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Job scheduler error: {e}")
                time.sleep(60)
    
    def _calculate_next_run(self, schedule: str) -> datetime:
        """Calculate next run time (simplified)"""
        now = timezone.now()
        
        # Simple schedule parsing (in production, use proper cron parsing)
        if schedule == 'hourly':
            return now + timedelta(hours=1)
        elif schedule == 'daily':
            return now + timedelta(days=1)
        elif schedule == 'weekly':
            return now + timedelta(weeks=1)
        elif schedule == 'monthly':
            return now + timedelta(days=30)
        else:
            # Default to hourly
            return now + timedelta(hours=1)


# Global instances
job_queue = JobQueue()
job_executor = JobExecutor(job_queue)
job_scheduler = JobScheduler(job_queue)


def initialize_background_jobs():
    """Initialize background job system"""
    # Start executor and scheduler
    job_executor.start()
    job_scheduler.start()
    
    # Schedule recurring jobs
    # Log cleanup - daily at 2 AM
    job_scheduler.schedule_job(
        SecurityLogCleanupJob,
        'daily',
        days_to_keep=90
    )
    
    # Threat intelligence update - every 6 hours
    job_scheduler.schedule_job(
        ThreatIntelligenceUpdateJob,
        'hourly'
    )
    
    # Security report - daily at 8 AM
    job_scheduler.schedule_job(
        SecurityReportGenerationJob,
        'daily',
        report_type='overview',
        period='last_24h'
    )
    
    # Sanction enforcement - every hour
    job_scheduler.schedule_job(
        SanctionEnforcementJob,
        'hourly'
    )
    
    # Cache warming - every 4 hours
    job_scheduler.schedule_job(
        CacheWarmingJob,
        'hourly'
    )
    
    logger.info("Background jobs initialized")


# Export classes and utilities
__all__ = [
    'JobStatus',
    'JobPriority',
    'BackgroundJob',
    'SecurityLogCleanupJob',
    'ThreatIntelligenceUpdateJob',
    'SecurityReportGenerationJob',
    'UserRiskAssessmentJob',
    'IncidentEscalationJob',
    'SanctionEnforcementJob',
    'CacheWarmingJob',
    'JobQueue',
    'job_queue',
    'JobExecutor',
    'job_executor',
    'JobScheduler',
    'job_scheduler',
    'initialize_background_jobs'
]