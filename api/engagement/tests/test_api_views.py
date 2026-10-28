# engagement/tests/test_api_views.py
"""
API-level integration tests using DRF's APIClient.
These tests hit the view layer end-to-end, covering auth, response shape,
status codes, and idempotency guards.
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from rest_framework.test import APIClient
from rest_framework import status

from .factories import (
    UserFactory, DailyCheckInFactory, SpinWheelFactory,
    LeaderboardFactory, LeaderboardRewardFactory,
    AchievementFactory, UserAchievementFactory,
    QuestFactory, UserQuestFactory,
    ShopItemFactory, NotificationFactory,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client(api_client):
    user = UserFactory(coin_balance=Decimal("500"))
    api_client.force_authenticate(user=user)
    api_client._user = user
    return api_client


# ── Daily Check-In ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCheckInAPI:

    def test_checkin_requires_auth(self, api_client):
        resp = api_client.post("/engagement/daily-checkin/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_checkin_success(self, auth_client):
        resp = auth_client.post("/engagement/daily-checkin/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "coins_earned" in data
        assert "consecutive_days" in data
        assert "new_balance" in data

    def test_checkin_double_returns_400(self, auth_client):
        auth_client.post("/engagement/daily-checkin/")
        resp = auth_client.post("/engagement/daily-checkin/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_checkins_list_returns_200(self, auth_client):
        resp = auth_client.get("/engagement/checkins/")
        assert resp.status_code == status.HTTP_200_OK
        assert "results" in resp.json()

    def test_checkins_stats_returns_200(self, auth_client):
        resp = auth_client.get("/engagement/checkins/stats/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "my_streak" in data
        assert "total_checkins_today" in data


# ── Spin Wheel ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSpinAPI:

    def test_spin_requires_auth(self, api_client):
        resp = api_client.post("/engagement/spin-wheel/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_spin_success(self, auth_client):
        resp = auth_client.post("/engagement/spin-wheel/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "coins_won" in data
        assert "spins_remaining" in data

    def test_spin_max_spins_returns_400(self, auth_client):
        from ..constants import SPIN_MAX_PER_DAY
        for _ in range(SPIN_MAX_PER_DAY):
            auth_client.post("/engagement/spin-wheel/")
        resp = auth_client.post("/engagement/spin-wheel/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_spins_list_returns_200(self, auth_client):
        resp = auth_client.get("/engagement/spins/")
        assert resp.status_code == status.HTTP_200_OK

    def test_spins_stats_returns_200(self, auth_client):
        resp = auth_client.get("/engagement/spins/stats/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "my_spins_remaining" in data
        assert "max_spins_per_day" in data


# ── Leaderboard ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLeaderboardAPI:

    def test_leaderboard_requires_auth(self, api_client):
        resp = api_client.get("/engagement/leaderboard/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_leaderboard_returns_200(self, auth_client):
        resp = auth_client.get("/engagement/leaderboard/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "leaderboard" in data
        assert "user_rank" in data

    def test_leaderboard_with_date_param(self, auth_client):
        today = str(date.today())
        resp  = auth_client.get(f"/engagement/leaderboard/?date={today}")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["date"] == today


# ── Achievements ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestAchievementsAPI:

    def test_achievements_list_returns_200(self, auth_client):
        AchievementFactory(is_active=True, is_secret=False)
        resp = auth_client.get("/engagement/achievements/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "results" in data

    def test_my_achievements_returns_200(self, auth_client):
        resp = auth_client.get("/engagement/achievements/mine/")
        assert resp.status_code == status.HTTP_200_OK


# ── Stats ─────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestStatsAPI:

    def test_daily_stats_returns_200(self, auth_client):
        resp = auth_client.get("/engagement/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "check_in" in data
        assert "spin_wheel" in data
        assert "coin_balance" in data
        assert "xp" in data

    def test_engagement_stats_returns_score(self, auth_client):
        resp = auth_client.get("/engagement/stats/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "engagement_score" in data
        assert 0 <= data["engagement_score"] <= 100

    def test_xp_endpoint_returns_level(self, auth_client):
        resp = auth_client.get("/engagement/xp/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "level" in data
        assert "total_xp" in data
        assert "level_pct" in data


# ── Shop ──────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestShopAPI:

    def test_shop_items_returns_200(self, auth_client):
        ShopItemFactory(is_active=True)
        resp = auth_client.get("/engagement/shop/")
        assert resp.status_code == status.HTTP_200_OK

    def test_purchase_success(self, auth_client):
        item = ShopItemFactory(price_coins=Decimal("50"), is_active=True, stock=-1)
        resp = auth_client.post("/engagement/shop/purchase/", {"item_slug": item.slug})
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "new_balance" in data

    def test_purchase_no_slug_returns_400(self, auth_client):
        resp = auth_client.post("/engagement/shop/purchase/", {})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_inventory_returns_200(self, auth_client):
        resp = auth_client.get("/engagement/shop/inventory/")
        assert resp.status_code == status.HTTP_200_OK


# ── Notifications ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestNotificationsAPI:

    def test_notifications_list_returns_200(self, auth_client):
        NotificationFactory(user=auth_client._user)
        resp = auth_client.get("/engagement/notifications/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "results" in data
        assert data["count"] == 1

    def test_unread_count_returns_200(self, auth_client):
        NotificationFactory(user=auth_client._user, is_read=False)
        resp = auth_client.get("/engagement/notifications/unread-count/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["unread_count"] == 1

    def test_mark_read_returns_200(self, auth_client):
        notif = NotificationFactory(user=auth_client._user, is_read=False)
        resp  = auth_client.post(f"/engagement/notifications/{notif.pk}/read/")
        assert resp.status_code == status.HTTP_200_OK
        notif.refresh_from_db()
        assert notif.is_read is True

    def test_mark_all_read_returns_200(self, auth_client):
        for _ in range(3):
            NotificationFactory(user=auth_client._user, is_read=False)
        resp = auth_client.post("/engagement/notifications/read-all/")
        assert resp.status_code == status.HTTP_200_OK
        from ..models.notification import Notification
        assert Notification.objects.filter(user=auth_client._user, is_read=False).count() == 0
