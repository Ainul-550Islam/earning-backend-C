# =============================================================================
# fraud_detection/tests/test_fraud_case.py
# =============================================================================
"""
Fraud Case Tests.

Comprehensive tests for fraud case management including
case creation, workflow, evidence handling, and resolution.
"""

import json
import pytest
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User

from api.fraud_detection.models import FraudCase, FraudCaseEvidence, FraudCaseAction, FraudAlert
from api.fraud_detection.choices import CaseStatus, EvidenceType, AlertPriority
from .factories import (
    UserFactory, FraudCaseFactory, FraudCaseEvidenceFactory,
    FraudCaseActionFactory, FraudAlertFactory
)


class TestFraudCase(TestCase):
    """Test cases for FraudCase model and management."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory.create()
        self.staff_user = UserFactory.create(is_staff=True)
        
    def test_fraud_case_creation(self):
        """Test basic fraud case creation."""
        case = FraudCaseFactory.create(
            user=self.user,
            title="Test fraud case",
            description="Test description",
            risk_score=75,
            priority="high"
        )
        
        self.assertIsInstance(case, FraudCase)
        self.assertEqual(case.user, self.user)
        self.assertEqual(case.title, "Test fraud case")
        self.assertEqual(case.risk_score, 75)
        self.assertEqual(case.priority, "high")
        self.assertEqual(case.status, CaseStatus.OPEN)
        self.assertIsNotNone(case.case_number)
        self.assertIsNotnull(case.opened_at)
    
    def test_case_number_generation(self):
        """Test unique case number generation."""
        cases = FraudCaseFactory.create_batch(5, user=self.user)
        
        case_numbers = [case.case_number for case in cases]
        
        # All case numbers should be unique
        self.assertEqual(len(set(case_numbers)), len(case_numbers))
        
        # All should follow the expected format
        for case_number in case_numbers:
            self.assertRegex(case_number, r'^FC-\d{8}-\d{3}$')
    
    def test_case_priority_validation(self):
        """Test case priority validation."""
        case = FraudCaseFactory.create(
            user=self.user,
            risk_score=85,
            priority="critical"
        )
        
        # High risk score should match critical priority
        self.assertEqual(case.priority, "critical")
        self.assertGreaterEqual(case.risk_score, 80)
    
    def test_case_status_transitions(self):
        """Test valid case status transitions."""
        case = FraudCaseFactory.create(
            user=self.user,
            status=CaseStatus.OPEN
        )
        
        # Valid transition: OPEN -> INVESTIGATING
        case.status = CaseStatus.INVESTIGATING
        case.save()
        
        self.assertEqual(case.status, CaseStatus.INVESTIGATING)
        
        # Valid transition: INVESTIGATING -> RESOLVED
        case.status = CaseStatus.RESOLVED
        case.resolved_at = timezone.now()
        case.save()
        
        self.assertEqual(case.status, CaseStatus.RESOLVED)
        self.assertIsNotnull(case.resolved_at)
    
    def test_case_evidence_addition(self):
        """Test adding evidence to fraud case."""
        case = FraudCaseFactory.create(user=self.user)
        
        evidence = FraudCaseEvidenceFactory.create(
            fraud_case=case,
            evidence_type=EvidenceType.LOG_DATA,
            data=json.dumps({"test": "data"}),
            added_by="Test User"
        )
        
        self.assertEqual(evidence.fraud_case, case)
        self.assertEqual(evidence.evidence_type, EvidenceType.LOG_DATA)
        self.assertEqual(evidence.added_by, "Test User")
        
        # Verify case has evidence
        self.assertEqual(case.evidence.count(), 1)
    
    def test_case_action_creation(self):
        """Test creating actions for fraud case."""
        case = FraudCaseFactory.create(user=self.user)
        
        action = FraudCaseActionFactory.create(
            fraud_case=case,
            action_type="investigate",
            note="Started investigation",
            performed_by=self.staff_user
        )
        
        self.assertEqual(action.fraud_case, case)
        self.assertEqual(action.action_type, "investigate")
        self.assertEqual(action.performed_by, self.staff_user)
        
        # Verify case has action
        self.assertEqual(case.actions.count(), 1)
    
    def test_case_assignment(self):
        """Test case assignment to staff."""
        case = FraudCaseFactory.create(user=self.user)
        
        case.assigned_to = self.staff_user
        case.save()
        
        self.assertEqual(case.assigned_to, self.staff_user)
        
        # Create assignment action
        action = FraudCaseActionFactory.create(
            fraud_case=case,
            action_type="assign",
            note=f"Assigned to {self.staff_user.username}",
            performed_by=self.staff_user,
            is_completed=True
        )
        
        self.assertEqual(action.action_type, "assign")
        self.assertTrue(action.is_completed)
    
    def test_case_resolution(self):
        """Test case resolution."""
        case = FraudCaseFactory.create(
            user=self.user,
            status=CaseStatus.INVESTIGATING
        )
        
        # Resolve the case
        case.status = CaseStatus.RESOLVED
        case.resolved_by = self.staff_user
        case.resolved_at = timezone.now()
        case.resolution_notes = "Case resolved after investigation"
        case.save()
        
        self.assertEqual(case.status, CaseStatus.RESOLVED)
        self.assertEqual(case.resolved_by, self.staff_user)
        self.assertIsNotnull(case.resolved_at)
        self.assertEqual(case.resolution_notes, "Case resolved after investigation")
        
        # Create resolution action
        action = FraudCaseActionFactory.create(
            fraud_case=case,
            action_type="resolve",
            note="Case resolved",
            performed_by=self.staff_user,
            is_completed=True,
            completed_at=timezone.now()
        )
        
        self.assertEqual(action.action_type, "resolve")
        self.assertTrue(action.is_completed)
    
    def test_case_escalation(self):
        """Test case escalation."""
        case = FraudCaseFactory.create(
            user=self.user,
            priority="high"
        )
        
        # Escalate to critical
        case.priority = "critical"
        case.save()
        
        self.assertEqual(case.priority, "critical")
        
        # Create escalation action
        action = FraudCaseActionFactory.create(
            fraud_case=case,
            action_type="escalate",
            note="Escalated to critical priority",
            performed_by=self.staff_user
        )
        
        self.assertEqual(action.action_type, "escalate")
    
    def test_case_reopening(self):
        """Test reopening resolved cases."""
        case = FraudCaseFactory.create(
            user=self.user,
            status=CaseStatus.RESOLVED,
            resolved_by=self.staff_user,
            resolved_at=timezone.now() - timedelta(days=1)
        )
        
        # Reopen the case
        case.status = CaseStatus.OPEN
        case.resolved_by = None
        case.resolved_at = None
        case.save()
        
        self.assertEqual(case.status, CaseStatus.OPEN)
        self.assertIsNone(case.resolved_by)
        self.assertIsNone(case.resolved_at)
        
        # Create reopen action
        action = FraudCaseActionFactory.create(
            fraud_case=case,
            action_type="reopen",
            note="Case reopened due to new evidence",
            performed_by=self.staff_user
        )
        
        self.assertEqual(action.action_type, "reopen")
    
    def test_case_evidence_validation(self):
        """Test evidence data validation."""
        case = FraudCaseFactory.create(user=self.user)
        
        # Valid JSON evidence
        valid_evidence = FraudCaseEvidenceFactory.create(
            fraud_case=case,
            evidence_type=EvidenceType.SCREENSHOT,
            data=json.dumps({"url": "https://example.com", "timestamp": "2024-01-01"}),
            added_by="System"
        )
        
        self.assertIsInstance(valid_evidence, FraudCaseEvidence)
        json.loads(valid_evidence.data)  # Should not raise exception
        
        # Invalid JSON evidence
        with self.assertRaises(Exception):
            FraudCaseEvidenceFactory.create(
                fraud_case=case,
                evidence_type=EvidenceType.LOG_DATA,
                data="invalid json",
                added_by="System"
            )
    
    def test_case_action_completion(self):
        """Test action completion tracking."""
        case = FraudCaseFactory.create(user=self.user)
        
        # Create incomplete action
        action = FraudCaseActionFactory.create(
            fraud_case=case,
            action_type="investigate",
            note="Investigation in progress",
            performed_by=self.staff_user,
            is_completed=False
        )
        
        self.assertFalse(action.is_completed)
        self.assertIsNone(action.completed_at)
        
        # Complete the action
        action.is_completed = True
        action.completed_at = timezone.now()
        action.save()
        
        self.assertTrue(action.is_completed)
        self.assertIsNotnull(action.completed_at)
    
    def test_case_metadata_handling(self):
        """Test case metadata storage and retrieval."""
        case = FraudCaseFactory.create(user=self.user)
        
        # Add metadata
        metadata = {
            "source_system": "fraud_detector",
            "auto_generated": True,
            "severity_score": 85
        }
        
        case.metadata = metadata
        case.save()
        
        # Retrieve metadata
        case.refresh_from_db()
        self.assertEqual(case.metadata, metadata)
        self.assertTrue(case.metadata["auto_generated"])
        self.assertEqual(case.metadata["severity_score"], 85)
    
    def test_case_hash_integrity(self):
        """Test case hash integrity verification."""
        case = FraudCaseFactory.create(user=self.user)
        
        # Case should have integrity hash
        self.assertIsNotNone(case.integrity_hash)
        self.assertEqual(len(case.integrity_hash), 64)  # SHA-256
        
        # Previous hash should be None for new case
        self.assertIsNone(case.previous_hash)
        
        # Modify case and verify hash changes
        original_hash = case.integrity_hash
        case.description = "Updated description"
        case.save()
        
        self.assertNotEqual(case.integrity_hash, original_hash)
        self.assertEqual(case.previous_hash, original_hash)
    
    def test_case_evidence_hash_integrity(self):
        """Test evidence hash integrity verification."""
        case = FraudCaseFactory.create(user=self.user)
        
        evidence = FraudCaseEvidenceFactory.create(
            fraud_case=case,
            evidence_type=EvidenceType.LOG_DATA,
            data=json.dumps({"test": "data"}),
            added_by="System"
        )
        
        # Evidence should have integrity hash
        self.assertIsNotNone(evidence.integrity_hash)
        self.assertEqual(len(evidence.integrity_hash), 64)
        
        # Previous hash should be None for new evidence
        self.assertIsNone(evidence.previous_hash)
    
    def test_case_action_hash_integrity(self):
        """Test action hash integrity verification."""
        case = FraudCaseFactory.create(user=self.user)
        
        action = FraudCaseActionFactory.create(
            fraud_case=case,
            action_type="investigate",
            note="Test action",
            performed_by=self.staff_user
        )
        
        # Action should have integrity hash
        self.assertIsNotNone(action.integrity_hash)
        self.assertEqual(len(action.integrity_hash), 64)
        
        # Previous hash should be None for new action
        self.assertIsNone(action.previous_hash)
    
    def test_case_search_functionality(self):
        """Test case search and filtering."""
        # Create cases with different attributes
        FraudCaseFactory.create(
            user=self.user,
            title="Suspicious login activity",
            priority="high",
            status=CaseStatus.OPEN
        )
        
        FraudCaseFactory.create(
            user=UserFactory.create(),
            title="Fraudulent transaction",
            priority="critical",
            status=CaseStatus.INVESTIGATING
        )
        
        FraudCaseFactory.create(
            user=UserFactory.create(),
            title="False positive",
            priority="low",
            status=CaseStatus.RESOLVED
        )
        
        # Search by title
        suspicious_cases = FraudCase.objects.filter(title__icontains="suspicious")
        self.assertEqual(suspicious_cases.count(), 1)
        
        # Filter by priority
        critical_cases = FraudCase.objects.filter(priority="critical")
        self.assertEqual(critical_cases.count(), 1)
        
        # Filter by status
        open_cases = FraudCase.objects.filter(status=CaseStatus.OPEN)
        self.assertEqual(open_cases.count(), 1)
    
    def test_case_ordering(self):
        """Test case ordering and sorting."""
        # Create cases with different priorities and dates
        old_case = FraudCaseFactory.create(
            user=self.user,
            priority="low",
            opened_at=timezone.now() - timedelta(days=5)
        )
        
        recent_case = FraudCaseFactory.create(
            user=UserFactory.create(),
            priority="critical",
            opened_at=timezone.now() - timedelta(days=1)
        )
        
        # Order by priority (descending)
        cases_by_priority = FraudCase.objects.order_by('-priority')
        self.assertEqual(cases_by_priority.first().priority, "critical")
        
        # Order by opened_at (descending)
        cases_by_date = FraudCase.objects.order_by('-opened_at')
        self.assertEqual(cases_by_date.first().opened_at, recent_case.opened_at)
    
    def test_case_statistics_calculation(self):
        """Test case statistics calculation."""
        # Create cases with different statuses and priorities
        FraudCaseFactory.create_batch(
            3,
            status=CaseStatus.OPEN,
            priority="high"
        )
        
        FraudCaseFactory.create_batch(
            2,
            status=CaseStatus.RESOLVED,
            priority="medium"
        )
        
        FraudCaseFactory.create_batch(
            1,
            status=CaseStatus.INVESTIGATING,
            priority="critical"
        )
        
        # Calculate statistics
        total_cases = FraudCase.objects.count()
        open_cases = FraudCase.objects.filter(status=CaseStatus.OPEN).count()
        resolved_cases = FraudCase.objects.filter(status=CaseStatus.RESOLVED).count()
        critical_cases = FraudCase.objects.filter(priority="critical").count()
        
        self.assertEqual(total_cases, 6)
        self.assertEqual(open_cases, 3)
        self.assertEqual(resolved_cases, 2)
        self.assertEqual(critical_cases, 1)
    
    def test_case_user_relationship(self):
        """Test case relationship with user."""
        case = FraudCaseFactory.create(user=self.user)
        
        # Test forward relationship
        self.assertEqual(case.user, self.user)
        
        # Test reverse relationship
        user_cases = self.user.fraud_cases.all()
        self.assertIn(case, user_cases)
        
        # Create multiple cases for user
        FraudCaseFactory.create_batch(
            3,
            user=self.user
        )
        
        self.assertEqual(self.user.fraud_cases.count(), 4)
    
    def test_case_evidence_relationship(self):
        """Test case relationship with evidence."""
        case = FraudCaseFactory.create(user=self.user)
        
        # Add multiple evidence items
        evidence_items = FraudCaseEvidenceFactory.create_batch(
            3,
            fraud_case=case
        )
        
        # Test forward relationship
        self.assertEqual(case.evidence.count(), 3)
        self.assertIn(evidence_items[0], case.evidence.all())
        
        # Test reverse relationship
        for evidence in evidence_items:
            self.assertEqual(evidence.fraud_case, case)
    
    def test_case_action_relationship(self):
        """Test case relationship with actions."""
        case = FraudCaseFactory.create(user=self.user)
        
        # Add multiple actions
        actions = FraudCaseActionFactory.create_batch(
            3,
            fraud_case=case,
            performed_by=self.staff_user
        )
        
        # Test forward relationship
        self.assertEqual(case.actions.count(), 3)
        self.assertIn(actions[0], case.actions.all())
        
        # Test reverse relationship
        for action in actions:
            self.assertEqual(action.fraud_case, case)
    
    def test_case_str_representation(self):
        """Test case string representation."""
        case = FraudCaseFactory.create(
            user=self.user,
            title="Test Case",
            case_number="FC-20240101-001"
        )
        
        expected_str = f"FC-20240101-001 - Test Case"
        self.assertEqual(str(case), expected_str)
    
    def test_case_absolute_url(self):
        """Test case absolute URL generation."""
        case = FraudCaseFactory.create(user=self.user)
        
        url = case.get_absolute_url()
        
        self.assertIsInstance(url, str)
        self.assertIn(f"/{case.id}/", url)
    
    def test_case_age_calculation(self):
        """Test case age calculation."""
        created_time = timezone.now() - timedelta(days=3, hours=5)
        case = FraudCaseFactory.create(
            user=self.user,
            opened_at=created_time
        )
        
        # Test age calculation (implementation dependent)
        if hasattr(case, 'get_age'):
            age = case.get_age()
            self.assertIsInstance(age, timedelta)
            self.assertGreaterEqual(age, timedelta(days=3))
    
    def test_case_duration_calculation(self):
        """Test case duration calculation for resolved cases."""
        opened_time = timezone.now() - timedelta(days=2, hours=3)
        resolved_time = timezone.now() - timedelta(hours=5)
        
        case = FraudCaseFactory.create(
            user=self.user,
            opened_at=opened_time,
            status=CaseStatus.RESOLVED,
            resolved_at=resolved_time
        )
        
        # Test duration calculation (implementation dependent)
        if hasattr(case, 'get_duration'):
            duration = case.get_duration()
            self.assertIsInstance(duration, timedelta)
            self.assertGreaterEqual(duration, timedelta(days=2))
    
    def test_case_bulk_operations(self):
        """Test bulk case operations."""
        # Create multiple cases
        cases = FraudCaseFactory.create_batch(
            5,
            user=self.user,
            status=CaseStatus.OPEN
        )
        
        # Bulk update status
        updated_count = FraudCase.objects.filter(
            id__in=[case.id for case in cases]
        ).update(status=CaseStatus.INVESTIGATING)
        
        self.assertEqual(updated_count, 5)
        
        # Verify updates
        for case in cases:
            case.refresh_from_db()
            self.assertEqual(case.status, CaseStatus.INVESTIGATING)
    
    def test_case_soft_delete_behavior(self):
        """Test case soft delete behavior (if implemented)."""
        case = FraudCaseFactory.create(user=self.user)
        
        # Test if soft delete is implemented
        if hasattr(case, 'is_deleted'):
            # Soft delete
            case.is_deleted = True
            case.save()
            
            # Should not appear in default queryset
            active_cases = FraudCase.objects.filter(is_deleted=False)
            self.assertNotIn(case, active_cases)
            
            # Should appear in all records
            all_cases = FraudCase.objects.all()
            self.assertIn(case, all_cases)


class TestFraudCaseIntegration(TestCase):
    """Integration tests for FraudCase model."""
    
    def setUp(self):
        """Set up integration test data."""
        self.user = UserFactory.create()
        self.staff_user = UserFactory.create(is_staff=True)
    
    def test_complete_case_lifecycle(self):
        """Test complete case lifecycle from creation to resolution."""
        # Create initial case
        case = FraudCaseFactory.create(
            user=self.user,
            title="Complete lifecycle test",
            description="Testing complete case workflow",
            risk_score=75,
            priority="high"
        )
        
        self.assertEqual(case.status, CaseStatus.OPEN)
        self.assertEqual(case.priority, "high")
        
        # Add evidence
        evidence1 = FraudCaseEvidenceFactory.create(
            fraud_case=case,
            evidence_type=EvidenceType.LOG_DATA,
            data=json.dumps({"event": "suspicious_login"}),
            added_by="System"
        )
        
        evidence2 = FraudCaseEvidenceFactory.create(
            fraud_case=case,
            evidence_type=EvidenceType.SCREENSHOT,
            data=json.dumps({"screenshot": "evidence.png"}),
            added_by="Investigator"
        )
        
        self.assertEqual(case.evidence.count(), 2)
        
        # Create investigation action
        investigate_action = FraudCaseActionFactory.create(
            fraud_case=case,
            action_type="investigate",
            note="Started investigation",
            performed_by=self.staff_user,
            is_completed=False
        )
        
        # Assign case
        case.assigned_to = self.staff_user
        case.save()
        
        assign_action = FraudCaseActionFactory.create(
            fraud_case=case,
            action_type="assign",
            note=f"Assigned to {self.staff_user.username}",
            performed_by=self.staff_user,
            is_completed=True
        )
        
        # Complete investigation
        investigate_action.is_completed = True
        investigate_action.completed_at = timezone.now()
        investigate_action.save()
        
        # Add more evidence during investigation
        investigation_evidence = FraudCaseEvidenceFactory.create(
            fraud_case=case,
            evidence_type=EvidenceType.USER_REPORT,
            data=json.dumps({"report": "User confirmed suspicious activity"}),
            added_by="User"
        )
        
        self.assertEqual(case.evidence.count(), 3)
        
        # Resolve case
        case.status = CaseStatus.RESOLVED
        case.resolved_by = self.staff_user
        case.resolved_at = timezone.now()
        case.resolution_notes = "Case resolved with confirmed fraud"
        case.save()
        
        resolve_action = FraudCaseActionFactory.create(
            fraud_case=case,
            action_type="resolve",
            note="Case resolved - confirmed fraud activity",
            performed_by=self.staff_user,
            is_completed=True,
            completed_at=timezone.now()
        )
        
        # Verify final state
        self.assertEqual(case.status, CaseStatus.RESOLVED)
        self.assertEqual(case.resolved_by, self.staff_user)
        self.assertIsNotnull(case.resolved_at)
        self.assertEqual(case.resolution_notes, "Case resolved with confirmed fraud")
        
        # Verify all actions are present
        self.assertEqual(case.actions.count(), 4)  # create, assign, investigate, resolve
        
        # Verify action sequence
        actions = case.actions.order_by('created_at')
        action_types = [action.action_type for action in actions]
        self.assertIn('create', action_types)
        self.assertIn('assign', action_types)
        self.assertIn('investigate', action_types)
        self.assertIn('resolve', action_types)
        
        # Verify evidence completeness
        evidence_types = [ev.evidence_type for ev in case.evidence.all()]
        self.assertIn(EvidenceType.LOG_DATA, evidence_types)
        self.assertIn(EvidenceType.SCREENSHOT, evidence_types)
        self.assertIn(EvidenceType.USER_REPORT, evidence_types)
    
    def test_case_with_alert_integration(self):
        """Test case integration with fraud alerts."""
        # Create fraud alerts
        alerts = FraudAlertFactory.create_batch(
            3,
            user=self.user,
            priority=AlertPriority.HIGH,
            is_resolved=False
        )
        
        # Create case linked to alerts
        case = FraudCaseFactory.create(
            user=self.user,
            title="Alert-based investigation",
            description="Case created from multiple high-priority alerts"
        )
        
        # Link alerts to case
        for alert in alerts:
            case.fraud_alerts.add(alert)
        
        self.assertEqual(case.fraud_alerts.count(), 3)
        
        # Verify alerts are accessible
        case_alerts = case.fraud_alerts.all()
        for alert in alerts:
            self.assertIn(alert, case_alerts)
        
        # Resolve case and update alerts
        case.status = CaseStatus.RESOLVED
        case.resolved_by = self.staff_user
        case.resolved_at = timezone.now()
        case.save()
        
        # Update related alerts
        case.fraud_alerts.update(is_resolved=True)
        
        self.assertEqual(case.fraud_alerts.filter(is_resolved=True).count(), 3)
    
    def test_case_collaboration_workflow(self):
        """Test case collaboration between multiple staff members."""
        # Create multiple staff members
        investigator = UserFactory.create(is_staff=True)
        senior_analyst = UserFactory.create(is_staff=True)
        
        # Create case
        case = FraudCaseFactory.create(
            user=self.user,
            title="Collaborative investigation",
            priority="critical"
        )
        
        # Initial assignment
        case.assigned_to = investigator
        case.save()
        
        # Investigator adds evidence and notes
        FraudCaseEvidenceFactory.create(
            fraud_case=case,
            evidence_type=EvidenceType.TECHNICAL_ANALYSIS,
            data=json.dumps({"analysis": "complex pattern detected"}),
            added_by=investigator.username
        )
        
        FraudCaseActionFactory.create(
            fraud_case=case,
            action_type="investigate",
            note="Technical analysis shows sophisticated fraud pattern",
            performed_by=investigator
        )
        
        # Escalate to senior analyst
        case.assigned_to = senior_analyst
        case.priority = "critical"
        case.save()
        
        FraudCaseActionFactory.create(
            fraud_case=case,
            action_type="escalate",
            note="Escalated to senior analyst for complex pattern review",
            performed_by=investigator
        )
        
        # Senior analyst completes review
        FraudCaseActionFactory.create(
            fraud_case=case,
            action_type="review",
            note="Senior review confirms sophisticated fraud operation",
            performed_by=senior_analyst
        )
        
        # Final resolution
        case.status = CaseStatus.RESOLVED
        case.resolved_by = senior_analyst
        case.resolved_at = timezone.now()
        case.save()
        
        FraudCaseActionFactory.create(
            fraud_case=case,
            action_type="resolve",
            note="Case resolved - coordinated investigation completed",
            performed_by=senior_analyst,
            is_completed=True,
            completed_at=timezone.now()
        )
        
        # Verify collaboration history
        actions = case.actions.order_by('created_at')
        collaborators = set(action.performed_by for action in actions)
        
        self.assertIn(investigator, collaborators)
        self.assertIn(senior_analyst, collaborators)
        
        # Verify workflow sequence
        action_sequence = [action.action_type for action in actions]
        self.assertIn('investigate', action_sequence)
        self.assertIn('escalate', action_sequence)
        self.assertIn('review', action_sequence)
        self.assertIn('resolve', action_sequence)


if __name__ == '__main__':
    import random
    
    # Add random import for integration tests
    TestFraudCaseIntegration.setUp = lambda self: (
        setattr(self, 'user', UserFactory.create()) or
        setattr(self, 'staff_user', UserFactory.create(is_staff=True))
    )
