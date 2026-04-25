"""
Creative Expiry Tasks

Flag expired creatives and manage creative lifecycle.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q

from ..models.campaign import CampaignCreative
try:
    from ..services import CampaignCreativeService
except ImportError:
    CampaignCreativeService = None

import logging
logger = logging.getLogger(__name__)


@shared_task(name="advertiser_portal.check_creative_expiry")
def check_creative_expiry():
    """
    Check for expired creatives and update their status.
    
    This task runs every hour to check for creatives
    that have expired and update their status.
    """
    try:
        creative_service = CampaignCreativeService()
        
        # Get all active creatives
        active_creatives = CampaignCreative.objects.filter(
            status='active'
        ).select_related('campaign', 'campaign__advertiser')
        
        creatives_expired = 0
        creatives_expiring_soon = 0
        
        current_time = timezone.now()
        
        for creative in active_creatives:
            try:
                # Check if creative has expiry date
                if creative.expiry_date and creative.expiry_date <= current_time:
                    # Creative has expired
                    result = creative_service.expire_creative(creative)
                    
                    if result.get('success'):
                        creatives_expired += 1
                        logger.info(f"Creative {creative.id} expired on {creative.expiry_date}")
                        
                        # Send expiry notification
                        _send_creative_expiry_notification(creative)
                    else:
                        logger.error(f"Failed to expire creative {creative.id}: {result.get('error', 'Unknown error')}")
                
                # Check if creative is expiring soon (within 24 hours)
                elif creative.expiry_date and creative.expiry_date <= current_time + timezone.timedelta(hours=24):
                    # Creative is expiring soon
                    if not creative.expiry_notification_sent:
                        creatives_expiring_soon += 1
                        logger.warning(f"Creative {creative.id} expiring soon on {creative.expiry_date}")
                        
                        # Send expiry warning notification
                        _send_creative_expiry_warning(creative)
                        
                        # Mark notification as sent
                        creative.expiry_notification_sent = True
                        creative.save()
                
                # Check if creative has end date
                if creative.end_date and creative.end_date <= current_time:
                    # Creative has reached end date
                    result = creative_service.deactivate_creative(creative, 'End date reached')
                    
                    if result.get('success'):
                        creatives_expired += 1
                        logger.info(f"Creative {creative.id} deactivated due to end date: {creative.end_date}")
                        
                        # Send deactivation notification
                        _send_creative_deactivation_notification(creative)
                    else:
                        logger.error(f"Failed to deactivate creative {creative.id}: {result.get('error', 'Unknown error')}")
                
                # Check if creative is approaching end date (within 48 hours)
                elif creative.end_date and creative.end_date <= current_time + timezone.timedelta(hours=48):
                    # Creative is approaching end date
                    if not creative.end_date_notification_sent:
                        creatives_expiring_soon += 1
                        logger.warning(f"Creative {creative.id} approaching end date: {creative.end_date}")
                        
                        # Send end date warning notification
                        _send_creative_end_date_warning(creative)
                        
                        # Mark notification as sent
                        creative.end_date_notification_sent = True
                        creative.save()
                
            except Exception as e:
                logger.error(f"Error checking creative expiry for creative {creative.id}: {e}")
                continue
        
        logger.info(f"Creative expiry check completed: {creatives_expired} expired, {creatives_expiring_soon} expiring soon")
        
        return {
            'creatives_checked': active_creatives.count(),
            'creatives_expired': creatives_expired,
            'creatives_expiring_soon': creatives_expiring_soon,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in creative expiry check task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.cleanup_expired_creatives")
def cleanup_expired_creatives():
    """
    Clean up expired creatives and archive old files.
    
    This task runs daily to clean up expired creatives
    and archive their files to save storage space.
    """
    try:
        creative_service = CampaignCreativeService()
        
        # Get creatives expired more than 30 days ago
        cutoff_date = timezone.now() - timezone.timedelta(days=30)
        
        expired_creatives = CampaignCreative.objects.filter(
            status='expired',
            expired_at__lt=cutoff_date
        ).select_related('campaign', 'campaign__advertiser')
        
        creatives_archived = 0
        storage_freed = 0
        
        for creative in expired_creatives:
            try:
                # Archive creative files
                archive_result = creative_service.archive_creative_files(creative)
                
                if archive_result.get('success'):
                    # Update creative status to archived
                    creative.status = 'archived'
                    creative.archived_at = timezone.now()
                    creative.save()
                    
                    creatives_archived += 1
                    storage_freed += archive_result.get('storage_freed', 0)
                    
                    logger.info(f"Creative {creative.id} archived, freed {archive_result.get('storage_freed', 0)} bytes")
                else:
                    logger.error(f"Failed to archive creative {creative.id}: {archive_result.get('error', 'Unknown error')}")
                
            except Exception as e:
                logger.error(f"Error archiving creative {creative.id}: {e}")
                continue
        
        logger.info(f"Creative cleanup completed: {creatives_archived} archived, {storage_freed} bytes freed")
        
        return {
            'cutoff_date': cutoff_date.isoformat(),
            'creatives_archived': creatives_archived,
            'storage_freed': storage_freed,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in creative cleanup task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.update_creative_performance")
def update_creative_performance():
    """
    Update creative performance metrics.
    
    This task runs every 6 hours to update creative
    performance metrics for optimization.
    """
    try:
        creative_service = CampaignCreativeService()
        
        # Get all active creatives
        active_creatives = CampaignCreative.objects.filter(
            status='active'
        ).select_related('campaign')
        
        creatives_updated = 0
        
        for creative in active_creatives:
            try:
                # Get performance data for the last 6 hours
                performance_data = creative_service.get_creative_performance(
                    creative,
                    hours=6
                )
                
                if performance_data:
                    # Update creative performance metrics
                    creative.impressions = performance_data.get('impressions', 0)
                    creative.clicks = performance_data.get('clicks', 0)
                    creative.conversions = performance_data.get('conversions', 0)
                    creative.ctr = performance_data.get('ctr', 0)
                    creative.conversion_rate = performance_data.get('conversion_rate', 0)
                    creative.performance_updated_at = timezone.now()
                    creative.save()
                    
                    creatives_updated += 1
                    logger.info(f"Performance updated for creative {creative.id}")
                
            except Exception as e:
                logger.error(f"Error updating performance for creative {creative.id}: {e}")
                continue
        
        logger.info(f"Creative performance update completed: {creatives_updated} creatives updated")
        
        return {
            'creatives_checked': active_creatives.count(),
            'creatives_updated': creatives_updated,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in creative performance update task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.check_creative_compliance")
def check_creative_compliance():
    """
    Check creative compliance with platform policies.
    
    This task runs daily to check if creatives
    comply with platform policies and guidelines.
    """
    try:
        creative_service = CampaignCreativeService()
        
        # Get all active and pending creatives
        creatives_to_check = CampaignCreative.objects.filter(
            status__in=['active', 'pending']
        ).select_related('campaign', 'campaign__advertiser')
        
        creatives_checked = 0
        creatives_flagged = 0
        
        for creative in creatives_to_check:
            try:
                # Check compliance
                compliance_result = creative_service.check_creative_compliance(creative)
                
                if not compliance_result.get('compliant', True):
                    # Flag creative for compliance issues
                    creative.status = 'flagged'
                    creative.compliance_issues = compliance_result.get('issues', [])
                    creative.flagged_at = timezone.now()
                    creative.save()
                    
                    creatives_flagged += 1
                    logger.warning(f"Creative {creative.id} flagged for compliance: {compliance_result.get('issues', [])}")
                    
                    # Send compliance notification
                    _send_compliance_notification(creative, compliance_result.get('issues', []))
                else:
                    # Mark as compliant
                    creative.is_compliant = True
                    creative.compliance_checked_at = timezone.now()
                    creative.save()
                
                creatives_checked += 1
                
            except Exception as e:
                logger.error(f"Error checking compliance for creative {creative.id}: {e}")
                continue
        
        logger.info(f"Creative compliance check completed: {creatives_checked} checked, {creatives_flagged} flagged")
        
        return {
            'creatives_checked': creatives_checked,
            'creatives_flagged': creatives_flagged,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in creative compliance check task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.generate_creative_reports")
def generate_creative_reports():
    """
    Generate creative performance reports.
    
    This task runs weekly to generate comprehensive
    creative performance reports.
    """
    try:
        # Get last week's date range
        end_date = timezone.now().date()
        start_date = end_date - timezone.timedelta(days=7)
        
        # Get all creatives with activity in the last week
        active_creatives = CampaignCreative.objects.filter(
            Q(performance_updated_at__date__gte=start_date) |
            Q(created_at__date__gte=start_date)
        ).select_related('campaign', 'campaign__advertiser')
        
        reports_generated = 0
        
        for creative in active_creatives:
            try:
                # Generate performance report
                report_data = creative_service.generate_creative_report(
                    creative,
                    start_date,
                    end_date
                )
                
                # Store report
                from ..models.reporting import CreativeReport
                report = CreativeReport.objects.create(
                    creative=creative,
                    report_date=end_date,
                    data=report_data,
                    generated_at=timezone.now()
                )
                
                reports_generated += 1
                logger.info(f"Creative report generated for creative {creative.id}")
                
            except Exception as e:
                logger.error(f"Error generating report for creative {creative.id}: {e}")
                continue
        
        logger.info(f"Creative report generation completed: {reports_generated} reports generated")
        
        return {
            'period': f"{start_date.isoformat()} to {end_date.isoformat()}",
            'reports_generated': reports_generated,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in creative report generation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def _send_creative_expiry_notification(creative):
    """Send creative expiry notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': creative.campaign.advertiser,
            'type': 'creative_expired',
            'title': 'Creative Expired',
            'message': f'Your creative "{creative.name}" has expired and been deactivated.',
            'data': {
                'creative_id': creative.id,
                'creative_name': creative.name,
                'campaign_name': creative.campaign.name,
                'expiry_date': creative.expiry_date.isoformat() if creative.expiry_date else None,
                'expired_at': creative.expired_at.isoformat() if creative.expired_at else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending creative expiry notification: {e}")


def _send_creative_expiry_warning(creative):
    """Send creative expiry warning notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': creative.campaign.advertiser,
            'type': 'creative_expiring_soon',
            'title': 'Creative Expiring Soon',
            'message': f'Your creative "{creative.name}" will expire in less than 24 hours.',
            'data': {
                'creative_id': creative.id,
                'creative_name': creative.name,
                'campaign_name': creative.campaign.name,
                'expiry_date': creative.expiry_date.isoformat() if creative.expiry_date else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending creative expiry warning notification: {e}")


def _send_creative_deactivation_notification(creative):
    """Send creative deactivation notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': creative.campaign.advertiser,
            'type': 'creative_deactivated',
            'title': 'Creative Deactivated',
            'message': f'Your creative "{creative.name}" has been deactivated due to end date.',
            'data': {
                'creative_id': creative.id,
                'creative_name': creative.name,
                'campaign_name': creative.campaign.name,
                'end_date': creative.end_date.isoformat() if creative.end_date else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending creative deactivation notification: {e}")


def _send_creative_end_date_warning(creative):
    """Send creative end date warning notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': creative.campaign.advertiser,
            'type': 'creative_end_date_approaching',
            'title': 'Creative End Date Approaching',
            'message': f'Your creative "{creative.name}" will reach its end date in less than 48 hours.',
            'data': {
                'creative_id': creative.id,
                'creative_name': creative.name,
                'campaign_name': creative.campaign.name,
                'end_date': creative.end_date.isoformat() if creative.end_date else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending creative end date warning notification: {e}")


def _send_compliance_notification(creative, issues):
    """Send compliance notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': creative.campaign.advertiser,
            'type': 'creative_compliance_issue',
            'title': 'Creative Compliance Issue',
            'message': f'Your creative "{creative.name}" has compliance issues: {", ".join(issues)}',
            'data': {
                'creative_id': creative.id,
                'creative_name': creative.name,
                'campaign_name': creative.campaign.name,
                'compliance_issues': issues,
                'flagged_at': creative.flagged_at.isoformat() if creative.flagged_at else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending compliance notification: {e}")
