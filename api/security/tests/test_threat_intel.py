"""
Enhanced Threat Intelligence Tests
Comprehensive test suite for threat intelligence functionality
Author: System Security Team
Version: 2.0.0
"""
from django.test import override_settings

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from rest_framework.test import APITestCase

from ..services.ThreatIntelService import ThreatIntelService
from .factories import (
    UserFactory, StaffUserFactory, ThreatIntelligenceFactory,
    IPBlacklistFactory, SecurityLogFactory, SecurityIncidentFactory
)


class ThreatIntelServiceTest(TestCase):
    """Test ThreatIntelService class"""
    
    def setUp(self):
        self.service = ThreatIntelService()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        cache.clear()
    
    def test_threat_intel_service_initialization(self):
        """Test ThreatIntelService initialization"""
        self.assertIsNotNone(self.service.cache_prefix)
        self.assertIsNotNone(self.service.default_confidence)
        self.assertIsNotNone(self.service.batch_size)
        self.assertIsNotNone(self.service.feed_configs)
        self.assertIsNotNone(self.service.logger)
    
    def test_threat_intel_service_default_config(self):
        """Test default configuration"""
        self.assertEqual(self.service.default_confidence, 0.5)
        self.assertEqual(self.service.batch_size, 100)
        self.assertEqual(self.service.cache_prefix, "threat_intel")
    
    def test_load_feed_configs_default(self):
        """Test loading default feed configurations"""
        config = self.service._load_feed_configs()
        
        self.assertIn('abuse_ch', config)
        self.assertIn('phishtank', config)
        self.assertIn('internal', config)
        
        # Check default values
        self.assertTrue(config['abuse_ch']['enabled'])
        self.assertEqual(config['abuse_ch']['update_interval'], 3600)
        self.assertEqual(config['abuse_ch']['timeout'], 30)
        self.assertEqual(config['abuse_ch']['retry_attempts'], 3)
    
    def test_load_feed_configs_custom(self):
        """Test loading custom feed configurations"""
        with override_settings(
            THREAT_FEED_CONFIGS={
                'custom_feed': {
                    'enabled': True,
                    'update_interval': 1800,
                    'timeout': 60,
                    'retry_attempts': 5
                }
            }
        ):
            service = ThreatIntelService()
            config = service._load_feed_configs()
            
            self.assertIn('custom_feed', config)
            self.assertEqual(config['custom_feed']['update_interval'], 1800)
            self.assertEqual(config['custom_feed']['timeout'], 60)
            self.assertEqual(config['custom_feed']['retry_attempts'], 5)
    
    def test_load_feed_configs_error(self):
        """Test error handling in feed config loading"""
        with patch('django.conf.settings.THREAT_FEED_CONFIGS', None):
            config = self.service._load_feed_configs()
            
            # Should return empty dict on error
            self.assertEqual(config, {})
    
    def test_check_ip_reputation_cached(self):
        """Test IP reputation check with caching"""
        test_ip = '192.168.1.100'
        cache_key = f"{self.service.cache_prefix}:ip_reputation:{test_ip}"
        
        # Set cache
        cached_result = {
            'ip_address': test_ip,
            'risk_score': 80,
            'is_blacklisted': True,
            'confidence': 0.9,
            'sources': ['test_source']
        }
        cache.set(cache_key, cached_result, 3600)
        
        result = self.service.check_ip_reputation(test_ip)
        
        self.assertEqual(result, cached_result)
        self.assertIn('cached', result)
    
    def test_check_ip_reputation_no_cache(self):
        """Test IP reputation check without cache"""
        test_ip = '192.168.1.100'
        
        with patch.object(self.service, '_check_existing_ip_reputation') as mock_existing:
            with patch.object(self.service, '_check_threat_intelligence_for_ip') as mock_threat:
                with patch.object(self.service, '_merge_reputation_results') as mock_merge:
                    
                    mock_existing.return_value = {'source': 'ip_reputation'}
                    mock_threat.return_value = {'source': 'threat_intel'}
                    mock_merge.return_value = {'merged_result': True}
                    
                    result = self.service.check_ip_reputation(test_ip)
                    
                    self.assertIn('merged_result', result)
                    mock_existing.assert_called_once_with(test_ip)
                    mock_threat.assert_called_once_with(test_ip)
                    mock_merge.assert_called_once()
    
    def test_check_ip_reputation_error(self):
        """Test IP reputation check error handling"""
        test_ip = '192.168.1.100'
        
        with patch.object(self.service, '_check_existing_ip_reputation') as mock_existing:
            mock_existing.side_effect = Exception("Test error")
            
            result = self.service.check_ip_reputation(test_ip)
            
            # Should return safe default on error
            self.assertEqual(result['ip_address'], test_ip)
            self.assertEqual(result['risk_score'], 0)
            self.assertFalse(result['is_blacklisted'])
            self.assertEqual(result['confidence'], 0.0)
            self.assertEqual(result['sources'], [])
            self.assertIn('error', result)
    
    def test_check_existing_ip_reputation_found(self):
        """Test checking existing IP reputation when found"""
        test_ip = '192.168.1.100'
        
        with patch('api.security.models.IPReputation') as mock_model:
            mock_instance = MagicMock()
            mock_instance.fraud_score = 75
            mock_instance.is_blacklisted = True
            mock_instance.country = 'US'
            mock_instance.updated_at = timezone.now()
            mock_model.objects.filter.return_value.first.return_value = mock_instance
            
            result = self.service._check_existing_ip_reputation(test_ip)
            
            self.assertEqual(result['ip_address'], test_ip)
            self.assertEqual(result['fraud_score'], 75)
            self.assertTrue(result['is_blacklisted'])
            self.assertEqual(result['country'], 'US')
            self.assertEqual(result['source'], 'ip_reputation')
            self.assertEqual(result['confidence'], 0.8)
    
    def test_check_existing_ip_reputation_not_found(self):
        """Test checking existing IP reputation when not found"""
        test_ip = '192.168.1.100'
        
        with patch('api.security.models.IPReputation') as mock_model:
            mock_model.objects.filter.return_value.first.return_value = None
            
            result = self.service._check_existing_ip_reputation(test_ip)
            
            self.assertIsNone(result)
    
    def test_check_existing_ip_reputation_import_error(self):
        """Test checking existing IP reputation with import error"""
        test_ip = '192.168.1.100'
        
        with patch('api.security.models.IPReputation') as mock_model:
            mock_model.objects.filter.side_effect = ImportError("No module")
            
            result = self.service._check_existing_ip_reputation(test_ip)
            
            self.assertIsNone(result)
    
    def test_check_threat_intelligence_for_ip_found(self):
        """Test checking threat intelligence for IP when found"""
        test_ip = '192.168.1.100'
        
        with patch('api.security.models.ThreatIntelligence') as mock_model:
            mock_instance = MagicMock()
            mock_instance.severity = 'high'
            mock_instance.threat_type = 'malware'
            mock_instance.confidence = 0.85
            mock_model.objects.filter.return_value.first.return_value = mock_instance
            
            result = self.service._check_threat_intelligence_for_ip(test_ip)
            
            self.assertEqual(result['threat_level'], 'high')
            self.assertEqual(result['threat_type'], 'malware')
            self.assertEqual(result['confidence'], 0.85)
    
    def test_check_threat_intelligence_for_ip_not_found(self):
        """Test checking threat intelligence for IP when not found"""
        test_ip = '192.168.1.100'
        
        with patch('api.security.models.ThreatIntelligence') as mock_model:
            mock_model.objects.filter.return_value.first.return_value = None
            
            result = self.service._check_threat_intelligence_for_ip(test_ip)
            
            self.assertIsNone(result)
    
    def test_merge_reputation_results(self):
        """Test merging reputation results"""
        ip_reputation = {
            'ip_address': '192.168.1.100',
            'fraud_score': 60,
            'is_blacklisted': False,
            'country': 'US',
            'source': 'ip_reputation',
            'confidence': 0.8
        }
        
        threat_intel = {
            'threat_level': 'medium',
            'threat_type': 'botnet',
            'confidence': 0.7
        }
        
        result = self.service._merge_reputation_results(
            ip_reputation, threat_intel, include_details=True
        )
        
        self.assertEqual(result['ip_address'], '192.168.1.100')
        self.assertEqual(result['risk_score'], 60)  # Higher of the two
        self.assertFalse(result['is_blacklisted'])
        self.assertEqual(result['country'], 'US')
        self.assertEqual(result['threat_level'], 'medium')
        self.assertEqual(result['threat_type'], 'botnet')
        self.assertEqual(result['confidence'], 0.8)  # Higher of the two
        self.assertIn('ip_reputation', result['sources'])
        self.assertIn('threat_intelligence', result['sources'])
    
    def test_merge_reputation_results_no_details(self):
        """Test merging reputation results without details"""
        ip_reputation = {'source': 'ip_reputation'}
        threat_intel = {'source': 'threat_intel'}
        
        result = self.service._merge_reputation_results(
            ip_reputation, threat_intel, include_details=False
        )
        
        self.assertNotIn('country', result)
        self.assertNotIn('threat_level', result)
    
    def test_create_threat_intelligence_from_feed(self):
        """Test creating threat intelligence from feed"""
        feed_data = [
            {
                'indicator': '192.168.1.100',
                'type': 'ip',
                'threat_type': 'malware',
                'severity': 'high',
                'confidence': 0.9,
                'source': 'test_feed'
            },
            {
                'indicator': 'malicious-domain.com',
                'type': 'domain',
                'threat_type': 'phishing',
                'severity': 'medium',
                'confidence': 0.7,
                'source': 'test_feed'
            }
        ]
        
        with patch.object(self.service, '_create_threat_intelligence_entry') as mock_create:
            mock_create.return_value = MagicMock()
            
            result = self.service._create_threat_intelligence_from_feed(
                feed_data, 'test_feed'
            )
            
            self.assertEqual(len(result), 2)
            self.assertEqual(mock_create.call_count, 2)
    
    def test_create_threat_intelligence_from_feed_batch(self):
        """Test creating threat intelligence from feed with batching"""
        feed_data = []
        for i in range(150):  # More than default batch size
            feed_data.append({
                'indicator': f'192.168.1.{i % 255}',
                'type': 'ip',
                'threat_type': 'malware',
                'severity': 'high',
                'confidence': 0.9,
                'source': 'test_feed'
            })
        
        with patch.object(self.service, '_create_threat_intelligence_entry') as mock_create:
            mock_create.return_value = MagicMock()
            
            result = self.service._create_threat_intelligence_from_feed(
                feed_data, 'test_feed'
            )
            
            self.assertEqual(len(result), 150)
            # Should be called in batches
            self.assertGreater(mock_create.call_count, 1)
    
    def test_create_threat_intelligence_entry(self):
        """Test creating individual threat intelligence entry"""
        entry_data = {
            'indicator': '192.168.1.100',
            'type': 'ip',
            'threat_type': 'malware',
            'severity': 'high',
            'confidence': 0.9,
            'source': 'test_feed',
            'description': 'Test threat'
        }
        
        with patch('api.security.models.ThreatIntelligence.objects.get_or_create') as mock_get_create:
            mock_instance = MagicMock()
            mock_instance.id = 'test-id'
            mock_get_create.return_value = (mock_instance, True)
            
            result = self.service._create_threat_intelligence_entry(entry_data)
            
            self.assertEqual(result, mock_instance)
            mock_get_create.assert_called_once()
    
    def test_update_threat_intelligence_from_feed(self):
        """Test updating threat intelligence from feed"""
        feed_data = [
            {
                'indicator': '192.168.1.100',
                'type': 'ip',
                'threat_type': 'malware',
                'severity': 'high',
                'confidence': 0.9,
                'source': 'test_feed'
            }
        ]
        
        with patch.object(self.service, '_update_threat_intelligence_entry') as mock_update:
            mock_update.return_value = MagicMock()
            
            result = self.service._update_threat_intelligence_from_feed(
                feed_data, 'test_feed'
            )
            
            self.assertEqual(len(result), 1)
            mock_update.assert_called_once()
    
    def test_update_threat_intelligence_entry(self):
        """Test updating individual threat intelligence entry"""
        entry_data = {
            'indicator': '192.168.1.100',
            'type': 'ip',
            'threat_type': 'malware',
            'severity': 'high',
            'confidence': 0.9,
            'source': 'test_feed'
        }
        
        with patch('api.security.models.ThreatIntelligence.objects.filter') as mock_filter:
            mock_instance = MagicMock()
            mock_instance.id = 'test-id'
            mock_filter.return_value.first.return_value = mock_instance
            
            result = self.service._update_threat_intelligence_entry(entry_data)
            
            self.assertEqual(result, mock_instance)
            mock_instance.save.assert_called_once()
    
    def test_update_threat_intelligence_entry_not_found(self):
        """Test updating threat intelligence entry when not found"""
        entry_data = {
            'indicator': '192.168.1.100',
            'type': 'ip',
            'threat_type': 'malware',
            'severity': 'high',
            'confidence': 0.9,
            'source': 'test_feed'
        }
        
        with patch('api.security.models.ThreatIntelligence.objects.filter') as mock_filter:
            mock_filter.return_value.first.return_value = None
            
            result = self.service._update_threat_intelligence_entry(entry_data)
            
            self.assertIsNone(result)
    
    def test_process_threat_feed_abuse_ch(self):
        """Test processing abuse.ch threat feed"""
        mock_response_data = [
            {
                'ipAddress': '192.168.1.100',
                'isTor': False,
                'malicious': True,
                'abuseConfidence': 95
            },
            {
                'ipAddress': '192.168.1.101',
                'isTor': True,
                'malicious': False,
                'abuseConfidence': 80
            }
        ]
        
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            with patch.object(self.service, '_create_threat_intelligence_from_feed') as mock_create:
                mock_create.return_value = []
                
                result = self.service._process_threat_feed('abuse_ch')
                
                self.assertEqual(len(result), 2)
                mock_get.assert_called_once()
                mock_create.assert_called_once()
    
    def test_process_threat_feed_phishtank(self):
        """Test processing phishtank threat feed"""
        mock_response_data = [
            {
                'url': 'http://malicious-site.com',
                'phish_detail_url': 'http://phishtank.com/details/test',
                'submission_time': '2023-01-01T00:00:00Z'
            }
        ]
        
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            with patch.object(self.service, '_create_threat_intelligence_from_feed') as mock_create:
                mock_create.return_value = []
                
                result = self.service._process_threat_feed('phishtank')
                
                self.assertEqual(len(result), 1)
                mock_get.assert_called_once()
                mock_create.assert_called_once()
    
    def test_process_threat_feed_internal(self):
        """Test processing internal threat feed"""
        internal_data = [
            {
                'indicator': '192.168.1.100',
                'type': 'ip',
                'threat_type': 'malware',
                'severity': 'high',
                'confidence': 0.9,
                'source': 'internal'
            }
        ]
        
        with patch.object(self.service, '_create_threat_intelligence_from_feed') as mock_create:
            mock_create.return_value = []
            
            result = self.service._process_threat_feed('internal')
            
            self.assertEqual(len(result), 1)
            mock_create.assert_called_once()
    
    def test_process_threat_feed_error(self):
        """Test processing threat feed with error"""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            result = self.service._process_threat_feed('abuse_ch')
            
            self.assertEqual(result, [])
    
    def test_process_all_feeds(self):
        """Test processing all configured feeds"""
        with patch.object(self.service, '_process_threat_feed') as mock_process:
            mock_process.return_value = []
            
            result = self.service._process_all_feeds()
            
            # Should process all configured feeds
            expected_feeds = ['abuse_ch', 'phishtank', 'internal']
            self.assertEqual(mock_process.call_count, len(expected_feeds))
            
            for feed in expected_feeds:
                mock_process.assert_any_call(feed)
    
    def test_get_threat_intelligence_stats(self):
        """Test getting threat intelligence statistics"""
        with patch('api.security.models.ThreatIntelligence.objects') as mock_model:
            mock_model.objects.count.return_value = 100
            mock_model.objects.filter.return_value.count.return_value = 25
            
            result = self.service._get_threat_intelligence_stats()
            
            self.assertEqual(result['total_indicators'], 100)
            self.assertEqual(result['active_indicators'], 25)
            self.assertIn('timestamp', result)
    
    def test_cleanup_expired_threat_intelligence(self):
        """Test cleaning up expired threat intelligence"""
        with patch('api.security.models.ThreatIntelligence.objects') as mock_model:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 10
            mock_queryset.delete.return_value = (10, {'api.security.ThreatIntelligence': 10})
            mock_model.objects.filter.return_value = mock_queryset
            
            result = self.service._cleanup_expired_threat_intelligence()
            
            self.assertEqual(result['deleted_count'], 10)
            mock_model.objects.filter.assert_called_once()
    
    def test_export_threat_intelligence(self):
        """Test exporting threat intelligence data"""
        with patch('api.security.models.ThreatIntelligence.objects') as mock_model:
            mock_queryset = MagicMock()
            mock_queryset.values_list.return_value = [
                ('192.168.1.100', 'ip', 'malware', 'high'),
                ('malicious-site.com', 'domain', 'phishing', 'medium')
            ]
            mock_model.objects.filter.return_value = mock_queryset
            
            result = self.service._export_threat_intelligence()
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0][0], '192.168.1.100')
            self.assertEqual(result[0][1], 'ip')
            self.assertEqual(result[1][0], 'malicious-site.com')
            self.assertEqual(result[1][1], 'domain')
    
    def test_import_threat_intelligence(self):
        """Test importing threat intelligence data"""
        import_data = [
            {
                'indicator': '192.168.1.100',
                'type': 'ip',
                'threat_type': 'malware',
                'severity': 'high',
                'confidence': 0.9,
                'source': 'import'
            }
        ]
        
        with patch.object(self.service, '_create_threat_intelligence_from_feed') as mock_create:
            mock_create.return_value = []
            
            result = self.service._import_threat_intelligence(import_data)
            
            self.assertEqual(len(result), 1)
            mock_create.assert_called_once()
    
    def test_validate_threat_data(self):
        """Test threat data validation"""
        valid_data = {
            'indicator': '192.168.1.100',
            'type': 'ip',
            'threat_type': 'malware',
            'severity': 'high',
            'confidence': 0.9,
            'source': 'test'
        }
        
        result = self.service._validate_threat_data(valid_data)
        
        self.assertTrue(result['valid'])
        self.assertNotIn('errors', result)
    
    def test_validate_threat_data_invalid(self):
        """Test threat data validation with invalid data"""
        invalid_data = {
            'indicator': '',  # Empty indicator
            'type': 'invalid_type',
            'threat_type': '',
            'severity': 'invalid_severity',
            'confidence': 1.5,  # Invalid confidence
            'source': ''
        }
        
        result = self.service._validate_threat_data(invalid_data)
        
        self.assertFalse(result['valid'])
        self.assertIn('errors', result)
        self.assertGreater(len(result['errors']), 0)
    
    def test_get_feed_status(self):
        """Test getting feed status"""
        with patch.object(self.service, '_check_feed_health') as mock_health:
            mock_health.return_value = {
                'abuse_ch': {'status': 'healthy', 'last_update': timezone.now()},
                'phishtank': {'status': 'healthy', 'last_update': timezone.now()},
                'internal': {'status': 'healthy', 'last_update': timezone.now()}
            }
            
            result = self.service._get_feed_status()
            
            self.assertIn('abuse_ch', result)
            self.assertIn('phishtank', result)
            self.assertIn('internal', result)
            self.assertEqual(result['abuse_ch']['status'], 'healthy')
    
    def test_check_feed_health(self):
        """Test checking feed health"""
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = self.service._check_feed_health('abuse_ch')
            
            self.assertEqual(result['status'], 'healthy')
            self.assertIn('last_check', result)
    
    def test_check_feed_health_error(self):
        """Test checking feed health with error"""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            result = self.service._check_feed_health('abuse_ch')
            
            self.assertEqual(result['status'], 'error')
            self.assertIn('error', result)
    
    def test_schedule_feed_updates(self):
        """Test scheduling feed updates"""
        with patch.object(self.service, '_process_all_feeds') as mock_process:
            mock_process.return_value = []
            
            result = self.service._schedule_feed_updates()
            
            self.assertIn('updated_feeds', result)
            self.assertIn('timestamp', result)
            mock_process.assert_called_once()


class ThreatIntelServiceIntegrationTest(TestCase):
    """Integration tests for ThreatIntelService"""
    
    def setUp(self):
        self.service = ThreatIntelService()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        cache.clear()
    
    def test_threat_intelligence_workflow(self):
        """Test complete threat intelligence workflow"""
        # Create threat intelligence
        threat = ThreatIntelligenceFactory(
            indicators=['192.168.1.100'],
            indicator_type='ip',
            threat_type='malware',
            severity='high',
            confidence=0.9
        )
        
        # Check IP reputation
        result = self.service.check_ip_reputation('192.168.1.100')
        
        self.assertIsNotNone(result)
        self.assertGreater(result['risk_score'], 0)
        self.assertIn('threat_intelligence', result.get('sources', []))
    
    def test_threat_intelligence_with_ip_blacklist(self):
        """Test threat intelligence integration with IP blacklist"""
        # Create threat intelligence
        threat = ThreatIntelligenceFactory(
            indicators=['192.168.1.100'],
            indicator_type='ip',
            threat_type='malware',
            severity='high',
            confidence=0.9
        )
        
        # Create IP blacklist
        blacklist = IPBlacklistFactory(
            ip_address='192.168.1.100',
            blacklist_type='threat_intelligence'
        )
        
        # Check IP reputation
        result = self.service.check_ip_reputation('192.168.1.100')
        
        self.assertTrue(result.get('is_blacklisted', False))
        self.assertGreater(result['risk_score'], 0)
    
    def test_threat_intelligence_with_security_logs(self):
        """Test threat intelligence integration with security logs"""
        # Create threat intelligence
        threat = ThreatIntelligenceFactory(
            indicators=['192.168.1.100'],
            indicator_type='ip',
            threat_type='malware',
            severity='high',
            confidence=0.9
        )
        
        # Create security log for threat IP
        security_log = SecurityLogFactory(
            ip_address='192.168.1.100',
            event_type='threat_detected',
            severity='warning'
        )
        
        # Check IP reputation
        result = self.service.check_ip_reputation('192.168.1.100')
        
        self.assertGreater(result['risk_score'], 0)
    
    def test_threat_intelligence_with_security_incidents(self):
        """Test threat intelligence integration with security incidents"""
        # Create threat intelligence
        threat = ThreatIntelligenceFactory(
            indicators=['192.168.1.100'],
            indicator_type='ip',
            threat_type='malware',
            severity='high',
            confidence=0.9
        )
        
        # Create security incident
        incident = SecurityIncidentFactory(
            incident_type='threat_detected',
            severity='high',
            evidence={'ip_addresses': ['192.168.1.100']}
        )
        
        # Check IP reputation
        result = self.service.check_ip_reputation('192.168.1.100')
        
        self.assertGreater(result['risk_score'], 0)
    
    def test_threat_intelligence_batch_processing(self):
        """Test batch processing of threat intelligence"""
        # Create multiple threat intelligence entries
        threats = ThreatIntelligenceFactory.create_batch(
            10,
            indicator_type='ip',
            threat_type='malware',
            severity='high',
            confidence=0.9
        )
        
        # Check all IPs
        ip_results = []
        for threat in threats:
            for indicator in threat.indicators:
                result = self.service.check_ip_reputation(indicator)
                ip_results.append(result)
        
        self.assertEqual(len(ip_results), 10)
        for result in ip_results:
            self.assertGreater(result['risk_score'], 0)
    
    def test_threat_intelligence_caching(self):
        """Test caching in threat intelligence checks"""
        test_ip = '192.168.1.100'
        
        # Create threat intelligence
        threat = ThreatIntelligenceFactory(
            indicators=[test_ip],
            indicator_type='ip',
            threat_type='malware',
            severity='high',
            confidence=0.9
        )
        
        # First check
        result1 = self.service.check_ip_reputation(test_ip)
        self.assertFalse(result1.get('cached', False))
        
        # Second check should use cache
        result2 = self.service.check_ip_reputation(test_ip)
        self.assertTrue(result2.get('cached', False))
        
        # Results should be the same
        self.assertEqual(result1['risk_score'], result2['risk_score'])
    
    def test_threat_intelligence_error_handling(self):
        """Test error handling in threat intelligence"""
        # Test with non-existent IP
        result = self.service.check_ip_reputation('999.999.999.999')
        
        # Should handle gracefully
        self.assertEqual(result['ip_address'], '999.999.999.999')
        self.assertEqual(result['risk_score'], 0)
        self.assertFalse(result['is_blacklisted'])
    
    def test_threat_intelligence_performance(self):
        """Test performance of threat intelligence checks"""
        import time
        
        # Create threat intelligence
        threat = ThreatIntelligenceFactory(
            indicators=['192.168.1.100'],
            indicator_type='ip',
            threat_type='malware',
            severity='high',
            confidence=0.9
        )
        
        # Measure performance
        start_time = time.time()
        
        for _ in range(100):
            self.service.check_ip_reputation('192.168.1.100')
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should be fast (less than 1 second for 100 checks)
        self.assertLess(duration, 1.0)
    
    def test_threat_intelligence_concurrent_access(self):
        """Test concurrent access to threat intelligence"""
        import threading
        import time
        
        # Create threat intelligence
        threat = ThreatIntelligenceFactory(
            indicators=['192.168.1.100'],
            indicator_type='ip',
            threat_type='malware',
            severity='high',
            confidence=0.9
        )
        
        results = []
        errors = []
        
        def check_ip():
            try:
                result = self.service.check_ip_reputation('192.168.1.100')
                results.append(result)
            except Exception as e:
                errors.append(str(e))
        
        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=check_ip)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should handle concurrent access gracefully
        self.assertEqual(len(results), 10)
        self.assertEqual(len(errors), 0)
        
        # All results should be consistent
        first_result = results[0]
        for result in results[1:]:
            self.assertEqual(result['risk_score'], first_result['risk_score'])
    
    def test_threat_intelligence_memory_usage(self):
        """Test memory usage of threat intelligence"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create many threat intelligence entries
        threats = ThreatIntelligenceFactory.create_batch(
            1000,
            indicator_type='ip',
            threat_type='malware',
            severity='high',
            confidence=0.9
        )
        
        # Check all IPs
        for threat in threats:
            for indicator in threat.indicators[:1]:  # Check one per threat
                self.service.check_ip_reputation(indicator)
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB)
        self.assertLess(memory_increase, 100 * 1024 * 1024)
    
    def test_threat_intelligence_configuration_validation(self):
        """Test configuration validation"""
        # Test with invalid configuration
        with override_settings(
            THREAT_FEED_CONFIGS={
                'invalid_feed': {
                    'enabled': True,
                    'update_interval': -1,  # Invalid
                    'timeout': 0,  # Invalid
                    'retry_attempts': -1  # Invalid
                }
            }
        ):
            service = ThreatIntelService()
            config = service._load_feed_configs()
            
            # Should handle invalid values gracefully
            self.assertIn('invalid_feed', config)
            self.assertTrue(config['invalid_feed']['enabled'])
    
    def test_threat_intelligence_data_integrity(self):
        """Test data integrity in threat intelligence"""
        # Create threat intelligence
        threat = ThreatIntelligenceFactory(
            indicators=['192.168.1.100'],
            indicator_type='ip',
            threat_type='malware',
            severity='high',
            confidence=0.9
        )
        
        # Verify data integrity
        self.assertEqual(len(threat.indicators), 1)
        self.assertEqual(threat.indicators[0], '192.168.1.100')
        self.assertEqual(threat.indicator_type, 'ip')
        self.assertEqual(threat.threat_type, 'malware')
        self.assertEqual(threat.severity, 'high')
        self.assertEqual(threat.confidence, 0.9)
        self.assertTrue(threat.is_active)
        
        # Check IP reputation
        result = self.service.check_ip_reputation('192.168.1.100')
        
        # Data should be consistent
        self.assertGreater(result['risk_score'], 0)
        self.assertIn('threat_intelligence', result.get('sources', []))
    
    def test_threat_intelligence_expiration(self):
        """Test threat intelligence expiration"""
        # Create expired threat intelligence
        expired_threat = ThreatIntelligenceFactory(
            indicators=['192.168.1.100'],
            indicator_type='ip',
            threat_type='malware',
            severity='high',
            confidence=0.9,
            expires_at=timezone.now() - timezone.timedelta(days=1)
        )
        
        # Create active threat intelligence
        active_threat = ThreatIntelligenceFactory(
            indicators=['192.168.1.101'],
            indicator_type='ip',
            threat_type='malware',
            severity='high',
            confidence=0.9,
            expires_at=timezone.now() + timezone.timedelta(days=1)
        )
        
        # Check expired IP
        result_expired = self.service.check_ip_reputation('192.168.1.100')
        self.assertEqual(result_expired['risk_score'], 0)
        
        # Check active IP
        result_active = self.service.check_ip_reputation('192.168.1.101')
        self.assertGreater(result_active['risk_score'], 0)