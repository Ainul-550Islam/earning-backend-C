import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
import pandas as pd
import numpy as np
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, Q
from django.db.models.functions import TruncDate, TruncHour, TruncMonth

from ..models import AnalyticsEvent, UserAnalytics, RevenueAnalytics, OfferPerformanceAnalytics
from ..collectors import UserAnalyticsCollector, RevenueCollector, OfferPerformanceCollector

logger = logging.getLogger(__name__)

class ChartDataBuilder:
    """
    Build chart data for dashboards and reports
    """
    
    # Color palettes
    COLOR_PALETTES = {
        'primary': ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'],
        'pastel': ['#93C5FD', '#6EE7B7', '#FCD34D', '#FCA5A5', '#C4B5FD'],
        'dark': ['#1E40AF', '#047857', '#B45309', '#B91C1C', '#5B21B6']
    }
    
    def __init__(self, color_palette: str = 'primary'):
        self.colors = self.COLOR_PALETTES.get(color_palette, self.COLOR_PALETTES['primary'])
        self.user_collector = UserAnalyticsCollector()
        self.revenue_collector = RevenueCollector()
        self.offer_collector = OfferPerformanceCollector()
    
    def build_time_series_data(
        self,
        metric: str,
        time_range: str = '7d',
        filters: Dict = None
    ) -> Dict:
        """
        Build time series data for charts
        
        Args:
            metric: Metric to track
            time_range: Time range (7d, 30d, 90d, 1y)
            filters: Additional filters
        
        Returns:
            Time series chart data
        """
        filters = filters or {}
        
        # Parse time range
        end_date = timezone.now()
        if time_range == '7d':
            start_date = end_date - timedelta(days=7)
            interval = 'day'
        elif time_range == '30d':
            start_date = end_date - timedelta(days=30)
            interval = 'day'
        elif time_range == '90d':
            start_date = end_date - timedelta(days=90)
            interval = 'week'
        elif time_range == '1y':
            start_date = end_date - timedelta(days=365)
            interval = 'month'
        else:
            start_date = end_date - timedelta(days=7)
            interval = 'day'
        
        # Get data based on metric
        if metric == 'revenue':
            data = self._build_revenue_time_series(start_date, end_date, interval)
        elif metric == 'users':
            data = self._build_users_time_series(start_date, end_date, interval)
        elif metric == 'tasks':
            data = self._build_tasks_time_series(start_date, end_date, interval)
        elif metric == 'offers':
            data = self._build_offers_time_series(start_date, end_date, interval)
        elif metric == 'withdrawals':
            data = self._build_withdrawals_time_series(start_date, end_date, interval)
        else:
            data = self._build_custom_time_series(metric, start_date, end_date, interval, filters)
        
        # Format for Chart.js
        chart_data = {
            'labels': [d['period'].strftime('%Y-%m-%d') for d in data],
            'datasets': [{
                'label': metric.replace('_', ' ').title(),
                'data': [float(d['value']) for d in data],
                'borderColor': self.colors[0],
                'backgroundColor': f"{self.colors[0]}20",
                'borderWidth': 2,
                'fill': True,
                'tension': 0.4
            }]
        }
        
        return chart_data
    
    def build_bar_chart_data(
        self,
        metric: str,
        time_range: str = '30d',
        group_by: str = 'day_of_week'
    ) -> Dict:
        """
        Build bar chart data
        
        Args:
            metric: Metric to track
            time_range: Time range
            group_by: Grouping field
        
        Returns:
            Bar chart data
        """
        # Parse time range
        end_date = timezone.now()
        if time_range == '7d':
            start_date = end_date - timedelta(days=7)
        elif time_range == '30d':
            start_date = end_date - timedelta(days=30)
        elif time_range == '90d':
            start_date = end_date - timedelta(days=90)
        else:
            start_date = end_date - timedelta(days=30)
        
        # Get data based on metric and group_by
        if metric == 'revenue_by_source':
            data = self._build_revenue_by_source(start_date, end_date)
        elif metric == 'user_engagement':
            data = self._build_user_engagement_by_segment(start_date, end_date)
        elif metric == 'offer_performance':
            data = self._build_offer_performance_by_category(start_date, end_date)
        elif group_by == 'day_of_week':
            data = self._build_metric_by_weekday(metric, start_date, end_date)
        elif group_by == 'hour_of_day':
            data = self._build_metric_by_hour(metric, start_date, end_date)
        else:
            data = self._build_generic_bar_data(metric, start_date, end_date, group_by)
        
        # Format for Chart.js
        if isinstance(data, list):
            labels = [d['label'] for d in data]
            values = [float(d['value']) for d in data]
        elif isinstance(data, dict):
            labels = list(data.keys())
            values = [float(v) for v in data.values()]
        else:
            labels = []
            values = []
        
        chart_data = {
            'labels': labels,
            'datasets': [{
                'label': metric.replace('_', ' ').title(),
                'data': values,
                'backgroundColor': self.colors[:len(values)],
                'borderColor': self.colors[:len(values)],
                'borderWidth': 1
            }]
        }
        
        return chart_data
    
    def build_pie_chart_data(
        self,
        metric: str,
        time_range: str = '30d',
        limit: int = 5
    ) -> Dict:
        """
        Build pie/doughnut chart data
        
        Args:
            metric: Metric to analyze
            time_range: Time range
            limit: Number of segments to show
        
        Returns:
            Pie chart data
        """
        # Parse time range
        end_date = timezone.now()
        if time_range == '7d':
            start_date = end_date - timedelta(days=7)
        elif time_range == '30d':
            start_date = end_date - timedelta(days=30)
        elif time_range == '90d':
            start_date = end_date - timedelta(days=90)
        else:
            start_date = end_date - timedelta(days=30)
        
        # Get data based on metric
        if metric == 'revenue_sources':
            data = self._build_revenue_sources_pie(start_date, end_date, limit)
        elif metric == 'user_devices':
            data = self._build_user_devices_pie(start_date, end_date)
        elif metric == 'offer_categories':
            data = self._build_offer_categories_pie(start_date, end_date, limit)
        elif metric == 'user_countries':
            data = self._build_user_countries_pie(start_date, end_date, limit)
        else:
            data = self._build_generic_pie_data(metric, start_date, end_date, limit)
        
        # Format for Chart.js
        labels = [d['label'] for d in data]
        values = [float(d['value']) for d in data]
        
        chart_data = {
            'labels': labels,
            'datasets': [{
                'data': values,
                'backgroundColor': self.colors[:len(values)],
                'borderColor': '#ffffff',
                'borderWidth': 2,
                'hoverOffset': 4
            }]
        }
        
        return chart_data
    
    def build_funnel_chart_data(
        self,
        funnel_type: str = 'offer_conversion',
        time_range: str = '30d'
    ) -> Dict:
        """
        Build funnel chart data
        
        Args:
            funnel_type: Type of funnel
            time_range: Time range
        
        Returns:
            Funnel chart data
        """
        # Parse time range
        end_date = timezone.now()
        if time_range == '7d':
            start_date = end_date - timedelta(days=7)
        elif time_range == '30d':
            start_date = end_date - timedelta(days=30)
        else:
            start_date = end_date - timedelta(days=30)
        
        # Get funnel data
        if funnel_type == 'offer_conversion':
            data = self._build_offer_funnel(start_date, end_date)
        elif funnel_type == 'user_signup':
            data = self._build_signup_funnel(start_date, end_date)
        elif funnel_type == 'withdrawal_process':
            data = self._build_withdrawal_funnel(start_date, end_date)
        else:
            data = self._build_generic_funnel(funnel_type, start_date, end_date)
        
        # Format for funnel chart
        stages = data.get('stages', {})
        
        chart_data = {
            'labels': list(stages.keys()),
            'datasets': [{
                'label': 'Conversion Funnel',
                'data': list(stages.values()),
                'backgroundColor': self.colors[:len(stages)],
                'borderColor': self.colors[:len(stages)],
                'borderWidth': 1
            }]
        }
        
        return chart_data
    
    def build_comparison_chart_data(
        self,
        comparison_type: str,
        items: List,
        time_range: str = '30d'
    ) -> Dict:
        """
        Build comparison chart data
        
        Args:
            comparison_type: Type of comparison
            items: Items to compare
            time_range: Time range
        
        Returns:
            Comparison chart data
        """
        # Parse time range
        end_date = timezone.now()
        if time_range == '7d':
            start_date = end_date - timedelta(days=7)
        elif time_range == '30d':
            start_date = end_date - timedelta(days=30)
        else:
            start_date = end_date - timedelta(days=30)
        
        # Get comparison data
        if comparison_type == 'offers':
            data = self._compare_offers(items, start_date, end_date)
        elif comparison_type == 'users':
            data = self._compare_users(items, start_date, end_date)
        elif comparison_type == 'periods':
            data = self._compare_periods(items, start_date, end_date)
        else:
            data = self._build_generic_comparison(comparison_type, items, start_date, end_date)
        
        # Format for comparison chart
        chart_data = {
            'labels': data.get('labels', []),
            'datasets': data.get('datasets', [])
        }
        
        return chart_data
    
    # Data building methods
    def _build_revenue_time_series(
        self,
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> List[Dict]:
        """Build revenue time series data"""
        # Get daily revenue
        revenue_data = self.revenue_collector.calculate_revenue_trends(
            days=(end_date - start_date).days
        )
        
        daily_data = revenue_data.get('daily_data', [])
        
        # Aggregate by interval
        df = pd.DataFrame(daily_data)
        if df.empty:
            return []
        
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        if interval == 'week':
            df_resampled = df.resample('W').sum()
        elif interval == 'month':
            df_resampled = df.resample('M').sum()
        else:
            df_resampled = df.resample('D').sum()
        
        # Convert to list
        time_series = []
        for date, row in df_resampled.iterrows():
            time_series.append({
                'period': date.to_pydatetime(),
                'value': float(row['revenue'])
            })
        
        return time_series
    
    def _build_users_time_series(
        self,
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> List[Dict]:
        """Build users time series data"""
        # Get user analytics
        user_data = AnalyticsEvent.objects.filter(
            event_type='user_login',
            event_time__gte=start_date,
            event_time__lte=end_date
        ).annotate(
            period=TruncDate('event_time')
        ).values('period').annotate(
            value=Count('user_id', distinct=True)
        ).order_by('period')
        
        # Convert to DataFrame for resampling
        data_list = list(user_data)
        if not data_list:
            return []
        
        df = pd.DataFrame(data_list)
        df['period'] = pd.to_datetime(df['period'])
        df.set_index('period', inplace=True)
        
        # Resample based on interval
        if interval == 'week':
            df_resampled = df.resample('W').sum()
        elif interval == 'month':
            df_resampled = df.resample('M').sum()
        else:
            df_resampled = df.resample('D').sum()
        
        # Fill missing values
        df_resampled = df_resampled.reindex(
            pd.date_range(start=start_date, end=end_date, freq=interval[0].upper()),
            fill_value=0
        )
        
        # Convert to list
        time_series = []
        for date, row in df_resampled.iterrows():
            time_series.append({
                'period': date.to_pydatetime(),
                'value': float(row['value'])
            })
        
        return time_series
    
    def _build_tasks_time_series(
        self,
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> List[Dict]:
        """Build tasks time series data"""
        tasks_data = AnalyticsEvent.objects.filter(
            event_type='task_completed',
            event_time__gte=start_date,
            event_time__lte=end_date
        ).annotate(
            period=TruncDate('event_time')
        ).values('period').annotate(
            value=Count('id')
        ).order_by('period')
        
        return list(tasks_data)
    
    def _build_offers_time_series(
        self,
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> List[Dict]:
        """Build offers time series data"""
        offers_data = AnalyticsEvent.objects.filter(
            event_type='offer_completed',
            event_time__gte=start_date,
            event_time__lte=end_date
        ).annotate(
            period=TruncDate('event_time')
        ).values('period').annotate(
            value=Count('id')
        ).order_by('period')
        
        return list(offers_data)
    
    def _build_withdrawals_time_series(
        self,
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> List[Dict]:
        """Build withdrawals time series data"""
        withdrawals_data = AnalyticsEvent.objects.filter(
            event_type='withdrawal_processed',
            event_time__gte=start_date,
            event_time__lte=end_date
        ).annotate(
            period=TruncDate('event_time')
        ).values('period').annotate(
            value=Count('id')
        ).order_by('period')
        
        return list(withdrawals_data)
    
    def _build_custom_time_series(
        self,
        metric: str,
        start_date: datetime,
        end_date: datetime,
        interval: str,
        filters: Dict
    ) -> List[Dict]:
        """Build custom time series data"""
        # Map metric to event type
        event_type_map = {
            'page_views': 'page_view',
            'button_clicks': 'button_click',
            'api_calls': 'api_call',
            'errors': 'error_occurred',
            'notifications': 'notification_sent'
        }
        
        event_type = event_type_map.get(metric, metric)
        
        # Get data
        queryset = AnalyticsEvent.objects.filter(
            event_time__gte=start_date,
            event_time__lte=end_date
        )
        
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        if filters:
            queryset = queryset.filter(**filters)
        
        data = queryset.annotate(
            period=TruncDate('event_time')
        ).values('period').annotate(
            value=Count('id')
        ).order_by('period')
        
        return list(data)
    
    def _build_revenue_by_source(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Build revenue by source data"""
        revenue_breakdown = self.revenue_collector.get_revenue_by_source_breakdown(
            start_date, end_date
        )
        
        by_source = revenue_breakdown.get('by_source', {})
        
        data = []
        for source, amount in by_source.items():
            data.append({
                'label': source.replace('_', ' ').title(),
                'value': float(amount)
            })
        
        return data
    
    def _build_user_engagement_by_segment(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Build user engagement by segment"""
        from ..models import UserAnalytics
        
        engagement_data = UserAnalytics.objects.filter(
            period_start__gte=start_date,
            period_end__lte=end_date
        ).values('user__segment').annotate(
            avg_engagement=Avg('engagement_score'),
            user_count=Count('user_id', distinct=True)
        ).order_by('-avg_engagement')
        
        data = []
        for item in engagement_data:
            segment = item['user__segment'] or 'Unknown'
            data.append({
                'label': segment,
                'value': float(item['avg_engagement'] or 0)
            })
        
        return data
    
    def _build_offer_performance_by_category(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Build offer performance by category"""
        from ..models import OfferPerformanceAnalytics
        
        performance_data = OfferPerformanceAnalytics.objects.filter(
            period_start__gte=start_date,
            period_end__lte=end_date
        ).values('offer__category').annotate(
            avg_conversion=Avg('conversion_rate'),
            total_revenue=Sum('revenue_generated'),
            offer_count=Count('offer_id', distinct=True)
        ).order_by('-total_revenue')
        
        data = []
        for item in performance_data:
            category = item['offer__category'] or 'Unknown'
            data.append({
                'label': category,
                'value': float(item['total_revenue'] or 0)
            })
        
        return data
    
    def _build_metric_by_weekday(
        self,
        metric: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Build metric by weekday"""
        # Map metric to event type
        event_type_map = {
            'revenue': None,  # Special handling
            'users': 'user_login',
            'tasks': 'task_completed',
            'offers': 'offer_completed'
        }
        
        event_type = event_type_map.get(metric)
        
        if metric == 'revenue':
            # Get revenue by weekday
            queryset = AnalyticsEvent.objects.filter(
                event_time__gte=start_date,
                event_time__lte=end_date,
                value__gt=0
            )
        elif event_type:
            queryset = AnalyticsEvent.objects.filter(
                event_type=event_type,
                event_time__gte=start_date,
                event_time__lte=end_date
            )
        else:
            return []
        
        # Get data by weekday
        data = queryset.annotate(
            weekday=F('event_time__week_day')
        ).values('weekday').annotate(
            value=Count('id') if metric != 'revenue' else Sum('value')
        ).order_by('weekday')
        
        # Map weekday numbers to names
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        result = []
        for item in data:
            weekday_num = item['weekday'] - 1  # Convert to 0-indexed
            if 0 <= weekday_num < 7:
                result.append({
                    'label': weekday_names[weekday_num],
                    'value': float(item['value'] or 0)
                })
        
        # Ensure all weekdays are present
        for i, day in enumerate(weekday_names):
            if not any(d['label'] == day for d in result):
                result.append({'label': day, 'value': 0})
        
        # Sort by weekday order
        result.sort(key=lambda x: weekday_names.index(x['label']))
        
        return result
    
    def _build_metric_by_hour(
        self,
        metric: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Build metric by hour of day"""
        # Map metric to event type
        event_type_map = {
            'users': 'user_login',
            'tasks': 'task_completed',
            'offers': 'offer_completed'
        }
        
        event_type = event_type_map.get(metric)
        if not event_type:
            return []
        
        # Get data by hour
        data = AnalyticsEvent.objects.filter(
            event_type=event_type,
            event_time__gte=start_date,
            event_time__lte=end_date
        ).annotate(
            hour=TruncHour('event_time')
        ).values('hour').annotate(
            value=Count('id')
        ).order_by('hour')
        
        # Format results
        result = []
        for item in data:
            hour = item['hour'].hour
            result.append({
                'label': f"{hour:02d}:00",
                'value': float(item['value'] or 0)
            })
        
        return result
    
    def _build_generic_bar_data(
        self,
        metric: str,
        start_date: datetime,
        end_date: datetime,
        group_by: str
    ) -> List[Dict]:
        """Build generic bar chart data"""
        # This is a placeholder for custom implementations
        return []
    
    def _build_revenue_sources_pie(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int
    ) -> List[Dict]:
        """Build revenue sources pie chart data"""
        revenue_breakdown = self.revenue_collector.get_revenue_by_source_breakdown(
            start_date, end_date
        )
        
        by_source = revenue_breakdown.get('by_source', {})
        
        # Sort and limit
        sorted_sources = sorted(by_source.items(), key=lambda x: x[1], reverse=True)[:limit]
        
        data = []
        for source, amount in sorted_sources:
            data.append({
                'label': source.replace('_', ' ').title(),
                'value': float(amount)
            })
        
        return data
    
    def _build_user_devices_pie(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Build user devices pie chart data"""
        device_data = AnalyticsEvent.objects.filter(
            event_type='user_login',
            event_time__gte=start_date,
            event_time__lte=end_date,
            device_type__isnull=False
        ).values('device_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        data = []
        for item in device_data:
            device = item['device_type'] or 'Unknown'
            data.append({
                'label': device.title(),
                'value': float(item['count'])
            })
        
        return data
    
    def _build_offer_categories_pie(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int
    ) -> List[Dict]:
        """Build offer categories pie chart data"""
        category_data = AnalyticsEvent.objects.filter(
            event_type='offer_completed',
            event_time__gte=start_date,
            event_time__lte=end_date
        ).values('metadata__offer_category').annotate(
            count=Count('id'),
            revenue=Sum('value')
        ).order_by('-revenue')[:limit]
        
        data = []
        for item in category_data:
            category = item['metadata__offer_category'] or 'Unknown'
            data.append({
                'label': category,
                'value': float(item['revenue'] or 0)
            })
        
        return data
    
    def _build_user_countries_pie(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int
    ) -> List[Dict]:
        """Build user countries pie chart data"""
        country_data = AnalyticsEvent.objects.filter(
            event_type='user_login',
            event_time__gte=start_date,
            event_time__lte=end_date,
            country__isnull=False
        ).values('country').annotate(
            count=Count('id', distinct=True)
        ).order_by('-count')[:limit]
        
        data = []
        for item in country_data:
            country = item['country'] or 'Unknown'
            data.append({
                'label': country,
                'value': float(item['count'])
            })
        
        return data
    
    def _build_generic_pie_data(
        self,
        metric: str,
        start_date: datetime,
        end_date: datetime,
        limit: int
    ) -> List[Dict]:
        """Build generic pie chart data"""
        # This is a placeholder for custom implementations
        return []
    
    def _build_offer_funnel(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Build offer conversion funnel"""
        # Get offer performance for top offers
        top_offers = self.offer_collector.collect_top_performing_offers(
            metric='revenue',
            limit=5,
            start_date=start_date,
            end_date=end_date
        )
        
        if not top_offers:
            return {'stages': {}}
        
        # Aggregate funnel data
        total_impressions = sum(o['views'] for o in top_offers)
        total_clicks = sum(o.get('clicks', 0) for o in top_offers)
        total_completions = sum(o['completions'] for o in top_offers)
        
        stages = {
            'Impressions': total_impressions,
            'Clicks': total_clicks,
            'Completions': total_completions
        }
        
        return {'stages': stages}
    
    def _build_signup_funnel(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Build user signup funnel"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get signup events
        signup_events = AnalyticsEvent.objects.filter(
            event_type='user_signup',
            event_time__gte=start_date,
            event_time__lte=end_date
        ).count()
        
        # Get completion of first task
        first_task_events = AnalyticsEvent.objects.filter(
            event_type='task_completed',
            event_time__gte=start_date,
            event_time__lte=end_date
        ).values('user_id').annotate(
            first_task=Min('event_time')
        ).count()
        
        # Get active users (logged in within 7 days)
        active_cutoff = timezone.now() - timedelta(days=7)
        active_users = AnalyticsEvent.objects.filter(
            event_type='user_login',
            event_time__gte=active_cutoff
        ).values('user_id').distinct().count()
        
        stages = {
            'Signups': signup_events,
            'First Task': first_task_events,
            'Active Users': active_users
        }
        
        return {'stages': stages}
    
    def _build_withdrawal_funnel(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Build withdrawal process funnel"""
        # Get withdrawal requests
        requests = AnalyticsEvent.objects.filter(
            event_type='withdrawal_requested',
            event_time__gte=start_date,
            event_time__lte=end_date
        ).count()
        
        # Get processed withdrawals
        processed = AnalyticsEvent.objects.filter(
            event_type='withdrawal_processed',
            event_time__gte=start_date,
            event_time__lte=end_date
        ).count()
        
        # Get successful withdrawals
        successful = AnalyticsEvent.objects.filter(
            event_type='withdrawal_processed',
            event_time__gte=start_date,
            event_time__lte=end_date,
            metadata__status='completed'
        ).count()
        
        stages = {
            'Requests': requests,
            'Processed': processed,
            'Successful': successful
        }
        
        return {'stages': stages}
    
    def _build_generic_funnel(
        self,
        funnel_type: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Build generic funnel chart data"""
        return {'stages': {}}
    
    def _compare_offers(
        self,
        offer_ids: List[int],
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Compare multiple offers"""
        comparison = self.offer_collector.collect_offer_comparison(
            offer_ids=offer_ids,
            start_date=start_date,
            end_date=end_date
        )
        
        offers = comparison.get('offers', [])
        
        # Prepare dataset for each metric
        datasets = []
        metrics = ['revenue', 'completions', 'conversion_rate']
        
        for i, metric in enumerate(metrics):
            dataset = {
                'label': metric.replace('_', ' ').title(),
                'data': [],
                'backgroundColor': self.colors[i % len(self.colors)],
                'borderColor': self.colors[i % len(self.colors)],
                'borderWidth': 1
            }
            
            for offer in offers:
                if metric == 'revenue':
                    dataset['data'].append(float(offer['revenue']))
                elif metric == 'completions':
                    dataset['data'].append(float(offer['completions']))
                elif metric == 'conversion_rate':
                    dataset['data'].append(float(offer['conversion_rate']))
            
            datasets.append(dataset)
        
        labels = [f"Offer {o['offer_id']}" for o in offers]
        
        return {
            'labels': labels,
            'datasets': datasets
        }
    
    def _compare_users(
        self,
        user_segments: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Compare user segments"""
        # Get user analytics for each segment
        datasets = []
        metrics = ['earnings_total', 'tasks_completed', 'engagement_score']
        
        for i, metric in enumerate(metrics):
            dataset = {
                'label': metric.replace('_', ' ').title(),
                'data': [],
                'backgroundColor': self.colors[i % len(self.colors)],
                'borderColor': self.colors[i % len(self.colors)]
            }
            
            for segment in user_segments:
                # Get average metric for segment
                avg_value = UserAnalytics.objects.filter(
                    period_start__gte=start_date,
                    period_end__lte=end_date,
                    user__segment=segment
                ).aggregate(
                    avg=Avg(metric)
                )['avg'] or 0
                
                dataset['data'].append(float(avg_value))
            
            datasets.append(dataset)
        
        return {
            'labels': [s.replace('_', ' ').title() for s in user_segments],
            'datasets': datasets
        }
    
    def _compare_periods(
        self,
        periods: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Compare different time periods"""
        # This is a simplified example
        datasets = [{
            'label': 'Revenue',
            'data': [1000, 1500, 2000, 2500][:len(periods)],
            'backgroundColor': self.colors[0],
            'borderColor': self.colors[0]
        }]
        
        return {
            'labels': periods,
            'datasets': datasets
        }
    
    def _build_generic_comparison(
        self,
        comparison_type: str,
        items: List,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Build generic comparison chart data"""
        return {'labels': [], 'datasets': []}