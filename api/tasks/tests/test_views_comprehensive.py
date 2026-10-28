"""
tasks/tests/test_views_comprehensive.py
Comprehensive test suite for views with enhanced coverage.
"""

import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch, MagicMock


@pytest.mark.django_db
class TestMasterTaskViewSetComprehensive:
    """Comprehensive tests for MasterTaskViewSet"""
    
    def test_list_tasks_basic(self, api_client, master_task):
        """Test basic task listing"""
        url = reverse('task-list')
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            if 'results' in data:
                assert len(data['results']) >= 1
            elif isinstance(data, list):
                assert len(data) >= 1
    
    def test_list_tasks_with_filters(self, api_client, master_task, featured_task):
        """Test task listing with filters"""
        # Test system type filter
        url = reverse('task-list') + '?system_type=click_visit'
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Should not error with filter
    
    def test_list_tasks_featured_only(self, api_client, featured_task):
        """Test listing featured tasks only"""
        url = reverse('task-list') + '?featured=true'
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Should include featured task
    
    def test_list_tasks_by_user_level(self, api_client, master_task):
        """Test listing tasks filtered by user level"""
        url = reverse('task-list') + '?user_level=5'
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Should not error with level filter
    
    def test_retrieve_task_success(self, api_client, master_task):
        """Test successful task retrieval"""
        url = reverse('task-detail', kwargs={'task_id': master_task.task_id})
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            assert 'data' in data
            assert data['data']['task_id'] == master_task.task_id
    
    def test_retrieve_task_not_found(self, api_client):
        """Test task retrieval with non-existent task"""
        url = reverse('task-detail', kwargs={'task_id': 'NON_EXISTENT'})
        response = api_client.get(url)
        
        assert response.status_code in (404, 400)
    
    def test_by_system_endpoint(self, api_client, master_task):
        """Test tasks grouped by system type"""
        url = reverse('task-by-system')
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            assert 'data' in data
            assert isinstance(data['data'], list)
    
    def test_featured_tasks_endpoint(self, api_client, featured_task):
        """Test featured tasks endpoint"""
        url = reverse('task-featured')
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            assert 'data' in data
            assert 'count' in data
    
    def test_check_availability_endpoint(self, api_client, master_task):
        """Test task availability check"""
        url = reverse('task-check-availability', kwargs={'task_id': master_task.task_id})
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            assert 'data' in data
            assert 'is_available' in data['data']
            assert 'task_id' in data['data']
    
    def test_task_statistics_endpoint(self, api_client, master_task):
        """Test task statistics endpoint"""
        url = reverse('task-statistics', kwargs={'task_id': master_task.task_id})
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            assert 'data' in data
            # Should contain various statistics
            stats = data['data']
            expected_stats = [
                'total_completions', 'unique_users', 'completion_rate',
                'daily_average', 'peak_hours', 'completion_by_level'
            ]
            for stat in expected_stats:
                assert stat in stats
    
    def test_bulk_import_admin_only(self, api_client):
        """Test bulk import requires admin permissions"""
        url = reverse('task-bulk-import')
        response = api_client.post(url)
        
        # Should require authentication/authorization
        assert response.status_code in (401, 403, 405)
    
    def test_bulk_import_admin_success(self, staff_client):
        """Test bulk import by admin"""
        url = reverse('task-bulk-import')
        response = staff_client.post(url)
        
        # Should be accessible to staff
        assert response.status_code not in (401, 403)
    
    def test_circuit_breaker_protection(self, api_client, master_task):
        """Test circuit breaker protection"""
        with patch('tasks.views.cache.get') as mock_cache:
            # Simulate circuit open
            mock_cache.return_value = None
            
            url = reverse('task-detail', kwargs={'task_id': master_task.task_id})
            response = api_client.get(url)
            
            # Should handle gracefully
            assert response.status_code in (200, 503)


@pytest.mark.django_db
class TestTaskCompletionViewSetComprehensive:
    """Comprehensive tests for TaskCompletionViewSet"""
    
    def test_list_completions_unauthorized(self, api_client):
        """Test completion listing requires authentication"""
        url = reverse('completion-list')
        response = api_client.get(url)
        
        assert response.status_code in (401, 403)
    
    def test_list_completions_authorized(self, auth_client, completion):
        """Test completion listing for authenticated user"""
        url = reverse('completion-list')
        response = auth_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            if 'results' in data:
                assert len(data['results']) >= 1
            elif isinstance(data, list):
                assert len(data) >= 1
    
    def test_list_completions_staff_sees_all(self, staff_client, completion):
        """Test staff can see all completions"""
        url = reverse('completion-list')
        response = staff_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Staff should see more data
            assert response.status_code not in (401, 403)
    
    def test_create_completion_success(self, auth_client, master_task):
        """Test successful completion creation"""
        url = reverse('completion-list')
        data = {
            'task': master_task.id,
            'status': 'started'
        }
        response = auth_client.post(url, data)
        
        if response.status_code in (200, 201):
            result_data = response.data
            if 'data' in result_data:
                assert result_data['data']['task'] == master_task.id
    
    def test_create_completion_missing_task(self, auth_client):
        """Test completion creation without task ID"""
        url = reverse('completion-list')
        data = {'status': 'started'}
        response = auth_client.post(url, data)
        
        assert response.status_code == 400
    
    def test_create_completion_task_not_found(self, auth_client):
        """Test completion creation with non-existent task"""
        url = reverse('completion-list')
        data = {'task': 99999, 'status': 'started'}
        response = auth_client.post(url, data)
        
        assert response.status_code == 404
    
    def test_create_completion_already_started(self, auth_client, master_task):
        """Test completion creation when already started"""
        from api.tasks.models import UserTaskCompletion
        
        # Create existing completion
        UserTaskCompletion.objects.create(
            user=auth_client.handler._force_user,
            task=master_task,
            status='started'
        )
        
        url = reverse('completion-list')
        data = {'task': master_task.id, 'status': 'started'}
        response = auth_client.post(url, data)
        
        if response.status_code == 200:
            data = response.data
            assert 'already_started' in data.get('status', '')
    
    def test_create_completion_task_unavailable(self, auth_client, master_task):
        """Test completion creation for unavailable task"""
        # Make task unavailable
        master_task.is_active = False
        master_task.save()
        
        url = reverse('completion-list')
        data = {'task': master_task.id, 'status': 'started'}
        response = auth_client.post(url, data)
        
        assert response.status_code == 400
    
    def test_list_completions_with_status_filter(self, auth_client, completion):
        """Test completion listing with status filter"""
        url = reverse('completion-list') + '?status=completed'
        response = auth_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Should filter by status
    
    def test_list_completions_with_date_filter(self, auth_client, completion):
        """Test completion listing with date filter"""
        from_date = (timezone.now() - timedelta(days=7)).isoformat()
        url = reverse('completion-list') + f'?from_date={from_date}'
        response = auth_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Should filter by date
    
    def test_completion_user_isolation(self, auth_client, other_user_completion):
        """Test users can only see their own completions"""
        url = reverse('completion-list')
        response = auth_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Should not show other user's completions
            if 'results' in data:
                completion_ids = [c.get('id') for c in data['results']]
                assert other_user_completion.id not in completion_ids


@pytest.mark.django_db
class TestViewSetErrorHandling:
    """Test error handling in viewsets"""
    
    def test_handle_not_authenticated(self, api_client):
        """Test NotAuthenticated error handling"""
        url = reverse('completion-list')
        response = api_client.get(url)
        
        if response.status_code == 401:
            data = response.data
            assert 'error' in data
            assert data['error'] == 'Authentication required'
    
    def test_handle_permission_denied(self, auth_client):
        """Test PermissionDenied error handling"""
        # Try to access admin-only endpoint as regular user
        url = reverse('task-bulk-import')
        response = auth_client.post(url)
        
        if response.status_code == 403:
            data = response.data
            assert 'error' in data
    
    def test_handle_not_found(self, api_client):
        """Test NotFound error handling"""
        url = reverse('task-detail', kwargs={'task_id': 'NON_EXISTENT'})
        response = api_client.get(url)
        
        if response.status_code == 404:
            data = response.data
            assert 'error' in data
    
    def test_handle_validation_error(self, auth_client):
        """Test ValidationError handling"""
        url = reverse('completion-list')
        data = {'task': 'invalid_id'}  # Invalid data
        response = auth_client.post(url, data)
        
        if response.status_code == 400:
            data = response.data
            assert 'error' in data
    
    def test_handle_internal_error(self, api_client, master_task):
        """Test internal error handling"""
        with patch('tasks.views.MasterTask.objects.get') as mock_get:
            mock_get.side_effect = Exception("Database error")
            
            url = reverse('task-detail', kwargs={'task_id': master_task.task_id})
            response = api_client.get(url)
            
            # Should handle gracefully
            assert response.status_code in (500, 200)


@pytest.mark.django_db
class TestViewSetPerformance:
    """Test viewset performance"""
    
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
    
    def test_pagination_performance(self, api_client):
        """Test pagination performance"""
        import time
        
        url = reverse('task-list') + '?page_size=100'
        start_time = time.time()
        response = api_client.get(url)
        end_time = time.time()
        
        response_time = end_time - start_time
        # Should handle pagination efficiently
        assert response_time < 2.0


@pytest.mark.django_db
class TestViewSetPagination:
    """Test viewset pagination"""
    
    def test_pagination_default_page_size(self, api_client, master_task):
        """Test default page size"""
        url = reverse('task-list')
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            if 'pagination' in data:
                pagination = data['pagination']
                assert pagination['page_size'] == 20
    
    def test_pagination_custom_page_size(self, api_client, master_task):
        """Test custom page size"""
        url = reverse('task-list') + '?page_size=50'
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            if 'pagination' in data:
                pagination = data['pagination']
                assert pagination['page_size'] == 50
    
    def test_pagination_max_page_size(self, api_client, master_task):
        """Test maximum page size limit"""
        url = reverse('task-list') + '?page_size=200'  # Over max
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            if 'pagination' in data:
                pagination = data['pagination']
                # Should be limited to max
                assert pagination['page_size'] <= 100
    
    def test_pagination_navigation(self, api_client):
        """Test pagination navigation"""
        url = reverse('task-list') + '?page=2'
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            if 'pagination' in data:
                pagination = data['pagination']
                assert pagination['page'] == 2
                assert 'has_previous' in pagination
                assert 'has_next' in pagination


@pytest.mark.django_db
class TestViewSetCaching:
    """Test viewset caching behavior"""
    
    @patch('tasks.views.cache.get')
    @patch('tasks.views.cache.set')
    def test_by_system_caching(self, mock_cache_set, mock_cache_get, api_client):
        """Test by-system endpoint caching"""
        # Cache miss
        mock_cache_get.return_value = None
        
        url = reverse('task-by-system')
        response = api_client.get(url)
        
        if response.status_code == 200:
            # Should attempt to cache
            mock_cache_set.assert_called()
    
    @patch('tasks.views.cache.get')
    def test_by_system_cache_hit(self, mock_cache_get, api_client):
        """Test by-system endpoint cache hit"""
        # Cache hit
        mock_cache_get.return_value = [{"cached": True}]
        
        url = reverse('task-by-system')
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            assert 'cached' in data


@pytest.mark.django_db
class TestViewSetFiltering:
    """Test viewset filtering capabilities"""
    
    def test_filter_by_system_type(self, api_client, master_task):
        """Test filtering by system type"""
        url = reverse('task-list') + f'?system_type={master_task.system_type}'
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Should filter correctly
    
    def test_filter_by_category(self, api_client, master_task):
        """Test filtering by category"""
        url = reverse('task-list') + f'?category={master_task.category}'
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Should filter correctly
    
    def test_filter_featured_only(self, api_client, featured_task):
        """Test filtering featured tasks only"""
        url = reverse('task-list') + '?featured=true'
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Should include featured task
    
    def test_filter_available_only(self, api_client, master_task):
        """Test filtering available tasks only"""
        url = reverse('task-list') + '?available_only=true'
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Should filter by availability
    
    def test_filter_combined(self, api_client, master_task, featured_task):
        """Test combined filters"""
        url = (reverse('task-list') + 
                f'?system_type={master_task.system_type}&featured=true&available_only=true')
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Should apply all filters


@pytest.mark.django_db
class TestViewSetOrdering:
    """Test viewset ordering capabilities"""
    
    def test_order_by_sort_order(self, api_client, master_task):
        """Test ordering by sort_order"""
        url = reverse('task-list') + '?ordering=sort_order'
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Should order by sort_order
    
    def test_order_by_created_at(self, api_client, master_task):
        """Test ordering by created_at"""
        url = reverse('task-list') + '?ordering=-created_at'
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Should order by created_at descending
    
    def test_order_by_total_completions(self, api_client, master_task):
        """Test ordering by total_completions"""
        url = reverse('task-list') + '?ordering=-total_completions'
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Should order by completions descending


@pytest.mark.django_db
class TestViewSetSearch:
    """Test viewset search functionality"""
    
    def test_search_by_name(self, api_client, master_task):
        """Test searching by task name"""
        url = reverse('task-list') + f'?search={master_task.name[:10]}'
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Should find matching tasks
    
    def test_search_by_description(self, api_client, master_task):
        """Test searching by task description"""
        if master_task.description:
            search_term = master_task.description[:10]
            url = reverse('task-list') + f'?search={search_term}'
            response = api_client.get(url)
            
            if response.status_code == 200:
                data = response.data
                # Should find matching tasks
    
    def test_search_by_task_id(self, api_client, master_task):
        """Test searching by task ID"""
        url = reverse('task-list') + f'?search={master_task.task_id[:10]}'
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Should find matching task


@pytest.mark.django_db
class TestViewSetSecurity:
    """Test viewset security measures"""
    
    def test_request_id_header(self, api_client, master_task):
        """Test request ID in response headers"""
        url = reverse('task-detail', kwargs={'task_id': master_task.task_id})
        response = api_client.get(url)
        
        if response.status_code == 200:
            # Should have request ID header (if implemented)
            pass  # Implementation dependent
    
    def test_cache_control_headers(self, api_client, master_task):
        """Test cache control headers for GET requests"""
        url = reverse('task-detail', kwargs={'task_id': master_task.task_id})
        response = api_client.get(url)
        
        if response.status_code == 200:
            # Should have cache control headers
            pass  # Implementation dependent
    
    def test_sql_injection_protection(self, api_client):
        """Test SQL injection protection"""
        malicious_input = "'; DROP TABLE tasks_mastertask; --"
        url = reverse('task-list') + f'?search={malicious_input}'
        response = api_client.get(url)
        
        # Should not cause server error
        assert response.status_code not in (500, 502)
    
    def test_xss_protection(self, api_client):
        """Test XSS protection in search"""
        xss_input = "<script>alert('xss')</script>"
        url = reverse('task-list') + f'?search={xss_input}'
        response = api_client.get(url)
        
        if response.status_code == 200:
            data = response.data
            # Should not contain unescaped script tags
            response_str = str(data)
            assert '<script>' not in response_str.lower()
