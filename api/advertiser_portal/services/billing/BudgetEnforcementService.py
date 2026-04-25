"""
Budget Enforcement Service

Service for enforcing budget limits,
including automatic campaign pausing when budgets are exhausted.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.campaign import AdCampaign
from ...models.billing import AdvertiserWallet
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class BudgetEnforcementService:
    """
    Service for enforcing budget limits.
    
    Handles automatic campaign pausing,
    budget monitoring, and enforcement rules.
    """
    
    def __init__(self):
        self.logger = logger
    
    def enforce_daily_budget_limits(self) -> Dict[str, Any]:
        """
        Enforce daily budget limits for all active campaigns.
        
        Returns:
            Dict[str, Any]: Enforcement results
        """
        try:
            now = timezone.now()
            today = now.date()
            
            # Get all active campaigns with daily budgets
            campaigns = AdCampaign.objects.filter(
                status='active',
                budget_daily__isnull=False,
                budget_daily__gt=0
            ).select_related('advertiser')
            
            enforced_count = 0
            skipped_count = 0
            errors = []
            
            for campaign in campaigns:
                try:
                    if self._should_enforce_daily_budget(campaign, today):
                        self._enforce_daily_budget_pause(campaign)
                        enforced_count += 1
                    else:
                        skipped_count += 1
                
                except Exception as e:
                    errors.append({
                        'campaign_id': campaign.id,
                        'campaign_name': campaign.name,
                        'error': str(e)
                    })
            
            return {
                'campaigns_checked': campaigns.count(),
                'enforced_count': enforced_count,
                'skipped_count': skipped_count,
                'errors': errors,
                'date': today.isoformat(),
                'timestamp': now.isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error enforcing daily budget limits: {e}")
            raise ValidationError(f"Failed to enforce daily budget limits: {str(e)}")
    
    def enforce_total_budget_limits(self) -> Dict[str, Any]:
        """
        Enforce total budget limits for all active campaigns.
        
        Returns:
            Dict[str, Any]: Enforcement results
        """
        try:
            now = timezone.now()
            
            # Get all active campaigns with total budgets
            campaigns = AdCampaign.objects.filter(
                status='active',
                budget_total__isnull=False,
                budget_total__gt=0
            ).select_related('advertiser')
            
            enforced_count = 0
            skipped_count = 0
            errors = []
            
            for campaign in campaigns:
                try:
                    if self._should_enforce_total_budget(campaign):
                        self._enforce_total_budget_pause(campaign)
                        enforced_count += 1
                    else:
                        skipped_count += 1
                
                except Exception as e:
                    errors.append({
                        'campaign_id': campaign.id,
                        'campaign_name': campaign.name,
                        'error': str(e)
                    })
            
            return {
                'campaigns_checked': campaigns.count(),
                'enforced_count': enforced_count,
                'skipped_count': skipped_count,
                'errors': errors,
                'timestamp': now.isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error enforcing total budget limits: {e}")
            raise ValidationError(f"Failed to enforce total budget limits: {str(e)}")
    
    def enforce_wallet_balance_limits(self) -> Dict[str, Any]:
        """
        Enforce wallet balance limits for all active campaigns.
        
        Returns:
            Dict[str, Any]: Enforcement results
        """
        try:
            now = timezone.now()
            
            # Get all active campaigns
            campaigns = AdCampaign.objects.filter(status='active').select_related('advertiser')
            
            suspended_count = 0
            skipped_count = 0
            errors = []
            
            for campaign in campaigns:
                try:
                    if self._should_enforce_wallet_balance(campaign):
                        self._enforce_wallet_balance_pause(campaign)
                        suspended_count += 1
                    else:
                        skipped_count += 1
                
                except Exception as e:
                    errors.append({
                        'campaign_id': campaign.id,
                        'campaign_name': campaign.name,
                        'error': str(e)
                    })
            
            return {
                'campaigns_checked': campaigns.count(),
                'suspended_count': suspended_count,
                'skipped_count': skipped_count,
                'errors': errors,
                'timestamp': now.isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error enforcing wallet balance limits: {e}")
            raise ValidationError(f"Failed to enforce wallet balance limits: {str(e)}")
    
    def check_campaign_budget_status(self, campaign: AdCampaign) -> Dict[str, Any]:
        """
        Check budget status for specific campaign.
        
        Args:
            campaign: Campaign instance
            
        Returns:
            Dict[str, Any]: Budget status
        """
        try:
            from ...models.billing import CampaignSpend
            
            now = timezone.now()
            today = now.date()
            
            # Get today's spend
            today_spend = CampaignSpend.objects.filter(
                campaign=campaign,
                date=today
            ).aggregate(
                total_spend=models.Sum('spend_amount')
            )['total_spend'] or 0
            
            # Get total spend
            total_spend = CampaignSpend.objects.filter(
                campaign=campaign
            ).aggregate(
                total_spend=models.Sum('spend_amount')
            )['total_spend'] or 0
            
            # Calculate status
            daily_status = self._calculate_daily_budget_status(campaign, today_spend)
            total_status = self._calculate_total_budget_status(campaign, total_spend)
            wallet_status = self._calculate_wallet_balance_status(campaign)
            
            return {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'daily_budget': {
                    'budget': float(campaign.budget_daily) if campaign.budget_daily else None,
                    'spent': float(today_spend),
                    'remaining': float(campaign.budget_daily - today_spend) if campaign.budget_daily else None,
                    'percentage_used': float((today_spend / campaign.budget_daily * 100) if campaign.budget_daily else 0),
                    'status': daily_status,
                },
                'total_budget': {
                    'budget': float(campaign.budget_total) if campaign.budget_total else None,
                    'spent': float(total_spend),
                    'remaining': float(campaign.budget_total - total_spend) if campaign.budget_total else None,
                    'percentage_used': float((total_spend / campaign.budget_total * 100) if campaign.budget_total else 0),
                    'status': total_status,
                },
                'wallet_balance': wallet_status,
                'overall_status': self._get_overall_budget_status(daily_status, total_status, wallet_status),
                'checked_at': now.isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error checking campaign budget status: {e}")
            raise ValidationError(f"Failed to check campaign budget status: {str(e)}")
    
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
                status = self.check_campaign_budget_status(campaign)
                
                # Check for alerts
                if status['daily_budget']['status'] in ['warning', 'exhausted']:
                    alerts.append({
                        'campaign': campaign,
                        'type': 'daily_budget',
                        'severity': 'high' if status['daily_budget']['status'] == 'exhausted' else 'medium',
                        'message': f"Daily budget {status['daily_budget']['status']}: {status['daily_budget']['percentage_used']:.1f}% used",
                        'percentage_used': status['daily_budget']['percentage_used'],
                    })
                
                if status['total_budget']['status'] in ['warning', 'exhausted']:
                    alerts.append({
                        'campaign': campaign,
                        'type': 'total_budget',
                        'severity': 'high' if status['total_budget']['status'] == 'exhausted' else 'medium',
                        'message': f"Total budget {status['total_budget']['status']}: {status['total_budget']['percentage_used']:.1f}% used",
                        'percentage_used': status['total_budget']['percentage_used'],
                    })
                
                if status['wallet_balance']['status'] == 'insufficient':
                    alerts.append({
                        'campaign': campaign,
                        'type': 'wallet_balance',
                        'severity': 'high',
                        'message': "Insufficient wallet balance",
                        'available_balance': status['wallet_balance']['available_balance'],
                    })
            
            # Sort by severity
            alerts.sort(key=lambda x: (x['severity'] != 'high', x['percentage_used']), reverse=True)
            
            return alerts
            
        except Exception as e:
            self.logger.error(f"Error getting budget alerts: {e}")
            return []
    
    def create_budget_enforcement_rule(self, advertiser, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create budget enforcement rule.
        
        Args:
            advertiser: Advertiser instance
            rule_data: Rule configuration
            
        Returns:
            Dict[str, Any]: Created rule
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # This would create a budget enforcement rule model
                # For now, store in advertiser metadata
                metadata = advertiser.profile.metadata or {}
                
                if 'budget_rules' not in metadata:
                    metadata['budget_rules'] = []
                
                rule = {
                    'id': f"rule_{timezone.now().timestamp()}",
                    'name': rule_data.get('name', 'Unnamed Rule'),
                    'type': rule_data.get('type', 'daily_budget'),
                    'threshold': rule_data.get('threshold', 90),
                    'action': rule_data.get('action', 'pause'),
                    'created_at': timezone.now().isoformat(),
                    'is_active': rule_data.get('is_active', True),
                }
                
                metadata['budget_rules'].append(rule)
                advertiser.profile.metadata = metadata
                advertiser.profile.save()
                
                self.logger.info(f"Created budget enforcement rule: {rule['name']} for {advertiser.company_name}")
                return rule
                
        except Exception as e:
            self.logger.error(f"Error creating budget enforcement rule: {e}")
            raise ValidationError(f"Failed to create budget enforcement rule: {str(e)}")
    
    def _should_enforce_daily_budget(self, campaign: AdCampaign, today) -> bool:
        """Check if daily budget should be enforced."""
        if not campaign.budget_daily or campaign.budget_daily <= 0:
            return False
        
        # Check if campaign was already paused today for budget
        if campaign.notes and 'Auto-paused: Daily budget exhausted' in campaign.notes:
            return False
        
        return True
    
    def _should_enforce_total_budget(self, campaign: AdCampaign) -> bool:
        """Check if total budget should be enforced."""
        if not campaign.budget_total or campaign.budget_total <= 0:
            return False
        
        # Check if campaign was already paused for total budget
        if campaign.notes and 'Auto-paused: Total budget exhausted' in campaign.notes:
            return False
        
        return True
    
    def _should_enforce_wallet_balance(self, campaign: AdCampaign) -> bool:
        """Check if wallet balance should be enforced."""
        try:
            wallet = AdvertiserWallet.objects.get(advertiser=campaign.advertiser)
            
            # Check if campaign was already paused for wallet balance
            if campaign.notes and 'Auto-paused: Insufficient balance' in campaign.notes:
                return False
            
            return wallet.available_balance <= 0
            
        except AdvertiserWallet.DoesNotExist:
            return False
    
    def _enforce_daily_budget_pause(self, campaign: AdCampaign):
        """Enforce daily budget pause."""
        campaign.status = 'paused'
        campaign.notes = f"Auto-paused: Daily budget exhausted\n{campaign.notes or ''}"
        campaign.save()
        
        # Send notification
        self._send_budget_pause_notification(campaign, 'daily_budget')
        
        self.logger.info(f"Auto-paused campaign due to daily budget: {campaign.name}")
    
    def _enforce_total_budget_pause(self, campaign: AdCampaign):
        """Enforce total budget pause."""
        campaign.status = 'paused'
        campaign.notes = f"Auto-paused: Total budget exhausted\n{campaign.notes or ''}"
        campaign.save()
        
        # Send notification
        self._send_budget_pause_notification(campaign, 'total_budget')
        
        self.logger.info(f"Auto-paused campaign due to total budget: {campaign.name}")
    
    def _enforce_wallet_balance_pause(self, campaign: AdCampaign):
        """Enforce wallet balance pause."""
        campaign.status = 'paused'
        campaign.notes = f"Auto-paused: Insufficient balance\n{campaign.notes or ''}"
        campaign.save()
        
        # Send notification
        self._send_budget_pause_notification(campaign, 'wallet_balance')
        
        self.logger.info(f"Auto-paused campaign due to insufficient balance: {campaign.name}")
    
    def _calculate_daily_budget_status(self, campaign: AdCampaign, today_spend: float) -> str:
        """Calculate daily budget status."""
        if not campaign.budget_daily or campaign.budget_daily <= 0:
            return 'no_limit'
        
        percentage = (today_spend / campaign.budget_daily) * 100
        
        if percentage >= 100:
            return 'exhausted'
        elif percentage >= 90:
            return 'warning'
        elif percentage >= 75:
            return 'caution'
        else:
            return 'healthy'
    
    def _calculate_total_budget_status(self, campaign: AdCampaign, total_spend: float) -> str:
        """Calculate total budget status."""
        if not campaign.budget_total or campaign.budget_total <= 0:
            return 'no_limit'
        
        percentage = (total_spend / campaign.budget_total) * 100
        
        if percentage >= 100:
            return 'exhausted'
        elif percentage >= 90:
            return 'warning'
        elif percentage >= 75:
            return 'caution'
        else:
            return 'healthy'
    
    def _calculate_wallet_balance_status(self, campaign: AdCampaign) -> Dict[str, Any]:
        """Calculate wallet balance status."""
        try:
            wallet = AdvertiserWallet.objects.get(advertiser=campaign.advertiser)
            
            if wallet.available_balance <= 0:
                return {
                    'status': 'insufficient',
                    'available_balance': float(wallet.available_balance),
                    'credit_limit': float(wallet.credit_limit),
                }
            else:
                return {
                    'status': 'sufficient',
                    'available_balance': float(wallet.available_balance),
                    'credit_limit': float(wallet.credit_limit),
                }
                
        except AdvertiserWallet.DoesNotExist:
            return {
                'status': 'no_wallet',
                'available_balance': 0.00,
                'credit_limit': 0.00,
            }
    
    def _get_overall_budget_status(self, daily_status: str, total_status: str, wallet_status: Dict[str, Any]) -> str:
        """Get overall budget status."""
        if daily_status == 'exhausted' or total_status == 'exhausted' or wallet_status['status'] == 'insufficient':
            return 'critical'
        elif daily_status == 'warning' or total_status == 'warning':
            return 'warning'
        elif daily_status == 'caution' or total_status == 'caution':
            return 'caution'
        else:
            return 'healthy'
    
    def _send_budget_pause_notification(self, campaign: AdCampaign, reason: str):
        """Send budget pause notification."""
        messages = {
            'daily_budget': 'Your campaign has been automatically paused because the daily budget has been exhausted.',
            'total_budget': 'Your campaign has been automatically paused because the total budget has been exhausted.',
            'wallet_balance': 'Your campaign has been automatically paused due to insufficient wallet balance.',
        }
        
        AdvertiserNotification.objects.create(
            advertiser=campaign.advertiser,
            type='budget_reached',
            title=_('Campaign Auto-Paused'),
            message=messages.get(reason, 'Your campaign has been automatically paused.'),
            priority='high',
            action_url=f'/advertiser/campaigns/{campaign.id}/',
            action_text=_('View Campaign')
        )
