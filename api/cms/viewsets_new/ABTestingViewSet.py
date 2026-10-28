# api/cms/viewsets_new/ABTestingViewSet.py
"""
API ViewSets for Advanced A/B Testing Framework
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone

from ..models_new.ab_testing import (
    ABTest, ABTestVariant, ABTestParticipant, ABTestResult
)
from ..services_new.ABTestingService import ABTestingManager, ABTestingAnalytics


class ABTestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for A/B test management
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['test_type', 'status']
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return ABTest.objects.all().select_related('variants').prefetch_related('participants')
        return ABTest.objects.filter(status='running').select_related('variants')
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start an A/B test"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        try:
            ABTestingManager().start_test(pk)
            return Response({'message': 'Test started successfully'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause an A/B test"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        try:
            ABTestingManager().pause_test(pk)
            return Response({'message': 'Test paused successfully'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete an A/B test"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        force = request.data.get('force', False)
        try:
            ABTestingManager().complete_test(pk, force=force)
            return Response({'message': 'Test completed successfully'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=True, methods=['get'])
    def results(self, request, pk=None):
        """Get test results with statistical analysis"""
        force_recalculate = request.query_params.get('force_recalculate', 'false').lower() == 'true'
        
        try:
            results = ABTestingManager().calculate_results(pk, force_recalculate)
            return Response(results)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=True, methods=['get'])
    def user_variant(self, request, pk=None):
        """Get current user's variant for this test"""
        variant = ABTestingManager().get_user_variant(pk, request.user)
        if variant:
            return Response({
                'variant_uuid': str(variant.uuid),
                'variant_name': variant.name,
                'is_control': variant.is_control,
                'configuration': variant.configuration
            })
        return Response({'message': 'User not included in this test'})
    
    @action(detail=True, methods=['post'])
    def track_conversion(self, request, pk=None):
        """Track conversion for current user"""
        value = request.data.get('value')
        metadata = request.data.get('metadata', {})
        
        try:
            success = ABTestingManager().track_conversion(
                pk, request.user, value, metadata
            )
            if success:
                return Response({'message': 'Conversion tracked successfully'})
            else:
                return Response({'error': 'Failed to track conversion'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=True, methods=['post'])
    def track_engagement(self, request, pk=None):
        """Track user engagement"""
        engagement_type = request.data.get('type')
        value = request.data.get('value', 1)
        
        if engagement_type not in ['click', 'page_view', 'time_spent']:
            return Response({'error': 'Invalid engagement type'}, status=400)
        
        try:
            success = ABTestingManager().track_engagement(
                pk, request.user, engagement_type, value
            )
            if success:
                return Response({'message': 'Engagement tracked successfully'})
            else:
                return Response({'error': 'Failed to track engagement'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=False, methods=['post'])
    def create_test(self, request):
        """Create a new A/B test"""
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        try:
            manager = ABTestingManager()
            test = manager.create_test(request.data)
            return Response({
                'test_uuid': str(test.uuid),
                'message': 'Test created successfully'
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=False, methods=['get'])
    def running_tests(self, request):
        """Get all currently running tests"""
        tests = ABTestingManager().get_running_tests()
        data = []
        for test in tests:
            data.append({
                'uuid': str(test.uuid),
                'name': test.name,
                'test_type': test.test_type,
                'start_time': test.start_time.isoformat() if test.start_time else None,
                'variants': [
                    {
                        'uuid': str(v.uuid),
                        'name': v.name,
                        'is_control': v.is_control,
                        'traffic_split': v.traffic_split
                    }
                    for v in test.variants.all()
                ]
            })
        return Response(data)


class ABTestVariantViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for A/B test variants
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return ABTestVariant.objects.all().select_related('test')
        return ABTestVariant.objects.filter(
            test__status='running',
            is_active=True
        ).select_related('test')


class ABTestAnalyticsViewSet(viewsets.ViewSet):
    """
    ViewSet for A/B testing analytics
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get overview of all A/B tests"""
        days = int(request.query_params.get('days', 30))
        
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        try:
            analytics = ABTestingAnalytics.get_test_overview(days)
            return Response(analytics)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=False, methods=['get'])
    def variant_performance(self, request):
        """Get detailed variant performance"""
        test_uuid = request.query_params.get('test_uuid')
        
        if not test_uuid:
            return Response({'error': 'test_uuid required'}, status=400)
        
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)
        
        try:
            performance = ABTestingAnalytics.get_variant_performance(test_uuid)
            return Response(performance)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=False, methods=['get'])
    def user_journey(self, request):
        """Get user's journey through tests"""
        test_uuid = request.query_params.get('test_uuid')
        
        if not test_uuid:
            return Response({'error': 'test_uuid required'}, status=400)
        
        try:
            journey = ABTestingAnalytics.get_user_journey(test_uuid, request.user.id)
            return Response(journey)
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# Aliases so imports work even if participant/result viewsets aren't implemented
class ABTestParticipantViewSet(ABTestAnalyticsViewSet):
    """Participant tracking for A/B tests — alias of ABTestAnalyticsViewSet."""
    pass


class ABTestResultViewSet(ABTestAnalyticsViewSet):
    """Results aggregation for A/B tests — alias of ABTestAnalyticsViewSet."""
    pass
