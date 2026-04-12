"""
Targeting Management Views

This module contains Django REST Framework ViewSets for managing
targeting operations, audience segments, and optimization.
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..database_models.targeting_model import Targeting, AudienceSegment, TargetingRule
from ..database_models.campaign_model import Campaign
from .services import (
    TargetingService, AudienceSegmentService, GeographicTargetingService,
    DeviceTargetingService, BehavioralTargetingService, TargetingOptimizationService
)
from .serializers import *
from ..exceptions import *
from ..utils import *


class TargetingViewSet(viewsets.ModelViewSet):
    """ViewSet for managing targeting configurations."""
    
    queryset = Targeting.objects.all()
    serializer_class = TargetingSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['geo_targeting_type', 'campaign']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'name', 'campaign']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return TargetingCreateSerializer
        elif self.action == 'update':
            return TargetingUpdateSerializer
        elif self.action in ['retrieve', 'list']:
            return TargetingDetailSerializer
        return self.serializer_class
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        # If user is not superuser, only show targetings from their advertiser
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'advertiser'):
                queryset = queryset.filter(campaign__advertiser=self.request.user.advertiser)
            else:
                # Other users see no targetings
                queryset = queryset.none()
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a new targeting configuration."""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            targeting = TargetingService.create_targeting(
                serializer.validated_data,
                created_by=request.user
            )
            
            response_serializer = TargetingDetailSerializer(targeting)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except TargetingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating targeting: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update(self, request, *args, **kwargs):
        """Update targeting configuration."""
        try:
            targeting = self.get_object()
            
            serializer = self.get_serializer(targeting, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            updated_targeting = TargetingService.update_targeting(
                targeting.id,
                serializer.validated_data,
                updated_by=request.user
            )
            
            response_serializer = TargetingDetailSerializer(updated_targeting)
            return Response(response_serializer.data)
            
        except TargetingNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except TargetingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating targeting: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def destroy(self, request, *args, **kwargs):
        """Delete targeting configuration."""
        try:
            targeting = self.get_object()
            
            success = TargetingService.delete_targeting(
                targeting.id,
                deleted_by=request.user
            )
            
            if success:
                return Response(status=status.HTTP_204_NO_CONTENT)
            else:
                return Response(
                    {'error': 'Failed to delete targeting'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except TargetingNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except TargetingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error deleting targeting: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """Validate targeting configuration."""
        try:
            targeting = self.get_object()
            validation_result = TargetingService.validate_targeting(targeting.id)
            
            return Response(validation_result)
            
        except TargetingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error validating targeting: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Get targeting summary."""
        try:
            targeting = self.get_object()
            summary = TargetingService.get_targeting_summary(targeting.id)
            
            return Response(summary)
            
        except TargetingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting targeting summary: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def estimate_reach(self, request, pk=None):
        """Estimate reach for targeting configuration."""
        try:
            targeting = self.get_object()
            reach_data = TargetingService.estimate_reach(targeting.id)
            
            return Response(reach_data)
            
        except TargetingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error estimating reach: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def calculate_score(self, request, pk=None):
        """Calculate targeting score."""
        try:
            targeting = self.get_object()
            score = TargetingService.calculate_targeting_score(targeting.id)
            
            return Response({
                'targeting_id': str(targeting.id),
                'targeting_score': score
            })
            
        except Exception as e:
            logger.error(f"Error calculating targeting score: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def check_overlap(self, request, pk=None):
        """Check overlap with another targeting configuration."""
        try:
            targeting = self.get_object()
            other_targeting_id = request.data.get('other_targeting_id')
            
            if not other_targeting_id:
                return Response(
                    {'error': 'other_targeting_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            overlap_data = TargetingService.check_targeting_overlap(
                targeting.id,
                other_targeting_id
            )
            
            return Response(overlap_data)
            
        except TargetingNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except TargetingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error checking targeting overlap: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def expand(self, request, pk=None):
        """Get targeting expansion suggestions."""
        try:
            targeting = self.get_object()
            expansion_type = request.data.get('type', 'similar')
            
            suggestions = TargetingService.expand_targeting(targeting.id, expansion_type)
            return Response(suggestions)
            
        except TargetingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error expanding targeting: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def optimize(self, request, pk=None):
        """Optimize targeting configuration."""
        try:
            targeting = self.get_object()
            optimization_type = request.data.get('type', 'auto')
            
            success = TargetingService.optimize_targeting(
                targeting.id,
                optimization_type,
                optimized_by=request.user
            )
            
            if success:
                return Response({'message': 'Targeting optimized successfully'})
            else:
                return Response(
                    {'error': 'Failed to optimize targeting'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except TargetingNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error optimizing targeting: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AudienceSegmentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing audience segments."""
    
    queryset = AudienceSegment.objects.all()
    serializer_class = AudienceSegmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['advertiser', 'segment_type', 'is_active', 'is_public']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'name', 'audience_size']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        # If user is not superuser, only show segments from their advertiser
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'advertiser'):
                queryset = queryset.filter(advertiser=self.request.user.advertiser)
            else:
                # Other users see no segments
                queryset = queryset.none()
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a new audience segment."""
        try:
            # Add advertiser ID to data if not present
            if hasattr(request.user, 'advertiser'):
                request.data['advertiser'] = request.user.advertiser.id
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            segment = AudienceSegmentService.create_audience_segment(
                serializer.validated_data,
                created_by=request.user
            )
            
            response_serializer = AudienceSegmentDetailSerializer(segment)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except TargetingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating audience segment: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update(self, request, *args, **kwargs):
        """Update audience segment."""
        try:
            segment = self.get_object()
            
            serializer = self.get_serializer(segment, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            updated_segment = AudienceSegmentService.update_audience_segment(
                segment.id,
                serializer.validated_data,
                updated_by=request.user
            )
            
            response_serializer = AudienceSegmentDetailSerializer(updated_segment)
            return Response(response_serializer.data)
            
        except TargetingNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except TargetingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating audience segment: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def destroy(self, request, *args, **kwargs):
        """Delete audience segment."""
        try:
            segment = self.get_object()
            
            success = AudienceSegmentService.delete_audience_segment(
                segment.id,
                deleted_by=request.user
            )
            
            if success:
                return Response(status=status.HTTP_204_NO_CONTENT)
            else:
                return Response(
                    {'error': 'Failed to delete audience segment'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except TargetingNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except TargetingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error deleting audience segment: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def refresh(self, request, pk=None):
        """Refresh audience segment data."""
        try:
            segment = self.get_object()
            
            success = AudienceSegmentService.refresh_audience_segment(
                segment.id,
                refreshed_by=request.user
            )
            
            if success:
                response_serializer = AudienceSegmentDetailSerializer(segment)
                return Response(response_serializer.data)
            else:
                return Response(
                    {'error': 'Failed to refresh audience segment'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except TargetingNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error refreshing audience segment: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def insights(self, request, pk=None):
        """Get insights for audience segment."""
        try:
            segment = self.get_object()
            insights = AudienceSegmentService.get_segment_insights(segment.id)
            
            return Response(insights)
            
        except TargetingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting segment insights: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GeographicTargetingViewSet(viewsets.ViewSet):
    """ViewSet for geographic targeting operations."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def countries_by_region(self, request):
        """Get countries by region."""
        try:
            region = request.query_params.get('region')
            
            if not region:
                return Response(
                    {'error': 'region parameter is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            countries = GeographicTargetingService.get_countries_by_region(region)
            return Response({'countries': countries})
            
        except Exception as e:
            logger.error(f"Error getting countries by region: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def cities_by_country(self, request):
        """Get cities by country."""
        try:
            country = request.query_params.get('country')
            
            if not country:
                return Response(
                    {'error': 'country parameter is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            cities = GeographicTargetingService.get_cities_by_country(country)
            return Response({'cities': cities})
            
        except Exception as e:
            logger.error(f"Error getting cities by country: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def validate_coordinates(self, request):
        """Validate geographic coordinates."""
        try:
            coordinates = request.data.get('coordinates', {})
            
            if not coordinates:
                return Response(
                    {'error': 'coordinates are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            is_valid = GeographicTargetingService.validate_geographic_coordinates(coordinates)
            return Response({'valid': is_valid})
            
        except Exception as e:
            logger.error(f"Error validating coordinates: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def calculate_distance(self, request):
        """Calculate distance between two points."""
        try:
            point1 = request.data.get('point1', {})
            point2 = request.data.get('point2', {})
            
            if not point1 or not point2:
                return Response(
                    {'error': 'Both point1 and point2 are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            distance = GeographicTargetingService.calculate_distance(
                point1.get('latitude', 0),
                point1.get('longitude', 0),
                point2.get('latitude', 0),
                point2.get('longitude', 0)
            )
            
            return Response({'distance': distance})
            
        except Exception as e:
            logger.error(f"Error calculating distance: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def get_timezone(self, request):
        """Get timezone by coordinates."""
        try:
            coordinates = request.data.get('coordinates', {})
            
            if not coordinates:
                return Response(
                    {'error': 'coordinates are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            timezone_str = GeographicTargetingService.get_timezone_by_coordinates(
                coordinates.get('latitude', 0),
                coordinates.get('longitude', 0)
            )
            
            return Response({'timezone': timezone_str})
            
        except Exception as e:
            logger.error(f"Error getting timezone: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def location_insights(self, request):
        """Get insights for geographic location."""
        try:
            location_data = request.data.get('location_data', {})
            
            if not location_data:
                return Response(
                    {'error': 'location_data is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            insights = GeographicTargetingService.get_location_insights(location_data)
            return Response(insights)
            
        except Exception as e:
            logger.error(f"Error getting location insights: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeviceTargetingViewSet(viewsets.ViewSet):
    """ViewSet for device targeting operations."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def device_statistics(self, request):
        """Get device statistics for campaign."""
        try:
            campaign_id = request.query_params.get('campaign_id')
            
            if not campaign_id:
                return Response(
                    {'error': 'campaign_id parameter is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            stats = DeviceTargetingService.get_device_statistics(campaign_id)
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Error getting device statistics: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def os_statistics(self, request):
        """Get operating system statistics for campaign."""
        try:
            campaign_id = request.query_params.get('campaign_id')
            
            if not campaign_id:
                return Response(
                    {'error': 'campaign_id parameter is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            stats = DeviceTargetingService.get_os_statistics(campaign_id)
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Error getting OS statistics: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def browser_statistics(self, request):
        """Get browser statistics for campaign."""
        try:
            campaign_id = request.query_params.get('campaign_id')
            
            if not campaign_id:
                return Response(
                    {'error': 'campaign_id parameter is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            stats = DeviceTargetingService.get_browser_statistics(campaign_id)
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Error getting browser statistics: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def performance_insights(self, request):
        """Get performance insights for device targeting."""
        try:
            targeting_data = request.data.get('targeting_data', {})
            
            if not targeting_data:
                return Response(
                    {'error': 'targeting_data is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            insights = DeviceTargetingService.get_device_performance_insights(targeting_data)
            return Response(insights)
            
        except Exception as e:
            logger.error(f"Error getting device performance insights: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BehavioralTargetingViewSet(viewsets.ViewSet):
    """ViewSet for behavioral targeting operations."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def create_segment(self, request):
        """Create behavioral targeting segment."""
        try:
            segment = BehavioralTargetingService.create_behavioral_segment(
                request.data,
                created_by=request.user
            )
            return Response(segment, status=status.HTTP_201_CREATED)
            
        except TargetingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating behavioral segment: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def behavioral_patterns(self, request):
        """Get behavioral patterns for user."""
        try:
            user_id = request.query_params.get('user_id')
            time_range = {
                'start_date': request.query_params.get('start_date'),
                'end_date': request.query_params.get('end_date')
            }
            
            if not user_id:
                return Response(
                    {'error': 'user_id parameter is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            patterns = BehavioralTargetingService.get_behavioral_patterns(user_id, time_range)
            return Response(patterns)
            
        except Exception as e:
            logger.error(f"Error getting behavioral patterns: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def interest_affinity(self, request):
        """Get interest affinity scores."""
        try:
            interests = request.data.get('interests', [])
            
            if not interests:
                return Response(
                    {'error': 'interests list is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            affinity = BehavioralTargetingService.get_interest_affinity(interests)
            return Response(affinity)
            
        except Exception as e:
            logger.error(f"Error getting interest affinity: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TargetingOptimizationViewSet(viewsets.ViewSet):
    """ViewSet for targeting optimization operations."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def optimize_configuration(self, request):
        """Optimize targeting configuration."""
        try:
            targeting_id = request.data.get('targeting_id')
            optimization_goals = request.data.get('optimization_goals', [])
            
            if not targeting_id:
                return Response(
                    {'error': 'targeting_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            result = TargetingOptimizationService.optimize_targeting_configuration(
                targeting_id,
                optimization_goals,
                optimized_by=request.user
            )
            
            return Response(result)
            
        except TargetingNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except TargetingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error optimizing targeting configuration: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def optimization_report(self, request):
        """Get targeting optimization report."""
        try:
            targeting_id = request.query_params.get('targeting_id')
            
            if not targeting_id:
                return Response(
                    {'error': 'targeting_id parameter is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            report = TargetingOptimizationService.get_targeting_optimization_report(targeting_id)
            return Response(report)
            
        except TargetingNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except TargetingServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting targeting optimization report: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
