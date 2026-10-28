"""
Pytest configuration for webhooks tests

Provides fixtures and configuration for all test modules.

BUG FIX: this file previously imported a `WebhookEventType` model that
doesn't exist anywhere in models/ (EventType is a TextChoices enum in
constants.py, not a database model - you can't .objects.create() it), and
used field names (name/url/is_active) that don't match the real
WebhookEndpoint model (label/target_url/status). Both are corrected below.
"""

import os
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.settings_test')

# Setup Django
django.setup()

import pytest
from django.contrib.auth.models import User
from api.webhooks.models import WebhookEndpoint
from api.webhooks.constants import WebhookStatus


@pytest.fixture
def test_user(db):
    """Create a test user"""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def test_endpoint(db, test_user):
    """Create a test webhook endpoint"""
    return WebhookEndpoint.objects.create(
        label='Test Endpoint',
        target_url='https://example.com/webhook',
        owner=test_user,
        status=WebhookStatus.ACTIVE,
    )


@pytest.fixture
def test_event_type():
    """A valid event type string (EventType is a choices enum, not a model)."""
    return 'user.created'


@pytest.fixture
def authenticated_client(test_user):
    """Create an authenticated API client"""
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=test_user)
    return client
