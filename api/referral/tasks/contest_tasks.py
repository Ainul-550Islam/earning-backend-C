# api/referral/tasks/contest_tasks.py
# Celery tasks: contest leaderboard update and prize distribution
# ============================================================

from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(
    name='referral.update_all_contest_leaderboards',
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def update_all_contest_leaderboards(self):
    """
    সব active contests এর leaderboard update করো।
    প্রতি ঘণ্টায় run হয়।

    Schedule example:
        'referral-update-leaderboards': {
            'task': 'referral.update_all_contest_leaderboards',
            'schedule': crontab(minute=15),  # every hour at :15
        }
    """
    try:
        from api.referral.models import ReferralContest
        from api.referral.services.ReferralContestService import (
            ReferralContestService,
        )
        from django.utils import timezone

        now = timezone.now()
        active_contests = ReferralContest.objects.filter(
            status='active',
            start_date__lte=now,
            end_date__gte=now,
        )

        updated = 0
        errors = 0

        for contest in active_contests:
            try:
                result = ReferralContestService.update_leaderboard(contest.id)
                if result.get('success'):
                    updated += 1
                else:
                    errors += 1
            except Exception as e:
                logger.error(
                    f"Leaderboard update error for contest {contest.id}: {e}"
                )
                errors += 1

        logger.info(
            f"[Task] update_all_contest_leaderboards: "
            f"updated={updated}, errors={errors}"
        )

        return {'updated': updated, 'errors': errors}

    except Exception as exc:
        logger.error(
            f"[Task] update_all_contest_leaderboards failed: {exc}"
        )
        raise self.retry(exc=exc)


@shared_task(
    name='referral.check_and_finalize_contests',
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def check_and_finalize_contests(self):
    """
    End date পার হয়েছে এমন contests finalize করো।
    Prize distribution।
    প্রতিদিন রাত ১২:৩০ তে run হয়।

    Schedule example:
        'referral-finalize-contests': {
            'task': 'referral.check_and_finalize_contests',
            'schedule': crontab(hour=0, minute=30),
        }
    """
    try:
        from api.referral.models import ReferralContest
        from api.referral.services.ReferralContestService import (
            ReferralContestService,
        )
        from django.utils import timezone

        now = timezone.now()

        # Contests that ended but not yet finalized
        ended_contests = ReferralContest.objects.filter(
            end_date__lt=now,
            status='ended',
        )

        finalized = 0
        errors = 0

        for contest in ended_contests:
            try:
                result = ReferralContestService.finalize_contest(contest.id)
                if result.get('success'):
                    finalized += 1
                    logger.info(
                        f"Contest finalized: {contest.title} "
                        f"(distributed={result.get('distributed', 0)})"
                    )
                else:
                    errors += 1
                    logger.error(
                        f"Contest finalize failed: {contest.title} "
                        f"— {result.get('error', 'unknown')}"
                    )
            except Exception as e:
                logger.error(
                    f"Contest finalize exception for {contest.id}: {e}"
                )
                errors += 1

        logger.info(
            f"[Task] check_and_finalize_contests: "
            f"finalized={finalized}, errors={errors}"
        )

        return {'finalized': finalized, 'errors': errors}

    except Exception as exc:
        logger.error(f"[Task] check_and_finalize_contests failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.update_contest_statuses',
    bind=True,
    max_retries=2,
)
def update_contest_statuses(self):
    """
    Contest status (upcoming/active/ended) auto-update করো।
    প্রতি ঘণ্টায় run হয়।

    Schedule example:
        'referral-contest-status': {
            'task': 'referral.update_contest_statuses',
            'schedule': crontab(minute=5),
        }
    """
    try:
        from api.referral.models import ReferralContest

        contests = ReferralContest.objects.filter(
            status__in=['upcoming', 'active']
        )

        updated = 0
        for contest in contests:
            old_status = contest.status
            contest.update_status()
            if contest.status != old_status:
                updated += 1
                logger.info(
                    f"Contest status updated: {contest.title} "
                    f"{old_status} → {contest.status}"
                )

        return {'updated': updated}

    except Exception as exc:
        logger.error(f"[Task] update_contest_statuses failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.notify_contest_rank_changes',
    bind=True,
    max_retries=2,
)
def notify_contest_rank_changes(self):
    """
    Top 3 এ rank change হলে users দের notify করো।
    প্রতিদিন একবার।

    Schedule example:
        'referral-notify-rank-changes': {
            'task': 'referral.notify_contest_rank_changes',
            'schedule': crontab(hour=18, minute=0),  # 6 PM daily
        }
    """
    try:
        from api.referral.models import ContestEntry, ReferralContest
        from api.referral.services.ReferralNotificationService import (
            ReferralNotificationService,
        )
        from django.utils import timezone

        now = timezone.now()
        active_contests = ReferralContest.objects.filter(
            status='active',
            is_public=True,
        )

        notified = 0
        for contest in active_contests:
            # Top 10 entries
            top_entries = ContestEntry.objects.filter(
                contest=contest,
                current_rank__isnull=False,
                current_rank__lte=10,
            ).select_related('user').order_by('current_rank')

            total_participants = ContestEntry.objects.filter(
                contest=contest
            ).count()

            for entry in top_entries:
                try:
                    ReferralNotificationService.notify_contest_rank_update(
                        user=entry.user,
                        contest_title=contest.title,
                        rank=entry.current_rank,
                        total_participants=total_participants,
                    )
                    notified += 1
                except Exception as e:
                    logger.warning(
                        f"Contest rank notification failed for "
                        f"{entry.user.username}: {e}"
                    )

        logger.info(
            f"[Task] notify_contest_rank_changes: notified={notified}"
        )
        return {'notified': notified}

    except Exception as exc:
        logger.error(f"[Task] notify_contest_rank_changes failed: {exc}")
        raise self.retry(exc=exc)