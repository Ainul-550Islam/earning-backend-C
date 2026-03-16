import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from decimal import Decimal

from ..models import AnalyticsEvent, UserAnalytics, RevenueAnalytics, RealTimeMetric
from ..collectors import UserAnalyticsCollector, RevenueCollector, OfferPerformanceCollector
from ..processors import DataProcessor, ChartDataBuilder

logger = logging.getLogger(__name__)

class AdminDashboard:
    """
    Admin dashboard with comprehensive analytics
    """
    
    def __init__(self):
        self.user_collector = UserAnalyticsCollector()
        self.revenue_collector = RevenueCollector()
        self.offer_collector = OfferPerformanceCollector()
        self.data_processor = DataProcessor()
        self.chart_builder = ChartDataBuilder()
    
    def get_data(self, time_range: str = '30d') -> Dict:
        """
        Get admin dashboard data
        
        Args:
            time_range: Time range for data
        
        Returns:
            Dashboard data
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
        
        # Collect all data in parallel (conceptually)
        dashboard_data = {
            'summary': self._get_summary_metrics(start_date, end_date),
            'charts': self._get_chart_data(start_date, end_date),
            'tables': self._get_table_data(start_date, end_date),
            'insights': self._get_insights(start_date, end_date),
            'alerts': self._get_alerts(),
            'real_time': self._get_real_time_metrics(),
            'period': {
                'start': start_date,
                'end': end_date,
                'range': time_range
            },
            'last_updated': timezone.now()
        }
        
        return dashboard_data
    
    def _get_summary_metrics(self, start_date: datetime, end_date: datetime) -> Dict:
        """Get summary metrics for dashboard"""
        # User metrics
        total_users = self.user_collector.get_total_users()
        active_users = self.user_collector.get_active_users(days=7)
        new_users_today = self.user_collector.get_new_users_today()
        
        # Revenue metrics
        revenue_today = self.revenue_collector.get_revenue_today()
        revenue_this_month = self.revenue_collector.get_revenue_this_month()
        
        # Activity metrics
        tasks_completed_today = self.user_collector.get_tasks_completed_today()
        offers_completed_today = self.user_collector.get_offers_completed_today()
        withdrawals_processed_today = self.revenue_collector.get_withdrawals_processed_today()
        
        # Conversion metrics
        conversion_rate = self.user_collector.get_conversion_rate()
        avg_engagement_score = self.user_collector.get_average_engagement_score()
        
        # Trends
        revenue_trend = self.revenue_collector.get_revenue_trend(days=30)
        user_growth_trend = self.user_collector.get_user_growth_trend(days=30)
        task_completion_trend = self.user_collector.get_task_completion_trend(days=30)
        
        return {
            'users': {
                'total': total_users,
                'active': active_users,
                'new_today': new_users_today,
                'growth_trend': user_growth_trend
            },
            'revenue': {
                'today': revenue_today,
                'this_month': revenue_this_month,
                'trend': revenue_trend
            },
            'activity': {
                'tasks_today': tasks_completed_today,
                'offers_today': offers_completed_today,
                'withdrawals_today': withdrawals_processed_today,
                'task_trend': task_completion_trend
            },
            'performance': {
                'conversion_rate': conversion_rate,
                'avg_engagement': avg_engagement_score
            }
        }
    
    def _get_chart_data(self, start_date: datetime, end_date: datetime) -> Dict:
        """Get chart data for dashboard"""
        charts = {}
        
        # Revenue trend chart
        charts['revenue_trend'] = self.chart_builder.build_time_series_data(
            metric='revenue',
            time_range='30d'
        )
        
        # User growth chart
        charts['user_growth'] = self.chart_builder.build_time_series_data(
            metric='users',
            time_range='30d'
        )
        
        # Activity comparison chart
        charts['activity_comparison'] = self.chart_builder.build_bar_chart_data(
            metric='revenue_by_source',
            time_range='30d'
        )
        
        # User engagement pie chart
        charts['user_segments'] = self.chart_builder.build_pie_chart_data(
            metric='user_devices',
            time_range='30d'
        )
        
        # Offer performance funnel
        charts['offer_funnel'] = self.chart_builder.build_funnel_chart_data(
            funnel_type='offer_conversion',
            time_range='30d'
        )
        
        # Daily patterns chart
        charts['daily_patterns'] = self.chart_builder.build_bar_chart_data(
            metric='revenue',
            time_range='30d',
            group_by='day_of_week'
        )
        
        return charts
    
    def _get_table_data(self, start_date: datetime, end_date: datetime) -> Dict:
        """Get table data for dashboard"""
        tables = {}
        
        # Top performing offers
        top_offers = self.offer_collector.collect_top_performing_offers(
            metric='revenue',
            limit=10,
            start_date=start_date,
            end_date=end_date
        )
        tables['top_offers'] = top_offers
        
        # Top earning users
        top_users = UserAnalytics.objects.filter(
            period_start__gte=start_date,
            period_end__lte=end_date
        ).values(
            'user__id', 'user__username', 'user__email'
        ).annotate(
            total_earnings=Sum('earnings_total'),
            tasks_completed=Sum('tasks_completed'),
            engagement_score=Avg('engagement_score')
        ).order_by('-total_earnings')[:10]
        tables['top_users'] = list(top_users)
        
        # Recent transactions
        recent_transactions = AnalyticsEvent.objects.filter(
            event_time__gte=start_date,
            event_time__lte=end_date,
            value__isnull=False
        ).exclude(value=0).select_related('user').order_by('-event_time')[:20]
        
        transactions_list = []
        for tx in recent_transactions:
            transactions_list.append({
                'id': tx.id,
                'user': tx.user.username if tx.user else 'Anonymous',
                'type': tx.event_type,
                'amount': tx.value,
                'time': tx.event_time,
                'metadata': tx.metadata
            })
        tables['recent_transactions'] = transactions_list
        
        # System alerts
        from ..models import AlertHistory
        recent_alerts = AlertHistory.objects.filter(
            triggered_at__gte=start_date,
            is_resolved=False
        ).select_related('rule').order_by('-triggered_at')[:10]
        tables['active_alerts'] = list(recent_alerts.values())
        
        return tables
    
    def _get_insights(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get insights and recommendations"""
        insights = []
        
        # Revenue insights
        revenue_trend = self.revenue_collector.get_revenue_trend(days=30)
        if revenue_trend < -10:
            insights.append({
                'type': 'warning',
                'title': 'Revenue Decline',
                'message': f'Revenue has decreased by {abs(revenue_trend):.1f}% compared to last month',
                'icon': '📉',
                'priority': 'high'
            })
        elif revenue_trend > 20:
            insights.append({
                'type': 'success',
                'title': 'Revenue Growth',
                'message': f'Revenue has increased by {revenue_trend:.1f}% compared to last month',
                'icon': '📈',
                'priority': 'medium'
            })
        
        # User engagement insights
        avg_engagement = self.user_collector.get_average_engagement_score()
        if avg_engagement < 30:
            insights.append({
                'type': 'warning',
                'title': 'Low User Engagement',
                'message': f'Average user engagement score is {avg_engagement:.1f}/100',
                'icon': '[WARN]',
                'priority': 'high',
                'action': 'Launch re-engagement campaign'
            })
        
        # Offer performance insights
        top_offers = self.offer_collector.collect_top_performing_offers(limit=5)
        if top_offers:
            best_offer = max(top_offers, key=lambda x: x['revenue'])
            worst_offer = min(top_offers, key=lambda x: x['conversion_rate'])
            
            if worst_offer['conversion_rate'] < 5:
                insights.append({
                    'type': 'info',
                    'title': 'Low Performing Offer',
                    'message': f'Offer "{worst_offer["offer_name"]}" has only {worst_offer["conversion_rate"]:.1f}% conversion rate',
                    'icon': '🎯',
                    'priority': 'medium',
                    'action': 'Consider optimizing or pausing this offer'
                })
        
        # System health insights
        error_rate = AnalyticsEvent.objects.filter(
            event_type='error_occurred',
            event_time__gte=start_date
        ).count()
        
        total_events = AnalyticsEvent.objects.filter(
            event_time__gte=start_date
        ).count()
        
        if total_events > 0:
            error_percentage = (error_rate / total_events) * 100
            if error_percentage > 5:
                insights.append({
                    'type': 'danger',
                    'title': 'High Error Rate',
                    'message': f'Error rate is {error_percentage:.1f}% of total events',
                    'icon': '🚨',
                    'priority': 'critical',
                    'action': 'Investigate system errors immediately'
                })
        
        # Retention insights
        retention_data = self.user_collector.collect_user_retention()
        if retention_data:
            latest_cohort = retention_data[-1]
            day_7_retention = latest_cohort.get('retention_rates', {}).get('day_7', 0)
            
            if day_7_retention < 20:
                insights.append({
                    'type': 'warning',
                    'title': 'Low User Retention',
                    'message': f'Only {day_7_retention:.1f}% of users are retained after 7 days',
                    'icon': '👥',
                    'priority': 'high',
                    'action': 'Improve onboarding and early user experience'
                })
        
        return insights
    
    def _get_alerts(self) -> List[Dict]:
        """Get active alerts"""
        from ..models import AlertHistory
        
        active_alerts = AlertHistory.objects.filter(
            is_resolved=False
        ).select_related('rule').order_by('-triggered_at')[:5]
        
        alerts_list = []
        for alert in active_alerts:
            alerts_list.append({
                'id': alert.id,
                'rule_name': alert.rule.name,
                'severity': alert.severity,
                'triggered_at': alert.triggered_at,
                'metric_value': alert.metric_value,
                'threshold': alert.threshold_value,
                'condition': alert.condition_met
            })
        
        return alerts_list
    
    def _get_real_time_metrics(self) -> Dict:
        """Get real-time metrics"""
        real_time_metrics = {}
        
        # Active users right now (last 5 minutes)
        five_min_ago = timezone.now() - timedelta(minutes=5)
        active_users_now = AnalyticsEvent.objects.filter(
            event_type='user_login',
            event_time__gte=five_min_ago
        ).values('user_id').distinct().count()
        real_time_metrics['active_users_now'] = active_users_now
        
        # Tasks being completed now
        tasks_now = AnalyticsEvent.objects.filter(
            event_type='task_completed',
            event_time__gte=five_min_ago
        ).count()
        real_time_metrics['tasks_now'] = tasks_now
        
        # Revenue in last hour
        hour_ago = timezone.now() - timedelta(hours=1)
        revenue_last_hour = AnalyticsEvent.objects.filter(
            event_time__gte=hour_ago,
            value__gt=0
        ).aggregate(total=Sum('value'))['total'] or Decimal('0')
        real_time_metrics['revenue_last_hour'] = revenue_last_hour
        
        # System metrics from RealTimeMetric model
        system_metrics = RealTimeMetric.objects.filter(
            metric_time__gte=timezone.now() - timedelta(minutes=5)
        ).order_by('-metric_time')
        
        for metric in system_metrics[:5]:
            real_time_metrics[metric.metric_type] = {
                'value': metric.value,
                'unit': metric.unit,
                'time': metric.metric_time
            }
        
        return real_time_metrics
    
    def get_widget_data(self, widget_type: str, **kwargs) -> Dict:
        """
        Get data for specific dashboard widget
        
        Args:
            widget_type: Type of widget
            **kwargs: Widget parameters
        
        Returns:
            Widget data
        """
        if widget_type == 'revenue_summary':
            return self._get_revenue_widget(**kwargs)
        elif widget_type == 'user_activity':
            return self._get_user_activity_widget(**kwargs)
        elif widget_type == 'offer_performance':
            return self._get_offer_performance_widget(**kwargs)
        elif widget_type == 'system_health':
            return self._get_system_health_widget(**kwargs)
        elif widget_type == 'geographical_distribution':
            return self._get_geographical_widget(**kwargs)
        else:
            return {'error': f'Unknown widget type: {widget_type}'}
    
    def _get_revenue_widget(self, **kwargs) -> Dict:
        """Get revenue widget data"""
        time_range = kwargs.get('time_range', '30d')
        
        revenue_trend = self.revenue_collector.calculate_revenue_trends(
            days=self._parse_time_range_days(time_range)
        )
        
        return {
            'type': 'revenue_summary',
            'data': revenue_trend,
            'charts': self.chart_builder.build_time_series_data('revenue', time_range)
        }
    
    def _get_user_activity_widget(self, **kwargs) -> Dict:
        """Get user activity widget data"""
        time_range = kwargs.get('time_range', '30d')
        days = self._parse_time_range_days(time_range)
        
        user_data = self.user_collector.collect_user_analytics(
            period='daily',
            start_date=timezone.now() - timedelta(days=days)
        )
        
        # Process for widget
        processor = DataProcessor()
        stats = processor.calculate_statistics(
            [{'value': d.get('earnings_total', 0)} for d in user_data],
            'value'
        )
        
        return {
            'type': 'user_activity',
            'stats': stats,
            'top_users': self._get_top_users(days),
            'charts': self.chart_builder.build_time_series_data('users', time_range)
        }
    
    def _get_offer_performance_widget(self, **kwargs) -> Dict:
        """Get offer performance widget data"""
        time_range = kwargs.get('time_range', '30d')
        days = self._parse_time_range_days(time_range)
        
        top_offers = self.offer_collector.collect_top_performing_offers(
            metric='revenue',
            limit=10,
            start_date=timezone.now() - timedelta(days=days)
        )
        
        return {
            'type': 'offer_performance',
            'top_offers': top_offers,
            'summary': {
                'total_offers': len(top_offers),
                'total_revenue': sum(o['revenue'] for o in top_offers),
                'avg_conversion_rate': sum(o['conversion_rate'] for o in top_offers) / len(top_offers) if top_offers else 0
            },
            'charts': self.chart_builder.build_pie_chart_data('offer_categories', time_range, limit=5)
        }
    
    def _get_system_health_widget(self, **kwargs) -> Dict:
        """Get system health widget data"""
        # Get error rates
        error_events = AnalyticsEvent.objects.filter(
            event_type='error_occurred',
            event_time__gte=timezone.now() - timedelta(days=1)
        ).count()
        
        total_events = AnalyticsEvent.objects.filter(
            event_time__gte=timezone.now() - timedelta(days=1)
        ).count()
        
        error_rate = (error_events / total_events * 100) if total_events > 0 else 0
        
        # Get response times
        api_events = AnalyticsEvent.objects.filter(
            event_type='api_call',
            event_time__gte=timezone.now() - timedelta(hours=1)
        ).aggregate(
            avg_duration=Avg('duration')
        )
        
        avg_response_time = api_events['avg_duration'] or 0
        
        # Get system metrics
        from ..models import RealTimeMetric
        system_metrics = RealTimeMetric.objects.filter(
            metric_time__gte=timezone.now() - timedelta(minutes=5)
        ).order_by('-metric_time')
        
        return {
            'type': 'system_health',
            'metrics': {
                'error_rate': error_rate,
                'avg_response_time': avg_response_time,
                'uptime': 99.9,  # Would come from monitoring system
                'active_connections': system_metrics.filter(metric_type='active_users').first().value if system_metrics.filter(metric_type='active_users').exists() else 0
            },
            'status': 'healthy' if error_rate < 1 and avg_response_time < 1000 else 'degraded'
        }
    
    def _get_geographical_widget(self, **kwargs) -> Dict:
        """Get geographical distribution widget data"""
        time_range = kwargs.get('time_range', '30d')
        days = self._parse_time_range_days(time_range)
        
        # Get user distribution by country
        country_data = AnalyticsEvent.objects.filter(
            event_type='user_login',
            event_time__gte=timezone.now() - timedelta(days=days),
            country__isnull=False
        ).values('country').annotate(
            user_count=Count('user_id', distinct=True),
            revenue=Sum('value', filter=Q(value__gt=0))
        ).order_by('-user_count')[:10]
        
        return {
            'type': 'geographical_distribution',
            'top_countries': list(country_data),
            'total_countries': country_data.count()
        }
    
    def _get_top_users(self, days: int = 30, limit: int = 5) -> List[Dict]:
        """Get top users by earnings"""
        top_users = UserAnalytics.objects.filter(
            period_start__gte=timezone.now() - timedelta(days=days)
        ).values(
            'user__id', 'user__username', 'user__email'
        ).annotate(
            total_earnings=Sum('earnings_total'),
            tasks_completed=Sum('tasks_completed')
        ).order_by('-total_earnings')[:limit]
        
        return list(top_users)
    
    def _parse_time_range_days(self, time_range: str) -> int:
        """Parse time range string to days"""
        if time_range == '7d':
            return 7
        elif time_range == '30d':
            return 30
        elif time_range == '90d':
            return 90
        elif time_range == '1y':
            return 365
        else:
            return 30