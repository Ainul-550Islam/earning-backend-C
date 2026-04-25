"""
Campaign Budget Service

Service for managing campaign budgets,
including budget enforcement and auto-pause functionality.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.campaign import AdCampaign
from ...models.billing import CampaignSpend, AdvertiserWallet
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class CampaignBudgetService:
    """
    Service for managing campaign budgets.
    
    Handles budget enforcement, daily limits,
    and auto-pause functionality.
    """
    
    def __init__(self):
        self.logger = logger
    
    def check_daily_budget(self, campaign: AdCampaign) -> Dict[str, Any]:
        """
        Check daily budget status for campaign.
        
        Args:
            campaign: Campaign instance
            
        Returns:
            Dict[str, Any]: Budget status information
        """
        try:
            if not campaign.budget_daily:
                return {
                    'has_daily_budget': False,
                    'status': 'no_limit',
                    'spent_today': 0,
                    'remaining': 0,
                    'percentage_used': 0,
                }
            
            # Get today's spend
            today = timezone.now().date()
            spend_today = CampaignSpend.objects.filter(
                campaign=campaign,
                date=today
            ).aggregate(
                total_spend=models.Sum('spend_amount')
            )['total_spend'] or 0
            
            remaining = campaign.budget_daily - spend_today
            percentage_used = (spend_today / campaign.budget_daily * 100) if campaign.budget_daily > 0 else 0
            
            # Determine status
            if percentage_used >= 100:
                status = 'exhausted'
            elif percentage_used >= 90:
                status = 'warning'
            elif percentage_used >= 75:
                status = 'caution'
            else:
                status = 'healthy'
            
            return {
                'has_daily_budget': True,
                'status': status,
                'spent_today': float(spend_today),
                'remaining': float(remaining),
                'percentage_used': round(percentage_used, 2),
                'budget_daily': float(campaign.budget_daily),
                'date': today.isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error checking daily budget: {e}")
            raise ValidationError(f"Failed to check daily budget: {str(e)}")
    
    def check_total_budget(self, campaign: AdCampaign) -> Dict[str, Any]:
        """
        Check total budget status for campaign.
        
        Args:
            campaign: Campaign instance
            
        Returns:
            Dict[str, Any]: Budget status information
        """
        try:
            if not campaign.budget_total:
                return {
                    'has_total_budget': False,
                    'status': 'no_limit',
                    'total_spent': 0,
                    'remaining': 0,
                    'percentage_used': 0,
                }
            
            # Get total spend
            total_spent = CampaignSpend.objects.filter(
                campaign=campaign
            ).aggregate(
                total_spend=models.Sum('spend_amount')
            )['total_spend'] or 0
            
            remaining = campaign.budget_total - total_spent
            percentage_used = (total_spent / campaign.budget_total * 100) if campaign.budget_total > 0 else 0
            
            # Determine status
            if percentage_used >= 100:
                status = 'exhausted'
            elif percentage_used >= 90:
                status = 'warning'
            elif percentage_used >= 75:
                status = 'caution'
            else:
                status = 'healthy'
            
            return {
                'has_total_budget': True,
                'status': status,
                'total_spent': float(total_spent),
                'remaining': float(remaining),
                'percentage_used': round(percentage_used, 2),
                'budget_total': float(campaign.budget_total),
            }
            
        except Exception as e:
            self.logger.error(f"Error checking total budget: {e}")
            raise ValidationError(f"Failed to check total budget: {str(e)}")
    
    def enforce_daily_budget(self, campaign: AdCampaign) -> bool:
        """
        Enforce daily budget limit and pause if exceeded.
        
        Args:
            campaign: Campaign instance
            
        Returns:
            bool: True if campaign was paused due to budget
        """
        try:
            with transaction.atomic():
                budget_status = self.check_daily_budget(campaign)
                
                if not budget_status['has_daily_budget']:
                    return False
                
                # Pause campaign if daily budget exhausted
                if budget_status['status'] == 'exhausted' and campaign.status == 'active':
                    campaign.status = 'paused'
                    campaign.notes = f"Auto-paused: Daily budget exhausted\n{campaign.notes or ''}"
                    campaign.save()
                    
                    # Send notification
                    self._send_daily_budget_exhausted_notification(campaign, budget_status)
                    
                    self.logger.info(f"Auto-paused campaign due to daily budget: {campaign.name}")
                    return True
                
                # Send warning if approaching limit
                elif budget_status['status'] == 'warning' and campaign.status == 'active':
                    self._send_daily_budget_warning_notification(campaign, budget_status)
                
                return False
                
        except Exception as e:
            self.logger.error(f"Error enforcing daily budget: {e}")
            return False
    
    def enforce_total_budget(self, campaign: AdCampaign) -> bool:
        """
        Enforce total budget limit and pause if exceeded.
        
        Args:
            campaign: Campaign instance
            
        Returns:
            bool: True if campaign was paused due to budget
        """
        try:
            with transaction.atomic():
                budget_status = self.check_total_budget(campaign)
                
                if not budget_status['has_total_budget']:
                    return False
                
                # Pause campaign if total budget exhausted
                if budget_status['status'] == 'exhausted' and campaign.status == 'active':
                    campaign.status = 'paused'
                    campaign.notes = f"Auto-paused: Total budget exhausted\n{campaign.notes or ''}"
                    campaign.save()
                    
                    # Send notification
                    self._send_total_budget_exhausted_notification(campaign, budget_status)
                    
                    self.logger.info(f"Auto-paused campaign due to total budget: {campaign.name}")
                    return True
                
                # Send warning if approaching limit
                elif budget_status['status'] == 'warning' and campaign.status == 'active':
                    self._send_total_budget_warning_notification(campaign, budget_status)
                
                return False
                
        except Exception as e:
            self.logger.error(f"Error enforcing total budget: {e}")
            return False
    
    def check_and_enforce_all_campaigns(self) -> Dict[str, Any]:
        """
        Check and enforce budget limits for all active campaigns.
        
        Returns:
            Dict[str, Any]: Enforcement results
        """
        try:
            active_campaigns = AdCampaign.objects.filter(status='active')
            
            daily_budget_paused = 0
            total_budget_paused = 0
            warnings_sent = 0
            
            for campaign in active_campaigns:
                # Check daily budget
                if self.enforce_daily_budget(campaign):
                    daily_budget_paused += 1
                
                # Check total budget
                if self.enforce_total_budget(campaign):
                    total_budget_paused += 1
            
            return {
                'campaigns_checked': active_campaigns.count(),
                'daily_budget_paused': daily_budget_paused,
                'total_budget_paused': total_budget_paused,
                'warnings_sent': warnings_sent,
                'timestamp': timezone.now().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error enforcing budgets for all campaigns: {e}")
            raise ValidationError(f"Failed to enforce budgets: {str(e)}")
    
    def get_budget_alerts(self, advertiser=None) -> List[Dict[str, Any]]:
        """
        Get budget alerts for campaigns.
        
        Args:
            advertiser: Optional advertiser filter
            
        Returns:
            List[Dict[str, Any]]: Budget alerts
        """
        try:
            campaigns = AdCampaign.objects.filter(status='active')
            if advertiser:
                campaigns = campaigns.filter(advertiser=advertiser)
            
            alerts = []
            
            for campaign in campaigns:
                # Check daily budget
                daily_status = self.check_daily_budget(campaign)
                if daily_status['status'] in ['warning', 'exhausted']:
                    alerts.append({
                        'campaign': campaign,
                        'type': 'daily_budget',
                        'status': daily_status['status'],
                        'percentage_used': daily_status['percentage_used'],
                        'remaining': daily_status['remaining'],
                        'budget_amount': daily_status['budget_daily'],
                    })
                
                # Check total budget
                total_status = self.check_total_budget(campaign)
                if total_status['status'] in ['warning', 'exhausted']:
                    alerts.append({
                        'campaign': campaign,
                        'type': 'total_budget',
                        'status': total_status['status'],
                        'percentage_used': total_status['percentage_used'],
                        'remaining': total_status['remaining'],
                        'budget_amount': total_status['budget_total'],
                    })
            
            return alerts
            
        except Exception as e:
            self.logger.error(f"Error getting budget alerts: {e}")
            return []
    
    def update_daily_budget(self, campaign: AdCampaign, new_budget: float) -> AdCampaign:
        """
        Update daily budget for campaign.
        
        Args:
            campaign: Campaign instance
            new_budget: New daily budget amount
            
        Returns:
            AdCampaign: Updated campaign instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                if new_budget <= 0:
                    raise ValidationError("Daily budget must be positive")
                
                old_budget = campaign.budget_daily
                campaign.budget_daily = new_budget
                campaign.save()
                
                # Send notification
                if old_budget != new_budget:
                    self._send_budget_updated_notification(campaign, 'daily', old_budget, new_budget)
                
                self.logger.info(f"Updated daily budget for campaign: {campaign.name} - {old_budget} -> {new_budget}")
                return campaign
                
        except Exception as e:
            self.logger.error(f"Error updating daily budget: {e}")
            raise ValidationError(f"Failed to update daily budget: {str(e)}")
    
    def update_total_budget(self, campaign: AdCampaign, new_budget: float) -> AdCampaign:
        """
        Update total budget for campaign.
        
        Args:
            campaign: Campaign instance
            new_budget: New total budget amount
            
        Returns:
            AdCampaign: Updated campaign instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                if new_budget <= 0:
                    raise ValidationError("Total budget must be positive")
                
                old_budget = campaign.budget_total
                campaign.budget_total = new_budget
                campaign.save()
                
                # Send notification
                if old_budget != new_budget:
                    self._send_budget_updated_notification(campaign, 'total', old_budget, new_budget)
                
                self.logger.info(f"Updated total budget for campaign: {campaign.name} - {old_budget} -> {new_budget}")
                return campaign
                
        except Exception as e:
            self.logger.error(f"Error updating total budget: {e}")
            raise ValidationError(f"Failed to update total budget: {str(e)}")
    
    def get_budget_utilization_report(self, advertiser=None, days: int = 30) -> Dict[str, Any]:
        """
        Get budget utilization report.
        
        Args:
            advertiser: Optional advertiser filter
            days: Number of days to analyze
            
        Returns:
            Dict[str, Any]: Budget utilization report
        """
        try:
            from django.db.models import Sum, Avg, Count
            
            start_date = timezone.now().date() - timezone.timedelta(days=days)
            
            campaigns = AdCampaign.objects.filter(
                created_at__date__gte=start_date
            )
            if advertiser:
                campaigns = campaigns.filter(advertiser=advertiser)
            
            # Get spend data
            spend_data = CampaignSpend.objects.filter(
                campaign__in=campaigns,
                date__gte=start_date
            ).aggregate(
                total_spend=Sum('spend_amount'),
                avg_daily_spend=Avg('spend_amount'),
                total_campaigns=Count('campaign', distinct=True),
                total_days=Count('date', distinct=True)
            )
            
            # Get budget data
            budget_data = campaigns.aggregate(
                total_daily_budget=Sum('budget_daily'),
                total_total_budget=Sum('budget_total')
            )
            
            # Calculate utilization
            total_daily_budget = budget_data['total_daily_budget'] or 0
            total_total_budget = budget_data['total_total_budget'] or 0
            total_spend = spend_data['total_spend'] or 0
            
            daily_utilization = (total_spend / (total_daily_budget * days) * 100) if total_daily_budget > 0 else 0
            total_utilization = (total_spend / total_total_budget * 100) if total_total_budget > 0 else 0
            
            return {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': timezone.now().date().isoformat(),
                    'days': days,
                },
                'spending': {
                    'total_spend': float(total_spend),
                    'avg_daily_spend': float(spend_data['avg_daily_spend'] or 0),
                },
                'budgets': {
                    'total_daily_budget': float(total_daily_budget),
                    'total_total_budget': float(total_total_budget),
                },
                'utilization': {
                    'daily_utilization': round(daily_utilization, 2),
                    'total_utilization': round(total_utilization, 2),
                },
                'campaigns': {
                    'total_campaigns': spend_data['total_campaigns'] or 0,
                    'active_campaigns': campaigns.filter(status='active').count(),
                },
                'generated_at': timezone.now().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error generating budget utilization report: {e}")
            raise ValidationError(f"Failed to generate report: {str(e)}")
    
    def _send_daily_budget_exhausted_notification(self, campaign: AdCampaign, budget_status: Dict[str, Any]):
        """Send daily budget exhausted notification."""
        AdvertiserNotification.objects.create(
            advertiser=campaign.advertiser,
            type='budget_reached',
            title=_('Daily Budget Exhausted'),
            message=_(
                'Your campaign "{campaign_name}" has exhausted its daily budget of ${budget:.2f}. '
                'The campaign has been automatically paused.'
            ).format(
                campaign_name=campaign.name,
                budget=budget_status['budget_daily']
            ),
            priority='high',
            action_url=f'/advertiser/campaigns/{campaign.id}/budget/',
            action_text=_('Adjust Budget')
        )
    
    def _send_total_budget_exhausted_notification(self, campaign: AdCampaign, budget_status: Dict[str, Any]):
        """Send total budget exhausted notification."""
        AdvertiserNotification.objects.create(
            advertiser=campaign.advertiser,
            type='budget_reached',
            title=_('Total Budget Exhausted'),
            message=_(
                'Your campaign "{campaign_name}" has exhausted its total budget of ${budget:.2f}. '
                'The campaign has been automatically paused.'
            ).format(
                campaign_name=campaign.name,
                budget=budget_status['budget_total']
            ),
            priority='high',
            action_url=f'/advertiser/campaigns/{campaign.id}/budget/',
            action_text=_('Adjust Budget')
        )
    
    def _send_daily_budget_warning_notification(self, campaign: AdCampaign, budget_status: Dict[str, Any]):
        """Send daily budget warning notification."""
        AdvertiserNotification.objects.create(
            advertiser=campaign.advertiser,
            type='budget_reached',
            title=_('Daily Budget Warning'),
            message=_(
                'Your campaign "{campaign_name}" has used {percentage:.1f}% of its daily budget. '
                'Consider increasing the budget to avoid interruption.'
            ).format(
                campaign_name=campaign.name,
                percentage=budget_status['percentage_used']
            ),
            priority='medium',
            action_url=f'/advertiser/campaigns/{campaign.id}/budget/',
            action_text=_('View Budget')
        )
    
    def _send_total_budget_warning_notification(self, campaign: AdCampaign, budget_status: Dict[str, Any]):
        """Send total budget warning notification."""
        AdvertiserNotification.objects.create(
            advertiser=campaign.advertiser,
            type='budget_reached',
            title=_('Total Budget Warning'),
            message=_(
                'Your campaign "{campaign_name}" has used {percentage:.1f}% of its total budget. '
                'Consider increasing the budget to avoid interruption.'
            ).format(
                campaign_name=campaign.name,
                percentage=budget_status['percentage_used']
            ),
            priority='medium',
            action_url=f'/advertiser/campaigns/{campaign.id}/budget/',
            action_text=_('View Budget')
        )
    
    def _send_budget_updated_notification(self, campaign: AdCampaign, budget_type: str, old_budget: float, new_budget: float):
        """Send budget updated notification."""
        AdvertiserNotification.objects.create(
            advertiser=campaign.advertiser,
            type='budget_reached',
            title=_('Budget Updated'),
            message=_(
                'Your campaign "{campaign_name}" {budget_type} budget has been updated '
                'from ${old_budget:.2f} to ${new_budget:.2f}.'
            ).format(
                campaign_name=campaign.name,
                budget_type=budget_type,
                old_budget=old_budget,
                new_budget=new_budget
            ),
            priority='low',
            action_url=f'/advertiser/campaigns/{campaign.id}/budget/',
            action_text=_('View Budget')
        )
