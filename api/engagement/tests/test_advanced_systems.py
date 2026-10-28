# engagement/tests/test_advanced_systems.py
import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from .factories import UserFactory


# ── Loot Box ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLootBoxService:

    def _make_chest(self):
        from ..models.loot_box import ChestType, ChestDropTable
        ct = ChestType.objects.create(
            slug="test-chest", name="Test Chest",
            rarity="common", price_coins=Decimal("50"), is_active=True,
        )
        ChestDropTable.objects.create(
            chest_type=ct, reward_type="coins",
            coins_min=Decimal("10"), coins_max=Decimal("10"),
            weight=100, is_active=True,
        )
        return ct

    def test_grant_and_open_chest(self):
        from ..services.loot_box_service import LootBoxService
        user  = UserFactory(coin_balance=Decimal("0"))
        chest = self._make_chest()
        LootBoxService.grant_chest(user, chest, quantity=1, source="test")
        result = LootBoxService.open_chest(user, chest.slug)
        assert result["reward_type"] == "coins"
        assert result["coins_won"] == 10.0

    def test_open_chest_without_inventory_raises(self):
        from ..services.loot_box_service import LootBoxService
        from ..exceptions import ItemNotAvailableError
        user  = UserFactory(coin_balance=Decimal("0"))
        chest = self._make_chest()
        with pytest.raises(ItemNotAvailableError):
            LootBoxService.open_chest(user, chest.slug)

    def test_buy_chest_deducts_coins(self):
        from ..services.loot_box_service import LootBoxService
        user  = UserFactory(coin_balance=Decimal("200"))
        chest = self._make_chest()
        LootBoxService.buy_chest(user, chest.slug)
        user.refresh_from_db()
        assert user.coin_balance == Decimal("150")

    def test_opening_decrements_inventory(self):
        from ..services.loot_box_service import LootBoxService
        from ..models.loot_box import UserChest
        user  = UserFactory(coin_balance=Decimal("0"))
        chest = self._make_chest()
        LootBoxService.grant_chest(user, chest, quantity=3)
        LootBoxService.open_chest(user, chest.slug)
        inv = UserChest.objects.get(user=user, chest_type=chest)
        assert inv.quantity == 2


# ── Combo System ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestComboService:

    def _make_config(self):
        from ..models.combo import ComboConfig
        return ComboConfig.objects.create(
            action="spin", window_seconds=3600,
            max_multiplier=Decimal("3"), step_multiplier=Decimal("0.25"),
            is_active=True,
        )

    def test_first_action_streak_is_1(self):
        from ..services.combo_service import ComboService
        user = UserFactory(coin_balance=Decimal("0"))
        self._make_config()
        result = ComboService.register_action(user, "spin")
        assert result["streak"] == 1
        assert result["multiplier"] == 1.0

    def test_second_consecutive_increases_streak(self):
        from ..services.combo_service import ComboService
        user = UserFactory(coin_balance=Decimal("0"))
        self._make_config()
        ComboService.register_action(user, "spin")
        result = ComboService.register_action(user, "spin")
        assert result["streak"] == 2
        assert result["multiplier"] == 1.25

    def test_multiplier_caps_at_max(self):
        from ..services.combo_service import ComboService
        user = UserFactory(coin_balance=Decimal("0"))
        self._make_config()
        for _ in range(20):
            result = ComboService.register_action(user, "spin")
        assert result["multiplier"] <= 3.0

    def test_unknown_action_returns_default(self):
        from ..services.combo_service import ComboService
        user   = UserFactory(coin_balance=Decimal("0"))
        result = ComboService.register_action(user, "nonexistent")
        assert result["multiplier"] == 1.0
        assert result["streak"] == 0


# ── Prestige System ───────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPrestigeService:

    def _make_prestige_level(self):
        from ..models.prestige import PrestigeLevel
        return PrestigeLevel.objects.create(
            level=1, name="Bronze", required_level=5,
            coin_multiplier=Decimal("1.1"), xp_multiplier=Decimal("1.1"),
        )

    def test_prestige_at_wrong_level_returns_error(self):
        from ..services.prestige_service import PrestigeService
        from ..models.xp import UserXP
        user = UserFactory(coin_balance=Decimal("0"))
        UserXP.objects.create(user=user, total_xp=0, level=1)
        self._make_prestige_level()
        result = PrestigeService.attempt_prestige(user)
        assert "error" in result

    def test_prestige_at_correct_level_succeeds(self):
        from ..services.prestige_service import PrestigeService
        from ..models.xp import UserXP
        user   = UserFactory(coin_balance=Decimal("0"))
        xp_obj = UserXP.objects.create(user=user, total_xp=500, level=5)
        self._make_prestige_level()
        result = PrestigeService.attempt_prestige(user)
        assert result.get("success") is True
        assert result["prestige_level"] == 1

    def test_prestige_resets_level_to_1(self):
        from ..services.prestige_service import PrestigeService
        from ..models.xp import UserXP
        user   = UserFactory(coin_balance=Decimal("0"))
        xp_obj = UserXP.objects.create(user=user, total_xp=500, level=5)
        self._make_prestige_level()
        PrestigeService.attempt_prestige(user)
        xp_obj.refresh_from_db()
        assert xp_obj.level == 1
        assert xp_obj.total_xp == 0

    def test_get_multipliers_no_prestige(self):
        from ..services.prestige_service import PrestigeService
        user = UserFactory(coin_balance=Decimal("0"))
        m    = PrestigeService.get_multipliers(user)
        assert m["prestige_level"] == 0
        assert m["coin_multiplier"] == 1.0


# ── Social Service ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSocialService:

    def test_post_feed_item_creates_record(self):
        from ..services.social_service import SocialService
        from ..models.social import FeedItem
        user = UserFactory(coin_balance=Decimal("0"))
        item = SocialService.post_feed_item(user, "checkin", "Checked in!")
        assert FeedItem.objects.filter(user=user, type="checkin").exists()

    def test_like_increments_count(self):
        from ..services.social_service import SocialService
        user  = UserFactory(coin_balance=Decimal("0"))
        user2 = UserFactory(coin_balance=Decimal("0"))
        item  = SocialService.post_feed_item(user, "checkin", "Checked in!")
        result = SocialService.like(user2, item.pk)
        assert result["liked"] is True
        assert result["like_count"] == 1

    def test_like_twice_unlikes(self):
        from ..services.social_service import SocialService
        user  = UserFactory(coin_balance=Decimal("0"))
        user2 = UserFactory(coin_balance=Decimal("0"))
        item  = SocialService.post_feed_item(user, "checkin", "Checked in!")
        SocialService.like(user2, item.pk)
        result = SocialService.like(user2, item.pk)
        assert result["liked"] is False
        assert result["like_count"] == 0

    def test_send_and_accept_friend_request(self):
        from ..services.social_service import SocialService
        user1 = UserFactory(coin_balance=Decimal("0"))
        user2 = UserFactory(coin_balance=Decimal("0"))
        fs    = SocialService.send_friend_request(user1, user2)
        assert fs.status == "pending"
        fs2   = SocialService.accept_friend_request(user2, fs.pk)
        assert fs2.status == "accepted"

    def test_cannot_friend_self(self):
        from ..services.social_service import SocialService
        user = UserFactory(coin_balance=Decimal("0"))
        with pytest.raises(ValueError):
            SocialService.send_friend_request(user, user)

    def test_friends_list_returns_accepted_friends(self):
        from ..services.social_service import SocialService
        u1 = UserFactory(coin_balance=Decimal("0"))
        u2 = UserFactory(coin_balance=Decimal("0"))
        fs = SocialService.send_friend_request(u1, u2)
        SocialService.accept_friend_request(u2, fs.pk)
        friends = SocialService.friends_list(u1)
        assert u2 in friends

    def test_follow_unfollow_toggle(self):
        from ..services.social_service import SocialService
        u1 = UserFactory(coin_balance=Decimal("0"))
        u2 = UserFactory(coin_balance=Decimal("0"))
        r1 = SocialService.follow(u1, u2)
        assert r1["following"] is True
        r2 = SocialService.follow(u1, u2)
        assert r2["following"] is False


# ── Anti-Cheat ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestAntiCheatService:

    def _seed_rules(self):
        from ..services.anti_cheat_service import AntiCheatService
        AntiCheatService.seed_default_rules()

    def test_seed_creates_rules(self):
        from ..models.anti_cheat import AntiCheatRule
        self._seed_rules()
        assert AntiCheatRule.objects.count() >= 5

    def test_spin_velocity_flags_fast_spinner(self):
        from ..services.anti_cheat_service import AntiCheatService
        from ..models.anti_cheat import AntiCheatLog
        from ..models.spinwheel import SpinWheel
        self._seed_rules()
        user = UserFactory(coin_balance=Decimal("0"))
        # Create 6 spins in last 60 seconds
        for _ in range(6):
            SpinWheel.objects.create(user=user, coins_won=Decimal("1"))
        AntiCheatService.check_spin_velocity(user, ip_address="1.2.3.4")
        assert AntiCheatLog.objects.filter(user=user, rule__slug="spin-velocity").exists()

    def test_risk_score_updated_by_flags(self):
        from ..services.anti_cheat_service import AntiCheatService
        from ..models.anti_cheat import UserRiskScore, AntiCheatLog, AntiCheatRule
        self._seed_rules()
        user = UserFactory(coin_balance=Decimal("0"))
        rule = AntiCheatRule.objects.first()
        AntiCheatLog.objects.create(user=user, rule=rule, severity=2, details={})
        AntiCheatService.recalculate_risk(user)
        risk = UserRiskScore.objects.get(user=user)
        assert risk.score > 0
        assert risk.flag_count == 1


# ── Scratch Card ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestScratchCardService:

    def _make_template(self):
        from ..models.scratch_card import ScratchCardTemplate, ScratchCardPrize
        tmpl = ScratchCardTemplate.objects.create(
            slug="test-scratch", name="Test Scratch",
            max_per_day=3, price_coins=Decimal("0"), is_active=True,
        )
        ScratchCardPrize.objects.create(
            template=tmpl, label="💰 10 Coins",
            coins=Decimal("10"), weight=100,
        )
        return tmpl

    def test_scratch_gives_reward(self):
        from ..services.scratch_card_service import ScratchCardService
        user = UserFactory(coin_balance=Decimal("0"))
        self._make_template()
        result = ScratchCardService.scratch(user, "test-scratch")
        assert "coins_won" in result
        assert result["coins_won"] == 10.0

    def test_scratch_daily_limit_enforced(self):
        from ..services.scratch_card_service import ScratchCardService
        from ..exceptions import ItemNotAvailableError
        user = UserFactory(coin_balance=Decimal("0"))
        self._make_template()
        for _ in range(3):
            ScratchCardService.scratch(user, "test-scratch")
        with pytest.raises(ItemNotAvailableError):
            ScratchCardService.scratch(user, "test-scratch")

    def test_scratch_adds_coins_to_balance(self):
        from ..services.scratch_card_service import ScratchCardService
        user = UserFactory(coin_balance=Decimal("0"))
        self._make_template()
        ScratchCardService.scratch(user, "test-scratch")
        user.refresh_from_db()
        assert user.coin_balance == Decimal("10")


# ── Auction ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestAuctionService:

    def _make_auction(self):
        from ..models.auction import Auction
        now = timezone.now()
        return Auction.objects.create(
            title="Test Auction", starting_bid=Decimal("10"),
            bid_increment=Decimal("5"), current_bid=Decimal("0"),
            status="active",
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=24),
        )

    def test_place_bid_deducts_coins(self):
        from ..services.auction_service import AuctionService
        user    = UserFactory(coin_balance=Decimal("200"))
        auction = self._make_auction()
        result  = AuctionService.place_bid(user, auction.pk, Decimal("50"))
        assert result["success"] is True
        user.refresh_from_db()
        assert user.coin_balance == Decimal("150")

    def test_bid_too_low_raises_error(self):
        from ..services.auction_service import AuctionService, AuctionError
        user    = UserFactory(coin_balance=Decimal("200"))
        auction = self._make_auction()
        with pytest.raises(AuctionError):
            AuctionService.place_bid(user, auction.pk, Decimal("5"))

    def test_outbid_refunds_previous_bidder(self):
        from ..services.auction_service import AuctionService
        user1   = UserFactory(coin_balance=Decimal("500"))
        user2   = UserFactory(coin_balance=Decimal("500"))
        auction = self._make_auction()
        AuctionService.place_bid(user1, auction.pk, Decimal("50"))
        AuctionService.place_bid(user2, auction.pk, Decimal("60"))
        user1.refresh_from_db()
        assert user1.coin_balance == Decimal("500")  # refunded

    def test_close_auction_sets_winner(self):
        from ..services.auction_service import AuctionService
        from ..models.auction import Auction
        user    = UserFactory(coin_balance=Decimal("500"))
        auction = self._make_auction()
        AuctionService.place_bid(user, auction.pk, Decimal("50"))
        result  = AuctionService.close_auction(auction.pk)
        assert result["winner_id"] == user.pk
        auction.refresh_from_db()
        assert auction.status == "completed"
        assert auction.winner == user
