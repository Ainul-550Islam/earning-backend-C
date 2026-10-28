import hmac
import hashlib
from django.test import TestCase, RequestFactory
from django.conf import settings
from unittest.mock import patch


class PostbackViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        # Ensure test secret is set
        if not hasattr(settings, 'SMARTLINK_POSTBACK_SECRET'):
            settings.SMARTLINK_POSTBACK_SECRET = 'test-secret-key'
        settings.SMARTLINK_BASE_URL = 'https://go.example.com'

    def _make_token(self, offer_id: str, click_id: str = '') -> str:
        """Match PostbackView._validate_token: HMAC-SHA256(offer_id only)[:16]."""
        secret  = getattr(settings, 'SMARTLINK_POSTBACK_SECRET', 'test-secret-key')
        return hmac.new(secret.encode(), offer_id.encode(), hashlib.sha256).hexdigest()[:16]

    def _make_v2_token(self, offer_id: str, click_id: str = '') -> str:
        """Match PostbackV2View._validate_token: HMAC-SHA256(offer_id:click_id)[:16]."""
        secret  = getattr(settings, 'SMARTLINK_POSTBACK_SECRET', 'test-secret-key')
        payload = f"{offer_id}:{click_id}"
        return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]

    @patch('api.smartlink.tasks.click_processing_tasks.attribute_conversion')
    def test_valid_postback_returns_ok(self, mock_task):
        from ..postback.views import PostbackView
        mock_task.delay = lambda **kw: None
        token   = self._make_token('456', '123')
        request = self.factory.get(
            '/postback/',
            {'click_id': '123', 'offer_id': '456',
             'payout': '2.50', 'token': token}
        )
        view = PostbackView.as_view()
        resp = view(request)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b'OK')

    def test_invalid_token_returns_403(self):
        from ..postback.views import PostbackView
        request = self.factory.get(
            '/postback/',
            {'click_id': '123', 'offer_id': '456',
             'payout': '2.50', 'token': 'wrongtoken12345'}
        )
        view = PostbackView.as_view()
        resp = view(request)
        self.assertEqual(resp.status_code, 403)

    def test_missing_token_returns_403(self):
        from ..postback.views import PostbackView
        request = self.factory.get(
            '/postback/',
            {'click_id': '123', 'offer_id': '456', 'payout': '1.00'}
        )
        view = PostbackView.as_view()
        resp = view(request)
        self.assertEqual(resp.status_code, 403)

    @patch('api.smartlink.tasks.click_processing_tasks.attribute_conversion')
    def test_v2_postback_valid_event(self, mock_task):
        from ..postback.v2.views import PostbackV2View
        mock_task.delay = lambda **kw: None
        token   = self._make_v2_token('789', '100')
        request = self.factory.get(
            '/api/v2/postback/',
            {'click_id': '100', 'offer_id': '789',
             'event': 'lead', 'payout': '5.00', 'token': token,
             'transaction_id': 'txn_abc123'}
        )
        view = PostbackV2View.as_view()
        resp = view(request)
        self.assertEqual(resp.status_code, 200)

    @patch('api.smartlink.tasks.click_processing_tasks.attribute_conversion')
    def test_v2_invalid_event_rejected(self, mock_task):
        from ..postback.v2.views import PostbackV2View
        token   = self._make_v2_token('789', '100')
        request = self.factory.get(
            '/api/v2/postback/',
            {'click_id': '100', 'offer_id': '789',
             'event': 'INVALID_EVENT', 'payout': '5.00', 'token': token}
        )
        view = PostbackV2View.as_view()
        resp = view(request)
        self.assertEqual(resp.status_code, 400)