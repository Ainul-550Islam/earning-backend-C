# engagement/tests/test_new_coverage.py
"""
New Coverage Tests
==================
Covers the remaining gaps identified in analysis:

  Views (3 uncovered):
    - buy_event_item        POST /engagement/events/shop/buy/
    - webhook_delete        DELETE /engagement/admin/webhooks/<pk>/
    - admin_campaign_update PUT  /engagement/admin/campaigns/<pk>/

  Serializers (6 new classes added in fix):
    - ComboConfigSerializer
    - UserComboSerializer   (includes multiplier SerializerMethodField)
    - EnergyConfigSerializer
    - EnergyCostSerializer
    - UserEnergySerializer  (includes current_energy SerializerMethodField)
    - ScratchCardPrizeSerializer

  Test import paths intentionally use relative imports consistent with
  test_advanced_systems.py / test_final_20_percent.py style.
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

User = get_user_model()


def mu(is_admin=False):
    """Make a unique test user."""
    import random
    username = f"u{random.randint(10_000, 99_999)}"
    u = User.objects.create_user(username=username, password="pw")
    u.is_staff = is_admin
    u.coin_balance = Decimal("500")
    u.save()
    return u


# ══════════════════════════════════════════════════════════════════════════════
# BLOCK 1 — buy_event_item view
# ══════════════════════════════════════════════════════════════════════════════

class TestBuyEventItemView(TestCase):
    """POST /engagement/events/shop/buy/ — previously uncovered."""

    def setUp(self):
        self.user   = mu()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = "/engagement/events/shop/buy/"

    def test_missing_item_id_returns_400(self):
        """No item_id in body → 400 with error message."""
        resp = self.client.post(self.url, {}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.data)
        self.assertIn("item_id", resp.data["error"])

    def test_valid_item_id_calls_service(self):
        """Valid item_id → service called, 200 returned."""
        mock_result = {"success": True, "item": "event_sword", "cost": 50}
        with patch(
            "engagement.views.advanced_views.SeasonalEventService.buy_event_item",
            return_value=mock_result,
        ) as mock_buy:
            resp = self.client.post(self.url, {"item_id": 7}, format="json")
        self.assertEqual(resp.status_code, 200)
        mock_buy.assert_called_once()
        call_args = mock_buy.call_args[0]
        self.assertEqual(call_args[1], 7)  # item_id cast to int

    def test_unauthenticated_returns_401(self):
        anon = APIClient()
        resp = anon.post(self.url, {"item_id": 1}, format="json")
        self.assertIn(resp.status_code, [401, 403])

    def test_item_id_cast_to_int(self):
        """String item_id is coerced to int before passing to service."""
        with patch(
            "engagement.views.advanced_views.SeasonalEventService.buy_event_item",
            return_value={"success": True},
        ) as mock_buy:
            self.client.post(self.url, {"item_id": "12"}, format="json")
        self.assertEqual(mock_buy.call_args[0][1], 12)


# ══════════════════════════════════════════════════════════════════════════════
# BLOCK 2 — webhook_delete view
# ══════════════════════════════════════════════════════════════════════════════

class TestWebhookDeleteView(TestCase):
    """DELETE /engagement/admin/webhooks/<pk>/ — previously uncovered."""

    def setUp(self):
        self.admin  = mu(is_admin=True)
        self.user   = mu()
        self.client = APIClient()

    def _url(self, pk):
        return f"/engagement/admin/webhooks/{pk}/"

    def test_delete_existing_webhook_returns_204(self):
        """Deleting an existing WebhookEndpoint returns HTTP 204 No Content."""
        from ..models.webhook import WebhookEndpoint
        ep = WebhookEndpoint.objects.create(
            url="https://example.com/hook",
            events=["checkin.completed"],
            tenant=None,
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self._url(ep.pk))
        self.assertEqual(resp.status_code, 204)

    def test_deleted_webhook_no_longer_exists(self):
        """After 204, the record is gone from the DB."""
        from ..models.webhook import WebhookEndpoint
        ep = WebhookEndpoint.objects.create(
            url="https://example.com/hook2",
            events=["xp.granted"],
            tenant=None,
        )
        pk = ep.pk
        self.client.force_authenticate(user=self.admin)
        self.client.delete(self._url(pk))
        self.assertFalse(WebhookEndpoint.objects.filter(pk=pk).exists())

    def test_delete_nonexistent_webhook_returns_404(self):
        """Missing pk → 404."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(self._url(99999))
        self.assertEqual(resp.status_code, 404)

    def test_non_admin_cannot_delete_webhook(self):
        """Regular user should be denied (403)."""
        from ..models.webhook import WebhookEndpoint
        ep = WebhookEndpoint.objects.create(
            url="https://example.com/hook3",
            events=["spin.completed"],
            tenant=None,
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.delete(self._url(ep.pk))
        self.assertIn(resp.status_code, [403, 401])


# ══════════════════════════════════════════════════════════════════════════════
# BLOCK 3 — admin_campaign_update view
# ══════════════════════════════════════════════════════════════════════════════

class TestAdminCampaignUpdateView(TestCase):
    """PUT /engagement/admin/campaigns/<pk>/ — previously uncovered."""

    def setUp(self):
        self.admin  = mu(is_admin=True)
        self.user   = mu()
        self.client = APIClient()

    def _url(self, pk=1):
        return f"/engagement/admin/campaigns/{pk}/"

    def test_valid_update_returns_200(self):
        payload = {"name": "Summer 2026", "is_active": True}
        mock_campaign = MagicMock()
        mock_campaign.pk = 1
        with patch(
            "engagement.views.advanced_views.CampaignService.update_campaign",
            return_value=mock_campaign,
        ):
            self.client.force_authenticate(user=self.admin)
            resp = self.client.put(self._url(1), payload, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("success"))

    def test_update_returns_campaign_id(self):
        mock_campaign = MagicMock()
        mock_campaign.pk = 42
        with patch(
            "engagement.views.advanced_views.CampaignService.update_campaign",
            return_value=mock_campaign,
        ):
            self.client.force_authenticate(user=self.admin)
            resp = self.client.put(self._url(42), {"name": "Updated"}, format="json")
        self.assertEqual(resp.data.get("id"), 42)

    def test_non_admin_cannot_update_campaign(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.put(self._url(1), {"name": "hack"}, format="json")
        self.assertIn(resp.status_code, [401, 403])

    def test_unauthenticated_cannot_update_campaign(self):
        resp = APIClient().put(self._url(1), {"name": "x"}, format="json")
        self.assertIn(resp.status_code, [401, 403])


# ══════════════════════════════════════════════════════════════════════════════
# BLOCK 4 — ComboConfigSerializer & UserComboSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestComboSerializers(TestCase):
    """ComboConfigSerializer and UserComboSerializer — new classes, no prior tests."""

    def _make_combo_config(self, action="spin"):
        from ..models.combo import ComboConfig
        return ComboConfig.objects.get_or_create(
            action=action,
            defaults=dict(
                max_combo=10,
                decay_seconds=60,
                multiplier_per_step=Decimal("0.1"),
                is_active=True,
            ),
        )[0]

    def _make_user_combo(self, user, action="spin", current_combo=3):
        from ..models.combo import UserCombo
        return UserCombo.objects.create(
            user=user,
            action=action,
            current_combo=current_combo,
            last_action_at=timezone.now(),
            expires_at=timezone.now() + timezone.timedelta(seconds=60),
        )

    def test_combo_config_serializer_fields(self):
        from ..serializers.combo_serializer import ComboConfigSerializer
        config = self._make_combo_config()
        data = ComboConfigSerializer(config).data
        for field in ["id", "action", "max_combo", "decay_seconds", "multiplier_per_step", "is_active"]:
            self.assertIn(field, data, f"Missing field: {field}")

    def test_combo_config_action_value(self):
        from ..serializers.combo_serializer import ComboConfigSerializer
        config = self._make_combo_config(action="checkin")
        data = ComboConfigSerializer(config).data
        self.assertEqual(data["action"], "checkin")

    def test_user_combo_serializer_fields(self):
        from ..serializers.combo_serializer import UserComboSerializer
        u = mu()
        self._make_combo_config()
        combo = self._make_user_combo(u, current_combo=4)
        data = UserComboSerializer(combo).data
        for field in ["id", "current_combo", "multiplier", "expires_at"]:
            self.assertIn(field, data, f"Missing field: {field}")

    def test_user_combo_multiplier_calculated(self):
        """multiplier = 1 + (current_combo × multiplier_per_step)."""
        from ..serializers.combo_serializer import UserComboSerializer
        u = mu()
        self._make_combo_config(action="spin")  # multiplier_per_step=0.1
        combo = self._make_user_combo(u, action="spin", current_combo=5)
        data = UserComboSerializer(combo).data
        expected = 1 + (5 * 0.1)
        self.assertAlmostEqual(float(data["multiplier"]), expected, places=4)

    def test_user_combo_no_config_multiplier_is_one(self):
        """If no ComboConfig exists for the action, multiplier defaults to 1.0."""
        from ..serializers.combo_serializer import UserComboSerializer
        u = mu()
        combo = self._make_user_combo(u, action="unknown_action_xyz", current_combo=10)
        data = UserComboSerializer(combo).data
        self.assertEqual(float(data["multiplier"]), 1.0)

    def test_user_combo_user_is_read_only(self):
        """user field must be read_only — cannot be written via serializer."""
        from ..serializers.combo_serializer import UserComboSerializer
        self.assertIn("user", UserComboSerializer.Meta.read_only_fields)

    def test_combo_config_id_is_read_only(self):
        from ..serializers.combo_serializer import ComboConfigSerializer
        self.assertIn("id", ComboConfigSerializer.Meta.read_only_fields)


# ══════════════════════════════════════════════════════════════════════════════
# BLOCK 5 — EnergyConfigSerializer / EnergyCostSerializer / UserEnergySerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestEnergySerializers(TestCase):
    """EnergyConfigSerializer, EnergyCostSerializer, UserEnergySerializer."""

    def _make_energy_config(self, action="spin"):
        from ..models.combo import EnergyConfig
        return EnergyConfig.objects.get_or_create(
            action=action,
            defaults=dict(cost=Decimal("5")),
        )[0]

    def _make_energy_cost(self, action="purchase"):
        from ..models.combo import EnergyCost
        return EnergyCost.objects.get_or_create(
            action=action,
            defaults=dict(cost=Decimal("10")),
        )[0]

    def _make_user_energy(self, user):
        from ..models.combo import UserEnergy
        return UserEnergy.objects.create(
            user=user,
            max_energy=100,
            recharge_rate_per_hour=Decimal("10"),
            last_recharged_at=timezone.now(),
        )

    def test_energy_config_serializer_fields(self):
        from ..serializers.combo_serializer import EnergyConfigSerializer
        config = self._make_energy_config()
        data = EnergyConfigSerializer(config).data
        for field in ["id", "action", "cost"]:
            self.assertIn(field, data)

    def test_energy_config_cost_value(self):
        from ..serializers.combo_serializer import EnergyConfigSerializer
        config = self._make_energy_config(action="spin")
        data = EnergyConfigSerializer(config).data
        self.assertEqual(Decimal(str(data["cost"])), Decimal("5"))

    def test_energy_cost_serializer_fields(self):
        from ..serializers.combo_serializer import EnergyCostSerializer
        ec = self._make_energy_cost()
        data = EnergyCostSerializer(ec).data
        for field in ["id", "action", "cost"]:
            self.assertIn(field, data)

    def test_user_energy_serializer_fields(self):
        from ..serializers.combo_serializer import UserEnergySerializer
        u = mu()
        ue = self._make_user_energy(u)
        data = UserEnergySerializer(ue).data
        for field in ["id", "max_energy", "recharge_rate_per_hour", "current_energy"]:
            self.assertIn(field, data)

    def test_user_energy_current_energy_calls_compute(self):
        """current_energy should call obj.compute_current()."""
        from ..serializers.combo_serializer import UserEnergySerializer
        u = mu()
        ue = self._make_user_energy(u)
        ue.compute_current = MagicMock(return_value=77)
        data = UserEnergySerializer(ue).data
        self.assertEqual(data["current_energy"], 77)

    def test_user_energy_user_read_only(self):
        from ..serializers.combo_serializer import UserEnergySerializer
        self.assertIn("user", UserEnergySerializer.Meta.read_only_fields)

    def test_user_energy_current_energy_read_only(self):
        from ..serializers.combo_serializer import UserEnergySerializer
        self.assertIn("current_energy", UserEnergySerializer.Meta.read_only_fields)


# ══════════════════════════════════════════════════════════════════════════════
# BLOCK 6 — ScratchCardPrizeSerializer
# ══════════════════════════════════════════════════════════════════════════════

class TestScratchCardPrizeSerializer(TestCase):
    """ScratchCardPrizeSerializer — class was missing entirely before the fix."""

    def _make_template(self, slug="sc-test"):
        from ..models.scratch_card import ScratchCardTemplate
        return ScratchCardTemplate.objects.get_or_create(
            slug=slug,
            defaults=dict(name="Test Card", max_per_day=3, price_coins=Decimal("20"), is_active=True),
        )[0]

    def _make_prize(self, template, label="Gold Coin", probability=0.5, coins=100, xp=50):
        from ..models.scratch_card import ScratchCardPrize
        return ScratchCardPrize.objects.create(
            template=template,
            label=label,
            probability=probability,
            coins=Decimal(str(coins)),
            xp=xp,
        )

    def test_prize_serializer_has_all_fields(self):
        from ..serializers.seasonal_serializer import ScratchCardPrizeSerializer
        t = self._make_template()
        prize = self._make_prize(t)
        data = ScratchCardPrizeSerializer(prize).data
        for field in ["id", "label", "probability", "coins", "xp"]:
            self.assertIn(field, data, f"Missing field: {field}")

    def test_prize_label_value(self):
        from ..serializers.seasonal_serializer import ScratchCardPrizeSerializer
        t = self._make_template(slug="sc-label")
        prize = self._make_prize(t, label="Diamond Chest")
        data = ScratchCardPrizeSerializer(prize).data
        self.assertEqual(data["label"], "Diamond Chest")

    def test_prize_coins_value(self):
        from ..serializers.seasonal_serializer import ScratchCardPrizeSerializer
        t = self._make_template(slug="sc-coins")
        prize = self._make_prize(t, coins=250)
        data = ScratchCardPrizeSerializer(prize).data
        self.assertEqual(Decimal(str(data["coins"])), Decimal("250"))

    def test_prize_probability_value(self):
        from ..serializers.seasonal_serializer import ScratchCardPrizeSerializer
        t = self._make_template(slug="sc-prob")
        prize = self._make_prize(t, probability=0.25)
        data = ScratchCardPrizeSerializer(prize).data
        self.assertAlmostEqual(float(data["probability"]), 0.25, places=4)

    def test_prize_xp_value(self):
        from ..serializers.seasonal_serializer import ScratchCardPrizeSerializer
        t = self._make_template(slug="sc-xp")
        prize = self._make_prize(t, xp=200)
        data = ScratchCardPrizeSerializer(prize).data
        self.assertEqual(data["xp"], 200)

    def test_prize_serializer_is_importable_from_main_init(self):
        """ScratchCardPrizeSerializer must be importable from the top-level serializers package."""
        try:
            from ..serializers import ScratchCardPrizeSerializer
        except ImportError as e:
            self.fail(f"Import failed: {e}")

    def test_prize_many_true(self):
        """Serializer works with many=True (list serialization)."""
        from ..serializers.seasonal_serializer import ScratchCardPrizeSerializer
        t = self._make_template(slug="sc-many")
        self._make_prize(t, label="Prize A", probability=0.4, coins=50)
        self._make_prize(t, label="Prize B", probability=0.6, coins=100)
        from ..models.scratch_card import ScratchCardPrize
        prizes = ScratchCardPrize.objects.filter(template=t)
        data = ScratchCardPrizeSerializer(prizes, many=True).data
        self.assertEqual(len(data), 2)
        labels = [d["label"] for d in data]
        self.assertIn("Prize A", labels)
        self.assertIn("Prize B", labels)


# ══════════════════════════════════════════════════════════════════════════════
# BLOCK 7 — Combo/Energy serializer export sanity
# ══════════════════════════════════════════════════════════════════════════════

class TestSerializerPackageExports(TestCase):
    """All 6 new serializer classes must be importable from the package root."""

    def test_combo_config_serializer_exported(self):
        from ..serializers import ComboConfigSerializer  # noqa

    def test_user_combo_serializer_exported(self):
        from ..serializers import UserComboSerializer  # noqa

    def test_energy_config_serializer_exported(self):
        from ..serializers import EnergyConfigSerializer  # noqa

    def test_energy_cost_serializer_exported(self):
        from ..serializers import EnergyCostSerializer  # noqa

    def test_user_energy_serializer_exported(self):
        from ..serializers import UserEnergySerializer  # noqa

    def test_scratch_card_prize_serializer_exported(self):
        from ..serializers import ScratchCardPrizeSerializer  # noqa
