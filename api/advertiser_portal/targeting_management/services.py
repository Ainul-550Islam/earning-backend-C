"""
Targeting Management Services

This module contains service classes for managing targeting operations,
including audience segmentation, geographic targeting, device targeting,
and behavioral targeting.
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

from ..database_models.targeting_model import Targeting, AudienceSegment, TargetingRule
from ..database_models.campaign_model import Campaign
from ..database_models.impression_model import Impression
from ..database_models.click_model import Click
from ..database_models.conversion_model import Conversion
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class TargetingService:
    """Service for managing targeting operations."""
    
    @staticmethod
    def create_targeting(data: Dict[str, Any], created_by: Optional[User] = None) -> Targeting:
        """Create a new targeting configuration."""
        try:
            with transaction.atomic():
                targeting = Targeting.objects.create(
                    campaign=data.get('campaign'),
                    name=data['name'],
                    description=data.get('description', ''),
                    geo_targeting_type=data.get('geo_targeting_type', 'countries'),
                    countries=data.get('countries', []),
                    regions=data.get('regions', []),
                    cities=data.get('cities', []),
                    postal_codes=data.get('postal_codes', []),
                    coordinates=data.get('coordinates'),
                    radius=data.get('radius'),
                    geo_fencing=data.get('geo_fencing', False),
                    device_targeting=data.get('device_targeting', []),
                    os_families=data.get('os_families', []),
                    browsers=data.get('browsers', []),
                    carriers=data.get('carriers', []),
                    device_models=data.get('device_models', []),
                    connection_types=data.get('connection_types', []),
                    age_min=data.get('age_min'),
                    age_max=data.get('age_max'),
                    genders=data.get('genders', []),
                    languages=data.get('languages', []),
                    interests=data.get('interests', []),
                    keywords=data.get('keywords', []),
                    custom_audiences=data.get('custom_audiences', []),
                    lookalike_audiences=data.get('lookalike_audiences', []),
                    exclude_audiences=data.get('exclude_audiences', []),
                    behavioral_segments=data.get('behavioral_segments', []),
                    contextual_targeting=data.get('contextual_targeting', {}),
                    site_targeting=data.get('site_targeting', []),
                    app_targeting=data.get('app_targeting', []),
                    content_categories=data.get('content_categories', []),
                    placement_targeting=data.get('placement_targeting', {}),
                    time_targeting=data.get('time_targeting', {}),
                    frequency_capping=data.get('frequency_capping', {}),
                    bid_adjustments=data.get('bid_adjustments', {}),
                    created_by=created_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=targeting.campaign.advertiser,
                    user=created_by,
                    title='Targeting Created',
                    message=f'Targeting "{targeting.name}" has been created successfully.',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    targeting,
                    created_by,
                    description=f"Created targeting: {targeting.name}"
                )
                
                return targeting
                
        except Exception as e:
            logger.error(f"Error creating targeting: {str(e)}")
            raise TargetingServiceError(f"Failed to create targeting: {str(e)}")
    
    @staticmethod
    def update_targeting(targeting_id: UUID, data: Dict[str, Any],
                          updated_by: Optional[User] = None) -> Targeting:
        """Update targeting configuration."""
        try:
            targeting = TargetingService.get_targeting(targeting_id)
            
            with transaction.atomic():
                # Track changes for audit log
                changed_fields = {}
                
                # Update fields
                for field in ['name', 'description', 'geo_targeting_type', 'countries',
                             'regions', 'cities', 'postal_codes', 'coordinates', 'radius',
                             'geo_fencing', 'device_targeting', 'os_families', 'browsers',
                             'carriers', 'device_models', 'connection_types', 'age_min',
                             'age_max', 'genders', 'languages', 'interests', 'keywords',
                             'custom_audiences', 'lookalike_audiences', 'exclude_audiences',
                             'behavioral_segments', 'contextual_targeting', 'site_targeting',
                             'app_targeting', 'content_categories', 'placement_targeting',
                             'time_targeting', 'frequency_capping', 'bid_adjustments']:
                    if field in data:
                        old_value = getattr(targeting, field)
                        new_value = data[field]
                        if old_value != new_value:
                            setattr(targeting, field, new_value)
                            changed_fields[field] = {'old': old_value, 'new': new_value}
                
                targeting.modified_by = updated_by
                targeting.save()
                
                # Log changes
                if changed_fields:
                    from ..database_models.audit_model import AuditLog
                    AuditLog.log_update(
                        targeting,
                        changed_fields,
                        updated_by,
                        description=f"Updated targeting: {targeting.name}"
                    )
                
                return targeting
                
        except Targeting.DoesNotExist:
            raise TargetingNotFoundError(f"Targeting {targeting_id} not found")
        except Exception as e:
            logger.error(f"Error updating targeting {targeting_id}: {str(e)}")
            raise TargetingServiceError(f"Failed to update targeting: {str(e)}")
    
    @staticmethod
    def delete_targeting(targeting_id: UUID, deleted_by: Optional[User] = None) -> bool:
        """Delete targeting configuration."""
        try:
            targeting = TargetingService.get_targeting(targeting_id)
            
            with transaction.atomic():
                # Log deletion
                from ..database_models.audit_model import AuditLog
                AuditLog.log_deletion(
                    targeting,
                    deleted_by,
                    description=f"Deleted targeting: {targeting.name}"
                )
                
                # Delete targeting
                targeting.delete()
                
                # Send notification
                Notification.objects.create(
                    advertiser=targeting.campaign.advertiser,
                    user=deleted_by,
                    title='Targeting Deleted',
                    message=f'Targeting "{targeting.name}" has been deleted.',
                    notification_type='system',
                    priority='high',
                    channels=['in_app']
                )
                
                return True
                
        except Targeting.DoesNotExist:
            raise TargetingNotFoundError(f"Targeting {targeting_id} not found")
        except Exception as e:
            logger.error(f"Error deleting targeting {targeting_id}: {str(e)}")
            raise TargetingServiceError(f"Failed to delete targeting: {str(e)}")
    
    @staticmethod
    def get_targeting(targeting_id: UUID) -> Targeting:
        """Get targeting by ID."""
        try:
            return Targeting.objects.get(id=targeting_id)
        except Targeting.DoesNotExist:
            raise TargetingNotFoundError(f"Targeting {targeting_id} not found")
    
    @staticmethod
    def list_targetings(campaign_id: Optional[UUID] = None,
                         filters: Optional[Dict[str, Any]] = None,
                         page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """List targeting configurations with filtering and pagination."""
        try:
            queryset = Targeting.objects.all()
            
            # Apply campaign filter
            if campaign_id:
                queryset = queryset.filter(campaign_id=campaign_id)
            
            # Apply filters
            if filters:
                if 'geo_targeting_type' in filters:
                    queryset = queryset.filter(geo_targeting_type=filters['geo_targeting_type'])
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
            targetings = queryset[offset:offset + page_size]
            
            return {
                'targetings': targetings,
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error(f"Error listing targetings: {str(e)}")
            raise TargetingServiceError(f"Failed to list targetings: {str(e)}")
    
    @staticmethod
    def validate_targeting(targeting_id: UUID) -> Dict[str, Any]:
        """Validate targeting configuration."""
        try:
            targeting = TargetingService.get_targeting(targeting_id)
            return targeting.validate_targeting()
            
        except Targeting.DoesNotExist:
            raise TargetingNotFoundError(f"Targeting {targeting_id} not found")
        except Exception as e:
            logger.error(f"Error validating targeting {targeting_id}: {str(e)}")
            raise TargetingServiceError(f"Failed to validate targeting: {str(e)}")
    
    @staticmethod
    def get_targeting_summary(targeting_id: UUID) -> Dict[str, Any]:
        """Get targeting summary."""
        try:
            targeting = TargetingService.get_targeting(targeting_id)
            return targeting.get_targeting_summary()
            
        except Targeting.DoesNotExist:
            raise TargetingNotFoundError(f"Targeting {targeting_id} not found")
        except Exception as e:
            logger.error(f"Error getting targeting summary {targeting_id}: {str(e)}")
            raise TargetingServiceError(f"Failed to get targeting summary: {str(e)}")
    
    @staticmethod
    def estimate_reach(targeting_id: UUID) -> Dict[str, Any]:
        """Estimate reach for targeting configuration."""
        try:
            targeting = TargetingService.get_targeting(targeting_id)
            return targeting.estimate_reach()
            
        except Targeting.DoesNotExist:
            raise TargetingNotFoundError(f"Targeting {targeting_id} not found")
        except Exception as e:
            logger.error(f"Error estimating reach {targeting_id}: {str(e)}")
            raise TargetingServiceError(f"Failed to estimate reach: {str(e)}")
    
    @staticmethod
    def calculate_targeting_score(targeting_id: UUID) -> float:
        """Calculate targeting score."""
        try:
            targeting = TargetingService.get_targeting(targeting_id)
            return targeting.calculate_targeting_score()
            
        except Targeting.DoesNotExist:
            raise TargetingNotFoundError(f"Targeting {targeting_id} not found")
        except Exception as e:
            logger.error(f"Error calculating targeting score {targeting_id}: {str(e)}")
            return 0.0
    
    @staticmethod
    def check_targeting_overlap(targeting_id: UUID, other_targeting_id: UUID) -> Dict[str, Any]:
        """Check overlap between two targeting configurations."""
        try:
            targeting = TargetingService.get_targeting(targeting_id)
            other_targeting = TargetingService.get_targeting(other_targeting_id)
            return targeting.check_overlap(other_targeting)
            
        except Targeting.DoesNotExist as e:
            raise TargetingNotFoundError(str(e))
        except Exception as e:
            logger.error(f"Error checking targeting overlap: {str(e)}")
            raise TargetingServiceError(f"Failed to check targeting overlap: {str(e)}")
    
    @staticmethod
    def expand_targeting(targeting_id: UUID, expansion_type: str = 'similar') -> Dict[str, Any]:
        """Get targeting expansion suggestions."""
        try:
            targeting = TargetingService.get_targeting(targeting_id)
            return targeting.expand_targeting(expansion_type)
            
        except Targeting.DoesNotExist:
            raise TargetingNotFoundError(f"Targeting {targeting_id} not found")
        except Exception as e:
            logger.error(f"Error expanding targeting {targeting_id}: {str(e)}")
            raise TargetingServiceError(f"Failed to expand targeting: {str(e)}")
    
    @staticmethod
    def optimize_targeting(targeting_id: UUID, optimization_type: str = 'auto',
                           optimized_by: Optional[User] = None) -> bool:
        """Optimize targeting configuration."""
        try:
            targeting = TargetingService.get_targeting(targeting_id)
            
            # Get performance data
            performance_data = TargetingService._get_targeting_performance(targeting)
            
            # Apply optimization logic
            if optimization_type == 'auto':
                # Auto-optimization based on performance
                recommendations = TargetingService._get_optimization_recommendations(targeting, performance_data)
                
                for recommendation in recommendations:
                    if recommendation['priority'] == 'high':
                        TargetingService._apply_optimization(targeting, recommendation)
            
            # Update targeting score
            targeting_score = targeting.calculate_targeting_score()
            
            # Log optimization
            from ..database_models.audit_model import AuditLog
            AuditLog.log_action(
                action='optimize',
                object_type='Targeting',
                object_id=str(targeting.id),
                user=optimized_by,
                advertiser=targeting.campaign.advertiser,
                description=f"Optimized targeting: {targeting.name}"
            )
            
            return True
            
        except Targeting.DoesNotExist:
            raise TargetingNotFoundError(f"Targeting {targeting_id} not found")
        except Exception as e:
            logger.error(f"Error optimizing targeting {targeting_id}: {str(e)}")
            return False
    
    @staticmethod
    def _get_targeting_performance(targeting: Targeting) -> Dict[str, Any]:
        """Get performance data for targeting."""
        # Get campaign performance
        campaign = targeting.campaign
        performance = campaign.get_performance_metrics()
        
        return {
            'impressions': performance.get('total_impressions', 0),
            'clicks': performance.get('total_clicks', 0),
            'conversions': performance.get('total_conversions', 0),
            'cost': performance.get('total_cost', 0),
            'revenue': performance.get('total_revenue', 0),
            'ctr': performance.get('ctr', 0),
            'cpc': performance.get('cpc', 0),
            'cpa': performance.get('cpa', 0),
            'conversion_rate': performance.get('conversion_rate', 0),
            'roas': performance.get('roas', 0)
        }
    
    @staticmethod
    def _get_optimization_recommendations(targeting: Targeting, performance: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get optimization recommendations for targeting."""
        recommendations = []
        
        # Analyze performance and generate recommendations
        ctr = performance.get('ctr', 0)
        cpc = performance.get('cpc', 0)
        conversion_rate = performance.get('conversion_rate', 0)
        
        # Low CTR recommendation
        if ctr < 0.5:
            recommendations.append({
                'type': 'low_ctr',
                'priority': 'high',
                'action': 'expand_audience',
                'description': 'CTR is low, consider expanding audience or adjusting targeting',
                'suggestion': 'Add more interests or expand geographic targeting'
            })
        
        # High CPC recommendation
        if cpc > 2.0:
            recommendations.append({
                'type': 'high_cpc',
                'priority': 'medium',
                'action': 'refine_targeting',
                'description': 'CPC is high, consider refining targeting to improve efficiency',
                'suggestion': 'Add more specific filters to reduce competition'
            })
        
        # Low conversion rate recommendation
        if conversion_rate < 1.0:
            recommendations.append({
                'type': 'low_conversion_rate',
                'priority': 'high',
                'action': 'adjust_audience',
                'description': 'Conversion rate is low, consider adjusting audience targeting',
                'suggestion': 'Focus on high-intentent audiences or adjust landing page'
            })
        
        return recommendations
    
    @staticmethod
    def _apply_optimization(targeting: Targeting, recommendation: Dict[str, Any]) -> None:
        """Apply specific optimization recommendation."""
        action = recommendation.get('action')
        
        if action == 'expand_audience':
            # Expand audience targeting
            if targeting.interests:
                # Add related interests
                related_interests = TargetingService._get_related_interests(targeting.interests)
                targeting.interests.extend(related_interests)
        
        elif action == 'refine_targeting':
            # Refine targeting by adding more specific filters
            if targeting.countries:
                # Add regions if only countries are specified
                if not targeting.regions:
                    targeting.regions = TargetingService._get_major_regions(targeting.countries)
        
        elif action == 'adjust_audience':
            # Adjust audience targeting
            if targeting.custom_audiences:
                # Add more specific custom audiences
                specific_audiences = TargetingService._get_specific_audiences(targeting.custom_audiences)
                targeting.custom_audiences.extend(specific_audiences)
        
        targeting.save()
    
    @staticmethod
    def _get_related_interests(interests: List[str]) -> List[str]:
        """Get related interests based on existing ones."""
        # This would implement actual interest mapping logic
        # For now, return empty list
        return []
    
    @staticmethod
    def _get_major_regions(countries: List[str]) -> List[str]:
        """Get major regions for specified countries."""
        # This would implement actual country-region mapping
        # For now, return empty list
        return []
    
    @staticmethod
    def _get_specific_audiences(audiences: List[str]) -> List[str]:
        """Get more specific audiences based on existing ones."""
        # This would implement actual audience refinement logic
        # For now, return empty list
        return []


class AudienceSegmentService:
    """Service for managing audience segments."""
    
    @staticmethod
    def create_audience_segment(data: Dict[str, Any], created_by: Optional[User] = None) -> AudienceSegment:
        """Create a new audience segment."""
        try:
            with transaction.atomic():
                segment = AudienceSegment.objects.create(
                    advertiser=data.get('advertiser'),
                    name=data['name'],
                    description=data.get('description', ''),
                    segment_type=data.get('segment_type', 'custom'),
                    criteria=data.get('criteria', {}),
                    audience_size=data.get('audience_size', 0),
                    estimated_reach=data.get('estimated_reach', 0),
                    refresh_frequency=data.get('refresh_frequency', 'daily'),
                    last_refresh=timezone.now(),
                    is_active=data.get('is_active', True),
                    is_public=data.get('is_public', False),
                    tags=data.get('tags', []),
                    created_by=created_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=segment.advertiser,
                    user=created_by,
                    title='Audience Segment Created',
                    message=f'Audience segment "{segment.name}" has been created successfully.',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    segment,
                    created_by,
                    description=f"Created audience segment: {segment.name}"
                )
                
                return segment
                
        except Exception as e:
            logger.error(f"Error creating audience segment: {str(e)}")
            raise TargetingServiceError(f"Failed to create audience segment: {str(e)}")
    
    @staticmethod
    def update_audience_segment(segment_id: UUID, data: Dict[str, Any],
                                 updated_by: Optional[User] = None) -> AudienceSegment:
        """Update audience segment."""
        try:
            segment = AudienceSegmentService.get_audience_segment(segment_id)
            
            with transaction.atomic():
                # Track changes for audit log
                changed_fields = {}
                
                # Update fields
                for field in ['name', 'description', 'segment_type', 'criteria',
                             'refresh_frequency', 'is_active', 'is_public', 'tags']:
                    if field in data:
                        old_value = getattr(segment, field)
                        new_value = data[field]
                        if old_value != new_value:
                            setattr(segment, field, new_value)
                            changed_fields[field] = {'old': old_value, 'new': new_value}
                
                segment.modified_by = updated_by
                segment.save()
                
                # Log changes
                if changed_fields:
                    from ..database_models.audit_model import AuditLog
                    AuditLog.log_update(
                        segment,
                        changed_fields,
                        updated_by,
                        description=f"Updated audience segment: {segment.name}"
                    )
                
                return segment
                
        except AudienceSegment.DoesNotExist:
            raise TargetingNotFoundError(f"Audience segment {segment_id} not found")
        except Exception as e:
            logger.error(f"Error updating audience segment {segment_id}: {str(e)}")
            raise TargetingServiceError(f"Failed to update audience segment: {str(e)}")
    
    @staticmethod
    def delete_audience_segment(segment_id: UUID, deleted_by: Optional[User] = None) -> bool:
        """Delete audience segment."""
        try:
            segment = AudienceSegmentService.get_audience_segment(segment_id)
            
            with transaction.atomic():
                # Log deletion
                from ..database_models.audit_model import AuditLog
                AuditLog.log_deletion(
                    segment,
                    deleted_by,
                    description=f"Deleted audience segment: {segment.name}"
                )
                
                # Delete segment
                segment.delete()
                
                # Send notification
                Notification.objects.create(
                    advertiser=segment.advertiser,
                    user=deleted_by,
                    title='Audience Segment Deleted',
                    message=f'Audience segment "{segment.name}" has been deleted.',
                    notification_type='system',
                    priority='high',
                    channels=['in_app']
                )
                
                return True
                
        except AudienceSegment.DoesNotExist:
            raise TargetingNotFoundError(f"Audience segment {segment_id} not found")
        except Exception as e:
            logger.error(f"Error deleting audience segment {segment_id}: {str(e)}")
            raise TargetingServiceError(f"Failed to delete audience segment: {str(e)}")
    
    @staticmethod
    def get_audience_segment(segment_id: UUID) -> AudienceSegment:
        """Get audience segment by ID."""
        try:
            return AudienceSegment.objects.get(id=segment_id)
        except AudienceSegment.DoesNotExist:
            raise TargetingNotFoundError(f"Audience segment {segment_id} not found")
    
    @staticmethod
    def list_audience_segments(advertiser_id: Optional[UUID] = None,
                                 filters: Optional[Dict[str, Any]] = None,
                                 page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """List audience segments with filtering and pagination."""
        try:
            queryset = AudienceSegment.objects.all()
            
            # Apply advertiser filter
            if advertiser_id:
                queryset = queryset.filter(advertiser_id=advertiser_id)
            
            # Apply filters
            if filters:
                if 'segment_type' in filters:
                    queryset = queryset.filter(segment_type=filters['segment_type'])
                if 'is_active' in filters:
                    queryset = queryset.filter(is_active=filters['is_active'])
                if 'is_public' in filters:
                    queryset = queryset.filter(is_public=filters['is_public'])
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
            segments = queryset[offset:offset + page_size]
            
            return {
                'segments': segments,
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error(f"Error listing audience segments: {str(e)}")
            raise TargetingServiceError(f"Failed to list audience segments: {str(e)}")
    
    @staticmethod
    def refresh_audience_segment(segment_id: UUID, refreshed_by: Optional[User] = None) -> bool:
        """Refresh audience segment data."""
        try:
            segment = AudienceSegmentService.get_audience_segment(segment_id)
            
            with transaction.atomic():
                # Recalculate audience size and reach
                new_size = AudienceSegmentService._calculate_audience_size(segment)
                new_reach = AudienceSegmentService._estimate_reach(segment)
                
                segment.audience_size = new_size
                segment.estimated_reach = new_reach
                segment.last_refresh = timezone.now()
                segment.save(update_fields=['audience_size', 'estimated_reach', 'last_refresh'])
                
                # Log refresh
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='refresh',
                    object_type='AudienceSegment',
                    object_id=str(segment.id),
                    user=refreshed_by,
                    advertiser=segment.advertiser,
                    description=f"Refreshed audience segment: {segment.name}"
                )
                
                return True
                
        except AudienceSegment.DoesNotExist:
            raise TargetingNotFoundError(f"Audience segment {segment_id} not found")
        except Exception as e:
            logger.error(f"Error refreshing audience segment {segment_id}: {str(e)}")
            return False
    
    @staticmethod
    def _calculate_audience_size(segment: AudienceSegment) -> int:
        """Calculate audience size for segment."""
        # This would implement actual audience size calculation
        # For now, return a mock value
        return 10000
    
    @staticmethod
    def _estimate_reach(segment: AudienceSegment) -> int:
        """Estimate reach for segment."""
        # This would implement actual reach estimation
        # For now, return a mock value
        return 5000
    
    @staticmethod
    def get_segment_insights(segment_id: UUID) -> Dict[str, Any]:
        """Get insights for audience segment."""
        try:
            segment = AudienceSegmentService.get_audience_segment(segment_id)
            
            return {
                'segment': {
                    'id': str(segment.id),
                    'name': segment.name,
                    'segment_type': segment.segment_type,
                    'audience_size': segment.audience_size,
                    'estimated_reach': segment.estimated_reach,
                    'refresh_frequency': segment.refresh_frequency,
                    'last_refresh': segment.last_refresh.isoformat()
                },
                'demographics': AudienceSegmentService._get_demographic_insights(segment),
                'interests': AudienceSegmentService._get_interest_insights(segment),
                'behavioral': AudienceSegmentService._get_behavioral_insights(segment),
                'performance': AudienceSegmentService._get_performance_insights(segment)
            }
            
        except AudienceSegment.DoesNotExist:
            raise TargetingNotFoundError(f"Audience segment {segment_id} not found")
        except Exception as e:
            logger.error(f"Error getting segment insights {segment_id}: {str(e)}")
            raise TargetingServiceError(f"Failed to get segment insights: {str(e)}")
    
    @staticmethod
    def _get_demographic_insights(segment: AudienceSegment) -> Dict[str, Any]:
        """Get demographic insights for segment."""
        # This would implement actual demographic analysis
        return {
            'age_distribution': {},
            'gender_distribution': {},
            'location_distribution': {},
            'language_distribution': {}
        }
    
    @staticmethod
    def _get_interest_insights(segment: AudienceSegment) -> Dict[str, Any]:
        """Get interest insights for segment."""
        # This would implement actual interest analysis
        return {
            'top_interests': [],
            'interest_categories': {},
            'interest_trends': {}
        }
    
    @staticmethod
    def _get_behavioral_insights(segment: AudienceSegment) -> Dict[str, Any]:
        """Get behavioral insights for segment."""
        # This would implement actual behavioral analysis
        return {
            'browsing_patterns': {},
            'purchase_behavior': {},
            'engagement_patterns': {}
        }
    
    @staticmethod
    def _get_performance_insights(segment: AudienceSegment) -> Dict[str, Any]:
        """Get performance insights for segment."""
        # This would implement actual performance analysis
        return {
            'ctr': 0,
            'conversion_rate': 0,
            'roas': 0,
            'performance_trend': []
        }


class GeographicTargetingService:
    """Service for managing geographic targeting."""
    
    @staticmethod
    def get_countries_by_region(region: str) -> List[Dict[str, Any]]:
        """Get countries by region."""
        # This would implement actual country-region mapping
        # For now, return empty list
        return []
    
    @staticmethod
    def get_cities_by_country(country: str) -> List[Dict[str, Any]]:
        """Get cities by country."""
        # This would implement actual city-country mapping
        # For now, return empty list
        return []
    
    @staticmethod
    def validate_geographic_coordinates(coordinates: Dict[str, Any]) -> bool:
        """Validate geographic coordinates."""
        try:
            lat = coordinates.get('latitude')
            lng = coordinates.get('longitude')
            
            if lat is None or lng is None:
                return False
            
            # Validate latitude range
            if not (-90 <= lat <= 90):
                return False
            
            # Validate longitude range
            if not (-180 <= lng <= 180):
                return False
            
            return True
            
        except Exception:
            return False
    
    @staticmethod
    def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance between two geographic points."""
        # This would implement actual distance calculation (e.g., Haversine formula)
        # For now, return mock value
        return 100.0
    
    @staticmethod
    def get_timezone_by_coordinates(lat: float, lng: float) -> str:
        """Get timezone by geographic coordinates."""
        # This would implement actual timezone lookup
        # For now, return default timezone
        return 'UTC'
    
    @staticmethod
    def get_location_insights(location_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get insights for geographic location."""
        return {
            'population_density': 0,
            'economic_indicators': {},
            'internet_penetration': 0,
            'device_distribution': {},
            'local_languages': []
        }


class DeviceTargetingService:
    """Service for managing device targeting."""
    
    @staticmethod
    def get_device_statistics(campaign_id: UUID) -> Dict[str, Any]:
        """Get device statistics for campaign."""
        try:
            # This would implement actual device statistics calculation
            # For now, return mock data
            return {
                'desktop': {'impressions': 1000, 'clicks': 50, 'conversions': 5},
                'mobile': {'impressions': 2000, 'clicks': 100, 'conversions': 10},
                'tablet': {'impressions': 500, 'clicks': 25, 'conversions': 2}
            }
            
        except Exception as e:
            logger.error(f"Error getting device statistics {campaign_id}: {str(e)}")
            return {}
    
    @staticmethod
    def get_os_statistics(campaign_id: UUID) -> Dict[str, Any]:
        """Get operating system statistics for campaign."""
        try:
            # This would implement actual OS statistics calculation
            # For now, return mock data
            return {
                'windows': {'impressions': 1500, 'clicks': 75, 'conversions': 7},
                'macos': {'impressions': 800, 'clicks': 40, 'conversions': 4},
                'android': {'impressions': 1200, 'clicks': 60, 'conversions': 6},
                'ios': {'impressions': 1000, 'clicks': 50, 'conversions': 5}
            }
            
        except Exception as e:
            logger.error(f"Error getting OS statistics {campaign_id}: {str(e)}")
            return {}
    
    @staticmethod
    def get_browser_statistics(campaign_id: UUID) -> Dict[str, Any]:
        """Get browser statistics for campaign."""
        try:
            # This would implement actual browser statistics calculation
            # For now, return mock data
            return {
                'chrome': {'impressions': 2000, 'clicks': 100, 'conversions': 10},
                'firefox': {'impressions': 800, 'clicks': 40, 'conversions': 4},
                'safari': {'impressions': 600, 'clicks': 30, 'conversions': 3},
                'edge': {'impressions': 400, 'clicks': 20, 'conversions': 2}
            }
            
        except Exception as e:
            logger.error(f"Error getting browser statistics {campaign_id}: {str(e)}")
            return {}
    
    @staticmethod
    def get_device_performance_insights(targeting_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get performance insights for device targeting."""
        return {
            'device_performance': {},
            'os_performance': {},
            'browser_performance': {},
            'recommendations': []
        }


class BehavioralTargetingService:
    """Service for managing behavioral targeting."""
    
    @staticmethod
    def create_behavioral_segment(data: Dict[str, Any], created_by: Optional[User] = None) -> Dict[str, Any]:
        """Create behavioral targeting segment."""
        try:
            # This would implement actual behavioral segment creation
            # For now, return mock response
            return {
                'segment_id': str(uuid.uuid4()),
                'name': data.get('name', 'Behavioral Segment'),
                'status': 'created'
            }
            
        except Exception as e:
            logger.error(f"Error creating behavioral segment: {str(e)}")
            raise TargetingServiceError(f"Failed to create behavioral segment: {str(e)}")
    
    @staticmethod
    def get_behavioral_patterns(user_id: str, time_range: Dict[str, str]) -> Dict[str, Any]:
        """Get behavioral patterns for user."""
        try:
            # This would implement actual behavioral pattern analysis
            # For now, return mock data
            return {
                'browsing_history': [],
                'search_patterns': [],
                'purchase_history': [],
                'engagement_patterns': []
            }
            
        except Exception as e:
            logger.error(f"Error getting behavioral patterns {user_id}: {str(e)}")
            return {}
    
    @staticmethod
    def get_interest_affinity(interests: List[str]) -> Dict[str, Any]:
        """Get interest affinity scores."""
        try:
            # This would implement actual interest affinity calculation
            # For now, return mock data
            return {
                interest: 0.5 for interest in interests
            }
            
        except Exception as e:
            logger.error(f"Error getting interest affinity: {str(e)}")
            return {}


class TargetingOptimizationService:
    """Service for targeting optimization operations."""
    
    @staticmethod
    def optimize_targeting_configuration(targeting_id: UUID, optimization_goals: List[str],
                                           optimized_by: Optional[User] = None) -> Dict[str, Any]:
        """Optimize targeting configuration."""
        try:
            targeting = TargetingService.get_targeting(targeting_id)
            
            # Get current performance
            performance = TargetingService._get_targeting_performance(targeting)
            
            # Generate optimization recommendations
            recommendations = TargetingService._get_optimization_recommendations(targeting, performance)
            
            # Apply high-priority recommendations
            applied_recommendations = []
            for recommendation in recommendations:
                if recommendation['priority'] == 'high':
                    TargetingService._apply_optimization(targeting, recommendation)
                    applied_recommendations.append(recommendation)
            
            # Recalculate targeting score
            new_score = targeting.calculate_targeting_score()
            
            # Log optimization
            from ..database_models.audit_model import AuditLog
            AuditLog.log_action(
                action='optimize_configuration',
                object_type='Targeting',
                object_id=str(targeting.id),
                user=optimized_by,
                advertiser=targeting.campaign.advertiser,
                description=f"Optimized targeting configuration: {targeting.name}"
            )
            
            return {
                'optimization_applied': True,
                'applied_recommendations': applied_recommendations,
                'new_targeting_score': new_score,
                'performance_improvement': TargetingService._estimate_performance_improvement(performance)
            }
            
        except Targeting.DoesNotExist:
            raise TargetingNotFoundError(f"Targeting {targeting_id} not found")
        except Exception as e:
            logger.error(f"Error optimizing targeting configuration {targeting_id}: {str(e)}")
            raise TargetingServiceError(f"Failed to optimize targeting configuration: {str(e)}")
    
    @staticmethod
    def _estimate_performance_improvement(current_performance: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate performance improvement."""
        # This would implement actual performance improvement estimation
        # For now, return mock data
        return {
            'ctr_improvement': 0.1,  # 10% improvement
            'conversion_rate_improvement': 0.15,  # 15% improvement
            'roas_improvement': 0.2  # 20% improvement
        }
    
    @staticmethod
    def get_targeting_optimization_report(targeting_id: UUID) -> Dict[str, Any]:
        """Get targeting optimization report."""
        try:
            targeting = TargetingService.get_targeting(targeting_id)
            
            return {
                'targeting': {
                    'id': str(targeting.id),
                    'name': targeting.name,
                    'targeting_score': targeting.calculate_targeting_score()
                },
                'current_performance': TargetingService._get_targeting_performance(targeting),
                'optimization_history': TargetingOptimizationService._get_optimization_history(targeting),
                'recommendations': TargetingService._get_optimization_recommendations(
                    targeting, TargetingService._get_targeting_performance(targeting)
                )
            }
            
        except Targeting.DoesNotExist:
            raise TargetingNotFoundError(f"Targeting {targeting_id} not found")
        except Exception as e:
            logger.error(f"Error getting targeting optimization report {targeting_id}: {str(e)}")
            raise TargetingServiceError(f"Failed to get targeting optimization report: {str(e)}")
    
    @staticmethod
    def _get_optimization_history(targeting: Targeting) -> List[Dict[str, Any]]:
        """Get optimization history for targeting."""
        # This would query optimization logs
        # For now, return empty list
        return []
