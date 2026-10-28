# engagement/tests/test_battle_pass.py
import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from ..services.battle_pass_service import BattlePassService
from ..models.battle_pass import BattlePass, BattlePassTier, UserBattlePass, BattlePassXPSource
from .factories import UserFactory


def make_battle_pass(tenant=None):
    now = timezone.now()
    bp  = BattlePass.objects.create(
        name="Test Season", season_num=1,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=30),
        is_active=True, premium_price_coins=Decimal("500"),
        total_tiers=50, tenant=tenant,
    )
    for i in range(1, 6):
        BattlePassTier.objects.create(
            battle_pass=bp, tier_number=i,
            xp_required=i * 100,
            free_coins=Decimal("10"), free_xp=20,
            premium_coins=Decimal("20"), premium_xp=40,
        )
    BattlePassXPSource.objects.create(
        battle_pass=bp, action="checkin", xp_amount=150, daily_cap=0,
    )
    BattlePassXPSource.objects.create(
        battle_pass=bp, action="spin", xp_amount=50, daily_cap=0,
    )
    return bp


@pytest.mark.django_db
class TestBattlePassService:

    def test_get_or_enroll_creates_user_pass(self):
        user = UserFactory(coin_balance=Decimal("0"))
        bp   = make_battle_pass()
        ubp  = BattlePassService.get_or_enroll(user, bp)
        assert ubp.user == user
        assert ubp.is_premium is False
        assert ubp.current_tier == 0

    def test_get_or_enroll_idempotent(self):
        user = UserFactory(coin_balance=Decimal("0"))
        bp   = make_battle_pass()
        BattlePassService.get_or_enroll(user, bp)
        BattlePassService.get_or_enroll(user, bp)
        assert UserBattlePass.objects.filter(user=user, battle_pass=bp).count() == 1

    def test_grant_xp_for_checkin_advances_tier(self):
        user = UserFactory(coin_balance=Decimal("0"))
        bp   = make_battle_pass()
        # Tier 1 requires 100 XP, source gives 150 → should hit tier 1
        result = BattlePassService.grant_xp(user, "checkin")
        assert result["xp_granted"] == 150
        assert result["new_tier"] >= 1
        assert len(result["tier_ups"]) >= 1

    def test_grant_xp_unknown_action_gives_zero(self):
        user   = UserFactory(coin_balance=Decimal("0"))
        bp     = make_battle_pass()
        result = BattlePassService.grant_xp(user, "unknown_action")
        assert result["xp_granted"] == 0

    def test_claim_tier_free_rewards(self):
        user = UserFactory(coin_balance=Decimal("0"))
        bp   = make_battle_pass()
        ubp  = BattlePassService.get_or_enroll(user, bp)
        ubp.current_tier = 1
        ubp.save(update_fields=["current_tier"])
        result = BattlePassService.claim_tier_rewards(user, 1)
        user.refresh_from_db()
        assert "free" in result
        assert user.coin_balance == Decimal("10")

    def test_claim_tier_not_reached_returns_error(self):
        user = UserFactory(coin_balance=Decimal("0"))
        bp   = make_battle_pass()
        result = BattlePassService.claim_tier_rewards(user, 5)
        assert "error" in result

    def test_claim_already_claimed_returns_error(self):
        user = UserFactory(coin_balance=Decimal("0"))
        bp   = make_battle_pass()
        ubp  = BattlePassService.get_or_enroll(user, bp)
        ubp.current_tier = 2
        ubp.last_claimed_tier = 1
        ubp.save(update_fields=["current_tier", "last_claimed_tier"])
        result = BattlePassService.claim_tier_rewards(user, 1)
        assert "error" in result

    def test_unlock_premium_deducts_coins(self):
        user = UserFactory(coin_balance=Decimal("600"))
        bp   = make_battle_pass()
        BattlePassService.get_or_enroll(user, bp)
        result = BattlePassService.unlock_premium(user)
        assert result["success"] is True
        user.refresh_from_db()
        assert user.coin_balance == Decimal("100")

    def test_unlock_premium_already_premium_returns_error(self):
        user = UserFactory(coin_balance=Decimal("1000"))
        bp   = make_battle_pass()
        BattlePassService.unlock_premium(user)
        result = BattlePassService.unlock_premium(user)
        assert "error" in result

    def test_premium_tier_claim_gives_bonus(self):
        user = UserFactory(coin_balance=Decimal("1000"))
        bp   = make_battle_pass()
        BattlePassService.unlock_premium(user)
        ubp  = UserBattlePass.objects.get(user=user, battle_pass=bp)
        ubp.current_tier = 1
        ubp.save(update_fields=["current_tier"])
        result = BattlePassService.claim_tier_rewards(user, 1)
        assert "premium" in result
        assert result["premium"].get("coins", 0) > 0

    def test_no_active_battle_pass_returns_zero(self):
        user = UserFactory(coin_balance=Decimal("0"))
        BattlePass.objects.all().update(is_active=False)
        result = BattlePassService.grant_xp(user, "checkin")
        assert result["xp_granted"] == 0
