# engagement/interactors.py
"""
Interactor pattern implementation for engagement system.
Provides use case coordination and business logic orchestration.
"""
from django.utils import timezone
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging

from .repositories import RepositoryFactory, UnitOfWork
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


class InteractorResult:
    """Result object for interactor execution."""
    
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


class BaseInteractor(ABC):
    """Base interactor class."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.uow = UnitOfWork()
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> InteractorResult:
        """Execute the interactor."""
        pass
    
    def log_execution(self, result: InteractorResult, **context):
        """Log interactor execution."""
        if result.success:
            self.logger.info(f"Interactor {self.__class__.__name__} executed successfully")
        else:
            self.logger.error(f"Interactor {self.__class__.__name__} failed: {result.error}")
        
        for warning in result.warnings:
            self.logger.warning(f"Interactor warning: {warning}")


# ── Check-in Interactors ─────────────────────────────────────────────────────

class CheckInInteractor(BaseInteractor):
    """Interactor for check-in operations."""
    
    def execute(self, user, use_shield=False, tenant=None) -> InteractorResult:
        """Execute check-in interactor."""
        try:
            with self.uow:
                # Validate user can check in today
                today_checkin = self.uow.checkin_repo.get_today_for_user(user)
                
                if today_checkin:
                    return InteractorResult(
                        success=False,
                        error="Already checked in today"
                    )
                
                # Process check-in
                result = CheckInService.process(user, use_shield=use_shield, tenant=tenant)
                
                # Create check-in record
                checkin = self.uow.checkin_repo.create(
                    user=user,
                    date=timezone.now().date(),
                    coins_earned=result['coins_earned'],
                    xp_earned=result['xp_earned'],
                    consecutive_days=result['streak'],
                    streak_shield_used=use_shield,
                    tenant=tenant
                )
                
                # Trigger gamification engine
                gamification_result = GamificationEngine.on_checkin(user, {
                    'checkin_id': checkin.id,
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
                
                # Send notification for milestone streaks
                if result['streak'] in [7, 14, 30, 50, 100]:
                    NotificationService.send(
                        user,
                        'streak_milestone',
                        title=f"🔥 {result['streak']}-Day Streak!",
                        body=f"Congratulations on your {result['streak']}-day streak!",
                        data={'streak': result['streak']},
                        tenant=tenant
                    )
                
                self.uow.commit()
                
                return InteractorResult(
                    success=True,
                    data=result,
                    metadata={
                        'checkin_id': checkin.id,
                        'gamification_result': gamification_result,
                        'analytics_recorded': True
                    }
                )
                
        except Exception as exc:
            self.logger.error(f"Check-in interactor failed: {exc}")
            self.uow.rollback()
            return InteractorResult(
                success=False,
                error=str(exc)
            )


class GetCheckInHistoryInteractor(BaseInteractor):
    """Interactor for getting check-in history."""
    
    def execute(self, user, days=30, tenant=None) -> InteractorResult:
        """Execute get check-in history interactor."""
        try:
            with self.uow:
                # Get check-in history
                history = self.uow.checkin_repo.get_streak_history(user, days)
                
                # Calculate statistics
                stats = {
                    'total_checkins': self.uow.checkin_repo.get_total_checkins_for_user(user),
                    'current_streak': self.uow.checkin_repo.get_streak_for_user(user),
                    'longest_streak': max([c.consecutive_days for c in history]) if history.exists() else 0,
                    'total_coins': sum([c.coins_earned for c in history]),
                    'total_xp': sum([c.xp_earned for c in history])
                }
                
                return InteractorResult(
                    success=True,
                    data={
                        'history': list(history),
                        'stats': stats
                    }
                )
                
        except Exception as exc:
            self.logger.error(f"Get check-in history interactor failed: {exc}")
            return InteractorResult(
                success=False,
                error=str(exc)
            )


# ── Spin Wheel Interactors ─────────────────────────────────────────────────────

class SpinInteractor(BaseInteractor):
    """Interactor for spin wheel operations."""
    
    def execute(self, user, use_boost=False, tenant=None) -> InteractorResult:
        """Execute spin interactor."""
        try:
            with self.uow:
                # Validate user can spin
                remaining_spins = self.uow.spin_repo.get_remaining_today(user)
                
                if remaining_spins <= 0:
                    return InteractorResult(
                        success=False,
                        error="No spins remaining today"
                    )
                
                # Process spin
                result = SpinService.spin(user, use_boost=use_boost, tenant=tenant)
                
                # Create spin record
                spin = self.uow.spin_repo.create(
                    user=user,
                    spun_at=timezone.now(),
                    coins_won=result['coins_won'],
                    xp_earned=result['xp_earned'],
                    outcome_idx=result['spin']['outcome_idx'],
                    is_boosted=use_boost,
                    tenant=tenant
                )
                
                # Trigger gamification engine
                gamification_result = GamificationEngine.on_spin(user, {
                    'spin_id': spin.id,
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
                
                # Send notification for big wins
                if result['coins_won'] >= 50:
                    NotificationService.send(
                        user,
                        'big_win',
                        title=f"🎉 Big Win!",
                        body=f"You won {result['coins_won']} coins!",
                        data={'coins_won': result['coins_won']},
                        tenant=tenant
                    )
                
                self.uow.commit()
                
                return InteractorResult(
                    success=True,
                    data=result,
                    metadata={
                        'spin_id': spin.id,
                        'remaining_spins': remaining_spins - 1,
                        'gamification_result': gamification_result,
                        'analytics_recorded': True
                    }
                )
                
        except Exception as exc:
            self.logger.error(f"Spin interactor failed: {exc}")
            self.uow.rollback()
            return InteractorResult(
                success=False,
                error=str(exc)
            )


class GetSpinHistoryInteractor(BaseInteractor):
    """Interactor for getting spin history."""
    
    def execute(self, user, limit=20, tenant=None) -> InteractorResult:
        """Execute get spin history interactor."""
        try:
            with self.uow:
                # Get spin history
                history = self.uow.spin_repo.get_spin_history(user, limit)
                
                # Calculate statistics
                stats = {
                    'total_spins': self.uow.spin_repo.get_total_spins_for_user(user),
                    'total_coins_won': sum([s.coins_won for s in history]),
                    'total_xp_earned': sum([s.xp_earned for s in history]),
                    'boosted_spins': len([s for s in history if s.is_boosted]),
                    'big_wins': len([s for s in history if s.coins_won >= 50])
                }
                
                return InteractorResult(
                    success=True,
                    data={
                        'history': list(history),
                        'stats': stats
                    }
                )
                
        except Exception as exc:
            self.logger.error(f"Get spin history interactor failed: {exc}")
            return InteractorResult(
                success=False,
                error=str(exc)
            )


# ── Quest Interactors ─────────────────────────────────────────────────────

class CompleteQuestInteractor(BaseInteractor):
    """Interactor for completing quests."""
    
    def execute(self, user, quest_id, progress=None, tenant=None) -> InteractorResult:
        """Execute quest completion interactor."""
        try:
            with self.uow:
                # Get user quest
                user_quest = self.uow.quest_repo.filter(user=user, quest__id=quest_id).first()
                
                if not user_quest:
                    return InteractorResult(
                        success=False,
                        error="Quest not found"
                    )
                
                # Complete quest
                result = QuestService.complete_quest(user, user_quest.quest, progress, tenant)
                
                # Update user quest
                self.uow.quest_repo.update(
                    user_quest,
                    status='completed',
                    progress=progress or user_quest.quest.required_progress,
                    completed_at=timezone.now()
                )
                
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
                
                # Send notification
                NotificationService.send(
                    user,
                    'quest_completed',
                    title=f"✅ Quest Completed!",
                    body=f"You've completed: {user_quest.quest.name}",
                    data={'quest_id': quest_id, 'quest_name': user_quest.quest.name},
                    tenant=tenant
                )
                
                self.uow.commit()
                
                return InteractorResult(
                    success=True,
                    data=result,
                    metadata={
                        'user_quest_id': user_quest.id,
                        'gamification_result': gamification_result,
                        'analytics_recorded': True
                    }
                )
                
        except Exception as exc:
            self.logger.error(f"Complete quest interactor failed: {exc}")
            self.uow.rollback()
            return InteractorResult(
                success=False,
                error=str(exc)
            )


class GetAvailableQuestsInteractor(BaseInteractor):
    """Interactor for getting available quests."""
    
    def execute(self, user, quest_type='daily', tenant=None) -> InteractorResult:
        """Execute get available quests interactor."""
        try:
            with self.uow:
                # Get available quests
                quests = QuestService.get_available_quests(user, quest_type, tenant)
                
                # Get user quest progress
                user_quests = self.uow.quest_repo.get_active_for_user(user)
                
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
                
                return InteractorResult(
                    success=True,
                    data={
                        'quests': quest_data,
                        'quest_type': quest_type
                    }
                )
                
        except Exception as exc:
            self.logger.error(f"Get available quests interactor failed: {exc}")
            return InteractorResult(
                success=False,
                error=str(exc)
            )


# ── Achievement Interactors ─────────────────────────────────────────────────────

class UnlockAchievementInteractor(BaseInteractor):
    """Interactor for unlocking achievements."""
    
    def execute(self, user, achievement_id, tenant=None) -> InteractorResult:
        """Execute unlock achievement interactor."""
        try:
            with self.uow:
                # Get user achievement
                user_achievement = self.uow.achievement_repo.filter(
                    user=user, 
                    achievement__id=achievement_id
                ).first()
                
                if not user_achievement:
                    return InteractorResult(
                        success=False,
                        error="Achievement not found"
                    )
                
                if user_achievement.unlocked_at:
                    return InteractorResult(
                        success=False,
                        error="Achievement already unlocked"
                    )
                
                # Unlock achievement
                self.uow.achievement_repo.update(
                    user_achievement,
                    progress=100,
                    unlocked_at=timezone.now()
                )
                
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
                
                # Send notification
                NotificationService.send(
                    user,
                    'achievement_unlocked',
                    title=f"🏆 Achievement Unlocked!",
                    body=f"You've unlocked: {user_achievement.achievement.name}",
                    data={
                        'achievement_id': achievement_id,
                        'achievement_name': user_achievement.achievement.name
                    },
                    tenant=tenant
                )
                
                self.uow.commit()
                
                return InteractorResult(
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
            self.logger.error(f"Unlock achievement interactor failed: {exc}")
            self.uow.rollback()
            return InteractorResult(
                success=False,
                error=str(exc)
            )


class GetAchievementProgressInteractor(BaseInteractor):
    """Interactor for getting achievement progress."""
    
    def execute(self, user, achievement_id=None, tenant=None) -> InteractorResult:
        """Execute get achievement progress interactor."""
        try:
            with self.uow:
                if achievement_id:
                    # Get specific achievement progress
                    progress = self.uow.achievement_repo.filter(
                        user=user, 
                        achievement__id=achievement_id
                    ).first()
                    
                    if not progress:
                        return InteractorResult(
                            success=False,
                            error="Achievement not found"
                        )
                    
                    return InteractorResult(
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
                    progress_list = self.uow.achievement_repo.get_progress_for_user(user)
                    
                    return InteractorResult(
                        success=True,
                        data={
                            'achievements': list(progress_list),
                            'total_achievements': progress_list.count(),
                            'unlocked_count': progress_list.filter(unlocked_at__isnull=False).count()
                        }
                    )
                
        except Exception as exc:
            self.logger.error(f"Get achievement progress interactor failed: {exc}")
            return InteractorResult(
                success=False,
                error=str(exc)
            )


# ── Shop Interactors ─────────────────────────────────────────────────────

class PurchaseItemInteractor(BaseInteractor):
    """Interactor for purchasing shop items."""
    
    def execute(self, user, item_id, quantity=1, tenant=None) -> InteractorResult:
        """Execute purchase item interactor."""
        try:
            with self.uow:
                # Get item
                from .models.shop import ShopItem
                item = ShopItem.objects.get(id=item_id)
                
                # Validate purchase
                if not item.is_active:
                    return InteractorResult(
                        success=False,
                        error="Item is not available"
                    )
                
                # Check user balance (mock - in real implementation, this would check user's coins)
                # For now, assume user has enough coins
                
                # Process purchase
                result = ShopService.purchase(user, item, quantity, tenant)
                
                # Create purchase record
                purchase = self.uow.shop_repo.create(
                    user=user,
                    item=item,
                    quantity=quantity,
                    coins_spent=result['coins_spent'],
                    status='completed',
                    purchased_at=timezone.now(),
                    tenant=tenant
                )
                
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
                
                # Send notification
                NotificationService.send(
                    user,
                    'purchase_completed',
                    title=f"🛍️ Purchase Completed!",
                    body=f"You've purchased: {item.name}",
                    data={'item_id': item_id, 'item_name': item.name},
                    tenant=tenant
                )
                
                self.uow.commit()
                
                return InteractorResult(
                    success=True,
                    data=result,
                    metadata={
                        'purchase_id': purchase.id,
                        'gamification_result': gamification_result,
                        'analytics_recorded': True
                    }
                )
                
        except Exception as exc:
            self.logger.error(f"Purchase item interactor failed: {exc}")
            self.uow.rollback()
            return InteractorResult(
                success=False,
                error=str(exc)
            )


class GetUserInventoryInteractor(BaseInteractor):
    """Interactor for getting user inventory."""
    
    def execute(self, user, tenant=None) -> InteractorResult:
        """Execute get user inventory interactor."""
        try:
            with self.uow:
                # Get inventory
                inventory = ShopService.get_inventory(user, tenant)
                
                # Calculate inventory statistics
                stats = {
                    'total_items': len(inventory),
                    'total_quantity': sum([item['quantity'] for item in inventory]),
                    'unique_item_types': len(set([item['item_type'] for item in inventory]))
                }
                
                return InteractorResult(
                    success=True,
                    data={
                        'inventory': inventory,
                        'stats': stats
                    }
                )
                
        except Exception as exc:
            self.logger.error(f"Get user inventory interactor failed: {exc}")
            return InteractorResult(
                success=False,
                error=str(exc)
            )


# ── Leaderboard Interactors ─────────────────────────────────────────────────────

class GetLeaderboardInteractor(BaseInteractor):
    """Interactor for getting leaderboard data."""
    
    def execute(self, user=None, period='daily', limit=100, tenant=None) -> InteractorResult:
        """Execute get leaderboard interactor."""
        try:
            with self.uow:
                # Get top players
                top_players = self.uow.leaderboard_repo.get_top_players(limit=limit)
                
                # Get user rank if user provided
                user_rank = None
                around_user = []
                if user:
                    user_rank = self.uow.leaderboard_repo.get_user_rank(user)
                    around_user = self.uow.leaderboard_repo.get_around_user(user, count=5)
                
                return InteractorResult(
                    success=True,
                    data={
                        'leaderboard': list(top_players),
                        'user_rank': user_rank,
                        'around_user': list(around_user),
                        'period': period
                    }
                )
                
        except Exception as exc:
            self.logger.error(f"Get leaderboard interactor failed: {exc}")
            return InteractorResult(
                success=False,
                error=str(exc)
            )


class GetUserRankInteractor(BaseInteractor):
    """Interactor for getting user's rank."""
    
    def execute(self, user, period='daily', tenant=None) -> InteractorResult:
        """Execute get user rank interactor."""
        try:
            with self.uow:
                # Get user rank
                rank = self.uow.leaderboard_repo.get_user_rank(user)
                
                # Get rank statistics
                total_players = self.uow.leaderboard_repo.count()
                percentile = (total_players - rank) / total_players * 100 if rank and total_players > 0 else 0
                
                return InteractorResult(
                    success=True,
                    data={
                        'rank': rank,
                        'total_players': total_players,
                        'percentile': round(percentile, 2),
                        'period': period
                    }
                )
                
        except Exception as exc:
            self.logger.error(f"Get user rank interactor failed: {exc}")
            return InteractorResult(
                success=False,
                error=str(exc)
            )


# ── Notification Interactors ─────────────────────────────────────────────────────

class SendNotificationInteractor(BaseInteractor):
    """Interactor for sending notifications."""
    
    def execute(self, user, notification_type, title, body, data=None, tenant=None) -> InteractorResult:
        """Execute send notification interactor."""
        try:
            with self.uow:
                # Send notification
                notification = self.uow.notification_repo.create(
                    user=user,
                    type=notification_type,
                    title=title,
                    body=body,
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
                
                self.uow.commit()
                
                return InteractorResult(
                    success=True,
                    data={
                        'notification_id': notification.id,
                        'notification_type': notification_type,
                        'title': title,
                        'sent_at': notification.created_at
                    },
                    metadata={
                        'analytics_recorded': True
                    }
                )
                
        except Exception as exc:
            self.logger.error(f"Send notification interactor failed: {exc}")
            self.uow.rollback()
            return InteractorResult(
                success=False,
                error=str(exc)
            )


class GetUserNotificationsInteractor(BaseInteractor):
    """Interactor for getting user notifications."""
    
    def execute(self, user, unread_only=False, limit=20, tenant=None) -> InteractorResult:
        """Execute get user notifications interactor."""
        try:
            with self.uow:
                # Get notifications
                if unread_only:
                    notifications = self.uow.notification_repo.get_unread_for_user(user)[:limit]
                else:
                    notifications = self.uow.notification_repo.get_for_user(user)[:limit]
                
                # Calculate notification statistics
                unread_count = self.uow.notification_repo.get_unread_for_user(user).count()
                total_count = self.uow.notification_repo.get_for_user(user).count()
                
                return InteractorResult(
                    success=True,
                    data={
                        'notifications': list(notifications),
                        'unread_count': unread_count,
                        'total_count': total_count,
                        'unread_only': unread_only
                    }
                )
                
        except Exception as exc:
            self.logger.error(f"Get user notifications interactor failed: {exc}")
            return InteractorResult(
                success=False,
                error=str(exc)
            )


# ── Profile Interactors ─────────────────────────────────────────────────────

class GetUserProfileInteractor(BaseInteractor):
    """Interactor for getting user profile."""
    
    def execute(self, user, tenant=None) -> InteractorResult:
        """Execute get user profile interactor."""
        try:
            with self.uow:
                # Get user statistics
                stats = AnalyticsService.get_user_stats(user, tenant)
                
                # Get recent activity
                recent_activity = self._get_recent_activity(user, tenant)
                
                # Get achievements
                achievements = self.uow.achievement_repo.get_unlocked_for_user(user)[:5]
                
                # Get active quests
                active_quests = self.uow.quest_repo.get_active_for_user(user)[:5]
                
                # Get notifications
                unread_notifications = self.uow.notification_repo.get_unread_for_user(user).count()
                
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
                
                return InteractorResult(
                    success=True,
                    data=profile_data
                )
                
        except Exception as exc:
            self.logger.error(f"Get user profile interactor failed: {exc}")
            return InteractorResult(
                success=False,
                error=str(exc)
            )
    
    def _get_recent_activity(self, user, tenant=None, limit=10):
        """Get recent user activity."""
        try:
            activities = []
            
            # Get recent check-ins
            recent_checkins = self.uow.checkin_repo.get_streak_history(user, days=7)[:5]
            
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
            recent_spins = self.uow.spin_repo.filter(user=user).order_by('-spun_at')[:5]
            
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


# ── Interactor Factory ─────────────────────────────────────────────────────

class InteractorFactory:
    """Factory for creating interactor instances."""
    
    @staticmethod
    def create_interactor(interactor_name: str):
        """Create interactor instance by name."""
        interactors = {
            'checkin': CheckInInteractor,
            'get_checkin_history': GetCheckInHistoryInteractor,
            'spin': SpinInteractor,
            'get_spin_history': GetSpinHistoryInteractor,
            'complete_quest': CompleteQuestInteractor,
            'get_available_quests': GetAvailableQuestsInteractor,
            'unlock_achievement': UnlockAchievementInteractor,
            'get_achievement_progress': GetAchievementProgressInteractor,
            'purchase_item': PurchaseItemInteractor,
            'get_user_inventory': GetUserInventoryInteractor,
            'get_leaderboard': GetLeaderboardInteractor,
            'get_user_rank': GetUserRankInteractor,
            'send_notification': SendNotificationInteractor,
            'get_user_notifications': GetUserNotificationsInteractor,
            'get_user_profile': GetUserProfileInteractor,
        }
        
        interactor_class = interactors.get(interactor_name)
        if interactor_class:
            return interactor_class()
        
        raise ValueError(f"Unknown interactor: {interactor_name}")
    
    @staticmethod
    def list_interactors():
        """List all available interactors."""
        return [
            'checkin',
            'get_checkin_history',
            'spin',
            'get_spin_history',
            'complete_quest',
            'get_available_quests',
            'unlock_achievement',
            'get_achievement_progress',
            'purchase_item',
            'get_user_inventory',
            'get_leaderboard',
            'get_user_rank',
            'send_notification',
            'get_user_notifications',
            'get_user_profile',
        ]


# ── Interactor Orchestrator ─────────────────────────────────────────────────────

class EngagementOrchestrator:
    """Orchestrator for complex engagement workflows using interactors."""
    
    def __init__(self):
        self.interactor_factory = InteractorFactory()
    
    def complete_user_onboarding(self, user, tenant=None) -> InteractorResult:
        """Complete user onboarding workflow."""
        try:
            # Send welcome notification
            notification_interactor = self.interactor_factory.create_interactor('send_notification')
            notification_result = notification_interactor.execute(
                user=user,
                notification_type='welcome',
                title='Welcome to Engagement!',
                body='Get started with your first check-in and spin!',
                tenant=tenant
            )
            
            # Get available quests
            quest_interactor = self.interactor_factory.create_interactor('get_available_quests')
            quests_result = quest_interactor.execute(user=user, tenant=tenant)
            
            # Get user profile
            profile_interactor = self.interactor_factory.create_interactor('get_user_profile')
            profile_result = profile_interactor.execute(user=user, tenant=tenant)
            
            return InteractorResult(
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
            return InteractorResult(
                success=False,
                error=str(exc)
            )
    
    def process_daily_engagement(self, user, tenant=None) -> InteractorResult:
        """Process daily engagement workflow."""
        try:
            # Check if user has already checked in today
            checkin_interactor = self.interactor_factory.create_interactor('checkin')
            checkin_result = checkin_interactor.execute(user=user, tenant=tenant)
            
            # Get user's current stats
            profile_interactor = self.interactor_factory.create_interactor('get_user_profile')
            profile_result = profile_interactor.execute(user=user, tenant=tenant)
            
            # Get available quests
            quest_interactor = self.interactor_factory.create_interactor('get_available_quests')
            quests_result = quest_interactor.execute(user=user, tenant=tenant)
            
            # Get leaderboard position
            rank_interactor = self.interactor_factory.create_interactor('get_user_rank')
            rank_result = rank_interactor.execute(user=user, tenant=tenant)
            
            return InteractorResult(
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
            return InteractorResult(
                success=False,
                error=str(exc)
            )
    
    def generate_user_digest(self, user, period='weekly', tenant=None) -> InteractorResult:
        """Generate user engagement digest."""
        try:
            # Get user profile
            profile_interactor = self.interactor_factory.create_interactor('get_user_profile')
            profile_result = profile_interactor.execute(user=user, tenant=tenant)
            
            # Get check-in history
            checkin_history_interactor = self.interactor_factory.create_interactor('get_checkin_history')
            days = 7 if period == 'weekly' else 30
            checkin_result = checkin_history_interactor.execute(user=user, days=days, tenant=tenant)
            
            # Get spin history
            spin_history_interactor = self.interactor_factory.create_interactor('get_spin_history')
            spin_result = spin_history_interactor.execute(user=user, limit=20, tenant=tenant)
            
            # Get achievement progress
            achievement_interactor = self.interactor_factory.create_interactor('get_achievement_progress')
            achievement_result = achievement_interactor.execute(user=user, tenant=tenant)
            
            # Get leaderboard rank
            rank_interactor = self.interactor_factory.create_interactor('get_user_rank')
            rank_result = rank_interactor.execute(user=user, tenant=tenant)
            
            return InteractorResult(
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
            return InteractorResult(
                success=False,
                error=str(exc)
            )
