# api/referral/services/ReferralContestService.py
# Referral contest: leaderboard, prize distribution
# ============================================================

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class ReferralContestService:
    """
    Contest management — leaderboard calculation, prize distribution।
    """

    @staticmethod
    def get_active_contests() -> list:
        """এখন active contests।"""
        from api.referral.models import ReferralContest

        now = timezone.now()
        contests = ReferralContest.objects.filter(
            status='active',
            start_date__lte=now,
            end_date__gte=now,
        ).order_by('-start_date')

        return [{
            'id': c.id,
            'title': c.title,
            'slug': c.slug,
            'description': c.description,
            'contest_type': c.contest_type,
            'prize_pool': float(c.prize_pool),
            'leaderboard_size': c.leaderboard_size,
            'start_date': c.start_date.strftime('%Y-%m-%d %H:%M'),
            'end_date': c.end_date.strftime('%Y-%m-%d %H:%M'),
            'days_remaining': max(0, (c.end_date - now).days),
        } for c in contests]

    @staticmethod
    def get_leaderboard(contest_id: int, limit: int = None) -> dict:
        """Contest leaderboard দাও।"""
        from api.referral.models import ReferralContest, ContestEntry

        try:
            contest = ReferralContest.objects.get(id=contest_id)
        except ReferralContest.DoesNotExist:
            return {'error': 'Contest not found'}

        limit = limit or contest.leaderboard_size

        entries = ContestEntry.objects.filter(
            contest=contest
        ).select_related('user').order_by('current_rank', '-commission_earned')[:limit]

        leaderboard = [{
            'rank': entry.current_rank or i + 1,
            'user_id': entry.user.id,
            'username': entry.user.username,
            'referral_count': entry.referral_count,
            'active_referral_count': entry.active_referral_count,
            'commission_earned': float(entry.commission_earned),
            'ltv_score': float(entry.ltv_score),
        } for i, entry in enumerate(entries)]

        return {
            'contest_id': contest.id,
            'title': contest.title,
            'contest_type': contest.contest_type,
            'status': contest.status,
            'leaderboard': leaderboard,
        }

    @staticmethod
    @transaction.atomic
    def update_leaderboard(contest_id: int) -> dict:
        """
        Contest leaderboard recalculate করো।
        Celery task contest_tasks.py দিয়ে periodically call করা হয়।
        """
        from api.referral.models import (
            ReferralContest, ContestEntry, Referral, ReferralEarning
        )
        from django.db.models import Count, Sum, Q

        try:
            contest = ReferralContest.objects.get(id=contest_id)
        except ReferralContest.DoesNotExist:
            return {'success': False, 'error': 'Contest not found'}

        if contest.contest_type == 'most_referrals':
            # Direct referral count
            data = Referral.objects.filter(
                created_at__gte=contest.start_date,
                created_at__lte=contest.end_date,
            ).values('referrer').annotate(
                score=Count('id'),
                active=Count('id', filter=Q(referred_user__is_active=True))
            ).order_by('-score')

        elif contest.contest_type == 'highest_commission':
            data = ReferralEarning.objects.filter(
                created_at__gte=contest.start_date,
                created_at__lte=contest.end_date,
                level=1,
            ).values('referrer').annotate(
                score=Sum('amount'),
                active=Count('id')
            ).order_by('-score')

        elif contest.contest_type == 'most_active_referrals':
            data = Referral.objects.filter(
                created_at__gte=contest.start_date,
                created_at__lte=contest.end_date,
                referred_user__is_active=True,
            ).values('referrer').annotate(
                score=Count('id'),
                active=Count('id'),
            ).order_by('-score')

        else:
            # Default: most_referrals
            data = Referral.objects.filter(
                created_at__gte=contest.start_date,
            ).values('referrer').annotate(
                score=Count('id'),
                active=Count('id'),
            ).order_by('-score')

        from django.contrib.auth import get_user_model
        User = get_user_model()

        updated = 0
        for rank, item in enumerate(
            data[:contest.leaderboard_size], start=1
        ):
            user_id = item.get('referrer')
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                continue

            score = item.get('score', 0)
            active = item.get('active', 0)

            entry, _ = ContestEntry.objects.get_or_create(
                contest=contest,
                user=user,
            )
            entry.referral_count = int(score) if contest.contest_type != 'highest_commission' else entry.referral_count
            entry.commission_earned = Decimal(str(score)) if contest.contest_type == 'highest_commission' else entry.commission_earned
            entry.active_referral_count = int(active)
            entry.current_rank = rank
            entry.save(update_fields=[
                'referral_count', 'commission_earned',
                'active_referral_count', 'current_rank'
            ])
            updated += 1

        logger.info(
            f"Leaderboard updated for contest {contest.title}: "
            f"{updated} entries"
        )

        return {'success': True, 'updated': updated}

    @staticmethod
    @transaction.atomic
    def finalize_contest(contest_id: int) -> dict:
        """
        Contest শেষে winners assign করো এবং prizes distribute করো।
        """
        from api.referral.models import ReferralContest, ReferralReward, ContestEntry

        try:
            contest = ReferralContest.objects.get(id=contest_id)
        except ReferralContest.DoesNotExist:
            return {'success': False, 'error': 'Contest not found'}

        if contest.status != 'ended':
            contest.update_status()
            if contest.status != 'ended':
                return {'success': False, 'error': 'Contest not yet ended'}

        # Final leaderboard update
        ReferralContestService.update_leaderboard(contest_id)

        # Assign winners to rewards
        rewards = ReferralReward.objects.filter(
            contest=contest, status='pending'
        ).order_by('rank')

        entries = ContestEntry.objects.filter(
            contest=contest
        ).order_by('current_rank').select_related('user')

        entry_map = {e.current_rank: e for e in entries}
        distributed = 0
        failed = 0

        for reward in rewards:
            # Handle rank ranges
            for rank in range(reward.rank, (reward.rank_to or reward.rank) + 1):
                entry = entry_map.get(rank)
                if not entry:
                    continue

                reward.assign_winner(entry.user)
                # Update final rank
                entry.final_rank = rank
                entry.save(update_fields=['final_rank'])

                # Distribute prize
                result = ReferralContestService._distribute_prize(
                    reward, entry.user
                )
                if result['success']:
                    distributed += 1
                else:
                    failed += 1

        # Mark contest prizes distributed
        contest.status = 'prizes_distributed'
        contest.save(update_fields=['status'])

        logger.info(
            f"Contest finalized: {contest.title} — "
            f"{distributed} prizes distributed, {failed} failed"
        )

        return {
            'success': True,
            'contest_id': contest.id,
            'distributed': distributed,
            'failed': failed,
        }

    @staticmethod
    @transaction.atomic
    def _distribute_prize(reward, user) -> dict:
        """Prize distribute করো।"""
        try:
            if reward.reward_type in ['cash', 'coins']:
                from api.wallet.services import WalletService
                from api.wallet.models import Wallet

                wallet, _ = Wallet.objects.get_or_create(user=user)
                wallet_txn = WalletService.add_earnings(
                    wallet=wallet,
                    amount=reward.reward_value,
                    description=(
                        f"Contest prize: {reward.contest.title} "
                        f"Rank #{reward.rank}"
                    ),
                    source_type='contest_prize',
                    source_id=str(reward.id),
                )

            reward.mark_distributed()

            logger.info(
                f"Prize distributed: {user.username} "
                f"rank={reward.rank} ৳{reward.reward_value}"
            )
            return {'success': True}

        except Exception as e:
            logger.error(f"Prize distribution error: {e}")
            reward.status = 'failed'
            reward.save(update_fields=['status'])
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_my_contest_rank(contest_id: int, user) -> dict:
        """User এর contest rank।"""
        from api.referral.models import ContestEntry

        entry = ContestEntry.objects.filter(
            contest_id=contest_id, user=user
        ).first()

        if not entry:
            return {
                'contest_id': contest_id,
                'rank': None,
                'not_participating': True,
            }

        return {
            'contest_id': contest_id,
            'rank': entry.current_rank,
            'final_rank': entry.final_rank,
            'referral_count': entry.referral_count,
            'commission_earned': float(entry.commission_earned),
        }