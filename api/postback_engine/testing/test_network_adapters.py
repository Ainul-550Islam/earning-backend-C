"""testing/test_network_adapters.py — Network adapter tests."""
from django.test import TestCase
from decimal import Decimal
from api.postback_engine.network_adapters.adapters import get_adapter, ADAPTER_REGISTRY

class TestAdapters(TestCase):
    def test_cpalead_maps_sub1_to_lead_id(self):
        a = get_adapter("cpalead")
        r = a.normalise({"sub1": "u1", "amount": "0.50", "oid": "o1", "sid": "t1"})
        self.assertEqual(r["lead_id"], "u1")
        self.assertEqual(r["payout"], Decimal("0.50"))

    def test_status_1_is_approved(self):
        for key in ["cpalead", "adgate", "offertoro"]:
            a = get_adapter(key)
            self.assertIn(a.normalise_status("1"), ["approved", "approved"])

    def test_expand_macros_replaces_click_id(self):
        a = get_adapter("cpalead")
        url = a.expand_macros("https://x.com/?c={click_id}", {"click_id": "abc"})
        self.assertEqual(url, "https://x.com/?c=abc")

    def test_unknown_macro_preserved(self):
        a = get_adapter("cpalead")
        url = a.expand_macros("https://x.com/?x={unknown}", {})
        self.assertIn("{unknown}", url)

    def test_all_registered_adapters_have_network_key(self):
        for key, cls in ADAPTER_REGISTRY.items():
            instance = cls()
            self.assertEqual(instance.get_network_key(), key, f"Adapter {key} has wrong network_key")

    def test_fallback_adapter_for_unknown_network(self):
        a = get_adapter("totally_unknown_xyz")
        self.assertIsNotNone(a)
        r = a.normalise({"lead_id": "u1", "payout": "1.00"})
        self.assertIn("lead_id", r)

    def test_payout_coercion_from_string(self):
        a = get_adapter("cpalead")
        self.assertEqual(a.parse_payout("1,234.56"), Decimal("1234.56"))
        self.assertEqual(a.parse_payout("invalid"), Decimal("0"))
        self.assertEqual(a.parse_payout(None), Decimal("0"))
