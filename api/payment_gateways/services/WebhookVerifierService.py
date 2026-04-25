# api/payment_gateways/services/WebhookVerifierService.py
# HMAC signature verification for all gateway webhooks

import hmac
import hashlib
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class WebhookVerifierService:
    """
    Verifies webhook authenticity per gateway using HMAC signatures.
    Each gateway has a different header and algorithm.
    """

    SIGNATURE_CONFIGS = {
        'bkash': {
            'header':    'X-bKash-Signature',
            'algo':      'sha256',
            'prefix':    '',
        },
        'nagad': {
            'header':    'X-Nagad-Signature',
            'algo':      'sha256',
            'prefix':    '',
        },
        'sslcommerz': {
            'header':    'X-Verify-Sign',
            'algo':      'md5',
            'use_store_password': True,
        },
        'amarpay': {
            'header':    'X-AmarPay-Signature',
            'algo':      'sha256',
        },
        'upay': {
            'header':    'X-Upay-Signature',
            'algo':      'sha256',
        },
        'shurjopay': {
            'header':    'X-ShurjoPay-Signature',
            'algo':      'sha256',
        },
        'stripe': {
            'header':    'Stripe-Signature',
            'algo':      'sha256',
            'prefix':    'v1=',
            'timestamp_field': 't',
        },
        'paypal': {
            'header':    'Paypal-Transmission-Sig',
            'algo':      'sha256',
        },
    }

    def verify(self, gateway: str, request_body: bytes, headers: dict) -> bool:
        """
        Verify webhook signature for a given gateway.

        Args:
            gateway:      Gateway name
            request_body: Raw request body bytes
            headers:      Request headers dict

        Returns:
            bool: True if signature is valid
        """
        config = self.SIGNATURE_CONFIGS.get(gateway)
        if not config:
            logger.warning(f'No webhook config for gateway: {gateway}')
            return True  # Allow unknown gateways (no config = no verification)

        secret = self._get_secret(gateway)
        if not secret:
            logger.warning(f'No webhook secret configured for {gateway}')
            return True  # Allow if no secret configured

        try:
            sig_header = config.get('header', '')
            received   = headers.get(sig_header, '') or headers.get(sig_header.lower(), '')

            if not received:
                logger.warning(f'{gateway}: Missing signature header {sig_header}')
                return False

            if gateway == 'stripe':
                return self._verify_stripe(request_body, received, secret)
            elif gateway == 'sslcommerz':
                return self._verify_sslcommerz(request_body, received, secret)
            else:
                return self._verify_hmac(request_body, received, secret, config.get('algo', 'sha256'))

        except Exception as e:
            logger.error(f'Webhook verification error for {gateway}: {e}')
            return False

    def _verify_hmac(self, body: bytes, received: str, secret: str, algo: str) -> bool:
        if algo == 'sha256':
            expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        elif algo == 'sha512':
            expected = hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()
        else:
            expected = hmac.new(secret.encode(), body, hashlib.md5).hexdigest()
        return hmac.compare_digest(expected, received.lower())

    def _verify_stripe(self, body: bytes, sig_header: str, secret: str) -> bool:
        """Stripe uses timestamp + payload concatenation."""
        try:
            parts     = {k: v for k, v in (p.split('=', 1) for p in sig_header.split(','))}
            timestamp = parts.get('t', '')
            v1_sig    = parts.get('v1', '')
            payload   = f'{timestamp}.'.encode() + body
            expected  = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, v1_sig)
        except Exception as e:
            logger.error(f'Stripe signature error: {e}')
            return False

    def _verify_sslcommerz(self, body: bytes, received: str, secret: str) -> bool:
        """SSLCommerz uses store_password MD5."""
        import hashlib as hl
        try:
            data = json.loads(body)
            data['store_passwd'] = secret
            sorted_data = {k: v for k, v in sorted(data.items())}
            hash_str = ''.join(str(v) for v in sorted_data.values())
            expected = hl.md5(hash_str.encode()).hexdigest()
            return received == expected
        except Exception:
            return False

    def _get_secret(self, gateway: str) -> str:
        setting_map = {
            'bkash':      'BKASH_WEBHOOK_SECRET',
            'nagad':      'NAGAD_WEBHOOK_SECRET',
            'sslcommerz': 'SSLCOMMERZ_STORE_PASSWORD',
            'amarpay':    'AMARPAY_SIGNATURE_KEY',
            'upay':       'UPAY_MERCHANT_KEY',
            'shurjopay':  'SHURJOPAY_PASSWORD',
            'stripe':     'STRIPE_WEBHOOK_SECRET',
            'paypal':     'PAYPAL_WEBHOOK_ID',
        }
        return getattr(settings, setting_map.get(gateway, ''), '')
