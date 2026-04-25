"""
Cap Tests for Offer Routing System

This module contains unit tests for cap functionality,
including cap enforcement, overrides, and analytics.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from ..services.cap import CapEnforcementService, cap_service
from ..models import OfferRoutingCap, UserOfferCap, CapOverride
from ..exceptions import CapExceededError, CapError

User = get_user_model()


class CapEnforcementServiceTestCase(TestCase):
    """Test cases for CapEnforcementService."""
    
    def setUp(self):
        """Set up test data."""
        self.cap_service = CapEnforcementService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
        
        # Create test offer route
        from ..models import OfferRoute
        self.offer_route = OfferRoute.objects.create(
            name='Test Route',
            description='Test route for unit testing',
            tenant=self.tenant,
            priority=5,
            max_offers=10,
            is_active=True
        )
    
    def test_check_offer_cap_global(self):
        """Test checking global offer cap."""
        # Create global cap
        global_cap = OfferRoutingCap.objects.create(
            tenant=self.tenant,
            offer=self.offer_route,
            cap_type='daily',
            cap_value=100,
            current_count=50
        )
        
        result = self.cap_service.check_offer_cap(self.user, self.offer_route)
        
        self.assertIsInstance(result, dict)
        self.assertIn('cap_exceeded', result)
        self.assertIn('remaining_capacity', result)
        self.assertFalse(result['cap_exceeded'])
    
    def test_check_offer_cap_exceeded(self):
        """Test checking exceeded offer cap."""
        # Create global cap that's exceeded
        global_cap = OfferRoutingCap.objects.create(
            tenant=self.tenant,
            offer=self.offer_route,
            cap_type='daily',
            cap_value=100,
            current_count=100
        )
        
        result = self.cap_service.check_offer_cap(self.user, self.offer_route)
        
        self.assertTrue(result['cap_exceeded'])
        self.assertEqual(result['remaining_capacity'], 0)
    
    def test_check_offer_cap_user_specific(self):
        """Test checking user-specific offer cap."""
        # Create user cap
        user_cap = UserOfferCap.objects.create(
            user=self.user,
            offer=self.offer_route,
            cap_type='daily',
            max_shows_per_day=10,
            shown_today=5
        )
        
        result = self.cap_service.check_offer_cap(self.user, self.offer_route)
        
        self.assertFalse(result['cap_exceeded'])
        self.assertEqual(result['remaining_capacity'], 5)
    
    def test_increment_cap_usage(self):
        """Test incrementing cap usage."""
        # Create user cap
        user_cap = UserOfferCap.objects.create(
            user=self.user,
            offer=self.offer_route,
            cap_type='daily',
            max_shows_per_day=10,
            shown_today=5
        )
        
        success = self.cap_service.increment_cap_usage(self.user, self.offer_route)
        
        self.assertTrue(success)
        
        # Check if usage was incremented
        user_cap.refresh_from_db()
        self.assertEqual(user_cap.shown_today, 6)
    
    def test_increment_cap_usage_exceeded(self):
        """Test incrementing cap usage when exceeded."""
        # Create user cap that's at limit
        user_cap = UserOfferCap.objects.create(
            user=self.user,
            offer=self.offer_route,
            cap_type='daily',
            max_shows_per_day=5,
            shown_today=5
        )
        
        with self.assertRaises(CapExceededError):
            self.cap_service.increment_cap_usage(self.user, self.offer_route)
    
    def test_reset_daily_caps(self):
        """Test resetting daily caps."""
        # Create user caps
        UserOfferCap.objects.create(
            user=self.user,
            offer=self.offer_route,
            cap_type='daily',
            max_shows_per_day=10,
            shown_today=8
        )
        
        # Create global cap
        OfferRoutingCap.objects.create(
            tenant=self.tenant,
            offer=self.offer_route,
            cap_type='daily',
            cap_value=100,
            current_count=50
        )
        
        reset_count = self.cap_service.reset_daily_caps()
        
        self.assertIsInstance(reset_count, int)
        self.assertGreaterEqual(reset_count, 2)
        
        # Check if caps were reset
        user_cap = UserOfferCap.objects.get(user=self.user, offer=self.offer_route)
        self.assertEqual(user_cap.shown_today, 0)
        
        global_cap = OfferRoutingCap.objects.get(tenant=self.tenant, offer=self.offer_route)
        self.assertEqual(global_cap.current_count, 0)
    
    def test_apply_cap_override(self):
        """Test applying cap override."""
        # Create cap override
        override = CapOverride.objects.create(
            tenant=self.tenant,
            offer=self.offer_route,
            override_type='increase',
            override_cap=150,
            is_active=True,
            valid_from=timezone.now(),
            valid_to=timezone.now() + timezone.timedelta(days=1)
        )
        
        # Create global cap
        global_cap = OfferRoutingCap.objects.create(
            tenant=self.tenant,
            offer=self.offer_route,
            cap_type='daily',
            cap_value=100,
            current_count=80
        )
        
        original_cap = global_cap.cap_value
        new_cap = self.cap_service._apply_cap_override(global_cap.cap_value, override)
        
        self.assertEqual(new_cap, 150)
        self.assertGreater(new_cap, original_cap)
    
    def test_get_cap_analytics(self):
        """Test getting cap analytics."""
        # Create caps
        OfferRoutingCap.objects.create(
            tenant=self.tenant,
            offer=self.offer_route,
            cap_type='daily',
            cap_value=100,
            current_count=50
        )
        
        UserOfferCap.objects.create(
            user=self.user,
            offer=self.offer_route,
            cap_type='daily',
            max_shows_per_day=10,
            shown_today=5
        )
        
        analytics = self.cap_service.get_cap_analytics(
            tenant_id=self.tenant.id,
            days=30
        )
        
        self.assertIsInstance(analytics, dict)
        self.assertIn('global_caps', analytics)
        self.assertIn('user_caps', analytics)
        self.assertIn('overrides', analytics)
    
    def test_check_cap_health(self):
        """Test cap health checking."""
        # Create caps
        OfferRoutingCap.objects.create(
            tenant=self.tenant,
            offer=self.offer_route,
            cap_type='daily',
            cap_value=100,
            current_count=95  # Near limit
        )
        
        UserOfferCap.objects.create(
            user=self.user,
            offer=self.offer_route,
            cap_type='daily',
            max_shows_per_day=10,
            shown_today=10  # At limit
        )
        
        health_issues = self.cap_service.check_cap_health()
        
        self.assertIsInstance(health_issues, list)
    
    def test_cleanup_expired_overrides(self):
        """Test cleanup of expired overrides."""
        # Create expired override
        expired_override = CapOverride.objects.create(
            tenant=self.tenant,
            offer=self.offer_route,
            override_type='increase',
            override_cap=150,
            is_active=True,
            valid_from=timezone.now() - timezone.timedelta(days=2),
            valid_to=timezone.now() - timezone.timedelta(days=1)
        )
        
        # Create active override
        active_override = CapOverride.objects.create(
            tenant=self.tenant,
            offer=self.offer_route,
            override_type='increase',
            override_cap=150,
            is_active=True,
            valid_from=timezone.now(),
            valid_to=timezone.now() + timezone.timedelta(days=1)
        )
        
        deactivated_count = self.cap_service.cleanup_expired_overrides()
        
        self.assertIsInstance(deactivated_count, int)
        self.assertGreaterEqual(deactivated_count, 1)
        
        # Check if expired override was deactivated
        expired_override.refresh_from_db()
        self.assertFalse(expired_override.is_active)
        
        # Active override should still be active
        active_override.refresh_from_db()
        self.assertTrue(active_override.is_active)
    
    def test_get_original_cap_value(self):
        """Test getting original cap value."""
        # Create global cap
        global_cap = OfferRoutingCap.objects.create(
            tenant=self.tenant,
            offer=self.offer_route,
            cap_type='daily',
            cap_value=100,
            current_count=50
        )
        
        # Create user cap
        user_cap = UserOfferCap.objects.create(
            user=self.user,
            offer=self.offer_route,
            cap_type='daily',
            max_shows_per_day=10,
            shown_today=5
        )
        
        # Test global cap
        original_value = self.cap_service._get_original_cap_value(self.user, self.offer_route)
        
        self.assertEqual(original_value, 100)
        
        # Test user-specific cap (should take precedence)
        original_value = self.cap_service._get_original_cap_value(self.user, self.offer_route)
        
        self.assertEqual(original_value, 10)
    
    def test_validate_cap_configuration(self):
        """Test cap configuration validation."""
        # Valid configuration
        valid_config = {
            'cap_type': 'daily',
            'cap_value': 100,
            'is_active': True
        }
        
        is_valid, errors = self.cap_service._validate_cap_configuration(valid_config)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Invalid configuration
        invalid_config = {
            'cap_type': 'invalid_type',
            'cap_value': -10,
            'is_active': True
        }
        
        is_valid, errors = self.cap_service._validate_cap_configuration(invalid_config)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)


class CapIntegrationTestCase(TestCase):
    """Integration tests for cap functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test offers
        from ..models import OfferRoute
        self.offers = []
        for i in range(3):
            offer = OfferRoute.objects.create(
                name=f'Test Route {i}',
                description=f'Test route {i} for integration testing',
                tenant=self.user,
                priority=i + 1,
                max_offers=10,
                is_active=True
            )
            self.offers.append(offer)
    
    def test_cap_workflow(self):
        """Test complete cap workflow."""
        # Create global caps
        for offer in self.offers:
            OfferRoutingCap.objects.create(
                tenant=self.user,
                offer=offer,
                cap_type='daily',
                cap_value=100,
                current_count=0
            )
        
        # Create user caps
        for offer in self.offers:
            UserOfferCap.objects.create(
                user=self.user,
                offer=offer,
                cap_type='daily',
                max_shows_per_day=10,
                shown_today=0
            )
        
        # Check caps
        for offer in self.offers:
            result = cap_service.check_offer_cap(self.user, offer)
            
            self.assertFalse(result['cap_exceeded'])
            self.assertGreater(result['remaining_capacity'], 0)
        
        # Increment usage
        for offer in self.offers:
            cap_service.increment_cap_usage(self.user, offer)
        
        # Check usage was incremented
        for offer in self.offers:
            user_cap = UserOfferCap.objects.get(user=self.user, offer=offer)
            self.assertEqual(user_cap.shown_today, 1)
    
    def test_cap_with_overrides(self):
        """Test caps with overrides."""
        # Create global cap
        global_cap = OfferRoutingCap.objects.create(
            tenant=self.user,
            offer=self.offers[0],
            cap_type='daily',
            cap_value=50,
            current_count=30
        )
        
        # Create override
        override = CapOverride.objects.create(
            tenant=self.user,
            offer=self.offers[0],
            override_type='increase',
            override_cap=100,
            is_active=True,
            valid_from=timezone.now(),
            valid_to=timezone.now() + timezone.timedelta(days=1)
        )
        
        result = cap_service.check_offer_cap(self.user, self.offers[0])
        
        # Should have increased capacity due to override
        self.assertGreater(result['remaining_capacity'], 20)
    
    def test_cap_enforcement(self):
        """Test cap enforcement."""
        # Create user cap with low limit
        user_cap = UserOfferCap.objects.create(
            user=self.user,
            offer=self.offers[0],
            cap_type='daily',
            max_shows_per_day=3,
            shown_today=3
        )
        
        # Should raise exception when trying to increment
        with self.assertRaises(CapExceededError):
            cap_service.increment_cap_usage(self.user, self.offers[0])
    
    def test_daily_reset(self):
        """Test daily cap reset."""
        # Create user caps
        for offer in self.offers:
            UserOfferCap.objects.create(
                user=self.user,
                offer=offer,
                cap_type='daily',
                max_shows_per_day=10,
                shown_today=8
            )
        
        # Reset caps
        reset_count = cap_service.reset_daily_caps()
        
        self.assertGreaterEqual(reset_count, len(self.offers))
        
        # Check if caps were reset
        for offer in self.offers:
            user_cap = UserOfferCap.objects.get(user=self.user, offer=offer)
            self.assertEqual(user_cap.shown_today, 0)
    
    def test_cap_analytics_integration(self):
        """Test cap analytics integration."""
        # Create caps with different usage levels
        OfferRoutingCap.objects.create(
            tenant=self.user,
            offer=self.offers[0],
            cap_type='daily',
            cap_value=100,
            current_count=80  # High usage
        )
        
        OfferRoutingCap.objects.create(
            tenant=self.user,
            offer=self.offers[1],
            cap_type='daily',
            cap_value=100,
            current_count=20  # Low usage
        )
        
        UserOfferCap.objects.create(
            user=self.user,
            offer=self.offers[0],
            cap_type='daily',
            max_shows_per_day=10,
            shown_today=8  # Near limit
        )
        
        UserOfferCap.objects.create(
            user=self.user,
            offer=self.offers[1],
            cap_type='daily',
            max_shows_per_day=10,
            shown_today=2  # Low usage
        )
        
        # Create override
        CapOverride.objects.create(
            tenant=self.user,
            offer=self.offers[0],
            override_type='increase',
            override_cap=150,
            is_active=True,
            valid_from=timezone.now(),
            valid_to=timezone.now() + timezone.timedelta(days=1)
        )
        
        analytics = cap_service.get_cap_analytics(
            tenant_id=self.user.id,
            days=30
        )
        
        self.assertIsInstance(analytics, dict)
        self.assertIn('global_caps', analytics)
        self.assertIn('user_caps', analytics)
        self.assertIn('overrides', analytics)
    
    def test_cap_performance(self):
        """Test cap performance."""
        import time
        
        # Create caps
        for offer in self.offers:
            OfferRoutingCap.objects.create(
                tenant=self.user,
                offer=offer,
                cap_type='daily',
                cap_value=100,
                current_count=50
            )
            
            UserOfferCap.objects.create(
                user=self.user,
                offer=offer,
                cap_type='daily',
                max_shows_per_day=10,
                shown_today=5
            )
        
        # Measure cap checking time
        start_time = time.time()
        
        for offer in self.offers:
            cap_service.check_offer_cap(self.user, offer)
        
        end_time = time.time()
        cap_check_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(cap_check_time, 100)  # Within 100ms
    
    def test_cap_error_handling(self):
        """Test error handling in cap functionality."""
        # Test with invalid offer
        with self.assertRaises(Exception):
            cap_service.check_offer_cap(self.user, None)
        
        # Test with invalid user
        with self.assertRaises(Exception):
            cap_service.check_offer_cap(None, self.offers[0])
        
        # Test increment with invalid data
        with self.assertRaises(Exception):
            cap_service.increment_cap_usage(self.user, None)
