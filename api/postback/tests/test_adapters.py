"""
test_adapters.py – Unit tests for postback network adapters.

Tests:
  • CPALeadAdapter: field mapping, goal_id derivation, event_type, reversal detection
  • GenericAdapter: alias resolution, field_mapping override, fallback
  • AdapterRegistry: registration, lookup, fallback to generic
"""
from django.test import TestCase
from unittest.mock import MagicMock

from api.postback.adapters.cpalead import CPALeadAdapter as _OldCPALeadAdapter
from api.postback.adapters.networks import CPALeadNetworkAdapter
from api.postback.adapters.generic import GenericAdapter
from api.postback.adapters.registry import AdapterRegistry, get_adapter

# Registry returns CPALeadNetworkAdapter (from networks.py)
CPALeadAdapter = _OldCPALeadAdapter  # keep for unit tests of the class itself


def _mock_config(network_key="cpalead", field_mapping=None, callback_url=""):
    config = MagicMock()
    config.network_key = network_key
    config.field_mapping = field_mapping or {}
    config.callback_url = callback_url
    return config


class CPALeadAdapterTests(TestCase):

    def setUp(self):
        self.adapter = CPALeadAdapter()
        self.config = _mock_config()

    def test_standard_fields_extracted(self):
        payload = {
            "lead_id": "LEAD_001",
            "offer_id": "OFFER_001",
            "user_id": "USER_001",
            "payout": "5.00",
            "currency": "USD",
            "transaction_id": "TXN_001",
        }
        result = self.adapter.adapt(payload, self.config)
        self.assertEqual(result["lead_id"], "LEAD_001")
        self.assertEqual(result["offer_id"], "OFFER_001")
        self.assertEqual(result["payout"], "5.00")
        self.assertEqual(result["currency"], "USD")

    def test_cpalead_specific_fields_extracted(self):
        payload = {
            "lead_id": "L1",
            "offer_id": "O1",
            "goal_id": "sale",
            "sub_id": "SUB1",
            "sub_id2": "SUB2",
            "sub_id3": "SUB3",
            "country": "US",
            "device": "mobile",
            "os": "ios",
            "browser": "safari",
            "status": "approved",
        }
        result = self.adapter.adapt(payload, self.config)
        self.assertEqual(result["goal_id"], "sale")
        self.assertEqual(result["sub_id1"], "SUB1")
        self.assertEqual(result["sub_id2"], "SUB2")
        self.assertEqual(result["sub_id3"], "SUB3")
        self.assertEqual(result["country"], "US")
        self.assertEqual(result["device"], "mobile")
        self.assertEqual(result["os"], "ios")

    def test_event_type_derived_from_goal_id_sale(self):
        payload = {"lead_id": "L1", "offer_id": "O1", "goal_id": "sale"}
        result = self.adapter.adapt(payload, self.config)
        self.assertEqual(result["event_type"], "sale")

    def test_event_type_derived_from_goal_id_install(self):
        payload = {"lead_id": "L1", "offer_id": "O1", "goal_id": "app_install"}
        result = self.adapter.adapt(payload, self.config)
        self.assertEqual(result["event_type"], "install")

    def test_event_type_derived_from_goal_id_registration(self):
        payload = {"lead_id": "L1", "offer_id": "O1", "goal_id": "signup"}
        result = self.adapter.adapt(payload, self.config)
        self.assertEqual(result["event_type"], "registration")

    def test_event_type_unknown_when_no_goal_id(self):
        payload = {"lead_id": "L1", "offer_id": "O1"}
        result = self.adapter.adapt(payload, self.config)
        self.assertEqual(result["event_type"], "unknown")

    def test_event_type_custom_for_unknown_goal(self):
        payload = {"lead_id": "L1", "offer_id": "O1", "goal_id": "mystery_event"}
        result = self.adapter.adapt(payload, self.config)
        self.assertEqual(result["event_type"], "custom")

    def test_reversal_detection_reversed_status(self):
        payload = {"lead_id": "L1", "offer_id": "O1", "status": "reversed"}
        result = self.adapter.adapt(payload, self.config)
        self.assertTrue(result["is_reversal"])

    def test_reversal_detection_approved_status(self):
        payload = {"lead_id": "L1", "offer_id": "O1", "status": "approved"}
        result = self.adapter.adapt(payload, self.config)
        self.assertFalse(result["is_reversal"])

    def test_field_mapping_override(self):
        """field_mapping lets admin remap CPAlead param names."""
        config = _mock_config(field_mapping={"lead_id": "click_id", "offer_id": "campaign"})
        payload = {"click_id": "MAPPED_LEAD", "campaign": "MAPPED_OFFER"}
        result = self.adapter.adapt(payload, config)
        self.assertEqual(result["lead_id"], "MAPPED_LEAD")
        self.assertEqual(result["offer_id"], "MAPPED_OFFER")

    def test_adapter_metadata_set(self):
        payload = {"lead_id": "L1", "offer_id": "O1"}
        result = self.adapter.adapt(payload, self.config)
        self.assertEqual(result["_adapter"], "cpalead")
        self.assertEqual(result["_network_key"], "cpalead")

    def test_missing_fields_return_empty_string(self):
        result = self.adapter.adapt({}, self.config)
        self.assertEqual(result["lead_id"], "")
        self.assertEqual(result["payout"], "0")
        self.assertEqual(result["currency"], "USD")  # default

    def test_exception_inside_adapt_returns_error_dict(self):
        """If adapt raises internally, returns {'_error': ...}."""
        adapter = CPALeadAdapter()
        # Pass an non-dict payload to force an error
        result = adapter.adapt(None, self.config)  # type: ignore
        self.assertIn("_error", result)

    def test_is_lead_reversed_method(self):
        adapted = {"cpalead_status": "reversed"}
        self.assertTrue(self.adapter.is_lead_reversed(adapted))

    def test_is_lead_pending_method(self):
        adapted = {"cpalead_status": "pending"}
        self.assertTrue(self.adapter.is_lead_pending(adapted))

    def test_network_keys_list(self):
        self.assertIn("cpalead", CPALeadAdapter.network_keys)


class GenericAdapterTests(TestCase):

    def setUp(self):
        self.adapter = GenericAdapter()
        self.config = _mock_config(network_key="unknown_net")

    def test_common_lead_id_aliases(self):
        for alias in ["lead_id", "click_id", "clickid", "lid"]:
            result = self.adapter.adapt({alias: "LEAD_TEST"}, self.config)
            self.assertEqual(result["lead_id"], "LEAD_TEST", f"Failed for alias: {alias}")

    def test_common_payout_aliases(self):
        for alias in ["payout", "commission", "amount", "revenue"]:
            result = self.adapter.adapt({alias: "3.50"}, self.config)
            self.assertEqual(result["payout"], "3.50", f"Failed for alias: {alias}")

    def test_currency_defaults_to_usd(self):
        result = self.adapter.adapt({"lead_id": "L1"}, self.config)
        self.assertEqual(result["currency"], "USD")

    def test_field_mapping_applied(self):
        config = _mock_config(field_mapping={"lead_id": "custom_lid"})
        result = self.adapter.adapt({"custom_lid": "MAPPED"}, config)
        self.assertEqual(result["lead_id"], "MAPPED")

    def test_adapter_metadata(self):
        result = self.adapter.adapt({}, self.config)
        self.assertEqual(result["_adapter"], "generic")

    def test_exception_returns_error_dict(self):
        result = self.adapter.adapt(None, self.config)  # type: ignore
        self.assertIn("_error", result)


class AdapterRegistryTests(TestCase):

    def setUp(self):
        # Re-register all adapters fresh for each test
        from api.postback.adapters.registry import register_all_adapters
        register_all_adapters()

    def test_cpalead_lookup_returns_cpalead_adapter(self):
        adapter = get_adapter("cpalead")
        self.assertIsInstance(adapter, (CPALeadNetworkAdapter, _OldCPALeadAdapter))

    def test_cpa_lead_alias_lookup(self):
        adapter = get_adapter("cpa_lead")
        self.assertIsInstance(adapter, (CPALeadNetworkAdapter, _OldCPALeadAdapter))

    def test_unknown_network_key_returns_generic(self):
        adapter = get_adapter("totally_unknown_network_xyz")
        self.assertIsInstance(adapter, GenericAdapter)

    def test_case_insensitive_lookup(self):
        adapter = get_adapter("CPALEAD")
        self.assertIsInstance(adapter, (CPALeadNetworkAdapter, _OldCPALeadAdapter))

    def test_registered_keys_not_empty(self):
        keys = AdapterRegistry.registered_keys()
        self.assertIn("cpalead", keys)
