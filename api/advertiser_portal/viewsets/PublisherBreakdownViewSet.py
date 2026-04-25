"""
Publisher Breakdown ViewSet

ViewSet for publisher-level statistics and analytics,
including performance breakdown by publisher.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from django.db.models import Case, When

from ..models.reporting import PublisherBreakdown
try:
    from ..services import RealtimeDashboardService
except ImportError:
    RealtimeDashboardService = None
from ..serializers import PublisherBreakdownSerializer
from ..permissions import IsAdvertiserOrReadOnly, IsOwnerOrReadOnly
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class PublisherBreakdownViewSet(viewsets.ModelViewSet):
    """
    ViewSet for publisher-level statistics and analytics.
    
    Handles performance breakdown by publisher,
    including metrics, trends, and comparisons.
    """
    
    queryset = PublisherBreakdown.objects.all()
    serializer_class = PublisherBreakdownSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdvertiserOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        if user.is_staff:
            # Admin can see all publisher breakdowns
            return PublisherBreakdown.objects.all()
        else:
            # Advertisers can only see their own publisher breakdowns
            return PublisherBreakdown.objects.filter(advertiser__user=user)
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """
        Get publisher performance overview.
        
        Returns comprehensive publisher breakdown with metrics.
        """
        try:
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get publisher breakdown for the period
            publisher_breakdowns = PublisherBreakdown.objects.filter(
                advertiser=request.user.advertiser,
                date__gte=start_date,
                date__lte=end_date
            ).select_related('publisher')
            
            # Aggregate performance data
            performance_data = publisher_breakdowns.aggregate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_spend=Sum('spend_amount'),
                avg_ctr=Avg('ctr'),
                avg_conversion_rate=Avg('conversion_rate'),
                avg_cpa=Avg('cpa'),
                avg_cpc=Avg('cpc'),
                publisher_count=Count('publisher', distinct=True),
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
            
            # Get publisher breakdown
            publisher_data = publisher_breakdowns.values(
                'publisher__id', 'publisher__name', 'publisher__domain'
            ).annotate(
                impressions=Sum('impressions'),
                clicks=Sum('clicks'),
                conversions=Sum('conversions'),
                spend=Sum('spend_amount'),
                avg_ctr=Avg('ctr'),
                avg_conversion_rate=Avg('conversion_rate'),
                avg_cpa=Avg('cpa'),
                avg_cpc=Avg('cpc'),
            ).order_by('-spend')
            
            # Get daily breakdown
            daily_breakdown = {}
            current_date = start_date.date()
            while current_date <= end_date:
                day_breakdowns = publisher_breakdowns.filter(date=current_date)
                day_data = day_breakdowns.aggregate(
                    impressions=Sum('impressions'),
                    clicks=Sum('clicks'),
                    conversions=Sum('conversions'),
                    spend=Sum('spend_amount'),
                    publisher_count=Count('publisher', distinct=True)
                )
                
                daily_breakdown[current_date.isoformat()] = {
                    'impressions': day_data['impressions'] or 0,
                    'clicks': day_data['clicks'] or 0,
                    'conversions': day_data['conversions'] or 0,
                    'spend': float(day_data['spend'] or 0),
                    'publisher_count': day_data['publisher_count'] or 0,
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
                    'publisher_count': performance_data['publisher_count'],
                    'ctr': float(calculated_ctr),
                    'cpc': float(calculated_cpc),
                    'cpa': float(calculated_cpa),
                    'conversion_rate': float((total_conversions / total_clicks * 100) if total_clicks > 0 else 0),
                },
                'publisher_breakdown': [
                    {
                        'publisher_id': item['publisher__id'],
                        'publisher_name': item['publisher__name'],
                        'publisher_domain': item['publisher__domain'],
                        'impressions': item['impressions'] or 0,
                        'clicks': item['clicks'] or 0,
                        'conversions': item['conversions'] or 0,
                        'spend': float(item['spend'] or 0),
                        'ctr': float(item['avg_ctr'] or 0),
                        'conversion_rate': float(item['avg_conversion_rate'] or 0),
                        'cpa': float(item['avg_cpa'] or 0),
                        'cpc': float(item['avg_cpc'] or 0),
                    }
                    for item in publisher_data
                ],
                'daily_breakdown': daily_breakdown,
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting publisher overview: {e}")
            return Response(
                {'detail': 'Failed to get publisher overview'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def top_publishers(self, request):
        """
        Get top performing publishers.
        
        Returns publishers ranked by performance metrics.
        """
        try:
            metric = request.query_params.get('metric', 'spend')
            limit = int(request.query_params.get('limit', 10))
            days = int(request.query_params.get('days', 30))
            
            start_date = timezone.now() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get publisher breakdown for the period
            publisher_breakdowns = PublisherBreakdown.objects.filter(
                advertiser=request.user.advertiser,
                date__gte=start_date,
                date__lte=end_date
            ).select_related('publisher')
            
            # Aggregate by publisher
            publisher_data = publisher_breakdowns.values(
                'publisher__id', 'publisher__name', 'publisher__domain'
            ).annotate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_spend=Sum('spend_amount'),
                avg_ctr=Avg('ctr'),
                avg_conversion_rate=Avg('conversion_rate'),
                avg_cpa=Avg('cpa'),
                avg_cpc=Avg('cpc'),
            )
            
            # Sort by requested metric
            if metric == 'spend':
                publisher_data = publisher_data.order_by('-total_spend')
            elif metric == 'impressions':
                publisher_data = publisher_data.order_by('-total_impressions')
            elif metric == 'clicks':
                publisher_data = publisher_data.order_by('-total_clicks')
            elif metric == 'conversions':
                publisher_data = publisher_data.order_by('-total_conversions')
            elif metric == 'ctr':
                publisher_data = publisher_data.order_by('-avg_ctr')
            elif metric == 'conversion_rate':
                publisher_data = publisher_data.order_by('-avg_conversion_rate')
            elif metric == 'cpa':
                publisher_data = publisher_data.order_by('avg_cpa')  # Lower CPA is better
            elif metric == 'cpc':
                publisher_data = publisher_data.order_by('avg_cpc')  # Lower CPC is better
            else:
                publisher_data = publisher_data.order_by('-total_spend')
            
            top_publishers = publisher_data[:limit]
            
            return Response({
                'metric': metric,
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days,
                },
                'top_publishers': [
                    {
                        'publisher_id': item['publisher__id'],
                        'publisher_name': item['publisher__name'],
                        'publisher_domain': item['publisher__domain'],
                        'total_impressions': item['total_impressions'] or 0,
                        'total_clicks': item['total_clicks'] or 0,
                        'total_conversions': item['total_conversions'] or 0,
                        'total_spend': float(item['total_spend'] or 0),
                        'avg_ctr': float(item['avg_ctr'] or 0),
                        'avg_conversion_rate': float(item['avg_conversion_rate'] or 0),
                        'avg_cpa': float(item['avg_cpa'] or 0),
                        'avg_cpc': float(item['avg_cpc'] or 0),
                    }
                    for item in top_publishers
                ],
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting top publishers: {e}")
            return Response(
                {'detail': 'Failed to get top publishers'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def publisher_trends(self, request):
        """
        Get publisher performance trends.
        
        Returns trend analysis for publisher performance.
        """
        try:
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get daily publisher breakdowns
            daily_breakdowns = PublisherBreakdown.objects.filter(
                advertiser=request.user.advertiser,
                date__gte=start_date,
                date__lte=end_date
            ).values('date').annotate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_spend=Sum('spend_amount'),
                publisher_count=Count('publisher', distinct=True)
            ).order_by('date')
            
            # Calculate trends
            if len(daily_breakdowns) >= 2:
                mid_point = len(daily_breakdowns) // 2
                recent_avg = daily_breakdowns[mid_point:].aggregate(
                    avg_spend=Avg('total_spend'),
                    avg_conversions=Avg('total_conversions'),
                    avg_clicks=Avg('total_clicks'),
                    avg_publishers=Avg('publisher_count')
                )
                
                older_avg = daily_breakdowns[:mid_point].aggregate(
                    avg_spend=Avg('total_spend'),
                    avg_conversions=Avg('total_conversions'),
                    avg_clicks=Avg('total_clicks'),
                    avg_publishers=Avg('publisher_count')
                )
                
                spend_trend = 'up' if recent_avg['avg_spend'] > older_avg['avg_spend'] else 'down'
                conversion_trend = 'up' if recent_avg['avg_conversions'] > older_avg['avg_conversions'] else 'down'
                click_trend = 'up' if recent_avg['avg_clicks'] > older_avg['avg_clicks'] else 'down'
                publisher_trend = 'up' if recent_avg['avg_publishers'] > older_avg['avg_publishers'] else 'down'
            else:
                spend_trend = 'stable'
                conversion_trend = 'stable'
                click_trend = 'stable'
                publisher_trend = 'stable'
            
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
                    'publisher_trend': publisher_trend,
                },
                'daily_data': [
                    {
                        'date': item['date'].isoformat(),
                        'impressions': item['total_impressions'] or 0,
                        'clicks': item['total_clicks'] or 0,
                        'conversions': item['total_conversions'] or 0,
                        'spend': float(item['total_spend'] or 0),
                        'publisher_count': item['publisher_count'] or 0,
                    }
                    for item in daily_breakdowns
                ],
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting publisher trends: {e}")
            return Response(
                {'detail': 'Failed to get publisher trends'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def publisher_comparison(self, request):
        """
        Get publisher performance comparison.
        
        Compares performance between different publishers.
        """
        try:
            publisher_ids = request.query_params.getlist('publisher_ids')
            days = int(request.query_params.get('days', 30))
            
            if not publisher_ids:
                return Response(
                    {'detail': 'Publisher IDs are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            start_date = timezone.now() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get publisher breakdown for specified publishers
            publisher_breakdowns = PublisherBreakdown.objects.filter(
                advertiser=request.user.advertiser,
                publisher_id__in=publisher_ids,
                date__gte=start_date,
                date__lte=end_date
            ).select_related('publisher')
            
            # Aggregate by publisher
            publisher_data = publisher_breakdowns.values(
                'publisher__id', 'publisher__name', 'publisher__domain'
            ).annotate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_spend=Sum('spend_amount'),
                avg_ctr=Avg('ctr'),
                avg_conversion_rate=Avg('conversion_rate'),
                avg_cpa=Avg('cpa'),
                avg_cpc=Avg('cpc'),
            )
            
            return Response({
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days,
                },
                'publisher_comparison': [
                    {
                        'publisher_id': item['publisher__id'],
                        'publisher_name': item['publisher__name'],
                        'publisher_domain': item['publisher__domain'],
                        'total_impressions': item['total_impressions'] or 0,
                        'total_clicks': item['total_clicks'] or 0,
                        'total_conversions': item['total_conversions'] or 0,
                        'total_spend': float(item['total_spend'] or 0),
                        'avg_ctr': float(item['avg_ctr'] or 0),
                        'avg_conversion_rate': float(item['avg_conversion_rate'] or 0),
                        'avg_cpa': float(item['avg_cpa'] or 0),
                        'avg_cpc': float(item['avg_cpc'] or 0),
                    }
                    for item in publisher_data
                ],
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting publisher comparison: {e}")
            return Response(
                {'detail': 'Failed to get publisher comparison'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def publisher_distribution(self, request):
        """
        Get publisher distribution analysis.
        
        Returns distribution of performance across publishers.
        """
        try:
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get publisher breakdown for the period
            publisher_breakdowns = PublisherBreakdown.objects.filter(
                advertiser=request.user.advertiser,
                date__gte=start_date,
                date__lte=end_date
            ).select_related('publisher')
            
            # Aggregate by publisher
            publisher_data = publisher_breakdowns.values(
                'publisher__id', 'publisher__name'
            ).annotate(
                total_spend=Sum('spend_amount'),
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions')
            ).order_by('-total_spend')
            
            # Calculate distribution
            total_spend = sum(item['total_spend'] or 0 for item in publisher_data)
            total_impressions = sum(item['total_impressions'] or 0 for item in publisher_data)
            total_clicks = sum(item['total_clicks'] or 0 for item in publisher_data)
            total_conversions = sum(item['total_conversions'] or 0 for item in publisher_data)
            
            # Create distribution data
            distribution_data = []
            cumulative_spend = 0
            cumulative_impressions = 0
            cumulative_clicks = 0
            cumulative_conversions = 0
            
            for i, item in enumerate(publisher_data):
                spend_percentage = (item['total_spend'] / total_spend * 100) if total_spend > 0 else 0
                impressions_percentage = (item['total_impressions'] / total_impressions * 100) if total_impressions > 0 else 0
                clicks_percentage = (item['total_clicks'] / total_clicks * 100) if total_clicks > 0 else 0
                conversions_percentage = (item['total_conversions'] / total_conversions * 100) if total_conversions > 0 else 0
                
                cumulative_spend += item['total_spend'] or 0
                cumulative_impressions += item['total_impressions'] or 0
                cumulative_clicks += item['total_clicks'] or 0
                cumulative_conversions += item['total_conversions'] or 0
                
                cumulative_spend_percentage = (cumulative_spend / total_spend * 100) if total_spend > 0 else 0
                cumulative_impressions_percentage = (cumulative_impressions / total_impressions * 100) if total_impressions > 0 else 0
                cumulative_clicks_percentage = (cumulative_clicks / total_clicks * 100) if total_clicks > 0 else 0
                cumulative_conversions_percentage = (cumulative_conversions / total_conversions * 100) if total_conversions > 0 else 0
                
                distribution_data.append({
                    'rank': i + 1,
                    'publisher_id': item['publisher__id'],
                    'publisher_name': item['publisher__name'],
                    'spend': float(item['total_spend'] or 0),
                    'spend_percentage': float(spend_percentage),
                    'cumulative_spend_percentage': float(cumulative_spend_percentage),
                    'impressions': item['total_impressions'] or 0,
                    'impressions_percentage': float(impressions_percentage),
                    'cumulative_impressions_percentage': float(cumulative_impressions_percentage),
                    'clicks': item['total_clicks'] or 0,
                    'clicks_percentage': float(clicks_percentage),
                    'cumulative_clicks_percentage': float(cumulative_clicks_percentage),
                    'conversions': item['total_conversions'] or 0,
                    'conversions_percentage': float(conversions_percentage),
                    'cumulative_conversions_percentage': float(cumulative_conversions_percentage),
                })
            
            return Response({
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days,
                },
                'total_publishers': len(publisher_data),
                'distribution': distribution_data,
                'summary': {
                    'top_10_percent_spend': sum(item['spend_percentage'] for item in distribution_data[:max(1, len(distribution_data) // 10)]),
                    'top_20_percent_spend': sum(item['spend_percentage'] for item in distribution_data[:max(1, len(distribution_data) // 5)]),
                    'top_50_percent_spend': sum(item['spend_percentage'] for item in distribution_data[:max(1, len(distribution_data) // 2)]),
                },
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting publisher distribution: {e}")
            return Response(
                {'detail': 'Failed to get publisher distribution'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def publisher_alerts(self, request):
        """
        Get publisher performance alerts.
        
        Returns alerts and recommendations for publishers.
        """
        try:
            days = int(request.query_params.get('days', 7))
            start_date = timezone.now() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get recent publisher breakdowns
            recent_breakdowns = PublisherBreakdown.objects.filter(
                advertiser=request.user.advertiser,
                date__gte=start_date,
                date__lte=end_date
            ).select_related('publisher')
            
            # Get previous period for comparison
            previous_start_date = start_date - timezone.timedelta(days=days)
            previous_end_date = start_date - timezone.timedelta(days=1)
            
            previous_breakdowns = PublisherBreakdown.objects.filter(
                advertiser=request.user.advertiser,
                date__gte=previous_start_date,
                date__lte=previous_end_date
            ).select_related('publisher')
            
            alerts = []
            
            # Analyze publisher performance
            recent_data = recent_breakdowns.values('publisher__id', 'publisher__name').annotate(
                recent_spend=Sum('spend_amount'),
                recent_conversions=Sum('conversions'),
                recent_ctr=Avg('ctr'),
            )
            
            previous_data = previous_breakdowns.values('publisher__id').annotate(
                previous_spend=Sum('spend_amount'),
                previous_conversions=Sum('conversions'),
                previous_ctr=Avg('ctr'),
            )
            
            # Create lookup for previous data
            previous_lookup = {item['publisher__id']: item for item in previous_data}
            
            for item in recent_data:
                publisher_id = item['publisher__id']
                publisher_name = item['publisher_name']
                
                previous = previous_lookup.get(publisher_id, {})
                previous_spend = previous.get('previous_spend', 0)
                previous_conversions = previous.get('previous_conversions', 0)
                previous_ctr = previous.get('previous_ctr', 0)
                
                recent_spend = item['recent_spend'] or 0
                recent_conversions = item['recent_conversions'] or 0
                recent_ctr = item['recent_ctr'] or 0
                
                # Check for spend decline
                if previous_spend > 0 and recent_spend > 0:
                    spend_change = ((recent_spend - previous_spend) / previous_spend) * 100
                    if spend_change < -20:  # 20% decline
                        alerts.append({
                            'type': 'spend_decline',
                            'severity': 'warning',
                            'publisher_id': publisher_id,
                            'publisher_name': publisher_name,
                            'message': f'Publisher spend declined by {abs(spend_change):.1f}%',
                            'recommendation': 'Review publisher performance and consider optimization',
                        })
                
                # Check for conversion decline
                if previous_conversions > 0 and recent_conversions > 0:
                    conversion_change = ((recent_conversions - previous_conversions) / previous_conversions) * 100
                    if conversion_change < -15:  # 15% decline
                        alerts.append({
                            'type': 'conversion_decline',
                            'severity': 'warning',
                            'publisher_id': publisher_id,
                            'publisher_name': publisher_name,
                            'message': f'Publisher conversions declined by {abs(conversion_change):.1f}%',
                            'recommendation': 'Investigate conversion tracking and publisher quality',
                        })
                
                # Check for low CTR
                if recent_ctr < 0.5:  # Less than 0.5%
                    alerts.append({
                        'type': 'low_ctr',
                        'severity': 'info',
                        'publisher_id': publisher_id,
                        'publisher_name': publisher_name,
                        'message': f'Low CTR: {recent_ctr:.2f}%',
                        'recommendation': 'Optimize ad creative or targeting for this publisher',
                    })
                
                # Check for high CPA
                if recent_conversions > 0 and recent_spend > 0:
                    cpa = recent_spend / recent_conversions
                    if cpa > 100:  # CPA > $100
                        alerts.append({
                            'type': 'high_cpa',
                            'severity': 'warning',
                            'publisher_id': publisher_id,
                            'publisher_name': publisher_name,
                            'message': f'High CPA: ${cpa:.2f}',
                            'recommendation': 'Review bid strategy and publisher quality',
                        })
            
            return Response({
                'alerts': alerts,
                'count': len(alerts),
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days,
                },
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting publisher alerts: {e}")
            return Response(
                {'detail': 'Failed to get publisher alerts'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def export_publisher_report(self, request):
        """
        Export publisher performance report.
        
        Generates and exports publisher breakdown report.
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
            report_data = self._generate_publisher_export_data(days, filters)
            
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
            logger.error(f"Error exporting publisher report: {e}")
            return Response(
                {'detail': 'Failed to export publisher report'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_publisher_export_data(self, days, filters):
        """Generate publisher report data for export."""
        start_date = timezone.now() - timezone.timedelta(days=days-1)
        end_date = timezone.now().date()
        
        # Get publisher breakdowns
        publisher_breakdowns = PublisherBreakdown.objects.filter(
            advertiser=self.request.user.advertiser,
            date__gte=start_date,
            date__lte=end_date
        ).select_related('publisher')
        
        # Apply filters
        if 'publisher_ids' in filters:
            publisher_breakdowns = publisher_breakdowns.filter(publisher_id__in=filters['publisher_ids'])
        
        # Aggregate data
        report_data = {
            'report_type': 'publisher_breakdown',
            'period': {
                'start_date': start_date.date().isoformat(),
                'end_date': end_date.isoformat(),
                'days': days,
            },
            'data': []
        }
        
        # Add publisher data
        publisher_data = publisher_breakdowns.values(
            'publisher__id', 'publisher__name', 'publisher__domain'
        ).annotate(
            impressions=Sum('impressions'),
            clicks=Sum('clicks'),
            conversions=Sum('conversions'),
            spend=Sum('spend_amount'),
            avg_ctr=Avg('ctr'),
            avg_conversion_rate=Avg('conversion_rate'),
            avg_cpa=Avg('cpa'),
            avg_cpc=Avg('cpc'),
        ).order_by('-spend')
        
        for item in publisher_data:
            report_data['data'].append({
                'publisher_id': item['publisher__id'],
                'publisher_name': item['publisher__name'],
                'publisher_domain': item['publisher__domain'],
                'impressions': item['impressions'] or 0,
                'clicks': item['clicks'] or 0,
                'conversions': item['conversions'] or 0,
                'spend': float(item['spend'] or 0),
                'ctr': float(item['avg_ctr'] or 0),
                'conversion_rate': float(item['avg_conversion_rate'] or 0),
                'cpa': float(item['avg_cpa'] or 0),
                'cpc': float(item['avg_cpc'] or 0),
            })
        
        return report_data
    
    def list(self, request, *args, **kwargs):
        """
        Override list to add filtering capabilities.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply additional filters
        advertiser_id = request.query_params.get('advertiser_id')
        publisher_id = request.query_params.get('publisher_id')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if advertiser_id:
            queryset = queryset.filter(advertiser_id=advertiser_id)
        
        if publisher_id:
            queryset = queryset.filter(publisher_id=publisher_id)
        
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
