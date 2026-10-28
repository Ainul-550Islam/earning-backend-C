"""
Comprehensive compliance testing for auto_mod module.

This test file covers all GDPR, CCPA, HIPAA compliance logic and
regulatory reporting functionality for automated moderation systems.
"""

import json
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core import mail
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.cache import cache
from datetime import datetime, timedelta
import tempfile
import os

from api.auto_mod.models import (
    ModerationRule, ModerationAction, ModerationLog, ContentFlag,
    AutoModerationQueue, ModerationAppeal, ModerationStats
)
from api.auto_mod.compliance import (
    ModerationComplianceManager, PrivacyManager, AuditTrailManager,
    check_moderation_compliance, validate_content_policy, generate_compliance_report
)
from api.auto_mod.exceptions import ComplianceError, ModerationError
from api.users.models import User

User = get_user_model()


class BaseComplianceTest(TestCase):
    """Base test class for compliance testing"""
    
    def setUp(self):
        """Set up common test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        self.moderator_user = User.objects.create_user(
            username='moderator',
            email='moderator@example.com',
            password='modpass123',
            is_staff=True
        )


class ModerationComplianceManagerTest(BaseComplianceTest):
    """Test ModerationComplianceManager functionality"""
    
    def setUp(self):
        super().setUp()
        self.compliance_manager = ModerationComplianceManager()
    
    def test_compliance_manager_initialization(self):
        """Test compliance manager initialization"""
        self.assertIsNotNone(self.compliance_manager)
        self.assertTrue(hasattr(self.compliance_manager, 'check_gdpr_compliance'))
        self.assertTrue(hasattr(self.compliance_manager, 'check_ccpa_compliance'))
        self.assertTrue(hasattr(self.compliance_manager, 'check_content_policy_compliance'))
    
    def test_gdpr_content_moderation_compliance(self):
        """Test GDPR compliance for content moderation"""
        # Create moderation rule
        rule = ModerationRule.objects.create(
            name="GDPR Content Rule",
            rule_type="content_filter",
            criteria={"personal_data": True},
            action="flag_for_review",
            severity="medium",
            created_by=self.admin_user
        )
        
        # Test compliance check
        result = self.compliance_manager.check_gdpr_compliance(rule)
        self.assertIsInstance(result, dict)
        self.assertIn('compliant', result)
        self.assertIn('violations', result)
        self.assertIn('recommendations', result)
    
    def test_ccpa_user_rights_compliance(self):
        """Test CCPA compliance for user rights in moderation"""
        # Create content flag
        flag = ContentFlag.objects.create(
            user=self.regular_user,
            content_type="post",
            content_id="post_001",
            flag_type="personal_data_request",
            reason="User requested deletion",
            status="pending",
            created_by=self.regular_user
        )
        
        result = self.compliance_manager.check_ccpa_compliance(flag)
        self.assertIsInstance(result, dict)
        self.assertIn('compliant', result)
        self.assertIn('user_rights_respected', result)
        self.assertIn('response_time', result)
    
    def test_hipaa_health_content_compliance(self):
        """Test HIPAA compliance for health-related content moderation"""
        health_rule = ModerationRule.objects.create(
            name="HIPAA Health Content Rule",
            rule_type="phi_filter",
            criteria={"health_information": True},
            action="immediate_removal",
            severity="high",
            created_by=self.admin_user
        )
        
        result = self.compliance_manager.check_hipaa_compliance(health_rule)
        self.assertIsInstance(result, dict)
        self.assertIn('compliant', result)
        self.assertIn('phi_protection', result)
        self.assertIn('audit_trail', result)
    
    def test_content_policy_compliance(self):
        """Test general content policy compliance"""
        policy_data = {
            'policy_type': 'community_guidelines',
            'content_categories': ['hate_speech', 'violence', 'spam'],
            'enforcement_actions': ['remove', 'suspend', 'ban'],
            'appeal_process': True
        }
        
        result = self.compliance_manager.check_content_policy_compliance(policy_data)
        self.assertIsInstance(result, dict)
        self.assertIn('compliant', result)
        self.assertIn('policy_adequacy', result)
        self.assertIn('appeal_mechanism', result)
    
    def test_moderation_bias_detection(self):
        """Test detection of moderation bias"""
        # Create test moderation data
        for i in range(100):
            ModerationLog.objects.create(
                moderator=self.moderator_user,
                user=self.regular_user,
                action="remove_content",
                reason="policy_violation",
                content_type="post",
                content_id=f"post_{i}",
                automated=True,
                created_at=timezone.now()
            )
        
        result = self.compliance_manager.check_moderation_bias()
        self.assertIsInstance(result, dict)
        self.assertIn('bias_detected', result)
        self.assertIn('bias_metrics', result)
        self.assertIn('recommendations', result)


class PrivacyManagerTest(BaseComplianceTest):
    """Test PrivacyManager functionality for content moderation"""
    
    def setUp(self):
        super().setUp()
        self.privacy_manager = PrivacyManager()
    
    def test_content_consent_management(self):
        """Test consent management for content processing"""
        consent_data = {
            'user_id': self.regular_user.id,
            'content_type': 'user_generated_content',
            'consent_type': 'content_moderation',
            'consent_given': True,
            'timestamp': timezone.now().isoformat(),
            'ip_address': '192.168.1.1'
        }
        
        result = self.privacy_manager.record_content_consent(consent_data)
        self.assertTrue(result.get('success', False))
        
        # Verify consent retrieval
        retrieved_consent = self.privacy_manager.get_content_consent(
            self.regular_user.id, 'content_moderation'
        )
        self.assertIsNotNone(retrieved_consent)
        self.assertTrue(retrieved_consent.get('consent_given', False))
    
    def test_user_content_access_rights(self):
        """Test user rights to access their content data"""
        # Create user content
        ModerationLog.objects.create(
            moderator=self.moderator_user,
            user=self.regular_user,
            action="review_content",
            reason="policy_check",
            content_type="post",
            content_id="user_post_001",
            automated=False,
            created_at=timezone.now()
        )
        
        access_result = self.privacy_manager.provide_content_access(
            self.regular_user.id, content_types=['post']
        )
        self.assertTrue(access_result.get('success', False))
        self.assertIn('content_data', access_result)
    
    def test_content_deletion_rights(self):
        """Test user rights to delete their content"""
        # Create content record
        flag = ContentFlag.objects.create(
            user=self.regular_user,
            content_type="comment",
            content_id="comment_001",
            flag_type="user_deletion_request",
            reason="User requested deletion",
            status="pending",
            created_by=self.regular_user
        )
        
        deletion_result = self.privacy_manager.process_content_deletion(
            self.regular_user.id, "comment_001"
        )
        self.assertTrue(deletion_result.get('success', False))
        
        # Verify deletion processing
        updated_flag = ContentFlag.objects.get(id=flag.id)
        self.assertEqual(updated_flag.status, "processed")
    
    def test_content_portability(self):
        """Test content portability for user data"""
        # Create user content data
        for i in range(5):
            ModerationLog.objects.create(
                moderator=self.moderator_user,
                user=self.regular_user,
                action="moderate",
                reason=f"policy_violation_{i}",
                content_type="post",
                content_id=f"post_{i}",
                automated=True,
                created_at=timezone.now()
            )
        
        portability_result = self.privacy_manager.export_content_data(
            self.regular_user.id, format='json'
        )
        self.assertTrue(portability_result.get('success', False))
        self.assertIn('export_data', portability_result)
        self.assertIn('download_url', portability_result)
    
    def test_sensitive_content_handling(self):
        """Test handling of sensitive content in moderation"""
        sensitive_content = {
            'content_id': 'sensitive_001',
            'content_type': 'health_post',
            'user_id': self.regular_user.id,
            'contains_phi': True,
            'data_classification': 'sensitive'
        }
        
        handling_result = self.privacy_manager.handle_sensitive_content(
            sensitive_content
        )
        self.assertTrue(handling_result.get('success', False))
        self.assertIn('encryption_applied', handling_result)
        self.assertIn('access_restricted', handling_result)


class AuditTrailManagerTest(BaseComplianceTest):
    """Test AuditTrailManager functionality"""
    
    def setUp(self):
        super().setUp()
        self.audit_manager = AuditTrailManager()
    
    def test_moderation_audit_logging(self):
        """Test comprehensive audit logging for moderation actions"""
        # Create moderation action
        action = ModerationAction.objects.create(
            moderator=self.moderator_user,
            target_user=self.regular_user,
            action_type="content_removal",
            content_type="post",
            content_id="audit_post_001",
            reason="policy_violation",
            automated=False,
            created_by=self.moderator_user
        )
        
        # Verify audit log creation
        audit_logs = self.audit_manager.get_moderation_audit_logs(
            action_id=action.id
        )
        self.assertGreater(len(audit_logs), 0)
        
        for log in audit_logs:
            self.assertIn('timestamp', log)
            self.assertIn('action_type', log)
            self.assertIn('moderator_id', log)
            self.assertIn('content_id', log)
    
    def test_audit_trail_integrity(self):
        """Test audit trail integrity and tamper protection"""
        # Create audit entry
        self.audit_manager.log_moderation_action(
            moderator=self.moderator_user,
            target_user=self.regular_user,
            action="content_flag",
            content_id="integrity_test_001",
            reason="spam_detection"
        )
        
        # Verify integrity hash
        audit_entries = self.audit_manager.get_audit_entries(
            content_id="integrity_test_001"
        )
        
        for entry in audit_entries:
            self.assertIn('integrity_hash', entry)
            self.assertIsNotNone(entry['integrity_hash'])
            
            # Verify hash validation
            is_valid = self.audit_manager.verify_audit_integrity(entry['id'])
            self.assertTrue(is_valid)
    
    def test_audit_log_retention(self):
        """Test audit log retention policies"""
        # Create old audit entry
        old_date = timezone.now() - timedelta(days=400)
        
        with patch('django.utils.timezone.now', return_value=old_date):
            old_audit = self.audit_manager.log_moderation_action(
                moderator=self.moderator_user,
                target_user=self.regular_user,
                action="content_removal",
                content_id="retention_test_001",
                reason="old_action"
            )
        
        # Apply retention policy
        deleted_count = self.audit_manager.apply_retention_policies(
            retention_days=365
        )
        self.assertGreater(deleted_count, 0)
        
        # Verify old entry deletion
        remaining_entries = self.audit_manager.get_audit_entries(
            content_id="retention_test_001"
        )
        self.assertEqual(len(remaining_entries), 0)
    
    def test_audit_report_generation(self):
        """Test comprehensive audit reporting"""
        # Create test audit data
        for i in range(10):
            self.audit_manager.log_moderation_action(
                moderator=self.moderator_user,
                target_user=self.regular_user,
                action="content_review",
                content_id=f"audit_report_{i}",
                reason=f"policy_check_{i}"
            )
        
        report = self.audit_manager.generate_audit_report(
            date_range=(timezone.now() - timedelta(days=7), timezone.now()),
            include_details=True
        )
        
        self.assertIsInstance(report, dict)
        self.assertIn('summary', report)
        self.assertIn('total_actions', report)
        self.assertIn('action_breakdown', report)
        self.assertIn('moderator_stats', report)
        self.assertIn('detailed_logs', report)


class ModerationAppealComplianceTest(BaseComplianceTest):
    """Test compliance for moderation appeal process"""
    
    def setUp(self):
        super().setUp()
        self.appeal_data = {
            'user': self.regular_user,
            'original_action': 'content_removal',
            'content_type': 'post',
            'content_id': 'appeal_test_001',
            'reason': 'Incorrect moderation decision',
            'evidence': 'User provided context'
        }
    
    def test_appeal_process_compliance(self):
        """Test compliance of appeal process"""
        appeal = ModerationAppeal.objects.create(**self.appeal_data)
        
        compliance_result = check_moderation_compliance(appeal.id)
        self.assertIsInstance(compliance_result, dict)
        self.assertIn('compliant', compliance_result)
        self.assertIn('appeal_rights', compliance_result)
        self.assertIn('response_time', compliance_result)
    
    def test_appeal_response_time_compliance(self):
        """Test compliance with appeal response time requirements"""
        appeal = ModerationAppeal.objects.create(**self.appeal_data)
        
        # Simulate delayed response
        delayed_time = timezone.now() + timedelta(days=8)
        with patch('django.utils.timezone.now', return_value=delayed_time):
            compliance_result = check_moderation_compliance(appeal.id)
            
        self.assertFalse(compliance_result.get('compliant', True))
        self.assertIn('response_time_violation', compliance_result.get('violations', []))
    
    def test_appeal_transparency_compliance(self):
        """Test transparency requirements for appeals"""
        appeal = ModerationAppeal.objects.create(**self.appeal_data)
        
        # Add decision without proper reasoning
        appeal.status = 'approved'
        appeal.decision_reason = ''  # Missing reasoning
        appeal.save()
        
        compliance_result = check_moderation_compliance(appeal.id)
        self.assertFalse(compliance_result.get('compliant', True))
        self.assertIn('transparency_violation', compliance_result.get('violations', []))


class AutoModerationComplianceTest(BaseComplianceTest):
    """Test compliance for automated moderation systems"""
    
    def setUp(self):
        super().setUp()
        self.auto_rule = ModerationRule.objects.create(
            name="Auto Spam Detection",
            rule_type="automated_filter",
            criteria={"spam_score": 0.8},
            action="auto_remove",
            severity="medium",
            automated=True,
            created_by=self.admin_user
        )
    
    def test_automated_decision_transparency(self):
        """Test transparency of automated moderation decisions"""
        # Create automated moderation action
        action = ModerationAction.objects.create(
            moderator=None,  # Automated action
            target_user=self.regular_user,
            action_type="auto_removal",
            content_type="post",
            content_id="auto_test_001",
            reason="spam_detection",
            automated=True,
            confidence_score=0.85,
            rule=self.auto_rule,
            created_by=None
        )
        
        compliance_result = check_moderation_compliance(action.id)
        self.assertIsInstance(compliance_result, dict)
        self.assertIn('transparency_score', compliance_result)
        self.assertIn('explainability', compliance_result)
    
    def test_algorithmic_bias_detection(self):
        """Test detection of algorithmic bias in auto-moderation"""
        # Create biased auto-moderation data
        user_groups = ['group_a', 'group_b']
        for group in user_groups:
            for i in range(50):
                ModerationAction.objects.create(
                    moderator=None,
                    target_user=self.regular_user,
                    action_type="auto_flag",
                    content_type="post",
                    content_id=f"auto_{group}_{i}",
                    reason=f"auto_detection_{group}",
                    automated=True,
                    confidence_score=0.9 if group == 'group_a' else 0.6,
                    user_group=group,
                    created_by=None
                )
        
        bias_result = self.compliance_manager.check_algorithmic_bias()
        self.assertIsInstance(bias_result, dict)
        self.assertIn('bias_detected', bias_result)
        self.assertIn('disparate_impact', bias_result)
        self.assertIn('recommendations', bias_result)
    
    def test_human_oversight_requirements(self):
        """Test human oversight requirements for automated decisions"""
        # Create high-impact automated action without human review
        high_impact_action = ModerationAction.objects.create(
            moderator=None,
            target_user=self.regular_user,
            action_type="auto_ban",
            content_type="user",
            content_id=str(self.regular_user.id),
            reason="repeated_violations",
            automated=True,
            confidence_score=0.75,
            human_reviewed=False,
            created_by=None
        )
        
        compliance_result = check_moderation_compliance(high_impact_action.id)
        self.assertFalse(compliance_result.get('compliant', True))
        self.assertIn('human_oversight_violation', compliance_result.get('violations', []))


class ComplianceIntegrationTest(BaseComplianceTest):
    """Integration tests for moderation compliance"""
    
    def test_end_to_end_compliance_workflow(self):
        """Test complete compliance workflow"""
        # Create content that triggers moderation
        flag = ContentFlag.objects.create(
            user=self.regular_user,
            content_type="post",
            content_id="integration_test_001",
            flag_type="policy_violation",
            reason="Potential hate speech",
            status="pending",
            created_by=self.admin_user
        )
        
        # Process moderation
        action = ModerationAction.objects.create(
            moderator=self.moderator_user,
            target_user=self.regular_user,
            action_type="content_removal",
            content_type="post",
            content_id="integration_test_001",
            reason="hate_speech_detected",
            automated=False,
            created_by=self.moderator_user
        )
        
        # Check compliance at each step
        flag_compliance = check_moderation_compliance(flag.id)
        action_compliance = check_moderation_compliance(action.id)
        
        self.assertIsInstance(flag_compliance, dict)
        self.assertIsInstance(action_compliance, dict)
        
        # Create appeal
        appeal = ModerationAppeal.objects.create(
            user=self.regular_user,
            original_action='content_removal',
            content_type="post",
            content_id="integration_test_001",
            reason="Incorrect classification",
            created_by=self.regular_user
        )
        
        appeal_compliance = check_moderation_compliance(appeal.id)
        self.assertIsInstance(appeal_compliance, dict)
    
    def test_cross_system_compliance_consistency(self):
        """Test consistency across different compliance systems"""
        # Create test data
        rule = ModerationRule.objects.create(
            name="Cross System Test Rule",
            rule_type="content_filter",
            criteria={"prohibited_content": True},
            action="flag_for_review",
            severity="medium",
            created_by=self.admin_user
        )
        
        # Test compliance from different managers
        moderation_compliance = ModerationComplianceManager()
        privacy_compliance = PrivacyManager()
        audit_compliance = AuditTrailManager()
        
        mod_result = moderation_compliance.check_full_compliance(rule)
        privacy_result = privacy_compliance.assess_rule_privacy_impact(rule.id)
        audit_result = audit_compliance.assess_audit_compliance(rule.id)
        
        # Results should be consistent
        self.assertEqual(
            mod_result.get('compliant'),
            privacy_result.get('compliant')
        )
    
    def test_compliance_reporting_integration(self):
        """Test integrated compliance reporting"""
        # Create comprehensive test data
        for i in range(5):
            ModerationRule.objects.create(
                name=f"Report Test Rule {i}",
                rule_type="content_filter",
                criteria={"test": True},
                action="flag",
                severity="low",
                created_by=self.admin_user
            )
            
            ModerationAction.objects.create(
                moderator=self.moderator_user,
                target_user=self.regular_user,
                action_type="content_review",
                content_type="post",
                content_id=f"report_test_{i}",
                reason="test_moderation",
                created_by=self.moderator_user
            )
        
        report = generate_compliance_report(
            standards=['gdpr', 'ccpa', 'hipaa'],
            date_range=(timezone.now() - timedelta(days=30), timezone.now())
        )
        
        self.assertIsInstance(report, dict)
        self.assertIn('summary', report)
        self.assertIn('moderation_compliance', report)
        self.assertIn('privacy_compliance', report)
        self.assertIn('audit_compliance', report)
        self.assertIn('recommendations', report)


class CompliancePerformanceTest(BaseComplianceTest):
    """Performance tests for compliance operations"""
    
    def test_large_scale_compliance_checking(self):
        """Test compliance checking with large datasets"""
        # Create large dataset
        rules = []
        for i in range(100):
            rule = ModerationRule.objects.create(
                name=f"Performance Test Rule {i}",
                rule_type="content_filter",
                criteria={"test": i},
                action="flag",
                severity="low",
                created_by=self.admin_user
            )
            rules.append(rule)
        
        # Measure performance
        import time
        start_time = time.time()
        
        compliance_manager = ModerationComplianceManager()
        results = []
        for rule in rules:
            result = compliance_manager.check_full_compliance(rule)
            results.append(result)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Performance assertion
        self.assertLess(duration, 15.0)  # 15 seconds max
        self.assertEqual(len(results), 100)
    
    def test_bulk_audit_processing(self):
        """Test performance of bulk audit processing"""
        audit_manager = AuditTrailManager()
        
        # Create bulk audit entries
        audit_entries = []
        for i in range(1000):
            entry = audit_manager.log_moderation_action(
                moderator=self.moderator_user,
                target_user=self.regular_user,
                action="bulk_test",
                content_id=f"bulk_{i}",
                reason=f"bulk_test_reason_{i}"
            )
            audit_entries.append(entry)
        
        # Measure bulk processing performance
        import time
        start_time = time.time()
        
        result = audit_manager.process_bulk_audit_entries(audit_entries)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Performance assertion
        self.assertLess(duration, 10.0)  # 10 seconds max
        self.assertTrue(result.get('success', False))


class ComplianceErrorHandlingTest(BaseComplianceTest):
    """Test error handling in compliance operations"""
    
    def test_invalid_moderation_data_handling(self):
        """Test handling of invalid moderation data"""
        compliance_manager = ModerationComplianceManager()
        
        invalid_data = {
            'rule_type': None,  # Invalid rule type
            'criteria': {},  # Empty criteria
            'action': 'invalid_action',  # Invalid action
            'severity': 'invalid_severity'  # Invalid severity
        }
        
        with self.assertRaises(ComplianceError):
            compliance_manager.validate_moderation_rule(invalid_data)
    
    def test_compliance_check_with_missing_data(self):
        """Test compliance checking with missing required data"""
        with self.assertRaises(ComplianceError):
            check_moderation_compliance(None)
    
    def test_audit_corruption_handling(self):
        """Test handling of corrupted audit data"""
        audit_manager = AuditTrailManager()
        
        # Test with corrupted audit entry
        with self.assertRaises(ComplianceError):
            audit_manager.verify_audit_integrity('invalid_id')
    
    def test_privacy_request_errors(self):
        """Test error handling in privacy requests"""
        privacy_manager = PrivacyManager()
        
        # Test invalid user request
        result = privacy_manager.provide_content_access(99999)
        self.assertFalse(result.get('success', True))
        self.assertIn('error', result)


class ComplianceSecurityTest(BaseComplianceTest):
    """Test security aspects of compliance operations"""
    
    def test_sensitive_audit_data_encryption(self):
        """Test encryption of sensitive audit data"""
        audit_manager = AuditTrailManager()
        
        sensitive_audit_data = {
            'user_id': self.regular_user.id,
            'content_data': 'sensitive_personal_information',
            'moderation_reason': 'protected_content',
            'ip_address': '192.168.1.100'
        }
        
        # Store sensitive audit data
        result = audit_manager.store_sensitive_audit(sensitive_audit_data)
        self.assertTrue(result.get('success', False))
        
        # Retrieve and verify encryption
        stored_data = audit_manager.retrieve_sensitive_audit(
            self.regular_user.id
        )
        self.assertIsNotNone(stored_data)
        self.assertNotEqual(
            stored_data.get('content_data'), 
            'sensitive_personal_information'
        )
    
    def test_compliance_data_integrity(self):
        """Test integrity of compliance data"""
        compliance_manager = ModerationComplianceManager()
        
        # Create compliance record
        rule = ModerationRule.objects.create(
            name="Integrity Test Rule",
            rule_type="content_filter",
            criteria={"test": True},
            action="flag",
            severity="medium",
            created_by=self.admin_user
        )
        
        # Generate integrity hash
        integrity_result = compliance_manager.generate_integrity_hash(rule.id)
        self.assertTrue(integrity_result.get('success', False))
        self.assertIn('hash', integrity_result)
        
        # Verify integrity
        verification_result = compliance_manager.verify_integrity(
            rule.id, integrity_result['hash']
        )
        self.assertTrue(verification_result.get('valid', False))
    
    def test_access_control_compliance(self):
        """Test access control for compliance operations"""
        # Test regular user cannot access admin compliance functions
        with self.assertRaises(PermissionError):
            compliance_manager = ModerationComplianceManager()
            compliance_manager.admin_compliance_overview(
                user=self.regular_user
            )
        
        # Test admin user can access compliance functions
        try:
            compliance_manager = ModerationComplianceManager()
            compliance_manager.admin_compliance_overview(
                user=self.admin_user
            )
        except PermissionError:
            self.fail("Admin user should have access to compliance functions")
    
    def test_secure_audit_log_storage(self):
        """Test secure storage of audit logs"""
        audit_manager = AuditTrailManager()
        
        # Create sensitive audit entry
        audit_result = audit_manager.log_moderation_action(
            moderator=self.moderator_user,
            target_user=self.regular_user,
            action="sensitive_content_removal",
            content_type="private_message",
            content_id="sensitive_001",
            reason="protected_content_violation",
            sensitive=True
        )
        
        self.assertTrue(audit_result.get('success', False))
        
        # Verify secure storage
        stored_entry = audit_manager.get_secure_audit_entry(audit_result['audit_id'])
        self.assertIsNotNone(stored_entry)
        self.assertTrue(stored_entry.get('encrypted', False))
        self.assertIn('access_log', stored_entry)
