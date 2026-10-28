# =============================================================================
# fraud_detection/tests.py
#
# Cross-app model guards — imports are optional; tests skip gracefully
# if the dependent app isn't installed.
# =============================================================================
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

# ── Optional cross-app model imports ─────────────────────────────────────────
try:
    from api.kyc.models import KYCSubmission
except ImportError:
    KYCSubmission = None  # type: ignore

try:
    from api.gamification.models import UserBadge, Badge
except ImportError:
    UserBadge = None  # type: ignore
    Badge = None      # type: ignore

# ── Core model imports ────────────────────────────────────────────────────────
from api.fraud_detection.models import (
    FraudRule, FraudAttempt, FraudAlert, UserRiskProfile,
)


class FraudRuleModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="password123"
        )

    def test_create_fraud_rule(self):
        rule = FraudRule.objects.create(
            name="Test Rule",
            rule_type="velocity",
            threshold=10,
            is_active=True,
        )
        self.assertEqual(rule.name, "Test Rule")
        self.assertTrue(rule.is_active)

    def test_fraud_rule_str(self):
        rule = FraudRule.objects.create(
            name="IP Block Rule", rule_type="ip_block", threshold=5
        )
        self.assertIn("IP Block Rule", str(rule))


class FraudAttemptModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser2", password="password123"
        )

    def test_create_fraud_attempt(self):
        attempt = FraudAttempt.objects.create(
            user=self.user,
            fraud_type="velocity",
            risk_score=75,
            ip_address="192.168.1.1",
        )
        self.assertEqual(attempt.user, self.user)
        self.assertEqual(attempt.risk_score, 75)


class FraudDetectionAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="apitest", password="password123"
        )
        self.client.force_authenticate(user=self.user)

    def test_fraud_detect_endpoint(self):
        response = self.client.post("/api/fraud/detect/check-user/", {
            "user_id": self.user.pk,
        }, format="json")
        self.assertIn(response.status_code, [200, 400, 403])

    def test_fraud_rules_list(self):
        response = self.client.get("/api/fraud/rules/")
        self.assertIn(response.status_code, [200, 403])


class KYCIntegrationTest(TestCase):
    """Tests KYC integration — skipped if kyc app not installed."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="kyctest", password="password123"
        )

    def test_kyc_submission_create(self):
        if KYCSubmission is None:
            self.skipTest("KYCSubmission model not available")
        kyc = KYCSubmission.objects.create(
            user=self.user,
            document_type="national_id",
            status="pending",
        )
        self.assertEqual(kyc.status, "pending")
        self.assertEqual(kyc.user, self.user)


class GamificationIntegrationTest(TestCase):
    """Tests gamification integration — skipped if gamification app not installed."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="gamtest", password="password123"
        )

    def test_user_badge_create(self):
        if Badge is None or UserBadge is None:
            self.skipTest("Gamification models not available")
        badge = Badge.objects.create(name="Test Badge", points=5)
        ub = UserBadge.objects.create(user=self.user, badge=badge)
        self.assertEqual(ub.user, self.user)
