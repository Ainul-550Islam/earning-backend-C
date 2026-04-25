# FILE 130 of 257 — tests/test_views.py
import pytest
from decimal import Decimal

@pytest.mark.django_db
class TestGatewayTransactionViewSet:
    def test_list_authenticated(self, auth_client):
        resp = auth_client.get('/api/payment/transactions/')
        assert resp.status_code == 200

    def test_list_unauthenticated(self, api_client):
        resp = api_client.get('/api/payment/transactions/')
        assert resp.status_code == 401

    def test_history_endpoint(self, auth_client):
        resp = auth_client.get('/api/payment/transactions/history/')
        assert resp.status_code == 200

@pytest.mark.django_db
class TestPaymentGatewayViewSet:
    def test_active_gateways_list(self, auth_client):
        resp = auth_client.get('/api/payment/gateways/active/')
        assert resp.status_code in (200, 403)

    def test_user_deposit_gateways(self, auth_client):
        resp = auth_client.get('/api/payment/user/gateways/deposit/')
        assert resp.status_code == 200

@pytest.mark.django_db
class TestRefundRequestViewSet:
    def test_my_refunds_empty(self, auth_client):
        resp = auth_client.get('/api/payment/refunds/refunds/my_refunds/')
        assert resp.status_code == 200

    def test_admin_pending_refunds(self, admin_client):
        resp = admin_client.get('/api/payment/refunds/refunds/pending/')
        assert resp.status_code == 200
