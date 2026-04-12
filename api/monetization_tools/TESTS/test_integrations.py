"""TESTS/test_integrations.py - Third-party integration tests."""
from decimal import Decimal
from ..INTEGRATIONS.facebook_pixel import FacebookPixelIntegration
from ..INTEGRATIONS.google_analytics import GoogleAnalyticsIntegration
from ..INTEGRATIONS.branch_integration import BranchIntegration
from ..INTEGRATIONS.segment_integration import SegmentIntegration


class TestFacebookPixelIntegration:
    def test_send_event(self):
        fb     = FacebookPixelIntegration("123456", "token_abc")
        result = fb.send_event("Purchase", {"email": "test@test.com"})
        assert result["status"] == "sent"

    def test_purchase(self):
        fb     = FacebookPixelIntegration("123456", "token")
        result = fb.purchase({"email": "t@t.com"}, Decimal("99.00"), "BDT")
        assert result["event"] == "Purchase"


class TestGoogleAnalyticsIntegration:
    def test_earn_virtual_currency(self):
        ga     = GoogleAnalyticsIntegration("G-ABC123", "secret")
        result = ga.earn_virtual_currency("client_001", 100.0)
        assert result["status"] == "sent"

    def test_purchase(self):
        ga     = GoogleAnalyticsIntegration("G-TEST", "secret")
        result = ga.purchase("client_002", 199.0, "BDT")
        assert result["event"] == "purchase"


class TestBranchIntegration:
    def test_referral_link_contains_user(self):
        branch = BranchIntegration("test_branch_key")
        link   = branch.generate_referral_link("user_123", "referral")
        assert "user_123" in link

    def test_log_event_ok(self):
        branch = BranchIntegration("key")
        result = branch.log_event("user1", "COMPLETE_REGISTRATION")
        assert result["status"] == "ok"


class TestSegmentIntegration:
    def test_track(self):
        seg    = SegmentIntegration("write_key_test")
        result = seg.track("user1", "OfferCompleted", {"offer_id": 1})
        assert result["status"] == "ok"

    def test_identify(self):
        seg    = SegmentIntegration("write_key_test")
        result = seg.identify("user1", {"name": "Test User", "coins": 500})
        assert result["status"] == "ok"
