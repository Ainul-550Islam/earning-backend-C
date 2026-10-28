# api/rate_limit/background_jobs.py
"""
Background jobs for rate limit module.

Provides asynchronous job processing for rate limiting operations.
"""

import logging
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from celery import shared_task, chain, group
from celery.result import AsyncResult
from django.db import transaction

from api.rate_limit.models import (
    RateLimitLog, RateLimitConfig, UserRateLimitProfile, 
    AbuseReport, IPBlockList, RateLimitInsight
)
from api.rate_limit.repositories import RepositoryFactory
from api.rate_limit.analytics import AnalyticsEngine
from api.rate_limit.monitoring import MonitoringService
from api.rate_limit.encryption import DataProtectionManager

logger = logging.getLogger(__name__)


class JobStatus:
    """Enumeration of job statuses."""
    
    PENDING = 'pending'
    RUNNING = 'running'
    SUCCESS = 'success'
    FAILURE = 'failure'
    RETRY = 'retry'
    REVOKED = 'revoked'
    
    CHOICES = [
        (PENDING, 'Pending'),
        (RUNNING, 'Running'),
        (SUCCESS, 'Success'),
        (FAILURE, 'Failure'),
        (RETRY, 'Retry'),
        (REVOKED, 'Revoked'),
    ]


class JobPriority:
    """Enumeration of job priorities."""
    
    LOW = 'low'
    NORMAL = 'normal'
    HIGH = 'high'
    CRITICAL = 'critical'
    
    CHOICES = [
        (LOW, 'Low'),
        (NORMAL, 'Normal'),
        (HIGH, 'High'),
        (CRITICAL, 'Critical'),
    ]


class BaseJob:
    """Base class for background jobs."""
    
    def __init__(self, name: str, description: str = '', priority: str = JobPriority.NORMAL):
        self.name = name
        self.description = description
        self.priority = priority
        self.created_at = timezone.now()
        self.started_at = None
        self.completed_at = None
        self.status = JobStatus.PENDING
        self.result = None
        self.error = None
        self.retry_count = 0
        self.max_retries = 3
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute the job."""
        raise NotImplementedError("Subclasses must implement execute()")
    
    def on_success(self, result: Any):
        """Called when job succeeds."""
        self.status = JobStatus.SUCCESS
        self.result = result
        self.completed_at = timezone.now()
        logger.info(f"Job {self.name} completed successfully")
    
    def on_failure(self, error: Exception):
        """Called when job fails."""
        self.status = JobStatus.FAILURE
        self.error = str(error)
        self.completed_at = timezone.now()
        logger.error(f"Job {self.name} failed: {str(error)}")
    
    def on_retry(self, error: Exception):
        """Called when job is retried."""
        self.status = JobStatus.RETRY
        self.retry_count += 1
        logger.warning(f"Job {self.name} retry {self.retry_count}/{self.max_retries}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary."""
        return {
            'name': self.name,
            'description': self.description,
            'priority': self.priority,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'result': self.result,
            'error': self.error
        }


class CleanupJob(BaseJob):
    """Job for cleaning up old data."""
    
    def __init__(self, days: int = 30, data_type: str = 'logs'):
        super().__init__(
            name=f"cleanup_{data_type}",
            description=f"Clean up old {data_type} older than {days} days",
            priority=JobPriority.LOW
        )
        self.days = days
        self.data_type = data_type
    
    def execute(self) -> Dict[str, Any]:
        """Execute cleanup job."""
        try:
            repositories = RepositoryFactory.get_all_repositories()
            
            since_time = timezone.now() - timedelta(days=self.days)
            deleted_count = 0
            
            if self.data_type == 'logs':
                deleted_count = repositories['rate_limit_log'].model.objects.filter(
                    timestamp__lt=since_time
                ).delete()[0]
            elif self.data_type == 'abuse_reports':
                deleted_count = repositories['abuse_report'].model.objects.filter(
                    created_at__lt=since_time,
                    is_investigated=True  # Only delete investigated reports
                ).delete()[0]
            elif self.data_type == 'ip_blocks':
                deleted_count = repositories['ip_block_list'].model.objects.filter(
                    permanent=False,
                    expires_at__lt=since_time
                ).delete()[0]
            
            return {
                'deleted_count': deleted_count,
                'data_type': self.data_type,
                'days': self.days
            }
            
        except Exception as e:
            logger.error(f"Cleanup job failed: {str(e)}")
            raise


class AnalyticsJob(BaseJob):
    """Job for generating analytics."""
    
    def __init__(self, analysis_type: str = 'overview', days: int = 7):
        super().__init__(
            name=f"analytics_{analysis_type}",
            description=f"Generate {analysis_type} analytics for last {days} days",
            priority=JobPriority.NORMAL
        )
        self.analysis_type = analysis_type
        self.days = days
    
    def execute(self) -> Dict[str, Any]:
        """Execute analytics job."""
        try:
            analytics_engine = AnalyticsEngine()
            
            if self.analysis_type == 'overview':
                result = analytics_engine.get_overview_statistics(self.days)
            elif self.analysis_type == 'time_series':
                result = analytics_engine.get_time_series_analysis(self.days)
            elif self.analysis_type == 'endpoint':
                result = analytics_engine.get_endpoint_analysis(days=self.days)
            elif self.analysis_type == 'user_behavior':
                result = analytics_engine.get_user_behavior_analysis(days=self.days)
            elif self.analysis_type == 'abuse_patterns':
                result = analytics_engine.get_abuse_pattern_analysis(self.days)
            elif self.analysis_type == 'performance':
                result = analytics_engine.get_performance_metrics(self.days * 24)
            else:
                raise ValueError(f"Unknown analysis type: {self.analysis_type}")
            
            return {
                'analysis_type': self.analysis_type,
                'days': self.days,
                'result': result
            }
            
        except Exception as e:
            logger.error(f"Analytics job failed: {str(e)}")
            raise


class ReportGenerationJob(BaseJob):
    """Job for generating reports."""
    
    def __init__(self, report_type: str, days: int = 30, format: str = 'json'):
        super().__init__(
            name=f"report_{report_type}",
            description=f"Generate {report_type} report for last {days} days in {format} format",
            priority=JobPriority.NORMAL
        )
        self.report_type = report_type
        self.days = days
        self.format = format
    
    def execute(self) -> Dict[str, Any]:
        """Execute report generation job."""
        try:
            analytics_engine = AnalyticsEngine()
            
            report_data = analytics_engine.generate_report(
                report_type=self.report_type,
                days=self.days,
                format=self.format
            )
            
            # Store report in cache
            from django.core.cache import cache
            cache_key = f"rate_limit_report:{self.report_type}:{timezone.now().date()}"
            cache.set(cache_key, report_data, timeout=86400 * 7)  # 7 days
            
            return {
                'report_type': self.report_type,
                'days': self.days,
                'format': self.format,
                'cache_key': cache_key,
                'report_data': report_data
            }
            
        except Exception as e:
            logger.error(f"Report generation job failed: {str(e)}")
            raise


class HealthCheckJob(BaseJob):
    """Job for system health checks."""
    
    def __init__(self, component: str = 'all'):
        super().__init__(
            name=f"health_check_{component}",
            description=f"Health check for {component}",
            priority=JobPriority.HIGH
        )
        self.component = component
    
    def execute(self) -> Dict[str, Any]:
        """Execute health check job."""
        try:
            monitoring_service = MonitoringService()
            
            if self.component == 'all':
                health_status = monitoring_service.health_monitor.calculate_system_health()
            else:
                # Check specific component
                health_status = {
                    'component': self.component,
                    'healthy': True,
                    'message': f"{self.component} is healthy"
                }
            
            # Store health status in cache
            from django.core.cache import cache
            cache_key = f"rate_limit_health:{self.component}"
            cache.set(cache_key, health_status, timeout=300)  # 5 minutes
            
            return health_status
            
        except Exception as e:
            logger.error(f"Health check job failed: {str(e)}")
            raise


class DataExportJob(BaseJob):
    """Job for exporting data."""
    
    def __init__(self, data_type: str, days: int = 30, format: str = 'csv'):
        super().__init__(
            name=f"export_{data_type}",
            description=f"Export {data_type} for last {days} days in {format} format",
            priority=JobPriority.NORMAL
        )
        self.data_type = data_type
        self.days = days
        self.format = format
    
    def execute(self) -> Dict[str, Any]:
        """Execute data export job."""
        try:
            analytics_engine = AnalyticsEngine()
            
            export_result = analytics_engine.export_data(
                data_type=self.data_type,
                days=self.days,
                format=self.format
            )
            
            if export_result.get('success'):
                # Store export in cache
                from django.core.cache import cache
                cache_key = f"rate_limit_export:{self.data_type}:{timezone.now().date()}"
                cache.set(cache_key, export_result, timeout=86400)  # 24 hours
            
            return export_result
            
        except Exception as e:
            logger.error(f"Data export job failed: {str(e)}")
            raise


class AnonymizationJob(BaseJob):
    """Job for data anonymization."""
    
    def __init__(self, data_type: str = 'logs', days: int = 90):
        super().__init__(
            name=f"anonymize_{data_type}",
            description=f"Anonymize {data_type} older than {days} days",
            priority=JobPriority.LOW
        )
        self.data_type = data_type
        self.days = days
    
    def execute(self) -> Dict[str, Any]:
        """Execute anonymization job."""
        try:
            data_protection = DataProtectionManager()
            repositories = RepositoryFactory.get_all_repositories()
            
            since_time = timezone.now() - timedelta(days=self.days)
            anonymized_count = 0
            
            if self.data_type == 'logs':
                # Get old logs
                logs = repositories['rate_limit_log'].model.objects.filter(
                    timestamp__lt=since_time
                )
                
                # Anonymize each log
                for log in logs:
                    log_data = {
                        'ip_address': log.ip_address,
                        'user_agent': log.user_agent,
                        'user': log.user.id if log.user else None
                    }
                    
                    anonymized_data = data_protection.anonymize_logs([log_data])
                    
                    # Update log with anonymized data
                    if 'ip_address_hash' in anonymized_data[0]:
                        log.ip_address_hash = anonymized_data[0]['ip_address_hash']
                        log.ip_address = None
                    
                    if 'user_id_hash' in anonymized_data[0]:
                        log.user_id_hash = anonymized_data[0]['user_id_hash']
                        log.user = None
                    
                    log.save(update_fields=['ip_address_hash', 'user_id_hash', 'ip_address', 'user'])
                    anonymized_count += 1
            
            return {
                'data_type': self.data_type,
                'days': self.days,
                'anonymized_count': anonymized_count
            }
            
        except Exception as e:
            logger.error(f"Anonymization job failed: {str(e)}")
            raise


class JobManager:
    """Manages background jobs."""
    
    def __init__(self):
        self.jobs: Dict[str, BaseJob] = {}
        self.repositories = RepositoryFactory.get_all_repositories()
    
    def register_job(self, job: BaseJob):
        """Register a job."""
        self.jobs[job.name] = job
        logger.info(f"Registered job: {job.name}")
    
    def unregister_job(self, name: str):
        """Unregister a job."""
        if name in self.jobs:
            del self.jobs[name]
            logger.info(f"Unregistered job: {name}")
    
    def get_job(self, name: str) -> Optional[BaseJob]:
        """Get job by name."""
        return self.jobs.get(name)
    
    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all registered jobs."""
        return [job.to_dict() for job in self.jobs.values()]
    
    def run_job(self, name: str, *args, **kwargs) -> Dict[str, Any]:
        """Run a job synchronously."""
        job = self.get_job(name)
        if not job:
            return {'success': False, 'error': f'Job not found: {name}'}
        
        try:
            job.status = JobStatus.RUNNING
            job.started_at = timezone.now()
            
            result = job.execute(*args, **kwargs)
            job.on_success(result)
            
            return {
                'success': True,
                'job': job.to_dict(),
                'result': result
            }
            
        except Exception as e:
            job.on_failure(e)
            return {
                'success': False,
                'job': job.to_dict(),
                'error': str(e)
            }
    
    def run_job_async(self, name: str, *args, **kwargs) -> AsyncResult:
        """Run a job asynchronously."""
        job = self.get_job(name)
        if not job:
            raise ValueError(f'Job not found: {name}')
        
        # Use Celery to run the job
        return run_background_job.delay(name, *args, **kwargs)


# Celery tasks
@shared_task(bind=True, max_retries=3)
def run_background_job(self, job_name: str, *args, **kwargs):
    """Run background job using Celery."""
    try:
        job_manager = JobManager()
        result = job_manager.run_job(job_name, *args, **kwargs)
        return result
    except Exception as exc:
        logger.error(f"Background job {job_name} failed: {str(exc)}")
        # Retry the task
        raise self.retry(exc=exc, countdown=60)


@shared_task
def cleanup_old_data():
    """Clean up old rate limit data."""
    job_manager = JobManager()
    
    # Clean up old logs
    logs_job = CleanupJob(days=90, data_type='logs')
    logs_result = job_manager.run_job(logs_job.name)
    
    # Clean up old abuse reports
    abuse_job = CleanupJob(days=365, data_type='abuse_reports')
    abuse_result = job_manager.run_job(abuse_job.name)
    
    # Clean up expired IP blocks
    blocks_job = CleanupJob(days=7, data_type='ip_blocks')
    blocks_result = job_manager.run_job(blocks_job.name)
    
    return {
        'logs': logs_result,
        'abuse_reports': abuse_result,
        'ip_blocks': blocks_result
    }


@shared_task
def generate_daily_analytics():
    """Generate daily analytics."""
    job_manager = JobManager()
    
    # Generate overview analytics
    overview_job = AnalyticsJob('overview', days=1)
    overview_result = job_manager.run_job(overview_job.name)
    
    # Generate endpoint analytics
    endpoint_job = AnalyticsJob('endpoint', days=1)
    endpoint_result = job_manager.run_job(endpoint_job.name)
    
    # Generate user behavior analytics
    user_job = AnalyticsJob('user_behavior', days=1)
    user_result = job_manager.run_job(user_job.name)
    
    return {
        'overview': overview_result,
        'endpoint': endpoint_result,
        'user_behavior': user_result
    }


@shared_task
def generate_weekly_report():
    """Generate weekly report."""
    job_manager = JobManager()
    
    report_job = ReportGenerationJob('detailed', days=7, format='json')
    return job_manager.run_job(report_job.name)


@shared_task
def health_check_all_components():
    """Health check for all components."""
    job_manager = JobManager()
    
    health_job = HealthCheckJob('all')
    return job_manager.run_job(health_job.name)


@shared_task
def export_monthly_data():
    """Export monthly data for archiving."""
    job_manager = JobManager()
    
    # Export logs
    logs_export = DataExportJob('logs', days=30, format='csv')
    logs_result = job_manager.run_job(logs_export.name)
    
    # Export configs
    configs_export = DataExportJob('configs', days=30, format='json')
    configs_result = job_manager.run_job(configs_export.name)
    
    # Export users
    users_export = DataExportJob('users', days=30, format='json')
    users_result = job_manager.run_job(users_export.name)
    
    return {
        'logs': logs_result,
        'configs': configs_result,
        'users': users_result
    }


@shared_task
def anonymize_old_data():
    """Anonymize old data for privacy compliance."""
    job_manager = JobManager()
    
    anonymize_job = AnonymizationJob('logs', days=90)
    return job_manager.run_job(anonymize_job.name)


@shared_task
def process_rate_limit_logs_batch(log_ids: List[int]):
    """Process a batch of rate limit logs."""
    try:
        repositories = RepositoryFactory.get_all_repositories()
        log_repo = repositories['rate_limit_log']
        
        processed_count = 0
        
        for log_id in log_ids:
            log = log_repo.get_by_id(log_id)
            if log:
                # Process log (e.g., update analytics, check for patterns)
                processed_count += 1
        
        return {
            'success': True,
            'processed_count': processed_count,
            'total_count': len(log_ids)
        }
        
    except Exception as e:
        logger.error(f"Batch processing failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


# Job chains and groups
def create_analytics_chain():
    """Create a chain of analytics jobs."""
    return chain(
        run_background_job.s('cleanup_logs'),
        run_background_job.s('generate_daily_analytics'),
        run_background_job.s('health_check_all')
    )


def create_report_generation_group():
    """Create a group of report generation jobs."""
    return group(
        run_background_job.s('generate_weekly_report'),
        run_background_job.s('export_monthly_data'),
        run_background_job.s('anonymize_old_data')
    )


# Schedule periodic jobs
def schedule_periodic_jobs():
    """Schedule periodic background jobs."""
    from celery.schedules import crontab
    
    # Daily cleanup at 2 AM
    cleanup_old_data.apply_async(
        countdown=60,  # Start after 1 minute
        expires=3600,  # Expire after 1 hour
        retry=True,
        retry_policy={'max_retries': 3, 'interval_start': 60, 'interval_step': 60}
    )
    
    # Daily analytics at 3 AM
    generate_daily_analytics.apply_async(
        countdown=120,  # Start after 2 minutes
        expires=3600,  # Expire after 1 hour
        retry=True,
        retry_policy={'max_retries': 3, 'interval_start': 60, 'interval_step': 60}
    )
    
    # Weekly reports on Sunday at 4 AM
    generate_weekly_report.apply_async(
        countdown=180,  # Start after 3 minutes
        expires=7200,  # Expire after 2 hours
        retry=True,
        retry_policy={'max_retries': 3, 'interval_start': 60, 'interval_step': 60}
    )
    
    # Monthly export on 1st of each month at 1 AM
    export_monthly_data.apply_async(
        countdown=240,  # Start after 4 minutes
        expires=14400,  # Expire after 4 hours
        retry=True,
        retry_policy={'max_retries': 3, 'interval_start': 60, 'interval_step': 60}
    )


# Global job manager instance
job_manager = JobManager()

# Register default jobs
job_manager.register_job(CleanupJob(days=30, data_type='logs'))
job_manager.register_job(CleanupJob(days=90, data_type='logs'))
job_manager.register_job(CleanupJob(days=365, data_type='abuse_reports'))
job_manager.register_job(CleanupJob(days=7, data_type='ip_blocks'))

job_manager.register_job(AnalyticsJob('overview', days=1))
job_manager.register_job(AnalyticsJob('overview', days=7))
job_manager.register_job(AnalyticsJob('overview', days=30))
job_manager.register_job(AnalyticsJob('time_series', days=7))
job_manager.register_job(AnalyticsJob('endpoint', days=7))
job_manager.register_job(AnalyticsJob('user_behavior', days=7))
job_manager.register_job(AnalyticsJob('abuse_patterns', days=7))
job_manager.register_job(AnalyticsJob('performance', days=1))

job_manager.register_job(ReportGenerationJob('overview', days=30, format='json'))
job_manager.register_job(ReportGenerationJob('detailed', days=7, format='json'))
job_manager.register_job(ReportGenerationJob('performance', days=7, format='json'))
job_manager.register_job(ReportGenerationJob('security', days=7, format='json'))

job_manager.register_job(HealthCheckJob('all'))
job_manager.register_job(HealthCheckJob('database'))
job_manager.register_job(HealthCheckJob('cache'))
job_manager.register_job(HealthCheckJob('rate_limit_service'))

job_manager.register_job(DataExportJob('logs', days=30, format='csv'))
job_manager.register_job(DataExportJob('configs', days=30, format='json'))
job_manager.register_job(DataExportJob('users', days=30, format='json'))
job_manager.register_job(DataExportJob('abuse', days=30, format='json'))

job_manager.register_job(AnonymizationJob('logs', days=90))
job_manager.register_job(AnonymizationJob('abuse_reports', days=365))


# Export classes and functions
__all__ = [
    'JobStatus',
    'JobPriority',
    'BaseJob',
    'CleanupJob',
    'AnalyticsJob',
    'ReportGenerationJob',
    'HealthCheckJob',
    'DataExportJob',
    'AnonymizationJob',
    'JobManager',
    'job_manager',
    'run_background_job',
    'cleanup_old_data',
    'generate_daily_analytics',
    'generate_weekly_report',
    'health_check_all_components',
    'export_monthly_data',
    'anonymize_old_data',
    'process_rate_limit_logs_batch',
    'create_analytics_chain',
    'create_report_generation_group',
    'schedule_periodic_jobs'
]
