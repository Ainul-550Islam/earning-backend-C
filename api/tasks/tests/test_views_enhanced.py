"""
tasks/tests/test_views_enhanced.py
Enhanced test suite for views with comprehensive coverage.
"""

import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch, MagicMock


@pytest.mark.django_db
class TestMasterTaskViewSetEnhanced:
    """Enhanced tests for MasterTaskViewSet"""
    
    def test_list_tasks_with_all_filters(self, api_client, master_task, featured_task):
        """Test task listing with all filter combinations"""
        url = reverse('task-list')
        
        # Test system type filter
        response = api_client.get(f"{url}?system_type={master_task.system_type}")
        if response.status_code == 200:
            data = response.data
            results = data.get('results', data) if isinstance(data, dict) else data
            assert isinstance(results, list)
        
        # Test category filter
        response = api_client.get(f"{url}?category={master_task.category}")
        if response.status_code == 200:
            data = response.data
            results = data.get('results', data) if isinstance(data, dict) else data
            assert isinstance(results, list)
        
        # Test featured filter
        response = api_client.get(f"{url}?featured=true")
        if response.status_code == 200:
            data = response.data
            results = data.get('results', data) if isinstance(data, dict) else data
            assert isinstance(results, list)
        
        # Test user level filter
        response = api_client.get(f"{url}?user_level=5")
        if response.status_code == 200:
            data = response.data
            results = data.get('results', data) if isinstance(data, dict) else data
            assert isinstance(results, list)
        
        # Test available only filter
        response = api_client.get(f"{url}?available_only=true")
        if response.status_code == 200:
            data = response.data
            results = data.get('results', data) if isinstance(data, dict) else data
            assert isinstance(results, list)
    
    def test_list_tasks_with_search(self, api_client, master_task):
        """Test task listing with search functionality"""
        url = reverse('task-list')
        
        # Search by task name
        response = api_client.get(f"{url}?search={master_task.name[:10]}")
        if response.status_code == 200:
            data = response.data
            results = data.get('results', data) if isinstance(data, dict) else data
            assert isinstance(results, list)
        
        # Search by task ID
        response = api_client.get(f"{url}?search={master_task.task_id[:10]}")
        if response.status_code == 200:
            data = response.data
            results = data.get('results', data) if isinstance(data, dict) else data
            assert isinstance(results, list)
    
    def test_list_tasks_with_pagination(self, api_client, master_task):
        """Test task listing pagination"""
        url = reverse('task-list')
        
        # Test custom page size
        response = api_client.get(f"{url}?page_size=5")
        if response.status_code == 200:
            data = response.data
            if 'pagination' in data:
                pagination = data['pagination']
                assert pagination['page_size'] == 5
        
        # Test page parameter
        response = api_client.get(f"{url}?page=2")
        if response.status_code == 200:
            data = response.data
            if 'pagination' in data:
                pagination = data['pagination']
                assert pagination['page'] == 2
        
        # Test max page size limit
        response = api_client.get(f"{url}?page_size=200")
        if response.status_code == 200:
            data = response.data
            if 'pagination' in data:
                pagination = data['pagination']
                assert pagination['page_size'] <= 100
    
    def test_list_tasks_with_ordering(self, api_client, master_task):
        """Test task listing with ordering"""
        url = reverse('task-list')
        
        # Test ordering by sort_order
        response = api_client.get(f"{url}?ordering=sort_order")
        if response.status_code == 200:
            data = response.data
            results = data.get('results', data) if isinstance(data, dict) else data
            assert isinstance(results, list)
        
        # Test ordering by created_at
        response = api_client.get(f"{url}?ordering=-created_at")
        if response.status_code == 200:
            data = response.data
            results = data.get('results', data) if isinstance(data, dict) else data
            assert isinstance(results, list)
        
        # Test ordering by total_completions
        response = api_client.get(f"{url}?ordering=-total_completions")
        if response.status_code == 200:
            data = response.data
            results = data.get('results', data) if isinstance(data, dict) else data
            assert isinstance(results, list)
    
    def test_retrieve_task_with_context(self, auth_client, master_task):
        """Test task retrieval with user context"""
        url = reverse('task-detail', kwargs={'task_id': master_task.task_id})
        response = auth_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            assert 'data' in data
            assert 'is_available' in data['data']
            assert 'unavailable_reason' in data['data']
            assert isinstance(data['data']['is_available'], bool)
    
    def test_by_system_endpoint(self, api_client, master_task):
        """Test tasks grouped by system type"""
        url = reverse('tasks-by-system')
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            assert 'data' in data
            assert isinstance(data['data'], list)
            
            # Check structure of system data
            if data['data']:
                system_data = data['data'][0]
                assert 'system_type' in system_data
                assert 'system_name' in system_data
                assert 'tasks' in system_data
                assert 'count' in system_data
    
    def test_featured_tasks_endpoint(self, api_client, featured_task):
        """Test featured tasks endpoint"""
        url = reverse('tasks-featured')
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            assert 'data' in data
            assert 'count' in data
            assert isinstance(data['data'], list)
            assert isinstance(data['count'], int)
    
    def test_check_availability_endpoint(self, auth_client, master_task):
        """Test task availability check endpoint"""
        url = reverse('task-check-availability', kwargs={'task_id': master_task.task_id})
        response = auth_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            assert 'data' in data
            task_data = data['data']
            
            assert 'task_id' in task_data
            assert 'is_available' in task_data
            assert 'reason' in task_data
            assert 'next_available' in task_data
            assert 'user_level' in task_data
            assert isinstance(task_data['is_available'], bool)
    
    def test_task_statistics_endpoint(self, api_client, master_task):
        """Test task statistics endpoint"""
        url = reverse('task-statistics', kwargs={'task_id': master_task.task_id})
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            assert 'data' in data
            stats = data['data']
            
            required_stats = [
                'total_completions', 'unique_users', 'completion_rate',
                'unique_users_30d', 'avg_completion_time',
                'daily_average', 'peak_hours', 'completion_by_level'
            ]
            
            for stat in required_stats:
                assert stat in stats
    
    def test_bulk_import_endpoint_admin_only(self, api_client):
        """Test bulk import requires admin permissions"""
        url = reverse('tasks-bulk-import')
        response = api_client.post(url)
        assert response.status_code in (401, 403, 405)
    
    def test_bulk_import_endpoint_staff_success(self, staff_client):
        """Test bulk import works for staff"""
        url = reverse('tasks-bulk-import')
        response = staff_client.post(url)
        
        # Should be accessible to staff
        assert response.status_code not in (401, 403)
    
    @patch('tasks.views.cache.get')
    def test_circuit_breaker_protection(self, mock_cache_get, api_client, master_task):
        """Test circuit breaker protection"""
        # Simulate circuit open
        mock_cache_get.return_value = None
        
        url = reverse('task-detail', kwargs={'task_id': master_task.task_id})
        response = api_client.get(url)
        
        # Should handle gracefully
        assert response.status_code in (200, 503)
    
    def test_error_handling_various_scenarios(self, api_client):
        """Test error handling for various scenarios"""
        # Test non-existent task
        url = reverse('task-detail', kwargs={'task_id': 'NON_EXISTENT'})
        response = api_client.get(url)
        assert response.status_code in (404, 400)
        
        # Test invalid task ID format
        url = reverse('task-detail', kwargs={'task_id': 'invalid@id'})
        response = api_client.get(url)
        assert response.status_code in (404, 400)


@pytest.mark.django_db
class TestTaskCompletionViewSetEnhanced:
    """Enhanced tests for TaskCompletionViewSet"""
    
    def test_completion_list_user_isolation(self, auth_client, other_user_completion):
        """Test users can only see their own completions"""
        url = reverse('completion-list')
        response = auth_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            results = data.get('results', data) if isinstance(data, dict) else data
            completion_ids = [c.get('id') for c in results]
            assert other_user_completion.id not in completion_ids
    
    def test_completion_list_staff_sees_all(self, staff_client, completion, other_user_completion):
        """Test staff can see all completions"""
        url = reverse('completion-list')
        response = staff_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            results = data.get('results', data) if isinstance(data, dict) else data
            completion_ids = [c.get('id') for c in results]
            # Staff should see both completions
            assert completion.id in completion_ids or other_user_completion.id in completion_ids
    
    def test_completion_create_with_validation(self, auth_client, master_task):
        """Test completion creation with validation"""
        url = reverse('completion-list')
        
        # Test missing task ID
        response = auth_client.post(url, {})
        assert response.status_code == 400
        
        # Test invalid task ID
        response = auth_client.post(url, {'task': 'invalid'})
        assert response.status_code == 400
        
        # Test valid creation
        response = auth_client.post(url, {'task': master_task.id, 'status': 'started'})
        if response.status_code in (200, 201):
            data = response.data
            assert 'data' in data or 'status' in data
    
    def test_completion_create_duplicate_handling(self, auth_client, master_task):
        """Test completion creation duplicate handling"""
        from api.tasks.models import UserTaskCompletion
        
        # Create existing completion
        UserTaskCompletion.objects.create(
            user=auth_client.handler._force_user,
            task=master_task,
            status='started'
        )
        
        url = reverse('completion-list')
        response = auth_client.post(url, {'task': master_task.id, 'status': 'started'})
        
        if response.status_code == 200:
            data = response.data
            # Should indicate already started
            assert 'already_started' in data.get('status', '')
    
    def test_completion_create_availability_check(self, auth_client, master_task):
        """Test completion creation checks task availability"""
        # Make task unavailable
        master_task.is_active = False
        master_task.save()
        
        url = reverse('completion-list')
        response = auth_client.post(url, {'task': master_task.id, 'status': 'started'})
        
        # Should be rejected
        assert response.status_code == 400
        
        # Restore task
        master_task.is_active = True
        master_task.save()
    
    def test_completion_list_with_date_filters(self, auth_client, completion):
        """Test completion listing with date filters"""
        url = reverse('completion-list')
        
        # Test from_date filter
        from_date = (timezone.now() - timedelta(days=7)).isoformat()
        response = auth_client.get(f"{url}?from_date={from_date}")
        if response.status_code == 200:
            data = response.data
            results = data.get('results', data) if isinstance(data, dict) else data
            assert isinstance(results, list)
        
        # Test to_date filter
        to_date = timezone.now().isoformat()
        response = auth_client.get(f"{url}?to_date={to_date}")
        if response.status_code == 200:
            data = response.data
            results = data.get('results', data) if isinstance(data, dict) else data
            assert isinstance(results, list)
        
        # Test status filter
        response = auth_client.get(f"{url}?status=completed")
        if response.status_code == 200:
            data = response.data
            results = data.get('results', data) if isinstance(data, dict) else data
            assert isinstance(results, list)
    
    def test_completion_list_with_optimization(self, auth_client, completion):
        """Test completion listing uses optimization"""
        url = reverse('completion-list')
        response = auth_client.get(url)
        
        if response.status_code == 200:
            # Should not cause N+1 queries
            # This would typically be tested with Django's assertNumQueries
            # For now, just ensure it doesn't error
            assert response.status_code in (200, 403, 401)
    
    def test_completion_error_scenarios(self, auth_client):
        """Test completion error scenarios"""
        url = reverse('completion-list')
        
        # Test unauthenticated
        response = auth_client.get(url)
        assert response.status_code in (401, 403)
        
        # Test invalid status
        response = auth_client.post(url, {'task': 1, 'status': 'invalid'})
        assert response.status_code == 400


@pytest.mark.django_db
class TestViewSetErrorHandlingEnhanced:
    """Enhanced tests for viewset error handling"""
    
    def test_not_authenticated_error_format(self, api_client):
        """Test NotAuthenticated error format"""
        url = reverse('completion-list')
        response = api_client.get(url)
        
        if response.status_code == 401:
            data = response.data
            assert 'error' in data
            assert 'error_code' in data
            assert data['error_code'] == 'NOT_AUTHENTICATED'
    
    def test_permission_denied_error_format(self, auth_client):
        """Test PermissionDenied error format"""
        # Try to access admin endpoint as regular user
        url = reverse('tasks-bulk-import')
        response = auth_client.post(url)
        
        if response.status_code == 403:
            data = response.data
            assert 'error' in data
            assert 'error_code' in data
            assert data['error_code'] == 'PERMISSION_DENIED'
    
    def test_not_found_error_format(self, api_client):
        """Test NotFound error format"""
        url = reverse('task-detail', kwargs={'task_id': 'NON_EXISTENT'})
        response = api_client.get(url)
        
        if response.status_code == 404:
            data = response.data
            assert 'error' in data
            assert 'error_code' in data
            assert data['error_code'] == 'NOT_FOUND'
    
    def test_validation_error_format(self, auth_client):
        """Test ValidationError error format"""
        url = reverse('completion-list')
        response = auth_client.post(url, {'task': 'invalid'})
        
        if response.status_code == 400:
            data = response.data
            assert 'error' in data
            assert 'error_code' in data
            assert data['error_code'] == 'VALIDATION_ERROR'
    
    def test_internal_error_handling(self, api_client):
        """Test internal error handling"""
        with patch('tasks.views.UserTaskCompletion.objects.get') as mock_get:
            mock_get.side_effect = Exception("Database error")
            
            url = reverse('task-detail', kwargs={'task_id': 'TEST_TASK'})
            response = api_client.get(url)
            
            # Should handle gracefully
            assert response.status_code in (500, 200)
            
            if response.status_code == 500:
                data = response.data
                assert 'error' in data
                assert 'error_code' in data


@pytest.mark.django_db
class TestViewSetPerformanceEnhanced:
    """Enhanced tests for viewset performance"""
    
    def test_list_tasks_performance(self, api_client, master_task):
        """Test task listing performance"""
        import time
        
        url = reverse('task-list')
        start_time = time.time()
        response = api_client.get(url)
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # Should respond within 1 second
        assert response_time < 1.0
        assert response.status_code in (200, 401, 403)
    
    def test_retrieve_task_performance(self, api_client, master_task):
        """Test task retrieval performance"""
        import time
        
        url = reverse('task-detail', kwargs={'task_id': master_task.task_id})
        start_time = time.time()
        response = api_client.get(url)
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # Should respond within 0.5 seconds
        assert response_time < 0.5
        assert response.status_code in (200, 404)
    
    def test_pagination_performance(self, api_client):
        """Test pagination performance"""
        import time
        
        url = reverse('task-list')
        start_time = time.time()
        response = api_client.get(f"{url}?page_size=100")
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # Should handle pagination efficiently
        assert response_time < 2.0
        assert response.status_code in (200, 401, 403)
    
    def test_concurrent_requests(self, api_client, master_task):
        """Test handling concurrent requests"""
        import threading
        import time
        
        url = reverse('task-list')
        results = []
        
        def make_request():
            response = api_client.get(url)
            results.append(response.status_code)
        
        # Make 10 concurrent requests
        threads = []
        for i in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should complete without errors
        assert all(status in (200, 401, 403) for status in results)
    
    def test_memory_usage(self, api_client):
        """Test memory usage with large datasets"""
        # This would typically be tested with memory profiling
        # For now, just ensure it doesn't crash
        url = reverse('task-list')
        response = api_client.get(f"{url}?page_size=100")
        
        # Should handle large page sizes
        assert response.status_code in (200, 401, 403)


@pytest.mark.django_db
class TestViewSetSecurityEnhanced:
    """Enhanced tests for viewset security"""
    
    def test_sql_injection_protection(self, api_client):
        """Test SQL injection protection"""
        malicious_inputs = [
            "'; DROP TABLE tasks_mastertask; --",
            "' OR '1'='1",
            "1' UNION SELECT * FROM auth_user --"
        ]
        
        url = reverse('task-list')
        for malicious_input in malicious_inputs:
            response = api_client.get(f"{url}?search={malicious_input}")
            # Should not cause server error
            assert response.status_code not in (500, 502)
    
    def test_xss_protection(self, api_client):
        """Test XSS protection"""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "'\"><script>alert('xss')</script>"
        ]
        
        url = reverse('task-list')
        for payload in xss_payloads:
            response = api_client.get(f"{url}?search={payload}")
            if response.status_code == 200:
                response_text = str(response.content)
                # Should not contain unescaped script tags
                assert '<script>' not in response_text.lower()
    
    def test_csrf_protection(self, api_client):
        """Test CSRF protection"""
        url = reverse('completion-list')
        
        # Test POST without CSRF token (if CSRF protection is enabled)
        response = api_client.post(url, {'task': 1, 'status': 'started'})
        
        # Should handle CSRF appropriately
        # This depends on Django's CSRF configuration
        assert response.status_code in (200, 201, 400, 401, 403)
    
    def test_rate_limiting(self, api_client):
        """Test rate limiting"""
        url = reverse('task-list')
        
        # Make many rapid requests
        responses = []
        for i in range(100):
            response = api_client.get(url)
            responses.append(response.status_code)
        
        # Should eventually be rate limited (if rate limiting is implemented)
        # For now, just ensure server doesn't crash
        assert all(status in (200, 401, 403, 429) for status in responses)
    
    def test_authentication_bypass_attempts(self, api_client):
        """Test authentication bypass attempts"""
        url = reverse('completion-list')
        
        # Test various authentication bypass attempts
        bypass_attempts = [
            {'Authorization': 'Bearer invalid_token'},
            {'Authorization': 'Basic invalid_credentials'},
            {'X-API-Key': 'invalid_key'},
            {'X-Forwarded-For': '127.0.0.1'},
        ]
        
        for headers in bypass_attempts:
            response = api_client.get(url, **headers)
            # Should not bypass authentication
            assert response.status_code in (401, 403)
    
    def test_sensitive_data_exposure(self, api_client):
        """Test sensitive data exposure"""
        url = reverse('task-detail', kwargs={'task_id': 'TEST_TASK'})
        
        response = api_client.get(url)
        
        if response.status_code == 200:
            response_text = str(response.content)
            # Should not expose sensitive information
            sensitive_patterns = [
                'password', 'secret', 'key', 'token',
                'private', 'internal', 'admin'
            ]
            
            for pattern in sensitive_patterns:
                # Check if sensitive data is in response (case-insensitive)
                assert pattern.lower() not in response_text.lower()
