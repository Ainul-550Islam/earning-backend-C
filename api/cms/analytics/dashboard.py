# cms/analytics/dashboard.py
"""
Analytics Dashboard System

Real-time business intelligence with:
- User engagement metrics
- Revenue analytics
- Conversion tracking
- Cohort analysis
- Custom reports
- Data export (CSV, Excel, JSON)
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta, date
from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone
import json
import logging

logger = logging.getLogger('cms.analytics.dashboard')


# ─────────────────────────────────────────────────────────────────────────────
# ANALYTICS METRICS
# ─────────────────────────────────────────────────────────────────────────────

class AnalyticsDashboard:
    """Central analytics dashboard"""
    
    @staticmethod
    def get_overview(days: int = 30) -> Dict[str, Any]:
        """Get high-level overview metrics"""
        from django.contrib.auth.models import User
        from api.cms.models_new.surveys import Survey, SurveyCompletion
        from api.cms.models_new.offers import Offer
        
        start_date = timezone.now() - timedelta(days=days)
        
        # User metrics
        total_users = User.objects.count()
        new_users = User.objects.filter(date_joined__gte=start_date).count()
        active_users = User.objects.filter(
            last_login__gte=start_date
        ).count()
        
        # Survey metrics
        surveys_available = Survey.objects.filter(is_active=True).count()
        completions = SurveyCompletion.objects.filter(
            created_at__gte=start_date
        ).count()
        
        # Revenue metrics
        total_earned = SurveyCompletion.objects.filter(
            created_at__gte=start_date
        ).aggregate(total=Sum('reward_amount'))['total'] or 0
        
        # Offer metrics
        offers_count = Offer.objects.filter(is_active=True).count()
        
        return {
            'total_users': total_users,
            'new_users': new_users,
            'active_users': active_users,
            'user_growth_rate': (new_users / total_users * 100) if total_users > 0 else 0,
            'surveys_available': surveys_available,
            'total_completions': completions,
            'total_earned': float(total_earned),
            'average_reward': float(total_earned / completions) if completions > 0 else 0,
            'offers_available': offers_count,
            'period_days': days,
        }
    
    @staticmethod
    def get_daily_metrics(days: int = 30) -> List[Dict[str, Any]]:
        """Get daily breakdown metrics"""
        from api.cms.models_new.surveys import SurveyCompletion
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_data = []
        for i in range(days):
            current_date = (start_date + timedelta(days=i)).date()
            next_date = current_date + timedelta(days=1)
            
            completions = SurveyCompletion.objects.filter(
                created_at__date=current_date
            ).count()
            
            earned = SurveyCompletion.objects.filter(
                created_at__date=current_date
            ).aggregate(total=Sum('reward_amount'))['total'] or 0
            
            daily_data.append({
                'date': current_date.isoformat(),
                'completions': completions,
                'earned': float(earned),
            })
        
        return daily_data
    
    @staticmethod
    def get_conversion_funnel() -> Dict[str, Any]:
        """Get conversion funnel (views -> clicks -> completions)"""
        from django.contrib.auth.models import User
        from api.cms.models_new.surveys import Survey, SurveyCompletion
        
        # Users who viewed offers
        viewers = User.objects.filter(
            surveycompletion__isnull=False
        ).distinct().count()
        
        # Users who completed at least one
        completers = SurveyCompletion.objects.values('user').distinct().count()
        
        # Users who completed multiple
        multi_completers = SurveyCompletion.objects.values('user').annotate(
            count=Count('id')
        ).filter(count__gt=1).count()
        
        total_users = User.objects.count()
        
        return {
            'total_users': total_users,
            'viewers': viewers,
            'viewer_rate': (viewers / total_users * 100) if total_users > 0 else 0,
            'completers': completers,
            'completion_rate': (completers / viewers * 100) if viewers > 0 else 0,
            'multi_completers': multi_completers,
            'repeat_rate': (multi_completers / completers * 100) if completers > 0 else 0,
        }
    
    @staticmethod
    def get_top_surveys(limit: int = 10) -> List[Dict[str, Any]]:
        """Get top performing surveys"""
        from api.cms.models_new.surveys import Survey, SurveyCompletion
        
        surveys = Survey.objects.annotate(
            completion_count=Count('surveycompletion'),
            total_earned=Sum('surveycompletion__reward_amount')
        ).filter(
            completion_count__gt=0
        ).order_by('-completion_count')[:limit]
        
        return [
            {
                'id': survey.id,
                'title': survey.title,
                'completions': survey.completion_count,
                'total_earned': float(survey.total_earned or 0),
                'reward_per_completion': float(survey.reward_amount),
            }
            for survey in surveys
        ]
    
    @staticmethod
    def get_top_earners(limit: int = 10) -> List[Dict[str, Any]]:
        """Get top earning users"""
        from django.contrib.auth.models import User
        from api.cms.models_new.surveys import SurveyCompletion
        
        users = User.objects.annotate(
            total_earned=Sum('surveycompletion__reward_amount'),
            completion_count=Count('surveycompletion')
        ).filter(
            completion_count__gt=0
        ).order_by('-total_earned')[:limit]
        
        return [
            {
                'user_id': user.id,
                'username': user.username,
                'total_earned': float(user.total_earned or 0),
                'completions': user.completion_count,
            }
            for user in users
        ]
    
    @staticmethod
    def get_cohort_analysis(cohort_size: int = 30) -> Dict[str, Any]:
        """Analyze user retention by cohort"""
        from django.contrib.auth.models import User
        
        cohorts = {}
        now = timezone.now()
        
        for week in range(12):  # Last 12 weeks
            week_start = now - timedelta(weeks=week+1)
            week_end = week_start + timedelta(weeks=1)
            
            new_users = User.objects.filter(
                date_joined__gte=week_start,
                date_joined__lt=week_end
            ).count()
            
            retained_users = User.objects.filter(
                date_joined__gte=week_start,
                date_joined__lt=week_end,
                last_login__gte=now - timedelta(days=7)
            ).count()
            
            cohorts[f'week_{week}'] = {
                'new_users': new_users,
                'retained_users': retained_users,
                'retention_rate': (retained_users / new_users * 100) if new_users > 0 else 0,
            }
        
        return cohorts
    
    @staticmethod
    def export_data(format: str = 'json', days: int = 30) -> str:
        """Export analytics data"""
        overview = AnalyticsDashboard.get_overview(days)
        daily = AnalyticsDashboard.get_daily_metrics(days)
        
        data = {
            'overview': overview,
            'daily_metrics': daily,
            'export_date': timezone.now().isoformat(),
        }
        
        if format == 'json':
            return json.dumps(data, indent=2)
        elif format == 'csv':
            return AnalyticsDashboard._to_csv(data)
        else:
            return json.dumps(data)
    
    @staticmethod
    def _to_csv(data: Dict[str, Any]) -> str:
        """Convert to CSV format"""
        lines = []
        lines.append('Date,Completions,Earned')
        
        for day in data['daily_metrics']:
            lines.append(f"{day['date']},{day['completions']},{day['earned']:.2f}")
        
        return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# REVENUE ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

class RevenueAnalytics:
    """Revenue and earnings analytics"""
    
    @staticmethod
    def get_earnings_summary(days: int = 30) -> Dict[str, Any]:
        """Get earnings summary"""
        from api.cms.models_new.surveys import SurveyCompletion
        
        start_date = timezone.now() - timedelta(days=days)
        
        completions = SurveyCompletion.objects.filter(
            created_at__gte=start_date
        )
        
        total_earned = completions.aggregate(
            total=Sum('reward_amount')
        )['total'] or 0
        
        avg_earning = completions.aggregate(
            avg=Avg('reward_amount')
        )['avg'] or 0
        
        max_earning = completions.aggregate(
            max=Count('reward_amount')
        )['max'] or 0
        
        return {
            'total_earned': float(total_earned),
            'completion_count': completions.count(),
            'average_per_completion': float(avg_earning),
            'total_completions': completions.count(),
            'period_days': days,
        }
    
    @staticmethod
    def get_earnings_by_source(days: int = 30) -> Dict[str, float]:
        """Get earnings breakdown by source (surveys, offers, etc)"""
        from api.cms.models_new.surveys import SurveyCompletion
        from api.cms.models_new.offers import OfferConversion
        
        start_date = timezone.now() - timedelta(days=days)
        
        survey_earnings = SurveyCompletion.objects.filter(
            created_at__gte=start_date
        ).aggregate(total=Sum('reward_amount'))['total'] or 0
        
        offer_earnings = OfferConversion.objects.filter(
            created_at__gte=start_date
        ).aggregate(total=Sum('commission'))['total'] or 0
        
        return {
            'surveys': float(survey_earnings),
            'offers': float(offer_earnings),
            'total': float(survey_earnings + offer_earnings),
        }


# ─────────────────────────────────────────────────────────────────────────────
# ENGAGEMENT ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

class EngagementAnalytics:
    """User engagement metrics"""
    
    @staticmethod
    def get_daily_active_users(days: int = 30) -> List[Dict[str, Any]]:
        """Get daily active users"""
        from django.contrib.auth.models import User
        
        dau_data = []
        for i in range(days):
            current_date = (timezone.now() - timedelta(days=i)).date()
            
            active = User.objects.filter(
                last_login__date=current_date
            ).count()
            
            dau_data.append({
                'date': current_date.isoformat(),
                'active_users': active,
            })
        
        return list(reversed(dau_data))
    
    @staticmethod
    def get_monthly_active_users() -> int:
        """Get monthly active users"""
        from django.contrib.auth.models import User
        
        month_ago = timezone.now() - timedelta(days=30)
        return User.objects.filter(
            last_login__gte=month_ago
        ).count()
    
    @staticmethod
    def get_user_segments() -> Dict[str, int]:
        """Segment users by activity level"""
        from django.contrib.auth.models import User
        from api.cms.models_new.surveys import SurveyCompletion
        
        # Define segments
        week_ago = timezone.now() - timedelta(days=7)
        month_ago = timezone.now() - timedelta(days=30)
        
        very_active = User.objects.filter(
            last_login__gte=week_ago
        ).count()
        
        active = User.objects.filter(
            last_login__gte=month_ago,
            last_login__lt=week_ago
        ).count()
        
        inactive = User.objects.filter(
            last_login__lt=month_ago
        ).count()
        
        return {
            'very_active': very_active,
            'active': active,
            'inactive': inactive,
        }


# Export public API
__all__ = [
    'AnalyticsDashboard',
    'RevenueAnalytics',
    'EngagementAnalytics',
]
