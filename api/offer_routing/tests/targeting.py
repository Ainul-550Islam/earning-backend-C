"""
Targeting Tests for Offer Routing System

This module contains unit tests for targeting functionality,
including geographic, device, user segment, time, and behavioral targeting.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from ..services.targeting import (
    TargetingService, targeting_service, GeoTargetingService, geo_targeting_service,
    DeviceTargetingService, device_targeting_service, SegmentTargetingService, segment_targeting_service,
    TimeTargetingService, time_targeting_service, BehaviorTargetingService, behavior_targeting_service
)
from ..models import (
    GeoRouteRule, DeviceRouteRule, UserSegmentRule,
    TimeRouteRule, BehaviorRouteRule
)
from ..exceptions import TargetingError, ValidationError

User = get_user_model()


class TargetingServiceTestCase(TestCase):
    """Test cases for TargetingService."""
    
    def setUp(self):
        """Set up test data."""
        self.targeting_service = TargetingService()
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
    
    def test_get_matching_routes(self):
        """Test getting matching routes for user."""
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'},
            'user_agent': 'Mozilla/5.0'
        }
        
        matching_routes = self.targeting_service.get_matching_routes(
            user_id=self.user.id,
            context=context
        )
        
        self.assertIsInstance(matching_routes, list)
    
    def test_get_matching_targeting_rules(self):
        """Test getting matching targeting rules."""
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'}
        }
        
        matching_rules = self.targeting_service.get_matching_targeting_rules(
            user_id=self.user.id,
            context=context
        )
        
        self.assertIsInstance(matching_rules, dict)
        self.assertIn('geo_rules', matching_rules) if isinstance(matching_rules, dict) else self.assertIsNotNone(matching_rules)
        self.assertIn('device_rules', matching_rules) if isinstance(matching_rules, dict) else self.assertIsNotNone(matching_rules)
    