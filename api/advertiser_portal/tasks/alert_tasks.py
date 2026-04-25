"""
Alert Tasks

Low balance and budget alerts for advertisers
and system monitoring notifications.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.core.cache import cache

from ..models.billing import AdvertiserWallet
from ..models.campaign import AdCampaign
from ..models.notification import AdvertiserNotification
try:
    from ..services import AdvertiserBillingService
except ImportError:
    AdvertiserBillingService = None
try:
    from ..services import NotificationService
except ImportError:
    NotificationService = None

import logging
logger = logging.getLogger(__name__)


@shared_task(name="advertiser_portal.check_low_balance_alerts")
def check_low_balance_alerts():
    """
    Check for low balance alerts and send notifications.
    
    This task runs every 30 minutes to check wallet balances
    and send low balance alerts.
    """
    try:
        billing_service = AdvertiserBillingService()
        notification_service = NotificationService()
        
        # Get all active wallets
        active_wallets = AdvertiserWallet.objects.filter(
            is_active=True,
            is_suspended=False
        ).select_related('advertiser')
        
        alerts_sent = 0
        
        for wallet in active_wallets:
            try:
                # Get current balance
                balance_info = billing_service.get_wallet_balance(wallet.advertiser)
                available_balance = balance_info.get('available_balance', 0)
                
                # Check low balance threshold (20% of credit limit)
                if wallet.credit_limit > 0:
                    low_balance_threshold = wallet.credit_limit * 0.2
                    
                    if available_balance <= low_balance_threshold and available_balance > 0:
                        # Check if alert was recently sent (avoid spam)
                        if _should_send_balance_alert(wallet, 'low_balance'):
                            # Send low balance alert
                            notification_data = {
                                'advertiser': wallet.advertiser,
                                'type': 'low_balance',
                                'title': 'Low Balance Alert',
                                'message': f'Your wallet balance is low: ${available_balance:.2f}. Consider adding funds to avoid campaign interruption.',
                                'data': {
                                    'available_balance': available_balance,
                                    'credit_limit': wallet.credit_limit,
                                    'threshold': low_balance_threshold,
                                    'percentage': (available_balance / wallet.credit_limit * 100),
                                }
                            }
                            
                            notification_service.send_notification(notification_data)
                            alerts_sent += 1
                            
                            # Record alert sent
                            _record_alert_sent(wallet, 'low_balance')
                            
                            logger.info(f"Low balance alert sent to advertiser {wallet.advertiser.id}: ${available_balance:.2f}")
                
                # Check zero balance
                if available_balance <= 0:
                    # Check if alert was recently sent
                    if _should_send_balance_alert(wallet, 'zero_balance'):
                        # Send zero balance alert
                        notification_data = {
                            'advertiser': wallet.advertiser,
                            'type': 'zero_balance',
                            'title': 'Zero Balance Alert',
                            'message': f'Your wallet balance is zero. All campaigns have been paused. Please add funds immediately.',
                            'data': {
                                'available_balance': available_balance,
                                'credit_limit': wallet.credit_limit,
                            }
                        }
                        
                        notification_service.send_notification(notification_data)
                        alerts_sent += 1
                        
                        # Record alert sent
                        _record_alert_sent(wallet, 'zero_balance')
                        
                        logger.info(f"Zero balance alert sent to advertiser {wallet.advertiser.id}")
                
            except Exception as e:
                logger.error(f"Error checking balance alerts for wallet {wallet.id}: {e}")
                continue
        
        logger.info(f"Low balance alerts completed: {alerts_sent} alerts sent")
        
        return {
            'wallets_checked': active_wallets.count(),
            'alerts_sent': alerts_sent,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in low balance alerts task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.check_budget_alerts")
def check_budget_alerts():
    """
    Check for budget alerts and send notifications.
    
    This task runs every hour to check campaign budgets
    and send budget alerts.
    """
    try:
        billing_service = AdvertiserBillingService()
        notification_service = NotificationService()
        
        # Get all active campaigns with budget alerts enabled
        alert_campaigns = AdCampaign.objects.filter(
            status='active',
            budget_alert_enabled=True
        ).select_related('advertiser')
        
        alerts_sent = 0
        
        for campaign in alert_campaigns:
            try:
                # Get current spend
                current_spend = billing_service.get_campaign_spend(campaign)
                
                # Check budget alert threshold
                if campaign.budget_alert_threshold and campaign.budget_limit:
                    alert_percentage = (current_spend / campaign.budget_limit * 100) if campaign.budget_limit > 0 else 0
                    
                    if alert_percentage >= campaign.budget_alert_threshold:
                        # Check if alert was recently sent
                        if _should_send_budget_alert(campaign):
                            # Send budget alert
                            notification_data = {
                                'advertiser': campaign.advertiser,
                                'type': 'budget_alert',
                                'title': 'Campaign Budget Alert',
                                'message': f'Campaign "{campaign.name}" has reached {alert_percentage:.1f}% of its budget limit.',
                                'data': {
                                    'campaign_id': campaign.id,
                                    'campaign_name': campaign.name,
                                    'current_spend': current_spend,
                                    'budget_limit': campaign.budget_limit,
                                    'percentage': alert_percentage,
                                }
                            }
                            
                            notification_service.send_notification(notification_data)
                            alerts_sent += 1
                            
                            # Record alert sent
                            _record_budget_alert_sent(campaign)
                            
                            logger.info(f"Budget alert sent for campaign {campaign.id}: {alert_percentage:.1f}%")
                
                # Check time-based alerts
                if campaign.budget_alert_time_based and campaign.end_date:
                    days_remaining = (campaign.end_date.date() - timezone.now().date()).days
                    
                    if days_remaining <= campaign.budget_alert_days:
                        # Check if alert was recently sent
                        if _should_send_time_alert(campaign):
                            # Send time-based alert
                            notification_data = {
                                'advertiser': campaign.advertiser,
                                'type': 'time_based_alert',
                                'title': 'Campaign Time Alert',
                                'message': f'Campaign "{campaign.name}" has {days_remaining} days remaining.',
                                'data': {
                                    'campaign_id': campaign.id,
                                    'campaign_name': campaign.name,
                                    'days_remaining': days_remaining,
                                    'end_date': campaign.end_date.isoformat(),
                                }
                            }
                            
                            notification_service.send_notification(notification_data)
                            alerts_sent += 1
                            
                            # Record alert sent
                            _record_time_alert_sent(campaign)
                            
                            logger.info(f"Time-based alert sent for campaign {campaign.id}: {days_remaining} days remaining")
                
            except Exception as e:
                logger.error(f"Error checking budget alerts for campaign {campaign.id}: {e}")
                continue
        
        logger.info(f"Budget alerts completed: {alerts_sent} alerts sent")
        
        return {
            'campaigns_checked': alert_campaigns.count(),
            'alerts_sent': alerts_sent,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in budget alerts task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.check_performance_alerts")
def check_performance_alerts():
    """
    Check for performance alerts and send notifications.
    
    This task runs every 6 hours to check campaign performance
    and send performance alerts.
    """
    try:
        notification_service = NotificationService()
        
        # Get all active campaigns with performance alerts enabled
        performance_campaigns = AdCampaign.objects.filter(
            status='active',
            performance_alert_enabled=True
        ).select_related('advertiser')
        
        alerts_sent = 0
        
        for campaign in performance_campaigns:
            try:
                # Get performance data for last 24 hours
                performance_data = _get_campaign_performance_data(campaign, hours=24)
                
                if not performance_data:
                    continue
                
                # Check CTR alert
                if campaign.target_ctr and performance_data.get('ctr', 0) < campaign.target_ctr:
                    if _should_send_performance_alert(campaign, 'ctr'):
                        notification_data = {
                            'advertiser': campaign.advertiser,
                            'type': 'performance_alert',
                            'title': 'Low CTR Alert',
                            'message': f'Campaign "{campaign.name}" CTR is below target: {performance_data.get("ctr", 0):.2f}% < {campaign.target_ctr:.2f}%',
                            'data': {
                                'campaign_id': campaign.id,
                                'campaign_name': campaign.name,
                                'metric': 'ctr',
                                'current_value': performance_data.get('ctr', 0),
                                'target_value': campaign.target_ctr,
                            }
                        }
                        
                        notification_service.send_notification(notification_data)
                        alerts_sent += 1
                        _record_performance_alert_sent(campaign, 'ctr')
                
                # Check CPA alert
                if campaign.target_cpa and performance_data.get('cpa', 0) > campaign.target_cpa:
                    if _should_send_performance_alert(campaign, 'cpa'):
                        notification_data = {
                            'advertiser': campaign.advertiser,
                            'type': 'performance_alert',
                            'title': 'High CPA Alert',
                            'message': f'Campaign "{campaign.name}" CPA is above target: ${performance_data.get("cpa", 0):.2f} > ${campaign.target_cpa:.2f}',
                            'data': {
                                'campaign_id': campaign.id,
                                'campaign_name': campaign.name,
                                'metric': 'cpa',
                                'current_value': performance_data.get('cpa', 0),
                                'target_value': campaign.target_cpa,
                            }
                        }
                        
                        notification_service.send_notification(notification_data)
                        alerts_sent += 1
                        _record_performance_alert_sent(campaign, 'cpa')
                
                # Check conversion rate alert
                if campaign.target_conversion_rate and performance_data.get('conversion_rate', 0) < campaign.target_conversion_rate:
                    if _should_send_performance_alert(campaign, 'conversion_rate'):
                        notification_data = {
                            'advertiser': campaign.advertiser,
                            'type': 'performance_alert',
                            'title': 'Low Conversion Rate Alert',
                            'message': f'Campaign "{campaign.name}" conversion rate is below target: {performance_data.get("conversion_rate", 0):.2f}% < {campaign.target_conversion_rate:.2f}%',
                            'data': {
                                'campaign_id': campaign.id,
                                'campaign_name': campaign.name,
                                'metric': 'conversion_rate',
                                'current_value': performance_data.get('conversion_rate', 0),
                                'target_value': campaign.target_conversion_rate,
                            }
                        }
                        
                        notification_service.send_notification(notification_data)
                        alerts_sent += 1
                        _record_performance_alert_sent(campaign, 'conversion_rate')
                
            except Exception as e:
                logger.error(f"Error checking performance alerts for campaign {campaign.id}: {e}")
                continue
        
        logger.info(f"Performance alerts completed: {alerts_sent} alerts sent")
        
        return {
            'campaigns_checked': performance_campaigns.count(),
            'alerts_sent': alerts_sent,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in performance alerts task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.check_system_alerts")
def check_system_alerts():
    """
    Check for system-level alerts and send notifications.
    
    This task runs every hour to check system health
    and send system alerts.
    """
    try:
        notification_service = NotificationService()
        
        alerts_sent = 0
        
        # Check database connection
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception as e:
            if _should_send_system_alert('database'):
                notification_data = {
                    'type': 'system_alert',
                    'title': 'Database Connection Alert',
                    'message': f'Database connection issue detected: {str(e)}',
                    'data': {
                        'component': 'database',
                        'error': str(e),
                        'severity': 'critical',
                    }
                }
                
                notification_service.send_admin_notification(notification_data)
                alerts_sent += 1
                _record_system_alert_sent('database')
        
        # Check cache connectivity
        try:
            cache.set('health_check', 'ok', timeout=60)
            cache.get('health_check')
        except Exception as e:
            if _should_send_system_alert('cache'):
                notification_data = {
                    'type': 'system_alert',
                    'title': 'Cache Connection Alert',
                    'message': f'Cache connection issue detected: {str(e)}',
                    'data': {
                        'component': 'cache',
                        'error': str(e),
                        'severity': 'warning',
                    }
                }
                
                notification_service.send_admin_notification(notification_data)
                alerts_sent += 1
                _record_system_alert_sent('cache')
        
        # Check task queue health
        try:
            # This would check task queue health
            # For now, just log
            pass
        except Exception as e:
            if _should_send_system_alert('task_queue'):
                notification_data = {
                    'type': 'system_alert',
                    'title': 'Task Queue Alert',
                    'message': f'Task queue issue detected: {str(e)}',
                    'data': {
                        'component': 'task_queue',
                        'error': str(e),
                        'severity': 'critical',
                    }
                }
                
                notification_service.send_admin_notification(notification_data)
                alerts_sent += 1
                _record_system_alert_sent('task_queue')
        
        logger.info(f"System alerts completed: {alerts_sent} alerts sent")
        
        return {
            'alerts_sent': alerts_sent,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in system alerts task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.cleanup_alert_history")
def cleanup_alert_history():
    """
    Clean up old alert history to maintain performance.
    
    This task runs weekly to clean up alert history
    older than 30 days.
    """
    try:
        # Clean up notification history older than 30 days
        cutoff_date = timezone.now() - timezone.timedelta(days=30)
        
        notifications_deleted = AdvertiserNotification.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Alert history cleanup completed: {notifications_deleted} notifications deleted")
        
        return {
            'cutoff_date': cutoff_date.isoformat(),
            'notifications_deleted': notifications_deleted,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in alert history cleanup task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def _should_send_balance_alert(wallet, alert_type):
    """Check if balance alert should be sent (avoid spam)."""
    try:
        cache_key = f"balance_alert_{wallet.id}_{alert_type}"
        last_sent = cache.get(cache_key)
        
        if last_sent:
            # Don't send if sent within last 6 hours
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking balance alert cooldown: {e}")
        return True


def _should_send_budget_alert(campaign):
    """Check if budget alert should be sent (avoid spam)."""
    try:
        cache_key = f"budget_alert_{campaign.id}"
        last_sent = cache.get(cache_key)
        
        if last_sent:
            # Don't send if sent within last 12 hours
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking budget alert cooldown: {e}")
        return True


def _should_send_time_alert(campaign):
    """Check if time-based alert should be sent (avoid spam)."""
    try:
        cache_key = f"time_alert_{campaign.id}"
        last_sent = cache.get(cache_key)
        
        if last_sent:
            # Don't send if sent within last 24 hours
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking time alert cooldown: {e}")
        return True


def _should_send_performance_alert(campaign, metric):
    """Check if performance alert should be sent (avoid spam)."""
    try:
        cache_key = f"performance_alert_{campaign.id}_{metric}"
        last_sent = cache.get(cache_key)
        
        if last_sent:
            # Don't send if sent within last 6 hours
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking performance alert cooldown: {e}")
        return True


def _should_send_system_alert(component):
    """Check if system alert should be sent (avoid spam)."""
    try:
        cache_key = f"system_alert_{component}"
        last_sent = cache.get(cache_key)
        
        if last_sent:
            # Don't send if sent within last 30 minutes for critical, 2 hours for warnings
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking system alert cooldown: {e}")
        return True


def _record_alert_sent(wallet, alert_type):
    """Record that balance alert was sent."""
    try:
        cache_key = f"balance_alert_{wallet.id}_{alert_type}"
        cache.set(cache_key, timezone.now(), timeout=21600)  # 6 hours
        
    except Exception as e:
        logger.error(f"Error recording balance alert sent: {e}")


def _record_budget_alert_sent(campaign):
    """Record that budget alert was sent."""
    try:
        cache_key = f"budget_alert_{campaign.id}"
        cache.set(cache_key, timezone.now(), timeout=43200)  # 12 hours
        
    except Exception as e:
        logger.error(f"Error recording budget alert sent: {e}")


def _record_time_alert_sent(campaign):
    """Record that time-based alert was sent."""
    try:
        cache_key = f"time_alert_{campaign.id}"
        cache.set(cache_key, timezone.now(), timeout=86400)  # 24 hours
        
    except Exception as e:
        logger.error(f"Error recording time alert sent: {e}")


def _record_performance_alert_sent(campaign, metric):
    """Record that performance alert was sent."""
    try:
        cache_key = f"performance_alert_{campaign.id}_{metric}"
        cache.set(cache_key, timezone.now(), timeout=21600)  # 6 hours
        
    except Exception as e:
        logger.error(f"Error recording performance alert sent: {e}")


def _record_system_alert_sent(component):
    """Record that system alert was sent."""
    try:
        cache_key = f"system_alert_{component}"
        cache.set(cache_key, timezone.now(), timeout=3600)  # 1 hour
        
    except Exception as e:
        logger.error(f"Error recording system alert sent: {e}")


def _get_campaign_performance_data(campaign, hours=24):
    """Get campaign performance data for the specified period."""
    try:
        # This would implement actual performance data retrieval
        # For now, return placeholder data
        from ..models.reporting import CampaignReport
        
        end_time = timezone.now()
        start_time = end_time - timezone.timedelta(hours=hours)
        
        reports = CampaignReport.objects.filter(
            campaign=campaign,
            date__gte=start_time.date(),
            date__lte=end_time.date()
        ).aggregate(
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            total_spend=Sum('spend_amount')
        )
        
        impressions = reports['total_impressions'] or 0
        clicks = reports['total_clicks'] or 0
        conversions = reports['total_conversions'] or 0
        spend = reports['total_spend'] or 0
        
        # Calculate metrics
        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        cpc = (spend / clicks) if clicks > 0 else 0
        cpa = (spend / conversions) if conversions > 0 else 0
        conversion_rate = (conversions / clicks * 100) if clicks > 0 else 0
        
        return {
            'impressions': impressions,
            'clicks': clicks,
            'conversions': conversions,
            'spend': spend,
            'ctr': ctr,
            'cpc': cpc,
            'cpa': cpa,
            'conversion_rate': conversion_rate,
        }
        
    except Exception as e:
        logger.error(f"Error getting campaign performance data: {e}")
        return None
