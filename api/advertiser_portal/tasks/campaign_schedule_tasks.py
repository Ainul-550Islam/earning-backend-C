"""
Campaign Schedule Tasks

Activate/deactivate campaigns by schedule
and manage campaign lifecycle automatically.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q

from ..models.campaign import AdCampaign
try:
    from ..services import CampaignSchedulerService
except ImportError:
    CampaignSchedulerService = None

import logging
logger = logging.getLogger(__name__)


@shared_task(name="advertiser_portal.activate_scheduled_campaigns")
def activate_scheduled_campaigns():
    """
    Activate campaigns that are scheduled to start.
    
    This task runs every minute to check for campaigns
    that should be activated based on their start date.
    """
    try:
        scheduler_service = CampaignSchedulerService()
        
        # Get campaigns that should be activated
        campaigns_to_activate = AdCampaign.objects.filter(
            status='scheduled',
            start_date__lte=timezone.now()
        ).select_related('advertiser')
        
        campaigns_activated = 0
        
        for campaign in campaigns_to_activate:
            try:
                # Activate campaign
                result = scheduler_service.activate_campaign(campaign)
                
                if result.get('success'):
                    campaigns_activated += 1
                    logger.info(f"Campaign {campaign.id} activated successfully")
                    
                    # Send activation notification
                    _send_campaign_activation_notification(campaign)
                else:
                    logger.error(f"Failed to activate campaign {campaign.id}: {result.get('error', 'Unknown error')}")
                
            except Exception as e:
                logger.error(f"Error activating campaign {campaign.id}: {e}")
                continue
        
        logger.info(f"Scheduled campaign activation completed: {campaigns_activated} campaigns activated")
        
        return {
            'campaigns_checked': campaigns_to_activate.count(),
            'campaigns_activated': campaigns_activated,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in campaign activation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.deactivate_expired_campaigns")
def deactivate_expired_campaigns():
    """
    Deactivate campaigns that have expired.
    
    This task runs every minute to check for campaigns
    that should be deactivated based on their end date.
    """
    try:
        scheduler_service = CampaignSchedulerService()
        
        # Get campaigns that should be deactivated
        campaigns_to_deactivate = AdCampaign.objects.filter(
            status='active',
            end_date__lte=timezone.now()
        ).select_related('advertiser')
        
        campaigns_deactivated = 0
        
        for campaign in campaigns_to_deactivate:
            try:
                # Deactivate campaign
                result = scheduler_service.deactivate_campaign(campaign)
                
                if result.get('success'):
                    campaigns_deactivated += 1
                    logger.info(f"Campaign {campaign.id} deactivated successfully")
                    
                    # Send deactivation notification
                    _send_campaign_deactivation_notification(campaign)
                else:
                    logger.error(f"Failed to deactivate campaign {campaign.id}: {result.get('error', 'Unknown error')}")
                
            except Exception as e:
                logger.error(f"Error deactivating campaign {campaign.id}: {e}")
                continue
        
        logger.info(f"Expired campaign deactivation completed: {campaigns_deactivated} campaigns deactivated")
        
        return {
            'campaigns_checked': campaigns_to_deactivate.count(),
            'campaigns_deactivated': campaigns_deactivated,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in campaign deactivation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.check_campaign_schedules")
def check_campaign_schedules():
    """
    Check all campaign schedules and update status.
    
    This task runs every hour to validate campaign schedules
    and update any that need attention.
    """
    try:
        scheduler_service = CampaignSchedulerService()
        
        # Get all campaigns with schedules
        scheduled_campaigns = AdCampaign.objects.filter(
            Q(status='scheduled') | Q(status='active')
        ).select_related('advertiser')
        
        schedule_issues = 0
        campaigns_checked = scheduled_campaigns.count()
        
        for campaign in scheduled_campaigns:
            try:
                # Check schedule validity
                schedule_check = scheduler_service.validate_campaign_schedule(campaign)
                
                if not schedule_check.get('valid', True):
                    schedule_issues += 1
                    logger.warning(f"Schedule issue for campaign {campaign.id}: {schedule_check.get('issues', [])}")
                    
                    # Send schedule issue notification
                    _send_schedule_issue_notification(campaign, schedule_check.get('issues', []))
                
                # Check if campaign should be in different status
                current_time = timezone.now()
                
                if campaign.status == 'scheduled' and campaign.start_date <= current_time:
                    # Should be active
                    logger.info(f"Campaign {campaign.id} should be active, activating now")
                    activate_scheduled_campaigns.delay()
                
                elif campaign.status == 'active' and campaign.end_date and campaign.end_date <= current_time:
                    # Should be ended
                    logger.info(f"Campaign {campaign.id} should be ended, deactivating now")
                    deactivate_expired_campaigns.delay()
                
                # Check time-based schedules
                if hasattr(campaign, 'schedule_config') and campaign.schedule_config:
                    _check_time_based_schedule(campaign, scheduler_service)
                
            except Exception as e:
                logger.error(f"Error checking schedule for campaign {campaign.id}: {e}")
                continue
        
        logger.info(f"Schedule check completed: {campaigns_checked} campaigns checked, {schedule_issues} issues found")
        
        return {
            'campaigns_checked': campaigns_checked,
            'schedule_issues': schedule_issues,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in campaign schedule check task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.update_campaign_time_based_status")
def update_campaign_time_based_status():
    """
    Update campaign status based on time-based rules.
    
    This task runs every minute to handle time-based
    campaign activation/deactivation rules.
    """
    try:
        scheduler_service = CampaignSchedulerService()
        
        # Get campaigns with time-based schedules
        time_based_campaigns = AdCampaign.objects.filter(
            status__in=['active', 'paused', 'scheduled'],
            schedule_type='time_based'
        ).select_related('advertiser')
        
        status_updates = 0
        
        for campaign in time_based_campaigns:
            try:
                # Check time-based rules
                should_be_active = scheduler_service.check_time_based_rules(campaign)
                
                if should_be_active and campaign.status != 'active':
                    # Should be active
                    result = scheduler_service.activate_campaign(campaign)
                    if result.get('success'):
                        status_updates += 1
                        logger.info(f"Time-based activation for campaign {campaign.id}")
                
                elif not should_be_active and campaign.status == 'active':
                    # Should be paused
                    result = scheduler_service.pause_campaign(campaign)
                    if result.get('success'):
                        status_updates += 1
                        logger.info(f"Time-based pause for campaign {campaign.id}")
                
            except Exception as e:
                logger.error(f"Error updating time-based status for campaign {campaign.id}: {e}")
                continue
        
        logger.info(f"Time-based status update completed: {status_updates} campaigns updated")
        
        return {
            'campaigns_checked': time_based_campaigns.count(),
            'status_updates': status_updates,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in time-based status update task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.cleanup_completed_campaigns")
def cleanup_completed_campaigns():
    """
    Clean up completed campaigns and archive data.
    
    This task runs daily to archive completed campaigns
    and clean up related data.
    """
    try:
        # Get campaigns completed more than 30 days ago
        completed_campaigns = AdCampaign.objects.filter(
            status='completed',
            updated_at__lte=timezone.now() - timezone.timedelta(days=30)
        ).select_related('advertiser')
        
        campaigns_archived = 0
        
        for campaign in completed_campaigns:
            try:
                # Archive campaign data
                _archive_campaign_data(campaign)
                
                # Update campaign status to archived
                campaign.status = 'archived'
                campaign.save()
                
                campaigns_archived += 1
                logger.info(f"Campaign {campaign.id} archived successfully")
                
            except Exception as e:
                logger.error(f"Error archiving campaign {campaign.id}: {e}")
                continue
        
        logger.info(f"Campaign cleanup completed: {campaigns_archived} campaigns archived")
        
        return {
            'campaigns_checked': completed_campaigns.count(),
            'campaigns_archived': campaigns_archived,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in campaign cleanup task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def _send_campaign_activation_notification(campaign):
    """Send campaign activation notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': campaign.advertiser,
            'type': 'campaign_activated',
            'title': 'Campaign Activated',
            'message': f'Your campaign "{campaign.name}" has been activated and is now running.',
            'data': {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'activated_at': timezone.now().isoformat(),
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending campaign activation notification: {e}")


def _send_campaign_deactivation_notification(campaign):
    """Send campaign deactivation notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': campaign.advertiser,
            'type': 'campaign_deactivated',
            'title': 'Campaign Deactivated',
            'message': f'Your campaign "{campaign.name}" has been deactivated as it has reached its end date.',
            'data': {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'deactivated_at': timezone.now().isoformat(),
                'end_date': campaign.end_date.isoformat() if campaign.end_date else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending campaign deactivation notification: {e}")


def _send_schedule_issue_notification(campaign, issues):
    """Send schedule issue notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': campaign.advertiser,
            'type': 'schedule_issue',
            'title': 'Campaign Schedule Issue',
            'message': f'Your campaign "{campaign.name}" has schedule issues that need attention.',
            'data': {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'issues': issues,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending schedule issue notification: {e}")


def _check_time_based_schedule(campaign, scheduler_service):
    """Check time-based schedule for campaign."""
    try:
        if not hasattr(campaign, 'schedule_config') or not campaign.schedule_config:
            return
        
        schedule_config = campaign.schedule_config
        
        # Check if current time matches schedule
        current_time = timezone.now()
        current_hour = current_time.hour
        current_day = current_time.weekday()  # 0 = Monday, 6 = Sunday
        
        # Check day schedule
        if 'days' in schedule_config:
            allowed_days = schedule_config['days']
            if current_day not in allowed_days and campaign.status == 'active':
                # Should be paused
                scheduler_service.pause_campaign(campaign)
                logger.info(f"Paused campaign {campaign.id} due to day schedule")
            elif current_day in allowed_days and campaign.status == 'paused':
                # Check hour schedule
                if 'hours' in schedule_config:
                    allowed_hours = schedule_config['hours']
                    if current_hour in allowed_hours:
                        # Should be active
                        scheduler_service.activate_campaign(campaign)
                        logger.info(f"Activated campaign {campaign.id} due to day/hour schedule")
                else:
                    # Should be active
                    scheduler_service.activate_campaign(campaign)
                    logger.info(f"Activated campaign {campaign.id} due to day schedule")
        
        # Check hour schedule only
        elif 'hours' in schedule_config:
            allowed_hours = schedule_config['hours']
            if current_hour not in allowed_hours and campaign.status == 'active':
                # Should be paused
                scheduler_service.pause_campaign(campaign)
                logger.info(f"Paused campaign {campaign.id} due to hour schedule")
            elif current_hour in allowed_hours and campaign.status == 'paused':
                # Should be active
                scheduler_service.activate_campaign(campaign)
                logger.info(f"Activated campaign {campaign.id} due to hour schedule")
        
    except Exception as e:
        logger.error(f"Error checking time-based schedule for campaign {campaign.id}: {e}")


def _archive_campaign_data(campaign):
    """Archive campaign data before deletion."""
    try:
        # This would implement actual archiving logic
        # For example, move to archive tables or create backup files
        
        logger.info(f"Archiving data for campaign {campaign.id}")
        
        # Archive campaign reports
        from ..models.reporting import CampaignReport
        CampaignReport.objects.filter(campaign=campaign).update(is_archived=True)
        
        # Archive publisher breakdowns
        from ..models.reporting import PublisherBreakdown
        PublisherBreakdown.objects.filter(advertiser=campaign.advertiser).update(is_archived=True)
        
        # Archive conversion quality scores
        from ..models.fraud import ConversionQualityScore
        ConversionQualityScore.objects.filter(advertiser=campaign.advertiser).update(is_archived=True)
        
    except Exception as e:
        logger.error(f"Error archiving campaign data: {e}")
        raise
