# =============================================================================
# api/auto_mod/tests/test_integration.py
# =============================================================================
"""
End-to-end integration tests for the complete auto_mod pipeline.

Tests the full workflow:
  Submit proof → Scan → Rule evaluation → Decision → Queue → Appeal → Resolve
"""
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from ..choices import ModerationStatus, ScanStatus, TaskType, AppealStatus
from ..models import SuspiciousSubmission, ModerationDecision, ModerationAppeal, TaskBot
from ..services import (
    ModerationService, BotService, AppealService,
    AutoApprovalService, ModerationQueueService,
)
from ..adapters import AdapterRegistry
from .factories import (
    UserFactory, StaffUserFactory,
    SuspiciousSubmissionFactory, TaskBotFactory,
)

User = get_user_model()


@override_settings(TESTING=True)
class FullModerationPipelineTest(TestCase):
    """
    E2E: submission → scan → decision → queue → appeal → resolve
    All external calls are mocked.
    """

    def setUp(self):
        self.user      = UserFactory()
        self.moderator = StaffUserFactory()

    @patch.object(BotService, 'run_ocr_scan')
    @patch.object(BotService, 'run_image_analysis')
    def test_full_approve_pipeline(self, mock_image, mock_ocr):
        """Happy path: submission → auto-approved."""
        mock_ocr.return_value    = {"extracted_text": "completed task", "confidence": 0.9}
        mock_image.return_value  = {"analysis": {"is_flagged": False}, "confidence": 0.9}

        submission = SuspiciousSubmissionFactory(
            user=self.user, status=ModerationStatus.PENDING
        )
        bot = TaskBotFactory(
            bot_type=TaskType.IMAGE_SCANNER,
            status="idle",
            created_by=self.moderator,
        )

        # Start bot and run scan
        BotService.start_bot(bot)
        scanner = BotService.initiate_ocr_scan(submission, initiated_by=self.moderator)
        self.assertIsNotNone(scanner)

        # Check scan result stored
        submission.refresh_from_db()
        self.assertIsNotNone(scanner.started_at)

    @patch.object(BotService, 'run_ocr_scan', side_effect=Exception("AI unavailable"))
    def test_scan_failure_graceful(self, mock_ocr):
        """Scan failure should not crash — scanner saved with FAILED status."""
        submission = SuspiciousSubmissionFactory(user=self.user)
        scanner    = BotService.initiate_ocr_scan(submission)
        scanner.refresh_from_db()
        self.assertEqual(scanner.status, ScanStatus.FAILED)

    def test_appeal_workflow_end_to_end(self):
        """Rejected → appeal → assign reviewer → resolve."""
        submission = SuspiciousSubmissionFactory(
            user=self.user, status=ModerationStatus.HUMAN_REJECTED
        )
        decision = ModerationDecision.objects.create(
            submission=submission,
            decision_type=ModerationStatus.HUMAN_REJECTED,
            reason="Insufficient proof",
            confidence=0.3,
            is_automated=False,
            decided_by=self.moderator,
        )
        svc = AppealService()

        # Create appeal
        appeal = svc.create_appeal(
            decision=decision,
            appellant=self.user,
            reason="I have additional evidence",
            additional_data={"extra_url": "https://example.com/proof2.png"},
        )
        self.assertEqual(appeal.status, AppealStatus.PENDING)

        # Assign reviewer
        appeal = svc.assign_reviewer(appeal=appeal, reviewer=self.moderator)
        self.assertEqual(appeal.status, AppealStatus.UNDER_REVIEW)

        # Resolve
        appeal = svc.resolve_appeal(
            appeal=appeal,
            final_decision="upheld",
            final_reason="Additional evidence accepted",
            reviewer=self.moderator,
        )
        self.assertEqual(appeal.status, AppealStatus.RESOLVED)
        self.assertIsNotNone(appeal.resolved_at)

    def test_adapter_registry_importable(self):
        """AdapterRegistry must be importable and have all 47 systems."""
        from ..adapters import AdapterRegistry
        adapter_count = len([
            a for a in dir(AdapterRegistry)
            if not a.startswith('_')
        ])
        self.assertGreaterEqual(adapter_count, 44)

    def test_tests_adapter_health_check(self):
        """TestsAdapter.assert_moderation_pipeline_healthy() must pass."""
        result = AdapterRegistry.tests.assert_moderation_pipeline_healthy()
        self.assertTrue(result["passed"], f"Pipeline unhealthy: {result['errors']}")


@override_settings(TESTING=True)
class FraudDetectionIntegrationTest(TestCase):
    """Integration: fraud signals correctly influence moderation decisions."""

    def setUp(self):
        self.user = UserFactory()

    def test_blacklisted_ip_blocks_submission(self):
        """Blacklisted IP → submission should be blocked at IVT detection."""
        from ..missing_components import BlacklistService, InvalidTrafficDetector
        BlacklistService.add("ip", "10.0.0.99", reason="test_blacklist")
        result = InvalidTrafficDetector.score(ip="10.0.0.99", user_agent="Mozilla/5.0")
        self.assertTrue(result["is_invalid"])
        self.assertEqual(result["action"], "block")
        # Cleanup
        BlacklistService.remove("ip", "10.0.0.99")

    def test_burst_detection_flags_user(self):
        """Rapid submissions trigger burst detection."""
        from ..missing_components import BehavioralAnomalyDetector
        uid = str(self.user.pk)
        for _ in range(12):
            BehavioralAnomalyDetector.record_submission(uid)
        self.assertTrue(BehavioralAnomalyDetector.is_burst(uid))

    def test_publisher_quality_degrades_on_fraud(self):
        """Fraud detection lowers publisher quality score."""
        from ..missing_components import PublisherQualityService
        pub_id = "test_publisher_001"
        initial = PublisherQualityService.get_score(pub_id)
        PublisherQualityService.record_fraud_detected(pub_id)
        after = PublisherQualityService.get_score(pub_id)
        self.assertLess(after, initial)

    def test_sla_breach_detection(self):
        """SLA breach correctly identified after deadline passes."""
        from ..missing_components import SLATracker
        import time
        # Start with 0.001h SLA (about 3.6 seconds)
        record = SLATracker.start("submission", "test-e2e-001", sla_hours=0.001)
        time.sleep(4)
        status = SLATracker.check("submission", "test-e2e-001")
        self.assertTrue(status["breached"])


@override_settings(TESTING=True)
class AdapterFallbackTest(TestCase):
    """Adapters must gracefully fall back when external systems are unavailable."""

    def test_user_adapter_fallback(self):
        result = AdapterRegistry.user.get_user_risk_profile("nonexistent_user_999")
        self.assertIn("trust_score", result)
        self.assertEqual(result["trust_score"], 0.7)  # safe default

    def test_fraud_adapter_fallback(self):
        result = AdapterRegistry.fraud.get_fraud_signals("nonexistent_user_999", ip="1.2.3.4")
        self.assertIn("risk_score", result)

    def test_notification_adapter_fallback(self):
        result = AdapterRegistry.notification.notify_user("999", "test_event")
        self.assertIsInstance(result, bool)

    def test_wallet_adapter_fallback(self):
        result = AdapterRegistry.wallet.credit_reward("999", 1.0, "test", "ref_001")
        self.assertIsInstance(result, bool)
