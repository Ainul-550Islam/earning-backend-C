# engagement/use_cases.py
"""
Use case pattern implementation for engagement system.
Provides business logic orchestration and use case definitions.
"""
from django.utils import timezone
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging

from .selectors import SelectorFactory
from .services.checkin_service import CheckInService
from .services.spin_service import SpinService
from .services.quest_service import QuestService
from .services.achievement_service import AchievementService
from .services.shop_service import ShopService
from .services.leaderboard_service import LeaderboardService
from .services.notification_service import NotificationService
from .services.analytics_service import AnalyticsService
from .services.gamification_engine import GamificationEngine

logger = logging.getLogger(__name__)


class UseCaseResult:
    """Result object for use case execution."""
    
    def __init__(self, success: bool, data: Any = None, error: str = None, 
                 warnings: List[str] = None, metadata: Dict[str, Any] = None):
        self.success = success
        self.data = data
        self.error = error
        self.warnings = warnings or []
        self.metadata = metadata or {}
    
    def add_warning(self, warning: str):
        """Add warning to result."""
        self.warnings.append(warning)
    
    def add_metadata(self, key: str, value: Any):
        """Add metadata to result."""
        self.metadata[key] = value


class BaseUseCase(ABC):
    """Base use case class."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> UseCaseResult:
        """Execute the use case."""
        pass
    
    def log_execution(self, result: UseCaseResult, **context):
        """Log use case execution."""
        if result.success:
            self.logger.info(f"Use case {self.__class__.__name__} executed successfully")
        else:
            self.logger.error(f"Use case {self.__class__.__name__} failed: {result.error}")
        
        for warning in result.warnings:
            self.logger.warning(f"Use case warning: {warning}")


# ── Check-in Use Cases ─────────────────────────────────────────────────────

class PerformDailyCheckIn(BaseUseCase):
    """Use case for performing daily check-in."""
    
    def execute(self, user, use_shield=False, tenant=None) -> UseCaseResult:
        """Execute daily check-in use case."""
        try:
            # Validate user can check in today
            checkin_selector = SelectorFactory.create_checkin_selector()
            today_checkin = checkin_selector.today_for_user(user)
            
            if today_checkin.exists():
                return UseCaseResult(
                    success=False,
                    error="Already checked in today"
                )
            
            # Process check-in
            result = CheckInService.process(user, use_shield=use_shield, tenant=tenant)
            
            # Trigger gamification engine
            gamification_result = GamificationEngine.on_checkin(user, {
                'checkin_id': result['checkin']['id'],
                'coins_earned': result['coins_earned'],
                'xp_earned': result['xp_earned'],
                'streak': result['streak'],
                'shield_used': use_shield
            })
            
            # Record analytics
            AnalyticsService.record(
                user,
                'checkin_completed',
                coins_delta=result['coins_earned'],
                xp_delta=result['xp_earned'],
                properties={
                    'streak': result['streak'],
                    'shield_used': use_shield,
                    'bonus_claimed': result.get('bonus_claimed', False)
                },
                tenant=tenant
            )
            
            return UseCaseResult(
                success=True,
                data=result,
                metadata={
                    'gamification_result': gamification_result,
                    'analytics_recorded': True
                }
            )
            
        except Exception as exc:
            self.logger.error(f"Check-in use case failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )


class GetCheckInHistory(BaseUseCase):
    """Use case for getting check-in history."""
    
    def execute(self, user, days=30, tenant=None) -> UseCaseResult:
        """Execute get check-in history use case."""
        try:
            checkin_selector = SelectorFactory.create_checkin_selector()
            history = checkin_selector.recent_for_user(user, days)
            
            # Calculate statistics
            stats = {
                'total_checkins': history.count(),
                'current_streak': checkin_selector.streak_for_user(user),
                'longest_streak': max([c.consecutive_days for c in history]) if history.exists() else 0,
                'total_coins': sum([c.coins_earned for c in history]),
                'total_xp': sum([c.xp_earned for c in history])
            }
            
            return UseCaseResult(
                success=True,
                data={
                    'history': list(history),
                    'stats': stats
                }
            )
            
        except Exception as exc:
            self.logger.error(f"Get check-in history use case failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )


# ── Spin Wheel Use Cases ─────────────────────────────────────────────────────

class PerformSpin(BaseUseCase):
    """Use case for performing spin wheel."""
    
    def execute(self, user, use_boost=False, tenant=None) -> UseCaseResult:
        """Execute spin wheel use case."""
        try:
            # Validate user can spin
            spin_selector = SelectorFactory.create_spin_selector()
            remaining_spins = spin_selector.remaining_today(user)
            
            if remaining_spins <= 0:
                return UseCaseResult(
                    success=False,
                    error="No spins remaining today"
                )
            
            # Process spin
            result = SpinService.spin(user, use_boost=use_boost, tenant=tenant)
            
            # Trigger gamification engine
            gamification_result = GamificationEngine.on_spin(user, {
                'spin_id': result['spin']['id'],
                'coins_won': result['coins_won'],
                'xp_earned': result['xp_earned'],
                'is_boosted': use_boost
            })
            
            # Record analytics
            AnalyticsService.record(
                user,
                'spin_completed',
                coins_delta=result['coins_won'],
                xp_delta=result['xp_earned'],
                properties={
                    'is_boosted': use_boost,
                    'outcome_idx': result['spin']['outcome_idx']
                },
                tenant=tenant
            )
            
            return UseCaseResult(
                success=True,
                data=result,
                metadata={
                    'gamification_result': gamification_result,
                    'analytics_recorded': True,
                    'remaining_spins': remaining_spins - 1
                }
            )
            
        except Exception as exc:
            self.logger.error(f"Spin use case failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )


class GetSpinHistory(BaseUseCase):
    """Use case for getting spin history."""
    
    def execute(self, user, limit=20, tenant=None) -> UseCaseResult:
        """Execute get spin history use case."""
        try:
            spin_selector = SelectorFactory.create_spin_selector()
            history = spin_selector.filter(user=user).execute().order_by('-spun_at')[:limit]
            
            # Calculate statistics
            stats = {
                'total_spins': spin_selector.total_spins_for_user(user),
                'total_coins_won': sum([s.coins_won for s in history]),
                'total_xp_earned': sum([s.xp_earned for s in history]),
                'boosted_spins': len([s for s in history if s.is_boosted]),
                'big_wins': len([s for s in history if s.coins_won >= 50])
            }
            
            return UseCaseResult(
                success=True,
                data={
                    'history': list(history),
                    'stats': stats
                }
            )
            
        except Exception as exc:
            self.logger.error(f"Get spin history use case failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )


# ── Quest Use Cases ─────────────────────────────────────────────────────

class CompleteQuest(BaseUseCase):
    """Use case for completing a quest."""
    
    def execute(self, user, quest_id, progress=None, tenant=None) -> UseCaseResult:
        """Execute quest completion use case."""
        try:
            # Get quest
            quest_selector = SelectorFactory.create_quest_selector()
            user_quest = quest_selector.filter(user=user, quest__id=quest_id).execute().first()
            
            if not user_quest:
                return UseCaseResult(
                    success=False,
                    error="Quest not found"
                )
            
            # Complete quest
            result = QuestService.complete_quest(user, user_quest.quest, progress, tenant)
            
            # Trigger gamification engine
            gamification_result = GamificationEngine.on_quest_complete(user, {
                'quest_id': quest_id,
                'user_quest_id': user_quest.id,
                'progress': progress or user_quest.progress
            })
            
            # Record analytics
            AnalyticsService.record(
                user,
                'quest_completed',
                coins_delta=result.get('coins', 0),
                xp_delta=result.get('xp', 0),
                properties={
                    'quest_id': quest_id,
                    'quest_type': user_quest.quest.type,
                    'difficulty': user_quest.quest.difficulty
                },
                tenant=tenant
            )
            
            return UseCaseResult(
                success=True,
                data=result,
                metadata={
                    'gamification_result': gamification_result,
                    'analytics_recorded': True
                }
            )
            
        except Exception as exc:
            self.logger.error(f"Complete quest use case failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )


class GetAvailableQuests(BaseUseCase):
    """Use case for getting available quests."""
    
    def execute(self, user, quest_type='daily', tenant=None) -> UseCaseResult:
        """Execute get available quests use case."""
        try:
            quests = QuestService.get_available_quests(user, quest_type, tenant)
            
            # Get user quest progress
            quest_selector = SelectorFactory.create_quest_selector()
            user_quests = quest_selector.active_for_user(user)
            
            # Combine quest data with progress
            quest_data = []
            for quest in quests:
                user_quest = user_quests.filter(quest=quest).first()
                quest_data.append({
                    'quest': quest,
                    'user_quest': user_quest,
                    'progress': user_quest.progress if user_quest else 0,
                    'required_progress': quest.required_progress,
                    'is_completed': user_quest.status == 'completed' if user_quest else False
                })
            
            return UseCaseResult(
                success=True,
                data={
                    'quests': quest_data,
                    'quest_type': quest_type
                }
            )
            
        except Exception as exc:
            self.logger.error(f"Get available quests use case failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )


# ── Achievement Use Cases ─────────────────────────────────────────────────────

class GetAchievementProgress(BaseUseCase):
    """Use case for getting achievement progress."""
    
    def execute(self, user, achievement_id=None, tenant=None) -> UseCaseResult:
        """Execute get achievement progress use case."""
        try:
            achievement_selector = SelectorFactory.create_achievement_selector()
            
            if achievement_id:
                # Get specific achievement progress
                progress = achievement_selector.filter(user=user, achievement__id=achievement_id).execute().first()
                
                if not progress:
                    return UseCaseResult(
                        success=False,
                        error="Achievement not found"
                    )
                
                return UseCaseResult(
                    success=True,
                    data={
                        'achievement': progress.achievement,
                        'progress': progress.progress,
                        'required_progress': 100,
                        'is_unlocked': progress.unlocked_at is not None,
                        'unlocked_at': progress.unlocked_at
                    }
                )
            else:
                # Get all achievement progress
                progress_list = achievement_selector.progress_for_user(user)
                
                return UseCaseResult(
                    success=True,
                    data={
                        'achievements': list(progress_list),
                        'total_achievements': progress_list.count(),
                        'unlocked_count': progress_list.filter(unlocked_at__isnull=False).count()
                    }
                )
            
        except Exception as exc:
            self.logger.error(f"Get achievement progress use case failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )


class UnlockAchievement(BaseUseCase):
    """Use case for unlocking achievement."""
    
    def execute(self, user, achievement_id, tenant=None) -> UseCaseResult:
        """Execute unlock achievement use case."""
        try:
            # Get achievement
            achievement_selector = SelectorFactory.create_achievement_selector()
            user_achievement = achievement_selector.filter(
                user=user, 
                achievement__id=achievement_id
            ).execute().first()
            
            if not user_achievement:
                return UseCaseResult(
                    success=False,
                    error="Achievement not found"
                )
            
            if user_achievement.unlocked_at:
                return UseCaseResult(
                    success=False,
                    error="Achievement already unlocked"
                )
            
            # Unlock achievement
            user_achievement.progress = 100
            user_achievement.unlocked_at = timezone.now()
            user_achievement.save()
            
            # Trigger gamification engine
            gamification_result = GamificationEngine.on_achievement_unlock(user, {
                'achievement_id': achievement_id,
                'user_achievement_id': user_achievement.id
            })
            
            # Record analytics
            AnalyticsService.record(
                user,
                'achievement_unlocked',
                coins_delta=user_achievement.achievement.coin_reward,
                xp_delta=user_achievement.achievement.xp_reward,
                properties={
                    'achievement_id': achievement_id,
                    'achievement_type': user_achievement.achievement.type,
                    'difficulty': user_achievement.achievement.difficulty
                },
                tenant=tenant
            )
            
            return UseCaseResult(
                success=True,
                data={
                    'achievement': user_achievement.achievement,
                    'unlocked_at': user_achievement.unlocked_at
                },
                metadata={
                    'gamification_result': gamification_result,
                    'analytics_recorded': True
                }
            )
            
        except Exception as exc:
            self.logger.error(f"Unlock achievement use case failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )


# ── Shop Use Cases ─────────────────────────────────────────────────────

class PurchaseShopItem(BaseUseCase):
    """Use case for purchasing shop item."""
    
    def execute(self, user, item_id, quantity=1, tenant=None) -> UseCaseResult:
        """Execute purchase shop item use case."""
        try:
            # Get item
            from .models.shop import ShopItem
            item = ShopItem.objects.get(id=item_id)
            
            # Validate purchase
            if not item.is_active:
                return UseCaseResult(
                    success=False,
                    error="Item is not available"
                )
            
            # Check user balance (mock - in real implementation, this would check user's coins)
            # For now, assume user has enough coins
            
            # Process purchase
            result = ShopService.purchase(user, item, quantity, tenant)
            
            # Trigger gamification engine
            gamification_result = GamificationEngine.on_purchase(user, {
                'item_id': item_id,
                'quantity': quantity,
                'coins_spent': result['coins_spent']
            })
            
            # Record analytics
            AnalyticsService.record(
                user,
                'shop_purchase',
                coins_delta=-result['coins_spent'],
                properties={
                    'item_id': item_id,
                    'item_type': item.type,
                    'quantity': quantity
                },
                tenant=tenant
            )
            
            return UseCaseResult(
                success=True,
                data=result,
                metadata={
                    'gamification_result': gamification_result,
                    'analytics_recorded': True
                }
            )
            
        except Exception as exc:
            self.logger.error(f"Purchase shop item use case failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )


class GetUserInventory(BaseUseCase):
    """Use case for getting user inventory."""
    
    def execute(self, user, tenant=None) -> UseCaseResult:
        """Execute get user inventory use case."""
        try:
            inventory = ShopService.get_inventory(user, tenant)
            
            # Calculate inventory statistics
            stats = {
                'total_items': len(inventory),
                'total_quantity': sum([item['quantity'] for item in inventory]),
                'unique_item_types': len(set([item['item_type'] for item in inventory]))
            }
            
            return UseCaseResult(
                success=True,
                data={
                    'inventory': inventory,
                    'stats': stats
                }
            )
            
        except Exception as exc:
            self.logger.error(f"Get user inventory use case failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )


# ── Leaderboard Use Cases ─────────────────────────────────────────────────────

class GetLeaderboard(BaseUseCase):
    """Use case for getting leaderboard data."""
    
    def execute(self, user=None, period='daily', limit=100, tenant=None) -> UseCaseResult:
        """Execute get leaderboard use case."""
        try:
            leaderboard_selector = SelectorFactory.create_leaderboard_selector()
            
            # Get top players
            top_players = leaderboard_selector.top_players(limit=limit, tenant=tenant)
            
            # Get user rank if user provided
            user_rank = None
            around_user = []
            if user:
                user_rank = leaderboard_selector.user_rank(user, tenant=tenant)
                around_user = leaderboard_selector.around_user(user, count=5, tenant=tenant)
            
            return UseCaseResult(
                success=True,
                data={
                    'leaderboard': list(top_players),
                    'user_rank': user_rank,
                    'around_user': list(around_user),
                    'period': period
                }
            )
            
        except Exception as exc:
            self.logger.error(f"Get leaderboard use case failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )


class GetUserRank(BaseUseCase):
    """Use case for getting user's rank."""
    
    def execute(self, user, period='daily', tenant=None) -> UseCaseResult:
        """Execute get user rank use case."""
        try:
            leaderboard_selector = SelectorFactory.create_leaderboard_selector()
            rank = leaderboard_selector.user_rank(user, tenant=tenant)
            
            # Get rank statistics
            total_players = leaderboard_selector.filter(tenant=tenant).count()
            percentile = (total_players - rank) / total_players * 100 if rank and total_players > 0 else 0
            
            return UseCaseResult(
                success=True,
                data={
                    'rank': rank,
                    'total_players': total_players,
                    'percentile': round(percentile, 2),
                    'period': period
                }
            )
            
        except Exception as exc:
            self.logger.error(f"Get user rank use case failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )


# ── Notification Use Cases ─────────────────────────────────────────────────────

class SendNotification(BaseUseCase):
    """Use case for sending notification."""
    
    def execute(self, user, notification_type, title, body, data=None, tenant=None) -> UseCaseResult:
        """Execute send notification use case."""
        try:
            # Send notification
            NotificationService.send(
                user,
                notification_type,
                title,
                body,
                data=data or {},
                tenant=tenant
            )
            
            # Record analytics
            AnalyticsService.record(
                user,
                'notification_sent',
                properties={
                    'notification_type': notification_type,
                    'title': title
                },
                tenant=tenant
            )
            
            return UseCaseResult(
                success=True,
                data={
                    'notification_type': notification_type,
                    'title': title,
                    'sent_at': timezone.now()
                },
                metadata={
                    'analytics_recorded': True
                }
            )
            
        except Exception as exc:
            self.logger.error(f"Send notification use case failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )


class GetUserNotifications(BaseUseCase):
    """Use case for getting user notifications."""
    
    def execute(self, user, unread_only=False, limit=20, tenant=None) -> UseCaseResult:
        """Execute get user notifications use case."""
        try:
            notification_selector = SelectorFactory.create_notification_selector()
            
            if unread_only:
                notifications = notification_selector.unread_for_user(user)[:limit]
            else:
                notifications = notification_selector.for_user(user)[:limit]
            
            # Calculate notification statistics
            unread_count = notification_selector.unread_for_user(user).count()
            total_count = notification_selector.for_user(user).count()
            
            return UseCaseResult(
                success=True,
                data={
                    'notifications': list(notifications),
                    'unread_count': unread_count,
                    'total_count': total_count,
                    'unread_only': unread_only
                }
            )
            
        except Exception as exc:
            self.logger.error(f"Get user notifications use case failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )


# ── Profile Use Cases ─────────────────────────────────────────────────────

class GetUserProfile(BaseUseCase):
    """Use case for getting user profile."""
    
    def execute(self, user, tenant=None) -> UseCaseResult:
        """Execute get user profile use case."""
        try:
            # Get user statistics
            stats = AnalyticsService.get_user_stats(user, tenant)
            
            # Get recent activity
            recent_activity = self._get_recent_activity(user, tenant)
            
            # Get achievements
            achievement_selector = SelectorFactory.create_achievement_selector()
            achievements = achievement_selector.unlocked_for_user(user)[:5]
            
            # Get active quests
            quest_selector = SelectorFactory.create_quest_selector()
            active_quests = quest_selector.active_for_user(user)[:5]
            
            # Get notifications
            notification_selector = SelectorFactory.create_notification_selector()
            unread_notifications = notification_selector.unread_for_user(user).count()
            
            profile_data = {
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'date_joined': user.date_joined.isoformat(),
                    'has_premium': getattr(user, 'has_premium', False),
                    'level': stats.get('level', 1),
                    'total_xp': stats.get('total_xp', 0),
                    'total_coins': stats.get('total_coins', 0)
                },
                'stats': stats,
                'achievements': list(achievements),
                'active_quests': list(active_quests),
                'recent_activity': recent_activity,
                'unread_notifications': unread_notifications
            }
            
            return UseCaseResult(
                success=True,
                data=profile_data
            )
            
        except Exception as exc:
            self.logger.error(f"Get user profile use case failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )
    
    def _get_recent_activity(self, user, tenant=None, limit=10):
        """Get recent user activity."""
        try:
            activities = []
            
            # Get recent check-ins
            checkin_selector = SelectorFactory.create_checkin_selector()
            recent_checkins = checkin_selector.recent_for_user(user, days=7)[:5]
            
            for checkin in recent_checkins:
                activities.append({
                    'type': 'checkin',
                    'date': checkin.date.isoformat(),
                    'data': {
                        'coins_earned': float(checkin.coins_earned),
                        'xp_earned': checkin.xp_earned,
                        'streak': checkin.consecutive_days
                    }
                })
            
            # Get recent spins
            spin_selector = SelectorFactory.create_spin_selector()
            recent_spins = spin_selector.filter(user=user).execute().order_by('-spun_at')[:5]
            
            for spin in recent_spins:
                activities.append({
                    'type': 'spin',
                    'date': spin.spun_at.isoformat(),
                    'data': {
                        'coins_won': float(spin.coins_won),
                        'xp_earned': spin.xp_earned,
                        'is_boosted': spin.is_boosted
                    }
                })
            
            # Sort by date and limit
            activities.sort(key=lambda x: x['date'], reverse=True)
            return activities[:limit]
            
        except Exception as exc:
            self.logger.error(f"Failed to get recent activity: {exc}")
            return []


# ── Use Case Factory ─────────────────────────────────────────────────────

class UseCaseFactory:
    """Factory for creating use case instances."""
    
    @staticmethod
    def create_use_case(use_case_name: str):
        """Create use case instance by name."""
        use_cases = {
            'perform_daily_checkin': PerformDailyCheckIn,
            'get_checkin_history': GetCheckInHistory,
            'perform_spin': PerformSpin,
            'get_spin_history': GetSpinHistory,
            'complete_quest': CompleteQuest,
            'get_available_quests': GetAvailableQuests,
            'get_achievement_progress': GetAchievementProgress,
            'unlock_achievement': UnlockAchievement,
            'purchase_shop_item': PurchaseShopItem,
            'get_user_inventory': GetUserInventory,
            'get_leaderboard': GetLeaderboard,
            'get_user_rank': GetUserRank,
            'send_notification': SendNotification,
            'get_user_notifications': GetUserNotifications,
            'get_user_profile': GetUserProfile,
        }
        
        use_case_class = use_cases.get(use_case_name)
        if use_case_class:
            return use_case_class()
        
        raise ValueError(f"Unknown use case: {use_case_name}")
    
    @staticmethod
    def list_use_cases():
        """List all available use cases."""
        return [
            'perform_daily_checkin',
            'get_checkin_history',
            'perform_spin',
            'get_spin_history',
            'complete_quest',
            'get_available_quests',
            'get_achievement_progress',
            'unlock_achievement',
            'purchase_shop_item',
            'get_user_inventory',
            'get_leaderboard',
            'get_user_rank',
            'send_notification',
            'get_user_notifications',
            'get_user_profile',
        ]


# ── Use Case Executor ─────────────────────────────────────────────────────

class UseCaseExecutor:
    """Executor for running use cases with error handling and logging."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def execute(self, use_case_name: str, *args, **kwargs) -> UseCaseResult:
        """Execute use case with error handling."""
        try:
            use_case = UseCaseFactory.create_use_case(use_case_name)
            result = use_case.execute(*args, **kwargs)
            
            # Log execution
            use_case.log_execution(result, use_case_name=use_case_name, args=args, kwargs=kwargs)
            
            return result
            
        except Exception as exc:
            self.logger.error(f"Use case execution failed: {exc}")
            return UseCaseResult(
                success=False,
                error=f"Use case execution failed: {str(exc)}"
            )
    
    def execute_batch(self, use_cases: List[Dict[str, Any]]) -> Dict[str, UseCaseResult]:
        """Execute multiple use cases."""
        results = {}
        
        for use_case_config in use_cases:
            name = use_case_config['name']
            args = use_case_config.get('args', [])
            kwargs = use_case_config.get('kwargs', {})
            
            results[name] = self.execute(name, *args, **kwargs)
        
        return results
    
    def execute_with_fallback(self, primary_use_case: str, fallback_use_case: str, 
                            *args, **kwargs) -> UseCaseResult:
        """Execute use case with fallback on failure."""
        result = self.execute(primary_use_case, *args, **kwargs)
        
        if not result.success:
            self.logger.warning(f"Primary use case {primary_use_case} failed, trying fallback {fallback_use_case}")
            result = self.execute(fallback_use_case, *args, **kwargs)
        
        return result


# ── Use Case Orchestration ─────────────────────────────────────────────────────

class EngagementOrchestrator:
    """Orchestrator for complex engagement workflows."""
    
    def __init__(self):
        self.executor = UseCaseExecutor()
    
    def complete_user_onboarding(self, user, tenant=None) -> UseCaseResult:
        """Complete user onboarding workflow."""
        try:
            # Send welcome notification
            notification_result = self.executor.execute(
                'send_notification',
                user=user,
                notification_type='welcome',
                title='Welcome to Engagement!',
                body='Get started with your first check-in and spin!',
                tenant=tenant
            )
            
            # Get available quests
            quests_result = self.executor.execute(
                'get_available_quests',
                user=user,
                tenant=tenant
            )
            
            # Get user profile
            profile_result = self.executor.execute(
                'get_user_profile',
                user=user,
                tenant=tenant
            )
            
            return UseCaseResult(
                success=True,
                data={
                    'notification': notification_result.data,
                    'quests': quests_result.data,
                    'profile': profile_result.data
                },
                metadata={
                    'onboarding_completed': True
                }
            )
            
        except Exception as exc:
            self.logger.error(f"User onboarding failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )
    
    def process_daily_engagement(self, user, tenant=None) -> UseCaseResult:
        """Process daily engagement workflow."""
        try:
            # Check if user has already checked in today
            checkin_result = self.executor.execute('perform_daily_checkin', user=user, tenant=tenant)
            
            # Get user's current stats
            profile_result = self.executor.execute('get_user_profile', user=user, tenant=tenant)
            
            # Get available quests
            quests_result = self.executor.execute('get_available_quests', user=user, tenant=tenant)
            
            # Get leaderboard position
            rank_result = self.executor.execute('get_user_rank', user=user, tenant=tenant)
            
            return UseCaseResult(
                success=True,
                data={
                    'checkin': checkin_result.data if checkin_result.success else None,
                    'profile': profile_result.data,
                    'quests': quests_result.data,
                    'rank': rank_result.data
                },
                metadata={
                    'daily_engagement_processed': True,
                    'checkin_completed': checkin_result.success
                }
            )
            
        except Exception as exc:
            self.logger.error(f"Daily engagement processing failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )
    
    def generate_user_digest(self, user, period='weekly', tenant=None) -> UseCaseResult:
        """Generate user engagement digest."""
        try:
            # Get user profile
            profile_result = self.executor.execute('get_user_profile', user=user, tenant=tenant)
            
            # Get check-in history
            days = 7 if period == 'weekly' else 30
            checkin_result = self.executor.execute('get_checkin_history', user=user, days=days, tenant=tenant)
            
            # Get spin history
            spin_result = self.executor.execute('get_spin_history', user=user, limit=20, tenant=tenant)
            
            # Get achievement progress
            achievement_result = self.executor.execute('get_achievement_progress', user=user, tenant=tenant)
            
            # Get leaderboard rank
            rank_result = self.executor.execute('get_user_rank', user=user, tenant=tenant)
            
            return UseCaseResult(
                success=True,
                data={
                    'profile': profile_result.data,
                    'checkin_history': checkin_result.data,
                    'spin_history': spin_result.data,
                    'achievements': achievement_result.data,
                    'rank': rank_result.data,
                    'period': period
                },
                metadata={
                    'digest_generated': True
                }
            )
            
        except Exception as exc:
            self.logger.error(f"User digest generation failed: {exc}")
            return UseCaseResult(
                success=False,
                error=str(exc)
            )
