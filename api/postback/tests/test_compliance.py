"""
Comprehensive compliance testing for postback module.

This test file covers all GDPR, CCPA, HIPAA compliance logic and
regulatory reporting functionality for postback systems.
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

from api.postback.models import (
    Postback, PostbackLog, PostbackEndpoint, PostbackRule,
    PostbackQueue, PostbackRetry, PostbackStats, PostbackAudit,
    PostbackSecurity, PostbackCompliance, PostbackConfiguration
)
from api.postback.compliance import (
    PostbackComplianceManager, PrivacyManager, DataRetentionManager,
    check_postback_compliance, validate_postback_system, generate_compliance_report
)
from api.postback.exceptions import ComplianceError, PostbackError
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
        self.partner_user = User.objects.create_user(
            username='partner',
            email='partner@example.com',
            password='partnerpass123'
        )


class PostbackComplianceManagerTest(BaseComplianceTest):
    """Test PostbackComplianceManager functionality"""
    
    def setUp(self):
        super().setUp()
        self.compliance_manager = PostbackComplianceManager()
        
        # Create test postback data
        self.postback = Postback.objects.create(
            user=self.regular_user,
            partner=self.partner_user,
            offer_id="OFFER-001",
            event_type="conversion",
            amount=Decimal("5.00"),
            currency="USD",
            status="completed",
            ip_address="192.168.1.1",
            user_agent="Test Browser",
            created_by=self.regular_user
        )
    
    def test_compliance_manager_initialization(self):
        """Test compliance manager initialization"""
        self.assertIsNotNone(self.compliance_manager)
        self.assertTrue(hasattr(self.compliance_manager, 'check_gdpr_compliance'))
        self.assertTrue(hasattr(self.compliance_manager, 'check_ccpa_compliance'))
        self.assertTrue(hasattr(self.compliance_manager, 'check_data_protection'))
    
    def test_gdpr_postback_compliance(self):
        """Test GDPR compliance for postback data handling"""
        result = self.compliance_manager.check_gdpr_compliance(self.postback)
        self.assertIsInstance(result, dict)
        self.assertIn('compliant', result)
        self.assertIn('data_minimization', result)
        self.assertIn('violations', result)
    
    def test_ccpa_transparency_compliance(self):
        """Test CCPA transparency requirements for postbacks"""
        result = self.compliance_manager.check_ccpa_compliance(self.postback)
        self.assertIsInstance(result, dict)
        self.assertIn('compliant', result)
        self.assertIn('transparency', result)
        self.assertIn('data_collection_notice', result)
    
    def test_data_protection_compliance(self):
        """Test data protection compliance"""
        result = self.compliance_manager.check_data_protection(self.postback)
        self.assertIsInstance(result, dict)
        self.assertIn('compliant', result)
        self.assertIn('encryption_required', result)
        self.assertIn('access_controls', result)
    
    def test_postback_endpoint_compliance(self):
        """Test compliance for postback endpoints"""
        endpoint = PostbackEndpoint.objects.create(
            name="Test Endpoint",
            url="https://example.com/postback",
            method="POST",
            authentication_required=True,
            data_encryption=True,
            created_by=self.admin_user
        )
        
        result = self.compliance_manager.check_endpoint_compliance(endpoint)
        self.assertIsInstance(result, dict)
        self.assertIn('compliant', result)
        self.assertIn('security_standards', result)
        self.assertIn('data_protection', result)
    
    def test_postback_rule_compliance(self):
        """Test compliance for postback rules"""
        rule = PostbackRule.objects.create(
            name="Test Rule",
            condition="event_type == 'conversion'",
            action="send_postback",
            priority=1,
            is_active=True,
            created_by=self.admin_user
        )
        
        result = self.compliance_manager.check_rule_compliance(rule)
        self.assertIsInstance(result, dict)
        self.assertIn('compliant', result)
        self.assertIn('rule_logic', result)
        self.assertIn('data_usage', result)


class PrivacyManagerTest(BaseComplianceTest):
    """Test PrivacyManager functionality for postback"""
    
    def setUp(self):
        super().setUp()
        self.privacy_manager = PrivacyManager()
        
        # Create test data
        self.postback = Postback.objects.create(
            user=self.regular_user,
            partner=self.partner_user,
            offer_id="PRIVACY-001",
            event_type="click",
            amount=Decimal("0.00"),
            currency="USD",
            status="completed",
            ip_address="192.168.1.1",
            user_agent="Privacy Test Browser",
            created_by=self.regular_user
        )
    
    def test_postback_consent_management(self):
        """Test consent management for postback data processing"""
        consent_data = {
            'user_id': self.regular_user.id,
            'consent_type': 'postback_tracking',
            'consent_given': True,
            'timestamp': timezone.now().isoformat(),
            'data_types': ['event_data', 'ip_address', 'user_agent', 'conversion_data']
        }
        
        result = self.privacy_manager.record_postback_consent(consent_data)
        self.assertTrue(result.get('success', False))
        
        # Verify consent retrieval
        retrieved_consent = self.privacy_manager.get_postback_consent(
            self.regular_user.id, 'postback_tracking'
        )
        self.assertIsNotNone(retrieved_consent)
        self.assertTrue(retrieved_consent.get('consent_given', False))
    
    def test_postback_data_privacy(self):
        """Test privacy for postback data"""
        privacy_result = self.privacy_manager.protect_postback_data(self.postback.id)
        self.assertTrue(privacy_result.get('success', False))
        self.assertIn('data_anonymization', privacy_result)
        self.assertIn('access_controls', privacy_result)
    
    def test_partner_data_privacy(self):
        """Test privacy for partner data"""
        partner_data = {
            'partner_id': self.partner_user.id,
            'postback_data': 'sensitive_partner_metrics',
            'revenue_data': 'confidential_revenue_info',
            'user_analytics': 'aggregated_user_data'
        }
        
        result = self.privacy_manager.protect_partner_data(partner_data)
        self.assertTrue(result.get('success', False))
        self.assertIn('encryption_applied', result)
        self.assertIn('access_restricted', result)
    
    def test_postback_data_portability(self):
        """Test data portability for postback data"""
        # Create user postback history
        for i in range(3):
            Postback.objects.create(
                user=self.regular_user,
                partner=self.partner_user,
                offer_id=f"PORT-{i}",
                event_type="conversion",
                amount=Decimal(f"{i+1}.00"),
                currency="USD",
                status="completed",
                created_by=self.regular_user
            )
        
        portability_result = self.privacy_manager.export_postback_data(
            self.regular_user.id, format='json'
        )
        self.assertTrue(portability_result.get('success', False))
        self.assertIn('export_data', portability_result)
        self.assertIn('download_url', portability_result)
    
    def test_right_to_be_forgotten_postback(self):
        """Test right to be forgotten for postback data"""
        # Create comprehensive user postback data
        postbacks = []
        for i in range(5):
            postback = Postback.objects.create(
                user=self.regular_user,
                partner=self.partner_user,
                offer_id=f"DELETE-{i}",
                event_type="conversion",
                amount=Decimal(f"{i+2}.00"),
                currency="USD",
                status="completed",
                created_by=self.regular_user
            )
            postbacks.append(postback)
        
        # Process deletion request
        deletion_result = self.privacy_manager.process_postback_deletion(
            self.regular_user.id
        )
        self.assertTrue(deletion_result.get('success', False))
        
        # Verify data anonymization (not deletion for audit purposes)
        remaining_postbacks = Postback.objects.filter(
            user=self.regular_user
        ).count()
        self.assertGreater(remaining_postbacks, 0)  # Should be anonymized, not deleted
        
        # Verify anonymization
        anonymized_postback = Postback.objects.filter(
            user=self.regular_user
        ).first()
        self.assertIsNone(anonymized_postback.user)
    
    def test_sensitive_postback_data_protection(self):
        """Test protection of sensitive postback data"""
        # Create sensitive postback
        sensitive_postback = Postback.objects.create(
            user=self.regular_user,
            partner=self.partner_user,
            offer_id="SENSITIVE-001",
            event_type="conversion",
            amount=Decimal("100.00"),
            currency="USD",
            status="completed",
            is_sensitive=True,
            created_by=self.regular_user
        )
        
        protection_result = self.privacy_manager.protect_sensitive_postback(
            sensitive_postback.id
        )
        self.assertTrue(protection_result.get('success', False))
        self.assertIn('encryption_applied', protection_result)
        self.assertIn('access_restricted', protection_result)


class DataRetentionManagerTest(BaseComplianceTest):
    """Test DataRetentionManager functionality"""
    
    def setUp(self):
        super().setUp()
        self.retention_manager = DataRetentionManager()
        
        # Create test data
        self.postback = Postback.objects.create(
            user=self.regular_user,
            partner=self.partner_user,
            offer_id="RETENTION-001",
            event_type="conversion",
            amount=Decimal("10.00"),
            currency="USD",
            status="completed",
            created_by=self.regular_user
        )
    
    def test_postback_retention(self):
        """Test retention policy for postback data"""
        # Create old postback
        old_date = timezone.now() - timedelta(days=3000)  # Very old
        
        with patch('django.utils.timezone.now', return_value=old_date):
            old_postback = Postback.objects.create(
                user=self.regular_user,
                partner=self.partner_user,
                offer_id="OLD-001",
                event_type="conversion",
                amount=Decimal("5.00"),
                currency="USD",
                status="completed",
                created_by=self.regular_user
            )
        
        # Apply retention policy
        deleted_count = self.retention_manager.apply_postback_retention(
            retention_years=7  # 7 years for financial records
        )
        self.assertEqual(deleted_count, 0)  # Should not be deleted yet
        
        # Verify preservation
        preserved_postback = Postback.objects.get(id=old_postback.id)
        self.assertIsNotNone(preserved_postback)
    
    def test_postback_log_retention(self):
        """Test retention for postback logs"""
        # Create old log
        old_date = timezone.now() - timedelta(days=400)
        
        with patch('django.utils.timezone.now', return_value=old_date):
            old_log = PostbackLog.objects.create(
                postback=self.postback,
                log_type="request",
                status="success",
                details="Old log entry",
                created_at=old_date
            )
        
        # Apply retention policy (shorter for logs)
        deleted_count = self.retention_manager.apply_log_retention(
            retention_days=365
        )
        self.assertGreater(deleted_count, 0)
        
        # Verify deletion
        with self.assertRaises(PostbackLog.DoesNotExist):
            PostbackLog.objects.get(id=old_log.id)
    
    def test_audit_retention(self):
        """Test retention for audit logs"""
        # Create old audit
        old_date = timezone.now() - timedelta(days=3000)
        
        with patch('django.utils.timezone.now', return_value=old_date):
            old_audit = PostbackAudit.objects.create(
                postback=self.postback,
                audit_type="compliance_check",
                result="passed",
                auditor=self.admin_user,
                details="Old audit entry"
            )
        
        # Apply audit retention (longer for compliance)
        deleted_count = self.retention_manager.apply_audit_retention(
            retention_years=10
        )
        self.assertEqual(deleted_count, 0)  # Should not be deleted
        
        # Verify preservation
        preserved_audit = PostbackAudit.objects.get(id=old_audit.id)
        self.assertIsNotNone(preserved_audit)
    
    def test_retention_audit_logging(self):
        """Test audit logging for retention operations"""
        # Create test data
        log = PostbackLog.objects.create(
            postback=self.postback,
            log_type="response",
            status="success",
            details="Test log entry"
        )
        
        # Apply retention with audit logging
        with patch('api.postback.compliance.logger') as mock_logger:
            self.retention_manager.apply_log_retention(retention_days=0)
            
            # Verify audit logging
            mock_logger.info.assert_called()
            log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
            self.assertTrue(any('postback_retention' in log for log in log_calls))


class PostbackSecurityComplianceTest(BaseComplianceTest):
    """Test security compliance for postback systems"""
    
    def setUp(self):
        super().setUp()
        
        # Create security test data
        self.endpoint = PostbackEndpoint.objects.create(
            name="Security Test Endpoint",
            url="https://secure.example.com/postback",
            method="POST",
            authentication_required=True,
            data_encryption=True,
            ssl_required=True,
            created_by=self.admin_user
        )
        
        self.postback = Postback.objects.create(
            user=self.regular_user,
            partner=self.partner_user,
            offer_id="SECURITY-001",
            event_type="conversion",
            amount=Decimal("15.00"),
            currency="USD",
            status="completed",
            endpoint=self.endpoint,
            created_by=self.regular_user
        )
    
    def test_endpoint_security_compliance(self):
        """Test security compliance for postback endpoints"""
        result = check_postback_compliance(self.endpoint.id)
        self.assertIsInstance(result, dict)
        self.assertIn('compliant', result)
        self.assertIn('security_standards', result)
        self.assertIn('encryption_requirements', result)
    
    def test_data_transmission_security(self):
        """Test security for data transmission"""
        transmission_result = self.compliance_manager.check_transmission_security(
            self.postback.id
        )
        self.assertIsInstance(transmission_result, dict)
        self.assertIn('compliant', transmission_result)
        self.assertIn('encryption_in_transit', transmission_result)
        self.assertIn('authentication', transmission_result)
    
    def test_postback_integrity_compliance(self):
        """Test integrity compliance for postbacks"""
        # Create postback with integrity hash
        postback_with_hash = Postback.objects.create(
            user=self.regular_user,
            partner=self.partner_user,
            offer_id="INTEGRITY-001",
            event_type="conversion",
            amount=Decimal("20.00"),
            currency="USD",
            status="completed",
            integrity_hash="generated_hash",
            created_by=self.regular_user
        )
        
        integrity_result = self.compliance_manager.check_integrity_compliance(
            postback_with_hash.id
        )
        self.assertIsInstance(integrity_result, dict)
        self.assertIn('compliant', integrity_result)
        self.assertIn('hash_verified', integrity_result)
        self.assertIn('tamper_evidence', integrity_result)
    
    def test_access_control_compliance(self):
        """Test access control compliance"""
        access_result = self.compliance_manager.check_access_control_compliance(
            self.endpoint.id
        )
        self.assertIsInstance(access_result, dict)
        self.assertIn('compliant', access_result)
        self.assertIn('authorization_required', access_result)
        self.assertIn('role_based_access', access_result)
    
    def test_api_security_compliance(self):
        """Test API security compliance"""
        # Create API security test
        security_config = PostbackSecurity.objects.create(
            endpoint=self.endpoint,
            require_https=True,
            rate_limit_enabled=True,
            ip_whitelist_enabled=False,
            api_key_required=True,
            created_by=self.admin_user
        )
        
        api_result = self.compliance_manager.check_api_security_compliance(
            security_config.id
        )
        self.assertIsInstance(api_result, dict)
        self.assertIn('compliant', api_result)
        self.assertIn('https_required', api_result)
        self.assertIn('rate_limiting', api_result)
        self.assertIn('api_authentication', api_result)


class PostbackDataProcessingComplianceTest(BaseComplianceTest):
    """Test data processing compliance"""
    
    def setUp(self):
        super().setUp()
        
        # Create data processing test data
        self.rule = PostbackRule.objects.create(
            name="Data Processing Rule",
            condition="amount > 10",
            action="enhanced_tracking",
            priority=1,
            is_active=True,
            created_by=self.admin_user
        )
        
        self.postback = Postback.objects.create(
            user=self.regular_user,
            partner=self.partner_user,
            offer_id="PROCESSING-001",
            event_type="conversion",
            amount=Decimal("15.00"),
            currency="USD",
            status="completed",
            created_by=self.regular_user
        )
    
    def test_data_processing_compliance(self):
        """Test compliance for data processing rules"""
        result = validate_postback_system(self.rule.id)
        self.assertIsInstance(result, dict)
        self.assertIn('compliant', result)
        self.assertIn('processing_logic', result)
        self.assertIn('data_usage', result)
    
    def test_data_aggregation_compliance(self):
        """Test compliance for data aggregation"""
        # Create aggregation test
        aggregation_data = {
            'aggregation_type': 'daily_summary',
            'data_fields': ['amount', 'event_type', 'conversion_rate'],
            'retention_period': 90,
            'anonymization_level': 'partial'
        }
        
        result = self.compliance_manager.check_aggregation_compliance(aggregation_data)
        self.assertIsInstance(result, dict)
        self.assertIn('compliant', result)
        self.assertIn('anonymization_adequate', result)
        self.assertIn('retention_appropriate', result)
    
    def test_real_time_processing_compliance(self):
        """Test compliance for real-time processing"""
        # Create real-time processing config
        realtime_config = PostbackConfiguration.objects.create(
            name="Real-time Config",
            processing_type="real_time",
            max_delay_seconds=5,
            data_encryption=True,
            audit_logging=True,
            created_by=self.admin_user
        )
        
        realtime_result = self.compliance_manager.check_realtime_compliance(
            realtime_config.id
        )
        self.assertIsInstance(realtime_result, dict)
        self.assertIn('compliant', realtime_result)
        self.assertIn('processing_delay', realtime_result)
        self.assertIn('data_protection', realtime_result)
    
    def test_batch_processing_compliance(self):
        """Test compliance for batch processing"""
        # Create batch processing config
        batch_config = PostbackConfiguration.objects.create(
            name="Batch Config",
            processing_type="batch",
            batch_size=1000,
            processing_interval=3600,  # 1 hour
            data_compression=True,
            created_by=self.admin_user
        )
        
        batch_result = self.compliance_manager.check_batch_compliance(batch_config.id)
        self.assertIsInstance(batch_result, dict)
        self.assertIn('compliant', batch_result)
        self.assertIn('batch_size_appropriate', batch_result)
        self.assertIn('data_security', batch_result)


class PostbackPartnerComplianceTest(BaseComplianceTest):
    """Test partner compliance for postback systems"""
    
    def setUp(self):
        super().setUp()
        
        # Create partner test data
        self.partner_endpoint = PostbackEndpoint.objects.create(
            name="Partner Endpoint",
            url="https://partner.example.com/postback",
            method="POST",
            authentication_required=True,
            partner=self.partner_user,
            created_by=self.admin_user
        )
        
        self.partner_postback = Postback.objects.create(
            user=self.regular_user,
            partner=self.partner_user,
            offer_id="PARTNER-001",
            event_type="conversion",
            amount=Decimal("25.00"),
            currency="USD",
            status="completed",
            endpoint=self.partner_endpoint,
            created_by=self.regular_user
        )
    
    def test_partner_data_sharing_compliance(self):
        """Test compliance for partner data sharing"""
        result = check_postback_compliance(self.partner_postback.id)
        self.assertIsInstance(result, dict)
        self.assertIn('compliant', result)
        self.assertIn('data_sharing_agreement', result)
        self.assertIn('partner_authorization', result)
    
    def test_partner_privacy_compliance(self):
        """Test privacy compliance for partner data"""
        privacy_result = self.compliance_manager.check_partner_privacy_compliance(
            self.partner_user.id
        )
        self.assertIsInstance(privacy_result, dict)
        self.assertIn('compliant', privacy_result)
        self.assertIn('data_protection_standards', privacy_result)
        self.assertIn('user_consent', privacy_result)
    
    def test_contractual_compliance(self):
        """Test contractual compliance for partners"""
        # Create contract test data
        contract_data = {
            'partner_id': self.partner_user.id,
            'contract_type': 'data_processing',
            'data_categories': ['conversion_events', 'user_analytics'],
            'retention_period': 365,
            'security_requirements': ['encryption', 'audit_logging']
        }
        
        result = self.compliance_manager.check_contractual_compliance(contract_data)
        self.assertIsInstance(result, dict)
        self.assertIn('compliant', result)
        self.assertIn('contract_terms_met', result)
        self.assertIn('security_requirements', result)
    
    def test_partner_audit_compliance(self):
        """Test audit compliance for partner relationships"""
        partner_audit = PostbackAudit.objects.create(
            postback=self.partner_postback,
            audit_type="partner_compliance",
            result="passed",
            auditor=self.admin_user,
            details="Partner compliance audit completed"
        )
        
        audit_result = self.compliance_manager.check_partner_audit_compliance(
            partner_audit.id
        )
        self.assertIsInstance(audit_result, dict)
        self.assertIn('compliant', audit_result)
        self.assertIn('audit_procedure', audit_result)
        self.assertIn('documentation', audit_result)


class ComplianceIntegrationTest(BaseComplianceTest):
    """Integration tests for postback compliance"""
    
    def test_end_to_end_compliance_workflow(self):
        """Test complete compliance workflow"""
        # Create comprehensive test data
        endpoint = PostbackEndpoint.objects.create(
            name="Integration Endpoint",
            url="https://integration.example.com/postback",
            method="POST",
            authentication_required=True,
            data_encryption=True,
            created_by=self.admin_user
        )
        
        postback = Postback.objects.create(
            user=self.regular_user,
            partner=self.partner_user,
            offer_id="INTEGRATION-001",
            event_type="conversion",
            amount=Decimal("30.00"),
            currency="USD",
            status="completed",
            endpoint=endpoint,
            created_by=self.regular_user
        )
        
        # Record user consent
        consent_data = {
            'user_id': self.regular_user.id,
            'consent_type': 'postback_tracking',
            'consent_given': True,
            'timestamp': timezone.now().isoformat()
        }
        
        privacy_manager = PrivacyManager()
        privacy_manager.record_postback_consent(consent_data)
        
        # Create compliance check
        compliance_check = PostbackCompliance.objects.create(
            postback=postback,
            check_type="full_compliance",
            status="passed",
            checker=self.admin_user,
            details="Full compliance check passed"
        )
        
        # Check compliance at each step
        postback_compliance = check_postback_compliance(postback.id)
        endpoint_compliance = check_postback_compliance(endpoint.id)
        
        self.assertIsInstance(postback_compliance, dict)
        self.assertIsInstance(endpoint_compliance, dict)
        
        # Test data portability
        portability_result = privacy_manager.export_postback_data(
            self.regular_user.id
        )
        self.assertTrue(portability_result.get('success', False))
    
    def test_cross_system_compliance_consistency(self):
        """Test consistency across different compliance systems"""
        # Create test data
        rule = PostbackRule.objects.create(
            name="Cross System Rule",
            condition="event_type == 'conversion'",
            action="send_postback",
            priority=1,
            is_active=True,
            created_by=self.admin_user
        )
        
        # Test compliance from different managers
        postback_compliance = PostbackComplianceManager()
        privacy_compliance = PrivacyManager()
        
        postback_result = postback_compliance.check_full_compliance(rule)
        privacy_result = privacy_compliance.assess_rule_privacy(rule.id)
        
        # Results should be consistent
        self.assertEqual(
            postback_result.get('compliant'),
            privacy_result.get('compliant')
        )
    
    def test_compliance_reporting_integration(self):
        """Test integrated compliance reporting"""
        # Create comprehensive test data
        for i in range(3):
            Postback.objects.create(
                user=self.regular_user,
                partner=self.partner_user,
                offer_id=f"REPORT-{i}",
                event_type="conversion",
                amount=Decimal(f"{i+5}.00"),
                currency="USD",
                status="completed",
                created_by=self.regular_user
            )
        
        report = generate_compliance_report(
            standards=['gdpr', 'ccpa', 'data_protection'],
            date_range=(timezone.now() - timedelta(days=30), timezone.now())
        )
        
        self.assertIsInstance(report, dict)
        self.assertIn('summary', report)
        self.assertIn('gdpr_compliance', report)
        self.assertIn('ccpa_compliance', report)
        self.assertIn('data_protection_compliance', report)
        self.assertIn('recommendations', report)


class CompliancePerformanceTest(BaseComplianceTest):
    """Performance tests for compliance operations"""
    
    def test_large_dataset_compliance_checking(self):
        """Test compliance checking with large datasets"""
        # Create large dataset
        postbacks = []
        for i in range(100):
            postback = Postback.objects.create(
                user=self.regular_user,
                partner=self.partner_user,
                offer_id=f"PERF-{i}",
                event_type="conversion",
                amount=Decimal(f"{i+1}.00"),
                currency="USD",
                status="completed",
                created_by=self.regular_user
            )
            postbacks.append(postback)
        
        # Measure performance
        import time
        start_time = time.time()
        
        compliance_manager = PostbackComplianceManager()
        results = []
        for postback in postbacks:
            result = compliance_manager.check_full_compliance(postback)
            results.append(result)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Performance assertion
        self.assertLess(duration, 12.0)  # 12 seconds max
        self.assertEqual(len(results), 100)
    
    def test_bulk_privacy_processing(self):
        """Test performance of bulk privacy processing"""
        privacy_manager = PrivacyManager()
        
        # Create bulk consent data
        consent_data = []
        for i in range(500):
            consent_data.append({
                'user_id': f"user_{i}",
                'consent_type': 'postback_tracking',
                'consent_given': True,
                'timestamp': timezone.now().isoformat()
            })
        
        # Measure performance
        import time
        start_time = time.time()
        
        result = privacy_manager.process_bulk_consent(consent_data)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Performance assertion
        self.assertLess(duration, 8.0)  # 8 seconds max
        self.assertTrue(result.get('success', False))


class ComplianceErrorHandlingTest(BaseComplianceTest):
    """Test error handling in compliance operations"""
    
    def test_invalid_postback_data_handling(self):
        """Test handling of invalid postback data"""
        compliance_manager = PostbackComplianceManager()
        
        invalid_data = {
            'user': None,  # Invalid user
            'partner': None,  # Invalid partner
            'amount': -10.00,  # Invalid amount
            'currency': 'INVALID',  # Invalid currency
            'event_type': 'invalid_type'  # Invalid event type
        }
        
        with self.assertRaises(ComplianceError):
            compliance_manager.validate_postback_data(invalid_data)
    
    def test_compliance_check_with_missing_data(self):
        """Test compliance checking with missing required data"""
        with self.assertRaises(ComplianceError):
            check_postback_compliance(None)
    
    def test_privacy_request_errors(self):
        """Test error handling in privacy requests"""
        privacy_manager = PrivacyManager()
        
        # Test invalid user request
        result = privacy_manager.export_postback_data(99999)
        self.assertFalse(result.get('success', True))
        self.assertIn('error', result)
    
    def test_retention_policy_errors(self):
        """Test error handling in retention operations"""
        retention_manager = DataRetentionManager()
        
        # Test with invalid retention policy
        with self.assertRaises(ComplianceError):
            retention_manager.apply_postback_retention(policy_id='invalid_policy')


class ComplianceSecurityTest(BaseComplianceTest):
    """Test security aspects of compliance operations"""
    
    def test_sensitive_postback_data_encryption(self):
        """Test encryption of sensitive postback data"""
        privacy_manager = PrivacyManager()
        
        sensitive_data = {
            'user_id': self.regular_user.id,
            'conversion_patterns': 'detailed_user_behavior',
            'revenue_data': 'confidential_financial_info',
            'partner_metrics': 'sensitive_business_data'
        }
        
        # Store sensitive data
        result = privacy_manager.store_sensitive_postback_data(sensitive_data)
        self.assertTrue(result.get('success', False))
        
        # Retrieve and verify encryption
        stored_data = privacy_manager.retrieve_sensitive_postback_data(
            self.regular_user.id
        )
        self.assertIsNotNone(stored_data)
        self.assertNotEqual(
            stored_data.get('conversion_patterns'), 
            'detailed_user_behavior'
        )
    
    def test_postback_data_integrity(self):
        """Test integrity of postback data"""
        # Create postback with integrity hash
        postback = Postback.objects.create(
            user=self.regular_user,
            partner=self.partner_user,
            offer_id="INTEGRITY-SEC-001",
            event_type="conversion",
            amount=Decimal("50.00"),
            currency="USD",
            status="completed",
            integrity_hash="generated_hash_value",
            created_by=self.regular_user
        )
        
        # Generate integrity hash
        integrity_result = self.compliance_manager.generate_integrity_hash(
            postback.id
        )
        self.assertTrue(integrity_result.get('success', False))
        self.assertIn('hash', integrity_result)
        
        # Verify integrity
        verification_result = self.compliance_manager.verify_integrity(
            postback.id, integrity_result['hash']
        )
        self.assertTrue(verification_result.get('valid', False))
    
    def test_access_control_compliance(self):
        """Test access control for compliance operations"""
        # Test regular user cannot access admin compliance functions
        with self.assertRaises(PermissionError):
            compliance_manager = PostbackComplianceManager()
            compliance_manager.admin_compliance_overview(
                user=self.regular_user
            )
        
        # Test admin user can access compliance functions
        try:
            compliance_manager = PostbackComplianceManager()
            compliance_manager.admin_compliance_overview(
                user=self.admin_user
            )
        except PermissionError:
            self.fail("Admin user should have access to compliance functions")
    
    def test_secure_endpoint_data_storage(self):
        """Test secure storage of endpoint data"""
        # Create high-security endpoint
        secure_endpoint = PostbackEndpoint.objects.create(
            name="High Security Endpoint",
            url="https://secure.example.com/postback",
            method="POST",
            authentication_required=True,
            data_encryption=True,
            ssl_required=True,
            ip_whitelist_enabled=True,
            created_by=self.admin_user
        )
        
        # Store with security
        privacy_manager = PrivacyManager()
        security_result = privacy_manager.secure_endpoint_data(secure_endpoint.id)
        self.assertTrue(security_result.get('success', False))
        self.assertIn('encryption_applied', security_result)
        self.assertIn('access_controls', security_result)
