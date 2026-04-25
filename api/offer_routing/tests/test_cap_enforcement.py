"""
Test Cap Enforcement

Tests for the cap enforcement service
to ensure it works correctly.
"""

import logging
import pytest
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch
from ..services.cap import CapEnforcementService
from ..models import OfferRoutingCap, UserOfferCap, UserOfferHistory
from ..constants import DEFAULT_ROUTING_LIMIT

logger = logging.getLogger(__name__)

User = get_user_model()


class TestCapEnforcement(TestCase):
    """Test cases for CapEnforcementService."""
    
    def setUp(self):
        """Set up test environment."""
        self.cap_service = CapEnforcementService()
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            is_active=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        User.objects.filter(id=self.test_user.id).delete()
    
    def test_check_global_cap_basic(self):
        """Test basic global cap checking."""
        try:
            # Create test global cap
            cap = OfferRoutingCap.objects.create(
                name='Test Global Cap',
                cap_type='daily',
                max_offers=10,
                is_active=True
            )
            
            # Create test user history
            UserOfferHistory.objects.create(
                user=self.test_user,
                offer_id=1,
                created_at=timezone.now()
            )
            
            # Mock cache service
            with patch('..services.cache.cache_service') as mock_cache:
                mock_cache.get.return_value = None
                
                # Check global cap
                result = self.cap_service.check_global_cap(
                    cap_id=cap.id,
                    user_id=self.test_user.id
                )
                
                # Assertions
                self.assertTrue(result['can_show'])
                self.assertEqual(result['remaining_offers'], 9)
                self.assertEqual(result['cap_id'], cap.id)
                self.assertEqual(result['cap_type'], 'daily')
                self.assertEqual(result['max_offers'], 10)
                
        except Exception as e:
            self.fail(f"Error in test_check_global_cap_basic: {e}")
    
    def test_check_global_cap_exceeded(self):
        """Test global cap when exceeded."""
        try:
            # Create test global cap
            cap = OfferRoutingCap.objects.create(
                name='Test Global Cap',
                cap_type='daily',
                max_offers=5,
                is_active=True
            )
            
            # Create test user history exceeding cap
            for i in range(6):
                UserOfferHistory.objects.create(
                    user=self.test_user,
                    offer_id=1,
                    created_at=timezone.now()
                )
            
            # Mock cache service
            with patch('..services.cache.cache_service') as mock_cache:
                mock_cache.get.return_value = None
                
                # Check global cap
                result = self.cap_service.check_global_cap(
                    cap_id=cap.id,
                    user_id=self.test_user.id
                )
                
                # Assertions
                self.assertFalse(result['can_show'])
                self.assertEqual(result['remaining_offers'], 0)
                self.assertEqual(result['reason'], 'Global daily cap exceeded')
                
        except Exception as e:
            self.fail(f"Error in test_check_global_cap_exceeded: {e}")
    
    def test_check_user_cap_basic(self):
        """Test basic user cap checking."""
        try:
            # Create test user cap
            cap = UserOfferCap.objects.create(
                user=self.test_user,
                cap_type='daily',
                max_offers=10,
                is_active=True
            )
            
            # Create test user history
            UserOfferHistory.objects.create(
                user=self.test_user,
                offer_id=1,
                created_at=timezone.now()
            )
            
            # Mock cache service
            with patch('..services.cache.cache_service') as mock_cache:
                mock_cache.get.return_value = None
                
                # Check user cap
                result = self.cap_service.check_user_cap(
                    cap_id=cap.id,
                    user_id=self.test_user.id
                )
                
                # Assertions
                self.assertTrue(result['can_show'])
                self.assertEqual(result['remaining_offers'], 9)
                self.assertEqual(result['cap_id'], cap.id)
                self.assertEqual(result['cap_type'], 'daily')
                self.assertEqual(result['max_offers'], 10)
                
        except Exception as e:
            self.fail(f"Error in test_check_user_cap_basic: {e}")
    
    def test_check_user_cap_exceeded(self):
        """Test user cap when exceeded."""
        try:
            # Create test user cap
            cap = UserOfferCap.objects.create(
                user=self.test_user,
                cap_type='daily',
                max_offers=5,
                is_active=True
            )
            
            # Create test user history exceeding cap
            for i in range(6):
                UserOfferHistory.objects.create(
                    user=self.test_user,
                    offer_id=1,
                    created_at=timezone.now()
                )
            
            # Mock cache service
            with patch('..services.cache.cache_service') as mock_cache:
                mock_cache.get.return_value = None
                
                # Check user cap
                result = self.cap_service.check_user_cap(
                    cap_id=cap.id,
                    user_id=self.test_user.id
                )
                
                # Assertions
                self.assertFalse(result['can_show'])
                self.assertEqual(result['remaining_offers'], 0)
                self.assertEqual(result['reason'], 'User daily cap exceeded')
                
        except Exception as e:
            self.fail(f"Error in test_check_user_cap_exceeded: {e}")
    
    def test_check_cap_with_cache_hit(self):
        """Test cap checking with cache hit."""
        try:
            # Create test user cap
            cap = UserOfferCap.objects.create(
                user=self.test_user,
                cap_type='daily',
                max_offers=10,
                is_active=True
            )
            
            # Mock cache service to return cached count
            with patch('..services.cache.cache_service') as mock_cache:
                mock_cache.get.return_value = {
                    'count': 3,
                    'timestamp': timezone.now().isoformat()
                }
                
                # Check user cap
                result = self.cap_service.check_user_cap(
                    cap_id=cap.id,
                    user_id=self.test_user.id
                )
                
                # Assertions
                self.assertTrue(result['can_show'])
                self.assertEqual(result['remaining_offers'], 7)
                self.assertEqual(result['cached'], True)
                mock_cache.get.assert_called_once()
                
        except Exception as e:
            self.fail(f"Error in test_check_cap_with_cache_hit: {e}")
    
    def test_increment_cap_usage_basic(self):
        """Test basic cap usage increment."""
        try:
            # Create test user cap
            cap = UserOfferCap.objects.create(
                user=self.test_user,
                cap_type='daily',
                max_offers=10,
                daily_count=5,
                is_active=True
            )
            
            # Increment usage
            result = self.cap_service.increment_cap_usage(
                cap_id=cap.id,
                increment=1
            )
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['new_count'], 6)
            
            # Verify cap was updated
            updated_cap = UserOfferCap.objects.get(id=cap.id)
            self.assertEqual(updated_cap.daily_count, 6)
            
        except Exception as e:
            self.fail(f"Error in test_increment_cap_usage_basic: {e}")
    
    def test_reset_cap_usage_basic(self):
        """Test basic cap usage reset."""
        try:
            # Create test user cap
            cap = UserOfferCap.objects.create(
                user=self.test_user,
                cap_type='daily',
                max_offers=10,
                daily_count=5,
                is_active=True
            )
            
            # Reset usage
            result = self.cap_service.reset_cap_usage(
                cap_id=cap.id,
                cap_type='daily'
            )
            
            # Assertions
            self.assertTrue(result['success'])
            
            # Verify cap was reset
            updated_cap = UserOfferCap.objects.get(id=cap.id)
            self.assertEqual(updated_cap.daily_count, 0)
            
        except Exception as e:
            self.fail(f"Error in test_reset_cap_usage_basic: {e}")
    
    def test_get_cap_status_basic(self):
        """Test basic cap status retrieval."""
        try:
            # Create test user caps
            caps = [
                UserOfferCap.objects.create(
                    user=self.test_user,
                    cap_type='daily',
                    max_offers=10,
                    daily_count=5,
                    is_active=True
                ),
                UserOfferCap.objects.create(
                    user=self.test_user,
                    cap_type='weekly',
                    max_offers=50,
                    weekly_count=20,
                    is_active=True
                )
            ]
            
            # Get cap status
            result = self.cap_service.get_cap_status(self.test_user.id)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(len(result['caps']), 2)
            
            # Verify cap data
            cap_data = {cap['cap_type']: cap for cap in result['caps']}
            self.assertEqual(cap_data['daily']['max_offers'], 10)
            self.assertEqual(cap_data['daily']['current_count'], 5)
            self.assertEqual(cap_data['weekly']['max_offers'], 50)
            self.assertEqual(cap_data['weekly']['current_count'], 20)
            
        except Exception as e:
            self.fail(f"Error in test_get_cap_status_basic: {e}")
    
    def test_check_cap_override_basic(self):
        """Test basic cap override checking."""
        try:
            # Create test cap override
            override = CapOverride.objects.create(
                user=self.test_user,
                cap_type='daily',
                override_value=20,
                reason='Test override',
                is_active=True
            )
            
            # Create test user cap
            cap = UserOfferCap.objects.create(
                user=self.test_user,
                cap_type='daily',
                max_offers=10,
                daily_count=5,
                is_active=True
            )
            
            # Check cap with override
            result = self.cap_service.check_cap_with_override(
                cap_id=cap.id,
                user_id=self.test_user.id
            )
            
            # Assertions
            self.assertTrue(result['can_show'])
            self.assertEqual(result['remaining_offers'], 15)  # Override allows 20 instead of 10
            self.assertTrue(result['has_override'])
            self.assertEqual(result['override_value'], 20)
            
        except Exception as e:
            self.fail(f"Error in test_check_cap_override_basic: {e}")
    
    def test_validate_cap_config_basic(self):
        """Test basic cap configuration validation."""
        try:
            # Test valid configuration
            valid_config = {
                'cap_type': 'daily',
                'max_offers': 10,
                'is_active': True
            }
            
            result = self.cap_service.validate_cap_config(valid_config)
            
            # Assertions
            self.assertTrue(result['valid'])
            self.assertEqual(len(result['errors']), 0)
            
        except Exception as e:
            self.fail(f"Error in test_validate_cap_config_basic: {e}")
    
    def test_validate_cap_config_invalid(self):
        """Test invalid cap configuration validation."""
        try:
            # Test invalid configuration
            invalid_config = {
                'cap_type': 'invalid_type',  # Invalid cap type
                'max_offers': -5,  # Negative max offers
                'is_active': True
            }
            
            result = self.cap_service.validate_cap_config(invalid_config)
            
            # Assertions
            self.assertFalse(result['valid'])
            self.assertIn('cap_type', result['errors'])
            self.assertIn('max_offers', result['errors'])
            
        except Exception as e:
            self.fail(f"Error in test_validate_cap_config_invalid: {e}")
    
    def test_health_check(self):
        """Test cap enforcement service health check."""
        try:
            # Mock cache service
            with patch('..services.cache.cache_service') as mock_cache:
                mock_cache.health_check.return_value = {'status': 'healthy'}
                
                # Test health check
                health = self.cap_service.health_check()
                
                # Assertions
                self.assertIsInstance(health, dict)
                self.assertIn('status', health)
                self.assertIn('timestamp', health)
                self.assertIn('cache_status', health)
                self.assertIn('performance_stats', health)
                
        except Exception as e:
            self.fail(f"Error in test_health_check: {e}")
    
    def test_performance_under_load(self):
        """Test cap enforcement performance under load."""
        try:
            # Create many test caps
            caps = []
            for i in range(100):
                caps.append(UserOfferCap.objects.create(
                    user=self.test_user,
                    cap_type='daily',
                    max_offers=10,
                    daily_count=i,
                    is_active=True
                ))
            
            # Mock cache service
            with patch('..services.cache.cache_service') as mock_cache:
                mock_cache.get.return_value = None
                
                # Measure performance
                start_time = timezone.now()
                
                # Check caps for all users
                for cap in caps:
                    self.cap_service.check_user_cap(
                        cap_id=cap.id,
                        user_id=self.test_user.id
                    )
                
                elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
                
                # Assertions
                self.assertLess(elapsed_ms, 5000)  # Should complete in under 5 seconds
                
        except Exception as e:
            self.fail(f"Error in test_performance_under_load: {e}")


if __name__ == '__main__':
    pytest.main()
