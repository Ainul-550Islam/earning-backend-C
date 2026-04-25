# api/payment_gateways/services/AmarPayService.py

import requests
import hashlib
import hmac
import json
import uuid
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from .PaymentProcessor import PaymentProcessor
from ..models import GatewayTransaction as TxnModel, PayoutRequest


class AmarPayService(PaymentProcessor):
    """AmarPay Payment Service Implementation (Bangladesh)"""

    def __init__(self):
        super().__init__('amarpay')
        is_sandbox = getattr(settings, 'AMARPAY_SANDBOX', True)
        self.base_url = (
            "https://sandbox.aamarpay.com"
            if is_sandbox
            else "https://secure.aamarpay.com"
        )
        self.config = self.load_config()

    def load_config(self):
        return {
            'store_id':    getattr(settings, 'AMARPAY_STORE_ID', 'aamarpay'),
            'signature_key': getattr(settings, 'AMARPAY_SIGNATURE_KEY', ''),
            'success_url': getattr(settings, 'AMARPAY_SUCCESS_URL', ''),
            'fail_url':    getattr(settings, 'AMARPAY_FAIL_URL', ''),
            'cancel_url':  getattr(settings, 'AMARPAY_CANCEL_URL', ''),
            'is_sandbox':  getattr(settings, 'AMARPAY_SANDBOX', True),
        }

    def process_deposit(self, user, amount, payment_method=None, **kwargs):
        """Initiate AmarPay payment"""
        self.validate_amount(amount)

        txn = self.create_GatewayTransaction(
            user=user,
            transaction_type='deposit',
            amount=amount,
            payment_method=payment_method,
            metadata=kwargs.get('metadata', {}),
        )

        try:
            url = f"{self.base_url}/index.php"

            payload = {
                'store_id':      self.config['store_id'],
                'tran_id':       txn.reference_id,
                'success_url':   self.config['success_url'],
                'fail_url':      self.config['fail_url'],
                'cancel_url':    self.config['cancel_url'],
                'amount':        str(amount),
                'payment_type':  'VISA',
                'currency':      'BDT',
                'desc':          'Deposit',
                'cus_name':      getattr(user, 'get_full_name', lambda: user.username)(),
                'cus_email':     user.email,
                'cus_phone':     getattr(user, 'phone', '01700000000'),
                'cus_add1':      'Dhaka',
                'cus_city':      'Dhaka',
                'cus_country':   'Bangladesh',
                'signature_key': self.config['signature_key'],
                'type':          'json',
            }

            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            payment_url = data.get('payment_url')
            if not payment_url:
                raise Exception(data.get('error', 'AmarPay payment initiation failed'))

            txn.metadata['amarpay_data'] = data
            txn.save()

            return {
                'transaction': txn,
                'payment_url': payment_url,
            }

        except Exception as e:
            txn.status = 'failed'
            txn.metadata['error'] = str(e)
            txn.save()
            raise Exception(f"AmarPay deposit failed: {str(e)}")

    def process_withdrawal(self, user, amount, payment_method, **kwargs):
        """AmarPay withdrawal — manual payout request"""
        self.validate_amount(amount)

        payout = PayoutRequest.objects.create(
            user=user,
            amount=amount,
            fee=self.calculate_fee(amount),
            net_amount=amount - self.calculate_fee(amount),
            payout_method='amarpay',
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

    def verify_payment(self, mer_txnid, **kwargs):
        """Verify AmarPay transaction by merchant transaction ID"""
        try:
            url = f"{self.base_url}/api/v1/trxcheck/request.php"
            params = {
                'request_id':    mer_txnid,
                'store_id':      self.config['store_id'],
                'signature_key': self.config['signature_key'],
                'type':          'json',
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            try:
                txn = TxnModel.objects.get(reference_id=mer_txnid)
                pay_status = data.get('pay_status', '')
                if pay_status == 'Successful':
                    txn.status = 'completed'
                    txn.metadata['verification_data'] = data
                    user = txn.user
                    if hasattr(user, 'balance'):
                        user.balance += txn.net_amount
                        user.save(update_fields=['balance'])
                else:
                    txn.status = 'failed'
                    txn.metadata['verification_data'] = data
                txn.save()
                return txn
            except TxnModel.DoesNotExist:
                return None

        except Exception as e:
            raise Exception(f"AmarPay verification failed: {str(e)}")

    def get_payment_url(self, txn, **kwargs):
        return txn.metadata.get('amarpay_data', {}).get('payment_url')
