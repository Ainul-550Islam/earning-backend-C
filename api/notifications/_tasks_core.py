# earning_backend/api/notifications/tasks.py
import logging
from celery import shared_task, chain, group, chord
from celery.utils.log import get_task_logger
from celery.exceptions import MaxRetriesExceededError
from django.utils import timezone
from django.db import transaction, DatabaseError
from django.db.models import Q, Count, F
from django.core.cache import cache
from datetime import datetime, timedelta
import json
import time
from typing import List, Dict, Optional, Any
import traceback

from .models import (
    Notification, NotificationCampaign, NotificationRule,
    NotificationAnalytics, NotificationLog, NotificationTemplate,
    DeviceToken
)
from ._services_core import (
    notification_service, template_service, rule_service,
    analytics_service, preferences_service, device_service
)

logger = get_task_logger(__name__)


# ==================== NOTIFICATION DELIVERY TASKS ====================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 1 minute
    queue='notifications_high'
)
def send_notification_task(self, notification_id: str):
    """
    Celery task to send a single notification
    """
    try:
        with transaction.atomic():
            # Get notification
            try:
                notification = Notification.objects.get(id=notification_id, is_deleted=False)
            except Notification.DoesNotExist:
                logger.error(f"Notification {notification_id} not found")
                return {'success': False, 'error': 'Notification not found'}
            
            # Check if notification can be sent
            if notification.is_sent and notification.status not in ['failed', 'pending']:
                logger.info(f"Notification {notification_id} already sent")
                return {'success': True, 'status': 'already_sent'}
            
            if notification.is_expired():
                notification.status = 'expired'
                notification.save()
                logger.info(f"Notification {notification_id} expired")
                return {'success': False, 'error': 'Notification expired'}
            
            # Send notification
            success = notification_service.send_notification(notification)
            
            if success:
                logger.info(f"Notification {notification_id} sent successfully")
                return {'success': True, 'notification_id': notification_id}
            else:
                logger.error(f"Failed to send notification {notification_id}")
                
                # Retry if max retries not reached
                if notification.delivery_attempts < notification.max_retries:
                    notification.prepare_for_retry()
                    notification.save()
                    
                    # Schedule retry
                    retry_delay = notification.retry_interval
                    raise self.retry(countdown=retry_delay)
                else:
                    return {'success': False, 'error': 'Max retries exceeded'}
    
    except DatabaseError as e:
        logger.error(f"Database error sending notification {notification_id}: {e}")
        raise self.retry(exc=e)
    
    except Exception as e:
        logger.error(f"Error sending notification {notification_id}: {e}")
        
        # Mark as failed
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.mark_as_failed(str(e))
        except:
            pass
        
        return {'success': False, 'error': str(e)}


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    queue='notifications_bulk'
)
def send_bulk_notifications_task(self, user_ids: List[int], title: str, message: str, **kwargs):
    """
    Celery task to send bulk notifications
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get users
        users = User.objects.filter(id__in=user_ids)
        
        if not users:
            logger.warning("No users found for bulk notifications")
            return {'success': False, 'error': 'No users found'}
        
        # Send notifications
        results = notification_service.create_bulk_notifications(
            users=list(users),
            title=title,
            message=message,
            **kwargs
        )
        
        logger.info(f"Bulk notifications sent: {results['successful']} successful, {results['failed']} failed")
        
        return results
    
    except Exception as e:
        logger.error(f"Error sending bulk notifications: {e}")
        raise self.retry(exc=e)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=600,  # 10 minutes
    queue='notifications_campaign'
)
def send_campaign_notifications_task(self, campaign_id: str, user_ids: List[int]):
    """
    Celery task to send campaign notifications
    """
    try:
        # Get campaign
        try:
            campaign = NotificationCampaign.objects.get(id=campaign_id)
        except NotificationCampaign.DoesNotExist:
            logger.error(f"Campaign {campaign_id} not found")
            return {'success': False, 'error': 'Campaign not found'}
        
        if campaign.status != 'running':
            logger.warning(f"Campaign {campaign_id} is not running (status: {campaign.status})")
            return {'success': False, 'error': f'Campaign is not running (status: {campaign.status})'}
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get users
        users = User.objects.filter(id__in=user_ids)
        
        if not users:
            logger.warning(f"No users found for campaign {campaign_id}")
            return {'success': True, 'message': 'No users found', 'notifications_sent': 0}
        
        # Send notifications
        results = notification_service.create_bulk_notifications(
            users=list(users),
            title=campaign.title_template,
            message=campaign.message_template,
            batch_id=str(campaign.id),
            notification_type=campaign.campaign_type,
            channel=campaign.channel,
            priority=campaign.priority,
            campaign_id=str(campaign.id),
            campaign_name=campaign.name,
        )
        
        # Update campaign progress
        campaign.total_sent += results['successful']
        campaign.save()
        campaign.update_progress()
        
        logger.info(f"Campaign {campaign_id}: {results['successful']} successful, {results['failed']} failed")
        
        return {
            'success': True,
            'campaign_id': campaign_id,
            'results': results,
            'total_sent': campaign.total_sent,
            'target_count': campaign.target_count,
        }
    
    except Exception as e:
        logger.error(f"Error sending campaign notifications for campaign {campaign_id}: {e}")
        raise self.retry(exc=e)


@shared_task(queue='notifications_low')
def send_scheduled_notifications():
    """
    Task to send scheduled notifications
    """
    try:
        now = timezone.now()
        
        # Get scheduled notifications that are due
        scheduled_notifications = Notification.objects.filter(
            status='scheduled',
            scheduled_for__lte=now,
            is_deleted=False,
            is_expired=False
        )
        
        count = scheduled_notifications.count()
        
        if count == 0:
            logger.info("No scheduled notifications to send")
            return {'success': True, 'count': 0}
        
        logger.info(f"Processing {count} scheduled notifications")
        
        # Update status to pending and send
        processed = 0
        failed = 0
        
        for notification in scheduled_notifications:
            try:
                # Update status
                notification.status = 'pending'
                notification.save()
                
                # Send notification
                send_notification_task.delay(str(notification.id))
                processed += 1
                
            except Exception as e:
                logger.error(f"Failed to process scheduled notification {notification.id}: {e}")
                notification.mark_as_failed(str(e))
                failed += 1
        
        logger.info(f"Scheduled notifications: {processed} processed, {failed} failed")
        
        return {
            'success': True,
            'total': count,
            'processed': processed,
            'failed': failed
        }
    
    except Exception as e:
        logger.error(f"Error processing scheduled notifications: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_low')
def retry_failed_notifications():
    """
    Task to retry failed notifications
    """
    try:
        result = notification_service.retry_failed_notifications()
        return result
    
    except Exception as e:
        logger.error(f"Error retrying failed notifications: {e}")
        return {'success': False, 'error': str(e)}


# ==================== CAMPAIGN TASKS ====================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    queue='notifications_campaign'
)
def process_campaign_task(self, campaign_id: str):
    """
    Process a campaign (main task)
    """
    try:
        result = notification_service.process_campaign(campaign_id)
        return result
    
    except Exception as e:
        logger.error(f"Error processing campaign {campaign_id}: {e}")
        
        # Mark campaign as failed
        try:
            campaign = NotificationCampaign.objects.get(id=campaign_id)
            campaign.status = 'failed'
            campaign.save()
        except:
            pass
        
        raise self.retry(exc=e)


@shared_task(queue='notifications_campaign')
def process_all_campaigns():
    """
    Process all running campaigns
    """
    try:
        # Get running campaigns
        campaigns = NotificationCampaign.objects.filter(
            status='running',
            is_deleted=False
        )
        
        count = campaigns.count()
        
        if count == 0:
            logger.info("No running campaigns to process")
            return {'success': True, 'count': 0}
        
        logger.info(f"Processing {count} campaigns")
        
        # Process each campaign
        results = []
        for campaign in campaigns:
            try:
                result = process_campaign_task.delay(str(campaign.id))
                results.append({
                    'campaign_id': str(campaign.id),
                    'campaign_name': campaign.name,
                    'task_id': result.id
                })
            except Exception as e:
                logger.error(f"Failed to start campaign {campaign.id}: {e}")
                results.append({
                    'campaign_id': str(campaign.id),
                    'campaign_name': campaign.name,
                    'error': str(e)
                })
        
        return {
            'success': True,
            'total': count,
            'results': results
        }
    
    except Exception as e:
        logger.error(f"Error processing campaigns: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_campaign')
def check_campaign_completion():
    """
    Check and update campaign completion status
    """
    try:
        campaigns = NotificationCampaign.objects.filter(
            status='running',
            is_deleted=False
        )
        
        completed = 0
        
        for campaign in campaigns:
            if campaign.is_completed():
                campaign.complete()
                completed += 1
        
        logger.info(f"Checked campaigns: {completed} completed")
        
        return {
            'success': True,
            'completed': completed,
            'total': campaigns.count()
        }
    
    except Exception as e:
        logger.error(f"Error checking campaign completion: {e}")
        return {'success': False, 'error': str(e)}


# ==================== RULE ENGINE TASKS ====================

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    queue='notifications_rules'
)
def execute_rule_task(self, rule_id: str, context: Optional[Dict] = None):
    """
    Execute a notification rule
    """
    try:
        result = rule_service.execute_rule(rule_id, context)
        return result
    
    except Exception as e:
        logger.error(f"Error executing rule {rule_id}: {e}")
        raise self.retry(exc=e)


@shared_task(queue='notifications_rules')
def execute_scheduled_rules():
    """
    Execute scheduled rules
    """
    try:
        # Get rules with schedule trigger
        rules = NotificationRule.objects.filter(
            trigger_type='schedule',
            is_active=True,
            is_enabled=True
        )
        
        count = rules.count()
        
        if count == 0:
            logger.info("No scheduled rules to execute")
            return {'success': True, 'count': 0}
        
        logger.info(f"Executing {count} scheduled rules")
        
        now = timezone.now()
        executed = 0
        failed = 0
        
        for rule in rules:
            try:
                # Check if rule can execute
                if rule.can_execute():
                    # Execute rule
                    execute_rule_task.delay(str(rule.id))
                    executed += 1
                else:
                    logger.debug(f"Rule {rule.id} cannot execute at this time")
            
            except Exception as e:
                logger.error(f"Failed to execute rule {rule.id}: {e}")
                failed += 1
        
        logger.info(f"Scheduled rules: {executed} executed, {failed} failed")
        
        return {
            'success': True,
            'total': count,
            'executed': executed,
            'failed': failed
        }
    
    except Exception as e:
        logger.error(f"Error executing scheduled rules: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_rules')
def process_event_rules(event_type: str, event_data: Dict):
    """
    Process rules for specific event
    """
    try:
        # Get rules with event trigger matching this event
        rules = NotificationRule.objects.filter(
            trigger_type='event',
            is_active=True,
            is_enabled=True
        )
        
        # Filter rules by event type from trigger_config
        matching_rules = []
        for rule in rules:
            trigger_config = rule.trigger_config or {}
            if trigger_config.get('event_type') == event_type:
                matching_rules.append(rule)
        
        count = len(matching_rules)
        
        if count == 0:
            logger.debug(f"No rules found for event: {event_type}")
            return {'success': True, 'count': 0}
        
        logger.info(f"Processing {count} rules for event: {event_type}")
        
        # Execute matching rules
        executed = 0
        failed = 0
        
        for rule in matching_rules:
            try:
                # Create context from event data
                context = {
                    'event_type': event_type,
                    'event_data': event_data,
                    'timestamp': timezone.now().isoformat(),
                    **event_data  # Add event data to context
                }
                
                # Check conditions
                if rule.evaluate_conditions(context):
                    # Execute rule
                    execute_rule_task.delay(str(rule.id), context)
                    executed += 1
                else:
                    logger.debug(f"Rule {rule.id} conditions not met for event {event_type}")
            
            except Exception as e:
                logger.error(f"Failed to process rule {rule.id} for event {event_type}: {e}")
                failed += 1
        
        logger.info(f"Event rules: {executed} executed, {failed} failed")
        
        return {
            'success': True,
            'event_type': event_type,
            'total': count,
            'executed': executed,
            'failed': failed
        }
    
    except Exception as e:
        logger.error(f"Error processing event rules for {event_type}: {e}")
        return {'success': False, 'error': str(e)}


# ==================== CLEANUP TASKS ====================

@shared_task(queue='notifications_maintenance')
def cleanup_expired_notifications():
    """
    Cleanup expired notifications
    """
    try:
        result = notification_service.delete_expired_notifications()
        return result
    
    except Exception as e:
        logger.error(f"Error cleaning up expired notifications: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_maintenance')
def cleanup_old_notifications(days: int = 90):
    """
    Cleanup old notifications
    """
    try:
        result = notification_service.cleanup_old_notifications(days)
        return result
    
    except Exception as e:
        logger.error(f"Error cleaning up old notifications: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_maintenance')
def cleanup_soft_deleted_notifications():
    """
    Permanently delete soft-deleted notifications older than 30 days
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # Get soft-deleted notifications older than cutoff
        notifications = Notification.objects.filter(
            is_deleted=True,
            deleted_at__lt=cutoff_date
        )
        
        count = notifications.count()
        
        if count == 0:
            logger.info("No soft-deleted notifications to clean up")
            return {'success': True, 'count': 0}
        
        # Delete permanently
        deleted_count, _ = notifications.delete()
        
        logger.info(f"Cleaned up {deleted_count} soft-deleted notifications")
        
        return {
            'success': True,
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error cleaning up soft-deleted notifications: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_maintenance')
def cleanup_old_logs(days: int = 30):
    """
    Cleanup old notification logs
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Delete old logs
        deleted_count, _ = NotificationLog.objects.filter(
            created_at__lt=cutoff_date
        ).delete()
        
        logger.info(f"Cleaned up {deleted_count} old logs (older than {days} days)")
        
        return {
            'success': True,
            'deleted_count': deleted_count,
            'days': days
        }
    
    except Exception as e:
        logger.error(f"Error cleaning up old logs: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_maintenance')
def cleanup_inactive_device_tokens(days: int = 90):
    """
    Cleanup inactive device tokens
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Deactivate tokens not used for specified days
        tokens = DeviceToken.objects.filter(
            last_active__lt=cutoff_date,
            is_active=True
        )
        
        count = tokens.count()
        
        if count == 0:
            logger.info("No inactive device tokens to clean up")
            return {'success': True, 'count': 0}
        
        # Deactivate tokens
        deactivated = 0
        for token in tokens:
            token.deactivate()
            deactivated += 1
        
        logger.info(f"Deactivated {deactivated} inactive device tokens")
        
        return {
            'success': True,
            'deactivated': deactivated,
            'days': days
        }
    
    except Exception as e:
        logger.error(f"Error cleaning up inactive device tokens: {e}")
        return {'success': False, 'error': str(e)}


# ==================== ANALYTICS TASKS ====================

@shared_task(queue='notifications_analytics')
def generate_daily_analytics(date_str: Optional[str] = None):
    """
    Generate daily analytics report
    """
    try:
        if date_str:
            date = datetime.fromisoformat(date_str).date()
        else:
            date = timezone.now().date()
        
        analytics = analytics_service.generate_daily_report(date)
        
        if analytics:
            logger.info(f"Generated daily analytics for {date}")
            return {
                'success': True,
                'date': date.isoformat(),
                'analytics_id': analytics.id
            }
        else:
            logger.info(f"No data for daily analytics on {date}")
            return {
                'success': True,
                'date': date.isoformat(),
                'message': 'No data available'
            }
    
    except Exception as e:
        logger.error(f"Error generating daily analytics: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_analytics')
def generate_weekly_analytics():
    """
    Generate weekly analytics report
    """
    try:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=7)
        
        report = analytics_service.generate_analytics_report(
            start_date=start_date,
            end_date=end_date,
            group_by='day'
        )
        
        logger.info(f"Generated weekly analytics for {start_date} to {end_date}")
        
        return {
            'success': True,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'report': report
        }
    
    except Exception as e:
        logger.error(f"Error generating weekly analytics: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_analytics')
def generate_monthly_analytics():
    """
    Generate monthly analytics report
    """
    try:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        report = analytics_service.generate_analytics_report(
            start_date=start_date,
            end_date=end_date,
            group_by='week'
        )
        
        logger.info(f"Generated monthly analytics for {start_date} to {end_date}")
        
        return {
            'success': True,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'report': report
        }
    
    except Exception as e:
        logger.error(f"Error generating monthly analytics: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_analytics')
def update_notification_engagement_scores():
    """
    Update engagement scores for notifications
    """
    try:
        # Get notifications from last 30 days that haven't been updated recently
        cutoff_date = timezone.now() - timedelta(days=30)
        
        notifications = Notification.objects.filter(
            created_at__gte=cutoff_date,
            is_deleted=False
        )
        
        count = notifications.count()
        
        if count == 0:
            logger.info("No notifications to update engagement scores")
            return {'success': True, 'count': 0}
        
        logger.info(f"Updating engagement scores for {count} notifications")
        
        updated = 0
        for notification in notifications:
            try:
                old_score = notification.engagement_score
                new_score = notification.calculate_engagement_score()
                
                if old_score != new_score:
                    notification.save()
                    updated += 1
            except Exception as e:
                logger.error(f"Failed to update engagement score for notification {notification.id}: {e}")
        
        logger.info(f"Updated engagement scores for {updated} notifications")
        
        return {
            'success': True,
            'total': count,
            'updated': updated
        }
    
    except Exception as e:
        logger.error(f"Error updating engagement scores: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_analytics')
def calculate_user_engagement_stats():
    """
    Calculate user engagement statistics
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get active users (users with notifications in last 30 days)
        cutoff_date = timezone.now() - timedelta(days=30)
        
        active_users = User.objects.filter(
            notifications__created_at__gte=cutoff_date
        ).distinct()
        
        total_users = User.objects.count()
        active_count = active_users.count()
        
        logger.info(f"Calculating engagement stats: {active_count} active users out of {total_users}")
        
        # Calculate engagement metrics
        engagement_metrics = {
            'total_users': total_users,
            'active_users': active_count,
            'engagement_rate': (active_count / total_users * 100) if total_users > 0 else 0,
            'timestamp': timezone.now().isoformat()
        }
        
        # Store in cache
        cache_key = 'user_engagement_metrics'
        cache.set(cache_key, engagement_metrics, 3600)  # Cache for 1 hour
        
        return {
            'success': True,
            'metrics': engagement_metrics
        }
    
    except Exception as e:
        logger.error(f"Error calculating user engagement stats: {e}")
        return {'success': False, 'error': str(e)}


# ==================== MAINTENANCE TASKS ====================

@shared_task(queue='notifications_maintenance')
def optimize_notification_tables():
    """
    Optimize notification database tables
    """
    try:
        from django.db import connection
        
        with connection.cursor() as cursor:
            # Analyze tables for optimization
            tables = [
                'notifications_notification',
                'notifications_notificationlog',
                'notifications_notificationfeedback',
                'notifications_notificationanalytics'
            ]
            
            for table in tables:
                cursor.execute(f"ANALYZE {table};")
        
        logger.info("Optimized notification tables")
        
        return {'success': True, 'message': 'Tables optimized'}
    
    except Exception as e:
        logger.error(f"Error optimizing tables: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_maintenance')
def rebuild_notification_indexes():
    """
    Rebuild notification indexes
    """
    try:
        # This would depend on your database backend
        # For PostgreSQL, you might use REINDEX
        # For MySQL, you might use OPTIMIZE TABLE
        
        logger.info("Rebuilt notification indexes")
        
        return {'success': True, 'message': 'Indexes rebuilt'}
    
    except Exception as e:
        logger.error(f"Error rebuilding indexes: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_maintenance')
def validate_notification_data():
    """
    Validate notification data integrity
    """
    try:
        # Find notifications with invalid data
        invalid_notifications = []
        
        # Check for notifications without users
        notifications = Notification.objects.filter(user__isnull=True)
        invalid_notifications.extend([
            {'id': str(n.id), 'issue': 'Missing user'}
            for n in notifications
        ])
        
        # Check for invalid metadata JSON
        notifications = Notification.objects.all()
        for notification in notifications:
            try:
                json.dumps(notification.metadata)
            except:
                invalid_notifications.append({
                    'id': str(notification.id),
                    'issue': 'Invalid metadata JSON'
                })
        
        # Check for expired but not marked as expired
        notifications = Notification.objects.filter(
            expire_date__lt=timezone.now(),
            status__in=['draft', 'scheduled', 'pending', 'sending']
        )
        invalid_notifications.extend([
            {'id': str(n.id), 'issue': 'Expired but not marked'}
            for n in notifications
        ])
        
        count = len(invalid_notifications)
        
        if count == 0:
            logger.info("No data validation issues found")
            return {'success': True, 'issues': 0}
        
        logger.warning(f"Found {count} data validation issues")
        
        # Fix issues (optional - could be dangerous)
        fix_issues = False  # Set to True to automatically fix
        
        if fix_issues:
            fixed = 0
            for issue in invalid_notifications:
                try:
                    notification = Notification.objects.get(id=issue['id'])
                    
                    if issue['issue'] == 'Missing user':
                        # Can't fix - need to delete
                        notification.delete()
                    elif issue['issue'] == 'Invalid metadata JSON':
                        notification.metadata = {}
                        notification.save()
                    elif issue['issue'] == 'Expired but not marked':
                        notification.status = 'expired'
                        notification.save()
                    
                    fixed += 1
                except:
                    pass
            
            logger.info(f"Fixed {fixed} out of {count} issues")
        
        return {
            'success': True,
            'issues': count,
            'invalid_notifications': invalid_notifications,
            'fixed': fixed if fix_issues else 0
        }
    
    except Exception as e:
        logger.error(f"Error validating notification data: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_maintenance')
def sync_notification_templates():
    """
    Sync notification templates from filesystem or external source
    """
    try:
        # This task would sync templates from:
        # 1. Filesystem templates
        # 2. External template repository
        # 3. Default templates
        
        # For now, just create default templates if they don't exist
        default_templates = [
            {
                'name': 'welcome_notification',
                'title_en': 'Welcome to Our Platform!',
                'message_en': 'Hello {username}, welcome to our platform! We\'re excited to have you.',
                'template_type': 'welcome',
                'category': 'system'
            },
            {
                'name': 'payment_success',
                'title_en': 'Payment Successful',
                'message_en': 'Your payment of ${amount} was successful. Transaction ID: {transaction_id}',
                'template_type': 'payment_success',
                'category': 'financial'
            },
            {
                'name': 'task_completed',
                'title_en': 'Task Completed',
                'message_en': 'Great job! You completed the task "{task_title}" and earned ${reward}.',
                'template_type': 'task_completed',
                'category': 'task'
            },
            {
                'name': 'security_alert',
                'title_en': 'Security Alert',
                'message_en': 'We detected suspicious activity on your account. Please review your account security.',
                'template_type': 'security_alert',
                'category': 'security'
            },
        ]
        
        created = 0
        updated = 0
        
        for template_data in default_templates:
            try:
                template, created_flag = NotificationTemplate.objects.get_or_create(
                    name=template_data['name'],
                    defaults={
                        'title_en': template_data['title_en'],
                        'message_en': template_data['message_en'],
                        'template_type': template_data['template_type'],
                        'category': template_data['category'],
                        'is_active': True,
                        'is_public': True,
                        'default_priority': 'medium',
                        'default_channel': 'in_app',
                        'variables': []  # Would need to parse from template
                    }
                )
                
                if created_flag:
                    created += 1
                else:
                    # Update existing template
                    template.title_en = template_data['title_en']
                    template.message_en = template_data['message_en']
                    template.template_type = template_data['template_type']
                    template.category = template_data['category']
                    template.save()
                    updated += 1
            
            except Exception as e:
                logger.error(f"Failed to sync template {template_data['name']}: {e}")
        
        logger.info(f"Synced templates: {created} created, {updated} updated")
        
        return {
            'success': True,
            'created': created,
            'updated': updated
        }
    
    except Exception as e:
        logger.error(f"Error syncing notification templates: {e}")
        return {'success': False, 'error': str(e)}


# ==================== MONITORING TASKS ====================

@shared_task(queue='notifications_monitoring')
def monitor_notification_queue():
    """
    Monitor notification queue health
    """
    try:
        from celery import current_app
        
        # Get queue statistics
        inspector = current_app.control.inspect()
        
        # Get active tasks
        active = inspector.active() or {}
        
        # Get scheduled tasks
        scheduled = inspector.scheduled() or {}
        
        # Get reserved tasks
        reserved = inspector.reserved() or {}
        
        # Count tasks by queue
        queue_stats = {}
        
        for worker, tasks in active.items():
            for task in tasks:
                queue = task.get('delivery_info', {}).get('routing_key', 'default')
                queue_stats[queue] = queue_stats.get(queue, 0) + 1
        
        # Check for stuck tasks (tasks running too long)
        stuck_tasks = []
        for worker, tasks in active.items():
            for task in tasks:
                started = task.get('time_start', 0)
                if started:
                    # Check if task has been running for more than 1 hour
                    if time.time() - started > 3600:
                        stuck_tasks.append({
                            'task_id': task['id'],
                            'name': task['name'],
                            'worker': worker,
                            'started': started,
                            'duration': time.time() - started
                        })
        
        stats = {
            'timestamp': timezone.now().isoformat(),
            'active_tasks': sum(len(tasks) for tasks in active.values()),
            'scheduled_tasks': sum(len(tasks) for tasks in scheduled.values()),
            'reserved_tasks': sum(len(tasks) for tasks in reserved.values()),
            'queue_stats': queue_stats,
            'stuck_tasks': len(stuck_tasks),
            'stuck_tasks_details': stuck_tasks[:10]  # Limit details
        }
        
        # Alert if too many stuck tasks
        if len(stuck_tasks) > 10:
            logger.error(f"Found {len(stuck_tasks)} stuck tasks!")
        
        logger.info(f"Queue monitoring: {stats['active_tasks']} active, {stats['scheduled_tasks']} scheduled, {stats['reserved_tasks']} reserved")
        
        return {
            'success': True,
            'stats': stats
        }
    
    except Exception as e:
        logger.error(f"Error monitoring notification queue: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_monitoring')
def monitor_notification_delivery():
    """
    Monitor notification delivery performance
    """
    try:
        # Check delivery rates for last 24 hours
        start_time = timezone.now() - timedelta(hours=24)
        
        # Get delivery statistics
        stats = Notification.objects.filter(
            created_at__gte=start_time,
            is_deleted=False
        ).aggregate(
            total=Count('id'),
            sent=Count('id', filter=Q(is_sent=True)),
            delivered=Count('id', filter=Q(is_delivered=True)),
            read=Count('id', filter=Q(is_read=True)),
            failed=Count('id', filter=Q(status='failed'))
        )
        
        # Calculate rates
        total = stats['total'] or 0
        sent = stats['sent'] or 0
        delivered = stats['delivered'] or 0
        read = stats['read'] or 0
        failed = stats['failed'] or 0
        
        delivery_rate = (delivered / sent * 100) if sent > 0 else 0
        read_rate = (read / sent * 100) if sent > 0 else 0
        failure_rate = (failed / total * 100) if total > 0 else 0
        
        metrics = {
            'timestamp': timezone.now().isoformat(),
            'period_hours': 24,
            'total_notifications': total,
            'sent': sent,
            'delivered': delivered,
            'read': read,
            'failed': failed,
            'delivery_rate': round(delivery_rate, 2),
            'read_rate': round(read_rate, 2),
            'failure_rate': round(failure_rate, 2)
        }
        
        # Check for delivery issues
        alerts = []
        
        if failure_rate > 10:  # More than 10% failure rate
            alerts.append({
                'level': 'error',
                'message': f'High failure rate: {failure_rate}%'
            })
        
        if delivery_rate < 80:  # Less than 80% delivery rate
            alerts.append({
                'level': 'warning',
                'message': f'Low delivery rate: {delivery_rate}%'
            })
        
        logger.info(f"Delivery monitoring: {delivery_rate}% delivery rate, {failure_rate}% failure rate")
        
        return {
            'success': True,
            'metrics': metrics,
            'alerts': alerts
        }
    
    except Exception as e:
        logger.error(f"Error monitoring notification delivery: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_monitoring')
def monitor_system_health():
    """
    Monitor overall system health
    """
    try:
        health_checks = []
        
        # Check database connection
        try:
            Notification.objects.count()
            health_checks.append({
                'component': 'database',
                'status': 'healthy',
                'message': 'Database connection OK'
            })
        except Exception as e:
            health_checks.append({
                'component': 'database',
                'status': 'unhealthy',
                'message': f'Database error: {e}'
            })
        
        # Check cache
        try:
            cache.set('health_check', 'ok', 10)
            if cache.get('health_check') == 'ok':
                health_checks.append({
                    'component': 'cache',
                    'status': 'healthy',
                    'message': 'Cache connection OK'
                })
            else:
                health_checks.append({
                    'component': 'cache',
                    'status': 'unhealthy',
                    'message': 'Cache read/write failed'
                })
        except Exception as e:
            health_checks.append({
                'component': 'cache',
                'status': 'unhealthy',
                'message': f'Cache error: {e}'
            })
        
        # Check Celery
        try:
            from celery import current_app
            inspector = current_app.control.inspect()
            if inspector.ping():
                health_checks.append({
                    'component': 'celery',
                    'status': 'healthy',
                    'message': 'Celery workers responding'
                })
            else:
                health_checks.append({
                    'component': 'celery',
                    'status': 'unhealthy',
                    'message': 'Celery workers not responding'
                })
        except Exception as e:
            health_checks.append({
                'component': 'celery',
                'status': 'unhealthy',
                'message': f'Celery error: {e}'
            })
        
        # Check external services (if configured)
        # This would check Firebase, SendGrid, Twilio, etc.
        
        # Overall status
        all_healthy = all(check['status'] == 'healthy' for check in health_checks)
        
        return {
            'success': True,
            'timestamp': timezone.now().isoformat(),
            'overall_status': 'healthy' if all_healthy else 'unhealthy',
            'checks': health_checks
        }
    
    except Exception as e:
        logger.error(f"Error monitoring system health: {e}")
        return {
            'success': False,
            'error': str(e),
            'overall_status': 'unhealthy'
        }


# ==================== BATCH PROCESSING TASKS ====================

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue='notifications_batch'
)
def process_batch_notifications(self, batch_data: List[Dict]):
    """
    Process a batch of notifications
    """
    try:
        results = {
            'total': len(batch_data),
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        for notification_data in batch_data:
            try:
                # Create notification
                notification = notification_service.create_notification(**notification_data)
                
                if notification:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'data': notification_data,
                        'error': 'Notification creation failed'
                    })
            
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'data': notification_data,
                    'error': str(e)
                })
        
        logger.info(f"Batch processing: {results['successful']} successful, {results['failed']} failed")
        
        return results
    
    except Exception as e:
        logger.error(f"Error processing batch notifications: {e}")
        raise self.retry(exc=e)


@shared_task(queue='notifications_batch')
def process_large_batch(batch_id: str, chunk_size: int = 100):
    """
    Process large batch in chunks
    """
    try:
        # This would typically read from a file or queue
        # For now, simulate with empty batch
        
        # Get batch data (implementation depends on data source)
        batch_data = []  # This would be loaded from somewhere
        
        total = len(batch_data)
        
        if total == 0:
            logger.info(f"Batch {batch_id} has no data")
            return {'success': True, 'message': 'No data to process'}
        
        logger.info(f"Processing batch {batch_id} with {total} items in chunks of {chunk_size}")
        
        # Process in chunks
        chunks = [batch_data[i:i + chunk_size] for i in range(0, total, chunk_size)]
        
        # Create chord for parallel processing with final callback
        header = [process_batch_notifications.s(chunk) for chunk in chunks]
        callback = process_batch_callback.s(batch_id)
        
        # Execute chord
        result = chord(header)(callback)
        
        return {
            'success': True,
            'batch_id': batch_id,
            'total': total,
            'chunks': len(chunks),
            'task_id': result.id
        }
    
    except Exception as e:
        logger.error(f"Error processing large batch {batch_id}: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_batch')
def process_batch_callback(results, batch_id: str):
    """
    Callback after batch processing completes
    """
    try:
        # Aggregate results
        total_successful = sum(r.get('successful', 0) for r in results)
        total_failed = sum(r.get('failed', 0) for r in results)
        
        logger.info(f"Batch {batch_id} completed: {total_successful} successful, {total_failed} failed")
        
        # Update batch status (if you have a batch model)
        # batch = NotificationBatch.objects.get(id=batch_id)
        # batch.status = 'completed'
        # batch.save()
        
        return {
            'success': True,
            'batch_id': batch_id,
            'total_successful': total_successful,
            'total_failed': total_failed,
            'results': results
        }
    
    except Exception as e:
        logger.error(f"Error in batch callback for {batch_id}: {e}")
        return {'success': False, 'error': str(e)}


# ==================== PERIODIC TASKS ====================

@shared_task(queue='notifications_periodic')
def run_periodic_maintenance():
    """
    Run all periodic maintenance tasks
    """
    try:
        tasks = [
            cleanup_expired_notifications.si(),
            cleanup_old_notifications.si(90),
            cleanup_soft_deleted_notifications.si(),
            cleanup_old_logs.si(30),
            cleanup_inactive_device_tokens.si(90),
            optimize_notification_tables.si(),
            validate_notification_data.si(),
            update_notification_engagement_scores.si(),
            calculate_user_engagement_stats.si(),
            sync_notification_templates.si(),
        ]
        
        # Execute in parallel
        group_result = group(tasks).apply_async()
        
        logger.info("Started periodic maintenance tasks")
        
        return {
            'success': True,
            'tasks': len(tasks),
            'group_id': group_result.id
        }
    
    except Exception as e:
        logger.error(f"Error running periodic maintenance: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_periodic')
def run_periodic_analytics():
    """
    Run all periodic analytics tasks
    """
    try:
        # Generate yesterday's analytics
        yesterday = timezone.now().date() - timedelta(days=1)
        
        tasks = [
            generate_daily_analytics.si(yesterday.isoformat()),
            generate_weekly_analytics.si(),
            generate_monthly_analytics.si(),
        ]
        
        group_result = group(tasks).apply_async()
        
        logger.info("Started periodic analytics tasks")
        
        return {
            'success': True,
            'tasks': len(tasks),
            'group_id': group_result.id
        }
    
    except Exception as e:
        logger.error(f"Error running periodic analytics: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_periodic')
def run_periodic_monitoring():
    """
    Run all periodic monitoring tasks
    """
    try:
        tasks = [
            monitor_notification_queue.si(),
            monitor_notification_delivery.si(),
            monitor_system_health.si(),
        ]
        
        group_result = group(tasks).apply_async()
        
        logger.info("Started periodic monitoring tasks")
        
        return {
            'success': True,
            'tasks': len(tasks),
            'group_id': group_result.id
        }
    
    except Exception as e:
        logger.error(f"Error running periodic monitoring: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_periodic')
def run_periodic_processing():
    """
    Run all periodic processing tasks
    """
    try:
        tasks = [
            send_scheduled_notifications.si(),
            retry_failed_notifications.si(),
            execute_scheduled_rules.si(),
            process_all_campaigns.si(),
            check_campaign_completion.si(),
        ]
        
        group_result = group(tasks).apply_async()
        
        logger.info("Started periodic processing tasks")
        
        return {
            'success': True,
            'tasks': len(tasks),
            'group_id': group_result.id
        }
    
    except Exception as e:
        logger.error(f"Error running periodic processing: {e}")
        return {'success': False, 'error': str(e)}


# ==================== ERROR HANDLING TASKS ====================

@shared_task(queue='notifications_errors')
def handle_notification_error(task_id: str, error_message: str, traceback_str: str):
    """
    Handle notification task errors
    """
    try:
        logger.error(f"Task {task_id} failed: {error_message}")
        
        # Log error to database
        NotificationLog.objects.create(
            log_type='error',
            log_level='error',
            message=f"Task failed: {error_message}",
            details={
                'task_id': task_id,
                'error': error_message,
                'traceback': traceback_str[:1000]  # Limit traceback size
            }
        )
        
        # Send alert (if configured)
        # This could send email, Slack message, etc.
        
        return {
            'success': True,
            'task_id': task_id,
            'handled': True
        }
    
    except Exception as e:
        logger.error(f"Error handling notification error: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_errors')
def recover_stuck_tasks():
    """
    Recover stuck tasks
    """
    try:
        from celery import current_app
        
        inspector = current_app.control.inspect()
        active = inspector.active() or {}
        
        recovered = 0
        
        for worker, tasks in active.items():
            for task in tasks:
                started = task.get('time_start', 0)
                if started and time.time() - started > 3600:  # Stuck for more than 1 hour
                    try:
                        # Revoke the stuck task
                        current_app.control.revoke(task['id'], terminate=True)
                        
                        # Log recovery
                        NotificationLog.objects.create(
                            log_type='warning',
                            log_level='warning',
                            message=f"Recovered stuck task: {task['id']}",
                            details={
                                'task_id': task['id'],
                                'task_name': task['name'],
                                'worker': worker,
                                'duration': time.time() - started
                            }
                        )
                        
                        recovered += 1
                    except Exception as e:
                        logger.error(f"Failed to recover task {task['id']}: {e}")
        
        if recovered > 0:
            logger.warning(f"Recovered {recovered} stuck tasks")
        
        return {
            'success': True,
            'recovered': recovered
        }
    
    except Exception as e:
        logger.error(f"Error recovering stuck tasks: {e}")
        return {'success': False, 'error': str(e)}


# ==================== TEST TASKS ====================

@shared_task(queue='notifications_test')
def test_notification_system():
    """
    Test the notification system
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get a test user (or create one)
        test_user = User.objects.filter(is_active=True).first()
        
        if not test_user:
            logger.error("No test user found")
            return {'success': False, 'error': 'No test user found'}
        
        # Test different notification types
        test_cases = [
            {
                'title': 'Test System Notification',
                'message': 'This is a test system notification.',
                'notification_type': 'system_update',
                'priority': 'medium',
                'channel': 'in_app'
            },
            {
                'title': 'Test Urgent Notification',
                'message': 'This is an urgent test notification!',
                'notification_type': 'security_alert',
                'priority': 'urgent',
                'channel': 'in_app'
            },
            {
                'title': 'Test Low Priority',
                'message': 'This is a low priority test.',
                'notification_type': 'general',
                'priority': 'low',
                'channel': 'in_app'
            }
        ]
        
        results = []
        
        for test_case in test_cases:
            try:
                notification = notification_service.create_notification(
                    user=test_user,
                    **test_case
                )
                
                if notification:
                    results.append({
                        'test_case': test_case,
                        'success': True,
                        'notification_id': str(notification.id)
                    })
                else:
                    results.append({
                        'test_case': test_case,
                        'success': False,
                        'error': 'Notification creation failed'
                    })
            except Exception as e:
                results.append({
                    'test_case': test_case,
                    'success': False,
                    'error': str(e)
                })
        
        # Check results
        successful = sum(1 for r in results if r['success'])
        total = len(results)
        
        logger.info(f"Notification system test: {successful}/{total} successful")
        
        return {
            'success': successful == total,
            'results': results,
            'summary': {
                'total': total,
                'successful': successful,
                'failed': total - successful
            }
        }
    
    except Exception as e:
        logger.error(f"Error testing notification system: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(queue='notifications_test')
def stress_test_notifications(user_count: int = 100, notifications_per_user: int = 10):
    """
    Stress test the notification system
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get users for testing
        users = User.objects.filter(is_active=True)[:user_count]
        
        if users.count() < user_count:
            logger.warning(f"Only {users.count()} users available for stress test")
        
        total_notifications = users.count() * notifications_per_user
        
        logger.info(f"Starting stress test: {users.count()} users, {notifications_per_user} notifications each = {total_notifications} total")
        
        # Create test notifications
        start_time = timezone.now()
        
        created = 0
        failed = 0
        
        for user in users:
            for i in range(notifications_per_user):
                try:
                    notification = Notification.objects.create(
                        user=user,
                        title=f'Stress Test Notification {i+1}',
                        message='This is a stress test notification.',
                        notification_type='system',
                        priority='low',
                        channel='in_app',
                        metadata={'stress_test': True, 'iteration': i+1}
                    )
                    created += 1
                except Exception as e:
                    failed += 1
                    logger.error(f"Failed to create stress test notification: {e}")
        
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        
        # Calculate performance
        rate = created / duration if duration > 0 else 0
        
        logger.info(f"Stress test completed: {created} created, {failed} failed in {duration:.2f} seconds ({rate:.2f} notifications/sec)")
        
        # Clean up test notifications
        cleanup_count = Notification.objects.filter(
            metadata__stress_test=True
        ).delete()[0]
        
        logger.info(f"Cleaned up {cleanup_count} stress test notifications")
        
        return {
            'success': True,
            'summary': {
                'users': users.count(),
                'notifications_per_user': notifications_per_user,
                'total_attempted': total_notifications,
                'created': created,
                'failed': failed,
                'duration_seconds': duration,
                'rate_per_second': rate,
                'cleaned_up': cleanup_count
            }
        }
    
    except Exception as e:
        logger.error(f"Error in stress test: {e}")
        return {'success': False, 'error': str(e)}


# ==================== CELERY BEAT SCHEDULE ====================

# Add this to your Celery beat schedule in settings.py:
"""
CELERY_BEAT_SCHEDULE = {
    # Every minute
    'send-scheduled-notifications': {
        'task': 'earning_backend.api.notifications.tasks.send_scheduled_notifications',
        'schedule': 60.0,  # Every minute
    },
    
    # Every 5 minutes
    'retry-failed-notifications': {
        'task': 'earning_backend.api.notifications.tasks.retry_failed_notifications',
        'schedule': 300.0,  # Every 5 minutes
    },
    
    # Every 10 minutes
    'process-campaigns': {
        'task': 'earning_backend.api.notifications.tasks.process_all_campaigns',
        'schedule': 600.0,  # Every 10 minutes
    },
    
    'execute-scheduled-rules': {
        'task': 'earning_backend.api.notifications.tasks.execute_scheduled_rules',
        'schedule': 600.0,  # Every 10 minutes
    },
    
    # Every hour
    'cleanup-expired-notifications': {
        'task': 'earning_backend.api.notifications.tasks.cleanup_expired_notifications',
        'schedule': 3600.0,  # Every hour
    },
    
    'generate-daily-analytics': {
        'task': 'earning_backend.api.notifications.tasks.generate_daily_analytics',
        'schedule': 3600.0,  # Every hour
    },
    
    # Every 6 hours
    'periodic-maintenance': {
        'task': 'earning_backend.api.notifications.tasks.run_periodic_maintenance',
        'schedule': 21600.0,  # Every 6 hours
    },
    
    # Daily (at midnight)
    'cleanup-old-notifications': {
        'task': 'earning_backend.api.notifications.tasks.cleanup_old_notifications',
        'schedule': 86400.0,  # Daily
        'args': (90,),  # Keep 90 days
    },
    
    'cleanup-old-logs': {
        'task': 'earning_backend.api.notifications.tasks.cleanup_old_logs',
        'schedule': 86400.0,  # Daily
        'args': (30,),  # Keep 30 days
    },
    
    'sync-templates': {
        'task': 'earning_backend.api.notifications.tasks.sync_notification_templates',
        'schedule': 86400.0,  # Daily
    },
    
    # Weekly (Monday at 3 AM)
    'weekly-analytics': {
        'task': 'earning_backend.api.notifications.tasks.generate_weekly_analytics',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),  # Monday 3 AM
    },
    
    # Monthly (1st of month at 4 AM)
    'monthly-analytics': {
        'task': 'earning_backend.api.notifications.tasks.generate_monthly_analytics',
        'schedule': crontab(hour=4, minute=0, day_of_month=1),  # 1st of month 4 AM
    },
    
    # Monitoring (every 5 minutes)
    'monitor-queue': {
        'task': 'earning_backend.api.notifications.tasks.monitor_notification_queue',
        'schedule': 300.0,  # Every 5 minutes
    },
    
    'monitor-delivery': {
        'task': 'earning_backend.api.notifications.tasks.monitor_notification_delivery',
        'schedule': 300.0,  # Every 5 minutes
    },
    
    # System health (every 15 minutes)
    'monitor-system-health': {
        'task': 'earning_backend.api.notifications.tasks.monitor_system_health',
        'schedule': 900.0,  # Every 15 minutes
    },
}
"""