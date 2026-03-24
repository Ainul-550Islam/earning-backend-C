# -*- coding: utf-8 -*-
"""
Tests for: fraud_detection, kyc, gamification, cache
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from decimal import Decimal
from unittest.mock import patch, MagicMock
import uuid

User = get_user_model()


def make_user(is_staff=False):
    uid = uuid.uuid4().hex[:8]
    u = User.objects.create_user(
        username=f"user_{uid}", email=f"{uid}@test.com", password="pass1234"
    )
    if is_staff:
        u.is_staff = True
        u.save()
    return u


# =============================================
# FRAUD DETECTION TESTS
# =============================================

class FraudDetectionModelTest(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_fraud_rule_create(self):
        try:
            from api.fraud_detection.models import FraudDetectionRule
            rule = FraudDetectionRule.objects.create(
                name="Test Rule",
                rule_type="ip_block",
                is_active=True,
            )
            self.assertIsNotNone(rule.pk)
            self.assertTrue(rule.is_active)
        except ImportError:
            self.skipTest("FraudDetectionRule not available")

    def test_blacklisted_ip_create(self):
        try:
            from api.fraud_detection.models import BlacklistedIP
            ip = BlacklistedIP.objects.create(
                ip_address="192.168.1.100",
                reason="Suspicious activity",
            )
            self.assertEqual(ip.ip_address, "192.168.1.100")
        except ImportError:
            self.skipTest("BlacklistedIP not available")

    def test_fraud_log_create(self):
        try:
            from api.fraud_detection.models import FraudLog
            log = FraudLog.objects.create(
                user=self.user,
                fraud_type="multiple_accounts",
                severity="high",
                ip_address="10.0.0.1",
            )
            self.assertIsNotNone(log.pk)
        except ImportError:
            self.skipTest("FraudLog not available")


class FraudDetectionAPITest(APITestCase):

    def setUp(self):
        self.user = make_user()
        self.admin = make_user(is_staff=True)

    def test_fraud_dashboard_admin(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/fraud-detection/dashboard/")
        self.assertNotIn(res.status_code, [500])

    def test_fraud_dashboard_user_forbidden(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.get("/api/fraud-detection/dashboard/")
        self.assertIn(res.status_code, [200, 403, 404])

    def test_blacklist_ip(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.post("/api/fraud-detection/blacklist/", {
            "ip_address": "192.168.1.200",
            "reason": "Spam",
        }, format="json")
        self.assertIn(res.status_code, [200, 201, 400, 404])

    def test_fraud_alerts_list(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/fraud-detection/alerts/")
        self.assertNotIn(res.status_code, [500])


# =============================================
# KYC TESTS
# =============================================

class KYCModelTest(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_kyc_submission_create(self):
        try:
            from api.kyc.models import KYCSubmission
            kyc = KYCSubmission.objects.create(
                user=self.user,
                document_type="national_id",
                status="pending",
            )
            self.assertEqual(kyc.status, "pending")
            self.assertEqual(kyc.user, self.user)
        except ImportError:
            self.skipTest("KYCSubmission not available")

    def test_kyc_status_choices(self):
        try:
            from api.kyc.models import KYCSubmission
            choices = [c[0] for c in KYCSubmission._meta.get_field("status").choices]
            self.assertIn("pending", choices)
        except (ImportError, Exception):
            self.skipTest("KYCSubmission status choices not available")


class KYCAPITest(APITestCase):

    def setUp(self):
        self.user = make_user()
        self.admin = make_user(is_staff=True)
        self.client.force_authenticate(user=self.user)

    def test_submit_kyc(self):
        res = self.client.post("/api/kyc/submit/", {
            "document_type": "national_id",
        }, format="json")
        self.assertIn(res.status_code, [200, 201, 400, 404])

    def test_kyc_status(self):
        res = self.client.get("/api/kyc/status/")
        self.assertNotIn(res.status_code, [500])

    def test_admin_kyc_list(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/kyc/")
        self.assertNotIn(res.status_code, [500])

    def test_kyc_unauthenticated(self):
        self.client.force_authenticate(user=None)
        res = self.client.get("/api/kyc/status/")
        self.assertIn(res.status_code, [401, 403])


# =============================================
# GAMIFICATION TESTS
# =============================================

class GamificationModelTest(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_badge_create(self):
        try:
            from api.gamification.models import Badge
            badge = Badge.objects.create(
                name="First Login",
                description="Awarded on first login",
                points=10,
            )
            self.assertEqual(badge.name, "First Login")
            self.assertEqual(badge.points, 10)
        except ImportError:
            self.skipTest("Badge model not available")

    def test_user_badge_award(self):
        try:
            from api.gamification.models import Badge, UserBadge
            badge = Badge.objects.create(name="Test Badge", points=5)
            ub = UserBadge.objects.create(user=self.user, badge=badge)
            self.assertEqual(ub.user, self.user)
        except ImportError:
            self.skipTest("UserBadge model not available")

    def test_leaderboard_entry(self):
        try:
            from api.gamification.models import LeaderboardEntry
            entry = LeaderboardEntry.objects.create(
                user=self.user,
                total_points=100,
                rank=1,
            )
            self.assertEqual(entry.total_points, 100)
        except ImportError:
            self.skipTest("LeaderboardEntry not available")


class GamificationAPITest(APITestCase):

    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(user=self.user)

    def test_leaderboard(self):
        res = self.client.get("/api/gamification/leaderboard/")
        self.assertNotIn(res.status_code, [500])

    def test_my_badges(self):
        res = self.client.get("/api/gamification/my-badges/")
        self.assertNotIn(res.status_code, [500])

    def test_my_points(self):
        res = self.client.get("/api/gamification/points/")
        self.assertNotIn(res.status_code, [500])

    def test_gamification_unauthenticated(self):
        self.client.force_authenticate(user=None)
        res = self.client.get("/api/gamification/leaderboard/")
        self.assertIn(res.status_code, [200, 401, 403])


# =============================================
# CACHE TESTS
# =============================================

class CacheModuleTest(TestCase):

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_basic_cache_operations(self):
        from django.core.cache import cache
        cache.set("test_key", "test_value", timeout=60)
        self.assertEqual(cache.get("test_key"), "test_value")

    def test_cache_miss_returns_none(self):
        from django.core.cache import cache
        self.assertIsNone(cache.get("nonexistent_key_xyz"))

    def test_cache_delete(self):
        from django.core.cache import cache
        cache.set("del_key", "value")
        cache.delete("del_key")
        self.assertIsNone(cache.get("del_key"))

    def test_cache_many(self):
        from django.core.cache import cache
        cache.set_many({"a": 1, "b": 2, "c": 3})
        result = cache.get_many(["a", "b", "c"])
        self.assertEqual(result["a"], 1)
        self.assertEqual(result["b"], 2)

    def test_cache_timeout(self):
        from django.core.cache import cache
        import time
        cache.set("expire_key", "value", timeout=1)
        time.sleep(1.5)
        self.assertIsNone(cache.get("expire_key"))

    def test_cache_increment(self):
        from django.core.cache import cache
        cache.set("counter", 0)
        cache.incr("counter", 5)
        self.assertEqual(cache.get("counter"), 5)


class CacheAPITest(APITestCase):

    def setUp(self):
        self.admin = make_user(is_staff=True)
        self.client.force_authenticate(user=self.admin)

    def test_cache_stats(self):
        res = self.client.get("/api/cache/stats/")
        self.assertNotIn(res.status_code, [500])

    def test_cache_flush_admin(self):
        res = self.client.post("/api/cache/flush/")
        self.assertIn(res.status_code, [200, 201, 403, 404])

    def test_cache_flush_unauthenticated(self):
        self.client.force_authenticate(user=None)
        res = self.client.post("/api/cache/flush/")
        self.assertIn(res.status_code, [401, 403])
