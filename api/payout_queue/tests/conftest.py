"""
payout_queue/tests/conftest.py
================================
pytest-django configuration for the payout_queue test suite.

Run all payout_queue tests with:
    pytest api/payout_queue/tests/ -v

Or a single file:
    pytest api/payout_queue/tests/test_services.py -v -k "test_create"

Coverage:
    pytest api/payout_queue/tests/ --cov=api.payout_queue --cov-report=html

SETTINGS
--------
Set DJANGO_SETTINGS_MODULE to match your project. Adjust the value below
if your settings module path differs from 'config.settings.test'.
"""
import django
import pytest

def pytest_configure(config):
    import os
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "config.settings.test",
    )
    django.setup()

@pytest.fixture(scope="session")
def django_db_setup():
    """Use default Django test database setup."""
    pass

@pytest.fixture(autouse=True)
def reset_cache():
    """Clear Django cache between tests to prevent state leakage."""
    from django.core.cache import cache
    yield
    cache.clear()

@pytest.fixture
def staff_user(db):
    """Return a staff user for API authentication."""
    from api.payout_queue.tests.factories import StaffUserFactory
    return StaffUserFactory()

@pytest.fixture
def regular_user(db):
    """Return a non-staff user."""
    from api.payout_queue.tests.factories import UserFactory
    return UserFactory()

@pytest.fixture
def api_client():
    """Unauthenticated DRF API client."""
    from rest_framework.test import APIClient
    return APIClient()

@pytest.fixture
def staff_client(staff_user):
    """DRF API client authenticated as a staff user."""
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client

@pytest.fixture
def pending_batch(db, staff_user):
    """A PENDING PayoutBatch ready for testing."""
    from api.payout_queue.tests.factories import PayoutBatchFactory
    from api.payout_queue.choices import PayoutBatchStatus, PaymentGateway
    return PayoutBatchFactory(
        status=PayoutBatchStatus.PENDING,
        gateway=PaymentGateway.BKASH,
        created_by=staff_user,
    )

@pytest.fixture
def queued_item(db, pending_batch):
    """A QUEUED PayoutItem inside a PENDING batch."""
    from api.payout_queue.tests.factories import PayoutItemFactory, UserFactory
    from api.payout_queue.choices import PayoutItemStatus
    return PayoutItemFactory(
        batch=pending_batch,
        status=PayoutItemStatus.QUEUED,
        user=UserFactory(),
    )
