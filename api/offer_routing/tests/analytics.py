"""
Analytics Tests for Offer Routing System

This module contains unit tests for analytics functionality,
including performance metrics, insights, and reporting.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Sum
from ..services.analytics import RoutingAnalyticsService, analytics_service
from ..models import RoutingDecisionLog, RoutingInsight, RoutePerformanceStat, OfferExposureStat
from ..exceptions import AnalyticsError, ValidationError

User = get_user_model()


class RoutingAnalyticsServiceTestCase(TestCase):
    """Test cases for RoutingAnalyticsService."""
    
    def setUp(self):
        """Set up test data."""
        self.analytics_service = RoutingAnalyticsService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
        
        # Create test decision logs
        for i in range(10):
            RoutingDecisionLog.objects.create(
                user=self.user,
                offer_id=i + 1,
                score=85.5 + (i * 2),
                response_time_ms=45.2 + (i * 3),
                cache_hit=i % 2 == 0,
                personalization_applied=i % 3 == 0,
                caps_checked=i % 2 == 0,
                fallback_used=i % 5 == 0,
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
    
    def test_aggregate_hourly_stats(self):
        """Test hourly stats aggregation."""
        aggregated_count = self.analytics_service.aggregate_hourly_stats()
        
        self.assertIsInstance(aggregated_count, int)
        self.assertGreaterEqual(aggregated_count, 0)
        
        # Check if stats were created
        from ..models import RoutePerformanceStat
        stats = RoutePerformanceStat.objects.all()
        self.assertGreaterEqual(stats.count(), 0)
    
    def test_generate_insights(self):
        """Test insights generation."""
        period_start = timezone.now() - timezone.timedelta(hours=24)
        period_end = timezone.now()
        
        generated_count = self.analytics_service.generate_insights(
            tenant_id=self.tenant.id,
            period_start=period_start,
            period_end=period_end
        )
        
        self.assertIsInstance(generated_count, int)
        self.assertGreaterEqual(generated_count, 0)
        
        # Check if insights were created
        insights = RoutingInsight.objects.all()
        self.assertGreaterEqual(insights.count(), 0)
    
    def test_get_performance_metrics(self):
        """Test getting performance metrics."""
        metrics = self.analytics_service.get_performance_metrics(
            tenant_id=self.tenant.id,
            days=30
        )
        
        self.assertIsInstance(metrics, dict)
        self.assertIn('total_decisions', metrics)
        self.assertIn('avg_response_time', metrics)
        self.assertIn('cache_hit_rate', metrics)
        self.assertIn('personalization_rate', metrics)
        self.assertIn('fallback_rate', metrics)
    
    def test_get_user_analytics(self):
        """Test getting user analytics."""
        analytics = self.analytics_service.get_user_analytics(
            user_id=self.user.id,
            days=30
        )
        
        self.assertIsInstance(analytics, dict)
        self.assertIn('total_decisions', analytics)
        self.assertIn('avg_score', analytics)
        self.assertIn('unique_offers', analytics)
        self.assertIn('conversion_rate', analytics)
    
    def test_get_route_analytics(self):
        """Test getting route analytics."""
        # Create test offer route
        from ..models import OfferRoute
        offer_route = OfferRoute.objects.create(
            name='Test Route',
            description='Test route for analytics',
            tenant=self.tenant,
            priority=5,
            max_offers=10,
            is_active=True
        )
        
        analytics = self.analytics_service.get_route_analytics(
            route_id=offer_route.id,
            days=30
        )
        
        self.assertIsInstance(analytics, dict)
        self.assertIn('total_decisions', analytics)
        self.assertIn('avg_score', analytics)
        self.assertIn('conversion_rate', analytics)
    
    def test_calculate_percentile(self):
        """Test percentile calculation."""
        values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        
        percentile_50 = self.analytics_service._calculate_percentile(values, 50)
        self.assertEqual(percentile_50, 50)
        
        percentile_90 = self.analytics_service._calculate_percentile(values, 90)
        self.assertEqual(percentile_90, 90)
    
    def test_calculate_trend(self):
        """Test trend calculation."""
        values = [10, 15, 20, 25, 30]
        
        trend = self.analytics_service._calculate_trend(values)
        
        self.assertIsInstance(trend, dict)
        self.assertIn('direction', trend)
        self.assertIn('slope', trend)
        self.assertIn('r_squared', trend)
    
    def test_detect_anomalies(self):
        """Test anomaly detection."""
        values = [10, 12, 11, 13, 12, 15, 50, 14, 13, 12]  # 50 is an anomaly
        
        anomalies = self.analytics_service._detect_anomalies(values)
        
        self.assertIsInstance(anomalies, list)
        self.assertGreater(len(anomalies), 0)
        
        # Check if anomaly was detected
        anomaly_indices = [a['index'] for a in anomalies]
        self.assertIn(6, anomaly_indices)  # Index of value 50
    
    def test_generate_performance_insights(self):
        """Test performance insights generation."""
        period_start = timezone.now() - timezone.timedelta(hours=24)
        period_end = timezone.now()
        
        insights = self.analytics_service._generate_performance_insights(
            tenant_id=self.tenant.id,
            period_start=period_start,
            period_end=period_end
        )
        
        self.assertIsInstance(insights, list)
        
        for insight in insights:
            self.assertIn('type', insight)
            self.assertIn('title', insight)
            self.assertIn('description', insight)
            self.assertIn('severity', insight)
    
    def test_generate_optimization_insights(self):
        """Test optimization insights generation."""
        period_start = timezone.now() - timezone.timedelta(hours=24)
        period_end = timezone.now()
        
        insights = self.analytics_service._generate_optimization_insights(
            tenant_id=self.tenant.id,
            period_start=period_start,
            period_end=period_end
        )
        
        self.assertIsInstance(insights, list)
        
        for insight in insights:
            self.assertIn('type', insight)
            self.assertIn('title', insight)
            self.assertIn('description', insight)
            self.assertIn('recommendation', insight)
    
    def test_generate_anomaly_insights(self):
        """Test anomaly insights generation."""
        period_start = timezone.now() - timezone.timedelta(hours=24)
        period_end = timezone.now()
        
        insights = self.analytics_service._generate_anomaly_insights(
            tenant_id=self.tenant.id,
            period_start=period_start,
            period_end=period_end
        )
        
        self.assertIsInstance(insights, list)
        
        for insight in insights:
            self.assertIn('type', insight)
            self.assertIn('title', insight)
            self.assertIn('description', insight)
            self.assertIn('severity', insight)
    
    def test_cleanup_old_data(self):
        """Test cleanup of old analytics data."""
        # Create old decision logs
        old_date = timezone.now() - timezone.timedelta(days=100)
        RoutingDecisionLog.objects.create(
            user=self.user,
            offer_id=999,
            score=85.5,
            response_time_ms=45.2,
            created_at=old_date
        )
        
        deleted_count = self.analytics_service.cleanup_old_data(days=30)
        
        self.assertIsInstance(deleted_count, int)
        self.assertGreaterEqual(deleted_count, 0)
    
    def test_export_analytics_data(self):
        """Test analytics data export."""
        export_data = self.analytics_service.export_analytics_data(
            tenant_id=self.tenant.id,
            days=30
        )
        
        self.assertIsInstance(export_data, dict)
        self.assertIn('decision_logs', export_data)
        self.assertIn('performance_stats', export_data)
        self.assertIn('insights', export_data)
        self.assertIn('export_timestamp', export_data)
    
    def test_import_analytics_data(self):
        """Test analytics data import."""
        export_data = {
            'decision_logs': [
                {
                    'user_id': self.user.id,
                    'offer_id': 1,
                    'score': 85.5,
                    'response_time_ms': 45.2,
                    'cache_hit': True,
                    'personalization_applied': False,
                    'caps_checked': True,
                    'fallback_used': False,
                    'created_at': timezone.now().isoformat()
                }
            ],
            'performance_stats': [],
            'insights': []
        }
        
        success = self.analytics_service.import_analytics_data(
            tenant_id=self.tenant.id,
            import_data=export_data
        )
        
        self.assertTrue(success)
        
        # Check if data was imported
        logs = RoutingDecisionLog.objects.filter(user=self.user)
        self.assertGreater(logs.count(), 0)


class RoutePerformanceStatTestCase(TestCase):
    """Test cases for RoutePerformanceStat."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test offer route
        from ..models import OfferRoute
        self.offer_route = OfferRoute.objects.create(
            name='Test Route',
            description='Test route for analytics',
            tenant=self.user,
            priority=5,
            max_offers=10,
            is_active=True
        )
        
        # Create performance stats
        for i in range(7):
            RoutePerformanceStat.objects.create(
                tenant=self.user,
                offer=self.offer_route,
                date=timezone.now().date() - timezone.timedelta(days=i),
                impressions=100 + (i * 10),
                clicks=10 + (i * 2),
                conversions=2 + i,
                revenue=20.0 + (i * 5),
                avg_response_time_ms=45.2 + (i * 2),
                cache_hit_rate=85.0 + (i * 2),
                click_through_rate=10.0 + (i * 2),
                conversion_rate=2.0 + (i * 0.5)
            )
    
    def test_get_performance_summary(self):
        """Test performance summary calculation."""
        from datetime import timedelta
        
        summary = RoutePerformanceStat.objects.filter(
            tenant=self.user,
            date__gte=timezone.now().date() - timedelta(days=7)
        ).aggregate(
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            total_revenue=Sum('revenue'),
            avg_response_time=Avg('avg_response_time_ms'),
            avg_cache_hit_rate=Avg('cache_hit_rate')
        )
        
        self.assertIsInstance(summary, dict)
        self.assertIn('total_impressions', summary)
        self.assertIn('total_revenue', summary)
    
    def test_get_trending_metrics(self):
        """Test trending metrics calculation."""
        from datetime import timedelta
        
        # Get recent stats
        recent_stats = RoutePerformanceStat.objects.filter(
            tenant=self.user,
            offer=self.offer_route,
            date__gte=timezone.now().date() - timedelta(days=7)
        ).order_by('date')
        
        # Calculate trends
        impressions_trend = self._calculate_trend([s.impressions for s in recent_stats])
        clicks_trend = self._calculate_trend([s.clicks for s in recent_stats])
        conversions_trend = self._calculate_trend([s.conversions for s in recent_stats])
        
        self.assertIsInstance(impressions_trend, dict)
        self.assertIn('direction', impressions_trend)
        self.assertIn('slope', impressions_trend)
    
    def _calculate_trend(self, values):
        """Helper method to calculate trend."""
        if len(values) < 2:
            return {'direction': 'stable', 'slope': 0, 'r_squared': 0}
        
        # Simple linear regression
        x = list(range(len(values)))
        n = len(values)
        
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(xi * yi for xi, yi in zip(x, values))
        sum_x2 = sum(xi * xi for xi in x)
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        
        # Calculate R-squared
        y_mean = sum_y / n
        ss_tot = sum((yi - y_mean) ** 2 for yi in values)
        ss_res = sum((yi - (slope * xi + (sum_y - slope * sum_x) / n)) ** 2 for xi, yi in zip(x, values))
        
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        direction = 'up' if slope > 0 else 'down' if slope < 0 else 'stable'
        
        return {'direction': direction, 'slope': slope, 'r_squared': r_squared}


class OfferExposureStatTestCase(TestCase):
    """Test cases for OfferExposureStat."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test offer route
        from ..models import OfferRoute
        self.offer_route = OfferRoute.objects.create(
            name='Test Route',
            description='Test route for analytics',
            tenant=self.user,
            priority=5,
            max_offers=10,
            is_active=True
        )
        
        # Create exposure stats
        for i in range(7):
            OfferExposureStat.objects.create(
                tenant=self.user,
                offer=self.offer_route,
                date=timezone.now().date() - timezone.timedelta(days=i),
                unique_users_exposed=50 + (i * 5),
                total_exposures=100 + (i * 10),
                repeat_exposures=50 + (i * 5),
                avg_exposures_per_user=2.0,
                max_exposures_per_user=5,
                geographic_distribution={'US': 30, 'CA': 20},
                device_distribution={'desktop': 40, 'mobile': 60},
                hourly_distribution={str(i): 10 for i in range(24)}
            )
    
    def test_get_exposure_summary(self):
        """Test exposure summary calculation."""
        from datetime import timedelta
        
        summary = OfferExposureStat.objects.filter(
            tenant=self.user,
            date__gte=timezone.now().date() - timedelta(days=7)
        ).aggregate(
            total_unique_users_exposed=Sum('unique_users_exposed'),
            total_exposures=Sum('total_exposures'),
            total_repeat_exposures=Sum('repeat_exposures'),
            avg_exposures_per_user=Avg('avg_exposures_per_user')
        )
        
        self.assertIsInstance(summary, dict)
        self.assertIn('total_unique_users_exposed', summary)
        self.assertIn('total_exposures', summary)
    
    def test_get_exposure_patterns(self):
        """Test exposure pattern analysis."""
        patterns = OfferExposureStat.objects.filter(
            tenant=self.user,
            offer=self.offer_route
        ).order_by('date')
        
        # Analyze patterns
        for stat in patterns:
            self.assertIsInstance(stat.geographic_distribution, dict)
            self.assertIsInstance(stat.device_distribution, dict)
            self.assertIsInstance(stat.hourly_distribution, dict)
            
            # Check if distributions sum to expected values
            geo_sum = sum(stat.geographic_distribution.values())
            device_sum = sum(stat.device_distribution.values())
            hourly_sum = sum(stat.hourly_distribution.values())
            
            self.assertEqual(geo_sum, 50)  # Should match unique_users_exposed
            self.assertEqual(device_sum, 50)
            self.assertEqual(hourly_sum, 100)  # Should match total_exposures
    
    def test_calculate_exposure_metrics(self):
        """Test exposure metrics calculation."""
        stat = OfferExposureStat.objects.first()
        
        # Calculate metrics
        exposure_rate = stat.total_exposures / stat.unique_users_exposed if stat.unique_users_exposed > 0 else 0
        repeat_rate = stat.repeat_exposures / stat.total_exposures if stat.total_exposures > 0 else 0
        
        self.assertIsInstance(exposure_rate, (int, float))
        self.assertIsInstance(repeat_rate, (int, float))
        self.assertGreaterEqual(exposure_rate, 0)
        self.assertLessEqual(repeat_rate, 1)


class AnalyticsIntegrationTestCase(TestCase):
    """Integration tests for analytics functionality."""
    
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
    
    def test_analytics_workflow(self):
        """Test complete analytics workflow."""
        # Create decision logs
        for i in range(50):
            RoutingDecisionLog.objects.create(
                user=self.user,
                offer_id=self.offers[i % 3].id,
                score=85.5 + (i * 0.5),
                response_time_ms=40.0 + (i * 0.5),
                cache_hit=i % 3 == 0,
                personalization_applied=i % 4 == 0,
                caps_checked=i % 2 == 0,
                fallback_used=i % 5 == 0,
                created_at=timezone.now() - timezone.timedelta(hours=i % 24)
            )
        
        # Aggregate hourly stats
        aggregated_count = analytics_service.aggregate_hourly_stats()
        self.assertGreaterEqual(aggregated_count, 0)
        
        # Generate insights
        period_start = timezone.now() - timezone.timedelta(hours=24)
        period_end = timezone.now()
        
        generated_count = analytics_service.generate_insights(
            tenant_id=self.user.id,
            period_start=period_start,
            period_end=period_end
        )
        self.assertGreaterEqual(generated_count, 0)
        
        # Get performance metrics
        metrics = analytics_service.get_performance_metrics(
            tenant_id=self.user.id,
            days=30
        )
        
        self.assertIsInstance(metrics, dict)
        self.assertIn('total_decisions', metrics)
        
        # Get user analytics
        user_analytics = analytics_service.get_user_analytics(
            user_id=self.user.id,
            days=30
        )
        
        self.assertIsInstance(user_analytics, dict)
        self.assertIn('total_decisions', user_analytics)
    
    def test_performance_analytics(self):
        """Test performance analytics."""
        # Create performance stats
        from ..models import RoutePerformanceStat
        
        for offer in self.offers:
            for i in range(7):
                RoutePerformanceStat.objects.create(
                    tenant=self.user,
                    offer=offer,
                    date=timezone.now().date() - timezone.timedelta(days=i),
                    impressions=100 + (i * 10),
                    clicks=10 + (i * 2),
                    conversions=2 + i,
                    revenue=20.0 + (i * 5),
                    avg_response_time_ms=45.2 + (i * 2),
                    cache_hit_rate=85.0 + (i * 2),
                    click_through_rate=10.0 + (i * 2),
                    conversion_rate=2.0 + (i * 0.5)
                )
        
        # Get performance metrics
        metrics = analytics_service.get_performance_metrics(
            tenant_id=self.user.id,
            days=30
        )
        
        self.assertIsInstance(metrics, dict)
        self.assertIn('avg_response_time', metrics)
        self.assertIn('cache_hit_rate', metrics)
        self.assertIn('conversion_rate', metrics)
    
    def test_exposure_analytics(self):
        """Test exposure analytics."""
        # Create exposure stats
        from ..models import OfferExposureStat
        
        for offer in self.offers:
            for i in range(7):
                OfferExposureStat.objects.create(
                    tenant=self.user,
                    offer=offer,
                    date=timezone.now().date() - timezone.timedelta(days=i),
                    unique_users_exposed=50 + (i * 5),
                    total_exposures=100 + (i * 10),
                    repeat_exposures=50 + (i * 5),
                    avg_exposures_per_user=2.0,
                    max_exposures_per_user=5,
                    geographic_distribution={'US': 30, 'CA': 20},
                    device_distribution={'desktop': 40, 'mobile': 60},
                    hourly_distribution={str(i): 10 for i in range(24)}
                )
        
        # Get exposure summary
        summary = OfferExposureStat.objects.filter(
            tenant=self.user,
            date__gte=timezone.now().date() - timezone.timedelta(days=7)
        ).aggregate(
            total_unique_users_exposed=Sum('unique_users_exposed'),
            total_exposures=Sum('total_exposures')
        )
        
        self.assertIsInstance(summary, dict)
        self.assertIn('total_unique_users_exposed', summary)
        self.assertIn('total_exposures', summary)
    
    def test_analytics_performance(self):
        """Test analytics performance."""
        import time
        
        # Create test data
        for i in range(100):
            RoutingDecisionLog.objects.create(
                user=self.user,
                offer_id=self.offers[i % 3].id,
                score=85.5,
                response_time_ms=45.2,
                cache_hit=True,
                personalization_applied=False,
                caps_checked=True,
                fallback_used=False,
                created_at=timezone.now()
            )
        
        # Measure aggregation time
        start_time = time.time()
        
        aggregated_count = analytics_service.aggregate_hourly_stats()
        
        end_time = time.time()
        aggregation_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(aggregation_time, 1000)  # Within 1 second
        
        # Measure insights generation time
        start_time = time.time()
        
        period_start = timezone.now() - timezone.timedelta(hours=1)
        period_end = timezone.now()
        
        generated_count = analytics_service.generate_insights(
            tenant_id=self.user.id,
            period_start=period_start,
            period_end=period_end
        )
        
        end_time = time.time()
        insights_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(insights_time, 500)  # Within 500ms
    
    def test_analytics_error_handling(self):
        """Test error handling in analytics."""
        # Test with invalid tenant ID
        with self.assertRaises(Exception):
            analytics_service.get_performance_metrics(
                tenant_id=999999,
                days=30
            )
        
        # Test with invalid user ID
        with self.assertRaises(Exception):
            analytics_service.get_user_analytics(
                user_id=999999,
                days=30
            )
        
        # Test with invalid date range
        with self.assertRaises(Exception):
            analytics_service.generate_insights(
                tenant_id=self.user.id,
                period_start=timezone.now(),
                period_end=timezone.now() - timezone.timedelta(hours=1)  # End before start
            )
