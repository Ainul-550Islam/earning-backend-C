# api/referral/services/ReferralTreeService.py
# Build, update, and query multi-level referral trees
# ============================================================

from decimal import Decimal
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
import logging
from api.referral.models.tree import ReferralTree
from api.referral.models.tree import ReferralTreeSnapshot

logger = logging.getLogger(__name__)


class ReferralTreeService:
    """
    ReferralTree এর build, update, query service।
    Tree কে consistent রাখার দায়িত্ব এই service এর।
    """

    @staticmethod
    def ensure_tree(user) -> 'ReferralTree':
        """User এর tree না থাকলে create করো।"""
        from api.referral.models import ReferralTree
        tree, created = ReferralTree.objects.get_or_create(root_user=user)
        if created:
            logger.info(f"Created new ReferralTree for {user.username}")
        return tree

    @staticmethod
    @transaction.atomic
    def rebuild_tree(user) -> 'ReferralTree':
        """
        User এর tree পুরোপুরি rebuild করো।
        ReferralRelationship + ReferralEarning থেকে data নেওয়া হয়।
        """
        from api.referral.models import ReferralTree

        tree = ReferralTreeService.ensure_tree(user)
        tree.refresh_counts()

        logger.debug(
            f"Tree rebuilt for {user.username}: "
            f"{tree.total_members} members, ৳{tree.total_earned}"
        )
        return tree

    @staticmethod
    def get_tree_data(user) -> dict:
        """User এর tree data + per-level breakdown।"""
        from api.referral.models import ReferralTree, ReferralRelationship

        tree = ReferralTreeService.ensure_tree(user)

        # Level 1 members detail
        l1_rels = ReferralRelationship.objects.filter(
            referrer=user, level=1
        ).select_related('referred').order_by('-joined_at')[:20]

        l1_members = [{
            'user_id': r.referred.id,
            'username': r.referred.username,
            'joined_at': r.joined_at.strftime('%Y-%m-%d'),
            'is_active': r.referred.is_active,
            'total_commission': float(r.total_commission_earned),
        } for r in l1_rels]

        return {
            'total_members': tree.total_members,
            'depth': tree.depth,
            'level1': {
                'count': tree.level1_count,
                'earned': float(tree.level1_earned),
                'members': l1_members,
            },
            'level2': {
                'count': tree.level2_count,
                'earned': float(tree.level2_earned),
            },
            'level3': {
                'count': tree.level3_count,
                'earned': float(tree.level3_earned),
            },
            'total_earned': float(tree.total_earned),
            'last_rebuilt': (
                tree.last_rebuilt_at.isoformat()
                if tree.last_rebuilt_at else None
            ),
        }

    @staticmethod
    def get_downline(user, level: int = None, max_results: int = 100) -> list:
        """
        User এর downline members।
        level=None → সব level
        level=1/2/3 → specific level
        """
        from api.referral.models import ReferralRelationship

        qs = ReferralRelationship.objects.filter(
            referrer=user
        ).select_related('referred')

        if level:
            qs = qs.filter(level=level)

        qs = qs.order_by('level', '-joined_at')[:max_results]

        return [{
            'user_id': r.referred.id,
            'username': r.referred.username,
            'level': r.level,
            'joined_at': r.joined_at.strftime('%Y-%m-%d %H:%M'),
            'is_active': r.referred.is_active,
            'commission_from': float(r.total_commission_earned),
            'last_activity': (
                r.last_activity.strftime('%Y-%m-%d')
                if r.last_activity else None
            ),
        } for r in qs]

    @staticmethod
    def get_upline(user) -> list:
        """
        User এর upline (who referred whom up the chain).
        Level 1, 2, 3 ancestors।
        """
        from api.referral.models import ReferralRelationship

        # User এর ancestors — যারা user কে refer করেছে (বিভিন্ন level এ)
        qs = ReferralRelationship.objects.filter(
            referred=user
        ).select_related('referrer').order_by('level')

        return [{
            'user_id': r.referrer.id,
            'username': r.referrer.username,
            'level': r.level,
            'joined_at': r.joined_at.strftime('%Y-%m-%d'),
        } for r in qs]

    @staticmethod
    def take_snapshot(user, period: str = 'weekly') -> 'ReferralTreeSnapshot':
        """User এর tree এর snapshot নাও।"""
        from api.referral.models import ReferralTreeSnapshot

        tree = ReferralTreeService.ensure_tree(user)
        tree.refresh_counts()

        snapshot_data = {
            'total_members': tree.total_members,
            'depth': tree.depth,
            'level1_count': tree.level1_count,
            'level2_count': tree.level2_count,
            'level3_count': tree.level3_count,
            'total_earned': str(tree.total_earned),
            'level1_earned': str(tree.level1_earned),
            'level2_earned': str(tree.level2_earned),
            'level3_earned': str(tree.level3_earned),
            'timestamp': timezone.now().isoformat(),
        }

        snapshot = ReferralTreeSnapshot.objects.create(
            tree=tree,
            period=period,
            snapshot_data=snapshot_data,
        )

        logger.info(
            f"Tree snapshot created for {user.username} [{period}]"
        )
        return snapshot

    @staticmethod
    def rebuild_all_trees(batch_size: int = 100) -> dict:
        """
        সব users এর tree rebuild করো।
        tree_rebuild_tasks.py Celery task দিয়ে call করা হয়।
        """
        from django.contrib.auth import get_user_model
        from api.referral.models import Referral

        User = get_user_model()
        rebuilt = 0
        errors = 0

        # শুধু যাদের referral আছে তাদের tree rebuild করো
        referrer_ids = Referral.objects.values_list(
            'referrer_id', flat=True
        ).distinct()

        for i in range(0, len(referrer_ids), batch_size):
            batch = referrer_ids[i:i + batch_size]
            users = User.objects.filter(id__in=batch)

            for user in users:
                try:
                    ReferralTreeService.rebuild_tree(user)
                    rebuilt += 1
                except Exception as e:
                    logger.error(
                        f"Tree rebuild error for user {user.id}: {e}"
                    )
                    errors += 1

        logger.info(
            f"Tree rebuild complete: {rebuilt} rebuilt, {errors} errors"
        )
        return {'rebuilt': rebuilt, 'errors': errors}

    @staticmethod
    def get_tree_health_check() -> dict:
        """Tree consistency check করো।"""
        from api.referral.models import ReferralTree, ReferralRelationship, Referral

        total_trees = ReferralTree.objects.count()
        total_relationships = ReferralRelationship.objects.count()
        total_referrals = Referral.objects.count()

        # Trees যেগুলো stale (7 দিনের বেশি আপডেট হয়নি)
        stale_cutoff = timezone.now() - timedelta(days=7)
        stale_trees = ReferralTree.objects.filter(
            last_rebuilt_at__lt=stale_cutoff
        ).count()

        return {
            'total_trees': total_trees,
            'total_relationships': total_relationships,
            'total_referrals': total_referrals,
            'stale_trees': stale_trees,
            'health': 'ok' if stale_trees == 0 else 'stale',
        }