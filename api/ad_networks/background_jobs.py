"""
api/ad_networks/background_jobs.py
Background job processing for ad networks module
SaaS-ready with tenant support
"""

import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Callable
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache

from .models import (
    AdNetwork, Offer, UserOfferEngagement, OfferConversion,
    OfferReward, UserWallet, NetworkHealthCheck, OfferDailyLimit
)
from .choices import (
    OfferStatus, EngagementStatus, ConversionStatus,
    RewardStatus, NetworkStatus
)
from .constants import FRAUD_SCORE_THRESHOLD, CACHE_TIMEOUTS
from .helpers import get_cache_key

logger = logging.getLogger(__name__)
User = get_user_model()


# ==================== JOB STATUS ====================

class JobStatus:
    """Job status definitions"""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


# ==================== JOB PRIORITY ====================

class JobPriority:
    """Job priority levels"""
    
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ==================== BASE JOB ====================

class BaseJob:
    """Base job class"""
    
    def __init__(self, tenant_id: str = 'default', job_id: str = None):
        self.tenant_id = tenant_id
        self.job_id = job_id or str(uuid.uuid4())
        self.status = JobStatus.PENDING
        self.priority = JobPriority.NORMAL
        self.created_at = timezone.now()
        self.started_at = None
        self.completed_at = None
        self.error_message = None
        self.retry_count = 0
        self.max_retries = 3
        self.timeout = 300  # 5 minutes default
        
    def execute(self) -> Dict[str, Any]:
        """Execute the job (to be implemented by subclasses)"""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def run(self) -> Dict[str, Any]:
        """Run the job with error handling and retry logic"""
        try:
            self.status = JobStatus.RUNNING
            self.started_at = timezone.now()
            
            result = self.execute()
            
            self.status = JobStatus.COMPLETED
            self.completed_at = timezone.now()
            
            return {
                'job_id': self.job_id,
                'status': self.status,
                'result': result,
                'started_at': self.started_at.isoformat(),
                'completed_at': self.completed_at.isoformat(),
                'duration_seconds': (self.completed_at - self.started_at).total_seconds(),
            }
            
        except Exception as e:
            self.error_message = str(e)
            logger.error(f"Job {self.job_id} failed: {str(e)}")
            
            if self.retry_count < self.max_retries:
                self.retry_count += 1
                self.status = JobStatus.RETRYING
                
                # Schedule retry (in production, use proper job queue)
                retry_delay = min(60 * (2 ** self.retry_count), 300)  # Exponential backoff
                
                logger.info(f"Job {self.job_id} will retry in {retry_delay} seconds (attempt {self.retry_count})")
                
                # For now, just retry immediately
                return self.run()
            else:
                self.status = JobStatus.FAILED
                self.completed_at = timezone.now()
                
                return {
                    'job_id': self.job_id,
                    'status': self.status,
                    'error': self.error_message,
                    'started_at': self.started_at.isoformat(),
                    'completed_at': self.completed_at.isoformat(),
                    'retry_count': self.retry_count,
                }
    
    def cancel(self) -> bool:
        """Cancel the job"""
        if self.status in [JobStatus.PENDING, JobStatus.RETRYING]:
            self.status = JobStatus.CANCELLED
            self.completed_at = timezone.now()
            return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary"""
        return {
            'job_id': self.job_id,
            'tenant_id': self.tenant_id,
            'status': self.status,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
        }


# ==================== OFFER SYNC JOB ====================

class OfferSyncJob(BaseJob):
    """Job to sync offers from ad networks"""
    
    def __init__(self, tenant_id: str = 'default', network_id: int = None, **kwargs):
        super().__init__(tenant_id, **kwargs)
        self.network_id = network_id
        self.priority = JobPriority.HIGH
    
    def execute(self) -> Dict[str, Any]:
        """Execute offer sync"""
        try:
            from .services.OfferSyncService import OfferSyncService
            
            sync_service = OfferSyncService(self.tenant_id)
            
            if self.network_id:
                # Sync specific network
                result = sync_service.sync_network_offers(self.network_id)
                return {
                    'network_id': self.network_id,
                    'sync_result': result,
                }
            else:
                # Sync all active networks
                networks = AdNetwork.objects.filter(
                    tenant_id=self.tenant_id,
                    is_active=True,
                    status=NetworkStatus.ACTIVE
                )
                
                results = []
                for network in networks:
                    try:
                        result = sync_service.sync_network_offers(network.id)
                        results.append({
                            'network_id': network.id,
                            'network_name': network.name,
                            'result': result,
                        })
                    except Exception as e:
                        logger.error(f"Error syncing network {network.id}: {str(e)}")
                        results.append({
                            'network_id': network.id,
                            'network_name': network.name,
                            'error': str(e),
                        })
                
                return {
                    'total_networks': networks.count(),
                    'results': results,
                }
                
        except Exception as e:
            logger.error(f"Error in offer sync job: {str(e)}")
            raise


# ==================== CONVERSION PROCESSING JOB ====================

class ConversionProcessingJob(BaseJob):
    """Job to process pending conversions"""
    
    def __init__(self, tenant_id: str = 'default', conversion_id: int = None, **kwargs):
        super().__init__(tenant_id, **kwargs)
        self.conversion_id = conversion_id
        self.priority = JobPriority.HIGH
    
    def execute(self) -> Dict[str, Any]:
        """Execute conversion processing"""
        try:
            from .services.ConversionService import ConversionService
            
            conversion_service = ConversionService(self.tenant_id)
            
            if self.conversion_id:
                # Process specific conversion
                result = conversion_service.process_conversion(self.conversion_id)
                return {
                    'conversion_id': self.conversion_id,
                    'processing_result': result,
                }
            else:
                # Process all pending conversions
                conversions = OfferConversion.objects.filter(
                    tenant_id=self.tenant_id,
                    status=ConversionStatus.PENDING
                )[:100]  # Limit to 100 per job
                
                results = []
                for conversion in conversions:
                    try:
                        result = conversion_service.process_conversion(conversion.id)
                        results.append({
                            'conversion_id': conversion.id,
                            'result': result,
                        })
                    except Exception as e:
                        logger.error(f"Error processing conversion {conversion.id}: {str(e)}")
                        results.append({
                            'conversion_id': conversion.id,
                            'error': str(e),
                        })
                
                return {
                    'total_conversions': len(conversions),
                    'results': results,
                }
                
        except Exception as e:
            logger.error(f"Error in conversion processing job: {str(e)}")
            raise


# ==================== REWARD PROCESSING JOB ====================

class RewardProcessingJob(BaseJob):
    """Job to process approved rewards"""
    
    def __init__(self, tenant_id: str = 'default', reward_id: int = None, **kwargs):
        super().__init__(tenant_id, **kwargs)
        self.reward_id = reward_id
        self.priority = JobPriority.HIGH
    
    def execute(self) -> Dict[str, Any]:
        """Execute reward processing"""
        try:
            from .services.RewardService import RewardService
            
            reward_service = RewardService(self.tenant_id)
            
            if self.reward_id:
                # Process specific reward
                result = reward_service.process_reward(self.reward_id)
                return {
                    'reward_id': self.reward_id,
                    'processing_result': result,
                }
            else:
                # Process all approved rewards
                rewards = OfferReward.objects.filter(
                    tenant_id=self.tenant_id,
                    status=RewardStatus.APPROVED
                )[:100]  # Limit to 100 per job
                
                results = []
                for reward in rewards:
                    try:
                        result = reward_service.process_reward(reward.id)
                        results.append({
                            'reward_id': reward.id,
                            'result': result,
                        })
                    except Exception as e:
                        logger.error(f"Error processing reward {reward.id}: {str(e)}")
                        results.append({
                            'reward_id': reward.id,
                            'error': str(e),
                        })
                
                return {
                    'total_rewards': len(rewards),
                    'results': results,
                }
                
        except Exception as e:
            logger.error(f"Error in reward processing job: {str(e)}")
            raise


# ==================== HEALTH CHECK JOB ====================

class HealthCheckJob(BaseJob):
    """Job to perform health checks on ad networks"""
    
    def __init__(self, tenant_id: str = 'default', network_id: int = None, **kwargs):
        super().__init__(tenant_id, **kwargs)
        self.network_id = network_id
        self.priority = JobPriority.NORMAL
    
    def execute(self) -> Dict[str, Any]:
        """Execute health check"""
        try:
            from .services.NetworkHealthService import NetworkHealthService
            
            health_service = NetworkHealthService(self.tenant_id)
            
            if self.network_id:
                # Check specific network
                result = health_service.check_network_health(self.network_id)
                return {
                    'network_id': self.network_id,
                    'health_result': result,
                }
            else:
                # Check all active networks
                networks = AdNetwork.objects.filter(
                    tenant_id=self.tenant_id,
                    is_active=True,
                    status=NetworkStatus.ACTIVE
                )
                
                results = []
                for network in networks:
                    try:
                        result = health_service.check_network_health(network.id)
                        results.append({
                            'network_id': network.id,
                            'network_name': network.name,
                            'result': result,
                        })
                    except Exception as e:
                        logger.error(f"Error checking health for network {network.id}: {str(e)}")
                        results.append({
                            'network_id': network.id,
                            'network_name': network.name,
                            'error': str(e),
                        })
                
                return {
                    'total_networks': networks.count(),
                    'results': results,
                }
                
        except Exception as e:
            logger.error(f"Error in health check job: {str(e)}")
            raise


# ==================== DAILY LIMIT RESET JOB ====================

class DailyLimitResetJob(BaseJob):
    """Job to reset daily limits"""
    
    def __init__(self, tenant_id: str = 'default', **kwargs):
        super().__init__(tenant_id, **kwargs)
        self.priority = JobPriority.NORMAL
    
    def execute(self) -> Dict[str, Any]:
        """Execute daily limit reset"""
        try:
            # Get all daily limits that need reset
            today = timezone.now().date()
            limits_to_reset = OfferDailyLimit.objects.filter(
                tenant_id=self.tenant_id,
                last_reset_at__date__lt=today
            )
            
            reset_count = 0
            
            for limit in limits_to_reset:
                try:
                    with transaction.atomic():
                        limit.count_today = 0
                        limit.last_reset_at = timezone.now()
                        limit.save(update_fields=['count_today', 'last_reset_at'])
                        reset_count += 1
                except Exception as e:
                    logger.error(f"Error resetting daily limit {limit.id}: {str(e)}")
            
            return {
                'reset_count': reset_count,
                'date': today.isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error in daily limit reset job: {str(e)}")
            raise


# ==================== ANALYTICS CALCULATION JOB ====================

class AnalyticsCalculationJob(BaseJob):
    """Job to calculate analytics data"""
    
    def __init__(self, tenant_id: str = 'default', period: str = 'daily', **kwargs):
        super().__init__(tenant_id, **kwargs)
        self.period = period
        self.priority = JobPriority.LOW
    
    def execute(self) -> Dict[str, Any]:
        """Execute analytics calculation"""
        try:
            from .analytics import OfferAnalytics, UserAnalytics, RevenueAnalytics
            
            # Calculate date range
            if self.period == 'daily':
                start_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(days=1)
            elif self.period == 'weekly':
                start_date = timezone.now() - timedelta(days=7)
                end_date = timezone.now()
            elif self.period == 'monthly':
                start_date = timezone.now() - timedelta(days=30)
                end_date = timezone.now()
            else:
                raise ValueError(f"Unsupported period: {self.period}")
            
            # Calculate offer analytics
            offer_analytics = OfferAnalytics(self.tenant_id)
            top_offers = offer_analytics.get_top_performing_offers('custom', 10, start_date, end_date)
            category_analytics = offer_analytics.get_category_analytics('custom', start_date, end_date)
            
            # Calculate user analytics
            user_analytics = UserAnalytics(self.tenant_id)
            top_users = user_analytics.get_top_users('custom', 'revenue', 10, start_date, end_date)
            
            # Calculate revenue analytics
            revenue_analytics = RevenueAnalytics(self.tenant_id)
            revenue_data = revenue_analytics.get_revenue_analytics('custom', start_date, end_date)
            
            return {
                'period': self.period,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                },
                'offer_analytics': {
                    'top_offers': top_offers,
                    'category_analytics': category_analytics,
                },
                'user_analytics': {
                    'top_users': top_users,
                },
                'revenue_analytics': revenue_data,
            }
            
        except Exception as e:
            logger.error(f"Error in analytics calculation job: {str(e)}")
            raise


# ==================== CLEANUP JOB ====================

class CleanupJob(BaseJob):
    """Job to clean up old data"""
    
    def __init__(self, tenant_id: str = 'default', days_to_keep: int = 90, **kwargs):
        super().__init__(tenant_id, **kwargs)
        self.days_to_keep = days_to_keep
        self.priority = JobPriority.LOW
    
    def execute(self) -> Dict[str, Any]:
        """Execute cleanup"""
        try:
            cutoff_date = timezone.now() - timedelta(days=self.days_to_keep)
            
            cleanup_results = {}
            
            # Clean up old API logs
            from .models import NetworkAPILog
            api_logs_deleted = NetworkAPILog.objects.filter(
                tenant_id=self.tenant_id,
                request_timestamp__lt=cutoff_date
            ).delete()[0]
            
            cleanup_results['api_logs_deleted'] = api_logs_deleted
            
            # Clean up old webhook logs
            from .models import AdNetworkWebhookLog
            webhook_logs_deleted = AdNetworkWebhookLog.objects.filter(
                tenant_id=self.tenant_id,
                created_at__lt=cutoff_date
            ).delete()[0]
            
            cleanup_results['webhook_logs_deleted'] = webhook_logs_deleted
            
            # Clean up old health checks (keep only last 30 days)
            health_cutoff = timezone.now() - timedelta(days=30)
            health_checks_deleted = NetworkHealthCheck.objects.filter(
                tenant_id=self.tenant_id,
                checked_at__lt=health_cutoff
            ).delete()[0]
            
            cleanup_results['health_checks_deleted'] = health_checks_deleted
            
            return {
                'days_to_keep': self.days_to_keep,
                'cutoff_date': cutoff_date.isoformat(),
                'cleanup_results': cleanup_results,
                'total_deleted': sum(cleanup_results.values()),
            }
            
        except Exception as e:
            logger.error(f"Error in cleanup job: {str(e)}")
            raise


# ==================== JOB QUEUE MANAGER ====================

class JobQueueManager:
    """Simple job queue manager (in production, use Celery or similar)"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.jobs = {}
        self.job_results = {}
    
    def enqueue_job(self, job: BaseJob) -> str:
        """Enqueue a job"""
        job.tenant_id = self.tenant_id
        self.jobs[job.job_id] = job
        logger.info(f"Job {job.job_id} enqueued")
        return job.job_id
    
    def dequeue_job(self) -> Optional[BaseJob]:
        """Dequeue next job"""
        # Simple FIFO implementation
        if self.jobs:
            job_id = next(iter(self.jobs))
            job = self.jobs.pop(job_id)
            return job
        return None
    
    def run_job(self, job: BaseJob) -> Dict[str, Any]:
        """Run a job and store result"""
        result = job.run()
        self.job_results[job.job_id] = result
        return result
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status"""
        if job_id in self.jobs:
            return self.jobs[job_id].to_dict()
        elif job_id in self.job_results:
            return self.job_results[job_id]
        return None
    
    def get_pending_jobs(self) -> List[Dict[str, Any]]:
        """Get all pending jobs"""
        return [job.to_dict() for job in self.jobs.values() if job.status == JobStatus.PENDING]
    
    def get_running_jobs(self) -> List[Dict[str, Any]]:
        """Get all running jobs"""
        return [job.to_dict() for job in self.jobs.values() if job.status == JobStatus.RUNNING]
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        if job_id in self.jobs:
            return self.jobs[job_id].cancel()
        return False
    
    def run_all_jobs(self) -> Dict[str, Any]:
        """Run all queued jobs"""
        results = []
        
        while self.jobs:
            job = self.dequeue_job()
            if job:
                result = self.run_job(job)
                results.append(result)
        
        return {
            'total_jobs': len(results),
            'results': results,
        }


# ==================== SCHEDULED JOB MANAGER ====================

class ScheduledJobManager:
    """Manager for scheduled jobs"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.queue_manager = JobQueueManager(tenant_id)
        self.schedules = {}
    
    def schedule_job(self, job_class: type, schedule: str, **kwargs) -> str:
        """Schedule a recurring job"""
        job_id = str(uuid.uuid4())
        
        self.schedules[job_id] = {
            'job_class': job_class,
            'schedule': schedule,
            'kwargs': kwargs,
            'last_run': None,
            'next_run': self._calculate_next_run(schedule),
            'active': True,
        }
        
        logger.info(f"Job {job_id} scheduled with schedule: {schedule}")
        return job_id
    
    def _calculate_next_run(self, schedule: str) -> datetime:
        """Calculate next run time"""
        now = timezone.now()
        
        if schedule == 'hourly':
            return now + timedelta(hours=1)
        elif schedule == 'daily':
            return now + timedelta(days=1)
        elif schedule == 'weekly':
            return now + timedelta(weeks=1)
        elif schedule == 'monthly':
            return now + timedelta(days=30)
        else:
            # Parse cron-like schedule
            return now + timedelta(hours=1)  # Default to hourly
    
    def run_scheduled_jobs(self) -> Dict[str, Any]:
        """Run all scheduled jobs that are due"""
        now = timezone.now()
        results = []
        
        for job_id, schedule_info in self.schedules.items():
            if not schedule_info['active']:
                continue
            
            if now >= schedule_info['next_run']:
                try:
                    # Create and run job
                    job = schedule_info['job_class'](
                        tenant_id=self.tenant_id,
                        **schedule_info['kwargs']
                    )
                    
                    result = self.queue_manager.run_job(job)
                    results.append({
                        'job_id': job_id,
                        'schedule': schedule_info['schedule'],
                        'result': result,
                    })
                    
                    # Update schedule
                    schedule_info['last_run'] = now
                    schedule_info['next_run'] = self._calculate_next_run(schedule_info['schedule'])
                    
                except Exception as e:
                    logger.error(f"Error running scheduled job {job_id}: {str(e)}")
                    results.append({
                        'job_id': job_id,
                        'schedule': schedule_info['schedule'],
                        'error': str(e),
                    })
        
        return {
            'total_jobs': len(results),
            'results': results,
        }
    
    def setup_default_schedules(self):
        """Setup default scheduled jobs"""
        # Daily limit reset
        self.schedule_job(DailyLimitResetJob, 'daily')
        
        # Health checks
        self.schedule_job(HealthCheckJob, 'hourly')
        
        # Analytics calculation
        self.schedule_job(AnalyticsCalculationJob, 'daily', period='daily')
        
        # Cleanup
        self.schedule_job(CleanupJob, 'weekly', days_to_keep=90)
        
        logger.info(f"Default schedules setup for tenant {self.tenant_id}")


# ==================== EXPORTS ====================

__all__ = [
    # Status and priority
    'JobStatus',
    'JobPriority',
    
    # Jobs
    'BaseJob',
    'OfferSyncJob',
    'ConversionProcessingJob',
    'RewardProcessingJob',
    'HealthCheckJob',
    'DailyLimitResetJob',
    'AnalyticsCalculationJob',
    'CleanupJob',
    
    # Managers
    'JobQueueManager',
    'ScheduledJobManager',
]
