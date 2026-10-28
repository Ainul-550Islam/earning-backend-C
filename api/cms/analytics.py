# api/cms/analytics.py
"""Analytics utilities for CMS."""
from django.db.models.functions import TruncHour
import logging
import datetime
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction, models
from django.db.models import Sum, Count, Avg, F, Q, Max, Min
from django.db.models.functions import TruncDate

from api.cms.abstracts import BaseService
from api.cms.monitoring import CMSMetrics
from api.cms.caching import CMSCache

logger = logging.getLogger(__name__)
User = get_user_model()


# ── Original Analytics (Preserved) ─────────────────────────────────────

class RevenueAnalytics:
    """CPAlead revenue and conversion analytics."""

    @staticmethod
    def get_summary(days: int = 30) -> Dict:
        """Overall revenue summary for dashboard."""
        from api.cms.models_new.cpalead import ConversionLog
        cutoff = timezone.now() - datetime.timedelta(days=days)
        agg = ConversionLog.objects.filter(
            status='approved', created_at__gte=cutoff
        ).aggregate(
            total_conversions=Count('id'),
            total_revenue=Sum('payout_usd'),
            avg_payout=Avg('payout_usd'),
            max_payout=Max('payout_usd'),
            total_coins_awarded=Sum('virtual_amount_awarded'),
        )
        # Compare to previous period
        prev_cutoff = cutoff - datetime.timedelta(days=days)
        prev = ConversionLog.objects.filter(
            status='approved',
            created_at__gte=prev_cutoff, created_at__lt=cutoff
        ).aggregate(
            total_revenue=Sum('payout_usd'),
            total_conversions=Count('id'),
        )
        curr_rev = float(agg['total_revenue'] or 0)
        prev_rev = float(prev['total_revenue'] or 0)
        revenue_change_pct = (
            round((curr_rev - prev_rev) / prev_rev * 100, 1) if prev_rev else 0
        )
        return {
            'period_days': days,
            'total_conversions': agg['total_conversions'] or 0,
            'total_revenue_usd': curr_rev,
            'avg_payout_usd': float(agg['avg_payout'] or 0),
            'max_payout_usd': float(agg['max_payout'] or 0),
            'total_coins_awarded': float(agg['total_coins_awarded'] or 0),
            'revenue_vs_prev_period_pct': revenue_change_pct,
            'prev_period_revenue_usd': prev_rev,
        }

    @staticmethod
    def get_daily_revenue(days: int = 30) -> List[Dict]:
        """Daily revenue breakdown."""
        from api.cms.models_new.cpalead import ConversionLog
        cutoff = timezone.now() - datetime.timedelta(days=days)
        return list(
            ConversionLog.objects
            .filter(status='approved', created_at__gte=cutoff)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(
                conversions=Count('id'),
                revenue=Sum('payout_usd'),
                coins=Sum('virtual_amount_awarded'),
                unique_users=Count('user', distinct=True),
            )
            .order_by('date')
        )

    @staticmethod
    def get_by_offer_type(days: int = 30) -> List[Dict]:
        """Revenue breakdown by offer type."""
        from api.cms.models_new.cpalead import ConversionLog
        cutoff = timezone.now() - datetime.timedelta(days=days)
        return list(
            ConversionLog.objects
            .filter(status='approved', created_at__gte=cutoff)
            .values('campaign_id')
            .annotate(count=Count('id'), total=Sum('payout_usd'))
            .order_by('-total')[:20]
        )

    @staticmethod
    def get_hourly_pattern(days: int = 7) -> List[Dict]:
        """Hourly conversion pattern — useful for scheduling."""
        from api.cms.models_new.cpalead import ConversionLog
        cutoff = timezone.now() - datetime.timedelta(days=days)
        return list(
            ConversionLog.objects
            .filter(status='approved', created_at__gte=cutoff)
            .annotate(hour=TruncHour('created_at'))
            .values('hour')
            .annotate(count=Count('id'), revenue=Sum('payout_usd'))
            .order_by('hour')
        )


class UserAnalytics:
    """User behavior and growth analytics."""

    @staticmethod
    def get_summary(days: int = 30) -> Dict:
        from django.contrib.auth import get_user_model
        from api.cms.models_new.withdrawal import UserProfile
        User = get_user_model()
        cutoff = timezone.now() - datetime.timedelta(days=days)
        total_users = User.objects.filter(is_active=True).count()
        new_users = User.objects.filter(date_joined__gte=cutoff).count()
        active_users = User.objects.filter(last_login__gte=cutoff).count()
        suspended = UserProfile.objects.filter(is_suspended=True).count()
        return {
            'total_users': total_users,
            'new_users_period': new_users,
            'active_users_period': active_users,
            'suspended_users': suspended,
            'activation_rate': round(active_users / max(total_users, 1) * 100, 1),
        }

    @staticmethod
    def get_registrations_over_time(days: int = 30) -> List[Dict]:
        from django.contrib.auth import get_user_model
        cutoff = timezone.now() - datetime.timedelta(days=days)
        return list(
            get_user_model().objects
            .filter(date_joined__gte=cutoff)
            .annotate(date=TruncDate('date_joined'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )

    @staticmethod
    def get_retention(cohort_days: int = 7) -> Dict:
        """Basic retention: users who returned after first conversion."""
        from api.cms.models_new.cpalead import ConversionLog
        return {
            'cohort_days': cohort_days,
            'note': 'Retention data requires full cohort analysis — placeholder',
        }

    @staticmethod
    def get_level_distribution() -> List[Dict]:
        from api.cms.models_new.withdrawal import UserProfile
        return list(
            UserProfile.objects
            .values('level')
            .annotate(count=Count('id'))
            .order_by('level')
        )


class OfferWallAnalytics:
    """Offerwall performance analytics."""

    @staticmethod
    def get_click_stats(days: int = 7) -> Dict:
        from api.cms.models_new.cpalead import ClickLog
        cutoff = timezone.now() - datetime.timedelta(days=days)
        return ClickLog.objects.filter(created_at__gte=cutoff).aggregate(
            total_clicks=Count('id'),
            converted=Count('id', filter=Q(has_converted=True)),
            fraud_clicks=Count('id', filter=Q(is_fraud=True)),
            unique_ips=Count('ip_address', distinct=True),
        )

    @staticmethod
    def get_top_countries(days: int = 7, limit: int = 10) -> List[Dict]:
        from api.cms.models_new.cpalead import ClickLog
        cutoff = timezone.now() - datetime.timedelta(days=days)
        return list(
            ClickLog.objects
            .filter(created_at__gte=cutoff, ip_address__isnull=False)
            .values('ip_address')  # Would use country_code if available
            .annotate(clicks=Count('id'), converted=Count('id', filter=Q(has_converted=True)))
            .order_by('-clicks')[:limit]
        )

    @staticmethod
    def get_locker_performance(limit: int = 10) -> List[Dict]:
        from api.cms.models_new.cpalead import ContentLocker
        return list(
            ContentLocker.objects
            .filter(is_active=True)
            .annotate(
                conversion_rate=F('total_unlocks') * 100.0 / (F('total_views') + 1)
            )
            .values('id', 'name', 'locker_type', 'total_views', 'total_unlocks', 'conversion_rate')
            .order_by('-total_unlocks')[:limit]
        )


class WithdrawalAnalytics:
    """Withdrawal and payout analytics."""

    @staticmethod
    def get_summary(days: int = 30) -> Dict:
        from api.cms.models_new.withdrawal import WithdrawalRequest
        cutoff = timezone.now() - datetime.timedelta(days=days)
        return WithdrawalRequest.objects.filter(created_at__gte=cutoff).aggregate(
            total_requests=Count('id'),
            total_paid=Sum('net_usd', filter=Q(status='paid')),
            total_pending=Count('id', filter=Q(status__in=['pending', 'approved'])),
            avg_amount=Avg('net_usd', filter=Q(status='paid')),
        )

    @staticmethod
    def get_by_method(days: int = 30) -> List[Dict]:
        from api.cms.models_new.withdrawal import WithdrawalRequest
        cutoff = timezone.now() - datetime.timedelta(days=days)
        return list(
            WithdrawalRequest.objects
            .filter(status='paid', created_at__gte=cutoff)
            .values('method')
            .annotate(count=Count('id'), total_usd=Sum('net_usd'))
            .order_by('-total_usd')
        )


class ContentAnalytics:
    """Content performance analytics."""

    @staticmethod
    def get_blog_stats(days: int = 30) -> Dict:
        try:
            from api.cms.models_new.blog import BlogPost
            cutoff = timezone.now() - datetime.timedelta(days=days)
            return {
                'total_posts': BlogPost.objects.filter(status='published').count(),
                'new_posts': BlogPost.objects.filter(
                    status='published', published_at__gte=cutoff
                ).count(),
            }
        except Exception:
            return {}

    @staticmethod
    def get_quiz_stats(days: int = 30) -> Dict:
        from api.cms.models_new.quiz import QuizAttempt, QuizTemplate
        cutoff = timezone.now() - datetime.timedelta(days=days)
        attempts = QuizAttempt.objects.filter(created_at__gte=cutoff)
        return {
            'total_quizzes': QuizTemplate.objects.filter(is_active=True).count(),
            'total_attempts': attempts.count(),
            'completions': attempts.filter(is_completed=True).count(),
            'coins_awarded': float(
                attempts.filter(is_completed=True).aggregate(
                    s=Sum('reward_coins'))['s'] or 0
            ),
        }

    @staticmethod
    def get_smartlink_stats(days: int = 7) -> Dict:
        from api.cms.models_new.smartlink import SmartLink, SmartLinkClick
        cutoff = timezone.now() - datetime.timedelta(days=days)
        return {
            'active_smartlinks': SmartLink.objects.filter(is_active=True).count(),
            'total_clicks': SmartLinkClick.objects.filter(created_at__gte=cutoff).count(),
            'conversions': SmartLinkClick.objects.filter(
                created_at__gte=cutoff, has_converted=True
            ).count(),
        }


class CMSAnalyticsDashboard:
    """Unified analytics dashboard — aggregates all analytics."""
    CACHE_TTL = 300  # 5 minutes

    @classmethod
    def get_full_dashboard(cls, days: int = 30) -> Dict:
        cache_key = f'cms:analytics:dashboard:{days}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        data = {
            'generated_at': timezone.now().isoformat(),
            'period_days': days,
            'revenue': RevenueAnalytics.get_summary(days),
            'users': UserAnalytics.get_summary(days),
            'offerwall': OfferWallAnalytics.get_click_stats(days),
            'withdrawals': WithdrawalAnalytics.get_summary(days),
            'content': {
                'blog': ContentAnalytics.get_blog_stats(days),
                'quiz': ContentAnalytics.get_quiz_stats(days),
                'smartlink': ContentAnalytics.get_smartlink_stats(days),
            },
        }
        cache.set(cache_key, data, cls.CACHE_TTL)
        return data


# ── Enhanced Analytics Classes ─────────────────────────────────────

class BaseAnalytics(BaseService):
    """Base analytics class with common functionality."""
    
    def __init__(self):
        """Initialize analytics."""
        super().__init__()
        self.metrics = CMSMetrics
        self.cache = CMSCache
    
    def validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input data."""
        return data
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute analytics."""
        raise NotImplementedError("Subclasses must implement execute method")


class UserAnalytics(BaseAnalytics):
    """Handle user-related analytics."""

    @staticmethod
    def get_summary(days: int = 30) -> Dict:
        """Get user analytics summary — delegates to instance method for backwards compat."""
        return UserAnalytics().get_user_summary(days=days)

    def get_user_summary(self, days: int = 30) -> Dict:
        """Aggregate user metrics for the dashboard."""
        from api.cms.models_new.profile_surveys import SurveyCompletion
        from api.cms.models_new.survey_rewards import RewardTransaction
        from django.contrib.auth import get_user_model
        _User = get_user_model()
        start = timezone.now() - datetime.timedelta(days=days)
        total_users   = _User.objects.filter(is_active=True).count()
        new_users     = _User.objects.filter(date_joined__gte=start).count()
        completions   = SurveyCompletion.objects.filter(completed_at__gte=start, status="approved")
        active_users  = completions.values("user").distinct().count()
        total_rewards = completions.aggregate(total=Sum("total_reward_earned"))["total"] or Decimal("0")
        return {
            "period_days": days,
            "total_users": total_users,
            "new_users": new_users,
            "active_users": active_users,
            "active_users_period": days,
            "total_rewards_paid": float(total_rewards),
        }

    def get_user_statistics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive user statistics."""
        try:
            user = User.objects.get(id=user_id)
            start_date = timezone.now() - timezone.timedelta(days=days)
            
            # Survey statistics
            from api.cms.models_new.profile_surveys import SurveyCompletion
            survey_stats = SurveyCompletion.objects.filter(
                user=user,
                completed_at__gte=start_date,
                status='completed'
            ).aggregate(
                total_surveys=Count('id'),
                total_rewards=Sum('survey__reward_amount')
            )
            
            # Transaction statistics
            from api.cms.models_new.survey_rewards import RewardTransaction
            transaction_stats = RewardTransaction.objects.filter(
                user=user,
                created_at__gte=start_date
            ).aggregate(
                total_transactions=Count('id'),
                total_earned=Sum('amount', filter=models.Q(transaction_type='earned')),
                total_withdrawn=Sum('amount', filter=models.Q(transaction_type='withdrawal'))
            )
            
            # Calculate current balance
            current_balance = self._calculate_user_balance(user)
            
            return {
                'user_id': user_id,
                'username': user.username,
                'period_days': days,
                'surveys': {
                    'completed': survey_stats['total_surveys'] or 0,
                    'total_rewards': float(survey_stats['total_rewards'] or 0)
                },
                'transactions': {
                    'total': transaction_stats['total_transactions'] or 0,
                    'earned': float(transaction_stats['total_earned'] or 0),
                    'withdrawn': float(transaction_stats['total_withdrawn'] or 0)
                },
                'balance': current_balance,
                'generated_at': timezone.now().isoformat()
            }
            
        except User.DoesNotExist:
            return {
                'error': 'User not found',
                'error_code': 'USER_NOT_FOUND'
            }
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            return {
                'error': 'Failed to get user statistics',
                'error_code': 'STATISTICS_ERROR'
            }
    
    def _calculate_user_balance(self, user) -> Dict[str, Any]:
        """Calculate user's current balance."""
        try:
            from api.cms.models_new.survey_rewards import RewardTransaction
            
            earned = RewardTransaction.objects.filter(
                user=user,
                transaction_type='earned',
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            withdrawn = RewardTransaction.objects.filter(
                user=user,
                transaction_type='withdrawal',
                status__in=['pending', 'completed']
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            current_balance = earned - withdrawn
            
            return {
                'current': float(current_balance),
                'total_earned': float(earned),
                'total_withdrawn': float(withdrawn),
                'currency': 'USD'
            }
        except Exception as e:
            logger.error(f"Error calculating user balance: {e}")
            return {
                'current': 0.0,
                'total_earned': 0.0,
                'total_withdrawn': 0.0,
                'currency': 'USD'
            }


class SurveyAnalytics(BaseAnalytics):
    """Handle survey-related analytics."""
    
    def get_survey_statistics(self, survey_id: int = None, days: int = 30) -> Dict[str, Any]:
        """Get survey statistics."""
        try:
            start_date = timezone.now() - timezone.timedelta(days=days)
            
            if survey_id:
                # Specific survey statistics
                from api.cms.models_new.survey import Survey, SurveyCompletion
                survey = Survey.objects.get(id=survey_id)
                
                completions = SurveyCompletion.objects.filter(
                    survey=survey,
                    completed_at__gte=start_date,
                    status='completed'
                ).aggregate(
                    total_completions=Count('id'),
                    total_rewards_paid=Sum('survey__reward_amount'),
                    avg_completion_time=Avg('duration'),
                    unique_users=Count('user', distinct=True)
                )
                
                return {
                    'survey_id': survey_id,
                    'survey_title': survey.title,
                    'period_days': days,
                    'completions': {
                        'total': completions['total_completions'] or 0,
                        'unique_users': completions['unique_users'] or 0,
                        'total_rewards_paid': float(completions['total_rewards_paid'] or 0),
                        'avg_completion_time': float(completions['avg_completion_time'] or 0)
                    },
                    'survey_info': {
                        'reward_amount': float(survey.reward_amount),
                        'is_active': survey.is_active,
                        'category': survey.category
                    },
                    'generated_at': timezone.now().isoformat()
                }
            else:
                # Overall survey statistics
                from api.cms.models_new.survey import Survey, SurveyCompletion
                
                survey_stats = SurveyCompletion.objects.filter(
                    completed_at__gte=start_date,
                    status='completed'
                ).aggregate(
                    total_completions=Count('id'),
                    total_rewards_paid=Sum('survey__reward_amount'),
                    unique_users=Count('user', distinct=True),
                    avg_completion_time=Avg('duration')
                )
                
                active_surveys = Survey.objects.filter(is_active=True).count()
                total_surveys = Survey.objects.count()
                
                return {
                    'period_days': days,
                    'overall': {
                        'total_completions': survey_stats['total_completions'] or 0,
                        'unique_users': survey_stats['unique_users'] or 0,
                        'total_rewards_paid': float(survey_stats['total_rewards_paid'] or 0),
                        'avg_completion_time': float(survey_stats['avg_completion_time'] or 0)
                    },
                    'surveys': {
                        'active': active_surveys,
                        'total': total_surveys,
                        'completion_rate': (survey_stats['total_completions'] or 0) / total_surveys * 100 if total_surveys > 0 else 0
                    },
                    'generated_at': timezone.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting survey statistics: {e}")
            return {
                'error': 'Failed to get survey statistics',
                'error_code': 'SURVEY_STATS_ERROR'
            }


# ── Analytics Manager ─────────────────────────────────────

class EnhancedAnalyticsManager:
    """Manager for handling all analytics."""
    
    def __init__(self):
        """Initialize analytics manager."""
        self.user = UserAnalytics()
        self.survey = SurveyAnalytics()
        self.logger = logging.getLogger(f"{__name__}.manager")
    
    def get_analytics(self, analytics_type: str, *args, **kwargs):
        """Get analytics by type."""
        try:
            if analytics_type == 'user':
                return self.user.get_user_statistics(*args, **kwargs)
            elif analytics_type == 'survey':
                return self.survey.get_survey_statistics(*args, **kwargs)
            else:
                return {
                    'error': f'Analytics type "{analytics_type}" not supported',
                    'error_code': 'UNSUPPORTED_ANALYTICS_TYPE'
                }
        except Exception as e:
            self.logger.error(f"Analytics execution failed: {analytics_type}, error: {e}")
            return {
                'error': 'Analytics execution failed',
                'error_code': 'ANALYTICS_ERROR'
            }
    
    def get_dashboard_data(self, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive dashboard data."""
        try:
            # Get all analytics data
            user_stats = self.get_analytics('user', user_id=None, days=days)
            survey_stats = self.get_analytics('survey', survey_id=None, days=days)
            
            return {
                'period_days': days,
                'users': user_stats if 'error' not in user_stats else {},
                'surveys': survey_stats if 'error' not in survey_stats else {},
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting dashboard data: {e}")
            return {
                'error': 'Failed to get dashboard data',
                'error_code': 'DASHBOARD_ERROR'
            }


# Global enhanced analytics manager
enhanced_analytics_manager = EnhancedAnalyticsManager()
