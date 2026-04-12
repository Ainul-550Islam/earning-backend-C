"""
Campaign Management Services

This module contains service classes for managing campaigns,
including creation, optimization, targeting, and analytics.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from ..database_models.campaign_model import Campaign, CampaignSpend, CampaignGroup
from ..database_models.creative_model import Creative
from ..database_models.targeting_model import Targeting
from ..database_models.impression_model import Impression
from ..database_models.click_model import Click
from ..database_models.conversion_model import Conversion
from ..database_models.analytics_model import AnalyticsReport
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class CampaignService:
    """Service for managing campaign operations."""
    
    @staticmethod
    def create_campaign(data: Dict[str, Any], created_by: Optional[User] = None) -> Campaign:
        """Create a new campaign."""
        try:
            with transaction.atomic():
                # Validate advertiser exists and has permission
                advertiser = data.get('advertiser')
                if not advertiser:
                    raise CampaignValidationError("Advertiser is required")
                
                # Check if advertiser can create campaigns
                if not AdvertiserService.can_create_campaign(advertiser.id):
                    raise CampaignValidationError("Advertiser cannot create more campaigns")
                
                # Create campaign
                campaign = Campaign.objects.create(
                    advertiser=advertiser,
                    name=data['name'],
                    description=data.get('description', ''),
                    objective=data.get('objective', CampaignObjectiveEnum.LEADS.value),
                    bidding_strategy=data.get('bidding_strategy', BiddingStrategyEnum.MANUAL_CPC.value),
                    target_cpa=data.get('target_cpa'),
                    target_roas=data.get('target_roas'),
                    daily_budget=Decimal(str(data.get('daily_budget', 0))),
                    total_budget=Decimal(str(data.get('total_budget', 0))),
                    start_date=data['start_date'],
                    end_date=data.get('end_date'),
                    delivery_method=data.get('delivery_method', 'standard'),
                    start_time=data.get('start_time'),
                    end_time=data.get('end_time'),
                    days_of_week=data.get('days_of_week', [1, 2, 3, 4, 5, 6, 7]),
                    timezone=data.get('timezone', 'UTC'),
                    frequency_cap=data.get('frequency_cap'),
                    frequency_cap_period=data.get('frequency_cap_period'),
                    device_targeting=data.get('device_targeting', {}),
                    platform_targeting=data.get('platform_targeting', {}),
                    geo_targeting=data.get('geo_targeting', {}),
                    audience_targeting=data.get('audience_targeting', {}),
                    language_targeting=data.get('language_targeting', {}),
                    content_targeting=data.get('content_targeting', {}),
                    auto_optimize=data.get('auto_optimize', False),
                    optimization_goals=data.get('optimization_goals', []),
                    learning_phase=data.get('learning_phase', True),
                    bid_adjustments=data.get('bid_adjustments', {}),
                    bid_floor=Decimal(str(data.get('bid_floor', 0.01))),
                    bid_ceiling=data.get('bid_ceiling'),
                    conversion_window=data.get('conversion_window', 30),
                    attribution_model=data.get('attribution_model', 'last_click'),
                    quality_score=0,
                    performance_score=0,
                    campaign_groups=data.get('campaign_groups', []),
                    labels=data.get('labels', []),
                    external_campaign_id=data.get('external_campaign_id'),
                    integration_settings=data.get('integration_settings', {}),
                    auto_pause_on_budget_exhaust=data.get('auto_pause_on_budget_exhaust', True),
                    auto_restart_on_budget_refill=data.get('auto_restart_on_budget_refill', False),
                    require_approval=data.get('require_approval', False),
                    created_by=created_by
                )
                
                # Create targeting if provided
                targeting_data = data.get('targeting', {})
                if targeting_data:
                    Targeting.objects.create(
                        campaign=campaign,
                        name=f"{campaign.name} - Targeting",
                        description="Default targeting configuration",
                        geo_targeting_type=targeting_data.get('geo_targeting_type', 'countries'),
                        countries=targeting_data.get('countries', []),
                        regions=targeting_data.get('regions', []),
                        cities=targeting_data.get('cities', []),
                        postal_codes=targeting_data.get('postal_codes', []),
                        device_targeting=targeting_data.get('device_targeting', []),
                        os_families=targeting_data.get('os_families', []),
                        browsers=targeting_data.get('browsers', []),
                        carriers=targeting_data.get('carriers', []),
                        device_models=targeting_data.get('device_models', []),
                        age_min=targeting_data.get('age_min'),
                        age_max=targeting_data.get('age_max'),
                        genders=targeting_data.get('genders', []),
                        languages=targeting_data.get('languages', []),
                        interests=targeting_data.get('interests', []),
                        keywords=targeting_data.get('keywords', []),
                        created_by=created_by
                    )
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=created_by,
                    title='Campaign Created',
                    message=f'Campaign "{campaign.name}" has been created successfully.',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    campaign,
                    created_by,
                    description=f"Created campaign: {campaign.name}"
                )
                
                return campaign
                
        except Exception as e:
            logger.error(f"Error creating campaign: {str(e)}")
            raise CampaignServiceError(f"Failed to create campaign: {str(e)}")
    
    @staticmethod
    def update_campaign(campaign_id: UUID, data: Dict[str, Any],
                       updated_by: Optional[User] = None) -> Campaign:
        """Update campaign details."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            
            with transaction.atomic():
                # Track changes for audit log
                changed_fields = {}
                
                # Update basic fields
                for field in ['name', 'description', 'objective', 'bidding_strategy',
                             'target_cpa', 'target_roas', 'daily_budget', 'total_budget',
                             'end_date', 'delivery_method', 'start_time', 'end_time',
                             'days_of_week', 'timezone', 'frequency_cap', 'frequency_cap_period',
                             'auto_optimize', 'optimization_goals', 'learning_phase',
                             'bid_adjustments', 'bid_floor', 'bid_ceiling', 'conversion_window',
                             'attribution_model', 'campaign_groups', 'labels',
                             'auto_pause_on_budget_exhaust', 'auto_restart_on_budget_refill',
                             'require_approval']:
                    if field in data:
                        old_value = getattr(campaign, field)
                        new_value = data[field]
                        if old_value != new_value:
                            setattr(campaign, field, new_value)
                            changed_fields[field] = {'old': old_value, 'new': new_value}
                
                # Update targeting fields
                for field in ['device_targeting', 'platform_targeting', 'geo_targeting',
                             'audience_targeting', 'language_targeting', 'content_targeting']:
                    if field in data:
                        old_value = getattr(campaign, field)
                        new_value = data[field]
                        if old_value != new_value:
                            setattr(campaign, field, new_value)
                            changed_fields[field] = {'old': old_value, 'new': new_value}
                
                campaign.modified_by = updated_by
                campaign.save()
                
                # Update targeting if provided
                targeting_data = data.get('targeting')
                if targeting_data:
                    targeting = campaign.targeting
                    for field, value in targeting_data.items():
                        if hasattr(targeting, field):
                            old_value = getattr(targeting, field)
                            if old_value != value:
                                setattr(targeting, field, value)
                                changed_fields[f'targeting_{field}'] = {'old': old_value, 'new': value}
                    
                    targeting.modified_by = updated_by
                    targeting.save()
                
                # Log changes
                if changed_fields:
                    from ..database_models.audit_model import AuditLog
                    AuditLog.log_update(
                        campaign,
                        changed_fields,
                        updated_by,
                        description=f"Updated campaign: {campaign.name}"
                    )
                
                return campaign
                
        except Campaign.DoesNotExist:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error updating campaign {campaign_id}: {str(e)}")
            raise CampaignServiceError(f"Failed to update campaign: {str(e)}")
    
    @staticmethod
    def delete_campaign(campaign_id: UUID, deleted_by: Optional[User] = None) -> bool:
        """Delete campaign (soft delete)."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            
            with transaction.atomic():
                # Log deletion
                from ..database_models.audit_model import AuditLog
                AuditLog.log_deletion(
                    campaign,
                    deleted_by,
                    description=f"Deleted campaign: {campaign.name}"
                )
                
                # Soft delete
                campaign.soft_delete()
                
                # Send notification
                Notification.objects.create(
                    advertiser=campaign.advertiser,
                    user=deleted_by,
                    title='Campaign Deleted',
                    message=f'Campaign "{campaign.name}" has been deleted.',
                    notification_type='system',
                    priority='high',
                    channels=['in_app']
                )
                
                return True
                
        except Campaign.DoesNotExist:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error deleting campaign {campaign_id}: {str(e)}")
            raise CampaignServiceError(f"Failed to delete campaign: {str(e)}")
    
    @staticmethod
    def get_campaign(campaign_id: UUID) -> Campaign:
        """Get campaign by ID."""
        try:
            return Campaign.objects.get(id=campaign_id, is_deleted=False)
        except Campaign.DoesNotExist:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
    
    @staticmethod
    def list_campaigns(advertiser_id: UUID, filters: Optional[Dict[str, Any]] = None,
                         page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """List campaigns with filtering and pagination."""
        try:
            queryset = Campaign.objects.filter(
                advertiser_id=advertiser_id,
                is_deleted=False
            )
            
            # Apply filters
            if filters:
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                if 'objective' in filters:
                    queryset = queryset.filter(objective=filters['objective'])
                if 'is_active' in filters:
                    if filters['is_active']:
                        queryset = queryset.filter(status='active')
                    else:
                        queryset = queryset.exclude(status='active')
                if 'search' in filters:
                    search = filters['search']
                    queryset = queryset.filter(
                        Q(name__icontains=search) |
                        Q(description__icontains=search)
                    )
            
            # Count total
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            campaigns = queryset[offset:offset + page_size]
            
            return {
                'campaigns': campaigns,
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error(f"Error listing campaigns: {str(e)}")
            raise CampaignServiceError(f"Failed to list campaigns: {str(e)}")
    
    @staticmethod
    def activate_campaign(campaign_id: UUID, activated_by: Optional[User] = None) -> bool:
        """Activate campaign."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            
            with transaction.atomic():
                campaign.status = CampaignStatusEnum.ACTIVE.value
                campaign.save(update_fields=['status'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=campaign.advertiser,
                    user=activated_by,
                    title='Campaign Activated',
                    message=f'Campaign "{campaign.name}" has been activated.',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log activation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='activate',
                    object_type='Campaign',
                    object_id=str(campaign.id),
                    user=activated_by,
                    advertiser=campaign.advertiser,
                    description=f"Activated campaign: {campaign.name}"
                )
                
                return True
                
        except Campaign.DoesNotExist:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error activating campaign {campaign_id}: {str(e)}")
            return False
    
    @staticmethod
    def pause_campaign(campaign_id: UUID, paused_by: Optional[User] = None) -> bool:
        """Pause campaign."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            
            with transaction.atomic():
                campaign.status = CampaignStatusEnum.PAUSED.value
                campaign.save(update_fields=['status'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=campaign.advertiser,
                    user=paused_by,
                    title='Campaign Paused',
                    message=f'Campaign "{campaign.name}" has been paused.',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log pause
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='pause',
                    object_type='Campaign',
                    object_id=str(campaign.id),
                    user=paused_by,
                    advertiser=campaign.advertiser,
                    description=f"Paused campaign: {campaign.name}"
                )
                
                return True
                
        except Campaign.DoesNotExist:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error pausing campaign {campaign_id}: {str(e)}")
            return False
    
    @staticmethod
    def duplicate_campaign(campaign_id: UUID, new_name: Optional[str] = None,
                           duplicated_by: Optional[User] = None) -> Campaign:
        """Duplicate campaign."""
        try:
            original_campaign = CampaignService.get_campaign(campaign_id)
            
            with transaction.atomic():
                new_campaign = original_campaign.duplicate(new_name)
                
                # Duplicate targeting if exists
                if original_campaign.targeting:
                    original_targeting = original_campaign.targeting
                    new_targeting = Targeting.objects.create(
                        campaign=new_campaign,
                        name=f"{new_campaign.name} - Targeting",
                        description="Duplicated targeting configuration",
                        geo_targeting_type=original_targeting.geo_targeting_type,
                        countries=original_targeting.countries,
                        regions=original_targeting.regions,
                        cities=original_targeting.cities,
                        postal_codes=original_targeting.postal_codes,
                        device_targeting=original_targeting.device_targeting,
                        os_families=original_targeting.os_families,
                        browsers=original_targeting.browsers,
                        carriers=original_targeting.carriers,
                        device_models=original_targeting.device_models,
                        age_min=original_targeting.age_min,
                        age_max=original_targeting.age_max,
                        genders=original_targeting.genders,
                        languages=original_targeting.languages,
                        interests=original_targeting.interests,
                        keywords=original_targeting.keywords,
                        created_by=duplicated_by
                    )
                
                # Send notification
                Notification.objects.create(
                    advertiser=new_campaign.advertiser,
                    user=duplicated_by,
                    title='Campaign Duplicated',
                    message=f'Campaign "{new_campaign.name}" has been duplicated from "{original_campaign.name}".',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log duplication
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='duplicate',
                    object_type='Campaign',
                    object_id=str(new_campaign.id),
                    user=duplicated_by,
                    advertiser=new_campaign.advertiser,
                    description=f"Duplicated campaign: {original_campaign.name} -> {new_campaign.name}"
                )
                
                return new_campaign
                
        except Campaign.DoesNotExist:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error duplicating campaign {campaign_id}: {str(e)}")
            raise CampaignServiceError(f"Failed to duplicate campaign: {str(e)}")
    
    @staticmethod
    def get_campaign_performance(campaign_id: UUID) -> Dict[str, Any]:
        """Get campaign performance metrics."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            return campaign.get_performance_metrics()
        except Exception as e:
            logger.error(f"Error getting campaign performance {campaign_id}: {str(e)}")
            raise CampaignServiceError(f"Failed to get campaign performance: {str(e)}")
    
    @staticmethod
    def can_spend(campaign_id: UUID, amount: Decimal) -> bool:
        """Check if campaign can spend specified amount."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            return campaign.can_spend(amount)
        except Campaign.DoesNotExist:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error checking spend capability {campaign_id}: {str(e)}")
            return False
    
    @staticmethod
    def add_spend(campaign_id: UUID, amount: Decimal, description: str = '') -> bool:
        """Add spend amount to campaign."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            return campaign.add_spend(amount)
        except Campaign.DoesNotExist:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error adding spend to campaign {campaign_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_optimization_recommendations(campaign_id: UUID) -> List[Dict[str, Any]]:
        """Get optimization recommendations for campaign."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            return campaign.get_optimization_recommendations()
        except Exception as e:
            logger.error(f"Error getting optimization recommendations {campaign_id}: {str(e)}")
            return []


class CampaignOptimizationService:
    """Service for campaign optimization operations."""
    
    @staticmethod
    def optimize_campaign(campaign_id: UUID, optimization_type: str = 'auto',
                          optimized_by: Optional[User] = None) -> bool:
        """Optimize campaign based on performance data."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            
            with transaction.atomic():
                # Get current performance metrics
                performance = campaign.get_performance_metrics()
                
                # Apply optimization logic based on type
                if optimization_type == 'auto':
                    recommendations = campaign.get_optimization_recommendations()
                    
                    for recommendation in recommendations:
                        if recommendation['priority'] == 'high':
                            CampaignOptimizationService._apply_optimization(
                                campaign, recommendation
                            )
                
                # Update optimization score
                campaign.performance_score = campaign.calculate_performance_score()
                campaign.save(update_fields=['performance_score'])
                
                # Log optimization
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='optimize',
                    object_type='Campaign',
                    object_id=str(campaign.id),
                    user=optimized_by,
                    advertiser=campaign.advertiser,
                    description=f"Optimized campaign: {campaign.name}"
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error optimizing campaign {campaign_id}: {str(e)}")
            return False
    
    @staticmethod
    def _apply_optimization(campaign: Campaign, recommendation: Dict[str, Any]) -> None:
        """Apply specific optimization recommendation."""
        action = recommendation.get('action')
        
        if action == 'increase_budget':
            # Increase budget by 20%
            new_budget = campaign.total_budget * Decimal('1.2')
            campaign.total_budget = new_budget
            campaign.save(update_fields=['total_budget'])
        
        elif action == 'optimize_creatives':
            # This would trigger creative optimization
            pass
        
        elif action == 'adjust_targeting':
            # This would adjust targeting parameters
            pass
        
        elif action == 'update_bidding':
            # This would update bidding strategy
            pass
    
    @staticmethod
    def get_optimization_report(campaign_id: UUID) -> Dict[str, Any]:
        """Get optimization report for campaign."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            
            performance = campaign.get_performance_metrics()
            recommendations = campaign.get_optimization_recommendations()
            
            return {
                'campaign': {
                    'id': str(campaign.id),
                    'name': campaign.name,
                    'status': campaign.status,
                    'performance_score': float(campaign.performance_score)
                },
                'performance': performance,
                'recommendations': recommendations,
                'optimization_history': CampaignOptimizationService._get_optimization_history(campaign)
            }
            
        except Exception as e:
            logger.error(f"Error getting optimization report {campaign_id}: {str(e)}")
            raise CampaignServiceError(f"Failed to get optimization report: {str(e)}")
    
    @staticmethod
    def _get_optimization_history(campaign: Campaign) -> List[Dict[str, Any]]:
        """Get optimization history for campaign."""
        # This would query optimization logs
        # For now, return empty list
        return []


class CampaignTargetingService:
    """Service for campaign targeting operations."""
    
    @staticmethod
    def update_targeting(campaign_id: UUID, targeting_data: Dict[str, Any],
                           updated_by: Optional[User] = None) -> bool:
        """Update campaign targeting."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            
            with transaction.atomic():
                targeting = campaign.targeting
                if not targeting:
                    targeting = Targeting.objects.create(
                        campaign=campaign,
                        name=f"{campaign.name} - Targeting",
                        description="Campaign targeting configuration",
                        created_by=updated_by
                    )
                
                # Update targeting fields
                for field, value in targeting_data.items():
                    if hasattr(targeting, field):
                        setattr(targeting, field, value)
                
                targeting.modified_by = updated_by
                targeting.save()
                
                # Log update
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='update',
                    object_type='Targeting',
                    object_id=str(targeting.id),
                    user=updated_by,
                    advertiser=campaign.advertiser,
                    description=f"Updated targeting for campaign: {campaign.name}"
                )
                
                return True
                
        except Campaign.DoesNotExist:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error updating targeting {campaign_id}: {str(e)}")
            return False
    
    @staticmethod
    def validate_targeting(campaign_id: UUID) -> Dict[str, Any]:
        """Validate campaign targeting configuration."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            targeting = campaign.targeting
            
            if not targeting:
                return {'valid': True, 'warnings': ['No targeting configuration found']}
            
            return targeting.validate_targeting()
            
        except Campaign.DoesNotExist:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error validating targeting {campaign_id}: {str(e)}")
            raise CampaignServiceError(f"Failed to validate targeting: {str(e)}")
    
    @staticmethod
    def get_targeting_summary(campaign_id: UUID) -> Dict[str, Any]:
        """Get targeting summary for campaign."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            targeting = campaign.targeting
            
            if not targeting:
                return {'error': 'No targeting configuration found'}
            
            return targeting.get_targeting_summary()
            
        except Campaign.DoesNotExist:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error getting targeting summary {campaign_id}: {str(e)}")
            raise CampaignServiceError(f"Failed to get targeting summary: {str(e)}")
    
    @staticmethod
    def expand_targeting(campaign_id: UUID, expansion_type: str = 'similar') -> Dict[str, Any]:
        """Get targeting expansion suggestions."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            targeting = campaign.targeting
            
            if not targeting:
                return {'error': 'No targeting configuration found'}
            
            return targeting.expand_targeting(expansion_type)
            
        except Campaign.DoesNotExist:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error expanding targeting {campaign_id}: {str(e)}")
            raise CampaignServiceError(f"Failed to expand targeting: {str(e)}")


class CampaignAnalyticsService:
    """Service for campaign analytics and reporting."""
    
    @staticmethod
    def get_analytics(campaign_id: UUID, date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get campaign analytics data."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            
            # Default to last 30 days if no date range provided
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timezone.timedelta(days=30)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            # Get aggregated data
            from ..database_models.impression_model import ImpressionAggregation
            from ..database_models.click_model import ClickAggregation
            from ..database_models.conversion_model import ConversionAggregation
            
            impressions = ImpressionAggregation.objects.filter(
                campaign=campaign,
                date__gte=start_date,
                date__lte=end_date
            ).aggregate(
                total_impressions=Sum('impressions'),
                total_cost=Sum('total_cost')
            )
            
            clicks = ClickAggregation.objects.filter(
                campaign=campaign,
                date__gte=start_date,
                date__lte=end_date
            ).aggregate(
                total_clicks=Sum('clicks'),
                total_cost=Sum('total_cost')
            )
            
            conversions = ConversionAggregation.objects.filter(
                campaign=campaign,
                date__gte=start_date,
                date__lte=end_date
            ).aggregate(
                total_conversions=Sum('conversions'),
                total_revenue=Sum('total_revenue')
            )
            
            # Calculate derived metrics
            total_impressions = impressions['total_impressions'] or 0
            total_clicks = clicks['total_clicks'] or 0
            total_conversions = conversions['total_conversions'] or 0
            total_cost = clicks['total_cost'] or 0
            total_revenue = conversions['total_revenue'] or 0
            
            ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            cpc = (total_cost / total_clicks) if total_clicks > 0 else 0
            cpa = (total_cost / total_conversions) if total_conversions > 0 else 0
            conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
            roas = (total_revenue / total_cost) if total_cost > 0 else 0
            
            return {
                'campaign': {
                    'id': str(campaign.id),
                    'name': campaign.name,
                    'date_range': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat()
                    }
                },
                'metrics': {
                    'total_impressions': total_impressions,
                    'total_clicks': total_clicks,
                    'total_conversions': total_conversions,
                    'total_cost': float(total_cost),
                    'total_revenue': float(total_revenue),
                    'ctr': ctr,
                    'cpc': cpc,
                    'cpa': cpa,
                    'conversion_rate': conversion_rate,
                    'roas': roas
                }
            }
            
        except Campaign.DoesNotExist:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error getting analytics {campaign_id}: {str(e)}")
            raise CampaignServiceError(f"Failed to get analytics: {str(e)}")
    
    @staticmethod
    def generate_report(campaign_id: UUID, report_type: str = 'performance',
                        date_range: Optional[Dict[str, str]] = None,
                        format_type: str = 'pdf') -> str:
        """Generate campaign report."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            
            # Create report
            report = AnalyticsReport.objects.create(
                advertiser=campaign.advertiser,
                campaign=campaign,
                report_name=f"{campaign.name} - {report_type.title()} Report",
                report_type=report_type,
                start_date=date_range['start_date'] if date_range else None,
                end_date=date_range['end_date'] if date_range else None,
                output_format=format_type
            )
            
            # Generate report data
            report.generate_report()
            
            return report.last_file
            
        except Campaign.DoesNotExist:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error generating report {campaign_id}: {str(e)}")
            raise CampaignServiceError(f"Failed to generate report: {str(e)}")


class CampaignBudgetService:
    """Service for campaign budget management."""
    
    @staticmethod
    def update_budget(campaign_id: UUID, budget_data: Dict[str, Any],
                      updated_by: Optional[User] = None) -> bool:
        """Update campaign budget settings."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            
            with transaction.atomic():
                # Update budget fields
                for field in ['daily_budget', 'total_budget', 'budget_delivery_method']:
                    if field in budget_data:
                        old_value = getattr(campaign, field)
                        new_value = budget_data[field]
                        if old_value != new_value:
                            setattr(campaign, field, new_value)
                
                campaign.modified_by = updated_by
                campaign.save()
                
                # Log update
                from ..database_models.audit_model import AuditLog
                AuditLog.log_update(
                    campaign,
                    {
                        field: {'old': old_value, 'new': new_value}
                        for field, new_value in budget_data.items()
                        if hasattr(campaign, field)
                    },
                    updated_by,
                    description=f"Updated budget for campaign: {campaign.name}"
                )
                
                return True
                
        except Campaign.DoesNotExist:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error updating budget {campaign_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_budget_summary(campaign_id: UUID) -> Dict[str, Any]:
        """Get budget summary for campaign."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            
            return {
                'budget_settings': {
                    'daily_budget': float(campaign.daily_budget),
                    'total_budget': float(campaign.total_budget),
                    'current_spend': float(campaign.current_spend),
                    'remaining_budget': float(campaign.remaining_budget),
                    'budget_utilization': float(campaign.budget_utilization),
                    'budget_delivery_method': campaign.budget_delivery_method
                },
                'spend_tracking': {
                    'daily_spend': CampaignBudgetService._get_daily_spend(campaign),
                    'total_spend': float(campaign.current_spend),
                    'spend_rate': CampaignBudgetService._calculate_spend_rate(campaign)
                }
            }
            
        except Campaign.DoesNotExist:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error getting budget summary {campaign_id}: {str(e)}")
            raise CampaignServiceError(f"Failed to get budget summary: {str(e)}")
    
    @staticmethod
    def _get_daily_spend(campaign: Campaign) -> List[Dict[str, Any]]:
        """Get daily spend data for campaign."""
        # This would query CampaignSpend table
        # For now, return empty list
        return []
    
    @staticmethod
    def _calculate_spend_rate(campaign: Campaign) -> float:
        """Calculate current spend rate."""
        if campaign.current_spend == 0:
            return 0.0
        
        # Calculate days since start
        days_active = (timezone.now().date() - campaign.start_date).days + 1
        if days_active <= 0:
            return 0.0
        
        return float(campaign.current_spend) / days_active
    
    @staticmethod
    def check_budget_alerts(campaign_id: UUID) -> List[Dict[str, Any]]:
        """Check for budget alerts."""
        try:
            campaign = CampaignService.get_campaign(campaign_id)
            alerts = []
            
            # Check budget utilization
            utilization = campaign.budget_utilization
            if utilization >= 80:
                alerts.append({
                    'type': 'budget_utilization',
                    'severity': 'high' if utilization >= 90 else 'medium',
                    'message': f'Budget utilization is {utilization:.1f}%',
                    'value': utilization
                })
            
            # Check daily budget
            daily_spend = CampaignBudgetService._get_daily_spend(campaign)
            if daily_spend and campaign.daily_budget > 0:
                today_spend = daily_spend[-1]['amount'] if daily_spend else 0
                daily_utilization = (today_spend / campaign.daily_budget) * 100
                
                if daily_utilization >= 100:
                    alerts.append({
                        'type': 'daily_budget_exhausted',
                        'severity': 'high',
                        'message': f'Daily budget exhausted ({today_spend}/{campaign.daily_budget})',
                        'value': daily_utilization
                    })
            
            return alerts
            
        except Campaign.DoesNotExist:
            raise CampaignNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error checking budget alerts {campaign_id}: {str(e)}")
            return []
