# api/djoyalty/integrations/nagad.py
"""
Nagad Integration -- Points cashout + payment।
Nagad Merchant API।
docs: https://nagad.com.bd/merchant

Settings required:
    DJOYALTY_NAGAD_MERCHANT_ID
    DJOYALTY_NAGAD_MERCHANT_NUMBER
    DJOYALTY_NAGAD_PUBLIC_KEY
    DJOYALTY_NAGAD_PRIVATE_KEY
    DJOYALTY_NAGAD_SANDBOX = True/False
"""
import base64
import json
import logging
import uuid
from datetime import datetime

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

NAGAD_SANDBOX_BASE = 'http://sandbox.mynagad.com:10080/remote-payment-gateway-1.0/api'
NAGAD_PROD_BASE    = 'https://api.mynagad.com/api'


class NagadIntegration:
    """
    Nagad Payment Gateway integration।

    Usage:
        nagad = NagadIntegration()
        init = nagad.init_payment(order_id='ORD-123', amount='500')
        confirm = nagad.confirm_payment(payment_ref_id=init['paymentRefId'])
    """

    def __init__(self):
        cfg = getattr(settings, 'DJOYALTY_NAGAD', {})
        self.merchant_id     = cfg.get('MERCHANT_ID', '')
        self.merchant_number = cfg.get('MERCHANT_NUMBER', '')
        self.pub_key         = cfg.get('PUBLIC_KEY', '')
        self.priv_key        = cfg.get('PRIVATE_KEY', '')
        self.sandbox         = cfg.get('SANDBOX', True)
        self.base_url        = NAGAD_SANDBOX_BASE if self.sandbox else NAGAD_PROD_BASE

    def _headers(self) -> dict:
        return {
            'Content-Type': 'application/json',
            'X-KM-Api-Version': 'v-0.2.0',
            'X-KM-IP-V4': '127.0.0.1',
            'X-KM-Client-Type': 'PC_WEB',
        }

    def _encrypt_with_public_key(self, data: str) -> str:
        """Encrypt data with Nagad public key।"""
        try:
            from cryptography.hazmat.primitives import serialization, hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            pub_key_bytes = base64.b64decode(self.pub_key)
            public_key = serialization.load_der_public_key(pub_key_bytes)
            encrypted = public_key.encrypt(
                data.encode(),
                padding.PKCS1v15(),
            )
            return base64.b64encode(encrypted).decode()
        except ImportError:
            logger.warning('NagadIntegration: cryptography package not installed. pip install cryptography')
            return base64.b64encode(data.encode()).decode()

    def _sign_with_private_key(self, data: str) -> str:
        """Sign data with merchant private key।"""
        try:
            from cryptography.hazmat.primitives import serialization, hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            priv_key_bytes = base64.b64decode(self.priv_key)
            private_key = serialization.load_der_private_key(priv_key_bytes, password=None)
            signature = private_key.sign(data.encode(), padding.PKCS1v15(), hashes.SHA256())
            return base64.b64encode(signature).decode()
        except ImportError:
            return base64.b64encode(data.encode()).decode()

    def init_payment(self, order_id: str, amount: str, callback_url: str = '') -> dict:
        """Initialize Nagad payment।"""
        datetime_str = datetime.now().strftime('%Y%m%d%H%M%S')
        sensitive = json.dumps({
            'merchantId': self.merchant_id,
            'datetime': datetime_str,
            'orderId': order_id,
            'challenge': str(uuid.uuid4()),
        })
        payload = {
            'dateTime': datetime_str,
            'sensitiveData': self._encrypt_with_public_key(sensitive),
            'signature': self._sign_with_private_key(sensitive),
        }
        resp = requests.post(
            f'{self.base_url}/dfs/check-out/initialize/{self.merchant_id}/{order_id}',
            json=payload,
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info('NagadIntegration: payment initialized -- %s', order_id)
        return data

    def confirm_payment(self, payment_ref_id: str, order_id: str,
                         amount: str, callback_url: str = '') -> dict:
        """Confirm Nagad payment।"""
        datetime_str = datetime.now().strftime('%Y%m%d%H%M%S')
        sensitive = json.dumps({
            'merchantId': self.merchant_id,
            'orderId': order_id,
            'amount': str(amount),
            'currencyCode': '050',
            'challenge': payment_ref_id,
        })
        payload = {
            'sensitiveData': self._encrypt_with_public_key(sensitive),
            'signature': self._sign_with_private_key(sensitive),
            'merchantCallbackURL': callback_url or getattr(settings, 'NAGAD_CALLBACK_URL', ''),
        }
        resp = requests.post(
            f'{self.base_url}/dfs/check-out/complete/{payment_ref_id}',
            json=payload,
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info('NagadIntegration: payment confirmed -- %s', payment_ref_id)
        return data

    def verify_payment(self, payment_ref_id: str) -> dict:
        """Verify Nagad payment status।"""
        resp = requests.get(
            f'{self.base_url}/dfs/verify/payment/{payment_ref_id}',
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def is_configured() -> bool:
        cfg = getattr(settings, 'DJOYALTY_NAGAD', {})
        return bool(cfg.get('MERCHANT_ID') and cfg.get('PUBLIC_KEY'))
