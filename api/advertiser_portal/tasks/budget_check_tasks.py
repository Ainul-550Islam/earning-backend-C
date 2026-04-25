"""
Budget Check Tasks

Every 5 minutes check if budget is exhausted
and automatically pause campaigns when needed.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Sum

from ..models.campaign import AdCampaign
from ..models.billing import AdvertiserWallet
try:
    from ..services import BudgetEnforcementService
except ImportError:
    BudgetEnforcementService = None
try:
    from ..services import AdvertiserBillingService
except ImportError:
    AdvertiserBillingService = None

import logging
logger = logging.getLogger(__name__)


@shared_task(name="advertiser_portal.check_campaign_budgets")
def check_campaign_budgets():
    """
    Check all active campaigns for budget exhaustion.
    
    This task runs every 5 minutes to check if any campaigns
    have exhausted their budget and should be paused.
    """
    try:
        budget_service = BudgetEnforcementService()
        billing_service = AdvertiserBillingService()
        
        # Get all active campaigns
        active_campaigns = AdCampaign.objects.filter(
            status='active'
        ).select_related('advertiser', 'advertiser__wallet')
        
        campaigns_paused = 0
        budgets_exhausted = 0
        
        for campaign in active_campaigns:
            try:
                # Get current spend for campaign
                # This would integrate with actual spend tracking
                current_spend = billing_service.get_campaign_spend(campaign)
                
                # Check if budget is exhausted
                if campaign.budget_limit and current_spend >= campaign.budget_limit:
                    logger.info(f"Budget exhausted for campaign {campaign.id}: {current_spend} >= {campaign.budget_limit}")
                    
                    # Pause campaign
                    budget_service.pause_campaign_for_budget(campaign, current_spend)
                    campaigns_paused += 1
                    budgets_exhausted += 1
                    
                # Check if approaching budget limit (90% warning)
                elif campaign.budget_limit and current_spend >= (campaign.budget_limit * 0.9):
                    logger.warning(f"Campaign {campaign.id} approaching budget limit: {current_spend} / {campaign.budget_limit}")
                    
                    # Send budget warning notification
                    _send_budget_warning(campaign, current_spend)
                
                # Check daily budget
                if campaign.daily_budget:
                    daily_spend = billing_service.get_campaign_daily_spend(campaign)
                    
                    if daily_spend >= campaign.daily_budget:
                        logger.info(f"Daily budget exhausted for campaign {campaign.id}: {daily_spend} >= {campaign.daily_budget}")
                        
                        # Pause campaign for daily budget
                        budget_service.pause_campaign_for_daily_budget(campaign, daily_spend)
                        campaigns_paused += 1
                        
                    elif daily_spend >= (campaign.daily_budget * 0.9):
                        logger.warning(f"Campaign {campaign.id} approaching daily budget limit: {daily_spend} / {campaign.daily_budget}")
                        
                        # Send daily budget warning
                        _send_daily_budget_warning(campaign, daily_spend)
                
                # Check wallet balance
                wallet = campaign.advertiser.wallet
                if wallet and wallet.available_balance <= 0:
                    logger.info(f"Wallet exhausted for advertiser {campaign.advertiser.id}: {wallet.available_balance}")
                    
                    # Pause all campaigns for this advertiser
                    advertiser_campaigns = AdCampaign.objects.filter(
                        advertiser=campaign.advertiser,
                        status='active'
                    )
                    
                    for adv_campaign in advertiser_campaigns:
                        budget_service.pause_campaign_for_wallet(adv_campaign, wallet.available_balance)
                        campaigns_paused += 1
                    
                    # Send wallet warning
                    _send_wallet_warning(campaign.advertiser, wallet)
                
            except Exception as e:
                logger.error(f"Error checking budget for campaign {campaign.id}: {e}")
                continue
        
        logger.info(f"Budget check completed: {campaigns_paused} campaigns paused, {budgets_exhausted} budgets exhausted")
        
        return {
            'campaigns_checked': active_campaigns.count(),
            'campaigns_paused': campaigns_paused,
            'budgets_exhausted': budgets_exhausted,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in budget check task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.check_wallet_balances")
def check_wallet_balances():
    """
    Check all advertiser wallets for low balance warnings.
    
    This task runs every 5 minutes to check if any wallets
    have low balance and should send warnings.
    """
    try:
        billing_service = AdvertiserBillingService()
        
        # Get all active wallets
        active_wallets = AdvertiserWallet.objects.filter(
            is_active=True,
            is_suspended=False
        ).select_related('advertiser')
        
        warnings_sent = 0
        wallets_checked = active_wallets.count()
        
        for wallet in active_wallets:
            try:
                # Check low balance warning (20% of credit limit)
                if wallet.credit_limit > 0:
                    low_balance_threshold = wallet.credit_limit * 0.2
                    
                    if wallet.available_balance <= low_balance_threshold and wallet.available_balance > 0:
                        logger.warning(f"Low balance warning for advertiser {wallet.advertiser.id}: {wallet.available_balance} <= {low_balance_threshold}")
                        
                        # Send low balance warning
                        _send_low_balance_warning(wallet)
                        warnings_sent += 1
                
                # Check zero balance
                if wallet.available_balance <= 0:
                    logger.info(f"Zero balance for advertiser {wallet.advertiser.id}: {wallet.available_balance}")
                    
                    # Send zero balance warning
                    _send_zero_balance_warning(wallet)
                    warnings_sent += 1
                
                # Check auto-refill eligibility
                if wallet.auto_refill_enabled and wallet.available_balance <= wallet.auto_refill_threshold:
                    logger.info(f"Auto-refill triggered for advertiser {wallet.advertiser.id}")
                    
                    # Trigger auto-refill
                    _trigger_auto_refill(wallet)
                
            except Exception as e:
                logger.error(f"Error checking wallet {wallet.id}: {e}")
                continue
        
        logger.info(f"Wallet balance check completed: {wallets_checked} wallets checked, {warnings_sent} warnings sent")
        
        return {
            'wallets_checked': wallets_checked,
            'warnings_sent': warnings_sent,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in wallet balance check task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.check_budget_alerts")
def check_budget_alerts():
    """
    Check for budget-related alerts and notifications.
    
    This task runs every 5 minutes to check for various
    budget-related conditions that need attention.
    """
    try:
        billing_service = AdvertiserBillingService()
        
        # Get campaigns with budget alerts
        alert_campaigns = AdCampaign.objects.filter(
            status='active',
            budget_alert_enabled=True
        ).select_related('advertiser')
        
        alerts_generated = 0
        
        for campaign in alert_campaigns:
            try:
                current_spend = billing_service.get_campaign_spend(campaign)
                
                # Check budget alert threshold
                if campaign.budget_alert_threshold:
                    alert_percentage = (current_spend / campaign.budget_limit * 100) if campaign.budget_limit > 0 else 0
                    
                    if alert_percentage >= campaign.budget_alert_threshold:
                        logger.info(f"Budget alert triggered for campaign {campaign.id}: {alert_percentage}% >= {campaign.budget_alert_threshold}%")
                        
                        # Send budget alert
                        _send_budget_alert(campaign, current_spend, alert_percentage)
                        alerts_generated += 1
                
                # Check time-based alerts
                if campaign.budget_alert_time_based:
                    days_remaining = _get_days_remaining(campaign)
                    
                    if days_remaining <= campaign.budget_alert_days:
                        logger.info(f"Time-based budget alert for campaign {campaign.id}: {days_remaining} days remaining")
                        
                        # Send time-based alert
                        _send_time_based_alert(campaign, days_remaining)
                        alerts_generated += 1
                
            except Exception as e:
                logger.error(f"Error checking budget alerts for campaign {campaign.id}: {e}")
                continue
        
        logger.info(f"Budget alerts check completed: {alerts_generated} alerts generated")
        
        return {
            'campaigns_checked': alert_campaigns.count(),
            'alerts_generated': alerts_generated,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in budget alerts check task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


def _send_budget_warning(campaign, current_spend):
    """Send budget warning notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': campaign.advertiser,
            'type': 'budget_warning',
            'title': 'Budget Warning',
            'message': f'Campaign "{campaign.name}" is approaching its budget limit. Current spend: ${current_spend:.2f} / ${campaign.budget_limit:.2f}',
            'data': {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'current_spend': current_spend,
                'budget_limit': campaign.budget_limit,
                'percentage': (current_spend / campaign.budget_limit * 100) if campaign.budget_limit > 0 else 0,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending budget warning: {e}")


def _send_daily_budget_warning(campaign, daily_spend):
    """Send daily budget warning notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': campaign.advertiser,
            'type': 'daily_budget_warning',
            'title': 'Daily Budget Warning',
            'message': f'Campaign "{campaign.name}" is approaching its daily budget limit. Current spend: ${daily_spend:.2f} / ${campaign.daily_budget:.2f}',
            'data': {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'daily_spend': daily_spend,
                'daily_budget': campaign.daily_budget,
                'percentage': (daily_spend / campaign.daily_budget * 100) if campaign.daily_budget > 0 else 0,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending daily budget warning: {e}")


def _send_wallet_warning(advertiser, wallet):
    """Send wallet warning notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': advertiser,
            'type': 'wallet_exhausted',
            'title': 'Wallet Exhausted',
            'message': f'Your wallet balance is exhausted. All campaigns have been paused. Please add funds to resume advertising.',
            'data': {
                'advertiser_id': advertiser.id,
                'wallet_balance': wallet.available_balance,
                'credit_limit': wallet.credit_limit,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending wallet warning: {e}")


def _send_low_balance_warning(wallet):
    """Send low balance warning notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': wallet.advertiser,
            'type': 'low_balance',
            'title': 'Low Balance Warning',
            'message': f'Your wallet balance is low. Current balance: ${wallet.available_balance:.2f}. Consider adding funds to avoid campaign interruption.',
            'data': {
                'advertiser_id': wallet.advertiser.id,
                'wallet_balance': wallet.available_balance,
                'credit_limit': wallet.credit_limit,
                'threshold': wallet.auto_refill_threshold if wallet.auto_refill_enabled else wallet.credit_limit * 0.2,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending low balance warning: {e}")


def _send_zero_balance_warning(wallet):
    """Send zero balance warning notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': wallet.advertiser,
            'type': 'zero_balance',
            'title': 'Zero Balance Alert',
            'message': f'Your wallet balance is zero. All campaigns have been paused. Please add funds immediately.',
            'data': {
                'advertiser_id': wallet.advertiser.id,
                'wallet_balance': wallet.available_balance,
                'credit_limit': wallet.credit_limit,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending zero balance warning: {e}")


def _trigger_auto_refill(wallet):
    """Trigger auto-refill for wallet."""
    try:
        try:
            from ..services import AutoRefillService
        except ImportError:
            AutoRefillService = None
        
        refill_service = AutoRefillService()
        result = refill_service.process_auto_refill(wallet)
        
        if result.get('success'):
            logger.info(f"Auto-refill successful for advertiser {wallet.advertiser.id}: ${result.get('amount', 0):.2f}")
        else:
            logger.error(f"Auto-refill failed for advertiser {wallet.advertiser.id}: {result.get('error', 'Unknown error')}")
        
    except Exception as e:
        logger.error(f"Error triggering auto-refill: {e}")


def _send_budget_alert(campaign, current_spend, percentage):
    """Send budget alert notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': campaign.advertiser,
            'type': 'budget_alert',
            'title': 'Budget Alert',
            'message': f'Campaign "{campaign.name}" has reached {percentage:.1f}% of its budget limit.',
            'data': {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'current_spend': current_spend,
                'budget_limit': campaign.budget_limit,
                'percentage': percentage,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending budget alert: {e}")


def _send_time_based_alert(campaign, days_remaining):
    """Send time-based budget alert notification."""
    try:
        try:
            from ..services import NotificationService
        except ImportError:
            NotificationService = None
        
        notification_service = NotificationService()
        
        notification_data = {
            'advertiser': campaign.advertiser,
            'type': 'time_based_alert',
            'title': 'Campaign Time Alert',
            'message': f'Campaign "{campaign.name}" has {days_remaining} days remaining.',
            'data': {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'days_remaining': days_remaining,
                'end_date': campaign.end_date.isoformat() if campaign.end_date else None,
            }
        }
        
        notification_service.send_notification(notification_data)
        
    except Exception as e:
        logger.error(f"Error sending time-based alert: {e}")


def _get_days_remaining(campaign):
    """Calculate days remaining for campaign."""
    if not campaign.end_date:
        return None
    
    today = timezone.now().date()
    end_date = campaign.end_date.date()
    
    if end_date <= today:
        return 0
    
    return (end_date - today).days
