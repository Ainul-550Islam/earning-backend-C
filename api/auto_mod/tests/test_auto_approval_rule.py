# =============================================================================
# auto_mod/tests/test_auto_approval_rule.py
# =============================================================================

"""
Tests for auto approval rules functionality.
"""

import pytest
from unittest.mock import Mock, patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from ..choices import RuleAction, SubmissionType, ModerationStatus
from ..models import AutoApprovalRule, SuspiciousSubmission, ModerationDecision
from api.auto_mod.services.AutoApprovalService import AutoApprovalService
from ..exceptions import InvalidRuleConfigError, RuleEvaluationError

User = get_user_model()


class AutoApprovalRuleModelTest(TestCase):
    """Test AutoApprovalRule model functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        self.rule = AutoApprovalRule.objects.create(
            name="Test Rule",
            submission_type=SubmissionType.IMAGE,
            action=RuleAction.AUTO_APPROVE,
            priority=50,
            confidence_threshold=0.8,
            created_by=self.user,
            conditions=[
                {
                    "field": "risk_score",
                    "operator": "less_than",
                    "value": 2.0
                }
            ]
        )
    
    def test_rule_creation(self):
        """Test basic rule creation."""
        self.assertEqual(self.rule.name, "Test Rule")
        self.assertEqual(self.rule.submission_type, SubmissionType.IMAGE)
        self.assertEqual(self.rule.action, RuleAction.AUTO_APPROVE)
        self.assertEqual(self.rule.priority, 50)
        self.assertEqual(self.rule.confidence_threshold, 0.8)
        self.assertTrue(self.rule.is_active)
        self.assertFalse(self.rule.is_system)
        self.assertEqual(self.rule.created_by, self.user)
    
    def test_rule_str_representation(self):
        """Test rule string representation."""
        expected = f"{self.rule.name} ({self.rule.submission_type})"
        self.assertEqual(str(self.rule), expected)
    
    def test_rule_conditions_validation(self):
        """Test rule conditions validation."""
        # Valid conditions
        valid_conditions = [
            {
                "field": "risk_score",
                "operator": "less_than",
                "value": 2.0
            }
        ]
        self.rule.conditions = valid_conditions
        self.rule.save()
        self.assertEqual(self.rule.conditions, valid_conditions)
    
    def test_for_evaluation_queryset(self):
        """Test for_evaluation queryset method."""
        qs = AutoApprovalRule.objects.for_evaluation(SubmissionType.IMAGE)
        self.assertIn(self.rule, qs)
        
        qs = AutoApprovalRule.objects.for_evaluation(SubmissionType.TEXT)
        self.assertNotIn(self.rule, qs)
        
        # Test inactive rule
        self.rule.is_active = False
        self.rule.save()
        qs = AutoApprovalRule.objects.for_evaluation(SubmissionType.IMAGE)
        self.assertNotIn(self.rule, qs)


class AutoApprovalServiceTest(TestCase):
    """Test AutoApprovalService functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.moderator = User.objects.create_user(
            username="moderator",
            email="mod@example.com",
            password="modpass123",
            is_staff=True
        )
        
        self.service = AutoApprovalService()
        
        # Create test submission
        self.submission = SuspiciousSubmission.objects.create(
            content_id="test123",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            risk_score=1.5,
            ai_confidence=0.9,
            status=ModerationStatus.PENDING
        )
        
        # Create test rule
        self.rule = AutoApprovalRule.objects.create(
            name="Auto Approve Low Risk",
            submission_type=SubmissionType.IMAGE,
            action=RuleAction.AUTO_APPROVE,
            priority=50,
            confidence_threshold=0.8,
            created_by=self.moderator,
            conditions=[
                {
                    "field": "risk_score",
                    "operator": "less_than",
                    "value": 2.0
                },
                {
                    "field": "ai_confidence",
                    "operator": "greater_equal",
                    "value": 0.8
                }
            ]
        )
    
    def test_evaluate_submission_for_auto_approval_success(self):
        """Test successful auto-approval evaluation."""
        result = self.service.evaluate_submission_for_auto_approval(self.submission)
        
        self.assertEqual(result["recommendation"], "approve_automatically")
        self.assertGreater(result["confidence"], 0.8)
        self.assertTrue(result["auto_approvable"])
        self.assertEqual(len(result["matched_rules"]), 1)
        self.assertEqual(result["matched_rules"][0]["rule_name"], "Auto Approve Low Risk")
    
    def test_evaluate_submission_no_rules(self):
        """Test evaluation when no rules match."""
        # Create submission with high risk score
        high_risk_submission = SuspiciousSubmission.objects.create(
            content_id="high123",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            risk_score=5.0,
            ai_confidence=0.9,
            status=ModerationStatus.PENDING
        )
        
        result = self.service.evaluate_submission_for_auto_approval(high_risk_submission)
        
        self.assertEqual(result["recommendation"], "human_review")
        self.assertEqual(result["confidence"], 0.0)
        self.assertFalse(result["auto_approvable"])
        self.assertEqual(len(result["matched_rules"]), 0)
    
    def test_evaluate_submission_already_processed(self):
        """Test evaluation of already processed submission."""
        self.submission.status = ModerationStatus.HUMAN_APPROVED
        self.submission.save()
        
        with self.assertRaises(RuleEvaluationError):
            self.service.evaluate_submission_for_auto_approval(self.submission)
    
    def test_execute_auto_decision_approve(self):
        """Test executing auto-approval decision."""
        result = self.service.evaluate_submission_for_auto_approval(self.submission)
        
        decision = self.service.execute_auto_decision(
            submission=self.submission,
            recommendation=result["recommendation"],
            confidence=result["confidence"],
            reason=result["reason"],
            applied_rules=[self.rule]
        )
        
        self.assertEqual(decision.decision_type, ModerationStatus.AUTO_APPROVED)
        self.assertEqual(decision.submission, self.submission)
        self.assertEqual(decision.confidence, result["confidence"])
        self.assertTrue(decision.is_automated)
        self.assertEqual(decision.applied_rule, self.rule)
        
        # Check submission status updated
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, ModerationStatus.AUTO_APPROVED)
    
    def test_execute_auto_decision_invalid_recommendation(self):
        """Test executing decision with invalid recommendation."""
        with self.assertRaises(RuleEvaluationError):
            self.service.execute_auto_decision(
                submission=self.submission,
                recommendation="invalid_recommendation",
                confidence=0.8,
                reason="Test reason"
            )
    
    def test_execute_auto_decision_invalid_confidence(self):
        """Test executing decision with invalid confidence."""
        with self.assertRaises(RuleEvaluationError):
            self.service.execute_auto_decision(
                submission=self.submission,
                recommendation="approve_automatically",
                confidence=1.5,  # Invalid confidence > 1.0
                reason="Test reason"
            )
    
    def test_create_auto_approval_rule_success(self):
        """Test successful rule creation."""
        conditions = [
            {
                "field": "risk_score",
                "operator": "less_than",
                "value": 3.0
            }
        ]
        
        rule = self.service.create_auto_approval_rule(
            name="Test Rule",
            submission_type=SubmissionType.TEXT,
            conditions=conditions,
            action=RuleAction.AUTO_REJECT,
            priority=75,
            confidence_threshold=0.9,
            created_by=self.user
        )
        
        self.assertEqual(rule.name, "Test Rule")
        self.assertEqual(rule.submission_type, SubmissionType.TEXT)
        self.assertEqual(rule.action, RuleAction.AUTO_REJECT)
        self.assertEqual(rule.priority, 75)
        self.assertEqual(rule.confidence_threshold, 0.9)
        self.assertEqual(rule.conditions, conditions)
        self.assertEqual(rule.created_by, self.user)
    
    def test_create_auto_approval_rule_invalid_action(self):
        """Test rule creation with invalid action."""
        with self.assertRaises(InvalidRuleConfigError):
            self.service.create_auto_approval_rule(
                name="Invalid Rule",
                submission_type=SubmissionType.TEXT,
                conditions=[],
                action="invalid_action"
            )
    
    def test_create_auto_approval_rule_invalid_conditions(self):
        """Test rule creation with invalid conditions."""
        with self.assertRaises(InvalidRuleConfigError):
            self.service.create_auto_approval_rule(
                name="Invalid Rule",
                submission_type=SubmissionType.TEXT,
                conditions=[],  # Empty conditions
                action=RuleAction.AUTO_APPROVE
            )
    
    def test_calculate_risk_score(self):
        """Test risk score calculation."""
        risk_score = self.service.calculate_risk_score(self.submission)
        
        # Should include base risk + signal risk + characteristic risk
        self.assertIsInstance(risk_score, float)
        self.assertGreaterEqual(risk_score, 0.0)
        self.assertLessEqual(risk_score, 10.0)
    
    def test_get_risk_assessment(self):
        """Test comprehensive risk assessment."""
        assessment = self.service.get_risk_assessment(self.submission)
        
        self.assertIn("submission_id", assessment)
        self.assertIn("risk_score", assessment)
        self.assertIn("risk_level", assessment)
        self.assertIn("factors", assessment)
        self.assertIn("recommendation", assessment)
        self.assertIn("assessed_at", assessment)
        
        self.assertIsInstance(assessment["risk_score"], float)
        self.assertIn(assessment["risk_level"], ["low", "medium", "high", "critical"])
        self.assertIsInstance(assessment["factors"], list)
    
    def test_process_pending_submissions(self):
        """Test batch processing of pending submissions."""
        # Create multiple submissions
        submissions = []
        for i in range(3):
            sub = SuspiciousSubmission.objects.create(
                content_id=f"test{i}",
                submission_type=SubmissionType.IMAGE,
                user=self.user,
                risk_score=1.0,
                ai_confidence=0.9,
                status=ModerationStatus.PENDING
            )
            submissions.append(sub)
        
        result = self.service.process_pending_submissions(
            submission_type=SubmissionType.IMAGE,
            batch_size=5,
            dry_run=False
        )
        
        self.assertGreater(result["processed"], 0)
        self.assertGreaterEqual(result["approved"], 0)
        self.assertGreaterEqual(result["rejected"], 0)
        self.assertGreaterEqual(result["escalated"], 0)
        self.assertGreaterEqual(result["human_review"], 0)
        self.assertEqual(result["dry_run"], False)
    
    def test_process_pending_submissions_dry_run(self):
        """Test batch processing in dry run mode."""
        result = self.service.process_pending_submissions(
            submission_type=SubmissionType.IMAGE,
            batch_size=5,
            dry_run=True
        )
        
        self.assertEqual(result["dry_run"], True)
        # Submissions should not be processed
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, ModerationStatus.PENDING)
    
    def test_get_rule_effectiveness(self):
        """Test rule effectiveness analysis."""
        # Create some decisions using the rule
        for i in range(5):
            ModerationDecision.objects.create(
                submission=self.submission,
                decision_type=ModerationStatus.AUTO_APPROVED,
                reason="Auto-approved",
                confidence=0.9,
                decided_by=self.user,
                is_automated=True,
                applied_rule=self.rule
            )
        
        effectiveness = self.service.get_rule_effectiveness(self.rule, days_back=30)
        
        self.assertEqual(effectiveness["rule_id"], str(self.rule.pk))
        self.assertEqual(effectiveness["rule_name"], self.rule.name)
        self.assertEqual(effectiveness["period_days"], 30)
        self.assertGreater(effectiveness["total_decisions"], 0)
        self.assertGreaterEqual(effectiveness["approval_rate"], 0)
        self.assertLessEqual(effectiveness["approval_rate"], 100)
    
    def test_get_auto_approval_statistics(self):
        """Test auto-approval statistics."""
        # Create some test data
        ModerationDecision.objects.create(
            submission=self.submission,
            decision_type=ModerationStatus.AUTO_APPROVED,
            reason="Auto-approved",
            confidence=0.9,
            decided_by=self.user,
            is_automated=True,
            applied_rule=self.rule
        )
        
        stats = self.service.get_auto_approval_statistics(days_back=30)
        
        self.assertIn("period_days", stats)
        self.assertIn("total_auto_decisions", stats)
        self.assertIn("decision_breakdown", stats)
        self.assertIn("approval_rate", stats)
        self.assertIn("confidence_stats", stats)
        self.assertIn("rule_effectiveness", stats)
        self.assertIn("error_rate", stats)


class AutoApprovalRuleAPITest(TestCase):
    """Test AutoApprovalRule API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.staff_user = User.objects.create_user(
            username="staffuser",
            email="staff@example.com",
            password="staffpass123",
            is_staff=True
        )
        
        self.rule = AutoApprovalRule.objects.create(
            name="Test Rule",
            submission_type=SubmissionType.IMAGE,
            action=RuleAction.AUTO_APPROVE,
            priority=50,
            confidence_threshold=0.8,
            created_by=self.staff_user,
            conditions=[
                {
                    "field": "risk_score",
                    "operator": "less_than",
                    "value": 2.0
                }
            ]
        )
    
    def test_list_rules_unauthorized(self):
        """Test listing rules without authentication."""
        response = self.client.get("/api/auto_mod/rules/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_list_rules_authorized(self):
        """Test listing rules with authentication."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/auto_mod/rules/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_create_rule_staff(self):
        """Test creating rule as staff user."""
        self.client.force_authenticate(user=self.staff_user)
        
        data = {
            "name": "New Rule",
            "submission_type": SubmissionType.TEXT,
            "action": RuleAction.AUTO_REJECT,
            "priority": 75,
            "confidence_threshold": 0.9,
            "conditions": [
                {
                    "field": "risk_score",
                    "operator": "greater_than",
                    "value": 5.0
                }
            ]
        }
        
        response = self.client.post("/api/auto_mod/rules/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AutoApprovalRule.objects.count(), 2)
    
    def test_create_rule_non_staff(self):
        """Test creating rule as non-staff user."""
        self.client.force_authenticate(user=self.user)
        
        data = {
            "name": "New Rule",
            "submission_type": SubmissionType.TEXT,
            "action": RuleAction.AUTO_REJECT,
            "priority": 75,
            "conditions": []
        }
        
        response = self.client.post("/api/auto_mod/rules/", data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_toggle_rule_active(self):
        """Test toggling rule active status."""
        self.client.force_authenticate(user=self.staff_user)
        
        # Deactivate rule
        response = self.client.post(f"/api/auto_mod/rules/{self.rule.pk}/toggle/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.rule.refresh_from_db()
        self.assertFalse(self.rule.is_active)
        
        # Reactivate rule
        response = self.client.post(f"/api/auto_mod/rules/{self.rule.pk}/toggle/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.rule.refresh_from_db()
        self.assertTrue(self.rule.is_active)
    
    def test_delete_system_rule(self):
        """Test deleting a system rule (should fail)."""
        self.rule.is_system = True
        self.rule.save()
        
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.delete(f"/api/auto_mod/rules/{self.rule.pk}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Rule should still exist
        self.assertTrue(AutoApprovalRule.objects.filter(pk=self.rule.pk).exists())


class RuleEvaluationTest(TestCase):
    """Test rule evaluation logic."""
    
    def setUp(self):
        self.service = AutoApprovalService()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        self.submission = SuspiciousSubmission.objects.create(
            content_id="test123",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            risk_score=1.5,
            ai_confidence=0.9,
            metadata={"test_field": "test_value"},
            status=ModerationStatus.PENDING
        )
    
    def test_evaluate_condition_equals(self):
        """Test equals operator."""
        condition = {"field": "submission_type", "operator": "equals", "value": SubmissionType.IMAGE}
        result = self.service._evaluate_condition(self.submission, condition)
        self.assertTrue(result["matched"])
        
        condition["value"] = SubmissionType.TEXT
        result = self.service._evaluate_condition(self.submission, condition)
        self.assertFalse(result["matched"])
    
    def test_evaluate_condition_greater_than(self):
        """Test greater_than operator."""
        condition = {"field": "risk_score", "operator": "greater_than", "value": 1.0}
        result = self.service._evaluate_condition(self.submission, condition)
        self.assertTrue(result["matched"])
        
        condition["value"] = 2.0
        result = self.service._evaluate_condition(self.submission, condition)
        self.assertFalse(result["matched"])
    
    def test_evaluate_condition_contains(self):
        """Test contains operator."""
        self.submission.flag_reason = "spam_content"
        self.submission.save()
        
        condition = {"field": "flag_reason", "operator": "contains", "value": "spam"}
        result = self.service._evaluate_condition(self.submission, condition)
        self.assertTrue(result["matched"])
        
        condition["value"] = "ham"
        result = self.service._evaluate_condition(self.submission, condition)
        self.assertFalse(result["matched"])
    
    def test_evaluate_condition_metadata(self):
        """Test metadata field evaluation."""
        condition = {"field": "metadata.test_field", "operator": "equals", "value": "test_value"}
        result = self.service._evaluate_condition(self.submission, condition)
        self.assertTrue(result["matched"])
    
    def test_evaluate_condition_invalid_field(self):
        """Test evaluation with invalid field."""
        condition = {"field": "invalid_field", "operator": "equals", "value": "test"}
        result = self.service._evaluate_condition(self.submission, condition)
        self.assertFalse(result["matched"])
        self.assertIn("error", result)
    
    def test_get_field_value(self):
        """Test getting field values from submission."""
        # Test direct field
        value = self.service._get_field_value(self.submission, "risk_score")
        self.assertEqual(value, 1.5)
        
        # Test metadata field
        value = self.service._get_field_value(self.submission, "metadata.test_field")
        self.assertEqual(value, "test_value")
        
        # Test invalid field
        with self.assertRaises(ValueError):
            self.service._get_field_value(self.submission, "invalid_field")
    
    def test_apply_operator(self):
        """Test applying comparison operators."""
        # Test equals
        result = self.service._apply_operator("test", "equals", "test")
        self.assertTrue(result)
        
        # Test greater_than
        result = self.service._apply_operator(5, "greater_than", 3)
        self.assertTrue(result)
        
        # Test contains
        result = self.service._apply_operator("hello world", "contains", "world")
        self.assertTrue(result)
        
        # Test invalid operator
        with self.assertRaises(ValueError):
            self.service._apply_operator(5, "invalid_op", 3)
    
    def test_validate_rule_conditions(self):
        """Test rule conditions validation."""
        # Valid conditions
        valid_conditions = [
            {"field": "risk_score", "operator": "less_than", "value": 2.0}
        ]
        # Should not raise exception
        self.service._validate_rule_conditions(valid_conditions)
        
        # Empty conditions
        with self.assertRaises(InvalidRuleConfigError):
            self.service._validate_rule_conditions([])
        
        # Missing required field
        invalid_conditions = [
            {"operator": "less_than", "value": 2.0}
        ]
        with self.assertRaises(InvalidRuleConfigError):
            self.service._validate_rule_conditions(invalid_conditions)
