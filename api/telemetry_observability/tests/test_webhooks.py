"""
Tests for webhooks.py — WebhookDispatcher payload building and delivery.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from ..webhooks import WebhookDispatcher, _build_alert_payload, _build_health_payload
from ..events import Event, EventType


def make_alert_event(event_type=EventType.ALERT_TRIGGERED):
    return Event(event_type, {
        'alert_id': 1, 'name': 'High CPU', 'severity': 'critical',
        'status': 'open', 'service': 'api', 'message': 'CPU is high',
    })


class TestWebhookDispatcher:
    def test_no_urls_skips_dispatch(self):
        """Dispatcher with no URLs should not make any HTTP calls."""
        dispatcher = WebhookDispatcher(urls=[])
        event      = make_alert_event()
        with patch('api.telemetry_observability.webhooks.urlopen') as mock_open:
            dispatcher.on_alert_triggered(event)
            mock_open.assert_not_called()

    def test_delivers_to_single_url(self):
        dispatcher = WebhookDispatcher(urls=['https://example.com/webhook'])
        event      = make_alert_event()
        mock_resp  = MagicMock()
        mock_resp.status = 200
        with patch('api.telemetry_observability.webhooks.urlopen',
                   return_value=MagicMock(__enter__=MagicMock(return_value=mock_resp),
                                         __exit__=MagicMock(return_value=False))):
            dispatcher.on_alert_triggered(event)

    def test_delivers_to_multiple_urls(self):
        urls       = ['https://url1.com/hook', 'https://url2.com/hook']
        dispatcher = WebhookDispatcher(urls=urls)
        event      = make_alert_event()
        call_count = [0]

        def fake_urlopen(req, timeout=5):
            call_count[0] += 1
            m = MagicMock()
            m.__enter__ = MagicMock(return_value=MagicMock(status=200))
            m.__exit__  = MagicMock(return_value=False)
            return m

        with patch('api.telemetry_observability.webhooks.urlopen', side_effect=fake_urlopen):
            dispatcher.on_alert_triggered(event)

        assert call_count[0] == 2

    def test_payload_contains_event_type(self):
        captured = []
        dispatcher = WebhookDispatcher(urls=['https://example.com/hook'])

        def fake_urlopen(req, timeout=5):
            captured.append(json.loads(req.data))
            m = MagicMock()
            m.__enter__ = MagicMock(return_value=MagicMock(status=200))
            m.__exit__  = MagicMock(return_value=False)
            return m

        with patch('api.telemetry_observability.webhooks.urlopen', side_effect=fake_urlopen):
            dispatcher.on_alert_triggered(make_alert_event())

        assert len(captured) == 1
        assert captured[0]['event'] == 'alert_triggered'

    def test_payload_contains_alert_data(self):
        captured = []
        dispatcher = WebhookDispatcher(urls=['https://example.com/hook'])

        def fake_urlopen(req, timeout=5):
            captured.append(json.loads(req.data))
            m = MagicMock()
            m.__enter__ = MagicMock(return_value=MagicMock(status=200))
            m.__exit__  = MagicMock(return_value=False)
            return m

        with patch('api.telemetry_observability.webhooks.urlopen', side_effect=fake_urlopen):
            dispatcher.on_alert_triggered(make_alert_event())

        assert captured[0]['data']['severity'] == 'critical'

    def test_hmac_signature_added_when_secret_set(self):
        import hashlib, hmac
        captured_headers = []
        dispatcher = WebhookDispatcher(urls=['https://example.com/hook'], secret='my-secret')

        def fake_urlopen(req, timeout=5):
            captured_headers.append(dict(req.headers))
            m = MagicMock()
            m.__enter__ = MagicMock(return_value=MagicMock(status=200))
            m.__exit__  = MagicMock(return_value=False)
            return m

        with patch('api.telemetry_observability.webhooks.urlopen', side_effect=fake_urlopen):
            dispatcher.on_alert_triggered(make_alert_event())

        headers = {k.lower(): v for k, v in captured_headers[0].items()}
        assert 'x-telemetry-signature' in headers
        assert headers['x-telemetry-signature'].startswith('sha256=')

    def test_no_signature_without_secret(self):
        captured_headers = []
        dispatcher = WebhookDispatcher(urls=['https://example.com/hook'], secret='')

        def fake_urlopen(req, timeout=5):
            captured_headers.append(dict(req.headers))
            m = MagicMock()
            m.__enter__ = MagicMock(return_value=MagicMock(status=200))
            m.__exit__  = MagicMock(return_value=False)
            return m

        with patch('api.telemetry_observability.webhooks.urlopen', side_effect=fake_urlopen):
            dispatcher.on_alert_triggered(make_alert_event())

        headers = {k.lower(): v for k, v in captured_headers[0].items()}
        assert 'x-telemetry-signature' not in headers

    def test_retry_on_failure(self):
        from urllib.error import URLError
        call_count = [0]
        dispatcher = WebhookDispatcher(urls=['https://example.com/hook'], max_retries=2)

        def fake_urlopen(req, timeout=5):
            call_count[0] += 1
            raise URLError("Connection refused")

        with patch('api.telemetry_observability.webhooks.urlopen', side_effect=fake_urlopen), \
             patch('api.telemetry_observability.webhooks.time.sleep'):
            dispatcher.on_alert_triggered(make_alert_event())

        assert call_count[0] == 3  # 1 initial + 2 retries

    def test_add_url(self):
        dispatcher = WebhookDispatcher(urls=[])
        dispatcher.add_url('https://new.example.com/hook')
        assert 'https://new.example.com/hook' in dispatcher.urls

    def test_add_url_no_duplicates(self):
        dispatcher = WebhookDispatcher(urls=['https://example.com/hook'])
        dispatcher.add_url('https://example.com/hook')
        assert dispatcher.urls.count('https://example.com/hook') == 1

    def test_remove_url(self):
        url        = 'https://example.com/hook'
        dispatcher = WebhookDispatcher(urls=[url])
        result     = dispatcher.remove_url(url)
        assert result is True
        assert url not in dispatcher.urls

    def test_remove_nonexistent_url(self):
        dispatcher = WebhookDispatcher(urls=[])
        result     = dispatcher.remove_url('https://nonexistent.com')
        assert result is False

    def test_on_alert_acknowledged(self):
        event      = Event(EventType.ALERT_ACKNOWLEDGED, {'alert_id': 1, 'acknowledged_by': 'ops'})
        dispatcher = WebhookDispatcher(urls=['https://example.com/hook'])
        call_count = [0]

        def fake_urlopen(req, timeout=5):
            call_count[0] += 1
            m = MagicMock()
            m.__enter__ = MagicMock(return_value=MagicMock(status=200))
            m.__exit__  = MagicMock(return_value=False)
            return m

        with patch('api.telemetry_observability.webhooks.urlopen', side_effect=fake_urlopen):
            dispatcher.on_alert_acknowledged(event)

        assert call_count[0] == 1

    def test_on_alert_resolved(self):
        event      = Event(EventType.ALERT_RESOLVED, {'alert_id': 1, 'status': 'resolved'})
        dispatcher = WebhookDispatcher(urls=['https://example.com/hook'])
        call_count = [0]

        def fake_urlopen(req, timeout=5):
            call_count[0] += 1
            m = MagicMock()
            m.__enter__ = MagicMock(return_value=MagicMock(status=200))
            m.__exit__  = MagicMock(return_value=False)
            return m

        with patch('api.telemetry_observability.webhooks.urlopen', side_effect=fake_urlopen):
            dispatcher.on_alert_resolved(event)

        assert call_count[0] == 1


class TestPayloadBuilders:
    def test_alert_payload_has_required_keys(self):
        event   = make_alert_event()
        payload = _build_alert_payload(event)
        assert 'event'     in payload
        assert 'data'      in payload
        assert 'timestamp' in payload
        assert 'source'    in payload
        assert payload['source'] == 'telemetry_observability'

    def test_health_payload_has_required_keys(self):
        event   = Event(EventType.HEALTH_STATUS_CHANGED, {'service_name': 'svc'})
        payload = _build_health_payload(event)
        assert 'event'     in payload
        assert 'data'      in payload
        assert 'timestamp' in payload
