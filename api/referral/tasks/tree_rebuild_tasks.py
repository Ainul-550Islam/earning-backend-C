# api/referral/tasks/tree_rebuild_tasks.py
# Celery tasks: periodic referral tree rebuild and consistency check
# ============================================================

from celery import shared_task
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(
    name='referral.rebuild_stale_trees',
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def rebuild_stale_trees(self):
    """
    7+ দিন ধরে আপডেট হয়নি এমন trees rebuild করো।
    প্রতিদিন ভোরে run হয়।

    Schedule example:
        'referral-rebuild-stale-trees': {
            'task': 'referral.rebuild_stale_trees',
            'schedule': crontab(hour=4, minute=30),
        }
    """
    try:
        from api.referral.models import ReferralTree
        from api.referral.services.ReferralTreeService import (
            ReferralTreeService,
        )
        from django.utils import timezone

        stale_cutoff = timezone.now() - timedelta(days=7)

        stale_trees = ReferralTree.objects.filter(
            last_rebuilt_at__lt=stale_cutoff
        ).select_related('root_user')

        rebuilt = 0
        errors = 0

        for tree in stale_trees:
            try:
                ReferralTreeService.rebuild_tree(tree.root_user)
                rebuilt += 1
            except Exception as e:
                logger.error(
                    f"Tree rebuild error for user "
                    f"{tree.root_user.username}: {e}"
                )
                errors += 1

        logger.info(
            f"[Task] rebuild_stale_trees: "
            f"rebuilt={rebuilt}, errors={errors}"
        )

        return {'rebuilt': rebuilt, 'errors': errors}

    except Exception as exc:
        logger.error(f"[Task] rebuild_stale_trees failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.full_tree_rebuild',
    bind=True,
    max_retries=1,
)
def full_tree_rebuild(self):
    """
    সব trees rebuild করো।
    Weekly — Sunday রাতে run হয়।
    Heavy task — শুধু weekly।

    Schedule example:
        'referral-full-tree-rebuild': {
            'task': 'referral.full_tree_rebuild',
            'schedule': crontab(hour=2, minute=0, day_of_week=0),  # Sunday 2AM
        }
    """
    try:
        from api.referral.services.ReferralTreeService import (
            ReferralTreeService,
        )

        result = ReferralTreeService.rebuild_all_trees(batch_size=100)

        logger.info(
            f"[Task] full_tree_rebuild: "
            f"rebuilt={result['rebuilt']}, errors={result['errors']}"
        )

        return result

    except Exception as exc:
        logger.error(f"[Task] full_tree_rebuild failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.tree_consistency_check',
    bind=True,
    max_retries=2,
)
def tree_consistency_check(self):
    """
    Tree consistency check — stale trees detect করো।
    প্রতিদিন।

    Schedule example:
        'referral-tree-consistency': {
            'task': 'referral.tree_consistency_check',
            'schedule': crontab(hour=6, minute=0),
        }
    """
    try:
        from api.referral.services.ReferralTreeService import (
            ReferralTreeService,
        )

        health = ReferralTreeService.get_tree_health_check()

        if health['stale_trees'] > 0:
            logger.warning(
                f"[Task] tree_consistency_check: "
                f"{health['stale_trees']} stale trees found. "
                f"Triggering rebuild."
            )
            rebuild_stale_trees.delay()

        logger.info(
            f"[Task] tree_consistency_check: "
            f"total_trees={health['total_trees']}, "
            f"stale={health['stale_trees']}, "
            f"health={health['health']}"
        )

        return health

    except Exception as exc:
        logger.error(f"[Task] tree_consistency_check failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name='referral.take_weekly_tree_snapshots',
    bind=True,
    max_retries=2,
)
def take_weekly_tree_snapshots(self):
    """
    সব active referrers এর weekly tree snapshot নাও।
    প্রতি সোমবার ভোরে।

    Schedule example:
        'referral-weekly-tree-snapshots': {
            'task': 'referral.take_weekly_tree_snapshots',
            'schedule': crontab(hour=3, minute=0, day_of_week=1),
        }
    """
    try:
        from api.referral.models import Referral
        from api.referral.services.ReferralTreeService import (
            ReferralTreeService,
        )
        from django.contrib.auth import get_user_model

        User = get_user_model()

        referrer_ids = Referral.objects.values_list(
            'referrer_id', flat=True
        ).distinct()

        users = User.objects.filter(id__in=referrer_ids, is_active=True)

        snapped = 0
        errors = 0

        for user in users:
            try:
                ReferralTreeService.take_snapshot(user=user, period='weekly')
                snapped += 1
            except Exception as e:
                logger.error(f"Snapshot error for {user.username}: {e}")
                errors += 1

        logger.info(
            f"[Task] take_weekly_tree_snapshots: "
            f"snapped={snapped}, errors={errors}"
        )

        return {'snapped': snapped, 'errors': errors}

    except Exception as exc:
        logger.error(f"[Task] take_weekly_tree_snapshots failed: {exc}")
        raise self.retry(exc=exc)