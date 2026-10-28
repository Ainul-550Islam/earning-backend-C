# api/referral/services/ReferralNotificationService.py
# Notify users on commission earned, milestone reached, contest results
# ============================================================

from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class ReferralNotificationService:
    """
    Referral event notification service।
    Commission, milestone, contest result notifications।
    In-app notification + optional push notification।
    """

    @staticmethod
    def notify_commission_earned(user, amount, level: int, from_user=None) -> bool:
        """Commission earn করলে notify করো।"""
        try:
            level_names = {1: 'Direct', 2: 'Level 2', 3: 'Level 3'}
            level_name = level_names.get(level, f'Level {level}')

            from_text = (
                f" from {from_user.username}" if from_user else ""
            )

            message = (
                f"৳{amount:.2f} {level_name} referral commission "
                f"earned{from_text}!"
            )

            ReferralNotificationService._send_notification(
                user=user,
                notification_type='referral_commission',
                title='Referral Commission Earned! 💰',
                message=message,
                data={
                    'amount': str(amount),
                    'level': level,
                    'from_user': from_user.username if from_user else None,
                    'type': 'commission',
                }
            )
            return True

        except Exception as e:
            logger.error(f"Notification error (commission): {e}")
            return False

    @staticmethod
    def notify_new_referral(referrer, new_user) -> bool:
        """কেউ referrer এর code ব্যবহার করে join করলে notify করো।"""
        try:
            ReferralNotificationService._send_notification(
                user=referrer,
                notification_type='new_referral',
                title='New Referral! 🎉',
                message=(
                    f"{new_user.username} joined using your referral link!"
                ),
                data={
                    'referred_user': new_user.username,
                    'type': 'new_referral',
                }
            )
            return True

        except Exception as e:
            logger.error(f"Notification error (new referral): {e}")
            return False

    @staticmethod
    def notify_signup_bonus(user, amount, bonus_type: str = 'referrer') -> bool:
        """Signup bonus দেওয়া হলে notify করো।"""
        try:
            if bonus_type == 'referrer':
                title = 'Referral Signup Bonus! 🎁'
                message = f"You received ৳{amount:.2f} for your referral!"
            else:
                title = 'Welcome Bonus! 🎁'
                message = f"You received ৳{amount:.2f} signup bonus!"

            ReferralNotificationService._send_notification(
                user=user,
                notification_type='signup_bonus',
                title=title,
                message=message,
                data={
                    'amount': str(amount),
                    'bonus_type': bonus_type,
                    'type': 'signup_bonus',
                }
            )
            return True

        except Exception as e:
            logger.error(f"Notification error (signup bonus): {e}")
            return False

    @staticmethod
    def notify_milestone_reached(user, milestone_value, bonus_amount, reward_type) -> bool:
        """Milestone reach করলে notify করো।"""
        try:
            if reward_type == 'cash':
                reward_text = f"৳{bonus_amount:.2f} bonus"
            elif reward_type == 'multiplier':
                reward_text = f"{bonus_amount}x commission multiplier"
            else:
                reward_text = f"{reward_type} reward"

            ReferralNotificationService._send_notification(
                user=user,
                notification_type='milestone_reached',
                title='Milestone Reached! 🏆',
                message=(
                    f"You reached {milestone_value} referrals! "
                    f"Reward: {reward_text}"
                ),
                data={
                    'milestone_value': str(milestone_value),
                    'bonus_amount': str(bonus_amount),
                    'reward_type': reward_type,
                    'type': 'milestone',
                }
            )
            return True

        except Exception as e:
            logger.error(f"Notification error (milestone): {e}")
            return False

    @staticmethod
    def notify_contest_rank_update(user, contest_title, rank, total_participants) -> bool:
        """Contest rank update হলে notify করো।"""
        try:
            if rank == 1:
                emoji = '🥇'
            elif rank == 2:
                emoji = '🥈'
            elif rank == 3:
                emoji = '🥉'
            else:
                emoji = '📊'

            ReferralNotificationService._send_notification(
                user=user,
                notification_type='contest_rank_update',
                title=f'{emoji} Contest Rank Update',
                message=(
                    f"You are ranked #{rank} out of "
                    f"{total_participants} in {contest_title}!"
                ),
                data={
                    'contest_title': contest_title,
                    'rank': rank,
                    'total_participants': total_participants,
                    'type': 'contest_rank',
                }
            )
            return True

        except Exception as e:
            logger.error(f"Notification error (contest rank): {e}")
            return False

    @staticmethod
    def notify_contest_prize(user, contest_title, rank, prize_amount, prize_type) -> bool:
        """Contest prize জিতলে notify করো।"""
        try:
            if prize_type == 'cash':
                prize_text = f"৳{prize_amount:.2f}"
            else:
                prize_text = f"{prize_type}: {prize_amount}"

            ReferralNotificationService._send_notification(
                user=user,
                notification_type='contest_prize',
                title='Contest Prize Won! 🎊',
                message=(
                    f"You won {prize_text} for finishing "
                    f"Rank #{rank} in {contest_title}!"
                ),
                data={
                    'contest_title': contest_title,
                    'rank': rank,
                    'prize_amount': str(prize_amount),
                    'prize_type': prize_type,
                    'type': 'contest_prize',
                }
            )
            return True

        except Exception as e:
            logger.error(f"Notification error (contest prize): {e}")
            return False

    @staticmethod
    def notify_commission_held(user, amount, hold_days: int) -> bool:
        """Commission hold হলে notify করো।"""
        try:
            from django.utils import timezone
            release_date = (
                timezone.now() + timedelta(days=hold_days)
            ).strftime('%B %d, %Y')

            ReferralNotificationService._send_notification(
                user=user,
                notification_type='commission_held',
                title='Commission On Hold ⏳',
                message=(
                    f"৳{amount:.2f} commission is on hold. "
                    f"It will be released on {release_date}."
                ),
                data={
                    'amount': str(amount),
                    'hold_days': hold_days,
                    'release_date': release_date,
                    'type': 'commission_held',
                }
            )
            return True

        except Exception as e:
            logger.error(f"Notification error (commission held): {e}")
            return False

    @staticmethod
    def notify_commission_released(user, amount) -> bool:
        """Held commission release হলে notify করো।"""
        try:
            ReferralNotificationService._send_notification(
                user=user,
                notification_type='commission_released',
                title='Commission Released! ✅',
                message=f"৳{amount:.2f} referral commission has been released to your wallet!",
                data={
                    'amount': str(amount),
                    'type': 'commission_released',
                }
            )
            return True

        except Exception as e:
            logger.error(f"Notification error (commission released): {e}")
            return False

    @staticmethod
    def notify_campaign_started(user, campaign_name, multiplier) -> bool:
        """New campaign শুরু হলে notify করো।"""
        try:
            ReferralNotificationService._send_notification(
                user=user,
                notification_type='campaign_started',
                title='🚀 New Referral Campaign!',
                message=(
                    f"'{campaign_name}' campaign is now active! "
                    f"Earn {multiplier}x commission on all referrals!"
                ),
                data={
                    'campaign_name': campaign_name,
                    'multiplier': str(multiplier),
                    'type': 'campaign_started',
                }
            )
            return True

        except Exception as e:
            logger.error(f"Notification error (campaign): {e}")
            return False

    @staticmethod
    def _send_notification(
        user,
        notification_type: str,
        title: str,
        message: str,
        data: dict = None,
    ):
        """
        Internal notification sender।
        Project এর notification system এ integrate করো।
        """
        try:
            # Use project's actual NotificationService
            from api.notifications.services import NotificationService
            ns = NotificationService()
            ns.create_notification(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                priority='medium',
                channel='in_app',
            )
        except ImportError:
            # Fallback: log only
            logger.info(
                f"[NOTIFICATION] {user.username}: {title} — {message}"
            )
        except Exception as e:
            logger.warning(f"Notification send failed: {e}")

    @staticmethod
    def bulk_notify_campaign(campaign_id: int) -> dict:
        """
        Active referrers কে campaign শুরু হওয়ার notification দাও।
        Celery task দিয়ে call করা হয়।
        """
        from api.referral.models import ReferralCampaign, Referral
        from django.contrib.auth import get_user_model

        User = get_user_model()

        try:
            campaign = ReferralCampaign.objects.get(id=campaign_id)
        except ReferralCampaign.DoesNotExist:
            return {'success': False, 'error': 'Campaign not found'}

        # Active referrers (who have at least 1 referral)
        referrer_ids = Referral.objects.values_list(
            'referrer_id', flat=True
        ).distinct()

        users = User.objects.filter(id__in=referrer_ids, is_active=True)

        notified = 0
        for user in users:
            result = ReferralNotificationService.notify_campaign_started(
                user=user,
                campaign_name=campaign.name,
                multiplier=float(campaign.bonus_multiplier),
            )
            if result:
                notified += 1

        logger.info(
            f"Campaign notification sent to {notified} users: {campaign.name}"
        )
        return {'success': True, 'notified': notified}