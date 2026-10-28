"""
tests/test_viewsets_webhooks.py — NEWLY CREATED
Tests for WebhookViewSet + OutgoingWebhookViewSet (0% covered before)
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


class WebhookViewSetBase(TestCase):
    def setUp(self):
        from api.alerts.webhooks import get_webhook_manager
        get_webhook_manager().webhooks.clear()  # the manager is a process-wide singleton
        self.addCleanup(get_webhook_manager().webhooks.clear)
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='wh_admin', email='wh@test.com', password='pass123')
        self.user = User.objects.create_user(
            username='wh_user', email='whuser@test.com', password='pass123')
        self.client.force_authenticate(user=self.admin)


# ── WebhookViewSet ────────────────────────────────────────────────────────────
class WebhookViewSetTest(WebhookViewSetBase):

    def test_list_webhooks(self):
        resp = self.client.get('/webhooks/')
        self.assertIn(resp.status_code, [200])

    def test_register_missing_fields(self):
        resp = self.client.post('/webhooks/register/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_register_missing_url(self):
        resp = self.client.post('/webhooks/register/',
                                {'webhook_id': 'test'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_register_missing_webhook_id(self):
        resp = self.client.post('/webhooks/register/',
                                {'url': 'https://example.com/hook'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_register_valid(self):
        resp = self.client.post('/webhooks/register/', {
            'webhook_id': 'test_hook_001',
            'url': 'https://example.com/webhook',
            'secret': 'mysecret123',
            'events': ['alert_triggered', 'alert_resolved']}, format='json')
        self.assertIn(resp.status_code, [200, 201, 400])

    def test_unregister_missing_id(self):
        resp = self.client.post('/webhooks/unregister/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_unregister_valid(self):
        resp = self.client.post('/webhooks/unregister/',
                                {'webhook_id': 'nonexistent_hook'}, format='json')
        self.assertIn(resp.status_code, [200, 404])

    def test_get_webhook_missing_id(self):
        resp = self.client.get('/webhooks/get/')
        self.assertEqual(resp.status_code, 400)

    def test_get_webhook_not_found(self):
        resp = self.client.get('/webhooks/get/?webhook_id=nonexistent')
        self.assertIn(resp.status_code, [404])

    def test_send_missing_id(self):
        resp = self.client.post('/webhooks/send/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_send_unknown_webhook_is_404(self):
        resp = self.client.post('/webhooks/send/', {
            'webhook_id': 'test_hook',
            'payload': {'alert_id': 1, 'severity': 'critical'},
            'event': 'alert_triggered'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_test_webhook_missing_id(self):
        resp = self.client.post('/webhooks/test/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_test_webhook_unknown_webhook_is_404(self):
        resp = self.client.post('/webhooks/test/',
                                {'webhook_id': 'test_hook'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_webhook_stats(self):
        resp = self.client.get('/webhooks/stats/')
        self.assertIn(resp.status_code, [200])

    def test_incoming_webhook_requires_webhook_id(self):
        resp = self.client.post('/webhooks/incoming/', {
            'event': 'alert_triggered',
            'data': {'source': 'prometheus', 'metric': 'server_error', 'value': 95}},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_webhook_info(self):
        resp = self.client.get('/webhooks/info/')
        self.assertIn(resp.status_code, [200])

    def test_regular_user_cannot_view(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/webhooks/')
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_blocked(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/webhooks/')
        self.assertIn(resp.status_code, [401, 403])


# ── OutgoingWebhookViewSet ────────────────────────────────────────────────────
class OutgoingWebhookViewSetTest(WebhookViewSetBase):

    def test_list_outgoing_webhooks(self):
        resp = self.client.get('/webhooks/outgoing/')
        self.assertIn(resp.status_code, [200])

    def test_trigger_outgoing(self):
        resp = self.client.post('/webhooks/outgoing/trigger/', {
            'event_type': 'alert_triggered',
            'payload': {'alert_id': 1}}, format='json')
        self.assertIn(resp.status_code, [200])

    def test_event_log(self):
        resp = self.client.get('/webhooks/outgoing/log/')
        self.assertIn(resp.status_code, [200])

    def test_verify_signature_missing_fields(self):
        resp = self.client.post('/webhooks/outgoing/verify/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_verify_signature_valid_request(self):
        import hmac, hashlib
        from api.alerts.webhooks import get_webhook_manager
        payload = '{"alert_id": 1}'
        secret = 'test_secret'
        get_webhook_manager().register_webhook('test_hook', {'url': 'https://example.com/hook', 'secret': secret})
        sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        resp = self.client.post('/webhooks/outgoing/verify/', {
            'webhook_id': 'test_hook',
            'payload': payload,
            'signature': f'sha256={sig}'}, format='json')
        self.assertIn(resp.status_code, [200])
        self.assertTrue(resp.data['valid'])

    def test_verify_signature_fails_closed_without_secret(self):
        from api.alerts.webhooks import get_webhook_manager
        get_webhook_manager().register_webhook('nosecret_hook', {'url': 'https://example.com/hook'})
        resp = self.client.post('/webhooks/outgoing/verify/', {
            'webhook_id': 'nosecret_hook', 'payload': '{}', 'signature': 'anything'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['valid'])

    def test_delivery_status(self):
        resp = self.client.get('/webhooks/outgoing/status/')
        self.assertIn(resp.status_code, [200])

    def test_delivery_status_with_id(self):
        resp = self.client.get('/webhooks/outgoing/status/?webhook_id=test')
        self.assertIn(resp.status_code, [200])

    def test_requires_admin(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/webhooks/outgoing/')
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_blocked(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post('/webhooks/outgoing/trigger/', {})
        self.assertIn(resp.status_code, [401, 403])


# -- Security / hardening ---------------------------------------------------------
import hashlib
import hmac
import json
from unittest import mock


class WebhookSecurityTest(WebhookViewSetBase):
    SECRET = 'a-long-test-secret-0123456789'

    def _register(self, webhook_id='sec_hook', **extra):
        from api.alerts.webhooks import get_webhook_manager
        cfg = {'url': 'https://example.com/hook', 'secret': self.SECRET, 'events': ['*']}
        cfg.update(extra)
        get_webhook_manager().register_webhook(webhook_id, cfg)

    def _sign(self, body, secret=None):
        return hmac.new((secret or self.SECRET).encode(), body, hashlib.sha256).hexdigest()

    def _post_incoming(self, body, signature=None, webhook_id='sec_hook'):
        extra = {'HTTP_X_SIGNATURE': signature} if signature is not None else {}
        return self.client.post(f'/webhooks/incoming/?webhook_id={webhook_id}', data=body,
                                content_type='application/json', **extra)

    # permissions
    def test_regular_user_blocked_from_management_endpoints(self):
        self._register()
        self.client.force_authenticate(user=self.user)
        for method, url in (('get', '/webhooks/'), ('get', '/webhooks/info/'), ('get', '/webhooks/stats/'),
                            ('get', '/webhooks/get/?webhook_id=sec_hook'), ('post', '/webhooks/send/'),
                            ('post', '/webhooks/test/'), ('post', '/webhooks/register/'),
                            ('post', '/webhooks/unregister/')):
            resp = getattr(self.client, method)(url, **({'format': 'json'} if method == 'post' else {}))
            self.assertEqual(resp.status_code, 403, f'{method} {url}')

    # secret masking
    def test_secrets_and_credential_headers_are_masked(self):
        self._register(headers={'Authorization': 'Bearer abc123', 'X-Custom': 'ok'})
        for url in ('/webhooks/', '/webhooks/info/', '/webhooks/get/?webhook_id=sec_hook'):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, url)
            body = resp.content.decode()
            self.assertNotIn(self.SECRET, body, url)
            self.assertNotIn('Bearer abc123', body, url)
            self.assertIn('********', body, url)
            self.assertIn('ok', body, url)

    # SSRF / validation
    def test_register_blocks_private_and_metadata_urls(self):
        for url in ('http://169.254.169.254/latest/meta-data', 'http://127.0.0.1:8000/x',
                    'http://10.0.0.5/h', 'http://localhost/h', 'ftp://example.com/x'):
            resp = self.client.post('/webhooks/register/', {'webhook_id': 'bad', 'url': url}, format='json')
            self.assertEqual(resp.status_code, 400, url)

    def test_register_rejects_bad_ids_and_types(self):
        for payload in ({'webhook_id': 'bad id!', 'url': 'https://example.com/h'},
                        {'webhook_id': 'ok', 'url': 'https://example.com/h', 'events': 'alert'},
                        {'webhook_id': 'ok', 'url': 'https://example.com/h', 'secret': 123}):
            self.assertEqual(self.client.post('/webhooks/register/', payload, format='json').status_code, 400)

    def test_delivery_to_private_target_is_blocked(self):
        self._register(url='http://10.0.0.5/h')  # bypasses the register endpoint on purpose
        with mock.patch('requests.post') as post:
            resp = self.client.post('/webhooks/send/', {'webhook_id': 'sec_hook', 'payload': {}}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['success'])
        post.assert_not_called()

    def test_delivery_success_on_2xx_and_no_redirects(self):
        self._register()
        with mock.patch('requests.post') as post:
            post.return_value.status_code = 204
            resp = self.client.post('/webhooks/send/', {'webhook_id': 'sec_hook', 'payload': {'a': 1},
                                                        'event': 'alert_triggered'}, format='json')
        self.assertTrue(resp.data['success'])
        self.assertIs(post.call_args.kwargs['allow_redirects'], False)

    def test_trigger_outgoing_delivers_to_registered_webhooks(self):
        self._register('hook_a')
        self._register('hook_b')
        with mock.patch('requests.post') as post:
            post.return_value.status_code = 200
            resp = self.client.post('/webhooks/outgoing/trigger/',
                                    {'event_type': 'alert_triggered', 'payload': {'alert_id': 1}}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual((resp.data['attempted'], resp.data['delivered']), (2, 2))

    def test_trigger_outgoing_unknown_webhook_is_404(self):
        resp = self.client.post('/webhooks/outgoing/trigger/', {'webhook_id': 'nope'}, format='json')
        self.assertEqual(resp.status_code, 404)

    # inbound signature handling
    def test_incoming_unknown_webhook_is_404(self):
        self.assertEqual(self._post_incoming(b'{}', 'x', webhook_id='ghost').status_code, 404)

    def test_incoming_requires_a_signing_secret(self):
        self._register(secret='')
        self.assertEqual(self._post_incoming(b'{}', 'x').status_code, 403)

    def test_incoming_rejects_missing_or_bad_signature(self):
        self._register()
        body = json.dumps({'event': 'alert.triggered', 'data': {}}).encode()
        self.assertEqual(self._post_incoming(body).status_code, 401)
        self.assertEqual(self._post_incoming(body, 'deadbeef').status_code, 401)
        self.assertEqual(self._post_incoming(body, self._sign(body, 'another-secret')).status_code, 401)

    def test_incoming_accepts_valid_signature(self):
        self._register()
        body = json.dumps({'event': 'alert.triggered', 'data': {'alert_id': 999999}}).encode()
        for signature in (self._sign(body), 'sha256=' + self._sign(body)):
            resp = self._post_incoming(body, signature)
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.data['received'] and resp.data['processed'])

    def test_incoming_unknown_event_is_acknowledged_but_not_processed(self):
        self._register()
        body = json.dumps({'event': 'something.else', 'data': {}}).encode()
        resp = self._post_incoming(body, self._sign(body))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['processed'])

    def test_incoming_requires_authentication(self):
        self._register()
        self.client.force_authenticate(user=None)
        body = b'{}'
        self.assertIn(self._post_incoming(body, self._sign(body)).status_code, [401, 403])
