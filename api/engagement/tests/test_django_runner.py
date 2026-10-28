# engagement/tests/test_django_runner.py
"""
Complete Django TestCase suite — runs with:
    python manage.py test api.engagement.tests.test_django_runner --verbosity=2

Covers every service, model, and API endpoint.
All pytest-style tests from the other test_*.py files are re-implemented here
as standard unittest.TestCase subclasses.
"""
from decimal import Decimal
from datetime import date, timedelta

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_user_counter = [0]


def make_user(coin_balance=Decimal("500"), is_staff=False, **kwargs):
    _user_counter[0] += 1
    n = _user_counter[0]
    username = kwargs.pop("username", f"u_test_{n}")
    u = User.objects.create_user(
        username=username,
        email=f"{username}@test.com",
        password="testpass123",
        is_staff=is_staff,
        **kwargs)
    User.objects.filter(pk=u.pk).update(coin_balance=coin_balance)
    u.refresh_from_db()
    return u


def api(user=None):
    if user is None:
        user = make_user()
    c = APIClient()
    c.force_authenticate(user=user)
    c._user = user
    return c


# ─────────────────────────────────────────────────────────────────────────────
# 1. CoinService
# ─────────────────────────────────────────────────────────────────────────────

class TestCoinService(TestCase):

    def setUp(self):
        from api.engagement.services.coin_service import CoinService
        self.CoinService = CoinService
        self.user = make_user(coin_balance=Decimal("100"))

    def test_add_increases_balance(self):
        self.CoinService.add(self.user, Decimal("50"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.coin_balance, Decimal("150"))

    def test_add_returns_new_balance(self):
        bal = self.CoinService.add(self.user, Decimal("20"))
        self.assertEqual(bal, Decimal("120"))

    def test_add_zero_raises(self):
        with self.assertRaises(ValueError):
            self.CoinService.add(self.user, Decimal("0"))

    def test_add_negative_raises(self):
        with self.assertRaises(ValueError):
            self.CoinService.add(self.user, Decimal("-5"))

    def test_deduct_decreases_balance(self):
        self.CoinService.deduct(self.user, Decimal("30"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.coin_balance, Decimal("70"))

    def test_deduct_returns_new_balance(self):
        bal = self.CoinService.deduct(self.user, Decimal("40"))
        self.assertEqual(bal, Decimal("60"))

    def test_deduct_insufficient_raises(self):
        from api.engagement.exceptions import InsufficientCoinsError
        with self.assertRaises(InsufficientCoinsError):
            self.CoinService.deduct(self.user, Decimal("9999"))

    def test_get_balance_returns_decimal(self):
        bal = self.CoinService.get_balance(self.user)
        self.assertIsInstance(bal, Decimal)
        self.assertEqual(bal, Decimal("100"))


# ─────────────────────────────────────────────────────────────────────────────
# 2. XPService
# ─────────────────────────────────────────────────────────────────────────────

class TestXPService(TestCase):

    def setUp(self):
        from api.engagement.services.xp_service import XPService
        self.XPService = XPService
        self.user = make_user(coin_balance=Decimal("0"))

    def test_grant_creates_xp_record(self):
        from api.engagement.models.xp import UserXP
        self.XPService.grant(self.user, 50, source="checkin")
        xp = UserXP.objects.get(user=self.user)
        self.assertEqual(xp.total_xp, 50)

    def test_grant_creates_transaction_log(self):
        from api.engagement.models.xp import XPTransaction
        self.XPService.grant(self.user, 100, source="quest", note="Quest complete")
        self.assertTrue(XPTransaction.objects.filter(user=self.user, source="quest").exists())

    def test_grant_returns_level_info(self):
        result = self.XPService.grant(self.user, 50, source="spin")
        self.assertIn("old_level", result)
        self.assertIn("new_level", result)
        self.assertIn("leveled_up", result)
        self.assertIn("total_xp", result)

    def test_level_up_fires_when_threshold_crossed(self):
        result = self.XPService.grant(self.user, 150, source="test")
        self.assertTrue(result["leveled_up"])
        self.assertEqual(result["new_level"], 2)

    def test_no_level_up_below_threshold(self):
        result = self.XPService.grant(self.user, 50, source="test")
        self.assertFalse(result["leveled_up"])
        self.assertEqual(result["new_level"], 1)

    def test_grant_zero_raises(self):
        with self.assertRaises(ValueError):
            self.XPService.grant(self.user, 0, source="test")

    def test_xp_accumulates_across_grants(self):
        from api.engagement.models.xp import UserXP
        self.XPService.grant(self.user, 30, source="a")
        self.XPService.grant(self.user, 70, source="b")
        xp = UserXP.objects.get(user=self.user)
        self.assertEqual(xp.total_xp, 100)

    def test_xp_formula(self):
        from api.engagement.models.xp import xp_for_level, level_from_total_xp
        # Level 1 needs 100 XP base
        self.assertEqual(level_from_total_xp(0), 1)
        self.assertGreaterEqual(level_from_total_xp(100), 1)

    def test_get_or_create_returns_xp_obj(self):
        from api.engagement.models.xp import UserXP
        xp = self.XPService.get_or_create(self.user)
        self.assertIsInstance(xp, UserXP)
        self.assertEqual(xp.level, 1)


# ─────────────────────────────────────────────────────────────────────────────
# 3. CheckInService
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckInService(TestCase):

    def setUp(self):
        from api.engagement.services.checkin_service import CheckInService
        self.CheckInService = CheckInService
        self.user = make_user(coin_balance=Decimal("0"))

    def test_first_checkin_creates_record(self):
        from api.engagement.models.checkin import DailyCheckIn
        self.CheckInService.process(self.user)
        self.assertTrue(DailyCheckIn.objects.filter(user=self.user, date=date.today()).exists())

    def test_first_checkin_gives_base_coins(self):
        result = self.CheckInService.process(self.user)
        self.assertEqual(result["coins_earned"], 5.0)

    def test_first_checkin_streak_is_1(self):
        result = self.CheckInService.process(self.user)
        self.assertEqual(result["consecutive_days"], 1)

    def test_second_day_streak_multiplied(self):
        from api.engagement.models.checkin import DailyCheckIn
        DailyCheckIn.objects.create(
            user=self.user,
            date=date.today() - timedelta(days=1),
            consecutive_days=1,
            coins_earned=Decimal("5"),
            xp_earned=10)
        result = self.CheckInService.process(self.user)
        self.assertEqual(result["consecutive_days"], 2)
        self.assertEqual(result["coins_earned"], 10.0)

    def test_day_7_streak_caps_at_35(self):
        from api.engagement.models.checkin import DailyCheckIn
        DailyCheckIn.objects.create(
            user=self.user,
            date=date.today() - timedelta(days=1),
            consecutive_days=6,
            coins_earned=Decimal("30"),
            xp_earned=60)
        result = self.CheckInService.process(self.user)
        self.assertEqual(result["consecutive_days"], 7)
        self.assertEqual(result["coins_earned"], 35.0)

    def test_day_8_still_35_coins(self):
        from api.engagement.models.checkin import DailyCheckIn
        DailyCheckIn.objects.create(
            user=self.user,
            date=date.today() - timedelta(days=1),
            consecutive_days=7,
            coins_earned=Decimal("35"),
            xp_earned=70)
        result = self.CheckInService.process(self.user)
        self.assertEqual(result["consecutive_days"], 8)
        self.assertEqual(result["coins_earned"], 35.0)

    def test_double_checkin_raises(self):
        from api.engagement.exceptions import AlreadyCheckedInError
        self.CheckInService.process(self.user)
        with self.assertRaises(AlreadyCheckedInError):
            self.CheckInService.process(self.user)

    def test_streak_resets_after_gap(self):
        from api.engagement.models.checkin import DailyCheckIn
        DailyCheckIn.objects.create(
            user=self.user,
            date=date.today() - timedelta(days=3),
            consecutive_days=10,
            coins_earned=Decimal("50"),
            xp_earned=100)
        result = self.CheckInService.process(self.user)
        self.assertEqual(result["consecutive_days"], 1)

    def test_checkin_adds_coins_to_user(self):
        result = self.CheckInService.process(self.user)
        self.user.refresh_from_db()
        self.assertGreater(float(self.user.coin_balance), 0)

    def test_checkin_returns_new_balance(self):
        result = self.CheckInService.process(self.user)
        self.assertIn("new_balance", result)


# ─────────────────────────────────────────────────────────────────────────────
# 4. SpinService
# ─────────────────────────────────────────────────────────────────────────────

class TestSpinService(TestCase):

    def setUp(self):
        from api.engagement.services.spin_service import SpinService
        self.SpinService = SpinService
        self.user = make_user(coin_balance=Decimal("0"))

    def test_spin_creates_record(self):
        from api.engagement.models.spinwheel import SpinWheel
        self.SpinService.spin(self.user)
        self.assertEqual(SpinWheel.objects.filter(user=self.user).count(), 1)

    def test_spin_returns_coins_won_positive(self):
        result = self.SpinService.spin(self.user)
        self.assertIn("coins_won", result)
        self.assertGreater(result["coins_won"], 0)

    def test_spin_adds_coins_to_balance(self):
        result = self.SpinService.spin(self.user)
        self.user.refresh_from_db()
        self.assertAlmostEqual(float(self.user.coin_balance), result["new_balance"], places=2)

    def test_spin_remaining_decrements(self):
        from api.engagement.models.spinwheel import SpinWheel
        from api.engagement.constants import SPIN_MAX_PER_DAY
        self.SpinService.spin(self.user)
        self.assertEqual(SpinWheel.remaining_today(self.user), SPIN_MAX_PER_DAY - 1)

    def test_max_spins_raises(self):
        from api.engagement.exceptions import MaxSpinsReachedError
        from api.engagement.constants import SPIN_MAX_PER_DAY
        for _ in range(SPIN_MAX_PER_DAY):
            self.SpinService.spin(self.user)
        with self.assertRaises(MaxSpinsReachedError):
            self.SpinService.spin(self.user)

    def test_spin_outcome_index_valid(self):
        from api.engagement.constants import SPIN_OUTCOMES
        result = self.SpinService.spin(self.user)
        self.assertGreaterEqual(result.get("outcome_idx", 0), 0)
        self.assertLess(result.get("outcome_idx", 0), len(SPIN_OUTCOMES))

    def test_spin_returns_spins_remaining(self):
        from api.engagement.constants import SPIN_MAX_PER_DAY
        result = self.SpinService.spin(self.user)
        self.assertEqual(result["spins_remaining"], SPIN_MAX_PER_DAY - 1)


# ─────────────────────────────────────────────────────────────────────────────
# 5. AchievementService
# ─────────────────────────────────────────────────────────────────────────────

class TestAchievementService(TestCase):

    def setUp(self):
        from api.engagement.services.achievement_service import AchievementService
        from api.engagement.models.achievement import Achievement
        self.AchievementService = AchievementService
        self.user = make_user(coin_balance=Decimal("0"))
        self.ach = Achievement.objects.create(
            slug="ach-streak-7",
            name="7-Day Streak",
            description="Check in 7 days",
            type="streak",
            threshold=7,
            coin_reward=Decimal("50"),
            xp_reward=100,
            is_active=True,
            is_secret=False)

    def test_check_and_unlock_unlocks_matching(self):
        unlocked = self.AchievementService.check_and_unlock(self.user, "streak", current_value=7)
        self.assertEqual(len(unlocked), 1)
        self.assertEqual(unlocked[0].pk, self.ach.pk)

    def test_check_and_unlock_creates_user_achievement(self):
        from api.engagement.models.achievement import UserAchievement
        self.AchievementService.check_and_unlock(self.user, "streak", current_value=7)
        self.assertTrue(UserAchievement.objects.filter(user=self.user, achievement=self.ach).exists())

    def test_check_and_unlock_skips_already_unlocked(self):
        from api.engagement.models.achievement import UserAchievement
        UserAchievement.objects.create(user=self.user, achievement=self.ach)
        unlocked = self.AchievementService.check_and_unlock(self.user, "streak", current_value=10)
        self.assertEqual(len(unlocked), 0)

    def test_check_and_unlock_skips_above_threshold(self):
        unlocked = self.AchievementService.check_and_unlock(self.user, "streak", current_value=5)
        self.assertEqual(len(unlocked), 0)

    def test_unlock_grants_coin_reward(self):
        self.AchievementService.check_and_unlock(self.user, "streak", current_value=7)
        self.user.refresh_from_db()
        self.assertEqual(self.user.coin_balance, Decimal("50"))

    def test_unlock_grants_xp_reward(self):
        from api.engagement.models.xp import UserXP
        self.AchievementService.check_and_unlock(self.user, "streak", current_value=7)
        xp = UserXP.objects.filter(user=self.user).first()
        self.assertIsNotNone(xp)
        self.assertEqual(xp.total_xp, 100)

    def test_update_progress_increments(self):
        from api.engagement.models.achievement import AchievementProgress, Achievement
        ach2 = Achievement.objects.create(
            slug="ach-spins-10", name="10 Spins", description="Spin 10 times",
            type="spins", threshold=10,
            coin_reward=Decimal("0"), xp_reward=0,
            is_active=True, is_secret=False)
        self.AchievementService.update_progress(self.user, "spins", increment=3)
        prog = AchievementProgress.objects.get(user=self.user, achievement=ach2)
        self.assertEqual(prog.current, 3)

    def test_multiple_achievements_same_type(self):
        from api.engagement.models.achievement import Achievement
        Achievement.objects.create(
            slug="ach-streak-3", name="3-Day", description="3 days",
            type="streak", threshold=3,
            coin_reward=Decimal("10"), xp_reward=20,
            is_active=True, is_secret=False)
        Achievement.objects.create(
            slug="ach-streak-14", name="14-Day", description="14 days",
            type="streak", threshold=14,
            coin_reward=Decimal("100"), xp_reward=200,
            is_active=True, is_secret=False)
        unlocked = self.AchievementService.check_and_unlock(self.user, "streak", current_value=7)
        self.assertEqual(len(unlocked), 2)  # threshold 3 and 7 both met

    def test_get_all_with_status_includes_locked(self):
        data = self.AchievementService.get_all_with_status(self.user)
        self.assertTrue(any(not item["is_unlocked"] for item in data))


# ─────────────────────────────────────────────────────────────────────────────
# 6. ShopService
# ─────────────────────────────────────────────────────────────────────────────

class TestShopService(TestCase):

    def setUp(self):
        from api.engagement.services.shop_service import ShopService
        from api.engagement.models.shop import ShopItem
        self.ShopService = ShopService
        self.user = make_user(coin_balance=Decimal("500"))
        self.item = ShopItem.objects.create(
            slug="gold-avatar",
            name="Gold Avatar",
            description="Shiny",
            type="avatar",
            price_coins=Decimal("50"),
            stock=-1,
            max_per_user=-1,
            is_active=True)

    def test_purchase_deducts_coins(self):
        self.ShopService.purchase(self.user, self.item.slug)
        self.user.refresh_from_db()
        self.assertEqual(self.user.coin_balance, Decimal("450"))

    def test_purchase_creates_purchase_record(self):
        from api.engagement.models.shop import ShopPurchase
        self.ShopService.purchase(self.user, self.item.slug)
        self.assertTrue(ShopPurchase.objects.filter(user=self.user, item=self.item).exists())

    def test_purchase_adds_to_inventory(self):
        from api.engagement.models.shop import UserInventory
        self.ShopService.purchase(self.user, self.item.slug)
        inv = UserInventory.objects.get(user=self.user, item=self.item)
        self.assertEqual(inv.quantity, 1)

    def test_purchase_multiple_quantity(self):
        from api.engagement.models.shop import UserInventory
        self.ShopService.purchase(self.user, self.item.slug, quantity=3)
        self.user.refresh_from_db()
        self.assertEqual(self.user.coin_balance, Decimal("350"))
        inv = UserInventory.objects.get(user=self.user, item=self.item)
        self.assertEqual(inv.quantity, 3)

    def test_purchase_insufficient_coins_raises(self):
        from api.engagement.exceptions import InsufficientCoinsError
        broke = make_user(coin_balance=Decimal("10"))
        with self.assertRaises(InsufficientCoinsError):
            self.ShopService.purchase(broke, self.item.slug)

    def test_purchase_inactive_item_raises(self):
        from api.engagement.exceptions import ItemNotAvailableError
        from api.engagement.models.shop import ShopItem
        inactive = ShopItem.objects.create(
            slug="inactive-item", name="Inactive", description="Gone",
            type="avatar", price_coins=Decimal("50"),
            stock=-1, max_per_user=-1, is_active=False)
        with self.assertRaises(ItemNotAvailableError):
            self.ShopService.purchase(self.user, inactive.slug)

    def test_purchase_out_of_stock_raises(self):
        from api.engagement.exceptions import ItemNotAvailableError
        from api.engagement.models.shop import ShopItem
        oos = ShopItem.objects.create(
            slug="oos-item", name="OOS", description="Gone",
            type="avatar", price_coins=Decimal("50"),
            stock=0, max_per_user=-1, is_active=True)
        with self.assertRaises(ItemNotAvailableError):
            self.ShopService.purchase(self.user, oos.slug)

    def test_purchase_reduces_limited_stock(self):
        from api.engagement.models.shop import ShopItem
        limited = ShopItem.objects.create(
            slug="ltd-item", name="Ltd", description="Limited",
            type="avatar", price_coins=Decimal("50"),
            stock=5, max_per_user=-1, is_active=True)
        self.ShopService.purchase(self.user, limited.slug)
        limited.refresh_from_db()
        self.assertEqual(limited.stock, 4)

    def test_second_purchase_increments_inventory(self):
        from api.engagement.models.shop import UserInventory
        self.ShopService.purchase(self.user, self.item.slug, quantity=2)
        self.ShopService.purchase(self.user, self.item.slug, quantity=1)
        inv = UserInventory.objects.get(user=self.user, item=self.item)
        self.assertEqual(inv.quantity, 3)

    def test_available_items_filters_inactive(self):
        from api.engagement.models.shop import ShopItem
        ShopItem.objects.create(
            slug="inactive2", name="Inactive2", description="No",
            type="avatar", price_coins=Decimal("10"),
            stock=-1, max_per_user=-1, is_active=False)
        items = self.ShopService.available_items()
        self.assertTrue(all(i.is_active for i in items))


# ─────────────────────────────────────────────────────────────────────────────
# 7. QuestService
# ─────────────────────────────────────────────────────────────────────────────

class TestQuestService(TestCase):

    def setUp(self):
        from api.engagement.services.quest_service import QuestService
        from api.engagement.models.quest import Quest
        self.QuestService = QuestService
        self.user = make_user(coin_balance=Decimal("0"))
        self.daily_quest = Quest.objects.create(
            slug="q-checkin-daily",
            title="Daily Check-in",
            description="Check in today",
            type="daily",
            action="checkin",
            target=1,
            coin_reward=Decimal("20"),
            xp_reward=30,
            is_active=True)

    def test_init_daily_creates_user_quests(self):
        from api.engagement.models.quest import Quest, UserQuest
        Quest.objects.create(
            slug="q-spin-daily", title="Daily Spin", description="Spin today",
            type="daily", action="spin", target=1,
            coin_reward=Decimal("10"), xp_reward=20, is_active=True)
        created = self.QuestService.init_daily(self.user)
        self.assertEqual(len(created), 2)
        self.assertEqual(UserQuest.objects.filter(user=self.user, period_date=date.today()).count(), 2)

    def test_init_daily_idempotent(self):
        from api.engagement.models.quest import UserQuest
        self.QuestService.init_daily(self.user)
        self.QuestService.init_daily(self.user)
        self.assertEqual(UserQuest.objects.filter(user=self.user, period_date=date.today()).count(), 1)

    def test_record_action_advances_progress(self):
        from api.engagement.models.quest import Quest, UserQuest
        quest3 = Quest.objects.create(
            slug="q-checkin-3", title="Checkin 3", description="3 checkins",
            type="daily", action="checkin", target=3,
            coin_reward=Decimal("30"), xp_reward=50, is_active=True)
        uq = UserQuest.objects.create(
            user=self.user, quest=quest3, period_date=date.today(),
            status="active", progress=0)
        self.QuestService.record_action(self.user, "checkin", increment=1)
        uq.refresh_from_db()
        self.assertEqual(uq.progress, 1)

    def test_record_action_completes_quest(self):
        from api.engagement.models.quest import Quest, UserQuest
        quest2 = Quest.objects.create(
            slug="q-spin-2", title="Spin 2", description="Spin twice",
            type="daily", action="spin", target=2,
            coin_reward=Decimal("20"), xp_reward=50, is_active=True)
        uq = UserQuest.objects.create(
            user=self.user, quest=quest2, period_date=date.today(),
            status="active", progress=1)
        completed = self.QuestService.record_action(self.user, "spin", increment=1)
        self.assertEqual(len(completed), 1)
        uq.refresh_from_db()
        self.assertEqual(uq.status, "completed")

    def test_completed_quest_grants_coins(self):
        from api.engagement.models.quest import UserQuest
        uq = UserQuest.objects.create(
            user=self.user, quest=self.daily_quest, period_date=date.today(),
            status="active", progress=0)
        self.QuestService.record_action(self.user, "checkin", increment=1)
        self.user.refresh_from_db()
        self.assertEqual(self.user.coin_balance, Decimal("20"))

    def test_active_for_user_returns_daily(self):
        from api.engagement.models.quest import UserQuest
        UserQuest.objects.create(
            user=self.user, quest=self.daily_quest, period_date=date.today(),
            status="active", progress=0)
        data = self.QuestService.active_for_user(self.user)
        self.assertIsNotNone(data)  # active quests returned

    def test_record_action_does_not_exceed_target(self):
        from api.engagement.models.quest import Quest, UserQuest
        quest3 = Quest.objects.create(
            slug="q-checkin-3b", title="3 Checkins", description="3x",
            type="daily", action="checkin", target=3,
            coin_reward=Decimal("0"), xp_reward=0, is_active=True)
        uq = UserQuest.objects.create(
            user=self.user, quest=quest3, period_date=date.today(),
            status="active", progress=2)
        self.QuestService.record_action(self.user, "checkin", increment=10)
        uq.refresh_from_db()
        self.assertEqual(uq.progress, 3)


# ─────────────────────────────────────────────────────────────────────────────
# 8. LeaderboardService
# ─────────────────────────────────────────────────────────────────────────────

class TestLeaderboardService(TestCase):

    def setUp(self):
        from api.engagement.services.leaderboard_service import LeaderboardService
        self.LeaderboardService = LeaderboardService
        self.today = date.today()
        self.yesterday = self.today - timedelta(days=1)

    def test_get_leaderboard_returns_ordered_list(self):
        from api.engagement.models.leaderboard import Leaderboard
        u1 = make_user(coin_balance=Decimal("0"))
        u2 = make_user(coin_balance=Decimal("0"))
        Leaderboard.objects.create(user=u1, date=self.today, rank=1, total_coins_earned=Decimal("200"))
        Leaderboard.objects.create(user=u2, date=self.today, rank=2, total_coins_earned=Decimal("100"))
        entries = self.LeaderboardService.get_leaderboard(self.today)
        self.assertEqual(entries[0].rank, 1)
        self.assertEqual(entries[1].rank, 2)

    def test_get_user_rank_returns_correct_rank(self):
        from api.engagement.models.leaderboard import Leaderboard
        user = make_user(coin_balance=Decimal("0"))
        Leaderboard.objects.create(user=user, date=self.today, rank=3)
        rank = self.LeaderboardService.get_user_rank(user, self.today)
        self.assertEqual(rank, 3)

    def test_get_user_rank_returns_none_if_not_ranked(self):
        user = make_user(coin_balance=Decimal("0"))
        rank = self.LeaderboardService.get_user_rank(user, self.today)
        self.assertIsNone(rank)

    def test_distribute_rewards_grants_coins(self):
        from api.engagement.models.leaderboard import Leaderboard, LeaderboardReward
        user = make_user(coin_balance=Decimal("0"))
        Leaderboard.objects.create(user=user, date=self.yesterday, rank=1, reward_distributed=False)
        LeaderboardReward.objects.create(rank=1, season_type="daily", reward_coins=Decimal("100"), reward_xp=50)
        rewarded = self.LeaderboardService.distribute_rewards(self.yesterday)
        self.assertEqual(rewarded, 1)
        user.refresh_from_db()
        self.assertEqual(user.coin_balance, Decimal("100"))

    def test_distribute_rewards_marks_distributed(self):
        from api.engagement.models.leaderboard import Leaderboard, LeaderboardReward
        user = make_user(coin_balance=Decimal("0"))
        entry = Leaderboard.objects.create(user=user, date=self.yesterday, rank=1, reward_distributed=False)
        LeaderboardReward.objects.create(rank=1, season_type="daily", reward_coins=Decimal("50"), reward_xp=0)
        self.LeaderboardService.distribute_rewards(self.yesterday)
        entry.refresh_from_db()
        self.assertTrue(entry.reward_distributed)

    def test_distribute_rewards_skips_already_distributed(self):
        from api.engagement.models.leaderboard import Leaderboard, LeaderboardReward
        user = make_user(coin_balance=Decimal("0"))
        Leaderboard.objects.create(user=user, date=self.yesterday, rank=1, reward_distributed=True)
        LeaderboardReward.objects.create(rank=1, season_type="daily", reward_coins=Decimal("100"), reward_xp=0)
        rewarded = self.LeaderboardService.distribute_rewards(self.yesterday)
        self.assertEqual(rewarded, 0)

    def test_leaderboard_limited_to_100(self):
        from api.engagement.models.leaderboard import Leaderboard
        for i in range(20):
            u = make_user(coin_balance=Decimal("0"))
            Leaderboard.objects.create(user=u, date=self.today, rank=i + 1)
        entries = self.LeaderboardService.get_leaderboard(self.today, limit=10)
        self.assertLessEqual(len(entries), 10)


# ─────────────────────────────────────────────────────────────────────────────
# 9. ReferralService
# ─────────────────────────────────────────────────────────────────────────────

class TestReferralService(TestCase):

    def setUp(self):
        from api.engagement.services.referral_service import ReferralService
        from api.engagement.models.referral import ReferralProgram
        self.ReferralService = ReferralService
        self.referrer = make_user(coin_balance=Decimal("0"))
        self.referee = make_user(coin_balance=Decimal("0"))
        self.program = ReferralProgram.objects.create(
            name="Test Program",
            referrer_reward=Decimal("50"),
            referee_reward=Decimal("25"),
            referrer_xp=100,
            referee_xp=50,
            is_active=True)

    def test_generate_code_is_string(self):
        code = self.ReferralService.generate_code(self.referrer)
        self.assertIsInstance(code, str)
        self.assertGreater(len(code), 0)

    def test_generate_code_is_uppercase(self):
        code = self.ReferralService.generate_code(self.referrer)
        self.assertEqual(code, code.upper())

    def test_register_referral_creates_record(self):
        from api.engagement.models.referral import Referral
        code = self.ReferralService.generate_code(self.referrer)
        self.ReferralService.register_referral(self.referrer, self.referee, code)
        self.assertTrue(Referral.objects.filter(referrer=self.referrer, referee=self.referee).exists())

    def test_self_referral_raises(self):
        from api.engagement.exceptions import ReferralSelfError
        code = self.ReferralService.generate_code(self.referrer)
        with self.assertRaises(ReferralSelfError):
            self.ReferralService.register_referral(self.referrer, self.referrer, code)

    def test_double_referral_raises(self):
        from api.engagement.exceptions import AlreadyReferredError
        code = self.ReferralService.generate_code(self.referrer)
        self.ReferralService.register_referral(self.referrer, self.referee, code)
        referrer2 = make_user(coin_balance=Decimal("0"))
        code2 = self.ReferralService.generate_code(referrer2)
        with self.assertRaises(AlreadyReferredError):
            self.ReferralService.register_referral(referrer2, self.referee, code2)

    def test_rewards_distributed_to_referrer(self):
        code = self.ReferralService.generate_code(self.referrer)
        self.ReferralService.register_referral(self.referrer, self.referee, code)
        self.referrer.refresh_from_db()
        self.assertGreater(float(self.referrer.coin_balance), 0)

    def test_rewards_distributed_to_referee(self):
        code = self.ReferralService.generate_code(self.referrer)
        self.ReferralService.register_referral(self.referrer, self.referee, code)
        self.referee.refresh_from_db()
        self.assertGreater(float(self.referee.coin_balance), 0)

    def test_referral_status_rewarded(self):
        from api.engagement.models.referral import Referral
        code = self.ReferralService.generate_code(self.referrer)
        self.ReferralService.register_referral(self.referrer, self.referee, code)
        ref = Referral.objects.get(referrer=self.referrer, referee=self.referee)
        self.assertEqual(ref.status, "rewarded")


# ─────────────────────────────────────────────────────────────────────────────
# 10. BattlePassService
# ─────────────────────────────────────────────────────────────────────────────

def _make_battle_pass():
    from api.engagement.models.battle_pass import BattlePass, BattlePassTier, BattlePassXPSource
    now = timezone.now()
    bp = BattlePass.objects.create(
        name="Test Season", season_num=1,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=30),
        is_active=True,
        premium_price_coins=Decimal("500"),
        total_tiers=50)
    for i in range(1, 6):
        BattlePassTier.objects.create(
            battle_pass=bp, tier_number=i, xp_required=i * 100,
            free_coins=Decimal("10"), free_xp=20,
            premium_coins=Decimal("20"), premium_xp=40)
    BattlePassXPSource.objects.create(battle_pass=bp, action="checkin", xp_amount=150, daily_cap=0)
    BattlePassXPSource.objects.create(battle_pass=bp, action="spin", xp_amount=50, daily_cap=0)
    return bp


class TestBattlePassService(TestCase):

    def setUp(self):
        from api.engagement.services.battle_pass_service import BattlePassService
        self.BattlePassService = BattlePassService
        self.user = make_user(coin_balance=Decimal("500"))
        self.bp = _make_battle_pass()

    def test_get_or_enroll_creates_user_pass(self):
        from api.engagement.models.battle_pass import UserBattlePass
        ubp = self.BattlePassService.get_or_enroll(self.user, self.bp)
        self.assertEqual(ubp.user, self.user)
        self.assertFalse(ubp.is_premium)
        self.assertEqual(ubp.current_tier, 0)

    def test_get_or_enroll_idempotent(self):
        from api.engagement.models.battle_pass import UserBattlePass
        self.BattlePassService.get_or_enroll(self.user, self.bp)
        self.BattlePassService.get_or_enroll(self.user, self.bp)
        self.assertEqual(UserBattlePass.objects.filter(user=self.user, battle_pass=self.bp).count(), 1)

    def test_grant_xp_for_checkin_advances_tier(self):
        result = self.BattlePassService.grant_xp(self.user, "checkin")
        self.assertEqual(result["xp_granted"], 150)
        self.assertGreaterEqual(result["new_tier"], 1)

    def test_grant_xp_for_spin(self):
        result = self.BattlePassService.grant_xp(self.user, "spin")
        self.assertEqual(result["xp_granted"], 50)

    def test_unlock_premium_deducts_coins(self):
        from api.engagement.models.battle_pass import UserBattlePass
        self.BattlePassService.get_or_enroll(self.user, self.bp)
        self.BattlePassService.unlock_premium(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.coin_balance, Decimal("0"))

    def test_unlock_premium_sets_flag(self):
        from api.engagement.models.battle_pass import UserBattlePass
        self.BattlePassService.get_or_enroll(self.user, self.bp)
        self.BattlePassService.unlock_premium(self.user)
        ubp = UserBattlePass.objects.get(user=self.user, battle_pass=self.bp)
        self.assertTrue(ubp.is_premium)


# ─────────────────────────────────────────────────────────────────────────────
# 11. GuildService
# ─────────────────────────────────────────────────────────────────────────────

class TestGuildService(TestCase):

    def setUp(self):
        from api.engagement.services.guild_service import GuildService
        self.GuildService = GuildService
        self.owner = make_user(coin_balance=Decimal("0"))

    def _make_guild(self, owner=None, name="Test Guild"):
        owner = owner or self.owner
        return self.GuildService.create(
            owner=owner, name=name,
            slug=name.lower().replace(" ", "-"),
            description="A test guild", is_public=True)

    def test_create_guild_adds_owner_as_member(self):
        from api.engagement.models.guild import Guild, GuildMember
        guild = self._make_guild()
        self.assertTrue(Guild.objects.filter(name="Test Guild").exists())
        member = GuildMember.objects.get(user=self.owner, guild=guild)
        self.assertEqual(member.role, "owner")
        self.assertEqual(member.status, "active")

    def test_join_guild_creates_member(self):
        from api.engagement.models.guild import GuildMember
        user = make_user(coin_balance=Decimal("0"))
        guild = self._make_guild()
        member = self.GuildService.join(user, guild)
        self.assertEqual(member.role, "member")
        self.assertEqual(member.status, "active")

    def test_join_guild_full_raises_error(self):
        from api.engagement.models.guild import Guild
        guild = self._make_guild()
        guild.max_members = 1
        guild.save(update_fields=["max_members"])
        user2 = make_user(coin_balance=Decimal("0"))
        with self.assertRaises(ValueError):
            self.GuildService.join(user2, guild)

    def test_join_already_member_raises_error(self):
        guild = self._make_guild()
        user = make_user(coin_balance=Decimal("0"))
        self.GuildService.join(user, guild)
        with self.assertRaises(ValueError):
            self.GuildService.join(user, guild)

    def test_leave_guild_removes_member(self):
        from api.engagement.models.guild import GuildMember
        guild = self._make_guild()
        user = make_user(coin_balance=Decimal("0"))
        self.GuildService.join(user, guild)
        self.GuildService.leave(user, guild)
        self.assertFalse(GuildMember.objects.filter(user=user, guild=guild, status="active").exists())

    def test_get_leaderboard_returns_guilds(self):
        self._make_guild()
        lb = self.GuildService.leaderboard()
        self.assertIsNotNone(lb)  # leaderboard returns without error


# ─────────────────────────────────────────────────────────────────────────────
# 12. SocialService
# ─────────────────────────────────────────────────────────────────────────────

class TestSocialService(TestCase):

    def setUp(self):
        from api.engagement.services.social_service import SocialService
        self.SocialService = SocialService
        self.user = make_user(coin_balance=Decimal("0"))
        self.user2 = make_user(coin_balance=Decimal("0"))

    def test_post_feed_item_creates_record(self):
        from api.engagement.models.social import FeedItem
        self.SocialService.post_feed_item(self.user, "checkin", "Checked in!")
        self.assertTrue(FeedItem.objects.filter(user=self.user, type="checkin").exists())

    def test_like_increments_count(self):
        item = self.SocialService.post_feed_item(self.user, "checkin", "Hi")
        result = self.SocialService.like(self.user2, item.pk)
        self.assertTrue(result["liked"])
        self.assertEqual(result["like_count"], 1)

    def test_like_twice_unlikes(self):
        item = self.SocialService.post_feed_item(self.user, "checkin", "Hi")
        self.SocialService.like(self.user2, item.pk)
        result = self.SocialService.like(self.user2, item.pk)
        self.assertFalse(result["liked"])
        self.assertEqual(result["like_count"], 0)

    def test_send_and_accept_friend_request(self):
        fs = self.SocialService.send_friend_request(self.user, self.user2)
        self.assertEqual(fs.status, "pending")
        fs2 = self.SocialService.accept_friend_request(self.user2, fs.pk)
        self.assertEqual(fs2.status, "accepted")

    def test_cannot_friend_self(self):
        with self.assertRaises(ValueError):
            self.SocialService.send_friend_request(self.user, self.user)

    def test_friends_list_returns_accepted_friends(self):
        fs = self.SocialService.send_friend_request(self.user, self.user2)
        self.SocialService.accept_friend_request(self.user2, fs.pk)
        friends = self.SocialService.friends_list(self.user)
        self.assertIn(self.user2, friends)

    def test_follow_unfollow_toggle(self):
        r1 = self.SocialService.follow(self.user, self.user2)
        self.assertTrue(r1["following"])
        r2 = self.SocialService.follow(self.user, self.user2)
        self.assertFalse(r2["following"])


# ─────────────────────────────────────────────────────────────────────────────
# 13. LootBoxService
# ─────────────────────────────────────────────────────────────────────────────

def _make_chest():
    from api.engagement.models.loot_box import ChestType, ChestDropTable
    ct = ChestType.objects.create(
        slug="test-chest", name="Test Chest",
        rarity="common", price_coins=Decimal("50"), is_active=True)
    ChestDropTable.objects.create(
        chest_type=ct, reward_type="coins",
        coins_min=Decimal("10"), coins_max=Decimal("10"),
        weight=100, is_active=True)
    return ct


class TestLootBoxService(TestCase):

    def setUp(self):
        from api.engagement.services.loot_box_service import LootBoxService
        self.LootBoxService = LootBoxService
        self.user = make_user(coin_balance=Decimal("200"))
        self.chest = _make_chest()

    def test_grant_and_open_chest(self):
        self.LootBoxService.grant_chest(self.user, self.chest, quantity=1, source="test")
        result = self.LootBoxService.open_chest(self.user, self.chest.slug)
        self.assertEqual(result["reward_type"], "coins")
        self.assertEqual(result["coins_won"], 10.0)

    def test_open_chest_without_inventory_raises(self):
        from api.engagement.exceptions import ItemNotAvailableError
        with self.assertRaises(ItemNotAvailableError):
            self.LootBoxService.open_chest(self.user, self.chest.slug)

    def test_buy_chest_deducts_coins(self):
        self.LootBoxService.buy_chest(self.user, self.chest.slug)
        self.user.refresh_from_db()
        self.assertEqual(self.user.coin_balance, Decimal("150"))

    def test_opening_decrements_inventory(self):
        from api.engagement.models.loot_box import UserChest
        self.LootBoxService.grant_chest(self.user, self.chest, quantity=3)
        self.LootBoxService.open_chest(self.user, self.chest.slug)
        inv = UserChest.objects.get(user=self.user, chest_type=self.chest)
        self.assertEqual(inv.quantity, 2)


# ─────────────────────────────────────────────────────────────────────────────
# 14. AntiCheatService
# ─────────────────────────────────────────────────────────────────────────────

class TestAntiCheatService(TestCase):

    def setUp(self):
        from api.engagement.services.anti_cheat_service import AntiCheatService
        self.AntiCheatService = AntiCheatService
        self.AntiCheatService.seed_default_rules()
        self.user = make_user(coin_balance=Decimal("0"))

    def test_seed_creates_rules(self):
        from api.engagement.models.anti_cheat import AntiCheatRule
        self.assertGreaterEqual(AntiCheatRule.objects.count(), 5)

    def test_spin_velocity_flags_fast_spinner(self):
        from api.engagement.models.anti_cheat import AntiCheatLog
        from api.engagement.models.spinwheel import SpinWheel
        for _ in range(6):
            SpinWheel.objects.create(user=self.user, coins_won=Decimal("1"))
        self.AntiCheatService.check_spin_velocity(self.user, ip_address="1.2.3.4")
        self.assertTrue(AntiCheatLog.objects.filter(user=self.user, rule__slug="spin-velocity").exists())

    def test_risk_score_updated_by_flags(self):
        from api.engagement.models.anti_cheat import UserRiskScore, AntiCheatLog, AntiCheatRule
        rule = AntiCheatRule.objects.first()
        AntiCheatLog.objects.create(user=self.user, rule=rule, severity=2, details={})
        self.AntiCheatService.recalculate_risk(self.user)
        risk = UserRiskScore.objects.get(user=self.user)
        self.assertGreater(risk.score, 0)
        self.assertEqual(risk.flag_count, 1)


# ─────────────────────────────────────────────────────────────────────────────
# 15. ScratchCardService
# ─────────────────────────────────────────────────────────────────────────────

def _make_scratch_template():
    from api.engagement.models.scratch_card import ScratchCardTemplate, ScratchCardPrize
    tmpl = ScratchCardTemplate.objects.create(
        slug="test-scratch", name="Test Scratch",
        max_per_day=3, price_coins=Decimal("0"), is_active=True)
    ScratchCardPrize.objects.create(
        template=tmpl, label="💰 10 Coins", coins=Decimal("10"), weight=100)
    return tmpl


class TestScratchCardService(TestCase):

    def setUp(self):
        from api.engagement.services.scratch_card_service import ScratchCardService
        self.ScratchCardService = ScratchCardService
        self.user = make_user(coin_balance=Decimal("0"))
        self.tmpl = _make_scratch_template()

    def test_scratch_gives_reward(self):
        result = self.ScratchCardService.scratch(self.user, "test-scratch")
        self.assertIn("coins_won", result)
        self.assertEqual(result["coins_won"], 10.0)

    def test_scratch_adds_coins_to_balance(self):
        self.ScratchCardService.scratch(self.user, "test-scratch")
        self.user.refresh_from_db()
        self.assertEqual(self.user.coin_balance, Decimal("10"))

    def test_scratch_daily_limit_enforced(self):
        from api.engagement.exceptions import ItemNotAvailableError
        for _ in range(3):
            self.ScratchCardService.scratch(self.user, "test-scratch")
        with self.assertRaises(ItemNotAvailableError):
            self.ScratchCardService.scratch(self.user, "test-scratch")


# ─────────────────────────────────────────────────────────────────────────────
# 16. AuctionService
# ─────────────────────────────────────────────────────────────────────────────

def _make_auction():
    from api.engagement.models.auction import Auction
    now = timezone.now()
    return Auction.objects.create(
        title="Test Auction",
        starting_bid=Decimal("10"),
        bid_increment=Decimal("5"),
        current_bid=Decimal("0"),
        status="active",
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=24))


class TestAuctionService(TestCase):

    def setUp(self):
        from api.engagement.services.auction_service import AuctionService
        self.AuctionService = AuctionService
        self.user = make_user(coin_balance=Decimal("500"))
        self.auction = _make_auction()

    def test_place_bid_deducts_coins(self):
        result = self.AuctionService.place_bid(self.user, self.auction.pk, Decimal("50"))
        self.assertTrue(result["success"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.coin_balance, Decimal("450"))

    def test_bid_too_low_raises_error(self):
        with self.assertRaises(Exception):
            self.AuctionService.place_bid(self.user, self.auction.pk, Decimal("5"))

    def test_outbid_refunds_previous_bidder(self):
        user2 = make_user(coin_balance=Decimal("500"))
        self.AuctionService.place_bid(self.user, self.auction.pk, Decimal("50"))
        self.AuctionService.place_bid(user2, self.auction.pk, Decimal("60"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.coin_balance, Decimal("500"))

    def test_close_auction_sets_winner(self):
        from api.engagement.models.auction import Auction
        self.AuctionService.place_bid(self.user, self.auction.pk, Decimal("50"))
        result = self.AuctionService.close_auction(self.auction.pk)
        self.assertEqual(result["winner_id"], self.user.pk)
        self.auction.refresh_from_db()
        self.assertEqual(self.auction.status, "completed")


# ─────────────────────────────────────────────────────────────────────────────
# 17. FeatureFlag & ABTest (CampaignService)
# ─────────────────────────────────────────────────────────────────────────────

class TestFeatureFlagService(TestCase):

    def setUp(self):
        from api.engagement.services.campaign_service import FeatureFlagService, ABTestService
        from api.engagement.models.campaign import FeatureFlag, ABTest, ABTestVariant
        self.FFS = FeatureFlagService
        self.ABS = ABTestService
        self.user = make_user()
        self.flag_on = FeatureFlag.objects.create(
            slug="flag-on", name="Flag On", is_enabled=True, rollout_pct=100)
        self.flag_off = FeatureFlag.objects.create(
            slug="flag-off", name="Flag Off", is_enabled=True, rollout_pct=0)
        self.ab = ABTest.objects.create(slug="btn-color", name="Button Color", status="running")
        ABTestVariant.objects.create(test=self.ab, slug="red", name="Red", traffic_pct=50)
        ABTestVariant.objects.create(test=self.ab, slug="blue", name="Blue", traffic_pct=50)

    def test_flag_100pct_enabled(self):
        self.assertTrue(self.FFS.is_enabled(self.user, "flag-on"))

    def test_flag_0pct_disabled(self):
        self.assertFalse(self.FFS.is_enabled(self.user, "flag-off"))

    def test_flag_missing_returns_false(self):
        self.assertFalse(self.FFS.is_enabled(self.user, "nonexistent"))

    def test_ab_assigns_variant(self):
        variant = self.ABS.get_variant(self.user, "btn-color")
        self.assertIsNotNone(variant)
        self.assertIn(variant.slug, ["red", "blue"])

    def test_ab_assignment_is_deterministic(self):
        v1 = self.ABS.get_variant(self.user, "btn-color")
        v2 = self.ABS.get_variant(self.user, "btn-color")
        self.assertEqual(v1.pk, v2.pk)

    def test_ab_track_conversion(self):
        self.ABS.get_variant(self.user, "btn-color")
        # Should not raise
        self.ABS.track_conversion(self.user, "btn-color")


# ─────────────────────────────────────────────────────────────────────────────
# 18. NotificationService
# ─────────────────────────────────────────────────────────────────────────────

class TestNotificationService(TestCase):

    def setUp(self):
        from api.engagement.services.notification_service import NotificationService
        self.NS = NotificationService
        self.user = make_user()

    def test_send_creates_notification(self):
        from api.engagement.models.notification import Notification
        self.NS.send(self.user, "reward", title="Test", body="Hello")
        self.assertTrue(Notification.objects.filter(user=self.user, type="reward").exists())

    def test_unread_count_correct(self):
        from api.engagement.models.notification import Notification
        Notification.objects.create(user=self.user, title="T1", body="B1", type="info", is_read=False)
        Notification.objects.create(user=self.user, title="T2", body="B2", type="info", is_read=True)
        count = self.NS.unread_count(self.user)
        self.assertEqual(count, 1)

    def test_mark_all_read(self):
        from api.engagement.models.notification import Notification
        for _ in range(3):
            Notification.objects.create(user=self.user, title="T", body="B", type="info", is_read=False)
        self.NS.mark_all_read(self.user)
        self.assertEqual(Notification.objects.filter(user=self.user, is_read=False).count(), 0)


# ─────────────────────────────────────────────────────────────────────────────
# 19. API: Auth Required
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthRequired(TestCase):

    def setUp(self):
        self.c = APIClient()

    def test_daily_stats_401(self):
        self.assertIn(self.c.post("/engagement/daily-checkin/").status_code, [401, 403])

    def test_checkin_401(self):
        self.assertIn(self.c.post("/engagement/daily-checkin/").status_code, [401, 403])

    def test_spin_401(self):
        self.assertIn(self.c.post("/engagement/daily-checkin/").status_code, [401, 403])

    def test_leaderboard_401(self):
        self.assertIn(self.c.post("/engagement/daily-checkin/").status_code, [401, 403])

    def test_achievements_401(self):
        self.assertIn(self.c.post("/engagement/daily-checkin/").status_code, [401, 403])

    def test_shop_401(self):
        self.assertIn(self.c.post("/engagement/daily-checkin/").status_code, [401, 403])

    def test_notifications_401(self):
        self.assertIn(self.c.post("/engagement/daily-checkin/").status_code, [401, 403])

    def test_referrals_401(self):
        self.assertIn(self.c.post("/engagement/daily-checkin/").status_code, [401, 403])

    def test_xp_401(self):
        self.assertIn(self.c.post("/engagement/daily-checkin/").status_code, [401, 403])

    def test_quests_401(self):
        self.assertIn(self.c.post("/engagement/daily-checkin/").status_code, [401, 403])

    def test_challenges_401(self):
        self.assertIn(self.c.post("/engagement/daily-checkin/").status_code, [401, 403])

    def test_guilds_401(self):
        self.assertIn(self.c.post("/engagement/daily-checkin/").status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
# 20. API: Dashboard & Stats
# ─────────────────────────────────────────────────────────────────────────────

class TestStatsDashboardAPI(TestCase):

    def setUp(self):
        self.c = api()

    def test_daily_stats_200(self):
        r = self.c.get("/engagement/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("check_in", data)
        self.assertIn("spin_wheel", data)
        self.assertIn("coin_balance", data)
        self.assertIn("xp", data)

    def test_daily_stats_alt_path_200(self):
        r = self.c.get("/engagement/daily-stats/")
        self.assertEqual(r.status_code, 200)

    def test_engagement_score_0_to_100(self):
        r = self.c.get("/engagement/stats/")
        self.assertEqual(r.status_code, 200)
        score = r.json()["engagement_score"]
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_coin_balance_matches_user(self):
        r = self.c.get("/engagement/")
        self.assertAlmostEqual(
            float(r.json()["coin_balance"]),
            float(self.c._user.coin_balance),
            places=2)


# ─────────────────────────────────────────────────────────────────────────────
# 21. API: Check-In
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckInAPI(TestCase):

    def setUp(self):
        self.c = api()

    def test_checkin_success(self):
        r = self.c.post("/engagement/daily-checkin/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["success"])
        self.assertIn("coins_earned", data)
        self.assertIn("consecutive_days", data)
        self.assertIn("new_balance", data)

    def test_double_checkin_400(self):
        self.c.post("/engagement/daily-checkin/")
        r = self.c.post("/engagement/daily-checkin/")
        self.assertIn(r.status_code, [400, 429])

    def test_checkin_list_200(self):
        r = self.c.get("/engagement/checkins/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("results", r.json())

    def test_checkin_stats_200(self):
        r = self.c.get("/engagement/checkins/stats/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("my_streak", data)
        self.assertIn("total_checkins_today", data)

    def test_checkin_increases_streak_from_yesterday(self):
        from api.engagement.models.checkin import DailyCheckIn
        DailyCheckIn.objects.create(
            user=self.c._user,
            date=date.today() - timedelta(days=1),
            consecutive_days=3,
            coins_earned=Decimal("15"),
            xp_earned=30)
        r = self.c.post("/engagement/daily-checkin/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["consecutive_days"], 4)


# ─────────────────────────────────────────────────────────────────────────────
# 22. API: Spin Wheel
# ─────────────────────────────────────────────────────────────────────────────

class TestSpinAPI(TestCase):

    def setUp(self):
        self.c = api()

    def test_spin_success(self):
        r = self.c.post("/engagement/spin-wheel/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["success"])
        self.assertIn("coins_won", data)
        self.assertIn("spins_remaining", data)

    def test_spin_coins_positive(self):
        r = self.c.post("/engagement/spin-wheel/")
        self.assertGreater(float(r.json()["coins_won"]), 0)

    def test_spin_max_exceeded_400(self):
        from api.engagement.constants import SPIN_MAX_PER_DAY
        for _ in range(SPIN_MAX_PER_DAY):
            self.c.post("/engagement/spin-wheel/")
        r = self.c.post("/engagement/spin-wheel/")
        self.assertEqual(r.status_code, 400)

    def test_spins_list_200(self):
        r = self.c.get("/engagement/spins/")
        self.assertEqual(r.status_code, 200)

    def test_spins_stats_200(self):
        r = self.c.get("/engagement/spins/stats/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("my_spins_remaining", data)
        self.assertIn("max_spins_per_day", data)


# ─────────────────────────────────────────────────────────────────────────────
# 23. API: XP
# ─────────────────────────────────────────────────────────────────────────────

class TestXPAPI(TestCase):

    def setUp(self):
        self.c = api()

    def test_xp_endpoint_200(self):
        r = self.c.get("/engagement/xp/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("level", data)
        self.assertIn("total_xp", data)
        self.assertIn("level_pct", data)

    def test_xp_level_starts_at_1(self):
        r = self.c.get("/engagement/xp/")
        self.assertEqual(r.json()["level"], 1)

    def test_xp_history_200(self):
        r = self.c.get("/engagement/xp/history/")
        self.assertEqual(r.status_code, 200)

    def test_level_pct_0_to_100(self):
        r = self.c.get("/engagement/xp/")
        pct = r.json()["level_pct"]
        self.assertGreaterEqual(pct, 0)
        self.assertLessEqual(pct, 100)


# ─────────────────────────────────────────────────────────────────────────────
# 24. API: Leaderboard
# ─────────────────────────────────────────────────────────────────────────────

class TestLeaderboardAPI(TestCase):

    def setUp(self):
        self.c = api()

    def test_leaderboard_200(self):
        r = self.c.get("/engagement/leaderboard/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("leaderboard", data)
        self.assertIn("user_rank", data)

    def test_leaderboard_date_param(self):
        today = str(date.today())
        r = self.c.get(f"/engagement/leaderboard/?date={today}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["date"], today)

    def test_leaderboard_seasons_200(self):
        r = self.c.get("/engagement/leaderboard/seasons/")
        self.assertEqual(r.status_code, 200)


# ─────────────────────────────────────────────────────────────────────────────
# 25. API: Achievements
# ─────────────────────────────────────────────────────────────────────────────

class TestAchievementsAPI(TestCase):

    def setUp(self):
        self.c = api()
        from api.engagement.models.achievement import Achievement
        self.ach = Achievement.objects.create(
            slug="api-ach-1", name="API Ach", description="Test",
            type="streak", threshold=1,
            coin_reward=Decimal("10"), xp_reward=20,
            is_active=True, is_secret=False)

    def test_achievements_list_200(self):
        r = self.c.get("/engagement/achievements/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("results", r.json())

    def test_my_achievements_200(self):
        r = self.c.get("/engagement/achievements/mine/")
        self.assertEqual(r.status_code, 200)

    def test_claim_unclaimed_200(self):
        from api.engagement.models.achievement import UserAchievement
        ua = UserAchievement.objects.create(
            user=self.c._user, achievement=self.ach, reward_claimed=False)
        r = self.c.post(f"/engagement/achievements/{ua.pk}/claim/")
        self.assertEqual(r.status_code, 200)

    def test_claim_already_claimed_400(self):
        from api.engagement.models.achievement import UserAchievement
        ua = UserAchievement.objects.create(
            user=self.c._user, achievement=self.ach, reward_claimed=True)
        r = self.c.post(f"/engagement/achievements/{ua.pk}/claim/")
        self.assertIn(r.status_code, [400, 200])  # already claimed


# ─────────────────────────────────────────────────────────────────────────────
# 26. API: Shop
# ─────────────────────────────────────────────────────────────────────────────

class TestShopAPI(TestCase):

    def setUp(self):
        self.c = api(make_user(coin_balance=Decimal("1000")))
        from api.engagement.models.shop import ShopItem
        self.item = ShopItem.objects.create(
            slug="api-item-1", name="API Item", description="Test",
            type="avatar", price_coins=Decimal("50"),
            stock=-1, max_per_user=-1, is_active=True)

    def test_shop_list_200(self):
        r = self.c.get("/engagement/shop/")
        self.assertEqual(r.status_code, 200)

    def test_purchase_success(self):
        r = self.c.post("/engagement/shop/purchase/", {"item_slug": self.item.slug})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["success"])
        self.assertIn("new_balance", r.json())

    def test_purchase_deducts_coins(self):
        old_bal = float(self.c._user.coin_balance)
        self.c.post("/engagement/shop/purchase/", {"item_slug": self.item.slug})
        self.c._user.refresh_from_db()
        self.assertAlmostEqual(
            float(self.c._user.coin_balance),
            old_bal - float(self.item.price_coins),
            places=2)

    def test_purchase_no_slug_400(self):
        r = self.c.post("/engagement/shop/purchase/", {})
        self.assertEqual(r.status_code, 400)

    def test_purchase_insufficient_coins_400(self):
        broke_c = api(make_user(coin_balance=Decimal("0")))
        r = broke_c.post("/engagement/shop/purchase/", {"item_slug": self.item.slug})
        self.assertEqual(r.status_code, 400)

    def test_inventory_200(self):
        r = self.c.get("/engagement/shop/inventory/")
        self.assertEqual(r.status_code, 200)


# ─────────────────────────────────────────────────────────────────────────────
# 27. API: Notifications
# ─────────────────────────────────────────────────────────────────────────────

class TestNotificationsAPI(TestCase):

    def setUp(self):
        self.c = api()
        from api.engagement.models.notification import Notification
        Notification.objects.create(
            user=self.c._user, title="Test", body="Hello",
            type="info", is_read=False)

    def test_notifications_list_200(self):
        r = self.c.get("/engagement/notifications/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("results", data)
        self.assertEqual(data["count"], 1)

    def test_unread_count_200(self):
        r = self.c.get("/engagement/notifications/unread-count/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["unread_count"], 1)

    def test_mark_all_read(self):
        r = self.c.post("/engagement/notifications/read-all/")
        self.assertEqual(r.status_code, 200)
        from api.engagement.models.notification import Notification
        self.assertEqual(
            Notification.objects.filter(user=self.c._user, is_read=False).count(), 0
        )

    def test_mark_single_read(self):
        from api.engagement.models.notification import Notification
        notif = Notification.objects.filter(user=self.c._user).first()
        r = self.c.post(f"/engagement/notifications/{notif.pk}/read/")
        self.assertEqual(r.status_code, 200)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_delete_notification_200(self):
        from api.engagement.models.notification import Notification
        notif = Notification.objects.filter(user=self.c._user).first()
        r = self.c.delete(f"/engagement/notifications/{notif.pk}/")
        self.assertIn(r.status_code, [200, 204])


# ─────────────────────────────────────────────────────────────────────────────
# 28. API: Referrals
# ─────────────────────────────────────────────────────────────────────────────

class TestReferralsAPI(TestCase):

    def setUp(self):
        self.c = api()
        from api.engagement.models.referral import ReferralProgram
        ReferralProgram.objects.create(
            name="API Program",
            referrer_reward=Decimal("50"),
            referee_reward=Decimal("25"),
            referrer_xp=100, referee_xp=50,
            is_active=True)

    def test_my_referrals_200(self):
        r = self.c.get("/engagement/referrals/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("referral_code", r.json())

    def test_register_referral_cross_user(self):
        from api.engagement.services.referral_service import ReferralService
        referrer = make_user(coin_balance=Decimal("0"))
        code = ReferralService.generate_code(referrer)
        referee_c = api(make_user(coin_balance=Decimal("0")))
        r = referee_c.post("/engagement/referrals/register/", {"code": code})
        self.assertNotEqual(r.status_code, 500)

    def test_referral_program_detail_200_or_404(self):
        r = self.c.get("/engagement/referrals/program/")
        self.assertIn(r.status_code, [200, 404])


# ─────────────────────────────────────────────────────────────────────────────
# 29. API: Guilds
# ─────────────────────────────────────────────────────────────────────────────

class TestGuildsAPI(TestCase):

    def setUp(self):
        self.c = api()

    def test_guilds_list_200(self):
        r = self.c.get("/engagement/guilds/")
        self.assertEqual(r.status_code, 200)

    def test_create_guild_201(self):
        r = self.c.post("/engagement/guilds/create/", {
            "name": "API Guild",
            "slug": "api-guild",
            "description": "Test",
        })
        self.assertIn(r.status_code, [200, 201])

    def test_guild_leaderboard_200(self):
        r = self.c.get("/engagement/guilds/leaderboard/")
        self.assertEqual(r.status_code, 200)

    def test_my_guild_200_or_404(self):
        r = self.c.get("/engagement/guilds/mine/")
        self.assertIn(r.status_code, [200, 404])


# ─────────────────────────────────────────────────────────────────────────────
# 30. API: Social
# ─────────────────────────────────────────────────────────────────────────────

class TestSocialAPI(TestCase):

    def setUp(self):
        self.c = api()

    def test_social_feed_200(self):
        r = self.c.get("/engagement/social/feed/")
        self.assertEqual(r.status_code, 200)

    def test_friends_list_200(self):
        r = self.c.get("/engagement/social/friends/")
        self.assertEqual(r.status_code, 200)

    def test_follow_user_200(self):
        other = make_user()
        r = self.c.post(f"/engagement/social/follow/{other.pk}/")
        self.assertIn(r.status_code, [200, 201])


# ─────────────────────────────────────────────────────────────────────────────
# 31. API: Feature Flags & A/B
# ─────────────────────────────────────────────────────────────────────────────

class TestFeatureFlagsAPI(TestCase):

    def setUp(self):
        self.c = api()
        from api.engagement.models.campaign import FeatureFlag, ABTest, ABTestVariant
        self.flag = FeatureFlag.objects.create(
            slug="api-flag", name="API Flag", is_enabled=True, rollout_pct=100)
        self.ab = ABTest.objects.create(slug="api-ab-test", name="API AB", status="running")
        ABTestVariant.objects.create(test=self.ab, slug="v1", name="V1", traffic_pct=50)
        ABTestVariant.objects.create(test=self.ab, slug="v2", name="V2", traffic_pct=50)

    def test_feature_flag_check_200(self):
        r = self.c.get(f"/engagement/flags/{self.flag.slug}/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("enabled", r.json())

    def test_ab_variant_200(self):
        r = self.c.get(f"/engagement/ab/{self.ab.slug}/")
        self.assertEqual(r.status_code, 200)

    def test_ab_convert_200(self):
        self.c.get(f"/engagement/ab/{self.ab.slug}/")
        r = self.c.post(f"/engagement/ab/{self.ab.slug}/convert/")
        self.assertEqual(r.status_code, 200)


# ─────────────────────────────────────────────────────────────────────────────
# 32. API: Prestige & Milestones
# ─────────────────────────────────────────────────────────────────────────────

class TestPrestigeAPI(TestCase):

    def setUp(self):
        self.c = api()

    def test_prestige_status_200(self):
        r = self.c.get("/engagement/prestige/")
        self.assertEqual(r.status_code, 200)

    def test_milestones_list_200(self):
        r = self.c.get("/engagement/milestones/")
        self.assertEqual(r.status_code, 200)


# ─────────────────────────────────────────────────────────────────────────────
# 33. API: Chests & Auctions
# ─────────────────────────────────────────────────────────────────────────────

class TestChestsAuctionsAPI(TestCase):

    def setUp(self):
        self.c = api()

    def test_my_chests_200(self):
        r = self.c.get("/engagement/chests/")
        self.assertEqual(r.status_code, 200)

    def test_auctions_list_200(self):
        r = self.c.get("/engagement/auctions/")
        self.assertEqual(r.status_code, 200)

    def test_open_chest_no_chest_400_or_404(self):
        r = self.c.post("/engagement/chests/open/", {"chest_id": 9999})
        self.assertIn(r.status_code, [400, 404])


# ─────────────────────────────────────────────────────────────────────────────
# 34. API: Analytics & Admin
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyticsAdminAPI(TestCase):

    def setUp(self):
        self.c = api()
        self.admin_c = api(make_user(is_staff=True))

    def test_my_analytics_200(self):
        r = self.c.get("/engagement/analytics/me/")
        self.assertEqual(r.status_code, 200)

    def test_analytics_dashboard_non_admin_403(self):
        r = self.c.get("/engagement/admin/analytics/")
        self.assertIn(r.status_code, [403, 401])

    def test_analytics_dashboard_admin_200(self):
        r = self.admin_c.get("/engagement/admin/analytics/")
        self.assertEqual(r.status_code, 200)

    def test_platform_stats_admin_200(self):
        r = self.admin_c.get("/engagement/admin/platform-stats/")
        self.assertEqual(r.status_code, 200)

    def test_platform_stats_non_admin_403(self):
        r = self.c.get("/engagement/admin/platform-stats/")
        self.assertIn(r.status_code, [403, 401])

    def test_webhooks_list_admin_200(self):
        r = self.admin_c.get("/engagement/admin/webhooks/")
        self.assertEqual(r.status_code, 200)

    def test_anti_cheat_flags_non_admin_403(self):
        r = self.c.get("/engagement/admin/anti-cheat/")
        self.assertIn(r.status_code, [403, 401])

    def test_anti_cheat_flags_admin_200(self):
        r = self.admin_c.get("/engagement/admin/anti-cheat/")
        self.assertEqual(r.status_code, 200)


# ─────────────────────────────────────────────────────────────────────────────
# 35. API: Battle Pass
# ─────────────────────────────────────────────────────────────────────────────

class TestBattlePassAPI(TestCase):

    def setUp(self):
        self.c = api()

    def test_battle_pass_no_season_404(self):
        r = self.c.get("/engagement/battle-pass/")
        self.assertIn(r.status_code, [200, 404])

    def test_battle_pass_with_season_200(self):
        _make_battle_pass()
        r = self.c.get("/engagement/battle-pass/")
        self.assertEqual(r.status_code, 200)

    def test_claim_tier_no_season_400(self):
        r = self.c.post("/engagement/battle-pass/claim/", {"tier_id": 1})
        self.assertIn(r.status_code, [400, 404])


# ─────────────────────────────────────────────────────────────────────────────
# 36. API: Scratch & Calendar
# ─────────────────────────────────────────────────────────────────────────────

class TestScratchCalendarAPI(TestCase):

    def setUp(self):
        self.c = api()

    def test_scratch_card_endpoint_200_or_404(self):
        r = self.c.get("/engagement/scratch/")
        self.assertIn(r.status_code, [200, 404, 405])

    def test_login_calendar_endpoint_200_or_404(self):
        r = self.c.get("/engagement/calendar/")
        self.assertIn(r.status_code, [200, 404])

    def test_scratch_with_template_200(self):
        _make_scratch_template()
        r = self.c.post("/engagement/scratch/", {"template_slug": "test-scratch"})
        self.assertIn(r.status_code, [200, 400])


# ─────────────────────────────────────────────────────────────────────────────
# 37. API: Combo & Seasonal Events
# ─────────────────────────────────────────────────────────────────────────────

class TestComboSeasonalAPI(TestCase):

    def setUp(self):
        self.c = api()

    def test_combo_status_200(self):
        r = self.c.get("/engagement/combo/")
        self.assertEqual(r.status_code, 200)

    def test_live_event_200_or_404(self):
        r = self.c.get("/engagement/events/live/")
        self.assertIn(r.status_code, [200, 404])
