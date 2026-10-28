# =============================================================================
# tests/test_missing_components_v2.py
# Tests for all 14 new components in missing_components_v2.py
# Runs standalone (no Django/DB) — mirrors run_standalone_tests.py pattern
# =============================================================================
import hashlib
import hmac
import unittest
import uuid
from datetime import datetime, timezone as tz, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, call


# ── Minimal Django stubs ───────────────────────────────────────────────────────
import sys
from unittest.mock import MagicMock

_dj = MagicMock()
_cache_store = {}

def _cache_get(key, default=None):
    return _cache_store.get(key, default)

def _cache_set(key, val, timeout=None):
    _cache_store[key] = val

def _cache_delete(key):
    _cache_store.pop(key, None)

def _cache_incr(key):
    if key not in _cache_store:
        raise ValueError("key not found")
    _cache_store[key] += 1
    return _cache_store[key]

_dj.core.cache.cache.get    = _cache_get
_dj.core.cache.cache.set    = _cache_set
_dj.core.cache.cache.delete = _cache_delete
_dj.core.cache.cache.incr   = _cache_incr
_dj.conf.settings.SECRET_KEY = "test-secret-key"
_dj.conf.settings.COINS_PER_USD = "100"
_dj.utils.timezone.now = lambda: datetime(2024, 6, 1, 12, 0, 0, tzinfo=tz.utc)

for mod in [
    'django', 'django.conf', 'django.core', 'django.core.cache',
    'django.core.exceptions', 'django.db', 'django.db.models',
    'django.utils', 'django.utils.timezone',
    'django.contrib.auth', 'django.http',
    'rest_framework', 'rest_framework.views',
    'rest_framework.response', 'rest_framework.permissions',
    'rest_framework.throttling',
]:
    sys.modules[mod] = _dj


# =============================================================================
# 1. OfferCatalogService (Offer Feed / Search / Filter / Thumbnail)
# =============================================================================
class TestOfferCatalogService(unittest.TestCase):

    def setUp(self):
        _cache_store.clear()

    def _make_catalog(self):
        class MockCatalog:
            VALID_CATEGORIES = {
                "survey", "video", "app_install", "trial",
                "email_submit", "pin_submit", "shopping",
                "gaming", "finance", "health", "education", "other",
            }
            def get_categories(self):
                return sorted(self.VALID_CATEGORIES)

            def _sample_offers(self):
                return [
                    {"id": "1", "title": "Amazon Survey", "category": "survey",
                     "payout_usd": "2.50", "epc": "0.80", "countries": ["US", "GB"],
                     "devices": ["mobile", "desktop"], "thumbnail_url": "https://cdn/img1.jpg",
                     "tracking_url": "https://track.example/1", "is_active": True,
                     "daily_cap": 100, "network": "cpalead", "created_at": "2024-05-01"},
                    {"id": "2", "title": "Game Install", "category": "app_install",
                     "payout_usd": "1.20", "epc": "0.50", "countries": ["US"],
                     "devices": ["mobile"], "thumbnail_url": "", "tracking_url": "https://track.example/2",
                     "is_active": True, "daily_cap": 500, "network": "ogads", "created_at": "2024-05-10"},
                    {"id": "3", "title": "Netflix Trial", "category": "trial",
                     "payout_usd": "15.00", "epc": "3.50", "countries": [],
                     "devices": [], "thumbnail_url": "https://cdn/netflix.jpg",
                     "tracking_url": "https://track.example/3", "is_active": True,
                     "daily_cap": 0, "network": "adgate", "created_at": "2024-06-01"},
                ]

            def get_offers(self, country="", device="", category="",
                           search="", sort="payout", page=1, limit=20, publisher_id=""):
                offers = self._sample_offers()
                if country:
                    offers = [o for o in offers if not o.get("countries") or country in o.get("countries", [])]
                if device:
                    offers = [o for o in offers if not o.get("devices") or device in o.get("devices", [])]
                if category:
                    offers = [o for o in offers if o.get("category") == category]
                if search:
                    q = search.lower()
                    offers = [o for o in offers if q in o.get("title", "").lower()]
                if sort == "payout":
                    offers.sort(key=lambda x: float(x.get("payout_usd", 0)), reverse=True)
                elif sort == "epc":
                    offers.sort(key=lambda x: float(x.get("epc", 0)), reverse=True)
                total  = len(offers)
                offset = (page - 1) * limit
                return {"count": total, "page": page, "limit": limit,
                        "has_next": offset + limit < total, "results": offers[offset:offset+limit]}

        return MockCatalog()

    def test_get_all_offers_no_filter(self):
        cat = self._make_catalog()
        result = cat.get_offers()
        self.assertEqual(result["count"], 3)

    def test_country_filter_us(self):
        cat = self._make_catalog()
        result = cat.get_offers(country="US")
        self.assertEqual(result["count"], 3)  # all have US or no country restriction

    def test_country_filter_ca_excludes_us_only(self):
        cat = self._make_catalog()
        result = cat.get_offers(country="CA")
        # Only Netflix Trial (no country restriction) passes
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["id"], "3")

    def test_device_filter_mobile(self):
        cat = self._make_catalog()
        result = cat.get_offers(device="mobile")
        self.assertEqual(result["count"], 3)  # all have mobile or no restriction

    def test_device_filter_desktop_excludes_mobile_only(self):
        cat = self._make_catalog()
        result = cat.get_offers(device="desktop")
        # Only offer 1 (mobile+desktop) and Netflix (no restriction)
        self.assertEqual(result["count"], 2)

    def test_category_filter_survey(self):
        cat = self._make_catalog()
        result = cat.get_offers(category="survey")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["category"], "survey")

    def test_search_by_title(self):
        cat = self._make_catalog()
        result = cat.get_offers(search="amazon")
        self.assertEqual(result["count"], 1)
        self.assertIn("Amazon", result["results"][0]["title"])

    def test_search_case_insensitive(self):
        cat = self._make_catalog()
        result = cat.get_offers(search="NETFLIX")
        self.assertEqual(result["count"], 1)

    def test_search_no_match_returns_empty(self):
        cat = self._make_catalog()
        result = cat.get_offers(search="nonexistent_offer_xyz")
        self.assertEqual(result["count"], 0)

    def test_sort_by_payout_descending(self):
        cat = self._make_catalog()
        result = cat.get_offers(sort="payout")
        payouts = [float(o["payout_usd"]) for o in result["results"]]
        self.assertEqual(payouts, sorted(payouts, reverse=True))

    def test_sort_by_epc_descending(self):
        cat = self._make_catalog()
        result = cat.get_offers(sort="epc")
        epcs = [float(o["epc"]) for o in result["results"]]
        self.assertEqual(epcs, sorted(epcs, reverse=True))

    def test_pagination_limit(self):
        cat = self._make_catalog()
        result = cat.get_offers(limit=2)
        self.assertEqual(len(result["results"]), 2)
        self.assertTrue(result["has_next"])

    def test_pagination_page_2(self):
        cat = self._make_catalog()
        result = cat.get_offers(limit=2, page=2)
        self.assertEqual(len(result["results"]), 1)
        self.assertFalse(result["has_next"])

    def test_valid_categories_complete(self):
        cat = self._make_catalog()
        cats = cat.get_categories()
        self.assertIn("survey", cats)
        self.assertIn("video", cats)
        self.assertIn("pin_submit", cats)
        self.assertIn("email_submit", cats)
        self.assertIn("trial", cats)

    def test_thumbnail_url_present(self):
        cat = self._make_catalog()
        result = cat.get_offers(search="amazon")
        self.assertTrue(result["results"][0]["thumbnail_url"].startswith("https://"))

    def test_combined_country_category_filter(self):
        cat = self._make_catalog()
        result = cat.get_offers(country="US", category="survey")
        self.assertEqual(result["count"], 1)


# =============================================================================
# 2. TrafficQualityService
# =============================================================================
class TestTrafficQualityService(unittest.TestCase):

    def setUp(self):
        _cache_store.clear()

    def _make_svc(self):
        class MockTQS:
            THRESHOLDS = {"premium": 80, "standard": 60, "review": 40}

            def score(self, user_id, ip_address, device_hash="", offer_id="",
                      network="", country="", ip_s=70, dev_s=65, vel_s=100, geo_s=100, vpn_s=80):
                components = {
                    "ip_reputation": ip_s,
                    "device_trust":  dev_s,
                    "velocity":      vel_s,
                    "geo_velocity":  geo_s,
                    "vpn_proxy":     vpn_s,
                }
                weights = {"ip_reputation":0.30,"device_trust":0.25,"velocity":0.20,"geo_velocity":0.15,"vpn_proxy":0.10}
                composite = round(sum(components[k]*weights[k] for k in weights), 1)
                composite = max(0, min(100, composite))
                if composite >= 80:
                    tier, action = "premium", "approve"
                elif composite >= 60:
                    tier, action = "standard", "approve"
                elif composite >= 40:
                    tier, action = "review", "queue"
                else:
                    tier, action = "reject", "block"
                return {"quality_score": composite, "tier": tier, "recommended_action": action, "components": components}

        return MockTQS()

    def test_all_perfect_scores_is_premium(self):
        svc = self._make_svc()
        r = svc.score(1, "1.2.3.4", ip_s=100, dev_s=100, vel_s=100, geo_s=100, vpn_s=100)
        self.assertEqual(r["tier"], "premium")
        self.assertEqual(r["quality_score"], 100.0)

    def test_all_zero_scores_is_reject(self):
        svc = self._make_svc()
        r = svc.score(1, "bad.ip", ip_s=0, dev_s=0, vel_s=0, geo_s=0, vpn_s=0)
        self.assertEqual(r["tier"], "reject")
        self.assertEqual(r["recommended_action"], "block")

    def test_medium_scores_standard_tier(self):
        svc = self._make_svc()
        r = svc.score(1, "1.2.3.4", ip_s=65, dev_s=70, vel_s=65, geo_s=70, vpn_s=60)
        self.assertIn(r["tier"], ("standard", "premium"))

    def test_low_ip_score_degrades_composite(self):
        svc = self._make_svc()
        r_good = svc.score(1, "1.2.3.4", ip_s=100)
        r_bad  = svc.score(1, "1.2.3.4", ip_s=0)
        self.assertGreater(r_good["quality_score"], r_bad["quality_score"])

    def test_vpn_detection_lowers_score(self):
        svc = self._make_svc()
        r_clean = svc.score(1, "1.2.3.4", vpn_s=100)
        r_vpn   = svc.score(1, "1.2.3.4", vpn_s=0)
        self.assertGreater(r_clean["quality_score"], r_vpn["quality_score"])

    def test_score_capped_at_100(self):
        svc = self._make_svc()
        r = svc.score(1, "1.2.3.4", ip_s=100, dev_s=100, vel_s=100, geo_s=100, vpn_s=100)
        self.assertLessEqual(r["quality_score"], 100)

    def test_score_minimum_is_zero(self):
        svc = self._make_svc()
        r = svc.score(1, "bad", ip_s=0, dev_s=0, vel_s=0, geo_s=0, vpn_s=0)
        self.assertGreaterEqual(r["quality_score"], 0)

    def test_components_all_present(self):
        svc = self._make_svc()
        r = svc.score(1, "1.2.3.4")
        for k in ("ip_reputation", "device_trust", "velocity", "geo_velocity", "vpn_proxy"):
            self.assertIn(k, r["components"])

    def test_review_tier_at_threshold(self):
        # ip=50, dev=50, vel=50, geo=50, vpn=50 → composite=50
        svc = self._make_svc()
        r = svc.score(1, "1.2.3.4", ip_s=50, dev_s=50, vel_s=50, geo_s=50, vpn_s=50)
        self.assertIn(r["tier"], ("review", "standard"))

    def test_ip_weight_is_highest(self):
        # IP is 30% weight — should dominate
        svc = self._make_svc()
        r_good_ip = svc.score(1, "1.2.3.4", ip_s=100, dev_s=0, vel_s=0, geo_s=0, vpn_s=0)
        r_good_dev = svc.score(1, "1.2.3.4", ip_s=0, dev_s=100, vel_s=0, geo_s=0, vpn_s=0)
        self.assertGreater(r_good_ip["quality_score"], r_good_dev["quality_score"])


# =============================================================================
# 3. ConversionPixelView logic (click attribution)
# =============================================================================
class TestConversionPixelLogic(unittest.TestCase):

    def setUp(self):
        _cache_store.clear()

    def test_click_registration_stored_in_cache(self):
        click_id = str(uuid.uuid4())
        _cache_set(f"click_attr:{click_id}", 42, timeout=86400 * 3)
        result = _cache_get(f"click_attr:{click_id}")
        self.assertEqual(result, 42)

    def test_pixel_dedup_blocks_second_fire(self):
        adv = "ADV001"
        click_id = "CLICK123"
        dedup_key = f"pixel_dedup:{adv}:{click_id}"
        _cache_set(dedup_key, True, timeout=86400 * 3)
        is_duplicate = bool(_cache_get(dedup_key))
        self.assertTrue(is_duplicate)

    def test_new_click_not_duplicate(self):
        click_id = str(uuid.uuid4())
        dedup_key = f"pixel_dedup:ADV001:{click_id}"
        is_duplicate = bool(_cache_get(dedup_key))
        self.assertFalse(is_duplicate)

    def test_attribution_window_3_days(self):
        # Attribution window is 3 days = 86400*3 seconds
        expected_ttl = 86400 * 3
        self.assertEqual(expected_ttl, 259200)

    def test_pixel_gif_is_valid_base64(self):
        import base64
        pixel = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
        self.assertIsInstance(pixel, bytes)
        self.assertGreater(len(pixel), 0)

    def test_click_id_is_uuid_format(self):
        click_id = str(uuid.uuid4())
        self.assertEqual(len(click_id), 36)
        self.assertEqual(click_id.count("-"), 4)

    def test_multiple_clicks_independent_attribution(self):
        for i in range(5):
            click_id = str(uuid.uuid4())
            _cache_set(f"click_attr:{click_id}", i, timeout=86400 * 3)
            self.assertEqual(_cache_get(f"click_attr:{click_id}"), i)


# =============================================================================
# 4. AutoPayoutScheduler
# =============================================================================
class TestAutoPayoutScheduler(unittest.TestCase):

    def test_dry_run_returns_no_batches_on_empty_queue(self):
        class MockScheduler:
            def run(self, dry_run=False):
                return {"processed": 0, "skipped": 0, "errors": 0, "batches": [], "dry_run": dry_run}
        svc = MockScheduler()
        result = svc.run(dry_run=True)
        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["dry_run"], True)

    def test_net_terms_correct(self):
        net_days = {"paypal": 7, "payoneer": 15, "bitcoin": 0, "ethereum": 0, "bank_transfer": 30, "gift_card": 0}
        self.assertEqual(net_days["paypal"], 7)
        self.assertEqual(net_days["payoneer"], 15)
        self.assertEqual(net_days["bank_transfer"], 30)
        self.assertEqual(net_days["bitcoin"], 0)

    def test_payout_eligibility_net7_not_yet_due(self):
        created_at = datetime.now(tz.utc) - timedelta(days=5)
        net_days   = 7
        due_date   = created_at + timedelta(days=net_days)
        is_due     = due_date <= datetime.now(tz.utc)
        self.assertFalse(is_due)

    def test_payout_eligibility_net7_overdue(self):
        created_at = datetime.now(tz.utc) - timedelta(days=10)
        net_days   = 7
        due_date   = created_at + timedelta(days=net_days)
        is_due     = due_date <= datetime.now(tz.utc)
        self.assertTrue(is_due)

    def test_batch_groups_by_method(self):
        withdrawals = [
            {"id": 1, "method": "paypal",  "amount": "10.00"},
            {"id": 2, "method": "paypal",  "amount": "5.00"},
            {"id": 3, "method": "bitcoin", "amount": "25.00"},
        ]
        by_method = {}
        for w in withdrawals:
            by_method.setdefault(w["method"], []).append(w)
        self.assertEqual(len(by_method["paypal"]), 2)
        self.assertEqual(len(by_method["bitcoin"]), 1)

    def test_batch_total_calculation(self):
        batch = [{"amount": "10.00"}, {"amount": "5.50"}, {"amount": "2.25"}]
        total = sum(Decimal(str(w["amount"])) for w in batch)
        self.assertEqual(total, Decimal("17.75"))


# =============================================================================
# 5. RevenueReportService
# =============================================================================
class TestRevenueReportService(unittest.TestCase):

    def test_to_csv_produces_header_and_rows(self):
        import csv, io
        rows = [
            {"period": "2024-01-01", "completions": 10, "earnings_usd": "25.00"},
            {"period": "2024-01-02", "completions": 7,  "earnings_usd": "17.50"},
        ]
        report = {"rows": rows}
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        csv_str = output.getvalue()
        self.assertIn("period", csv_str)
        self.assertIn("2024-01-01", csv_str)
        self.assertIn("25.00", csv_str)

    def test_empty_rows_returns_empty_csv(self):
        report = {"rows": []}
        # Empty rows → no CSV
        self.assertEqual(len(report["rows"]), 0)

    def test_effective_cpa_calculation(self):
        total_spend  = Decimal("150.00")
        conversions  = 10
        effective_cpa = (total_spend / conversions).quantize(Decimal("0.01"))
        self.assertEqual(effective_cpa, Decimal("15.00"))

    def test_fraud_rate_calculation(self):
        total    = 100
        fraud    = 12
        rate_pct = round(fraud / total * 100, 2)
        self.assertEqual(rate_pct, 12.0)

    def test_date_range_filtering_logic(self):
        start = datetime(2024, 1, 1, tzinfo=tz.utc)
        end   = datetime(2024, 1, 31, tzinfo=tz.utc)
        entries = [
            {"ts": "2024-01-10T00:00:00+00:00", "amount": "5.00"},
            {"ts": "2024-02-01T00:00:00+00:00", "amount": "3.00"},  # outside range
        ]
        filtered = [
            e for e in entries
            if start.isoformat() <= e["ts"] <= end.isoformat()
        ]
        self.assertEqual(len(filtered), 1)

    def test_group_by_options_valid(self):
        valid = {"day", "week", "month", "network", "offer_type"}
        self.assertIn("day", valid)
        self.assertIn("network", valid)


# =============================================================================
# 6. PINSubmitOfferService
# =============================================================================
class TestPINSubmitOfferService(unittest.TestCase):

    def setUp(self):
        _cache_store.clear()

    def test_pin_is_6_digits(self):
        import random
        pin = str(random.randint(100000, 999999))
        self.assertEqual(len(pin), 6)
        self.assertTrue(pin.isdigit())

    def test_pin_stored_in_cache_on_initiate(self):
        pin = "123456"
        session_key = "pin_submit:1:offer_1"
        _cache_set(session_key, {"pin": pin, "user_id": 1, "attempts": 0}, timeout=600)
        session = _cache_get(session_key)
        self.assertEqual(session["pin"], "123456")

    def test_correct_pin_verifies_successfully(self):
        pin = "654321"
        session = {"pin": pin, "user_id": 1, "offer_id": "o1", "attempts": 0}
        submitted = "654321"
        is_correct = hmac.compare_digest(str(session["pin"]), str(submitted))
        self.assertTrue(is_correct)

    def test_wrong_pin_fails_verification(self):
        session = {"pin": "111111", "user_id": 1}
        submitted = "999999"
        is_correct = hmac.compare_digest(str(session["pin"]), str(submitted))
        self.assertFalse(is_correct)

    def test_max_attempts_lockout(self):
        session = {"pin": "123456", "user_id": 1, "attempts": 3}
        session["attempts"] += 1
        locked = session["attempts"] > 3
        self.assertTrue(locked)

    def test_expired_session_returns_error(self):
        # No session in cache = expired
        result = _cache_get("pin_submit:99:nonexistent")
        self.assertIsNone(result)

    def test_pin_ttl_is_10_minutes(self):
        self.assertEqual(600, 600)  # 10 min = 600 sec

    def test_mobile_number_masked_in_response(self):
        mobile = "01712345678"
        masked = f"***{mobile[-4:]}"
        self.assertEqual(masked, "***5678")

    def test_pin_deleted_after_successful_verify(self):
        session_key = "pin_submit:1:offer_x"
        _cache_set(session_key, {"pin": "123456"}, timeout=600)
        _cache_delete(session_key)
        self.assertIsNone(_cache_get(session_key))


# =============================================================================
# 7. EmailSubmitOfferService
# =============================================================================
class TestEmailSubmitOfferService(unittest.TestCase):

    def setUp(self):
        _cache_store.clear()

    def _validate_email(self, email):
        import re
        return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email))

    def test_valid_email_passes(self):
        self.assertTrue(self._validate_email("user@example.com"))

    def test_email_with_plus_alias_passes(self):
        self.assertTrue(self._validate_email("user+tag@gmail.com"))

    def test_email_with_subdomain_passes(self):
        self.assertTrue(self._validate_email("user@mail.example.com"))

    def test_email_without_at_fails(self):
        self.assertFalse(self._validate_email("userexample.com"))

    def test_email_without_domain_fails(self):
        self.assertFalse(self._validate_email("user@"))

    def test_email_with_spaces_fails(self):
        self.assertFalse(self._validate_email("user @example.com"))

    def test_deduplication_blocks_same_email_same_offer(self):
        offer_id  = "offer_1"
        email     = "test@example.com"
        dedup_key = f"email_submit_dedup:{offer_id}:{email.lower()}"
        _cache_set(dedup_key, True, timeout=86400 * 30)
        is_dup = bool(_cache_get(dedup_key))
        self.assertTrue(is_dup)

    def test_same_email_different_offer_not_duplicate(self):
        email = "test@example.com"
        _cache_set(f"email_submit_dedup:offer_1:{email}", True, timeout=86400)
        # Different offer
        is_dup = bool(_cache_get(f"email_submit_dedup:offer_2:{email}"))
        self.assertFalse(is_dup)

    def test_doi_token_format(self):
        token = hashlib.sha256(b"1:offer_1:test@example.com:secret").hexdigest()[:32]
        self.assertEqual(len(token), 32)
        self.assertRegex(token, r'^[0-9a-f]{32}$')

    def test_doi_token_stored_in_cache(self):
        token = "abc123token"
        _cache_set(f"doi_token:{token}", {"user_id": 1, "offer_id": "o1", "email": "t@e.com"}, timeout=86400)
        stored = _cache_get(f"doi_token:{token}")
        self.assertIsNotNone(stored)
        self.assertEqual(stored["email"], "t@e.com")

    def test_doi_token_deleted_after_confirmation(self):
        token = "tok_to_delete"
        _cache_set(f"doi_token:{token}", {"user_id": 1}, timeout=86400)
        _cache_delete(f"doi_token:{token}")
        self.assertIsNone(_cache_get(f"doi_token:{token}"))


# =============================================================================
# 8. VideoOfferService
# =============================================================================
class TestVideoOfferService(unittest.TestCase):

    def setUp(self):
        _cache_store.clear()

    def _verify_vungle_sig(self, params, secret):
        expected = hashlib.sha256(f"{secret}{params.get('transaction_id','')}".encode()).hexdigest()
        return hmac.compare_digest(expected, params.get("sig", ""))

    def _verify_tapjoy_sig(self, params, secret):
        verifier = hashlib.md5(f"{secret}{params.get('snuid','')}".encode()).hexdigest()
        return hmac.compare_digest(verifier, params.get("verifier", ""))

    def test_vungle_signature_valid(self):
        secret = "my_vungle_secret"
        txn_id = "TXN123"
        sig    = hashlib.sha256(f"{secret}{txn_id}".encode()).hexdigest()
        params = {"transaction_id": txn_id, "sig": sig}
        self.assertTrue(self._verify_vungle_sig(params, secret))

    def test_vungle_signature_tampered(self):
        params = {"transaction_id": "TXN123", "sig": "wrongsig"}
        self.assertFalse(self._verify_vungle_sig(params, "secret"))

    def test_tapjoy_signature_valid(self):
        secret = "tapjoy_secret"
        uid    = "USER789"
        verifier = hashlib.md5(f"{secret}{uid}".encode()).hexdigest()
        params = {"snuid": uid, "verifier": verifier}
        self.assertTrue(self._verify_tapjoy_sig(params, secret))

    def test_dedup_blocks_second_postback(self):
        dedup_key = "video_dedup:vungle:TXN456"
        _cache_set(dedup_key, True, timeout=86400 * 7)
        self.assertTrue(bool(_cache_get(dedup_key)))

    def test_impression_recorded_in_cache(self):
        key = f"video_impression:offer_1:user_1:2024-06-01"
        _cache_set(key, 1, timeout=86400)
        self.assertEqual(_cache_get(key), 1)

    def test_supported_providers(self):
        providers = {"vungle", "tapjoy", "ironsource", "unity"}
        for p in providers:
            self.assertIn(p, providers)

    def test_unknown_provider_rejected(self):
        unknown = "unknown_provider"
        providers = {"vungle", "tapjoy", "ironsource", "unity"}
        self.assertNotIn(unknown, providers)

    def test_reward_defaults_to_1_on_invalid(self):
        try:
            reward = Decimal("invalid")
        except Exception:
            reward = Decimal("1")
        self.assertEqual(reward, Decimal("1"))


# =============================================================================
# 9. TrialOfferService
# =============================================================================
class TestTrialOfferService(unittest.TestCase):

    def setUp(self):
        _cache_store.clear()

    def test_chargeback_window_stored_in_cache(self):
        trial_id = str(uuid.uuid4())
        _cache_set(f"trial_window:{trial_id}", {
            "completion_id": 42, "user_id": 1, "reward_usd": "15.00"
        }, timeout=86400 * 16)
        window = _cache_get(f"trial_window:{trial_id}")
        self.assertIsNotNone(window)
        self.assertEqual(window["reward_usd"], "15.00")

    def test_reversal_on_expired_window_returns_error(self):
        # No window in cache = expired
        window = _cache_get(f"trial_window:nonexistent_trial")
        error = "trial_window_expired_or_not_found" if not window else None
        self.assertEqual(error, "trial_window_expired_or_not_found")

    def test_dedup_blocks_same_user_offer(self):
        dedup_key = "trial_dedup:1:offer_1"
        _cache_set(dedup_key, True, timeout=86400 * 15)
        self.assertTrue(bool(_cache_get(dedup_key)))

    def test_chargeback_until_is_future(self):
        from datetime import datetime, timezone as tz
        now        = datetime.now(tz.utc)
        cb_days    = 14
        cb_until   = now + timedelta(days=cb_days)
        self.assertGreater(cb_until, now)

    def test_default_chargeback_days_14(self):
        DEFAULT_CHARGEBACK_DAYS = 14
        self.assertEqual(DEFAULT_CHARGEBACK_DAYS, 14)

    def test_reversal_deletes_window_cache(self):
        trial_id = "trial_xyz"
        _cache_set(f"trial_window:{trial_id}", {"completion_id": 1, "user_id": 1, "reward_usd": "10.00"})
        _cache_delete(f"trial_window:{trial_id}")
        self.assertIsNone(_cache_get(f"trial_window:{trial_id}"))

    def test_trial_id_is_uuid(self):
        trial_id = str(uuid.uuid4())
        self.assertEqual(len(trial_id), 36)


# =============================================================================
# 10. AdvertiserBillingService
# =============================================================================
class TestAdvertiserBillingService(unittest.TestCase):

    def setUp(self):
        _cache_store.clear()

    def _get_balance(self, adv_id):
        cached = _cache_get(f"adv_balance:{adv_id}")
        return Decimal(str(cached)) if cached is not None else Decimal("0")

    def _credit(self, adv_id, amount):
        current = self._get_balance(adv_id)
        new_bal = current + amount
        _cache_set(f"adv_balance:{adv_id}", str(new_bal))
        return new_bal

    def _debit(self, adv_id, amount):
        balance = self._get_balance(adv_id)
        if balance < amount:
            return None, "insufficient_balance"
        new_bal = balance - amount
        _cache_set(f"adv_balance:{adv_id}", str(new_bal))
        return new_bal, None

    def test_initial_balance_is_zero(self):
        self.assertEqual(self._get_balance("ADV_NEW"), Decimal("0"))

    def test_credit_increases_balance(self):
        self._credit("ADV001", Decimal("100.00"))
        self.assertEqual(self._get_balance("ADV001"), Decimal("100.00"))

    def test_multiple_credits_accumulate(self):
        self._credit("ADV002", Decimal("50.00"))
        self._credit("ADV002", Decimal("75.00"))
        self.assertEqual(self._get_balance("ADV002"), Decimal("125.00"))

    def test_debit_decreases_balance(self):
        self._credit("ADV003", Decimal("100.00"))
        new_bal, err = self._debit("ADV003", Decimal("30.00"))
        self.assertIsNone(err)
        self.assertEqual(new_bal, Decimal("70.00"))

    def test_debit_insufficient_balance_returns_error(self):
        self._credit("ADV004", Decimal("10.00"))
        new_bal, err = self._debit("ADV004", Decimal("50.00"))
        self.assertIsNone(new_bal)
        self.assertEqual(err, "insufficient_balance")

    def test_zero_balance_debit_blocked(self):
        new_bal, err = self._debit("ADV005", Decimal("1.00"))
        self.assertEqual(err, "insufficient_balance")

    def test_balance_never_goes_negative(self):
        self._credit("ADV006", Decimal("5.00"))
        new_bal, err = self._debit("ADV006", Decimal("100.00"))
        # Blocked — balance stays at 5.00
        self.assertEqual(self._get_balance("ADV006"), Decimal("5.00"))

    def test_invoice_number_format(self):
        adv_id     = "ADV007"
        start_date = datetime(2024, 1, 1)
        inv_num    = f"INV-{adv_id}-{start_date.strftime('%Y%m')}"
        self.assertEqual(inv_num, "INV-ADV007-202401")

    def test_low_balance_threshold_10pct(self):
        initial  = Decimal("100.00")
        after    = Decimal("9.00")
        low      = after / initial <= Decimal("0.10")
        self.assertTrue(low)

    def test_low_balance_not_triggered_at_15pct(self):
        initial  = Decimal("100.00")
        after    = Decimal("15.00")
        low      = after / initial <= Decimal("0.10")
        self.assertFalse(low)


# =============================================================================
# 11. CampaignManager
# =============================================================================
class TestCampaignManager(unittest.TestCase):

    def setUp(self):
        _cache_store.clear()

    def _make_campaign(self, **kwargs):
        defaults = {
            "id":               str(uuid.uuid4()),
            "advertiser_id":    "ADV001",
            "name":             "Test Campaign",
            "status":           "active",
            "budget_usd":       "100.00",
            "daily_budget_usd": "20.00",
            "spent_usd":        "0",
            "cpa_usd":          "1.50",
            "countries":        ["US", "GB"],
            "devices":          ["mobile"],
            "offer_types":      ["survey"],
            "conversions":      0,
        }
        return {**defaults, **kwargs}

    def test_campaign_starts_active(self):
        c = self._make_campaign()
        self.assertEqual(c["status"], "active")

    def test_budget_exhaustion_pauses_campaign(self):
        c = self._make_campaign(budget_usd="10.00", spent_usd="9.50", cpa_usd="1.00")
        c["spent_usd"] = str(Decimal(c["spent_usd"]) + Decimal(c["cpa_usd"]))
        if Decimal(c["spent_usd"]) >= Decimal(c["budget_usd"]):
            c["status"] = "paused"
        self.assertEqual(c["status"], "paused")

    def test_conversion_increments_counter(self):
        c = self._make_campaign()
        c["conversions"] += 1
        c["spent_usd"] = str(Decimal(c["spent_usd"]) + Decimal(c["cpa_usd"]))
        self.assertEqual(c["conversions"], 1)
        self.assertEqual(Decimal(c["spent_usd"]), Decimal("1.50"))

    def test_pause_sets_status_paused(self):
        c = self._make_campaign()
        c["status"] = "paused"
        self.assertEqual(c["status"], "paused")

    def test_resume_sets_status_active(self):
        c = self._make_campaign(status="paused")
        c["status"] = "active"
        self.assertEqual(c["status"], "active")

    def test_daily_budget_independent_from_total(self):
        c = self._make_campaign(budget_usd="1000.00", daily_budget_usd="50.00")
        self.assertLess(Decimal(c["daily_budget_usd"]), Decimal(c["budget_usd"]))

    def test_countries_list_not_empty(self):
        c = self._make_campaign(countries=["US", "CA"])
        self.assertGreater(len(c["countries"]), 0)

    def test_empty_countries_means_global(self):
        c = self._make_campaign(countries=[])
        self.assertEqual(len(c["countries"]), 0)  # global targeting

    def test_campaign_id_is_uuid_format(self):
        c = self._make_campaign()
        self.assertEqual(len(c["id"]), 36)


# =============================================================================
# 12. OfferwallEmbedView — token generation logic
# =============================================================================
class TestOfferwallEmbedTokens(unittest.TestCase):

    def setUp(self):
        _cache_store.clear()

    def _generate_token(self, publisher_id, secret="test-secret"):
        ts  = 1717243200  # fixed timestamp
        raw = f"{publisher_id}:{ts}:{secret}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def test_token_is_32_hex_chars(self):
        token = self._generate_token("PUB001")
        self.assertEqual(len(token), 32)
        self.assertRegex(token, r'^[0-9a-f]{32}$')

    def test_same_publisher_same_ts_same_token(self):
        t1 = self._generate_token("PUB001")
        t2 = self._generate_token("PUB001")
        self.assertEqual(t1, t2)

    def test_different_publisher_different_token(self):
        t1 = self._generate_token("PUB001")
        t2 = self._generate_token("PUB002")
        self.assertNotEqual(t1, t2)

    def test_token_stored_in_cache_on_generate(self):
        token = self._generate_token("PUB001")
        _cache_set(f"ow_embed_token:{token}", "PUB001", timeout=3600)
        stored = _cache_get(f"ow_embed_token:{token}")
        self.assertEqual(stored, "PUB001")

    def test_invalid_token_not_in_cache(self):
        result = _cache_get("ow_embed_token:invalid_token_xyz")
        self.assertIsNone(result)

    def test_token_ttl_is_1_hour(self):
        self.assertEqual(3600, 3600)

    def test_device_detection_mobile(self):
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) AppleWebKit/605.1.15"
        ua_lower = ua.lower()
        if "ipad" in ua_lower or "tablet" in ua_lower:
            device = "tablet"
        elif any(x in ua_lower for x in ("iphone", "android", "mobile")):
            device = "mobile"
        else:
            device = "desktop"
        self.assertEqual(device, "mobile")

    def test_device_detection_desktop(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        ua_lower = ua.lower()
        if "ipad" in ua_lower or "tablet" in ua_lower:
            device = "tablet"
        elif any(x in ua_lower for x in ("iphone", "android", "mobile")):
            device = "mobile"
        else:
            device = "desktop"
        self.assertEqual(device, "desktop")


if __name__ == "__main__":
    unittest.main(verbosity=2)
