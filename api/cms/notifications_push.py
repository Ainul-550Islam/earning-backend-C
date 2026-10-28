# api/cms/notifications_push.py
"""Push notification management for CMS."""
from django.conf import settings
import logging
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from api.cms.abstracts import BaseService
from api.cms.monitoring import CMSMetrics
from api.cms.caching import CMSCache

logger = logging.getLogger(__name__)
User = get_user_model()


# ── Original Push Notifications (Preserved) ─────────────────────────────────────

class DeviceToken:
    """Store and manage user device push tokens."""

    @staticmethod
    def register(user, token: str, platform: str = 'fcm',
                 device_id: str = '') -> bool:
        """Register a push notification token for a user."""
        from django.core.cache import cache
        cache_key = f"push_token:{user.id}:{platform}"
        tokens = cache.get(cache_key, [])
        if token not in tokens:
            tokens.append(token)
            tokens = tokens[-10:]  # Keep last 10 tokens
            cache.set(cache_key, tokens, 86400 * 30)  # 30 days
        logger.debug(f"[Push] Token registered: user={user.id} platform={platform}")
        return True

    @staticmethod
    def get_tokens(user, platform: str = 'fcm') -> List[str]:
        from django.core.cache import cache
        cache_key = f"push_token:{user.id}:{platform}"
        return cache.get(cache_key, [])

    @staticmethod
    def unregister(user, token: str, platform: str = 'fcm') -> bool:
        from django.core.cache import cache
        cache_key = f"push_token:{user.id}:{platform}"
        tokens = cache.get(cache_key, [])
        tokens = [t for t in tokens if t != token]
        cache.set(cache_key, tokens, 86400 * 30)
        return True


class FCMPushSender:
    """Firebase Cloud Messaging push notification sender."""

    @classmethod
    def _get_server_key(cls) -> str:
        from django.conf import settings
        return getattr(settings, 'FCM_SERVER_KEY', '')

    @classmethod
    def send(cls, tokens: List[str], title: str, body: str,
              data: Dict = None, icon: str = '') -> Dict:
        """Send push notification via FCM."""
        server_key = cls._get_server_key()
        if not server_key:
            logger.debug("[Push] FCM_SERVER_KEY not configured — skipping push")
            return {'success': False, 'reason': 'not_configured'}
        if not tokens:
            return {'success': False, 'reason': 'no_tokens'}

        try:
            import urllib.request
            import json
            payload = {
                'registration_ids': tokens,
                'notification': {
                    'title': title, 'body': body,
                    'icon': icon or '/static/cms/icon-192.png',
                    'click_action': 'FLUTTER_NOTIFICATION_CLICK',
                },
                'data': data or {},
                'priority': 'high',
            }
            body_bytes = json.dumps(payload).encode()
            req = urllib.request.Request(
                'https://fcm.googleapis.com/fcm/send',
                data=body_bytes,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'key={server_key}',
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                success_count = result.get('success', 0)
                logger.debug(f"[Push] FCM sent: {success_count}/{len(tokens)} tokens")
                return {'success': True, 'sent': success_count, 'total': len(tokens)}
        except Exception as e:
            logger.warning(f"[Push] FCM send failed: {e}")
            return {'success': False, 'error': str(e)}

    @classmethod
    def send_to_user(cls, user, title: str, body: str,
                      data: Dict = None) -> Dict:
        """Send push notification to all user's devices."""
        tokens = DeviceToken.get_tokens(user)
        if not tokens:
            return {'success': False, 'reason': 'no_tokens_for_user'}
        return cls.send(tokens, title, body, data)


class CMSPushNotificationService:
    """
    High-level CMS push notification service.
    Sends typed notifications for all CMS events.
    """

    @classmethod
    def notify_reward_earned(cls, user, coins: float, source: str = 'Offer') -> bool:
        """Notify user about earned reward."""
        return cls._send(
            user=user,
            title="💰 Coins Earned!",
            body=f"You earned {coins:.0f} coins from {source}",
            data={'type': 'reward', 'coins': str(coins)},
        )

    @classmethod
    def notify_withdrawal_update(cls, user, amount_usd: float, status: str) -> bool:
        """Notify user about withdrawal status change."""
        status_messages = {
            'approved': f"✅ Withdrawal of ${amount_usd:.2f} approved!",
            'paid':     f"💸 ${amount_usd:.2f} has been sent to your account!",
            'rejected': f"❌ Withdrawal of ${amount_usd:.2f} was rejected.",
        }
        body = status_messages.get(status, f"Withdrawal update: {status}")
        return cls._send(
            user=user,
            title="Withdrawal Update",
            body=body,
            data={'type': 'withdrawal', 'status': status},
        )

    @classmethod
    def notify_streak_milestone(cls, user, days: int, title: str,
                                 bonus_coins: float) -> bool:
        """Notify user about streak milestone."""
        return cls._send(
            user=user,
            title=f"🔥 {days}-Day Streak!",
            body=f"{title} — You earned {bonus_coins:.0f} bonus coins!",
            data={'type': 'streak', 'days': str(days)},
        )

    @classmethod
    def notify_referral_bonus(cls, user, referred_username: str,
                               bonus_coins: float) -> bool:
        """Notify referrer about referral bonus."""
        return cls._send(
            user=user,
            title="👥 Referral Bonus!",
            body=f"{referred_username} completed an offer! You earned {bonus_coins:.0f} coins",
            data={'type': 'referral', 'bonus': str(bonus_coins)},
        )

    @classmethod
    def notify_level_up(cls, user, new_level: int, level_name: str) -> bool:
        """Notify user about level up."""
        return cls._send(
            user=user,
            title="⭐ Level Up!",
            body=f"Congratulations! You reached {level_name} level!",
            data={'type': 'level_up', 'level': str(new_level)},
        )

    @classmethod
    def notify_new_offer(cls, users: List[Any], offer_title: str,
                          payout_coins: float) -> int:
        """Notify multiple users about a new featured offer."""
        sent = 0
        for user in users:
            success = cls._send(
                user=user,
                title="🎯 New Offer Available!",
                body=f"{offer_title} — Earn {payout_coins:.0f} coins",
                data={'type': 'new_offer'},
            )
            if success:
                sent += 1
        return sent

    @classmethod
    def notify_streak_reminder(cls, user, current_streak: int) -> bool:
        """Remind user to maintain streak."""
        return cls._send(
            user=user,
            title="🔥 Keep Your Streak!",
            body=f"Don't break your {current_streak}-day streak! Complete an offer today.",
            data={'type': 'streak_reminder', 'streak': str(current_streak)},
        )

    @classmethod
    def _send(cls, user, title: str, body: str, data: Dict = None) -> bool:
        """Internal: send push + fallback to in-app notification."""
        # Try push
        try:
            from api.cms.feature_flags import FeatureFlags, FLAG_PUSH_NOTIFICATIONS
            if FeatureFlags.is_enabled(FLAG_PUSH_NOTIFICATIONS, user):
                result = FCMPushSender.send_to_user(user, title, body, data)
                if result.get('success'):
                    return True
        except Exception as e:
            logger.debug(f"[Push] FCM failed, falling back to in-app: {e}")

        # Fallback: in-app notification
        try:
            from api.cms.repositories import NotificationRepository
            NotificationRepository.create(
                user=user,
                notification_type=(data or {}).get('type', 'system'),
                title=title,
                message=body,
                extra_data=data or {},
            )
            return True
        except Exception as e:
            logger.warning(f"[Push] Fallback in-app also failed: {e}")
            return False


class WebPushSender:
    """
    Web Push API (VAPID) for browser push notifications.
    Used for desktop browser notifications.
    """

    @classmethod
    def send(cls, subscription: Dict, title: str, body: str,
              data: Dict = None) -> bool:
        """Send web push notification using pywebpush."""
        try:
            from pywebpush import webpush, WebPushException
            import json
            vapid_private = getattr(settings, 'VAPID_PRIVATE_KEY', '')
            vapid_email = getattr(settings, 'VAPID_CLAIMS_EMAIL', 'mailto:admin@site.com')
            if not vapid_private:
                return False
            webpush(
                subscription_info=subscription,
                data=json.dumps({'title': title, 'body': body, 'data': data or {}}),
                vapid_private_key=vapid_private,
                vapid_claims={'sub': vapid_email},
            )
            return True
        except ImportError:
            logger.debug("[Push] pywebpush not installed")
            return False
        except Exception as e:
            logger.warning(f"[Push] WebPush failed: {e}")
            return False


# ── Enhanced Push Notification Classes ─────────────────────────────────────

class BasePushNotification(BaseService):
    """Base push notification class with common functionality."""
    
    def __init__(self):
        """Initialize push notification."""
        super().__init__()
        self.metrics = CMSMetrics
        self.cache = CMSCache
    
    def validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input data."""
        return data
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute push notification."""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def send_notification(self, user_id: int, title: str, message: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send push notification to user."""
        return {
            'success': False,
            'error': 'Not implemented',
            'error_code': 'NOT_IMPLEMENTED'
        }


class EnhancedPushNotificationManager:
    """Enhanced manager for handling push notifications."""
    
    def __init__(self):
        """Initialize push notification manager."""
        self.providers = {}
        self.logger = logging.getLogger(f"{__name__}.manager")
    
    def register_provider(self, name: str, provider: BasePushNotification):
        """Register a new push notification provider."""
        self.providers[name] = provider
        logger.info(f"Push notification provider registered: {name}")
    
    def send_notification(self, user_id: int, title: str, message: str, data: Dict[str, Any] = None, provider: str = None) -> Dict[str, Any]:
        """Send push notification to user."""
        try:
            # Use original PushNotifications class as fallback
            from api.cms.repositories import NotificationRepository
            user = User.objects.get(id=user_id)
            
            # Try to send push notification using original system
            try:
                from api.cms.feature_flags import FeatureFlags, FLAG_PUSH_NOTIFICATIONS
                if FeatureFlags.is_enabled(FLAG_PUSH_NOTIFICATIONS, user):
                    result = FCMPushSender.send_to_user(user, title, message, data)
                    if result.get('success'):
                        # Record metrics
                        self.metrics.increment('push_notifications_sent')
                        return result
            except Exception as e:
                logger.debug(f"Enhanced push failed, falling back: {e}")
            
            # Fallback to in-app notification
            notification = NotificationRepository.create(
                user=user,
                notification_type=(data or {}).get('type', 'system'),
                title=title,
                message=message,
                extra_data=data or {},
            )
            
            return {
                'success': True,
                'fallback': 'in_app',
                'notification_id': notification.id,
                'message': 'Push notification failed, created in-app notification instead'
            }
            
        except User.DoesNotExist:
            return {
                'success': False,
                'error': 'User not found',
                'error_code': 'USER_NOT_FOUND'
            }
        except Exception as e:
            self.logger.error(f"Error sending push notification: {e}")
            return {
                'success': False,
                'error': 'Failed to send notification',
                'error_code': 'SEND_ERROR',
                'exception': str(e)
            }
    
    def send_bulk_notification(self, user_ids: List[int], title: str, message: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send bulk push notification to multiple users."""
        results = []
        success_count = 0
        failure_count = 0
        
        for user_id in user_ids:
            result = self.send_notification(user_id, title, message, data)
            results.append({
                'user_id': user_id,
                'result': result
            })
            
            if result.get('success'):
                success_count += 1
            else:
                failure_count += 1
        
        return {
            'success': success_count > 0,
            'total_users': len(user_ids),
            'success_count': success_count,
            'failure_count': failure_count,
            'results': results
        }
    
    def register_device(self, user_id: int, device_type: str, token: str, device_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """Register user device for push notifications."""
        try:
            user = User.objects.get(id=user_id)
            
            # Use original DeviceToken class
            platform = 'fcm' if device_type == 'android' else 'apns'
            success = DeviceToken.register(user, token, platform)
            
            if success:
                # Record metrics
                self.metrics.increment('devices_registered')
                
                logger.info(f"Device registered for user {user_id}: {device_type}")
                
                return {
                    'success': True,
                    'device': {
                        'type': device_type,
                        'platform': platform,
                        'registered_at': timezone.now().isoformat()
                    }
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to register device',
                    'error_code': 'REGISTRATION_ERROR'
                }
                
        except User.DoesNotExist:
            return {
                'success': False,
                'error': 'User not found',
                'error_code': 'USER_NOT_FOUND'
            }
        except Exception as e:
            self.logger.error(f"Error registering device: {e}")
            return {
                'success': False,
                'error': 'Failed to register device',
                'error_code': 'REGISTRATION_ERROR'
            }
    
    def get_notification_history(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get notification history for user."""
        try:
            from api.cms.repositories import NotificationRepository
            
            # Get notifications from repository
            notifications = NotificationRepository.get_by_user(user_id, limit)
            
            return [
                {
                    'id': notification.id,
                    'title': notification.title,
                    'message': notification.message,
                    'type': notification.notification_type,
                    'created_at': notification.created_at.isoformat(),
                    'is_read': notification.is_read
                }
                for notification in notifications
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting notification history: {e}")
            return []
    
    def get_provider_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get provider statistics."""
        try:
            # This would query actual notification models
            # For now, return mock data
            return {
                'period_days': days,
                'total_notifications': 0,
                'push_notifications': 0,
                'in_app_notifications': 0,
                'success_rate': 0.0
            }
            
        except Exception as e:
            self.logger.error(f"Error getting provider statistics: {e}")
            return {
                'period_days': days,
                'total_notifications': 0,
                'push_notifications': 0,
                'in_app_notifications': 0,
                'success_rate': 0.0,
                'error': str(e)
            }


# Global enhanced push notification manager
enhanced_push_notification_manager = EnhancedPushNotificationManager()
