"""
Tracking Pixel ViewSet

ViewSet for tracking pixel management,
including generation, testing, and analytics.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q

from ..models.tracking import TrackingPixel
try:
    from ..services import TrackingPixelService
except ImportError:
    TrackingPixelService = None
from ..serializers import TrackingPixelSerializer
from ..permissions import IsAdvertiserOrReadOnly, IsOwnerOrReadOnly
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class TrackingPixelViewSet(viewsets.ModelViewSet):
    """
    ViewSet for tracking pixel management.
    
    Handles pixel generation, testing, firing,
    and analytics tracking.
    """
    
    queryset = TrackingPixel.objects.all()
    serializer_class = TrackingPixelSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdvertiserOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        if user.is_staff:
            # Admin can see all pixels
            return TrackingPixel.objects.all()
        else:
            # Advertisers can only see their own pixels
            return TrackingPixel.objects.filter(advertiser__user=user)
    
    def perform_create(self, serializer):
        """Create pixel with associated advertiser."""
        user = self.request.user
        
        # Get advertiser for user
        from ..models.advertiser import Advertiser
        advertiser = get_object_or_404(Advertiser, user=user)
        
        pixel_service = TrackingPixelService()
        pixel = pixel_service.create_tracking_pixel(advertiser, serializer.validated_data)
        serializer.instance = pixel
    
    @action(detail=True, methods=['get'])
    def generate_code(self, request, pk=None):
        """
        Generate tracking pixel code.
        
        Returns pixel code in various formats.
        """
        pixel = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or pixel.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        format_type = request.query_params.get('format', 'html')
        
        try:
            pixel_service = TrackingPixelService()
            pixel_code = pixel_service.get_pixel_code(pixel, format_type)
            
            return Response({
                'pixel_id': pixel.id,
                'pixel_name': pixel.name,
                'pixel_type': pixel.pixel_type,
                'format': format_type,
                'code': pixel_code,
                'pixel_url': pixel.pixel_url,
                'generated_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error generating pixel code: {e}")
            return Response(
                {'detail': 'Failed to generate pixel code'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        Test tracking pixel.
        
        Validates pixel configuration and functionality.
        """
        pixel = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or pixel.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            pixel_service = TrackingPixelService()
            test_result = pixel_service.test_pixel(pixel)
            
            return Response(test_result)
            
        except Exception as e:
            logger.error(f"Error testing pixel: {e}")
            return Response(
                {'detail': 'Failed to test pixel'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def fire(self, request, pk=None):
        """
        Fire tracking pixel.
        
        Simulates pixel firing with test data.
        """
        pixel = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or pixel.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        context = request.data.get('context', {})
        
        try:
            pixel_service = TrackingPixelService()
            fire_result = pixel_service.fire_pixel(pixel.pixel_code, context)
            
            return Response(fire_result)
            
        except Exception as e:
            logger.error(f"Error firing pixel: {e}")
            return Response(
                {'detail': 'Failed to fire pixel'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def regenerate_code(self, request, pk=None):
        """
        Regenerate pixel code.
        
        Creates new pixel code and updates configuration.
        """
        pixel = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or pixel.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            pixel_service = TrackingPixelService()
            
            # Generate new pixel code
            import secrets
            timestamp = str(int(timezone.now().timestamp()))
            random_str = secrets.token_hex(4)
            new_pixel_code = f"px_{timestamp}_{random_str}"
            
            pixel.pixel_code = new_pixel_code
            pixel_service._generate_default_pixel_code(pixel)
            pixel.save()
            
            return Response({
                'detail': 'Pixel code regenerated successfully',
                'pixel_code': new_pixel_code,
                'pixel_url': pixel.pixel_url
            })
            
        except Exception as e:
            logger.error(f"Error regenerating pixel code: {e}")
            return Response(
                {'detail': 'Failed to regenerate pixel code'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_settings(self, request, pk=None):
        """
        Update pixel settings.
        
        Updates firing configuration and options.
        """
        pixel = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or pixel.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Update pixel settings
            settings = request.data.get('settings', {})
            
            if 'fire_on' in settings:
                pixel.fire_on = settings['fire_on']
            
            if 'is_secure' in settings:
                pixel.is_secure = settings['is_secure']
            
            if 'async_firing' in settings:
                pixel.async_firing = settings['async_firing']
            
            if 'delay_ms' in settings:
                pixel.delay_ms = settings['delay_ms']
            
            if 'timeout_ms' in settings:
                pixel.timeout_ms = settings['timeout_ms']
            
            if 'custom_parameters' in settings:
                pixel.custom_parameters = settings['custom_parameters']
            
            pixel.save()
            
            # Regenerate code if needed
            if settings.get('regenerate_code', False):
                pixel_service = TrackingPixelService()
                pixel_service._generate_default_pixel_code(pixel)
                pixel.save()
            
            serializer = self.get_serializer(pixel)
            return Response({
                'detail': 'Pixel settings updated successfully',
                'pixel': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error updating pixel settings: {e}")
            return Response(
                {'detail': 'Failed to update pixel settings'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        """
        Enable tracking pixel.
        
        Makes pixel active for firing.
        """
        pixel = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or pixel.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            pixel.is_active = True
            pixel.save()
            
            return Response({
                'detail': 'Pixel enabled successfully',
                'is_active': True
            })
            
        except Exception as e:
            logger.error(f"Error enabling pixel: {e}")
            return Response(
                {'detail': 'Failed to enable pixel'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        """
        Disable tracking pixel.
        
        Makes pixel inactive.
        """
        pixel = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or pixel.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            pixel.is_active = False
            pixel.save()
            
            return Response({
                'detail': 'Pixel disabled successfully',
                'is_active': False
            })
            
        except Exception as e:
            logger.error(f"Error disabling pixel: {e}")
            return Response(
                {'detail': 'Failed to disable pixel'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """
        Get pixel analytics.
        
        Returns firing statistics and performance metrics.
        """
        pixel = self.get_object()
        
        try:
            pixel_service = TrackingPixelService()
            analytics = pixel_service.get_pixel_analytics(pixel)
            
            return Response(analytics)
            
        except Exception as e:
            logger.error(f"Error getting pixel analytics: {e}")
            return Response(
                {'detail': 'Failed to get analytics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def firing_history(self, request, pk=None):
        """
        Get pixel firing history.
        
        Returns recent firing events and statistics.
        """
        pixel = self.get_object()
        
        days = request.query_params.get('days', 7)
        
        try:
            # This would implement actual firing history tracking
            # For now, return placeholder data
            history = {
                'pixel_id': pixel.id,
                'pixel_name': pixel.name,
                'pixel_type': pixel.pixel_type,
                'period_days': int(days),
                'total_fires': 0,
                'successful_fires': 0,
                'failed_fires': 0,
                'success_rate': 0.0,
                'average_response_time': 0.0,
                'daily_breakdown': {},
                'recent_fires': [],
            }
            
            return Response(history)
            
        except Exception as e:
            logger.error(f"Error getting firing history: {e}")
            return Response(
                {'detail': 'Failed to get firing history'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """
        Get pixel preview.
        
        Returns pixel preview information and code samples.
        """
        pixel = self.get_object()
        
        try:
            pixel_service = TrackingPixelService()
            
            # Get code in different formats
            html_code = pixel_service.get_pixel_code(pixel, 'html')
            js_code = pixel_service.get_pixel_code(pixel, 'js')
            img_code = pixel_service.get_pixel_code(pixel, 'img')
            url_code = pixel_service.get_pixel_code(pixel, 'url')
            
            preview_data = {
                'pixel_id': pixel.id,
                'pixel_name': pixel.name,
                'pixel_type': pixel.pixel_type,
                'pixel_code': pixel.pixel_code,
                'pixel_url': pixel.pixel_url,
                'fire_on': pixel.fire_on,
                'is_active': pixel.is_active,
                'is_secure': pixel.is_secure,
                'code_samples': {
                    'html': html_code,
                    'javascript': js_code,
                    'image': img_code,
                    'url': url_code,
                },
                'settings': {
                    'async_firing': pixel.async_firing,
                    'delay_ms': pixel.delay_ms,
                    'timeout_ms': pixel.timeout_ms,
                    'custom_parameters': pixel.custom_parameters,
                },
                'created_at': pixel.created_at.isoformat(),
            }
            
            return Response(preview_data)
            
        except Exception as e:
            logger.error(f"Error getting pixel preview: {e}")
            return Response(
                {'detail': 'Failed to get preview'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def pixel_types(self, request):
        """
        Get available pixel types.
        
        Returns list of supported pixel types and their configurations.
        """
        try:
            pixel_types = {
                'impression': {
                    'name': 'Impression Pixel',
                    'description': 'Tracks page impressions',
                    'default_fire_on': 'page_load',
                    'common_use': 'Page view tracking',
                },
                'click': {
                    'name': 'Click Pixel',
                    'description': 'Tracks click events',
                    'default_fire_on': 'click',
                    'common_use': 'Link click tracking',
                },
                'conversion': {
                    'name': 'Conversion Pixel',
                    'description': 'Tracks conversion events',
                    'default_fire_on': 'page_load',
                    'common_use': 'Conversion tracking',
                },
                'lead': {
                    'name': 'Lead Pixel',
                    'description': 'Tracks lead generation',
                    'default_fire_on': 'page_load',
                    'common_use': 'Lead form tracking',
                },
                'sale': {
                    'name': 'Sale Pixel',
                    'description': 'Tracks sales transactions',
                    'default_fire_on': 'page_load',
                    'common_use': 'Purchase tracking',
                },
                'custom': {
                    'name': 'Custom Pixel',
                    'description': 'Custom tracking pixel',
                    'default_fire_on': 'page_load',
                    'common_use': 'Custom event tracking',
                },
            }
            
            return Response(pixel_types)
            
        except Exception as e:
            logger.error(f"Error getting pixel types: {e}")
            return Response(
                {'detail': 'Failed to get pixel types'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def fire_options(self, request):
        """
        Get available fire options.
        
        Returns list of supported firing triggers and options.
        """
        try:
            fire_options = {
                'page_load': {
                    'name': 'Page Load',
                    'description': 'Fires when page loads',
                    'suitable_for': ['impression', 'conversion', 'lead', 'sale'],
                },
                'click': {
                    'name': 'Click Event',
                    'description': 'Fires when element is clicked',
                    'suitable_for': ['click', 'conversion'],
                },
                'form_submit': {
                    'name': 'Form Submit',
                    'description': 'Fires when form is submitted',
                    'suitable_for': ['lead', 'conversion'],
                },
                'scroll': {
                    'name': 'Scroll Event',
                    'description': 'Fires when user scrolls',
                    'suitable_for': ['impression', 'engagement'],
                },
                'exit_intent': {
                    'name': 'Exit Intent',
                    'description': 'Fires when user attempts to leave',
                    'suitable_for': ['lead', 'conversion'],
                },
                'custom': {
                    'name': 'Custom Event',
                    'description': 'Fires on custom JavaScript event',
                    'suitable_for': ['custom'],
                },
            }
            
            return Response(fire_options)
            
        except Exception as e:
            logger.error(f"Error getting fire options: {e}")
            return Response(
                {'detail': 'Failed to get fire options'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def validate_pixel_config(self, request):
        """
        Validate pixel configuration.
        
        Checks for logical errors and best practices.
        """
        config = request.data.get('config', {})
        
        if not config:
            return Response(
                {'detail': 'No configuration provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            validation_results = {
                'is_valid': True,
                'errors': [],
                'warnings': [],
                'recommendations': [],
            }
            
            # Check required fields
            required_fields = ['name', 'pixel_type']
            for field in required_fields:
                if field not in config:
                    validation_results['errors'].append(f'Missing required field: {field}')
                    validation_results['is_valid'] = False
            
            # Check pixel type
            pixel_type = config.get('pixel_type')
            if pixel_type:
                valid_types = ['impression', 'click', 'conversion', 'lead', 'sale', 'custom']
                if pixel_type not in valid_types:
                    validation_results['errors'].append(f'Invalid pixel type: {pixel_type}')
                    validation_results['is_valid'] = False
            
            # Check fire on option
            fire_on = config.get('fire_on')
            if fire_on:
                valid_fire_options = ['page_load', 'click', 'form_submit', 'scroll', 'exit_intent', 'custom']
                if fire_on not in valid_fire_options:
                    validation_results['errors'].append(f'Invalid fire option: {fire_on}')
                    validation_results['is_valid'] = False
            
            # Check delay and timeout
            delay_ms = config.get('delay_ms')
            if delay_ms is not None and delay_ms < 0:
                validation_results['errors'].append('Delay cannot be negative')
                validation_results['is_valid'] = False
            elif delay_ms is not None and delay_ms > 10000:
                validation_results['warnings'].append('Very long delay may affect user experience')
            
            timeout_ms = config.get('timeout_ms')
            if timeout_ms is not None and timeout_ms <= 0:
                validation_results['errors'].append('Timeout must be positive')
                validation_results['is_valid'] = False
            elif timeout_ms is not None and timeout_ms > 30000:
                validation_results['warnings'].append('Very long timeout may affect performance')
            
            # Generate recommendations
            if validation_results['is_valid']:
                if not config.get('is_secure', True):
                    validation_results['recommendations'].append('Consider using HTTPS for better security')
                
                if not config.get('async_firing', True):
                    validation_results['recommendations'].append('Consider using async firing for better performance')
                
                if not config.get('timeout_ms'):
                    validation_results['recommendations'].append('Set a timeout to prevent hanging requests')
            
            return Response(validation_results)
            
        except Exception as e:
            logger.error(f"Error validating pixel config: {e}")
            return Response(
                {'detail': 'Failed to validate configuration'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_test(self, request):
        """
        Bulk test multiple pixels.
        
        Only staff members can perform this action.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        pixel_ids = request.data.get('pixel_ids', [])
        
        if not pixel_ids:
            return Response(
                {'detail': 'No pixel IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            pixel_service = TrackingPixelService()
            
            results = {
                'tested': 0,
                'failed': 0,
                'errors': []
            }
            
            for pixel_id in pixel_ids:
                try:
                    pixel = TrackingPixel.objects.get(id=pixel_id)
                    test_result = pixel_service.test_pixel(pixel)
                    
                    if test_result.get('overall_status') == 'passed':
                        results['tested'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append({
                            'pixel_id': pixel_id,
                            'error': 'Test failed',
                            'issues': test_result.get('issues', [])
                        })
                        
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'pixel_id': pixel_id,
                        'error': str(e)
                    })
            
            return Response(results)
            
        except Exception as e:
            logger.error(f"Error in bulk test: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def list(self, request, *args, **kwargs):
        """
        Override list to add filtering capabilities.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply additional filters
        advertiser_id = request.query_params.get('advertiser_id')
        pixel_type = request.query_params.get('pixel_type')
        is_active = request.query_params.get('is_active')
        is_secure = request.query_params.get('is_secure')
        search = request.query_params.get('search')
        
        if advertiser_id:
            queryset = queryset.filter(advertiser_id=advertiser_id)
        
        if pixel_type:
            queryset = queryset.filter(pixel_type=pixel_type)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        if is_secure is not None:
            queryset = queryset.filter(is_secure=is_secure.lower() == 'true')
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(pixel_code__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
