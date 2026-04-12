"""
Retargeting Engines Services

This module handles retargeting operations including pixel management,
audience segmentation, retargeting campaigns, and conversion tracking.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.retargeting_model import RetargetingPixel, AudienceSegment, RetargetingCampaign, ConversionEvent
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class RetargetingService:
    """Service for managing retargeting operations."""
    
    @staticmethod
    def create_retargeting_campaign(campaign_data: Dict[str, Any], created_by: Optional[User] = None) -> RetargetingCampaign:
        """Create a new retargeting campaign."""
        try:
            # Validate campaign data
            advertiser_id = campaign_data.get('advertiser_id')
            if not advertiser_id:
                raise AdvertiserValidationError("advertiser_id is required")
            
            advertiser = RetargetingService.get_advertiser(advertiser_id)
            
            campaign_name = campaign_data.get('name')
            if not campaign_name:
                raise AdvertiserValidationError("name is required")
            
            retargeting_type = campaign_data.get('retargeting_type', 'pixel')
            if retargeting_type not in ['pixel', 'email', 'crm', 'custom']:
                raise AdvertiserValidationError("Invalid retargeting_type")
            
            with transaction.atomic():
                # Create retargeting campaign
                retargeting_campaign = RetargetingCampaign.objects.create(
                    advertiser=advertiser,
                    name=campaign_name,
                    description=campaign_data.get('description', ''),
                    retargeting_type=retargeting_type,
                    pixel_id=campaign_data.get('pixel_id'),
                    audience_segment_id=campaign_data.get('audience_segment_id'),
                    targeting_rules=campaign_data.get('targeting_rules', {}),
                    budget_limits=campaign_data.get('budget_limits', {}),
                    frequency_capping=campaign_data.get('frequency_capping', {}),
                    duration_days=campaign_data.get('duration_days', 30),
                    status='draft',
                    created_by=created_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=created_by,
                    title='Retargeting Campaign Created',
                    message=f'Retargeting campaign "{campaign_name}" has been created.',
                    notification_type='retargeting',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    retargeting_campaign,
                    created_by,
                    description=f"Created retargeting campaign: {campaign_name}"
                )
                
                return retargeting_campaign
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error creating retargeting campaign: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create retargeting campaign: {str(e)}")
    
    @staticmethod
    def activate_retargeting_campaign(campaign_id: UUID, activated_by: Optional[User] = None) -> bool:
        """Activate retargeting campaign."""
        try:
            campaign = RetargetingService.get_retargeting_campaign(campaign_id)
            
            with transaction.atomic():
                campaign.status = 'active'
                campaign.activated_at = timezone.now()
                campaign.activated_by = activated_by
                campaign.save(update_fields=['status', 'activated_at', 'activated_by'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=campaign.advertiser,
                    user=activated_by,
                    title='Retargeting Campaign Activated',
                    message=f'Retargeting campaign "{campaign.name}" has been activated.',
                    notification_type='retargeting',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log activation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='activate_retargeting_campaign',
                    object_type='RetargetingCampaign',
                    object_id=str(campaign.id),
                    user=activated_by,
                    advertiser=campaign.advertiser,
                    description=f"Activated retargeting campaign: {campaign.name}"
                )
                
                return True
                
        except RetargetingCampaign.DoesNotExist:
            raise AdvertiserNotFoundError(f"Retargeting campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error activating retargeting campaign {campaign_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_retargeting_performance(campaign_id: UUID, date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get retargeting campaign performance."""
        try:
            campaign = RetargetingService.get_retargeting_campaign(campaign_id)
            
            # Default date range (last 30 days)
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=30)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            # Get conversion events for this campaign
            conversion_events = ConversionEvent.objects.filter(
                retargeting_campaign=campaign,
                event_date__date__gte=start_date,
                event_date__date__lte=end_date
            )
            
            # Calculate performance metrics
            total_conversions = conversion_events.count()
            total_revenue = conversion_events.aggregate(
                total=Sum('conversion_value')
            )['total'] or Decimal('0.00')
            
            # Get audience metrics
            audience_size = RetargetingService._get_audience_size(campaign)
            
            # Calculate conversion rate
            conversion_rate = (total_conversions / audience_size * 100) if audience_size > 0 else 0
            
            return {
                'campaign_id': str(campaign_id),
                'campaign_name': campaign.name,
                'retargeting_type': campaign.retargeting_type,
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'performance_metrics': {
                    'total_conversions': total_conversions,
                    'total_revenue': float(total_revenue),
                    'audience_size': audience_size,
                    'conversion_rate': conversion_rate,
                    'average_order_value': float(total_revenue / total_conversions) if total_conversions > 0 else 0
                },
                'generated_at': timezone.now().isoformat()
            }
            
        except RetargetingCampaign.DoesNotExist:
            raise AdvertiserNotFoundError(f"Retargeting campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error getting retargeting performance {campaign_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get retargeting performance: {str(e)}")
    
    @staticmethod
    def _get_audience_size(campaign: RetargetingCampaign) -> int:
        """Get audience size for retargeting campaign."""
        try:
            if campaign.audience_segment:
                return campaign.audience_segment.audience_size
            elif campaign.pixel_id:
                # Get pixel audience size
                pixel = RetargetingService.get_pixel(campaign.pixel_id)
                return RetargetingService._get_pixel_audience_size(pixel)
            else:
                return 0
                
        except Exception as e:
            logger.error(f"Error getting audience size: {str(e)}")
            return 0
    
    @staticmethod
    def _get_pixel_audience_size(pixel: RetargetingPixel) -> int:
        """Get pixel audience size."""
        try:
            # Mock implementation - would query actual pixel data
            return 1000  # Placeholder
            
        except Exception as e:
            logger.error(f"Error getting pixel audience size: {str(e)}")
            return 0
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def get_retargeting_campaign(campaign_id: UUID) -> RetargetingCampaign:
        """Get retargeting campaign by ID."""
        try:
            return RetargetingCampaign.objects.get(id=campaign_id)
        except RetargetingCampaign.DoesNotExist:
            raise AdvertiserNotFoundError(f"Retargeting campaign {campaign_id} not found")
    
    @staticmethod
    def get_pixel(pixel_id: UUID) -> RetargetingPixel:
        """Get pixel by ID."""
        try:
            return RetargetingPixel.objects.get(id=pixel_id)
        except RetargetingPixel.DoesNotExist:
            raise AdvertiserNotFoundError(f"Pixel {pixel_id} not found")


class PixelService:
    """Service for managing retargeting pixels."""
    
    @staticmethod
    def create_pixel(pixel_data: Dict[str, Any], created_by: Optional[User] = None) -> RetargetingPixel:
        """Create a new retargeting pixel."""
        try:
            # Validate pixel data
            advertiser_id = pixel_data.get('advertiser_id')
            if not advertiser_id:
                raise AdvertiserValidationError("advertiser_id is required")
            
            advertiser = PixelService.get_advertiser(advertiser_id)
            
            pixel_name = pixel_data.get('name')
            if not pixel_name:
                raise AdvertiserValidationError("name is required")
            
            pixel_type = pixel_data.get('pixel_type', 'conversion')
            if pixel_type not in ['conversion', 'page_view', 'custom']:
                raise AdvertiserValidationError("Invalid pixel_type")
            
            with transaction.atomic():
                # Generate pixel code
                pixel_code = PixelService._generate_pixel_code()
                
                # Create pixel
                pixel = RetargetingPixel.objects.create(
                    advertiser=advertiser,
                    name=pixel_name,
                    description=pixel_data.get('description', ''),
                    pixel_type=pixel_type,
                    pixel_code=pixel_code,
                    tracking_url=pixel_data.get('tracking_url', ''),
                    conversion_value=Decimal(str(pixel_data.get('conversion_value', 0))),
                    status='active',
                    created_by=created_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=created_by,
                    title='Retargeting Pixel Created',
                    message f'Retargeting pixel "{pixel_name}" has been created.',
                    notification_type='retargeting',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    pixel,
                    created_by,
                    description=f"Created retargeting pixel: {pixel_name}"
                )
                
                return pixel
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error creating pixel: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create pixel: {str(e)}")
    
    @staticmethod
    def get_pixel_code(pixel_id: UUID) -> Dict[str, Any]:
        """Get pixel tracking code."""
        try:
            pixel = PixelService.get_pixel(pixel_id)
            
            # Generate pixel tracking code
            tracking_code = PixelService._generate_tracking_code(pixel)
            
            return {
                'pixel_id': str(pixel_id),
                'pixel_name': pixel.name,
                'pixel_type': pixel.pixel_type,
                'pixel_code': pixel.pixel_code,
                'tracking_code': tracking_code,
                'tracking_url': pixel.tracking_url,
                'instructions': PixelService._get_pixel_instructions(pixel)
            }
            
        except RetargetingPixel.DoesNotExist:
            raise AdvertiserNotFoundError(f"Pixel {pixel_id} not found")
        except Exception as e:
            logger.error(f"Error getting pixel code {pixel_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get pixel code: {str(e)}")
    
    @staticmethod
    def track_pixel_event(pixel_id: UUID, event_data: Dict[str, Any]) -> bool:
        """Track pixel event."""
        try:
            pixel = PixelService.get_pixel(pixel_id)
            
            # Create conversion event
            conversion_event = ConversionEvent.objects.create(
                pixel=pixel,
                event_type=event_data.get('event_type', 'conversion'),
                conversion_value=Decimal(str(event_data.get('conversion_value', pixel.conversion_value))),
                user_agent=event_data.get('user_agent', ''),
                ip_address=event_data.get('ip_address', ''),
                custom_data=event_data.get('custom_data', {}),
                event_date=timezone.now()
            )
            
            return True
            
        except RetargetingPixel.DoesNotExist:
            raise AdvertiserNotFoundError(f"Pixel {pixel_id} not found")
        except Exception as e:
            logger.error(f"Error tracking pixel event {pixel_id}: {str(e)}")
            return False
    
    @staticmethod
    def _generate_pixel_code() -> str:
        """Generate unique pixel code."""
        import secrets
        return f"pixel_{secrets.token_urlsafe(16)}"
    
    @staticmethod
    def _generate_tracking_code(pixel: RetargetingPixel) -> str:
        """Generate tracking code for pixel."""
        base_url = getattr(settings, 'TRACKING_BASE_URL', 'https://track.example.com')
        
        tracking_code = f"""
<!-- {pixel.name} Retargeting Pixel -->
<script>
  (function() {{
    var pixel = document.createElement('img');
    pixel.src = '{base_url}/pixel/{pixel.pixel_code}/?t=' + Date.now();
    pixel.style.display = 'none';
    document.body.appendChild(pixel);
  }})();
</script>
<!-- End {pixel.name} Pixel -->
        """.strip()
        
        return tracking_code
    
    @staticmethod
    def _get_pixel_instructions(pixel: RetargetingPixel) -> List[str]:
        """Get pixel implementation instructions."""
        instructions = [
            f"1. Copy the tracking code for {pixel.name}",
            f"2. Paste it on your website pages where you want to track {pixel.pixel_type} events",
            f"3. The pixel will automatically fire when the page loads",
            f"4. For custom events, you can trigger them manually using the API"
        ]
        
        if pixel.pixel_type == 'conversion':
            instructions.append("5. Set conversion value to track revenue")
        
        return instructions
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def get_pixel(pixel_id: UUID) -> RetargetingPixel:
        """Get pixel by ID."""
        try:
            return RetargetingPixel.objects.get(id=pixel_id)
        except RetargetingPixel.DoesNotExist:
            raise AdvertiserNotFoundError(f"Pixel {pixel_id} not found")


class AudienceSegmentService:
    """Service for managing audience segments."""
    
    @staticmethod
    def create_audience_segment(segment_data: Dict[str, Any], created_by: Optional[User] = None) -> AudienceSegment:
        """Create a new audience segment."""
        try:
            # Validate segment data
            advertiser_id = segment_data.get('advertiser_id')
            if not advertiser_id:
                raise AdvertiserValidationError("advertiser_id is required")
            
            advertiser = AudienceSegmentService.get_advertiser(advertiser_id)
            
            segment_name = segment_data.get('name')
            if not segment_name:
                raise AdvertiserValidationError("name is required")
            
            segment_type = segment_data.get('segment_type', 'custom')
            if segment_type not in ['pixel_based', 'behavioral', 'demographic', 'custom']:
                raise AdvertiserValidationError("Invalid segment_type")
            
            with transaction.atomic():
                # Create audience segment
                segment = AudienceSegment.objects.create(
                    advertiser=advertiser,
                    name=segment_name,
                    description=segment_data.get('description', ''),
                    segment_type=segment_type,
                    criteria=segment_data.get('criteria', {}),
                    pixel_ids=segment_data.get('pixel_ids', []),
                    rules=segment_data.get('rules', []),
                    audience_size=0,  # Will be calculated
                    status='active',
                    created_by=created_by
                )
                
                # Calculate audience size
                audience_size = AudienceSegmentService._calculate_audience_size(segment)
                segment.audience_size = audience_size
                segment.save(update_fields=['audience_size'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=created_by,
                    title='Audience Segment Created',
                    message f'Audience segment "{segment_name}" has been created with {audience_size} users.',
                    notification_type='retargeting',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    segment,
                    created_by,
                    description=f"Created audience segment: {segment_name}"
                )
                
                return segment
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error creating audience segment: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create audience segment: {str(e)}")
    
    @staticmethod
    def update_audience_size(segment_id: UUID) -> bool:
        """Update audience segment size."""
        try:
            segment = AudienceSegmentService.get_audience_segment(segment_id)
            
            # Calculate new audience size
            new_size = AudienceSegmentService._calculate_audience_size(segment)
            
            # Update segment
            segment.audience_size = new_size
            segment.updated_at = timezone.now()
            segment.save(update_fields=['audience_size', 'updated_at'])
            
            return True
            
        except AudienceSegment.DoesNotExist:
            raise AdvertiserNotFoundError(f"Audience segment {segment_id} not found")
        except Exception as e:
            logger.error(f"Error updating audience size {segment_id}: {str(e)}")
            return False
    
    @staticmethod
    def _calculate_audience_size(segment: AudienceSegment) -> int:
        """Calculate audience segment size."""
        try:
            # Mock implementation - would query actual user data
            if segment.segment_type == 'pixel_based':
                # Count unique users from pixel events
                return 1000  # Placeholder
            elif segment.segment_type == 'behavioral':
                # Count users matching behavioral criteria
                return 500   # Placeholder
            elif segment.segment_type == 'demographic':
                # Count users matching demographic criteria
                return 2000  # Placeholder
            else:
                return 100   # Placeholder
                
        except Exception as e:
            logger.error(f"Error calculating audience size: {str(e)}")
            return 0
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def get_audience_segment(segment_id: UUID) -> AudienceSegment:
        """Get audience segment by ID."""
        try:
            return AudienceSegment.objects.get(id=segment_id)
        except AudienceSegment.DoesNotExist:
            raise AdvertiserNotFoundError(f"Audience segment {segment_id} not found")


class ConversionTrackingService:
    """Service for managing conversion tracking."""
    
    @staticmethod
    def track_conversion(event_data: Dict[str, Any]) -> bool:
        """Track conversion event."""
        try:
            # Validate event data
            pixel_id = event_data.get('pixel_id')
            if not pixel_id:
                raise AdvertiserValidationError("pixel_id is required")
            
            # Get pixel
            pixel = ConversionTrackingService.get_pixel(pixel_id)
            
            # Create conversion event
            conversion_event = ConversionEvent.objects.create(
                pixel=pixel,
                retargeting_campaign=event_data.get('retargeting_campaign'),
                event_type=event_data.get('event_type', 'conversion'),
                conversion_value=Decimal(str(event_data.get('conversion_value', pixel.conversion_value))),
                user_agent=event_data.get('user_agent', ''),
                ip_address=event_data.get('ip_address', ''),
                custom_data=event_data.get('custom_data', {}),
                event_date=timezone.now()
            )
            
            # Update campaign performance
            if conversion_event.retargeting_campaign:
                ConversionTrackingService._update_campaign_performance(conversion_event)
            
            return True
            
        except RetargetingPixel.DoesNotExist:
            raise AdvertiserNotFoundError(f"Pixel {pixel_id} not found")
        except Exception as e:
            logger.error(f"Error tracking conversion: {str(e)}")
            return False
    
    @staticmethod
    def get_conversion_statistics(pixel_id: UUID, date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get conversion statistics for pixel."""
        try:
            pixel = ConversionTrackingService.get_pixel(pixel_id)
            
            # Default date range (last 30 days)
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=30)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            # Get conversion events
            conversion_events = ConversionEvent.objects.filter(
                pixel=pixel,
                event_date__date__gte=start_date,
                event_date__date__lte=end_date
            )
            
            # Calculate statistics
            total_conversions = conversion_events.count()
            total_revenue = conversion_events.aggregate(
                total=Sum('conversion_value')
            )['total'] or Decimal('0.00')
            
            daily_conversions = conversion_events.extra(
                {'date': 'date(event_date)'}
            ).values('date').annotate(
                count=Count('id'),
                revenue=Sum('conversion_value')
            ).order_by('date')
            
            return {
                'pixel_id': str(pixel_id),
                'pixel_name': pixel.name,
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'statistics': {
                    'total_conversions': total_conversions,
                    'total_revenue': float(total_revenue),
                    'average_conversion_value': float(total_revenue / total_conversions) if total_conversions > 0 else 0,
                    'conversion_rate': ConversionTrackingService._calculate_conversion_rate(pixel, start_date, end_date)
                },
                'daily_conversions': [
                    {
                        'date': item['date'].isoformat(),
                        'conversions': item['count'],
                        'revenue': float(item['revenue'])
                    }
                    for item in daily_conversions
                ]
            }
            
        except RetargetingPixel.DoesNotExist:
            raise AdvertiserNotFoundError(f"Pixel {pixel_id} not found")
        except Exception as e:
            logger.error(f"Error getting conversion statistics {pixel_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get conversion statistics: {str(e)}")
    
    @staticmethod
    def _update_campaign_performance(conversion_event: ConversionEvent) -> None:
        """Update campaign performance metrics."""
        try:
            campaign = conversion_event.retargeting_campaign
            if campaign:
                # Update campaign conversion metrics
                # This would update campaign performance counters
                pass
                
        except Exception as e:
            logger.error(f"Error updating campaign performance: {str(e)}")
    
    @staticmethod
    def _calculate_conversion_rate(pixel: RetargetingPixel, start_date: date, end_date: date) -> float:
        """Calculate conversion rate for pixel."""
        try:
            # Get total visitors and conversions for the period
            total_visitors = 1000  # Mock data
            total_conversions = ConversionEvent.objects.filter(
                pixel=pixel,
                event_date__date__gte=start_date,
                event_date__date__lte=end_date
            ).count()
            
            return (total_conversions / total_visitors * 100) if total_visitors > 0 else 0
            
        except Exception as e:
            logger.error(f"Error calculating conversion rate: {str(e)}")
            return 0
    
    @staticmethod
    def get_pixel(pixel_id: UUID) -> RetargetingPixel:
        """Get pixel by ID."""
        try:
            return RetargetingPixel.objects.get(id=pixel_id)
        except RetargetingPixel.DoesNotExist:
            raise AdvertiserNotFoundError(f"Pixel {pixel_id} not found")
