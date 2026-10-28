# api/djoyalty/integrations/sslcommerz.py
"""
SSLCommerz Integration -- Bangladesh largest payment gateway।
Supports: bKash, Nagad, Rocket, VISA, MasterCard, Bank transfer।
13,600+ merchants, all-in-one solution।

docs: https://developer.sslcommerz.com/

Settings required:
    DJOYALTY_SSLCOMMERZ_STORE_ID
    DJOYALTY_SSLCOMMERZ_STORE_PASSWD
    DJOYALTY_SSLCOMMERZ_SANDBOX = True/False
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SSLCOMMERZ_SANDBOX_URL = 'https://sandbox.sslcommerz.com/gwprocess/v4/api.php'
SSLCOMMERZ_PROD_URL    = 'https://securepay.sslcommerz.com/gwprocess/v4/api.php'
SSLCOMMERZ_VALIDATE_SANDBOX = 'https://sandbox.sslcommerz.com/validator/api/validationserverAPI.php'
SSLCOMMERZ_VALIDATE_PROD    = 'https://securepay.sslcommerz.com/validator/api/validationserverAPI.php'


class SSLCommerzIntegration:
    """
    SSLCommerz payment gateway।
    Loyalty subscription payment + cashout এ ব্যবহার করুন।

    Usage:
        ssl = SSLCommerzIntegration()
        session = ssl.init_payment(
            order_id='ORD-001',
            amount=500,
            customer={'name': 'John', 'email': 'j@e.com', 'phone': '01700000000'},
            success_url='https://yoursite.com/payment/success',
            fail_url='https://yoursite.com/payment/fail',
        )
        # Redirect customer to session['GatewayPageURL']
    """

    def __init__(self):
        cfg = getattr(settings, 'DJOYALTY_SSLCOMMERZ', {})
        self.store_id    = cfg.get('STORE_ID', '')
        self.store_passwd = cfg.get('STORE_PASSWD', '')
        self.sandbox     = cfg.get('SANDBOX', True)
        self.api_url     = SSLCOMMERZ_SANDBOX_URL if self.sandbox else SSLCOMMERZ_PROD_URL
        self.validate_url = SSLCOMMERZ_VALIDATE_SANDBOX if self.sandbox else SSLCOMMERZ_VALIDATE_PROD

    def init_payment(self, order_id: str, amount: float,
                      customer: dict, success_url: str,
                      fail_url: str, cancel_url: str = '',
                      currency: str = 'BDT',
                      product_name: str = 'Loyalty Subscription',
                      product_category: str = 'loyalty') -> dict:
        """
        Initialize SSLCommerz payment session।
        Returns dict with GatewayPageURL to redirect customer।
        """
        payload = {
            'store_id': self.store_id,
            'store_passwd': self.store_passwd,
            'total_amount': str(amount),
            'currency': currency,
            'tran_id': order_id,
            'success_url': success_url,
            'fail_url': fail_url,
            'cancel_url': cancel_url or fail_url,
            'ipn_url': getattr(settings, 'SSLCOMMERZ_IPN_URL', success_url),
            'product_name': product_name,
            'product_category': product_category,
            'product_profile': 'general',
            'cus_name': customer.get('name', ''),
            'cus_email': customer.get('email', ''),
            'cus_add1': customer.get('address', 'Bangladesh'),
            'cus_city': customer.get('city', 'Dhaka'),
            'cus_country': customer.get('country', 'Bangladesh'),
            'cus_phone': customer.get('phone', ''),
            'shipping_method': 'NO',
            'num_of_item': 1,
            'ship_name': customer.get('name', ''),
            'ship_add1': 'Digital',
            'ship_city': 'Dhaka',
            'ship_country': 'Bangladesh',
        }

        resp = requests.post(self.api_url, data=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        if data.get('status') != 'SUCCESS':
            raise ValueError(f'SSLCommerz init failed: {data.get("failedreason")}')

        logger.info('SSLCommerzIntegration: session created -- %s (%s %s)', order_id, amount, currency)
        return data

    def validate_payment(self, val_id: str) -> dict:
        """Validate IPN / callback payment।"""
        resp = requests.get(
            self.validate_url,
            params={
                'val_id': val_id,
                'store_id': self.store_id,
                'store_passwd': self.store_passwd,
                'format': 'json',
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info('SSLCommerzIntegration: payment validated -- %s status=%s', val_id, data.get('status'))
        return data

    def refund(self, tran_id: str, refund_amount: float, reason: str = 'Loyalty Refund') -> dict:
        """Refund SSLCommerz transaction।"""
        refund_url = (
            'https://sandbox.sslcommerz.com/validator/api/merchantTransIDvalidationAPI.php'
            if self.sandbox else
            'https://securepay.sslcommerz.com/validator/api/merchantTransIDvalidationAPI.php'
        )
        resp = requests.get(refund_url, params={
            'tran_id': tran_id,
            'store_id': self.store_id,
            'store_passwd': self.store_passwd,
            'reftime': '',
            'amount': str(refund_amount),
            'bank_tran_id': '',
            'remark': reason,
            'format': 'json',
        }, timeout=10)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def is_configured() -> bool:
        cfg = getattr(settings, 'DJOYALTY_SSLCOMMERZ', {})
        return bool(cfg.get('STORE_ID') and cfg.get('STORE_PASSWD'))
