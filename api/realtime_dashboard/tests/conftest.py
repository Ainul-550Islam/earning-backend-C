"""
Pytest configuration for Real-time Dashboard Backend tests.
"""
import pytest
from django.test import Client
from django.contrib.auth import get_user_model


@pytest.fixture
def client():
    """
    Fixture for Django test client.
    """
    return Client()


@pytest.fixture
def api_client():
    """
    Fixture for API test client.
    """
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def test_user(db):
    """
    Fixture for creating a test user.
    """
    User = get_user_model()
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def authenticated_client(client, test_user):
    """
    Fixture for authenticated client.
    """
    client.force_login(test_user)
    return client


@pytest.fixture
def authenticated_api_client(api_client, test_user):
    """
    Fixture for authenticated API client.
    """
    api_client.force_authenticate(user=test_user)
    return api_client


@pytest.fixture
def sample_dashboard_data():
    """
    Fixture for sample dashboard data.
    """
    return {
        'name': 'Test Dashboard',
        'description': 'A test dashboard',
        'status': 'active',
        'user_id': 'test_user_123',
        'widgets': [],
        'metadata': {},
        'tags': ['test']
    }


@pytest.fixture
def sample_widget_data():
    """
    Fixture for sample widget data.
    """
    return {
        'name': 'Test Widget',
        'description': 'A test widget',
        'widget_type': 'chart',
        'status': 'active',
        'configuration': {},
        'data_source': 'test_source',
        'refresh_interval': 60,
        'width': 6,
        'height': 4,
        'metadata': {},
        'tags': ['test'],
        'created_by': 'test_user'
    }


@pytest.fixture
def sample_metric_data():
    """
    Fixture for sample metric data.
    """
    return {
        'name': 'Test Metric',
        'description': 'A test metric',
        'metric_type': 'gauge',
        'status': 'active',
        'value': 100.0,
        'unit': 'units',
        'warning_threshold': 80.0,
        'critical_threshold': 90.0,
        'metadata': {},
        'tags': ['test']
    }


# ── Additional fixtures added in V4 ─────────────────────────────────────────
# These are needed for:
#   - Ownership isolation tests (second_user cannot access test_user's data)
#   - IsAdminOrReadOnly tests (staff_user can write layouts; test_user cannot)


@pytest.fixture
def staff_user(db):
    """Staff (admin) user — can write to admin-only endpoints."""
    User = get_user_model()
    return User.objects.create_user(
        username='staffuser',
        email='staff@example.com',
        password='staffpass123',
        is_staff=True,
    )


@pytest.fixture
def second_user(db):
    """A second regular user — used to test ownership isolation."""
    User = get_user_model()
    return User.objects.create_user(
        username='seconduser',
        email='second@example.com',
        password='secondpass123',
    )


@pytest.fixture
def authenticated_staff_client(staff_user):
    """API client authenticated as the staff user (own instance — not shared with other clients)."""
    from rest_framework.test import APIClient
    c = APIClient()
    c.force_authenticate(user=staff_user)
    return c


@pytest.fixture
def authenticated_second_client(second_user):
    """API client authenticated as the second user (own instance — not shared with other clients)."""
    from rest_framework.test import APIClient
    c = APIClient()
    c.force_authenticate(user=second_user)
    return c


@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    """
    Clear Django's cache before and after every test.

    Rationale: RealTimeMetricService and WidgetService cache ORM instances
    with cache.set(key, obj). Django's test runner wraps each test in a DB
    transaction that is rolled back — but the cache is NOT rolled back.
    After rollback, SQLite reuses the same auto-increment PK for the next
    test's DB object. If a previous test left a cached instance under that
    PK, the next test sees the stale cached object instead of the freshly
    created one, causing "AssertionError: 'FreshMetric' != 'FoundMetric'"-
    style failures that only appear in full-suite runs (never in isolation).
    """
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()
