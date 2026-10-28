# engagement/analytics.py
"""
Analytics system for engagement gamification.
Provides data collection, analysis, and reporting capabilities.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime, timedelta

from django.db import models
from django.db.models import Count, Sum, Avg, Q, F, Window
from django.db.models.functions import TruncDate, TruncHour, TruncDay, TruncWeek, TruncMonth
from django.utils import timezone
from django.core.cache import cache

from .models.checkin import DailyCheckIn
from .models.spinwheel import SpinWheel
from .models.quest import UserQuest, Quest
from .models.achievement import UserAchievement, Achievement
from .models.shop import ShopPurchase
from .models.leaderboard import Leaderboard

logger = logging.getLogger(__name__)


class AnalyticsPeriod(Enum):
    """Analytics time periods."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class MetricCategory(Enum):
    """Categories of analytics metrics."""
    ENGAGEMENT = "engagement"
    RETENTION = "retention"
    MONETIZATION = "monetization"
    PERFORMANCE = "performance"
    SOCIAL = "social"
    GAMIFICATION = "gamification"


@dataclass
class AnalyticsMetric:
    """Analytics metric data structure."""
    name: str
    value: Union[int, float, str]
    category: MetricCategory
    period: AnalyticsPeriod
    timestamp: datetime = field(default_factory=timezone.now)
    dimensions: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserAnalytics:
    """User-specific analytics data."""
    user_id: int
    total_checkins: int = 0
    total_spins: int = 0
    total_quests_completed: int = 0
    total_achievements_unlocked: int = 0
    total_coins_earned: int = 0
    total_coins_spent: int = 0
    total_xp_earned: int = 0
    current_level: int = 1
    current_streak: int = 0
    longest_streak: int = 0
    last_activity: Optional[datetime] = None
    activity_days: int = 0
    avg_daily_engagement: float = 0.0


@dataclass
class EngagementAnalytics:
    """Engagement analytics data."""
    period: AnalyticsPeriod
    total_users: int = 0
    active_users: int = 0
    new_users: int = 0
    returning_users: int = 0
    total_checkins: int = 0
    total_spins: int = 0
    total_quests_completed: int = 0
    total_achievements_unlocked: int = 0
    total_coins_earned: int = 0
    total_coins_spent: int = 0
    avg_session_duration: float = 0.0
    retention_rate: float = 0.0
    churn_rate: float = 0.0


class BaseAnalyticsEngine(ABC):
    """Base analytics engine class."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def calculate_metrics(self, period: AnalyticsPeriod, start_date: datetime, 
                         end_date: datetime, dimensions: Dict[str, Any] = None) -> List[AnalyticsMetric]:
        """Calculate analytics metrics."""
        pass


class UserAnalyticsEngine(BaseAnalyticsEngine):
    """Analytics engine for user-specific data."""
    
    def calculate_metrics(self, period: AnalyticsPeriod, start_date: datetime, 
                         end_date: datetime, dimensions: Dict[str, Any] = None) -> List[AnalyticsMetric]:
        """Calculate user analytics metrics."""
        metrics = []
        
        try:
            # Get user-specific metrics
            user_ids = dimensions.get('user_ids') if dimensions else None
            
            if user_ids:
                user_metrics = self._calculate_user_metrics_batch(user_ids, start_date, end_date)
            else:
                user_metrics = self._calculate_all_user_metrics(start_date, end_date)
            
            for user_analytics in user_metrics:
                # Convert to AnalyticsMetric objects
                metrics.extend(self._user_analytics_to_metrics(user_analytics, period))
        
        except Exception as exc:
            self.logger.error(f"Failed to calculate user analytics: {exc}")
        
        return metrics
    
    def _calculate_user_metrics_batch(self, user_ids: List[int], start_date: datetime, 
                                     end_date: datetime) -> List[UserAnalytics]:
        """Calculate metrics for specific users."""
        user_metrics = []
        
        for user_id in user_ids:
            user_analytics = self._calculate_single_user_metrics(user_id, start_date, end_date)
            user_metrics.append(user_analytics)
        
        return user_metrics
    
    def _calculate_all_user_metrics(self, start_date: datetime, 
                                   end_date: datetime) -> List[UserAnalytics]:
        """Calculate metrics for all users."""
        user_metrics = []
        
        # Get all users who had activity in the period
        active_users = set()
        
        # From check-ins
        checkin_users = DailyCheckIn.objects.filter(
            date__gte=start_date.date(),
            date__lte=end_date.date()
        ).values_list('user_id', flat=True)
        active_users.update(checkin_users)
        
        # From spins
        spin_users = SpinWheel.objects.filter(
            spun_at__gte=start_date,
            spun_at__lte=end_date
        ).values_list('user_id', flat=True)
        active_users.update(spin_users)
        
        # From quests
        quest_users = UserQuest.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        ).values_list('user_id', flat=True)
        active_users.update(quest_users)
        
        for user_id in active_users:
            user_analytics = self._calculate_single_user_metrics(user_id, start_date, end_date)
            user_metrics.append(user_analytics)
        
        return user_metrics
    
    def _calculate_single_user_metrics(self, user_id: int, start_date: datetime, 
                                      end_date: datetime) -> UserAnalytics:
        """Calculate metrics for a single user."""
        user_analytics = UserAnalytics(user_id=user_id)
        
        # Check-ins
        checkins = DailyCheckIn.objects.filter(
            user_id=user_id,
            date__gte=start_date.date(),
            date__lte=end_date.date()
        )
        
        user_analytics.total_checkins = checkins.count()
        user_analytics.current_streak = self._get_current_streak(user_id)
        user_analytics.longest_streak = checkins.aggregate(
            longest_streak=models.Max('consecutive_days')
        )['longest_streak'] or 0
        
        # Spins
        spins = SpinWheel.objects.filter(
            user_id=user_id,
            spun_at__gte=start_date,
            spun_at__lte=end_date
        )
        user_analytics.total_spins = spins.count()
        
        # Quests
        completed_quests = UserQuest.objects.filter(
            user_id=user_id,
            status='completed',
            completed_at__gte=start_date,
            completed_at__lte=end_date
        )
        user_analytics.total_quests_completed = completed_quests.count()
        
        # Achievements
        unlocked_achievements = UserAchievement.objects.filter(
            user_id=user_id,
            unlocked_at__gte=start_date,
            unlocked_at__lte=end_date
        )
        user_analytics.total_achievements_unlocked = unlocked_achievements.count()
        
        # Coins
        user_analytics.total_coins_earned = checkins.aggregate(
            total=Sum('coins_earned')
        )['total'] or 0
        
        user_analytics.total_coins_earned += spins.aggregate(
            total=Sum('coins_won')
        )['total'] or 0
        
        user_analytics.total_coins_spent = ShopPurchase.objects.filter(
            user_id=user_id,
            purchased_at__gte=start_date,
            purchased_at__lte=end_date
        ).aggregate(total=Sum('coins_spent'))['total'] or 0
        
        # XP
        user_analytics.total_xp_earned = checkins.aggregate(
            total=Sum('xp_earned')
        )['total'] or 0
        
        user_analytics.total_xp_earned += spins.aggregate(
            total=Sum('xp_earned')
        )['total'] or 0
        
        # Activity days
        activity_dates = set()
        activity_dates.update(checkins.values_list('date', flat=True))
        activity_dates.update(spins.values_list('spun_at__date', flat=True))
        user_analytics.activity_days = len(activity_dates)
        
        # Average daily engagement
        period_days = (end_date - start_date).days + 1
        user_analytics.avg_daily_engagement = user_analytics.activity_days / period_days
        
        # Last activity
        last_checkin = checkins.order_by('-date').first()
        last_spin = spins.order_by('-spun_at').first()
        
        if last_checkin and last_spin:
            user_analytics.last_activity = max(
                datetime.combine(last_checkin.date, datetime.min.time()),
                last_spin.spun_at
            )
        elif last_checkin:
            user_analytics.last_activity = datetime.combine(last_checkin.date, datetime.min.time())
        elif last_spin:
            user_analytics.last_activity = last_spin.spun_at
        
        return user_analytics
    
    def _get_current_streak(self, user_id: int) -> int:
        """Get current streak for user."""
        latest_checkin = DailyCheckIn.objects.filter(
            user_id=user_id
        ).order_by('-date').first()
        
        return latest_checkin.consecutive_days if latest_checkin else 0
    
    def _user_analytics_to_metrics(self, user_analytics: UserAnalytics, 
                                  period: AnalyticsPeriod) -> List[AnalyticsMetric]:
        """Convert UserAnalytics to AnalyticsMetric objects."""
        metrics = []
        
        # Create metrics for each user attribute
        metric_mappings = [
            ('total_checkins', MetricCategory.ENGAGEMENT),
            ('total_spins', MetricCategory.ENGAGEMENT),
            ('total_quests_completed', MetricCategory.GAMIFICATION),
            ('total_achievements_unlocked', MetricCategory.GAMIFICATION),
            ('total_coins_earned', MetricCategory.MONETIZATION),
            ('total_coins_spent', MetricCategory.MONETIZATION),
            ('total_xp_earned', MetricCategory.GAMIFICATION),
            ('current_streak', MetricCategory.ENGAGEMENT),
            ('longest_streak', MetricCategory.ENGAGEMENT),
            ('activity_days', MetricCategory.ENGAGEMENT),
            ('avg_daily_engagement', MetricCategory.ENGAGEMENT),
        ]
        
        for attr_name, category in metric_mappings:
            value = getattr(user_analytics, attr_name)
            metrics.append(AnalyticsMetric(
                name=f"user_{attr_name}",
                value=value,
                category=category,
                period=period,
                dimensions={'user_id': user_analytics.user_id}
            ))
        
        return metrics


class EngagementAnalyticsEngine(BaseAnalyticsEngine):
    """Analytics engine for engagement data."""
    
    def calculate_metrics(self, period: AnalyticsPeriod, start_date: datetime, 
                         end_date: datetime, dimensions: Dict[str, Any] = None) -> List[AnalyticsMetric]:
        """Calculate engagement analytics metrics."""
        metrics = []
        
        try:
            # Calculate overall engagement metrics
            engagement_analytics = self._calculate_engagement_analytics(start_date, end_date)
            
            # Convert to AnalyticsMetric objects
            metrics.extend(self._engagement_analytics_to_metrics(engagement_analytics, period))
            
            # Calculate additional engagement metrics
            additional_metrics = self._calculate_additional_engagement_metrics(start_date, end_date, period)
            metrics.extend(additional_metrics)
            
        except Exception as exc:
            self.logger.error(f"Failed to calculate engagement analytics: {exc}")
        
        return metrics
    
    def _calculate_engagement_analytics(self, start_date: datetime, 
                                      end_date: datetime) -> EngagementAnalytics:
        """Calculate engagement analytics."""
        engagement_analytics = EngagementAnalytics(period=AnalyticsPeriod.DAILY)
        
        # Get date range
        date_range = [start_date.date() + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
        
        # Total users (unique users in period)
        user_ids = set()
        user_ids.update(DailyCheckIn.objects.filter(date__in=date_range).values_list('user_id', flat=True))
        user_ids.update(SpinWheel.objects.filter(spun_at__date__in=date_range).values_list('user_id', flat=True))
        user_ids.update(UserQuest.objects.filter(created_at__date__in=date_range).values_list('user_id', flat=True))
        
        engagement_analytics.total_users = len(user_ids)
        
        # Active users (users with activity in period)
        engagement_analytics.active_users = engagement_analytics.total_users
        
        # New users (users who joined in period)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        engagement_analytics.new_users = User.objects.filter(
            date_joined__date__in=date_range
        ).count()
        
        # Returning users (users who were active before period)
        period_start = start_date.date()
        returning_users = DailyCheckIn.objects.filter(
            date__lt=period_start,
            user_id__in=user_ids
        ).values_list('user_id', flat=True).distinct()
        
        engagement_analytics.returning_users = len(set(returning_users))
        
        # Total check-ins
        engagement_analytics.total_checkins = DailyCheckIn.objects.filter(
            date__in=date_range
        ).count()
        
        # Total spins
        engagement_analytics.total_spins = SpinWheel.objects.filter(
            spun_at__date__in=date_range
        ).count()
        
        # Total quests completed
        engagement_analytics.total_quests_completed = UserQuest.objects.filter(
            status='completed',
            completed_at__date__in=date_range
        ).count()
        
        # Total achievements unlocked
        engagement_analytics.total_achievements_unlocked = UserAchievement.objects.filter(
            unlocked_at__date__in=date_range
        ).count()
        
        # Total coins earned
        engagement_analytics.total_coins_earned = (
            DailyCheckIn.objects.filter(date__in=date_range).aggregate(
                total=Sum('coins_earned')
            )['total'] or 0
        )
        
        engagement_analytics.total_coins_earned += SpinWheel.objects.filter(
            spun_at__date__in=date_range
        ).aggregate(total=Sum('coins_won'))['total'] or 0
        
        # Total coins spent
        engagement_analytics.total_coins_spent = ShopPurchase.objects.filter(
            purchased_at__date__in=date_range
        ).aggregate(total=Sum('coins_spent'))['total'] or 0
        
        # Average session duration (mock calculation)
        engagement_analytics.avg_session_duration = 15.5  # Mock value
        
        # Retention rate
        if engagement_analytics.active_users > 0:
            engagement_analytics.retention_rate = engagement_analytics.returning_users / engagement_analytics.active_users * 100
        else:
            engagement_analytics.retention_rate = 0.0
        
        # Churn rate (mock calculation)
        engagement_analytics.churn_rate = 5.2  # Mock value
        
        return engagement_analytics
    
    def _engagement_analytics_to_metrics(self, engagement_analytics: EngagementAnalytics, 
                                       period: AnalyticsPeriod) -> List[AnalyticsMetric]:
        """Convert EngagementAnalytics to AnalyticsMetric objects."""
        metrics = []
        
        metric_mappings = [
            ('total_users', MetricCategory.ENGAGEMENT),
            ('active_users', MetricCategory.ENGAGEMENT),
            ('new_users', MetricCategory.ENGAGEMENT),
            ('returning_users', MetricCategory.RETENTION),
            ('total_checkins', MetricCategory.ENGAGEMENT),
            ('total_spins', MetricCategory.ENGAGEMENT),
            ('total_quests_completed', MetricCategory.GAMIFICATION),
            ('total_achievements_unlocked', MetricCategory.GAMIFICATION),
            ('total_coins_earned', MetricCategory.MONETIZATION),
            ('total_coins_spent', MetricCategory.MONETIZATION),
            ('avg_session_duration', MetricCategory.PERFORMANCE),
            ('retention_rate', MetricCategory.RETENTION),
            ('churn_rate', MetricCategory.RETENTION),
        ]
        
        for attr_name, category in metric_mappings:
            value = getattr(engagement_analytics, attr_name)
            metrics.append(AnalyticsMetric(
                name=f"engagement_{attr_name}",
                value=value,
                category=category,
                period=period
            ))
        
        return metrics
    
    def _calculate_additional_engagement_metrics(self, start_date: datetime, 
                                              end_date: datetime, period: AnalyticsPeriod) -> List[AnalyticsMetric]:
        """Calculate additional engagement metrics."""
        metrics = []
        
        # Daily engagement trends
        daily_metrics = self._calculate_daily_trends(start_date, end_date)
        metrics.extend(daily_metrics)
        
        # Feature usage metrics
        feature_metrics = self._calculate_feature_usage(start_date, end_date)
        metrics.extend(feature_metrics)
        
        # User lifecycle metrics
        lifecycle_metrics = self._calculate_lifecycle_metrics(start_date, end_date)
        metrics.extend(lifecycle_metrics)
        
        return metrics
    
    def _calculate_daily_trends(self, start_date: datetime, end_date: datetime) -> List[AnalyticsMetric]:
        """Calculate daily engagement trends."""
        metrics = []
        
        # Group by date
        date_range = [start_date.date() + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
        
        for date in date_range:
            # Daily check-ins
            daily_checkins = DailyCheckIn.objects.filter(date=date).count()
            metrics.append(AnalyticsMetric(
                name="daily_checkins",
                value=daily_checkins,
                category=MetricCategory.ENGAGEMENT,
                period=AnalyticsPeriod.DAILY,
                dimensions={'date': date.isoformat()}
            ))
            
            # Daily active users
            daily_active_users = DailyCheckIn.objects.filter(date=date).values('user_id').distinct().count()
            metrics.append(AnalyticsMetric(
                name="daily_active_users",
                value=daily_active_users,
                category=MetricCategory.ENGAGEMENT,
                period=AnalyticsPeriod.DAILY,
                dimensions={'date': date.isoformat()}
            ))
            
            # Daily spins
            daily_spins = SpinWheel.objects.filter(spun_at__date=date).count()
            metrics.append(AnalyticsMetric(
                name="daily_spins",
                value=daily_spins,
                category=MetricCategory.ENGAGEMENT,
                period=AnalyticsPeriod.DAILY,
                dimensions={'date': date.isoformat()}
            ))
        
        return metrics
    
    def _calculate_feature_usage(self, start_date: datetime, end_date: datetime) -> List[AnalyticsMetric]:
        """Calculate feature usage metrics."""
        metrics = []
        
        date_range = [start_date.date() + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
        
        # Check-in feature usage
        total_checkins = DailyCheckIn.objects.filter(date__in=date_range).count()
        metrics.append(AnalyticsMetric(
            name="feature_usage_checkin",
            value=total_checkins,
            category=MetricCategory.ENGAGEMENT,
            period=AnalyticsPeriod.DAILY,
            dimensions={'feature': 'checkin'}
        ))
        
        # Spin wheel feature usage
        total_spins = SpinWheel.objects.filter(spun_at__date__in=date_range).count()
        metrics.append(AnalyticsMetric(
            name="feature_usage_spin",
            value=total_spins,
            category=MetricCategory.ENGAGEMENT,
            period=AnalyticsPeriod.DAILY,
            dimensions={'feature': 'spin'}
        ))
        
        # Quest feature usage
        total_quests = UserQuest.objects.filter(created_at__date__in=date_range).count()
        metrics.append(AnalyticsMetric(
            name="feature_usage_quest",
            value=total_quests,
            category=MetricCategory.GAMIFICATION,
            period=AnalyticsPeriod.DAILY,
            dimensions={'feature': 'quest'}
        ))
        
        return metrics
    
    def _calculate_lifecycle_metrics(self, start_date: datetime, end_date: datetime) -> List[AnalyticsMetric]:
        """Calculate user lifecycle metrics."""
        metrics = []
        
        # User acquisition
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        date_range = [start_date.date() + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
        
        for date in date_range:
            new_users = User.objects.filter(date_joined__date=date).count()
            metrics.append(AnalyticsMetric(
                name="user_acquisition",
                value=new_users,
                category=MetricCategory.RETENTION,
                period=AnalyticsPeriod.DAILY,
                dimensions={'date': date.isoformat()}
            ))
        
        # User retention by cohort
        retention_data = self._calculate_cohort_retention(start_date, end_date)
        for cohort_date, retention_rate in retention_data.items():
            metrics.append(AnalyticsMetric(
                name="cohort_retention",
                value=retention_rate,
                category=MetricCategory.RETENTION,
                period=AnalyticsPeriod.WEEKLY,
                dimensions={'cohort_date': cohort_date.isoformat()}
            ))
        
        return metrics
    
    def _calculate_cohort_retention(self, start_date: datetime, end_date: datetime) -> Dict[datetime.date, float]:
        """Calculate cohort retention rates."""
        cohort_retention = {}
        
        # Get weekly cohorts
        week_start = start_date.date()
        while week_start <= end_date.date():
            # Users who joined this week
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            week_end = week_start + timedelta(days=6)
            cohort_users = User.objects.filter(
                date_joined__date__gte=week_start,
                date_joined__date__lte=week_end
            ).values_list('id', flat=True)
            
            if cohort_users:
                # Check if they were active in the following week
                following_week_start = week_end + timedelta(days=1)
                following_week_end = following_week_start + timedelta(days=6)
                
                active_users = DailyCheckIn.objects.filter(
                    user_id__in=cohort_users,
                    date__gte=following_week_start,
                    date__lte=following_week_end
                ).values('user_id').distinct().count()
                
                retention_rate = active_users / len(cohort_users) * 100
                cohort_retention[week_start] = retention_rate
            
            week_start += timedelta(days=7)
        
        return cohort_retention


class MonetizationAnalyticsEngine(BaseAnalyticsEngine):
    """Analytics engine for monetization data."""
    
    def calculate_metrics(self, period: AnalyticsPeriod, start_date: datetime, 
                         end_date: datetime, dimensions: Dict[str, Any] = None) -> List[AnalyticsMetric]:
        """Calculate monetization analytics metrics."""
        metrics = []
        
        try:
            # Revenue metrics
            revenue_metrics = self._calculate_revenue_metrics(start_date, end_date, period)
            metrics.extend(revenue_metrics)
            
            # Purchase metrics
            purchase_metrics = self._calculate_purchase_metrics(start_date, end_date, period)
            metrics.extend(purchase_metrics)
            
            # Shop performance metrics
            shop_metrics = self._calculate_shop_performance(start_date, end_date, period)
            metrics.extend(shop_metrics)
            
        except Exception as exc:
            self.logger.error(f"Failed to calculate monetization analytics: {exc}")
        
        return metrics
    
    def _calculate_revenue_metrics(self, start_date: datetime, end_date: datetime, 
                                  period: AnalyticsPeriod) -> List[AnalyticsMetric]:
        """Calculate revenue metrics."""
        metrics = []
        
        # Total revenue
        total_revenue = ShopPurchase.objects.filter(
            purchased_at__gte=start_date,
            purchased_at__lte=end_date
        ).aggregate(total=Sum('coins_spent'))['total'] or 0
        
        metrics.append(AnalyticsMetric(
            name="total_revenue",
            value=total_revenue,
            category=MetricCategory.MONETIZATION,
            period=period
        ))
        
        # Average revenue per user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        active_users = DailyCheckIn.objects.filter(
            date__gte=start_date.date(),
            date__lte=end_date.date()
        ).values('user_id').distinct().count()
        
        if active_users > 0:
            arpu = total_revenue / active_users
            metrics.append(AnalyticsMetric(
                name="average_revenue_per_user",
                value=arpu,
                category=MetricCategory.MONETIZATION,
                period=period
            ))
        
        # Revenue trends
        date_range = [start_date.date() + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
        
        for date in date_range:
            daily_revenue = ShopPurchase.objects.filter(
                purchased_at__date=date
            ).aggregate(total=Sum('coins_spent'))['total'] or 0
            
            metrics.append(AnalyticsMetric(
                name="daily_revenue",
                value=daily_revenue,
                category=MetricCategory.MONETIZATION,
                period=AnalyticsPeriod.DAILY,
                dimensions={'date': date.isoformat()}
            ))
        
        return metrics
    
    def _calculate_purchase_metrics(self, start_date: datetime, end_date: datetime, 
                                   period: AnalyticsPeriod) -> List[AnalyticsMetric]:
        """Calculate purchase metrics."""
        metrics = []
        
        # Total purchases
        total_purchases = ShopPurchase.objects.filter(
            purchased_at__gte=start_date,
            purchased_at__lte=end_date
        ).count()
        
        metrics.append(AnalyticsMetric(
            name="total_purchases",
            value=total_purchases,
            category=MetricCategory.MONETIZATION,
            period=period
        ))
        
        # Average purchase value
        avg_purchase_value = ShopPurchase.objects.filter(
            purchased_at__gte=start_date,
            purchased_at__lte=end_date
        ).aggregate(avg=Avg('coins_spent'))['avg'] or 0
        
        metrics.append(AnalyticsMetric(
            name="average_purchase_value",
            value=avg_purchase_value,
            category=MetricCategory.MONETIZATION,
            period=period
        ))
        
        # Purchase frequency
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        active_users = DailyCheckIn.objects.filter(
            date__gte=start_date.date(),
            date__lte=end_date.date()
        ).values('user_id').distinct().count()
        
        if active_users > 0:
            purchase_frequency = total_purchases / active_users
            metrics.append(AnalyticsMetric(
                name="purchase_frequency",
                value=purchase_frequency,
                category=MetricCategory.MONETIZATION,
                period=period
            ))
        
        return metrics
    
    def _calculate_shop_performance(self, start_date: datetime, end_date: datetime, 
                                   period: AnalyticsPeriod) -> List[AnalyticsMetric]:
        """Calculate shop performance metrics."""
        metrics = []
        
        # Top selling items
        top_items = ShopPurchase.objects.filter(
            purchased_at__gte=start_date,
            purchased_at__lte=end_date
        ).values('item__name', 'item__type').annotate(
            total_revenue=Sum('coins_spent'),
            total_quantity=Sum('quantity')
        ).order_by('-total_revenue')[:10]
        
        for item in top_items:
            metrics.append(AnalyticsMetric(
                name="item_revenue",
                value=item['total_revenue'],
                category=MetricCategory.MONETIZATION,
                period=period,
                dimensions={
                    'item_name': item['item__name'],
                    'item_type': item['item__type']
                }
            ))
            
            metrics.append(AnalyticsMetric(
                name="item_quantity_sold",
                value=item['total_quantity'],
                category=MetricCategory.MONETIZATION,
                period=period,
                dimensions={
                    'item_name': item['item__name'],
                    'item_type': item['item__type']
                }
            ))
        
        return metrics


class AnalyticsManager:
    """Manager for all analytics operations."""
    
    def __init__(self):
        self.engines = {
            MetricCategory.ENGAGEMENT: EngagementAnalyticsEngine(),
            MetricCategory.USER: UserAnalyticsEngine(),
            MetricCategory.MONETIZATION: MonetizationAnalyticsEngine(),
        }
        self.metrics_cache = {}
        self.cache_timeout = 300  # 5 minutes
    
    def calculate_metrics(self, categories: List[MetricCategory] = None, 
                         period: AnalyticsPeriod = AnalyticsPeriod.DAILY,
                         start_date: datetime = None, end_date: datetime = None,
                         dimensions: Dict[str, Any] = None) -> List[AnalyticsMetric]:
        """Calculate analytics metrics."""
        if start_date is None:
            start_date = timezone.now() - timedelta(days=7)
        if end_date is None:
            end_date = timezone.now()
        
        if categories is None:
            categories = list(self.engines.keys())
        
        all_metrics = []
        
        for category in categories:
            engine = self.engines.get(category)
            if engine:
                try:
                    metrics = engine.calculate_metrics(period, start_date, end_date, dimensions)
                    all_metrics.extend(metrics)
                except Exception as exc:
                    logger.error(f"Failed to calculate metrics for category {category}: {exc}")
        
        return all_metrics
    
    def get_user_analytics(self, user_id: int, days: int = 30) -> UserAnalytics:
        """Get analytics for a specific user."""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        engine = self.engines[MetricCategory.USER]
        user_metrics = engine.calculate_metrics(
            AnalyticsPeriod.DAILY, start_date, end_date,
            dimensions={'user_ids': [user_id]}
        )
        
        # Convert back to UserAnalytics
        user_analytics = UserAnalytics(user_id=user_id)
        
        for metric in user_metrics:
            if metric.name == "user_total_checkins":
                user_analytics.total_checkins = metric.value
            elif metric.name == "user_total_spins":
                user_analytics.total_spins = metric.value
            elif metric.name == "user_total_quests_completed":
                user_analytics.total_quests_completed = metric.value
            elif metric.name == "user_total_achievements_unlocked":
                user_analytics.total_achievements_unlocked = metric.value
            elif metric.name == "user_total_coins_earned":
                user_analytics.total_coins_earned = metric.value
            elif metric.name == "user_total_coins_spent":
                user_analytics.total_coins_spent = metric.value
            elif metric.name == "user_total_xp_earned":
                user_analytics.total_xp_earned = metric.value
            elif metric.name == "user_current_streak":
                user_analytics.current_streak = metric.value
            elif metric.name == "user_longest_streak":
                user_analytics.longest_streak = metric.value
            elif metric.name == "user_activity_days":
                user_analytics.activity_days = metric.value
            elif metric.name == "user_avg_daily_engagement":
                user_analytics.avg_daily_engagement = metric.value
        
        return user_analytics
    
    def get_dashboard_data(self, period: AnalyticsPeriod = AnalyticsPeriod.DAILY, 
                          days: int = 7) -> Dict[str, Any]:
        """Get dashboard analytics data."""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Calculate all metrics
        metrics = self.calculate_metrics(
            period=period,
            start_date=start_date,
            end_date=end_date
        )
        
        # Organize metrics by category
        dashboard_data = {
            'period': period.value,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'metrics': {}
        }
        
        for metric in metrics:
            category = metric.category.value
            if category not in dashboard_data['metrics']:
                dashboard_data['metrics'][category] = []
            
            dashboard_data['metrics'][category].append({
                'name': metric.name,
                'value': metric.value,
                'dimensions': metric.dimensions,
                'timestamp': metric.timestamp.isoformat()
            })
        
        return dashboard_data
    
    def export_metrics(self, format: str = 'json', **kwargs) -> str:
        """Export metrics in specified format."""
        metrics = self.calculate_metrics(**kwargs)
        
        if format.lower() == 'json':
            import json
            return json.dumps([
                {
                    'name': m.name,
                    'value': m.value,
                    'category': m.category.value,
                    'period': m.period.value,
                    'timestamp': m.timestamp.isoformat(),
                    'dimensions': m.dimensions,
                    'metadata': m.metadata
                }
                for m in metrics
            ], indent=2)
        elif format.lower() == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['name', 'value', 'category', 'period', 'timestamp', 'dimensions', 'metadata'])
            
            # Write data
            for m in metrics:
                writer.writerow([
                    m.name,
                    m.value,
                    m.category.value,
                    m.period.value,
                    m.timestamp.isoformat(),
                    str(m.dimensions),
                    str(m.metadata)
                ])
            
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format}")


# Global analytics manager instance
analytics_manager = AnalyticsManager()
