# earning_backend/api/notifications/conftest.py
"""
Pytest configuration and shared fixtures for notification tests.
"""
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='testuser', email='test@example.com', password='testpass123'
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username='admin', email='admin@example.com', password='adminpass123'
    )


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def notification(db, user):
    from notifications.models import Notification
    return Notification.objects.create(
        user=user,
        title='Test Notification',
        message='Test message body',
        notification_type='announcement',
        channel='in_app',
        priority='medium',
    )


@pytest.fixture
def push_device(db, user):
    from notifications.models.channel import PushDevice
    return PushDevice.objects.create(
        user=user,
        device_type='android',
        fcm_token='test_fcm_token_abc123',
        device_name='Test Android Phone',
    )


@pytest.fixture
def in_app_message(db, user, notification):
    from notifications.models.channel import InAppMessage
    return InAppMessage.objects.create(
        user=user,
        notification=notification,
        message_type='toast',
        title='Test In-App',
        body='Test body',
    )


@pytest.fixture
def campaign_segment(db, user):
    from notifications.models.campaign import CampaignSegment
    return CampaignSegment.objects.create(
        name='All Users',
        segment_type='all',
        conditions={},
        created_by=user,
    )


@pytest.fixture
def notification_template(db, user):
    from notifications.models import NotificationTemplate
    return NotificationTemplate.objects.create(
        name='test_template',
        title_en='Test Title',
        message_en='Test message for {{ user.username }}',
        notification_type='announcement',
        channel='in_app',
        is_active=True,
        created_by=user,
    )


@pytest.fixture
def opt_out_record(db, user):
    from notifications.models.analytics import OptOutTracking
    return OptOutTracking.opt_out(user, 'email', reason='too_many')


@pytest.fixture
def fatigue_record(db, user):
    from notifications.models.analytics import NotificationFatigue
    record, _ = NotificationFatigue.objects.get_or_create(user=user)
    return record
