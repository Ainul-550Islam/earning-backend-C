"""
Retargeting Engines Views

This module provides DRF ViewSets for retargeting operations including
pixel management, audience segmentation, retargeting campaigns, and conversion tracking.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.retargeting_model import RetargetingPixel, AudienceSegment, RetargetingCampaign, ConversionEvent
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *
from .services import (
    RetargetingService, PixelService, AudienceSegmentService, ConversionTrackingService
)

User = get_user_model()


class RetargetingViewSet(viewsets.ModelViewSet):
    """ViewSet for managing retargeting campaigns."""
    
    queryset = RetargetingCampaign.objects.all()
    serializer_class = None  # Will be set in serializers.py
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['advertiser', 'retargeting_type', 'status']
    
    def get_queryset(self):
        """Filter retargeting campaigns by advertiser."""
        user = self.request.user
        if user.is_superuser:
            return RetargetingCampaign.objects.all()
        
        try:
            advertiser = Advertiser.objects.get(user=user, is_deleted=False)
            return RetargetingCampaign.objects.filter(advertiser=advertiser)
        except Advertiser.DoesNotExist:
            return RetargetingCampaign.objects.none()
    
    def create(self, request, *args, **kwargs):
        """Create a new retargeting campaign."""
        try:
            campaign_data = request.data
            campaign = RetargetingService.create_retargeting_campaign(campaign_data, request.user)
            
            response_data = {
                'id': str(campaign.id),
                'advertiser_id': str(campaign.advertiser.id),
                'name': campaign.name,
                'description': campaign.description,
                'retargeting_type': campaign.retargeting_type,
                'pixel_id': str(campaign.pixel_id) if campaign.pixel_id else None,
                'audience_segment_id': str(campaign.audience_segment.id) if campaign.audience_segment else None,
                'targeting_rules': campaign.targeting_rules,
                'budget_limits': campaign.budget_limits,
                'frequency_capping': campaign.frequency_capping,
                'duration_days': campaign.duration_days,
                'status': campaign.status,
                'created_at': campaign.created_at.isoformat()
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating retargeting campaign: {str(e)}")
            return Response({'error': 'Failed to create retargeting campaign'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate retargeting campaign."""
        try:
            campaign_id = UUID(pk)
            success = RetargetingService.activate_retargeting_campaign(campaign_id, request.user)
            
            if success:
                return Response({'message': 'Retargeting campaign activated'}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Failed to activate campaign'}, status=status.HTTP_400_BAD_REQUEST)
                
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error activating retargeting campaign: {str(e)}")
            return Response({'error': 'Failed to activate campaign'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause retargeting campaign."""
        try:
            campaign = self.get_object()
            campaign.status = 'paused'
            campaign.paused_at = timezone.now()
            campaign.paused_by = request.user
            campaign.save(update_fields=['status', 'paused_at', 'paused_by'])
            
            return Response({'message': 'Retargeting campaign paused'}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error pausing retargeting campaign: {str(e)}")
            return Response({'error': 'Failed to pause campaign'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get retargeting campaign performance."""
        try:
            campaign_id = UUID(pk)
            date_range = request.query_params.dict()
            
            performance_data = RetargetingService.get_retargeting_performance(campaign_id, date_range)
            
            return Response(performance_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting retargeting performance: {str(e)}")
            return Response({'error': 'Failed to get performance'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get retargeting statistics."""
        try:
            user = request.user
            if user.is_superuser:
                campaigns = RetargetingCampaign.objects.all()
            else:
                advertiser = Advertiser.objects.get(user=user, is_deleted=False)
                campaigns = RetargetingCampaign.objects.filter(advertiser=advertiser)
            
            # Calculate statistics
            total_campaigns = campaigns.count()
            active_campaigns = campaigns.filter(status='active').count()
            
            # Calculate by type
            campaigns_by_type = {}
            for retargeting_type in ['pixel', 'email', 'crm', 'custom']:
                count = campaigns.filter(retargeting_type=retargeting_type).count()
                campaigns_by_type[retargeting_type] = count
            
            return Response({
                'total_campaigns': total_campaigns,
                'active_campaigns': active_campaigns,
                'campaigns_by_type': campaigns_by_type
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting retargeting statistics: {str(e)}")
            return Response({'error': 'Failed to get statistics'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PixelViewSet(viewsets.ModelViewSet):
    """ViewSet for managing retargeting pixels."""
    
    queryset = RetargetingPixel.objects.all()
    serializer_class = None  # Will be set in serializers.py
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['advertiser', 'pixel_type', 'status']
    
    def get_queryset(self):
        """Filter pixels by advertiser."""
        user = self.request.user
        if user.is_superuser:
            return RetargetingPixel.objects.all()
        
        try:
            advertiser = Advertiser.objects.get(user=user, is_deleted=False)
            return RetargetingPixel.objects.filter(advertiser=advertiser)
        except Advertiser.DoesNotExist:
            return RetargetingPixel.objects.none()
    
    def create(self, request, *args, **kwargs):
        """Create a new retargeting pixel."""
        try:
            pixel_data = request.data
            pixel = PixelService.create_pixel(pixel_data, request.user)
            
            response_data = {
                'id': str(pixel.id),
                'advertiser_id': str(pixel.advertiser.id),
                'name': pixel.name,
                'description': pixel.description,
                'pixel_type': pixel.pixel_type,
                'pixel_code': pixel.pixel_code,
                'tracking_url': pixel.tracking_url,
                'conversion_value': float(pixel.conversion_value),
                'status': pixel.status,
                'created_at': pixel.created_at.isoformat()
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating retargeting pixel: {str(e)}")
            return Response({'error': 'Failed to create retargeting pixel'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def code(self, request, pk=None):
        """Get pixel tracking code."""
        try:
            pixel_id = UUID(pk)
            pixel_code_data = PixelService.get_pixel_code(pixel_id)
            
            return Response(pixel_code_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting pixel code: {str(e)}")
            return Response({'error': 'Failed to get pixel code'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def track(self, request, pk=None):
        """Track pixel event."""
        try:
            pixel_id = UUID(pk)
            event_data = request.data
            
            success = PixelService.track_pixel_event(pixel_id, event_data)
            
            if success:
                return Response({'message': 'Pixel event tracked successfully'}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Failed to track pixel event'}, status=status.HTTP_400_BAD_REQUEST)
                
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error tracking pixel event: {str(e)}")
            return Response({'error': 'Failed to track pixel event'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate pixel."""
        try:
            pixel = self.get_object()
            pixel.status = 'active'
            pixel.save(update_fields=['status'])
            
            return Response({'message': 'Pixel activated'}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error activating pixel: {str(e)}")
            return Response({'error': 'Failed to activate pixel'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate pixel."""
        try:
            pixel = self.get_object()
            pixel.status = 'inactive'
            pixel.save(update_fields=['status'])
            
            return Response({'message': 'Pixel deactivated'}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error deactivating pixel: {str(e)}")
            return Response({'error': 'Failed to deactivate pixel'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AudienceSegmentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing audience segments."""
    
    queryset = AudienceSegment.objects.all()
    serializer_class = None  # Will be set in serializers.py
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['advertiser', 'segment_type', 'status']
    
    def get_queryset(self):
        """Filter audience segments by advertiser."""
        user = self.request.user
        if user.is_superuser:
            return AudienceSegment.objects.all()
        
        try:
            advertiser = Advertiser.objects.get(user=user, is_deleted=False)
            return AudienceSegment.objects.filter(advertiser=advertiser)
        except Advertiser.DoesNotExist:
            return AudienceSegment.objects.none()
    
    def create(self, request, *args, **kwargs):
        """Create a new audience segment."""
        try:
            segment_data = request.data
            segment = AudienceSegmentService.create_audience_segment(segment_data, request.user)
            
            response_data = {
                'id': str(segment.id),
                'advertiser_id': str(segment.advertiser.id),
                'name': segment.name,
                'description': segment.description,
                'segment_type': segment.segment_type,
                'criteria': segment.criteria,
                'pixel_ids': segment.pixel_ids,
                'rules': segment.rules,
                'audience_size': segment.audience_size,
                'status': segment.status,
                'created_at': segment.created_at.isoformat()
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating audience segment: {str(e)}")
            return Response({'error': 'Failed to create audience segment'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def update_size(self, request, pk=None):
        """Update audience segment size."""
        try:
            segment_id = UUID(pk)
            success = AudienceSegmentService.update_audience_size(segment_id)
            
            if success:
                segment = AudienceSegmentService.get_audience_segment(segment_id)
                return Response({
                    'message': 'Audience size updated',
                    'audience_size': segment.audience_size
                }, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Failed to update audience size'}, status=status.HTTP_400_BAD_REQUEST)
                
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error updating audience size: {str(e)}")
            return Response({'error': 'Failed to update audience size'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def insights(self, request, pk=None):
        """Get audience segment insights."""
        try:
            segment = self.get_object()
            
            # Mock insights data
            insights = {
                'segment_id': str(segment.id),
                'segment_name': segment.name,
                'audience_size': segment.audience_size,
                'demographics': {
                    'age_groups': {'18-24': 20, '25-34': 35, '35-44': 25, '45-54': 15, '55+': 5},
                    'genders': {'male': 55, 'female': 45},
                    'locations': {'US': 60, 'UK': 20, 'CA': 10, 'Other': 10}
                },
                'behavior': {
                    'avg_session_duration': 180,  # seconds
                    'pages_per_session': 3.5,
                    'bounce_rate': 45.2
                },
                'engagement': {
                    'click_through_rate': 2.5,
                    'conversion_rate': 1.8,
                    'return_visitor_rate': 65.3
                }
            }
            
            return Response(insights, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting audience insights: {str(e)}")
            return Response({'error': 'Failed to get insights'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConversionTrackingViewSet(viewsets.ViewSet):
    """ViewSet for conversion tracking."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def track(self, request):
        """Track conversion event."""
        try:
            event_data = request.data
            success = ConversionTrackingService.track_conversion(event_data)
            
            if success:
                return Response({'message': 'Conversion tracked successfully'}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Failed to track conversion'}, status=status.HTTP_400_BAD_REQUEST)
                
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error tracking conversion: {str(e)}")
            return Response({'error': 'Failed to track conversion'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get conversion statistics."""
        try:
            pixel_id = request.query_params.get('pixel_id')
            if not pixel_id:
                return Response({'error': 'pixel_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            date_range = request.query_params.dict()
            statistics_data = ConversionTrackingService.get_conversion_statistics(
                UUID(pixel_id), date_range
            )
            
            return Response(statistics_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting conversion statistics: {str(e)}")
            return Response({'error': 'Failed to get statistics'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def pixels(self, request):
        """Get pixels for conversion tracking."""
        try:
            user = request.user
            if user.is_superuser:
                pixels = RetargetingPixel.objects.all()
            else:
                advertiser = Advertiser.objects.get(user=user, is_deleted=False)
                pixels = RetargetingPixel.objects.filter(advertiser=advertiser)
            
            pixel_data = []
            for pixel in pixels:
                pixel_data.append({
                    'id': str(pixel.id),
                    'name': pixel.name,
                    'pixel_type': pixel.pixel_type,
                    'pixel_code': pixel.pixel_code,
                    'status': pixel.status,
                    'created_at': pixel.created_at.isoformat()
                })
            
            return Response({'pixels': pixel_data}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting pixels: {str(e)}")
            return Response({'error': 'Failed to get pixels'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
