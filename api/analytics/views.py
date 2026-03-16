from rest_framework import viewsets, status, filters, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Sum, Avg, Count, Q, F, Max, Min
from django.db.models.functions import TruncDate, TruncMonth, TruncYear
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, JsonResponse, FileResponse
from django.core.cache import cache
import pandas as pd
from datetime import datetime, timedelta
import json
import csv
import io

from .models import (
    AnalyticsEvent, UserAnalytics, RevenueAnalytics,
    OfferPerformanceAnalytics, FunnelAnalytics, RetentionAnalytics,
    Dashboard, Report, RealTimeMetric, AlertRule, AlertHistory
)
from .serializers import (
    AnalyticsEventSerializer, UserAnalyticsSerializer, RevenueAnalyticsSerializer,
    OfferPerformanceAnalyticsSerializer, FunnelAnalyticsSerializer,
    RetentionAnalyticsSerializer, DashboardSerializer, ReportSerializer,
    RealTimeMetricSerializer, AlertRuleSerializer, AlertHistorySerializer,
    AnalyticsSummarySerializer, TimeSeriesDataSerializer, ExportAnalyticsSerializer
)
# from .collectors import (
#     UserAnalyticsCollector, RevenueCollector, OfferPerformanceCollector
# )
# from .processors import DataProcessor, ReportGenerator, ChartDataBuilder
# from .reports import PDFReport, ExcelReport, HTMLReport
# from .dashboards import AdminDashboard, RealTimeDashboard, UserDashboard

# Permissions
class IsAdminOrReadOnly(IsAuthenticated):
    """Allow admin users to edit, authenticated users to view"""
    def has_permission(self, request, view):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_staff

class IsDashboardOwnerOrAdmin(IsAuthenticated):
    """Allow dashboard owners and admins to edit"""
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.created_by == request.user or request.user in obj.allowed_users.all()

# ViewSets
class AnalyticsEventViewSet(viewsets.ModelViewSet):
    """ViewSet for analytics events"""
    queryset = AnalyticsEvent.objects.all()
    serializer_class = AnalyticsEventSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['event_type', 'user', 'device_type', 'country', 'session_id']
    search_fields = ['user__username', 'user__email', 'ip_address', 'user_agent']
    ordering_fields = ['event_time', 'created_at', 'value']
    ordering = ['-event_time']
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = super().get_queryset()
        
        # Non-admin users can only see their own events
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        
        # Date filtering
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(event_time__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(event_time__date__lte=end_date)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def event_types(self, request):
        """Get list of event types with counts"""
        event_types = AnalyticsEvent.objects.values('event_type').annotate(
            count=Count('id'),
            latest=Max('event_time')
        ).order_by('-count')
        
        return Response(event_types)
    
    @action(detail=False, methods=['get'])
    def timeline(self, request):
        """Get events timeline for visualization"""
        interval = request.query_params.get('interval', 'hour')  # hour, day, week, month
        
        trunc_map = {
            'hour': TruncDate('event_time'),
            'day': TruncDate('event_time'),
            'week': TruncDate('event_time'),
            'month': TruncMonth('event_time'),
        }
        
        trunc_func = trunc_map.get(interval, TruncDate('event_time'))
        
        timeline = AnalyticsEvent.objects.annotate(
            period=trunc_func
        ).values('period', 'event_type').annotate(
            count=Count('id')
        ).order_by('period')
        
        return Response(timeline)
    
    @action(detail=False, methods=['post'])
    def track_event(self, request):
        """Track an analytics event from frontend"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Add user if authenticated
        if request.user.is_authenticated:
            serializer.validated_data['user'] = request.user
        
        # Add IP address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        serializer.validated_data['ip_address'] = ip
        
        # Add user agent
        serializer.validated_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
        
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class UserAnalyticsViewSet(viewsets.ModelViewSet):
    """ViewSet for user analytics"""
    queryset = UserAnalytics.objects.all()
    serializer_class = UserAnalyticsSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['user', 'period', 'is_retained']
    ordering_fields = ['period_start', 'earnings_total', 'engagement_score']
    ordering = ['-period_start']
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = super().get_queryset()
        
        # Non-admin users can only see their own analytics
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        
        # Date filtering
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(period_start__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(period_end__date__lte=end_date)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def my_analytics(self, request):
        """Get current user's analytics"""
        collector = UserAnalyticsCollector()
        analytics = collector.collect_user_analytics(request.user, 'daily')
        
        serializer = self.get_serializer(analytics)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        """Get user leaderboard"""
        period = request.query_params.get('period', 'daily')
        limit = int(request.query_params.get('limit', 10))
        
        # Get top users by earnings
        top_users = UserAnalytics.objects.filter(
            period=period,
            period_start__gte=timezone.now() - timedelta(days=30)
        ).values(
            'user__id', 'user__username', 'user__email'
        ).annotate(
            total_earnings=Sum('earnings_total'),
            tasks_completed=Sum('tasks_completed'),
            engagement_score=Avg('engagement_score')
        ).order_by('-total_earnings')[:limit]
        
        return Response(top_users)
    
    @action(detail=False, methods=['get'])
    def retention_curve(self, request):
        """Get user retention curve"""
        user_id = request.query_params.get('user_id')
        if user_id:
            user_analytics = UserAnalytics.objects.filter(user_id=user_id)
        elif request.user.is_authenticated and not request.user.is_staff:
            user_analytics = UserAnalytics.objects.filter(user=request.user)
        else:
            user_analytics = UserAnalytics.objects.all()
        
        # Group by period and calculate retention
        retention_data = user_analytics.values('period').annotate(
            avg_retention=Avg('is_retained') * 100,
            user_count=Count('user', distinct=True)
        ).order_by('period')
        
        return Response(retention_data)

class RevenueAnalyticsViewSet(viewsets.ModelViewSet):
    """ViewSet for revenue analytics"""
    queryset = RevenueAnalytics.objects.all()
    serializer_class = RevenueAnalyticsSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['period']
    ordering_fields = ['period_start', 'revenue_total', 'profit_margin']
    ordering = ['-period_start']
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get revenue summary"""
        collector = RevenueCollector()
        
        # Get daily, weekly, monthly summaries
        daily = collector.calculate_daily_revenue()
        weekly = collector.calculate_weekly_revenue()
        monthly = collector.calculate_monthly_revenue()
        
        data = {
            'daily': daily,
            'weekly': weekly,
            'monthly': monthly,
            'trends': collector.calculate_revenue_trends()
        }
        
        return Response(data)
    
    @action(detail=False, methods=['get'])
    def sources(self, request):
        """Get revenue by source breakdown"""
        period = request.query_params.get('period', 'monthly')
        limit = int(request.query_params.get('limit', 5))
        
        revenue_by_source = RevenueAnalytics.objects.filter(
            period=period,
            period_start__gte=timezone.now() - timedelta(days=365)
        ).values('revenue_by_source')
        
        # Aggregate revenue by source
        source_totals = {}
        for item in revenue_by_source:
            for source, amount in item['revenue_by_source'].items():
                if source in source_totals:
                    source_totals[source] += amount
                else:
                    source_totals[source] = amount
        
        # Sort and limit
        sorted_sources = sorted(source_totals.items(), key=lambda x: x[1], reverse=True)[:limit]
        
        return Response({
            'sources': dict(sorted_sources),
            'total': sum(source_totals.values())
        })
    
    @action(detail=False, methods=['get'])
    def forecast(self, request):
        """Get revenue forecast"""
        periods = int(request.query_params.get('periods', 6))
        
        processor = DataProcessor()
        forecast = processor.forecast_revenue(periods)
        
        return Response(forecast)

class OfferPerformanceViewSet(viewsets.ModelViewSet):
    """ViewSet for offer performance analytics"""
    queryset = OfferPerformanceAnalytics.objects.all()
    serializer_class = OfferPerformanceAnalyticsSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['offer', 'period']
    search_fields = ['offer__name', 'offer__description']
    ordering_fields = ['period_start', 'completion_rate', 'roi']
    ordering = ['-period_start']
    
    @action(detail=False, methods=['get'])
    def top_performing(self, request):
        """Get top performing offers"""
        period = request.query_params.get('period', 'monthly')
        limit = int(request.query_params.get('limit', 10))
        metric = request.query_params.get('metric', 'roi')
        
        order_by_map = {
            'roi': '-roi',
            'completion_rate': '-completion_rate',
            'revenue': '-revenue_generated',
            'clicks': '-clicks'
        }
        
        order_by = order_by_map.get(metric, '-roi')
        
        top_offers = OfferPerformanceAnalytics.objects.filter(
            period=period,
            period_start__gte=timezone.now() - timedelta(days=90)
        ).select_related('offer').order_by(order_by)[:limit]
        
        serializer = self.get_serializer(top_offers, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def funnel(self, request, pk=None):
        """Get offer conversion funnel"""
        offer_analytics = self.get_object()
        
        funnel_data = {
            'impressions': offer_analytics.impressions,
            'clicks': offer_analytics.clicks,
            'completions': offer_analytics.completions,
            'conversion_rates': {
                'impression_to_click': offer_analytics.click_through_rate,
                'click_to_completion': offer_analytics.engagement_rate,
                'impression_to_completion': offer_analytics.completion_rate
            }
        }
        
        return Response(funnel_data)
    
    @action(detail=False, methods=['get'])
    def comparison(self, request):
        """Compare multiple offers"""
        offer_ids = request.query_params.get('offer_ids', '').split(',')
        period = request.query_params.get('period', 'monthly')
        
        if not offer_ids or offer_ids[0] == '':
            return Response({'error': 'No offer IDs provided'}, status=400)
        
        offers_analytics = OfferPerformanceAnalytics.objects.filter(
            offer_id__in=offer_ids,
            period=period,
            period_start__gte=timezone.now() - timedelta(days=30)
        ).select_related('offer')
        
        comparison_data = []
        for analytics in offers_analytics:
            comparison_data.append({
                'offer_id': analytics.offer.id,
                'offer_name': analytics.offer.name,
                'impressions': analytics.impressions,
                'clicks': analytics.clicks,
                'completions': analytics.completions,
                'ctr': analytics.click_through_rate,
                'completion_rate': analytics.completion_rate,
                'revenue': float(analytics.revenue_generated),
                'roi': analytics.roi
            })
        
        return Response(comparison_data)

class DashboardViewSet(viewsets.ModelViewSet):
    """ViewSet for dashboards"""
    queryset = Dashboard.objects.all()
    serializer_class = DashboardSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['dashboard_type', 'is_public']
    search_fields = ['name', 'description']
    
    def get_queryset(self):
        """Filter dashboards based on user permissions"""
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_staff:
            return queryset
        
        role_q = Q(allowed_roles__contains=[user.role]) if hasattr(user, 'role') else Q()
        return queryset.filter(
            Q(is_public=True) |
            Q(allowed_users=user) |
            Q(created_by=user) |
            role_q
            ).distinct()
    
    def perform_create(self, serializer):
        """Set created_by when creating dashboard"""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def data(self, request, pk=None):
        """Get dashboard data"""
        dashboard = self.get_object()
        
        # Get dashboard type specific data
        if dashboard.dashboard_type == 'admin':
            dashboard_builder = AdminDashboard()
        elif dashboard.dashboard_type == 'realtime':
            dashboard_builder = RealTimeDashboard()
        elif dashboard.dashboard_type == 'user':
            dashboard_builder = UserDashboard(request.user)
        else:
            dashboard_builder = AdminDashboard()
        
        dashboard_data = dashboard_builder.get_data()
        
        return Response({
            'dashboard': self.get_serializer(dashboard).data,
            'data': dashboard_data
        })
    
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """Clone a dashboard"""
        dashboard = self.get_object()
        
        # Create clone
        clone = Dashboard.objects.create(
            name=f"{dashboard.name} (Copy)",
            dashboard_type=dashboard.dashboard_type,
            description=dashboard.description,
            layout_config=dashboard.layout_config,
            widget_configs=dashboard.widget_configs,
            is_public=dashboard.is_public,
            refresh_interval=dashboard.refresh_interval,
            default_time_range=dashboard.default_time_range,
            created_by=request.user
        )
        
        # Copy allowed users
        clone.allowed_users.set(dashboard.allowed_users.all())
        
        serializer = self.get_serializer(clone)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def export(self, request, pk=None):
        """Export dashboard configuration"""
        dashboard = self.get_object()
        
        export_data = {
            'name': dashboard.name,
            'dashboard_type': dashboard.dashboard_type,
            'description': dashboard.description,
            'layout_config': dashboard.layout_config,
            'widget_configs': dashboard.widget_configs,
            'exported_at': timezone.now().isoformat(),
            'exported_by': request.user.username
        }
        
        # Create response
        response = HttpResponse(
            json.dumps(export_data, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="{dashboard.name}.json"'
        
        return response

class ReportViewSet(viewsets.ModelViewSet):
    """ViewSet for reports"""
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['report_type', 'format', 'status', 'generated_by']
    search_fields = ['name', 'parameters']
    ordering_fields = ['generated_at', 'name']
    ordering = ['-generated_at']
    
    def get_queryset(self):
        """Filter reports based on user permissions"""
        queryset = super().get_queryset()
        
        if not self.request.user.is_staff:
            queryset = queryset.filter(generated_by=self.request.user)
        
        return queryset
    
    def perform_create(self, serializer):
        """Set generated_by when creating report"""
        serializer.save(generated_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download report file"""
        report = self.get_object()
        
        if report.file:
            return FileResponse(report.file.open(), as_attachment=True, filename=report.file.name)
        elif report.file_url:
            return Response({'url': report.file_url})
        else:
            return Response({'error': 'Report file not available'}, status=404)
    
    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Generate a new report"""
        report_type = request.data.get('report_type')
        format = request.data.get('format', 'pdf')
        parameters = request.data.get('parameters', {})
        
        # Validate parameters
        if not report_type:
            return Response({'error': 'report_type is required'}, status=400)
        
        # Create report generator
        generator = ReportGenerator()
        
        try:
            # Generate report
            report = generator.generate_report(
                report_type=report_type,
                format=format,
                parameters=parameters,
                user=request.user
            )
            
            serializer = self.get_serializer(report)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def schedule(self, request):
        """Schedule report generation"""
        from celery import shared_task
        
        report_type = request.data.get('report_type')
        format = request.data.get('format', 'pdf')
        parameters = request.data.get('parameters', {})
        schedule_time = request.data.get('schedule_time')
        frequency = request.data.get('frequency')  # daily, weekly, monthly
        
        if not report_type:
            return Response({'error': 'report_type is required'}, status=400)
        
        # Schedule report generation
        task_id = f"report_{report_type}_{request.user.id}_{datetime.now().timestamp()}"
        
        # Here you would schedule the Celery task
        # generate_report_task.apply_async(
        #     args=[report_type, format, parameters, request.user.id],
        #     eta=schedule_time,
        #     task_id=task_id
        # )
        
        return Response({
            'message': 'Report generation scheduled',
            'task_id': task_id,
            'scheduled_for': schedule_time
        })

class RealTimeMetricsView(APIView):
    """API for real-time metrics"""
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        """Get real-time metrics"""
        metric_type = request.query_params.get('metric_type')
        time_range = request.query_params.get('time_range', '5min')  # 5min, hour, day
        limit = int(request.query_params.get('limit', 100))
        
        # Calculate time range
        time_ranges = {
            '5min': timedelta(minutes=5),
            'hour': timedelta(hours=1),
            'day': timedelta(days=1),
            'week': timedelta(weeks=1)
        }
        
        time_delta = time_ranges.get(time_range, timedelta(minutes=5))
        start_time = timezone.now() - time_delta
        
        # Query metrics
        metrics = RealTimeMetric.objects.filter(
            metric_time__gte=start_time
        )
        
        if metric_type:
            metrics = metrics.filter(metric_type=metric_type)
        
        metrics = metrics.order_by('-metric_time')[:limit]
        
        serializer = RealTimeMetricSerializer(metrics, many=True)
        
        # Calculate aggregates
        if metric_type and metrics:
            values = [m.value for m in metrics]
            aggregates = {
                'current': values[0] if values else 0,
                'average': sum(values) / len(values) if values else 0,
                'min': min(values) if values else 0,
                'max': max(values) if values else 0,
                'trend': self.calculate_trend(values)
            }
        else:
            aggregates = {}
        
        return Response({
            'metrics': serializer.data,
            'aggregates': aggregates,
            'time_range': time_range,
            'from_time': start_time,
            'to_time': timezone.now()
        })
    
    def calculate_trend(self, values):
        """Calculate trend from values"""
        if len(values) < 2:
            return 0
        
        # Simple linear trend
        first = values[-1]  # Most recent
        last = values[0]   # Oldest in the queryset
        
        if last == 0:
            return 0
        
        return ((first - last) / last) * 100
    
    def post(self, request):
        """Record a real-time metric"""
        serializer = RealTimeMetricSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Analytics Summary Views
class AnalyticsSummaryView(APIView):
    """Get analytics summary"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get comprehensive analytics summary"""
        
        # Check cache first
        cache_key = f"analytics_summary_{request.user.id}"
        cached_data = cache.get(cache_key)
        
        if cached_data and not request.user.is_staff:  # Admins get fresh data
            return Response(cached_data)
        from django.contrib.auth import get_user_model
        from django.db.models import Sum, Count
        User = get_user_model()
        today = timezone.now().date()
        total_users = User.objects.count()
        active_users = User.objects.filter(last_login__gte=timezone.now() - timedelta(days=7)).count()
        new_users_today = User.objects.filter(date_joined__date=today).count()
        from api.analytics.models import RevenueAnalytics, AnalyticsEvent
        revenue_today = RevenueAnalytics.objects.filter(period_start__date=today).aggregate(t=Sum("revenue_total"))["t"] or 0
        revenue_month = RevenueAnalytics.objects.filter(period_start__year=today.year, period_start__month=today.month).aggregate(t=Sum("revenue_total"))["t"] or 0
        tasks_today = AnalyticsEvent.objects.filter(event_type="task_completed", event_time__date=today).count()
        offers_today = AnalyticsEvent.objects.filter(event_type="offer_completed", event_time__date=today).count()
        withdrawals_today = AnalyticsEvent.objects.filter(event_type="withdrawal_processed", event_time__date=today).count()
        summary_data = {
            "total_users": total_users,
            "active_users": active_users,
            "new_users_today": new_users_today,
            "revenue_today": float(revenue_today),
            "revenue_this_month": float(revenue_month),
            "tasks_completed_today": tasks_today,
            "offers_completed_today": offers_today,
            "withdrawals_processed_today": withdrawals_today,
            "conversion_rate": round((offers_today / active_users * 100), 2) if active_users > 0 else 0,
            "avg_engagement_score": 0,
            "revenue_trend": 0,
            "user_growth_trend": 0,
            "task_completion_trend": 0,
            "system_uptime": 99.9,
            "avg_response_time": 150,
            "error_rate": 0.1
        }
        cache.set(cache_key, summary_data, 300)
        
        serializer = AnalyticsSummarySerializer(summary_data)
        return Response(serializer.data)

# Chart Data Views
class ChartDataView(APIView):
    """Get data for charts"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get chart data based on parameters"""
        chart_type = request.query_params.get('chart_type')
        time_range = request.query_params.get('time_range', '7d')
        metric = request.query_params.get('metric', 'revenue')
        
        if not chart_type:
            return Response({'error': 'chart_type is required'}, status=400)
        
        # Build chart data
        builder = ChartDataBuilder()
        
        try:
            if chart_type == 'time_series':
                data = builder.build_time_series_data(metric, time_range)
            elif chart_type == 'bar':
                data = builder.build_bar_chart_data(metric, time_range)
            elif chart_type == 'pie':
                data = builder.build_pie_chart_data(metric)
            elif chart_type == 'funnel':
                data = builder.build_funnel_chart_data(metric)
            else:
                return Response({'error': 'Invalid chart type'}, status=400)
            
            serializer = TimeSeriesDataSerializer(data)
            return Response(serializer.data)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Export Views
class ExportAnalyticsView(APIView):
    """Export analytics data"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Export analytics data in specified format"""
        serializer = ExportAnalyticsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        
        data = serializer.validated_data
        format = data['format']
        
        # Collect data based on metrics
        all_data = []
        
        if 'user_activity' in data['metrics'] or 'all' in data['metrics']:
            user_data = UserAnalytics.objects.filter(
                period_start__date__gte=data['start_date'],
                period_end__date__lte=data['end_date']
            ).values()
            all_data.extend(list(user_data))
        
        if 'revenue' in data['metrics'] or 'all' in data['metrics']:
            revenue_data = RevenueAnalytics.objects.filter(
                period_start__date__gte=data['start_date'],
                period_end__date__lte=data['end_date']
            ).values()
            all_data.extend(list(revenue_data))
        
        if 'offer_performance' in data['metrics'] or 'all' in data['metrics']:
            offer_data = OfferPerformanceAnalytics.objects.filter(
                period_start__date__gte=data['start_date'],
                period_end__date__lte=data['end_date']
            ).values()
            all_data.extend(list(offer_data))
        
        # Convert to DataFrame for processing
        df = pd.DataFrame(all_data)
        
        # Group by if specified
        if not df.empty and data['group_by'] and 'period_start' in df.columns:
            if data['group_by'] == 'day':
                df['group'] = pd.to_datetime(df['period_start']).dt.date
            elif data['group_by'] == 'week':
                df['group'] = pd.to_datetime(df['period_start']).dt.strftime('%Y-W%U')
            elif data['group_by'] == 'month':
                df['group'] = pd.to_datetime(df['period_start']).dt.strftime('%Y-%m')
        
        # Export based on format
        if format == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="analytics_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            
            df.to_csv(response, index=False)
            return response
            
        elif format == 'excel':
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="analytics_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
            
            with pd.ExcelWriter(response, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Analytics')
            
            return response
            
        elif format == 'json':
            return JsonResponse(df.to_dict(orient='records'), safe=False)
        
        return Response({'error': 'Invalid format'}, status=400)

# Alert Views
class AlertRuleViewSet(viewsets.ModelViewSet):
    """ViewSet for alert rules"""
    queryset = AlertRule.objects.all()
    serializer_class = AlertRuleSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['alert_type', 'severity', 'is_active', 'metric_type']
    search_fields = ['name', 'description']
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test alert rule"""
        alert_rule = self.get_object()
        
        # Test the rule
        from .processors import DataProcessor
        processor = DataProcessor()
        
        test_result = processor.test_alert_rule(alert_rule)
        
        return Response(test_result)
    
    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Toggle alert rule active status"""
        alert_rule = self.get_object()
        alert_rule.is_active = not alert_rule.is_active
        alert_rule.save()
        
        serializer = self.get_serializer(alert_rule)
        return Response(serializer.data)

class AlertHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for alert history"""
    queryset = AlertHistory.objects.all()
    serializer_class = AlertHistorySerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['rule', 'severity', 'is_resolved']
    ordering_fields = ['triggered_at', 'severity']
    ordering = ['-triggered_at']
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve an alert"""
        alert = self.get_object()
        
        if alert.is_resolved:
            return Response({'message': 'Alert already resolved'})
        
        alert.is_resolved = True
        alert.resolved_at = timezone.now()
        alert.resolved_by = request.user
        alert.resolution_notes = request.data.get('resolution_notes', '')
        alert.save()
        
        serializer = self.get_serializer(alert)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def unresolved(self, request):
        """Get unresolved alerts"""
        unresolved = self.get_queryset().filter(is_resolved=False)
        serializer = self.get_serializer(unresolved, many=True)
        return Response(serializer.data)

# Real-time Dashboard WebSocket (conceptual)
@api_view(['GET'])
@permission_classes([IsAdminUser])
def real_time_ws_token(request):
    """Get WebSocket token for real-time dashboard"""
    from django.contrib.auth.models import User
    import jwt
    import secrets
    
    # Generate token
    token = jwt.encode({
        'user_id': request.user.id,
        'username': request.user.username,
        'exp': datetime.now() + timedelta(hours=1)
    }, secrets.token_urlsafe(32), algorithm='HS256')
    
    return Response({
        'token': token,
        'ws_url': f'wss://{request.get_host()}/ws/analytics/realtime/'
    })
    
    
    
    
    # ── views.py তে এই দুটো ViewSet add করুন ─────────────────────────────────────

class FunnelAnalyticsViewSet(viewsets.ModelViewSet):
    """ViewSet for funnel analytics"""
    queryset = FunnelAnalytics.objects.all()
    serializer_class = FunnelAnalyticsSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['funnel_type', 'period']
    ordering_fields = ['period_start', 'conversion_rate']
    ordering = ['-period_start']

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Get funnel data grouped by funnel type"""
        funnel_type = request.query_params.get('funnel_type')
        if not funnel_type:
            return Response({'error': 'funnel_type is required'}, status=400)

        funnels = self.get_queryset().filter(funnel_type=funnel_type)
        serializer = self.get_serializer(funnels, many=True)
        return Response(serializer.data)


class RetentionAnalyticsViewSet(viewsets.ModelViewSet):
    """ViewSet for retention analytics"""
    queryset = RetentionAnalytics.objects.all()
    serializer_class = RetentionAnalyticsSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['cohort_type']
    ordering_fields = ['cohort_date', 'retention_day_7', 'churn_rate']
    ordering = ['-cohort_date']

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get retention summary across all cohorts"""
        cohort_type = request.query_params.get('cohort_type', 'monthly')

        summary = RetentionAnalytics.objects.filter(
            cohort_type=cohort_type
        ).aggregate(
            avg_d1=Avg('retention_day_1'),
            avg_d7=Avg('retention_day_7'),
            avg_d30=Avg('retention_day_30'),
            avg_churn=Avg('churn_rate'),
            total_users=Sum('total_users'),
        )

        return Response(summary)


# ── views.py তে এই HealthCheckView টাও add করুন ───────────────────────────────

class HealthCheckView(APIView):
    """Simple health check — no auth required"""
    permission_classes = []

    def get(self, request):
        return Response({
            'status': 'ok',
            'timestamp': timezone.now().isoformat(),
        })