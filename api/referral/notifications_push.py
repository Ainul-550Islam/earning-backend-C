# api/referral/notifications_push.py
# Push notification system for referral events
# Sends push notifications via FCM, APNS, Web Push
# Integrates with api/notifications/ module
# ============================================================

import logging
from decimal import Decimal
from typing import Dict, List, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Notification Templates ────────────────────────────────────────────────────

TEMPLATES = {
    'commission_paid': {
        'title':   '💰 Referral Commission!',
        'body':    'You earned ৳{amount} (Level {level}) from {username}',
        'icon':    'commission',
        'sound':   'cash',
        'priority':'high',
    },
    'new_referral': {
        'title':   '🎉 New Referral!',
        'body':    '{username} joined using your referral code',
        'icon':    'people',
        'sound':   'default',
        'priority':'normal',
    },
    'milestone_reached': {
        'title':   '🏆 Milestone Reached!',
        'body':    'You reached {milestone} referrals! Bonus: ৳{bonus}',
        'icon':    'trophy',
        'sound':   'achievement',
        'priority':'high',
    },
    'commission_held': {
        'title':   '⏳ Commission On Hold',
        'body':    '৳{amount} will be released in {days} days',
        'icon':    'clock',
        'sound':   'default',
        'priority':'normal',
    },
    'commission_released': {
        'title':   '✅ Commission Released!',
        'body':    '৳{amount} has been added to your wallet',
        'icon':    'wallet',
        'sound':   'cash',
        'priority':'high',
    },
    'campaign_started': {
        'title':   '🚀 New Campaign Live!',
        'body':    '{name}: {multiplier}x commission bonus is now active!',
        'icon':    'campaign',
        'sound':   'notification',
        'priority':'normal',
    },
    'contest_rank': {
        'title':   '📊 Leaderboard Update',
        'body':    'You are now ranked #{rank} in the {period} contest',
        'icon':    'leaderboard',
        'sound':   'default',
        'priority':'normal',
    },
    'contest_prize': {
        'title':   '🥇 You Won a Prize!',
        'body':    'Congratulations! You won ৳{amount} in the {contest} contest',
        'icon':    'prize',
        'sound':   'achievement',
        'priority':'high',
    },
    'fraud_alert': {
        'title':   '⚠️ Account Notice',
        'body':    'A referral in your network has been flagged for review',
        'icon':    'warning',
        'sound':   'alert',
        'priority':'high',
    },
    'streak_bonus': {
        'title':   '🔥 Streak Bonus!',
        'body':    'You have a {days}-day streak! Enjoy {multiplier}x commissions',
        'icon':    'fire',
        'sound':   'achievement',
        'priority':'normal',
    },
    'tier_upgraded': {
        'title':   '⬆️ Tier Upgrade!',
        'body':    'Congratulations! You are now a {tier} affiliate',
        'icon':    'tier',
        'sound':   'achievement',
        'priority':'high',
    },
    'weekly_summary': {
        'title':   '📈 Weekly Referral Summary',
        'body':    'This week: {referrals} new referrals, ৳{commission} earned',
        'icon':    'chart',
        'sound':   'default',
        'priority':'low',
    },
}


class ReferralPushNotificationService:
    """
    Push notification service for referral events.
    Integrates with api/notifications/services.py for delivery.
    """

    @staticmethod
    def send(user, template_name: str, data: Dict = None, channels: List[str] = None) -> bool:
        """
        Send a push notification to a user.

        Args:
            user:          Recipient user
            template_name: Key from TEMPLATES dict
            data:          Template variable substitutions
            channels:      List of channels: ['push', 'in_app', 'email']
        """
        template = TEMPLATES.get(template_name)
        if not template:
            logger.warning(f'[PushNotif] Unknown template: {template_name}')
            return False

        data = data or {}
        channels = channels or ['push', 'in_app']

        try:
            title = template['title'].format(**data)
            body  = template['body'].format(**data)
        except KeyError as e:
            logger.warning(f'[PushNotif] Template {template_name} missing key: {e}')
            title = template['title']
            body  = template['body']

        # Check user push preferences
        if not ReferralPushNotificationService._should_send(user, template_name):
            return False

        sent_any = False
        for channel in channels:
            if channel == 'in_app':
                sent_any |= ReferralPushNotificationService._send_in_app(
                    user, title, body, template_name, data
                )
            elif channel == 'push':
                sent_any |= ReferralPushNotificationService._send_push(
                    user, title, body, template.get('priority', 'normal'), data
                )
            elif channel == 'email' and template.get('send_email', False):
                sent_any |= ReferralPushNotificationService._send_email(
                    user, title, body, data
                )

        return sent_any

    @staticmethod
    def send_commission_paid(user, amount: Decimal, level: int, from_username: str) -> bool:
        return ReferralPushNotificationService.send(
            user=user,
            template_name='commission_paid',
            data={'amount': f'{float(amount):.2f}', 'level': level, 'username': from_username},
        )

    @staticmethod
    def send_new_referral(user, referred_username: str) -> bool:
        return ReferralPushNotificationService.send(
            user=user,
            template_name='new_referral',
            data={'username': referred_username},
        )

    @staticmethod
    def send_milestone_reached(user, milestone: int, bonus: Decimal) -> bool:
        return ReferralPushNotificationService.send(
            user=user,
            template_name='milestone_reached',
            data={'milestone': milestone, 'bonus': f'{float(bonus):.2f}'},
        )

    @staticmethod
    def send_commission_held(user, amount: Decimal, days: int) -> bool:
        return ReferralPushNotificationService.send(
            user=user,
            template_name='commission_held',
            data={'amount': f'{float(amount):.2f}', 'days': days},
            channels=['in_app'],
        )

    @staticmethod
    def send_commission_released(user, amount: Decimal) -> bool:
        return ReferralPushNotificationService.send(
            user=user,
            template_name='commission_released',
            data={'amount': f'{float(amount):.2f}'},
        )

    @staticmethod
    def send_tier_upgraded(user, new_tier: str) -> bool:
        return ReferralPushNotificationService.send(
            user=user,
            template_name='tier_upgraded',
            data={'tier': new_tier.title()},
        )

    @staticmethod
    def send_streak_bonus(user, streak_days: int, multiplier: float) -> bool:
        return ReferralPushNotificationService.send(
            user=user,
            template_name='streak_bonus',
            data={'days': streak_days, 'multiplier': f'{multiplier:.1f}'},
        )

    @staticmethod
    def send_weekly_summary(user, referrals: int, commission: Decimal) -> bool:
        return ReferralPushNotificationService.send(
            user=user,
            template_name='weekly_summary',
            data={'referrals': referrals, 'commission': f'{float(commission):.2f}'},
            channels=['in_app', 'push'],
        )

    @staticmethod
    def send_bulk(users, template_name: str, data: Dict = None) -> Dict:
        """Send notification to multiple users."""
        sent = 0
        failed = 0
        for user in users:
            if ReferralPushNotificationService.send(user, template_name, data):
                sent += 1
            else:
                failed += 1
        return {'sent': sent, 'failed': failed}

    # ── Private Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _should_send(user, notification_type: str) -> bool:
        """Check user's notification preferences."""
        try:
            from api.referral.models import UserPayoutPreference
            pref = UserPayoutPreference.objects.filter(user=user).first()
            if not pref:
                return True

            type_pref_map = {
                'commission_paid':     pref.notify_on_commission,
                'commission_held':     pref.notify_on_commission,
                'commission_released': pref.notify_on_commission,
                'milestone_reached':   pref.notify_on_milestone,
                'weekly_summary':      pref.notify_weekly_summary,
            }
            return type_pref_map.get(notification_type, True)
        except Exception:
            return True

    @staticmethod
    def _send_in_app(user, title: str, body: str,
                     notification_type: str, data: Dict) -> bool:
        try:
            from api.notifications.services import NotificationService
            ns = NotificationService()
            ns.create_notification(
                user=user,
                title=title,
                message=body,
                notification_type=f'referral_{notification_type}',
                priority='medium',
                channel='in_app',
            )
            return True
        except Exception as e:
            logger.debug(f'[PushNotif] in_app failed: {e}')
            return False

    @staticmethod
    def _send_push(user, title: str, body: str,
                   priority: str, data: Dict) -> bool:
        """Send via FCM/Firebase through project's notification system."""
        try:
            from api.notifications.services import NotificationService
            ns = NotificationService()
            ns.create_notification(
                user=user,
                title=title,
                message=body,
                notification_type='referral_push',
                priority=priority,
                channel='push',
            )
            return True
        except Exception as e:
            logger.debug(f'[PushNotif] push failed: {e}')
            return False

    @staticmethod
    def _send_email(user, title: str, body: str, data: Dict) -> bool:
        try:
            from django.core.mail import send_mail
            from django.conf import settings as s
            send_mail(
                subject=title,
                message=body,
                from_email=getattr(s, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                recipient_list=[user.email],
                fail_silently=True,
            )
            return True
        except Exception:
            return False