"""
Analytics Viewsets for Offer Routing System

This module contains viewsets for accessing routing analytics,
insights, performance metrics, and business reports.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Avg, Count, Sum, Max, Min
from ..models import (
    RoutingDecisionLog, RoutingInsight, RoutePerformanceStat,
    OfferExposureStat, RoutingABTest, ABTestResult
)
from ..services.analytics import analytics_service
from ..services.reporter import routing_reporter
from ..permissions import IsAuthenticatedOrReadOnly, CanViewAnalytics
from ..exceptions import ValidationError, AnalyticsError

User = get_user_model()


class RoutingDecisionLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing routing decision logs.
    
    Provides read-only access to routing decision logs
    with filtering and analytics capabilities.
    """
    
    queryset = RoutingDecisionLog.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanViewAnalytics]
    
    def get_queryset(self):
        """Filter logs by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(user__tenant=self.request.user)
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def decision_analytics(self, request):
        """Get analytics for routing decisions."""
        try:
            days = int(request.query_params.get('days', 30))
            
            from ..services.analytics import RoutingAnalyticsService
            analytics_service_instance = RoutingAnalyticsService()
            analytics = analytics_service_instance.get_performance_metrics(
                tenant_id=request.user.id,
                days=days
            )
            
            return Response({
                'success': True,
                'period_days': days,
                'analytics': analytics
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def performance_trends(self, request):
        """Get performance trends over time."""
        try:
            days = int(request.query_params.get('days', 30))
            
            # Get daily performance data
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            daily_stats = RoutingDecisionLog.objects.filter(
                user__tenant=request.user,
                created_at__gte=cutoff_date
            ).extra({
                'date': 'date(created_at)'
            }).values('date').annotate(
                total_decisions=Count('id'),
                avg_response_time=Avg('response_time_ms'),
                cache_hit_rate=Avg('cache_hit'),
                personalization_rate=Avg('personalization_applied'),
                caps_check_rate=Avg('caps_checked'),
                fallback_rate=Avg('fallback_used')
            ).order_by('date')
            
            trends = []
            for stat in daily_stats:
                trends.append({
                    'date': stat['date'].isoformat(),
                    'total_decisions': stat['total_decisions'],
                    'avg_response_time_ms': stat['avg_response_time'] or 0,
                    'cache_hit_rate': (stat['cache_hit_rate'] or 0) * 100,
                    'personalization_rate': (stat['personalization_rate'] or 0) * 100,
                    'caps_check_rate': (stat['caps_check_rate'] or 0) * 100,
                    'fallback_rate': (stat['fallback_used'] or 0) * 100
                })
            
            return Response({
                'success': True,
                'period_days': days,
                'trends': trends
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def aggregate_stats(self, request):
        """Trigger aggregation of hourly statistics."""
        try:
            from ..services.analytics import RoutingAnalyticsService
            analytics_service_instance = RoutingAnalyticsService()
            
            aggregated_count = analytics_service_instance.aggregate_hourly_stats()
            
            return Response({
                'success': True,
                'aggregated_count': aggregated_count
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def cleanup_old_data(self, request):
        """Clean up old decision logs."""
        try:
            from ..services.analytics import RoutingAnalyticsService
            analytics_service_instance = RoutingAnalyticsService()
            
            deleted_count = analytics_service_instance.cleanup_old_data()
            
            return Response({
                'success': True,
                'deleted_count': deleted_count
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RoutingInsightViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing routing insights.
    
    Provides read-only access to routing insights
    with filtering and management capabilities.
    """
    
    queryset = RoutingInsight.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanViewAnalytics]
    
    def get_queryset(self):
        """Filter insights by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(tenant=self.request.user)
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def active_insights(self, request):
        """Get active insights."""
        try:
            insights = self.get_queryset().filter(
                is_actionable=True,
                action_taken=False
            )
            
            insight_data = []
            for insight in insights:
                insight_data.append({
                    'insight_id': insight.id,
                    'title': insight.title,
                    'description': insight.description,
                    'insight_type': insight.insight_type,
                    'severity': insight.severity,
                    'confidence': insight.confidence,
                    'action_suggestion': insight.action_suggestion,
                    'period_start': insight.period_start.isoformat(),
                    'period_end': insight.period_end.isoformat(),
                    'created_at': insight.created_at.isoformat()
                })
            
            return Response({
                'success': True,
                'active_insights': insight_data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def mark_action_taken(self, request, pk=None):
        """Mark insight as action taken."""
        try:
            insight = self.get_object()
            
            insight.action_taken = True
            insight.save()
            
            return Response({
                'success': True,
                'insight_id': insight.id,
                'action_taken': True,
                'action_taken_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def generate_insights(self, request):
        """Generate insights for a specific period."""
        try:
            days = int(request.data.get('days', 7))
            
            from datetime import timedelta
            period_start = timezone.now() - timedelta(days=days)
            period_end = timezone.now()
            
            from ..services.analytics import RoutingAnalyticsService
            analytics_service_instance = RoutingAnalyticsService()
            
            generated_count = analytics_service_instance.generate_insights(
                tenant_id=request.user.id,
                period_start=period_start,
                period_end=period_end
            )
            
            return Response({
                'success': True,
                'generated_count': generated_count,
                'period_days': days
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def insight_analytics(self, request):
        """Get analytics for insights."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=30)
            
            # Get insight statistics
            insights = self.get_queryset().filter(
                created_at__gte=cutoff_date
            ).aggregate(
                total_insights=Count('id'),
                actionable_insights=Count('id', filter=Q(is_actionable=True)),
                insights_with_action_taken=Count('id', filter=Q(action_taken=True)),
                avg_confidence=Avg('confidence')
            )
            
            # Get distribution by type
            type_distribution = self.get_queryset().filter(
                created_at__gte=cutoff_date
            ).values('insight_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Get distribution by severity
            severity_distribution = self.get_queryset().filter(
                created_at__gte=cutoff_date
            ).values('severity').annotate(
                count=Count('id')
            ).order_by('-count')
            
            return Response({
                'success': True,
                'period_days': 30,
                'insight_stats': insights,
                'type_distribution': list(type_distribution),
                'severity_distribution': list(severity_distribution)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RoutePerformanceStatViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing route performance statistics.
    
    Provides read-only access to performance statistics
    with filtering and analytics capabilities.
    """
    
    queryset = RoutePerformanceStat.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanViewAnalytics]
    
    def get_queryset(self):
        """Filter stats by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(tenant=self.request.user)
        return queryset.order_by('-date')
    
    @action(detail=False, methods=['get'])
    def performance_summary(self, request):
        """Get performance summary for all routes."""
        try:
            days = int(request.query_params.get('days', 30))
            
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get overall statistics
            stats = self.get_queryset().filter(
                date__gte=cutoff_date.date()
            ).aggregate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_revenue=Sum('revenue'),
                avg_click_through_rate=Avg('click_through_rate'),
                avg_conversion_rate=Avg('conversion_rate'),
                avg_response_time=Avg('avg_response_time_ms'),
                avg_cache_hit_rate=Avg('cache_hit_rate')
            )
            
            # Get top performing routes
            top_routes = self.get_queryset().filter(
                date__gte=cutoff_date.date()
            ).values('route_id', 'route__name').annotate(
                total_revenue=Sum('revenue')
            ).order_by('-total_revenue')[:10]
            
            return Response({
                'success': True,
                'period_days': days,
                'summary': stats,
                'top_routes': list(top_routes)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def route_comparison(self, request):
        """Compare performance between routes."""
        try:
            route_ids = request.query_params.getlist('route_ids')
            if not route_ids:
                return Response({
                    'success': False,
                    'error': 'route_ids parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            days = int(request.query_params.get('days', 30))
            
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get stats for specified routes
            route_stats = self.get_queryset().filter(
                route_id__in=route_ids,
                date__gte=cutoff_date.date()
            ).values('route_id', 'route__name').annotate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_revenue=Sum('revenue'),
                avg_conversion_rate=Avg('conversion_rate'),
                avg_response_time=Avg('avg_response_time_ms')
            ).order_by('-total_revenue')
            
            return Response({
                'success': True,
                'period_days': days,
                'route_stats': list(route_stats)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def performance_trends(self, request):
        """Get performance trends over time."""
        try:
            days = int(request.query_params.get('days', 30))
            
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get daily performance data
            daily_stats = self.get_queryset().filter(
                tenant=self.request.user,
                date__gte=cutoff_date.date()
            ).values('date').annotate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_revenue=Sum('revenue'),
                avg_conversion_rate=Avg('conversion_rate'),
                avg_response_time=Avg('avg_response_time_ms')
            ).order_by('date')
            
            trends = []
            for stat in daily_stats:
                trends.append({
                    'date': stat['date'].isoformat(),
                    'total_impressions': stat['total_impressions'] or 0,
                    'total_clicks': stat['total_clicks'] or 0,
                    'total_conversions': stat['total_conversions'] or 0,
                    'total_revenue': float(stat['total_revenue'] or 0),
                    'avg_conversion_rate': stat['avg_conversion_rate'] or 0,
                    'avg_response_time_ms': stat['avg_response_time_ms'] or 0
                })
            
            return Response({
                'success': True,
                'period_days': days,
                'trends': trends
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OfferExposureStatViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing offer exposure statistics.
    
    Provides read-only access to exposure statistics
    with filtering and analytics capabilities.
    """
    
    queryset = OfferExposureStat.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanViewAnalytics]
    
    def get_queryset(self):
        """Filter stats by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(tenant=self.request.user)
        return queryset.order_by('-date')
    
    @action(detail=False, methods=['get'])
    def exposure_summary(self, request):
        """Get exposure summary for all offers."""
        try:
            days = int(request.query_params.get('days', 30))
            
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get overall statistics
            stats = self.get_queryset().filter(
                date__gte=cutoff_date.date()
            ).aggregate(
                total_unique_users_exposed=Sum('unique_users_exposed'),
                total_exposures=Sum('total_exposures'),
                total_repeat_exposures=Sum('repeat_exposures'),
                avg_exposures_per_user=Avg('avg_exposures_per_user'),
                max_exposures_per_user=Max('max_exposures_per_user')
            )
            
            # Get most exposed offers
            most_exposed = self.get_queryset().filter(
                date__gte=cutoff_date.date()
            ).values('offer_id', 'offer__name').annotate(
                total_exposures=Sum('total_exposures')
            ).order_by('-total_exposures')[:10]
            
            return Response({
                'success': True,
                'period_days': days,
                'summary': stats,
                'most_exposed': list(most_exposed)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def offer_exposure_patterns(self, request):
        """Get exposure patterns for offers."""
        try:
            offer_id = request.query_params.get('offer_id')
            if not offer_id:
                return Response({
                    'success': False,
                    'error': 'offer_id parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            days = int(request.query_params.get('days', 30))
            
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get exposure data for this offer
            exposure_data = self.get_queryset().filter(
                offer_id=offer_id,
                date__gte=cutoff_date.date()
            ).order_by('date')
            
            patterns = []
            for stat in exposure_data:
                patterns.append({
                    'date': stat.date.isoformat(),
                    'unique_users_exposed': stat.unique_users_exposed,
                    'total_exposures': stat.total_exposures,
                    'repeat_exposures': stat.repeat_exposures,
                    'avg_exposures_per_user': stat.avg_exposures_per_user,
                    'max_exposures_per_user': stat.max_exposures_per_user,
                    'geographic_distribution': stat.geographic_distribution,
                    'device_distribution': stat.device_distribution,
                    'hourly_distribution': stat.hourly_distribution
                })
            
            return Response({
                'success': True,
                'offer_id': offer_id,
                'period_days': days,
                'patterns': patterns
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReportViewSet(viewsets.ViewSet):
    """
    ViewSet for generating comprehensive reports.
    
    Provides endpoints for generating various types of reports
    including performance, A/B test, and business reports.
    """
    
    permission_classes = [IsAuthenticatedOrReadOnly, CanViewAnalytics]
    
    @action(detail=False, methods=['post'])
    def generate_performance_report(self, request):
        """Generate comprehensive performance report."""
        try:
            days = int(request.data.get('days', 30))
            
            report = routing_reporter.generate_performance_report(
                tenant_id=request.user.id,
                days=days
            )
            
            return Response({
                'success': True,
                'report': report
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def generate_ab_test_report(self, request):
        """Generate A/B testing report."""
        try:
            days = int(request.data.get('days', 30))
            
            report = routing_reporter.generate_ab_test_report(
                tenant_id=request.user.id,
                days=days
            )
            
            return Response({
                'success': True,
                'report': report
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def generate_business_report(self, request):
        """Generate business-focused report."""
        try:
            days = int(request.data.get('days', 30))
            
            report = routing_reporter.generate_business_report(
                tenant_id=request.user.id,
                days=days
            )
            
            return Response({
                'success': True,
                'report': report
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def report_list(self, request):
        """Get list of available report types."""
        try:
            reports = [
                {
                    'type': 'performance',
                    'name': 'Performance Report',
                    'description': 'Comprehensive performance metrics and analytics',
                    'default_days': 30
                },
                {
                    'type': 'ab_test',
                    'name': 'A/B Test Report',
                    'description': 'A/B testing results and analysis',
                    'default_days': 30
                },
                {
                    'type': 'business',
                    'name': 'Business Report',
                    'description': 'Revenue and conversion metrics',
                    'default_days': 30
                }
            ]
            
            return Response({
                'success': True,
                'reports': reports
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
