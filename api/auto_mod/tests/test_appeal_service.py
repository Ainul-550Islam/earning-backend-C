# =============================================================================
# auto_mod/tests/test_appeal_service.py
# =============================================================================

"""
Tests for appeal service functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from ..choices import ModerationStatus, AppealStatus, AppealOutcome, SubmissionType
from ..models import ModerationAppeal, ModerationDecision, SuspiciousSubmission
from api.auto_mod.services.AppealService import AppealService
from ..exceptions import AppealNotFoundError, AppealProcessingError

User = get_user_model()


class ModerationAppealModelTest(TestCase):
    """Test ModerationAppeal model functionality."""
    
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
        
        self.submission = SuspiciousSubmission.objects.create(
            content_id="test123",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.HUMAN_REJECTED
        )
        
        self.decision = ModerationDecision.objects.create(
            submission=self.submission,
            decision_type=ModerationStatus.HUMAN_REJECTED,
            reason="Inappropriate content",
            confidence=0.9,
            decided_by=self.moderator,
            is_automated=False
        )
        
        self.appeal = ModerationAppeal.objects.create(
            user=self.user,
            original_decision=self.decision,
            submission=self.submission,
            reason="I disagree with this decision",
            status=AppealStatus.PENDING
        )
    
    def test_appeal_creation(self):
        """Test basic appeal creation."""
        self.assertEqual(self.appeal.user, self.user)
        self.assertEqual(self.appeal.original_decision, self.decision)
        self.assertEqual(self.appeal.submission, self.submission)
        self.assertEqual(self.appeal.reason, "I disagree with this decision")
        self.assertEqual(self.appeal.status, AppealStatus.PENDING)
        self.assertIsNone(self.appeal.reviewed_by)
        self.assertIsNone(self.appeal.reviewed_at)
        self.assertIsNone(self.appeal.final_outcome)
        self.assertIsNotNone(self.appeal.created_at)
    
    def test_appeal_str_representation(self):
        """Test appeal string representation."""
        expected = f"Appeal: {self.submission.content_id} by {self.user.username}"
        self.assertEqual(str(self.appeal), expected)
    
    def test_assign_reviewer(self):
        """Test assigning reviewer to appeal."""
        reviewer = User.objects.create_user(
            username="reviewer",
            email="reviewer@example.com",
            password="reviewerpass123",
            is_staff=True
        )
        
        self.appeal.assign_reviewer(reviewer)
        self.appeal.save()
        
        self.assertEqual(self.appeal.reviewed_by, reviewer)
        self.assertEqual(self.appeal.status, AppealStatus.UNDER_REVIEW)
        self.assertIsNotNone(self.appeal.reviewed_at)
    
    def test_resolve_appeal(self):
        """Test resolving an appeal."""
        reviewer = User.objects.create_user(
            username="reviewer",
            email="reviewer@example.com",
            password="reviewerpass123",
            is_staff=True
        )
        
        self.appeal.resolve(
            final_outcome=AppealOutcome.UPHELD,
            final_reason="Original decision stands",
            reviewer=reviewer
        )
        self.appeal.save()
        
        self.assertEqual(self.appeal.final_outcome, AppealOutcome.UPHELD)
        self.assertEqual(self.appeal.final_reason, "Original decision stands")
        self.assertEqual(self.appeal.reviewed_by, reviewer)
        self.assertEqual(self.appeal.status, AppealStatus.RESOLVED)
        self.assertIsNotNone(self.appeal.resolved_at)
    
    def test_is_overdue_property(self):
        """Test is_overdue property."""
        # Fresh appeal should not be overdue
        self.assertFalse(self.appeal.is_overdue)
        
        # Make it overdue
        self.appeal.created_at = timezone.now() - timezone.timedelta(days=8)
        self.appeal.save()
        
        self.assertTrue(self.appeal.is_overdue)
    
    def test_get_pending_appeals(self):
        """Test getting pending appeals."""
        pending_appeals = ModerationAppeal.objects.get_pending_appeals()
        self.assertIn(self.appeal, pending_appeals)
        
        # Resolve the appeal
        self.appeal.status = AppealStatus.RESOLVED
        self.appeal.save()
        
        pending_appeals = ModerationAppeal.objects.get_pending_appeals()
        self.assertNotIn(self.appeal, pending_appeals)
    
    def test_get_appeals_for_reviewer(self):
        """Test getting appeals for reviewer."""
        reviewer = User.objects.create_user(
            username="reviewer",
            email="reviewer@example.com",
            password="reviewerpass123",
            is_staff=True
        )
        
        # Assign appeal to reviewer
        self.appeal.assign_reviewer(reviewer)
        self.appeal.save()
        
        reviewer_appeals = ModerationAppeal.objects.get_appeals_for_reviewer(reviewer)
        self.assertIn(self.appeal, reviewer_appeals)
        
        # Test with different reviewer
        other_reviewer = User.objects.create_user(
            username="otherreviewer",
            email="other@example.com",
            password="otherpass123",
            is_staff=True
        )
        
        other_appeals = ModerationAppeal.objects.get_appeals_for_reviewer(other_reviewer)
        self.assertNotIn(self.appeal, other_appeals)
    
    def test_get_appeals_by_submission(self):
        """Test getting appeals by submission."""
        submission_appeals = ModerationAppeal.objects.get_appeals_by_submission(self.submission)
        self.assertIn(self.appeal, submission_appeals)
        
        # Test with different submission
        other_submission = SuspiciousSubmission.objects.create(
            content_id="other123",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.HUMAN_REJECTED
        )
        
        other_appeals = ModerationAppeal.objects.get_appeals_by_submission(other_submission)
        self.assertNotIn(self.appeal, other_appeals)


class AppealServiceTest(TestCase):
    """Test AppealService functionality."""
    
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
        self.reviewer = User.objects.create_user(
            username="reviewer",
            email="reviewer@example.com",
            password="reviewerpass123",
            is_staff=True
        )
        
        self.appeal_service = AppealService()
        
        self.submission = SuspiciousSubmission.objects.create(
            content_id="test123",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.HUMAN_REJECTED
        )
        
        self.decision = ModerationDecision.objects.create(
            submission=self.submission,
            decision_type=ModerationStatus.HUMAN_REJECTED,
            reason="Inappropriate content",
            confidence=0.9,
            decided_by=self.moderator,
            is_automated=False
        )
    
    def test_create_appeal_success(self):
        """Test successful appeal creation."""
        appeal = self.appeal_service.create_appeal(
            decision=self.decision,
            appellant=self.user,
            reason="I disagree with this decision",
            additional_data={"evidence": "screenshot.png"}
        )
        
        self.assertEqual(appeal.user, self.user)
        self.assertEqual(appeal.original_decision, self.decision)
        self.assertEqual(appeal.submission, self.submission)
        self.assertEqual(appeal.reason, "I disagree with this decision")
        self.assertEqual(appeal.additional_data, {"evidence": "screenshot.png"})
        self.assertEqual(appeal.status, AppealStatus.PENDING)
    
    def test_create_appeal_already_appealed(self):
        """Test creating appeal for already appealed decision."""
        # Create first appeal
        self.appeal_service.create_appeal(
            decision=self.decision,
            appellant=self.user,
            reason="First appeal"
        )
        
        # Try to create second appeal
        with self.assertRaises(AppealProcessingError):
            self.appeal_service.create_appeal(
                decision=self.decision,
                appellant=self.user,
                reason="Second appeal"
            )
    
    def test_create_appeal_decision_too_old(self):
        """Test creating appeal for old decision."""
        # Make decision old
        self.decision.decided_at = timezone.now() - timezone.timedelta(days=35)
        self.decision.save()
        
        with self.assertRaises(AppealProcessingError):
            self.appeal_service.create_appeal(
                decision=self.decision,
                appellant=self.user,
                reason="Late appeal"
            )
    
    def test_assign_reviewer_success(self):
        """Test successful reviewer assignment."""
        appeal = self.appeal_service.create_appeal(
            decision=self.decision,
            appellant=self.user,
            reason="Test appeal"
        )
        
        updated_appeal = self.appeal_service.assign_reviewer(
            appeal=appeal,
            reviewer=self.reviewer,
            assigned_by=self.moderator,
            notes="Assign to senior reviewer"
        )
        
        self.assertEqual(updated_appeal.reviewed_by, self.reviewer)
        self.assertEqual(updated_appeal.status, AppealStatus.UNDER_REVIEW)
        self.assertIn("Assign to senior reviewer", updated_appeal.review_notes)
        self.assertIsNotNone(updated_appeal.reviewed_at)
    
    def test_assign_reviewer_already_assigned(self):
        """Test assigning reviewer to already assigned appeal."""
        appeal = self.appeal_service.create_appeal(
            decision=self.decision,
            appellant=self.user,
            reason="Test appeal"
        )
        
        # First assignment
        appeal.assign_reviewer(self.reviewer)
        appeal.save()
        
        # Second assignment should fail
        with self.assertRaises(AppealProcessingError):
            self.appeal_service.assign_reviewer(
                appeal=appeal,
                reviewer=self.moderator,
                assigned_by=self.moderator
            )
    
    def test_resolve_appeal_success(self):
        """Test successful appeal resolution."""
        appeal = self.appeal_service.create_appeal(
            decision=self.decision,
            appellant=self.user,
            reason="Test appeal"
        )
        appeal.assign_reviewer(self.reviewer)
        appeal.save()
        
        updated_appeal = self.appeal_service.resolve_appeal(
            appeal=appeal,
            final_decision=AppealOutcome.OVERTURNED,
            final_reason="Evidence supports user",
            reviewer=self.reviewer,
            override_original=True
        )
        
        self.assertEqual(updated_appeal.final_outcome, AppealOutcome.OVERTURNED)
        self.assertEqual(updated_appeal.final_reason, "Evidence supports user")
        self.assertEqual(updated_appeal.status, AppealStatus.RESOLVED)
        self.assertIsNotNone(updated_appeal.resolved_at)
        
        # Check submission status was updated
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, ModerationStatus.HUMAN_APPROVED)
    
    def test_resolve_appeal_upheld(self):
        """Test resolving appeal with upheld decision."""
        appeal = self.appeal_service.create_appeal(
            decision=self.decision,
            appellant=self.user,
            reason="Test appeal"
        )
        appeal.assign_reviewer(self.reviewer)
        appeal.save()
        
        updated_appeal = self.appeal_service.resolve_appeal(
            appeal=appeal,
            final_decision=AppealOutcome.UPHELD,
            final_reason="Original decision correct",
            reviewer=self.reviewer,
            override_original=False
        )
        
        self.assertEqual(updated_appeal.final_outcome, AppealOutcome.UPHELD)
        
        # Check submission status remains rejected
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, ModerationStatus.HUMAN_REJECTED)
    
    def test_resolve_appeal_not_assigned(self):
        """Test resolving unassigned appeal."""
        appeal = self.appeal_service.create_appeal(
            decision=self.decision,
            appellant=self.user,
            reason="Test appeal"
        )
        
        with self.assertRaises(AppealProcessingError):
            self.appeal_service.resolve_appeal(
                appeal=appeal,
                final_decision=AppealOutcome.UPHELD,
                final_reason="Test resolution",
                reviewer=self.reviewer
            )
    
    def test_escalate_appeal_success(self):
        """Test successful appeal escalation."""
        senior_reviewer = User.objects.create_user(
            username="senior",
            email="senior@example.com",
            password="seniorpass123",
            is_staff=True
        )
        
        appeal = self.appeal_service.create_appeal(
            decision=self.decision,
            appellant=self.user,
            reason="Test appeal"
        )
        appeal.assign_reviewer(self.reviewer)
        appeal.save()
        
        updated_appeal = self.appeal_service.escalate_appeal(
            appeal=appeal,
            escalated_to=senior_reviewer,
            reason="Complex case needs senior review",
            escalated_by=self.moderator
        )
        
        self.assertEqual(updated_appeal.reviewed_by, senior_reviewer)
        self.assertEqual(updated_appeal.escalation_level, 1)
        self.assertIn("Complex case needs senior review", updated_appeal.review_notes)
    
    def test_get_pending_appeals(self):
        """Test getting pending appeals."""
        # Create multiple appeals
        appeals = []
        for i in range(3):
            decision = ModerationDecision.objects.create(
                submission=self.submission,
                decision_type=ModerationStatus.HUMAN_REJECTED,
                reason=f"Decision {i}",
                decided_by=self.moderator
            )
            
            appeal = self.appeal_service.create_appeal(
                decision=decision,
                appellant=self.user,
                reason=f"Appeal {i}"
            )
            appeals.append(appeal)
        
        pending_appeals = self.appeal_service.get_pending_appeals(
            reviewer=None,
            limit=10
        )
        
        self.assertEqual(len(pending_appeals), 3)
        for appeal in appeals:
            self.assertIn(appeal, pending_appeals)
    
    def test_get_pending_appeals_for_reviewer(self):
        """Test getting pending appeals for specific reviewer."""
        # Create appeals assigned to reviewer
        assigned_appeals = []
        for i in range(2):
            decision = ModerationDecision.objects.create(
                submission=self.submission,
                decision_type=ModerationStatus.HUMAN_REJECTED,
                reason=f"Decision {i}",
                decided_by=self.moderator
            )
            
            appeal = self.appeal_service.create_appeal(
                decision=decision,
                appellant=self.user,
                reason=f"Appeal {i}"
            )
            appeal.assign_reviewer(self.reviewer)
            appeal.save()
            assigned_appeals.append(appeal)
        
        reviewer_appeals = self.appeal_service.get_pending_appeals(
            reviewer=self.reviewer,
            limit=10
        )
        
        self.assertEqual(len(reviewer_appeals), 2)
        for appeal in assigned_appeals:
            self.assertIn(appeal, reviewer_appeals)
    
    def test_auto_assign_appeals(self):
        """Test auto-assigning appeals."""
        # Create multiple appeals
        appeals = []
        for i in range(5):
            decision = ModerationDecision.objects.create(
                submission=self.submission,
                decision_type=ModerationStatus.HUMAN_REJECTED,
                reason=f"Decision {i}",
                decided_by=self.moderator
            )
            
            appeal = self.appeal_service.create_appeal(
                decision=decision,
                appellant=self.user,
                reason=f"Appeal {i}"
            )
            appeals.append(appeal)
        
        results = self.appeal_service.auto_assign_appeals(
            batch_size=5,
            submission_type=SubmissionType.IMAGE
        )
        
        self.assertGreater(results["assigned"], 0)
        self.assertLessEqual(results["assigned"], 5)
        self.assertGreaterEqual(results["unassigned"], 0)
    
    def test_get_appeal_statistics(self):
        """Test appeal statistics retrieval."""
        # Create appeals with different statuses
        pending_appeal = self.appeal_service.create_appeal(
            decision=self.decision,
            appellant=self.user,
            reason="Pending appeal"
        )
        
        resolved_appeal = self.appeal_service.create_appeal(
            decision=ModerationDecision.objects.create(
                submission=self.submission,
                decision_type=ModerationStatus.HUMAN_REJECTED,
                reason="Another decision",
                decided_by=self.moderator
            ),
            appellant=self.user,
            reason="Resolved appeal"
        )
        resolved_appeal.assign_reviewer(self.reviewer)
        resolved_appeal.resolve(
            final_outcome=AppealOutcome.UPHELD,
            final_reason="Test resolution",
            reviewer=self.reviewer
        )
        resolved_appeal.save()
        
        stats = self.appeal_service.get_appeal_statistics()
        
        self.assertIn("total_appeals", stats)
        self.assertIn("status_breakdown", stats)
        self.assertIn("outcome_breakdown", stats)
        self.assertIn("by_submission_type", stats)
        self.assertIn("average_resolution_time", stats)
        self.assertIn("escalation_rate", stats)
        self.assertGreater(stats["total_appeals"], 0)
    
    def test_get_reviewer_workload(self):
        """Test getting reviewer workload."""
        # Create appeals assigned to reviewer
        for i in range(3):
            decision = ModerationDecision.objects.create(
                submission=self.submission,
                decision_type=ModerationStatus.HUMAN_REJECTED,
                reason=f"Decision {i}",
                decided_by=self.moderator
            )
            
            appeal = self.appeal_service.create_appeal(
                decision=decision,
                appellant=self.user,
                reason=f"Appeal {i}"
            )
            appeal.assign_reviewer(self.reviewer)
            appeal.save()
        
        workload = self.appeal_service.get_reviewer_workload(self.reviewer, days_back=7)
        
        self.assertEqual(workload["reviewer_id"], str(self.reviewer.pk))
        self.assertEqual(workload["reviewer_name"], self.reviewer.username)
        self.assertEqual(workload["total_assigned"], 3)
        self.assertIn("pending_count", workload)
        self.assertIn("resolved_count", workload)
        self.assertIn("average_resolution_time", workload)
    
    def test_get_appeal_history_for_submission(self):
        """Test getting appeal history for submission."""
        # Create multiple appeals for submission
        appeals = []
        for i in range(3):
            decision = ModerationDecision.objects.create(
                submission=self.submission,
                decision_type=ModerationStatus.HUMAN_REJECTED,
                reason=f"Decision {i}",
                decided_by=self.moderator
            )
            
            appeal = self.appeal_service.create_appeal(
                decision=decision,
                appellant=self.user,
                reason=f"Appeal {i}"
            )
            appeals.append(appeal)
        
        history = self.appeal_service.get_appeal_history_for_submission(self.submission)
        
        self.assertEqual(len(history), 3)
        for appeal in appeals:
            appeal_data = next((a for a in history if a["appeal_id"] == str(appeal.pk)), None)
            self.assertIsNotNone(appeal_data)
            self.assertEqual(appeal_data["reason"], appeal.reason)


class AppealAPITest(TestCase):
    """Test Appeal API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
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
        
        self.submission = SuspiciousSubmission.objects.create(
            content_id="test123",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.HUMAN_REJECTED
        )
        
        self.decision = ModerationDecision.objects.create(
            submission=self.submission,
            decision_type=ModerationStatus.HUMAN_REJECTED,
            reason="Inappropriate content",
            confidence=0.9,
            decided_by=self.moderator,
            is_automated=False
        )
        
        self.appeal = ModerationAppeal.objects.create(
            user=self.user,
            original_decision=self.decision,
            submission=self.submission,
            reason="I disagree with this decision",
            status=AppealStatus.PENDING
        )
    
    def test_list_appeals_unauthorized(self):
        """Test listing appeals without authentication."""
        response = self.client.get("/api/auto_mod/appeals/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_list_appeals_non_moderator(self):
        """Test listing appeals as non-moderator."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/auto_mod/appeals/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_list_appeals_moderator(self):
        """Test listing appeals as moderator."""
        self.client.force_authenticate(user=self.moderator)
        response = self.client.get("/api/auto_mod/appeals/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_create_appeal(self):
        """Test creating a new appeal."""
        self.client.force_authenticate(user=self.user)
        
        data = {
            "decision_id": str(self.decision.pk),
            "reason": "I disagree with this decision",
            "additional_data": {"evidence": "screenshot.png"}
        }
        
        response = self.client.post("/api/auto_mod/appeals/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ModerationAppeal.objects.count(), 2)
    
    def test_create_appeal_non_owner(self):
        """Test creating appeal as non-owner."""
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="otherpass123"
        )
        
        self.client.force_authenticate(user=other_user)
        
        data = {
            "decision_id": str(self.decision.pk),
            "reason": "I disagree with this decision"
        }
        
        response = self.client.post("/api/auto_mod/appeals/", data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_assign_reviewer(self):
        """Test assigning reviewer action."""
        self.client.force_authenticate(user=self.moderator)
        
        response = self.client.post(f"/api/auto_mod/appeals/{self.appeal.pk}/assign/", {
            "reviewer_id": str(self.moderator.pk),
            "notes": "Assign to moderator"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.appeal.refresh_from_db()
        self.assertEqual(self.appeal.reviewed_by, self.moderator)
        self.assertEqual(self.appeal.status, AppealStatus.UNDER_REVIEW)
    
    def test_resolve_appeal(self):
        """Test resolving appeal action."""
        self.client.force_authenticate(user=self.moderator)
        
        # First assign reviewer
        self.appeal.assign_reviewer(self.moderator)
        self.appeal.save()
        
        response = self.client.post(f"/api/auto_mod/appeals/{self.appeal.pk}/resolve/", {
            "final_decision": AppealOutcome.UPHELD,
            "final_reason": "Original decision stands",
            "override_original": False
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.appeal.refresh_from_db()
        self.assertEqual(self.appeal.final_outcome, AppealOutcome.UPHELD)
        self.assertEqual(self.appeal.status, AppealStatus.RESOLVED)
    
    def test_escalate_appeal(self):
        """Test escalating appeal action."""
        self.client.force_authenticate(user=self.moderator)
        
        senior_moderator = User.objects.create_user(
            username="senior",
            email="senior@example.com",
            password="seniorpass123",
            is_staff=True
        )
        
        response = self.client.post(f"/api/auto_mod/appeals/{self.appeal.pk}/escalate/", {
            "escalated_to_id": str(senior_moderator.pk),
            "reason": "Complex case needs senior review"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.appeal.refresh_from_db()
        self.assertEqual(self.appeal.reviewed_by, senior_moderator)
        self.assertEqual(self.appeal.escalation_level, 1)
    
    def test_my_appeals(self):
        """Test getting current user's appeals."""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get("/api/auto_mod/appeals/my-appeals/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_pending_appeals(self):
        """Test getting pending appeals."""
        self.client.force_authenticate(user=self.moderator)
        
        response = self.client.get("/api/auto_mod/appeals/pending/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_auto_assign_appeals(self):
        """Test auto-assign appeals endpoint."""
        self.client.force_authenticate(user=self.moderator)
        
        response = self.client.post("/api/auto_mod/appeals/auto-assign/", {
            "batch_size": 10,
            "submission_type": SubmissionType.IMAGE
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("assigned", response.data)
    
    def test_appeal_statistics(self):
        """Test appeal statistics endpoint."""
        self.client.force_authenticate(user=self.moderator)
        
        response = self.client.get("/api/auto_mod/appeals/statistics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_appeals", response.data)
    
    def test_reviewer_workload(self):
        """Test reviewer workload endpoint."""
        self.client.force_authenticate(user=self.moderator)
        
        response = self.client.get("/api/auto_mod/appeals/reviewer-workload/", {
            "days_back": 7
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
    
    def test_appeal_history(self):
        """Test appeal history endpoint."""
        self.client.force_authenticate(user=self.moderator)
        
        response = self.client.get(f"/api/auto_mod/appeals/{self.appeal.pk}/history/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, dict)


class AppealIntegrationTest(TestCase):
    """Test appeal integration with moderation workflow."""
    
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
        self.reviewer = User.objects.create_user(
            username="reviewer",
            email="reviewer@example.com",
            password="reviewerpass123",
            is_staff=True
        )
        
        self.appeal_service = AppealService()
        
        self.submission = SuspiciousSubmission.objects.create(
            content_id="integration_test",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.HUMAN_REJECTED
        )
    
    def test_full_appeal_workflow(self):
        """Test complete appeal workflow from creation to resolution."""
        # Create decision
        decision = ModerationDecision.objects.create(
            submission=self.submission,
            decision_type=ModerationStatus.HUMAN_REJECTED,
            reason="Inappropriate content",
            confidence=0.9,
            decided_by=self.moderator,
            is_automated=False
        )
        
        # Create appeal
        appeal = self.appeal_service.create_appeal(
            decision=decision,
            appellant=self.user,
            reason="I disagree with this decision"
        )
        
        # Assign reviewer
        assigned_appeal = self.appeal_service.assign_reviewer(
            appeal=appeal,
            reviewer=self.reviewer,
            assigned_by=self.moderator
        )
        
        # Resolve appeal
        resolved_appeal = self.appeal_service.resolve_appeal(
            appeal=assigned_appeal,
            final_decision=AppealOutcome.OVERTURNED,
            final_reason="Evidence supports user",
            reviewer=self.reviewer,
            override_original=True
        )
        
        # Verify workflow
        self.assertEqual(resolved_appeal.status, AppealStatus.RESOLVED)
        self.assertEqual(resolved_appeal.final_outcome, AppealOutcome.OVERTURNED)
        
        # Verify submission status updated
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, ModerationStatus.HUMAN_APPROVED)
    
    def test_appeal_escalation_workflow(self):
        """Test appeal escalation workflow."""
        # Create decision and appeal
        decision = ModerationDecision.objects.create(
            submission=self.submission,
            decision_type=ModerationStatus.HUMAN_REJECTED,
            reason="Complex case",
            decided_by=self.moderator
        )
        
        appeal = self.appeal_service.create_appeal(
            decision=decision,
            appellant=self.user,
            reason="Complex case needs review"
        )
        
        # Assign to junior reviewer
        appeal.assign_reviewer(self.reviewer)
        appeal.save()
        
        # Escalate to senior reviewer
        senior_reviewer = User.objects.create_user(
            username="senior",
            email="senior@example.com",
            password="seniorpass123",
            is_staff=True
        )
        
        escalated_appeal = self.appeal_service.escalate_appeal(
            appeal=appeal,
            escalated_to=senior_reviewer,
            reason="Complex case needs senior review",
            escalated_by=self.moderator
        )
        
        # Verify escalation
        self.assertEqual(escalated_appeal.reviewed_by, senior_reviewer)
        self.assertEqual(escalated_appeal.escalation_level, 1)
        self.assertIn("Complex case needs senior review", escalated_appeal.review_notes)
    
    def test_multiple_appeals_workflow(self):
        """Test multiple appeals for same submission."""
        # Create first decision and appeal
        decision1 = ModerationDecision.objects.create(
            submission=self.submission,
            decision_type=ModerationStatus.HUMAN_REJECTED,
            reason="First decision",
            decided_by=self.moderator
        )
        
        appeal1 = self.appeal_service.create_appeal(
            decision=decision1,
            appellant=self.user,
            reason="First appeal"
        )
        
        # Resolve first appeal (upheld)
        appeal1.assign_reviewer(self.reviewer)
        appeal1.resolve(
            final_outcome=AppealOutcome.UPHELD,
            final_reason="First decision correct",
            reviewer=self.reviewer
        )
        appeal1.save()
        
        # Create new decision and second appeal
        decision2 = ModerationDecision.objects.create(
            submission=self.submission,
            decision_type=ModerationStatus.HUMAN_REJECTED,
            reason="Second decision",
            decided_by=self.moderator
        )
        
        appeal2 = self.appeal_service.create_appeal(
            decision=decision2,
            appellant=self.user,
            reason="Second appeal"
        )
        
        # Verify both appeals exist
        appeals = ModerationAppeal.objects.filter(submission=self.submission)
        self.assertEqual(appeals.count(), 2)
        
        # Verify appeal history
        history = self.appeal_service.get_appeal_history_for_submission(self.submission)
        self.assertEqual(len(history), 2)
    
    def test_appeal_performance_monitoring(self):
        """Test appeal performance monitoring."""
        import time
        
        # Create multiple appeals
        appeals = []
        start_time = timezone.now()
        
        for i in range(5):
            decision = ModerationDecision.objects.create(
                submission=self.submission,
                decision_type=ModerationStatus.HUMAN_REJECTED,
                reason=f"Decision {i}",
                decided_by=self.moderator
            )
            
            appeal = self.appeal_service.create_appeal(
                decision=decision,
                appellant=self.user,
                reason=f"Appeal {i}"
            )
            
            # Assign and resolve
            appeal.assign_reviewer(self.reviewer)
            appeal.resolve(
                final_outcome=AppealOutcome.UPHELD,
                final_reason="Test resolution",
                reviewer=self.reviewer
            )
            appeal.save()
            
            appeals.append(appeal)
        
        end_time = timezone.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Get statistics
        stats = self.appeal_service.get_appeal_statistics()
        
        self.assertIn("average_resolution_time", stats)
        self.assertGreater(stats["total_appeals"], 0)
        self.assertLess(processing_time, 10.0)  # Should complete within 10 seconds


class AppealSignalTest(TestCase):
    """Test appeal signal handling."""
    
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
        self.reviewer = User.objects.create_user(
            username="reviewer",
            email="reviewer@example.com",
            password="reviewerpass123",
            is_staff=True
        )
        
        self.appeal_service = AppealService()
        
        self.submission = SuspiciousSubmission.objects.create(
            content_id="signal_test",
            submission_type=SubmissionType.IMAGE,
            user=self.user,
            status=ModerationStatus.HUMAN_REJECTED
        )
    
    @patch('api.auto_mod.signals.appeal_created')
    def test_appeal_created_signal(self, mock_signal):
        """Test appeal created signal."""
        decision = ModerationDecision.objects.create(
            submission=self.submission,
            decision_type=ModerationStatus.HUMAN_REJECTED,
            reason="Test decision",
            decided_by=self.moderator
        )
        
        appeal = self.appeal_service.create_appeal(
            decision=decision,
            appellant=self.user,
            reason="Test appeal"
        )
        
        # Verify signal was sent
        mock_signal.assert_called_once()
        call_args = mock_signal.call_args[1]
        self.assertEqual(call_args['appeal'], appeal)
        self.assertEqual(call_args['original_decision'], decision)
        self.assertEqual(call_args['appellant'], self.user)
    
    @patch('api.auto_mod.signals.appeal_assigned')
    def test_appeal_assigned_signal(self, mock_signal):
        """Test appeal assigned signal."""
        decision = ModerationDecision.objects.create(
            submission=self.submission,
            decision_type=ModerationStatus.HUMAN_REJECTED,
            reason="Test decision",
            decided_by=self.moderator
        )
        
        appeal = self.appeal_service.create_appeal(
            decision=decision,
            appellant=self.user,
            reason="Test appeal"
        )
        
        self.appeal_service.assign_reviewer(
            appeal=appeal,
            reviewer=self.reviewer,
            assigned_by=self.moderator
        )
        
        # Verify signal was sent
        mock_signal.assert_called_once()
        call_args = mock_signal.call_args[1]
        self.assertEqual(call_args['appeal'], appeal)
        self.assertEqual(call_args['reviewer'], self.reviewer)
        self.assertEqual(call_args['assigned_by'], self.moderator)
    
    @patch('api.auto_mod.signals.appeal_resolved')
    def test_appeal_resolved_signal(self, mock_signal):
        """Test appeal resolved signal."""
        decision = ModerationDecision.objects.create(
            submission=self.submission,
            decision_type=ModerationStatus.HUMAN_REJECTED,
            reason="Test decision",
            decided_by=self.moderator
        )
        
        appeal = self.appeal_service.create_appeal(
            decision=decision,
            appellant=self.user,
            reason="Test appeal"
        )
        appeal.assign_reviewer(self.reviewer)
        appeal.save()
        
        self.appeal_service.resolve_appeal(
            appeal=appeal,
            final_decision=AppealOutcome.UPHELD,
            final_reason="Test resolution",
            reviewer=self.reviewer
        )
        
        # Verify signal was sent
        mock_signal.assert_called_once()
        call_args = mock_signal.call_args[1]
        self.assertEqual(call_args['appeal'], appeal)
        self.assertEqual(call_args['final_decision'], AppealOutcome.UPHELD)
        self.assertEqual(call_args['reviewer'], self.reviewer)
