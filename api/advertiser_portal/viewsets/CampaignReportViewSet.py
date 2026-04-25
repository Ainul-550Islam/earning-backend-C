"""
Campaign Report ViewSet

ViewSet for campaign performance dashboard,
including metrics, analytics, and reporting.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from django.db.models import Case, When

from ..models.campaign import AdCampaign
from ..models.reporting import CampaignReport
try:
    from ..services import RealtimeDashboardService
except ImportError:
    RealtimeDashboardService = None
from ..serializers import CampaignReportSerializer
from ..permissions import IsAdvertiserOrReadOnly, IsOwnerOrReadOnly
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class CampaignReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for campaign performance dashboard.
    
    Handles metrics, analytics, and reporting
    for campaign performance.
    """
    
    queryset = CampaignReport.objects.all()
    serializer_class = CampaignReportSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdvertiserOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        if user.is_staff:
            # Admin can see all reports
            return CampaignReport.objects.all()
        else:
            # Advertisers can only see their own reports
            return CampaignReport.objects.filter(campaign__advertiser__user=user)
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """
        Get campaign performance dashboard.
        
        Returns comprehensive dashboard with metrics and analytics.
        """
        try:
            dashboard_service = RealtimeDashboardService()
            dashboard_data = dashboard_service.get_dashboard_overview(request.user.advertiser)
            
            return Response(dashboard_data)
            
        except Exception as e:
            logger.error(f"Error getting dashboard: {e}")
            return Response(
                {'detail': 'Failed to get dashboard data'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def live_metrics(self, request):
        """
        Get live performance metrics.
        
        Returns real-time campaign performance data.
        """
        try:
            time_range = request.query_params.get('time_range', '24h')
            dashboard_service = RealtimeDashboardService()
            
            live_data = dashboard_service.get_live_metrics(request.user.advertiser, time_range)
            
            return Response(live_data)
            
        except Exception as e:
            logger.error(f"Error getting live metrics: {e}")
            return Response(
                {'detail': 'Failed to get live metrics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def campaign_performance(self, request):
        """
        Get campaign performance overview.
        
        Returns performance data for all campaigns.
        """
        try:
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get campaign reports for the period
            campaign_reports = CampaignReport.objects.filter(
                campaign__advertiser=request.user.advertiser,
                date__gte=start_date,
                date__lte=end_date
            ).select_related('campaign')
            
            # Aggregate performance data
            performance_data = campaign_reports.aggregate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_spend=Sum('spend_amount'),
                avg_ctr=Avg('ctr'),
                avg_conversion_rate=Avg('conversion_rate'),
                avg_cpa=Avg('cpa'),
                avg_cpc=Avg('cpc'),
                campaign_count=Count('campaign', distinct=True),
            )
            
            # Fill missing values
            for key, value in performance_data.items():
                if value is None:
                    performance_data[key] = 0
            
            # Calculate derived metrics
            total_impressions = performance_data['total_impressions']
            total_clicks = performance_data['total_clicks']
            total_conversions = performance_data['total_conversions']
            total_spend = performance_data['total_spend']
            
            calculated_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            calculated_cpc = (total_spend / total_clicks) if total_clicks > 0 else 0
            calculated_cpa = (total_spend / total_conversions) if total_conversions > 0 else 0
            
            # Get campaign breakdown
            campaign_breakdown = campaign_reports.values(
                'campaign__id', 'campaign__name'
            ).annotate(
                impressions=Sum('impressions'),
                clicks=Sum('clicks'),
                conversions=Sum('conversions'),
                spend=Sum('spend_amount')
            ).order_by('-spend')
            
            # Get daily breakdown
            daily_breakdown = {}
            current_date = start_date.date()
            while current_date <= end_date:
                day_reports = campaign_reports.filter(date=current_date)
                day_data = day_reports.aggregate(
                    impressions=Sum('impressions'),
                    clicks=Sum('clicks'),
                    conversions=Sum('conversions'),
                    spend=Sum('spend_amount')
                )
                
                daily_breakdown[current_date.isoformat()] = {
                    'impressions': day_data['impressions'] or 0,
                    'clicks': day_data['clicks'] or 0,
                    'conversions': day_data['conversions'] or 0,
                    'spend': float(day_data['spend'] or 0),
                }
                
                current_date += timezone.timedelta(days=1)
            
            return Response({
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days,
                },
                'summary': {
                    'total_impressions': total_impressions,
                    'total_clicks': total_clicks,
                    'total_conversions': total_conversions,
                    'total_spend': float(total_spend),
                    'campaign_count': performance_data['campaign_count'],
                    'ctr': float(calculated_ctr),
                    'cpc': float(calculated_cpc),
                    'cpa': float(calculated_cpa),
                    'conversion_rate': float((total_conversions / total_clicks * 100) if total_clicks > 0 else 0),
                },
                'campaign_breakdown': [
                    {
                        'campaign_id': item['campaign__id'],
                        'campaign_name': item['campaign__name'],
                        'impressions': item['impressions'] or 0,
                        'clicks': item['clicks'] or 0,
                        'conversions': item['conversions'] or 0,
                        'spend': float(item['spend'] or 0),
                        'ctr': float((item['clicks'] / item['impressions'] * 100) if item['impressions'] and item['clicks'] else 0),
                        'cpa': float((item['spend'] / item['conversions']) if item['conversions'] and item['spend'] else 0),
                    }
                    for item in campaign_breakdown
                ],
                'daily_breakdown': daily_breakdown,
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting campaign performance: {e}")
            return Response(
                {'detail': 'Failed to get campaign performance'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def top_campaigns(self, request):
        """
        Get top performing campaigns.
        
        Returns campaigns ranked by performance metrics.
        """
        try:
            metric = request.query_params.get('metric', 'spend')
            limit = int(request.query_params.get('limit', 10))
            days = int(request.query_params.get('days', 30))
            
            start_date = timezone.now() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get campaign reports for the period
            campaign_reports = CampaignReport.objects.filter(
                campaign__advertiser=request.user.advertiser,
                date__gte=start_date,
                date__lte=end_date
            ).select_related('campaign')
            
            # Aggregate by campaign
            campaign_data = campaign_reports.values(
                'campaign__id', 'campaign__name'
            ).annotate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_spend=Sum('spend_amount'),
                avg_ctr=Avg('ctr'),
                avg_conversion_rate=Avg('conversion_rate'),
                avg_cpa=Avg('cpa'),
            )
            
            # Sort by requested metric
            if metric == 'spend':
                campaign_data = campaign_data.order_by('-total_spend')
            elif metric == 'impressions':
                campaign_data = campaign_data.order_by('-total_impressions')
            elif metric == 'clicks':
                campaign_data = campaign_data.order_by('-total_clicks')
            elif metric == 'conversions':
                campaign_data = campaign_data.order_by('-total_conversions')
            elif metric == 'ctr':
                campaign_data = campaign_data.order_by('-avg_ctr')
            elif metric == 'conversion_rate':
                campaign_data = campaign_data.order_by('-avg_conversion_rate')
            elif metric == 'cpa':
                campaign_data = campaign_data.order_by('avg_cpa')  # Lower CPA is better
            else:
                campaign_data = campaign_data.order_by('-total_spend')
            
            top_campaigns = campaign_data[:limit]
            
            return Response({
                'metric': metric,
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days,
                },
                'top_campaigns': [
                    {
                        'campaign_id': item['campaign__id'],
                        'campaign_name': item['campaign__name'],
                        'total_impressions': item['total_impressions'] or 0,
                        'total_clicks': item['total_clicks'] or 0,
                        'total_conversions': item['total_conversions'] or 0,
                        'total_spend': float(item['total_spend'] or 0),
                        'avg_ctr': float(item['avg_ctr'] or 0),
                        'avg_conversion_rate': float(item['avg_conversion_rate'] or 0),
                        'avg_cpa': float(item['avg_cpa'] or 0),
                    }
                    for item in top_campaigns
                ],
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting top campaigns: {e}")
            return Response(
                {'detail': 'Failed to get top campaigns'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def performance_comparison(self, request):
        """
        Get performance comparison.
        
        Compares performance between different periods.
        """
        try:
            comparison_period = request.query_params.get('comparison_period', 'previous_period')
            days = int(request.query_params.get('days', 30))
            
            dashboard_service = RealtimeDashboardService()
            comparison_data = dashboard_service.get_performance_comparison(
                request.user.advertiser, comparison_period
            )
            
            return Response(comparison_data)
            
        except Exception as e:
            logger.error(f"Error getting performance comparison: {e}")
            return Response(
                {'detail': 'Failed to get performance comparison'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def alerts(self, request):
        """
        Get performance alerts.
        
        Returns alerts and recommendations for campaigns.
        """
        try:
            dashboard_service = RealtimeDashboardService()
            alerts = dashboard_service.get_real_time_alerts(request.user.advertiser)
            
            return Response({
                'alerts': alerts,
                'count': len(alerts),
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            return Response(
                {'detail': 'Failed to get alerts'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def metrics_trends(self, request):
        """
        Get metrics trends.
        
        Returns trend analysis for key metrics.
        """
        try:
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get daily reports
            daily_reports = CampaignReport.objects.filter(
                campaign__advertiser=request.user.advertiser,
                date__gte=start_date,
                date__lte=end_date
            ).values('date').annotate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_spend=Sum('spend_amount')
            ).order_by('date')
            
            # Calculate trends
            if len(daily_reports) >= 2:
                mid_point = len(daily_reports) // 2
                recent_avg = daily_reports[mid_point:].aggregate(
                    avg_spend=Avg('total_spend'),
                    avg_conversions=Avg('total_conversions'),
                    avg_clicks=Avg('total_clicks')
                )
                
                older_avg = daily_reports[:mid_point].aggregate(
                    avg_spend=Avg('total_spend'),
                    avg_conversions=Avg('total_conversions'),
                    avg_clicks=Avg('total_clicks')
                )
                
                spend_trend = 'up' if recent_avg['avg_spend'] > older_avg['avg_spend'] else 'down'
                conversion_trend = 'up' if recent_avg['avg_conversions'] > older_avg['avg_conversions'] else 'down'
                click_trend = 'up' if recent_avg['avg_clicks'] > older_avg['avg_clicks'] else 'down'
            else:
                spend_trend = 'stable'
                conversion_trend = 'stable'
                click_trend = 'stable'
            
            return Response({
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days,
                },
                'trends': {
                    'spend_trend': spend_trend,
                    'conversion_trend': conversion_trend,
                    'click_trend': click_trend,
                },
                'daily_data': [
                    {
                        'date': item['date'].isoformat(),
                        'impressions': item['total_impressions'] or 0,
                        'clicks': item['total_clicks'] or 0,
                        'conversions': item['total_conversions'] or 0,
                        'spend': float(item['total_spend'] or 0),
                    }
                    for item in daily_reports
                ],
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting metrics trends: {e}")
            return Response(
                {'detail': 'Failed to get metrics trends'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def time_range_options(self, request):
        """
        Get available time range options.
        
        Returns list of supported time ranges for reporting.
        """
        try:
            time_ranges = {
                '1h': {
                    'name': 'Last Hour',
                    'description': 'Performance data from the last hour',
                    'suitable_for': 'Real-time monitoring',
                },
                '24h': {
                    'name': 'Last 24 Hours',
                    'description': 'Performance data from the last day',
                    'suitable_for': 'Daily performance tracking',
                },
                '7d': {
                    'name': 'Last 7 Days',
                    'description': 'Performance data from the last week',
                    'suitable_for': 'Weekly performance review',
                },
                '30d': {
                    'name': 'Last 30 Days',
                    'description': 'Performance data from the last month',
                    'suitable_for': 'Monthly performance analysis',
                },
                '90d': {
                    'name': 'Last 90 Days',
                    'description': 'Performance data from the last quarter',
                    'suitable_for': 'Quarterly performance review',
                },
            }
            
            return Response(time_ranges)
            
        except Exception as e:
            logger.error(f"Error getting time range options: {e}")
            return Response(
                {'detail': 'Failed to get time range options'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def metric_definitions(self, request):
        """
        Get metric definitions.
        
        Returns explanations of available metrics.
        """
        try:
            metrics = {
                'impressions': {
                    'name': 'Impressions',
                    'description': 'Number of times ads were shown',
                    'unit': 'count',
                    'higher_is_better': True,
                },
                'clicks': {
                    'name': 'Clicks',
                    'description': 'Number of times ads were clicked',
                    'unit': 'count',
                    'higher_is_better': True,
                },
                'conversions': {
                    'name': 'Conversions',
                    'description': 'Number of completed actions',
                    'unit': 'count',
                    'higher_is_better': True,
                },
                'spend': {
                    'name': 'Spend',
                    'description': 'Total amount spent on ads',
                    'unit': 'currency',
                    'higher_is_better': False,
                },
                'ctr': {
                    'name': 'Click Through Rate',
                    'description': 'Percentage of impressions that resulted in clicks',
                    'unit': 'percentage',
                    'higher_is_better': True,
                },
                'conversion_rate': {
                    'name': 'Conversion Rate',
                    'description': 'Percentage of clicks that resulted in conversions',
                    'unit': 'percentage',
                    'higher_is_better': True,
                },
                'cpc': {
                    'name': 'Cost Per Click',
                    'description': 'Average cost per click',
                    'unit': 'currency',
                    'higher_is_better': False,
                },
                'cpa': {
                    'name': 'Cost Per Acquisition',
                    'description': 'Average cost per conversion',
                    'unit': 'currency',
                    'higher_is_better': False,
                },
            }
            
            return Response(metrics)
            
        except Exception as e:
            logger.error(f"Error getting metric definitions: {e}")
            return Response(
                {'detail': 'Failed to get metric definitions'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def export_report(self, request):
        """
        Export campaign report.
        
        Generates and exports campaign performance report.
        """
        try:
            try:
                from ..services import ReportExportService
            except ImportError:
                ReportExportService = None
            
            export_service = ReportExportService()
            
            format_type = request.data.get('format', 'csv')
            days = int(request.data.get('days', 30))
            filters = request.data.get('filters', {})
            
            # Generate report data
            report_data = self._generate_export_report_data(days, filters)
            
            # Export based on format
            if format_type == 'csv':
                response = export_service.export_report_to_csv(request.user.advertiser, report_data)
            elif format_type == 'pdf':
                response = export_service.export_report_to_pdf(request.user.advertiser, report_data)
            elif format_type == 'excel':
                response = export_service.export_report_to_excel(request.user.advertiser, report_data)
            else:
                return Response(
                    {'detail': 'Invalid format type'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Error exporting report: {e}")
            return Response(
                {'detail': 'Failed to export report'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_export_report_data(self, days, filters):
        """Generate report data for export."""
        start_date = timezone.now() - timezone.timedelta(days=days-1)
        end_date = timezone.now().date()
        
        # Get campaign reports
        campaign_reports = CampaignReport.objects.filter(
            campaign__advertiser=self.request.user.advertiser,
            date__gte=start_date,
            date__lte=end_date
        ).select_related('campaign')
        
        # Aggregate data
        report_data = {
            'report_type': 'campaign_performance',
            'period': {
                'start_date': start_date.date().isoformat(),
                'end_date': end_date.isoformat(),
                'days': days,
            },
            'data': []
        }
        
        # Add daily data
        daily_data = campaign_reports.values('date').annotate(
            impressions=Sum('impressions'),
            clicks=Sum('clicks'),
            conversions=Sum('conversions'),
            spend=Sum('spend_amount')
        ).order_by('date')
        
        for day in daily_data:
            report_data['data'].append({
                'date': day['date'].isoformat(),
                'impressions': day['impressions'] or 0,
                'clicks': day['clicks'] or 0,
                'conversions': day['conversions'] or 0,
                'spend': float(day['spend'] or 0),
            })
        
        return report_data
    
    def list(self, request, *args, **kwargs):
        """
        Override list to add filtering capabilities.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply additional filters
        campaign_id = request.query_params.get('campaign_id')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        report_type = request.query_params.get('report_type')
        
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
