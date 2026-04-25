# api/payment_gateways/services/SSLCommerzService.py

import requests
import hashlib
import uuid
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from .PaymentProcessor import PaymentProcessor
from ..models import GatewayTransaction as TxnModel, PayoutRequest


class SSLCommerzService(PaymentProcessor):
    """SSLCommerz Payment Service Implementation (Bangladesh)"""

    def __init__(self):
        super().__init__('sslcommerz')
        is_sandbox = getattr(settings, 'SSLCOMMERZ_SANDBOX', True)
        self.base_url = (
            "https://sandbox.sslcommerz.com"
            if is_sandbox
            else "https://securepay.sslcommerz.com"
        )
        self.config = self.load_config()

    def load_config(self):
        return {
            'store_id':     getattr(settings, 'SSLCOMMERZ_STORE_ID', ''),
            'store_passwd':  getattr(settings, 'SSLCOMMERZ_STORE_PASSWORD', ''),
            'success_url':  getattr(settings, 'SSLCOMMERZ_SUCCESS_URL', ''),
            'fail_url':     getattr(settings, 'SSLCOMMERZ_FAIL_URL', ''),
            'cancel_url':   getattr(settings, 'SSLCOMMERZ_CANCEL_URL', ''),
            'ipn_url':      getattr(settings, 'SSLCOMMERZ_IPN_URL', ''),
            'is_sandbox':   getattr(settings, 'SSLCOMMERZ_SANDBOX', True),
        }

    def process_deposit(self, user, amount, payment_method=None, **kwargs):
        """Initiate SSLCommerz payment session"""
        self.validate_amount(amount)

        txn = self.create_GatewayTransaction(
            user=user,
            transaction_type='deposit',
            amount=amount,
            payment_method=payment_method,
            metadata=kwargs.get('metadata', {}),
        )

        try:
            url = f"{self.base_url}/gwprocess/v4/api.php"

            payload = {
                'store_id':        self.config['store_id'],
                'store_passwd':    self.config['store_passwd'],
                'total_amount':    str(amount),
                'currency':        'BDT',
                'tran_id':         txn.reference_id,
                'success_url':     self.config['success_url'],
                'fail_url':        self.config['fail_url'],
                'cancel_url':      self.config['cancel_url'],
                'ipn_url':         self.config['ipn_url'],
                # Customer info
                'cus_name':        getattr(user, 'get_full_name', lambda: user.username)(),
                'cus_email':       user.email,
                'cus_phone':       getattr(user, 'phone', '01700000000'),
                'cus_add1':        'Dhaka',
                'cus_city':        'Dhaka',
                'cus_country':     'Bangladesh',
                # Product info
                'product_name':    'Deposit',
                'product_category': 'Online Payment',
                'product_profile': 'general',
                'shipping_method': 'NO',
                'num_of_item':     1,
                'product_amount':  str(amount),
                'vat':             '0',
                'discount_amount': '0',
                'convenience_fee': '0',
            }

            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'SUCCESS':
                txn.gateway_reference = data.get('sessionkey')
                txn.metadata['sslcommerz_data'] = data
                txn.save()

                return {
                    'transaction':   txn,
                    'payment_url':   data.get('GatewayPageURL'),
                    'session_key':   data.get('sessionkey'),
                }
            else:
                raise Exception(data.get('failedreason', 'SSLCommerz session init failed'))

        except Exception as e:
            txn.status = 'failed'
            txn.metadata['error'] = str(e)
            txn.save()
            raise Exception(f"SSLCommerz deposit failed: {str(e)}")

    def process_withdrawal(self, user, amount, payment_method, **kwargs):
        """SSLCommerz does not support direct withdrawal — creates manual payout request"""
        self.validate_amount(amount)

        payout = PayoutRequest.objects.create(
            user=user,
            amount=amount,
            fee=self.calculate_fee(amount),
            net_amount=amount - self.calculate_fee(amount),
            payout_method='sslcommerz',
            account_number=payment_method.account_number,
            account_name=payment_method.account_name,
            status='pending',
            reference_id=self.generate_reference_id(),
        )

        txn = self.create_GatewayTransaction(
            user=user,
            transaction_type='withdrawal',
            amount=amount,
            payment_method=payment_method,
            metadata={'payout_id': payout.id, **kwargs.get('metadata', {})},
        )

        return {
            'transaction': txn,
            'payout':      payout,
            'message':     'Withdrawal request submitted. Admin will process it shortly.',
        }

    def verify_payment(self, val_id, **kwargs):
        """Verify SSLCommerz payment by validation ID"""
        try:
            url = f"{self.base_url}/validator/api/validationserverAPI.php"
            params = {
                'val_id':      val_id,
                'store_id':    self.config['store_id'],
                'store_passwd': self.config['store_passwd'],
                'v':           1,
                'format':      'json',
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            tran_id = data.get('tran_id')
            try:
                txn = TxnModel.objects.get(reference_id=tran_id)
                if data.get('status') == 'VALID' or data.get('status') == 'VALIDATED':
                    txn.status = 'completed'
                    txn.metadata['validation_data'] = data
                    user = txn.user
                    if hasattr(user, 'balance'):
                        user.balance += txn.net_amount
                        user.save(update_fields=['balance'])
                else:
                    txn.status = 'failed'
                    txn.metadata['validation_data'] = data
                txn.save()
                return txn
            except TxnModel.DoesNotExist:
                return None

        except Exception as e:
            raise Exception(f"SSLCommerz verification failed: {str(e)}")

    def verify_ipn(self, ipn_data):
        """Verify IPN (Instant Payment Notification) from SSLCommerz"""
        verify_sign = ipn_data.get('verify_sign')
        verify_key = ipn_data.get('verify_key')

        if not verify_sign or not verify_key:
            return False

        # Build hash string from keys
        keys = verify_key.split(',')
        hash_string = self.config['store_passwd']
        for key in sorted(keys):
            hash_string += ipn_data.get(key, '')

        generated_hash = hashlib.md5(hash_string.encode()).hexdigest()
        return generated_hash == verify_sign

    def get_payment_url(self, txn, **kwargs):
        return txn.metadata.get('sslcommerz_data', {}).get('GatewayPageURL')
