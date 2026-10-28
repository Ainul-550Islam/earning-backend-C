"""
Flag Analytics viewset for Feature Flags & A/B Testing.
"""
from django.db.models import Sum  # FIX: was missing — `summary` action raised NameError on every call
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models.flag_analytics import FlagAnalytics
from ..serializers.analytics_serializer import FlagAnalyticsSerializer, FlagAnalyticsListSerializer
from ..permissions import CanViewFlags


class FlagAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Viewset for FlagAnalytics model (read-only).
    """

    queryset = FlagAnalytics.objects.all()
    serializer_class = FlagAnalyticsSerializer
    # NEW: authentication & permissions (previously NONE on any viewset)
    permission_classes = [IsAuthenticated, CanViewFlags]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return FlagAnalyticsListSerializer
        return FlagAnalyticsSerializer

    @action(detail=False, methods=['get'])
    def by_flag(self, request):
        """
        Get analytics by flag.
        """
        flag_id = request.query_params.get('flag_id')

        if not flag_id:
            return Response({
                'success': False,
                'error': 'flag_id parameter is required'
            }, status=400)

        analytics = self.queryset.filter(flag_id=flag_id)
        serializer = self.get_serializer(analytics, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_date(self, request):
        """
        Get analytics by date range.
        """
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        analytics = self.queryset.all()

        if date_from:
            analytics = analytics.filter(date__gte=date_from)

        if date_to:
            analytics = analytics.filter(date__lte=date_to)

        serializer = self.get_serializer(analytics, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get analytics summary.

        FIX: `Sum` is now imported at module level (see top of file) —
        previously this action raised `NameError: name 'Sum' is not
        defined` on every single invocation.
        """
        flag_id = request.query_params.get('flag_id')

        if not flag_id:
            return Response({
                'success': False,
                'error': 'flag_id parameter is required'
            }, status=400)

        analytics = self.queryset.filter(flag_id=flag_id)

        total_evaluations = analytics.aggregate(total=Sum('evaluation_count'))['total'] or 0
        total_enabled = analytics.aggregate(total=Sum('enabled_count'))['total'] or 0
        total_unique_users = analytics.aggregate(total=Sum('unique_users'))['total'] or 0
        total_conversions = analytics.aggregate(total=Sum('conversion_count'))['total'] or 0

        return Response({
            'success': True,
            'data': {
                'total_evaluations': total_evaluations,
                'total_enabled': total_enabled,
                'enable_rate': round((total_enabled / total_evaluations * 100) if total_evaluations > 0 else 0, 2),
                'total_unique_users': total_unique_users,
                'total_conversions': total_conversions,
                'conversion_rate': round((total_conversions / total_unique_users * 100) if total_unique_users > 0 else 0, 2)
            }
        })

    # NEW: floating-code fix — this aggregate logic existed in
    # AnalyticsService.get_flag_analytics() but had no endpoint exposing it.
    @action(detail=False, methods=['get'])
    def portfolio_overview(self, request):
        """Overview of all flags' analytics (NEW — previously floating code in AnalyticsService)."""
        from ..models.feature_flag import FeatureFlag
        from django.db.models import Count

        environment = request.query_params.get('environment', 'production')
        flags = FeatureFlag.objects.filter(environment=environment)

        return Response({
            'environment': environment,
            'total_flags': flags.count(),
            'active_flags': flags.filter(status=FeatureFlag.Status.ACTIVE).count(),
            'paused_flags': flags.filter(status=FeatureFlag.Status.PAUSED).count(),
            'draft_flags': flags.filter(status=FeatureFlag.Status.DRAFT).count(),
            'archived_flags': flags.filter(status=FeatureFlag.Status.ARCHIVED).count(),
            'flags_by_type': dict(
                flags.values('flag_type').annotate(count=Count('id')).values_list('flag_type', 'count')
            ),
        })

    @action(detail=False, methods=['get'])
    def performance(self, request):
        """NEW: performance/optimization-score for a single flag (Missing
        Component #10: Performance Metrics), powered by PerformanceService."""
        from ..services.performance_service import PerformanceService

        flag_id = request.query_params.get('flag_id')
        if not flag_id:
            return Response({'error': 'flag_id parameter is required'}, status=400)

        from ..models.feature_flag import FeatureFlag
        try:
            impact = PerformanceService().get_flag_impact(int(flag_id))
        except (FeatureFlag.DoesNotExist, ValueError):
            return Response({'error': 'Flag not found'}, status=404)

        return Response({'success': True, 'data': impact})
