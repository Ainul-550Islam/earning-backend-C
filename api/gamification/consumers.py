"""
Gamification WebSocket Consumers — Real-time WebSocket consumers for gamification.

This module provides WebSocket consumers for real-time gamification updates,
including live leaderboards, achievement notifications, and streak updates.
"""

from __future__ import annotations
from django.db import models

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from api.gamification.models import (
    Badge, UserBadge, DailyChallenge, UserDailyChallenge,
    Streak, LevelConfig, ContestCycle, UserAchievement,
    UserPoints, PointsTransaction, StreakFreeze, ContestParticipant,
    GamificationConfig, GamificationInsight
)
from api.gamification.exceptions import GamificationServiceError
from api.gamification.helpers import LeaderboardHelper
from api.gamification.analytics import UserAnalytics

User = get_user_model()
logger = logging.getLogger(__name__)


class BaseGamificationConsumer(AsyncWebsocketConsumer):
    """Base WebSocket consumer for gamification."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.user_id = None
        self.room_group_name = None
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def connect(self) -> None:
        """Handle WebSocket connection."""
        try:
            # Authenticate user
            self.user = self.scope["user"]
            if not self.user or not self.user.is_authenticated:
                await self.close(code=4001)  # Authentication required
                return
            
            self.user_id = str(self.user.id)
            self.room_group_name = f"gamification_{self.user_id}"
            
            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
            
            self.logger.info(f"User {self.user_id} connected to gamification WebSocket")
            
            # Send initial data
            await self.send_initial_data()
            
        except Exception as e:
            self.logger.error(f"Error in WebSocket connect: {e}")
            await self.close(code=4000)
    
    async def disconnect(self, close_code: int) -> None:
        """Handle WebSocket disconnection."""
        try:
            if self.room_group_name:
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )
            
            self.logger.info(f"User {self.user_id} disconnected from gamification WebSocket")
            
        except Exception as e:
            self.logger.error(f"Error in WebSocket disconnect: {e}")
    
    async def receive(self, text_data: str) -> None:
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                await self.send_pong()
            elif message_type == 'subscribe':
                await self.handle_subscribe(data)
            elif message_type == 'unsubscribe':
                await self.handle_unsubscribe(data)
            elif message_type == 'get_leaderboard':
                await self.handle_get_leaderboard(data)
            elif message_type == 'get_user_stats':
                await self.handle_get_user_stats(data)
            else:
                await self.send_error(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
        except Exception as e:
            self.logger.error(f"Error receiving WebSocket message: {e}")
            await self.send_error("Internal server error")
    
    async def send_initial_data(self) -> None:
        """Send initial data to connected user."""
        try:
            # Get user's current stats
            user_stats = await self.get_user_stats()
            
            await self.send_json({
                'type': 'initial_data',
                'data': user_stats,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            self.logger.error(f"Error sending initial data: {e}")
    
    async def send_json(self, data: Dict[str, Any]) -> None:
        """Send JSON message."""
        await self.send(text_data=json.dumps(data))
    
    async def send_error(self, message: str) -> None:
        """Send error message."""
        await self.send_json({
            'type': 'error',
            'message': message,
            'timestamp': timezone.now().isoformat()
        })
    
    async def send_pong(self) -> None:
        """Send pong response."""
        await self.send_json({
            'type': 'pong',
            'timestamp': timezone.now().isoformat()
        })
    
    async def handle_subscribe(self, data: Dict[str, Any]) -> None:
        """Handle subscription to specific events."""
        subscription_type = data.get('subscription_type')
        
        if subscription_type in ['leaderboard', 'achievements', 'streaks', 'challenges']:
            # Join specific room group
            room_name = f"gamification_{subscription_type}"
            await self.channel_layer.group_add(room_name, self.channel_name)
            
            await self.send_json({
                'type': 'subscribed',
                'subscription_type': subscription_type,
                'timestamp': timezone.now().isoformat()
            })
        else:
            await self.send_error(f"Invalid subscription type: {subscription_type}")
    
    async def handle_unsubscribe(self, data: Dict[str, Any]) -> None:
        """Handle unsubscription from specific events."""
        subscription_type = data.get('subscription_type')
        
        if subscription_type in ['leaderboard', 'achievements', 'streaks', 'challenges']:
            # Leave specific room group
            room_name = f"gamification_{subscription_type}"
            await self.channel_layer.group_discard(room_name, self.channel_name)
            
            await self.send_json({
                'type': 'unsubscribed',
                'subscription_type': subscription_type,
                'timestamp': timezone.now().isoformat()
            })
        else:
            await self.send_error(f"Invalid subscription type: {subscription_type}")
    
    async def handle_get_leaderboard(self, data: Dict[str, Any]) -> None:
        """Handle leaderboard request."""
        scope = data.get('scope', 'global')
        limit = data.get('limit', 50)
        
        try:
            leaderboard = await self.get_leaderboard(scope, limit)
            
            await self.send_json({
                'type': 'leaderboard',
                'data': leaderboard,
                'scope': scope,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            self.logger.error(f"Error getting leaderboard: {e}")
            await self.send_error("Failed to get leaderboard")
    
    async def handle_get_user_stats(self, data: Dict[str, Any]) -> None:
        """Handle user stats request."""
        try:
            user_stats = await self.get_user_stats()
            
            await self.send_json({
                'type': 'user_stats',
                'data': user_stats,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            self.logger.error(f"Error getting user stats: {e}")
            await self.send_error("Failed to get user stats")
    
    @database_sync_to_async
    def get_user_stats(self) -> Dict[str, Any]:
        """Get user's gamification stats."""
        try:
            user_badges = UserBadge.objects.filter(user=self.user).count()
            user_streak = Streak.objects.filter(user=self.user).first()
            user_achievements = UserAchievement.objects.filter(
                user=self.user, is_awarded=True
            ).count()
            
            # Get level info
            total_points = UserAchievement.objects.filter(
                user=self.user, is_awarded=True
            ).aggregate(total=models.Sum('points_awarded'))['total'] or 0
            
            level_info = LevelConfig.objects.filter(
                points_required__lte=total_points
            ).order_by('-level_number').first()
            
            return {
                'user_id': self.user_id,
                'username': self.user.username,
                'badges_count': user_badges,
                'streak_days': user_streak.current_days if user_streak else 0,
                'streak_active': user_streak.is_active if user_streak else False,
                'achievements_count': user_achievements,
                'total_points': total_points,
                'current_level': level_info.level_number if level_info else 1,
                'next_level_points': level_info.points_required if level_info else 0
            }
            
        except Exception as e:
            self.logger.error(f"Error getting user stats: {e}")
            return {}
    
    @database_sync_to_async
    def get_leaderboard(self, scope: str = 'global', limit: int = 50) -> List[Dict[str, Any]]:
        """Get leaderboard data."""
        try:
            leaderboard = LeaderboardHelper.get_leaderboard(scope, limit)
            return leaderboard
        except Exception as e:
            self.logger.error(f"Error getting leaderboard: {e}")
            return []
    
    async def gamification_update(self, event: Dict[str, Any]) -> None:
        """Handle gamification update events."""
        await self.send_json({
            'type': 'gamification_update',
            'event': event,
            'timestamp': timezone.now().isoformat()
        })


class LeaderboardConsumer(BaseGamificationConsumer):
    """WebSocket consumer for real-time leaderboard updates."""
    
    async def connect(self) -> None:
        """Connect to leaderboard updates."""
        await super().connect()
        
        # Join leaderboard room group
        await self.channel_layer.group_add(
            "gamification_leaderboard",
            self.channel_name
        )
    
    async def leaderboard_update(self, event: Dict[str, Any]) -> None:
        """Handle leaderboard update events."""
        await self.send_json({
            'type': 'leaderboard_update',
            'data': event,
            'timestamp': timezone.now().isoformat()
        })


class AchievementConsumer(BaseGamificationConsumer):
    """WebSocket consumer for real-time achievement updates."""
    
    async def connect(self) -> None:
        """Connect to achievement updates."""
        await super().connect()
        
        # Join achievements room group
        await self.channel_layer.group_add(
            "gamification_achievements",
            self.channel_name
        )
    
    async def achievement_earned(self, event: Dict[str, Any]) -> None:
        """Handle achievement earned events."""
        await self.send_json({
            'type': 'achievement_earned',
            'data': event,
            'timestamp': timezone.now().isoformat()
        })


class StreakConsumer(BaseGamificationConsumer):
    """WebSocket consumer for real-time streak updates."""
    
    async def connect(self) -> None:
        """Connect to streak updates."""
        await super().connect()
        
        # Join streaks room group
        await self.channel_layer.group_add(
            "gamification_streaks",
            self.channel_name
        )
    
    async def streak_update(self, event: Dict[str, Any]) -> None:
        """Handle streak update events."""
        await self.send_json({
            'type': 'streak_update',
            'data': event,
            'timestamp': timezone.now().isoformat()
        })


class ChallengeConsumer(BaseGamificationConsumer):
    """WebSocket consumer for real-time challenge updates."""
    
    async def connect(self) -> None:
        """Connect to challenge updates."""
        await super().connect()
        
        # Join challenges room group
        await self.channel_layer.group_add(
            "gamification_challenges",
            self.channel_name
        )
    
    async def challenge_update(self, event: Dict[str, Any]) -> None:
        """Handle challenge update events."""
        await self.send_json({
            'type': 'challenge_update',
            'data': event,
            'timestamp': timezone.now().isoformat()
        })


class NotificationConsumer(BaseGamificationConsumer):
    """WebSocket consumer for real-time notifications."""
    
    async def connect(self) -> None:
        """Connect to notifications."""
        await super().connect()
        
        # Join notifications room group
        await self.channel_layer.group_add(
            f"gamification_notifications_{self.user_id}",
            self.channel_name
        )
    
    async def notification(self, event: Dict[str, Any]) -> None:
        """Handle notification events."""
        await self.send_json({
            'type': 'notification',
            'data': event,
            'timestamp': timezone.now().isoformat()
        })


class ContestConsumer(BaseGamificationConsumer):
    """WebSocket consumer for real-time contest updates."""
    
    async def connect(self) -> None:
        """Connect to contest updates."""
        await super().connect()
        
        # Join contests room group
        await self.channel_layer.group_add(
            "gamification_contests",
            self.channel_name
        )
    
    async def contest_update(self, event: Dict[str, Any]) -> None:
        """Handle contest update events."""
        await self.send_json({
            'type': 'contest_update',
            'data': event,
            'timestamp': timezone.now().isoformat()
        })


class PointsConsumer(BaseGamificationConsumer):
    """WebSocket consumer for real-time points updates."""
    
    async def connect(self) -> None:
        """Connect to points updates."""
        await super().connect()
        
        # Join points room group
        await self.channel_layer.group_add(
            "gamification_points",
            self.channel_name
        )
    
    async def points_update(self, event: Dict[str, Any]) -> None:
        """Handle points update events."""
        await self.send_json({
            'type': 'points_update',
            'data': event,
            'timestamp': timezone.now().isoformat()
        })
    
    async def points_transaction(self, event: Dict[str, Any]) -> None:
        """Handle points transaction events."""
        await self.send_json({
            'type': 'points_transaction',
            'data': event,
            'timestamp': timezone.now().isoformat()
        })


class StreakFreezeConsumer(BaseGamificationConsumer):
    """WebSocket consumer for real-time streak freeze updates."""
    
    async def connect(self) -> None:
        """Connect to streak freeze updates."""
        await super().connect()
        
        # Join streak freezes room group
        await self.channel_layer.group_add(
            "gamification_streak_freezes",
            self.channel_name
        )
    
    async def streak_freeze_update(self, event: Dict[str, Any]) -> None:
        """Handle streak freeze update events."""
        await self.send_json({
            'type': 'streak_freeze_update',
            'data': event,
            'timestamp': timezone.now().isoformat()
        })


class ContestParticipantConsumer(BaseGamificationConsumer):
    """WebSocket consumer for real-time contest participant updates."""
    
    async def connect(self) -> None:
        """Connect to contest participant updates."""
        await super().connect()
        
        # Join contest participants room group
        await self.channel_layer.group_add(
            "gamification_contest_participants",
            self.channel_name
        )
    
    async def participant_update(self, event: Dict[str, Any]) -> None:
        """Handle participant update events."""
        await self.send_json({
            'type': 'participant_update',
            'data': event,
            'timestamp': timezone.now().isoformat()
        })


class GamificationConfigConsumer(BaseGamificationConsumer):
    """WebSocket consumer for real-time gamification config updates."""
    
    async def connect(self) -> None:
        """Connect to gamification config updates."""
        await super().connect()
        
        # Join config room group
        await self.channel_layer.group_add(
            "gamification_config",
            self.channel_name
        )
    
    async def config_update(self, event: Dict[str, Any]) -> None:
        """Handle config update events."""
        await self.send_json({
            'type': 'config_update',
            'data': event,
            'timestamp': timezone.now().isoformat()
        })


class GamificationInsightConsumer(BaseGamificationConsumer):
    """WebSocket consumer for real-time gamification insights."""
    
    async def connect(self) -> None:
        """Connect to gamification insights."""
        await super().connect()
        
        # Join insights room group
        await self.channel_layer.group_add(
            "gamification_insights",
            self.channel_name
        )
    
    async def insight_update(self, event: Dict[str, Any]) -> None:
        """Handle insight update events."""
        await self.send_json({
            'type': 'insight_update',
            'data': event,
            'timestamp': timezone.now().isoformat()
        })


# WebSocket event handlers
async def broadcast_badge_earned(user_id: str, badge_data: Dict[str, Any]) -> None:
    """Broadcast badge earned event."""
    try:
        # Send to user's personal room
        await get_channel_layer().group_send(
            f"gamification_{user_id}",
            {
                'type': 'badge_earned',
                'user_id': user_id,
                'badge_data': badge_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        # Send to achievements room
        await get_channel_layer().group_send(
            "gamification_achievements",
            {
                'type': 'badge_earned_broadcast',
                'user_id': user_id,
                'badge_data': badge_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error broadcasting badge earned event: {e}")


async def broadcast_streak_update(user_id: str, streak_data: Dict[str, Any]) -> None:
    """Broadcast streak update event."""
    try:
        # Send to user's personal room
        await get_channel_layer().group_send(
            f"gamification_{user_id}",
            {
                'type': 'streak_update',
                'user_id': user_id,
                'streak_data': streak_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        # Send to streaks room
        await get_channel_layer().group_send(
            "gamification_streaks",
            {
                'type': 'streak_update_broadcast',
                'user_id': user_id,
                'streak_data': streak_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error broadcasting streak update event: {e}")


async def broadcast_challenge_completed(user_id: str, challenge_data: Dict[str, Any]) -> None:
    """Broadcast challenge completed event."""
    try:
        # Send to user's personal room
        await get_channel_layer().group_send(
            f"gamification_{user_id}",
            {
                'type': 'challenge_completed',
                'user_id': user_id,
                'challenge_data': challenge_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        # Send to challenges room
        await get_channel_layer().group_send(
            "gamification_challenges",
            {
                'type': 'challenge_completed_broadcast',
                'user_id': user_id,
                'challenge_data': challenge_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error broadcasting challenge completed event: {e}")


async def broadcast_leaderboard_update(scope: str, leaderboard_data: List[Dict[str, Any]]) -> None:
    """Broadcast leaderboard update."""
    try:
        # Send to leaderboard room
        await get_channel_layer().group_send(
            "gamification_leaderboard",
            {
                'type': 'leaderboard_update_broadcast',
                'scope': scope,
                'leaderboard_data': leaderboard_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error broadcasting leaderboard update: {e}")


async def send_user_notification(user_id: str, notification_data: Dict[str, Any]) -> None:
    """Send notification to specific user."""
    try:
        await get_channel_layer().group_send(
            f"gamification_notifications_{user_id}",
            {
                'type': 'user_notification',
                'user_id': user_id,
                'notification_data': notification_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error sending user notification: {e}")


async def broadcast_contest_update(contest_data: Dict[str, Any]) -> None:
    """Broadcast contest update."""
    try:
        # Send to contests room
        await get_channel_layer().group_send(
            "gamification_contests",
            {
                'type': 'contest_update_broadcast',
                'contest_data': contest_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error broadcasting contest update: {e}")


async def broadcast_points_update(user_id: str, points_data: Dict[str, Any]) -> None:
    """Broadcast points update event."""
    try:
        # Send to user's personal room
        await get_channel_layer().group_send(
            f"gamification_{user_id}",
            {
                'type': 'points_update',
                'user_id': user_id,
                'points_data': points_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        # Send to points room
        await get_channel_layer().group_send(
            "gamification_points",
            {
                'type': 'points_update_broadcast',
                'user_id': user_id,
                'points_data': points_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error broadcasting points update event: {e}")


async def broadcast_points_transaction(user_id: str, transaction_data: Dict[str, Any]) -> None:
    """Broadcast points transaction event."""
    try:
        # Send to user's personal room
        await get_channel_layer().group_send(
            f"gamification_{user_id}",
            {
                'type': 'points_transaction',
                'user_id': user_id,
                'transaction_data': transaction_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        # Send to points room
        await get_channel_layer().group_send(
            "gamification_points",
            {
                'type': 'points_transaction_broadcast',
                'user_id': user_id,
                'transaction_data': transaction_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error broadcasting points transaction event: {e}")


async def broadcast_streak_freeze_update(user_id: str, freeze_data: Dict[str, Any]) -> None:
    """Broadcast streak freeze update event."""
    try:
        # Send to user's personal room
        await get_channel_layer().group_send(
            f"gamification_{user_id}",
            {
                'type': 'streak_freeze_update',
                'user_id': user_id,
                'freeze_data': freeze_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        # Send to streak freezes room
        await get_channel_layer().group_send(
            "gamification_streak_freezes",
            {
                'type': 'streak_freeze_update_broadcast',
                'user_id': user_id,
                'freeze_data': freeze_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error broadcasting streak freeze update event: {e}")


async def broadcast_contest_participant_update(participant_data: Dict[str, Any]) -> None:
    """Broadcast contest participant update event."""
    try:
        # Send to contest participants room
        await get_channel_layer().group_send(
            "gamification_contest_participants",
            {
                'type': 'participant_update_broadcast',
                'participant_data': participant_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error broadcasting contest participant update event: {e}")


async def broadcast_gamification_config_update(tenant_id: str, config_data: Dict[str, Any]) -> None:
    """Broadcast gamification config update event."""
    try:
        # Send to config room
        await get_channel_layer().group_send(
            "gamification_config",
            {
                'type': 'config_update_broadcast',
                'tenant_id': tenant_id,
                'config_data': config_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error broadcasting gamification config update event: {e}")


async def broadcast_gamification_insight_update(insight_data: Dict[str, Any]) -> None:
    """Broadcast gamification insight update event."""
    try:
        # Send to insights room
        await get_channel_layer().group_send(
            "gamification_insights",
            {
                'type': 'insight_update_broadcast',
                'insight_data': insight_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error broadcasting gamification insight update event: {e}")


def get_channel_layer():
    """Get channel layer instance."""
    from channels.layers import get_channel_layer as _get_channel_layer
    return _get_channel_layer()


# Consumer registry for routing
CONSUMER_REGISTRY = {
    'gamification': BaseGamificationConsumer,
    'leaderboard': LeaderboardConsumer,
    'achievements': AchievementConsumer,
    'streaks': StreakConsumer,
    'challenges': ChallengeConsumer,
    'notifications': NotificationConsumer,
    'contests': ContestConsumer,
    'points': PointsConsumer,
    'streak_freezes': StreakFreezeConsumer,
    'contest_participants': ContestParticipantConsumer,
    'gamification_config': GamificationConfigConsumer,
    'gamification_insights': GamificationInsightConsumer,
}


def get_consumer(consumer_type: str) -> BaseGamificationConsumer:
    """Get consumer by type."""
    consumer_class = CONSUMER_REGISTRY.get(consumer_type)
    if not consumer_class:
        raise ValueError(f"Unknown consumer type: {consumer_type}")
    return consumer_class


# Utility functions for WebSocket management
async def get_connected_users(consumer_type: str) -> List[str]:
    """Get list of connected users for a consumer type."""
    try:
        # This would typically require channel layer inspection
        # For now, return empty list (implementation depends on channel layer)
        return []
    except Exception as e:
        logger.error(f"Error getting connected users: {e}")
        return []


async def broadcast_to_all_users(message: Dict[str, Any]) -> None:
    """Broadcast message to all connected users."""
    try:
        # Send to all gamification room groups
        room_groups = [
            "gamification_leaderboard",
            "gamification_achievements",
            "gamification_streaks",
            "gamification_challenges",
            "gamification_contests",
            "gamification_points",
            "gamification_streak_freezes",
            "gamification_contest_participants",
            "gamification_config",
            "gamification_insights"
        ]
        
        for room_group in room_groups:
            await get_channel_layer().group_send(
                room_group,
                {
                    'type': 'broadcast',
                    'message': message,
                    'timestamp': timezone.now().isoformat()
                }
            )
        
    except Exception as e:
        logger.error(f"Error broadcasting to all users: {e}")


async def get_connection_stats() -> Dict[str, Any]:
    """Get WebSocket connection statistics."""
    try:
        # This would typically require channel layer inspection
        # For now, return empty stats (implementation depends on channel layer)
        return {
            'total_connections': 0,
            'connections_by_type': {},
            'active_connections': [],
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting connection stats: {e}")
        return {
            'total_connections': 0,
            'connections_by_type': {},
            'active_connections': [],
            'timestamp': timezone.now().isoformat()
        }
