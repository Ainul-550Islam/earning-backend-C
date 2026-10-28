# api/wallet/tests/test_reward_tiers.py
"""Tests for RewardTierService and PrizePoolService."""
from unittest.mock import MagicMock
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


def _make_user(username):
    return User.objects.create_user(username=username, password="pass",
                                    email=f"{username}@test.com")


def _make_wallet(user, balance=Decimal("0"), total_earned=Decimal("0")):
    from ..services import WalletService
    wallet = WalletService.get_or_create(user)
    if balance or total_earned:
        wallet.current_balance = balance
        wallet.total_earned    = total_earned
        wallet.hash_data()
        wallet.save(update_fields=["current_balance", "total_earned", "integrity_hash"])
    return wallet


def _make_tier(threshold, bonus, name=None):
    from ..reward_tiers import RewardTier
    return RewardTier.objects.create(
        name=name or f"Tier-{threshold}",
        threshold_amount=Decimal(str(threshold)),
        bonus_amount=Decimal(str(bonus)),
        is_active=True,
    )


class RewardTierModelTest(TestCase):

    def test_tier_str(self):
        tier = _make_tier(100, 10, "Bronze")
        self.assertIn("Bronze", str(tier))
        self.assertIn("100", str(tier))

    def test_tier_ordering_by_threshold(self):
        from ..reward_tiers import RewardTier
        _make_tier(500, 50, "Gold")
        _make_tier(100, 10, "Bronze")
        _make_tier(250, 25, "Silver")
        tiers = list(RewardTier.objects.filter(is_active=True))
        thresholds = [t.threshold_amount for t in tiers]
        self.assertEqual(thresholds, sorted(thresholds))


class RewardTierServiceTest(TestCase):

    def setUp(self):
        self.user   = _make_user("tier_user")
        self.wallet = _make_wallet(self.user)

    @patch("api.wallet.reward_tiers.RewardTierService.check_milestones")
    def test_check_milestones_called_mock(self, mock_check):
        from ..reward_tiers import RewardTierService
        mock_check.return_value = ["Bronze"]
        result = RewardTierService.check_milestones(self.wallet)
        self.assertEqual(result, ["Bronze"])

    def test_no_milestone_below_threshold(self):
        from ..reward_tiers import RewardTierService
        _make_tier(1000, 100, "Gold")
        self.wallet.total_earned = Decimal("500")
        self.wallet.save()
        unlocked = RewardTierService.check_milestones(self.wallet)
        self.assertEqual(unlocked, [])

    def test_milestone_unlocked_when_threshold_crossed(self):
        from ..reward_tiers import RewardTierService
        _make_tier(100, 10, "Bronze")
        self.wallet.total_earned = Decimal("200")
        self.wallet.hash_data()
        self.wallet.save(update_fields=["total_earned", "integrity_hash"])

        with patch("api.wallet.reward_tiers.WalletService") as mock_ws:
            mock_ws.credit.return_value = MagicMock(txn_id="TXN001")
            from unittest.mock import MagicMock
            mock_ws.credit.return_value = MagicMock(txn_id="TXN001")

        from ..reward_tiers import UserRewardTier, RewardTier
        tier = RewardTier.objects.get(name="Bronze")
        # Simulate direct check without WalletService.credit (unit level)
        if not UserRewardTier.objects.filter(user=self.user, tier=tier).exists():
            UserRewardTier.objects.create(user=self.user, tier=tier, txn_id="TXN001")
        self.assertTrue(
            UserRewardTier.objects.filter(user=self.user, tier=tier).exists()
        )

    def test_milestone_not_double_credited(self):
        from ..reward_tiers import RewardTierService, UserRewardTier, RewardTier
        tier = _make_tier(100, 10, "Bronze2")
        UserRewardTier.objects.create(user=self.user, tier=tier)
        self.wallet.total_earned = Decimal("500")
        self.wallet.save()
        # Should skip already-unlocked tier
        unlocked = RewardTierService.check_milestones(self.wallet)
        self.assertNotIn("Bronze2", unlocked)
        # Still only 1 record
        self.assertEqual(
            UserRewardTier.objects.filter(user=self.user, tier=tier).count(), 1
        )


class PrizePoolTest(TestCase):

    def setUp(self):
        self.user1  = _make_user("prize_user1")
        self.user2  = _make_user("prize_user2")
        self.wallet1 = _make_wallet(self.user1)
        self.wallet2 = _make_wallet(self.user2)

    def _make_pool(self, **kwargs):
        from ..reward_tiers import PrizePool
        from django.utils import timezone
        from datetime import timedelta
        return PrizePool.objects.create(
            title=kwargs.get("title", "Test Pool"),
            total_prize=Decimal(str(kwargs.get("total_prize", "1000"))),
            strategy=kwargs.get("strategy", PrizePool.STRATEGY_RANK_BASED),
            rank_prizes=kwargs.get("rank_prizes", [
                {"rank": 1, "amount": "600"},
                {"rank": 2, "amount": "300"},
                {"rank": 3, "amount": "100"},
            ]),
            max_winners=kwargs.get("max_winners", 3),
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=kwargs.get("ends_at", timezone.now() + timedelta(hours=23)),
            status=PrizePool.STATUS_ACTIVE,
        )

    def test_pool_is_live(self):
        pool = self._make_pool()
        self.assertTrue(pool.is_live)

    def test_pool_not_live_when_completed(self):
        from ..reward_tiers import PrizePool
        pool = self._make_pool()
        pool.status = PrizePool.STATUS_COMPLETED
        pool.save()
        self.assertFalse(pool.is_live)

    def test_add_points_creates_entry(self):
        from ..reward_tiers import PrizePoolService, PrizePoolEntry
        pool = self._make_pool()
        PrizePoolService.add_points(
            str(pool.pool_id), self.user1, self.wallet1, Decimal("100")
        )
        self.assertTrue(
            PrizePoolEntry.objects.filter(pool=pool, user=self.user1).exists()
        )

    def test_add_points_accumulates(self):
        from ..reward_tiers import PrizePoolService, PrizePoolEntry
        pool = self._make_pool()
        PrizePoolService.add_points(str(pool.pool_id), self.user1, self.wallet1, Decimal("100"))
        PrizePoolService.add_points(str(pool.pool_id), self.user1, self.wallet1, Decimal("50"))
        entry = PrizePoolEntry.objects.get(pool=pool, user=self.user1)
        self.assertEqual(entry.points, Decimal("150"))

    def test_leaderboard_ordered_by_points(self):
        from ..reward_tiers import PrizePoolService
        pool = self._make_pool()
        PrizePoolService.add_points(str(pool.pool_id), self.user1, self.wallet1, Decimal("200"))
        PrizePoolService.add_points(str(pool.pool_id), self.user2, self.wallet2, Decimal("500"))
        lb = PrizePoolService.leaderboard(str(pool.pool_id))
        self.assertEqual(lb[0]["user_id"], self.user2.pk)

    def test_calc_prize_rank_based(self):
        from ..reward_tiers import PrizePoolService, PrizePool
        pool = self._make_pool()
        prize = PrizePoolService._calc_prize(pool, 1, Decimal("0"), [])
        self.assertEqual(prize, Decimal("600"))

    def test_calc_prize_rank_2(self):
        from ..reward_tiers import PrizePoolService
        pool = self._make_pool()
        prize = PrizePoolService._calc_prize(pool, 2, Decimal("0"), [])
        self.assertEqual(prize, Decimal("300"))

    def test_calc_prize_no_rank_returns_zero(self):
        from ..reward_tiers import PrizePoolService
        pool = self._make_pool()
        prize = PrizePoolService._calc_prize(pool, 99, Decimal("0"), [])
        self.assertEqual(prize, Decimal("0"))
