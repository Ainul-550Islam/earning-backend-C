# engagement/tests/test_xp.py
import pytest
from decimal import Decimal

from ..services.xp_service import XPService
from ..models.xp import UserXP, XPTransaction, xp_for_level, level_from_total_xp
from .factories import UserFactory


@pytest.mark.django_db
class TestXPService:

    def test_grant_creates_xp_record(self):
        user = UserFactory(coin_balance=Decimal("0"))
        XPService.grant(user, 50, source="checkin")
        xp_obj = UserXP.objects.get(user=user)
        assert xp_obj.total_xp == 50

    def test_grant_creates_transaction_log(self):
        user = UserFactory(coin_balance=Decimal("0"))
        XPService.grant(user, 100, source="quest", note="Quest complete")
        assert XPTransaction.objects.filter(user=user, source="quest").exists()

    def test_grant_returns_level_info(self):
        user   = UserFactory(coin_balance=Decimal("0"))
        result = XPService.grant(user, 50, source="spin")
        assert "old_level" in result
        assert "new_level" in result
        assert "leveled_up" in result
        assert "total_xp" in result

    def test_level_up_detected(self):
        user = UserFactory(coin_balance=Decimal("0"))
        # Level 1 → 2 requires 100 XP
        result = XPService.grant(user, 100, source="checkin")
        assert result["leveled_up"] is True
        assert result["new_level"] == 2

    def test_no_level_up_when_xp_insufficient(self):
        user   = UserFactory(coin_balance=Decimal("0"))
        result = XPService.grant(user, 50, source="checkin")
        assert result["leveled_up"] is False
        assert result["new_level"] == 1

    def test_cumulative_xp_grants(self):
        user = UserFactory(coin_balance=Decimal("0"))
        XPService.grant(user, 60, source="checkin")
        XPService.grant(user, 60, source="spin")
        xp_obj = UserXP.objects.get(user=user)
        assert xp_obj.total_xp == 120
        assert xp_obj.level == 2

    def test_get_or_create_returns_xp_obj(self):
        user   = UserFactory(coin_balance=Decimal("0"))
        xp_obj = XPService.get_or_create(user)
        assert isinstance(xp_obj, UserXP)
        assert xp_obj.level == 1

    def test_zero_xp_grant_raises_error(self):
        user = UserFactory(coin_balance=Decimal("0"))
        with pytest.raises(ValueError):
            XPService.grant(user, 0, source="checkin")

    def test_xp_for_level_math(self):
        """Level 1→2 costs 100 XP; each level costs 1.5× more."""
        assert xp_for_level(1) == 100
        assert xp_for_level(2) == 150   # 100 * 1.5
        assert xp_for_level(3) == 225   # 150 * 1.5

    def test_level_from_total_xp(self):
        assert level_from_total_xp(0)   == 1
        assert level_from_total_xp(99)  == 1
        assert level_from_total_xp(100) == 2
        assert level_from_total_xp(249) == 2
        assert level_from_total_xp(250) == 3

    def test_level_pct_property(self):
        user = UserFactory(coin_balance=Decimal("0"))
        XPService.grant(user, 50, source="checkin")   # halfway to level 2
        xp_obj = UserXP.objects.get(user=user)
        assert xp_obj.level_pct == 50
