# =============================================================================
# auto_mod/tests/test_ml_models.py
# =============================================================================

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from ..choices import ModerationStatus, RiskLevel, RuleAction
from ..exceptions import (
    InvalidConfidenceScoreError, 
    InvalidRuleConfigError,
    ModelVersionError,
    ModelTrainingError,
    ModelAlreadyDeployedError,
    ModelPerformanceThresholdError
)
from ..ml.image_scanner import ImageScanner, ImageScanResult
from ..ml.text_analyzer import TextAnalyzer, TextAnalysisResult
from ..models import AutoApprovalRule, SuspiciousSubmission, MLModelVersion
from api.auto_mod.services import (
    ModerationService, 
    RuleEngineService, 
    SubmissionService,
    MLModelService
)
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

User = get_user_model()


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


# =============================================================================
# MLModelVersion Tests
# =============================================================================

class TestMLModelVersionModel(TestCase):
    """Test MLModelVersion model functionality."""
    
    def setUp(self):
        self.user = UserFactory()
        self.model_version = MLModelVersion.objects.create(
            model_type="image",
            version="1.0.0",
            display_name="Test Image Model",
            description="A test model for image analysis",
            created_by=self.user,
            status="idle"
        )
    
    def test_model_version_creation(self):
        """Test basic model version creation."""
        self.assertEqual(self.model_version.model_type, "image")
        self.assertEqual(self.model_version.version, "1.0.0")
        self.assertEqual(self.model_version.display_name, "Test Image Model")
        self.assertEqual(self.model_version.created_by, self.user)
        self.assertEqual(self.model_version.status, "idle")
        self.assertFalse(self.model_version.is_active)
        self.assertIsNone(self.model_version.deployed_at)
        self.assertIsNone(self.model_version.accuracy)
    
    def test_model_version_str_representation(self):
        """Test model version string representation."""
        expected = f"{self.model_version.display_name} v{self.model_version.version}"
        self.assertEqual(str(self.model_version), expected)
    
    def test_mark_deployed(self):
        """Test marking model as deployed."""
        self.model_version.mark_deployed()
        
        self.assertTrue(self.model_version.is_active)
        self.assertEqual(self.model_version.status, "deployed")
        self.assertIsNotNone(self.model_version.deployed_at)
    
    def test_mark_retired(self):
        """Test marking model as retired."""
        self.model_version.mark_retired()
        
        self.assertFalse(self.model_version.is_active)
        self.assertEqual(self.model_version.status, "retired")
    
    def test_is_deployed_property(self):
        """Test is_deployed property."""
        self.assertFalse(self.model_version.is_deployed)
        
        self.model_version.mark_deployed()
        self.assertTrue(self.model_version.is_deployed)
        
        self.model_version.mark_retired()
        self.assertFalse(self.model_version.is_deployed)


class TestMLModelService(TestCase):
    """Test MLModelService functionality."""
    
    def setUp(self):
        self.user = UserFactory()
        self.service = MLModelService()
        
        self.model_version = MLModelVersion.objects.create(
            model_type="text",
            version="1.0.0",
            display_name="Test Text Model",
            created_by=self.user,
            status="idle"
        )
    
    @patch('api.auto_mod.services.MLModelService._save_model_file')
    @patch('api.auto_mod.services.MLModelService._calculate_file_checksum')
    def test_create_model_version_success(self, mock_checksum, mock_save):
        """Test successful model version creation."""
        mock_checksum.return_value = "abc123"
        mock_save.return_value = "/path/to/model.pkl"
        
        model = self.service.create_model_version(
            model_type="image",
            version="2.0.0",
            display_name="New Image Model",
            description="An improved image model",
            created_by=self.user,
            hyperparameters={"learning_rate": 0.001},
            metadata={"framework": "pytorch"}
        )
        
        self.assertEqual(model.model_type, "image")
        self.assertEqual(model.version, "2.0.0")
        self.assertEqual(model.display_name, "New Image Model")
        self.assertEqual(model.created_by, self.user)
        self.assertEqual(model.hyperparameters, {"learning_rate": 0.001})
        self.assertEqual(model.metadata, {"framework": "pytorch"})
        self.assertEqual(model.checksum, "abc123")
        self.assertEqual(model.file_path, "/path/to/model.pkl")
    
    def test_create_model_version_invalid_type(self):
        """Test model creation with invalid type."""
        with self.assertRaises(ModelVersionError):
            self.service.create_model_version(
                model_type="invalid_type",
                version="1.0.0",
                display_name="Invalid Model",
                created_by=self.user
            )
    
    def test_create_model_version_duplicate_version(self):
        """Test model creation with duplicate version."""
        with self.assertRaises(ModelVersionError):
            self.service.create_model_version(
                model_type="text",
                version="1.0.0",  # Same version as existing model
                display_name="Duplicate Model",
                created_by=self.user
            )
    
    def test_start_model_training_success(self):
        """Test successful model training start."""
        training_config = {"epochs": 10, "batch_size": 32}
        
        updated_model = self.service.start_model_training(
            model_version=self.model_version,
            training_config=training_config,
            training_data_version="v2.0",
            created_by=self.user
        )
        
        self.assertEqual(updated_model.status, "training")
        self.assertEqual(updated_model.training_data_version, "v2.0")
        self.assertIn("epochs", updated_model.hyperparameters)
        self.assertIn("batch_size", updated_model.hyperparameters)
    
    def test_start_model_training_invalid_status(self):
        """Test starting training on model not in idle status."""
        self.model_version.status = "training"
        self.model_version.save()
        
        with self.assertRaises(ModelTrainingError):
            self.service.start_model_training(
                model_version=self.model_version,
                training_config={},
                created_by=self.user
            )
    
    def test_complete_model_training_success(self):
        """Test successful model training completion."""
        # First start training
        self.model_version.status = "training"
        self.model_version.save()
        
        performance_metrics = {
            "accuracy": 0.95,
            "precision": 0.93,
            "recall": 0.94,
            "f1_score": 0.935
        }
        
        updated_model = self.service.complete_model_training(
            model_version=self.model_version,
            performance_metrics=performance_metrics,
            training_log="Training completed successfully",
            training_duration_hours=2.5
        )
        
        self.assertEqual(updated_model.status, "deployed")  # Auto-deployed due to high accuracy
        self.assertEqual(updated_model.accuracy, 0.95)
        self.assertEqual(updated_model.precision, 0.93)
        self.assertEqual(updated_model.recall, 0.94)
        self.assertEqual(updated_model.f1_score, 0.935)
        self.assertEqual(updated_model.training_duration_hours, 2.5)
        self.assertTrue(updated_model.is_active)
        self.assertIsNotNone(updated_model.deployed_at)
    
    def test_complete_model_training_low_accuracy(self):
        """Test training completion with low accuracy (should not auto-deploy)."""
        self.model_version.status = "training"
        self.model_version.save()
        
        performance_metrics = {
            "accuracy": 0.75,  # Below threshold
            "precision": 0.73,
            "recall": 0.74,
            "f1_score": 0.735
        }
        
        updated_model = self.service.complete_model_training(
            model_version=self.model_version,
            performance_metrics=performance_metrics
        )
        
        self.assertEqual(updated_model.status, "validating")  # Not auto-deployed
        self.assertFalse(updated_model.is_active)
        self.assertIsNone(updated_model.deployed_at)
    
    def test_deploy_model_success(self):
        """Test successful model deployment."""
        self.model_version.accuracy = 0.9
        self.model_version.save()
        
        updated_model = self.service.deploy_model(
            model_version=self.model_version,
            deployed_by=self.user,
            deployment_config={"environment": "production"}
        )
        
        self.assertEqual(updated_model.status, "deployed")
        self.assertTrue(updated_model.is_active)
        self.assertIsNotNone(updated_model.deployed_at)
        self.assertEqual(updated_model.deployment_config, {"environment": "production"})
    
    def test_deploy_model_already_deployed(self):
        """Test deploying already deployed model."""
        self.model_version.mark_deployed()
        
        with self.assertRaises(ModelAlreadyDeployedError):
            self.service.deploy_model(
                model_version=self.model_version,
                deployed_by=self.user
            )
    
    def test_deploy_model_low_accuracy(self):
        """Test deploying model with low accuracy."""
        self.model_version.accuracy = 0.7  # Below threshold
        self.model_version.save()
        
        with self.assertRaises(ModelPerformanceThresholdError):
            self.service.deploy_model(
                model_version=self.model_version,
                deployed_by=self.user
            )
    
    def test_retire_model_success(self):
        """Test successful model retirement."""
        self.model_version.mark_deployed()
        
        updated_model = self.service.retire_model(
            model_version=self.model_version,
            retirement_reason="Model deprecated",
            retired_by=self.user
        )
        
        self.assertEqual(updated_model.status, "retired")
        self.assertFalse(updated_model.is_active)
        self.assertIn("retirement", updated_model.metadata)
        self.assertEqual(updated_model.metadata["retirement"]["reason"], "Model deprecated")
        self.assertEqual(updated_model.metadata["retirement"]["retired_by"], self.user.username)
    
    def test_get_active_models(self):
        """Test getting active models."""
        # Create active model
        active_model = MLModelVersion.objects.create(
            model_type="image",
            version="2.0.0",
            display_name="Active Model",
            created_by=self.user,
            status="deployed",
            is_active=True
        )
        
        # Create inactive model
        inactive_model = MLModelVersion.objects.create(
            model_type="text",
            version="1.5.0",
            display_name="Inactive Model",
            created_by=self.user,
            status="idle",
            is_active=False
        )
        
        active_models = self.service.get_active_models()
        
        self.assertIn(active_model, active_models)
        self.assertNotIn(inactive_model, active_models)
        self.assertNotIn(self.model_version, active_models)
    
    def test_get_best_model_for_type(self):
        """Test getting best model for a type."""
        # Create multiple models of same type
        model1 = MLModelVersion.objects.create(
            model_type="image",
            version="1.0.0",
            display_name="Model 1",
            created_by=self.user,
            status="deployed",
            is_active=True,
            accuracy=0.85
        )
        
        model2 = MLModelVersion.objects.create(
            model_type="image",
            version="2.0.0",
            display_name="Model 2",
            created_by=self.user,
            status="deployed",
            is_active=True,
            accuracy=0.92  # Higher accuracy
        )
        
        best_model = self.service.get_best_model_for_type("image")
        
        self.assertEqual(best_model, model2)
    
    def test_check_model_health(self):
        """Test model health check."""
        # Healthy model
        self.model_version.mark_deployed()
        self.model_version.file_path = "/path/to/model.pkl"
        self.model_version.checksum = "abc123"
        
        with patch('api.auto_mod.services.MLModelService._verify_file_integrity', return_value=True):
            health = self.service.check_model_health(self.model_version)
            
            self.assertEqual(health["health_status"], "healthy")
            self.assertEqual(len(health["issues"]), 0)
    
    def test_check_model_health_unhealthy(self):
        """Test model health check for unhealthy model."""
        # Unhealthy model - no file integrity
        self.model_version.mark_deployed()
        self.model_version.file_path = "/path/to/missing.pkl"
        self.model_version.checksum = "abc123"
        
        with patch('api.auto_mod.services.MLModelService._verify_file_integrity', return_value=False):
            health = self.service.check_model_health(self.model_version)
            
            self.assertEqual(health["health_status"], "critical")
            self.assertGreater(len(health["issues"]), 0)
    
    def test_get_model_statistics(self):
        """Test model statistics retrieval."""
        # Create models with different statuses
        MLModelVersion.objects.create(
            model_type="image",
            version="2.0.0",
            display_name="Active Model",
            created_by=self.user,
            status="deployed",
            is_active=True,
            accuracy=0.9
        )
        
        MLModelVersion.objects.create(
            model_type="text",
            version="1.5.0",
            display_name="Training Model",
            created_by=self.user,
            status="training"
        )
        
        stats = self.service.get_model_statistics()
        
        self.assertIn("total_models", stats)
        self.assertIn("active_models", stats)
        self.assertIn("deployed_models", stats)
        self.assertIn("training_models", stats)
        self.assertIn("type_breakdown", stats)
        self.assertIn("status_breakdown", stats)
        self.assertIn("avg_performance_metrics", stats)
        self.assertGreater(stats["total_models"], 0)
    
    def test_compare_model_versions(self):
        """Test model version comparison."""
        model1 = MLModelVersion.objects.create(
            model_type="image",
            version="1.0.0",
            display_name="Model v1",
            created_by=self.user,
            accuracy=0.85,
            precision=0.83,
            recall=0.87
        )
        
        model2 = MLModelVersion.objects.create(
            model_type="image",
            version="2.0.0",
            display_name="Model v2",
            created_by=self.user,
            accuracy=0.92,
            precision=0.90,
            recall=0.94
        )
        
        comparison = self.service.compare_model_versions(model1, model2)
        
        self.assertIn("version1", comparison)
        self.assertIn("version2", comparison)
        self.assertIn("improvements", comparison)
        
        # Check improvements
        self.assertGreater(comparison["improvements"]["accuracy"], 0)
        self.assertGreater(comparison["improvements"]["precision"], 0)
        self.assertGreater(comparison["improvements"]["recall"], 0)


class TestMLModelAPI(TestCase):
    """Test MLModel API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        
        self.model_version = MLModelVersion.objects.create(
            model_type="image",
            version="1.0.0",
            display_name="Test Model",
            created_by=self.staff_user,
            status="idle"
        )
    
    def test_list_models_unauthorized(self):
        """Test listing models without authentication."""
        response = self.client.get("/api/auto_mod/models/")
        self.assertEqual(response.status_code, 401)
    
    def test_list_models_non_staff(self):
        """Test listing models as non-staff user."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/auto_mod/models/")
        self.assertEqual(response.status_code, 403)
    
    def test_list_models_staff(self):
        """Test listing models as staff user."""
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get("/api/auto_mod/models/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
    
    def test_create_model_staff(self):
        """Test creating model as staff user."""
        self.client.force_authenticate(user=self.staff_user)
        
        data = {
            "model_type": "text",
            "version": "2.0.0",
            "display_name": "New Model",
            "description": "A new text model",
            "hyperparameters": {"learning_rate": 0.001}
        }
        
        response = self.client.post("/api/auto_mod/models/", data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(MLModelVersion.objects.count(), 2)
    
    def test_deploy_model(self):
        """Test deploying model endpoint."""
        self.client.force_authenticate(user=self.staff_user)
        
        # Set accuracy to meet threshold
        self.model_version.accuracy = 0.9
        self.model_version.save()
        
        response = self.client.post(f"/api/auto_mod/models/{self.model_version.pk}/deploy/")
        self.assertEqual(response.status_code, 200)
        
        self.model_version.refresh_from_db()
        self.assertEqual(self.model_version.status, "deployed")
        self.assertTrue(self.model_version.is_active)
    
    def test_train_model(self):
        """Test training model endpoint."""
        self.client.force_authenticate(user=self.staff_user)
        
        training_config = {"epochs": 10, "batch_size": 32}
        
        response = self.client.post(f"/api/auto_mod/models/{self.model_version.pk}/train/", {
            "config": training_config
        })
        self.assertEqual(response.status_code, 200)
        
        self.model_version.refresh_from_db()
        self.assertEqual(self.model_version.status, "training")
    
    def test_retire_model(self):
        """Test retiring model endpoint."""
        self.client.force_authenticate(user=self.staff_user)
        
        # First deploy the model
        self.model_version.mark_deployed()
        
        response = self.client.post(f"/api/auto_mod/models/{self.model_version.pk}/retire/", {
            "reason": "Model deprecated"
        })
        self.assertEqual(response.status_code, 200)
        
        self.model_version.refresh_from_db()
        self.assertEqual(self.model_version.status, "retired")
        self.assertFalse(self.model_version.is_active)
    
    def test_get_active_models(self):
        """Test getting active models endpoint."""
        self.client.force_authenticate(user=self.staff_user)
        
        # Create active model
        active_model = MLModelVersion.objects.create(
            model_type="image",
            version="2.0.0",
            display_name="Active Model",
            created_by=self.staff_user,
            status="deployed",
            is_active=True
        )
        
        response = self.client.get("/api/auto_mod/models/active/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], str(active_model.pk))
    
    def test_model_health_check(self):
        """Test model health check endpoint."""
        self.client.force_authenticate(user=self.staff_user)
        
        with patch('api.auto_mod.services.MLModelService.check_model_health') as mock_health:
            mock_health.return_value = {
                "health_status": "healthy",
                "issues": []
            }
            
            response = self.client.get(f"/api/auto_mod/models/{self.model_version.pk}/health/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["health_status"], "healthy")
    
    def test_model_statistics(self):
        """Test model statistics endpoint."""
        self.client.force_authenticate(user=self.staff_user)
        
        response = self.client.get("/api/auto_mod/models/statistics/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("total_models", response.data)
        self.assertIn("active_models", response.data)
