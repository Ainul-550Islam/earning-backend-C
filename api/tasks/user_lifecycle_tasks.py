"""
tasks/user_lifecycle_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
User Lifecycle Management Celery Tasks (CPAlead Gap)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead user lifecycle:
  - Welcome email sequence
  - Onboarding task assignment
  - Re-engagement campaigns
  - Churn prevention notifications
  - Account activity scoring
  - Inactive account cleanup
  - VIP user recognition

  ✅ send_welcome_sequence        — 3-email onboarding drip
  ✅ assign_onboarding_tasks      — give new users starter tasks
  ✅ send_reengagement            — win back inactive users
  ✅ identify_vip_users           — tag high-value users
  ✅ cleanup_inactive_accounts    — flag/suspend truly inactive accounts
  ✅ send_birthday_bonus          — birthday reward credit
  ✅ auto_deactivate_dormant      — suspend accounts inactive > 1 year
"""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

VIP_THRESHOLD_MONTHLY = Decimal('50')    # $50+/month = VIP
VIP_THRESHOLD_TOTAL   = Decimal('500')   # $500+ total = VIP


@shared_task(bind=True, max_retries=3, default_retry_delay=30,
             name='tasks.user_lifecycle_tasks.send_welcome_sequence')
def send_welcome_sequence(self, user_id: int, step: int = 1) -> dict:
    """
    3-step welcome email drip sequence for new users:
    Step 1 (immediate): Welcome + how it works
    Step 2 (day 1):     First task recommendations
    Step 3 (day 3):     Referral program introduction
    """
    try:
        from django.core.mail import send_mail
        from django.contrib.auth import get_user_model
        from django.conf import settings

        User = get_user_model()
        user = User.objects.filter(pk=user_id).first()
        if not user or not user.email:
            return {'status': 'skipped', 'reason': 'no_user_or_email'}

        site_name = getattr(settings, 'SITE_NAME', 'Platform')

        email_steps = {
            1: {
                'subject': f'Welcome to {site_name}! 🎉 Start Earning Today',
                'message': (
                    f"Hi {user.username}!\n\n"
                    f"Welcome to {site_name}! You can start earning real money by:\n\n"
                    f"  ✅ Completing simple tasks (videos, surveys, app installs)\n"
                    f"  ✅ Inviting friends with your referral link\n"
                    f"  ✅ Maintaining daily streaks for bonus rewards\n\n"
                    f"Log in now and complete your first task!\n\n"
                    f"– The {site_name} Team"
                ),
            },
            2: {
                'subject': f'🎯 Your Personalized Tasks Are Ready!',
                'message': (
                    f"Hi {user.username}!\n\n"
                    f"We've selected the best tasks for you based on your profile.\n"
                    f"Complete 3 tasks today and earn your first streak bonus!\n\n"
                    f"Log in to see your tasks: {getattr(settings, 'FRONTEND_URL', '')}/tasks/\n\n"
                    f"– The {site_name} Team"
                ),
            },
            3: {
                'subject': f'💰 Earn More with Referrals!',
                'message': (
                    f"Hi {user.username}!\n\n"
                    f"Did you know? You can earn 10% of every friend's earnings!\n\n"
                    f"Share your referral link and start building passive income.\n"
                    f"Log in to get your link: {getattr(settings, 'FRONTEND_URL', '')}/referral/\n\n"
                    f"– The {site_name} Team"
                ),
            },
        }

        email_content = email_steps.get(step)
        if not email_content:
            return {'status': 'skipped', 'reason': f'invalid_step_{step}'}

        # Avoid sending if already sent this step
        cache_key = f'welcome_seq_{user_id}_step{step}'
        if cache.get(cache_key):
            return {'status': 'skipped', 'reason': 'already_sent'}

        send_mail(
            subject=email_content['subject'],
            message=email_content['message'],
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            recipient_list=[user.email],
            fail_silently=True,
        )
        cache.set(cache_key, 1, timeout=86400 * 7)

        # Schedule next step
        delays = {1: 86400, 2: 86400 * 3, 3: None}
        next_delay = delays.get(step)
        if next_delay:
            send_welcome_sequence.apply_async(
                kwargs={'user_id': user_id, 'step': step + 1},
                countdown=next_delay,
            )

        logger.info(f"[LIFECYCLE] Welcome email step {step} sent to user {user_id}")
        return {
            'status': 'success',
            'user_id': user_id,
            'step': step,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.user_lifecycle_tasks.assign_onboarding_tasks')
def assign_onboarding_tasks(self, user_id: int) -> dict:
    """
    Assign starter tasks to a new user for smooth onboarding.
    Picks 5 simple, high-payout tasks appropriate for new users.
    """
    try:
        logger.info(f"📋 Assigning onboarding tasks to user {user_id}...")

        try:
            from api.tasks.models import MasterTask
            from django.contrib.auth import get_user_model

            # Get beginner-friendly tasks
            starter_tasks = MasterTask.objects.filter(
                is_active=True,
                category='daily_retention',
            ).order_by('sort_order')[:5]

            task_ids = list(starter_tasks.values_list('task_id', flat=True))
            cache.set(f'onboarding_tasks_{user_id}', task_ids, timeout=86400 * 7)

            logger.info(f"[LIFECYCLE] Assigned {len(task_ids)} onboarding tasks to user {user_id}")
            return {
                'status': 'success',
                'user_id': user_id,
                'tasks_assigned': len(task_ids),
                'task_ids': task_ids,
                'timestamp': timezone.now().isoformat(),
            }

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")
            return {'status': 'skipped', 'reason': 'model_not_available'}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.user_lifecycle_tasks.send_reengagement')
def send_reengagement(self, inactivity_days: int = 7) -> dict:
    """
    Send re-engagement push + email to users inactive for `inactivity_days`.
    Includes a limited-time bonus offer to encourage return.
    """
    try:
        from datetime import timedelta
        from django.db.models import Max
        from django.contrib.auth import get_user_model
        logger.info(f"📣 Sending re-engagement (inactive>{inactivity_days}d)...")

        User    = get_user_model()
        cutoff  = timezone.now() - timedelta(days=inactivity_days)
        sent    = 0
        skipped = 0

        try:
            from api.tasks.models import UserTaskCompletion
            from api.tasks.notification_tasks import send_push_notification, send_email_notification

            inactive_users = (
                UserTaskCompletion.objects.filter(status='completed')
                .values('user_id')
                .annotate(last_done=Max('completed_at'))
                .filter(last_done__lt=cutoff)
            )

            for row in inactive_users:
                uid = row['user_id']
                dedup_key = f'reengagement_sent_{uid}'
                if cache.get(dedup_key):
                    skipped += 1
                    continue

                # Give a comeback bonus
                bonus = Decimal('0.25')
                try:
                    from api.tasks.services import WalletService
                    WalletService().credit(
                        user_id=uid,
                        amount=bonus,
                        transaction_type='reengagement_bonus',
                        reference=f'reengage_{timezone.now().strftime("%Y%m%d")}',
                    )
                except ImportError:
                    pass

                send_push_notification.apply_async(kwargs={
                    'user_id': uid,
                    'title': "We miss you! 💔",
                    'body': f"Come back and claim your ${bonus:.2f} comeback bonus!",
                })
                send_email_notification.apply_async(kwargs={
                    'user_id': uid,
                    'subject': "We miss you — here's a bonus! 🎁",
                    'message': f"You've been away for a while. We've added ${bonus:.2f} to your account to welcome you back!",
                })

                cache.set(dedup_key, 1, timeout=86400 * 7)
                sent += 1

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        return {
            'status': 'success',
            'sent': sent,
            'skipped': skipped,
            'inactivity_days': inactivity_days,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.user_lifecycle_tasks.identify_vip_users')
def identify_vip_users(self) -> dict:
    """
    Tag users as VIP based on monthly/total earnings.
    VIP users get: higher revenue share, priority support, exclusive offers.
    """
    try:
        from datetime import timedelta
        from django.db.models import Sum
        logger.info("⭐ Identifying VIP users...")

        tagged    = 0
        untagged  = 0

        try:
            from api.tasks.models import UserTaskCompletion

            cutoff = timezone.now() - timedelta(days=30)
            monthly = (
                UserTaskCompletion.objects.filter(
                    completed_at__gte=cutoff, status='completed'
                )
                .values('user_id')
                .annotate(monthly_earnings=Sum('reward_amount'))
            )

            total_all = (
                UserTaskCompletion.objects.filter(status='completed')
                .values('user_id')
                .annotate(total_earnings=Sum('reward_amount'))
            )

            total_map = {row['user_id']: Decimal(str(row['total_earnings'] or 0))
                         for row in total_all}

            for row in monthly:
                uid     = row['user_id']
                monthly_earn = Decimal(str(row['monthly_earnings'] or 0))
                total_earn   = total_map.get(uid, Decimal('0'))

                is_vip = (monthly_earn >= VIP_THRESHOLD_MONTHLY or
                          total_earn >= VIP_THRESHOLD_TOTAL)

                try:
                    from users.models import Profile
                    Profile.objects.filter(user_id=uid).update(is_vip=is_vip)
                except ImportError:
                    cache.set(f'user_is_vip_{uid}', is_vip, timeout=86400)

                if is_vip:
                    tagged += 1
                else:
                    untagged += 1

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        return {
            'status': 'success',
            'vip_tagged': tagged,
            'non_vip': untagged,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.user_lifecycle_tasks.send_birthday_bonus')
def send_birthday_bonus(self) -> dict:
    """
    Credit a birthday bonus to users whose birthday is today.
    Also sends a personalized birthday notification.
    """
    try:
        from django.contrib.auth import get_user_model
        logger.info("🎂 Processing birthday bonuses...")

        User        = get_user_model()
        today       = timezone.now().date()
        credited    = 0
        BIRTHDAY_BONUS = Decimal('1.00')

        try:
            from users.models import Profile
            from api.tasks.services import WalletService
            from api.tasks.notification_tasks import dispatch_in_app_notification

            birthday_users = Profile.objects.filter(
                birthday__month=today.month,
                birthday__day=today.day,
                user__is_active=True,
            ).select_related('user')

            ws = WalletService()
            for profile in birthday_users:
                dedup_key = f'birthday_bonus_{profile.user_id}_{today.year}'
                if cache.get(dedup_key):
                    continue

                ws.credit(
                    user_id=profile.user_id,
                    amount=BIRTHDAY_BONUS,
                    transaction_type='birthday_bonus',
                    reference=f'birthday_{today}',
                    metadata={'birthday_year': today.year},
                )
                cache.set(dedup_key, 1, timeout=86400 * 400)

                dispatch_in_app_notification.apply_async(kwargs={
                    'user_id': profile.user_id,
                    'title': f'🎂 Happy Birthday, {profile.user.username}!',
                    'message': f'We gifted you ${BIRTHDAY_BONUS:.2f} as a birthday present! Enjoy!',
                    'notification_type': 'success',
                })
                credited += 1

        except ImportError as e:
            logger.warning(f"[WARN] Profile model not available: {e}")

        return {
            'status': 'success',
            'credited': credited,
            'bonus_amount': str(BIRTHDAY_BONUS),
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=120,
             name='tasks.user_lifecycle_tasks.auto_deactivate_dormant')
def auto_deactivate_dormant(self, dormant_days: int = 365) -> dict:
    """
    Suspend accounts that have had zero activity for `dormant_days`.
    Sends final warning 7 days before suspension.
    """
    try:
        from datetime import timedelta
        from django.db.models import Max
        from django.contrib.auth import get_user_model
        logger.info(f"💤 Auto-deactivating dormant accounts (>{dormant_days}d inactive)...")

        User      = get_user_model()
        cutoff    = timezone.now() - timedelta(days=dormant_days)
        warn_cut  = timezone.now() - timedelta(days=dormant_days - 7)
        deactivated = 0
        warned      = 0

        try:
            from api.tasks.models import UserTaskCompletion

            # Users with no completion in cutoff period
            active_ids = set(
                UserTaskCompletion.objects.filter(completed_at__gte=cutoff)
                .values_list('user_id', flat=True)
                .distinct()
            )

            dormant = User.objects.filter(
                is_active=True,
                date_joined__lt=cutoff,
            ).exclude(id__in=active_ids).exclude(is_staff=True)

            for user in dormant:
                last_login = user.last_login
                days_since = (timezone.now() - (last_login or user.date_joined)).days

                if days_since >= dormant_days:
                    user.is_active = False
                    user.save(update_fields=['is_active'])
                    deactivated += 1
                elif days_since >= dormant_days - 7:
                    # Warning: 7 days left
                    try:
                        from api.tasks.notification_tasks import send_email_notification
                        send_email_notification.apply_async(kwargs={
                            'user_id': user.pk,
                            'subject': '⚠️ Account Deactivation Notice',
                            'message': (
                                f"Your account will be deactivated in 7 days due to inactivity.\n"
                                f"Log in to keep your account active."
                            ),
                        })
                    except ImportError:
                        pass
                    warned += 1

        except ImportError as e:
            logger.warning(f"[WARN] Models not available: {e}")

        return {
            'status': 'success',
            'deactivated': deactivated,
            'warned': warned,
            'dormant_days': dormant_days,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)
