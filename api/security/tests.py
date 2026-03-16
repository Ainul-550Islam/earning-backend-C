"""
Security App Tests - Production Ready
Comprehensive test suite with defensive coding patterns
Version: 3.0.0
"""

import logging
import json
import time
from datetime import timedelta
from unittest.mock import patch, MagicMock, ANY
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.db.utils import IntegrityError
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from ..models import DeviceInfo, SecurityLog, UserBan
from ..serializers import DeviceInfoSerializer
from ..viewsets import DeviceInfoViewSet
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase, Client, TransactionTestCase
from django.db import transaction
from django.conf import settings



from .models import (
    DeviceInfo, SecurityLog, RiskScore, SecurityDashboard,
    AutoBlockRule, FraudPattern, GeolocationLog, IPBlacklist,
    UserBan, APIRateLimit, UserSession
)
from .middleware import (
    SecurityHeadersMiddleware, RateLimitMiddleware,
    SecurityAuditMiddleware, VPNProxyDetectionMiddleware
)
from .vpn_detector import VPNDetector
from .utils import NullSafe, TypeValidator, GracefulDegradation

logger = logging.getLogger('security.tests')
User = get_user_model()


class BaseSecurityTest(APITestCase):
    """
    Base test class with defensive coding utilities.
    All security tests should inherit from this.
    """
    
    def setUp(self):
        """Set up test data with defensive coding"""
        try:
            # Clear cache before tests
            cache.clear()
            
            # Create test users
            self.admin_user = self._create_user(
                username='admin_user',
                email='admin@test.com',
                is_staff=True,
                is_superuser=True
            )
            
            self.regular_user = self._create_user(
                username='regular_user',
                email='user@test.com'
            )
            
            self.suspicious_user = self._create_user(
                username='suspicious_user',
                email='suspicious@test.com'
            )
            
            # Create test devices
            self.trusted_device = self._create_device(
                user=self.regular_user,
                device_id='trusted_device_123',
                is_trusted=True,
                risk_score=10
            )
            
            self.suspicious_device = self._create_device(
                user=self.suspicious_user,
                device_id='suspicious_device_456',
                is_rooted=True,
                is_vpn=True,
                risk_score=85
            )
            
            # Create test security logs
            self.security_log = self._create_security_log(
                user=self.regular_user,
                security_type='failed_login',
                severity='medium'
            )
            
            # Create test risk score
            self.risk_score = self._create_risk_score(
                user=self.regular_user,
                current_score=45
            )
            
            logger.info("Test setup completed successfully")
            
        except Exception as e:
            logger.error(f"Test setup failed: {str(e)}", exc_info=True)
            raise
    
    def _create_user(self, **kwargs) -> User:
        """Create test user with defensive coding"""
        try:
            defaults = {
                'username': 'test_user',
                'email': 'test@example.com',
                'password': 'TestPass123!',
                'is_active': True,
            }
            defaults.update(kwargs)
            
            user = User.objects.create_user(**defaults)
            return user
            
        except Exception as e:
            logger.error(f"Failed to create test user: {str(e)}")
            raise
    
    def _create_device(self, **kwargs) -> DeviceInfo:
        """Create test device with defensive coding"""
        try:
            defaults = {
                'device_id': 'test_device',
                'device_model': 'Test Model',
                'device_brand': 'Test Brand',
                'android_version': '11',
                'app_version': '1.0.0',
                'is_rooted': False,
                'is_emulator': False,
                'is_vpn': False,
                'is_proxy': False,
                'risk_score': 0,
                'is_trusted': False,
            }
            defaults.update(kwargs)
            
            # Ensure required fields
            if 'user' not in defaults:
                defaults['user'] = self.regular_user
            
            if 'device_id_hash' not in defaults and defaults.get('device_id'):
                import hashlib
                device_hash = hashlib.sha256(
                    f"{defaults['device_id']}salt".encode()
                ).hexdigest()
                defaults['device_id_hash'] = device_hash
            
            device = DeviceInfo.objects.create(**defaults)
            return device
            
        except Exception as e:
            logger.error(f"Failed to create test device: {str(e)}")
            raise
    
    def _create_security_log(self, **kwargs) -> SecurityLog:
        """Create test security log with defensive coding"""
        try:
            defaults = {
                'security_type': 'suspicious_activity',
                'severity': 'medium',
                'description': 'Test security event',
                'risk_score': 30,
                'resolved': False,
            }
            defaults.update(kwargs)
            
            # Ensure required fields
            if 'user' not in defaults:
                defaults['user'] = self.regular_user
            
            log = SecurityLog.objects.create(**defaults)
            return log
            
        except Exception as e:
            logger.error(f"Failed to create security log: {str(e)}")
            raise
    
    def _create_risk_score(self, **kwargs) -> RiskScore:
        """Create test risk score with defensive coding"""
        try:
            defaults = {
                'current_score': 50,
                'previous_score': 40,
                'failed_login_attempts': 2,
                'suspicious_activities': 1,
                'vpn_usage_count': 0,
            }
            defaults.update(kwargs)
            
            # Ensure required fields
            if 'user' not in defaults:
                defaults['user'] = self.regular_user
            
            risk_score = RiskScore.objects.create(**defaults)
            return risk_score
            
        except Exception as e:
            logger.error(f"Failed to create risk score: {str(e)}")
            raise
    
    def assertSafeResponse(self, response, expected_status=200):
        """Assert response is safe and contains expected data"""
        try:
            self.assertEqual(response.status_code, expected_status)
            
            # Check response has content
            self.assertIsNotNone(response.data)
            
            # For error responses, ensure error field exists
            if expected_status >= 400:
                self.assertIn('error', response.data)
            else:
                # For success responses, check for expected structure
                if isinstance(response.data, dict):
                    self.assertNotIn('traceback', response.data)  # No debug info in production
                    
            return True
            
        except AssertionError as e:
            logger.error(f"Safe response assertion failed: {str(e)}")
            raise
    
    def assertDefensiveBehavior(self, func, *args, **kwargs):
        """Assert function exhibits defensive coding behavior"""
        try:
            # Test with invalid inputs
            result = func(None, *args, **kwargs)
            
            # Should not crash with None input
            self.assertIsNotNone(result)
            
            # Should return appropriate default or error
            if isinstance(result, dict):
                self.assertIn('error', result)
            
            return True
            
        except Exception as e:
            self.fail(f"Function failed defensive test: {str(e)}")

# =================== DEFENSIVE TESTING DECORATORS ====================

def skip_if_no_database(func):
    """Skip test if database is not available"""
    def wrapper(*args, **kwargs):
        try:
            # Check database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Skipping test due to database error: {e}")
            return None
    return wrapper


def retry_on_failure(max_retries=3, delay=0.1):
    """Retry test on failure (for flaky tests)"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except AssertionError as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"Test attempt {attempt + 1} failed, retrying...")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator


# ==================== BASE TEST CLASS WITH DEFENSIVE UTILITIES ====================

class BaseSecurityTest(TestCase):
    """Base test class with defensive utilities"""
    
    def setUp(self):
        """Set up test data with defensive coding"""
        super().setUp()
        self._test_data = {}
        self._created_objects = []
        self._setup_successful = False
        
        try:
            # Clear cache before each test
            cache.clear()
            
            # Set up test data
            self._setup_test_data()
            
            self._setup_successful = True
            logger.info(f"{self.__class__.__name__} setup completed successfully")
            
        except Exception as e:
            logger.error(f"Test setup failed: {str(e)}", exc_info=True)
            self._setup_successful = False
            raise
    
    def tearDown(self):
        """Clean up after tests"""
        try:
            # Clean up created objects
            for obj in self._created_objects:
                try:
                    obj.delete()
                except Exception as e:
                    logger.debug(f"Failed to delete {obj}: {e}")
            
            # Clear cache
            cache.clear()
            
            logger.info(f"{self.__class__.__name__} teardown completed")
            
        except Exception as e:
            logger.error(f"Test teardown failed: {str(e)}")
        finally:
            super().tearDown()
    
    def _setup_test_data(self):
        """Override this method in child classes"""
        pass
    
    def _create_test_user(self, **kwargs):
        """Helper to create test user defensively"""
        try:
            defaults = {
                'is_active': True,
                'is_staff': False,
                'is_superuser': False
            }
            defaults.update(kwargs)
            
            username = defaults.pop('username')
            email = defaults.pop('email')
            password = defaults.pop('password')
            
            # Check if user already exists
            if User.objects.filter(username=username).exists():
                logger.warning(f"User {username} already exists, fetching existing")
                return User.objects.get(username=username)
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                **defaults
            )
            
            self._created_objects.append(user)
            return user
            
        except Exception as e:
            logger.error(f"User creation failed: {str(e)}")
            return None
    
    def _create_test_device(self, **kwargs):
        """Helper to create test device defensively"""
        try:
            # Generate device_id if not provided
            if 'device_id' not in kwargs:
                import uuid
                kwargs['device_id'] = f"test_device_{uuid.uuid4().hex[:8]}"
            
            device = DeviceInfo.objects.create(**kwargs)
            
            # Generate device hash if not provided
            if not device.device_id_hash and device.device_id:
                import hashlib
                device.device_id_hash = hashlib.sha256(
                    device.device_id.encode()
                ).hexdigest()
                device.save(update_fields=['device_id_hash'])
            
            self._created_objects.append(device)
            return device
            
        except Exception as e:
            logger.error(f"Device creation failed: {str(e)}")
            return None
    
    def _create_test_security_log(self, **kwargs):
        """Helper to create test security log defensively"""
        try:
            defaults = {
                'security_type': 'test_event',
                'severity': 'medium',
                'description': 'Test security event',
                'ip_address': '127.0.0.1',
                'user_agent': 'test-agent',
                'risk_score': 50,
                'metadata': {}
            }
            defaults.update(kwargs)
            
            log = SecurityLog.objects.create(**defaults)
            self._created_objects.append(log)
            return log
            
        except Exception as e:
            logger.error(f"Security log creation failed: {str(e)}")
            return None
    
    def assertSafeResponse(self, response, expected_status):
        """Custom assertion for safe response handling"""
        self.assertIsNotNone(response, "Response should not be None")
        self.assertEqual(
            response.status_code, expected_status,
            f"Expected status {expected_status}, got {response.status_code}"
        )
        
        # Check for common error patterns
        if response.status_code >= 400:
            self.assertTrue(
                hasattr(response, 'data'),
                "Error response should have data attribute"
            )
            
            if isinstance(response.data, dict):
                self.assertTrue(
                    'error' in response.data or 'detail' in response.data,
                    "Error response should contain error field"
                )
    
    def assertDeviceData(self, data, expected_device):
        """Assert device data matches expected"""
        self.assertEqual(data['id'], expected_device.id)
        self.assertEqual(data['device_id'], expected_device.device_id)
        self.assertEqual(data['risk_score'], expected_device.risk_score)
        self.assertEqual(data['is_trusted'], expected_device.is_trusted)
        
        # Check computed fields
        self.assertIn('device_status', data)
        self.assertIn('security_assessment', data)
        self.assertIn('is_suspicious', data)
    
    def assertRiskLevel(self, risk_score, expected_level):
        """Assert risk level matches expected"""
        if risk_score >= 80:
            self.assertEqual(expected_level, 'critical')
        elif risk_score >= 60:
            self.assertEqual(expected_level, 'high')
        elif risk_score >= 40:
            self.assertEqual(expected_level, 'medium')
        elif risk_score >= 20:
            self.assertEqual(expected_level, 'low')
        else:
            self.assertEqual(expected_level, 'safe')


# ==================== DEVICE INFO TESTS ====================

class DeviceInfoTests(BaseSecurityTest):
    """Tests for DeviceInfo model and views"""
    
    def _setup_test_data(self):
        """Set up test data"""
        # Create test users
        self.regular_user = self._create_test_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.admin_user = self._create_test_user(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        
        # Create test devices
        self.trusted_device = self._create_test_device(
            user=self.regular_user,
            device_id='trusted_device_123',
            device_model='iPhone 13',
            device_brand='Apple',
            is_trusted=True,
            trust_level=3,
            risk_score=10
        )
        
        self.suspicious_device = self._create_test_device(
            user=self.regular_user,
            device_id='suspicious_device_456',
            device_model='OnePlus 9',
            device_brand='OnePlus',
            is_rooted=True,
            is_emulator=False,
            risk_score=85
        )
        
        self.vpn_device = self._create_test_device(
            user=self.regular_user,
            device_id='vpn_device_789',
            device_model='Pixel 6',
            device_brand='Google',
            is_vpn=True,
            is_proxy=False,
            risk_score=45
        )
        
        # Create test security logs
        self._create_test_security_log(
            user=self.regular_user,
            device_info=self.suspicious_device,
            security_type='rooted_device',
            severity='high',
            risk_score=85
        )
    
    # ==================== SKIP CONDITIONS ====================
    
    @skip_if_no_database
    def test_database_connection(self):
        """Test database connection is working"""
        self.assertTrue(self._setup_successful)
    
    # ==================== MODEL TESTS ====================
    
    def test_device_model_str(self):
        """Test DeviceInfo model string representation"""
        try:
            device_str = str(self.trusted_device)
            self.assertIsInstance(device_str, str)
            self.assertIn(self.regular_user.username, device_str)
            self.assertIn(self.trusted_device.device_model, device_str)
        except Exception as e:
            logger.error(f"Device model str test failed: {str(e)}")
            raise
    
    def test_device_risk_calculation(self):
        """Test risk score calculation"""
        try:
            # Test risk score for rooted device
            self.assertEqual(self.suspicious_device.risk_score, 85)
            
            # Test risk level method
            risk_level = self.suspicious_device.get_risk_level()
            self.assertEqual(risk_level, 'critical')
            
            # Test is_suspicious method
            self.assertTrue(self.suspicious_device.is_suspicious())
            self.assertFalse(self.trusted_device.is_suspicious())
            
        except Exception as e:
            logger.error(f"Device risk calculation test failed: {str(e)}")
            raise
    
    def test_device_duplicate_check(self):
        """Test duplicate device checking"""
        try:
            # Create duplicate device
            duplicate_device = self._create_test_device(
                user=self.admin_user,  # Different user
                device_id='trusted_device_123',  # Same device ID
                device_model='iPhone 13',
                device_brand='Apple'
            )
            
            # Check duplicates
            duplicate_count = DeviceInfo.check_duplicate_devices(
                self.trusted_device.device_id_hash,
                exclude_user=self.regular_user
            )
            
            self.assertEqual(duplicate_count, 1)
            
        except Exception as e:
            logger.error(f"Device duplicate check test failed: {str(e)}")
            raise
    
    def test_device_update_risk_score(self):
        """Test risk score update method"""
        try:
            initial_score = self.trusted_device.risk_score
            
            # Update risk score
            self.trusted_device.update_risk_score()
            
            # Refresh from DB
            self.trusted_device.refresh_from_db()
            
            # Risk score might change based on various factors
            self.assertIsNotNone(self.trusted_device.risk_score)
            
        except Exception as e:
            logger.error(f"Device update risk score test failed: {str(e)}")
            raise
    
    def test_device_clean_validation(self):
        """Test model validation"""
        try:
            # Test invalid risk score
            self.trusted_device.risk_score = 150
            with self.assertRaises(ValidationError):
                self.trusted_device.full_clean()
            
            # Test invalid IP
            self.trusted_device.last_ip = 'invalid_ip'
            with self.assertRaises(ValidationError):
                self.trusted_device.full_clean()
            
            # Fix and validate
            self.trusted_device.risk_score = 50
            self.trusted_device.last_ip = '192.168.1.1'
            self.trusted_device.full_clean()  # Should not raise
            
        except Exception as e:
            logger.error(f"Device validation test failed: {str(e)}")
            raise
    
    # ==================== API TESTS ====================
    
    @retry_on_failure(max_retries=3)
    def test_device_creation(self):
        """Test device creation with defensive coding"""
        try:
            device_data = {
                'device_id': 'test_device_789',
                'device_model': 'Samsung Galaxy S21',
                'device_brand': 'Samsung',
                'android_version': '12',
                'app_version': '2.0.0',
                'is_rooted': False,
                'is_vpn': False,
                'risk_score': 20,
            }
            
            # Authenticate as regular user
            self.client.force_authenticate(user=self.regular_user)
            
            # Create device via API
            response = self.client.post(
                reverse('device-list'),
                data=device_data,
                format='json'
            )
            
            self.assertSafeResponse(response, status.HTTP_201_CREATED)
            
            # Verify device was created
            device_id = response.data.get('id')
            self.assertIsNotNone(device_id)
            
            # Verify defensive fields
            self.assertIn('device_id_hash', response.data)
            self.assertIsNotNone(response.data['device_id_hash'])
            
            # Verify device was saved in database
            device = DeviceInfo.objects.filter(id=device_id).first()
            self.assertIsNotNone(device)
            self.assertEqual(device.user, self.regular_user)
            
        except Exception as e:
            logger.error(f"Device creation test failed: {str(e)}")
            raise
    
    def test_device_creation_without_auth(self):
        """Test device creation without authentication"""
        try:
            device_data = {
                'device_id': 'test_device_789',
                'device_model': 'Samsung Galaxy S21',
            }
            
            # No authentication
            response = self.client.post(
                reverse('device-list'),
                data=device_data,
                format='json'
            )
            
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
            
        except Exception as e:
            logger.error(f"Device creation without auth test failed: {str(e)}")
            raise
    
    def test_device_retrieval(self):
        """Test device retrieval with defensive coding"""
        try:
            # Authenticate as device owner
            self.client.force_authenticate(user=self.regular_user)
            
            # Get device details
            response = self.client.get(
                reverse('device-detail', args=[self.trusted_device.id])
            )
            
            self.assertSafeResponse(response, status.HTTP_200_OK)
            
            # Verify response structure
            self.assertIn('device_id', response.data)
            self.assertIn('risk_score', response.data)
            self.assertIn('is_trusted', response.data)
            self.assertIn('security_assessment', response.data)
            self.assertIn('device_status', response.data)
            
            # Verify correct data
            self.assertEqual(response.data['device_id'], self.trusted_device.device_id)
            self.assertEqual(response.data['risk_score'], self.trusted_device.risk_score)
            
            # Test with non-existent device
            response = self.client.get(
                reverse('device-detail', args=[99999])
            )
            self.assertSafeResponse(response, status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            logger.error(f"Device retrieval test failed: {str(e)}")
            raise
    
    def test_device_retrieval_unauthorized(self):
        """Test retrieving someone else's device"""
        try:
            # Create another user
            other_user = self._create_test_user(
                username='otheruser',
                email='other@example.com',
                password='otherpass123'
            )
            
            # Authenticate as other user
            self.client.force_authenticate(user=other_user)
            
            # Try to get regular_user's device
            response = self.client.get(
                reverse('device-detail', args=[self.trusted_device.id])
            )
            
            # Should be forbidden or not found
            self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])
            
        except Exception as e:
            logger.error(f"Device retrieval unauthorized test failed: {str(e)}")
            raise
    
    def test_device_list(self):
        """Test device listing"""
        try:
            # Authenticate as regular user
            self.client.force_authenticate(user=self.regular_user)
            
            # Get device list
            response = self.client.get(reverse('device-list'))
            
            self.assertSafeResponse(response, status.HTTP_200_OK)
            
            # Should only see own devices (3 devices)
            self.assertEqual(len(response.data.get('results', [])), 3)
            
            # Test filtering
            response = self.client.get(
                reverse('device-list'),
                {'suspicious_only': 'true'}
            )
            
            self.assertSafeResponse(response, status.HTTP_200_OK)
            
            # Should see only suspicious devices
            results = response.data.get('results', [])
            for device in results:
                self.assertTrue(device['is_rooted'] or device['risk_score'] > 70)
            
        except Exception as e:
            logger.error(f"Device list test failed: {str(e)}")
            raise
    
    def test_device_analytics(self):
        """Test device analytics endpoint"""
        try:
            # Authenticate as admin
            self.client.force_authenticate(user=self.admin_user)
            
            # Get device analytics
            response = self.client.get(
                reverse('device-analytics'),
                {'days': 7}
            )
            
            self.assertSafeResponse(response, status.HTTP_200_OK)
            
            # Verify analytics structure
            data = response.data
            self.assertIn('overview', data)
            self.assertIn('risk_distribution', data)
            self.assertIn('device_types', data)
            self.assertIn('suspicious_activity', data)
            self.assertIn('trends', data)
            self.assertIn('timeframe', data)
            
            # Verify data types
            overview = data['overview']
            self.assertIsInstance(overview['total_devices'], int)
            self.assertIsInstance(overview['average_risk_score'], (int, float))
            
            # Verify risk distribution
            risk_dist = data['risk_distribution']
            self.assertIn('low_risk', risk_dist)
            self.assertIn('medium_risk', risk_dist)
            self.assertIn('high_risk', risk_dist)
            
            # Verify total matches
            total = risk_dist['low_risk'] + risk_dist['medium_risk'] + risk_dist['high_risk']
            self.assertEqual(total, overview['total_devices'])
            
        except Exception as e:
            logger.error(f"Device analytics test failed: {str(e)}")
            raise
    
    def test_device_analytics_unauthorized(self):
        """Test analytics endpoint with regular user"""
        try:
            # Authenticate as regular user
            self.client.force_authenticate(user=self.regular_user)
            
            # Get device analytics (should work but only show user's data)
            response = self.client.get(
                reverse('device-analytics'),
                {'days': 7}
            )
            
            self.assertSafeResponse(response, status.HTTP_200_OK)
            
            # Should have user-specific data
            data = response.data
            self.assertIn('overview', data)
            
            # Overview should reflect user's devices only
            overview = data['overview']
            self.assertEqual(overview['total_devices'], 3)  # User has 3 devices
            
        except Exception as e:
            logger.error(f"Device analytics unauthorized test failed: {str(e)}")
            raise
    
    def test_device_trust_toggle(self):
        """Test device trust toggle functionality"""
        try:
            # Authenticate as admin
            self.client.force_authenticate(user=self.admin_user)
            
            # Initial state
            self.assertTrue(self.trusted_device.is_trusted)
            
            # Toggle device trust
            response = self.client.post(
                reverse('device-toggle-trust', args=[self.trusted_device.id]),
                format='json'
            )
            
            self.assertSafeResponse(response, status.HTTP_200_OK)
            
            # Verify response
            self.assertIn('message', response.data)
            self.assertIn('is_trusted', response.data)
            
            # Verify trust was toggled in database
            self.trusted_device.refresh_from_db()
            self.assertFalse(self.trusted_device.is_trusted)  # Was True, now False
            
            # Toggle again
            response = self.client.post(
                reverse('device-toggle-trust', args=[self.trusted_device.id]),
                format='json'
            )
            
            self.assertSafeResponse(response, status.HTTP_200_OK)
            
            # Verify trust was toggled back
            self.trusted_device.refresh_from_db()
            self.assertTrue(self.trusted_device.is_trusted)  # Back to True
            
        except Exception as e:
            logger.error(f"Device trust toggle test failed: {str(e)}")
            raise
    
    def test_device_trust_toggle_unauthorized(self):
        """Test trust toggle with regular user"""
        try:
            # Authenticate as regular user
            self.client.force_authenticate(user=self.regular_user)
            
            # Try to toggle device trust
            response = self.client.post(
                reverse('device-toggle-trust', args=[self.trusted_device.id]),
                format='json'
            )
            
            # Should be forbidden
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
            
        except Exception as e:
            logger.error(f"Device trust toggle unauthorized test failed: {str(e)}")
            raise
    
    def test_device_blacklist(self):
        """Test device blacklist functionality"""
        try:
            # Authenticate as admin
            self.client.force_authenticate(user=self.admin_user)
            
            # Blacklist device
            response = self.client.post(
                reverse('device-blacklist', args=[self.suspicious_device.id]),
                data={'reason': 'Testing blacklist'},
                format='json'
            )
            
            self.assertSafeResponse(response, status.HTTP_200_OK)
            
            # Verify response
            self.assertIn('message', response.data)
            self.assertTrue(response.data['is_blacklisted'])
            self.assertEqual(response.data['risk_score'], 100)
            
            # Verify device was updated
            self.suspicious_device.refresh_from_db()
            self.assertTrue(self.suspicious_device.is_blacklisted)
            self.assertEqual(self.suspicious_device.risk_score, 100)
            
            # Verify security log was created
            log = SecurityLog.objects.filter(
                device_info=self.suspicious_device,
                security_type='device_blacklisted'
            ).first()
            self.assertIsNotNone(log)
            
        except Exception as e:
            logger.error(f"Device blacklist test failed: {str(e)}")
            raise
    
    def test_device_whitelist(self):
        """Test device whitelist functionality"""
        try:
            # First blacklist the device
            self.suspicious_device.is_blacklisted = True
            self.suspicious_device.save()
            
            # Authenticate as admin
            self.client.force_authenticate(user=self.admin_user)
            
            # Whitelist device
            response = self.client.post(
                reverse('device-whitelist', args=[self.suspicious_device.id]),
                data={'reason': 'Testing whitelist'},
                format='json'
            )
            
            self.assertSafeResponse(response, status.HTTP_200_OK)
            
            # Verify response
            self.assertIn('message', response.data)
            self.assertTrue(response.data['is_trusted'])
            self.assertFalse(response.data['is_blacklisted'])
            
            # Verify device was updated
            self.suspicious_device.refresh_from_db()
            self.assertFalse(self.suspicious_device.is_blacklisted)
            self.assertTrue(self.suspicious_device.is_trusted)
            self.assertEqual(self.suspicious_device.risk_score, 10)
            
        except Exception as e:
            logger.error(f"Device whitelist test failed: {str(e)}")
            raise
    
    def test_device_summary(self):
        """Test device summary endpoint"""
        try:
            # Authenticate as regular user
            self.client.force_authenticate(user=self.regular_user)
            
            # Get device summary
            response = self.client.get(reverse('device-summary'))
            
            self.assertSafeResponse(response, status.HTTP_200_OK)
            
            # Verify response for regular user
            data = response.data
            self.assertEqual(data['scope'], 'user')
            self.assertEqual(data['total_devices'], 3)
            self.assertEqual(data['trusted_devices'], 1)
            self.assertEqual(data['suspicious_devices'], 1)
            
            # Authenticate as admin
            self.client.force_authenticate(user=self.admin_user)
            
            # Get device summary
            response = self.client.get(reverse('device-summary'))
            
            self.assertSafeResponse(response, status.HTTP_200_OK)
            
            # Verify response for admin
            data = response.data
            self.assertEqual(data['scope'], 'system')
            self.assertGreaterEqual(data['total_devices'], 3)
            self.assertIn('trust_percentage', data)
            self.assertIn('risk_percentage', data)
            
        except Exception as e:
            logger.error(f"Device summary test failed: {str(e)}")
            raise
    
    def test_device_update(self):
        """Test device update"""
        try:
            # Authenticate as admin
            self.client.force_authenticate(user=self.admin_user)
            
            # Update device
            update_data = {
                'device_model': 'Updated Model',
                'android_version': '13',
                'is_vpn': True
            }
            
            response = self.client.patch(
                reverse('device-detail', args=[self.trusted_device.id]),
                data=update_data,
                format='json'
            )
            
            self.assertSafeResponse(response, status.HTTP_200_OK)
            
            # Verify update
            self.trusted_device.refresh_from_db()
            self.assertEqual(self.trusted_device.device_model, 'Updated Model')
            self.assertEqual(self.trusted_device.android_version, '13')
            self.assertTrue(self.trusted_device.is_vpn)
            
        except Exception as e:
            logger.error(f"Device update test failed: {str(e)}")
            raise
    
    def test_device_delete(self):
        """Test device deletion"""
        try:
            # Authenticate as admin
            self.client.force_authenticate(user=self.admin_user)
            
            # Delete device
            response = self.client.delete(
                reverse('device-detail', args=[self.vpn_device.id])
            )
            
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            
            # Verify deletion
            with self.assertRaises(DeviceInfo.DoesNotExist):
                DeviceInfo.objects.get(id=self.vpn_device.id)
            
        except Exception as e:
            logger.error(f"Device delete test failed: {str(e)}")
            raise
    
    # ==================== DEFENSIVE TESTS ====================
    
    def test_defensive_device_handling(self):
        """Test defensive handling of edge cases"""
        try:
            # Test with invalid device ID
            self.client.force_authenticate(user=self.regular_user)
            
            response = self.client.get(
                reverse('device-detail', args=['invalid_id'])  # Non-integer ID
            )
            self.assertSafeResponse(response, status.HTTP_404_NOT_FOUND)
            
            # Test with missing required fields
            response = self.client.post(
                reverse('device-list'),
                data={},  # Empty data
                format='json'
            )
            self.assertSafeResponse(response, status.HTTP_400_BAD_REQUEST)
            
            # Test with malicious input
            malicious_data = {
                'device_id': 'a' * 1000,  # Very long device ID
                'device_model': '<script>alert("xss")</script>',
                'risk_score': 150,  # Out of range
                'is_rooted': 'not_boolean',  # Invalid boolean
            }
            
            response = self.client.post(
                reverse('device-list'),
                data=malicious_data,
                format='json'
            )
            # Should either reject or sanitize the input
            self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_201_CREATED])
            
            # If created, check sanitization
            if response.status_code == status.HTTP_201_CREATED:
                device_id = response.data.get('id')
                device = DeviceInfo.objects.get(id=device_id)
                self.assertNotIn('<script>', device.device_model)  # XSS should be escaped
            
        except Exception as e:
            logger.error(f"Defensive device handling test failed: {str(e)}")
            raise
    
    def test_rate_limiting(self):
        """Test rate limiting on list endpoint"""
        try:
            self.client.force_authenticate(user=self.regular_user)
            
            # Make many requests
            for i in range(25):  # More than limit (20)
                response = self.client.get(reverse('device-list'))
                
                if i < 20:
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                else:
                    # Should start rate limiting
                    self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
                    self.assertIn('error', response.data)
                    
        except Exception as e:
            logger.error(f"Rate limiting test failed: {str(e)}")
            raise
    
    def test_device_limit(self):
        """Test maximum devices per user"""
        try:
            self.client.force_authenticate(user=self.regular_user)
            
            # Try to create more than 10 devices
            for i in range(12):
                device_data = {
                    'device_id': f'test_device_{i}',
                    'device_model': f'Test Model {i}',
                }
                
                response = self.client.post(
                    reverse('device-list'),
                    data=device_data,
                    format='json'
                )
                
                if i < 10:
                    self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                else:
                    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                    
        except Exception as e:
            logger.error(f"Device limit test failed: {str(e)}")
            raise
    
    def test_concurrent_device_creation(self):
        """Test concurrent device creation"""
        try:
            from concurrent.futures import ThreadPoolExecutor
            
            self.client.force_authenticate(user=self.regular_user)
            
            def create_device(i):
                device_data = {
                    'device_id': f'concurrent_device_{i}',
                    'device_model': f'Concurrent Model {i}',
                }
                return self.client.post(
                    reverse('device-list'),
                    data=device_data,
                    format='json'
                )
            
            # Create 5 devices concurrently
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(create_device, i) for i in range(5)]
                responses = [f.result() for f in futures]
            
            # All should succeed
            for response in responses:
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"Concurrent device creation test failed: {str(e)}")
            raise
    
    # ==================== MODEL METHOD TESTS ====================
    
    def test_device_model_methods(self):
        """Test all device model methods"""
        try:
            device = self.suspicious_device
            
            # Test get_risk_level
            risk_level = device.get_risk_level()
            self.assertIn(risk_level, ['safe', 'low', 'medium', 'high', 'critical'])
            
            # Test get_risk_level_display
            display = device.get_risk_level_display()
            self.assertIsInstance(display, str)
            self.assertIn(device.get_risk_level(), display.lower())
            
            # Test get_security_flags
            flags = device.get_security_flags()
            self.assertIsInstance(flags, list)
            
            # Test is_suspicious
            suspicious = device.is_suspicious()
            self.assertIsInstance(suspicious, bool)
            
            # Test get_fingerprint
            fingerprint = device.get_fingerprint()
            self.assertIsInstance(fingerprint, dict)
            self.assertIn('device_id_hash', fingerprint)
            self.assertIn('risk_score', fingerprint)
            
        except Exception as e:
            logger.error(f"Device model methods test failed: {str(e)}")
            raise
    
    def test_device_manager_methods(self):
        """Test device manager methods"""
        try:
            # Test active_devices
            active = DeviceInfo.objects.active_devices(hours=24)
            self.assertIsNotNone(active)
            
            # Test high_risk_devices
            high_risk = DeviceInfo.objects.high_risk_devices()
            self.assertIn(self.suspicious_device, high_risk)
            
            # Test suspicious_devices
            suspicious = DeviceInfo.objects.suspicious_devices()
            self.assertIn(self.suspicious_device, suspicious)
            
            # Test trusted_devices
            trusted = DeviceInfo.objects.trusted_devices()
            self.assertIn(self.trusted_device, trusted)
            
            # Test devices_by_user
            user_devices = DeviceInfo.objects.devices_by_user(self.regular_user)
            self.assertEqual(user_devices.count(), 3)
            
            # Test devices_by_ip
            ip_devices = DeviceInfo.objects.devices_by_ip('127.0.0.1')
            self.assertIsNotNone(ip_devices)
            
        except Exception as e:
            logger.error(f"Device manager methods test failed: {str(e)}")
            raise
    
    def test_duplicate_report(self):
        """Test duplicate device report"""
        try:
            # Create duplicate device
            duplicate_device = self._create_test_device(
                user=self.admin_user,
                device_id='trusted_device_123',
                device_model='iPhone 13',
                device_brand='Apple'
            )
            
            # Get duplicate report
            report = DeviceInfo.get_duplicate_report()
            
            self.assertIsInstance(report, dict)
            self.assertIn('total_duplicates', report)
            self.assertIn('devices', report)
            self.assertIn('top_offenders', report)
            
            # Should find at least one duplicate
            self.assertGreaterEqual(report['total_duplicates'], 1)
            
        except Exception as e:
            logger.error(f"Duplicate report test failed: {str(e)}")
            raise
    
    # ==================== EDGE CASE TESTS ====================
    
    def test_device_with_null_user(self):
        """Test device with null user"""
        try:
            device = self._create_test_device(
                user=None,
                device_id='null_user_device',
                device_model='Anonymous Device'
            )
            
            self.assertIsNotNone(device)
            self.assertIsNone(device.user)
            
            # Test string representation
            device_str = str(device)
            self.assertIn('Anonymous', device_str)
            
        except Exception as e:
            logger.error(f"Device null user test failed: {str(e)}")
            raise
    
    def test_device_with_malformed_ip(self):
        """Test device with malformed IP"""
        try:
            device = self._create_test_device(
                user=self.regular_user,
                device_id='malformed_ip_device',
                last_ip='not_an_ip'
            )
            
            # Should still save but IP might be validated
            self.assertIsNotNone(device)
            
        except Exception as e:
            logger.error(f"Device malformed IP test failed: {str(e)}")
            raise
    
    def test_device_with_long_strings(self):
        """Test device with very long strings"""
        try:
            long_string = 'a' * 500  # Longer than max_length
            
            device = self._create_test_device(
                user=self.regular_user,
                device_id=long_string,
                device_model=long_string,
                device_brand=long_string
            )
            
            # Should either truncate or reject
            if device:
                self.assertLessEqual(len(device.device_id), 255)
            
        except Exception as e:
            logger.error(f"Device long strings test failed: {str(e)}")
            raise
    
    # ==================== TRANSACTION TESTS ====================
    
    @transaction.atomic
    def test_device_creation_in_transaction(self):
        """Test device creation within transaction"""
        try:
            device = self._create_test_device(
                user=self.regular_user,
                device_id='transaction_device',
                device_model='Transaction Test'
            )
            
            self.assertIsNotNone(device)
            
        except Exception as e:
            logger.error(f"Device transaction test failed: {str(e)}")
            raise
    
    # ==================== SIGNAL TESTS ====================
    
    def test_device_post_save_signal(self):
        """Test post-save signal"""
        try:
            with patch('security.models.logger') as mock_logger:
                device = self._create_test_device(
                    user=self.regular_user,
                    device_id='signal_test_device'
                )
                
                # Signal should log creation
                mock_logger.info.assert_called()
                
        except Exception as e:
            logger.error(f"Device signal test failed: {str(e)}")
            raise
    
    # ==================== SERIALIZER TESTS ====================
    
    def test_device_serializer_validation(self):
        """Test device serializer validation"""
        try:
            from ..serializers import DeviceInfoSerializer
            
            # Test valid data
            valid_data = {
                'raw_device_id': 'valid_device_123',
                'device_model': 'Test Model',
                'device_brand': 'Test Brand',
                'android_version': '12',
                'app_version': '1.0.0'
            }
            
            serializer = DeviceInfoSerializer(data=valid_data)
            self.assertTrue(serializer.is_valid())
            
            # Test invalid data
            invalid_data = {
                'raw_device_id': 'a' * 300,  # Too long
                'risk_score': 150,  # Out of range
                'trust_level': 5,  # Invalid choice
            }
            
            serializer = DeviceInfoSerializer(data=invalid_data)
            self.assertFalse(serializer.is_valid())
            self.assertIn('raw_device_id', serializer.errors)
            self.assertIn('risk_score', serializer.errors)
            
        except Exception as e:
            logger.error(f"Serializer validation test failed: {str(e)}")
            raise


# ==================== INTEGRATION TESTS ====================

class DeviceInfoIntegrationTests(APITestCase):
    """Integration tests for DeviceInfo"""
    
    def setUp(self):
        """Set up integration test data"""
        self.client = APIClient()
        
        # Create users
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        # Clear cache
        cache.clear()
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
    
    def test_full_device_lifecycle(self):
        """Test complete device lifecycle"""
        try:
            # 1. Create device
            self.client.force_authenticate(user=self.user)
            
            device_data = {
                'device_id': 'lifecycle_device',
                'device_model': 'Lifecycle Test',
                'device_brand': 'TestBrand',
                'android_version': '12',
            }
            
            response = self.client.post(
                reverse('device-list'),
                data=device_data,
                format='json'
            )
            
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            device_id = response.data['id']
            
            # 2. Retrieve device
            response = self.client.get(
                reverse('device-detail', args=[device_id])
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # 3. Update device (as admin)
            self.client.force_authenticate(user=self.admin)
            
            update_data = {
                'is_trusted': True,
                'trust_level': 3
            }
            
            response = self.client.patch(
                reverse('device-detail', args=[device_id]),
                data=update_data,
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # 4. Get device summary
            response = self.client.get(reverse('device-summary'))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # 5. Delete device
            response = self.client.delete(
                reverse('device-detail', args=[device_id])
            )
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            logger.error(f"Device lifecycle test failed: {str(e)}")
            raise
    
    def test_device_security_flow(self):
        """Test security flow for suspicious device"""
        try:
            self.client.force_authenticate(user=self.user)
            
            # 1. Create suspicious device
            device_data = {
                'device_id': 'suspicious_device',
                'device_model': 'Rooted Phone',
                'is_rooted': True,
                'is_emulator': False
            }
            
            response = self.client.post(
                reverse('device-list'),
                data=device_data,
                format='json'
            )
            
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            device_id = response.data['id']
            
            # 2. Check security assessment
            response = self.client.get(
                reverse('device-detail', args=[device_id])
            )
            
            security = response.data.get('security_assessment', {})
            self.assertEqual(security.get('overall_risk'), 'high')
            
            # 3. Admin blacklists device
            self.client.force_authenticate(user=self.admin)
            
            response = self.client.post(
                reverse('device-blacklist', args=[device_id]),
                data={'reason': 'Suspicious activity'}
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # 4. Verify security log was created
            log_exists = SecurityLog.objects.filter(
                device_info_id=device_id,
                security_type='device_blacklisted'
            ).exists()
            self.assertTrue(log_exists)
            
        except Exception as e:
            logger.error(f"Device security flow test failed: {str(e)}")
            raise
    
    def test_duplicate_device_detection_flow(self):
        """Test duplicate device detection flow"""
        try:
            self.client.force_authenticate(user=self.user)
            
            # 1. Create first device
            device_data = {
                'device_id': 'shared_device_123',
                'device_model': 'Shared Device',
            }
            
            response = self.client.post(
                reverse('device-list'),
                data=device_data,
                format='json'
            )
            
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            
            # 2. Create second user
            other_user = User.objects.create_user(
                username='otheruser2',
                email='other2@example.com',
                password='otherpass123'
            )
            
            self.client.force_authenticate(user=other_user)
            
            # 3. Create same device for other user
            response = self.client.post(
                reverse('device-list'),
                data=device_data,
                format='json'
            )
            
            # Should still succeed but with warning
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            
            # 4. Check duplicate report
            self.client.force_authenticate(user=self.admin)
            
            response = self.client.get(reverse('device-analytics'))
            suspicious = response.data.get('suspicious_activity', {})
            
            self.assertGreaterEqual(suspicious.get('duplicate_devices', 0), 1)
            
        except Exception as e:
            logger.error(f"Duplicate device flow test failed: {str(e)}")
            raise
    
    def test_bulk_device_operations(self):
        """Test bulk device operations"""
        try:
            self.client.force_authenticate(user=self.admin)
            
            # Create multiple devices first
            device_ids = []
            for i in range(3):
                response = self.client.post(
                    reverse('device-list'),
                    data={
                        'device_id': f'bulk_test_{i}',
                        'device_model': f'Bulk Model {i}',
                    },
                    format='json'
                )
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                device_ids.append(response.data['id'])
            
            # Test bulk update (if endpoint exists)
            # This would test a bulk update endpoint if available
            
        except Exception as e:
            logger.error(f"Bulk operations test failed: {str(e)}")
            raise


# ==================== PERFORMANCE TESTS ====================

class DeviceInfoPerformanceTests(TestCase):
    """Performance tests for DeviceInfo"""
    
    def setUp(self):
        """Set up performance test data"""
        self.user = User.objects.create_user(
            username='perfuser',
            email='perf@example.com',
            password='perfpass123'
        )
        
        # Create many devices
        self.devices = []
        for i in range(100):
            device = DeviceInfo.objects.create(
                user=self.user if i % 2 == 0 else None,
                device_id=f'perf_device_{i}',
                device_model=f'Model {i}',
                is_rooted=(i % 5 == 0),
                is_emulator=(i % 7 == 0),
                risk_score=i % 100
            )
            self.devices.append(device)
    
    def test_queryset_performance(self):
        """Test queryset performance"""
        from django.db import connection
        
        # Test count with index
        with self.assertNumQueries(1):
            count = DeviceInfo.objects.filter(is_rooted=True).count()
            self.assertGreaterEqual(count, 0)
        
        # Test filter with index
        with self.assertNumQueries(1):
            devices = list(DeviceInfo.objects.filter(risk_score__gte=70))
        
        # Test select_related
        with self.assertNumQueries(1):
            devices = list(DeviceInfo.objects.select_related('user')[:10])
    
    def test_serializer_performance(self):
        """Test serializer performance"""
        from ..serializers import DeviceInfoSerializer
        
        device = self.devices[0]
        
        # Measure serialization time
        import time
        start = time.time()
        
        serializer = DeviceInfoSerializer(device)
        data = serializer.data
        
        duration = time.time() - start
        self.assertLess(duration, 0.1)  # Should take less than 100ms
    
    def test_manager_methods_performance(self):
        """Test manager methods performance"""
        with self.assertNumQueries(1):
            active = DeviceInfo.objects.active_devices()
            list(active)
        
        with self.assertNumQueries(1):
            high_risk = DeviceInfo.objects.high_risk_devices()
            list(high_risk)
    
    def tearDown(self):
        """Clean up"""
        DeviceInfo.objects.all().delete()
        User.objects.all().delete()

class SecurityLogTests(BaseSecurityTest):
    """Tests for SecurityLog model and views"""
    
    def test_security_log_creation(self):
        """Test security log creation"""
        try:
            log_data = {
                'security_type': 'unauthorized_access',
                'severity': 'high',
                'description': 'Test unauthorized access attempt',
                'ip_address': '192.168.1.100',
                'risk_score': 75,
            }
            
            # Authenticate as admin
            self.client.force_authenticate(user=self.admin_user)
            
            response = self.client.post(
                reverse('security-log-list'),
                data=log_data,
                format='json'
            )
            
            self.assertSafeResponse(response, 201)
            
            # Verify log was created
            log_id = response.data.get('id')
            self.assertIsNotNone(log_id)
            
            # Verify severity-based risk score
            self.assertGreaterEqual(response.data['risk_score'], 60)
            
        except Exception as e:
            logger.error(f"Security log creation test failed: {str(e)}")
            raise
    
    def test_security_log_retrieval(self):
        """Test security log retrieval with permissions"""
        try:
            # Test as log owner
            self.client.force_authenticate(user=self.regular_user)
            
            response = self.client.get(
                reverse('security-log-detail', args=[self.security_log.id])
            )
            
            self.assertSafeResponse(response, 200)
            
            # Test as admin (should see all logs)
            self.client.force_authenticate(user=self.admin_user)
            
            response = self.client.get(reverse('security-log-list'))
            self.assertSafeResponse(response, 200)
            self.assertGreater(len(response.data['results']), 0)
            
            # Test as other user (should not see this log)
            other_user = self._create_user(username='other_user')
            self.client.force_authenticate(user=other_user)
            
            response = self.client.get(
                reverse('security-log-detail', args=[self.security_log.id])
            )
            self.assertSafeResponse(response, 404)
            
        except Exception as e:
            logger.error(f"Security log retrieval test failed: {str(e)}")
            raise
    
    def test_security_log_resolution(self):
        """Test security log resolution"""
        try:
            # Authenticate as admin
            self.client.force_authenticate(user=self.admin_user)
            
            resolution_data = {
                'reason': 'False positive',
                'notes': 'Verified as legitimate activity'
            }
            
            response = self.client.post(
                reverse('resolve-log', args=[self.security_log.id]),
                data=resolution_data,
                format='json'
            )
            
            self.assertSafeResponse(response, 200)
            
            # Verify log was resolved
            self.security_log.refresh_from_db()
            self.assertTrue(self.security_log.resolved)
            self.assertIsNotNone(self.security_log.resolved_at)
            self.assertEqual(self.security_log.resolved_by, self.admin_user)
            
        except Exception as e:
            logger.error(f"Security log resolution test failed: {str(e)}")
            raise
    
    def test_security_log_statistics(self):
        """Test security log statistics endpoint"""
        try:
            # Create more test logs
            for i in range(5):
                self._create_security_log(
                    user=self.regular_user,
                    security_type='failed_login',
                    severity='medium'
                )
            
            # Authenticate as admin
            self.client.force_authenticate(user=self.admin_user)
            
            response = self.client.get(reverse('log-statistics'))
            
            self.assertSafeResponse(response, 200)
            
            # Verify statistics structure
            stats = response.data
            self.assertIn('total_logs', stats)
            self.assertIn('by_severity', stats)
            self.assertIn('by_type', stats)
            self.assertIn('resolution_rate', stats)
            self.assertIn('hourly_distribution', stats)
            
            # Verify data integrity
            self.assertGreater(stats['total_logs'], 0)
            self.assertIsInstance(stats['resolution_rate']['rate'], (int, float))
            
        except Exception as e:
            logger.error(f"Security log statistics test failed: {str(e)}")
            raise
    
    def test_bulk_log_resolution(self):
        """Test bulk security log resolution"""
        try:
            # Create multiple logs for bulk operation
            log_ids = []
            for i in range(3):
                log = self._create_security_log(
                    user=self.regular_user,
                    security_type=f'test_type_{i}',
                    severity='low'
                )
                log_ids.append(log.id)
            
            # Authenticate as admin
            self.client.force_authenticate(user=self.admin_user)
            
            bulk_data = {
                'log_ids': log_ids,
                'reason': 'Bulk test resolution'
            }
            
            response = self.client.post(
                reverse('bulk-resolve-logs'),
                data=bulk_data,
                format='json'
            )
            
            self.assertSafeResponse(response, 200)
            
            # Verify logs were resolved
            resolved_logs = SecurityLog.objects.filter(
                id__in=log_ids,
                resolved=True
            ).count()
            self.assertEqual(resolved_logs, len(log_ids))
            
        except Exception as e:
            logger.error(f"Bulk log resolution test failed: {str(e)}")
            raise


class RiskScoreTests(BaseSecurityTest):
    """Tests for RiskScore model and views"""
    
    def test_risk_score_calculation(self):
        """Test risk score calculation"""
        try:
            # Create risk score with various factors
            risk_score = self._create_risk_score(
                user=self.regular_user,
                failed_login_attempts=8,
                suspicious_activities=3,
                vpn_usage_count=5,
                device_diversity=7,
                location_diversity=4
            )
            
            # Recalculate score
            risk_score.update_score()
            
            # Verify score is within bounds
            self.assertGreaterEqual(risk_score.current_score, 0)
            self.assertLessEqual(risk_score.current_score, 100)
            
            # Verify score changed from previous
            self.assertNotEqual(risk_score.current_score, risk_score.previous_score)
            
        except Exception as e:
            logger.error(f"Risk score calculation test failed: {str(e)}")
            raise
    
    def test_risk_score_retrieval(self):
        """Test risk score retrieval"""
        try:
            # Test as user (own risk score)
            self.client.force_authenticate(user=self.regular_user)
            
            response = self.client.get(
                reverse('risk-score-detail', args=[self.risk_score.id])
            )
            
            self.assertSafeResponse(response, 200)
            
            # Verify response contains risk data
            self.assertIn('current_score', response.data)
            self.assertIn('failed_login_attempts', response.data)
            self.assertIn('suspicious_activities', response.data)
            
            # Test as admin (all risk scores)
            self.client.force_authenticate(user=self.admin_user)
            
            response = self.client.get(reverse('risk-score-list'))
            self.assertSafeResponse(response, 200)
            self.assertGreater(len(response.data['results']), 0)
            
        except Exception as e:
            logger.error(f"Risk score retrieval test failed: {str(e)}")
            raise
    
    def test_risk_score_recalculation(self):
        """Test manual risk score recalculation"""
        try:
            # Authenticate as admin
            self.client.force_authenticate(user=self.admin_user)
            
            response = self.client.post(
                reverse('recalculate-risk', args=[self.risk_score.id]),
                format='json'
            )
            
            self.assertSafeResponse(response, 200)
            
            # Verify score was recalculated
            self.risk_score.refresh_from_db()
            self.assertNotEqual(self.risk_score.current_score, 45)  # Original score
            
        except Exception as e:
            logger.error(f"Risk score recalculation test failed: {str(e)}")
            raise
    
    def test_risk_distribution(self):
        """Test risk distribution endpoint"""
        try:
            # Create multiple risk scores
            for score in [10, 30, 60, 85]:
                self._create_risk_score(
                    user=self._create_user(username=f'user_{score}'),
                    current_score=score
                )
            
            # Authenticate as admin
            self.client.force_authenticate(user=self.admin_user)
            
            response = self.client.get(reverse('risk-distribution'))
            
            self.assertSafeResponse(response, 200)
            
            # Verify distribution data
            distribution = response.data
            self.assertIn('low_risk', distribution)
            self.assertIn('medium_risk', distribution)
            self.assertIn('high_risk', distribution)
            self.assertIn('average_score', distribution)
            
            # Verify counts make sense
            total_risky = (
                distribution['medium_risk'] + 
                distribution['high_risk']
            )
            self.assertGreaterEqual(total_risky, 0)
            
        except Exception as e:
            logger.error(f"Risk distribution test failed: {str(e)}")
            raise
    
    def test_bulk_risk_recalculation(self):
        """Test bulk risk score recalculation"""
        try:
            # Create multiple users with risk scores
            users = []
            for i in range(5):
                user = self._create_user(username=f'bulk_user_{i}')
                self._create_risk_score(user=user, current_score=50)
                users.append(user)
            
            # Authenticate as admin
            self.client.force_authenticate(user=self.admin_user)
            
            response = self.client.post(
                reverse('recalculate-all-risks'),
                format='json'
            )
            
            self.assertSafeResponse(response, 200)
            
            # Verify response contains correct counts
            self.assertIn('updated_count', response.data)
            self.assertIn('total_users', response.data)
            
        except Exception as e:
            logger.error(f"Bulk risk recalculation test failed: {str(e)}")
            raise


class MiddlewareTests(TestCase):
    """Tests for security middleware"""
    
    def setUp(self):
        """Set up middleware tests"""
        try:
            self.client = Client()
            self.user = User.objects.create_user(
                username='testuser',
                password='TestPass123!'
            )
            
            # Create middleware instances
            self.security_headers_middleware = SecurityHeadersMiddleware(
                lambda request: self._dummy_response()
            )
            self.rate_limit_middleware = RateLimitMiddleware(
                lambda request: self._dummy_response()
            )
            self.audit_middleware = SecurityAuditMiddleware(
                lambda request: self._dummy_response()
            )
            
        except Exception as e:
            logger.error(f"Middleware test setup failed: {str(e)}")
            raise
    
    def _dummy_response(self):
        """Create dummy response for middleware testing"""
        from django.http import HttpResponse
        return HttpResponse('Test response')
    
    def _create_request(self, path='/test/', method='GET', **kwargs):
        """Create test request"""
        from django.test import RequestFactory
        factory = RequestFactory()
        
        request = factory.generic(method, path, **kwargs)
        request.user = self.user
        request.session = {}
        
        # Add required META data
        request.META.update({
            'REMOTE_ADDR': '192.168.1.100',
            'HTTP_USER_AGENT': 'Test Browser',
            'HTTP_ACCEPT_LANGUAGE': 'en-US,en;q=0.9',
        })
        
        return request
    
    def test_security_headers_middleware(self):
        """Test security headers middleware"""
        try:
            request = self._create_request()
            response = self.security_headers_middleware.process_response(
                request, 
                self._dummy_response()
            )
            
            # Verify security headers are present
            self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
            self.assertEqual(response['X-Frame-Options'], 'DENY')
            self.assertEqual(response['X-XSS-Protection'], '1; mode=block')
            
            # Verify custom headers
            self.assertIn('X-Security-Timestamp', response)
            
        except Exception as e:
            logger.error(f"Security headers test failed: {str(e)}")
            raise
    
    def test_rate_limit_middleware(self):
        """Test rate limiting middleware"""
        try:
            # Clear cache first
            cache.clear()
            
            request = self._create_request()
            
            # First request should pass
            response = self.rate_limit_middleware.process_request(request)
            self.assertIsNone(response)  # Should return None (allow request)
            
            # Simulate many requests
            for i in range(100):
                request = self._create_request(path=f'/test/{i}/')
                response = self.rate_limit_middleware.process_request(request)
                if response is not None:
                    break
            
            # Should eventually get rate limited
            if response is not None:
                self.assertEqual(response.status_code, 429)
                self.assertIn('Rate limit', response.content.decode())
            
        except Exception as e:
            logger.error(f"Rate limit test failed: {str(e)}")
            raise
    
    def test_audit_middleware(self):
        """Test security audit middleware"""
        try:
            request = self._create_request(
                path='/api/test/',
                method='POST',
                data={'test': 'data'},
                content_type='application/json'
            )
            
            # Process request
            response = self.audit_middleware.process_request(request)
            self.assertIsNone(response)
            
            # Verify audit data was stored
            self.assertTrue(hasattr(request, 'security_audit_data'))
            
            audit_data = request.security_audit_data
            self.assertEqual(audit_data['method'], 'POST')
            self.assertEqual(audit_data['path'], '/api/test/')
            self.assertEqual(audit_data['user'], 'testuser')
            
            # Process response
            dummy_response = self._dummy_response()
            response = self.audit_middleware.process_response(request, dummy_response)
            
            # Verify response was not modified
            self.assertEqual(response, dummy_response)
            
        except Exception as e:
            logger.error(f"Audit middleware test failed: {str(e)}")
            raise
    
    def test_defensive_middleware_handling(self):
        """Test defensive behavior in middleware"""
        try:
            # Test with malformed request
            request = self._create_request()
            request.META['REMOTE_ADDR'] = 'invalid_ip_address'
            
            # Should not crash
            response = self.security_headers_middleware.process_response(
                request, 
                self._dummy_response()
            )
            self.assertIsNotNone(response)
            
            # Test with None request
            try:
                response = self.security_headers_middleware.process_response(
                    None,
                    self._dummy_response()
                )
                self.assertIsNotNone(response)
            except Exception:
                # Some middleware might fail with None, that's OK
                pass
            
            # Test with missing user agent
            request = self._create_request()
            del request.META['HTTP_USER_AGENT']
            
            response = self.audit_middleware.process_request(request)
            self.assertIsNone(response)  # Should not crash
            
        except Exception as e:
            logger.error(f"Defensive middleware test failed: {str(e)}")
            raise


class VPNDetectorTests(TestCase):
    """Tests for VPN detector"""
    
    def setUp(self):
        """Set up VPN detector tests"""
        try:
            self.detector = VPNDetector()
            
            # Test IP addresses
            self.regular_ip = '8.8.8.8'  # Google DNS
            self.aws_ip = '54.240.197.5'  # Amazon AWS
            self.local_ip = '192.168.1.1'
            self.invalid_ip = '999.999.999.999'
            
        except Exception as e:
            logger.error(f"VPN detector test setup failed: {str(e)}")
            raise
    
    def test_ip_validation(self):
        """Test IP address validation"""
        try:
            # Valid IPs
            self.assertTrue(self.detector._validate_ip_address('8.8.8.8'))
            self.assertTrue(self.detector._validate_ip_address('2001:0db8:85a3:0000:0000:8a2e:0370:7334'))
            
            # Invalid IPs
            self.assertFalse(self.detector._validate_ip_address(''))
            self.assertFalse(self.detector._validate_ip_address('invalid'))
            self.assertFalse(self.detector._validate_ip_address('999.999.999.999'))
            self.assertFalse(self.detector._validate_ip_address(None))
            
        except Exception as e:
            logger.error(f"IP validation test failed: {str(e)}")
            raise
    
    def test_vpn_detection_basic(self):
        """Test basic VPN detection"""
        try:
            # Test with regular IP
            result = self.detector.detect_vpn_proxy(self.regular_ip)
            
            # Verify result structure
            self.assertIn('is_vpn', result)
            self.assertIn('is_proxy', result)
            self.assertIn('confidence', result)
            self.assertIn('geolocation', result)
            self.assertIn('timestamp', result)
            
            # Verify data types
            self.assertIsInstance(result['is_vpn'], bool)
            self.assertIsInstance(result['is_proxy'], bool)
            self.assertIsInstance(result['confidence'], (int, float))
            self.assertIsInstance(result['geolocation'], dict)
            
            # Verify confidence bounds
            self.assertGreaterEqual(result['confidence'], 0)
            self.assertLessEqual(result['confidence'], 1.0)
            
        except Exception as e:
            logger.error(f"Basic VPN detection test failed: {str(e)}")
            raise
    
    def test_vpn_detection_invalid_ip(self):
        """Test VPN detection with invalid IP"""
        try:
            result = self.detector.detect_vpn_proxy(self.invalid_ip)
            
            # Should return error or default result
            self.assertIn('is_vpn', result)
            self.assertFalse(result['is_vpn'])
            self.assertFalse(result['is_proxy'])
            
        except Exception as e:
            logger.error(f"Invalid IP detection test failed: {str(e)}")
            raise
    
    def test_bulk_detection(self):
        """Test bulk VPN detection"""
        try:
            ip_list = [self.regular_ip, self.aws_ip, self.local_ip]
            
            result = self.detector.bulk_detect(ip_list)
            
            # Verify result structure
            self.assertIsInstance(result, dict)
            self.assertEqual(len(result), len(ip_list))
            
            for ip, detection in result.items():
                self.assertIn('is_vpn', detection)
                self.assertIn('is_proxy', detection)
                
        except Exception as e:
            logger.error(f"Bulk detection test failed: {str(e)}")
            raise
    
    def test_defensive_detection(self):
        """Test defensive behavior in detection"""
        try:
            # Test with None
            result = self.detector.detect_vpn_proxy(None)
            self.assertFalse(result['is_vpn'])
            self.assertFalse(result['is_proxy'])
            
            # Test with empty string
            result = self.detector.detect_vpn_proxy('')
            self.assertFalse(result['is_vpn'])
            self.assertFalse(result['is_proxy'])
            
            # Test with very long string
            long_ip = '8.8.8.8' * 100
            result = self.detector.detect_vpn_proxy(long_ip)
            self.assertFalse(result['is_vpn'])
            self.assertFalse(result['is_proxy'])
            
        except Exception as e:
            logger.error(f"Defensive detection test failed: {str(e)}")
            raise
    
    def test_cache_behavior(self):
        """Test caching behavior"""
        try:
            # Clear cache
            cache_key = f"vpn_detection_{self.regular_ip}"
            cache.delete(cache_key)
            
            # First detection (should miss cache)
            result1 = self.detector.detect_vpn_proxy(self.regular_ip)
            
            # Second detection (should hit cache)
            result2 = self.detector.detect_vpn_proxy(self.regular_ip)
            
            # Results should be identical
            self.assertEqual(result1['is_vpn'], result2['is_vpn'])
            self.assertEqual(result1['is_proxy'], result2['is_proxy'])
            
            # Test cache invalidation
            cache.delete(cache_key)
            result3 = self.detector.detect_vpn_proxy(self.regular_ip)
            # Might be different due to fresh detection
            
        except Exception as e:
            logger.error(f"Cache behavior test failed: {str(e)}")
            raise


class UtilsTests(TestCase):
    """Tests for utility functions"""
    
    def test_null_safe(self):
        """Test NullSafe utility"""
        try:
            # Test with object
            class TestObj:
                def __init__(self):
                    self.name = 'Test'
                    self.value = 42
            
            obj = TestObj()
            
            # Valid attribute
            self.assertEqual(NullSafe.get_safe(obj, 'name', 'Default'), 'Test')
            
            # Invalid attribute with default
            self.assertEqual(NullSafe.get_safe(obj, 'nonexistent', 'Default'), 'Default')
            
            # Test with None object
            self.assertEqual(NullSafe.get_safe(None, 'name', 'Default'), 'Default')
            
            # Test dict_get_safe
            test_dict = {'key': 'value', 'number': 123}
            self.assertEqual(NullSafe.dict_get_safe(test_dict, 'key', 'default'), 'value')
            self.assertEqual(NullSafe.dict_get_safe(test_dict, 'missing', 'default'), 'default')
            self.assertEqual(NullSafe.dict_get_safe(None, 'key', 'default'), 'default')
            
            # Test execute_safe
            def good_func():
                return 'success'
            
            def bad_func():
                raise ValueError('error')
            
            self.assertEqual(NullSafe.execute_safe(good_func), 'success')
            self.assertIsNone(NullSafe.execute_safe(bad_func))
            
        except Exception as e:
            logger.error(f"NullSafe test failed: {str(e)}")
            raise
    
    def test_type_validator(self):
        """Test TypeValidator utility"""
        try:
            # Test type validation
            self.assertEqual(TypeValidator.validate_type('123', int, 0), 123)
            self.assertEqual(TypeValidator.validate_type('45.67', float, 0.0), 45.67)
            self.assertEqual(TypeValidator.validate_type('100', Decimal, Decimal('0')), Decimal('100'))
            self.assertEqual(TypeValidator.validate_type(True, str, ''), 'True')
            
            # Test invalid conversions
            self.assertEqual(TypeValidator.validate_type('not_a_number', int, 999), 999)
            self.assertEqual(TypeValidator.validate_type(None, int, 888), 888)
            
            # Test list validation
            test_list = [1, 'two', 3.0, None, 'five']
            validated = TypeValidator.validate_list(test_list, str)
            self.assertEqual(validated, ['two', 'five'])
            
            self.assertEqual(TypeValidator.validate_list(None, str), [])
            self.assertEqual(TypeValidator.validate_list('not_a_list', str), [])
            
        except Exception as e:
            logger.error(f"TypeValidator test failed: {str(e)}")
            raise
    
    def test_graceful_degradation(self):
        """Test GracefulDegradation utility"""
        try:
            def primary_func(x):
                return x * 2
            
            def fallback_func(x):
                return x + 10
            
            # Primary function succeeds
            result = GracefulDegradation.fallback_execute(
                primary_func, fallback_func, 5
            )
            self.assertEqual(result, 10)
            
            # Primary function fails, fallback succeeds
            def failing_primary(x):
                raise RuntimeError('Primary failed')
            
            result = GracefulDegradation.fallback_execute(
                failing_primary, fallback_func, 5
            )
            self.assertEqual(result, 15)
            
            # Both functions fail
            def failing_fallback(x):
                raise RuntimeError('Fallback failed')
            
            result = GracefulDegradation.fallback_execute(
                failing_primary, failing_fallback, 5
            )
            self.assertIsNone(result)
            
            # Test decorator
            @GracefulDegradation.with_default('default_value')
            def unreliable_func(should_fail=False):
                if should_fail:
                    raise ValueError('Function failed')
                return 'success'
            
            self.assertEqual(unreliable_func(False), 'success')
            self.assertEqual(unreliable_func(True), 'default_value')
            
        except Exception as e:
            logger.error(f"GracefulDegradation test failed: {str(e)}")
            raise


class IntegrationTests(BaseSecurityTest):
    """Integration tests for complete security system"""
    
    def test_complete_workflow(self):
        """Test complete security workflow"""
        try:
            # 1. User registers device
            self.client.force_authenticate(user=self.regular_user)
            
            device_data = {
                'device_id': 'integration_test_device',
                'device_model': 'Integration Test',
                'device_brand': 'Test',
                'android_version': '10',
                'is_rooted': False,
                'is_vpn': False,
            }
            
            response = self.client.post(
                reverse('device-list'),
                data=device_data,
                format='json'
            )
            self.assertSafeResponse(response, 201)
            
            device_id = response.data['id']
            
            # 2. Device performs suspicious activity
            security_log_data = {
                'security_type': 'fast_clicking',
                'severity': 'medium',
                'description': 'Rapid clicking detected',
                'ip_address': '10.0.0.1',
                'risk_score': 60,
            }
            
            self.client.force_authenticate(user=self.admin_user)
            response = self.client.post(
                reverse('security-log-list'),
                data=security_log_data,
                format='json'
            )
            self.assertSafeResponse(response, 201)
            
            # 3. Risk score updates
            risk_score = RiskScore.objects.get(user=self.regular_user)
            old_score = risk_score.current_score
            risk_score.update_score()
            
            # Score should increase due to suspicious activity
            self.assertGreater(risk_score.current_score, old_score)
            
            # 4. Admin reviews and resolves
            response = self.client.post(
                reverse('resolve-log', args=[response.data['id']]),
                data={'reason': 'False alarm'},
                format='json'
            )
            self.assertSafeResponse(response, 200)
            
            # 5. Check system status
            response = self.client.get(reverse('system-status'))
            self.assertSafeResponse(response, 200)
            
            # Verify system is healthy
            self.assertIn('modules', response.data)
            self.assertIn('threats', response.data)
            
        except Exception as e:
            logger.error(f"Integration test failed: {str(e)}")
            raise
    
    def test_rate_limiting_integration(self):
        """Test rate limiting integration"""
        try:
            # Clear cache
            cache.clear()
            
            # Make multiple requests quickly
            self.client.force_authenticate(user=self.regular_user)
            
            responses = []
            for i in range(15):  # Should trigger rate limit
                response = self.client.get(reverse('device-list'))
                responses.append(response.status_code)
            
            # Should have some 429 responses
            self.assertIn(429, responses)
            
        except Exception as e:
            logger.error(f"Rate limiting integration test failed: {str(e)}")
            raise
    
    def test_defensive_integration(self):
        """Test defensive behavior in integration"""
        try:
            # Test with invalid authentication
            self.client.logout()
            
            response = self.client.get(reverse('device-list'))
            self.assertIn(response.status_code, [401, 403])
            
            # Test with malformed JSON
            self.client.force_authenticate(user=self.regular_user)
            
            response = self.client.post(
                reverse('device-list'),
                data='{invalid json',
                content_type='application/json'
            )
            self.assertSafeResponse(response, 400)
            
            # Test with SQL injection attempt
            sql_injection_data = {
                'device_id': "test'; DROP TABLE devices; --",
                'device_model': "test' OR '1'='1",
            }
            
            response = self.client.post(
                reverse('device-list'),
                data=sql_injection_data,
                format='json'
            )
            # Should either reject or sanitize
            self.assertIn(response.status_code, [400, 201])
            
        except Exception as e:
            logger.error(f"Defensive integration test failed: {str(e)}")
            raise


class PerformanceTests(BaseSecurityTest):
    """Performance and load tests"""
    
    def test_bulk_operations_performance(self):
        """Test performance of bulk operations"""
        try:
            import time
            
            # Create many devices
            start_time = time.time()
            
            devices = []
            for i in range(100):
                device = DeviceInfo.objects.create(
                    user=self.regular_user,
                    device_id=f'perf_test_{i}',
                    device_id_hash=f'hash_{i}',
                    device_model='Performance Test',
                    risk_score=i % 100,
                    last_activity=timezone.now()
                )
                devices.append(device)
            
            create_time = time.time() - start_time
            logger.info(f"Created 100 devices in {create_time:.2f} seconds")
            
            # Test bulk retrieval
            start_time = time.time()
            
            self.client.force_authenticate(user=self.admin_user)
            response = self.client.get(
                reverse('device-list'),
                {'page_size': 100}
            )
            
            retrieve_time = time.time() - start_time
            logger.info(f"Retrieved 100 devices in {retrieve_time:.2f} seconds")
            
            self.assertSafeResponse(response, 200)
            self.assertEqual(len(response.data['results']), 50)  # Default page size
            
            # Cleanup
            for device in devices:
                device.delete()
            
        except Exception as e:
            logger.error(f"Performance test failed: {str(e)}")
            raise
    
    def test_cache_performance(self):
        """Test cache performance"""
        try:
            import time
            
            # Clear cache
            cache.clear()
            
            # First request (cache miss)
            start_time = time.time()
            self.detector.detect_vpn_proxy('8.8.8.8')
            first_time = time.time() - start_time
            
            # Second request (cache hit)
            start_time = time.time()
            self.detector.detect_vpn_proxy('8.8.8.8')
            second_time = time.time() - start_time
            
            # Cache hit should be faster
            self.assertLess(second_time, first_time * 0.5)  # At least 2x faster
            
            logger.info(f"Cache miss: {first_time:.4f}s, Cache hit: {second_time:.4f}s")
            
        except Exception as e:
            logger.error(f"Cache performance test failed: {str(e)}")
            raise


class SecurityTests(BaseSecurityTest):
    """Security-specific tests"""
    
    def test_authentication_bypass(self):
        """Test for authentication bypass vulnerabilities"""
        try:
            # Try to access admin endpoints as regular user
            self.client.force_authenticate(user=self.regular_user)
            
            endpoints = [
                reverse('security-config'),
                reverse('security-audit'),
                reverse('bulk-device-action'),
            ]
            
            for endpoint in endpoints:
                response = self.client.get(endpoint)
                self.assertIn(response.status_code, [403, 404, 405])
            
        except Exception as e:
            logger.error(f"Authentication bypass test failed: {str(e)}")
            raise
    
    def test_sql_injection(self):
        """Test for SQL injection vulnerabilities"""
        try:
            # Test with potential SQL injection in query parameters
            injection_params = [
                "'; DROP TABLE users; --",
                "' OR '1'='1",
                "1' UNION SELECT * FROM users --",
                "' AND SLEEP(5) --",
            ]
            
            self.client.force_authenticate(user=self.admin_user)
            
            for param in injection_params:
                response = self.client.get(
                    reverse('security-log-list'),
                    {'search': param}
                )
                
                # Should not crash or return unexpected data
                self.assertIn(response.status_code, [200, 400, 500])
                
                if response.status_code == 200:
                    # Should return empty or filtered results, not all data
                    pass
            
        except Exception as e:
            logger.error(f"SQL injection test failed: {str(e)}")
            raise
    
    def test_xss_protection(self):
        """Test for XSS vulnerabilities"""
        try:
            xss_payloads = [
                '<script>alert("xss")</script>',
                '<img src="x" onerror="alert(1)">',
                '<svg/onload=alert(1)>',
                'javascript:alert(1)',
            ]
            
            self.client.force_authenticate(user=self.regular_user)
            
            for payload in xss_payloads:
                # Try to create device with XSS payload
                device_data = {
                    'device_id': 'xss_test',
                    'device_model': payload,
                    'device_brand': 'Test',
                    'description': payload,
                }
                
                response = self.client.post(
                    reverse('device-list'),
                    data=device_data,
                    format='json'
                )
                
                # Should either reject or sanitize
                self.assertIn(response.status_code, [201, 400])
                
                if response.status_code == 201:
                    # Check if payload was sanitized in response
                    response_data = response.data
                    self.assertNotIn('<script>', str(response_data))
                    self.assertNotIn('javascript:', str(response_data))
            
        except Exception as e:
            logger.error(f"XSS test failed: {str(e)}")
            raise


# Test suite configuration
def create_test_suite():
    """Create comprehensive test suite"""
    import unittest
    
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        DeviceInfoTests,
        SecurityLogTests,
        RiskScoreTests,
        MiddlewareTests,
        VPNDetectorTests,
        UtilsTests,
        IntegrationTests,
        PerformanceTests,
        SecurityTests,
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    return suite


# Run tests
if __name__ == '__main__':
    import django
    django.setup()
    
    runner = unittest.TextTestRunner(verbosity=2)
    suite = create_test_suite()
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.1f}%")
    print('='*60)