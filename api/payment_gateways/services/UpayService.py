# api/payment_gateways/services/UpayService.py

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


class UpayService(PaymentProcessor):
    """Upay Payment Service Implementation (Bangladesh — United Commercial Bank)"""

    SANDBOX_URL = "https://uat.upay.com.bd/api/v1"
    LIVE_URL    = "https://upay.com.bd/api/v1"

    def __init__(self):
        super().__init__('upay')
        is_sandbox = getattr(settings, 'UPAY_SANDBOX', True)
        self.base_url = self.SANDBOX_URL if is_sandbox else self.LIVE_URL
        self.config = self.load_config()

    def load_config(self):
        return {
            'merchant_id':      getattr(settings, 'UPAY_MERCHANT_ID', ''),
            'merchant_key':     getattr(settings, 'UPAY_MERCHANT_KEY', ''),
            'merchant_code':    getattr(settings, 'UPAY_MERCHANT_CODE', ''),
            'merchant_name':    getattr(settings, 'UPAY_MERCHANT_NAME', ''),
            'success_redirect': getattr(settings, 'UPAY_SUCCESS_URL', ''),
            'error_redirect':   getattr(settings, 'UPAY_FAIL_URL', ''),
            'is_sandbox':       getattr(settings, 'UPAY_SANDBOX', True),
        }

    def _get_auth_token(self):
        """Get Upay auth token"""
        url = f"{self.base_url}/rgw/token/generate"
        payload = {
            'merchant_id':   self.config['merchant_id'],
            'merchant_key':  self.config['merchant_key'],
        }
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        token = data.get('merchant_token')
        if not token:
            raise Exception("Upay: Failed to get auth token")
        return token

    def process_deposit(self, user, amount, payment_method=None, **kwargs):
        """Initiate Upay payment"""
        self.validate_amount(amount)

        txn = self.create_GatewayTransaction(
            user=user,
            transaction_type='deposit',
            amount=amount,
            payment_method=payment_method,
            metadata=kwargs.get('metadata', {}),
        )

        try:
            token = self._get_auth_token()
            url   = f"{self.base_url}/rgw/payment/init"

            payload = {
                'merchant_id':      self.config['merchant_id'],
                'merchant_name':    self.config['merchant_name'],
                'merchant_code':    self.config['merchant_code'],
                'merchant_country_code': 'BD',
                'merchant_currency': 'BDT',
                'merchant_order_id': txn.reference_id,
                'transaction_amount': str(amount),
                'success_redirect_url': self.config['success_redirect'],
                'error_redirect_url':   self.config['error_redirect'],
                'customer_mobile_no':   getattr(user, 'phone', '01700000000'),
            }

            headers = {
                'merchant-token': token,
                'Content-Type':   'application/json',
            }

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'SUCCESS' or data.get('code') == '0000':
                txn.gateway_reference = data.get('transaction_id', '')
                txn.metadata['upay_data'] = data
                txn.save()

                return {
                    'transaction': txn,
                    'payment_url': data.get('redirectGatewayURL') or data.get('payment_url', ''),
                    'token':       data.get('transaction_id'),
                }
            else:
                raise Exception(data.get('message', 'Upay payment initiation failed'))

        except Exception as e:
            txn.status = 'failed'
            txn.metadata['error'] = str(e)
            txn.save()
            raise Exception(f"Upay deposit failed: {str(e)}")

    def process_withdrawal(self, user, amount, payment_method, **kwargs):
        """Upay withdrawal — manual payout request"""
        self.validate_amount(amount)

        payout = PayoutRequest.objects.create(
            user=user,
            amount=amount,
            fee=self.calculate_fee(amount),
            net_amount=amount - self.calculate_fee(amount),
            payout_method='upay',
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

    def verify_payment(self, transaction_id, **kwargs):
        """Verify Upay payment by transaction ID"""
        try:
            token = self._get_auth_token()
            url   = f"{self.base_url}/rgw/payment/status"

            payload = {
                'merchant_id':    self.config['merchant_id'],
                'transaction_id': transaction_id,
            }
            headers = {
                'merchant-token': token,
                'Content-Type':   'application/json',
            }

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            try:
                txn = TxnModel.objects.get(gateway_reference=transaction_id)
                if data.get('status') == 'SUCCESS' or data.get('code') == '0000':
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
            raise Exception(f"Upay verification failed: {str(e)}")

    def get_payment_url(self, txn, **kwargs):
        data = txn.metadata.get('upay_data', {})
        return data.get('redirectGatewayURL') or data.get('payment_url')
