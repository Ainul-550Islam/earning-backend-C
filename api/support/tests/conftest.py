# api/support/tests/conftest.py
"""
pytest conftest — shared fixtures for all support tests.
"""
import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(
        username='testuser', email='test@test.com', password='pass123'
    )


@pytest.fixture
def staff_user(db):
    User = get_user_model()
    return User.objects.create_user(
        username='staffuser', email='staff@test.com',
        password='pass123', is_staff=True
    )


@pytest.fixture
def ticket(db, user):
    from api.support.models import SupportTicket
    return SupportTicket.objects.create(
        user=user, subject='Test ticket',
        description='Test description text.', category='technical',
    )


@pytest.fixture
def faq(db):
    from api.support.models import FAQ
    return FAQ.objects.create(
        question='Test FAQ?', answer='Yes, it is.', category='general', is_active=True
    )


@pytest.fixture
def support_settings(db):
    from api.support.models import SupportSettings
    obj, _ = SupportSettings.objects.get_or_create(id=1)
    return obj


@pytest.fixture
def offer_dispute(db, user):
    from api.support.models import OfferDispute
    return OfferDispute.objects.create(
        user=user, offer_id='OFF_TEST_001', expected_amount=50, status='pending'
    )


@pytest.fixture
def chat_session(db, user):
    from api.support.models import ChatSession
    return ChatSession.objects.create(user=user, status='active')


@pytest.fixture
def api_client(user):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_client(staff_user):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client