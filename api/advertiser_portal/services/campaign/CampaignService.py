"""
Campaign Service

Comprehensive service for managing advertising campaigns,
including creation, lifecycle management, and optimization.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.campaign import AdCampaign, CampaignCreative, CampaignTargeting, CampaignBid, CampaignSchedule
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class CampaignService:
    """
    Service for managing advertising campaigns.
    
    Handles campaign creation, lifecycle management,
    and campaign optimization workflows.
    """
    
    def __init__(self):
        self.logger = logger
    
    def create_campaign(self, advertiser, data: Dict[str, Any]) -> AdCampaign:
        """
        Create a new advertising campaign.
        
        Args:
            advertiser: Advertiser instance
            data: Campaign creation data
            
        Returns:
            AdCampaign: Created campaign instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Validate advertiser status
                if advertiser.verification_status != 'verified':
                    raise ValidationError("Advertiser must be verified to create campaigns")
                
                if advertiser.status != 'active':
                    raise ValidationError("Advertiser account must be active")
                
                # Create campaign
                campaign = AdCampaign.objects.create(
                    advertiser=advertiser,
                    name=data.get('name'),
                    description=data.get('description', ''),
                    objective=data.get('objective', 'cpa'),
                    status='draft',
                    budget_total=data.get('budget_total'),
                    budget_daily=data.get('budget_daily'),
                    start_date=data.get('start_date'),
                    end_date=data.get('end_date'),
                    timezone=data.get('timezone', 'UTC'),
                    notes=data.get('notes', ''),
                    metadata=data.get('metadata', {})
                )
                
                # Create campaign targeting if provided
                if 'targeting' in data:
                    self._create_campaign_targeting(campaign, data['targeting'])
                
                # Create campaign bid if provided
                if 'bid' in data:
                    self._create_campaign_bid(campaign, data['bid'])
                
                # Create campaign schedule if provided
                if 'schedule' in data:
                    self._create_campaign_schedule(campaign, data['schedule'])
                
                # Send notification
                self._send_campaign_created_notification(advertiser, campaign)
                
                self.logger.info(f"Created campaign: {campaign.name} for {advertiser.company_name}")
                return campaign
                
        except Exception as e:
            self.logger.error(f"Error creating campaign: {e}")
            raise ValidationError(f"Failed to create campaign: {str(e)}")
    
    def update_campaign(self, campaign: AdCampaign, data: Dict[str, Any]) -> AdCampaign:
        """
        Update campaign information.
        
        Args:
            campaign: Campaign instance to update
            data: Update data
            
        Returns:
            AdCampaign: Updated campaign instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Check if campaign can be updated
                if campaign.status == 'ended':
                    raise ValidationError("Cannot update ended campaign")
                
                # Update campaign fields
                allowed_fields = [
                    'name', 'description', 'objective', 'budget_total', 
                    'budget_daily', 'start_date', 'end_date', 'timezone', 'notes'
                ]
                
                for field in allowed_fields:
                    if field in data:
                        setattr(campaign, field, data[field])
                
                campaign.save()
                
                # Update targeting if provided
                if 'targeting' in data:
                    self._update_campaign_targeting(campaign, data['targeting'])
                
                # Update bid if provided
                if 'bid' in data:
                    self._update_campaign_bid(campaign, data['bid'])
                
                # Update schedule if provided
                if 'schedule' in data:
                    self._update_campaign_schedule(campaign, data['schedule'])
                
                self.logger.info(f"Updated campaign: {campaign.name}")
                return campaign
                
        except Exception as e:
            self.logger.error(f"Error updating campaign: {e}")
            raise ValidationError(f"Failed to update campaign: {str(e)}")
    
    def start_campaign(self, campaign: AdCampaign) -> AdCampaign:
        """
        Start a campaign.
        
        Args:
            campaign: Campaign instance to start
            
        Returns:
            AdCampaign: Updated campaign instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Validate campaign can be started
                if campaign.status != 'draft':
                    raise ValidationError("Only draft campaigns can be started")
                
                if not campaign.start_date or campaign.start_date > timezone.now().date():
                    raise ValidationError("Campaign start date must be today or in the past")
                
                # Check advertiser wallet balance
                if not self._check_advertiser_balance(campaign.advertiser, campaign.budget_daily):
                    raise ValidationError("Insufficient balance to start campaign")
                
                # Update campaign status
                campaign.status = 'active'
                campaign.actual_start_date = timezone.now()
                campaign.save()
                
                # Send notification
                self._send_campaign_started_notification(campaign.advertiser, campaign)
                
                self.logger.info(f"Started campaign: {campaign.name}")
                return campaign
                
        except Exception as e:
            self.logger.error(f"Error starting campaign: {e}")
            raise ValidationError(f"Failed to start campaign: {str(e)}")
    
    def pause_campaign(self, campaign: AdCampaign, reason: str = None) -> AdCampaign:
        """
        Pause a campaign.
        
        Args:
            campaign: Campaign instance to pause
            reason: Reason for pausing
            
        Returns:
            AdCampaign: Updated campaign instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                if campaign.status != 'active':
                    raise ValidationError("Only active campaigns can be paused")
                
                # Update campaign status
                campaign.status = 'paused'
                campaign.notes = f"Paused: {reason}\n{campaign.notes or ''}" if reason else campaign.notes
                campaign.save()
                
                # Send notification
                self._send_campaign_paused_notification(campaign.advertiser, campaign, reason)
                
                self.logger.info(f"Paused campaign: {campaign.name}")
                return campaign
                
        except Exception as e:
            self.logger.error(f"Error pausing campaign: {e}")
            raise ValidationError(f"Failed to pause campaign: {str(e)}")
    
    def resume_campaign(self, campaign: AdCampaign) -> AdCampaign:
        """
        Resume a paused campaign.
        
        Args:
            campaign: Campaign instance to resume
            
        Returns:
            AdCampaign: Updated campaign instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                if campaign.status != 'paused':
                    raise ValidationError("Only paused campaigns can be resumed")
                
                # Check if campaign should still be running
                now = timezone.now()
                if campaign.end_date and now.date() > campaign.end_date:
                    raise ValidationError("Cannot resume campaign past end date")
                
                # Check advertiser balance
                if not self._check_advertiser_balance(campaign.advertiser, campaign.budget_daily):
                    raise ValidationError("Insufficient balance to resume campaign")
                
                # Update campaign status
                campaign.status = 'active'
                campaign.save()
                
                # Send notification
                self._send_campaign_resumed_notification(campaign.advertiser, campaign)
                
                self.logger.info(f"Resumed campaign: {campaign.name}")
                return campaign
                
        except Exception as e:
            self.logger.error(f"Error resuming campaign: {e}")
            raise ValidationError(f"Failed to resume campaign: {str(e)}")
    
    def end_campaign(self, campaign: AdCampaign, reason: str = None) -> AdCampaign:
        """
        End a campaign.
        
        Args:
            campaign: Campaign instance to end
            reason: Reason for ending
            
        Returns:
            AdCampaign: Updated campaign instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                if campaign.status in ['ended', 'cancelled']:
                    raise ValidationError("Campaign is already ended or cancelled")
                
                # Update campaign status
                campaign.status = 'ended'
                campaign.actual_end_date = timezone.now()
                campaign.notes = f"Ended: {reason}\n{campaign.notes or ''}" if reason else campaign.notes
                campaign.save()
                
                # Send notification
                self._send_campaign_ended_notification(campaign.advertiser, campaign, reason)
                
                self.logger.info(f"Ended campaign: {campaign.name}")
                return campaign
                
        except Exception as e:
            self.logger.error(f"Error ending campaign: {e}")
            raise ValidationError(f"Failed to end campaign: {str(e)}")
    
    def cancel_campaign(self, campaign: AdCampaign, reason: str = None) -> AdCampaign:
        """
        Cancel a campaign.
        
        Args:
            campaign: Campaign instance to cancel
            reason: Reason for cancellation
            
        Returns:
            AdCampaign: Updated campaign instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                if campaign.status in ['ended', 'cancelled']:
                    raise ValidationError("Campaign is already ended or cancelled")
                
                # Update campaign status
                campaign.status = 'cancelled'
                campaign.actual_end_date = timezone.now()
                campaign.notes = f"Cancelled: {reason}\n{campaign.notes or ''}" if reason else campaign.notes
                campaign.save()
                
                # Send notification
                self._send_campaign_cancelled_notification(campaign.advertiser, campaign, reason)
                
                self.logger.info(f"Cancelled campaign: {campaign.name}")
                return campaign
                
        except Exception as e:
            self.logger.error(f"Error cancelling campaign: {e}")
            raise ValidationError(f"Failed to cancel campaign: {str(e)}")
    
    def get_campaign(self, campaign_id: int) -> Optional[AdCampaign]:
        """
        Get campaign by ID.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            AdCampaign: Campaign instance or None
        """
        try:
            return AdCampaign.objects.select_related(
                'advertiser', 'advertiser__user'
            ).prefetch_related(
                'creatives', 'offers', 'targeting', 'bid', 'schedule'
            ).get(id=campaign_id)
        except AdCampaign.DoesNotExist:
            return None
    
    def get_campaigns(self, advertiser=None, filters: Dict[str, Any] = None) -> List[AdCampaign]:
        """
        Get campaigns with optional filtering.
        
        Args:
            advertiser: Optional advertiser filter
            filters: Additional filter criteria
            
        Returns:
            List[AdCampaign]: List of campaigns
        """
        queryset = AdCampaign.objects.select_related('advertiser').order_by('-created_at')
        
        if advertiser:
            queryset = queryset.filter(advertiser=advertiser)
        
        if filters:
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
            
            if 'objective' in filters:
                queryset = queryset.filter(objective=filters['objective'])
            
            if 'start_date_from' in filters:
                queryset = queryset.filter(start_date__gte=filters['start_date_from'])
            
            if 'start_date_to' in filters:
                queryset = queryset.filter(start_date__lte=filters['start_date_to'])
            
            if 'search' in filters:
                search_term = filters['search']
                queryset = queryset.filter(
                    models.Q(name__icontains=search_term) |
                    models.Q(description__icontains=search_term)
                )
        
        return list(queryset)
    
    def get_campaign_stats(self, campaign: AdCampaign) -> Dict[str, Any]:
        """
        Get campaign statistics.
        
        Args:
            campaign: Campaign instance
            
        Returns:
            Dict[str, Any]: Campaign statistics
        """
        from ...models.reporting import CampaignReport
        from ...models.offer import AdvertiserOffer
        
        # Basic stats
        total_offers = AdvertiserOffer.objects.filter(campaign=campaign).count()
        active_offers = AdvertiserOffer.objects.filter(campaign=campaign, status='active').count()
        
        # Performance stats
        performance_data = CampaignReport.objects.filter(campaign=campaign).aggregate(
            total_impressions=models.Sum('impressions'),
            total_clicks=models.Sum('clicks'),
            total_conversions=models.Sum('conversions'),
            total_spend=models.Sum('spend_amount'),
            avg_ctr=models.Avg('ctr'),
            avg_conversion_rate=models.Avg('conversion_rate'),
            avg_cpa=models.Avg('cpa')
        )
        
        # Fill missing values with 0
        for key, value in performance_data.items():
            if value is None:
                performance_data[key] = 0
        
        # Calculate derived metrics
        total_impressions = performance_data['total_impressions'] or 0
        total_clicks = performance_data['total_clicks'] or 0
        total_conversions = performance_data['total_conversions'] or 0
        total_spend = performance_data['total_spend'] or 0
        
        calculated_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        calculated_cpa = (total_spend / total_conversions) if total_conversions > 0 else 0
        
        return {
            'basic_stats': {
                'total_offers': total_offers,
                'active_offers': active_offers,
                'status': campaign.status,
                'objective': campaign.objective,
                'created_at': campaign.created_at.isoformat(),
            },
            'performance_stats': {
                'total_impressions': total_impressions,
                'total_clicks': total_clicks,
                'total_conversions': total_conversions,
                'total_spend': float(total_spend),
                'ctr': float(calculated_ctr),
                'cpa': float(calculated_cpa),
                'avg_ctr': float(performance_data['avg_ctr'] or 0),
                'avg_conversion_rate': float(performance_data['avg_conversion_rate'] or 0),
                'avg_cpa': float(performance_data['avg_cpa'] or 0),
            },
            'budget_stats': {
                'budget_total': float(campaign.budget_total or 0),
                'budget_daily': float(campaign.budget_daily or 0),
                'total_spend': float(total_spend),
                'budget_utilization': (total_spend / campaign.budget_total * 100) if campaign.budget_total else 0,
            },
            'date_info': {
                'start_date': campaign.start_date.isoformat() if campaign.start_date else None,
                'end_date': campaign.end_date.isoformat() if campaign.end_date else None,
                'actual_start_date': campaign.actual_start_date.isoformat() if campaign.actual_start_date else None,
                'actual_end_date': campaign.actual_end_date.isoformat() if campaign.actual_end_date else None,
                'is_running': campaign.status == 'active',
                'days_running': self._calculate_days_running(campaign),
            }
        }
    
    def search_campaigns(self, query: str, advertiser=None, limit: int = 50) -> List[AdCampaign]:
        """
        Search campaigns by name or description.
        
        Args:
            query: Search query
            advertiser: Optional advertiser filter
            limit: Maximum results
            
        Returns:
            List[AdCampaign]: Matching campaigns
        """
        queryset = AdCampaign.objects.filter(
            models.Q(name__icontains=query) |
            models.Q(description__icontains=query)
        )
        
        if advertiser:
            queryset = queryset.filter(advertiser=advertiser)
        
        return list(queryset.select_related('advertiser')[:limit])
    
    def _create_campaign_targeting(self, campaign: AdCampaign, targeting_data: Dict[str, Any]):
        """Create campaign targeting."""
        CampaignTargeting.objects.create(
            campaign=campaign,
            countries=targeting_data.get('countries', []),
            devices=targeting_data.get('devices', []),
            operating_systems=targeting_data.get('operating_systems', []),
            browsers=targeting_data.get('browsers', []),
            categories=targeting_data.get('categories', []),
            keywords=targeting_data.get('keywords', []),
            min_age=targeting_data.get('min_age'),
            max_age=targeting_data.get('max_age'),
            gender=targeting_data.get('gender'),
            custom_rules=targeting_data.get('custom_rules', {})
        )
    
    def _create_campaign_bid(self, campaign: AdCampaign, bid_data: Dict[str, Any]):
        """Create campaign bid."""
        CampaignBid.objects.create(
            campaign=campaign,
            bid_type=bid_data.get('bid_type', 'cpc'),
            bid_amount=bid_data.get('bid_amount'),
            max_bid=bid_data.get('max_bid'),
            auto_optimize=bid_data.get('auto_optimize', False),
            optimization_goals=bid_data.get('optimization_goals', {}),
            bid_adjustments=bid_data.get('bid_adjustments', {})
        )
    
    def _create_campaign_schedule(self, campaign: AdCampaign, schedule_data: Dict[str, Any]):
        """Create campaign schedule."""
        CampaignSchedule.objects.create(
            campaign=campaign,
            hours=schedule_data.get('hours', {}),
            timezone=schedule_data.get('timezone', 'UTC'),
            custom_rules=schedule_data.get('custom_rules', {})
        )
    
    def _update_campaign_targeting(self, campaign: AdCampaign, targeting_data: Dict[str, Any]):
        """Update campaign targeting."""
        targeting, created = CampaignTargeting.objects.get_or_create(campaign=campaign)
        
        for field, value in targeting_data.items():
            if hasattr(targeting, field):
                setattr(targeting, field, value)
        
        targeting.save()
    
    def _update_campaign_bid(self, campaign: AdCampaign, bid_data: Dict[str, Any]):
        """Update campaign bid."""
        bid, created = CampaignBid.objects.get_or_create(campaign=campaign)
        
        for field, value in bid_data.items():
            if hasattr(bid, field):
                setattr(bid, field, value)
        
        bid.save()
    
    def _update_campaign_schedule(self, campaign: AdCampaign, schedule_data: Dict[str, Any]):
        """Update campaign schedule."""
        schedule, created = CampaignSchedule.objects.get_or_create(campaign=campaign)
        
        for field, value in schedule_data.items():
            if hasattr(schedule, field):
                setattr(schedule, field, value)
        
        schedule.save()
    
    def _check_advertiser_balance(self, advertiser, daily_budget: float) -> bool:
        """Check if advertiser has sufficient balance."""
        from ...models.billing import AdvertiserWallet
        
        try:
            wallet = AdvertiserWallet.objects.get(advertiser=advertiser)
            return wallet.available_balance >= daily_budget
        except AdvertiserWallet.DoesNotExist:
            return False
    
    def _calculate_days_running(self, campaign: AdCampaign) -> int:
        """Calculate days campaign has been running."""
        if not campaign.actual_start_date:
            return 0
        
        end_date = campaign.actual_end_date or timezone.now()
        return (end_date.date() - campaign.actual_start_date.date()).days
    
    def _send_campaign_created_notification(self, advertiser, campaign: AdCampaign):
        """Send campaign created notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='campaign_created',
            title=_('Campaign Created'),
            message=_('Your campaign "{campaign_name}" has been created successfully.').format(
                campaign_name=campaign.name
            ),
            priority='medium',
            action_url=f'/advertiser/campaigns/{campaign.id}/',
            action_text=_('View Campaign')
        )
    
    def _send_campaign_started_notification(self, advertiser, campaign: AdCampaign):
        """Send campaign started notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='campaign_started',
            title=_('Campaign Started'),
            message=_('Your campaign "{campaign_name}" has started running.').format(
                campaign_name=campaign.name
            ),
            priority='high',
            action_url=f'/advertiser/campaigns/{campaign.id}/',
            action_text=_('View Performance')
        )
    
    def _send_campaign_paused_notification(self, advertiser, campaign: AdCampaign, reason: str):
        """Send campaign paused notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='campaign_paused',
            title=_('Campaign Paused'),
            message=_('Your campaign "{campaign_name}" has been paused.').format(
                campaign_name=campaign.name
            ),
            priority='medium',
            action_url=f'/advertiser/campaigns/{campaign.id}/',
            action_text=_('View Campaign')
        )
    
    def _send_campaign_resumed_notification(self, advertiser, campaign: AdCampaign):
        """Send campaign resumed notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='campaign_started',
            title=_('Campaign Resumed'),
            message=_('Your campaign "{campaign_name}" has been resumed and is now active.').format(
                campaign_name=campaign.name
            ),
            priority='medium',
            action_url=f'/advertiser/campaigns/{campaign.id}/',
            action_text=_('View Performance')
        )
    
    def _send_campaign_ended_notification(self, advertiser, campaign: AdCampaign, reason: str):
        """Send campaign ended notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='campaign_ended',
            title=_('Campaign Ended'),
            message=_('Your campaign "{campaign_name}" has ended.').format(
                campaign_name=campaign.name
            ),
            priority='medium',
            action_url=f'/advertiser/campaigns/{campaign.id}/report/',
            action_text=_('View Report')
        )
    
    def _send_campaign_cancelled_notification(self, advertiser, campaign: AdCampaign, reason: str):
        """Send campaign cancelled notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='campaign_ended',
            title=_('Campaign Cancelled'),
            message=_('Your campaign "{campaign_name}" has been cancelled.').format(
                campaign_name=campaign.name
            ),
            priority='high',
            action_url=f'/advertiser/campaigns/{campaign.id}/',
            action_text=_('View Campaign')
        )
