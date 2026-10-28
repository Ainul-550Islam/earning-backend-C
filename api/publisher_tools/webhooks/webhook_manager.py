# api/publisher_tools/webhooks/webhook_manager.py
"""
Webhook Manager — Publisher event webhooks.
Real-time event notifications to publisher endpoints.
"""
import hashlib
import hmac
import json
import time
import uuid
from typing import Dict, List

import requests as http_requests
from django.utils import timezone

from api.publisher_tools.models import PublisherWebhook, WebhookDeliveryLog


def _is_subscribed_to(webhook: PublisherWebhook, event_type: str) -> bool:
    if webhook.subscribe_all:
        return True
    return event_type in (webhook.subscribed_events or [])


def _generate_signature(webhook: PublisherWebhook, payload: str) -> str:
    secret = webhook.secret_key or ''
    return hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def _build_request_headers(webhook: PublisherWebhook, payload: str, event_type: str) -> Dict:
    headers = {
        'Content-Type': 'application/json',
        'X-Publisher-Tools-Event': event_type,
        'X-Publisher-Tools-Signature': f'sha256={_generate_signature(webhook, payload)}',
        'X-Publisher-Tools-Delivery': uuid.uuid4().hex,
        'X-Publisher-Tools-Timestamp': str(int(timezone.now().timestamp())),
        'User-Agent': 'PublisherTools-Webhooks/1.0',
    }
    headers.update(webhook.custom_headers or {})
    return headers


def send_webhook_event(publisher, event_type: str, event_data: Dict) -> List[WebhookDeliveryLog]:
    """Send an event to all active publisher webhooks."""
    webhooks = PublisherWebhook.objects.filter(
        publisher=publisher,
        is_active=True,
        status='active',
    )

    delivery_logs = []
    for webhook in webhooks:
        if not _is_subscribed_to(webhook, event_type):
            continue

        payload = {
            'event': event_type,
            'timestamp': timezone.now().isoformat(),
            'publisher_id': publisher.publisher_id,
            'data': event_data,
        }
        payload_str = json.dumps(payload, default=str)
        headers = _build_request_headers(webhook, payload_str, event_type)

        log = WebhookDeliveryLog.objects.create(
            webhook=webhook,
            event_type=event_type,
            payload=payload,
            status='pending',
        )

        try:
            start_time = time.time()
            response = http_requests.post(
                webhook.endpoint_url,
                data=payload_str,
                headers=headers,
                timeout=webhook.timeout_seconds,
            )
            elapsed_ms = int((time.time() - start_time) * 1000)
            success = 200 <= response.status_code < 300

            log.response_code = response.status_code
            log.response_body = response.text[:2000]
            log.delivery_time_ms = elapsed_ms
            log.status = 'success' if success else 'failed'
            log.delivered_at = timezone.now()
            if not success:
                log.error_message = f'HTTP {response.status_code}: {response.text[:500]}'
            log.save()

            if success:
                webhook.mark_success()
            else:
                webhook.mark_failed(reason=log.error_message)

        except Exception as exc:
            log.status = 'failed'
            log.error_message = str(exc)
            log.save()
            webhook.mark_failed(reason=str(exc))

        delivery_logs.append(log)

    return delivery_logs


def build_earning_event_payload(earning) -> Dict:
    """Build earning event payload."""
    return {
        'earning_id': str(earning.id),
        'date': str(earning.date),
        'earning_type': earning.earning_type,
        'publisher_id': earning.publisher.publisher_id,
        'ad_unit_id': earning.ad_unit.unit_id if earning.ad_unit else None,
        'site_id': earning.site.site_id if earning.site else None,
        'country': earning.country,
        'impressions': earning.impressions,
        'clicks': earning.clicks,
        'publisher_revenue': float(earning.publisher_revenue),
        'ecpm': float(earning.ecpm),
        'status': earning.status,
    }


def build_invoice_event_payload(invoice) -> Dict:
    """Build invoice event payload."""
    return {
        'invoice_number': invoice.invoice_number,
        'publisher_id': invoice.publisher.publisher_id,
        'period_start': str(invoice.period_start),
        'period_end': str(invoice.period_end),
        'gross_revenue': float(invoice.gross_revenue),
        'net_payable': float(invoice.net_payable),
        'currency': invoice.currency,
        'status': invoice.status,
        'paid_at': invoice.paid_at.isoformat() if invoice.paid_at else None,
        'payment_reference': invoice.payment_reference,
    }
