# api/cms/services_new/NotificationService.py
"""
NotificationService: Create, send, manage in-app and push notifications.
CPAlead earning pattern: auto-notify on reward, withdrawal, milestone.
"""
import logging
from typing import List, Dict, Optional, Any

from django.db.models import Q, F
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing user notifications."""

    # ── Create Notifications ──────────────────────────────────────

    @staticmethod
    def notify_user(
        user,
        notification_type: str,
        title: str,
        message: str,
        reward_amount=None,
        reward_currency: str = 'USD',
        source_type: str = '',
        source_id: int = None,
        action_url: str = '',
        action_text: str = '',
        metadata: dict = None
    ):
        """Create an in-app notification for a user."""
        from api.cms.models_new.extras import Notification
        try:
            notif = Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                reward_amount=reward_amount,
                reward_currency=reward_currency if reward_amount else '',
                source_type=source_type,
                source_id=source_id,
                action_url=action_url,
                action_text=action_text,
                metadata=metadata or {},
            )
            # Invalidate unread cache
            cache.delete(f'notif_unread_{user.id}')
            logger.debug(f"Created notification for user {user.id}: {notification_type}")
            return notif
        except Exception as e:
            logger.error(f"Error creating notification: {e}", exc_info=True)
            return None

    @staticmethod
    def notify_reward(user, amount, currency='USD', source_type='', source_id=None, description=''):
        """Notify user of a reward — CPAlead earning pattern."""
        from api.cms.models_new.extras import Notification
        title = f"💰 You earned {currency} {amount}!"
        message = description or f"Your reward of {currency} {amount} has been credited."
        return NotificationService.notify_user(
            user=user,
            notification_type='reward',
            title=title,
            message=message,
            reward_amount=amount,
            reward_currency=currency,
            source_type=source_type,
            source_id=source_id,
            action_url='/wallet/',
            action_text='View Wallet',
        )

    @staticmethod
    def notify_banner_reward(user, banner, amount, currency='USD'):
        """Notify user of banner click reward."""
        return NotificationService.notify_user(
            user=user,
            notification_type='banner_reward',
            title=f"🎯 Banner reward: {currency} {amount}",
            message=f"You earned {currency} {amount} for clicking '{banner.name}'.",
            reward_amount=amount,
            reward_currency=currency,
            source_type='Banner',
            source_id=banner.id,
        )

    @staticmethod
    def notify_offer_completed(user, offer_name, amount, currency='USD'):
        """Notify user of offer completion reward."""
        return NotificationService.notify_user(
            user=user,
            notification_type='offer_reward',
            title=f"✅ Offer completed!",
            message=f"You earned {currency} {amount} for completing '{offer_name}'.",
            reward_amount=amount,
            reward_currency=currency,
            source_type='Offer',
        )

    @staticmethod
    def notify_withdrawal(user, amount, currency='USD', status='requested'):
        """Notify user about withdrawal status."""
        type_map = {
            'requested': ('withdrawal', f"💸 Withdrawal of {currency} {amount} requested"),
            'approved': ('withdrawal', f"✅ Withdrawal of {currency} {amount} approved!"),
            'rejected': ('withdrawal', f"❌ Withdrawal of {currency} {amount} rejected"),
        }
        notif_type, title = type_map.get(status, ('withdrawal', 'Withdrawal Update'))
        messages = {
            'requested': f"Your withdrawal request of {currency} {amount} is being processed.",
            'approved': f"Your withdrawal of {currency} {amount} has been approved and is on its way!",
            'rejected': f"Your withdrawal of {currency} {amount} was rejected. Please contact support.",
        }
        return NotificationService.notify_user(
            user=user,
            notification_type=notif_type,
            title=title,
            message=messages.get(status, ''),
            action_url='/wallet/',
            action_text='View Wallet',
        )

    @staticmethod
    def notify_milestone(user, milestone_name: str, reward_amount=None, currency='USD'):
        """Notify user of milestone achievement."""
        return NotificationService.notify_user(
            user=user,
            notification_type='milestone',
            title=f"🏆 Milestone: {milestone_name}",
            message=f"Congratulations! You've achieved: {milestone_name}",
            reward_amount=reward_amount,
            reward_currency=currency,
            action_url='/profile/',
            action_text='View Profile',
        )

    @staticmethod
    def notify_referral_bonus(user, referred_username: str, amount, currency='USD'):
        """Notify user of referral bonus."""
        return NotificationService.notify_user(
            user=user,
            notification_type='referral_bonus',
            title=f"👥 Referral bonus: {currency} {amount}",
            message=f"You earned {currency} {amount} because {referred_username} joined using your referral!",
            reward_amount=amount,
            reward_currency=currency,
        )

    @staticmethod
    def broadcast_announcement(announcement, user_ids: List[int] = None):
        """Send announcement notification to all users or specific users."""
        from api.cms.models_new.extras import Notification
        try:
            if user_ids is None:
                # Get all active users
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user_ids = list(User.objects.filter(is_active=True).values_list('id', flat=True)[:5000])

            Notification.bulk_create_for_users(
                user_ids=user_ids,
                notification_type='system',
                title=announcement.title,
                message=announcement.message,
                source_type='Announcement',
                source_id=announcement.id,
            )
            logger.info(f"Broadcast announcement {announcement.id} to {len(user_ids)} users")
            return len(user_ids)
        except Exception as e:
            logger.error(f"Error broadcasting announcement: {e}", exc_info=True)
            return 0

    # ── Read / Manage ─────────────────────────────────────────────

    @staticmethod
    def get_user_notifications(user, unread_only: bool = False, limit: int = 20, offset: int = 0):
        """Get notifications for a user."""
        from api.cms.models_new.extras import Notification
        qs = Notification.objects.filter(user=user, is_active=True)
        if unread_only:
            qs = qs.filter(is_read=False)
        return list(qs.order_by('-created_at')[offset:offset + limit])

    @staticmethod
    def get_unread_count(user) -> int:
        """Get unread notification count for user."""
        from api.cms.models_new.extras import Notification
        return Notification.get_unread_count(user)

    @staticmethod
    def mark_read(notification_id: int, user) -> bool:
        """Mark a notification as read."""
        from api.cms.models_new.extras import Notification
        try:
            notif = Notification.objects.get(id=notification_id, user=user)
            notif.mark_read()
            cache.delete(f'notif_unread_{user.id}')
            return True
        except Notification.DoesNotExist:
            return False

    @staticmethod
    def mark_all_read(user) -> int:
        """Mark all notifications as read for a user."""
        from api.cms.models_new.extras import Notification
        count = Notification.objects.filter(user=user, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        cache.delete(f'notif_unread_{user.id}')
        return count

    @staticmethod
    def delete_old_notifications(days: int = 90) -> int:
        """Delete old read notifications."""
        from api.cms.models_new.extras import Notification
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = Notification.objects.filter(
            is_read=True, created_at__lt=cutoff
        ).delete()
        logger.info(f"Deleted {deleted} old notifications")
        return deleted

    # ── Templates ─────────────────────────────────────────────────

    @staticmethod
    def notify_from_template(user, template_name: str, context: dict):
        """Create notification from a template."""
        from api.cms.models_new.extras import NotificationTemplate
        try:
            template = NotificationTemplate.objects.get(name=template_name, is_active=True)
            title, message = template.render(context)
            return NotificationService.notify_user(
                user=user,
                notification_type=template.notification_type,
                title=title,
                message=message,
                icon=template.icon,
            )
        except NotificationTemplate.DoesNotExist:
            logger.warning(f"Notification template not found: {template_name}")
            return None
        except Exception as e:
            logger.error(f"Error creating notification from template: {e}", exc_info=True)
            return None
