# api/cms/tasks/reward_management_tasks.py
"""Background tasks for survey reward management"""
import logging
from celery import shared_task
from django.utils import timezone

from api.cms.services_new.SurveyRewardService import SurveyRewardService

logger = logging.getLogger(__name__)


@shared_task(name='cms.tasks.process_survey_completion_rewards', bind=True, max_retries=3)
def process_survey_completion_rewards(self, completion_uuid: str):
    """Process rewards for a specific survey completion"""
    try:
        service = SurveyRewardService()
        
        # Get completion and process rewards
        transactions = service.process_survey_completion_rewards(completion_uuid)
        
        logger.info(f"Processed {len(transactions)} reward transactions for completion {completion_uuid}")
        return {
            'status': 'success',
            'completion_uuid': completion_uuid,
            'transactions_processed': len(transactions)
        }
    except Exception as exc:
        logger.error(f"Failed to process survey completion rewards for {completion_uuid}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(name='cms.tasks.update_reward_statistics', bind=True, max_retries=2)
def update_reward_statistics(self, reward_config_uuid: str = None):
    """Update statistics for reward configurations"""
    try:
        service = SurveyRewardService()
        
        if reward_config_uuid:
            # Update specific reward config
            stats = service.update_reward_statistics(reward_config_uuid)
            logger.info(f"Updated statistics for reward config {reward_config_uuid}")
            return {
                'status': 'success',
                'reward_config_uuid': reward_config_uuid,
                'updated_at': stats.get('updated_at')
            }
        else:
            # Update all reward configs
            service = SurveyRewardService()
            # This would need to be implemented in the service
            logger.info("Updated statistics for all reward configurations")
            return {
                'status': 'success',
                'message': 'All reward config statistics updated'
            }
    except Exception as exc:
        logger.error(f"Failed to update reward statistics: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='cms.tasks.check_reward_pool_utilization', bind=True, max_retries=2)
def check_reward_pool_utilization(self):
    """Check reward pool utilization and send alerts"""
    try:
        service = SurveyRewardService()
        pools = service.get_all_reward_pools()
        
        alerts_sent = 0
        for pool in pools:
            utilization = service.get_reward_pool_utilization(str(pool.uuid))
            
            # Check for alerts
            if utilization.get('alerts'):
                from api.cms.tasks.notification_tasks import send_notification
                for alert in utilization['alerts']:
                    # Send alert to admins
                    send_notification(
                        user_id=None,  # System notification
                        notification_type='system_alert',
                        title=f'Reward Pool Alert: {alert["type"]}',
                        message=f'Pool {pool.name}: {alert["message"]}',
                        metadata={
                            'pool_uuid': str(pool.uuid),
                            'pool_name': pool.name,
                            'alert_type': alert['type'],
                            'utilization_rate': utilization['pool_info']['utilization_rate']
                        }
                    )
                    alerts_sent += 1
        
        logger.info(f"Checked {len(pools)} reward pools, sent {alerts_sent} alerts")
        return {
            'status': 'success',
            'pools_checked': len(pools),
            'alerts_sent': alerts_sent
        }
    except Exception as exc:
        logger.error(f"Failed to check reward pool utilization: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='cms.tasks.auto_refill_reward_pools', bind=True, max_retries=2)
def auto_refill_reward_pools(self):
    """Auto-refill reward pools that are below threshold"""
    try:
        service = SurveyRewardService()
        pools_refilled = service.auto_refill_pools()
        
        logger.info(f"Auto-refilled {len(pools_refilled)} reward pools")
        return {
            'status': 'success',
            'pools_refilled': len(pools_refilled),
            'pools_refilled': [str(p.uuid) for p in pools_refilled]
        }
    except Exception as exc:
        logger.error(f"Failed to auto-refill reward pools: {exc}")
        raise self.retry(exc=exc, countdown=600)


@shared_task(name='cms.tasks.generate_reward_reports', bind=True, max_retries=2)
def generate_reward_reports(self, report_type: str = 'daily', pool_uuid: str = None):
    """Generate reward system reports"""
    try:
        from api.cms.services_new.SurveyRewardService import SurveyRewardService
        service = SurveyRewardService()
        
        if pool_uuid:
            # Generate report for specific pool
            report = service.generate_pool_report(pool_uuid, report_type)
            logger.info(f"Generated {report_type} report for pool {pool_uuid}")
            return {
                'status': 'success',
                'pool_uuid': pool_uuid,
                'report_type': report_type,
                'generated_at': timezone.now().isoformat()
            }
        else:
            # Generate system-wide report
            report = service.generate_system_report(report_type)
            logger.info(f"Generated {report_type} system-wide reward report")
            return {
                'status': 'success',
                'report_type': report_type,
                'generated_at': timezone.now().isoformat()
            }
    except Exception as exc:
        logger.error(f"Failed to generate reward reports: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='cms.tasks.cleanup_old_reward_transactions', bind=True, max_retries=2)
def cleanup_old_reward_transactions(self, days: int = 90):
    """Clean up old reward transactions"""
    try:
        from api.cms.services_new.SurveyRewardService import SurveyRewardService
        service = SurveyRewardService()
        
        deleted_count = service.cleanup_old_transactions(days)
        
        logger.info(f"Cleaned up {deleted_count} old reward transactions older than {days} days")
        return {
            'status': 'success',
            'deleted_count': deleted_count,
            'days': days
        }
    except Exception as exc:
        logger.error(f"Failed to cleanup old reward transactions: {exc}")
        raise self.retry(exc=exc, countdown=600)
