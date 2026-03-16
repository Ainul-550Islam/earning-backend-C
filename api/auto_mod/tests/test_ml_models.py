# =============================================================================
# auto_mod/tests/test_ml_models.py
# =============================================================================

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase

from ..choices import ModerationStatus, RiskLevel, RuleAction
from ..exceptions import InvalidConfidenceScoreError, InvalidRuleConfigError
from ..ml.image_scanner import ImageScanner, ImageScanResult
from ..ml.text_analyzer import TextAnalyzer, TextAnalysisResult
from ..models import AutoApprovalRule, SuspiciousSubmission
from ..services import ModerationService, RuleEngineService, SubmissionService
from ..utils.ai_validator import (
    validate_confidence,
    validate_file_url,
    validate_labels,
    validate_scan_result,
)
from ..utils.ocr_helper import OCRHelper, OCRResult
from .factories import (
    AutoApprovalRuleFactory,
    ProofScannerFactory,
    StaffUserFactory,
    SuspiciousSubmissionFactory,
    UserFactory,
)


# =============================================================================
# TextAnalyzer
# =============================================================================

class TestTextAnalyzer(TestCase):

    def setUp(self):
        self.analyzer = TextAnalyzer()

    def test_clean_text_returns_high_confidence(self):
        result = self.analyzer.analyze("I completed the task successfully today.")
        self.assertFalse(result.is_flagged)
        self.assertGreater(result.confidence, 0.5)
        self.assertIn("clean_text", result.labels)

    def test_empty_text_returns_unflagged(self):
        result = self.analyzer.analyze("")
        self.assertFalse(result.is_flagged)
        self.assertIn("empty_text", result.labels)

    def test_spam_pattern_detected(self):
        result = self.analyzer.analyze("Click here to make $500 today from home!")
        self.assertTrue(result.is_flagged)
        self.assertIn("spam", result.labels)

    def test_fake_proof_pattern_detected(self):
        result = self.analyzer.analyze("This image was photoshopped by me.")
        self.assertTrue(result.is_flagged)
        self.assertIn("fake_proof", result.labels)

    def test_repetitive_content_detected(self):
        result = self.analyzer.analyze("done done done done done done done done done done")
        self.assertTrue(result.is_flagged)
        self.assertIn("repetitive_content", result.labels)

    def test_low_quality_very_short_text(self):
        result = self.analyzer.analyze("ok")
        self.assertIn("low_quality", result.labels)

    def test_confidence_range_valid(self):
        result = self.analyzer.analyze("Some normal text about completing work.")
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)

    def test_model_version_set(self):
        result = self.analyzer.analyze("Hello world")
        self.assertNotEqual(result.model_version, "unloaded")
        self.assertIn("heuristic", result.model_version)

    def test_batch_analysis_returns_same_count(self):
        texts   = ["Text one", "Text two", ""]
        results = self.analyzer.analyze_batch(texts)
        self.assertEqual(len(results), 3)

    def test_batch_per_item_error_does_not_abort(self):
        # Analyzer should never crash even on weird input
        results = self.analyzer.analyze_batch(["normal", None, "another"])
        self.assertEqual(len(results), 3)

    def test_long_text_truncated(self):
        long_text = "word " * 5000   # > MAX_SUBMISSION_TEXT_LENGTH chars
        result = self.analyzer.analyze(long_text)
        self.assertIsInstance(result, TextAnalysisResult)


# =============================================================================
# ImageScanner
# =============================================================================

class TestImageScanner(TestCase):

    def setUp(self):
        self.scanner = ImageScanner()

    def test_scan_bytes_returns_result(self):
        # Minimal valid 1x1 PNG
        tiny_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
            b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
            b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        result = self.scanner.scan_bytes(tiny_png, filename="test.png")
        self.assertIsInstance(result, ImageScanResult)
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)

    def test_unsupported_extension_raises(self):
        from ..exceptions import UnsupportedFileTypeError
        with self.assertRaises(UnsupportedFileTypeError):
            self.scanner.scan_bytes(b"data", filename="file.exe")

    def test_empty_bytes_raises_scan_failed(self):
        from ..exceptions import ScanFailedError
        with self.assertRaises(ScanFailedError):
            self.scanner._run_inference(b"")

    def test_scan_error_returns_safe_result(self):
        # Scanning a non-image URL should return an error result, not raise
        result = self.scanner.scan("https://example.com/notanimage.jpg")
        # Either succeeds or returns error-encoded result
        self.assertIsInstance(result, ImageScanResult)

    def test_model_version_set(self):
        tiny_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        result = self.scanner.scan_bytes(tiny_png, filename="t.png")
        self.assertNotEqual(result.model_version, "unloaded")


# =============================================================================
# OCRHelper
# =============================================================================

class TestOCRHelper(TestCase):

    def test_empty_bytes_returns_empty_result(self):
        result = OCRHelper().extract_text(b"")
        self.assertEqual(result.text, "")
        self.assertEqual(result.confidence, 0.0)

    def test_stub_backend_returns_empty(self):
        helper = OCRHelper()
        helper._backend = "stub"
        result = helper.extract_text(b"fake image bytes")
        self.assertIsInstance(result, OCRResult)
        self.assertEqual(result.confidence, 0.0)


# =============================================================================
# AI Validators
# =============================================================================

class TestAIValidator(TestCase):

    def test_validate_confidence_valid(self):
        self.assertEqual(validate_confidence(0.95), 0.95)
        self.assertEqual(validate_confidence(0),    0.0)
        self.assertEqual(validate_confidence(1),    1.0)

    def test_validate_confidence_out_of_range(self):
        with self.assertRaises(InvalidConfidenceScoreError):
            validate_confidence(1.5)
        with self.assertRaises(InvalidConfidenceScoreError):
            validate_confidence(-0.1)

    def test_validate_confidence_non_numeric(self):
        with self.assertRaises(InvalidConfidenceScoreError):
            validate_confidence("high")

    def test_validate_labels_valid(self):
        labels = validate_labels(["spam", "low_quality"])
        self.assertEqual(labels, ["spam", "low_quality"])

    def test_validate_labels_invalid_chars(self):
        from ..exceptions import InvalidSubmissionError
        with self.assertRaises(InvalidSubmissionError):
            validate_labels(["UPPERCASE_LABEL"])

    def test_validate_labels_too_many(self):
        from ..exceptions import InvalidSubmissionError
        with self.assertRaises(InvalidSubmissionError):
            validate_labels([f"label_{i}" for i in range(51)])

    def test_validate_file_url_valid(self):
        url = validate_file_url("https://cdn.example.com/proof.jpg")
        self.assertEqual(url, "https://cdn.example.com/proof.jpg")

    def test_validate_file_url_bad_scheme(self):
        from ..exceptions import InvalidSubmissionError
        with self.assertRaises(InvalidSubmissionError):
            validate_file_url("ftp://example.com/file.jpg")

    def test_validate_scan_result_valid(self):
        result = validate_scan_result({
            "confidence": 0.85,
            "is_flagged": False,
            "labels": ["clean_text"],
        })
        self.assertEqual(result["confidence"], 0.85)

    def test_validate_scan_result_missing_is_flagged(self):
        from ..exceptions import InvalidSubmissionError
        with self.assertRaises(InvalidSubmissionError):
            validate_scan_result({"confidence": 0.5, "labels": []})


# =============================================================================
# RuleEngineService
# =============================================================================

class TestRuleEngineService(TestCase):

    def setUp(self):
        self.staff = StaffUserFactory()

    def test_no_rules_returns_none(self):
        sub  = SuspiciousSubmissionFactory()
        rule, action = RuleEngineService.evaluate(
            submission=sub,
            submission_type=sub.submission_type,
            confidence=0.95,
        )
        self.assertIsNone(rule)
        self.assertIsNone(action)

    def test_matching_rule_fires(self):
        AutoApprovalRuleFactory(
            submission_type="task_proof",
            action=RuleAction.APPROVE,
            confidence_threshold=0.80,
            conditions=[{"field": "confidence", "operator": "gte", "value": 0.80}],
        )
        sub = SuspiciousSubmissionFactory.build(
            submission_type="task_proof",
            risk_score=0.1,
            risk_level=RiskLevel.LOW,
        )
        sub.save()
        rule, action = RuleEngineService.evaluate(
            submission=sub,
            submission_type="task_proof",
            confidence=0.92,
        )
        self.assertIsNotNone(rule)
        self.assertEqual(action, RuleAction.APPROVE)

    def test_confidence_below_threshold_no_match(self):
        AutoApprovalRuleFactory(
            submission_type="task_proof",
            action=RuleAction.APPROVE,
            confidence_threshold=0.95,
            conditions=[{"field": "confidence", "operator": "gte", "value": 0.95}],
        )
        sub  = SuspiciousSubmissionFactory()
        rule, action = RuleEngineService.evaluate(
            submission=sub,
            submission_type="task_proof",
            confidence=0.70,    # below threshold
        )
        self.assertIsNone(rule)

    def test_eval_single_operators(self):
        ctx = {"confidence": 0.9, "risk_level": "low", "scan_label_count": 2}
        self.assertTrue(RuleEngineService._eval_single(
            {"field": "confidence", "operator": "gte", "value": 0.9}, ctx
        ))
        self.assertFalse(RuleEngineService._eval_single(
            {"field": "confidence", "operator": "gt", "value": 0.9}, ctx
        ))
        self.assertTrue(RuleEngineService._eval_single(
            {"field": "risk_level", "operator": "eq", "value": "low"}, ctx
        ))
        self.assertTrue(RuleEngineService._eval_single(
            {"field": "risk_level", "operator": "in", "value": ["low", "medium"]}, ctx
        ))


# =============================================================================
# SubmissionService
# =============================================================================

class TestSubmissionService(TestCase):

    def test_human_approve(self):
        reviewer = StaffUserFactory()
        sub      = SuspiciousSubmissionFactory(status=ModerationStatus.HUMAN_REVIEW)
        updated  = SubmissionService.human_approve(
            submission=sub, reviewer=reviewer, note="Looks good"
        )
        self.assertEqual(updated.status, ModerationStatus.HUMAN_APPROVED)
        self.assertEqual(updated.reviewed_by, reviewer)
        self.assertEqual(updated.reviewer_note, "Looks good")

    def test_human_reject(self):
        reviewer = StaffUserFactory()
        sub      = SuspiciousSubmissionFactory(status=ModerationStatus.HUMAN_REVIEW)
        updated  = SubmissionService.human_reject(
            submission=sub, reviewer=reviewer, note="Fake proof"
        )
        self.assertEqual(updated.status, ModerationStatus.HUMAN_REJECTED)

    def test_escalate(self):
        admin = StaffUserFactory()
        sub   = SuspiciousSubmissionFactory(status=ModerationStatus.HUMAN_REVIEW)
        updated = SubmissionService.escalate(
            submission=sub, escalated_to=admin, note="Needs senior review"
        )
        self.assertEqual(updated.status, ModerationStatus.ESCALATED)
        self.assertEqual(updated.escalated_to, admin)

    def test_get_or_404_not_found(self):
        from ..exceptions import SubmissionNotFoundError
        import uuid
        with self.assertRaises(SubmissionNotFoundError):
            SubmissionService.get_or_404(str(uuid.uuid4()))


# =============================================================================
# AutoApprovalRule model clean()
# =============================================================================

class TestAutoApprovalRuleModel(TestCase):

    def test_invalid_conditions_not_list(self):
        rule = AutoApprovalRuleFactory.build(conditions={"bad": "dict"})
        with self.assertRaises(Exception):
            rule.clean()

    def test_too_many_conditions(self):
        from ..constants import MAX_CONDITIONS_PER_RULE
        rule = AutoApprovalRuleFactory.build(
            conditions=[{"field": "x", "operator": "eq", "value": 1}] * (MAX_CONDITIONS_PER_RULE + 1)
        )
        with self.assertRaises(Exception):
            rule.clean()

    def test_valid_rule_clean_passes(self):
        rule = AutoApprovalRuleFactory.build()
        rule.clean()   # should not raise

    def test_condition_count_property(self):
        rule = AutoApprovalRuleFactory.build(
            conditions=[
                {"field": "confidence", "operator": "gte", "value": 0.9},
                {"field": "risk_level", "operator": "eq",  "value": "low"},
            ]
        )
        self.assertEqual(rule.condition_count, 2)
