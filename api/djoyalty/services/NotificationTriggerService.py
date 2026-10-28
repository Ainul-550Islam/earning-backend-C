# api/djoyalty/services/NotificationTriggerService.py
"""
NotificationTriggerService -- loyalty events এ notifications trigger করো।
"""
import logging
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class NotificationTriggerService:

    @staticmethod
    def trigger_tier_upgrade(customer, from_tier: str, to_tier: str, tenant=None):
        """Tier upgrade notification।"""
        try:
            from ..models.advanced import LoyaltyNotification
            LoyaltyNotification.objects.create(
                customer=customer,
                tenant=tenant or customer.tenant,
                notification_type='tier_up',
                title=f'🎉 Congratulations! You reached {to_tier.title()} tier!',
                message=f'You\'ve been upgraded from {from_tier.title()} to {to_tier.title()} tier. Enjoy your new benefits!',
                channel='in_app',
                is_sent=False,
            )
            logger.info('NotificationTriggerService: tier_up for %s -> %s', customer.code, to_tier)
        except Exception as e:
            logger.error('NotificationTriggerService.trigger_tier_upgrade error: %s', e)

    @staticmethod
    def trigger_tier_downgrade(customer, from_tier: str, to_tier: str, tenant=None):
        """Tier downgrade notification।"""
        try:
            from ..models.advanced import LoyaltyNotification
            LoyaltyNotification.objects.create(
                customer=customer,
                tenant=tenant or customer.tenant,
                notification_type='tier_down',
                title=f'Tier Update',
                message=f'Your tier has been updated to {to_tier.title()}. Keep earning to upgrade!',
                channel='in_app',
                is_sent=False,
            )
        except Exception as e:
            logger.error('NotificationTriggerService.trigger_tier_downgrade error: %s', e)

    @staticmethod
    def trigger_badge_unlocked(customer, badge_name: str, points_reward=None, tenant=None):
        """Badge unlock notification।"""
        try:
            from ..models.advanced import LoyaltyNotification
            msg = f'You\'ve unlocked the "{badge_name}" badge!'
            if points_reward and points_reward > 0:
                msg += f' +{points_reward} bonus points awarded.'
            LoyaltyNotification.objects.create(
                customer=customer,
                tenant=tenant or customer.tenant,
                notification_type='badge',
                title=f'🏅 Badge Unlocked: {badge_name}',
                message=msg,
                channel='in_app',
                is_sent=False,
            )
        except Exception as e:
            logger.error('NotificationTriggerService.trigger_badge_unlocked error: %s', e)

    @staticmethod
    def trigger_streak_milestone(customer, milestone_days: int, points_awarded=None, tenant=None):
        """Streak milestone notification।"""
        try:
            from ..models.advanced import LoyaltyNotification
            msg = f'Amazing! You\'ve maintained a {milestone_days}-day activity streak!'
            if points_awarded and points_awarded > 0:
                msg += f' +{points_awarded} bonus points!'
            LoyaltyNotification.objects.create(
                customer=customer,
                tenant=tenant or customer.tenant,
                notification_type='streak',
                title=f'🔥 {milestone_days}-Day Streak!',
                message=msg,
                channel='in_app',
                is_sent=False,
            )
        except Exception as e:
            logger.error('NotificationTriggerService.trigger_streak_milestone error: %s', e)

    @staticmethod
    def trigger_points_expiry_warning(customer, points_expiring, days_left: int, tenant=None):
        """Points expiry warning notification।"""
        try:
            from ..models.advanced import LoyaltyNotification
            LoyaltyNotification.objects.create(
                customer=customer,
                tenant=tenant or customer.tenant,
                notification_type='expiry',
                title='⚠️ Points Expiring Soon',
                message=f'{points_expiring} points will expire in {days_left} days. Use them before they\'re gone!',
                channel='in_app',
                is_sent=False,
                scheduled_at=timezone.now(),
            )
        except Exception as e:
            logger.error('NotificationTriggerService.trigger_points_expiry_warning error: %s', e)

    @staticmethod
    def trigger_challenge_completed(customer, challenge_name: str, points_reward=None, tenant=None):
        """Challenge completion notification।"""
        try:
            from ..models.advanced import LoyaltyNotification
            msg = f'You\'ve completed the "{challenge_name}" challenge!'
            if points_reward and points_reward > 0:
                msg += f' +{points_reward} points earned!'
            LoyaltyNotification.objects.create(
                customer=customer,
                tenant=tenant or customer.tenant,
                notification_type='challenge',
                title='✅ Challenge Completed!',
                message=msg,
                channel='in_app',
                is_sent=False,
            )
        except Exception as e:
            logger.error('NotificationTriggerService.trigger_challenge_completed error: %s', e)

    @staticmethod
    def send_bulk_notification(customer_ids: list, title: str, message: str,
                               notification_type: str = 'general', channel: str = 'in_app', tenant=None):
        """Bulk notification to multiple customers।"""
        from ..models.advanced import LoyaltyNotification
        from ..models.core import Customer
        count = 0
        for customer in Customer.objects.filter(id__in=customer_ids, is_active=True):
            try:
                LoyaltyNotification.objects.create(
                    customer=customer,
                    tenant=tenant or customer.tenant,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    channel=channel,
                    is_sent=False,
                )
                count += 1
            except Exception as e:
                logger.error('Bulk notification error for customer %s: %s', customer.id, e)
        logger.info('NotificationTriggerService.send_bulk_notification: sent to %d customers', count)
        return count
