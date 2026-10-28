# engagement/repositories.py
"""
Repository pattern implementation for engagement system.
Provides data access layer with business logic separation.
"""
from django.core.cache import cache
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, TypeVar, Generic
from django.db import models, transaction
from django.db.models import Q, QuerySet, Count, Sum, Avg
from django.utils import timezone
from datetime import datetime, date, timedelta

from .models.checkin import DailyCheckIn
from .models.spinwheel import SpinWheel
from .models.quest import UserQuest, Quest
from .models.achievement import UserAchievement, Achievement
from .models.shop import ShopItem, ShopPurchase
from .models.leaderboard import Leaderboard
from .models.social import FeedItem
from .models.notification import Notification
from .models.referral import Referral

T = TypeVar('T', bound=models.Model)


class BaseRepository(ABC, Generic[T]):
    """Base repository for engagement models."""
    
    def __init__(self, model_class: type[T]):
        self.model_class = model_class
        self.queryset = model_class.objects.all()
    
    @abstractmethod
    def get_by_id(self, id: int) -> Optional[T]:
        """Get model instance by ID."""
        pass
    
    @abstractmethod
    def get_all(self) -> QuerySet[T]:
        """Get all model instances."""
        pass
    
    @abstractmethod
    def create(self, **kwargs) -> T:
        """Create new model instance."""
        pass
    
    @abstractmethod
    def update(self, instance: T, **kwargs) -> T:
        """Update existing model instance."""
        pass
    
    @abstractmethod
    def delete(self, instance: T) -> bool:
        """Delete model instance."""
        pass
    
    def filter(self, **kwargs) -> QuerySet[T]:
        """Filter queryset by kwargs."""
        return self.queryset.filter(**kwargs)
    
    def exists(self, **kwargs) -> bool:
        """Check if instance exists."""
        return self.filter(**kwargs).exists()
    
    def count(self, **kwargs) -> int:
        """Count instances."""
        return self.filter(**kwargs).count()
    
    def get_or_create(self, defaults=None, **kwargs) -> tuple[T, bool]:
        """Get or create instance."""
        return self.model_class.objects.get_or_create(defaults=defaults or {}, **kwargs)


class CheckInRepository(BaseRepository[DailyCheckIn]):
    """Repository for DailyCheckIn model."""
    
    def __init__(self):
        super().__init__(DailyCheckIn)
    
    def get_by_id(self, id: int) -> Optional[DailyCheckIn]:
        """Get check-in by ID."""
        try:
            return self.queryset.get(id=id)
        except DailyCheckIn.DoesNotExist:
            return None
    
    def get_all(self) -> QuerySet[DailyCheckIn]:
        """Get all check-ins."""
        return self.queryset.select_related('user', 'tenant')
    
    def create(self, **kwargs) -> DailyCheckIn:
        """Create new check-in."""
        return self.model_class.objects.create(**kwargs)
    
    def update(self, instance: DailyCheckIn, **kwargs) -> DailyCheckIn:
        """Update check-in."""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        instance.save()
        return instance
    
    def delete(self, instance: DailyCheckIn) -> bool:
        """Delete check-in."""
        try:
            instance.delete()
            return True
        except Exception:
            return False
    
    def get_today_for_user(self, user) -> Optional[DailyCheckIn]:
        """Get today's check-in for user."""
        today = timezone.now().date()
        return self.filter(user=user, date=today).first()
    
    def get_streak_for_user(self, user) -> int:
        """Get current streak for user."""
        latest = self.filter(user=user).order_by('-date').first()
        return latest.consecutive_days if latest else 0
    
    def get_total_checkins_for_user(self, user) -> int:
        """Get total check-ins for user."""
        return self.filter(user=user).count()
    
    def get_checkins_in_period(self, start_date, end_date=None, user=None):
        """Get check-ins within a period."""
        queryset = self.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        if user:
            queryset = queryset.filter(user=user)
        return queryset.order_by('-date')
    
    def get_streak_history(self, user, days=30):
        """Get streak history for user."""
        cutoff = timezone.now().date() - timedelta(days=days)
        return self.filter(user=user, date__gte=cutoff).order_by('-date')
    
    def get_by_month(self, user=None, year=None, month=None):
        """Get check-ins by month."""
        queryset = self.filter()
        
        if user:
            queryset = queryset.filter(user=user)
        
        if year and month:
            queryset = queryset.filter(date__year=year, date__month=month)
        
        return queryset.order_by('-date')


class SpinWheelRepository(BaseRepository[SpinWheel]):
    """Repository for SpinWheel model."""
    
    def __init__(self):
        super().__init__(SpinWheel)
    
    def get_by_id(self, id: int) -> Optional[SpinWheel]:
        """Get spin by ID."""
        try:
            return self.queryset.get(id=id)
        except SpinWheel.DoesNotExist:
            return None
    
    def get_all(self) -> QuerySet[SpinWheel]:
        """Get all spins."""
        return self.queryset.select_related('user', 'tenant')
    
    def create(self, **kwargs) -> SpinWheel:
        """Create new spin."""
        return self.model_class.objects.create(**kwargs)
    
    def update(self, instance: SpinWheel, **kwargs) -> SpinWheel:
        """Update spin."""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        instance.save()
        return instance
    
    def delete(self, instance: SpinWheel) -> bool:
        """Delete spin."""
        try:
            instance.delete()
            return True
        except Exception:
            return False
    
    def get_today_for_user(self, user) -> QuerySet[SpinWheel]:
        """Get today's spins for user."""
        today = timezone.now().date()
        return self.filter(user=user, spun_at__date=today)
    
    def get_remaining_today(self, user) -> int:
        """Get remaining spins for user today."""
        from .constants import SPIN_MAX_PER_DAY
        
        today_count = self.get_today_for_user(user).count()
        return max(0, SPIN_MAX_PER_DAY - today_count)
    
    def get_total_spins_for_user(self, user) -> int:
        """Get total spins for user."""
        return self.filter(user=user).count()
    
    def get_spins_in_period(self, start_date, end_date=None, user=None):
        """Get spins within a period."""
        queryset = self.filter(spun_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(spun_at__date__lte=end_date)
        if user:
            queryset = queryset.filter(user=user)
        return queryset.order_by('-spun_at')
    
    def get_spin_history(self, user, limit=20):
        """Get spin history for user."""
        return self.filter(user=user).order_by('-spun_at')[:limit]
    
    def get_big_wins(self, min_coins=50):
        """Get spins with big wins."""
        return self.filter(coins_won__gte=min_coins).order_by('-coins_won')
    
    def get_boosted_spins(self):
        """Get boosted spins."""
        return self.filter(is_boosted=True).order_by('-spun_at')


class UserQuestRepository(BaseRepository[UserQuest]):
    """Repository for UserQuest model."""
    
    def __init__(self):
        super().__init__(UserQuest)
    
    def get_by_id(self, id: int) -> Optional[UserQuest]:
        """Get user quest by ID."""
        try:
            return self.queryset.select_related('user', 'quest', 'tenant').get(id=id)
        except UserQuest.DoesNotExist:
            return None
    
    def get_all(self) -> QuerySet[UserQuest]:
        """Get all user quests."""
        return self.queryset.select_related('user', 'quest', 'tenant')
    
    def create(self, **kwargs) -> UserQuest:
        """Create new user quest."""
        return self.model_class.objects.create(**kwargs)
    
    def update(self, instance: UserQuest, **kwargs) -> UserQuest:
        """Update user quest."""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        instance.save()
        return instance
    
    def delete(self, instance: UserQuest) -> bool:
        """Delete user quest."""
        try:
            instance.delete()
            return True
        except Exception:
            return False
    
    def get_active_for_user(self, user) -> QuerySet[UserQuest]:
        """Get active quests for user."""
        return self.filter(user=user, status__in=['available', 'active']).select_related('quest')
    
    def get_completed_for_user(self, user) -> QuerySet[UserQuest]:
        """Get completed quests for user."""
        return self.filter(user=user, status='completed').select_related('quest')
    
    def get_expiring_soon(self, user, hours=24):
        """Get quests expiring soon."""
        cutoff = timezone.now() + timedelta(hours=hours)
        return self.filter(
            user=user,
            status__in=['available', 'active'],
            expires_at__lte=cutoff,
            expires_at__gt=timezone.now()
        ).select_related('quest')
    
    def get_by_type(self, user, quest_type=None):
        """Get quests by type."""
        queryset = self.filter(user=user).select_related('quest')
        if quest_type:
            queryset = queryset.filter(quest__type=quest_type)
        return queryset
    
    def get_near_completion(self, user, threshold=0.8):
        """Get quests near completion."""
        return self.filter(
            user=user,
            status__in=['available', 'active'],
            progress__gte=models.F('quest__required_progress') * threshold
        ).select_related('quest')


class UserAchievementRepository(BaseRepository[UserAchievement]):
    """Repository for UserAchievement model."""
    
    def __init__(self):
        super().__init__(UserAchievement)
    
    def get_by_id(self, id: int) -> Optional[UserAchievement]:
        """Get user achievement by ID."""
        try:
            return self.queryset.select_related('user', 'achievement', 'tenant').get(id=id)
        except UserAchievement.DoesNotExist:
            return None
    
    def get_all(self) -> QuerySet[UserAchievement]:
        """Get all user achievements."""
        return self.queryset.select_related('user', 'achievement', 'tenant')
    
    def create(self, **kwargs) -> UserAchievement:
        """Create new user achievement."""
        return self.model_class.objects.create(**kwargs)
    
    def update(self, instance: UserAchievement, **kwargs) -> UserAchievement:
        """Update user achievement."""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        instance.save()
        return instance
    
    def delete(self, instance: UserAchievement) -> bool:
        """Delete user achievement."""
        try:
            instance.delete()
            return True
        except Exception:
            return False
    
    def get_unlocked_for_user(self, user) -> QuerySet[UserAchievement]:
        """Get unlocked achievements for user."""
        return self.filter(user=user, unlocked_at__isnull=False).select_related('achievement')
    
    def get_locked_for_user(self, user) -> QuerySet[UserAchievement]:
        """Get locked achievements for user."""
        return self.filter(user=user, unlocked_at__isnull=True).select_related('achievement')
    
    def get_progress_for_user(self, user) -> QuerySet[UserAchievement]:
        """Get achievement progress for user."""
        return self.filter(user=user).select_related('achievement').annotate(
            progress=models.Coalesce(models.F('progress'), 0),
            is_unlocked=models.Count('id', filter=models.Q(unlocked_at__isnull=False))
        )
    
    def get_by_difficulty(self, user, difficulty=None):
        """Get achievements by difficulty."""
        queryset = self.filter(user=user).select_related('achievement')
        if difficulty:
            queryset = queryset.filter(achievement__difficulty=difficulty)
        return queryset
    
    def get_recently_unlocked(self, user, days=7):
        """Get recently unlocked achievements."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.get_unlocked_for_user(user).filter(unlocked_at__gte=cutoff)


class ShopPurchaseRepository(BaseRepository[ShopPurchase]):
    """Repository for ShopPurchase model."""
    
    def __init__(self):
        super().__init__(ShopPurchase)
    
    def get_by_id(self, id: int) -> Optional[ShopPurchase]:
        """Get shop purchase by ID."""
        try:
            return self.queryset.select_related('user', 'item', 'tenant').get(id=id)
        except ShopPurchase.DoesNotExist:
            return None
    
    def get_all(self) -> QuerySet[ShopPurchase]:
        """Get all shop purchases."""
        return self.queryset.select_related('user', 'item', 'tenant')
    
    def create(self, **kwargs) -> ShopPurchase:
        """Create new shop purchase."""
        return self.model_class.objects.create(**kwargs)
    
    def update(self, instance: ShopPurchase, **kwargs) -> ShopPurchase:
        """Update shop purchase."""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        instance.save()
        return instance
    
    def delete(self, instance: ShopPurchase) -> bool:
        """Delete shop purchase."""
        try:
            instance.delete()
            return True
        except Exception:
            return False
    
    def get_for_user(self, user) -> QuerySet[ShopPurchase]:
        """Get purchases for user."""
        return self.filter(user=user).select_related('item')
    
    def get_by_status(self, status) -> QuerySet[ShopPurchase]:
        """Get purchases by status."""
        return self.filter(status=status).select_related('item')
    
    def get_by_item_type(self, item_type) -> QuerySet[ShopPurchase]:
        """Get purchases by item type."""
        return self.filter(item__type=item_type).select_related('item')
    
    def get_recent(self, days=30):
        """Get recent purchases."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(purchased_at__gte=cutoff).select_related('item')
    
    def get_by_month(self, user=None, year=None, month=None):
        """Get purchases by month."""
        queryset = self.filter()
        
        if user:
            queryset = queryset.filter(user=user)
        
        if year and month:
            queryset = queryset.filter(purchased_at__year=year, purchased_at__month=month)
        
        return queryset.order_by('-purchased_at')
    
    def get_popular_items(self, days=30, limit=10):
        """Get most popular items."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(purchased_at__gte=cutoff).values(
            'item__name', 'item__type'
        ).annotate(
            purchase_count=models.Count('id'),
            total_revenue=models.Sum('coins_spent')
        ).order_by('-purchase_count')[:limit]


class LeaderboardRepository(BaseRepository[Leaderboard]):
    """Repository for Leaderboard model."""
    
    def __init__(self):
        super().__init__(Leaderboard)
    
    def get_by_id(self, id: int) -> Optional[Leaderboard]:
        """Get leaderboard entry by ID."""
        try:
            return self.queryset.select_related('user', 'tenant').get(id=id)
        except Leaderboard.DoesNotExist:
            return None
    
    def get_all(self) -> QuerySet[Leaderboard]:
        """Get all leaderboard entries."""
        return self.queryset.select_related('user', 'tenant')
    
    def create(self, **kwargs) -> Leaderboard:
        """Create new leaderboard entry."""
        return self.model_class.objects.create(**kwargs)
    
    def update(self, instance: Leaderboard, **kwargs) -> Leaderboard:
        """Update leaderboard entry."""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        instance.save()
        return instance
    
    def delete(self, instance: Leaderboard) -> bool:
        """Delete leaderboard entry."""
        try:
            instance.delete()
            return True
        except Exception:
            return False
    
    def get_for_date(self, date) -> QuerySet[Leaderboard]:
        """Get leaderboard for specific date."""
        return self.filter(date=date).select_related('user')
    
    def get_top_players(self, date=None, limit=100):
        """Get top players for date."""
        if date is None:
            date = timezone.now().date()
        
        return self.filter(date=date).select_related('user').order_by('rank')[:limit]
    
    def get_user_rank(self, user, date=None):
        """Get user's rank for date."""
        if date is None:
            date = timezone.now().date()
        
        entry = self.filter(user=user, date=date).first()
        return entry.rank if entry else None
    
    def get_around_user(self, user, date=None, count=5):
        """Get entries around user's rank."""
        user_rank = self.get_user_rank(user, date)
        if not user_rank:
            return []
        
        start_rank = max(1, user_rank - count)
        end_rank = user_rank + count
        
        return self.filter(date=date, rank__gte=start_rank, rank__lte=end_rank).select_related('user')
    
    def get_by_period(self, start_date, end_date=None, user=None):
        """Get leaderboard entries for period."""
        queryset = self.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        if user:
            queryset = queryset.filter(user=user)
        return queryset.order_by('-date', 'rank')


class NotificationRepository(BaseRepository[Notification]):
    """Repository for Notification model."""
    
    def __init__(self):
        super().__init__(Notification)
    
    def get_by_id(self, id: int) -> Optional[Notification]:
        """Get notification by ID."""
        try:
            return self.queryset.get(id=id)
        except Notification.DoesNotExist:
            return None
    
    def get_all(self) -> QuerySet[Notification]:
        """Get all notifications."""
        return self.queryset.select_related('user', 'tenant')
    
    def create(self, **kwargs) -> Notification:
        """Create new notification."""
        return self.model_class.objects.create(**kwargs)
    
    def update(self, instance: Notification, **kwargs) -> Notification:
        """Update notification."""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        instance.save()
        return instance
    
    def delete(self, instance: Notification) -> bool:
        """Delete notification."""
        try:
            instance.delete()
            return True
        except Exception:
            return False
    
    def get_for_user(self, user) -> QuerySet[Notification]:
        """Get notifications for user."""
        return self.filter(user=user)
    
    def get_unread_for_user(self, user) -> QuerySet[Notification]:
        """Get unread notifications for user."""
        return self.filter(user=user, is_read=False)
    
    def get_by_type(self, notification_type) -> QuerySet[Notification]:
        """Get notifications by type."""
        return self.filter(type=notification_type)
    
    def get_recent(self, days=30):
        """Get recent notifications."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)
    
    def mark_as_read(self, user, notification_id=None) -> int:
        """Mark notification(s) as read."""
        queryset = self.filter(user=user, is_read=False)
        if notification_id:
            queryset = queryset.filter(id=notification_id)
        
        updated = queryset.update(is_read=True, read_at=timezone.now())
        return updated
    
    def mark_all_as_read(self, user) -> int:
        """Mark all notifications as read for user."""
        return self.mark_as_read(user)


class ReferralRepository(BaseRepository[Referral]):
    """Repository for Referral model."""
    
    def __init__(self):
        super().__init__(Referral)
    
    def get_by_id(self, id: int) -> Optional[Referral]:
        """Get referral by ID."""
        try:
            return self.queryset.select_related('referrer', 'referred', 'program', 'tenant').get(id=id)
        except Referral.DoesNotExist:
            return None
    
    def get_all(self) -> QuerySet[Referral]:
        """Get all referrals."""
        return self.queryset.select_related('referrer', 'referred', 'program', 'tenant')
    
    def create(self, **kwargs) -> Referral:
        """Create new referral."""
        return self.model_class.objects.create(**kwargs)
    
    def update(self, instance: Referral, **kwargs) -> Referral:
        """Update referral."""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        instance.save()
        return instance
    
    def delete(self, instance: Referral) -> bool:
        """Delete referral."""
        try:
            instance.delete()
            return True
        except Exception:
            return False
    
    def get_for_referrer(self, user) -> QuerySet[Referral]:
        """Get referrals made by user."""
        return self.filter(referrer=user).select_related('referred', 'program')
    
    def get_for_referred(self, user) -> QuerySet[Referral]:
        """Get referrals where user is referred."""
        return self.filter(referred=user).select_related('referrer', 'program')
    
    def get_by_status(self, status) -> QuerySet[Referral]:
        """Get referrals by status."""
        return self.filter(status=status).select_related('referrer', 'referred', 'program')
    
    def get_successful_for_user(self, user) -> QuerySet[Referral]:
        """Get successful referrals for user."""
        return self.get_for_referrer(user).filter(status__in=['confirmed', 'rewarded'])
    
    def get_by_code(self, referral_code) -> Optional[Referral]:
        """Get referral by code."""
        try:
            return self.filter(referral_code=referral_code).select_related('program').first()
        except Exception:
            return None


# ── Repository Factory ─────────────────────────────────────────────────────

class RepositoryFactory:
    """Factory for creating repository instances."""
    
    @staticmethod
    def create_repository(model_class: type[T]) -> BaseRepository[T]:
        """Create repository instance for model class."""
        repository_map = {
            DailyCheckIn: CheckInRepository,
            SpinWheel: SpinWheelRepository,
            UserQuest: UserQuestRepository,
            UserAchievement: UserAchievementRepository,
            ShopPurchase: ShopPurchaseRepository,
            Leaderboard: LeaderboardRepository,
            Notification: NotificationRepository,
            Referral: ReferralRepository,
        }
        
        repository_class = repository_map.get(model_class)
        if repository_class:
            return repository_class()
        
        raise ValueError(f"No repository found for model {model_class.__name__}")
    
    @staticmethod
    def create_checkin_repository() -> CheckInRepository:
        """Create check-in repository."""
        return CheckInRepository()
    
    @staticmethod
    def create_spin_repository() -> SpinWheelRepository:
        """Create spin repository."""
        return SpinWheelRepository()
    
    @staticmethod
    def create_quest_repository() -> UserQuestRepository:
        """Create quest repository."""
        return UserQuestRepository()
    
    @staticmethod
    def create_achievement_repository() -> UserAchievementRepository:
        """Create achievement repository."""
        return UserAchievementRepository()
    
    @staticmethod
    def create_shop_repository() -> ShopPurchaseRepository:
        """Create shop repository."""
        return ShopPurchaseRepository()
    
    @staticmethod
    def create_leaderboard_repository() -> LeaderboardRepository:
        """Create leaderboard repository."""
        return LeaderboardRepository()
    
    @staticmethod
    def create_notification_repository() -> NotificationRepository:
        """Create notification repository."""
        return NotificationRepository()
    
    @staticmethod
    def create_referral_repository() -> ReferralRepository:
        """Create referral repository."""
        return ReferralRepository()


# ── Unit of Work Pattern ─────────────────────────────────────────────────────

class UnitOfWork:
    """Unit of work pattern for transaction management."""
    
    def __init__(self):
        self.checkin_repo = RepositoryFactory.create_checkin_repository()
        self.spin_repo = RepositoryFactory.create_spin_repository()
        self.quest_repo = RepositoryFactory.create_quest_repository()
        self.achievement_repo = RepositoryFactory.create_achievement_repository()
        self.shop_repo = RepositoryFactory.create_shop_repository()
        self.leaderboard_repo = RepositoryFactory.create_leaderboard_repository()
        self.notification_repo = RepositoryFactory.create_notification_repository()
        self.referral_repo = RepositoryFactory.create_referral_repository()
        
        self._repositories = [
            self.checkin_repo,
            self.spin_repo,
            self.quest_repo,
            self.achievement_repo,
            self.shop_repo,
            self.leaderboard_repo,
            self.notification_repo,
            self.referral_repo,
        ]
    
    def __enter__(self):
        """Enter transaction context."""
        transaction.set_autocommit(False)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit transaction context."""
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        transaction.set_autocommit(True)
    
    def commit(self):
        """Commit transaction."""
        try:
            transaction.commit()
        except Exception as exc:
            self.rollback()
            raise exc
    
    def rollback(self):
        """Rollback transaction."""
        try:
            transaction.rollback()
        except Exception:
            pass  # Ignore rollback errors
    
    def get_repository(self, model_class: type[T]) -> BaseRepository[T]:
        """Get repository by model class."""
        return RepositoryFactory.create_repository(model_class)


# ── Caching Repository Decorator ─────────────────────────────────────────────

class CachedRepository:
    """Decorator for adding caching to repositories."""
    
    def __init__(self, cache_timeout=300):
        self.cache_timeout = cache_timeout
    
    def __call__(self, repository_class):
        """Wrap repository class with caching."""
        
        class CachedWrapper(repository_class):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._cache_timeout = kwargs.get('cache_timeout', self.cache_timeout)
            
            def get_by_id(self, id: int):
                cache_key = f"{self.model_class.__name__}_{id}"
                cached_result = cache.get(cache_key)
                
                if cached_result is not None:
                    return cached_result
                
                result = super().get_by_id(id)
                if result:
                    cache.set(cache_key, result, self._cache_timeout)
                
                return result
            
            def invalidate_cache(self, instance):
                """Invalidate cache for instance."""
                cache_key = f"{self.model_class.__name__}_{instance.id}"
                cache.delete(cache_key)
            
            def create(self, **kwargs):
                result = super().create(**kwargs)
                self.invalidate_cache(result)
                return result
            
            def update(self, instance, **kwargs):
                result = super().update(instance, **kwargs)
                self.invalidate_cache(result)
                return result
            
            def delete(self, instance):
                self.invalidate_cache(instance)
                return super().delete(instance)
        
        return CachedWrapper


# ── Repository Utilities ─────────────────────────────────────────────────────

class RepositoryUtils:
    """Utility functions for repositories."""
    
    @staticmethod
    def bulk_create(repository: BaseRepository, instances_data: List[Dict[str, Any]]) -> List:
        """Bulk create instances."""
        return repository.model_class.objects.bulk_create([
            repository.model_class(**data) for data in instances_data
        ])
    
    @staticmethod
    def bulk_update(repository: BaseRepository, instances: List, fields: List[str]) -> int:
        """Bulk update instances."""
        return repository.model_class.objects.bulk_update(instances, fields)
    
    @staticmethod
    def bulk_delete(repository: BaseRepository, instances: List) -> int:
        """Bulk delete instances."""
        return repository.model_class.objects.bulk_delete(instances)
    
    @staticmethod
    def get_or_create_with_defaults(repository: BaseRepository, defaults: Dict[str, Any], **kwargs):
        """Get or create instance with defaults."""
        return repository.model_class.objects.get_or_create(defaults=defaults, **kwargs)
    
    @staticmethod
    def update_or_create(repository: BaseRepository, defaults: Dict[str, Any], **kwargs):
        """Update or create instance."""
        return repository.model_class.objects.update_or_create(defaults=defaults, **kwargs)
    
    @staticmethod
    def annotate_queryset(queryset: QuerySet, **annotations):
        """Annotate queryset with additional fields."""
        return queryset.annotate(**annotations)
    
    @staticmethod
    def aggregate_queryset(queryset: QuerySet, **aggregations):
        """Aggregate queryset."""
        return queryset.aggregate(**aggregations)
    
    @staticmethod
    def paginate_queryset(queryset: QuerySet, page: int, page_size: int):
        """Paginate queryset."""
        offset = (page - 1) * page_size
        return queryset[offset:offset + page_size]
    
    @staticmethod
    def order_queryset(queryset: QuerySet, *fields):
        """Order queryset by fields."""
        return queryset.order_by(*fields)
    
    @staticmethod
    def distinct_queryset(queryset: QuerySet, *fields):
        """Get distinct values from queryset."""
        if fields:
            return queryset.order_by(*fields).distinct(*fields)
        return queryset.distinct()


# ── Advanced Repository Patterns ─────────────────────────────────────────────

class ReadOnlyRepository(BaseRepository[T]):
    """Read-only repository base class."""
    
    def create(self, **kwargs) -> T:
        """Create not allowed in read-only repository."""
        raise NotImplementedError("Create not allowed in read-only repository")
    
    def update(self, instance: T, **kwargs) -> T:
        """Update not allowed in read-only repository."""
        raise NotImplementedError("Update not allowed in read-only repository")
    
    def delete(self, instance: T) -> bool:
        """Delete not allowed in read-only repository."""
        raise NotImplementedError("Delete not allowed in read-only repository")


class TenantAwareRepository(BaseRepository[T]):
    """Tenant-aware repository base class."""
    
    def __init__(self, model_class: type[T]):
        super().__init__(model_class)
        self._tenant = None
    
    def set_tenant(self, tenant):
        """Set tenant for repository."""
        self._tenant = tenant
        self.queryset = self.model_class.objects.filter(tenant=tenant)
    
    def get_all(self) -> QuerySet[T]:
        """Get all instances for current tenant."""
        return self.queryset.filter(tenant=self._tenant)
    
    def create(self, **kwargs) -> T:
        """Create instance with tenant."""
        kwargs['tenant'] = self._tenant
        return super().create(**kwargs)


class AuditableRepository(BaseRepository[T]):
    """Auditable repository with change tracking."""
    
    def create(self, **kwargs) -> T:
        """Create instance with audit trail."""
        instance = super().create(**kwargs)
        self._log_change('CREATE', instance)
        return instance
    
    def update(self, instance: T, **kwargs) -> T:
        """Update instance with audit trail."""
        old_values = {field: getattr(instance, field) for field in instance._meta.fields}
        result = super().update(instance, **kwargs)
        self._log_change('UPDATE', instance, old_values)
        return result
    
    def delete(self, instance: T) -> bool:
        """Delete instance with audit trail."""
        self._log_change('DELETE', instance)
        return super().delete(instance)
    
    def _log_change(self, action: str, instance: T, old_values: Dict[str, Any] = None):
        """Log change to audit trail."""
        # This would integrate with your audit logging system
        pass
