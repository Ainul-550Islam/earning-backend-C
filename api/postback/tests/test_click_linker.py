"""
test_click_linker.py – Tests for click-to-conversion linking.
"""
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase

from api.postback.utils.click_linker import (
    _looks_like_click_id,
    _cache_get,
    _cache_result,
    resolve_click_id,
)


class LooksLikeClickIdTests(TestCase):

    def test_uuid_is_click_id(self):
        self.assertTrue(_looks_like_click_id("550e8400-e29b-41d4-a716-446655440000"))

    def test_long_hex_is_click_id(self):
        self.assertTrue(_looks_like_click_id("a" * 32))

    def test_long_alphanumeric_is_click_id(self):
        self.assertTrue(_looks_like_click_id("ABCD1234EFGH5678IJKL9012"))

    def test_short_string_not_click_id(self):
        self.assertFalse(_looks_like_click_id("US"))

    def test_country_code_not_click_id(self):
        self.assertFalse(_looks_like_click_id("mobile"))

    def test_empty_not_click_id(self):
        self.assertFalse(_looks_like_click_id(""))


class CacheTests(TestCase):

    def setUp(self):
        cache.clear()

    def test_cache_set_and_get(self):
        _cache_result("cpalead", "LEAD001", "CLICK001")
        result = _cache_get("cpalead", "LEAD001")
        self.assertEqual(result, "CLICK001")

    def test_cache_miss_returns_empty(self):
        result = _cache_get("cpalead", "NONEXISTENT_LEAD")
        self.assertEqual(result, "")

    def test_empty_lead_id_returns_empty(self):
        result = _cache_get("cpalead", "")
        self.assertEqual(result, "")


class ResolveClickIdTests(TestCase):

    def setUp(self):
        cache.clear()

    def _make_log(self, click_id=""):
        log = MagicMock()
        log.pk = "log-uuid-001"
        log.click_id = click_id
        return log

    def _payload(self, **kwargs):
        base = {"lead_id": "LEAD001", "offer_id": "OFFER001", "_network_key": "cpalead"}
        base.update(kwargs)
        return base

    def test_strategy1_explicit_click_id_in_payload(self):
        payload = self._payload(click_id="EXPLICIT_CLICK_001")
        log = self._make_log()
        result = resolve_click_id(adapted_payload=payload, postback_log=log)
        self.assertEqual(result, "EXPLICIT_CLICK_001")
        self.assertEqual(log.click_id, "EXPLICIT_CLICK_001")

    def test_strategy1_sub_id1_uuid_detected(self):
        uuid_val = "550e8400-e29b-41d4-a716-446655440000"
        payload = self._payload(sub_id1=uuid_val)
        log = self._make_log()
        result = resolve_click_id(adapted_payload=payload, postback_log=log)
        self.assertEqual(result, uuid_val)

    def test_strategy2_cache_hit(self):
        _cache_result("cpalead", "LEAD002", "CACHED_CLICK_002")
        payload = self._payload(lead_id="LEAD002")
        log = self._make_log()
        result = resolve_click_id(adapted_payload=payload, postback_log=log)
        self.assertEqual(result, "CACHED_CLICK_002")

    @patch("api.postback.utils.click_linker._lookup_offer_click")
    def test_strategy3_lead_id_matches_offer_click(self, mock_lookup):
        mock_lookup.return_value = "LEAD003"
        payload = self._payload(lead_id="LEAD003")
        log = self._make_log()
        result = resolve_click_id(adapted_payload=payload, postback_log=log)
        self.assertEqual(result, "LEAD003")
        mock_lookup.assert_called_once_with(click_id="LEAD003")

    @patch("api.postback.utils.click_linker._lookup_offer_click")
    def test_strategy4_transaction_id_matches(self, mock_lookup):
        mock_lookup.side_effect = lambda click_id: "TXN_CLICK" if click_id == "TXN001" else ""
        payload = self._payload(lead_id="UNKNOWN_LEAD", transaction_id="TXN001")
        log = self._make_log()
        result = resolve_click_id(adapted_payload=payload, postback_log=log)
        self.assertEqual(result, "TXN_CLICK")

    @patch("api.postback.utils.click_linker._lookup_offer_click")
    def test_no_match_returns_empty(self, mock_lookup):
        mock_lookup.return_value = ""
        payload = self._payload(lead_id="NOMATCH", transaction_id="NOTXN")
        log = self._make_log()
        result = resolve_click_id(adapted_payload=payload, postback_log=log)
        self.assertEqual(result, "")

    def test_exception_returns_empty_never_raises(self):
        """resolve_click_id never raises — returns empty on error."""
        result = resolve_click_id(adapted_payload=None, postback_log=self._make_log())
        self.assertEqual(result, "")

    def test_ad_networks_not_installed_returns_empty(self):
        """If ad_networks app not installed, returns "" gracefully."""
        with patch("api.postback.utils.click_linker._lookup_offer_click",
                   side_effect=ImportError("no ad_networks")):
            payload = self._payload(lead_id="L1")
            log = self._make_log()
            result = resolve_click_id(adapted_payload=payload, postback_log=log)
            self.assertEqual(result, "")
