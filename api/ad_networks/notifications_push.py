"""
api/ad_networks/notifications_push.py
Push notification system for ad networks module
SaaS-ready with tenant support
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings

from .models import Offer, UserOfferEngagement, OfferConversion, OfferReward
from .choices import OfferStatus, EngagementStatus, ConversionStatus, RewardStatus
from .constants import CACHE_TIMEOUTS
from .helpers import get_cache_key

logger = logging.getLogger(__name__)
User = get_user_model()


# ==================== NOTIFICATION TYPES ====================

class NotificationType:
    """Push notification types"""
    
    # Offer notifications
    OFFER_NEW = "offer_new"
    OFFER_UPDATED = "offer_updated"
    OFFER_EXPIRING_SOON = "offer_expiring_soon"
    OFFER_COMPLETED = "offer_completed"
    OFFER_APPROVED = "offer_approved"
    OFFER_REJECTED = "offer_rejected"
    
    # Reward notifications
    REWARD_EARNED = "reward_earned"
    REWARD_APPROVED = "reward_approved"
    REWARD_PAID = "reward_paid"
    REWARD_CANCELLED = "reward_cancelled"
    
    # System notifications
    SYSTEM_MAINTENANCE = "system_maintenance"
    SYSTEM_UPDATE = "system_update"
    SYSTEM_ALERT = "system_alert"
    
    # Achievement notifications
    ACHIEVEMENT_UNLOCKED = "achievement_unlocked"
    LEVEL_UP = "level_up"
    MILESTONE_REACHED = "milestone_reached"
    
    # Referral notifications
    REFERRAL_JOINED = "referral_joined"
    REFERRAL_EARNED = "referral_earned"
    
    # Security notifications
    SECURITY_ALERT = "security_alert"
    LOGIN_NEW_DEVICE = "login_new_device"
    ACCOUNT_SUSPENDED = "account_suspended"


# ==================== PUSH PROVIDERS ====================

class PushProvider:
    """Push notification providers"""
    
    FIREBASE = "firebase"
    APNS = "apns"  # Apple Push Notification Service
    ONE_SIGNAL = "one_signal"
    PUSHWOOSH = "pushwoosh"
    URBAN_AIRSHIP = "urban_airship"


# ==================== BASE PUSH MANAGER ====================

class BasePushManager:
    """Base push notification manager"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.cache_timeout = CACHE_TIMEOUTS.get('notifications', 3600)
    
    def _get_cache_key(self, *args, **kwargs) -> str:
        """Generate cache key"""
        return get_cache_key(self.__class__.__name__, self.tenant_id, *args, **kwargs)
    
    def _get_from_cache(self, key: str) -> Any:
        """Get data from cache"""
        return cache.get(key)
    
    def _set_cache(self, key: str, data: Any, timeout: int = None) -> None:
        """Set data in cache"""
        timeout = timeout or self.cache_timeout
        cache.set(key, data, timeout)


# ==================== FIREBASE PUSH MANAGER ====================

class FirebasePushManager(BasePushManager):
    """Firebase Cloud Messaging (FCM) push manager"""
    
    def __init__(self, tenant_id: str = 'default'):
        super().__init__(tenant_id)
        self.fcm_key = getattr(settings, 'FCM_SERVER_KEY', None)
        self.fcm_url = "https://fcm.googleapis.com/fcm/send"
    
    def send_notification(self, user_id: int, notification: Dict[str, Any],
                        data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send push notification via Firebase"""
        try:
            # Get user's FCM token
            fcm_token = self._get_user_fcm_token(user_id)
            if not fcm_token:
                return {'success': False, 'error': 'No FCM token found for user'}
            
            # Prepare notification payload
            payload = {
                'to': fcm_token,
                'notification': {
                    'title': notification.get('title', ''),
                    'body': notification.get('body', ''),
                    'icon': notification.get('icon', ''),
                    'badge': notification.get('badge', 1),
                    'sound': notification.get('sound', 'default'),
                    'click_action': notification.get('click_action', ''),
                },
                'data': data or {},
                'priority': notification.get('priority', 'high'),
                'time_to_live': notification.get('time_to_live', 2419200),  # 28 days
            }
            
            # Send to Firebase
            result = self._send_to_firebase(payload)
            
            # Log notification
            self._log_notification(user_id, notification.get('type'), result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending Firebase notification: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _get_user_fcm_token(self, user_id: int) -> Optional[str]:
        """Get user's FCM token"""
        # This would typically get from user profile or device tokens table
        # For now, return None (placeholder)
        return None
    
    def _send_to_firebase(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send notification to Firebase"""
        import requests
        
        headers = {
            'Authorization': f'key={self.fcm_key}',
            'Content-Type': 'application/json',
        }
        
        try:
            response = requests.post(
                self.fcm_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('success', 0) > 0:
                    return {
                        'success': True,
                        'message_id': result.get('results', [{}])[0].get('message_id'),
                        'response': result,
                    }
                else:
                    return {
                        'success': False,
                        'error': result.get('results', [{}])[0].get('error'),
                        'response': result,
                    }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text}',
                    'status_code': response.status_code,
                }
                
        except requests.RequestException as e:
            return {
                'success': False,
                'error': f'Request error: {str(e)}',
            }
    
    def _log_notification(self, user_id: int, notification_type: str, result: Dict[str, Any]):
        """Log notification result"""
        log_data = {
            'user_id': user_id,
            'tenant_id': self.tenant_id,
            'notification_type': notification_type,
            'success': result.get('success', False),
            'error': result.get('error'),
            'message_id': result.get('message_id'),
            'timestamp': timezone.now().isoformat(),
        }
        
        if result.get('success'):
            logger.info(f"Push notification sent: {log_data}")
        else:
            logger.error(f"Push notification failed: {log_data}")
    
    def send_bulk_notifications(self, notifications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Send bulk notifications"""
        results = []
        success_count = 0
        error_count = 0
        
        for notification in notifications:
            result = self.send_notification(
                notification['user_id'],
                notification['notification'],
                notification.get('data')
            )
            
            results.append(result)
            
            if result.get('success'):
                success_count += 1
            else:
                error_count += 1
        
        return {
            'total': len(notifications),
            'success': success_count,
            'errors': error_count,
            'results': results,
        }


# ==================== PUSH NOTIFICATION MANAGER ====================

class PushNotificationManager(BasePushManager):
    """Main push notification manager"""
    
    def __init__(self, tenant_id: str = 'default'):
        super().__init__(tenant_id)
        self.firebase_manager = FirebasePushManager(tenant_id)
        self.enabled_providers = getattr(settings, 'PUSH_PROVIDERS', [PushProvider.FIREBASE])
    
    def send_notification(self, user_id: int, notification_type: str,
                        title: str, body: str, data: Dict[str, Any] = None,
                        priority: str = 'high', **kwargs) -> Dict[str, Any]:
        """Send push notification"""
        notification_data = {
            'type': notification_type,
            'title': title,
            'body': body,
            'priority': priority,
            **kwargs
        }
        
        results = []
        
        # Send via enabled providers
        if PushProvider.FIREBASE in self.enabled_providers:
            result = self.firebase_manager.send_notification(user_id, notification_data, data)
            results.append({'provider': PushProvider.FIREBASE, 'result': result})
        
        # Add other providers as needed
        # if PushProvider.ONE_SIGNAL in self.enabled_providers:
        #     result = self.one_signal_manager.send_notification(user_id, notification_data, data)
        #     results.append({'provider': PushProvider.ONE_SIGNAL, 'result': result})
        
        # Return overall result
        success_count = sum(1 for r in results if r['result'].get('success', False))
        
        return {
            'success': success_count > 0,
            'providers_sent': len(results),
            'successful_providers': success_count,
            'results': results,
        }
    
    def send_offer_notification(self, user_id: int, offer: Offer, 
                              notification_type: str = NotificationType.OFFER_NEW) -> Dict[str, Any]:
        """Send offer-related notification"""
        if notification_type == NotificationType.OFFER_NEW:
            title = "New Offer Available!"
            body = f"Complete {offer.title} and earn {offer.reward_amount} {offer.reward_currency}"
            data = {
                'offer_id': offer.id,
                'offer_title': offer.title,
                'reward_amount': str(offer.reward_amount),
                'reward_currency': offer.reward_currency,
                'action': 'view_offer',
            }
        
        elif notification_type == NotificationType.OFFER_EXPIRING_SOON:
            title = "Offer Expiring Soon!"
            body = f"Complete {offer.title} before it expires"
            data = {
                'offer_id': offer.id,
                'offer_title': offer.title,
                'expires_at': offer.expires_at.isoformat() if offer.expires_at else None,
                'action': 'view_offer',
            }
        
        else:
            return {'success': False, 'error': 'Unknown notification type'}
        
        return self.send_notification(user_id, notification_type, title, body, data)
    
    def send_conversion_notification(self, user_id: int, conversion, 
                                   notification_type: str = NotificationType.OFFER_APPROVED) -> Dict[str, Any]:
        """Send conversion-related notification"""
        if notification_type == NotificationType.OFFER_APPROVED:
            title = "Offer Approved!"
            body = f"Your completion of {conversion.engagement.offer.title} has been approved"
            data = {
                'conversion_id': conversion.id,
                'offer_id': conversion.engagement.offer.id,
                'offer_title': conversion.engagement.offer.title,
                'payout': str(conversion.payout),
                'currency': conversion.currency,
                'action': 'view_rewards',
            }
        
        elif notification_type == NotificationType.OFFER_REJECTED:
            title = "Offer Rejected"
            body = f"Your completion of {conversion.engagement.offer.title} was not approved"
            data = {
                'conversion_id': conversion.id,
                'offer_id': conversion.engagement.offer.id,
                'offer_title': conversion.engagement.offer.title,
                'rejection_reason': conversion.rejection_reason,
                'action': 'view_details',
            }
        
        else:
            return {'success': False, 'error': 'Unknown notification type'}
        
        return self.send_notification(user_id, notification_type, title, body, data)
    
    def send_reward_notification(self, user_id: int, reward: OfferReward,
                                notification_type: str = NotificationType.REWARD_EARNED) -> Dict[str, Any]:
        """Send reward-related notification"""
        if notification_type == NotificationType.REWARD_EARNED:
            title = "Reward Earned!"
            body = f"You've earned {reward.amount} {reward.currency} from {reward.offer.title}"
            data = {
                'reward_id': reward.id,
                'offer_id': reward.offer.id,
                'offer_title': reward.offer.title,
                'amount': str(reward.amount),
                'currency': reward.currency,
                'action': 'view_rewards',
            }
        
        elif notification_type == NotificationType.REWARD_APPROVED:
            title = "Reward Approved!"
            body = f"Your reward of {reward.amount} {reward.currency} has been approved"
            data = {
                'reward_id': reward.id,
                'amount': str(reward.amount),
                'currency': reward.currency,
                'action': 'view_rewards',
            }
        
        elif notification_type == NotificationType.REWARD_PAID:
            title = "Reward Paid!"
            body = f"Your reward of {reward.amount} {reward.currency} has been paid"
            data = {
                'reward_id': reward.id,
                'amount': str(reward.amount),
                'currency': reward.currency,
                'payment_method': reward.payment_method,
                'action': 'view_rewards',
            }
        
        else:
            return {'success': False, 'error': 'Unknown notification type'}
        
        return self.send_notification(user_id, notification_type, title, body, data)
    
    def send_system_notification(self, user_ids: List[int], notification_type: str,
                                title: str, body: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send system notification to multiple users"""
        results = []
        
        for user_id in user_ids:
            result = self.send_notification(user_id, notification_type, title, body, data)
            results.append({'user_id': user_id, 'result': result})
        
        success_count = sum(1 for r in results if r['result'].get('success', False))
        
        return {
            'total_users': len(user_ids),
            'success': success_count,
            'errors': len(user_ids) - success_count,
            'results': results,
        }
    
    def send_bulk_offer_notifications(self, offer: Offer, user_ids: List[int],
                                    notification_type: str = NotificationType.OFFER_NEW) -> Dict[str, Any]:
        """Send bulk offer notifications"""
        notifications = []
        
        for user_id in user_ids:
            notifications.append({
                'user_id': user_id,
                'notification': {
                    'type': notification_type,
                    'title': "New Offer Available!",
                    'body': f"Complete {offer.title} and earn {offer.reward_amount} {offer.reward_currency}",
                    'offer_id': offer.id,
                },
                'data': {
                    'offer_id': offer.id,
                    'offer_title': offer.title,
                    'reward_amount': str(offer.reward_amount),
                    'reward_currency': offer.reward_currency,
                    'action': 'view_offer',
                }
            })
        
        return self.firebase_manager.send_bulk_notifications(notifications)


# ==================== NOTIFICATION TEMPLATES ====================

class NotificationTemplates:
    """Pre-defined notification templates"""
    
    OFFER_TEMPLATES = {
        NotificationType.OFFER_NEW: {
            'title': 'New Offer Available!',
            'body_template': 'Complete {offer_title} and earn {reward_amount} {reward_currency}',
            'data_keys': ['offer_id', 'offer_title', 'reward_amount', 'reward_currency'],
        },
        NotificationType.OFFER_EXPIRING_SOON: {
            'title': 'Offer Expiring Soon!',
            'body_template': 'Complete {offer_title} before it expires',
            'data_keys': ['offer_id', 'offer_title', 'expires_at'],
        },
        NotificationType.OFFER_COMPLETED: {
            'title': 'Offer Completed!',
            'body_template': 'Great job! You completed {offer_title}',
            'data_keys': ['offer_id', 'offer_title'],
        },
    }
    
    REWARD_TEMPLATES = {
        NotificationType.REWARD_EARNED: {
            'title': 'Reward Earned!',
            'body_template': 'You\'ve earned {amount} {currency} from {offer_title}',
            'data_keys': ['reward_id', 'offer_id', 'offer_title', 'amount', 'currency'],
        },
        NotificationType.REWARD_APPROVED: {
            'title': 'Reward Approved!',
            'body_template': 'Your reward of {amount} {currency} has been approved',
            'data_keys': ['reward_id', 'amount', 'currency'],
        },
        NotificationType.REWARD_PAID: {
            'title': 'Reward Paid!',
            'body_template': 'Your reward of {amount} {currency} has been paid',
            'data_keys': ['reward_id', 'amount', 'currency', 'payment_method'],
        },
    }
    
    SYSTEM_TEMPLATES = {
        NotificationType.SYSTEM_MAINTENANCE: {
            'title': 'System Maintenance',
            'body_template': 'The system will be under maintenance from {start_time} to {end_time}',
            'data_keys': ['start_time', 'end_time'],
        },
        NotificationType.SYSTEM_UPDATE: {
            'title': 'System Update',
            'body_template': 'New features have been added to the platform',
            'data_keys': ['version', 'features'],
        },
    }
    
    @classmethod
    def get_template(cls, notification_type: str) -> Optional[Dict[str, Any]]:
        """Get notification template"""
        if notification_type in cls.OFFER_TEMPLATES:
            return cls.OFFER_TEMPLATES[notification_type]
        elif notification_type in cls.REWARD_TEMPLATES:
            return cls.REWARD_TEMPLATES[notification_type]
        elif notification_type in cls.SYSTEM_TEMPLATES:
            return cls.SYSTEM_TEMPLATES[notification_type]
        
        return None
    
    @classmethod
    def render_template(cls, template: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Render template with data"""
        rendered = {
            'title': template['title'],
            'body': template['body_template'].format(**data),
        }
        
        # Include only specified data keys
        if 'data_keys' in template:
            filtered_data = {key: data.get(key) for key in template['data_keys']}
            rendered['data'] = filtered_data
        
        return rendered


# ==================== NOTIFICATION SCHEDULER ====================

class NotificationScheduler(BasePushManager):
    """Schedule and manage push notifications"""
    
    def __init__(self, tenant_id: str = 'default'):
        super().__init__(tenant_id)
        self.push_manager = PushNotificationManager(tenant_id)
    
    def schedule_offer_expiry_notifications(self, hours_ahead: int = 24) -> Dict[str, Any]:
        """Schedule notifications for offers expiring soon"""
        try:
            # Get offers expiring in the next X hours
            expiry_time = timezone.now() + timedelta(hours=hours_ahead)
            
            expiring_offers = Offer.objects.filter(
                tenant_id=self.tenant_id,
                status=OfferStatus.ACTIVE,
                expires_at__lte=expiry_time,
                expires_at__gt=timezone.now()
            )
            
            notifications_sent = 0
            
            for offer in expiring_offers:
                # Get users who might be interested in this offer
                interested_users = self._get_interested_users(offer)
                
                if interested_users:
                    result = self.push_manager.send_bulk_offer_notifications(
                        offer, interested_users, NotificationType.OFFER_EXPIRING_SOON
                    )
                    notifications_sent += result.get('success', 0)
            
            return {
                'offers_processed': expiring_offers.count(),
                'notifications_sent': notifications_sent,
                'hours_ahead': hours_ahead,
            }
            
        except Exception as e:
            logger.error(f"Error scheduling offer expiry notifications: {str(e)}")
            return {'error': str(e)}
    
    def _get_interested_users(self, offer: Offer, limit: int = 100) -> List[int]:
        """Get users who might be interested in an offer"""
        # This would typically use user preferences, engagement history, etc.
        # For now, return a simple implementation
        
        # Get users who have completed similar offers
        similar_offers = Offer.objects.filter(
            tenant_id=self.tenant_id,
            category=offer.category,
            status=OfferStatus.ACTIVE
        ).exclude(id=offer.id)[:10]
        
        user_ids = set()
        
        for similar_offer in similar_offers:
            users = UserOfferEngagement.objects.filter(
                tenant_id=self.tenant_id,
                offer=similar_offer,
                status=EngagementStatus.COMPLETED
            ).values_list('user_id', flat=True)[:10]
            
            user_ids.update(users)
        
        return list(user_ids)[:limit]
    
    def schedule_daily_digest(self) -> Dict[str, Any]:
        """Schedule daily digest notifications"""
        try:
            # Get users who want daily digests
            digest_users = self._get_digest_users()
            
            notifications_sent = 0
            
            for user_id in digest_users:
                # Get user's daily stats
                daily_stats = self._get_user_daily_stats(user_id)
                
                if daily_stats['total_conversions'] > 0:
                    title = "Daily Summary"
                    body = f"You completed {daily_stats['total_conversions']} offers today and earned {daily_stats['total_earned']}"
                    
                    result = self.push_manager.send_notification(
                        user_id, 'daily_digest', title, body,
                        {
                            'conversions': daily_stats['total_conversions'],
                            'earned': str(daily_stats['total_earned']),
                            'action': 'view_daily_summary',
                        }
                    )
                    
                    if result.get('success'):
                        notifications_sent += 1
            
            return {
                'users_processed': len(digest_users),
                'notifications_sent': notifications_sent,
            }
            
        except Exception as e:
            logger.error(f"Error scheduling daily digest: {str(e)}")
            return {'error': str(e)}
    
    def _get_digest_users(self) -> List[int]:
        """Get users who want daily digest notifications"""
        # This would typically check user preferences
        # For now, return empty list (placeholder)
        return []
    
    def _get_user_daily_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user's daily statistics"""
        start_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        conversions = OfferConversion.objects.filter(
            tenant_id=self.tenant_id,
            engagement__user_id=user_id,
            created_at__range=[start_date, end_date],
            status=ConversionStatus.APPROVED
        )
        
        total_conversions = conversions.count()
        total_earned = conversions.aggregate(total=Sum('payout'))['total'] or 0
        
        return {
            'total_conversions': total_conversions,
            'total_earned': total_earned,
        }


# ==================== NOTIFICATION PREFERENCES ====================

class NotificationPreferences(BasePushManager):
    """Manage user notification preferences"""
    
    def get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        """Get user's notification preferences"""
        # This would typically get from user profile or preferences table
        # For now, return default preferences
        return {
            'push_enabled': True,
            'offer_notifications': True,
            'reward_notifications': True,
            'system_notifications': True,
            'daily_digest': False,
            'quiet_hours': {
                'enabled': False,
                'start': '22:00',
                'end': '08:00',
            }
        }
    
    def update_user_preferences(self, user_id: int, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Update user's notification preferences"""
        # This would typically save to user profile or preferences table
        # For now, just return success
        return {
            'success': True,
            'preferences': preferences,
        }
    
    def should_send_notification(self, user_id: int, notification_type: str) -> bool:
        """Check if notification should be sent to user"""
        preferences = self.get_user_preferences(user_id)
        
        if not preferences.get('push_enabled', True):
            return False
        
        # Check quiet hours
        if preferences.get('quiet_hours', {}).get('enabled', False):
            current_time = timezone.now().time()
            quiet_start = datetime.strptime(preferences['quiet_hours']['start'], '%H:%M').time()
            quiet_end = datetime.strptime(preferences['quiet_hours']['end'], '%H:%M').time()
            
            if quiet_start <= current_time <= quiet_end or current_time <= quiet_end <= quiet_start:
                return False
        
        # Check notification type preferences
        if notification_type.startswith('offer_') and not preferences.get('offer_notifications', True):
            return False
        
        if notification_type.startswith('reward_') and not preferences.get('reward_notifications', True):
            return False
        
        if notification_type.startswith('system_') and not preferences.get('system_notifications', True):
            return False
        
        return True


# ==================== EXPORTS ====================

__all__ = [
    # Types and providers
    'NotificationType',
    'PushProvider',
    
    # Managers
    'BasePushManager',
    'FirebasePushManager',
    'PushNotificationManager',
    'NotificationScheduler',
    'NotificationPreferences',
    
    # Templates
    'NotificationTemplates',
]
