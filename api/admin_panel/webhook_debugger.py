# api/admin_panel/webhook_debugger.py
"""Webhook payload inspector, replay, and delivery testing tool."""
from __future__ import annotations
import json
import logging
from typing import Any, Dict, List, Optional
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)
BUFFER_KEY = 'admin_panel:webhook_debug_buffer'
BUFFER_SIZE = 500


class WebhookDebugger:
    """Debug and test webhook deliveries."""

    @classmethod
    def log_outgoing(cls, url: str, event_type: str, payload: Dict,
                      status_code: int, response: str, success: bool) -> None:
        """Log an outgoing webhook delivery to debug buffer."""
        import uuid
        entry = {
            'id':           str(uuid.uuid4()),
            'url':          url,
            'event_type':   event_type,
            'payload':      payload,
            'status_code':  status_code,
            'response':     response[:500],
            'success':      success,
            'timestamp':    timezone.now().isoformat(),
        }
        buffer = cache.get(BUFFER_KEY) or []
        buffer.insert(0, entry)
        cache.set(BUFFER_KEY, buffer[:BUFFER_SIZE], 86400)

    @classmethod
    def get_recent_deliveries(cls, limit: int = 50, event_type: str = '',
                               success: Optional[bool] = None) -> List[Dict]:
        buffer = cache.get(BUFFER_KEY) or []
        if event_type:
            buffer = [e for e in buffer if e.get('event_type') == event_type]
        if success is not None:
            buffer = [e for e in buffer if e.get('success') == success]
        return buffer[:limit]

    @classmethod
    def replay_delivery(cls, delivery_id: str, actor) -> Dict:
        """Replay a webhook delivery by ID."""
        buffer = cache.get(BUFFER_KEY) or []
        delivery = next((e for e in buffer if e.get('id') == delivery_id), None)
        if not delivery:
            return {'success': False, 'error': 'Delivery not found in buffer'}
        try:
            import requests
            resp = requests.post(
                delivery['url'],
                json=delivery['payload'],
                headers={'Content-Type': 'application/json', 'X-AdminPanel-Replay': 'true'},
                timeout=10
            )
            result = {'success': resp.status_code < 400, 'status_code': resp.status_code,
                      'response': resp.text[:200], 'replayed_at': timezone.now().isoformat()}
            cls.log_outgoing(delivery['url'], delivery['event_type'], delivery['payload'],
                              resp.status_code, resp.text[:200], resp.status_code < 400)
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=actor, action='replay_webhook',
                              changes={'delivery_id': delivery_id, 'url': delivery['url']})
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def test_url(cls, url: str, event_type: str, sample_payload: Dict, actor) -> Dict:
        """Send a test webhook to any URL."""
        try:
            import requests, uuid
            payload = {
                'event': event_type,
                'data': sample_payload,
                'test': True,
                'timestamp': timezone.now().isoformat(),
                'event_id': str(uuid.uuid4()),
            }
            resp = requests.post(url, json=payload,
                                  headers={'Content-Type': 'application/json',
                                           'X-AdminPanel-Event': event_type,
                                           'X-AdminPanel-Test': 'true'},
                                  timeout=10)
            cls.log_outgoing(url, event_type, payload, resp.status_code, resp.text[:200], resp.status_code < 400)
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=actor, action='test_webhook_url',
                              changes={'url': url, 'event': event_type, 'status': resp.status_code})
            return {'success': resp.status_code < 400, 'status_code': resp.status_code,
                    'response': resp.text[:500], 'url': url}
        except Exception as e:
            return {'success': False, 'error': str(e), 'url': url}

    @classmethod
    def get_delivery_stats(cls) -> Dict:
        buffer = cache.get(BUFFER_KEY) or []
        total = len(buffer)
        success = sum(1 for e in buffer if e.get('success'))
        failed = total - success
        by_event = {}
        for e in buffer:
            evt = e.get('event_type', 'unknown')
            by_event[evt] = by_event.get(evt, 0) + 1
        return {'total': total, 'success': success, 'failed': failed,
                'success_rate': round(success / max(total, 1) * 100, 1),
                'by_event': sorted(by_event.items(), key=lambda x: x[1], reverse=True)[:10]}

webhook_debugger = WebhookDebugger()