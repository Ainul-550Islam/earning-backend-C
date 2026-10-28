"""
Enhanced VPN Detector Tests
Comprehensive test suite for VPN detection functionality
Author: System Security Team
Version: 2.0.0
"""
from django.test import override_settings

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

from ..vpn_detector import (
    VPNDetector, SimpleVPNDetector, VPNServiceError,
    VPNServiceUnavailableError, with_vpn_check
)
from .factories import UserFactory, IPBlacklistFactory, ThreatIntelligenceFactory
import requests


class VPNDetectorTest(TestCase):
    """Test VPNDetector class"""
    
    def setUp(self):
        self.detector = VPNDetector()
        self.test_ip = '192.168.1.100'
        cache.clear()
    
    def test_vpn_detector_initialization(self):
        """Test VPNDetector initialization"""
        self.assertIsNotNone(self.detector.config)
        self.assertIsNotNone(self.detector.services)
        self.assertIsNotNone(self.detector.stats)
        self.assertEqual(self.detector.cache_prefix, "vpn_detector")
    
    def test_vpn_detector_default_config(self):
        """Test default configuration"""
        self.assertEqual(self.detector.config['cache_timeout'], 3600)
        self.assertEqual(self.detector.config['retry_attempts'], 3)
        self.assertEqual(self.detector.config['threshold_score'], 70)
        self.assertEqual(self.detector.config['rate_limit_per_minute'], 60)
    
    def test_vpn_detector_custom_config(self):
        """Test custom configuration"""
        custom_config = {
            'cache_timeout': 7200,
            'threshold_score': 80,
            'rate_limit_per_minute': 120
        }
        
        detector = VPNDetector(config=custom_config)
        
        self.assertEqual(detector.config['cache_timeout'], 7200)
        self.assertEqual(detector.config['threshold_score'], 80)
        self.assertEqual(detector.config['rate_limit_per_minute'], 120)
    
    def test_validate_ip_address_valid(self):
        """Test valid IP address validation"""
        valid_ips = [
            '192.168.1.1',
            '10.0.0.1',
            '172.16.0.1',
            '8.8.8.8',
            '2001:4860:4860::8888'  # IPv6
        ]
        
        for ip in valid_ips:
            self.assertTrue(self.detector._validate_ip_address(ip))
    
    def test_validate_ip_address_invalid(self):
        """Test invalid IP address validation"""
        invalid_ips = [
            '',
            'invalid_ip',
            '999.999.999.999',
            '192.168.1',
            '192.168.1.1.1'
        ]
        
        for ip in invalid_ips:
            self.assertFalse(self.detector._validate_ip_address(ip))
    
    def test_generate_cache_key(self):
        """Test cache key generation"""
        cache_key = self.detector.generate_cache_key(self.test_ip)
        
        self.assertIn(self.detector.cache_prefix, cache_key)
        self.assertIn(self.test_ip.replace('.', '_'), cache_key)
    
    def test_generate_cache_key_invalid_ip(self):
        """Test cache key generation with invalid IP"""
        cache_key = self.detector.generate_cache_key('invalid_ip')
        
        self.assertIn('invalid_ip', cache_key)
    
    def test_check_rate_limit(self):
        """Test rate limiting functionality"""
        # Reset rate limit
        cache.delete(f"{self.detector.rate_limit_cache_key}:{timezone.now().strftime('%Y%m%d%H%M')}")
        
        # Should allow requests within limit
        for _ in range(60):  # Default limit is 60 per minute
            self.assertTrue(self.detector.check_rate_limit())
        
        # Should block when limit exceeded
        self.assertFalse(self.detector.check_rate_limit())
    
    def test_check_rate_limit_different_minutes(self):
        """Test rate limiting across different minutes"""
        # Should allow requests in new minute
        self.assertTrue(self.detector.check_rate_limit())
        
        # Simulate new minute
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = timezone.now() + timezone.timedelta(minutes=1)
            self.assertTrue(self.detector.check_rate_limit())
    
    def test_safe_request_success(self):
        """Test successful HTTP request"""
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {'vpn': True, 'proxy': False}
            mock_response.raise_for_status.return_value = None
            
            result = self.detector._safe_request(
                'https://api.example.com/test',
                {'User-Agent': 'Test'},
                5.0
            )
            
            self.assertIsNotNone(result)
            self.assertEqual(result['vpn'], True)
            mock_get.assert_called_once()
    
    def test_safe_request_timeout(self):
        """Test HTTP request timeout"""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout("Timeout")
            
            with self.assertRaises(VPNServiceUnavailableError):
                self.detector._safe_request(
                    'https://api.example.com/test',
                    {'User-Agent': 'Test'},
                    5.0
                )
    
    def test_safe_request_retry_logic(self):
        """Test retry logic for failed requests"""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = [
                requests.exceptions.ConnectionError("Connection failed"),
                requests.exceptions.ConnectionError("Connection failed"),
                MagicMock(json=lambda: {'vpn': False}, raise_for_status=lambda: None)
            ]
            
            result = self.detector._safe_request(
                'https://api.example.com/test',
                {'User-Agent': 'Test'},
                5.0
            )
            
            self.assertIsNotNone(result)
            self.assertEqual(result['vpn'], False)
            self.assertEqual(mock_get.call_count, 3)
    
    def test_parse_service_result_ipinfo(self):
        """Test parsing ipinfo.io service result"""
        result = {
            'vpn': True,
            'proxy': False,
            'tor': False,
            'hosting': False,
            'org': 'Test Organization',
            'country': 'US',
            'city': 'New York'
        }
        
        parsed = self.detector._parse_service_result(result, 'ipinfo.io')
        
        self.assertTrue(parsed['is_vpn'])
        self.assertFalse(parsed['is_proxy'])
        self.assertEqual(parsed['service'], 'ipinfo.io')
        self.assertEqual(parsed['confidence'], 90)
        self.assertEqual(parsed['details']['provider'], 'Test Organization')
        self.assertEqual(parsed['details']['country'], 'US')
    
    def test_parse_service_result_vpnapi(self):
        """Test parsing vpnapi.io service result"""
        result = {
            'network': 'Test Network',
            'location': {'country': 'US'},
            'security': {
                'vpn': True,
                'proxy': False,
                'tor': False,
                'score': 0.8
            }
        }
        
        parsed = self.detector._parse_service_result(result, 'vpnapi.io')
        
        self.assertTrue(parsed['is_vpn'])
        self.assertFalse(parsed['is_proxy'])
        self.assertEqual(parsed['service'], 'vpnapi.io')
        self.assertEqual(parsed['confidence'], 80)
        self.assertEqual(parsed['details']['network'], 'Test Network')
    
    def test_parse_service_result_mock(self):
        """Test parsing mock service result"""
        result = {'mock': True}
        
        parsed = self.detector._parse_service_result(result, 'mock')
        
        self.assertFalse(parsed['is_vpn'])
        self.assertFalse(parsed['is_proxy'])
        self.assertEqual(parsed['service'], 'mock')
        self.assertEqual(parsed['confidence'], 0)
        self.assertTrue(parsed['details']['mock'])
    
    def test_parse_service_result_error(self):
        """Test parsing service result with error"""
        result = {'invalid': 'data'}
        
        parsed = self.detector._parse_service_result(result, 'test_service')
        
        self.assertFalse(parsed['is_vpn'])
        self.assertFalse(parsed['is_proxy'])
        self.assertEqual(parsed['service'], 'test_service')
        self.assertEqual(parsed['confidence'], 0)
        self.assertIn('error', parsed)
    
    def test_check_local_patterns_private_ip(self):
        """Test local pattern detection for private IPs"""
        private_ips = [
            '10.0.0.1',
            '172.16.0.1',
            '192.168.1.1'
        ]
        
        for ip in private_ips:
            result = self.detector._check_local_patterns(ip)
            
            self.assertIn('private_ip_range', result['patterns'])
            self.assertGreater(result['confidence'], 0)
    
    def test_check_local_patterns_suspicious_ranges(self):
        """Test local pattern detection for suspicious IP ranges"""
        suspicious_ips = [
            '5.0.0.1',
            '45.0.0.1',
            '46.0.0.1',
            '89.0.0.1',
            '103.0.0.1',
            '104.0.0.1'
        ]
        
        for ip in suspicious_ips:
            result = self.detector._check_local_patterns(ip)
            
            self.assertIn('suspicious_ip_range', result['patterns'])
            self.assertGreater(result['confidence'], 20)
    
    def test_check_local_patterns_known_providers(self):
        """Test local pattern detection for known VPN providers"""
        # This would need custom implementation for provider detection
        # For now, test the basic structure
        result = self.detector._check_local_patterns(self.test_ip)
        
        self.assertIsInstance(result, dict)
        self.assertIn('is_vpn', result)
        self.assertIn('is_proxy', result)
        self.assertIn('confidence', result)
        self.assertIn('patterns', result)
    
    def test_is_vpn_basic_functionality(self):
        """Test basic VPN detection functionality"""
        with patch.object(self.detector, '_check_local_patterns') as mock_local:
            mock_local.return_value = {
                'is_vpn': False,
                'is_proxy': False,
                'confidence': 0,
                'patterns': []
            }
            
            is_vpn, details = self.detector.is_vpn(self.test_ip)
            
            self.assertFalse(is_vpn)
            self.assertFalse(details['is_vpn'])
            self.assertEqual(details['service'], 'local_patterns')
            mock_local.assert_called_once_with(self.test_ip)
    
    def test_is_vpn_invalid_ip(self):
        """Test VPN detection with invalid IP"""
        is_vpn, details = self.detector.is_vpn('invalid_ip')
        
        self.assertFalse(is_vpn)
        self.assertIn('error', details)
    
    def test_is_vpn_rate_limit_exceeded(self):
        """Test VPN detection when rate limited"""
        # Exceed rate limit
        for _ in range(70):  # More than default limit of 60
            self.detector.check_rate_limit()
        
        is_vpn, details = self.detector.is_vpn(self.test_ip)
        
        self.assertFalse(is_vpn)  # Fallback check
        self.assertEqual(details['service'], 'fallback')
        self.assertIn('rate limit', details['note'])
    
    def test_is_vpn_caching(self):
        """Test VPN detection caching"""
        with patch.object(self.detector, '_check_local_patterns') as mock_local:
            mock_local.return_value = {
                'is_vpn': True,
                'is_proxy': True,
                'confidence': 80,
                'patterns': ['test_pattern']
            }
            
            # First call
            is_vpn1, details1 = self.detector.is_vpn(self.test_ip)
            self.assertTrue(is_vpn1)
            self.assertFalse(details1['cached'])
            
            # Second call should use cache
            is_vpn2, details2 = self.detector.is_vpn(self.test_ip)
            self.assertTrue(is_vpn2)
            self.assertTrue(details2['cached'])
            
            # Should only call local patterns once
            mock_local.assert_called_once()
    
    def test_is_vpn_service_integration(self):
        """Test VPN detection with external services"""
        with patch.object(self.detector, '_check_local_patterns') as mock_local:
            with patch.object(self.detector, 'check_ip_with_service') as mock_service:
                # Local patterns return low confidence
                mock_local.return_value = {
                    'is_vpn': False,
                    'is_proxy': False,
                    'confidence': 30,
                    'patterns': []
                }
                
                # Service returns high confidence
                mock_service.return_value = {
                    'is_vpn': True,
                    'is_proxy': True,
                    'confidence': 90,
                    'service': 'test_service'
                }
                
                is_vpn, details = self.detector.is_vpn(self.test_ip)
                
                self.assertTrue(is_vpn)
                self.assertEqual(details['service'], 'test_service')
                self.assertEqual(details['confidence'], 90)
    
    def test_is_vpn_statistics_tracking(self):
        """Test statistics tracking"""
        initial_stats = self.detector.get_statistics()
        initial_checks = initial_stats['total_checks']
        
        self.detector.is_vpn(self.test_ip)
        
        updated_stats = self.detector.get_statistics()
        self.assertEqual(updated_stats['total_checks'], initial_checks + 1)
    
    def test_get_statistics(self):
        """Test statistics retrieval"""
        stats = self.detector.get_statistics()
        
        self.assertIn('total_checks', stats)
        self.assertIn('cache_hits', stats)
        self.assertIn('cache_misses', stats)
        self.assertIn('service_calls', stats)
        self.assertIn('errors', stats)
        self.assertIn('vpn_detections', stats)
        self.assertIn('proxy_detections', stats)
        self.assertIn('cache_prefix', stats)
        self.assertIn('services_configured', stats)
        self.assertIn('config', stats)
        self.assertIn('timestamp', stats)
    
    def test_clear_cache(self):
        """Test cache clearing"""
        result = self.detector.clear_cache()
        
        self.assertTrue(result['success'])
        self.assertIn('Cache clear logged', result['message'])
        self.assertIn('timestamp', result)
    
    def test_fallback_check(self):
        """Test fallback check functionality"""
        is_vpn, details = self.detector._fallback_check(self.test_ip)
        
        self.assertFalse(is_vpn)
        self.assertEqual(details['service'], 'fallback')
        self.assertIn('timestamp', details)
    
    def test_fallback_check_private_network(self):
        """Test fallback check for private network IPs"""
        private_ips = ['192.168.1.1', '10.0.0.1']
        
        for ip in private_ips:
            is_vpn, details = self.detector._fallback_check(ip)
            
            self.assertFalse(is_vpn)
            self.assertIn('private_network', details['patterns'])
            self.assertGreater(details['confidence'], 0)
    
    def test_check_security_models_integration(self):
        """Test security models integration"""
        from .factories import IPBlacklistFactory, ThreatIntelligenceFactory
        
        # Create test data
        blacklist = IPBlacklistFactory(ip_address=self.test_ip)
        threat = ThreatIntelligenceFactory(indicators=[self.test_ip])
        
        with patch('api.security.vpn_detector.SECURITY_MODELS_AVAILABLE', True):
            result = self.detector._check_security_models(self.test_ip)
            
            self.assertIsNotNone(result)
            self.assertEqual(result['service'], 'ip_blacklist')
            self.assertTrue(result['is_vpn'])
            self.assertEqual(result['confidence'], 90)
    
    def test_check_security_models_no_models(self):
        """Test security models check when models unavailable"""
        with patch('api.security.vpn_detector.SECURITY_MODELS_AVAILABLE', False):
            result = self.detector._check_security_models(self.test_ip)
            
            self.assertIsNone(result)
    
    def test_log_vpn_detection_to_security_models(self):
        """Test logging VPN detection to security models"""
        detection_result = {
            'service': 'test_service',
            'confidence': 90,
            'is_proxy': True,
            'is_tor': False,
            'details': {'test': 'data'},
            'patterns': ['test_pattern']
        }
        
        with patch('api.security.vpn_detector.SECURITY_MODELS_AVAILABLE', True):
            with patch('api.security.vpn_detector.SecurityLog.objects.create') as mock_log:
                with patch('api.security.vpn_detector.IPBlacklist.objects.update_or_create') as mock_blacklist:
                    with patch('api.security.vpn_detector.ThreatIntelligence.objects.update_or_create') as mock_threat:
                        
                        self.detector._log_vpn_detection_to_security_models(
                            self.test_ip, detection_result
                        )
                        
                        # Should create security log
                        mock_log.assert_called_once()
                        log_args = mock_log.call_args[1]
                        self.assertEqual(log_args['event_type'], 'vpn_detected')
                        self.assertEqual(log_args['ip_address'], self.test_ip)
                        
                        # Should create/update IP blacklist for high confidence
                        mock_blacklist.assert_called_once()
                        
                        # Should create/update threat intelligence
                        mock_threat.assert_called_once()
    
    def test_log_vpn_detection_no_models(self):
        """Test logging VPN detection when models unavailable"""
        detection_result = {
            'service': 'test_service',
            'confidence': 90
        }
        
        with patch('api.security.vpn_detector.SECURITY_MODELS_AVAILABLE', False):
            # Should not raise error
            self.detector._log_vpn_detection_to_security_models(
                self.test_ip, detection_result
            )


class SimpleVPNDetectorTest(TestCase):
    """Test SimpleVPNDetector class"""
    
    def setUp(self):
        self.detector = SimpleVPNDetector()
        self.test_ip = '192.168.1.100'
    
    def test_simple_vpn_detector_initialization(self):
        """Test SimpleVPNDetector initialization"""
        self.assertIsNotNone(self.detector.cache)
        self.assertEqual(len(self.detector.cache), 0)
    
    def test_simple_vpn_detector_basic_functionality(self):
        """Test basic SimpleVPNDetector functionality"""
        is_vpn, details = self.detector.is_vpn(self.test_ip)
        
        self.assertFalse(is_vpn)
        self.assertFalse(details['is_vpn'])
        self.assertEqual(details['service'], 'simple_detector')
        self.assertIn('checked_at', details)
    
    def test_simple_vpn_detector_no_ip(self):
        """Test SimpleVPNDetector with no IP"""
        is_vpn, details = self.detector.is_vpn('')
        
        self.assertFalse(is_vpn)
        self.assertIn('error', details)
    
    def test_simple_vpn_detector_caching(self):
        """Test SimpleVPNDetector caching"""
        # First call
        is_vpn1, details1 = self.detector.is_vpn(self.test_ip)
        self.assertFalse(is_vpn1)
        
        # Second call should use cache
        is_vpn2, details2 = self.detector.is_vpn(self.test_ip)
        self.assertFalse(is_vpn2)
        
        # Should be in cache
        self.assertIn(self.test_ip, self.detector.cache)
    
    def test_simple_vpn_detector_cache_limit(self):
        """Test SimpleVPNDetector cache size limit"""
        # Fill cache beyond limit
        for i in range(1005):  # Beyond default limit of 1000
            ip = f'192.168.1.{i}'
            self.detector.is_vpn(ip)
        
        # Cache should be limited
        self.assertLessEqual(len(self.detector.cache), 1000)
    
    def test_simple_vpn_detector_error_handling(self):
        """Test SimpleVPNDetector error handling"""
        # Test with invalid IP that might cause errors
        with patch.object(self.detector, 'is_vpn') as mock_is_vpn:
            mock_is_vpn.side_effect = Exception("Test error")
            
            is_vpn, details = self.detector.is_vpn(self.test_ip)
            
            self.assertFalse(is_vpn)
            self.assertIn('error', details)


class VPNDecoratorTest(TestCase):
    """Test VPN detection decorator"""
    
    def setUp(self):
        self.test_ip = '192.168.1.100'
    
    def test_with_vpn_check_decorator(self):
        """Test VPN check decorator"""
        @with_vpn_check()
        def test_function(ip_address=None):
            return "success"
        
        with patch('api.security.vpn_detector.VPNDetector') as mock_detector:
            mock_detector.return_value.is_vpn.return_value = (False, {'is_vpn': False})
            
            result = test_function(ip_address=self.test_ip)
            
            self.assertEqual(result, "success")
            self.assertIn('vpn_info', test_function.__closure__)
            mock_detector.return_value.is_vpn.assert_called_once_with(self.test_ip)
    
    def test_with_vpn_check_decorator_vpn_detected(self):
        """Test VPN check decorator when VPN detected"""
        @with_vpn_check()
        def test_function(ip_address=None):
            return "success"
        
        with patch('api.security.vpn_detector.VPNDetector') as mock_detector:
            mock_detector.return_value.is_vpn.return_value = (True, {'is_vpn': True})
            
            with patch('api.security.vpn_detector.logger') as mock_logger:
                result = test_function(ip_address=self.test_ip)
                
                self.assertEqual(result, "success")
                self.assertTrue(test_function.__closure__)
                mock_logger.warning.assert_called_once()
    
    def test_with_vpn_check_decorator_no_ip(self):
        """Test VPN check decorator without IP address"""
        @with_vpn_check()
        def test_function():
            return "success"
        
        result = test_function()
        
        self.assertEqual(result, "success")
        self.assertIn('vpn_info', test_function.__closure__)
    
    def test_with_vpn_check_decorator_ip_in_args(self):
        """Test VPN check decorator with IP in args"""
        @with_vpn_check()
        def test_function(ip_address):
            return "success"
        
        with patch('api.security.vpn_detector.VPNDetector') as mock_detector:
            mock_detector.return_value.is_vpn.return_value = (False, {'is_vpn': False})
            
            result = test_function(self.test_ip)
            
            self.assertEqual(result, "success")
            mock_detector.return_value.is_vpn.assert_called_once_with(self.test_ip)
    
    def test_with_vpn_check_decorator_error(self):
        """Test VPN check decorator with error"""
        @with_vpn_check(fallback=False)
        def test_function(ip_address=None):
            return "success"
        
        with patch('api.security.vpn_detector.VPNDetector') as mock_detector:
            mock_detector.return_value.is_vpn.side_effect = Exception("Detection error")
            
            with self.assertRaises(Exception):
                test_function(ip_address=self.test_ip)
    
    def test_with_vpn_check_decorator_fallback(self):
        """Test VPN check decorator with fallback"""
        @with_vpn_check(fallback=True)
        def test_function(ip_address=None):
            return "success"
        
        with patch('api.security.vpn_detector.VPNDetector') as mock_detector:
            mock_detector.return_value.is_vpn.side_effect = Exception("Detection error")
            
            result = test_function(ip_address=self.test_ip)
            
            self.assertEqual(result, "success")
            self.assertIn('error', test_function.__closure__)


class VPNDetectorIntegrationTest(TestCase):
    """Integration tests for VPN detector"""
    
    def setUp(self):
        self.detector = VPNDetector()
        self.test_ip = '192.168.1.100'
        cache.clear()
    
    def test_vpn_detector_with_real_service_config(self):
        """Test VPN detector with real service configuration"""
        with override_settings(
            VPN_SERVICES={
                'ipinfo': {
                    'enabled': True,
                    'endpoint': 'https://ipinfo.io',
                    'api_key': 'test_key',
                    'priority': 1,
                    'timeout': 5
                },
                'vpnapi': {
                    'enabled': True,
                    'endpoint': 'https://vpnapi.io',
                    'api_key': 'test_key',
                    'priority': 2,
                    'timeout': 3
                }
            }
        ):
            detector = VPNDetector()
            
            self.assertEqual(len(detector.services), 2)
            self.assertIn('ipinfo', detector.services)
            self.assertIn('vpnapi', detector.services)
            self.assertEqual(detector.services['ipinfo']['priority'], 1)
            self.assertEqual(detector.services['vpnapi']['priority'], 2)
    
    def test_vpn_detector_service_priority(self):
        """Test VPN detector service priority ordering"""
        with override_settings(
            VPN_SERVICES={
                'low_priority': {
                    'enabled': True,
                    'endpoint': 'https://low-priority.com',
                    'priority': 10
                },
                'high_priority': {
                    'enabled': True,
                    'endpoint': 'https://high-priority.com',
                    'priority': 1
                }
            }
        ):
            detector = VPNDetector()
            
            # Services should be ordered by priority
            services_by_priority = sorted(
                detector.services.items(),
                key=lambda x: x[1].get('priority', 1)
            )
            
            self.assertEqual(services_by_priority[0][0], 'high_priority')
            self.assertEqual(services_by_priority[1][0], 'low_priority')
    
    def test_vpn_detector_with_no_services(self):
        """Test VPN detector with no services configured"""
        with override_settings(VPN_SERVICES={}):
            detector = VPNDetector()
            
            # Should have mock service
            self.assertEqual(len(detector.services), 1)
            self.assertIn('mock', detector.services)
            self.assertTrue(detector.services['mock']['enabled'])
    
    def test_vpn_detector_concurrent_requests(self):
        """Test VPN detector with concurrent requests"""
        import threading
        import time
        
        results = []
        errors = []
        
        def check_vpn(ip):
            try:
                is_vpn, details = self.detector.is_vpn(ip)
                results.append((ip, is_vpn, details))
            except Exception as e:
                errors.append((ip, str(e)))
        
        # Create multiple threads checking different IPs
        threads = []
        for i in range(10):
            ip = f'192.168.1.{i + 1}'
            thread = threading.Thread(target=check_vpn, args=(ip,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should have results for all IPs
        self.assertEqual(len(results), 10)
        self.assertEqual(len(errors), 0)
        
        # All results should have required fields
        for ip, is_vpn, details in results:
            self.assertIn('is_vpn', details)
            self.assertIn('is_proxy', details)
            self.assertIn('confidence', details)
            self.assertIn('service', details)
    
    def test_vpn_detector_memory_usage(self):
        """Test VPN detector memory usage"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Make many VPN detection calls
        for i in range(1000):
            ip = f'192.168.1.{i % 255}'
            self.detector.is_vpn(ip)
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 50MB)
        self.assertLess(memory_increase, 50 * 1024 * 1024)
    
    def test_vpn_detector_performance(self):
        """Test VPN detector performance"""
        import time
        
        # Test performance of local pattern checking
        start_time = time.time()
        
        for i in range(1000):
            ip = f'192.168.1.{i % 255}'
            self.detector._check_local_patterns(ip)
        
        local_patterns_time = time.time() - start_time
        
        # Should be fast (less than 1 second for 1000 checks)
        self.assertLess(local_patterns_time, 1.0)
        
        # Test performance of caching
        start_time = time.time()
        
        for i in range(1000):
            ip = f'192.168.1.{i % 255}'
            self.detector.generate_cache_key(ip)
        
        cache_key_time = time.time() - start_time
        
        # Should be very fast (less than 0.1 seconds for 1000 operations)
        self.assertLess(cache_key_time, 0.1)
    
    def test_vpn_detector_error_recovery(self):
        """Test VPN detector error recovery"""
        # Test with various error conditions
        error_conditions = [
            '',  # Empty IP
            'invalid_ip',  # Invalid IP format
            '999.999.999.999',  # Invalid IP range
        ]
        
        for ip in error_conditions:
            is_vpn, details = self.detector.is_vpn(ip)
            
            # Should handle all errors gracefully
            self.assertFalse(is_vpn)
            self.assertIn('error', details)
    
    def test_vpn_detector_configuration_validation(self):
        """Test VPN detector configuration validation"""
        # Test invalid configurations
        invalid_configs = [
            {'cache_timeout': -1},  # Negative timeout
            {'threshold_score': 150},  # Invalid threshold
            {'rate_limit_per_minute': 0},  # Zero rate limit
        ]
        
        for config in invalid_configs:
            detector = VPNDetector(config=config)
            
            # Should use default values for invalid config
            self.assertGreaterEqual(detector.config['cache_timeout'], 0)
            self.assertLessEqual(detector.config['threshold_score'], 100)
            self.assertGreater(detector.config['rate_limit_per_minute'], 0)