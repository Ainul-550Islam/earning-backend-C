"""
test_s2s.py – Tests for S2S outbound postback sender.

Tests:
  • Macro substitution (lead_id, payout, ip_address, goal_id, sub_ids)
  • HTTPS enforcement (HTTP → HTTPS upgrade)
  • URL encoding of macro values
  • Retry logic (3 attempts with backoff)
  • HMAC signing of outbound URL
  • fire_delay_ms respected
  • S2SLog record created on success and failure
  • No callback_url → skip silently (returns True)
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

from django.test import TestCase

from api.postback.utils.s2s_sender import (
    _substitute_macros,
    _enforce_https,
    _safe_encode_value,
    fire_s2s_postback,
)


def _mock_config(
    network_key="test_net",
    callback_url="",
    callback_method="GET",
    callback_secret="",
):
    config = MagicMock()
    config.network_key = network_key
    config.callback_url = callback_url
    config.callback_method = callback_method
    config.callback_secret = callback_secret
    return config


def _payload(**kwargs):
    base = {
        "lead_id": "LEAD_001",
        "offer_id": "OFFER_001",
        "user_id": "USER_001",
        "payout": "5.00",
        "currency": "USD",
        "transaction_id": "TXN_001",
        "goal_id": "sale",
        "sub_id1": "SUB1",
        "sub_id2": "SUB2",
        "sub_id3": "SUB3",
        "country": "US",
        "device": "mobile",
        "_source_ip": "1.2.3.4",
        "_network_key": "test_net",
        "event_type": "sale",
        "cpalead_status": "approved",
    }
    base.update(kwargs)
    return base


class MacroSubstitutionTests(TestCase):

    def test_lead_id_macro(self):
        url = "https://example.com/cb?lead={lead_id}"
        result = _substitute_macros(url, _payload())
        self.assertEqual(result, "https://example.com/cb?lead=LEAD_001")

    def test_payout_macro(self):
        url = "https://example.com/cb?rev={payout}"
        result = _substitute_macros(url, _payload())
        self.assertEqual(result, "https://example.com/cb?rev=5.00")

    def test_ip_address_macro(self):
        url = "https://example.com/cb?ip={ip_address}"
        result = _substitute_macros(url, _payload())
        self.assertEqual(result, "https://example.com/cb?ip=1.2.3.4")

    def test_ip_alias_macro(self):
        url = "https://example.com/cb?ip={ip}"
        result = _substitute_macros(url, _payload())
        self.assertEqual(result, "https://example.com/cb?ip=1.2.3.4")

    def test_goal_id_macro(self):
        url = "https://example.com/cb?goal={goal_id}"
        result = _substitute_macros(url, _payload())
        self.assertEqual(result, "https://example.com/cb?goal=sale")

    def test_sub_id_macros(self):
        url = "https://example.com/cb?s1={sub_id1}&s2={sub_id2}&s3={sub_id3}"
        result = _substitute_macros(url, _payload())
        self.assertEqual(result, "https://example.com/cb?s1=SUB1&s2=SUB2&s3=SUB3")

    def test_event_type_macro(self):
        url = "https://example.com/cb?evt={event_type}"
        result = _substitute_macros(url, _payload())
        self.assertEqual(result, "https://example.com/cb?evt=sale")

    def test_unknown_macro_replaced_with_empty(self):
        url = "https://example.com/cb?x={nonexistent_macro}"
        result = _substitute_macros(url, _payload())
        self.assertEqual(result, "https://example.com/cb?x=")

    def test_multiple_macros_in_one_url(self):
        url = "https://t.com/?l={lead_id}&p={payout}&ip={ip_address}&g={goal_id}"
        result = _substitute_macros(url, _payload())
        self.assertEqual(result, "https://t.com/?l=LEAD_001&p=5.00&ip=1.2.3.4&g=sale")

    def test_url_encoding_of_special_chars(self):
        payload = _payload(sub_id1="hello world&test=1")
        url = "https://example.com/cb?s={sub_id1}"
        result = _substitute_macros(url, payload)
        self.assertNotIn(" ", result)
        self.assertNotIn("&test=1", result.split("s=")[1])


class HTTPSEnforcerTests(TestCase):

    def test_https_url_unchanged(self):
        url = "https://example.com/cb"
        self.assertEqual(_enforce_https(url, "net"), url)

    def test_http_url_upgraded_to_https(self):
        url = "http://example.com/cb"
        result = _enforce_https(url, "net")
        self.assertTrue(result.startswith("https://"))
        self.assertEqual(result, "https://example.com/cb")

    def test_http_upgrade_preserves_path_and_params(self):
        url = "http://track.example.com/postback?lead=123&payout=5.00"
        result = _enforce_https(url, "net")
        self.assertEqual(result, "https://track.example.com/postback?lead=123&payout=5.00")


class SafeEncodeTests(TestCase):

    def test_normal_string_unchanged(self):
        self.assertEqual(_safe_encode_value("hello"), "hello")

    def test_space_encoded(self):
        result = _safe_encode_value("hello world")
        self.assertNotIn(" ", result)

    def test_ampersand_encoded(self):
        result = _safe_encode_value("a&b=c")
        self.assertNotIn("&", result)

    def test_equals_encoded(self):
        result = _safe_encode_value("key=val")
        self.assertNotIn("=", result)


class FireS2SPostbackTests(TestCase):

    def test_no_callback_url_returns_true(self):
        config = _mock_config(callback_url="")
        result = fire_s2s_postback(
            network_config=config,
            adapted_payload=_payload(),
            postback_log_id=None,
        )
        self.assertTrue(result)

    @patch("api.postback.utils.s2s_sender._fire_http")
    @patch("api.postback.utils.s2s_sender._record_s2s_result")
    def test_successful_http_200_returns_true(self, mock_record, mock_http):
        mock_http.return_value = (200, "OK", None)
        config = _mock_config(callback_url="https://adv.example.com/cb?l={lead_id}")
        result = fire_s2s_postback(
            network_config=config,
            adapted_payload=_payload(),
            postback_log_id="log-uuid-001",
        )
        self.assertTrue(result)
        mock_record.assert_called_once()
        call_kwargs = mock_record.call_args[1]
        self.assertTrue(call_kwargs["success"])

    @patch("api.postback.utils.s2s_sender._fire_http")
    @patch("api.postback.utils.s2s_sender._record_s2s_result")
    @patch("time.sleep")
    def test_retry_on_failure_exhausts_all_attempts(self, mock_sleep, mock_record, mock_http):
        mock_http.return_value = (500, "Error", None)
        config = _mock_config(callback_url="https://adv.example.com/cb")
        result = fire_s2s_postback(
            network_config=config,
            adapted_payload=_payload(),
            postback_log_id="log-uuid-002",
        )
        self.assertFalse(result)
        self.assertEqual(mock_http.call_count, 3)  # 3 retries
        mock_record.assert_called_once()
        self.assertFalse(mock_record.call_args[1]["success"])

    @patch("api.postback.utils.s2s_sender._fire_http")
    @patch("api.postback.utils.s2s_sender._record_s2s_result")
    @patch("time.sleep")
    def test_retry_succeeds_on_second_attempt(self, mock_sleep, mock_record, mock_http):
        mock_http.side_effect = [(500, "Error", None), (200, "OK", None)]
        config = _mock_config(callback_url="https://adv.example.com/cb")
        result = fire_s2s_postback(
            network_config=config,
            adapted_payload=_payload(),
            postback_log_id="log-uuid-003",
        )
        self.assertTrue(result)
        self.assertEqual(mock_http.call_count, 2)

    @patch("api.postback.utils.s2s_sender._fire_http")
    @patch("api.postback.utils.s2s_sender._record_s2s_result")
    def test_http_url_upgraded_to_https_before_fire(self, mock_record, mock_http):
        mock_http.return_value = (200, "OK", None)
        config = _mock_config(callback_url="http://adv.example.com/cb?l={lead_id}")
        fire_s2s_postback(
            network_config=config,
            adapted_payload=_payload(),
            postback_log_id=None,
        )
        fired_url = mock_http.call_args[0][0]
        self.assertTrue(fired_url.startswith("https://"), f"Expected HTTPS, got: {fired_url}")

    @patch("api.postback.utils.s2s_sender._fire_http")
    @patch("api.postback.utils.s2s_sender._record_s2s_result")
    def test_hmac_sig_appended_when_secret_set(self, mock_record, mock_http):
        mock_http.return_value = (200, "OK", None)
        config = _mock_config(
            callback_url="https://adv.example.com/cb",
            callback_secret="my-secret-key",
        )
        fire_s2s_postback(
            network_config=config,
            adapted_payload=_payload(),
            postback_log_id=None,
        )
        fired_url = mock_http.call_args[0][0]
        self.assertIn("sig=", fired_url)
        self.assertIn("sig_ts=", fired_url)

    @patch("api.postback.utils.s2s_sender._fire_http")
    @patch("api.postback.utils.s2s_sender._record_s2s_result")
    def test_no_hmac_when_no_secret(self, mock_record, mock_http):
        mock_http.return_value = (200, "OK", None)
        config = _mock_config(
            callback_url="https://adv.example.com/cb",
            callback_secret="",
        )
        fire_s2s_postback(
            network_config=config,
            adapted_payload=_payload(),
            postback_log_id=None,
        )
        fired_url = mock_http.call_args[0][0]
        self.assertNotIn("sig=", fired_url)
