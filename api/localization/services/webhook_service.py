# services/webhook_service.py — Full webhook management with retry + DB log
import json
import hashlib
import hmac
import time
import logging
import urllib.request
import urllib.error
from typing import List, Dict
from django.utils import timezone

logger = logging.getLogger(__name__)

EVENTS = [
    'translation.updated', 'translation.approved', 'coverage.changed',
    'language.activated', 'pack.built', 'missing.detected', 'qa.failed',
    'key.created', 'key.deleted', 'screenshot.uploaded',
]


class WebhookService:
    """
    Full webhook delivery service with:
    - DB registration management
    - HMAC-SHA256 signature
    - Retry on failure (3x with exponential backoff)
    - Delivery log
    """

    def deliver(self, event: str, payload: Dict) -> List[Dict]:
        """Registered webhooks-এ event deliver করে"""
        results = []
        try:
            from ..models.settings import WebhookRegistration
            webhooks = WebhookRegistration.objects.filter(
                is_active=True
            ).filter(
                events__contains=[event]
            ) | WebhookRegistration.objects.filter(
                is_active=True,
                events__contains=['*']
            )

            body = json.dumps({
                'event': event,
                'timestamp': timezone.now().isoformat(),
                'payload': payload,
            }, ensure_ascii=False)

            for webhook in webhooks.distinct():
                result = self._deliver_with_retry(webhook, event, body, payload)
                results.append(result)

        except Exception as e:
            logger.error(f"WebhookService.deliver failed: {e}")

        return results

    def _deliver_with_retry(self, webhook, event: str, body: str, payload: Dict) -> Dict:
        """Retry logic সহ delivery"""
        last_result = {}
        for attempt in range(1, webhook.retry_count + 1):
            result = self._deliver_once(webhook, event, body, attempt)
            last_result = result
            if result.get('success'):
                break
            # Exponential backoff: 1s, 2s, 4s
            if attempt < webhook.retry_count:
                time.sleep(2 ** (attempt - 1))

        # Log delivery
        self._log_delivery(webhook, event, payload, last_result)
        # Update webhook stats
        self._update_webhook_stats(webhook, last_result)
        return last_result

    def _deliver_once(self, webhook, event: str, body: str, attempt: int) -> Dict:
        """Single delivery attempt"""
        start = time.time()
        try:
            body_bytes = body.encode('utf-8')
            sig = ''
            if webhook.secret:
                sig = 'sha256=' + hmac.new(webhook.secret.encode(), body_bytes, hashlib.sha256).hexdigest()

            headers = {
                'Content-Type': 'application/json',
                'X-Localization-Event': event,
                'X-Localization-Signature': sig,
                'X-Delivery-Attempt': str(attempt),
                'User-Agent': 'World1Localization-Webhook/2.0',
                **(webhook.headers or {}),
            }
            req = urllib.request.Request(webhook.url, data=body_bytes, headers=headers, method='POST')

            with urllib.request.urlopen(req, timeout=webhook.timeout_secs) as resp:
                status_code = resp.getcode()
                response_body = resp.read().decode('utf-8', errors='ignore')[:500]
                elapsed = int((time.time() - start) * 1000)
                success = 200 <= status_code < 300
                return {
                    'webhook_id': webhook.pk, 'url': webhook.url,
                    'status': status_code, 'success': success,
                    'attempt': attempt, 'duration_ms': elapsed,
                    'response': response_body,
                }

        except urllib.error.HTTPError as e:
            elapsed = int((time.time() - start) * 1000)
            body_resp = e.read().decode('utf-8', errors='ignore')[:200]
            return {'webhook_id': webhook.pk, 'url': webhook.url, 'status': e.code,
                    'success': False, 'attempt': attempt, 'duration_ms': elapsed, 'error': body_resp}
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            return {'webhook_id': webhook.pk, 'url': webhook.url, 'status': 0,
                    'success': False, 'attempt': attempt, 'duration_ms': elapsed, 'error': str(e)}

    def _log_delivery(self, webhook, event: str, payload: Dict, result: Dict):
        """Delivery attempt DB-তে log করে"""
        try:
            from ..models.settings import WebhookDeliveryLog
            WebhookDeliveryLog.objects.create(
                webhook=webhook,
                event=event,
                payload=payload,
                response_status=result.get('status'),
                response_body=result.get('response', ''),
                attempt=result.get('attempt', 1),
                delivered=result.get('success', False),
                error=result.get('error', ''),
                duration_ms=result.get('duration_ms'),
            )
        except Exception as e:
            logger.error(f"Webhook log failed: {e}")

    def _update_webhook_stats(self, webhook, result: Dict):
        """Webhook stats update করে"""
        try:
            update_fields = ['total_calls', 'last_called', 'last_status']
            webhook.total_calls += 1
            webhook.last_called = timezone.now()
            webhook.last_status = result.get('status', 0)
            if not result.get('success'):
                webhook.failed_calls += 1
                update_fields.append('failed_calls')
            webhook.save(update_fields=update_fields)
        except Exception:
            pass

    # ── Convenience methods ──────────────────────────────────────

    def notify_translation_updated(self, key: str, language: str, new_value: str):
        self.deliver('translation.updated', {'key': key, 'language': language, 'value': new_value[:200]})

    def notify_pack_built(self, language: str, namespace: str, count: int, checksum: str):
        self.deliver('pack.built', {'language': language, 'namespace': namespace, 'count': count, 'checksum': checksum})

    def notify_coverage_changed(self, language: str, old_pct: float, new_pct: float):
        self.deliver('coverage.changed', {'language': language, 'old': old_pct, 'new': new_pct, 'change': round(new_pct - old_pct, 2)})

    def notify_key_created(self, key: str, category: str):
        self.deliver('key.created', {'key': key, 'category': category})

    def test_webhook(self, webhook_id: int) -> Dict:
        """Webhook test করে — ping event পাঠায়"""
        try:
            from ..models.settings import WebhookRegistration
            webhook = WebhookRegistration.objects.filter(pk=webhook_id).first()
            if not webhook:
                return {'success': False, 'error': 'Webhook not found'}
            body = json.dumps({'event': 'test.ping', 'timestamp': timezone.now().isoformat(), 'payload': {'test': True}})
            return self._deliver_once(webhook, 'test.ping', body, attempt=1)
        except Exception as e:
            return {'success': False, 'error': str(e)}
