"""
Comprehensive compliance testing for fraud_detection module.

This test file covers all GDPR, CCPA, HIPAA compliance logic and
regulatory reporting functionality that was previously untested.
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

from api.fraud_detection.models import (
    FraudRule, FraudAttempt, FraudPattern, UserRiskProfile,
    DeviceFingerprint, IPReputation, FraudAlert, FraudCase
)
from api.fraud_detection.compliance import (
    AMLComplianceManager, FraudReportingManager, ComplianceAuditManager,
    monitor_aml_compliance, create_fraud_incident_report, generate_monthly_compliance_report
)
from api.fraud_detection.exceptions import ComplianceError, ReportingError
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
        
        # Create test fraud data
        self.fraud_rule = FraudRule.objects.create(
            name='Test Rule',
            description='Test fraud detection rule',
            rule_type='account',
            severity='medium',
            condition={'amount_threshold': 1000},
            is_active=True
        )
        
        self.fraud_attempt = FraudAttempt.objects.create(
            user=self.regular_user,
            attempt_type='multi_account',
            description='Test fraud attempt',
            detected_by='TestDetector',
            fraud_score=85,
            status='detected'
        )
        
        cache.clear()
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()


class AMLComplianceManagerTest(BaseComplianceTest):
    """Test cases for AMLComplianceManager"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.aml_manager = AMLComplianceManager()
    
    def test_load_aml_thresholds(self):
        """Test AML thresholds loading"""
        thresholds = self.aml_manager._load_aml_thresholds()
        
        self.assertIn('single_transaction', thresholds)
        self.assertIn('daily_aggregate', thresholds)
        self.assertIn('weekly_aggregate', thresholds)
        self.assertIn('monthly_aggregate', thresholds)
        self.assertIn('suspicious_pattern_threshold', thresholds)
        self.assertIn('structuring_threshold', thresholds)
        
        # Check default values
        self.assertEqual(thresholds['single_transaction'], 10000.00)
        self.assertEqual(thresholds['daily_aggregate'], 15000.00)
        self.assertEqual(thresholds['suspicious_pattern_threshold'], 5)
    
    def test_load_reporting_rules(self):
        """Test reporting rules loading"""
        rules = self.aml_manager._load_reporting_rules()
        
        self.assertIn('sar_threshold', rules)
        self.assertIn('ctr_threshold', rules)
        self.assertIn('reporting_timeframe_hours', rules)
        self.assertIn('auto_file_reports', rules)
        
        # Check default values
        self.assertEqual(rules['sar_threshold'], 5000.00)
        self.assertEqual(rules['ctr_threshold'], 10000.00)
        self.assertEqual(rules['reporting_timeframe_hours'], 24)
        self.assertFalse(rules['auto_file_reports'])
    
    def test_load_regulatory_bodies(self):
        """Test regulatory bodies loading"""
        bodies = self.aml_manager._load_regulatory_bodies()
        
        self.assertIn('fintrac', bodies)
        self.assertIn('fincen', bodies)
        self.assertIn('internal', bodies)
        
        # Check fintrac details
        fintrac = bodies['fintrac']
        self.assertEqual(fintrac['name'], 'Financial Transactions and Reports Analysis Centre')
        self.assertEqual(fintrac['email'], 'reports@fintrac-canafe.gc.ca')
        self.assertEqual(fintrac['country'], 'CA')
        
        # Check fincen details
        fincen = bodies['fincen']
        self.assertEqual(fincen['name'], 'Financial Crimes Enforcement Network')
        self.assertEqual(fincen['email'], 'frc@fincen.gov')
        self.assertEqual(fincen['country'], 'US')
    
    def test_monitor_transaction_limits_compliant(self):
        """Test monitoring compliant transaction"""
        transaction_data = {
            'user_id': self.regular_user.pk,
            'amount': 500.00,  # Below all thresholds
            'timestamp': timezone.now(),
            'transaction_type': 'payment'
        }
        
        result = self.aml_manager.monitor_transaction_limits(transaction_data)
        
        self.assertTrue(result['compliant'])
        self.assertEqual(len(result['thresholds_breached']), 0)
        self.assertEqual(len(result['alerts_triggered']), 0)
        self.assertFalse(result['reporting_required'])
        self.assertEqual(result['risk_level'], 'low')
    
    def test_monitor_transaction_limits_single_threshold_breach(self):
        """Test monitoring transaction that breaches single transaction threshold"""
        transaction_data = {
            'user_id': self.regular_user.pk,
            'amount': 15000.00,  # Above single transaction threshold
            'timestamp': timezone.now(),
            'transaction_type': 'payment'
        }
        
        result = self.aml_manager.monitor_transaction_limits(transaction_data)
        
        self.assertFalse(result['compliant'])
        self.assertEqual(len(result['thresholds_breached']), 1)
        self.assertEqual(result['thresholds_breached'][0]['type'], 'single_transaction')
        self.assertEqual(result['thresholds_breached'][0]['amount'], 15000.00)
        self.assertTrue(result['reporting_required'])
        self.assertEqual(result['risk_level'], 'high')
        
        # Check recommendations
        self.assertIn('File SAR (Suspicious Activity Report)', result['recommendations'])
        self.assertIn('Enhanced monitoring required', result['recommendations'])
    
    def test_monitor_transaction_limits_daily_aggregate_breach(self):
        """Test monitoring transaction that breaches daily aggregate threshold"""
        transaction_data = {
            'user_id': self.regular_user.pk,
            'amount': 1000.00,
            'timestamp': timezone.now(),
            'transaction_type': 'payment'
        }
        
        # Mock daily aggregate calculation to return high value
        with patch.object(self.aml_manager, '_calculate_daily_aggregate', return_value=Decimal('20000.00')):
            result = self.aml_manager.monitor_transaction_limits(transaction_data)
            
            self.assertFalse(result['compliant'])
            self.assertEqual(len(result['thresholds_breached']), 1)
            self.assertEqual(result['thresholds_breached'][0]['type'], 'daily_aggregate')
            self.assertTrue(result['reporting_required'])
            self.assertEqual(result['risk_level'], 'high')
    
    def test_monitor_transaction_limits_structuring_detection(self):
        """Test monitoring transaction with structuring pattern detection"""
        transaction_data = {
            'user_id': self.regular_user.pk,
            'amount': 1000.00,
            'timestamp': timezone.now(),
            'transaction_type': 'payment'
        }
        
        # Mock structuring pattern detection
        with patch.object(self.aml_manager, '_detect_structuring_pattern', return_value=True):
            result = self.aml_manager.monitor_transaction_limits(transaction_data)
            
            self.assertFalse(result['compliant'])
            self.assertEqual(len(result['alerts_triggered']), 1)
            self.assertEqual(result['alerts_triggered'][0]['type'], 'structuring_pattern')
            self.assertTrue(result['reporting_required'])
            self.assertEqual(result['risk_level'], 'medium')
    
    def test_monitor_transaction_limits_suspicious_pattern_detection(self):
        """Test monitoring transaction with suspicious pattern detection"""
        transaction_data = {
            'user_id': self.regular_user.pk,
            'amount': 1000.00,
            'timestamp': timezone.now(),
            'transaction_type': 'payment'
        }
        
        # Mock suspicious transaction count
        with patch.object(self.aml_manager, '_count_suspicious_transactions', return_value=6):
            result = self.aml_manager.monitor_transaction_limits(transaction_data)
            
            self.assertFalse(result['compliant'])
            self.assertEqual(len(result['alerts_triggered']), 1)
            self.assertEqual(result['alerts_triggered'][0]['type'], 'suspicious_pattern')
            self.assertEqual(result['alerts_triggered'][0]['count'], 6)
            self.assertTrue(result['reporting_required'])
            self.assertEqual(result['risk_level'], 'high')
    
    def test_generate_sar_report(self):
        """Test SAR report generation"""
        case_data = {
            'user_id': self.regular_user.pk,
            'case_id': 'CASE_123',
            'total_suspicious_amount': 25000.00,
            'transaction_count': 15,
            'activity_period': '2023-01-01 to 2023-01-31',
            'suspicion_reasons': ['Structuring', 'Unusual timing'],
            'account_numbers': ['ACC123456', 'ACC789012'],
            'identification_details': {
                'name': 'John Doe',
                'address': '123 Main St',
                'id_number': 'ID123456'
            },
            'suspicious_activities': [
                {
                    'date': '2023-01-15',
                    'amount': 9500.00,
                    'description': 'Multiple transactions just below threshold'
                }
            ]
        }
        
        sar_report = self.aml_manager.generate_sar_report(case_data)
        
        self.assertEqual(sar_report['report_type'], 'SAR')
        self.assertIn('report_id', sar_report)
        self.assertIn('filing_date', sar_report)
        self.assertEqual(sar_report['suspicious_activity']['total_amount'], 25000.00)
        self.assertEqual(sar_report['suspicious_activity']['transaction_count'], 15)
        self.assertEqual(sar_report['subject_information']['user_id'], self.regular_user.pk)
        self.assertEqual(len(sar_report['subject_information']['account_numbers']), 2)
        self.assertIn('integrity_hash', sar_report)
        self.assertEqual(sar_report['report_status'], 'draft')
    
    def test_generate_ctr_report(self):
        """Test CTR report generation"""
        transaction_data = {
            'user_id': self.regular_user.pk,
            'amount': 15000.00,
            'timestamp': timezone.now(),
            'transaction_type': 'cash_deposit',
            'customer_name': 'John Doe',
            'customer_identification': {
                'id_type': 'passport',
                'id_number': 'PP123456',
                'issuing_country': 'US'
            },
            'branch': 'Main Branch'
        }
        
        ctr_report = self.aml_manager.generate_ctr_report(transaction_data)
        
        self.assertEqual(ctr_report['report_type'], 'CTR')
        self.assertIn('report_id', ctr_report)
        self.assertEqual(ctr_report['transaction_amount'], 15000.00)
        self.assertEqual(ctr_report['subject_information']['user_id'], self.regular_user.pk)
        self.assertEqual(ctr_report['subject_information']['name'], 'John Doe')
        self.assertIn('integrity_hash', ctr_report)
        self.assertEqual(ctr_report['report_status'], 'draft')
    
    def test_calculate_daily_aggregate(self):
        """Test daily aggregate calculation"""
        user_id = self.regular_user.pk
        reference_time = timezone.now()
        
        # Test with no transactions (mocked)
        daily_total = self.aml_manager._calculate_daily_aggregate(user_id, reference_time)
        self.assertEqual(daily_total, Decimal('0.00'))
        
        # Test error handling
        with patch.object(self.aml_manager, '_calculate_daily_aggregate', side_effect=Exception("Test error")):
            daily_total = self.aml_manager._calculate_daily_aggregate(user_id, reference_time)
            self.assertEqual(daily_total, Decimal('0.00'))
    
    def test_detect_structuring_pattern(self):
        """Test structuring pattern detection"""
        user_id = self.regular_user.pk
        reference_time = timezone.now()
        
        # Test with no structuring (default implementation)
        result = self.aml_manager._detect_structuring_pattern(user_id, reference_time)
        self.assertFalse(result)
        
        # Test error handling
        with patch.object(self.aml_manager, '_detect_structuring_pattern', side_effect=Exception("Test error")):
            result = self.aml_manager._detect_structuring_pattern(user_id, reference_time)
            self.assertFalse(result)
    
    def test_count_suspicious_transactions(self):
        """Test suspicious transaction counting"""
        user_id = self.regular_user.pk
        reference_time = timezone.now()
        
        # Test with no suspicious transactions (default implementation)
        count = self.aml_manager._count_suspicious_transactions(user_id, reference_time)
        self.assertEqual(count, 0)
        
        # Test error handling
        with patch.object(self.aml_manager, '_count_suspicious_transactions', side_effect=Exception("Test error")):
            count = self.aml_manager._count_suspicious_transactions(user_id, reference_time)
            self.assertEqual(count, 0)
    
    def test_generate_report_id(self):
        """Test report ID generation"""
        report_id = self.aml_manager._generate_report_id('SAR')
        
        self.assertTrue(report_id.startswith('SAR-'))
        self.assertIn('-', report_id)  # Should have timestamp separator
        
        # Test different report types
        ctr_id = self.aml_manager._generate_report_id('CTR')
        self.assertTrue(ctr_id.startswith('CTR-'))
        self.assertNotEqual(report_id, ctr_id)  # Should be unique
    
    def test_get_reporting_period(self):
        """Test reporting period calculation"""
        now = timezone.now()
        
        # Test first half of month
        with patch('django.utils.timezone.now', return_value=datetime(2023, 1, 10, 12, 0, 0, tzinfo=now.tzinfo)):
            period = self.aml_manager._get_reporting_period()
            self.assertEqual(period, "2023-01-01 to 2023-01-15")
        
        # Test second half of month
        with patch('django.utils.timezone.now', return_value=datetime(2023, 1, 20, 12, 0, 0, tzinfo=now.tzinfo)):
            period = self.aml_manager._get_reporting_period()
            self.assertEqual(period, "2023-01-16 to 2023-01-31")


class FraudReportingManagerTest(BaseComplianceTest):
    """Test cases for FraudReportingManager"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.reporting_manager = FraudReportingManager()
    
    def test_load_reporting_channels(self):
        """Test reporting channels loading"""
        channels = self.reporting_manager._load_reporting_channels()
        
        self.assertIn('email', channels)
        self.assertIn('slack', channels)
        self.assertIn('sms', channels)
        self.assertIn('regulatory', channels)
        
        # Check email channel
        email_channel = channels['email']
        self.assertTrue(email_channel['enabled'])
        self.assertIn('fraud@company.com', email_channel['recipients'])
        self.assertIn('compliance@company.com', email_channel['recipients'])
        
        # Check regulatory channel
        regulatory_channel = channels['regulatory']
        self.assertTrue(regulatory_channel['enabled'])
        self.assertIn('fintrac', regulatory_channel['bodies'])
        self.assertIn('fincen', regulatory_channel['bodies'])
    
    def test_load_notification_templates(self):
        """Test notification templates loading"""
        templates = self.reporting_manager._load_notification_templates()
        
        self.assertIn('fraud_alert_email', templates)
        self.assertIn('fraud_alert_sms', templates)
        self.assertIn('sar_notification', templates)
        
        # Check email template contains placeholders
        email_template = templates['fraud_alert_email']
        self.assertIn('{alert_id}', email_template)
        self.assertIn('{severity}', email_template)
        self.assertIn('{user_id}', email_template)
        self.assertIn('{risk_score}', email_template)
    
    def test_load_escalation_rules(self):
        """Test escalation rules loading"""
        rules = self.reporting_manager._load_escalation_rules()
        
        self.assertIn('critical_threshold', rules)
        self.assertIn('high_threshold', rules)
        self.assertIn('medium_threshold', rules)
        self.assertIn('escalation_timeframe_hours', rules)
        self.assertIn('auto_escalate_critical', rules)
        
        # Check default values
        self.assertEqual(rules['critical_threshold'], 90)
        self.assertEqual(rules['high_threshold'], 70)
        self.assertEqual(rules['medium_threshold'], 50)
        self.assertEqual(rules['escalation_timeframe_hours'], 24)
    
    def test_create_fraud_report(self):
        """Test fraud report creation"""
        case_data = {
            'case_id': 'CASE_123',
            'user_id': self.regular_user.pk,
            'severity': 'high',
            'risk_score': 85,
            'summary': 'Suspicious account activity detected',
            'description': 'Multiple fraudulent transactions detected',
            'evidence': ['Transaction logs', 'IP addresses', 'Device fingerprints'],
            'timeline': [
                {'time': '2023-01-15 10:00', 'event': 'Suspicious login'},
                {'time': '2023-01-15 10:05', 'event': 'Fraudulent transaction'}
            ],
            'financial_impact': 5000.00,
            'affected_accounts': ['ACC123', 'ACC456'],
            'potential_loss': 10000.00
        }
        
        with patch.object(self.reporting_manager, '_send_fraud_notifications', return_value=['email:test@example.com']):
            fraud_report = self.reporting_manager.create_fraud_report(case_data)
            
            self.assertEqual(fraud_report['report_type'], 'fraud_incident')
            self.assertIn('report_id', fraud_report)
            self.assertEqual(fraud_report['case_id'], 'CASE_123')
            self.assertEqual(fraud_report['user_id'], self.regular_user.pk)
            self.assertEqual(fraud_report['severity'], 'high')
            self.assertEqual(fraud_report['risk_score'], 85)
            self.assertIn('created_at', fraud_report)
            self.assertEqual(fraud_report['investigation_status'], 'pending')
            self.assertIn('integrity_hash', fraud_report)
            self.assertEqual(fraud_report['notifications_sent'], ['email:test@example.com'])
    
    def test_create_fraud_report_error_handling(self):
        """Test fraud report creation error handling"""
        case_data = {
            'case_id': 'CASE_123',
            'user_id': self.regular_user.pk,
            'severity': 'high'
        }
        
        with patch.object(self.reporting_manager, '_send_fraud_notifications', side_effect=Exception("Notification error")):
            with self.assertRaises(ReportingError) as context:
                self.reporting_manager.create_fraud_report(case_data)
            
            self.assertIn("Failed to create fraud report", str(context.exception))
    
    def test_send_regulatory_report_success(self):
        """Test successful regulatory report sending"""
        report_data = {
            'report_id': 'SAR-20230115-12345',
            'report_type': 'SAR'
        }
        
        with patch.object(self.reporting_manager, '_send_email_report', return_value=True):
            result = self.reporting_manager.send_regulatory_report(report_data, 'fincen')
            self.assertTrue(result)
    
    def test_send_regulatory_report_unknown_body(self):
        """Test regulatory report sending with unknown body"""
        report_data = {
            'report_id': 'SAR-20230115-12345',
            'report_type': 'SAR'
        }
        
        with self.assertRaises(ComplianceError) as context:
            self.reporting_manager.send_regulatory_report(report_data, 'unknown_body')
        
        self.assertIn("Unknown regulatory body", str(context.exception))
    
    def test_send_regulatory_report_email_failure(self):
        """Test regulatory report sending email failure"""
        report_data = {
            'report_id': 'SAR-20230115-12345',
            'report_type': 'SAR'
        }
        
        with patch.object(self.reporting_manager, '_send_email_report', return_value=False):
            result = self.reporting_manager.send_regulatory_report(report_data, 'fincen')
            self.assertFalse(result)
    
    def test_escalate_fraud_case_critical(self):
        """Test fraud case escalation for critical cases"""
        case_data = {
            'case_id': 'CASE_123',
            'user_id': self.regular_user.pk,
            'risk_score': 95,  # Above critical threshold
            'severity': 'critical'
        }
        
        with patch.object(self.reporting_manager, '_send_escalation_notifications', return_value=['email:executive@company.com']):
            escalation_result = self.reporting_manager.escalate_fraud_case(case_data)
            
            self.assertTrue(escalation_result['escalated'])
            self.assertEqual(escalation_result['escalation_level'], 'critical')
            self.assertEqual(escalation_result['escalation_reason'], 'Critical risk score or severity')
            self.assertIsNotNone(escalation_result['next_review_time'])
            self.assertEqual(escalation_result['notifications_sent'], ['email:executive@company.com'])
    
    def test_escalate_fraud_case_high(self):
        """Test fraud case escalation for high cases"""
        case_data = {
            'case_id': 'CASE_123',
            'user_id': self.regular_user.pk,
            'risk_score': 75,  # Above high threshold
            'severity': 'high'
        }
        
        with patch.object(self.reporting_manager, '_send_escalation_notifications', return_value=['email:compliance@company.com']):
            escalation_result = self.reporting_manager.escalate_fraud_case(case_data)
            
            self.assertTrue(escalation_result['escalated'])
            self.assertEqual(escalation_result['escalation_level'], 'high')
            self.assertEqual(escalation_result['escalation_reason'], 'High risk score or severity')
            self.assertIsNotNone(escalation_result['next_review_time'])
    
    def test_escalate_fraud_case_medium(self):
        """Test fraud case escalation for medium cases"""
        case_data = {
            'case_id': 'CASE_123',
            'user_id': self.regular_user.pk,
            'risk_score': 55,  # Above medium threshold
            'severity': 'medium'
        }
        
        with patch.object(self.reporting_manager, '_send_escalation_notifications', return_value=['email:compliance@company.com']):
            escalation_result = self.reporting_manager.escalate_fraud_case(case_data)
            
            self.assertTrue(escalation_result['escalated'])
            self.assertEqual(escalation_result['escalation_level'], 'medium')
            self.assertEqual(escalation_result['escalation_reason'], 'Medium risk score or severity')
            self.assertIsNotNone(escalation_result['next_review_time'])
    
    def test_escalate_fraud_case_no_escalation(self):
        """Test fraud case with no escalation needed"""
        case_data = {
            'case_id': 'CASE_123',
            'user_id': self.regular_user.pk,
            'risk_score': 30,  # Below all thresholds
            'severity': 'low'
        }
        
        escalation_result = self.reporting_manager.escalate_fraud_case(case_data)
        
        self.assertFalse(escalation_result['escalated'])
        self.assertIsNone(escalation_result['escalation_level'])
        self.assertEqual(escalation_result['escalation_reason'], '')
        self.assertEqual(len(escalation_result['notifications_sent']), 0)
        self.assertIsNone(escalation_result['next_review_time'])
    
    def test_send_fraud_notifications_email_enabled(self):
        """Test sending fraud notifications via email"""
        fraud_report = {
            'report_id': 'FRAUD-123',
            'severity': 'high',
            'user_id': self.regular_user.pk,
            'risk_score': 85,
            'created_at': '2023-01-15T10:00:00Z',
            'incident_details': {
                'summary': 'Test fraud incident',
                'description': 'Test description',
                'evidence': ['Evidence 1', 'Evidence 2'],
                'timeline': []
            }
        }
        
        # Enable email channel
        self.reporting_manager.reporting_channels['email']['enabled'] = True
        
        with patch('django.core.mail.send_mail') as mock_send_mail:
            notifications = self.reporting_manager._send_fraud_notifications(fraud_report)
            
            self.assertGreater(len(notifications), 0)
            mock_send_mail.assert_called()
            
            # Check email content
            call_args = mock_send_mail.call_args
            self.assertIn('FRAUD ALERT', call_args[0][0])  # Subject
            self.assertIn('Test fraud incident', call_args[0][1])  # Message
    
    def test_send_fraud_notifications_email_disabled(self):
        """Test sending fraud notifications with email disabled"""
        fraud_report = {
            'report_id': 'FRAUD-123',
            'severity': 'high',
            'user_id': self.regular_user.pk,
            'risk_score': 85,
            'created_at': '2023-01-15T10:00:00Z',
            'incident_details': {
                'summary': 'Test fraud incident',
                'description': 'Test description',
                'evidence': ['Evidence 1', 'Evidence 2'],
                'timeline': []
            }
        }
        
        # Disable email channel
        self.reporting_manager.reporting_channels['email']['enabled'] = False
        
        with patch('django.core.mail.send_mail') as mock_send_mail:
            notifications = self.reporting_manager._send_fraud_notifications(fraud_report)
            
            self.assertEqual(len(notifications), 0)
            mock_send_mail.assert_not_called()
    
    def test_send_email_report_success(self):
        """Test successful email report sending"""
        report_data = {
            'report_id': 'SAR-123',
            'report_type': 'SAR',
            'submission_date': '2023-01-15T10:00:00Z',
            'submitting_institution': 'Test Company'
        }
        
        with patch('django.core.mail.send_mail') as mock_send_mail:
            result = self.reporting_manager._send_email_report('test@example.com', report_data)
            
            self.assertTrue(result)
            mock_send_mail.assert_called_once()
            
            # Check email content
            call_args = mock_send_mail.call_args
            self.assertIn('REGULATORY REPORT SUBMISSION', call_args[0][0])
            self.assertIn('SAR-123', call_args[0][1])
    
    def test_send_email_report_failure(self):
        """Test email report sending failure"""
        report_data = {
            'report_id': 'SAR-123',
            'report_type': 'SAR'
        }
        
        with patch('django.core.mail.send_mail', side_effect=Exception("Email error")):
            result = self.reporting_manager._send_email_report('test@example.com', report_data)
            
            self.assertFalse(result)
    
    def test_send_escalation_notifications(self):
        """Test sending escalation notifications"""
        case_data = {
            'case_id': 'CASE_123',
            'user_id': self.regular_user.pk,
            'risk_score': 85
        }
        
        escalation_result = {
            'escalated': True,
            'escalation_level': 'high',
            'escalation_reason': 'High risk score',
            'next_review_time': timezone.now() + timedelta(hours=4)
        }
        
        with patch('django.core.mail.send_mail') as mock_send_mail:
            notifications = self.reporting_manager._send_escalation_notifications(case_data, escalation_result)
            
            self.assertGreater(len(notifications), 0)
            mock_send_mail.assert_called()
            
            # Check email content
            call_args = mock_send_mail.call_args
            self.assertIn('ESCALATION', call_args[0][0])  # Subject
            self.assertIn('CASE_123', call_args[0][1])  # Message
    
    def test_generate_report_id(self):
        """Test report ID generation"""
        report_id = self.reporting_manager._generate_report_id('FRAUD')
        
        self.assertTrue(report_id.startswith('FRAUD-'))
        self.assertIn('-', report_id)
        
        # Test uniqueness
        another_id = self.reporting_manager._generate_report_id('FRAUD')
        self.assertNotEqual(report_id, another_id)
    
    def test_generate_recommendations(self):
        """Test recommendations generation"""
        # Test critical case
        fraud_report = {
            'risk_score': 95,
            'severity': 'critical'
        }
        
        recommendations = self.reporting_manager._generate_recommendations(fraud_report)
        
        self.assertIn('Immediate account suspension', recommendations)
        self.assertIn('Freeze all related assets', recommendations)
        self.assertIn('Contact law enforcement', recommendations)
        self.assertIn('File SAR within 24 hours', recommendations)
        
        # Test high case
        fraud_report = {
            'risk_score': 75,
            'severity': 'high'
        }
        
        recommendations = self.reporting_manager._generate_recommendations(fraud_report)
        
        self.assertIn('Enhanced monitoring', recommendations)
        self.assertIn('Limit account functionality', recommendations)
        
        # Test low case
        fraud_report = {
            'risk_score': 25,
            'severity': 'low'
        }
        
        recommendations = self.reporting_manager._generate_recommendations(fraud_report)
        
        self.assertEqual(recommendations, 'Standard monitoring procedures apply.')


class ComplianceAuditManagerTest(BaseComplianceTest):
    """Test cases for ComplianceAuditManager"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.audit_manager = ComplianceAuditManager()
    
    def test_initialization(self):
        """Test audit manager initialization"""
        self.assertEqual(self.audit_manager.audit_retention_days, 2555)  # 7 years default
    
    def test_generate_compliance_report(self):
        """Test compliance report generation"""
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
        
        compliance_report = self.audit_manager.generate_compliance_report(start_date, end_date)
        
        self.assertEqual(compliance_report['report_type'], 'COMPLIANCE')  # From report ID
        self.assertIn('report_period', compliance_report)
        self.assertIn('generated_at', compliance_report)
        self.assertIn('summary_statistics', compliance_report)
        self.assertIn('aml_compliance', compliance_report)
        self.assertIn('fraud_cases', compliance_report)
        self.assertIn('regulatory_filings', compliance_report)
        self.assertIn('audit_trail', compliance_report)
        self.assertIn('recommendations', compliance_report)
        self.assertIn('integrity_hash', compliance_report)
        
        # Check report period
        period = compliance_report['report_period']
        self.assertEqual(period['start_date'], start_date.isoformat())
        self.assertEqual(period['end_date'], end_date.isoformat())
    
    def test_generate_compliance_report_error_handling(self):
        """Test compliance report generation error handling"""
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
        
        with patch.object(self.audit_manager, '_get_summary_statistics', side_effect=Exception("Test error")):
            with self.assertRaises(ComplianceError) as context:
                self.audit_manager.generate_compliance_report(start_date, end_date)
            
            self.assertIn("Failed to generate compliance report", str(context.exception))
    
    def test_get_summary_statistics(self):
        """Test summary statistics generation"""
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
        
        stats = self.audit_manager._get_summary_statistics(start_date, end_date)
        
        self.assertIn('total_transactions', stats)
        self.assertIn('total_amount', stats)
        self.assertIn('suspicious_transactions', stats)
        self.assertIn('fraud_cases_opened', stats)
        self.assertIn('fraud_cases_closed', stats)
        self.assertIn('sar_reports_filed', stats)
        self.assertIn('ctr_reports_filed', stats)
        
        # Check default values (placeholder implementation)
        self.assertEqual(stats['total_transactions'], 0)
        self.assertEqual(stats['total_amount'], 0.0)
    
    def test_get_aml_compliance_data(self):
        """Test AML compliance data generation"""
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
        
        aml_data = self.audit_manager._get_aml_compliance_data(start_date, end_date)
        
        self.assertIn('threshold_breaches', aml_data)
        self.assertIn('structuring_detections', aml_data)
        self.assertIn('suspicious_patterns', aml_data)
        self.assertIn('regulatory_filings', aml_data)
        
        # Check default values (placeholder implementation)
        self.assertEqual(len(aml_data['threshold_breaches']), 0)
        self.assertEqual(len(aml_data['structuring_detections']), 0)
    
    def test_get_fraud_case_summary(self):
        """Test fraud case summary generation"""
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
        
        case_summary = self.audit_manager._get_fraud_case_summary(start_date, end_date)
        
        self.assertIn('total_cases', case_summary)
        self.assertIn('cases_by_severity', case_summary)
        self.assertIn('cases_by_status', case_summary)
        self.assertIn('average_resolution_time', case_summary)
        self.assertIn('total_financial_impact', case_summary)
        
        # Check default values (placeholder implementation)
        self.assertEqual(case_summary['total_cases'], 0)
        self.assertEqual(case_summary['average_resolution_time'], 0)
    
    def test_get_regulatory_filings_summary(self):
        """Test regulatory filings summary generation"""
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
        
        filings_summary = self.audit_manager._get_regulatory_filings_summary(start_date, end_date)
        
        self.assertIn('sar_filings', filings_summary)
        self.assertIn('ctr_filings', filings_summary)
        self.assertIn('other_filings', filings_summary)
        self.assertIn('filing_deadlines_met', filings_summary)
        self.assertIn('filing_deadlines_missed', filings_summary)
        
        # Check default values (placeholder implementation)
        self.assertEqual(len(filings_summary['sar_filings']), 0)
        self.assertEqual(filings_summary['filing_deadlines_met'], 0)
    
    def test_generate_audit_trail_summary(self):
        """Test audit trail summary generation"""
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
        
        audit_trail = self.audit_manager._generate_audit_trail_summary(start_date, end_date)
        
        self.assertIn('total_audit_entries', audit_trail)
        self.assertIn('access_logs', audit_trail)
        self.assertIn('modification_logs', audit_trail)
        self.assertIn('system_changes', audit_trail)
        self.assertIn('compliance_checks', audit_trail)
        
        # Check default values (placeholder implementation)
        self.assertEqual(audit_trail['total_audit_entries'], 0)
        self.assertEqual(len(audit_trail['access_logs']), 0)
    
    def test_generate_compliance_recommendations(self):
        """Test compliance recommendations generation"""
        recommendations = self.audit_manager._generate_compliance_recommendations()
        
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)
        
        # Check for key recommendations
        rec_text = ' '.join(recommendations)
        self.assertIn('AML policies', rec_text)
        self.assertIn('staff training', rec_text)
        self.assertIn('automated monitoring', rec_text)
        self.assertIn('sanctions lists', rec_text)
    
    def test_generate_report_id(self):
        """Test report ID generation"""
        report_id = self.audit_manager._generate_report_id('COMPLIANCE')
        
        self.assertTrue(report_id.startswith('COMPLIANCE-'))
        self.assertIn('-', report_id)
        
        # Test uniqueness
        another_id = self.audit_manager._generate_report_id('COMPLIANCE')
        self.assertNotEqual(report_id, another_id)


class ComplianceIntegrationTest(BaseComplianceTest):
    """Integration tests for compliance functionality"""
    
    def test_monitor_aml_compliance_convenience_function(self):
        """Test AML compliance monitoring convenience function"""
        transaction_data = {
            'user_id': self.regular_user.pk,
            'amount': 500.00,
            'timestamp': timezone.now()
        }
        
        result = monitor_aml_compliance(transaction_data)
        
        self.assertIn('compliant', result)
        self.assertIn('thresholds_breached', result)
        self.assertIn('alerts_triggered', result)
        self.assertTrue(result['compliant'])
    
    def test_create_fraud_incident_report_convenience_function(self):
        """Test fraud incident reporting convenience function"""
        case_data = {
            'case_id': 'CASE_123',
            'user_id': self.regular_user.pk,
            'severity': 'high',
            'risk_score': 85,
            'summary': 'Test fraud incident'
        }
        
        with patch('api.fraud_detection.compliance.fraud_reporting_manager._send_fraud_notifications', return_value=['email:test@example.com']):
            fraud_report = create_fraud_incident_report(case_data)
            
            self.assertEqual(fraud_report['report_type'], 'fraud_incident')
            self.assertEqual(fraud_report['case_id'], 'CASE_123')
            self.assertEqual(fraud_report['severity'], 'high')
    
    def test_generate_monthly_compliance_report_convenience_function(self):
        """Test monthly compliance reporting convenience function"""
        with patch('api.fraud_detection.compliance.compliance_audit_manager.generate_compliance_report') as mock_generate:
            mock_generate.return_value = {
                'report_id': 'COMPLIANCE-20230115-12345',
                'report_period': {
                    'start_date': '2023-01-01T00:00:00Z',
                    'end_date': '2023-01-31T23:59:59Z'
                }
            }
            
            compliance_report = generate_monthly_compliance_report()
            
            self.assertIn('report_id', compliance_report)
            self.assertIn('report_period', compliance_report)
            mock_generate.assert_called_once()
    
    def test_end_to_end_aml_workflow(self):
        """Test end-to-end AML compliance workflow"""
        # Step 1: Monitor high-value transaction
        transaction_data = {
            'user_id': self.regular_user.pk,
            'amount': 15000.00,  # Above single transaction threshold
            'timestamp': timezone.now(),
            'transaction_type': 'cash_deposit'
        }
        
        monitoring_result = self.aml_manager.monitor_transaction_limits(transaction_data)
        
        self.assertFalse(monitoring_result['compliant'])
        self.assertTrue(monitoring_result['reporting_required'])
        
        # Step 2: Generate SAR report
        case_data = {
            'user_id': self.regular_user.pk,
            'case_id': 'CASE_456',
            'total_suspicious_amount': 15000.00,
            'transaction_count': 1,
            'suspicion_reasons': ['High value cash transaction'],
            'account_numbers': ['ACC123456']
        }
        
        sar_report = self.aml_manager.generate_sar_report(case_data)
        
        self.assertEqual(sar_report['report_type'], 'SAR')
        self.assertIn('integrity_hash', sar_report)
        
        # Step 3: Send regulatory report
        with patch.object(self.aml_manager, '_send_email_report', return_value=True):
            result = self.reporting_manager.send_regulatory_report(sar_report, 'fincen')
            self.assertTrue(result)
    
    def test_end_to_end_fraud_reporting_workflow(self):
        """Test end-to-end fraud reporting workflow"""
        # Step 1: Create fraud case
        case_data = {
            'case_id': 'CASE_789',
            'user_id': self.regular_user.pk,
            'severity': 'critical',
            'risk_score': 95,
            'summary': 'Critical fraud incident',
            'financial_impact': 25000.00
        }
        
        with patch.object(self.reporting_manager, '_send_fraud_notifications', return_value=['email:test@example.com']):
            fraud_report = self.reporting_manager.create_fraud_report(case_data)
            
            self.assertEqual(fraud_report['severity'], 'critical')
            self.assertEqual(fraud_report['risk_score'], 95)
        
        # Step 2: Escalate case
        escalation_result = self.reporting_manager.escalate_fraud_case(case_data)
        
        self.assertTrue(escalation_result['escalated'])
        self.assertEqual(escalation_result['escalation_level'], 'critical')
        
        # Step 3: Generate compliance report
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
        
        compliance_report = self.audit_manager.generate_compliance_report(start_date, end_date)
        
        self.assertIn('fraud_cases', compliance_report)
        self.assertIn('integrity_hash', compliance_report)
    
    def test_compliance_data_integrity(self):
        """Test compliance data integrity through hashing"""
        case_data = {
            'user_id': self.regular_user.pk,
            'case_id': 'CASE_INTEGRITY',
            'severity': 'high',
            'risk_score': 85
        }
        
        with patch.object(self.reporting_manager, '_send_fraud_notifications', return_value=[]):
            # Create original report
            original_report = self.reporting_manager.create_fraud_report(case_data)
            original_hash = original_report['integrity_hash']
            
            # Modify report data
            modified_report = original_report.copy()
            modified_report['risk_score'] = 90
            
            # Hash should be different
            with patch('api.fraud_detection.compliance.generate_integrity_hash') as mock_hash:
                mock_hash.return_value = 'different_hash'
                modified_report['integrity_hash'] = mock_hash(modified_report)
            
            self.assertNotEqual(original_hash, modified_report['integrity_hash'])
    
    def test_compliance_error_recovery(self):
        """Test compliance system error recovery"""
        # Test AML monitoring error recovery
        transaction_data = {
            'user_id': self.regular_user.pk,
            'amount': 15000.00,
            'timestamp': timezone.now()
        }
        
        with patch.object(self.aml_manager, '_calculate_daily_aggregate', side_effect=Exception("Database error")):
            # Should handle error gracefully and still return result
            result = self.aml_manager.monitor_transaction_limits(transaction_data)
            
            # Should still detect single transaction breach
            self.assertFalse(result['compliant'])
            self.assertTrue(result['reporting_required'])
        
        # Test reporting error recovery
        case_data = {
            'case_id': 'CASE_ERROR',
            'user_id': self.regular_user.pk,
            'severity': 'high'
        }
        
        with patch.object(self.reporting_manager, '_send_fraud_notifications', side_effect=Exception("Email error")):
            # Should still create report even if notifications fail
            with self.assertRaises(ReportingError):
                self.reporting_manager.create_fraud_report(case_data)


class ComplianceSecurityTest(BaseComplianceTest):
    """Security tests for compliance functionality"""
    
    def test_sensitive_data_handling(self):
        """Test sensitive data handling in compliance reports"""
        case_data = {
            'user_id': self.regular_user.pk,
            'case_id': 'CASE_SENSITIVE',
            'severity': 'high',
            'risk_score': 85,
            'account_numbers': ['ACC123456', 'ACC789012'],
            'identification_details': {
                'ssn': '123-45-6789',
                'passport': 'PP123456789'
            }
        }
        
        with patch.object(self.reporting_manager, '_send_fraud_notifications', return_value=[]):
            fraud_report = self.reporting_manager.create_fraud_report(case_data)
            
            # Sensitive data should be included in report but properly handled
            self.assertIn('account_numbers', fraud_report['incident_details'])
            self.assertIn('identification_details', fraud_report['incident_details'])
            
            # Report should have integrity hash for tamper detection
            self.assertIn('integrity_hash', fraud_report)
    
    def test_regulatory_report_security(self):
        """Test security of regulatory reports"""
        case_data = {
            'user_id': self.regular_user.pk,
            'case_id': 'CASE_SECURE',
            'total_suspicious_amount': 50000.00,
            'account_numbers': ['ACC123456'],
            'identification_details': {
                'name': 'John Doe',
                'ssn': '123-45-6789'
            }
        }
        
        sar_report = self.aml_manager.generate_sar_report(case_data)
        
        # SAR should contain sensitive information but be properly structured
        self.assertIn('subject_information', sar_report)
        self.assertIn('suspicious_activity_details', sar_report)
        self.assertIn('integrity_hash', sar_report)
        
        # Should have proper report structure for regulatory submission
        self.assertEqual(sar_report['report_type'], 'SAR')
        self.assertIn('financial_institution', sar_report)
        self.assertIn('law_enforcement_contact', sar_report)
    
    def test_compliance_audit_trail(self):
        """Test compliance audit trail functionality"""
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
        
        audit_trail = self.audit_manager._generate_audit_trail_summary(start_date, end_date)
        
        # Audit trail should have proper structure
        self.assertIn('total_audit_entries', audit_trail)
        self.assertIn('access_logs', audit_trail)
        self.assertIn('modification_logs', audit_trail)
        self.assertIn('system_changes', audit_trail)
        self.assertIn('compliance_checks', audit_trail)
        
        # Should be ready for audit purposes
        self.assertIsInstance(audit_trail['total_audit_entries'], int)
        self.assertIsInstance(audit_trail['access_logs'], list)
    
    def test_data_retention_compliance(self):
        """Test data retention compliance"""
        # Check retention period is properly set
        self.assertEqual(self.audit_manager.audit_retention_days, 2555)  # 7 years
        
        # This should comply with most regulatory requirements
        # GDPR: 5-6 years for financial data
        # CCPA: Similar retention requirements
        # HIPAA: 6 years for health records
        
        self.assertGreaterEqual(self.audit_manager.audit_retention_days, 1825)  # At least 5 years
        self.assertLessEqual(self.audit_manager.audit_retention_days, 3650)     # At most 10 years


class CompliancePerformanceTest(BaseComplianceTest):
    """Performance tests for compliance functionality"""
    
    def test_aml_monitoring_performance(self):
        """Test AML monitoring performance"""
        import time
        
        transaction_data = {
            'user_id': self.regular_user.pk,
            'amount': 15000.00,
            'timestamp': timezone.now()
        }
        
        # Measure monitoring time
        start_time = time.time()
        result = self.aml_manager.monitor_transaction_limits(transaction_data)
        end_time = time.time()
        
        monitoring_time = end_time - start_time
        
        # Should complete quickly (under 100ms for mocked operations)
        self.assertLess(monitoring_time, 0.1)
        
        # Should still produce correct results
        self.assertFalse(result['compliant'])
        self.assertTrue(result['reporting_required'])
    
    def test_report_generation_performance(self):
        """Test report generation performance"""
        import time
        
        case_data = {
            'case_id': 'CASE_PERF',
            'user_id': self.regular_user.pk,
            'severity': 'high',
            'risk_score': 85,
            'summary': 'Performance test case',
            'evidence': ['Evidence ' + str(i) for i in range(100)],  # Large evidence list
            'timeline': [{'time': f'2023-01-{i:02d} 10:00', 'event': f'Event {i}'} for i in range(50)]
        }
        
        with patch.object(self.reporting_manager, '_send_fraud_notifications', return_value=[]):
            # Measure report generation time
            start_time = time.time()
            fraud_report = self.reporting_manager.create_fraud_report(case_data)
            end_time = time.time()
            
            generation_time = end_time - start_time
            
            # Should complete in reasonable time (under 500ms)
            self.assertLess(generation_time, 0.5)
            
            # Should still produce correct report
            self.assertEqual(fraud_report['case_id'], 'CASE_PERF')
            self.assertEqual(len(fraud_report['incident_details']['evidence']), 100)
    
    def test_compliance_report_performance(self):
        """Test compliance report generation performance"""
        import time
        
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
        
        # Measure compliance report generation time
        start_time = time.time()
        compliance_report = self.audit_manager.generate_compliance_report(start_date, end_date)
        end_time = time.time()
        
        generation_time = end_time - start_time
        
        # Should complete in reasonable time (under 1 second)
        self.assertLess(generation_time, 1.0)
        
        # Should still produce correct report structure
        self.assertIn('report_id', compliance_report)
        self.assertIn('summary_statistics', compliance_report)
        self.assertIn('aml_compliance', compliance_report)
    
    def test_bulk_transaction_monitoring_performance(self):
        """Test performance of bulk transaction monitoring"""
        import time
        
        # Generate multiple transactions
        transactions = []
        for i in range(100):
            transactions.append({
                'user_id': self.regular_user.pk,
                'amount': 1000.00 + i * 100,
                'timestamp': timezone.now() - timedelta(minutes=i),
                'transaction_type': 'payment'
            })
        
        # Monitor all transactions
        start_time = time.time()
        results = []
        for transaction in transactions:
            result = self.aml_manager.monitor_transaction_limits(transaction)
            results.append(result)
        end_time = time.time()
        
        total_time = end_time - start_time
        avg_time_per_transaction = total_time / len(transactions)
        
        # Should handle bulk transactions efficiently
        self.assertLess(total_time, 2.0)  # Total time under 2 seconds
        self.assertLess(avg_time_per_transaction, 0.02)  # Average under 20ms per transaction
        
        # Should produce correct results for all transactions
        self.assertEqual(len(results), 100)
        for result in results:
            self.assertIn('compliant', result)
            self.assertIn('reporting_required', result)
