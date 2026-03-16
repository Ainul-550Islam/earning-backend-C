import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.db.models import Sum, Avg, Count, Q
from decimal import Decimal

from ..models import AnalyticsEvent, UserAnalytics
from ..processors import ChartDataBuilder

logger = logging.getLogger(__name__)

class UserDashboard:
    """
    User dashboard with personalized analytics
    """
    
    def __init__(self, user):
        self.user = user
        self.chart_builder = ChartDataBuilder(color_palette='primary')
    
    def get_data(self, time_range: str = '30d') -> Dict:
        """
        Get user dashboard data
        
        Args:
            time_range: Time range for data
        
        Returns:
            User dashboard data
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
        
        dashboard_data = {
            'user': self._get_user_info(),
            'summary': self._get_summary_metrics(start_date, end_date),
            'earnings': self._get_earnings_data(start_date, end_date),
            'activity': self._get_activity_data(start_date, end_date),
            'progress': self._get_progress_data(),
            'recommendations': self._get_recommendations(),
            'charts': self._get_user_charts(start_date, end_date, time_range),
            'goals': self._get_user_goals(),
            'period': {
                'start': start_date,
                'end': end_date,
                'range': time_range
            }
        }
        
        return dashboard_data
    
    def _get_user_info(self) -> Dict:
        """Get user information"""
        return {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'join_date': self.user.date_joined,
            'account_type': getattr(self.user, 'account_type', 'standard'),
            'profile_completion': self._calculate_profile_completion(),
            'verification_status': getattr(self.user, 'is_verified', False)
        }
    
    def _get_summary_metrics(self, start_date: datetime, end_date: datetime) -> Dict:
        """Get summary metrics for user"""
        # Get user analytics
        user_analytics = UserAnalytics.objects.filter(
            user=self.user,
            period_start__gte=start_date,
            period_end__lte=end_date
        ).aggregate(
            total_earnings=Sum('earnings_total'),
            tasks_completed=Sum('tasks_completed'),
            offers_completed=Sum('offers_completed'),
            avg_engagement=Avg('engagement_score'),
            active_days=Sum('active_days')
        )
        
        # Current balance
        current_balance = getattr(self.user, 'wallet_balance', Decimal('0'))
        
        # Recent activity
        recent_activity = AnalyticsEvent.objects.filter(
            user=self.user,
            event_time__gte=timezone.now() - timedelta(days=1)
        ).count()
        
        # Rank/percentile (simplified)
        user_rank = self._calculate_user_rank()
        
        return {
            'current_balance': current_balance,
            'total_earnings': user_analytics['total_earnings'] or Decimal('0'),
            'tasks_completed': user_analytics['tasks_completed'] or 0,
            'offers_completed': user_analytics['offers_completed'] or 0,
            'engagement_score': user_analytics['avg_engagement'] or 0,
            'active_days': user_analytics['active_days'] or 0,
            'recent_activity': recent_activity,
            'user_rank': user_rank,
            'withdrawal_eligible': current_balance >= Decimal('100')  # Minimum withdrawal
        }
    
    def _get_earnings_data(self, start_date: datetime, end_date: datetime) -> Dict:
        """Get earnings breakdown"""
        # Earnings by source
        earnings_by_source = AnalyticsEvent.objects.filter(
            user=self.user,
            event_time__gte=start_date,
            event_time__lte=end_date,
            event_type='earning'
        ).values('source').annotate(total_earnings=Sum('amount'))
        earnings_data = {entry['source']: entry['total_earnings'] for entry in earnings_by_source}