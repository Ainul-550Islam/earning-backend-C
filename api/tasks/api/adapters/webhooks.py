"""
api/adapters/webhooks.py
Outbound webhook dispatcher.
When key events occur (task completed, payout sent, dispute opened),
POST a signed JSON payload to registered publisher webhook URLs.
"""
import logging, hashlib, hmac, json
import requests
from django.conf import settings
logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = 5
WEBHOOK_SECRET  = getattr(settings, 'WEBHOOK_SIGNING_SECRET', 'changeme')

SUPPORTED_EVENTS = {
    'task.completed', 'task.failed', 'payout.sent',
    'dispute.opened', 'dispute.resolved', 'fraud.flagged',
}

def dispatch(event: str, payload: dict, webhook_url: str) -> bool:
    if event not in SUPPORTED_EVENTS:
        logger.warning('[Webhook] Unknown event: %s', event)
        return False
    body = json.dumps({'event': event, 'data': payload}, default=str)
    sig  = _sign(body)
    try:
        r = requests.post(
            webhook_url, data=body,
            headers={'Content-Type': 'application/json',
                     'X-Webhook-Signature': sig,
                     'X-Webhook-Event': event},
            timeout=WEBHOOK_TIMEOUT,
        )
        r.raise_for_status()
        logger.info('[Webhook] %s → %s status=%s', event, webhook_url, r.status_code)
        return True
    except Exception as e:
        logger.error('[Webhook] dispatch failed: %s', e)
        return False

def _sign(body: str) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()

def verify_signature(body: str, signature: str) -> bool:
    expected = _sign(body)
    return hmac.compare_digest(expected, signature)
