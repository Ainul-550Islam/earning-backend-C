from django.db.models import Count, Sum, Avg, F, Q, Max, Min
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.utils import timezone
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging
from ..models import AnalyticsEvent, UserAnalytics
from .DataCollector import DataCollector

logger = logging.getLogger(__name__)

class UserAnalyticsCollector(DataCollector):
    """
    Collector for user analytics data
    """
    
    def __init__(self):
        super().__init__(cache_timeout=600)  # 10 minutes cache
    
    def collect_user_analytics(
        self,
        user=None,
        period: str = 'daily',
        start_date: datetime = None,
        end_date: datetime = None
    ) -> List[Dict]:
        """
        Collect user analytics for a period
        
        Args:
            user: Specific user or None for all users
            period: Analytics period (daily, weekly, monthly)
            start_date: Start date
            end_date: End date
        
        Returns:
            List of user analytics data
        """
        # Set default dates
        if not start_date:
            if period == 'daily':
                start_date = timezone.now() - timedelta(days=7)
            elif period == 'weekly':
                start_date = timezone.now() - timedelta(weeks=4)
            elif period == 'monthly':
                start_date = timezone.now() - timedelta(days=90)
        
        if not end_date:
            end_date = timezone.now()
        
        # Build filters
        filters = {
            'event_time__gte': start_date,
            'event_time__lte': end_date
        }
        
        if user:
            filters['user'] = user
        
        # Collect event data
        events = AnalyticsEvent.objects.filter(**filters)
        
        # Group by period
        trunc_map = {
            'daily': TruncDate('event_time'),
            'weekly': TruncWeek('event_time'),
            'monthly': TruncMonth('event_time')
        }
        
        trunc_func = trunc_map.get(period, TruncDate('event_time'))
        
        # Aggregate by period and user
        analytics_data = events.annotate(
            period=trunc_func
        ).values(
            'period', 'user_id', 'user__username'
        ).annotate(
            # Activity metrics
            login_count=Count('id', filter=Q(event_type='user_login')),
            session_duration_avg=Avg('duration', filter=Q(event_type='user_login')),
            page_views=Count('id', filter=Q(event_type='page_view')),
            
            # Task metrics
            tasks_completed=Count('id', filter=Q(event_type='task_completed')),
            tasks_attempted=Count('id', filter=Q(event_type='task_completed') | Q(event_type='task_failed')),
            
            # Offer metrics
            offers_viewed=Count('id', filter=Q(event_type='offer_viewed')),
            offers_completed=Count('id', filter=Q(event_type='offer_completed')),
            
            # Earning metrics
            earnings_total=Sum('value', filter=Q(
                event_type__in=['task_completed', 'offer_completed', 'referral_joined']
            )),
            earnings_from_tasks=Sum('value', filter=Q(event_type='task_completed')),
            earnings_from_offers=Sum('value', filter=Q(event_type='offer_completed')),
            earnings_from_referrals=Sum('value', filter=Q(event_type='referral_joined')),
            
            # Withdrawal metrics
            withdrawals_requested=Count('id', filter=Q(event_type='withdrawal_requested')),
            withdrawals_completed=Count('id', filter=Q(event_type='withdrawal_processed')),
            withdrawals_amount=Sum('value', filter=Q(event_type='withdrawal_processed')),
            
            # Device metrics
            device_mobile_count=Count('id', filter=Q(device_type='mobile')),
            device_desktop_count=Count('id', filter=Q(device_type='desktop')),
            device_tablet_count=Count('id', filter=Q(device_type='tablet'))
        ).order_by('period', 'user_id')
        
        # Calculate derived metrics
        for data in analytics_data:
            # Task success rate
            if data['tasks_attempted'] > 0:
                data['task_success_rate'] = (data['tasks_completed'] / data['tasks_attempted']) * 100
            else:
                data['task_success_rate'] = 0.0
            
            # Offer conversion rate
            if data['offers_viewed'] > 0:
                data['offer_conversion_rate'] = (data['offers_completed'] / data['offers_viewed']) * 100
            else:
                data['offer_conversion_rate'] = 0.0
        
        return list(analytics_data)
    
    def collect_user_engagement(
        self,
        user_id: int = None,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict:
        """
        Collect user engagement metrics
        
        Args:
            user_id: Specific user ID
            start_date: Start date
            end_date: End date
        
        Returns:
            User engagement metrics
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        filters = {
            'event_time__gte': start_date,
            'event_time__lte': end_date
        }
        
        if user_id:
            filters['user_id'] = user_id
        
        events = AnalyticsEvent.objects.filter(**filters)
        
        # Calculate engagement metrics
        engagement_metrics = events.aggregate(
            total_sessions=Count('session_id', distinct=True),
            avg_session_duration=Avg('duration', filter=Q(event_type='user_login')),
            daily_active_users=Count('user_id', distinct=True, filter=Q(event_type='user_login')),
            weekly_active_users=Count('user_id', distinct=True),
            
            # Feature usage
            tasks_per_user=Avg(
                Count('id', filter=Q(event_type='task_completed')),
                distinct=True
            ),
            offers_per_user=Avg(
                Count('id', filter=Q(event_type='offer_completed')),
                distinct=True
            ),
            
            # Time metrics
            avg_time_between_logins=Avg('event_time'),  # Would need window function
            peak_usage_hour=Count('id', filter=Q(
                event_time__hour__gte=9,
                event_time__hour__lte=17
            ))
        )
        
        # Calculate engagement score
        score = 0
        
        # Session frequency (max 30)
        if engagement_metrics['total_sessions']:
            score += min(30, (engagement_metrics['total_sessions'] / 30) * 30)
        
        # Task completion (max 40)
        if engagement_metrics['tasks_per_user']:
            score += min(40, engagement_metrics['tasks_per_user'] * 10)
        
        # Offer completion (max 30)
        if engagement_metrics['offers_per_user']:
            score += min(30, engagement_metrics['offers_per_user'] * 10)
        
        engagement_metrics['engagement_score'] = min(100, score)
        engagement_metrics['engagement_level'] = self._get_engagement_level(score)
        
        return engagement_metrics
    
    def collect_user_retention(
        self,
        cohort_period: str = 'monthly',
        lookback_days: int = 90
    ) -> List[Dict]:
        """
        Collect user retention data by cohort
        
        Args:
            cohort_period: Cohort period (daily, weekly, monthly)
            lookback_days: Number of days to look back
        
        Returns:
            Retention data by cohort
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        start_date = timezone.now() - timedelta(days=lookback_days)
        
        # Get user cohorts
        trunc_map = {
            'daily': TruncDate('date_joined'),
            'weekly': TruncWeek('date_joined'),
            'monthly': TruncMonth('date_joined')
        }
        
        trunc_func = trunc_map.get(cohort_period, TruncMonth('date_joined'))
        
        cohorts = User.objects.filter(
            date_joined__gte=start_date
        ).annotate(
            cohort=trunc_func
        ).values('cohort').annotate(
            cohort_size=Count('id'),
            user_ids=ArrayAgg('id')
        ).order_by('cohort')
        
        retention_data = []
        
        for cohort in cohorts:
            cohort_date = cohort['cohort']
            cohort_users = set(cohort['user_ids'])
            
            cohort_retention = {
                'cohort_date': cohort_date,
                'cohort_size': len(cohort_users),
                'retention_days': {}
            }
            
            # Check retention for 1, 7, 14, 30, 60, 90 days
            retention_periods = [1, 7, 14, 30, 60, 90]
            
            for days in retention_periods:
                retention_date = cohort_date + timedelta(days=days)
                
                # Check if users were active after retention period
                active_users = AnalyticsEvent.objects.filter(
                    user_id__in=cohort_users,
                    event_time__gte=cohort_date,
                    event_time__lte=retention_date,
                    event_type='user_login'
                ).values_list('user_id', flat=True).distinct()
                
                retention_rate = self._calculate_conversion_rate(
                    len(active_users),
                    len(cohort_users)
                )
                
                cohort_retention['retention_days'][f'day_{days}'] = retention_rate
            
            retention_data.append(cohort_retention)
        
        return retention_data
    
    def collect_user_segmentation(
        self,
        segment_by: str = 'engagement',
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict:
        """
        Segment users based on criteria
        
        Args:
            segment_by: Segmentation criteria
            start_date: Start date
            end_date: End date
        
        Returns:
            User segments with metrics
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        segments = {}
        
        if segment_by == 'engagement':
            # Segment by engagement level
            segments = {
                'high': {'min_score': 70, 'max_score': 100},
                'medium': {'min_score': 30, 'max_score': 69},
                'low': {'min_score': 0, 'max_score': 29}
            }
            
            # Get user analytics
            user_analytics = UserAnalytics.objects.filter(
                period_start__gte=start_date,
                period_end__lte=end_date
            )
            
            for segment_name, score_range in segments.items():
                segment_users = user_analytics.filter(
                    engagement_score__gte=score_range['min_score'],
                    engagement_score__lte=score_range['max_score']
                )
                
                segments[segment_name] = {
                    'user_count': segment_users.count(),
                    'avg_earnings': segment_users.aggregate(avg=Avg('earnings_total'))['avg'] or 0,
                    'avg_tasks': segment_users.aggregate(avg=Avg('tasks_completed'))['avg'] or 0,
                    'retention_rate': segment_users.filter(is_retained=True).count() / segment_users.count() * 100 if segment_users.count() > 0 else 0
                }
        
        elif segment_by == 'spending':
            # Segment by spending behavior
            segments = {
                'whales': {'min_amount': 100, 'description': 'Top spenders'},
                'dolphins': {'min_amount': 10, 'max_amount': 99, 'description': 'Medium spenders'},
                'minnows': {'max_amount': 9, 'description': 'Low spenders'},
                'free': {'max_amount': 0, 'description': 'Non-spenders'}
            }
            
            # Get revenue data per user
            from ..models import RevenueAnalytics
            
        elif segment_by == 'activity':
            # Segment by activity frequency
            segments = {
                'daily_active': {'min_logins': 20, 'description': 'Daily users'},
                'weekly_active': {'min_logins': 4, 'max_logins': 19, 'description': 'Weekly users'},
                'monthly_active': {'min_logins': 1, 'max_logins': 3, 'description': 'Monthly users'},
                'inactive': {'max_logins': 0, 'description': 'Inactive users'}
            }
        
        return segments
    
    def get_total_users(self) -> int:
        """Get total number of users"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.count()
    
    def get_active_users(self, days: int = 7) -> int:
        """Get number of active users in last N days"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        active_users = AnalyticsEvent.objects.filter(
            event_type='user_login',
            event_time__gte=cutoff_date
        ).values('user_id').distinct().count()
        
        return active_users
    
    def get_new_users_today(self) -> int:
        """Get number of new users today"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        
        return User.objects.filter(
            date_joined__gte=today,
            date_joined__lt=tomorrow
        ).count()
    
    def get_tasks_completed_today(self) -> int:
        """Get number of tasks completed today"""
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        
        return AnalyticsEvent.objects.filter(
            event_type='task_completed',
            event_time__gte=today,
            event_time__lt=tomorrow
        ).count()
    
    def get_offers_completed_today(self) -> int:
        """Get number of offers completed today"""
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        
        return AnalyticsEvent.objects.filter(
            event_type='offer_completed',
            event_time__gte=today,
            event_time__lt=tomorrow
        ).count()
    
    def get_conversion_rate(self) -> float:
        """Get overall conversion rate"""
        offers_viewed = AnalyticsEvent.objects.filter(
            event_type='offer_viewed'
        ).count()
        
        offers_completed = AnalyticsEvent.objects.filter(
            event_type='offer_completed'
        ).count()
        
        if offers_viewed > 0:
            return (offers_completed / offers_viewed) * 100
        return 0.0
    
    def get_average_engagement_score(self) -> float:
        """Get average engagement score"""
        avg_score = UserAnalytics.objects.aggregate(
            avg_score=Avg('engagement_score')
        )['avg_score'] or 0
        
        return round(avg_score, 2)
    
    def get_user_growth_trend(self, days: int = 30) -> float:
        """Get user growth trend percentage"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        previous_start_date = start_date - timedelta(days=days)
        
        # Current period users
        current_users = User.objects.filter(
            date_joined__gte=start_date,
            date_joined__lt=end_date
        ).count()
        
        # Previous period users
        previous_users = User.objects.filter(
            date_joined__gte=previous_start_date,
            date_joined__lt=start_date
        ).count()
        
        if previous_users > 0:
            return ((current_users - previous_users) / previous_users) * 100
        elif current_users > 0:
            return 100.0
        else:
            return 0.0
    
    def get_task_completion_trend(self, days: int = 30) -> float:
        """Get task completion trend percentage"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        previous_start_date = start_date - timedelta(days=days)
        
        # Current period tasks
        current_tasks = AnalyticsEvent.objects.filter(
            event_type='task_completed',
            event_time__gte=start_date,
            event_time__lt=end_date
        ).count()
        
        # Previous period tasks
        previous_tasks = AnalyticsEvent.objects.filter(
            event_type='task_completed',
            event_time__gte=previous_start_date,
            event_time__lt=start_date
        ).count()
        
        if previous_tasks > 0:
            return ((current_tasks - previous_tasks) / previous_tasks) * 100
        elif current_tasks > 0:
            return 100.0
        else:
            return 0.0
    
    # Helper methods
    def _get_engagement_level(self, score: float) -> str:
        """Get engagement level from score"""
        if score >= 70:
            return 'high'
        elif score >= 30:
            return 'medium'
        else:
            return 'low'