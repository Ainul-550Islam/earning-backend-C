"""
Comprehensive compliance testing for rate_limit module.

This test file covers all GDPR, CCPA, HIPAA compliance logic and
data protection functionality that was previously untested.
"""

import json
from datetime import datetime, timedelta, date
from unittest.mock import patch, MagicMock, AsyncMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from django.core.management import call_command
import tempfile
import os

from api.rate_limit.models import (
    RateLimitLog, RateLimitConfig, UserRateLimitProfile, 
    AbuseReport, IPBlockList, RateLimitInsight
)
from api.rate_limit.compliance import (
    ComplianceStandard, ComplianceCategory, ComplianceRule,
    ComplianceAuditTrail, DataRetentionManager, ConsentManager,
    ComplianceManager, compliance_manager
)
from api.rate_limit.exceptions import ComplianceError
from django.contrib.auth import get_user_model
User = get_user_model()

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
        
        # Create test rate limit data
        self.rate_limit_config = RateLimitConfig.objects.create(
            name='test_config',
            rate_limit_type='api',
            requests_per_minute=100,
            burst_size=200,
            is_active=True
        )
        
        self.user_profile = UserRateLimitProfile.objects.create(
            user=self.regular_user,
            tier='standard',
            daily_limit=1000,
            hourly_limit=100,
            is_active=True
        )
        
        self.rate_limit_log = RateLimitLog.objects.create(
            user=self.regular_user,
            ip_address='192.168.1.1',
            endpoint='/api/test/',
            method='GET',
            status_code=200,
            response_time=0.5,
            user_agent='Mozilla/5.0'
        )
        
        cache.clear()

        # Managers used by integration/security/performance subclasses that have no setUp
        self.audit_trail = ComplianceAuditTrail()
        self.retention_manager = DataRetentionManager()
        self.consent_manager = ConsentManager()
        self.compliance_mgr = ComplianceManager()
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()


class ComplianceStandardTest(BaseComplianceTest):
    """Test cases for ComplianceStandard enumeration"""
    
    def test_compliance_standards(self):
        """Test compliance standard constants"""
        self.assertEqual(ComplianceStandard.GDPR, 'gdpr')
        self.assertEqual(ComplianceStandard.CCPA, 'ccpa')
        self.assertEqual(ComplianceStandard.HIPAA, 'hipaa')
        self.assertEqual(ComplianceStandard.SOX, 'sox')
        self.assertEqual(ComplianceStandard.PCI_DSS, 'pci_dss')
        
        # Test choices
        choices = ComplianceStandard.CHOICES
        self.assertEqual(len(choices), 5)
        self.assertIn((ComplianceStandard.GDPR, 'GDPR'), choices)
        self.assertIn((ComplianceStandard.CCPA, 'CCPA'), choices)
        self.assertIn((ComplianceStandard.HIPAA, 'HIPAA'), choices)
        self.assertIn((ComplianceStandard.SOX, 'SOX'), choices)
        self.assertIn((ComplianceStandard.PCI_DSS, 'PCI-DSS'), choices)


class ComplianceCategoryTest(BaseComplianceTest):
    """Test cases for ComplianceCategory enumeration"""
    
    def test_compliance_categories(self):
        """Test compliance category constants"""
        self.assertEqual(ComplianceCategory.DATA_PROTECTION, 'data_protection')
        self.assertEqual(ComplianceCategory.PRIVACY, 'privacy')
        self.assertEqual(ComplianceCategory.SECURITY, 'security')
        self.assertEqual(ComplianceCategory.AUDIT_TRAIL, 'audit_trail')
        self.assertEqual(ComplianceCategory.RETENTION, 'retention')
        self.assertEqual(ComplianceCategory.CONSENT, 'consent')
        
        # Test choices
        choices = ComplianceCategory.CHOICES
        self.assertEqual(len(choices), 6)
        self.assertIn((ComplianceCategory.DATA_PROTECTION, 'Data Protection'), choices)
        self.assertIn((ComplianceCategory.PRIVACY, 'Privacy'), choices)
        self.assertIn((ComplianceCategory.SECURITY, 'Security'), choices)
        self.assertIn((ComplianceCategory.AUDIT_TRAIL, 'Audit Trail'), choices)
        self.assertIn((ComplianceCategory.RETENTION, 'Retention'), choices)
        self.assertIn((ComplianceCategory.CONSENT, 'Consent'), choices)


class ComplianceRuleTest(BaseComplianceTest):
    """Test cases for ComplianceRule"""
    
    def test_compliance_rule_creation(self):
        """Test compliance rule creation"""
        def test_check_function(context):
            return {'compliant': True, 'details': 'Test check passed'}
        
        rule = ComplianceRule(
            name='test_rule',
            standard=ComplianceStandard.GDPR,
            category=ComplianceCategory.DATA_PROTECTION,
            description='Test compliance rule',
            check_function=test_check_function,
            severity='high',
            enabled=True
        )
        
        self.assertEqual(rule.name, 'test_rule')
        self.assertEqual(rule.standard, ComplianceStandard.GDPR)
        self.assertEqual(rule.category, ComplianceCategory.DATA_PROTECTION)
        self.assertEqual(rule.severity, 'high')
        self.assertTrue(rule.enabled)
        self.assertIsNone(rule.last_checked)
        self.assertIsNone(rule.last_result)
    
    def test_compliance_rule_check_passed(self):
        """Test compliance rule check that passes"""
        def test_check_function(context):
            return {'compliant': True, 'details': 'Test check passed'}
        
        rule = ComplianceRule(
            name='test_rule',
            standard=ComplianceStandard.GDPR,
            category=ComplianceCategory.DATA_PROTECTION,
            description='Test compliance rule',
            check_function=test_check_function,
            enabled=True
        )
        
        result = rule.check()
        
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['rule'], 'test_rule')
        self.assertEqual(result['standard'], ComplianceStandard.GDPR)
        self.assertEqual(result['category'], ComplianceCategory.DATA_PROTECTION)
        self.assertEqual(result['severity'], 'high')
        self.assertTrue(result['result']['compliant'])
        self.assertIn('checked_at', result)
        self.assertIsNotNone(rule.last_checked)
        self.assertIsNotNone(rule.last_result)
    
    def test_compliance_rule_check_failed(self):
        """Test compliance rule check that fails"""
        def test_check_function(context):
            return {'compliant': False, 'details': 'Test check failed'}
        
        rule = ComplianceRule(
            name='test_rule',
            standard=ComplianceStandard.GDPR,
            category=ComplianceCategory.DATA_PROTECTION,
            description='Test compliance rule',
            check_function=test_check_function,
            enabled=True
        )
        
        result = rule.check()
        
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['rule'], 'test_rule')
        self.assertFalse(result['result']['compliant'])
    
    def test_compliance_rule_check_disabled(self):
        """Test compliance rule check when disabled"""
        def test_check_function(context):
            return {'compliant': True, 'details': 'Test check passed'}
        
        rule = ComplianceRule(
            name='test_rule',
            standard=ComplianceStandard.GDPR,
            category=ComplianceCategory.DATA_PROTECTION,
            description='Test compliance rule',
            check_function=test_check_function,
            enabled=False
        )
        
        result = rule.check()
        
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['reason'], 'Rule disabled')
    
    def test_compliance_rule_check_error(self):
        """Test compliance rule check with error"""
        def test_check_function(context):
            raise Exception("Test error")
        
        rule = ComplianceRule(
            name='test_rule',
            standard=ComplianceStandard.GDPR,
            category=ComplianceCategory.DATA_PROTECTION,
            description='Test compliance rule',
            check_function=test_check_function,
            enabled=True
        )
        
        result = rule.check()
        
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error'], 'Test error')
        self.assertIn('checked_at', result)


class ComplianceAuditTrailTest(BaseComplianceTest):
    """Test cases for ComplianceAuditTrail"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.audit_trail = ComplianceAuditTrail()
    
    def test_log_action(self):
        """Test logging an action"""
        with patch('django.core.cache.cache') as mock_cache:
            mock_cache.get.return_value = []
            mock_cache.set.return_value = True
            
            self.audit_trail.log_action(
                action='test_action',
                user_id=self.regular_user.pk,
                ip_address='192.168.1.1',
                resource_type='RateLimitConfig',
                resource_id=self.rate_limit_config.pk,
                details={'test': 'data'},
                compliance_relevant=True
            )
            
            # Verify cache was called
            mock_cache.get.assert_called_once()
            mock_cache.set.assert_called_once()
            
            # Check cache key format
            cache_key = mock_cache.set.call_args[0][0]
            self.assertTrue(cache_key.startswith('compliance_audit:'))
    
    def test_log_action_without_user(self):
        """Test logging an action without user"""
        with patch('django.core.cache.cache') as mock_cache:
            mock_cache.get.return_value = []
            mock_cache.set.return_value = True
            
            self.audit_trail.log_action(
                action='system_action',
                ip_address='192.168.1.1',
                resource_type='RateLimitConfig',
                resource_id=self.rate_limit_config.pk,
                compliance_relevant=False
            )
            
            # Verify cache was called
            mock_cache.get.assert_called_once()
            mock_cache.set.assert_called_once()
    
    def test_get_audit_logs(self):
        """Test getting audit logs"""
        test_date = timezone.now().date()
        
        with patch('django.core.cache.cache') as mock_cache:
            test_logs = [
                {
                    'action': 'test_action',
                    'user_id': self.regular_user.pk,
                    'ip_address': '192.168.1.1',
                    'timestamp': timezone.now().isoformat(),
                    'compliance_relevant': True
                },
                {
                    'action': 'other_action',
                    'user_id': self.admin_user.pk,
                    'ip_address': '192.168.1.2',
                    'timestamp': timezone.now().isoformat(),
                    'compliance_relevant': False
                }
            ]
            mock_cache.get.return_value = test_logs
            
            logs = self.audit_trail.get_audit_logs(date=test_date)
            
            self.assertEqual(len(logs), 2)
            mock_cache.get.assert_called_once_with(f'compliance_audit:{test_date}')
    
    def test_get_audit_logs_with_filters(self):
        """Test getting audit logs with filters"""
        test_date = timezone.now().date()
        
        with patch('django.core.cache.cache') as mock_cache:
            test_logs = [
                {
                    'action': 'test_action',
                    'user_id': self.regular_user.pk,
                    'ip_address': '192.168.1.1',
                    'timestamp': timezone.now().isoformat(),
                    'compliance_relevant': True
                },
                {
                    'action': 'other_action',
                    'user_id': self.admin_user.pk,
                    'ip_address': '192.168.1.2',
                    'timestamp': timezone.now().isoformat(),
                    'compliance_relevant': False
                }
            ]
            mock_cache.get.return_value = test_logs
            
            # Filter by user
            logs = self.audit_trail.get_audit_logs(
                date=test_date,
                user_id=self.regular_user.pk
            )
            
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0]['user_id'], self.regular_user.pk)
            
            # Filter by action
            logs = self.audit_trail.get_audit_logs(
                date=test_date,
                action='test_action'
            )
            
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0]['action'], 'test_action')
            
            # Filter by compliance relevance
            logs = self.audit_trail.get_audit_logs(
                date=test_date,
                compliance_relevant=True
            )
            
            self.assertEqual(len(logs), 1)
            self.assertTrue(logs[0]['compliance_relevant'])
    
    def test_export_audit_logs(self):
        """Test exporting audit logs"""
        start_date = timezone.now().date() - timedelta(days=7)
        end_date = timezone.now().date()
        
        with patch.object(self.audit_trail, 'get_audit_logs') as mock_get_logs:
            mock_get_logs.return_value = [
                {
                    'action': 'test_action',
                    'user_id': self.regular_user.pk,
                    'ip_address': '192.168.1.1',
                    'timestamp': timezone.now().isoformat(),
                    'compliance_relevant': True
                }
            ]
            
            with patch.object(self.audit_trail.data_protection.encryption_manager, 'generate_hash') as mock_hash:
                mock_hash.return_value = 'hashed_ip'
                
                result = self.audit_trail.export_audit_logs(start_date, end_date, format='json')
                
                self.assertTrue(result['success'])
                self.assertIn('data', result)
                
                export_data = result['data']
                self.assertIn('export_metadata', export_data)
                self.assertIn('audit_logs', export_data)
                
                # Check metadata
                metadata = export_data['export_metadata']
                self.assertEqual(metadata['format'], 'json')
                self.assertEqual(metadata['start_date'], start_date.isoformat())
                self.assertEqual(metadata['end_date'], end_date.isoformat())
                self.assertEqual(metadata['record_count'], 1)
                
                # Check IP address was hashed
                audit_logs = export_data['audit_logs']
                self.assertEqual(audit_logs[0]['ip_address'], 'hashed_ip')
    
    def test_export_audit_logs_error(self):
        """Test exporting audit logs with error"""
        start_date = timezone.now().date() - timedelta(days=7)
        end_date = timezone.now().date()
        
        with patch.object(self.audit_trail, 'get_audit_logs') as mock_get_logs:
            mock_get_logs.side_effect = Exception("Test error")
            
            result = self.audit_trail.export_audit_logs(start_date, end_date)
            
            self.assertFalse(result['success'])
            self.assertEqual(result['error'], 'Test error')


class DataRetentionManagerTest(BaseComplianceTest):
    """Test cases for DataRetentionManager"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.retention_manager = DataRetentionManager()
    
    def test_load_retention_policies(self):
        """Test loading retention policies"""
        policies = self.retention_manager._load_retention_policies()
        
        self.assertIn('rate_limit_logs', policies)
        self.assertIn('user_profiles', policies)
        self.assertIn('abuse_reports', policies)
        self.assertIn('ip_blocks', policies)
        
        # Check policy structure
        rate_limit_policy = policies['rate_limit_logs']
        self.assertIn('retention_days', rate_limit_policy)
        self.assertIn('anonymize_after', rate_limit_policy)
        self.assertIn('delete_after', rate_limit_policy)
    
    def test_apply_retention_policies(self):
        """Test applying retention policies"""
        with patch.object(self.retention_manager, '_apply_retention_policy') as mock_apply:
            mock_apply.return_value = {
                'data_type': 'rate_limit_logs',
                'anonymized_count': 10,
                'deleted_count': 5,
                'processed_at': timezone.now().isoformat()
            }
            
            result = self.retention_manager.apply_retention_policies()
            
            self.assertTrue(result['success'])
            self.assertIn('results', result)
            self.assertIn('applied_at', result)
            
            # Should call apply_retention_policy for each data type
            self.assertEqual(mock_apply.call_count, 4)
    
    def test_apply_retention_policies_error(self):
        """Test applying retention policies with error"""
        with patch.object(self.retention_manager, '_apply_retention_policy') as mock_apply:
            mock_apply.side_effect = Exception("Test error")
            
            result = self.retention_manager.apply_retention_policies()
            
            self.assertFalse(result['success'])
            self.assertEqual(result['error'], 'Test error')
    
    def test_apply_retention_policy(self):
        """Test applying retention policy for specific data type"""
        policy = {
            'retention_days': 365,
            'anonymize_after': 180,
            'delete_after': 365
        }
        
        with patch.object(self.retention_manager, '_anonymize_data') as mock_anonymize:
            with patch.object(self.retention_manager, '_delete_data') as mock_delete:
                mock_anonymize.return_value = 10
                mock_delete.return_value = 5
                
                result = self.retention_manager._apply_retention_policy('rate_limit_logs', policy)
                
                self.assertEqual(result['data_type'], 'rate_limit_logs')
                self.assertEqual(result['anonymized_count'], 10)
                self.assertEqual(result['deleted_count'], 5)
                self.assertEqual(result['policy'], policy)
                self.assertIn('processed_at', result)
    
    def test_anonymize_data_rate_limit_logs(self):
        """Test anonymizing rate limit logs"""
        cutoff = timezone.now() - timedelta(days=200)
        
        # Create additional test logs
        for i in range(3):
            RateLimitLog.objects.create(
                user=self.regular_user,
                ip_address=f'192.168.1.{i+1}',
                endpoint='/api/test/',
                method='GET',
                status_code=200,
                response_time=0.5,
                user_agent='Mozilla/5.0',
                timestamp=timezone.now() - timedelta(days=250)
            )
        
        with patch.object(self.retention_manager.data_protection.encryption_manager, 'generate_hash') as mock_hash:
            mock_hash.return_value = 'hashed_value'
            
            count = self.retention_manager._anonymize_data('rate_limit_logs', cutoff)
            
            self.assertEqual(count, 3)  # Should anonymize 3 logs
            
            # Verify logs were anonymized
            logs = RateLimitLog.objects.filter(timestamp__lt=cutoff)
            for log in logs:
                self.assertIsNone(log.ip_address)
                self.assertIsNone(log.user_agent)
                self.assertIsNone(log.user)
                self.assertEqual(log.ip_address_hash, 'hashed_value')
                self.assertEqual(log.user_id_hash, 'hashed_value')
    
    def test_delete_data_rate_limit_logs(self):
        """Test deleting rate limit logs"""
        cutoff = timezone.now() - timedelta(days=400)
        
        # Create old logs
        for i in range(3):
            RateLimitLog.objects.create(
                user=self.regular_user,
                ip_address=f'192.168.1.{i+1}',
                endpoint='/api/test/',
                method='GET',
                status_code=200,
                response_time=0.5,
                user_agent='Mozilla/5.0',
                timestamp=timezone.now() - timedelta(days=450)
            )
        
        count = self.retention_manager._delete_data('rate_limit_logs', cutoff)
        
        self.assertEqual(count, 3)  # Should delete 3 logs
        
        # Verify logs were deleted
        remaining_logs = RateLimitLog.objects.filter(timestamp__lt=cutoff)
        self.assertEqual(remaining_logs.count(), 0)
    
    def test_delete_data_abuse_reports(self):
        """Test deleting abuse reports"""
        cutoff = timezone.now() - timedelta(days=400)
        
        # Create old investigated reports
        for i in range(3):
            AbuseReport.objects.create(
                user=self.regular_user,
                ip_address=f'192.168.1.{i+1}',
                reason='spam',
                description='Test spam report',
                is_investigated=True,
                created_at=timezone.now() - timedelta(days=450)
            )
        
        # Create uninvestigated report (should not be deleted)
        AbuseReport.objects.create(
            user=self.regular_user,
            ip_address='192.168.1.100',
            reason='spam',
            description='Uninvestigated report',
            is_investigated=False,
            created_at=timezone.now() - timedelta(days=450)
        )
        
        count = self.retention_manager._delete_data('abuse_reports', cutoff)
        
        self.assertEqual(count, 3)  # Should delete 3 investigated reports
        
        # Verify uninvestigated report remains
        remaining_reports = AbuseReport.objects.filter(created_at__lt=cutoff)
        self.assertEqual(remaining_reports.count(), 1)
        self.assertFalse(remaining_reports.first().is_investigated)
    
    def test_delete_data_ip_blocks(self):
        """Test deleting IP blocks"""
        cutoff = timezone.now() - timedelta(days=400)
        
        # Create expired non-permanent blocks
        for i in range(3):
            IPBlockList.objects.create(
                ip_address=f'192.168.1.{i+1}',
                reason='spam',
                permanent=False,
                expires_at=timezone.now() - timedelta(days=450)
            )
        
        # Create permanent block (should not be deleted)
        IPBlockList.objects.create(
            ip_address='192.168.1.100',
            reason='spam',
            permanent=True,
            expires_at=timezone.now() - timedelta(days=450)
        )
        
        # Create non-expired block (should not be deleted)
        IPBlockList.objects.create(
            ip_address='192.168.1.101',
            reason='spam',
            permanent=False,
            expires_at=timezone.now() + timedelta(days=30)
        )
        
        count = self.retention_manager._delete_data('ip_blocks', cutoff)
        
        self.assertEqual(count, 3)  # Should delete 3 expired non-permanent blocks
        
        # Verify permanent and non-expired blocks remain
        remaining_blocks = IPBlockList.objects.all()
        self.assertEqual(remaining_blocks.count(), 2)
    
    def test_get_retention_status(self):
        """Test getting retention status"""
        with patch('api.rate_limit.repositories.RepositoryFactory.get_all_repositories') as mock_factory:
            mock_repo = MagicMock()
            mock_repo.model.objects.count.return_value = 100
            mock_repo.model.objects.filter.return_value.count.return_value = 50
            mock_factory.return_value = {'rate_limit_log': mock_repo}
            
            status = self.retention_manager.get_retention_status()
            
            self.assertTrue(status['success'])
            self.assertIn('status', status)
            self.assertIn('checked_at', status)
            
            rate_limit_status = status['status']['rate_limit_logs']
            self.assertEqual(rate_limit_status['total_records'], 100)
            self.assertEqual(rate_limit_status['ready_to_anonymize'], 50)
            self.assertIn('policy', rate_limit_status)
    
    def test_get_retention_status_error(self):
        """Test getting retention status with error"""
        with patch('api.rate_limit.repositories.RepositoryFactory.get_all_repositories') as mock_factory:
            mock_factory.side_effect = Exception("Test error")
            
            status = self.retention_manager.get_retention_status()
            
            self.assertFalse(status['success'])
            self.assertEqual(status['error'], 'Test error')


class ConsentManagerTest(BaseComplianceTest):
    """Test cases for ConsentManager"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.consent_manager = ConsentManager()
    
    def test_load_consent_types(self):
        """Test loading consent types"""
        consent_types = self.consent_manager._load_consent_types()
        
        self.assertIn('data_processing', consent_types)
        self.assertIn('analytics', consent_types)
        self.assertIn('marketing', consent_types)
        
        # Check consent type structure
        data_processing = consent_types['data_processing']
        self.assertEqual(data_processing['name'], 'Data Processing')
        self.assertTrue(data_processing['required'])
        self.assertIn('retention_days', data_processing)
    
    def test_record_consent(self):
        """Test recording user consent"""
        with patch('django.core.cache.cache') as mock_cache:
            mock_cache.set.return_value = True
            
            with patch('api.rate_limit.compliance.ComplianceAuditTrail') as mock_audit:
                mock_audit_instance = MagicMock()
                mock_audit.return_value = mock_audit_instance
                
                result = self.consent_manager.record_consent(
                    user_id=self.regular_user.pk,
                    consent_type='data_processing',
                    granted=True,
                    ip_address='192.168.1.1',
                    details={'source': 'web_form'}
                )
                
                self.assertTrue(result['success'])
                self.assertIn('consent_data', result)
                
                consent_data = result['consent_data']
                self.assertEqual(consent_data['user_id'], self.regular_user.pk)
                self.assertEqual(consent_data['consent_type'], 'data_processing')
                self.assertTrue(consent_data['granted'])
                self.assertEqual(consent_data['ip_address'], '192.168.1.1')
                self.assertIn('recorded_at', consent_data)
                
                # Verify cache was called
                mock_cache.set.assert_called_once()
                
                # Verify audit trail was called
                mock_audit_instance.log_action.assert_called_once()
    
    def test_record_consent_invalid_type(self):
        """Test recording consent with invalid type"""
        result = self.consent_manager.record_consent(
            user_id=self.regular_user.pk,
            consent_type='invalid_type',
            granted=True
        )
        
        self.assertFalse(result['success'])
        self.assertIn('Unknown consent type', result['error'])
    
    def test_check_consent_granted(self):
        """Test checking granted consent"""
        consent_data = {
            'user_id': self.regular_user.pk,
            'consent_type': 'data_processing',
            'granted': True,
            'recorded_at': (timezone.now() - timedelta(days=10)).isoformat()
        }
        
        with patch('django.core.cache.cache') as mock_cache:
            mock_cache.get.return_value = consent_data
            
            result = self.consent_manager.check_consent(
                user_id=self.regular_user.pk,
                consent_type='data_processing'
            )
            
            self.assertTrue(result['has_consent'])
            self.assertFalse(result['required'])  # Will be set by consent_types
            self.assertIn('consent_data', result)
    
    def test_check_consent_no_record_optional(self):
        """Test checking consent with no record for optional consent"""
        with patch('django.core.cache.cache') as mock_cache:
            mock_cache.get.return_value = None
            
            result = self.consent_manager.check_consent(
                user_id=self.regular_user.pk,
                consent_type='analytics'  # Optional consent
            )
            
            self.assertTrue(result['has_consent'])
            self.assertFalse(result['required'])
            self.assertEqual(result['message'], 'Optional consent assumed')
    
    def test_check_consent_no_record_required(self):
        """Test checking consent with no record for required consent"""
        with patch('django.core.cache.cache') as mock_cache:
            mock_cache.get.return_value = None
            
            result = self.consent_manager.check_consent(
                user_id=self.regular_user.pk,
                consent_type='data_processing'  # Required consent
            )
            
            self.assertFalse(result['has_consent'])
            self.assertTrue(result['required'])
            self.assertEqual(result['message'], 'Required consent not found')
    
    def test_check_consent_expired(self):
        """Test checking expired consent"""
        consent_data = {
            'user_id': self.regular_user.pk,
            'consent_type': 'data_processing',
            'granted': True,
            'recorded_at': (timezone.now() - timedelta(days=400)).isoformat()  # Very old
        }
        
        with patch('django.core.cache.cache') as mock_cache:
            mock_cache.get.return_value = consent_data
            
            result = self.consent_manager.check_consent(
                user_id=self.regular_user.pk,
                consent_type='data_processing'
            )
            
            self.assertFalse(result['has_consent'])
            self.assertEqual(result['message'], 'Consent has expired')
    
    def test_withdraw_consent(self):
        """Test withdrawing consent"""
        with patch.object(self.consent_manager, 'record_consent') as mock_record:
            mock_record.return_value = {'success': True}
            
            with patch.object(self.consent_manager, '_delete_user_data') as mock_delete:
                
                result = self.consent_manager.withdraw_consent(
                    user_id=self.regular_user.pk,
                    consent_type='data_processing',
                    ip_address='192.168.1.1'
                )
                
                self.assertTrue(result['success'])
                
                # Verify consent was recorded as withdrawn
                mock_record.assert_called_once_with(
                    user_id=self.regular_user.pk,
                    consent_type='data_processing',
                    granted=False,
                    ip_address='192.168.1.1',
                    details={'action': 'withdrawal'}
                )
                
                # Verify user data was deleted
                mock_delete.assert_called_once_with(self.regular_user.pk)
    
    def test_withdraw_consent_non_data_processing(self):
        """Test withdrawing consent for non-data-processing type"""
        with patch.object(self.consent_manager, 'record_consent') as mock_record:
            mock_record.return_value = {'success': True}
            
            result = self.consent_manager.withdraw_consent(
                user_id=self.regular_user.pk,
                consent_type='analytics',
                ip_address='192.168.1.1'
            )
            
            self.assertTrue(result['success'])
            
            # Verify consent was recorded but data deletion not triggered
            mock_record.assert_called_once()
    
    def test_delete_user_data(self):
        """Test deleting user data"""
        # Create additional user data
        additional_logs = []
        for i in range(3):
            log = RateLimitLog.objects.create(
                user=self.regular_user,
                ip_address=f'192.168.1.{i+1}',
                endpoint='/api/test/',
                method='GET',
                status_code=200,
                response_time=0.5,
                user_agent='Mozilla/5.0'
            )
            additional_logs.append(log)
        
        with patch.object(self.consent_manager.repositories['user_rate_limit_profile'].encryption_manager, 'generate_hash') as mock_hash:
            mock_hash.return_value = 'hashed_user_id'
            
            self.consent_manager._delete_user_data(self.regular_user.pk)
            
            # Verify user profile was deleted
            with self.assertRaises(UserRateLimitProfile.DoesNotExist):
                UserRateLimitProfile.objects.get(user=self.regular_user)
            
            # Verify logs were anonymized
            for log in additional_logs:
                log.refresh_from_db()
                self.assertIsNone(log.user)
                self.assertEqual(log.user_id_hash, 'hashed_user_id')


class ComplianceManagerTest(BaseComplianceTest):
    """Test cases for ComplianceManager"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.compliance_mgr = ComplianceManager()
    
    def test_load_compliance_rules(self):
        """Test loading compliance rules"""
        self.assertGreater(len(self.compliance_mgr.rules), 0)
        
        # Check GDPR rules
        gdpr_rules = [rule for rule in self.compliance_mgr.rules if rule.standard == ComplianceStandard.GDPR]
        self.assertGreater(len(gdpr_rules), 0)
        
        # Check specific rules
        rule_names = [rule.name for rule in self.compliance_mgr.rules]
        self.assertIn('gdpr_data_protection', rule_names)
        self.assertIn('gdpr_consent', rule_names)
        self.assertIn('gdpr_retention', rule_names)
        self.assertIn('security_audit_trail', rule_names)
    
    def test_run_compliance_check_all(self):
        """Test running all compliance checks"""
        with patch.object(self.compliance_mgr.retention_manager, 'get_retention_status') as mock_retention:
            mock_retention.return_value = {'success': True, 'status': {}}
            
            result = self.compliance_mgr.run_compliance_check()
            
            self.assertTrue(result['success'])
            self.assertIn('overall_status', result)
            self.assertIn('total_rules', result)
            self.assertIn('passed_rules', result)
            self.assertIn('failed_rules', result)
            self.assertIn('compliance_rate', result)
            self.assertIn('results', result)
            self.assertIn('checked_at', result)
            
            # Should have checked all rules
            self.assertEqual(result['total_rules'], len(self.compliance_mgr.rules))
            
            # All simplified checks should pass
            self.assertEqual(result['overall_status'], 'compliant')
            self.assertEqual(result['passed_rules'], len(self.compliance_mgr.rules))
            self.assertEqual(result['failed_rules'], 0)
    
    def test_run_compliance_check_filtered(self):
        """Test running compliance checks with filters"""
        with patch.object(self.compliance_mgr.retention_manager, 'get_retention_status') as mock_retention:
            mock_retention.return_value = {'success': True, 'status': {}}
            
            # Filter by standard
            result = self.compliance_mgr.run_compliance_check(standard=ComplianceStandard.GDPR)
            
            self.assertTrue(result['success'])
            
            # Should only check GDPR rules
            gdpr_rules = [rule for rule in self.compliance_mgr.rules if rule.standard == ComplianceStandard.GDPR]
            self.assertEqual(result['total_rules'], len(gdpr_rules))
            
            # Filter by category
            result = self.compliance_mgr.run_compliance_check(category=ComplianceCategory.DATA_PROTECTION)
            
            self.assertTrue(result['success'])
            
            # Should only check data protection rules
            data_protection_rules = [rule for rule in self.compliance_mgr.rules if rule.category == ComplianceCategory.DATA_PROTECTION]
            self.assertEqual(result['total_rules'], len(data_protection_rules))
    
    def test_run_compliance_check_error(self):
        """Test running compliance check with error"""
        # Add a rule that will fail
        def failing_check(context):
            raise Exception("Test error")
        
        self.compliance_mgr.rules.append(ComplianceRule(
            name='failing_rule',
            standard=ComplianceStandard.GDPR,
            category=ComplianceCategory.DATA_PROTECTION,
            description='Failing test rule',
            check_function=failing_check,
            enabled=True
        ))
        
        result = self.compliance_mgr.run_compliance_check()
        
        self.assertTrue(result['success'])
        
        # Should have one error result
        error_results = [r for r in result['results'] if r['status'] == 'error']
        self.assertEqual(len(error_results), 1)
        self.assertEqual(error_results[0]['error'], 'Test error')
    
    def test_generate_compliance_report(self):
        """Test generating compliance report"""
        with patch.object(self.compliance_mgr, 'run_compliance_check') as mock_check:
            mock_check.return_value = {
                'success': True,
                'overall_status': 'compliant',
                'total_rules': 4,
                'passed_rules': 4,
                'failed_rules': 0,
                'compliance_rate': 100.0,
                'results': []
            }
            
            with patch.object(self.compliance_mgr.retention_manager, 'get_retention_status') as mock_retention:
                mock_retention.return_value = {'success': True, 'status': {}}
                
                with patch.object(self.compliance_mgr.audit_trail, 'get_audit_logs') as mock_audit:
                    mock_audit.return_value = []
                    
                    result = self.compliance_mgr.generate_compliance_report()
                    
                    self.assertTrue(result['success'])
                    self.assertIn('report', result)
                    
                    report = result['report']
                    self.assertIn('report_metadata', report)
                    self.assertIn('compliance_status', report)
                    self.assertIn('data_retention', report)
                    self.assertIn('audit_trail_summary', report)
                    self.assertIn('recommendations', report)
                    
                    # Check metadata
                    metadata = report['report_metadata']
                    self.assertIsNone(metadata['standard'])  # No filter applied
                    self.assertIn('generated_at', metadata)
                    self.assertIn('report_period', metadata)
    
    def test_generate_compliance_report_filtered(self):
        """Test generating compliance report with standard filter"""
        with patch.object(self.compliance_mgr, 'run_compliance_check') as mock_check:
            mock_check.return_value = {
                'success': True,
                'overall_status': 'compliant',
                'total_rules': 3,
                'passed_rules': 3,
                'failed_rules': 0,
                'compliance_rate': 100.0,
                'results': []
            }
            
            with patch.object(self.compliance_mgr.retention_manager, 'get_retention_status') as mock_retention:
                mock_retention.return_value = {'success': True, 'status': {}}
                
                with patch.object(self.compliance_mgr.audit_trail, 'get_audit_logs') as mock_audit:
                    mock_audit.return_value = []
                    
                    result = self.compliance_mgr.generate_compliance_report(standard=ComplianceStandard.GDPR)
                    
                    self.assertTrue(result['success'])
                    
                    report = result['report']
                    metadata = report['report_metadata']
                    self.assertEqual(metadata['standard'], ComplianceStandard.GDPR)
    
    def test_generate_recommendations(self):
        """Test generating compliance recommendations"""
        check_results = {
            'results': [
                {
                    'status': 'passed',
                    'rule': 'test_rule_1',
                    'standard': 'gdpr',
                    'category': 'data_protection',
                    'severity': 'high'
                },
                {
                    'status': 'failed',
                    'rule': 'test_rule_2',
                    'standard': 'gdpr',
                    'category': 'consent',
                    'severity': 'medium'
                },
                {
                    'status': 'failed',
                    'rule': 'test_rule_3',
                    'standard': 'ccpa',
                    'category': 'privacy',
                    'severity': 'low'
                }
            ]
        }
        
        recommendations = self.compliance_mgr._generate_recommendations(check_results)
        
        self.assertEqual(len(recommendations), 2)  # Only for failed rules
        
        # Check first recommendation
        rec1 = recommendations[0]
        self.assertEqual(rec1['rule'], 'test_rule_2')
        self.assertEqual(rec1['standard'], 'gdpr')
        self.assertEqual(rec1['category'], 'consent')
        self.assertEqual(rec1['severity'], 'medium')
        self.assertIn('Address compliance issue', rec1['recommendation'])
    
    def test_export_compliance_data(self):
        """Test exporting compliance data"""
        start_date = timezone.now().date() - timedelta(days=7)
        end_date = timezone.now().date()
        
        with patch.object(self.compliance_mgr.audit_trail, 'export_audit_logs') as mock_audit:
            mock_audit.return_value = {
                'success': True,
                'data': {
                    'export_metadata': {'format': 'json'},
                    'audit_logs': []
                }
            }
            
            with patch.object(self.compliance_mgr.retention_manager, 'get_retention_status') as mock_retention:
                mock_retention.return_value = {'success': True, 'status': {}}
                
                result = self.compliance_mgr.export_compliance_data(
                    start_date=start_date,
                    end_date=end_date,
                    include_audit_trail=True,
                    include_retention_status=True
                )
                
                self.assertTrue(result['success'])
                self.assertIn('data', result)
                
                export_data = result['data']
                self.assertIn('export_metadata', export_data)
                self.assertIn('audit_trail', export_data)
                self.assertIn('retention_status', export_data)
                
                # Check metadata
                metadata = export_data['export_metadata']
                self.assertEqual(metadata['start_date'], start_date.isoformat())
                self.assertEqual(metadata['end_date'], end_date.isoformat())
                self.assertIn('exported_at', metadata)
    
    def test_export_compliance_data_partial(self):
        """Test exporting compliance data with partial includes"""
        start_date = timezone.now().date() - timedelta(days=7)
        end_date = timezone.now().date()
        
        with patch.object(self.compliance_mgr.audit_trail, 'export_audit_logs') as mock_audit:
            with patch.object(self.compliance_mgr.retention_manager, 'get_retention_status') as mock_retention:
                
                result = self.compliance_mgr.export_compliance_data(
                    start_date=start_date,
                    end_date=end_date,
                    include_audit_trail=False,
                    include_retention_status=False
                )
                
                self.assertTrue(result['success'])
                
                export_data = result['data']
                self.assertIn('export_metadata', export_data)
                self.assertNotIn('audit_trail', export_data)
                self.assertNotIn('retention_status', export_data)
                
                # Verify methods were not called
                mock_audit.assert_not_called()
                mock_retention.assert_not_called()
    
    def test_export_compliance_data_error(self):
        """Test exporting compliance data with error"""
        start_date = timezone.now().date() - timedelta(days=7)
        end_date = timezone.now().date()
        
        with patch.object(self.compliance_mgr.audit_trail, 'export_audit_logs') as mock_audit:
            mock_audit.side_effect = Exception("Test error")
            
            result = self.compliance_mgr.export_compliance_data(
                start_date=start_date,
                end_date=end_date
            )
            
            self.assertFalse(result['success'])
            self.assertEqual(result['error'], 'Test error')


class ComplianceIntegrationTest(BaseComplianceTest):
    """Integration tests for compliance functionality"""
    
    def test_end_to_end_compliance_workflow(self):
        """Test end-to-end compliance workflow"""
        # Step 1: Record user consent
        consent_result = self.consent_manager.record_consent(
            user_id=self.regular_user.pk,
            consent_type='data_processing',
            granted=True,
            ip_address='192.168.1.1'
        )
        
        self.assertTrue(consent_result['success'])
        
        # Step 2: Log compliance-relevant action
        self.audit_trail.log_action(
            action='data_access',
            user_id=self.regular_user.pk,
            ip_address='192.168.1.1',
            resource_type='UserRateLimitProfile',
            resource_id=self.user_profile.pk,
            compliance_relevant=True
        )
        
        # Step 3: Run compliance check
        with patch.object(compliance_manager.retention_manager, 'get_retention_status') as mock_retention:
            mock_retention.return_value = {'success': True, 'status': {}}
            
            check_result = compliance_manager.run_compliance_check()
            
            self.assertTrue(check_result['success'])
            self.assertEqual(check_result['overall_status'], 'compliant')
        
        # Step 4: Generate compliance report
        with patch.object(compliance_manager.audit_trail, 'get_audit_logs') as mock_audit:
            mock_audit.return_value = [
                {
                    'action': 'data_access',
                    'user_id': self.regular_user.pk,
                    'compliance_relevant': True,
                    'timestamp': timezone.now().isoformat()
                }
            ]
            
            report_result = compliance_manager.generate_compliance_report()
            
            self.assertTrue(report_result['success'])
            self.assertIn('report', report_result)
    
    def test_consent_withdrawal_workflow(self):
        """Test consent withdrawal workflow"""
        # Step 1: Grant consent
        consent_result = self.consent_manager.record_consent(
            user_id=self.regular_user.pk,
            consent_type='data_processing',
            granted=True,
            ip_address='192.168.1.1'
        )
        
        self.assertTrue(consent_result['success'])
        
        # Step 2: Verify consent exists
        with patch('django.core.cache.cache') as mock_cache:
            mock_cache.get.return_value = consent_result['consent_data']
            
            check_result = self.consent_manager.check_consent(
                user_id=self.regular_user.pk,
                consent_type='data_processing'
            )
            
            self.assertTrue(check_result['has_consent'])
        
        # Step 3: Withdraw consent
        with patch.object(self.consent_manager, 'record_consent') as mock_record:
            mock_record.return_value = {'success': True}
            
            with patch.object(self.consent_manager, '_delete_user_data') as mock_delete:
                
                withdrawal_result = self.consent_manager.withdraw_consent(
                    user_id=self.regular_user.pk,
                    consent_type='data_processing',
                    ip_address='192.168.1.2'
                )
                
                self.assertTrue(withdrawal_result['success'])
                mock_delete.assert_called_once()
    
    def test_data_retention_workflow(self):
        """Test data retention workflow"""
        # Step 1: Create old data
        old_date = timezone.now() - timedelta(days=200)
        
        old_log = RateLimitLog.objects.create(
            user=self.regular_user,
            ip_address='192.168.1.100',
            endpoint='/api/old/',
            method='GET',
            status_code=200,
            response_time=0.5,
            user_agent='Mozilla/5.0',
            timestamp=old_date
        )
        
        # Step 2: Apply retention policies
        with patch.object(self.retention_manager.data_protection.encryption_manager, 'generate_hash') as mock_hash:
            mock_hash.return_value = 'hashed_ip'
            
            result = self.retention_manager.apply_retention_policies()
            
            self.assertTrue(result['success'])
            self.assertIn('results', result)
        
        # Step 3: Verify data was anonymized
        old_log.refresh_from_db()
        self.assertIsNone(old_log.ip_address)
        self.assertEqual(old_log.ip_address_hash, 'hashed_ip')
    
    def test_compliance_export_workflow(self):
        """Test compliance data export workflow"""
        # Step 1: Create audit logs
        self.audit_trail.log_action(
            action='test_action_1',
            user_id=self.regular_user.pk,
            ip_address='192.168.1.1',
            compliance_relevant=True
        )
        
        self.audit_trail.log_action(
            action='test_action_2',
            user_id=self.admin_user.pk,
            ip_address='192.168.1.2',
            compliance_relevant=True
        )
        
        # Step 2: Export compliance data
        start_date = timezone.now().date() - timedelta(days=1)
        end_date = timezone.now().date()
        
        with patch.object(self.audit_trail, 'export_audit_logs') as mock_export:
            mock_export.return_value = {
                'success': True,
                'data': {
                    'export_metadata': {
                        'format': 'json',
                        'record_count': 2
                    },
                    'audit_logs': [
                        {'action': 'test_action_1', 'ip_address': 'hashed_ip_1'},
                        {'action': 'test_action_2', 'ip_address': 'hashed_ip_2'}
                    ]
                }
            }
            
            result = compliance_manager.export_compliance_data(
                start_date=start_date,
                end_date=end_date,
                include_audit_trail=True,
                include_retention_status=False
            )
            
            self.assertTrue(result['success'])
            
            export_data = result['data']
            self.assertEqual(export_data['export_metadata']['record_count'], 2)
            self.assertEqual(len(export_data['audit_logs']), 2)
    
    def test_compliance_error_recovery(self):
        """Test compliance system error recovery"""
        # Test audit trail error recovery
        with patch('django.core.cache.cache') as mock_cache:
            mock_cache.get.side_effect = Exception("Cache error")
            
            logs = self.audit_trail.get_audit_logs()
            
            # Should return empty list on error
            self.assertEqual(logs, [])
        
        # Test retention manager error recovery
        with patch.object(self.retention_manager, '_apply_retention_policy') as mock_apply:
            mock_apply.side_effect = Exception("Retention error")
            
            result = self.retention_manager.apply_retention_policies()
            
            self.assertFalse(result['success'])
            self.assertIn('error', result)
        
        # Test consent manager error recovery
        with patch('django.core.cache.cache') as mock_cache:
            mock_cache.set.side_effect = Exception("Cache error")
            
            result = self.consent_manager.record_consent(
                user_id=self.regular_user.pk,
                consent_type='data_processing',
                granted=True
            )
            
            self.assertFalse(result['success'])
            self.assertIn('error', result)


class ComplianceSecurityTest(BaseComplianceTest):
    """Security tests for compliance functionality"""
    
    def test_data_anonymization_security(self):
        """Test data anonymization security"""
        # Create sensitive data
        sensitive_log = RateLimitLog.objects.create(
            user=self.regular_user,
            ip_address='192.168.1.123',
            endpoint='/api/sensitive/',
            method='POST',
            status_code=200,
            response_time=0.5,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            timestamp=timezone.now() - timedelta(days=200)
        )
        
        # Apply anonymization
        cutoff = timezone.now() - timedelta(days=150)
        
        with patch.object(self.retention_manager.data_protection.encryption_manager, 'generate_hash') as mock_hash:
            mock_hash.return_value = 'secure_hash_value'
            
            count = self.retention_manager._anonymize_data('rate_limit_logs', cutoff)
            
            self.assertEqual(count, 1)
            
            # Verify sensitive data was removed
            sensitive_log.refresh_from_db()
            self.assertIsNone(sensitive_log.ip_address)
            self.assertIsNone(sensitive_log.user_agent)
            self.assertIsNone(sensitive_log.user)
            
            # Verify hash was applied
            self.assertEqual(sensitive_log.ip_address_hash, 'secure_hash_value')
            self.assertEqual(sensitive_log.user_id_hash, 'secure_hash_value')
    
    def test_consent_data_protection(self):
        """Test consent data protection"""
        consent_data = {
            'user_id': self.regular_user.pk,
            'consent_type': 'data_processing',
            'granted': True,
            'ip_address': '192.168.1.1',
            'details': {'source': 'web_form', 'version': '1.0'},
            'recorded_at': timezone.now().isoformat()
        }
        
        # Store consent data
        with patch('django.core.cache.cache') as mock_cache:
            mock_cache.set.return_value = True
            
            result = self.consent_manager.record_consent(
                user_id=self.regular_user.pk,
                consent_type='data_processing',
                granted=True,
                ip_address='192.168.1.1',
                details={'source': 'web_form', 'version': '1.0'}
            )
            
            self.assertTrue(result['success'])
            
            # Verify cache key includes user ID for isolation
            cache_key = mock_cache.set.call_args[0][0]
            self.assertIn(str(self.regular_user.pk), cache_key)
            self.assertIn('data_processing', cache_key)
    
    def test_audit_log_protection(self):
        """Test audit log data protection"""
        # Create sensitive audit log
        self.audit_trail.log_action(
            action='sensitive_data_access',
            user_id=self.regular_user.pk,
            ip_address='192.168.1.100',
            resource_type='UserRateLimitProfile',
            resource_id=self.user_profile.pk,
            details={'sensitive_field': 'sensitive_value'},
            compliance_relevant=True
        )
        
        # Export audit logs
        start_date = timezone.now().date()
        end_date = timezone.now().date()
        
        with patch.object(self.audit_trail, 'get_audit_logs') as mock_get_logs:
            mock_get_logs.return_value = [
                {
                    'action': 'sensitive_data_access',
                    'user_id': self.regular_user.pk,
                    'ip_address': '192.168.1.100',
                    'details': {'sensitive_field': 'sensitive_value'},
                    'timestamp': timezone.now().isoformat(),
                    'compliance_relevant': True
                }
            ]
            
            with patch.object(self.audit_trail.data_protection.encryption_manager, 'generate_hash') as mock_hash:
                mock_hash.return_value = 'hashed_ip_address'
                
                result = self.audit_trail.export_audit_logs(start_date, end_date)
                
                self.assertTrue(result['success'])
                
                audit_logs = result['data']['audit_logs']
                self.assertEqual(len(audit_logs), 1)
                
                # Verify IP address was hashed but other data preserved
                exported_log = audit_logs[0]
                self.assertEqual(exported_log['ip_address'], 'hashed_ip_address')
                self.assertEqual(exported_log['action'], 'sensitive_data_access')
                self.assertEqual(exported_log['details']['sensitive_field'], 'sensitive_value')
    
    def test_right_to_be_forgotten(self):
        """Test GDPR right to be forgotten implementation"""
        # Create user data
        user_logs = []
        for i in range(5):
            log = RateLimitLog.objects.create(
                user=self.regular_user,
                ip_address=f'192.168.1.{i+1}',
                endpoint=f'/api/test/{i}/',
                method='GET',
                status_code=200,
                response_time=0.5,
                user_agent='Mozilla/5.0'
            )
            user_logs.append(log)
        
        # Withdraw consent and trigger data deletion
        with patch.object(self.consent_manager, 'record_consent') as mock_record:
            mock_record.return_value = {'success': True}
            
            with patch.object(self.consent_manager.repositories['user_rate_limit_profile'].encryption_manager, 'generate_hash') as mock_hash:
                mock_hash.return_value = 'hashed_user_id'
                
                result = self.consent_manager.withdraw_consent(
                    user_id=self.regular_user.pk,
                    consent_type='data_processing'
                )
                
                self.assertTrue(result['success'])
                
                # Verify user profile was deleted
                with self.assertRaises(UserRateLimitProfile.DoesNotExist):
                    UserRateLimitProfile.objects.get(user=self.regular_user)
                
                # Verify logs were anonymized
                for log in user_logs:
                    log.refresh_from_db()
                    self.assertIsNone(log.user)
                    self.assertEqual(log.user_id_hash, 'hashed_user_id')
    
    def test_data_minimization_principle(self):
        """Test GDPR data minimization principle"""
        # Create logs with excessive data
        detailed_log = RateLimitLog.objects.create(
            user=self.regular_user,
            ip_address='192.168.1.200',
            endpoint='/api/detailed/',
            method='POST',
            status_code=200,
            response_time=0.5,
            user_agent='Mozilla/5.0 (detailed user agent string with lots of information)',
            timestamp=timezone.now() - timedelta(days=200)
        )
        
        # Apply data minimization through retention policies
        cutoff = timezone.now() - timedelta(days=150)
        
        with patch.object(self.retention_manager.data_protection.encryption_manager, 'generate_hash') as mock_hash:
            mock_hash.return_value = 'minimized_hash'
            
            count = self.retention_manager._anonymize_data('rate_limit_logs', cutoff)
            
            self.assertEqual(count, 1)
            
            # Verify data was minimized
            detailed_log.refresh_from_db()
            self.assertIsNone(detailed_log.user_agent)  # Detailed user agent removed
            self.assertIsNone(detailed_log.ip_address)   # IP address hashed
            self.assertEqual(detailed_log.ip_address_hash, 'minimized_hash')


class CompliancePerformanceTest(BaseComplianceTest):
    """Performance tests for compliance functionality"""
    
    def test_compliance_check_performance(self):
        """Test compliance check performance"""
        import time
        
        with patch.object(compliance_manager.retention_manager, 'get_retention_status') as mock_retention:
            mock_retention.return_value = {'success': True, 'status': {}}
            
            # Measure compliance check time
            start_time = time.time()
            result = compliance_manager.run_compliance_check()
            end_time = time.time()
            
            check_time = end_time - start_time
            
            # Should complete quickly (under 100ms for mocked operations)
            self.assertLess(check_time, 0.1)
            
            # Should produce correct results
            self.assertTrue(result['success'])
            self.assertEqual(result['overall_status'], 'compliant')
    
    def test_audit_trail_performance(self):
        """Test audit trail performance with large datasets"""
        import time
        
        # Create many audit logs
        test_logs = []
        for i in range(100):
            test_logs.append({
                'action': f'action_{i}',
                'user_id': self.regular_user.pk,
                'ip_address': f'192.168.1.{i%255}',
                'timestamp': timezone.now().isoformat(),
                'compliance_relevant': i % 2 == 0
            })
        
        with patch('django.core.cache.cache') as mock_cache:
            mock_cache.get.return_value = test_logs
            
            # Measure get_audit_logs time
            start_time = time.time()
            logs = self.audit_trail.get_audit_logs(compliance_relevant=True)
            end_time = time.time()
            
            query_time = end_time - start_time
            
            # Should handle large datasets efficiently
            self.assertLess(query_time, 0.05)
            
            # Should filter correctly
            self.assertEqual(len(logs), 50)  # Half should be compliance_relevant
    
    def test_data_retention_performance(self):
        """Test data retention performance"""
        import time
        
        # Create many old logs
        old_cutoff = timezone.now() - timedelta(days=200)
        for i in range(50):
            RateLimitLog.objects.create(
                user=self.regular_user,
                ip_address=f'192.168.1.{i+1}',
                endpoint=f'/api/test/{i}/',
                method='GET',
                status_code=200,
                response_time=0.5,
                user_agent='Mozilla/5.0',
                timestamp=old_cutoff
            )
        
        with patch.object(self.retention_manager.data_protection.encryption_manager, 'generate_hash') as mock_hash:
            mock_hash.return_value = 'hashed_value'
            
            # Measure anonymization time
            start_time = time.time()
            count = self.retention_manager._anonymize_data('rate_limit_logs', old_cutoff)
            end_time = time.time()
            
            anonymize_time = end_time - start_time
            
            # Should handle bulk operations efficiently
            self.assertLess(anonymize_time, 0.2)
            
            # Should process all records
            self.assertEqual(count, 50)
    
    def test_consent_management_performance(self):
        """Test consent management performance"""
        import time
        
        # Test bulk consent recording
        with patch('django.core.cache.cache') as mock_cache:
            mock_cache.set.return_value = True
            
            start_time = time.time()
            
            for i in range(20):
                self.consent_manager.record_consent(
                    user_id=self.regular_user.pk,
                    consent_type='analytics',
                    granted=i % 2 == 0,
                    ip_address=f'192.168.1.{i+1}'
                )
            
            end_time = time.time()
            
            consent_time = end_time - start_time
            
            # Should handle bulk consent operations efficiently
            self.assertLess(consent_time, 0.1)
            
            # Verify all operations were recorded
            self.assertEqual(mock_cache.set.call_count, 20)
    
    def test_export_performance(self):
        """Test export performance"""
        import time
        
        # Create large audit dataset
        large_dataset = []
        for i in range(200):
            large_dataset.append({
                'action': f'bulk_action_{i}',
                'user_id': self.regular_user.pk,
                'ip_address': f'192.168.1.{i%255}',
                'timestamp': timezone.now().isoformat(),
                'compliance_relevant': True
            })
        
        with patch.object(self.audit_trail, 'get_audit_logs') as mock_get_logs:
            mock_get_logs.return_value = large_dataset
            
            with patch.object(self.audit_trail.data_protection.encryption_manager, 'generate_hash') as mock_hash:
                mock_hash.return_value = 'hashed_ip'
                
                # Measure export time
                start_time = time.time()
                result = self.audit_trail.export_audit_logs(
                    start_date=timezone.now().date() - timedelta(days=7),
                    end_date=timezone.now().date()
                )
                end_time = time.time()
                
                export_time = end_time - start_time
                
                # Should handle large exports efficiently
                self.assertLess(export_time, 0.3)
                
                # Should export all records
                self.assertTrue(result['success'])
                self.assertEqual(result['data']['export_metadata']['record_count'], 200)
                
                # Verify all IPs were hashed
                self.assertEqual(mock_hash.call_count, 200)
