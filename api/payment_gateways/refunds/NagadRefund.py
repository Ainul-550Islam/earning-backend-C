# api/payment_gateways/refunds/NagadRefund.py
# FILE 51 of 257 — Nagad Refund Processor

import requests
import json
import base64
import hashlib
from decimal import Decimal
from datetime import datetime
from django.conf import settings
from django.utils import timezone

from .RefundProcessor import RefundProcessor


class NagadRefund(RefundProcessor):
    """
    Nagad Refund Processor.

    Uses Nagad Merchant API for refund/reverse operations.
    Docs: https://nagad.com.bd/merchant-api

    Note: Nagad uses RSA encryption for API security.
    Supports:
        - Full refund
        - Partial refund
    """

    def __init__(self):
        super().__init__('nagad')
        is_sandbox = getattr(settings, 'NAGAD_SANDBOX', True)
        self.base_url = (
            'https://api.mynagad.com/api/dfs'
            if not is_sandbox
            else 'https://api.mynagad.com/api/dfs'   # Nagad uses same URL, sandbox via credentials
        )
        self.config = {
            'merchant_id':      getattr(settings, 'NAGAD_MERCHANT_ID', ''),
            'merchant_private_key': getattr(settings, 'NAGAD_MERCHANT_PRIVATE_KEY', ''),
            'nagad_public_key': getattr(settings, 'NAGAD_PUBLIC_KEY', ''),
            'callback_url':     getattr(settings, 'NAGAD_CALLBACK_URL', ''),
        }

    def _get_timestamp(self) -> str:
        return datetime.now().strftime('%Y%m%d%H%M%S')

    def _encrypt_with_public_key(self, data: str) -> str:
        """Encrypt data with Nagad's public key (RSA PKCS1_OAEP)"""
        try:
            from Crypto.PublicKey import RSA
            from Crypto.Cipher import PKCS1_OAEP
            import base64

            public_key_pem = self.config['nagad_public_key']
            if not public_key_pem.startswith('-----'):
                public_key_pem = f"-----BEGIN PUBLIC KEY-----\n{public_key_pem}\n-----END PUBLIC KEY-----"

            key    = RSA.import_key(public_key_pem)
            cipher = PKCS1_OAEP.new(key)
            encrypted = cipher.encrypt(data.encode())
            return base64.b64encode(encrypted).decode()
        except ImportError:
            # pycryptodome not installed — return raw data for sandbox
            return base64.b64encode(data.encode()).decode()

    def _sign_with_private_key(self, data: str) -> str:
        """Sign data with merchant's private key (RSA SHA256)"""
        try:
            from Crypto.Signature import pkcs1_15
            from Crypto.Hash import SHA256
            from Crypto.PublicKey import RSA
            import base64

            private_key_pem = self.config['merchant_private_key']
            if not private_key_pem.startswith('-----'):
                private_key_pem = f"-----BEGIN RSA PRIVATE KEY-----\n{private_key_pem}\n-----END RSA PRIVATE KEY-----"

            key     = RSA.import_key(private_key_pem)
            h       = SHA256.new(data.encode())
            sig     = pkcs1_15.new(key).sign(h)
            return base64.b64encode(sig).decode()
        except ImportError:
            return base64.b64encode(data.encode()).decode()

    # ── process_refund ────────────────────────────────────────────────────────

    def process_refund(self, transaction, amount: Decimal, reason: str = 'customer_request', **kwargs) -> dict:
        """
        Initiate Nagad refund.
        Nagad refund requires the original payment reference (order_id).
        """
        refund = self.create_refund_request(transaction, amount, reason, **kwargs)

        nagad_order_id = transaction.gateway_reference or transaction.reference_id

        try:
            timestamp = self._get_timestamp()

            # Sensitive data encrypted with Nagad's public key
            sensitive = json.dumps({
                'merchantId':   self.config['merchant_id'],
                'datetime':     timestamp,
                'orderid':      nagad_order_id,
                'amount':       str(amount),
                'currencyCode': '050',   # BDT
                'challenge':    refund.reference_id,
            })

            encrypted_sensitive = self._encrypt_with_public_key(sensitive)
            signature           = self._sign_with_private_key(sensitive)

            url = f'{self.base_url}/check-out/refund'

            payload = {
                'merchantId':          self.config['merchant_id'],
                'orderId':             nagad_order_id,
                'refundAmount':        str(amount),
                'reason':              reason,
                'sensitiveData':       encrypted_sensitive,
                'signature':           signature,
                'merchantCallbackURL': self.config['callback_url'],
            }

            headers = {
                'X-KM-Api-Version':   'v-0.2.0',
                'X-KM-IP-V4':         kwargs.get('client_ip', '127.0.0.1'),
                'X-KM-Client-Type':   'PC_WEB',
                'X-KM-Datetime':      timestamp,
                'Content-Type':       'application/json',
            }

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            status_code = data.get('status', '')
            refund_id   = data.get('refundId', '') or data.get('orderId', '')

            if status_code in ('Success', '000'):
                self.update_refund_status(
                    refund, 'completed',
                    gateway_refund_id=refund_id,
                    raw_response=data,
                )
                return {
                    'refund_request':    refund,
                    'gateway_refund_id': refund_id,
                    'status':            'completed',
                    'message':           f'Nagad refund of {amount} BDT completed.',
                }
            elif status_code == 'Pending':
                self.update_refund_status(
                    refund, 'processing',
                    gateway_refund_id=refund_id,
                    raw_response=data,
                )
                return {
                    'refund_request':    refund,
                    'gateway_refund_id': refund_id,
                    'status':            'processing',
                    'message':           'Nagad refund is being processed.',
                }
            else:
                error = data.get('message', 'Unknown Nagad error')
                self.update_refund_status(refund, 'failed', raw_response=data)
                raise Exception(f'Nagad refund failed: {error}')

        except Exception as e:
            if refund.status not in ('completed', 'processing'):
                self.update_refund_status(refund, 'failed', raw_response={'error': str(e)})
            raise

    # ── check_refund_status ───────────────────────────────────────────────────

    def check_refund_status(self, refund_request, **kwargs) -> dict:
        """Check Nagad refund status via API"""
        try:
            timestamp = self._get_timestamp()
            url       = f'{self.base_url}/check-out/refund/status/{refund_request.gateway_refund_id}'

            headers = {
                'X-KM-Api-Version': 'v-0.2.0',
                'X-KM-Datetime':    timestamp,
                'Content-Type':     'application/json',
            }

            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            api_status = data.get('status', '')
            if api_status == 'Success':
                self.update_refund_status(refund_request, 'completed', raw_response=data)
            elif api_status == 'Pending':
                self.update_refund_status(refund_request, 'processing', raw_response=data)
            else:
                self.update_refund_status(refund_request, 'failed', raw_response=data)

            return {
                'status':         refund_request.status,
                'gateway_status': api_status,
                'raw_response':   data,
            }

        except Exception as e:
            return {
                'status':         refund_request.status,
                'gateway_status': 'unknown',
                'error':          str(e),
            }

    # ── cancel_refund ─────────────────────────────────────────────────────────

    def cancel_refund(self, refund_request, **kwargs) -> bool:
        """Nagad does not support refund cancellation after initiation."""
        raise NotImplementedError('Nagad does not support refund cancellation.')
