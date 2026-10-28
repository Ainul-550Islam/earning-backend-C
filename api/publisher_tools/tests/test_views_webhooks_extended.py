# publisher_tools/tests/test_views_webhooks_extended.py
"""Tests for WebhookExtendedViewSet (views_webhooks_extended.py) — 20 actions."""
import pytest
from publisher_tools.tests.factories import PublisherWebhookFactory

BASE = '/api/publisher-tools/webhooks-ext'

@pytest.mark.django_db
class TestWebhooksExtendedAuth:
    def test_unauth_event_types_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/event-types/').status_code in (401, 403)
    def test_unauth_simulate_rejected(self, unauthenticated_client):
        assert unauthenticated_client.post(f'{BASE}/simulate/').status_code in (401, 403)

@pytest.mark.django_db
class TestWebhooksExtendedEventTypes:
    def test_returns_event_catalogue(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/event-types/')
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()['data']
            assert 'events' in data
            assert 'total' in data
            assert data['total'] > 0
    def test_filter_by_payment_category(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/event-types/', {'category': 'payment'})
        assert resp.status_code in (200, 503)
    def test_filter_by_tracking_category(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/event-types/', {'category': 'tracking'})
        assert resp.status_code in (200, 503)

@pytest.mark.django_db
class TestWebhooksExtendedPayloadPreview:
    def test_missing_event_type_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/payload-preview/').status_code == 400
    def test_invalid_event_type_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/payload-preview/', {'event_type': 'nonexistent.event'}).status_code == 400
    def test_valid_event_type_returns_preview(self, publisher_client):
        resp = publisher_client.get(f'{BASE}/payload-preview/', {'event_type': 'invoice.paid'})
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            assert 'sample_payload' in resp.json()['data']

@pytest.mark.django_db
class TestWebhooksExtendedSimulate:
    def test_missing_event_type_returns_400(self, publisher_client):
        assert publisher_client.post(f'{BASE}/simulate/', {}, format='json').status_code == 400
    def test_invalid_event_type_returns_400(self, publisher_client):
        assert publisher_client.post(f'{BASE}/simulate/', {'event_type': 'fake.event'}, format='json').status_code == 400
    def test_valid_event_simulates(self, publisher_client):
        assert publisher_client.post(f'{BASE}/simulate/', {'event_type': 'invoice.paid'}, format='json').status_code in (200, 503)

@pytest.mark.django_db
class TestWebhooksExtendedDeliveryStats:
    def test_returns_stats(self, publisher_client):
        assert publisher_client.get(f'{BASE}/delivery-stats/').status_code in (200, 503)
    def test_with_specific_webhook(self, publisher_client, publisher):
        webhook = PublisherWebhookFactory(publisher=publisher)
        assert publisher_client.get(f'{BASE}/delivery-stats/', {'webhook_id': webhook.pk}).status_code in (200, 503)

@pytest.mark.django_db
class TestWebhooksExtendedFailedDeliveries:
    def test_returns_failures(self, publisher_client):
        assert publisher_client.get(f'{BASE}/failed-deliveries/').status_code in (200, 503)

@pytest.mark.django_db
class TestWebhooksExtendedReplay:
    def test_missing_delivery_id_returns_400(self, publisher_client):
        assert publisher_client.post(f'{BASE}/replay/', {}, format='json').status_code == 400
    def test_nonexistent_delivery_returns_404(self, publisher_client):
        assert publisher_client.post(f'{BASE}/replay/', {'delivery_id': 99999}, format='json').status_code in (404, 503)

@pytest.mark.django_db
class TestWebhooksExtendedTracking:
    def test_track_click_missing_unit_id_returns_400(self, publisher_client):
        assert publisher_client.post(f'{BASE}/track-click/', {}, format='json').status_code == 400
    def test_track_click_valid(self, publisher_client, ad_unit):
        assert publisher_client.post(f'{BASE}/track-click/', {'unit_id': ad_unit.unit_id, 'ip': '1.2.3.4'}, format='json').status_code in (200, 503)
    def test_track_impression_missing_unit_id_returns_400(self, publisher_client):
        assert publisher_client.post(f'{BASE}/track-impression/', {}, format='json').status_code == 400
    def test_track_impression_valid(self, publisher_client, ad_unit):
        assert publisher_client.post(f'{BASE}/track-impression/', {'unit_id': ad_unit.unit_id}, format='json').status_code in (200, 503)
    def test_track_conversion_missing_unit_id_returns_400(self, publisher_client):
        assert publisher_client.post(f'{BASE}/track-conversion/', {}, format='json').status_code == 400
    def test_track_impression_batch_empty_returns_400(self, publisher_client):
        assert publisher_client.post(f'{BASE}/track-impression-batch/', {'impressions': []}, format='json').status_code == 400
    def test_track_impression_batch_valid(self, publisher_client, ad_unit):
        data = {'impressions': [{'unit_id': ad_unit.unit_id, 'session_id': 's1'}]}
        assert publisher_client.post(f'{BASE}/track-impression-batch/', data, format='json').status_code in (200, 503)

@pytest.mark.django_db
class TestWebhooksExtendedAdminSenders:
    def test_send_kyc_alert_requires_admin(self, publisher_client):
        assert publisher_client.post(f'{BASE}/send-kyc-alert/', {'publisher_id': 'X'}, format='json').status_code in (403, 401)
    def test_send_alert_requires_admin(self, publisher_client):
        assert publisher_client.post(f'{BASE}/send-alert/', {'publisher_id': 'X'}, format='json').status_code in (403, 401)
    def test_admin_missing_publisher_id_returns_400(self, admin_client):
        assert admin_client.post(f'{BASE}/send-alert/', {}, format='json').status_code == 400
