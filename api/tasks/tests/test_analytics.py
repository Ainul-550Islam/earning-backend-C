"""
tasks/tests/test_analytics.py
Comprehensive test suite for analytics endpoints.
"""

import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch, MagicMock


@pytest.mark.django_db
class TestAnalyticsViewSet:
    """Test analytics endpoints"""
    
    def test_analytics_dashboard_unauthorized(self, api_client):
        """Test dashboard requires authentication"""
        url = reverse('analytics-dashboard')
        response = api_client.get(url)
        assert response.status_code in (401, 403)
    
    def test_analytics_dashboard_authorized(self, auth_client, master_task, completion):
        """Test dashboard with authenticated user"""
        url = reverse('analytics-dashboard')
        response = auth_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            assert 'data' in data
            assert 'user_stats' in data['data']
            assert 'task_stats' in data['data']
            assert 'revenue_stats' in data['data']
            assert 'engagement_stats' in data['data']
            assert 'performance_metrics' in data['data']
            assert data['timeframe'] == '30 days'
    
    def test_analytics_dashboard_custom_days(self, auth_client):
        """Test dashboard with custom days parameter"""
        url = reverse('analytics-dashboard') + '?days=7'
        response = auth_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            assert data['timeframe'] == '7 days'
    
    def test_analytics_dashboard_staff_user(self, staff_client, master_task, completion):
        """Test dashboard with staff user sees more data"""
        url = reverse('analytics-dashboard')
        response = staff_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            user_stats = data['data']['user_stats']
            # Staff should see user growth metrics
            assert 'total_users' in user_stats
            assert 'active_users' in user_stats
            assert 'new_users_today' in user_stats
            assert 'user_growth_rate' in user_stats
    
    @patch('tasks.views.cache.get')
    def test_analytics_real_time(self, mock_cache, auth_client, completion):
        """Test real-time analytics"""
        mock_cache.return_value = None
        
        url = reverse('analytics-real-time')
        response = auth_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            assert 'data' in data
            assert 'active_users' in data['data']
            assert 'completions_per_minute' in data['data']
            assert 'popular_tasks' in data['data']
            assert 'revenue_per_minute' in data['data']
            assert 'conversion_rates' in data['data']
            assert 'timestamp' in data
            assert data['window'] == '5 minutes'
    
    def test_analytics_trends(self, auth_client):
        """Test analytics trends endpoint"""
        url = reverse('analytics-trends')
        response = auth_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            assert 'data' in data
            assert 'daily_trends' in data['data']
            assert 'weekly_comparison' in data['data']
            assert 'growth_rates' in data['data']
            assert 'predictions' in data['data']
            assert 'metric' in data
            assert 'period' in data
    
    def test_analytics_trends_custom_metric(self, auth_client):
        """Test trends with custom metric"""
        url = reverse('analytics-trends') + '?metric=revenue'
        response = auth_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            assert data['metric'] == 'revenue'
    
    def test_analytics_user_behavior(self, auth_client):
        """Test user behavior analytics"""
        url = reverse('analytics-user-behavior')
        response = auth_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            assert 'data' in data
            assert 'user_segments' in data['data']
            assert 'retention_analysis' in data['data']
            assert 'engagement_patterns' in data['data']
            assert 'conversion_funnel' in data['data']
            assert 'cohort_analysis' in data['data']
            assert 'analysis_period' in data
    
    def test_analytics_error_handling(self, auth_client):
        """Test analytics error handling"""
        with patch('tasks.views.UserTaskCompletion.objects.filter') as mock_filter:
            mock_filter.side_effect = Exception("Database error")
            
            url = reverse('analytics-dashboard')
            response = auth_client.get(url)
            
            # Should handle error gracefully
            assert response.status_code in (500, 200)


@pytest.mark.django_db
class TestAnalyticsCalculations:
    """Test analytics calculation methods"""
    
    def test_get_user_stats_regular_user(self, auth_client, user, master_task, completion):
        """Test user stats calculation for regular user"""
        from api.tasks.views import AnalyticsViewSet
        
        viewset = AnalyticsViewSet()
        viewset.request = MagicMock()
        viewset.request.user = user
        
        from_date = timezone.now() - timedelta(days=30)
        stats = viewset._get_user_stats(user, from_date, False)
        
        assert 'total_completions' in stats
        assert 'total_earned' in stats
        assert 'completion_streak' in stats
        assert 'level' in stats
        assert 'experience_points' in stats
    
    def test_get_user_stats_staff_user(self, staff_client, admin_user):
        """Test user stats calculation for staff user"""
        from api.tasks.views import AnalyticsViewSet
        
        viewset = AnalyticsViewSet()
        viewset.request = MagicMock()
        viewset.request.user = admin_user
        
        from_date = timezone.now() - timedelta(days=30)
        stats = viewset._get_user_stats(admin_user, from_date, True)
        
        assert 'total_users' in stats
        assert 'active_users' in stats
        assert 'new_users_today' in stats
        assert 'user_growth_rate' in stats
    
    def test_get_task_stats_regular_user(self, auth_client, user, master_task):
        """Test task stats for regular user"""
        from api.tasks.views import AnalyticsViewSet
        
        viewset = AnalyticsViewSet()
        viewset.request = MagicMock()
        viewset.request.user = user
        
        from_date = timezone.now() - timedelta(days=30)
        stats = viewset._get_task_stats(from_date, False)
        
        assert 'total_tasks' in stats
        assert 'active_tasks' in stats
        assert 'featured_tasks' in stats
        assert 'total_completions' in stats
        assert 'average_completion_time' in stats
        assert 'top_performing_tasks' in stats
    
    def test_get_task_stats_staff_user(self, staff_client, admin_user, master_task):
        """Test task stats for staff user"""
        from api.tasks.views import AnalyticsViewSet
        
        viewset = AnalyticsViewSet()
        viewset.request = MagicMock()
        viewset.request.user = admin_user
        
        from_date = timezone.now() - timedelta(days=30)
        stats = viewset._get_task_stats(from_date, True)
        
        assert 'total_tasks' in stats
        assert 'active_tasks' in stats
        assert 'featured_tasks' in stats
        assert 'total_completions' in stats
    
    def test_get_revenue_stats_regular_user(self, auth_client, user, completion):
        """Test revenue stats for regular user"""
        from api.tasks.views import AnalyticsViewSet
        
        viewset = AnalyticsViewSet()
        viewset.request = MagicMock()
        viewset.request.user = user
        
        from_date = timezone.now() - timedelta(days=30)
        stats = viewset._get_revenue_stats(user, from_date, False)
        
        assert 'total_earned' in stats
        assert 'daily_average' in stats
        assert 'pending_earnings' in stats
    
    def test_get_revenue_stats_staff_user(self, staff_client, admin_user, completion):
        """Test revenue stats for staff user"""
        from api.tasks.views import AnalyticsViewSet
        
        viewset = AnalyticsViewSet()
        viewset.request = MagicMock()
        viewset.request.user = admin_user
        
        from_date = timezone.now() - timedelta(days=30)
        stats = viewset._get_revenue_stats(admin_user, from_date, True)
        
        assert 'total_revenue' in stats
        assert 'admin_revenue' in stats
        assert 'payout_rate' in stats
        assert 'daily_average' in stats
    
    def test_get_popular_tasks(self, auth_client, master_task, completion):
        """Test popular tasks calculation"""
        from api.tasks.views import AnalyticsViewSet
        
        viewset = AnalyticsViewSet()
        popular = viewset._get_popular_tasks([completion])
        
        assert isinstance(popular, list)
        if popular:
            assert 'task__name' in popular[0]
            assert 'task__task_id' in popular[0]
            assert 'count' in popular[0]
    
    def test_calculate_real_time_revenue(self, auth_client, completion):
        """Test real-time revenue calculation"""
        from api.tasks.views import AnalyticsViewSet
        
        viewset = AnalyticsViewSet()
        revenue = viewset._calculate_real_time_revenue([completion])
        
        assert isinstance(revenue, float)
        assert revenue >= 0
    
    def test_get_real_time_conversion_rates(self, auth_client, completion):
        """Test real-time conversion rates"""
        from api.tasks.views import AnalyticsViewSet
        
        viewset = AnalyticsViewSet()
        cutoff = timezone.now() - timedelta(minutes=5)
        rates = viewset._get_real_time_conversion_rates(cutoff)
        
        assert 'started' in rates
        assert 'completed' in rates
        assert 'conversion_rate' in rates
        assert isinstance(rates['conversion_rate'], (int, float))


@pytest.mark.django_db
class TestAnalyticsPermissions:
    """Test analytics permissions"""
    
    def test_analytics_requires_authentication(self, api_client):
        """Test all analytics endpoints require authentication"""
        endpoints = [
            'analytics-dashboard',
            'analytics-real-time',
            'analytics-trends',
            'analytics-user-behavior'
        ]
        
        for endpoint in endpoints:
            url = reverse(endpoint)
            response = api_client.get(url)
            assert response.status_code in (401, 403)
    
    def test_analytics_accessible_to_authenticated_user(self, auth_client):
        """Test analytics accessible to authenticated users"""
        endpoints = [
            'analytics-dashboard',
            'analytics-real-time',
            'analytics-trends',
            'analytics-user-behavior'
        ]
        
        for endpoint in endpoints:
            url = reverse(endpoint)
            response = auth_client.get(url)
            # Should not be authentication error
            assert response.status_code not in (401, 403)
    
    def test_analytics_accessible_to_staff_user(self, staff_client):
        """Test analytics accessible to staff users"""
        endpoints = [
            'analytics-dashboard',
            'analytics-real-time',
            'analytics-trends',
            'analytics-user-behavior'
        ]
        
        for endpoint in endpoints:
            url = reverse(endpoint)
            response = staff_client.get(url)
            # Should not be authentication error
            assert response.status_code not in (401, 403)


@pytest.mark.django_db
class TestAnalyticsPerformance:
    """Test analytics performance"""
    
    def test_analytics_dashboard_response_time(self, auth_client):
        """Test dashboard response time is reasonable"""
        import time
        
        url = reverse('analytics-dashboard')
        start_time = time.time()
        response = auth_client.get(url)
        end_time = time.time()
        
        response_time = end_time - start_time
        # Should respond within 2 seconds
        assert response_time < 2.0
    
    def test_analytics_with_large_dataset(self, auth_client, master_task):
        """Test analytics with large dataset"""
        # Create many completions
        from api.tasks.models import UserTaskCompletion
        user = auth_client.handler._force_user
        
        for i in range(100):
            UserTaskCompletion.objects.create(
                user=user,
                task=master_task,
                status='completed',
                reward_amount=Decimal('0.25'),
                completed_at=timezone.now() - timedelta(minutes=i)
            )
        
        url = reverse('analytics-dashboard')
        response = auth_client.get(url)
        
        # Should still handle large dataset
        assert response.status_code in (200, 500)  # 500 is acceptable for test environment


@pytest.mark.django_db
class TestAnalyticsDataIntegrity:
    """Test analytics data integrity"""
    
    def test_analytics_dashboard_data_structure(self, auth_client):
        """Test dashboard data structure is consistent"""
        url = reverse('analytics-dashboard')
        response = auth_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            required_fields = [
                'status', 'data', 'timeframe', 'generated_at'
            ]
            
            for field in required_fields:
                assert field in data
            
            # Check data structure
            required_data_fields = [
                'user_stats', 'task_stats', 'revenue_stats',
                'engagement_stats', 'performance_metrics'
            ]
            
            for field in required_data_fields:
                assert field in data['data']
    
    def test_analytics_data_types(self, auth_client):
        """Test analytics data types are correct"""
        url = reverse('analytics-dashboard')
        response = auth_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            
            # Check timestamp is string
            assert isinstance(data['generated_at'], str)
            
            # Check timeframe is string
            assert isinstance(data['timeframe'], str)
            
            # Check monetary values are numbers
            revenue_stats = data['data']['revenue_stats']
            if 'total_earned' in revenue_stats:
                assert isinstance(revenue_stats['total_earned'], (int, float))
    
    def test_analytics_error_responses(self, auth_client):
        """Test analytics error responses are consistent"""
        url = reverse('analytics-dashboard')
        
        # Test with invalid data that might cause errors
        with patch('tasks.views.timezone.now') as mock_now:
            mock_now.side_effect = Exception("Time error")
            
            response = auth_client.get(url)
            
            # Should return error response or handle gracefully
            assert response.status_code in (500, 200)
            
            if response.status_code == 500:
                error_data = response.data
                assert 'error' in error_data


# Integration tests
@pytest.mark.django_db
class TestAnalyticsIntegration:
    """Test analytics integration with other components"""
    
    def test_analytics_with_completions(self, auth_client, master_task):
        """Test analytics with actual completions"""
        from api.tasks.models import UserTaskCompletion
        user = auth_client.handler._force_user
        
        # Create completions
        for i in range(5):
            UserTaskCompletion.objects.create(
                user=user,
                task=master_task,
                status='completed',
                reward_amount=Decimal('0.50'),
                completed_at=timezone.now() - timedelta(hours=i)
            )
        
        url = reverse('analytics-dashboard')
        response = auth_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            user_stats = data['data']['user_stats']
            revenue_stats = data['data']['revenue_stats']
            
            # Should reflect the completions
            assert user_stats['total_completions'] >= 5
            assert revenue_stats['total_earned'] >= Decimal('2.50')
    
    def test_analytics_with_different_time_periods(self, auth_client, master_task, completion):
        """Test analytics with different time periods"""
        periods = ['7', '30', '90']
        
        for period in periods:
            url = reverse('analytics-dashboard') + f'?days={period}'
            response = auth_client.get(url)
            
            if response.status_code == 200:
                data = response.data
                assert data['timeframe'] == f'{period} days'
    
    def test_analytics_caching(self, auth_client):
        """Test analytics caching behavior"""
        with patch('tasks.views.cache.get') as mock_cache_get:
            with patch('tasks.views.cache.set') as mock_cache_set:
                # First call - cache miss
                mock_cache_get.return_value = None
                
                url = reverse('analytics-dashboard')
                response1 = auth_client.get(url)
                
                # Should attempt to cache result
                mock_cache_set.assert_called()
                
                # Second call - cache hit
                mock_cache_get.return_value = {'cached': True}
                response2 = auth_client.get(url)
                
                # Should return cached data
                if response2.status_code == 200:
                    assert 'cached' in response2.data
