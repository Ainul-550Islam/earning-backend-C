"""
Targeting Viewsets for Offer Routing System

Exposes ALL five targeting sub-services via API:
  - GeoRouteRuleViewSet       — geographic CRUD + GeoTargetingService wired
  - DeviceRouteRuleViewSet    — device CRUD + DeviceTargetingService wired
  - UserSegmentRuleViewSet    — segment CRUD + SegmentTargetingService wired
  - TimeRouteRuleViewSet      — time CRUD + TimeTargetingService wired
  - BehaviorRouteRuleViewSet  — behavior CRUD + BehaviorTargetingService wired
  - TargetingPreviewViewSet   — preview/test cross-targeting ← NEW

Business Value Added:
  - Advertisers can preview how many users a rule would match BEFORE saving
  - QA teams can test any rule against a real user context instantly
  - Ops teams can see targeting performance analytics per rule type
  - All get_queryset() methods are now fail-safe (return none() on error)
"""

import logging

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone

from ..models import (
    GeoRouteRule, DeviceRouteRule, UserSegmentRule,
    TimeRouteRule, BehaviorRouteRule,
)
from ..services.targeting import (
    geo_targeting_service,
    device_targeting_service,
    behavior_targeting_service,
    segment_targeting_service,
    time_targeting_service,
    targeting_service,
)
from ..permissions import IsAuthenticatedOrReadOnly, CanManageRoutes
from ..serializers import (
    GeoRouteRuleSerializer, DeviceRouteRuleSerializer,
    UserSegmentRuleSerializer, TimeRouteRuleSerializer,
    BehaviorRouteRuleSerializer,
)
from ..throttling import RoutingEngineThrottle

logger = logging.getLogger(__name__)
User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# GeoRouteRuleViewSet
# ─────────────────────────────────────────────────────────────────────────────

class GeoRouteRuleViewSet(viewsets.ModelViewSet):
    """Geographic targeting rules — CRUD + GeoTargetingService test/preview."""

    queryset = GeoRouteRule.objects.all()
    serializer_class = GeoRouteRuleSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageRoutes]
    throttle_classes = [RoutingEngineThrottle]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_authenticated:
            return queryset.none()
        try:
            queryset = queryset.filter(route__tenant=self.request.user)
        except Exception as e:
            logger.error("GeoRouteRuleViewSet.get_queryset error: %s", e, exc_info=True)
            return queryset.none()
        return queryset.order_by('route__priority', 'route__name')

    @action(detail=True, methods=['post'])
    def test_rule(self, request, pk=None):
        """Test this geo rule against supplied location data."""
        try:
            rule = self.get_object()
            test_location = request.data.get('location', {})
            if not test_location:
                return Response({'success': False, 'error': 'location data is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            matches = geo_targeting_service.evaluate_geo_rule(rule, test_location)
            return Response({'success': True, 'rule_id': rule.id,
                             'test_location': test_location, 'matches': matches})
        except Exception as e:
            logger.error("geo test_rule error pk=%s: %s", pk, e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def preview_matches(self, request):
        """
        Preview how many users an UNSAVED geo rule would match.
        Business value: advertisers QA coverage before going live.
        """
        try:
            rule_config = request.data.get('rule_config', {})
            if not rule_config:
                return Response({'success': False, 'error': 'rule_config is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = targeting_service.preview_rule_matches(
                rule_type='geo', rule_config=rule_config, tenant_id=request.user.id,
            )
            return Response({'success': True, 'preview': result})
        except Exception as e:
            logger.error("geo preview_matches error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def supported_countries(self, request):
        """List of countries supported by GeoTargetingService."""
        try:
            countries = geo_targeting_service.get_supported_countries()
            if not countries:
                countries = [
                    {'code': 'US', 'name': 'United States'},
                    {'code': 'GB', 'name': 'United Kingdom'},
                    {'code': 'CA', 'name': 'Canada'},
                    {'code': 'AU', 'name': 'Australia'},
                    {'code': 'DE', 'name': 'Germany'},
                    {'code': 'FR', 'name': 'France'},
                    {'code': 'JP', 'name': 'Japan'},
                    {'code': 'IN', 'name': 'India'},
                    {'code': 'BR', 'name': 'Brazil'},
                    {'code': 'BD', 'name': 'Bangladesh'},
                ]
            return Response({'success': True, 'countries': countries})
        except Exception as e:
            logger.error("supported_countries error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def service_health(self, request):
        """Health status of GeoTargetingService."""
        return Response({'success': True, 'health': geo_targeting_service.health_check()})


# ─────────────────────────────────────────────────────────────────────────────
# DeviceRouteRuleViewSet
# ─────────────────────────────────────────────────────────────────────────────

class DeviceRouteRuleViewSet(viewsets.ModelViewSet):
    """Device targeting rules — CRUD + DeviceTargetingService test/preview."""

    queryset = DeviceRouteRule.objects.all()
    serializer_class = DeviceRouteRuleSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageRoutes]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_authenticated:
            return queryset.none()
        try:
            queryset = queryset.filter(route__tenant=self.request.user)
        except Exception as e:
            logger.error("DeviceRouteRuleViewSet.get_queryset error: %s", e, exc_info=True)
            return queryset.none()
        return queryset.order_by('route__priority', 'route__name')

    @action(detail=True, methods=['post'])
    def test_rule(self, request, pk=None):
        """Test this device rule against supplied device data."""
        try:
            rule = self.get_object()
            test_device = request.data.get('device', {})
            if not test_device:
                return Response({'success': False, 'error': 'device data is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            matches = device_targeting_service.evaluate_device_rule(rule, test_device)
            parsed  = device_targeting_service.parse_user_agent(
                test_device.get('user_agent', ''))
            return Response({'success': True, 'rule_id': rule.id,
                             'test_device': test_device, 'parsed_device': parsed,
                             'matches': matches})
        except Exception as e:
            logger.error("device test_rule error pk=%s: %s", pk, e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def preview_matches(self, request):
        """Preview how many users an UNSAVED device rule would match."""
        try:
            rule_config = request.data.get('rule_config', {})
            if not rule_config:
                return Response({'success': False, 'error': 'rule_config is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = targeting_service.preview_rule_matches(
                rule_type='device', rule_config=rule_config, tenant_id=request.user.id,
            )
            return Response({'success': True, 'preview': result})
        except Exception as e:
            logger.error("device preview_matches error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def supported_devices(self, request):
        """Device types, OS types and browsers recognised by DeviceTargetingService."""
        try:
            devices = device_targeting_service.get_supported_devices()
            if not devices:
                devices = [
                    {'value': 'desktop',      'label': 'Desktop'},
                    {'value': 'mobile',       'label': 'Mobile'},
                    {'value': 'tablet',       'label': 'Tablet'},
                    {'value': 'smart_tv',     'label': 'Smart TV'},
                    {'value': 'game_console', 'label': 'Game Console'},
                ]
            return Response({'success': True,
                             'device_types': devices,
                             'os_types': [
                                 {'value': 'windows', 'label': 'Windows'},
                                 {'value': 'macos',   'label': 'macOS'},
                                 {'value': 'linux',   'label': 'Linux'},
                                 {'value': 'ios',     'label': 'iOS'},
                                 {'value': 'android', 'label': 'Android'},
                             ],
                             'browsers': [
                                 {'value': 'chrome',  'label': 'Chrome'},
                                 {'value': 'firefox', 'label': 'Firefox'},
                                 {'value': 'safari',  'label': 'Safari'},
                                 {'value': 'edge',    'label': 'Edge'},
                             ]})
        except Exception as e:
            logger.error("supported_devices error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def service_health(self, request):
        return Response({'success': True, 'health': device_targeting_service.health_check()})


# ─────────────────────────────────────────────────────────────────────────────
# UserSegmentRuleViewSet
# ─────────────────────────────────────────────────────────────────────────────

class UserSegmentRuleViewSet(viewsets.ModelViewSet):
    """User segment targeting rules — CRUD + SegmentTargetingService test/preview."""

    queryset = UserSegmentRule.objects.all()
    serializer_class = UserSegmentRuleSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageRoutes]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_authenticated:
            return queryset.none()
        try:
            queryset = queryset.filter(route__tenant=self.request.user)
        except Exception as e:
            logger.error("UserSegmentRuleViewSet.get_queryset error: %s", e, exc_info=True)
            return queryset.none()
        return queryset.order_by('route__priority', 'route__name')

    @action(detail=True, methods=['post'])
    def test_rule(self, request, pk=None):
        """Test this segment rule against a real user in your tenant."""
        try:
            rule = self.get_object()
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({'success': False, 'error': 'user_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({'success': False, 'error': 'User not in your tenant'},
                                    status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'success': False, 'error': 'User not found'},
                                status=status.HTTP_404_NOT_FOUND)

            segments = segment_targeting_service.get_user_segments(user)
            matches  = segment_targeting_service.evaluate_segment_rule(rule, {'user_segments': segments})
            return Response({'success': True, 'rule_id': rule.id,
                             'user_id': user_id, 'user_segments': segments, 'matches': matches})
        except Exception as e:
            logger.error("segment test_rule error pk=%s: %s", pk, e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def preview_matches(self, request):
        """Preview user count for an UNSAVED segment rule."""
        try:
            rule_config = request.data.get('rule_config', {})
            if not rule_config:
                return Response({'success': False, 'error': 'rule_config is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = targeting_service.preview_rule_matches(
                rule_type='segment', rule_config=rule_config, tenant_id=request.user.id,
            )
            return Response({'success': True, 'preview': result})
        except Exception as e:
            logger.error("segment preview_matches error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def supported_segments(self, request):
        """Segment types and operators supported by SegmentTargetingService."""
        try:
            segments = segment_targeting_service.get_available_segments()
            if not segments:
                segments = [
                    {'value': 'tier',          'label': 'User Tier'},
                    {'value': 'new_user',       'label': 'New User'},
                    {'value': 'active_user',    'label': 'Active User'},
                    {'value': 'premium_user',   'label': 'Premium User'},
                    {'value': 'churned_user',   'label': 'Churned User'},
                    {'value': 'engaged_user',   'label': 'Engaged User'},
                    {'value': 'inactive_user',  'label': 'Inactive User'},
                ]
            return Response({'success': True, 'segment_types': segments,
                             'operators': [
                                 {'value': 'equals',       'label': 'Equals'},
                                 {'value': 'not_equals',   'label': 'Not Equals'},
                                 {'value': 'in',           'label': 'In'},
                                 {'value': 'not_in',       'label': 'Not In'},
                             ]})
        except Exception as e:
            logger.error("supported_segments error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def segment_values(self, request):
        """Allowed values for a given segment_type."""
        segment_type = request.query_params.get('segment_type')
        value_map = {
            'tier':         [{'value': 'basic'}, {'value': 'premium'}, {'value': 'enterprise'}],
            'new_user':     [{'value': True}, {'value': False}],
            'active_user':  [{'value': True}, {'value': False}],
            'premium_user': [{'value': True}, {'value': False}],
        }
        if not segment_type:
            return Response({'success': False, 'error': 'segment_type is required'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'success': True, 'segment_type': segment_type,
                         'values': value_map.get(segment_type, [])})

    @action(detail=False, methods=['get'])
    def service_health(self, request):
        return Response({'success': True, 'health': segment_targeting_service.health_check()})


# ─────────────────────────────────────────────────────────────────────────────
# TimeRouteRuleViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TimeRouteRuleViewSet(viewsets.ModelViewSet):
    """Time-based targeting rules — CRUD + TimeTargetingService test/preview."""

    queryset = TimeRouteRule.objects.all()
    serializer_class = TimeRouteRuleSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageRoutes]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_authenticated:
            return queryset.none()
        try:
            queryset = queryset.filter(route__tenant=self.request.user)
        except Exception as e:
            logger.error("TimeRouteRuleViewSet.get_queryset error: %s", e, exc_info=True)
            return queryset.none()
        return queryset.order_by('route__priority', 'route__name')

    @action(detail=True, methods=['post'])
    def test_rule(self, request, pk=None):
        """Test this time rule against a supplied ISO datetime string."""
        try:
            rule = self.get_object()
            test_time_raw = request.data.get('time')
            if test_time_raw:
                from datetime import datetime
                test_time = datetime.fromisoformat(test_time_raw.replace('Z', '+00:00'))
            else:
                test_time = timezone.now()

            context = {'hour': test_time.hour, 'day_of_week': test_time.weekday(),
                       'timestamp': test_time.isoformat()}
            matches = time_targeting_service.evaluate_time_rule(rule, context)
            return Response({'success': True, 'rule_id': rule.id,
                             'test_time': test_time.isoformat(),
                             'hour': test_time.hour, 'day_of_week': test_time.weekday(),
                             'matches': matches})
        except Exception as e:
            logger.error("time test_rule error pk=%s: %s", pk, e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def preview_matches(self, request):
        """Preview how many users are online during a time window."""
        try:
            rule_config = request.data.get('rule_config', {})
            if not rule_config:
                return Response({'success': False, 'error': 'rule_config is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = targeting_service.preview_rule_matches(
                rule_type='time', rule_config=rule_config, tenant_id=request.user.id,
            )
            return Response({'success': True, 'preview': result})
        except Exception as e:
            logger.error("time preview_matches error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def timezones(self, request):
        """Supported timezones."""
        return Response({'success': True, 'timezones': [
            {'value': 'UTC',                  'label': 'UTC'},
            {'value': 'America/New_York',     'label': 'Eastern Time (ET)'},
            {'value': 'America/Chicago',      'label': 'Central Time (CT)'},
            {'value': 'America/Los_Angeles',  'label': 'Pacific Time (PT)'},
            {'value': 'Europe/London',        'label': 'London (GMT/BST)'},
            {'value': 'Europe/Paris',         'label': 'Paris (CET/CEST)'},
            {'value': 'Asia/Dhaka',           'label': 'Dhaka (BST)'},
            {'value': 'Asia/Tokyo',           'label': 'Tokyo (JST)'},
            {'value': 'Asia/Shanghai',        'label': 'Shanghai (CST)'},
            {'value': 'Australia/Sydney',     'label': 'Sydney (AEST/AEDT)'},
        ]})

    @action(detail=False, methods=['get'])
    def current_schedule(self, request):
        """Get which time rules are currently active right now."""
        try:
            schedule = time_targeting_service.get_current_schedule()
            return Response({'success': True, 'current_time': timezone.now().isoformat(),
                             'active_rules': schedule})
        except Exception as e:
            logger.error("current_schedule error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def service_health(self, request):
        return Response({'success': True, 'health': time_targeting_service.health_check()})


# ─────────────────────────────────────────────────────────────────────────────
# BehaviorRouteRuleViewSet
# ─────────────────────────────────────────────────────────────────────────────

class BehaviorRouteRuleViewSet(viewsets.ModelViewSet):
    """Behavioral targeting rules — CRUD + BehaviorTargetingService test/preview."""

    queryset = BehaviorRouteRule.objects.all()
    serializer_class = BehaviorRouteRuleSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageRoutes]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_authenticated:
            return queryset.none()
        try:
            queryset = queryset.filter(route__tenant=self.request.user)
        except Exception as e:
            logger.error("BehaviorRouteRuleViewSet.get_queryset error: %s", e, exc_info=True)
            return queryset.none()
        return queryset.order_by('route__priority', 'route__name')

    @action(detail=True, methods=['post'])
    def test_rule(self, request, pk=None):
        """Test this behavior rule against a real user in your tenant."""
        try:
            rule = self.get_object()
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({'success': False, 'error': 'user_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({'success': False, 'error': 'User not in your tenant'},
                                    status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'success': False, 'error': 'User not found'},
                                status=status.HTTP_404_NOT_FOUND)

            profile = behavior_targeting_service.get_user_behavior_profile(user)
            matches = behavior_targeting_service.evaluate_behavior_rule(rule, {'behavior': profile})
            return Response({'success': True, 'rule_id': rule.id,
                             'user_id': user_id, 'behavior_profile': profile, 'matches': matches})
        except Exception as e:
            logger.error("behavior test_rule error pk=%s: %s", pk, e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def preview_matches(self, request):
        """Preview user count for an UNSAVED behavior rule."""
        try:
            rule_config = request.data.get('rule_config', {})
            if not rule_config:
                return Response({'success': False, 'error': 'rule_config is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = targeting_service.preview_rule_matches(
                rule_type='behavior', rule_config=rule_config, tenant_id=request.user.id,
            )
            return Response({'success': True, 'preview': result})
        except Exception as e:
            logger.error("behavior preview_matches error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def supported_events(self, request):
        """Event types supported by BehaviorTargetingService."""
        try:
            events = behavior_targeting_service.get_supported_event_types()
            if not events:
                events = [
                    {'value': 'offer_view',       'label': 'Offer View'},
                    {'value': 'offer_click',       'label': 'Offer Click'},
                    {'value': 'offer_conversion',  'label': 'Offer Conversion'},
                    {'value': 'page_view',         'label': 'Page View'},
                    {'value': 'purchase',          'label': 'Purchase'},
                    {'value': 'search',            'label': 'Search'},
                    {'value': 'add_to_cart',       'label': 'Add to Cart'},
                ]
            return Response({'success': True, 'event_types': events,
                             'operators': [
                                 {'value': 'equals',        'label': 'Equals'},
                                 {'value': 'greater_than',  'label': 'Greater Than'},
                                 {'value': 'less_than',     'label': 'Less Than'},
                             ]})
        except Exception as e:
            logger.error("supported_events error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def user_behavior_summary(self, request):
        """Behavior profile for a specific user."""
        try:
            user_id = request.query_params.get('user_id')
            if not user_id:
                return Response({'success': False, 'error': 'user_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({'success': False, 'error': 'User not in your tenant'},
                                    status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'success': False, 'error': 'User not found'},
                                status=status.HTTP_404_NOT_FOUND)

            profile = behavior_targeting_service.get_user_behavior_profile(user)
            return Response({'success': True, 'user_id': user_id, 'behavior_profile': profile})
        except Exception as e:
            logger.error("user_behavior_summary error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def service_health(self, request):
        return Response({'success': True, 'health': behavior_targeting_service.health_check()})


# ─────────────────────────────────────────────────────────────────────────────
# TargetingPreviewViewSet  ← NEW — cross-rule preview & aggregate health
# ─────────────────────────────────────────────────────────────────────────────

class TargetingPreviewViewSet(viewsets.ViewSet):
    """
    Cross-targeting preview and aggregate health endpoint.

    Business Value:
      - Advertisers can test a COMBINED rule set (geo + device + time) at once
      - Ops teams can check all 5 targeting services in a single call
      - QA can run end-to-end targeting evaluation before a campaign launch
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    @action(detail=False, methods=['post'])
    def evaluate_all(self, request):
        """
        Evaluate ALL five targeting rule types for a given user + context.

        POST body:
            user_id   (int)   — required
            context   (dict)  — required: {ip_address, user_agent, ...}
        """
        try:
            user_id = request.data.get('user_id')
            context = request.data.get('context', {})
            if not user_id:
                return Response({'success': False, 'error': 'user_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({'success': False, 'error': 'User not in your tenant'},
                                    status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'success': False, 'error': 'User not found'},
                                status=status.HTTP_404_NOT_FOUND)

            from ..models import OfferRoute
            results = []
            for route in OfferRoute.objects.filter(tenant=request.user, is_active=True)[:20]:
                eval_result = targeting_service.evaluate_all_rules(route, context)
                results.append({'route_id': route.id, 'route_name': route.name,
                                 'targeting_results': eval_result})

            overall_matches = sum(1 for r in results if r['targeting_results'].get('overall'))
            return Response({'success': True, 'user_id': user_id,
                             'evaluated_routes': len(results),
                             'matching_routes': overall_matches,
                             'details': results})
        except Exception as e:
            logger.error("targeting evaluate_all error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def health(self, request):
        """Aggregate health of all 5 targeting sub-services."""
        return Response({'success': True, 'health': targeting_service.health_check()})
