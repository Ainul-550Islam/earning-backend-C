"""
Targeting Viewsets for Offer Routing System

This module contains viewsets for managing targeting rules
including geographic, device, user segment, time, and behavioral targeting.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q
from ..models import (
    GeoRouteRule, DeviceRouteRule, UserSegmentRule,
    TimeRouteRule, BehaviorRouteRule
)
from ..permissions import IsAuthenticatedOrReadOnly, CanManageRoutes
from ..exceptions import ValidationError

User = get_user_model()


class GeoRouteRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing geographic targeting rules.
    
    Provides CRUD operations for geographic targeting rules
    with validation and testing capabilities.
    """
    
    queryset = GeoRouteRule.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageRoutes]
    
    def get_queryset(self):
        """Filter rules by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(route__tenant=self.request.user)
        return queryset.order_by('route__priority', 'route__name')
    
    @action(detail=True, methods=['post'])
    def test_rule(self, request, pk=None):
        """Test geographic rule with sample location data."""
        try:
            rule = self.get_object()
            
            # Get test location data
            test_location = request.data.get('location', {})
            if not test_location:
                return Response({
                    'success': False,
                    'error': 'Location data is required for testing'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Test rule
            from ..services.targeting import geo_targeting_service
            
            # Create mock user and context
            mock_context = {'location': test_location}
            mock_user = User.objects.first() or request.user
            
            matches = geo_targeting_service._matches_geo_rule(rule, test_location)
            
            return Response({
                'success': True,
                'rule_id': rule.id,
                'rule_name': rule.route.name,
                'test_location': test_location,
                'matches': matches,
                'is_include': rule.is_include
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def supported_countries(self, request):
        """Get list of supported countries for geographic targeting."""
        try:
            # This would return actual supported countries
            # For now, return placeholder data
            countries = [
                {'code': 'US', 'name': 'United States'},
                {'code': 'GB', 'name': 'United Kingdom'},
                {'code': 'CA', 'name': 'Canada'},
                {'code': 'AU', 'name': 'Australia'},
                {'code': 'DE', 'name': 'Germany'},
                {'code': 'FR', 'name': 'France'},
                {'code': 'JP', 'name': 'Japan'},
                {'code': 'CN', 'name': 'China'},
                {'code': 'IN', 'name': 'India'},
                {'code': 'BR', 'name': 'Brazil'}
            ]
            
            return Response({
                'success': True,
                'countries': countries
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeviceRouteRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing device targeting rules.
    
    Provides CRUD operations for device-based targeting rules
    with validation and testing capabilities.
    """
    
    queryset = DeviceRouteRule.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageRoutes]
    
    def get_queryset(self):
        """Filter rules by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(route__tenant=self.request.user)
        return queryset.order_by('route__priority', 'route__name')
    
    @action(detail=True, methods=['post'])
    def test_rule(self, request, pk=None):
        """Test device rule with sample device data."""
        try:
            rule = self.get_object()
            
            # Get test device data
            test_device = request.data.get('device', {})
            if not test_device:
                return Response({
                    'success': False,
                    'error': 'Device data is required for testing'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Test rule
            from ..services.targeting import device_targeting_service
            
            matches = device_targeting_service._matches_device_rule(rule, test_device)
            
            return Response({
                'success': True,
                'rule_id': rule.id,
                'rule_name': rule.route.name,
                'test_device': test_device,
                'matches': matches,
                'is_include': rule.is_include
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def supported_devices(self, request):
        """Get list of supported device types and operating systems."""
        try:
            device_types = [
                {'value': 'desktop', 'label': 'Desktop'},
                {'value': 'mobile', 'label': 'Mobile'},
                {'value': 'tablet', 'label': 'Tablet'},
                {'value': 'smart_tv', 'label': 'Smart TV'},
                {'value': 'game_console', 'label': 'Game Console'}
            ]
            
            os_types = [
                {'value': 'windows', 'label': 'Windows'},
                {'value': 'macos', 'label': 'macOS'},
                {'value': 'linux', 'label': 'Linux'},
                {'value': 'ios', 'label': 'iOS'},
                {'value': 'android', 'label': 'Android'},
                {'value': 'chrome_os', 'label': 'Chrome OS'}
            ]
            
            browsers = [
                {'value': 'chrome', 'label': 'Chrome'},
                {'value': 'firefox', 'label': 'Firefox'},
                {'value': 'safari', 'label': 'Safari'},
                {'value': 'edge', 'label': 'Edge'},
                {'value': 'opera', 'label': 'Opera'},
                {'value': 'ie', 'label': 'Internet Explorer'}
            ]
            
            return Response({
                'success': True,
                'device_types': device_types,
                'os_types': os_types,
                'browsers': browsers
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserSegmentRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user segment targeting rules.
    
    Provides CRUD operations for user segment-based targeting rules
    with validation and testing capabilities.
    """
    
    queryset = UserSegmentRule.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageRoutes]
    
    def get_queryset(self):
        """Filter rules by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(route__tenant=self.request.user)
        return queryset.order_by('route__priority', 'route__name')
    
    @action(detail=True, methods=['post'])
    def test_rule(self, request, pk=None):
        """Test user segment rule with sample user data."""
        try:
            rule = self.get_object()
            
            # Get test user data
            test_user_id = request.data.get('user_id')
            test_segment_info = request.data.get('segment_info', {})
            
            if not test_user_id:
                return Response({
                    'success': False,
                    'error': 'User ID is required for testing'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get test user
            try:
                test_user = User.objects.get(id=test_user_id)
                if test_user.tenant != request.user:
                    return Response({
                        'success': False,
                        'error': 'User not found in your tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Test user not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Test rule
            from ..services.targeting import segment_targeting_service
            
            matches = segment_targeting_service._matches_segment_rule(
                rule, test_user, test_segment_info
            )
            
            return Response({
                'success': True,
                'rule_id': rule.id,
                'rule_name': rule.route.name,
                'test_user_id': test_user_id,
                'test_segment_info': test_segment_info,
                'matches': matches
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def supported_segments(self, request):
        """Get list of supported user segment types."""
        try:
            segment_types = [
                {'value': 'tier', 'label': 'User Tier'},
                {'value': 'new_user', 'label': 'New User'},
                {'value': 'active_user', 'label': 'Active User'},
                {'value': 'premium_user', 'label': 'Premium User'},
                {'value': 'churned_user', 'label': 'Churned User'},
                {'value': 'engaged_user', 'label': 'Engaged User'},
                {'value': 'inactive_user', 'label': 'Inactive User'}
            ]
            
            operators = [
                {'value': 'equals', 'label': 'Equals'},
                {'value': 'not_equals', 'label': 'Not Equals'},
                {'value': 'in', 'label': 'In'},
                {'value': 'not_in', 'label': 'Not In'},
                {'value': 'contains', 'label': 'Contains'},
                {'value': 'not_contains', 'label': 'Not Contains'}
            ]
            
            return Response({
                'success': True,
                'segment_types': segment_types,
                'operators': operators
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def segment_values(self, request):
        """Get available values for a specific segment type."""
        try:
            segment_type = request.query_params.get('segment_type')
            if not segment_type:
                return Response({
                    'success': False,
                    'error': 'segment_type parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get values based on segment type
            values = []
            
            if segment_type == 'tier':
                values = [
                    {'value': 'basic', 'label': 'Basic'},
                    {'value': 'premium', 'label': 'Premium'},
                    {'value': 'enterprise', 'label': 'Enterprise'}
                ]
            elif segment_type == 'new_user':
                values = [
                    {'value': True, 'label': 'Yes'},
                    {'value': False, 'label': 'No'}
                ]
            elif segment_type == 'active_user':
                values = [
                    {'value': True, 'label': 'Yes'},
                    {'value': False, 'label': 'No'}
                ]
            elif segment_type == 'premium_user':
                values = [
                    {'value': True, 'label': 'Yes'},
                    {'value': False, 'label': 'No'}
                ]
            # Add more segment types as needed
            
            return Response({
                'success': True,
                'segment_type': segment_type,
                'values': values
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TimeRouteRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing time-based targeting rules.
    
    Provides CRUD operations for time-based targeting rules
    with validation and testing capabilities.
    """
    
    queryset = TimeRouteRule.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageRoutes]
    
    def get_queryset(self):
        """Filter rules by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(route__tenant=self.request.user)
        return queryset.order_by('route__priority', 'route__name')
    
    @action(detail=True, methods=['post'])
    def test_rule(self, request, pk=None):
        """Test time rule with sample time data."""
        try:
            rule = self.get_object()
            
            # Get test time data
            test_time = request.data.get('time')
            if not test_time:
                # Use current time if not provided
                test_time = timezone.now()
            else:
                # Parse time string
                from datetime import datetime
                test_time = datetime.fromisoformat(test_time.replace('Z', '+00:00'))
            
            # Test rule
            current_hour = test_time.hour
            current_day_of_week = test_time.weekday()
            
            matches = rule.matches_time(current_hour, current_day_of_week)
            
            return Response({
                'success': True,
                'rule_id': rule.id,
                'rule_name': rule.route.name,
                'test_time': test_time.isoformat(),
                'current_hour': current_hour,
                'current_day_of_week': current_day_of_week,
                'matches': matches
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def timezones(self, request):
        """Get list of supported timezones."""
        try:
            # This would return actual supported timezones
            # For now, return common timezones
            timezones = [
                {'value': 'UTC', 'label': 'UTC'},
                {'value': 'America/New_York', 'label': 'Eastern Time (ET)'},
                {'value': 'America/Chicago', 'label': 'Central Time (CT)'},
                {'value': 'America/Denver', 'label': 'Mountain Time (MT)'},
                {'value': 'America/Los_Angeles', 'label': 'Pacific Time (PT)'},
                {'value': 'Europe/London', 'label': 'London (GMT/BST)'},
                {'value': 'Europe/Paris', 'label': 'Paris (CET/CEST)'},
                {'value': 'Asia/Tokyo', 'label': 'Tokyo (JST)'},
                {'value': 'Asia/Shanghai', 'label': 'Shanghai (CST)'},
                {'value': 'Australia/Sydney', 'label': 'Sydney (AEST/AEDT)'}
            ]
            
            return Response({
                'success': True,
                'timezones': timezones
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BehaviorRouteRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing behavioral targeting rules.
    
    Provides CRUD operations for behavioral targeting rules
    with validation and testing capabilities.
    """
    
    queryset = BehaviorRouteRule.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageRoutes]
    
    def get_queryset(self):
        """Filter rules by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(route__tenant=self.request.user)
        return queryset.order_by('route__priority', 'route__name')
    
    @action(detail=True, methods=['post'])
    def test_rule(self, request, pk=None):
        """Test behavior rule with sample user data."""
        try:
            rule = self.get_object()
            
            # Get test user data
            test_user_id = request.data.get('user_id')
            if not test_user_id:
                return Response({
                    'success': False,
                    'error': 'User ID is required for testing'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get test user
            try:
                test_user = User.objects.get(id=test_user_id)
                if test_user.tenant != request.user:
                    return Response({
                        'success': False,
                        'error': 'User not found in your tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Test user not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Test rule
            from ..services.targeting import behavior_targeting_service
            
            # Get user events
            user_events = behavior_targeting_service._get_user_events(test_user)
            matches = rule.matches_behavior(user_events)
            
            return Response({
                'success': True,
                'rule_id': rule.id,
                'rule_name': rule.route.name,
                'test_user_id': test_user_id,
                'matches': matches,
                'user_events_count': len(user_events)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def supported_events(self, request):
        """Get list of supported behavioral events."""
        try:
            event_types = [
                {'value': 'offer_view', 'label': 'Offer View'},
                {'value': 'offer_click', 'label': 'Offer Click'},
                {'value': 'offer_conversion', 'label': 'Offer Conversion'},
                {'value': 'page_view', 'label': 'Page View'},
                {'value': 'search', 'label': 'Search'},
                {'value': 'add_to_cart', 'label': 'Add to Cart'},
                {'value': 'purchase', 'label': 'Purchase'},
                {'value': 'login', 'label': 'Login'},
                {'value': 'logout', 'label': 'Logout'},
                {'value': 'share', 'label': 'Share'}
            ]
            
            operators = [
                {'value': 'equals', 'label': 'Equals'},
                {'value': 'greater_than', 'label': 'Greater Than'},
                {'value': 'less_than', 'label': 'Less Than'},
                {'value': 'greater_equal', 'label': 'Greater Than or Equal'},
                {'value': 'less_equal', 'label': 'Less Than or Equal'}
            ]
            
            return Response({
                'success': True,
                'event_types': event_types,
                'operators': operators
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def user_behavior_summary(self, request):
        """Get behavior summary for a user."""
        try:
            user_id = request.query_params.get('user_id')
            if not user_id:
                return Response({
                    'success': False,
                    'error': 'user_id parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get user
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({
                        'success': False,
                        'error': 'User not found in your tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'User not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get behavior summary
            from ..services.targeting import behavior_targeting_service
            user_events = behavior_targeting_service._get_user_events(user)
            
            # Group events by type
            event_summary = {}
            for event in user_events:
                event_type = event.get('event_type', 'unknown')
                if event_type not in event_summary:
                    event_summary[event_type] = 0
                event_summary[event_type] += 1
            
            return Response({
                'success': True,
                'user_id': user_id,
                'total_events': len(user_events),
                'event_summary': event_summary
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
