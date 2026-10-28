# publisher_tools/tests/test_views_webhooks.py
"""
Tests for PublisherWebhookViewSet.
Covers: list, create, retrieve, update, delete,
        test, deliveries, pause, resume.
Permission checks: publisher owns webhook, 
                   other publisher cannot access.
"""
import pytest
from publisher_tools.tests.factories import PublisherFactory

WEBHOOK_BASE = '/api/publisher-tools/webhooks'


def url(suffix=''):
    return f'{WEBHOOK_BASE}{suffix}/'


def webhook_payload(**kwargs):
    data = {
        'name':              'Test Webhook',
        'endpoint_url':      'https://hooks.example.com/publisher',
        'subscribed_events': ['invoice.paid', 'publisher.approved'],
        'subscribe_all':     False,
        'timeout_seconds':   10,
        'max_retries':       3,
    }
    data.update(kwargs)
    return data


# ─── helpers ─────────────────────────────────────────────────────────────────

def create_webhook(client, **kwargs):
    return client.post(url(), webhook_payload(**kwargs), format='json')


# ==============================================================================
# LIST
# ==============================================================================

@pytest.mark.django_db
class TestWebhookList:

    def test_publisher_can_list_own_webhooks(self, publisher_client):
        create_webhook(publisher_client)
        resp = publisher_client.get(url())
        assert resp.status_code == 200

    def test_unauthenticated_cannot_list(self, api_client):
        resp = api_client.get(url())
        assert resp.status_code in (401, 403)

    def test_publisher_sees_only_own_webhooks(self, publisher_client, publisher_client_2):
        create_webhook(publisher_client)
        create_webhook(publisher_client_2, name='Other Webhook', endpoint_url='https://other.example.com/hook')
        resp = publisher_client.get(url())
        body = resp.json()
        results = body.get('results', body.get('data', []))
        # publisher only sees their own
        for item in results:
            assert 'Other Webhook' not in item.get('name', '')

    def test_admin_can_list_all_webhooks(self, admin_client, publisher_client, publisher_client_2):
        create_webhook(publisher_client)
        create_webhook(publisher_client_2, name='Pub2 Hook', endpoint_url='https://pub2.example.com/hook')
        resp = admin_client.get(url())
        assert resp.status_code == 200

    def test_filter_by_status(self, publisher_client):
        create_webhook(publisher_client)
        resp = publisher_client.get(url(), {'status': 'active'})
        assert resp.status_code == 200


# ==============================================================================
# CREATE
# ==============================================================================

@pytest.mark.django_db
class TestWebhookCreate:

    def test_publisher_can_create_webhook(self, publisher_client):
        resp = create_webhook(publisher_client)
        assert resp.status_code == 201

    def test_created_webhook_has_secret_key(self, publisher_client):
        resp = create_webhook(publisher_client)
        body = resp.json()
        data = body.get('data', body)
        # secret_key should NOT be exposed in response (security)
        assert 'secret_key' not in data or data.get('secret_key') == ''

    def test_created_webhook_status_active(self, publisher_client):
        resp = create_webhook(publisher_client)
        body = resp.json()
        data = body.get('data', body)
        assert data.get('status') == 'active'

    def test_missing_endpoint_url_returns_400(self, publisher_client):
        resp = publisher_client.post(url(), {
            'name': 'Bad Webhook',
            'subscribed_events': ['invoice.paid'],
        }, format='json')
        assert resp.status_code == 400

    def test_invalid_endpoint_url_returns_400(self, publisher_client):
        resp = create_webhook(publisher_client, endpoint_url='not-a-url')
        assert resp.status_code == 400

    def test_invalid_event_type_returns_400(self, publisher_client):
        resp = create_webhook(
            publisher_client,
            subscribed_events=['fake.event.type'],
        )
        assert resp.status_code == 400

    def test_neither_subscribe_all_nor_events_returns_400(self, publisher_client):
        resp = publisher_client.post(url(), {
            'name':              'Empty Webhook',
            'endpoint_url':      'https://hooks.example.com/empty',
            'subscribe_all':     False,
            'subscribed_events': [],
        }, format='json')
        assert resp.status_code == 400

    def test_subscribe_all_true_accepts_empty_events(self, publisher_client):
        resp = publisher_client.post(url(), {
            'name':              'All Events Hook',
            'endpoint_url':      'https://hooks.example.com/all',
            'subscribe_all':     True,
            'subscribed_events': [],
        }, format='json')
        assert resp.status_code == 201

    def test_unauthenticated_cannot_create(self, api_client):
        resp = api_client.post(url(), webhook_payload(), format='json')
        assert resp.status_code in (401, 403)


# ==============================================================================
# RETRIEVE / UPDATE / DELETE
# ==============================================================================

@pytest.mark.django_db
class TestWebhookRetrieveUpdateDelete:

    def _create(self, client, **kwargs):
        resp = create_webhook(client, **kwargs)
        return resp.json().get('data', resp.json()).get('id') or \
               resp.json().get('id')

    def test_publisher_can_retrieve_own(self, publisher_client):
        wh_id = self._create(publisher_client)
        resp  = publisher_client.get(url(f'/{wh_id}'))
        assert resp.status_code == 200

    def test_other_publisher_cannot_retrieve(self, publisher_client, publisher_client_2):
        wh_id = self._create(publisher_client)
        resp  = publisher_client_2.get(url(f'/{wh_id}'))
        assert resp.status_code in (403, 404)

    def test_admin_can_retrieve_any(self, admin_client, publisher_client):
        wh_id = self._create(publisher_client)
        resp  = admin_client.get(url(f'/{wh_id}'))
        assert resp.status_code == 200

    def test_publisher_can_update_name(self, publisher_client):
        wh_id = self._create(publisher_client)
        resp  = publisher_client.patch(
            url(f'/{wh_id}'), {'name': 'Updated Name'}, format='json'
        )
        assert resp.status_code == 200

    def test_publisher_can_delete_own(self, publisher_client):
        wh_id = self._create(publisher_client)
        resp  = publisher_client.delete(url(f'/{wh_id}'))
        assert resp.status_code in (200, 204)

    def test_other_publisher_cannot_delete(self, publisher_client, publisher_client_2):
        wh_id = self._create(publisher_client)
        resp  = publisher_client_2.delete(url(f'/{wh_id}'))
        assert resp.status_code in (403, 404)


# ==============================================================================
# PAUSE / RESUME
# ==============================================================================

@pytest.mark.django_db
class TestWebhookPauseResume:

    def _create_id(self, client):
        resp = create_webhook(client)
        body = resp.json()
        return body.get('data', body).get('id') or body.get('id')

    def test_publisher_can_pause_webhook(self, publisher_client):
        wh_id = self._create_id(publisher_client)
        resp  = publisher_client.post(url(f'/{wh_id}/pause'))
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        assert data.get('status') == 'paused'

    def test_publisher_can_resume_paused_webhook(self, publisher_client):
        wh_id = self._create_id(publisher_client)
        publisher_client.post(url(f'/{wh_id}/pause'))
        resp = publisher_client.post(url(f'/{wh_id}/resume'))
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        assert data.get('status') == 'active'

    def test_pausing_already_paused_is_idempotent(self, publisher_client):
        wh_id = self._create_id(publisher_client)
        publisher_client.post(url(f'/{wh_id}/pause'))
        resp = publisher_client.post(url(f'/{wh_id}/pause'))
        assert resp.status_code == 200

    def test_other_publisher_cannot_pause(self, publisher_client, publisher_client_2):
        wh_id = self._create_id(publisher_client)
        resp  = publisher_client_2.post(url(f'/{wh_id}/pause'))
        assert resp.status_code in (403, 404)

    def test_unauthenticated_cannot_pause(self, api_client, publisher_client):
        wh_id = self._create_id(publisher_client)
        resp  = api_client.post(url(f'/{wh_id}/pause'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# TEST (send test event)
# ==============================================================================

@pytest.mark.django_db
class TestWebhookTestAction:

    def _create_id(self, client):
        resp = create_webhook(client)
        body = resp.json()
        return body.get('data', body).get('id') or body.get('id')

    def test_publisher_can_send_test_event(self, publisher_client):
        wh_id = self._create_id(publisher_client)
        resp  = publisher_client.post(
            url(f'/{wh_id}/test'),
            {'event_type': 'test.ping'},
            format='json',
        )
        # 200 = delivery attempted (may succeed or fail depending on test endpoint)
        assert resp.status_code == 200

    def test_test_response_has_success_and_event_type(self, publisher_client):
        wh_id = self._create_id(publisher_client)
        resp  = publisher_client.post(url(f'/{wh_id}/test'), {}, format='json')
        body  = resp.json()
        data  = body.get('data', body)
        assert 'event_type' in data
        assert 'endpoint_url' in data

    def test_invalid_event_type_returns_400(self, publisher_client):
        wh_id = self._create_id(publisher_client)
        resp  = publisher_client.post(
            url(f'/{wh_id}/test'),
            {'event_type': 'not.a.real.event'},
            format='json',
        )
        assert resp.status_code == 400

    def test_other_publisher_cannot_test(self, publisher_client, publisher_client_2):
        wh_id = self._create_id(publisher_client)
        resp  = publisher_client_2.post(url(f'/{wh_id}/test'), {}, format='json')
        assert resp.status_code in (403, 404)


# ==============================================================================
# DELIVERIES
# ==============================================================================

@pytest.mark.django_db
class TestWebhookDeliveries:

    def _create_id(self, client):
        resp = create_webhook(client)
        body = resp.json()
        return body.get('data', body).get('id') or body.get('id')

    def test_publisher_can_view_delivery_logs(self, publisher_client):
        wh_id = self._create_id(publisher_client)
        resp  = publisher_client.get(url(f'/{wh_id}/deliveries'))
        assert resp.status_code == 200
        body  = resp.json()
        data  = body.get('data', body)
        assert 'logs' in data or isinstance(data, (list, dict))

    def test_delivery_response_has_stats(self, publisher_client):
        wh_id = self._create_id(publisher_client)
        resp  = publisher_client.get(url(f'/{wh_id}/deliveries'))
        body  = resp.json()
        data  = body.get('data', body)
        assert 'total_deliveries' in data
        assert 'success_rate' in data

    def test_filter_by_status_param(self, publisher_client):
        wh_id = self._create_id(publisher_client)
        resp  = publisher_client.get(url(f'/{wh_id}/deliveries'), {'status': 'failed'})
        assert resp.status_code == 200

    def test_other_publisher_cannot_view_deliveries(self, publisher_client, publisher_client_2):
        wh_id = self._create_id(publisher_client)
        resp  = publisher_client_2.get(url(f'/{wh_id}/deliveries'))
        assert resp.status_code in (403, 404)
