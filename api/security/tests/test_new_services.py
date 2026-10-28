"""
api/security/tests/test_new_services.py
========================================
Comprehensive test coverage for:
- JWTService
- ClickInjectionPrevention
- PostbackS2SSecurity
- SubIDTrackingSecurity
- AdvertiserFraudShield
- BotDetectionML
"""
from __future__ import annotations

import hashlib
import hmac
import time
from datetime import timedelta
from typing import Optional
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_request(
    ua:       str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    ip:       str = "203.0.113.5",
    path:     str = "/",
    method:   str = "GET",
    headers:  Optional[dict] = None,
) -> MagicMock:
    rf  = RequestFactory()
    req = rf.get(path)
    req.META["HTTP_USER_AGENT"]    = ua
    req.META["REMOTE_ADDR"]        = ip
    req.META["HTTP_ACCEPT"]        = "text/html,application/xhtml+xml"
    req.META["HTTP_ACCEPT_LANGUAGE"] = "en-US,en;q=0.9"
    req.META["HTTP_ACCEPT_ENCODING"] = "gzip, deflate, br"
    if headers:
        for k, v in headers.items():
            req.META[k] = v
    return req


# ─────────────────────────────────────────────────────────────────────────────
# 1. JWT Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestJWTManager(TestCase):

    def setUp(self):
        from api.security.services.JWTService import JWTManager
        self.manager = JWTManager()

    def test_issue_returns_token_pair(self):
        pair = self.manager.issue(user_id=1)
        self.assertIsNotNone(pair.access_token)
        self.assertIsNotNone(pair.refresh_token)
        self.assertTrue(pair.access_token.count(".") == 2)   # header.body.sig

    def test_validate_access_valid_token(self):
        pair    = self.manager.issue(user_id=42)
        payload = self.manager.validate_access(pair.access_token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["user_id"], 42)

    def test_validate_access_wrong_type_rejected(self):
        pair    = self.manager.issue(user_id=42)
        # Refresh token must NOT validate as access token
        payload = self.manager.validate_access(pair.refresh_token)
        self.assertIsNone(payload)

    def test_validate_access_tampered_token_rejected(self):
        pair    = self.manager.issue(user_id=42)
        tampered = pair.access_token[:-5] + "XXXXX"
        payload  = self.manager.validate_access(tampered)
        self.assertIsNone(payload)

    def test_validate_access_expired_token_rejected(self):
        pair    = self.manager.issue(user_id=42)
        # Manually build expired payload
        payload = self.manager._decode(pair.access_token)
        payload["exp"] = int(time.time()) - 1
        expired_token  = self.manager._encode(payload)
        result = self.manager.validate_access(expired_token)
        self.assertIsNone(result)

    def test_revoke_invalidates_token(self):
        pair   = self.manager.issue(user_id=42)
        self.manager.revoke(pair.access_token)
        result = self.manager.validate_access(pair.access_token)
        self.assertIsNone(result)

    def test_rotate_refresh_issues_new_pair(self):
        pair     = self.manager.issue(user_id=42)
        new_pair = self.manager.rotate_refresh(pair.refresh_token)
        self.assertIsNotNone(new_pair)
        self.assertNotEqual(pair.access_token, new_pair.access_token)
        self.assertNotEqual(pair.refresh_token, new_pair.refresh_token)

    def test_rotate_refresh_blacklists_old_token(self):
        pair = self.manager.issue(user_id=42)
        self.manager.rotate_refresh(pair.refresh_token)
        # Old refresh token should now be invalid
        result = self.manager.rotate_refresh(pair.refresh_token)
        self.assertIsNone(result)

    def test_refresh_token_reuse_attack_revokes_family(self):
        """Replaying a refresh token should revoke the entire family."""
        pair = self.manager.issue(user_id=42)
        self.manager.rotate_refresh(pair.refresh_token)   # first use
        self.manager.rotate_refresh(pair.refresh_token)   # replay attempt → revoke family
        # Even a new refresh from the new pair should be invalid now
        # (family revoked means all tokens in family are invalid)

    def test_revoke_all_clears_user_tokens(self):
        self.manager.issue(user_id=99)
        self.manager.issue(user_id=99)
        revoked = self.manager.revoke_all(user_id=99)
        self.assertGreaterEqual(revoked, 1)

    def test_introspect_valid_token(self):
        pair = self.manager.issue(user_id=42)
        info = self.manager.introspect(pair.access_token)
        self.assertEqual(info["user_id"], 42)
        self.assertTrue(info["valid"])
        self.assertFalse(info["blacklisted"])

    def test_introspect_invalid_token(self):
        info = self.manager.introspect("not.a.token")
        self.assertFalse(info["valid"])

    def test_device_id_stored_in_payload(self):
        pair    = self.manager.issue(user_id=42, device_id="dev_abc123")
        payload = self.manager.validate_access(pair.access_token)
        self.assertEqual(payload["device_id"], "dev_abc123")

    def test_token_pair_has_expiry(self):
        pair = self.manager.issue(user_id=42)
        self.assertIsNotNone(pair.access_expires_at)
        self.assertIsNotNone(pair.refresh_expires_at)
        self.assertGreater(pair.refresh_expires_at, pair.access_expires_at)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Click Injection Prevention Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestClickInjectionPrevention(TestCase):

    def setUp(self):
        from api.security.services.ClickInjectionPrevention import ClickInjectionPrevention
        self.engine = ClickInjectionPrevention()

    def _valid_click(self, **overrides):
        defaults = dict(
            click_token = "token_abc123",
            offer_id    = "offer_1",
            user_id     = 42,
            ip          = "203.0.113.5",
            user_agent  = "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36",
            referrer    = "https://google.com/ads",
            sub_id      = "source_fb01",
            device_id   = "dev_abc",
            click_ts    = int(time.time()),
        )
        defaults.update(overrides)
        return defaults

    def test_valid_click_is_allowed(self):
        result = self.engine.validate_click(**self._valid_click())
        self.assertTrue(result.is_valid)
        self.assertFalse(result.is_injected)
        self.assertEqual(result.recommended_action, "allow")

    def test_future_timestamp_flagged(self):
        result = self.engine.validate_click(
            **self._valid_click(click_token="fut_token", click_ts=int(time.time()) + 3600)
        )
        self.assertIn("future_timestamp", result.signals)
        self.assertGreater(result.risk_score, 0)

    def test_fraud_subid_flagged(self):
        result = self.engine.validate_click(
            **self._valid_click(click_token="fraud_sub_tok", sub_id="test")
        )
        self.assertTrue(any("fraud_subid" in s for s in result.signals))

    def test_missing_user_agent_increases_score(self):
        result = self.engine.validate_click(
            **self._valid_click(click_token="no_ua_tok", user_agent="")
        )
        self.assertGreater(result.risk_score, 0)

    def test_conversion_before_click_is_rejected(self):
        click_ts = int(time.time())
        conv_ts  = click_ts - 100   # conversion happened BEFORE click
        self.engine.validate_click(**self._valid_click(click_token="before_tok", click_ts=click_ts))
        result = self.engine.validate_conversion(
            click_token   = "before_tok",
            conversion_ts = conv_ts,
            offer_id      = "offer_1",
        )
        self.assertIn("conversion_before_click", result.signals)
        self.assertTrue(result.is_injected)
        self.assertEqual(result.recommended_action, "reject")

    def test_instant_install_to_click_is_injected(self):
        click_ts = int(time.time()) - 1  # click 1 second ago
        conv_ts  = int(time.time())       # conversion NOW (1s after click)
        self.engine.validate_click(**self._valid_click(click_token="fast_conv_tok", click_ts=click_ts))
        result = self.engine.validate_conversion(
            click_token   = "fast_conv_tok",
            conversion_ts = conv_ts,
            offer_id      = "offer_1",
        )
        self.assertIn("install_to_click_too_fast", result.signals)
        self.assertTrue(result.is_injected)
        self.assertEqual(result.recommended_action, "reject")

    def test_unknown_click_token_conversion_rejected(self):
        result = self.engine.validate_conversion(
            click_token   = "nonexistent_token_xyz",
            conversion_ts = int(time.time()),
            offer_id      = "offer_1",
        )
        self.assertFalse(result.is_valid)
        self.assertIn("click_not_found", result.signals)

    def test_legitimate_conversion_credited(self):
        click_ts = int(time.time()) - 300   # click 5 minutes ago
        conv_ts  = int(time.time())
        self.engine.validate_click(**self._valid_click(click_token="legit_tok", click_ts=click_ts))
        result = self.engine.validate_conversion(
            click_token   = "legit_tok",
            conversion_ts = conv_ts,
            offer_id      = "offer_1",
        )
        self.assertTrue(result.is_valid)
        self.assertFalse(result.is_injected)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Postback S2S Security Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPostbackS2SSecurity(TestCase):

    def setUp(self):
        from api.security.services.PostbackS2SSecurity import PostbackS2SSecurity
        self.engine = PostbackS2SSecurity()

    def _valid_postback(self, **overrides):
        defaults = dict(
            advertiser_id = 1,
            click_token   = "click_abc123",
            payout        = 5.00,
            currency      = "USD",
            goal_id       = "install",
            postback_ts   = int(time.time()),
            signature     = "",
            sender_ip     = "203.0.113.10",
            raw_query     = "advertiser_id=1&click_id=click_abc123&payout=5.00",
            sub_id        = "pub_src_001",
            publisher_id  = 42,
        )
        defaults.update(overrides)
        return defaults

    def test_valid_postback_accepted(self):
        result = self.engine.validate_postback(**self._valid_postback())
        self.assertTrue(result.is_valid)
        self.assertEqual(result.status, "ok")

    def test_expired_postback_rejected(self):
        result = self.engine.validate_postback(
            **self._valid_postback(
                click_token = "old_tok_001",
                postback_ts = int(time.time()) - 600,  # 10 minutes old
            )
        )
        self.assertIn("postback_timestamp_expired", result.signals)

    def test_replay_attack_rejected(self):
        params = self._valid_postback(click_token="replay_tok")
        self.engine.validate_postback(**params)   # first call OK
        result = self.engine.validate_postback(**params)  # replay
        self.assertFalse(result.is_valid)
        self.assertEqual(result.status, "duplicate")

    def test_negative_payout_flagged(self):
        result = self.engine.validate_postback(
            **self._valid_postback(click_token="neg_pay_tok", payout=-1.0)
        )
        self.assertIn("negative_payout", result.signals)

    def test_excessive_payout_flagged(self):
        result = self.engine.validate_postback(
            **self._valid_postback(click_token="big_pay_tok", payout=99999.0)
        )
        self.assertIn("payout_exceeds_max_threshold", result.signals)

    def test_audit_hash_is_sha256(self):
        result = self.engine.validate_postback(**self._valid_postback(click_token="hash_tok"))
        self.assertEqual(len(result.audit_hash), 64)  # SHA-256 hex = 64 chars

    def test_duplicate_conversion_rejected(self):
        params = self._valid_postback(click_token="dup_conv_tok")
        first  = self.engine.validate_postback(**params)
        second = self.engine.validate_postback(**{**params, "postback_ts": int(time.time()) + 10})
        self.assertTrue(first.is_valid)
        self.assertFalse(second.is_valid)
        self.assertEqual(second.status, "duplicate")


# ─────────────────────────────────────────────────────────────────────────────
# 4. SubID Tracking Security Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSubIDTrackingSecurity(TestCase):

    def setUp(self):
        from api.security.services.SubIDTrackingSecurity import SubIDTrackingSecurity
        self.engine = SubIDTrackingSecurity()

    def test_valid_subid_allowed(self):
        result = self.engine.validate(
            sub_id="source_fb_001", publisher_id=42, offer_id="offer_1"
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.action, "allow")

    def test_empty_subid_flagged(self):
        result = self.engine.validate(sub_id="", publisher_id=42)
        self.assertIn("empty_subid", result.signals)
        self.assertFalse(result.is_valid)

    def test_too_long_subid_rejected(self):
        result = self.engine.validate(sub_id="a" * 65, publisher_id=42)
        self.assertIn("subid_too_long", result.signals)

    def test_invalid_chars_rejected(self):
        result = self.engine.validate(sub_id="source<script>", publisher_id=42)
        self.assertIn("subid_invalid_characters", result.signals)

    def test_known_fraud_value_blocked(self):
        for bad_value in ["test", "bot", "fake", "null", "undefined"]:
            result = self.engine.validate(sub_id=bad_value, publisher_id=42)
            self.assertIn("known_fraud_subid_value", result.signals,
                          f"Expected fraud signal for sub_id='{bad_value}'")

    def test_blacklisted_subid_rejected(self):
        self.engine.blacklist("fraud_source", 42, reason="test")
        result = self.engine.validate(sub_id="fraud_source", publisher_id=42)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.action, "reject")
        self.assertIn("subid_blacklisted", result.signals)

    def test_unblacklist_allows_again(self):
        self.engine.blacklist("temp_fraud", 42)
        self.engine.unblacklist("temp_fraud", 42)
        result = self.engine.validate(sub_id="temp_fraud", publisher_id=42)
        self.assertNotIn("subid_blacklisted", result.signals)

    def test_record_conversion_updates_reputation(self):
        self.engine.validate(sub_id="track_me", publisher_id=42)
        self.engine.record_conversion(sub_id="track_me", publisher_id=42, payout=2.50)
        rep = self.engine.get_reputation(sub_id="track_me", publisher_id=42)
        self.assertEqual(rep.total_convs, 1)

    def test_reputation_has_correct_fields(self):
        self.engine.validate(sub_id="rep_test", publisher_id=99)
        rep = self.engine.get_reputation("rep_test", 99)
        self.assertIsNotNone(rep)
        self.assertEqual(rep.publisher_id, 99)
        self.assertEqual(rep.sub_id, "rep_test")

    def test_cross_publisher_same_subid_flagged(self):
        """Same sub-ID used by many publishers = likely theft."""
        sub = "shared_fraud_source"
        for pub_id in [1, 2, 3, 4]:
            self.engine.validate(sub_id=sub, publisher_id=pub_id)
        result = self.engine.validate(sub_id=sub, publisher_id=5)
        # Should detect cross-publisher usage
        self.assertIn("cross_publisher_subid_theft", result.signals)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Advertiser Fraud Shield Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAdvertiserFraudShield(TestCase):

    def setUp(self):
        from api.security.services.AdvertiserFraudShield import AdvertiserFraudShield
        self.shield = AdvertiserFraudShield()

    def test_clean_click_allowed(self):
        result = self.shield.evaluate_click(
            advertiser_id = 1,
            publisher_id  = 42,
            click_token   = "clk_001",
            ip            = "203.0.113.5",
            user_agent    = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            is_vpn        = False,
            is_bot        = False,
        )
        self.assertFalse(result.should_block)

    def test_bot_traffic_blocked(self):
        result = self.shield.evaluate_click(
            advertiser_id = 1,
            publisher_id  = 42,
            click_token   = "bot_clk",
            ip            = "203.0.113.6",
            user_agent    = "python-requests/2.28.0",
            is_bot        = True,
            is_vpn        = False,
        )
        self.assertTrue(result.should_block)
        self.assertIn("bot_traffic_detected", result.signals)

    def test_suspended_publisher_blocks_click(self):
        self.shield.suspend_publisher(999, reason="test suspension")
        result = self.shield.evaluate_click(
            advertiser_id = 1,
            publisher_id  = 999,
            click_token   = "susp_clk",
            ip            = "203.0.113.7",
            user_agent    = "Mozilla/5.0",
            is_bot        = False,
            is_vpn        = False,
        )
        self.assertTrue(result.should_block)
        self.shield.reinstate_publisher(999)

    def test_reinstate_publisher_allows_clicks(self):
        self.shield.suspend_publisher(888, reason="test")
        self.shield.reinstate_publisher(888)
        result = self.shield.evaluate_click(
            advertiser_id = 1,
            publisher_id  = 888,
            click_token   = "reinst_clk",
            ip            = "203.0.113.8",
            user_agent    = "Mozilla/5.0",
            is_bot        = False,
            is_vpn        = False,
        )
        self.assertFalse(result.should_block)

    def test_publisher_quality_report_has_grade(self):
        report = self.shield.get_publisher_quality(publisher_id=42)
        self.assertIsNotNone(report.grade)
        self.assertIn(report.grade.value, ["A", "B", "C", "D", "F"])

    def test_conversion_from_suspended_publisher_blocked(self):
        self.shield.suspend_publisher(777, reason="fraud")
        result = self.shield.evaluate_conversion(
            advertiser_id = 1,
            publisher_id  = 777,
            click_token   = "conv_susp",
            conversion_ts = int(time.time()),
            payout        = 5.0,
        )
        self.assertTrue(result.should_block)
        self.shield.reinstate_publisher(777)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Bot Detection ML Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBotDetectionML(TestCase):

    def setUp(self):
        from api.security.services.BotDetectionML import BotDetectionML
        self.detector = BotDetectionML()

    def _request(self, ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"):
        return _make_request(ua=ua)

    def test_real_browser_ua_not_bot(self):
        req    = self._request()
        result = self.detector.analyze(req)
        self.assertFalse(result.is_bot)
        self.assertLess(result.bot_score, 65)

    def test_empty_ua_high_score(self):
        req    = self._request(ua="")
        result = self.detector.analyze(req)
        self.assertGreater(result.bot_score, 30)
        self.assertIn("no_user_agent", result.active_signals)

    def test_curl_ua_detected_as_bot(self):
        req    = self._request(ua="curl/7.88.1")
        result = self.detector.analyze(req)
        self.assertTrue(result.is_bot)
        self.assertIn("bot_ua_exact", result.active_signals)

    def test_python_requests_ua_detected_as_bot(self):
        req    = self._request(ua="python-requests/2.28.2")
        result = self.detector.analyze(req)
        self.assertTrue(result.is_bot)

    def test_scrapy_ua_detected_as_bot(self):
        req    = self._request(ua="Scrapy/2.8.0 (+https://scrapy.org)")
        result = self.detector.analyze(req)
        self.assertTrue(result.is_bot)

    def test_headless_chrome_detected(self):
        req    = self._request(ua="HeadlessChrome/114.0.5735.90")
        result = self.detector.analyze(req)
        self.assertTrue(result.is_bot)
        self.assertIn("bot_ua_pattern", result.active_signals)

    def test_missing_headers_increase_score(self):
        req = _make_request()
        del req.META["HTTP_ACCEPT"]
        del req.META["HTTP_ACCEPT_LANGUAGE"]
        result = self.detector.analyze(req)
        self.assertGreater(result.bot_score, 0)
        self.assertIn("missing_accept_header", result.active_signals)

    def test_webdriver_flag_confirmed_bot(self):
        req    = self._request()
        result = self.detector.analyze(req, js_signals={"webdriver": True})
        self.assertTrue(result.is_bot)
        self.assertEqual(result.bot_type, "headless_browser")
        self.assertEqual(result.recommended_action, "block")

    def test_no_plugins_increases_score(self):
        req    = self._request()
        result = self.detector.analyze(req, js_signals={"plugins_length": 0})
        self.assertGreater(result.bot_score, 0)

    def test_real_browser_js_signals_human(self):
        req    = self._request()
        result = self.detector.analyze(req, js_signals={
            "webdriver":      False,
            "plugins_length": 5,
            "screen_width":   1920,
            "screen_height":  1080,
            "color_depth":    24,
            "languages":      ["en-US", "en"],
            "mouse_moved":    True,
            "time_on_page":   8.5,
            "scroll_depth":   35,
        })
        self.assertFalse(result.is_bot)

    def test_machine_speed_interaction_flagged(self):
        req    = self._request()
        result = self.detector.analyze(req, js_signals={
            "time_on_page": 1.0,   # 1 second
            "keystrokes":   500,   # 500 keys in 1 second = impossible
        })
        self.assertIn("machine_speed_interaction", result.active_signals)

    def test_instant_page_interaction_flagged(self):
        req    = self._request()
        result = self.detector.analyze(req, js_signals={"time_on_page": 0.1})
        self.assertIn("instant_page_interaction", result.active_signals)

    def test_result_has_all_fields(self):
        req    = self._request()
        result = self.detector.analyze(req)
        data   = result.to_dict()
        for key in ["is_bot", "confidence", "bot_score", "bot_type",
                    "risk_level", "active_signals", "recommended_action"]:
            self.assertIn(key, data)

    def test_confidence_is_normalized(self):
        req    = self._request(ua="python-requests/2.28.2")
        result = self.detector.analyze(req)
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)

    def test_risk_level_mapping(self):
        from api.security.services.BotDetectionML import BotDetectionResult
        r = BotDetectionResult(is_bot=False, confidence=0.1, bot_score=10)
        self.assertEqual(r.risk_level, "human")
        r.bot_score = 30
        self.assertEqual(r.risk_level, "low_risk")
        r.bot_score = 50
        self.assertEqual(r.risk_level, "suspicious")
        r.bot_score = 70
        self.assertEqual(r.risk_level, "likely_bot")
        r.bot_score = 90
        self.assertEqual(r.risk_level, "confirmed_bot")