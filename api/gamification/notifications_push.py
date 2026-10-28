"""
Gamification Push Notifications — Push notification system for gamification events.

This module provides push notification functionality for the gamification system,
including notification templates, delivery management, and user preferences.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import models
from django.utils import timezone

from api.gamification.models import (
    Badge, UserBadge, DailyChallenge, UserDailyChallenge,
    Streak, LevelConfig, ContestCycle, UserAchievement
)
from api.gamification.choices import (
    BadgeRarity, BadgeCriteriaType, ChallengeAction,
    ContestCycleStatus, AchievementType
)
from api.gamification.exceptions import GamificationServiceError
from api.gamification.helpers import CacheHelper

User = get_user_model()
logger = logging.getLogger(__name__)


class PushNotification:
    """Represents a push notification."""
    
    def __init_(self, title: str, body: str, data: Optional[Dict[str, Any]] = None,
                 user_id: Optional[str] = None, priority: str = "normal",
                 category: Optional[str] = None, icon: Optional[str] = None,
                 image: Optional[str] = None, actions: Optional[List[Dict[str, Any]]] = None,
                 ttl: Optional[int] = None, timestamp: Optional[datetime] = None):
        self.title = title
        self.body = body
        self.data = data or {}
        self.user_id = user_id
        self.priority = priority  # low, normal, high
        self.category = category
        self.icon = icon
        self.image = image
        self.actions = actions or []
        self.ttl = ttl  # Time to live in seconds
        self.timestamp = timestamp or timezone.now()
        self.id = f"{user_id}_{int(self.timestamp.timestamp())}" if user_id else f"broadcast_{int(self.timestamp.timestamp())}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert notification to dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'body': self.body,
            'data': self.data,
            'user_id': self.user_id,
            'priority': self.priority,
            'category': self.category,
            'icon': self.icon,
            'image': self.image,
            'actions': self.actions,
            'ttl': self.ttl,
            'timestamp': self.timestamp.isoformat()
        }


class NotificationTemplate:
    """Template for generating notifications."""
    
    def __init_(self, template_id: str, title_template: str, body_template: str,
                 data_mapping: Dict[str, str], category: str = "general",
                 priority: str = "normal", icon: Optional[str] = None,
                 actions: Optional[List[Dict[str, Any]]] = None):
        self.template_id = template_id
        self.title_template = title_template
        self.body_template = body_template
        self.data_mapping = data_mapping
        self.category = category
        self.priority = priority
        self.icon = icon
        self.actions = actions or []
    
    def render(self, context: Dict[str, Any], user_id: Optional[str] = None) -> PushNotification:
        """Render template with context data."""
        try:
            # Map context data to template variables
            template_vars = {}
            for key, context_key in self.data_mapping.items():
                template_vars[key] = context.get(context_key, '')
            
            # Format title and body
            title = self.title_template.format(**template_vars)
            body = self.body_template.format(**template_vars)
            
            # Create notification
            notification = PushNotification(
                title=title,
                body=body,
                data=context,
                user_id=user_id,
                priority=self.priority,
                category=self.category,
                icon=self.icon,
                actions=self.actions
            )
            
            return notification
            
        except Exception as e:
            logger.error(f"Error rendering notification template {self.template_id}: {e}")
            raise GamificationServiceError(f"Failed to render notification template: {e}")


class NotificationPreferences:
    """User notification preferences."""
    
    def __init_(self, user_id: str):
        self.user_id = user_id
        self.cache_key = f"notification_preferences:{user_id}"
        self.default_preferences = {
            'badge_earned': True,
            'streak_updated': True,
            'challenge_completed': True,
            'level_up': True,
            'achievement_earned': True,
            'contest_reminder': True,
            'contest_results': True,
            'daily_reminder': False,
            'weekly_summary': False,
            'leaderboard_update': False,
            'friend_activity': False,
            'system_announcements': True
        }
    
    def get_preferences(self) -> Dict[str, bool]:
        """Get user's notification preferences."""
        cached_prefs = cache.get(self.cache_key)
        if cached_prefs:
            return cached_prefs
        
        # In a real implementation, this would be stored in the database
        # For now, return default preferences
        return self.default_preferences.copy()
    
    def set_preference(self, category: str, enabled: bool) -> None:
        """Set a specific notification preference."""
        preferences = self.get_preferences()
        preferences[category] = enabled
        
        # Cache the preferences
        cache.set(self.cache_key, preferences, 86400)  # 24 hours
    
    def set_preferences(self, preferences: Dict[str, bool]) -> None:
        """Set multiple notification preferences."""
        current_prefs = self.get_preferences()
        current_prefs.update(preferences)
        
        # Cache the preferences
        cache.set(self.cache_key, current_prefs, 86400)  # 24 hours
    
    def is_enabled(self, category: str) -> bool:
        """Check if a notification category is enabled for the user."""
        preferences = self.get_preferences()
        return preferences.get(category, False)


class PushNotificationProvider:
    """Base class for push notification providers."""
    
    def __init_(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    def send_notification(self, notification: PushNotification) -> Dict[str, Any]:
        """Send a push notification."""
        raise NotImplementedError("Subclasses must implement send_notification method")
    
    def send_bulk_notifications(self, notifications: List[PushNotification]) -> List[Dict[str, Any]]:
        """Send multiple push notifications."""
        results = []
        for notification in notifications:
            result = self.send_notification(notification)
            results.append(result)
        return results


class FirebasePushProvider(PushNotificationProvider):
    """Firebase Cloud Messaging (FCM) provider."""
    
    def __init_(self, config: Dict[str, Any]):
        super().__init_("firebase", config)
        self.api_key = config.get('api_key')
        self.fcm_url = "https://fcm.googleapis.com/fcm/send"
    
    def send_notification(self, notification: PushNotification) -> Dict[str, Any]:
        """Send notification via Firebase."""
        try:
            import requests
            
            # Get user's FCM token (in a real implementation, this would be stored in the database)
            fcm_token = self._get_user_fcm_token(notification.user_id)
            
            if not fcm_token:
                return {
                    'success': False,
                    'error': 'No FCM token found for user',
                    'provider': self.name
                }
            
            # Build FCM payload
            payload = {
                'to': fcm_token,
                'notification': {
                    'title': notification.title,
                    'body': notification.body,
                    'icon': notification.icon,
                    'image': notification.image,
                    'click_action': notification.data.get('click_action', '')
                },
                'data': notification.data,
                'priority': self._map_priority(notification.priority),
                'ttl': notification.ttl
            }
            
            # Add actions if specified
            if notification.actions:
                payload['notification']['actions'] = notification.actions
            
            # Send request
            headers = {
                'Authorization': f'key={self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                self.fcm_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get('success') == 1:
                return {
                    'success': True,
                    'message_id': response_data.get('message_id'),
                    'provider': self.name,
                    'response': response_data
                }
            else:
                return {
                    'success': False,
                    'error': response_data.get('error', 'Unknown error'),
                    'provider': self.name,
                    'response': response_data
                }
            
        except Exception as e:
            self.logger.error(f"Error sending Firebase notification: {e}")
            return {
                'success': False,
                'error': str(e),
                'provider': self.name
            }
    
    def _get_user_fcm_token(self, user_id: str) -> Optional[str]:
        """Get user's FCM token."""
        # In a real implementation, this would query the database
        # For now, return a mock token
        return f"mock_fcm_token_{user_id}"
    
    def _map_priority(self, priority: str) -> str:
        """Map notification priority to FCM priority."""
        priority_mapping = {
            'low': 'normal',
            'normal': 'normal',
            'high': 'high'
        }
        return priority_mapping.get(priority, 'normal')


class APNSPushProvider(PushNotificationProvider):
    """Apple Push Notification Service (APNS) provider."""
    
    def __init_(self, config: Dict[str, Any]):
        super().__init_("apns", config)
        self.team_id = config.get('team_id')
        self.key_id = config.get('key_id')
        self.bundle_id = config.get('bundle_id')
        self.key_file = config.get('key_file')
        self.use_sandbox = config.get('use_sandbox', False)
    
    def send_notification(self, notification: PushNotification) -> Dict[str, Any]:
        """Send notification via APNS."""
        try:
            import jwt
            import requests
            
            # Get user's APNS token (in a real implementation, this would be stored in the database)
            device_token = self._get_user_device_token(notification.user_id)
            
            if not device_token:
                return {
                    'success': False,
                    'error': 'No APNS token found for user',
                    'provider': self.name
                }
            
            # Generate JWT token
            jwt_token = self._generate_jwt_token()
            
            # Build APNS payload
            payload = {
                'aps': {
                    'alert': {
                        'title': notification.title,
                        'body': notification.body
                    },
                    'badge': notification.data.get('badge', 1),
                    'sound': 'default',
                    'category': notification.category,
                    'thread-id': notification.data.get('thread_id')
                }
            }
            
            # Add custom data
            for key, value in notification.data.items():
                if key not in ['badge', 'thread_id']:
                    payload[key] = value
            
            # Send request
            apns_url = f"https://{'api.development' if self.use_sandbox else 'api'}.push.apple.com/3/device/{device_token}"
            
            headers = {
                'Authorization': f'bearer {jwt_token}',
                'apns-topic': self.bundle_id,
                'apns-priority': '10' if notification.priority == 'high' else '5',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                apns_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'message_id': response.headers.get('apns-id'),
                    'provider': self.name
                }
            else:
                return {
                    'success': False,
                    'error': response.text,
                    'provider': self.name,
                    'status_code': response.status_code
                }
            
        except Exception as e:
            self.logger.error(f"Error sending APNS notification: {e}")
            return {
                'success': False,
                'error': str(e),
                'provider': self.name
            }
    
    def _get_user_device_token(self, user_id: str) -> Optional[str]:
        """Get user's APNS device token."""
        # In a real implementation, this would query the database
        # For now, return a mock token
        return f"mock_apns_token_{user_id}"
    
    def _generate_jwt_token(self) -> str:
        """Generate JWT token for APNS."""
        import jwt
        
        # In a real implementation, this would use the actual key file
        # For now, return a mock token
        return f"mock_jwt_token_{int(timezone.now().timestamp())}"


class PushNotificationService:
    """Main service for push notifications."""
    
    def __init_(self):
        self.logger = logging.getLogger(__name__)
        self.providers: Dict[str, PushNotificationProvider] = {}
        self.templates: Dict[str, NotificationTemplate] = {}
        self._initialize_providers()
        self._initialize_templates()
    
    def _initialize_providers(self):
        """Initialize push notification providers."""
        # Firebase provider
        firebase_config = getattr(settings, 'FIREBASE_CONFIG', {})
        if firebase_config.get('api_key'):
            self.providers['firebase'] = FirebasePushProvider(firebase_config)
        
        # APNS provider
        apns_config = getattr(settings, 'APNS_CONFIG', {})
        if apns_config.get('team_id') and apns_config.get('key_id'):
            self.providers['apns'] = APNSPushProvider(apns_config)
        
        self.logger.info(f"Initialized {len(self.providers)} push notification providers")
    
    def _initialize_templates(self):
        """Initialize notification templates."""
        templates = {
            'badge_earned': NotificationTemplate(
                template_id='badge_earned',
                title_template='🏆 New Badge Earned!',
                body_template='Congratulations! You earned the {badge_name} badge. {points_bonus} points awarded!',
                data_mapping={'badge_name': 'badge_name', 'points_bonus': 'points_bonus'},
                category='badge',
                priority='normal',
                icon='badge'
            ),
            
            'streak_updated': NotificationTemplate(
                template_id='streak_updated',
                title_template='🔥 Streak Updated!',
                body_template='Your streak is now {current_days} days! Keep it going!',
                data_mapping={'current_days': 'current_days'},
                category='streak',
                priority='normal',
                icon='streak'
            ),
            
            'challenge_completed': NotificationTemplate(
                template_id='challenge_completed',
                title_template='✅ Challenge Completed!',
                body_template='Great job! You completed the {challenge_title} challenge. {bonus_points} points awarded!',
                data_mapping={'challenge_title': 'challenge_title', 'bonus_points': 'bonus_points'},
                category='challenge',
                priority='normal',
                icon='challenge'
            ),
            
            'level_up': NotificationTemplate(
                template_id='level_up',
                title_template='⬆️ Level Up!',
                body_template='Congratulations! You reached level {new_level}! {perks_count} new perks unlocked.',
                data_mapping={'new_level': 'new_level', 'perks_count': 'perks_count'},
                category='level',
                priority='high',
                icon='level'
            ),
            
            'achievement_earned': NotificationTemplate(
                template_id='achievement_earned',
                title_template='🎉 Achievement Unlocked!',
                body_template='Amazing! You earned the {achievement_type} achievement. {points_awarded} points awarded!',
                data_mapping={'achievement_type': 'achievement_type', 'points_awarded': 'points_awarded'},
                category='achievement',
                priority='high',
                icon='achievement'
            ),
            
            'contest_reminder': NotificationTemplate(
                template_id='contest_reminder',
                title_template='🏁 Contest Starting Soon!',
                body_template='The {contest_name} contest starts in {hours_until_start} hours. Don\'t miss out!',
                data_mapping={'contest_name': 'contest_name', 'hours_until_start': 'hours_until_start'},
                category='contest',
                priority='normal',
                icon='contest'
            ),
            
            'contest_results': NotificationTemplate(
                template_id='contest_results',
                title_template='🏆 Contest Results!',
                body_template='The {contest_name} contest has ended. Check your rank and rewards!',
                data_mapping={'contest_name': 'contest_name'},
                category='contest',
                priority='normal',
                icon='contest'
            ),
            
            'streak_expiring': NotificationTemplate(
                template_id='streak_expiring',
                title_template='⚠️ Streak Expiring Soon!',
                body_template='Your streak will expire today! Complete an activity to keep it going.',
                data_mapping={},
                category='streak',
                priority='high',
                icon='warning'
            ),
            
            'daily_reminder': NotificationTemplate(
                template_id='daily_reminder',
                title_template='📅 Daily Reminder',
                body_template='Don\'t forget to check your daily challenges and keep your streak alive!',
                data_mapping={},
                category='reminder',
                priority='low',
                icon='reminder'
            ),
            
            'weekly_summary': NotificationTemplate(
                template_id='weekly_summary',
                title_template='📊 Weekly Summary',
                body_template='You earned {badges_count} badges and completed {challenges_count} challenges this week!',
                data_mapping={'badges_count': 'badges_count', 'challenges_count': 'challenges_count'},
                category='summary',
                priority='low',
                icon='summary'
            )
        }
        
        self.templates.update(templates)
        self.logger.info(f"Initialized {len(self.templates)} notification templates")
    
    def send_notification(self, user_id: str, template_id: str,
                         context: Dict[str, Any], provider: Optional[str] = None) -> Dict[str, Any]:
        """Send a push notification using a template."""
        try:
            # Check user preferences
            preferences = NotificationPreferences(user_id)
            if not preferences.is_enabled(template_id):
                return {
                    'success': False,
                    'error': 'User has disabled this notification type',
                    'skipped': True
                }
            
            # Render template
            template = self.templates.get(template_id)
            if not template:
                return {
                    'success': False,
                    'error': f'Template {template_id} not found'
                }
            
            notification = template.render(context, user_id)
            
            # Send notification
            return self._send_notification(notification, provider)
            
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_custom_notification(self, notification: PushNotification,
                              provider: Optional[str] = None) -> Dict[str, Any]:
        """Send a custom push notification."""
        try:
            # Check user preferences for custom notifications
            if notification.user_id:
                preferences = NotificationPreferences(notification.user_id)
                if not preferences.is_enabled('custom'):
                    return {
                        'success': False,
                        'error': 'User has disabled custom notifications',
                        'skipped': True
                    }
            
            return self._send_notification(notification, provider)
            
        except Exception as e:
            self.logger.error(f"Error sending custom notification: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_bulk_notifications(self, user_ids: List[str], template_id: str,
                               context: Dict[str, Any], provider: Optional[str] = None) -> List[Dict[str, Any]]:
        """Send bulk notifications to multiple users."""
        results = []
        
        for user_id in user_ids:
            result = self.send_notification(user_id, template_id, context, provider)
            results.append(result)
        
        return results
    
    def send_broadcast_notification(self, template_id: str, context: Dict[str, Any],
                                 provider: Optional[str] = None) -> Dict[str, Any]:
        """Send broadcast notification to all users."""
        try:
            # Get all active users
            active_users = User.objects.filter(is_active=True).values_list('id', flat=True)
            
            # Send to all users (in batches to avoid overwhelming the system)
            batch_size = 100
            all_results = []
            
            for i in range(0, len(active_users), batch_size):
                batch_user_ids = active_users[i:i + batch_size]
                batch_results = self.send_bulk_notifications(
                    [str(uid) for uid in batch_user_ids],
                    template_id,
                    context,
                    provider
                )
                all_results.extend(batch_results)
            
            # Calculate summary
            successful = sum(1 for r in all_results if r.get('success'))
            failed = len(all_results) - successful
            skipped = sum(1 for r in all_results if r.get('skipped'))
            
            return {
                'success': True,
                'total_users': len(active_users),
                'successful': successful,
                'failed': failed,
                'skipped': skipped,
                'results': all_results
            }
            
        except Exception as e:
            self.logger.error(f"Error sending broadcast notification: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_notification(self, notification: PushNotification,
                         provider: Optional[str] = None) -> Dict[str, Any]:
        """Send notification using specified or all available providers."""
        if provider and provider in self.providers:
            # Use specific provider
            return self.providers[provider].send_notification(notification)
        elif self.providers:
            # Try all providers until one succeeds
            for provider_name, provider_instance in self.providers.items():
                result = provider_instance.send_notification(notification)
                if result.get('success'):
                    result['provider'] = provider_name
                    return result
            
            # All providers failed
            return {
                'success': False,
                'error': 'All providers failed',
                'provider_results': {
                    name: self.providers[name].send_notification(notification)
                    for name in self.providers.keys()
                }
            }
        else:
            return {
                'success': False,
                'error': 'No push notification providers configured'
            }
    
    def get_notification_templates(self) -> List[Dict[str, Any]]:
        """Get all available notification templates."""
        return [
            {
                'template_id': template.template_id,
                'title_template': template.title_template,
                'body_template': template.body_template,
                'category': template.category,
                'priority': template.priority,
                'icon': template.icon
            }
            for template in self.templates.values()
        ]
    
    def get_user_notification_history(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's notification history."""
        # In a real implementation, this would query a notification history table
        # For now, return mock data
        return [
            {
                'id': f"notif_{i}",
                'title': f"Notification {i}",
                'body': f"This is notification {i}",
                'category': 'general',
                'timestamp': (timezone.now() - timedelta(hours=i)).isoformat(),
                'read': i % 3 != 0
            }
            for i in range(min(limit, 10))
        ]


# Notification event handlers
class NotificationEventHandler:
    """Handles gamification events and sends appropriate notifications."""
    
    def __init_(self):
        self.notification_service = PushNotificationService()
        self.logger = logging.getLogger(__name__)
    
    def on_badge_earned(self, user_id: str, badge: Badge, user_badge: UserBadge) -> None:
        """Handle badge earned event."""
        try:
            context = {
                'badge_name': badge.name,
                'points_bonus': badge.points_bonus,
                'badge_rarity': badge.rarity
            }
            
            self.notification_service.send_notification(user_id, 'badge_earned', context)
            
        except Exception as e:
            self.logger.error(f"Error sending badge earned notification: {e}")
    
    def on_streak_updated(self, user_id: str, streak: Streak, was_extended: bool) -> None:
        """Handle streak updated event."""
        try:
            if was_extended:
                context = {
                    'current_days': streak.current_days
                }
                
                self.notification_service.send_notification(user_id, 'streak_updated', context)
            
            # Check if streak is expiring soon
            if streak.is_active and streak.last_activity_date == timezone.now().date() - timedelta(days=1):
                self.notification_service.send_notification(user_id, 'streak_expiring', {})
            
        except Exception as e:
            self.logger.error(f"Error sending streak notification: {e}")
    
    def on_challenge_completed(self, user_id: str, challenge: DailyChallenge,
                            user_challenge: UserDailyChallenge) -> None:
        """Handle challenge completed event."""
        try:
            context = {
                'challenge_title': challenge.title,
                'bonus_points': challenge.bonus_points
            }
            
            self.notification_service.send_notification(user_id, 'challenge_completed', context)
            
        except Exception as e:
            self.logger.error(f"Error sending challenge completed notification: {e}")
    
    def on_level_up(self, user_id: str, old_level: int, new_level: int) -> None:
        """Handle level up event."""
        try:
            # Get perks count for new level
            from api.gamification.models import LevelConfig
            level_config = LevelConfig.objects.filter(level_number=new_level).first()
            perks_count = len(level_config.perks) if level_config and level_config.perks else 0
            
            context = {
                'new_level': new_level,
                'perks_count': perks_count
            }
            
            self.notification_service.send_notification(user_id, 'level_up', context)
            
        except Exception as e:
            self.logger.error(f"Error sending level up notification: {e}")
    
    def on_achievement_earned(self, user_id: str, achievement: UserAchievement) -> None:
        """Handle achievement earned event."""
        try:
            context = {
                'achievement_type': achievement.achievement_type,
                'points_awarded': achievement.points_awarded,
                'rank': achievement.rank
            }
            
            self.notification_service.send_notification(user_id, 'achievement_earned', context)
            
        except Exception as e:
            self.logger.error(f"Error sending achievement earned notification: {e}")


# Global instances
push_notification_service = PushNotificationService()
notification_event_handler = NotificationEventHandler()


# Convenience functions
def send_push_notification(user_id: str, template_id: str,
                         context: Dict[str, Any], provider: Optional[str] = None) -> Dict[str, Any]:
    """Send a push notification."""
    return push_notification_service.send_notification(user_id, template_id, context, provider)


def send_custom_notification(notification: PushNotification,
                          provider: Optional[str] = None) -> Dict[str, Any]:
    """Send a custom push notification."""
    return push_notification_service.send_custom_notification(notification, provider)


def send_broadcast_notification(template_id: str, context: Dict[str, Any],
                             provider: Optional[str] = None) -> Dict[str, Any]:
    """Send a broadcast notification."""
    return push_notification_service.send_broadcast_notification(template_id, context, provider)


def get_user_notification_preferences(user_id: str) -> NotificationPreferences:
    """Get user's notification preferences."""
    return NotificationPreferences(user_id)


def set_notification_preference(user_id: str, category: str, enabled: bool) -> None:
    """Set a user's notification preference."""
    preferences = NotificationPreferences(user_id)
    preferences.set_preference(category, enabled)


def get_notification_templates() -> List[Dict[str, Any]]:
    """Get all available notification templates."""
    return push_notification_service.get_notification_templates()


def get_notification_history(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get user's notification history."""
    return push_notification_service.get_user_notification_history(user_id, limit)
