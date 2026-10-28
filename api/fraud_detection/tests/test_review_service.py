# =============================================================================
# fraud_detection/tests/test_review_service.py
# =============================================================================
"""
Review Service Tests.

Comprehensive tests for fraud review service including
case management, review workflows, and decision tracking.
"""

import json
import pytest
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User

from api.fraud_detection.services.ReviewService import ReviewService
from api.fraud_detection.models import FraudCase, FraudCaseAction, FraudAlert, UserRiskProfile
from api.fraud_detection.choices import CaseStatus, EvidenceType
from .factories import (
    UserFactory, FraudCaseFactory, FraudCaseActionFactory,
    FraudAlertFactory, UserRiskProfileFactory
)


class TestReviewService(TestCase):
    """Test cases for ReviewService."""
    
    def setUp(self):
        """Set up test data."""
        self.review_service = ReviewService()
        self.user = UserFactory.create()
        self.staff_user = UserFactory.create(is_staff=True)
        self.reviewer = UserFactory.create(is_staff=True)
        
    def test_create_review_case(self):
        """Test creation of review cases."""
        case_data = {
            'user_id': self.user.id,
            'title': 'Suspicious activity review',
            'description': 'User showing unusual patterns',
            'priority': 'high',
            'evidence': [
                {
                    'type': 'fraud_attempt',
                    'data': {'attempt_id': 'attempt_123', 'score': 85},
                    'description': 'High fraud score detected'
                }
            ]
        }
        
        case = self.review_service.create_review_case(case_data, created_by=self.staff_user.id)
        
        self.assertIsInstance(case, FraudCase)
        self.assertEqual(case.user, self.user)
        self.assertEqual(case.title, case_data['title'])
        self.assertEqual(case.priority, case_data['priority'])
        self.assertEqual(case.status, CaseStatus.OPEN)
        self.assertEqual(case.assigned_to, self.staff_user)
        
        # Check evidence was added
        self.assertEqual(case.evidence.count(), 1)
        
        # Check initial action was created
        self.assertEqual(case.actions.count(), 1)
        initial_action = case.actions.first()
        self.assertEqual(initial_action.action_type, 'create')
    
    def test_assign_review_case(self):
        """Test review case assignment."""
        # Create a case
        case = FraudCaseFactory.create(
            user=self.user,
            assigned_to=self.staff_user
        )
        
        # Assign to different reviewer
        result = self.review_service.assign_review_case(
            case.id,
            self.reviewer.id,
            assignment_reason="Reassigning to specialist",
            assigned_by=self.staff_user.id
        )
        
        self.assertTrue(result['success'])
        
        # Verify assignment
        case.refresh_from_db()
        self.assertEqual(case.assigned_to, self.reviewer)
        
        # Check assignment action was created
        assignment_action = case.actions.filter(action_type='assign').first()
        self.assertIsNotNone(assignment_action)
        self.assertEqual(assignment_action.performed_by, self.staff_user)
    
    def test_review_case_approval(self):
        """Test case review approval."""
        # Create a case
        case = FraudCaseFactory.create(
            user=self.user,
            assigned_to=self.reviewer,
            status=CaseStatus.INVESTIGATING
        )
        
        review_data = {
            'decision': 'confirmed_fraud',
            'reason': 'Clear evidence of fraudulent activity',
            'risk_score': 85,
            'recommendations': ['ban_user', 'freeze_accounts'],
            'evidence_review': {
                'evidence_1': {'verified': True, 'weight': 'high'},
                'evidence_2': {'verified': False, 'weight': 'low'},
            }
        }
        
        result = self.review_service.review_case(
            case.id,
            review_data,
            reviewed_by=self.reviewer.id
        )
        
        self.assertTrue(result['success'])
        
        # Verify case status
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.RESOLVED)
        self.assertEqual(case.resolved_by, self.reviewer)
        self.assertIsNotNone(case.resolved_at)
        
        # Check review action was created
        review_action = case.actions.filter(action_type='resolve').first()
        self.assertIsNotNone(review_action)
        self.assertEqual(review_action.performed_by, self.reviewer)
    
    def test_review_case_rejection(self):
        """Test case review rejection."""
        # Create a case
        case = FraudCaseFactory.create(
            user=self.user,
            assigned_to=self.reviewer,
            status=CaseStatus.INVESTIGATING
        )
        
        review_data = {
            'decision': 'false_positive',
            'reason': 'Activity appears legitimate upon review',
            'risk_score': 15,
            'recommendations': ['clear_flags', 'monitor_normal'],
        }
        
        result = self.review_service.review_case(
            case.id,
            review_data,
            reviewed_by=self.reviewer.id
        )
        
        self.assertTrue(result['success'])
        
        # Verify case status
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.RESOLVED)
        self.assertEqual(case.resolved_by, self.reviewer)
        
        # Check user risk profile was updated
        risk_profile = UserRiskProfile.objects.filter(user=self.user).first()
        if risk_profile:
            self.assertLess(risk_profile.overall_risk_score, 30)
    
    def test_request_additional_information(self):
        """Test requesting additional information for review."""
        # Create a case
        case = FraudCaseFactory.create(
            user=self.user,
            assigned_to=self.reviewer,
            status=CaseStatus.INVESTIGATING
        )
        
        request_data = {
            'information_needed': [
                'User transaction history for last 30 days',
                'Device fingerprint analysis',
                'IP geolocation details'
            ],
            'reason': 'Need more context for accurate assessment',
            'deadline': timezone.now() + timedelta(days=3)
        }
        
        result = self.review_service.request_additional_info(
            case.id,
            request_data,
            requested_by=self.reviewer.id
        )
        
        self.assertTrue(result['success'])
        
        # Verify case status
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.REVIEWING)
        
        # Check request action was created
        request_action = case.actions.filter(action_type='review').first()
        self.assertIsNotNone(request_action)
        self.assertIn('information_request', request_action.metadata)
    
    def test_add_review_evidence(self):
        """Test adding evidence during review."""
        # Create a case
        case = FraudCaseFactory.create(
            user=self.user,
            assigned_to=self.reviewer
        )
        
        evidence_data = {
            'evidence_type': 'transaction_analysis',
            'data': json.dumps({
                'suspicious_transactions': [
                    {'id': 1, 'amount': 1000, 'time': '2024-01-01'},
                    {'id': 2, 'amount': 500, 'time': '2024-01-02'}
                ]
            }),
            'description': 'Analysis of user transaction patterns',
            'added_by': self.reviewer.username
        }
        
        evidence = self.review_service.add_review_evidence(
            case.id,
            evidence_data
        )
        
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.evidence_type, evidence_data['evidence_type'])
        self.assertEqual(evidence.added_by, evidence_data['added_by'])
        
        # Verify case priority might be updated based on evidence
        case.refresh_from_db()
        # Priority might change based on evidence weight
    
    def test_get_review_queue(self):
        """Test getting review queue."""
        # Create cases with different priorities and statuses
        FraudCaseFactory.create(
            user=self.user,
            priority='critical',
            status=CaseStatus.OPEN,
            assigned_to=None
        )
        
        FraudCaseFactory.create(
            user=UserFactory.create(),
            priority='high',
            status=CaseStatus.OPEN,
            assigned_to=None
        )
        
        FraudCaseFactory.create(
            user=UserFactory.create(),
            priority='medium',
            status=CaseStatus.INVESTIGATING,
            assigned_to=self.reviewer
        )
        
        # Get unassigned cases
        unassigned = self.review_service.get_review_queue(
            assigned_to=None,
            status=CaseStatus.OPEN
        )
        
        self.assertIsInstance(unassigned, list)
        self.assertEqual(len(unassigned), 2)
        
        # Should be ordered by priority
        self.assertEqual(unassigned[0].priority, 'critical')
        self.assertEqual(unassigned[1].priority, 'high')
        
        # Get reviewer's assigned cases
        assigned = self.review_service.get_review_queue(
            assigned_to=self.reviewer.id
        )
        
        self.assertIsInstance(assigned, list)
        self.assertEqual(len(assigned), 1)
        self.assertEqual(assigned[0].assigned_to, self.reviewer)
    
    def test_get_reviewer_workload(self):
        """Test getting reviewer workload statistics."""
        # Assign cases to reviewer
        FraudCaseFactory.create_batch(
            5,
            assigned_to=self.reviewer,
            status=CaseStatus.INVESTIGATING
        )
        
        FraudCaseFactory.create_batch(
            2,
            assigned_to=self.reviewer,
            status=CaseStatus.RESOLVED
        )
        
        workload = self.review_service.get_reviewer_workload(self.reviewer.id)
        
        self.assertIsInstance(workload, dict)
        self.assertIn('total_cases', workload)
        self.assertIn('open_cases', workload)
        self.assertIn('resolved_cases', workload)
        self.assertIn('avg_resolution_time', workload)
        self.assertIn('workload_score', workload)
        
        self.assertEqual(workload['total_cases'], 7)
        self.assertEqual(workload['open_cases'], 5)
        self.assertEqual(workload['resolved_cases'], 2)
    
    def test_auto_assign_cases(self):
        """Test automatic case assignment."""
        # Create unassigned cases
        FraudCaseFactory.create_batch(
            3,
            assigned_to=None,
            status=CaseStatus.OPEN,
            priority='high'
        )
        
        # Create multiple reviewers
        reviewers = UserFactory.create_batch(2, is_staff=True)
        
        # Auto assign
        assignment_result = self.review_service.auto_assign_cases(
            reviewer_ids=[r.id for r in reviewers]
        )
        
        self.assertIsInstance(assignment_result, dict)
        self.assertIn('assigned_cases', assignment_result)
        self.assertIn('unassigned_cases', assignment_result)
        
        self.assertEqual(assignment_result['assigned_cases'], 3)
        self.assertEqual(assignment_result['unassigned_cases'], 0)
    
    def test_escalate_case(self):
        """Test case escalation."""
        # Create a case
        case = FraudCaseFactory.create(
            user=self.user,
            assigned_to=self.reviewer,
            priority='high',
            status=CaseStatus.INVESTIGATING
        )
        
        escalation_data = {
            'reason': 'Case complexity requires senior review',
            'escalated_to': self.staff_user.id,
            'urgency': 'high',
            'additional_context': 'Multiple fraud patterns detected'
        }
        
        result = self.review_service.escalate_case(
            case.id,
            escalation_data,
            escalated_by=self.reviewer.id
        )
        
        self.assertTrue(result['success'])
        
        # Verify escalation
        case.refresh_from_db()
        self.assertEqual(case.assigned_to, self.staff_user)
        self.assertEqual(case.priority, 'critical')
        
        # Check escalation action was created
        escalation_action = case.actions.filter(action_type='escalate').first()
        self.assertIsNotNone(escalation_action)
        self.assertEqual(escalation_action.performed_by, self.reviewer)
    
    def test_bulk_review_cases(self):
        """Test bulk case review."""
        # Create multiple cases
        cases = FraudCaseFactory.create_batch(
            5,
            assigned_to=self.reviewer,
            status=CaseStatus.INVESTIGATING
        )
        
        # Bulk review data
        bulk_review = {
            'decision': 'false_positive',
            'reason': 'Batch review: all cases appear to be false positives',
            'risk_scores': {case.id: 15 for case in cases},
            'case_ids': [case.id for case in cases]
        }
        
        result = self.review_service.bulk_review_cases(
            bulk_review,
            reviewed_by=self.reviewer.id
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('processed_cases', result)
        self.assertIn('failed_cases', result)
        
        self.assertEqual(result['processed_cases'], 5)
        self.assertEqual(result['failed_cases'], 0)
        
        # Verify all cases are resolved
        for case in cases:
            case.refresh_from_db()
            self.assertEqual(case.status, CaseStatus.RESOLVED)
    
    def test_get_review_statistics(self):
        """Test review statistics calculation."""
        # Create cases with different outcomes
        FraudCaseFactory.create(
            user=self.user,
            assigned_to=self.reviewer,
            status=CaseStatus.RESOLVED,
            priority='high'
        )
        
        FraudCaseFactory.create(
            user=UserFactory.create(),
            assigned_to=self.reviewer,
            status=CaseStatus.RESOLVED,
            priority='medium'
        )
        
        FraudCaseFactory.create(
            user=UserFactory.create(),
            assigned_to=self.reviewer,
            status=CaseStatus.INVESTIGATING,
            priority='critical'
        )
        
        stats = self.review_service.get_review_statistics(
            reviewer_id=self.reviewer.id,
            days=30
        )
        
        self.assertIsInstance(stats, dict)
        self.assertIn('total_cases', stats)
        self.assertIn('resolved_cases', stats)
        self.assertIn('open_cases', stats)
        self.assertIn('resolution_rate', stats)
        self.assertIn('avg_resolution_time', stats)
        self.assertIn('priority_breakdown', stats)
        
        self.assertEqual(stats['total_cases'], 3)
        self.assertEqual(stats['resolved_cases'], 2)
        self.assertEqual(stats['open_cases'], 1)
    
    def test_create_review_template(self):
        """Test creation of review templates."""
        template_data = {
            'name': 'Standard Fraud Review',
            'description': 'Template for standard fraud case reviews',
            'checklist': [
                'Verify user identity',
                'Analyze transaction patterns',
                'Check device fingerprint',
                'Review IP reputation'
            ],
            'required_fields': [
                'decision',
                'reason',
                'risk_score'
            ],
            'default_actions': [
                'update_user_risk_profile',
                'create_alert_if_needed'
            ]
        }
        
        template = self.review_service.create_review_template(
            template_data,
            created_by=self.staff_user.id
        )
        
        self.assertIsInstance(template, dict)
        self.assertIn('template_id', template)
        self.assertIn('name', template)
        self.assertEqual(template['name'], template_data['name'])
    
    def test_apply_review_template(self):
        """Test applying review template to case."""
        # Create a template
        template_data = {
            'name': 'Quick Review',
            'checklist': ['Verify user', 'Check patterns'],
            'required_fields': ['decision', 'reason']
        }
        
        template = self.review_service.create_review_template(
            template_data,
            created_by=self.staff_user.id
        )
        
        # Create a case
        case = FraudCaseFactory.create(
            user=self.user,
            assigned_to=self.reviewer
        )
        
        # Apply template
        result = self.review_service.apply_review_template(
            case.id,
            template['template_id'],
            applied_by=self.reviewer.id
        )
        
        self.assertTrue(result['success'])
        
        # Verify template was applied
        case.refresh_from_db()
        self.assertIn('template_applied', case.metadata)
    
    def test_get_case_timeline(self):
        """Test getting case timeline."""
        # Create a case with multiple actions
        case = FraudCaseFactory.create(
            user=self.user,
            assigned_to=self.reviewer
        )
        
        # Add multiple actions
        FraudCaseActionFactory.create(
            fraud_case=case,
            action_type='investigate',
            performed_by=self.reviewer,
            note='Started investigation'
        )
        
        FraudCaseActionFactory.create(
            fraud_case=case,
            action_type='evidence_add',
            performed_by=self.reviewer,
            note='Added new evidence'
        )
        
        timeline = self.review_service.get_case_timeline(case.id)
        
        self.assertIsInstance(timeline, list)
        self.assertGreater(len(timeline), 0)
        
        # Should include case creation
        timeline_events = [event['action_type'] for event in timeline]
        self.assertIn('create', timeline_events)
        self.assertIn('investigate', timeline_events)
        self.assertIn('evidence_add', timeline_events)
    
    def test_search_cases(self):
        """Test case search functionality."""
        # Create cases with different attributes
        FraudCaseFactory.create(
            user=self.user,
            title='Suspicious login activity',
            priority='high'
        )
        
        FraudCaseFactory.create(
            user=UserFactory.create(),
            title='Unusual transaction pattern',
            priority='medium'
        )
        
        # Search by title
        results = self.review_service.search_cases(
            query='suspicious',
            search_fields=['title']
        )
        
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, 'Suspicious login activity')
        
        # Search by priority
        results = self.review_service.search_cases(
            filters={'priority': 'high'}
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].priority, 'high')
    
    @patch('fraud_detection.services.ReviewService.logger')
    def test_error_handling(self, mock_logger):
        """Test error handling in review service."""
        # Test with invalid case ID
        with self.assertRaises(ValueError):
            self.review_service.assign_review_case(999999, self.reviewer.id)
        
        # Test with invalid reviewer ID
        with self.assertRaises(ValueError):
            self.review_service.assign_review_case(1, 999999)
        
        # Verify error logging
        mock_logger.error.assert_called()
    
    def test_review_workflow_validation(self):
        """Test review workflow validation."""
        # Create a case
        case = FraudCaseFactory.create(
            user=self.user,
            assigned_to=self.reviewer,
            status=CaseStatus.INVESTIGATING
        )
        
        # Test invalid review data
        invalid_review = {
            'decision': 'invalid_decision',
            'reason': '',
            'risk_score': 150  # Invalid score
        }
        
        with self.assertRaises(ValueError):
            self.review_service.review_case(case.id, invalid_review, self.reviewer.id)
        
        # Test valid review data
        valid_review = {
            'decision': 'confirmed_fraud',
            'reason': 'Valid review reason',
            'risk_score': 75
        }
        
        result = self.review_service.review_case(case.id, valid_review, self.reviewer.id)
        self.assertTrue(result['success'])
    
    def test_performance_with_large_dataset(self):
        """Test performance with large dataset."""
        # Create large number of cases
        cases = FraudCaseFactory.create_batch(
            100,
            assigned_to=self.reviewer,
            status=random.choice(['open', 'investigating', 'resolved'])
        )
        
        # Test queue retrieval performance
        import time
        start_time = time.time()
        
        queue = self.review_service.get_review_queue(assigned_to=self.reviewer.id)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(processing_time, 2.0)  # 2 seconds max
        self.assertIsInstance(queue, list)


class TestReviewServiceIntegration(TestCase):
    """Integration tests for ReviewService."""
    
    def setUp(self):
        """Set up integration test data."""
        self.review_service = ReviewService()
        self.staff_user = UserFactory.create(is_staff=True)
        self.reviewer = UserFactory.create(is_staff=True)
    
    def test_end_to_end_review_workflow(self):
        """Test end-to-end review workflow."""
        user = UserFactory.create()
        
        # Create initial fraud detection scenario
        case_data = {
            'user_id': user.id,
            'title': 'Complex fraud pattern detected',
            'description': 'User exhibiting multiple suspicious behaviors',
            'priority': 'critical',
            'evidence': [
                {
                    'type': 'multiple_ip_usage',
                    'data': {'ips': ['192.168.1.1', '192.168.1.2', '10.0.0.1']},
                    'description': 'User accessing from multiple IP addresses'
                },
                {
                    'type': 'unusual_timing',
                    'data': {'times': ['02:00', '03:30', '04:15']},
                    'description': 'Activity during unusual hours'
                }
            ]
        }
        
        # Create review case
        case = self.review_service.create_review_case(case_data, created_by=self.staff_user.id)
        
        # Assign to reviewer
        assignment = self.review_service.assign_review_case(
            case.id,
            self.reviewer.id,
            assignment_reason="Complex case requiring specialist review",
            assigned_by=self.staff_user.id
        )
        
        self.assertTrue(assignment['success'])
        
        # Request additional information
        info_request = self.review_service.request_additional_info(
            case.id,
            {
                'information_needed': ['Device fingerprint analysis', 'Transaction history'],
                'reason': 'Need technical analysis for accurate assessment',
                'deadline': timezone.now() + timedelta(days=2)
            },
            requested_by=self.reviewer.id
        )
        
        self.assertTrue(info_request['success'])
        
        # Add additional evidence
        evidence = self.review_service.add_review_evidence(
            case.id,
            {
                'evidence_type': 'technical_analysis',
                'data': json.dumps({
                    'device_trust_score': 25,
                    'ip_risk_score': 80,
                    'behavioral_anomaly': 0.85
                }),
                'description': 'Technical analysis results',
                'added_by': self.reviewer.username
            }
        )
        
        # Complete review
        review_data = {
            'decision': 'confirmed_fraud',
            'reason': 'Multiple high-risk indicators confirm fraudulent activity',
            'risk_score': 90,
            'recommendations': ['immediate_ban', 'freeze_accounts', 'investigate_related_accounts'],
            'evidence_review': {
                'multiple_ip_usage': {'verified': True, 'weight': 'high'},
                'unusual_timing': {'verified': True, 'weight': 'medium'},
                'technical_analysis': {'verified': True, 'weight': 'high'}
            }
        }
        
        review_result = self.review_service.review_case(
            case.id,
            review_data,
            reviewed_by=self.reviewer.id
        )
        
        self.assertTrue(review_result['success'])
        
        # Verify final state
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.RESOLVED)
        self.assertEqual(case.resolved_by, self.reviewer)
        self.assertIsNotNone(case.resolved_at)
        
        # Check timeline
        timeline = self.review_service.get_case_timeline(case.id)
        self.assertGreater(len(timeline), 3)  # create, assign, review
        
        # Verify user risk profile was updated
        risk_profile = UserRiskProfile.objects.filter(user=user).first()
        if risk_profile:
            self.assertGreaterEqual(risk_profile.overall_risk_score, 80)
    
    def test_bulk_review_processing(self):
        """Test bulk review processing workflow."""
        # Create multiple cases
        users = UserFactory.create_batch(10)
        cases = []
        
        for user in users:
            case_data = {
                'user_id': user.id,
                'title': f'Review case for {user.username}',
                'description': 'Standard fraud review',
                'priority': random.choice(['low', 'medium', 'high']),
                'evidence': [{
                    'type': 'fraud_score',
                    'data': {'score': random.randint(20, 80)},
                    'description': 'Fraud score analysis'
                }]
            }
            
            case = self.review_service.create_review_case(case_data, created_by=self.staff_user.id)
            cases.append(case)
        
        # Assign all to reviewer
        for case in cases:
            self.review_service.assign_review_case(
                case.id,
                self.reviewer.id,
                assignment_reason="Bulk assignment",
                assigned_by=self.staff_user.id
            )
        
        # Bulk review with mixed decisions
        bulk_review_data = {
            'case_ids': [case.id for case in cases],
            'decision': 'mixed',
            'case_decisions': {
                cases[0].id: 'confirmed_fraud',
                cases[1].id: 'false_positive',
                cases[2].id: 'confirmed_fraud',
                cases[3].id: 'false_positive',
                cases[4].id: 'confirmed_fraud',
                # Rest will use default
            },
            'default_decision': 'false_positive',
            'reason': 'Bulk review completed',
            'default_risk_score': 25
        }
        
        bulk_result = self.review_service.bulk_review_cases(
            bulk_review_data,
            reviewed_by=self.reviewer.id
        )
        
        self.assertIsInstance(bulk_result, dict)
        self.assertIn('processed_cases', bulk_result)
        self.assertIn('failed_cases', bulk_result)
        
        self.assertEqual(bulk_result['processed_cases'], len(cases))
        self.assertEqual(bulk_result['failed_cases'], 0)
        
        # Verify final states
        confirmed_count = 0
        false_positive_count = 0
        
        for case in cases:
            case.refresh_from_db()
            self.assertEqual(case.status, CaseStatus.RESOLVED)
            
            # Check decision from metadata or actions
            if 'decision' in case.metadata:
                if case.metadata['decision'] == 'confirmed_fraud':
                    confirmed_count += 1
                else:
                    false_positive_count += 1
        
        self.assertGreater(confirmed_count, 0)
        self.assertGreater(false_positive_count, 0)
    
    def test_review_team_collaboration(self):
        """Test review team collaboration workflow."""
        # Create multiple reviewers
        senior_reviewer = UserFactory.create(is_staff=True)
        junior_reviewer = UserFactory.create(is_staff=True)
        
        # Create complex case
        case_data = {
            'user_id': UserFactory.create().id,
            'title': 'Complex international fraud case',
            'description': 'Multi-country fraud pattern requiring expertise',
            'priority': 'critical',
            'evidence': [{
                'type': 'international_pattern',
                'data': {'countries': ['US', 'GB', 'CA', 'AU']},
                'description': 'Fraud spanning multiple countries'
            }]
        }
        
        case = self.review_service.create_review_case(case_data, created_by=self.staff_user.id)
        
        # Initial assignment to junior reviewer
        self.review_service.assign_review_case(
            case.id,
            junior_reviewer.id,
            assignment_reason="Initial review",
            assigned_by=self.staff_user.id
        )
        
        # Junior reviewer requests escalation
        escalation = self.review_service.escalate_case(
            case.id,
            {
                'reason': 'Case complexity requires senior expertise',
                'escalated_to': senior_reviewer.id,
                'urgency': 'high',
                'junior_findings': 'Initial analysis shows complex patterns'
            },
            escalated_by=junior_reviewer.id
        )
        
        self.assertTrue(escalation['success'])
        
        # Senior reviewer completes review
        review_data = {
            'decision': 'confirmed_fraud',
            'reason': 'Sophisticated international fraud operation confirmed',
            'risk_score': 95,
            'recommendations': ['immediate_ban', 'legal_action', 'international_cooperation'],
            'collaboration_notes': 'Working with junior reviewer on complex analysis'
        }
        
        final_review = self.review_service.review_case(
            case.id,
            review_data,
            reviewed_by=senior_reviewer.id
        )
        
        self.assertTrue(final_review['success'])
        
        # Verify collaboration history
        timeline = self.review_service.get_case_timeline(case.id)
        
        # Should show both reviewers' actions
        reviewer_actions = [action for action in timeline if action['performed_by_id'] in [junior_reviewer.id, senior_reviewer.id]]
        self.assertGreater(len(reviewer_actions), 1)
        
        # Verify final resolution
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.RESOLVED)
        self.assertEqual(case.assigned_to, senior_reviewer)


if __name__ == '__main__':
    import random
    
    # Add random import for integration tests
    TestReviewServiceIntegration.setUp = lambda self: (
        setattr(self, 'review_service', ReviewService()) or
        setattr(self, 'staff_user', UserFactory.create(is_staff=True)) or
        setattr(self, 'reviewer', UserFactory.create(is_staff=True))
    )
