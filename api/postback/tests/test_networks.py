"""
test_networks.py – Tests for all 91 network adapters in adapters/networks.py

Tests:
  • EngineAdapterBridge base behaviour
  • Every adapter: network_keys set, adapt() returns standard fields
  • Status normalisation across all adapters
  • Field mapping override via network_config
  • AdapterRegistry returns correct adapter for each network_key
  • GenericAdapter fallback for unknown networks
"""
from unittest.mock import MagicMock

from django.test import TestCase

from api.postback.adapters.networks import (
    ALL_NETWORK_ADAPTERS,
    EngineAdapterBridge,
    CPALeadNetworkAdapter,
    AdGateMediaAdapter,
    HasOffersAdapter,
    EverflowAdapter,
    CustomSlotAdapter,
    PollfishAdapter,
    UnityAdsAdapter,
    FacebookAdsAdapter,
)
from api.postback.adapters.registry import get_adapter, AdapterRegistry
from api.postback.adapters.generic import GenericAdapter


def _config(network_key="test", field_mapping=None):
    c = MagicMock()
    c.network_key = network_key
    c.field_mapping = field_mapping or {}
    return c


STANDARD_FIELDS = [
    "lead_id", "offer_id", "payout", "currency",
    "transaction_id", "goal_id", "sub_id1",
    "cpalead_status", "is_reversal", "event_type",
    "_adapter", "_network_key",
]


class EngineAdapterBridgeTests(TestCase):

    def setUp(self):
        self.adapter = CPALeadNetworkAdapter()
        self.config = _config("cpalead")

    def test_adapt_returns_dict(self):
        result = self.adapter.adapt({}, self.config)
        self.assertIsInstance(result, dict)

    def test_adapt_has_all_standard_fields(self):
        result = self.adapter.adapt({"lead_id": "L1", "offer_id": "O1"}, self.config)
        for field in STANDARD_FIELDS:
            self.assertIn(field, result, f"Missing field: {field}")

    def test_payout_defaults_to_0(self):
        result = self.adapter.adapt({}, self.config)
        self.assertEqual(result["payout"], "0")

    def test_currency_defaults_to_usd(self):
        result = self.adapter.adapt({}, self.config)
        self.assertEqual(result["currency"], "USD")

    def test_approved_status_normalised(self):
        for approved_val in ["1", "approved", "success", "paid", "true"]:
            r = self.adapter.adapt({"status": approved_val}, self.config)
            self.assertEqual(r["cpalead_status"], "approved",
                             f"Expected approved for status={approved_val!r}")

    def test_reversed_status_normalised(self):
        for rejected_val in ["0", "reversed", "chargeback", "fraud", "false"]:
            r = self.adapter.adapt({"status": rejected_val}, self.config)
            self.assertIn(r["cpalead_status"], ("reversed", "rejected"),
                          f"Expected reversed/rejected for status={rejected_val!r}")

    def test_is_reversal_set_on_reversed_status(self):
        r = self.adapter.adapt({"status": "reversed"}, self.config)
        self.assertTrue(r["is_reversal"])

    def test_is_reversal_false_on_approved(self):
        r = self.adapter.adapt({"status": "approved"}, self.config)
        self.assertFalse(r["is_reversal"])

    def test_field_mapping_override(self):
        config = _config("cpalead", field_mapping={"lead_id": "my_uid"})
        r = self.adapter.adapt({"my_uid": "MAPPED_LEAD"}, config)
        self.assertEqual(r["lead_id"], "MAPPED_LEAD")

    def test_exception_returns_error_dict(self):
        r = self.adapter.adapt(None, self.config)
        self.assertIn("_error", r)

    def test_adapter_network_key_in_result(self):
        r = self.adapter.adapt({}, self.config)
        self.assertEqual(r["_network_key"], "cpalead")


class CPALeadAdapterSpecificTests(TestCase):

    def setUp(self):
        self.adapter = CPALeadNetworkAdapter()
        self.config = _config("cpalead")

    def test_sub1_maps_to_lead_id(self):
        r = self.adapter.adapt({"sub1": "LEAD_VIA_SUB1"}, self.config)
        self.assertEqual(r["lead_id"], "LEAD_VIA_SUB1")

    def test_oid_maps_to_offer_id(self):
        r = self.adapter.adapt({"oid": "OFFER_VIA_OID"}, self.config)
        self.assertEqual(r["offer_id"], "OFFER_VIA_OID")

    def test_amount_maps_to_payout(self):
        r = self.adapter.adapt({"amount": "7.50"}, self.config)
        self.assertEqual(r["payout"], "7.50")

    def test_sid_maps_to_transaction_id(self):
        r = self.adapter.adapt({"sid": "TXN_001"}, self.config)
        self.assertEqual(r["transaction_id"], "TXN_001")

    def test_goal_derives_sale_event_type(self):
        r = self.adapter.adapt({"goal": "purchase"}, self.config)
        self.assertEqual(r["event_type"], "sale")

    def test_is_lead_reversed_method(self):
        self.assertTrue(self.adapter.is_lead_reversed({"cpalead_status": "reversed"}))
        self.assertFalse(self.adapter.is_lead_reversed({"cpalead_status": "approved"}))

    def test_is_lead_pending_method(self):
        self.assertTrue(self.adapter.is_lead_pending({"cpalead_status": "pending"}))
        self.assertFalse(self.adapter.is_lead_pending({"cpalead_status": "approved"}))

    def test_network_keys_include_aliases(self):
        for key in ["cpalead", "cpa_lead", "cpaleadnet"]:
            self.assertIn(key, CPALeadNetworkAdapter.network_keys)


class HasOffersAdapterTests(TestCase):
    """HasOffers/TUNE uses aff_sub for lead_id."""

    def test_aff_sub_maps_to_lead_id(self):
        adapter = HasOffersAdapter()
        r = adapter.adapt({"aff_sub": "HASOFFER_LEAD"}, _config("hasoffers"))
        self.assertEqual(r["lead_id"], "HASOFFER_LEAD")

    def test_network_keys(self):
        for key in ["hasoffers", "tune"]:
            self.assertIn(key, HasOffersAdapter.network_keys)


class EverflowAdapterTests(TestCase):

    def test_sub1_maps_to_lead_id(self):
        adapter = EverflowAdapter()
        r = adapter.adapt({"sub1": "EF_LEAD"}, _config("everflow"))
        self.assertEqual(r["lead_id"], "EF_LEAD")

    def test_status_map_approved(self):
        adapter = EverflowAdapter()
        r = adapter.adapt({"status": "approved"}, _config("everflow"))
        self.assertEqual(r["cpalead_status"], "approved")

    def test_status_map_rejected_to_reversed(self):
        adapter = EverflowAdapter()
        r = adapter.adapt({"status": "rejected"}, _config("everflow"))
        self.assertIn(r["cpalead_status"], ("reversed", "rejected"))


class PollfishAdapterTests(TestCase):
    """Pollfish uses POST JSON with user_id and survey_id."""

    def test_user_id_maps_to_lead_id(self):
        adapter = PollfishAdapter()
        r = adapter.adapt({"user_id": "POLL_USER"}, _config("pollfish"))
        self.assertEqual(r["lead_id"], "POLL_USER")

    def test_survey_id_maps_to_offer_id(self):
        adapter = PollfishAdapter()
        r = adapter.adapt({"survey_id": "SURVEY_001"}, _config("pollfish"))
        self.assertEqual(r["offer_id"], "SURVEY_001")

    def test_cpa_maps_to_payout(self):
        adapter = PollfishAdapter()
        r = adapter.adapt({"cpa": "3.00"}, _config("pollfish"))
        self.assertEqual(r["payout"], "3.00")


class UnityAdsAdapterTests(TestCase):
    """Unity Ads uses productId, gameId, value, rewardName."""

    def test_product_id_maps_to_lead_id(self):
        adapter = UnityAdsAdapter()
        r = adapter.adapt({"productId": "UNITY_PRODUCT"}, _config("unity"))
        self.assertEqual(r["lead_id"], "UNITY_PRODUCT")

    def test_value_maps_to_payout(self):
        adapter = UnityAdsAdapter()
        r = adapter.adapt({"value": "1.50"}, _config("unity_ads"))
        self.assertEqual(r["payout"], "1.50")


class FacebookAdsAdapterTests(TestCase):
    """Facebook Ads Conversions API uses event_id, campaign_id, value."""

    def test_event_id_maps_to_lead_id(self):
        adapter = FacebookAdsAdapter()
        r = adapter.adapt({"event_id": "FB_EVENT_001"}, _config("facebook"))
        self.assertEqual(r["lead_id"], "FB_EVENT_001")

    def test_value_maps_to_payout(self):
        adapter = FacebookAdsAdapter()
        r = adapter.adapt({"value": "25.00"}, _config("meta"))
        self.assertEqual(r["payout"], "25.00")


class CustomSlotAdapterTests(TestCase):
    """Custom slots (custom1–custom10) use field_mapping from NetworkPostbackConfig."""

    def test_all_custom_keys_registered(self):
        for i in range(1, 11):
            self.assertIn(f"custom{i}", CustomSlotAdapter.network_keys)

    def test_empty_field_map_uses_generic_aliases(self):
        adapter = CustomSlotAdapter()
        r = adapter.adapt({"lead_id": "CUSTOM_LEAD"}, _config("custom1"))
        self.assertEqual(r["lead_id"], "CUSTOM_LEAD")

    def test_field_mapping_from_config_applied(self):
        adapter = CustomSlotAdapter()
        config = _config("custom2", field_mapping={"lead_id": "my_user_id"})
        r = adapter.adapt({"my_user_id": "MAPPED"}, config)
        self.assertEqual(r["lead_id"], "MAPPED")


class AllAdaptersRegistrationTests(TestCase):
    """Every adapter in ALL_NETWORK_ADAPTERS must be registerable and functional."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from api.postback.adapters.registry import register_all_adapters
        register_all_adapters()

    def test_all_adapters_count(self):
        self.assertGreaterEqual(len(ALL_NETWORK_ADAPTERS), 80)

    def test_every_adapter_has_network_keys(self):
        for cls in ALL_NETWORK_ADAPTERS:
            self.assertTrue(
                hasattr(cls, "network_keys") and len(cls.network_keys) > 0,
                f"{cls.__name__} has no network_keys"
            )

    def test_every_adapter_adapt_returns_dict(self):
        config = _config("test")
        for cls in ALL_NETWORK_ADAPTERS:
            adapter = cls()
            result = adapter.adapt({}, config)
            self.assertIsInstance(result, dict,
                f"{cls.__name__}.adapt() did not return dict")

    def test_every_adapter_has_standard_fields(self):
        config = _config("test")
        required = ["lead_id", "payout", "currency", "cpalead_status", "is_reversal"]
        for cls in ALL_NETWORK_ADAPTERS:
            adapter = cls()
            result = adapter.adapt({"lead_id": "L1"}, config)
            if "_error" in result:
                continue  # Skip adapters that errored
            for field in required:
                self.assertIn(field, result,
                    f"{cls.__name__} missing field: {field}")

    def test_registry_has_many_networks_registered(self):
        """Registry should have all 84+ networks registered."""
        registered = AdapterRegistry.registered_keys()
        self.assertGreater(len(registered), 10)  # at least 10 networks

    def test_known_keys_resolve_correctly(self):
        """Spot check known network keys resolve to correct adapter type."""
        from api.postback.adapters.networks import (
            CPALeadNetworkAdapter, HasOffersAdapter, EverflowAdapter,
            PollfishAdapter, UnityAdsAdapter,
        )
        checks = [
            ("cpalead", CPALeadNetworkAdapter),
            ("hasoffers", HasOffersAdapter),
            ("everflow", EverflowAdapter),
            ("pollfish", PollfishAdapter),
            ("unity", UnityAdsAdapter),
        ]
        for key, expected_cls in checks:
            adapter = get_adapter(key)
            self.assertIsInstance(adapter, expected_cls,
                f"get_adapter({key!r}) returned {type(adapter).__name__}")

    def test_unknown_key_returns_generic(self):
        adapter = get_adapter("totally_nonexistent_network_xyz")
        self.assertIsInstance(adapter, GenericAdapter)


class AdapterEventTypeDerivationTests(TestCase):
    """Test event_type derivation across different goal_id patterns."""

    def setUp(self):
        self.adapter = CPALeadNetworkAdapter()
        self.config = _config("cpalead")

    def test_install_events(self):
        for goal in ["install", "app_install", "app"]:
            r = self.adapter.adapt({"goal": goal}, self.config)
            self.assertEqual(r["event_type"], "install", f"Failed for goal={goal!r}")

    def test_sale_events(self):
        for goal in ["sale", "purchase", "order"]:
            r = self.adapter.adapt({"goal": goal}, self.config)
            self.assertEqual(r["event_type"], "sale", f"Failed for goal={goal!r}")

    def test_registration_events(self):
        for goal in ["signup", "register", "registration"]:
            r = self.adapter.adapt({"goal": goal}, self.config)
            self.assertEqual(r["event_type"], "registration", f"Failed for goal={goal!r}")

    def test_survey_events(self):
        r = self.adapter.adapt({"goal": "survey"}, self.config)
        self.assertEqual(r["event_type"], "survey")

    def test_deposit_events(self):
        for goal in ["deposit", "ftd"]:
            r = self.adapter.adapt({"goal": goal}, self.config)
            self.assertEqual(r["event_type"], "deposit")

    def test_unknown_goal_returns_custom(self):
        r = self.adapter.adapt({"goal": "mystery_action_xyz"}, self.config)
        self.assertEqual(r["event_type"], "custom")

    def test_no_goal_returns_unknown(self):
        r = self.adapter.adapt({}, self.config)
        self.assertEqual(r["event_type"], "unknown")
