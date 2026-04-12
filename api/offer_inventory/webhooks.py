# api/offer_inventory/webhooks.py
"""
Central Webhook Dispatcher.
Routes incoming webhooks to appropriate handlers.
Manages outbound webhook delivery to configured endpoints.
"""
import hmac
import hashlib
import json
import logging
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class WebhookDispatcher:
    """
    Dispatch incoming webhooks from external sources
    and send outbound webhooks to configured endpoints.
    """

    # ── Inbound routing ───────────────────────────────────────────

    @staticmethod
    def dispatch_postback(network_slug: str, raw_params: dict,
                           source_ip: str, raw_body: str = '',
                           source_id=None) -> dict:
        """Route a postback to the S2S handler."""
        from api.offer_inventory.webhooks.s2s_postback import S2SPostbackHandler
        handler = S2SPostbackHandler(network_slug)
        return handler.handle(raw_params, source_ip, raw_body, source_id)

    @staticmethod
    def dispatch_cpa_webhook(network_name: str, params: dict) -> dict:
        """Route to CPA network handler."""
        from api.offer_inventory.webhooks.cpa_network import CPANetworkWebhook
        handler = CPANetworkWebhook(network_name)
        parsed  = handler.receive_conversion(params)
        if not parsed:
            return {'status': 'error', 'message': 'Failed to parse webhook'}
        return {'status': 'ok', 'parsed': parsed}

    @staticmethod
    def handle_pixel_request(offer_id: str, token: str = '') -> object:
        """Route pixel request to pixel tracker."""
        from api.offer_inventory.webhooks.pixel_tracking import PixelTracker
        return PixelTracker.gif_response()

    # ── Outbound delivery ─────────────────────────────────────────

    @classmethod
    def deliver_to_all_configs(cls, event: str, payload: dict,
                                tenant=None) -> dict:
        """
        Deliver an event to all matching WebhookConfig records.
        """
        from api.offer_inventory.models import WebhookConfig

        configs = WebhookConfig.objects.filter(is_active=True)
        if tenant:
            configs = configs.filter(tenant=tenant)

        results = {'delivered': 0, 'failed': 0}

        for config in configs:
            events = config.events or []
            if event not in events and '*' not in events:
                continue

            success = cls._deliver_single(
                url     =config.url,
                event   =event,
                payload =payload,
                secret  =config.secret_key,
            )

            from django.db.models import F
            if success:
                results['delivered'] += 1
                WebhookConfig.objects.filter(id=config.id).update(
                    last_fired  =timezone.now(),
                    last_status =200,
                )
            else:
                results['failed'] += 1
                WebhookConfig.objects.filter(id=config.id).update(
                    last_status=0,
                )

        return results

    @staticmethod
    def _deliver_single(url: str, event: str, payload: dict,
                         secret: str = '', timeout: int = 10) -> bool:
        """Deliver a single webhook with HMAC signature."""
        import requests as _req

        body    = json.dumps({
            'event'    : event,
            'data'     : payload,
            'timestamp': timezone.now().isoformat(),
        }, default=str)

        headers = {
            'Content-Type': 'application/json',
            'X-Event-Type': event,
        }
        if secret:
            sig = hmac.new(
                secret.encode(), body.encode(), hashlib.sha256
            ).hexdigest()
            headers['X-Signature'] = f'sha256={sig}'

        try:
            resp = _req.post(url, data=body, headers=headers, timeout=timeout)
            return resp.status_code in (200, 201, 204)
        except Exception as e:
            logger.warning(f'Webhook delivery failed: {url} → {e}')
            return False

    # ── Event firing helpers ──────────────────────────────────────

    @classmethod
    def fire_conversion_approved(cls, conversion, tenant=None):
        cls.deliver_to_all_configs('conversion.approved', {
            'conversion_id': str(conversion.id),
            'offer_id'     : str(conversion.offer_id),
            'user_id'      : str(conversion.user_id),
            'payout'       : str(conversion.payout_amount),
            'reward'       : str(conversion.reward_amount),
        }, tenant=tenant)

    @classmethod
    def fire_withdrawal_completed(cls, withdrawal, tenant=None):
        cls.deliver_to_all_configs('withdrawal.completed', {
            'withdrawal_id': str(withdrawal.id),
            'reference_no' : withdrawal.reference_no,
            'amount'       : str(withdrawal.net_amount),
            'user_id'      : str(withdrawal.user_id),
        }, tenant=tenant)

    @classmethod
    def fire_fraud_detected(cls, user_id, fraud_type: str, tenant=None):
        cls.deliver_to_all_configs('fraud.detected', {
            'user_id'   : str(user_id),
            'fraud_type': fraud_type,
            'detected_at': timezone.now().isoformat(),
        }, tenant=tenant)

    @classmethod
    def fire_offer_expired(cls, offer, tenant=None):
        cls.deliver_to_all_configs('offer.expired', {
            'offer_id': str(offer.id),
            'title'   : offer.title,
        }, tenant=tenant)


class WebhookVerifier:
    """Verify incoming webhook signatures."""

    @staticmethod
    def verify_hmac(payload: bytes, signature: str, secret: str) -> bool:
        """Verify HMAC-SHA256 signature (timing-safe)."""
        if not all([payload, signature, secret]):
            return False
        expected = 'sha256=' + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature.strip())

    @staticmethod
    def verify_tapjoy(params: dict, secret: str) -> bool:
        """Verify Tapjoy postback signature."""
        verifier = params.get('verifier', '')
        if not verifier or not secret:
            return True
        payload = (
            str(params.get('snuid', '')) +
            str(params.get('currency', '')) +
            secret
        )
        expected = hashlib.md5(payload.encode()).hexdigest()
        return hmac.compare_digest(expected, verifier)

    @staticmethod
    def verify_fyber(params: dict, secret: str) -> bool:
        """Verify Fyber postback signature."""
        sig = params.get('signature', '')
        if not sig or not secret:
            return True
        # Fyber uses specific param ordering
        fields = ['uid', 'oid', 'sid', 'amount', 'pub0', 'pub1', 'pub2', 'pub3', 'pub4', 'pub5']
        payload = '&'.join(f'{k}={params.get(k, "")}' for k in fields if k in params)
        payload += secret
        expected = hashlib.sha1(payload.encode()).hexdigest()
        return hmac.compare_digest(expected, sig)


class WebhookRetryQueue:
    """
    Retry queue for failed webhook deliveries.
    Uses Redis to track pending retries.
    """

    MAX_RETRIES = 5
    RETRY_DELAYS = [60, 300, 900, 3600, 86400]  # 1min, 5min, 15min, 1h, 24h

    @classmethod
    def enqueue_retry(cls, url: str, event: str, payload: dict,
                       secret: str = '', attempt: int = 1):
        """Add a failed webhook to the retry queue."""
        if attempt > cls.MAX_RETRIES:
            logger.error(f'Webhook max retries exceeded: {url} event={event}')
            return

        delay = cls.RETRY_DELAYS[min(attempt - 1, len(cls.RETRY_DELAYS) - 1)]

        from api.offer_inventory.tasks import retry_webhook_delivery
        retry_webhook_delivery.apply_async(
            args=[url, event, payload, secret, attempt + 1],
            countdown=delay,
        )

    @classmethod
    def get_pending_count(cls) -> int:
        """Get count of webhooks pending retry."""
        from api.offer_inventory.models import WebhookConfig
        return WebhookConfig.objects.filter(
            is_active=True, last_status=0
        ).count()
