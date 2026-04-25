# FILE 126 of 257 — tests/conftest.py
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        username='testuser', email='test@example.com',
        password='testpass123', balance=Decimal('10000')
    )

@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username='admin', email='admin@example.com', password='adminpass123'
    )

@pytest.fixture
def completed_transaction(db, test_user):
    from payment_gateways.models import GatewayTransaction
    return GatewayTransaction.objects.create(
        user=test_user, gateway='bkash', transaction_type='deposit',
        amount=Decimal('500'), fee=Decimal('7.5'), net_amount=Decimal('492.5'),
        status='completed', reference_id='BKASH_TEST_001',
        gateway_reference='PAY_001', metadata={}
    )

@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()

@pytest.fixture
def auth_client(api_client, test_user):
    api_client.force_authenticate(user=test_user)
    return api_client

@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client
