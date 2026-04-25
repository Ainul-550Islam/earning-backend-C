"""
Test Fraud Config

Comprehensive tests for fraud configuration functionality
including fraud rules, pattern detection, and automated blocking.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock

from ..models.fraud import FraudRule, FraudConfig, ConversionQualityScore
from ..models.tracking import Conversion
from ..models.advertiser import Advertiser
try:
    from ..services import AdvertiserFraudService
except ImportError:
    AdvertiserFraudService = None
try:
    from ..services import ConversionQualityService
except ImportError:
    ConversionQualityService = None
try:
    from ..services import AdvertiserService
except ImportError:
    AdvertiserService = None

User = get_user_model()


class FraudConfigServiceTestCase(TestCase):
    """Test cases for fraud configuration service."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.fraud_service = AdvertiserFraudService()
        self.quality_service = ConversionQualityService()
        
        self.advertiser = self.advertiser_service.create_advertiser(
            self.user, 
            {
                'company_name': 'Test Company',
                'contact_email': 'contact@testcompany.com',
                'contact_phone': '+1234567890',
                'website': 'https://testcompany.com',
                'industry': 'technology',
                'company_size': 'medium',
            }
        )
        
        self.valid_fraud_rule_data = {
            'name': 'High Velocity Rule',
            'description': 'Detect high velocity conversions',
            'rule_type': 'velocity',
            'conditions': {
                'max_conversions_per_hour': 10,
                'time_window': 3600
            },
            'actions': {
                'flag_conversion': True,
                'block_ip': False,
                'notify_admin': True
            },
            'severity': 'medium',
            'is_active': True,
        }
    
    def test_create_fraud_rule_success(self):
        """Test successful fraud rule creation."""
        rule = self.fraud_service.create_fraud_rule(
            self.advertiser,
            self.valid_fraud_rule_data
        )
        
        self.assertIsInstance(rule, FraudRule)
        self.assertEqual(rule.advertiser, self.advertiser)
        self.assertEqual(rule.name, 'High Velocity Rule')
        self.assertEqual(rule.rule_type, 'velocity')
        self.assertEqual(rule.severity, 'medium')
        self.assertTrue(rule.is_active)
    
    def test_create_fraud_rule_invalid_data(self):
        """Test fraud rule creation with invalid data."""
        invalid_data = self.valid_fraud_rule_data.copy()
        invalid_data['name'] = ''  # Empty name
        
        with self.assertRaises(ValueError) as context:
            self.fraud_service.create_fraud_rule(
                self.advertiser,
                invalid_data
            )
        
        self.assertIn('Rule name is required', str(context.exception))
    
    def test_create_fraud_rule_invalid_type(self):
        """Test fraud rule creation with invalid type."""
        invalid_data = self.valid_fraud_rule_data.copy()
        invalid_data['rule_type'] = 'invalid_type'
        
        with self.assertRaises(ValueError) as context:
            self.fraud_service.create_fraud_rule(
                self.advertiser,
                invalid_data
            )
        
        self.assertIn('Invalid rule type', str(context.exception))
    
    def test_update_fraud_rule_success(self):
        """Test successful fraud rule update."""
        rule = self.fraud_service.create_fraud_rule(
            self.advertiser,
            self.valid_fraud_rule_data
        )
        
        update_data = {
            'name': 'Updated Rule',
            'description': 'Updated description',
            'severity': 'high',
        }
        
        updated_rule = self.fraud_service.update_fraud_rule(
            rule,
            update_data
        )
        
        self.assertEqual(updated_rule.name, 'Updated Rule')
        self.assertEqual(updated_rule.description, 'Updated description')
        self.assertEqual(updated_rule.severity, 'high')
        self.assertEqual(rule.rule_type, 'velocity')  # Unchanged
    
    def test_activate_fraud_rule_success(self):
        """Test successful fraud rule activation."""
        rule = self.fraud_service.create_fraud_rule(
            self.advertiser,
            self.valid_fraud_rule_data
        )
        
        # Deactivate first
        rule.is_active = False
        rule.save()
        
        # Activate
        activated_rule = self.fraud_service.activate_fraud_rule(rule)
        
        self.assertTrue(activated_rule.is_active)
        self.assertIsNotNone(activated_rule.activated_at)
    
    def test_deactivate_fraud_rule_success(self):
        """Test successful fraud rule deactivation."""
        rule = self.fraud_service.create_fraud_rule(
            self.advertiser,
            self.valid_fraud_rule_data
        )
        
        # Deactivate
        deactivated_rule = self.fraud_service.deactivate_fraud_rule(rule)
        
        self.assertFalse(deactivated_rule.is_active)
        self.assertIsNotNone(deactivated_rule.deactivated_at)
    
    def test_delete_fraud_rule_success(self):
        """Test successful fraud rule deletion."""
        rule = self.fraud_service.create_fraud_rule(
            self.advertiser,
            self.valid_fraud_rule_data
        )
        
        rule_id = rule.id
        
        self.fraud_service.delete_fraud_rule(rule)
        
        with self.assertRaises(FraudRule.DoesNotExist):
            FraudRule.objects.get(id=rule_id)
    
    def test_apply_fraud_rules_success(self):
        """Test successful fraud rule application."""
        # Create conversion
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            created_at=timezone.now()
        )
        
        # Create fraud rule
        rule = self.fraud_service.create_fraud_rule(
            self.advertiser,
            self.valid_fraud_rule_data
        )
        
        # Apply rules
        result = self.fraud_service.apply_fraud_rules(conversion)
        
        self.assertIn('fraud_score', result)
        self.assertIn('is_flagged', result)
        self.assertIn('risk_factors', result)
        self.assertIn('applied_rules', result)
        
        self.assertIsInstance(result['fraud_score'], float)
        self.assertGreaterEqual(result['fraud_score'], 0.0)
        self.assertLessEqual(result['fraud_score'], 1.0)
    
    def test_apply_fraud_rules_no_rules(self):
        """Test applying fraud rules with no rules configured."""
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            created_at=timezone.now()
        )
        
        result = self.fraud_service.apply_fraud_rules(conversion)
        
        self.assertEqual(result['fraud_score'], 0.0)
        self.assertFalse(result['is_flagged'])
        self.assertEqual(len(result['applied_rules']), 0)
    
    def test_apply_fraud_rules_high_velocity(self):
        """Test applying fraud rules for high velocity detection."""
        # Create multiple conversions from same IP
        for i in range(15):  # More than the rule limit of 10
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('25.00'),
                ip_address='192.168.1.1',  # Same IP
                user_agent='Mozilla/5.0',
                created_at=timezone.now() - timezone.timedelta(minutes=i)
            )
        
        # Create velocity rule
        rule_data = self.valid_fraud_rule_data.copy()
        rule_data['conditions'] = {
            'max_conversions_per_hour': 10,
            'time_window': 3600
        }
        
        rule = self.fraud_service.create_fraud_rule(
            self.advertiser,
            rule_data
        )
        
        # Apply rules to last conversion
        last_conversion = Conversion.objects.filter(
            advertiser=self.advertiser
        ).order_by('-created_at').first()
        
        result = self.fraud_service.apply_fraud_rules(last_conversion)
        
        self.assertGreater(result['fraud_score'], 0.5)  # Should be flagged
        self.assertTrue(result['is_flagged'])
        self.assertIn('high_velocity', str(result['risk_factors']))
    
    def test_apply_fraud_rules_suspicious_ip(self):
        """Test applying fraud rules for suspicious IP detection."""
        # Create conversion from suspicious IP
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.100',  # Suspicious IP
            user_agent='Mozilla/5.0',
            created_at=timezone.now()
        )
        
        # Create IP blacklist rule
        rule_data = {
            'name': 'IP Blacklist Rule',
            'description': 'Block conversions from blacklisted IPs',
            'rule_type': 'ip_blacklist',
            'conditions': {
                'blacklisted_ips': ['192.168.1.100', '192.168.1.101']
            },
            'actions': {
                'flag_conversion': True,
                'block_ip': True,
                'notify_admin': True
            },
            'severity': 'high',
            'is_active': True,
        }
        
        rule = self.fraud_service.create_fraud_rule(
            self.advertiser,
            rule_data
        )
        
        # Apply rules
        result = self.fraud_service.apply_fraud_rules(conversion)
        
        self.assertGreater(result['fraud_score'], 0.7)  # Should be high
        self.assertTrue(result['is_flagged'])
        self.assertIn('blacklisted_ip', str(result['risk_factors']))
    
    def test_apply_fraud_rules_unusual_revenue(self):
        """Test applying fraud rules for unusual revenue detection."""
        # Create conversion with unusual revenue
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('1000.00'),  # Unusually high
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            created_at=timezone.now()
        )
        
        # Create revenue anomaly rule
        rule_data = {
            'name': 'Revenue Anomaly Rule',
            'description': 'Detect unusual revenue amounts',
            'rule_type': 'revenue_anomaly',
            'conditions': {
                'max_revenue': 100.00,
                'min_revenue': 1.00
            },
            'actions': {
                'flag_conversion': True,
                'block_ip': False,
                'notify_admin': True
            },
            'severity': 'medium',
            'is_active': True,
        }
        
        rule = self.fraud_service.create_fraud_rule(
            self.advertiser,
            rule_data
        )
        
        # Apply rules
        result = self.fraud_service.apply_fraud_rules(conversion)
        
        self.assertGreater(result['fraud_score'], 0.4)  # Should be flagged
        self.assertTrue(result['is_flagged'])
        self.assertIn('unusual_revenue', str(result['risk_factors']))
    
    def test_get_fraud_rules_success(self):
        """Test getting fraud rules."""
        # Create multiple rules
        for i in range(3):
            data = self.valid_fraud_rule_data.copy()
            data['name'] = f'Rule {i}'
            data['severity'] = ['low', 'medium', 'high'][i]
            
            self.fraud_service.create_fraud_rule(
                self.advertiser,
                data
            )
        
        # Get rules
        rules = self.fraud_service.get_fraud_rules(self.advertiser)
        
        self.assertEqual(len(rules), 3)
        
        # Check that all rules are returned
        rule_names = [rule.name for rule in rules]
        self.assertIn('Rule 0', rule_names)
        self.assertIn('Rule 1', rule_names)
        self.assertIn('Rule 2', rule_names)
    
    def test_get_active_fraud_rules_success(self):
        """Test getting active fraud rules."""
        # Create multiple rules
        rules = []
        for i in range(3):
            data = self.valid_fraud_rule_data.copy()
            data['name'] = f'Rule {i}'
            
            rule = self.fraud_service.create_fraud_rule(
                self.advertiser,
                data
            )
            
            # Deactivate one rule
            if i == 1:
                rule.is_active = False
                rule.save()
            
            rules.append(rule)
        
        # Get active rules
        active_rules = self.fraud_service.get_active_fraud_rules(self.advertiser)
        
        self.assertEqual(len(active_rules), 2)
        
        # Check that only active rules are returned
        for rule in active_rules:
            self.assertTrue(rule.is_active)
    
    def test_get_fraud_rule_by_id_success(self):
        """Test getting fraud rule by ID."""
        rule = self.fraud_service.create_fraud_rule(
            self.advertiser,
            self.valid_fraud_rule_data
        )
        
        retrieved_rule = self.fraud_service.get_fraud_rule_by_id(
            self.advertiser,
            rule.id
        )
        
        self.assertEqual(retrieved_rule.id, rule.id)
        self.assertEqual(retrieved_rule.name, 'High Velocity Rule')
    
    def test_get_fraud_rule_by_id_not_found(self):
        """Test getting fraud rule by ID when not found."""
        with self.assertRaises(ValueError) as context:
            self.fraud_service.get_fraud_rule_by_id(
                self.advertiser,
                99999  # Non-existent ID
            )
        
        self.assertIn('Fraud rule not found', str(context.exception))
    
    def test_validate_fraud_rule_success(self):
        """Test successful fraud rule validation."""
        is_valid, errors = self.fraud_service.validate_fraud_rule(
            self.valid_fraud_rule_data
        )
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_fraud_rule_invalid_type(self):
        """Test fraud rule validation with invalid type."""
        invalid_data = self.valid_fraud_rule_data.copy()
        invalid_data['rule_type'] = 'invalid_type'
        
        is_valid, errors = self.fraud_service.validate_fraud_rule(
            invalid_data
        )
        
        self.assertFalse(is_valid)
        self.assertIn('rule_type', errors)
        self.assertIn('Invalid rule type', errors['rule_type'])
    
    def test_validate_fraud_rule_invalid_severity(self):
        """Test fraud rule validation with invalid severity."""
        invalid_data = self.valid_fraud_rule_data.copy()
        invalid_data['severity'] = 'invalid_severity'
        
        is_valid, errors = self.fraud_service.validate_fraud_rule(
            invalid_data
        )
        
        self.assertFalse(is_valid)
        self.assertIn('severity', errors)
        self.assertIn('Invalid severity level', errors['severity'])
    
    def test_get_supported_rule_types(self):
        """Test getting supported rule types."""
        rule_types = self.fraud_service.get_supported_rule_types()
        
        expected_types = [
            'velocity',
            'ip_blacklist',
            'revenue_anomaly',
            'user_agent_anomaly',
            'geo_anomaly',
            'time_pattern',
            'conversion_pattern',
            'device_fingerprint'
        ]
        
        for rule_type in expected_types:
            self.assertIn(rule_type, rule_types)
    
    def test_get_supported_severity_levels(self):
        """Test getting supported severity levels."""
        severity_levels = self.fraud_service.get_supported_severity_levels()
        
        expected_levels = ['low', 'medium', 'high', 'critical']
        
        for level in expected_levels:
            self.assertIn(level, severity_levels)
    
    def test_analyze_fraud_patterns_success(self):
        """Test successful fraud pattern analysis."""
        # Create conversions with fraud indicators
        for i in range(20):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('25.00'),
                ip_address=f'192.168.1.{i % 5}',  # Some IPs repeated
                user_agent='Mozilla/5.0',
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
            
            # Flag some conversions
            if i % 4 == 0:
                conversion.is_flagged = True
                conversion.fraud_score = 0.8
                conversion.save()
        
        # Analyze patterns
        patterns = self.fraud_service.analyze_fraud_patterns(
            self.advertiser,
            days=7
        )
        
        self.assertIn('ip_patterns', patterns)
        self.assertIn('time_patterns', patterns)
        self.assertIn('revenue_patterns', patterns)
        self.assertIn('device_patterns', patterns)
        self.assertIn('recommendations', patterns)
    
    def test_analyze_fraud_patterns_no_data(self):
        """Test fraud pattern analysis with no data."""
        patterns = self.fraud_service.analyze_fraud_patterns(
            self.advertiser,
            days=7
        )
        
        self.assertIn('ip_patterns', patterns)
        self.assertIn('time_patterns', patterns)
        self.assertIn('revenue_patterns', patterns)
        self.assertIn('device_patterns', patterns)
        self.assertEqual(len(patterns['ip_patterns']), 0)
    
    def test_create_fraud_config_success(self):
        """Test successful fraud config creation."""
        config_data = {
            'name': 'Default Fraud Config',
            'description': 'Default fraud detection configuration',
            'auto_block_enabled': True,
            'notification_enabled': True,
            'threshold_score': 0.7,
            'review_required_score': 0.5,
            'is_active': True,
        }
        
        config = self.fraud_service.create_fraud_config(
            self.advertiser,
            config_data
        )
        
        self.assertIsInstance(config, FraudConfig)
        self.assertEqual(config.advertiser, self.advertiser)
        self.assertEqual(config.name, 'Default Fraud Config')
        self.assertTrue(config.auto_block_enabled)
        self.assertTrue(config.notification_enabled)
        self.assertEqual(config.threshold_score, 0.7)
    
    def test_update_fraud_config_success(self):
        """Test successful fraud config update."""
        config_data = {
            'name': 'Default Fraud Config',
            'description': 'Default fraud detection configuration',
            'auto_block_enabled': True,
            'notification_enabled': True,
            'threshold_score': 0.7,
            'review_required_score': 0.5,
            'is_active': True,
        }
        
        config = self.fraud_service.create_fraud_config(
            self.advertiser,
            config_data
        )
        
        # Update config
        update_data = {
            'threshold_score': 0.8,
            'auto_block_enabled': False,
        }
        
        updated_config = self.fraud_service.update_fraud_config(
            config,
            update_data
        )
        
        self.assertEqual(updated_config.threshold_score, 0.8)
        self.assertFalse(updated_config.auto_block_enabled)
    
    def test_get_fraud_statistics_success(self):
        """Test getting fraud statistics."""
        # Create conversions with different fraud scores
        for i in range(20):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('25.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                created_at=timezone.now()
            )
            
            # Set fraud scores
            if i < 5:
                conversion.fraud_score = 0.2
            elif i < 10:
                conversion.fraud_score = 0.5
            elif i < 15:
                conversion.fraud_score = 0.8
                conversion.is_flagged = True
            else:
                conversion.fraud_score = 0.9
                conversion.is_flagged = True
            
            conversion.save()
        
        # Get statistics
        stats = self.fraud_service.get_fraud_statistics(
            self.advertiser,
            days=7
        )
        
        self.assertIn('total_conversions', stats)
        self.assertIn('flagged_conversions', stats)
        self.assertIn('average_fraud_score', stats)
        self.assertIn('high_risk_conversions', stats)
        self.assertIn('flag_rate', stats)
        
        self.assertEqual(stats['total_conversions'], 20)
        self.assertEqual(stats['flagged_conversions'], 10)
        self.assertEqual(stats['flag_rate'], 50.0)
    
    def test_export_fraud_data_success(self):
        """Test exporting fraud data."""
        # Create conversions with fraud data
        for i in range(10):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('25.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                fraud_score=0.6 if i % 2 == 0 else 0.2,
                is_flagged=i % 2 == 0,
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
        
        # Export data
        export_data = self.fraud_service.export_fraud_data(
            self.advertiser,
            days=7
        )
        
        self.assertIn('conversions', export_data)
        self.assertIn('fraud_rules', export_data)
        self.assertIn('statistics', export_data)
        self.assertIn('patterns', export_data)
        self.assertIn('export_date', export_data)
        
        # Check data counts
        self.assertEqual(len(export_data['conversions']), 10)
    
    @patch('api.advertiser_portal.services.fraud.AdvertiserFraudService.send_notification')
    def test_send_fraud_notification(self, mock_send_notification):
        """Test sending fraud notification."""
        # Create conversion
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            fraud_score=0.8,
            is_flagged=True,
            created_at=timezone.now()
        )
        
        # Send notification
        self.fraud_service.send_fraud_notification(
            conversion,
            'high_fraud_score',
            'High fraud score detected',
            {'fraud_score': 0.8, 'risk_factors': ['suspicious_ip']}
        )
        
        mock_send_notification.assert_called_once()
        
        # Check notification data
        call_args = mock_send_notification.call_args
        notification_data = call_args[0][1] if call_args else None
        
        if notification_data:
            self.assertEqual(notification_data['type'], 'high_fraud_score')
            self.assertIn('High fraud score detected', notification_data['message'])
    
    def test_get_fraud_health_status(self):
        """Test getting fraud system health status."""
        # Create conversions with fraud data
        for i in range(20):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('25.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                fraud_score=0.3 + (i * 0.03),
                is_flagged=i > 10,
                created_at=timezone.now()
            )
        
        # Get health status
        health_status = self.fraud_service.get_fraud_health_status(
            self.advertiser,
            days=7
        )
        
        self.assertIn('status', health_status)
        self.assertIn('total_conversions', health_status)
        self.assertIn('flagged_conversions', health_status)
        self.assertIn('average_fraud_score', health_status)
        self.assertIn('rule_effectiveness', health_status)
        self.assertIn('recommendations', health_status)


class ConversionQualityServiceTestCase(TestCase):
    """Test cases for ConversionQualityService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.quality_service = ConversionQualityService()
        
        self.advertiser = self.advertiser_service.create_advertiser(
            self.user, 
            {
                'company_name': 'Test Company',
                'contact_email': 'contact@testcompany.com',
                'contact_phone': '+1234567890',
                'website': 'https://testcompany.com',
                'industry': 'technology',
                'company_size': 'medium',
            }
        )
    
    def test_calculate_conversion_quality_score_success(self):
        """Test successful conversion quality score calculation."""
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            created_at=timezone.now()
        )
        
        quality_score = self.quality_service.calculate_conversion_quality_score(
            conversion
        )
        
        self.assertIsInstance(quality_score, ConversionQualityScore)
        self.assertEqual(quality_score.conversion, conversion)
        self.assertIsInstance(quality_score.score, float)
        self.assertGreaterEqual(quality_score.score, 0.0)
        self.assertLessEqual(quality_score.score, 1.0)
        self.assertIn('factors', quality_score)
    
    def test_calculate_conversion_quality_score_with_data(self):
        """Test quality score calculation with additional data."""
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            created_at=timezone.now()
        )
        
        # Add additional data
        additional_data = {
            'session_duration': 300,  # 5 minutes
            'pages_visited': 5,
            'device_type': 'desktop',
            'country': 'US',
            'time_to_conversion': 120,  # 2 minutes
        }
        
        quality_score = self.quality_service.calculate_conversion_quality_score(
            conversion,
            additional_data
        )
        
        self.assertGreater(quality_score.score, 0.0)
        self.assertIn('session_duration', quality_score.factors)
        self.assertIn('pages_visited', quality_score.factors)
        self.assertIn('time_to_conversion', quality_score.factors)
    
    def test_calculate_conversion_quality_score_low_quality(self):
        """Test quality score calculation for low quality conversion."""
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            created_at=timezone.now()
        )
        
        # Add low quality indicators
        additional_data = {
            'session_duration': 5,  # Very short session
            'pages_visited': 1,  # Only one page
            'device_type': 'mobile',
            'country': 'XX',  # Invalid country
            'time_to_conversion': 1,  # Very fast conversion
            'suspicious_activity': True
        }
        
        quality_score = self.quality_service.calculate_conversion_quality_score(
            conversion,
            additional_data
        )
        
        self.assertLess(quality_score.score, 0.5)  # Should be low quality
        self.assertIn('suspicious_activity', quality_score.factors)
    
    def test_get_conversion_quality_factors_success(self):
        """Test getting conversion quality factors."""
        factors = self.quality_service.get_conversion_quality_factors()
        
        self.assertIn('session_duration', factors)
        self.assertIn('pages_visited', factors)
        self.assertIn('time_to_conversion', factors)
        self.assertIn('device_consistency', factors)
        self.assertIn('geo_consistency', factors)
        self.assertIn('user_agent_consistency', factors)
        self.assertIn('revenue_consistency', factors)
        self.assertIn('conversion_pattern', factors)
    
    def test_analyze_conversion_patterns_success(self):
        """Test successful conversion pattern analysis."""
        # Create conversions with different patterns
        for i in range(20):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('25.00'),
                ip_address=f'192.168.1.{i % 10}',
                user_agent='Mozilla/5.0',
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
            
            # Create quality scores
            quality_score = ConversionQualityScore.objects.create(
                conversion=conversion,
                score=0.8 if i % 4 == 0 else 0.4,
                factors={
                    'session_duration': 300 if i % 4 == 0 else 30,
                    'pages_visited': 5 if i % 4 == 0 else 1
                },
                created_at=timezone.now()
            )
        
        # Analyze patterns
        patterns = self.quality_service.analyze_conversion_patterns(
            self.advertiser,
            days=7
        )
        
        self.assertIn('quality_distribution', patterns)
        self.assertIn('factor_analysis', patterns)
        self.assertIn('time_patterns', patterns)
        self.assertIn('geo_patterns', patterns)
        self.assertIn('device_patterns', patterns)
    
    def test_update_quality_model_success(self):
        """Test successful quality model update."""
        # Create conversions with quality scores
        for i in range(10):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('25.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                created_at=timezone.now()
            )
            
            ConversionQualityScore.objects.create(
                conversion=conversion,
                score=0.7 + (i * 0.02),
                factors={'session_duration': 200 + (i * 10)},
                created_at=timezone.now()
            )
        
        # Update model
        update_result = self.quality_service.update_quality_model(
            self.advertiser,
            days=7
        )
        
        self.assertTrue(update_result.get('success', False))
        self.assertIn('model_version', update_result)
        self.assertIn('accuracy', update_result)
        self.assertIn('samples_used', update_result)
    
    def test_get_quality_statistics_success(self):
        """Test getting quality statistics."""
        # Create conversions with quality scores
        for i in range(20):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('25.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                created_at=timezone.now()
            )
            
            # Mix of quality scores
            score = 0.9 if i < 5 else (0.6 if i < 15 else 0.3)
            ConversionQualityScore.objects.create(
                conversion=conversion,
                score=score,
                factors={'session_duration': 300 if score > 0.7 else 50},
                created_at=timezone.now()
            )
        
        # Get statistics
        stats = self.quality_service.get_quality_statistics(
            self.advertiser,
            days=7
        )
        
        self.assertIn('total_conversions', stats)
        self.assertIn('average_quality_score', stats)
        self.assertIn('high_quality_conversions', stats)
        self.assertIn('low_quality_conversions', stats)
        self.assertIn('quality_distribution', stats)
        
        self.assertEqual(stats['total_conversions'], 20)
        self.assertEqual(stats['high_quality_conversions'], 5)
    
    def test_get_quality_trends_success(self):
        """Test getting quality trends."""
        # Create conversions over time
        for i in range(7):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('25.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                created_at=timezone.now() - timezone.timedelta(days=i)
            )
            
            # Varying quality scores over time
            score = 0.8 - (i * 0.05)  # Decreasing quality over time
            ConversionQualityScore.objects.create(
                conversion=conversion,
                score=score,
                factors={'session_duration': 300 - (i * 20)},
                created_at=timezone.now() - timezone.timedelta(days=i)
            )
        
        # Get trends
        trends = self.quality_service.get_quality_trends(
            self.advertiser,
            days=7
        )
        
        self.assertIn('daily_trends', trends)
        self.assertIn('quality_trend', trends)
        self.assertIn('factor_trends', trends)
        self.assertIn('forecast', trends)
    
    def test_export_quality_data_success(self):
        """Test exporting quality data."""
        # Create conversions with quality scores
        for i in range(10):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('25.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                created_at=timezone.now()
            )
            
            ConversionQualityScore.objects.create(
                conversion=conversion,
                score=0.7 + (i * 0.02),
                factors={'session_duration': 200 + (i * 10)},
                created_at=timezone.now()
            )
        
        # Export data
        export_data = self.quality_service.export_quality_data(
            self.advertiser,
            days=7
        )
        
        self.assertIn('quality_scores', export_data)
        self.assertIn('statistics', export_data)
        self.assertIn('trends', export_data)
        self.assertIn('patterns', export_data)
        self.assertIn('export_date', export_data)
        
        # Check data counts
        self.assertEqual(len(export_data['quality_scores']), 10)
    
    @patch('api.advertiser_portal.services.fraud.ConversionQualityService.send_notification')
    def test_send_quality_notification(self, mock_send_notification):
        """Test sending quality notification."""
        # Create conversion
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            created_at=timezone.now()
        )
        
        # Create quality score
        quality_score = ConversionQualityScore.objects.create(
            conversion=conversion,
            score=0.2,  # Low quality
            factors={'session_duration': 10},
            created_at=timezone.now()
        )
        
        # Send notification
        self.quality_service.send_quality_notification(
            quality_score,
            'low_quality_score',
            'Low quality score detected',
            {'score': 0.2, 'factors': {'session_duration': 10}}
        )
        
        mock_send_notification.assert_called_once()
        
        # Check notification data
        call_args = mock_send_notification.call_args
        notification_data = call_args[0][1] if call_args else None
        
        if notification_data:
            self.assertEqual(notification_data['type'], 'low_quality_score')
            self.assertIn('Low quality score detected', notification_data['message'])


class FraudConfigIntegrationTestCase(TestCase):
    """Test cases for fraud configuration integration."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.fraud_service = AdvertiserFraudService()
        self.quality_service = ConversionQualityService()
        
        self.advertiser = self.advertiser_service.create_advertiser(
            self.user, 
            {
                'company_name': 'Test Company',
                'contact_email': 'contact@testcompany.com',
                'contact_phone': '+1234567890',
                'website': 'https://testcompany.com',
                'industry': 'technology',
                'company_size': 'medium',
            }
        )
    
    def test_fraud_quality_integration(self):
        """Test fraud and quality service integration."""
        # Create conversion
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            created_at=timezone.now()
        )
        
        # Calculate quality score
        quality_score = self.quality_service.calculate_conversion_quality_score(
            conversion,
            {
                'session_duration': 300,
                'pages_visited': 5,
                'device_type': 'desktop',
                'country': 'US',
                'time_to_conversion': 120
            }
        )
        
        # Apply fraud rules
        fraud_result = self.fraud_service.apply_fraud_rules(conversion)
        
        # Check integration
        self.assertIsNotNone(quality_score.score)
        self.assertIsNotNone(fraud_result['fraud_score'])
        
        # Quality score should influence fraud score
        combined_score = (quality_score.score + fraud_result['fraud_score']) / 2
        self.assertGreaterEqual(combined_score, 0.0)
        self.assertLessEqual(combined_score, 1.0)
    
    def test_automated_fraud_blocking(self):
        """Test automated fraud blocking."""
        # Create fraud config
        config_data = {
            'name': 'Strict Fraud Config',
            'description': 'Strict fraud detection configuration',
            'auto_block_enabled': True,
            'notification_enabled': True,
            'threshold_score': 0.7,
            'review_required_score': 0.5,
            'is_active': True,
        }
        
        config = self.fraud_service.create_fraud_config(
            self.advertiser,
            config_data
        )
        
        # Create high fraud rule
        rule_data = {
            'name': 'High Fraud Rule',
            'description': 'Block high fraud conversions',
            'rule_type': 'revenue_anomaly',
            'conditions': {
                'max_revenue': 50.00
            },
            'actions': {
                'flag_conversion': True,
                'block_conversion': True,
                'notify_admin': True
            },
            'severity': 'high',
            'is_active': True,
        }
        
        rule = self.fraud_service.create_fraud_rule(
            self.advertiser,
            rule_data
        )
        
        # Create suspicious conversion
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('1000.00'),  # Suspiciously high
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            created_at=timezone.now()
        )
        
        # Apply rules
        result = self.fraud_service.apply_fraud_rules(conversion)
        
        # Should be flagged and blocked
        self.assertGreater(result['fraud_score'], 0.7)
        self.assertTrue(result['is_flagged'])
        self.assertTrue(result.get('is_blocked', False))
    
    def test_fraud_pattern_learning(self):
        """Test fraud pattern learning."""
        # Create conversions with fraud patterns
        for i in range(20):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('25.00'),
                ip_address=f'192.168.1.{i % 3}',  # 3 IPs repeated
                user_agent='Mozilla/5.0',
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
            
            # Flag conversions from certain IPs
            if i % 3 == 0:
                conversion.is_flagged = True
                conversion.fraud_score = 0.8
                conversion.save()
        
        # Analyze patterns
        patterns = self.fraud_service.analyze_fraud_patterns(
            self.advertiser,
            days=7
        )
        
        # Should detect IP patterns
        self.assertIn('ip_patterns', patterns)
        self.assertGreater(len(patterns['ip_patterns']), 0)
        
        # Generate new rules based on patterns
        new_rules = self.fraud_service.generate_rules_from_patterns(
            self.advertiser,
            patterns
        )
        
        self.assertIsInstance(new_rules, list)
        # Should generate rules for suspicious IPs
    
    def test_quality_based_fraud_adjustment(self):
        """Test fraud score adjustment based on quality."""
        # Create conversion
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            created_at=timezone.now()
        )
        
        # Calculate quality score
        quality_score = self.quality_service.calculate_conversion_quality_score(
            conversion,
            {
                'session_duration': 10,  # Low quality
                'pages_visited': 1,
                'device_type': 'mobile',
                'time_to_conversion': 1
            }
        )
        
        # Apply fraud rules
        fraud_result = self.fraud_service.apply_fraud_rules(conversion)
        
        # Adjust fraud score based on quality
        adjusted_fraud_score = self.fraud_service.adjust_fraud_score_by_quality(
            fraud_result['fraud_score'],
            quality_score.score
        )
        
        # Low quality should increase fraud score
        self.assertGreater(adjusted_fraud_score, fraud_result['fraud_score'])
    
    def test_comprehensive_fraud_analysis(self):
        """Test comprehensive fraud analysis."""
        # Create various conversions
        for i in range(30):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal(str(25.00 + i)),
                ip_address=f'192.168.1.{i % 10}',
                user_agent='Mozilla/5.0',
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
            
            # Apply fraud rules
            fraud_result = self.fraud_service.apply_fraud_rules(conversion)
            
            # Calculate quality score
            quality_score = self.quality_service.calculate_conversion_quality_score(
                conversion,
                {
                    'session_duration': 100 + (i * 10),
                    'pages_visited': 2 + (i % 3),
                    'device_type': 'desktop' if i % 2 == 0 else 'mobile',
                    'time_to_conversion': 60 + (i * 5)
                }
            )
            
            # Update conversion with results
            conversion.fraud_score = fraud_result['fraud_score']
            conversion.is_flagged = fraud_result['is_flagged']
            conversion.save()
        
        # Get comprehensive analysis
        analysis = self.fraud_service.get_comprehensive_fraud_analysis(
            self.advertiser,
            days=7
        )
        
        self.assertIn('fraud_statistics', analysis)
        self.assertIn('quality_statistics', analysis)
        self.assertIn('risk_assessment', analysis)
        self.assertIn('recommendations', analysis)
        self.assertIn('trends', analysis)
