# api/referral/tasks/notification_tasks.py
# Celery tasks: milestone notifications, campaign alerts
# ============================================================

from celery import shared_task
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(
    name='referral.check_milestone_achievements',
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def check_milestone_achievements(self, user_id: int = None):
    """
    User(s) এর milestone achievements check করো এবং award করো।
    user_id=None → সব active referrers check করো।
    Signup বা commission event এর পরে call করা হয়।

    Schedule example (periodic):
        'referral-check-milestones': {
            'task': 'referral.check_milestone_achievements',
            'schedule': crontab(hour='*/6', minute=0),  # Every 6 hours
        }
    """
    try:
        from api.referral.services.ReferralBonusService import (
            ReferralBonusService,
        )
        from django.contrib.auth import get_user_model

        User = get_user_model()

        if user_id:
            users = User.objects.filter(id=user_id, is_active=True)
        else:
            # Active referrers only
            from api.referral.models import Referral
            referrer_ids = Referral.objects.values_list(
                'referrer_id', flat=True
            ).distinct()
            users = User.objects.filter(id__in=referrer_ids, is_active=True)

        total_awarded = 0
        users_awarded = 0

        for user in users:
            awarded = ReferralBonusService.check_and_award_milestones(user)
            if awarded:
                total_awarded += len(awarded)
                users_awarded += 1

                for bonus in awarded:
                    logger.info(
                        f"Milestone awarded: {user.username} "
                        f"milestone={bonus['milestone']} "
                        f"amount={bonus['amount']}"
                    )

        logger.info(
            f"[Task] check_milestone_achievements: "
            f"users_checked={users.count()}, "
            f"users_awarded={users_awarded}, "
            f"total_awarded={total_awarded}"
        )

        return {
            'users_awarded': users_awarded,
            'total_bonuses_awarded': total_awarded,
        }

    except Exception as exc:
        logger.error(f"[Task] check_milestone_achievements failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.send_milestone_notification',
    bind=True,
    max_retries=2,
)
def send_milestone_notification(
    self,
    user_id: int,
    milestone_value: float,
    bonus_amount: float,
    reward_type: str,
):
    """
    Milestone reach হলে user কে notify করো।
    check_milestone_achievements থেকে async call।
    """
    try:
        from django.contrib.auth import get_user_model
        from api.referral.services.ReferralNotificationService import (
            ReferralNotificationService,
        )

        User = get_user_model()
        user = User.objects.get(id=user_id)

        ReferralNotificationService.notify_milestone_reached(
            user=user,
            milestone_value=milestone_value,
            bonus_amount=bonus_amount,
            reward_type=reward_type,
        )

        return {'sent': True, 'user': user.username}

    except Exception as exc:
        logger.error(f"[Task] send_milestone_notification failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.notify_new_referral_async',
    bind=True,
    max_retries=2,
)
def notify_new_referral_async(self, referrer_id: int, new_user_id: int):
    """
    New referral signup হলে referrer কে notify করো।
    Signup flow থেকে async call।
    """
    try:
        from django.contrib.auth import get_user_model
        from api.referral.services.ReferralNotificationService import (
            ReferralNotificationService,
        )

        User = get_user_model()
        referrer = User.objects.get(id=referrer_id)
        new_user = User.objects.get(id=new_user_id)

        ReferralNotificationService.notify_new_referral(
            referrer=referrer, new_user=new_user
        )

        return {'sent': True}

    except Exception as exc:
        logger.error(f"[Task] notify_new_referral_async failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.send_weekly_referral_summary',
    bind=True,
    max_retries=2,
)
def send_weekly_referral_summary(self):
    """
    Weekly referral performance summary সব active referrers কে পাঠাও।
    প্রতি সোমবার সকালে।

    Schedule example:
        'referral-weekly-summary': {
            'task': 'referral.send_weekly_referral_summary',
            'schedule': crontab(hour=8, minute=0, day_of_week=1),  # Monday 8AM
        }
    """
    try:
        from api.referral.models import Referral, ReferralEarning
        from api.referral.services.ReferralNotificationService import (
            ReferralNotificationService,
        )
        from django.db.models import Sum, Count, Q
        from django.utils import timezone
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Last 7 days
        week_ago = timezone.now() - timedelta(days=7)

        active_referrers = Referral.objects.values_list(
            'referrer_id', flat=True
        ).distinct()

        sent = 0
        for user_id in active_referrers:
            try:
                user = User.objects.get(id=user_id, is_active=True)

                week_earnings = ReferralEarning.objects.filter(
                    referrer=user,
                    created_at__gte=week_ago,
                ).aggregate(total=Sum('amount'))['total'] or 0

                week_referrals = Referral.objects.filter(
                    referrer=user,
                    created_at__gte=week_ago,
                ).count()

                if week_earnings > 0 or week_referrals > 0:
                    ReferralNotificationService._send_notification(
                        user=user,
                        notification_type='weekly_summary',
                        title='📊 Weekly Referral Summary',
                        message=(
                            f"This week: {week_referrals} new referrals, "
                            f"৳{float(week_earnings):.2f} commission earned!"
                        ),
                        data={
                            'week_referrals': week_referrals,
                            'week_earnings': str(week_earnings),
                            'type': 'weekly_summary',
                        }
                    )
                    sent += 1

            except User.DoesNotExist:
                continue
            except Exception as e:
                logger.warning(f"Weekly summary error for user {user_id}: {e}")

        logger.info(
            f"[Task] send_weekly_referral_summary: sent={sent}"
        )

        return {'sent': sent}

    except Exception as exc:
        logger.error(f"[Task] send_weekly_referral_summary failed: {exc}")
        raise self.retry(exc=exc)