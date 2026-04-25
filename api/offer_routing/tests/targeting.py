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
        self.assertIn('geo_rules', matching_rules)
        self.assertIn('device_rules', matching_rules)
    
    def test_update_targeting_data(self):
        """Test updating targeting data."""
        targeting_data = {
            'geo_data': {'country': 'US'},
            'device_data': {'type': 'desktop'},
            'segment_data': {'tier': 'premium'},
            'behavior_data': {'recent_views': 5}
        }
        
        success = self.targeting_service.update_targeting_data(
            user_id=self.user.id,
            targeting_data=targeting_data
        )
        
        self.assertTrue(success)
    
    def test_validate_targeting_rules(self):
        """Test targeting rule validation."""
        # Create a targeting rule
        geo_rule = GeoRouteRule.objects.create(
            route=self.offer_route,
            country='US',
            is_include=True
        )
        
        validation_result = self.targeting_service.validate_targeting_rules(
            route_id=self.offer_route.id
        )
        
        self.assertIsInstance(validation_result, dict)
        self.assertIn('is_valid', validation_result)
    
    def test_get_targeting_analytics(self):
        """Test getting targeting analytics."""
        analytics = self.targeting_service.get_targeting_analytics(
            user_id=self.user.id,
            days=30
        )
        
        self.assertIsInstance(analytics, dict)
    
    def test_cleanup_expired_rules(self):
        """Test cleanup of expired targeting rules."""
        # Create expired time rule
        expired_rule = TimeRouteRule.objects.create(
            route=self.offer_route,
            start_time=timezone.now() - timezone.timedelta(days=10),
            end_time=timezone.now() - timezone.timedelta(days=5),
            is_include=True
        )
        
        cleaned_count = self.targeting_service.cleanup_expired_rules()
        
        self.assertIsInstance(cleaned_count, int)
        self.assertGreaterEqual(cleaned_count, 0)


class GeoTargetingServiceTestCase(TestCase):
    """Test cases for GeoTargetingService."""
    
    def setUp(self):
        """Set up test data."""
        self.geo_targeting_service = GeoTargetingService()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test offer route
        from ..models import OfferRoute
        self.offer_route = OfferRoute.objects.create(
            name='Test Route',
            description='Test route for unit testing',
            tenant=self.user,
            priority=5,
            max_offers=10,
            is_active=True
        )
    
    def test_matches_geo_rule_include(self):
        """Test geo rule matching for include rule."""
        rule = GeoRouteRule.objects.create(
            route=self.offer_route,
            country='US',
            is_include=True
        )
        
        location = {'country': 'US'}
        
        matches = self.geo_targeting_service._matches_geo_rule(rule, location)
        
        self.assertTrue(matches)
    
    def test_matches_geo_rule_exclude(self):
        """Test geo rule matching for exclude rule."""
        rule = GeoRouteRule.objects.create(
            route=self.offer_route,
            country='US',
            is_include=False
        )
        
        location = {'country': 'US'}
        
        matches = self.geo_targeting_service._matches_geo_rule(rule, location)
        
        self.assertFalse(matches)
    
    def test_matches_geo_rule_multiple_countries(self):
        """Test geo rule matching with multiple countries."""
        rule = GeoRouteRule.objects.create(
            route=self.offer_route,
            country='US,CA,GB',
            is_include=True
        )
        
        location = {'country': 'US'}
        
        matches = self.geo_targeting_service._matches_geo_rule(rule, location)
        
        self.assertTrue(matches)
    
    def test_get_matching_geo_rules(self):
        """Test getting matching geo rules."""
        # Create geo rules
        GeoRouteRule.objects.create(
            route=self.offer_route,
            country='US',
            is_include=True
        )
        
        GeoRouteRule.objects.create(
            route=self.offer_route,
            country='CA',
            is_include=False
        )
        
        location = {'country': 'US'}
        
        matching_rules = self.geo_targeting_service.get_matching_geo_rules(
            route=self.offer_route,
            location=location
        )
        
        self.assertIsInstance(matching_rules, list)
    
    def test_parse_ip_address(self):
        """Test IP address parsing."""
        ip_address = '192.168.1.1'
        
        location = self.geo_targeting_service._parse_ip_address(ip_address)
        
        self.assertIsInstance(location, dict)
        self.assertIn('country', location)
    
    def test_normalize_country_code(self):
        """Test country code normalization."""
        test_cases = [
            ('US', 'US'),
            ('USA', 'US'),
            ('us', 'US'),
            ('GB', 'GB'),
            ('UK', 'GB')
        ]
        
        for input_code, expected_code in test_cases:
            normalized = self.geo_targeting_service._normalize_country_code(input_code)
            self.assertEqual(normalized, expected_code)


class DeviceTargetingServiceTestCase(TestCase):
    """Test cases for DeviceTargetingService."""
    
    def setUp(self):
        """Set up test data."""
        self.device_targeting_service = DeviceTargetingService()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test offer route
        from ..models import OfferRoute
        self.offer_route = OfferRoute.objects.create(
            name='Test Route',
            description='Test route for unit testing',
            tenant=self.user,
            priority=5,
            max_offers=10,
            is_active=True
        )
    
    def test_matches_device_rule(self):
        """Test device rule matching."""
        rule = DeviceRouteRule.objects.create(
            route=self.offer_route,
            device_type='desktop',
            is_include=True
        )
        
        device = {'type': 'desktop', 'os': 'Windows'}
        
        matches = self.device_targeting_service._matches_device_rule(rule, device)
        
        self.assertTrue(matches)
    
    def test_matches_device_rule_exclude(self):
        """Test device rule matching for exclude."""
        rule = DeviceRouteRule.objects.create(
            route=self.offer_route,
            device_type='mobile',
            is_include=False
        )
        
        device = {'type': 'desktop', 'os': 'Windows'}
        
        matches = self.device_targeting_service._matches_device_rule(rule, device)
        
        self.assertTrue(matches)  # Should match because it's not mobile
    
    def test_get_matching_device_rules(self):
        """Test getting matching device rules."""
        # Create device rules
        DeviceRouteRule.objects.create(
            route=self.offer_route,
            device_type='desktop',
            is_include=True
        )
        
        DeviceRouteRule.objects.create(
            route=self.offer_route,
            os_type='Windows',
            is_include=True
        )
        
        device = {'type': 'desktop', 'os': 'Windows'}
        
        matching_rules = self.device_targeting_service.get_matching_device_rules(
            route=self.offer_route,
            device=device
        )
        
        self.assertIsInstance(matching_rules, list)
    
    def test_parse_user_agent(self):
        """Test user agent parsing."""
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        
        device_info = self.device_targeting_service._parse_user_agent(user_agent)
        
        self.assertIsInstance(device_info, dict)
        self.assertIn('type', device_info)
        self.assertIn('os', device_info)


class SegmentTargetingServiceTestCase(TestCase):
    """Test cases for SegmentTargetingService."""
    
    def setUp(self):
        """Set up test data."""
        self.segment_targeting_service = SegmentTargetingService()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test offer route
        from ..models import OfferRoute
        self.offer_route = OfferRoute.objects.create(
            name='Test Route',
            description='Test route for unit testing',
            tenant=self.user,
            priority=5,
            max_offers=10,
            is_active=True
        )
    
    def test_matches_segment_rule(self):
        """Test segment rule matching."""
        rule = UserSegmentRule.objects.create(
            route=self.offer_route,
            segment_type='tier',
            segment_value='premium',
            operator='equals',
            is_include=True
        )
        
        # Add segment info to user (mock)
        segment_info = {'tier': 'premium'}
        
        matches = self.segment_targeting_service._matches_segment_rule(
            rule, self.user, segment_info
        )
        
        self.assertTrue(matches)
    
    def test_matches_segment_rule_not_equals(self):
        """Test segment rule matching with not equals operator."""
        rule = UserSegmentRule.objects.create(
            route=self.offer_route,
            segment_type='tier',
            segment_value='basic',
            operator='not_equals',
            is_include=True
        )
        
        segment_info = {'tier': 'premium'}
        
        matches = self.segment_targeting_service._matches_segment_rule(
            rule, self.user, segment_info
        )
        
        self.assertTrue(matches)
    
    def test_get_matching_segment_rules(self):
        """Test getting matching segment rules."""
        # Create segment rules
        UserSegmentRule.objects.create(
            route=self.offer_route,
            segment_type='tier',
            segment_value='premium',
            operator='equals',
            is_include=True
        )
        
        UserSegmentRule.objects.create(
            route=self.offer_route,
            segment_type='new_user',
            segment_value=True,
            operator='equals',
            is_include=False
        )
        
        segment_info = {'tier': 'premium', 'new_user': False}
        
        matching_rules = self.segment_targeting_service.get_matching_segment_rules(
            route=self.offer_route,
            user=self.user,
            segment_info=segment_info
        )
        
        self.assertIsInstance(matching_rules, list)
    
    def test_get_user_segment_info(self):
        """Test getting user segment information."""
        segment_info = self.segment_targeting_service.get_user_segment_info(self.user.id)
        
        self.assertIsInstance(segment_info, dict)
    
    def test_update_user_segments(self):
        """Test updating user segments."""
        segment_data = {
            'tier': 'premium',
            'new_user': False,
            'active_user': True
        }
        
        success = self.segment_targeting_service.update_user_segments(
            user_id=self.user.id,
            segment_data=segment_data
        )
        
        self.assertTrue(success)


class TimeTargetingServiceTestCase(TestCase):
    """Test cases for TimeTargetingService."""
    
    def setUp(self):
        """Set up test data."""
        self.time_targeting_service = TimeTargetingService()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test offer route
        from ..models import OfferRoute
        self.offer_route = OfferRoute.objects.create(
            name='Test Route',
            description='Test route for unit testing',
            tenant=self.user,
            priority=5,
            max_offers=10,
            is_active=True
        )
    
    def test_matches_time_rule_active(self):
        """Test time rule matching when rule is active."""
        rule = TimeRouteRule.objects.create(
            route=self.offer_route,
            start_time=timezone.now() - timezone.timedelta(hours=1),
            end_time=timezone.now() + timezone.timedelta(hours=1),
            is_include=True
        )
        
        matches = self.time_targeting_service._matches_time_rule(rule)
        
        self.assertTrue(matches)
    
    def test_matches_time_rule_inactive(self):
        """Test time rule matching when rule is inactive."""
        rule = TimeRouteRule.objects.create(
            route=self.offer_route,
            start_time=timezone.now() - timezone.timedelta(hours=2),
            end_time=timezone.now() - timezone.timedelta(hours=1),
            is_include=True
        )
        
        matches = self.time_targeting_service._matches_time_rule(rule)
        
        self.assertFalse(matches)
    
    def test_matches_time_rule_hours(self):
        """Test time rule matching with hours."""
        current_hour = timezone.now().hour
        
        rule = TimeRouteRule.objects.create(
            route=self.offer_route,
            start_hour=current_hour - 1,
            end_hour=current_hour + 1,
            is_include=True
        )
        
        matches = self.time_targeting_service._matches_time_rule(rule)
        
        self.assertTrue(matches)
    
    def test_get_matching_time_rules(self):
        """Test getting matching time rules."""
        # Create time rules
        TimeRouteRule.objects.create(
            route=self.offer_route,
            start_time=timezone.now() - timezone.timedelta(hours=1),
            end_time=timezone.now() + timezone.timedelta(hours=1),
            is_include=True
        )
        
        TimeRouteRule.objects.create(
            route=self.offer_route,
            start_hour=9,
            end_hour=17,
            is_include=True
        )
        
        matching_rules = self.time_targeting_service.get_matching_time_rules(
            route=self.offer_route
        )
        
        self.assertIsInstance(matching_rules, list)
    
    def test_is_in_time_range(self):
        """Test time range checking."""
        current_time = timezone.now()
        
        # Test within range
        start_time = current_time - timezone.timedelta(hours=1)
        end_time = current_time + timezone.timedelta(hours=1)
        
        in_range = self.time_targeting_service._is_in_time_range(
            current_time, start_time, end_time
        )
        
        self.assertTrue(in_range)
        
        # Test outside range
        start_time = current_time + timezone.timedelta(hours=2)
        end_time = current_time + timezone.timedelta(hours=3)
        
        in_range = self.time_targeting_service._is_in_time_range(
            current_time, start_time, end_time
        )
        
        self.assertFalse(in_range)


class BehaviorTargetingServiceTestCase(TestCase):
    """Test cases for BehaviorTargetingService."""
    
    def setUp(self):
        """Set up test data."""
        self.behavior_targeting_service = BehaviorTargetingService()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test offer route
        from ..models import OfferRoute
        self.offer_route = OfferRoute.objects.create(
            name='Test Route',
            description='Test route for unit testing',
            tenant=self.user,
            priority=5,
            max_offers=10,
            is_active=True
        )
    
    def test_matches_behavior_rule(self):
        """Test behavior rule matching."""
        rule = BehaviorRouteRule.objects.create(
            route=self.offer_route,
            event_type='offer_view',
            event_count_min=5,
            time_period_hours=24,
            is_include=True
        )
        
        # Mock user events
        user_events = [
            {'event_type': 'offer_view', 'timestamp': timezone.now()}
            for _ in range(5)
        ]
        
        matches = self.behavior_targeting_service._matches_behavior_rule(
            rule, user_events
        )
        
        self.assertTrue(matches)
    
    def test_get_user_events(self):
        """Test getting user events."""
        events = self.behavior_targeting_service._get_user_events(self.user)
        
        self.assertIsInstance(events, list)
    
    def test_get_matching_behavior_rules(self):
        """Test getting matching behavior rules."""
        # Create behavior rules
        BehaviorRouteRule.objects.create(
            route=self.offer_route,
            event_type='offer_view',
            event_count_min=3,
            time_period_hours=24,
            is_include=True
        )
        
        BehaviorRouteRule.objects.create(
            route=self.offer_route,
            event_type='offer_click',
            event_count_max=2,
            time_period_hours=24,
            is_include=False
        )
        
        matching_rules = self.behavior_targeting_service.get_matching_behavior_rules(
            route=self.offer_route,
            user=self.user
        )
        
        self.assertIsInstance(matching_rules, list)
    
    def test_filter_events_by_type(self):
        """Test filtering events by type."""
        events = [
            {'event_type': 'offer_view', 'timestamp': timezone.now()},
            {'event_type': 'offer_click', 'timestamp': timezone.now()},
            {'event_type': 'offer_view', 'timestamp': timezone.now()},
        ]
        
        filtered_events = self.behavior_targeting_service._filter_events_by_type(
            events, 'offer_view'
        )
        
        self.assertEqual(len(filtered_events), 2)
        for event in filtered_events:
            self.assertEqual(event['event_type'], 'offer_view')
    
    def test_count_events_in_period(self):
        """Test counting events in time period."""
        now = timezone.now()
        events = [
            {'event_type': 'offer_view', 'timestamp': now},
            {'event_type': 'offer_view', 'timestamp': now - timezone.timedelta(hours=1)},
            {'event_type': 'offer_view', 'timestamp': now - timezone.timedelta(hours=25)},
        ]
        
        count = self.behavior_targeting_service._count_events_in_period(
            events, 24  # 24 hours
        )
        
        self.assertEqual(count, 2)


class TargetingIntegrationTestCase(TestCase):
    """Integration tests for targeting functionality."""
    
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
    
    def test_targeting_workflow(self):
        """Test complete targeting workflow."""
        # Create targeting rules for first offer
        GeoRouteRule.objects.create(
            route=self.offers[0],
            country='US',
            is_include=True
        )
        
        DeviceRouteRule.objects.create(
            route=self.offers[0],
            device_type='desktop',
            is_include=True
        )
        
        UserSegmentRule.objects.create(
            route=self.offers[0],
            segment_type='tier',
            segment_value='premium',
            operator='equals',
            is_include=True
        )
        
        # Test targeting
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop', 'os': 'Windows'},
            'user_agent': 'Mozilla/5.0'
        }
        
        matching_routes = targeting_service.get_matching_routes(
            user_id=self.user.id,
            context=context
        )
        
        self.assertIsInstance(matching_routes, list)
    
    def test_geo_targeting_integration(self):
        """Test geographic targeting integration."""
        # Create geo rules
        GeoRouteRule.objects.create(
            route=self.offers[0],
            country='US',
            is_include=True
        )
        
        GeoRouteRule.objects.create(
            route=self.offers[1],
            country='CA',
            is_include=True
        )
        
        location = {'country': 'US'}
        
        matching_rules = geo_targeting_service.get_matching_geo_rules(
            route=self.offers[0],
            location=location
        )
        
        self.assertIsInstance(matching_rules, list)
        self.assertGreater(len(matching_rules), 0)
    
    def test_device_targeting_integration(self):
        """Test device targeting integration."""
        # Create device rules
        DeviceRouteRule.objects.create(
            route=self.offers[0],
            device_type='desktop',
            is_include=True
        )
        
        DeviceRouteRule.objects.create(
            route=self.offers[0],
            os_type='Windows',
            is_include=True
        )
        
        device = {'type': 'desktop', 'os': 'Windows'}
        
        matching_rules = device_targeting_service.get_matching_device_rules(
            route=self.offers[0],
            device=device
        )
        
        self.assertIsInstance(matching_rules, list)
        self.assertGreater(len(matching_rules), 0)
    
    def test_time_targeting_integration(self):
        """Test time targeting integration."""
        # Create time rule
        TimeRouteRule.objects.create(
            route=self.offers[0],
            start_time=timezone.now() - timezone.timedelta(hours=1),
            end_time=timezone.now() + timezone.timedelta(hours=1),
            is_include=True
        )
        
        matching_rules = time_targeting_service.get_matching_time_rules(
            route=self.offers[0]
        )
        
        self.assertIsInstance(matching_rules, list)
        self.assertGreater(len(matching_rules), 0)
    
    def test_behavior_targeting_integration(self):
        """Test behavior targeting integration."""
        # Create behavior rule
        BehaviorRouteRule.objects.create(
            route=self.offers[0],
            event_type='offer_view',
            event_count_min=1,
            time_period_hours=24,
            is_include=True
        )
        
        matching_rules = behavior_targeting_service.get_matching_behavior_rules(
            route=self.offers[0],
            user=self.user
        )
        
        self.assertIsInstance(matching_rules, list)
    
    def test_targeting_performance(self):
        """Test targeting performance."""
        import time
        
        # Create targeting rules
        GeoRouteRule.objects.create(
            route=self.offers[0],
            country='US',
            is_include=True
        )
        
        DeviceRouteRule.objects.create(
            route=self.offers[0],
            device_type='desktop',
            is_include=True
        )
        
        context = {
            'location': {'country': 'US'},
            'device': {'type': 'desktop'}
        }
        
        # Measure targeting time
        start_time = time.time()
        
        matching_routes = targeting_service.get_matching_routes(
            user_id=self.user.id,
            context=context
        )
        
        end_time = time.time()
        targeting_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(targeting_time, 100)  # Within 100ms
    
    def test_targeting_error_handling(self):
        """Test error handling in targeting."""
        # Test with invalid context
        with self.assertRaises(Exception):
            targeting_service.get_matching_routes(
                user_id=self.user.id,
                context=None
            )
        
        # Test with invalid user ID
        with self.assertRaises(Exception):
            targeting_service.get_matching_routes(
                user_id=999999,
                context={'location': {'country': 'US'}}
            )
