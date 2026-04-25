# api/payment_gateways/services/ShurjoPayService.py

import requests
import json
import uuid
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from .PaymentProcessor import PaymentProcessor
from ..models import GatewayTransaction as TxnModel, PayoutRequest


class ShurjoPayService(PaymentProcessor):
    """ShurjoPay Payment Service Implementation (Bangladesh)"""

    SANDBOX_URL = "https://sandbox.shurjopayment.com/api"
    LIVE_URL    = "https://engine.shurjopayment.com/api"

    def __init__(self):
        super().__init__('shurjopay')
        is_sandbox = getattr(settings, 'SHURJOPAY_SANDBOX', True)
        self.base_url = self.SANDBOX_URL if is_sandbox else self.LIVE_URL
        self.config = self.load_config()
        self._token_cache = None

    def load_config(self):
        return {
            'username':    getattr(settings, 'SHURJOPAY_USERNAME', ''),
            'password':    getattr(settings, 'SHURJOPAY_PASSWORD', ''),
            'client_ip':   getattr(settings, 'SHURJOPAY_CLIENT_IP', '127.0.0.1'),
            'return_url':  getattr(settings, 'SHURJOPAY_RETURN_URL', ''),
            'cancel_url':  getattr(settings, 'SHURJOPAY_CANCEL_URL', ''),
            'is_sandbox':  getattr(settings, 'SHURJOPAY_SANDBOX', True),
        }

    def _get_token(self):
        """Get ShurjoPay auth token"""
        if self._token_cache:
            return self._token_cache

        url = f"{self.base_url}/get_token/"
        payload = {
            'username': self.config['username'],
            'password': self.config['password'],
        }
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        token = data.get('token')
        if not token:
            raise Exception("ShurjoPay: Failed to get auth token")

        self._token_cache = {
            'token':        token,
            'store_id':     data.get('store_id'),
            'execute_url':  data.get('execute_url'),
            'token_type':   data.get('token_type', 'Bearer'),
        }
        return self._token_cache

    def process_deposit(self, user, amount, payment_method=None, **kwargs):
        """Initiate ShurjoPay payment"""
        self.validate_amount(amount)

        txn = self.create_GatewayTransaction(
            user=user,
            transaction_type='deposit',
            amount=amount,
            payment_method=payment_method,
            metadata=kwargs.get('metadata', {}),
        )

        try:
            token_data = self._get_token()
            url = f"{self.base_url}/secret-pay/"

            headers = {
                'Authorization': f"{token_data['token_type']} {token_data['token']}",
                'Content-Type':  'application/json',
            }

            payload = {
                'prefix':         'SP',
                'token':          token_data['token'],
                'return_url':     self.config['return_url'],
                'cancel_url':     self.config['cancel_url'],
                'store_id':       token_data['store_id'],
                'amount':         str(amount),
                'order_id':       txn.reference_id,
                'currency':       'BDT',
                'client_ip':      self.config['client_ip'],
                'customer_name':  getattr(user, 'get_full_name', lambda: user.username)(),
                'customer_email': user.email,
                'customer_phone': getattr(user, 'phone', '01700000000'),
                'customer_address': 'Dhaka',
                'customer_city':  'Dhaka',
                'customer_country': 'Bangladesh',
            }

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            checkout_url = data.get('checkout_url')
            if not checkout_url:
                raise Exception(data.get('message', 'ShurjoPay payment init failed'))

            txn.gateway_reference = data.get('sp_order_id', '')
            txn.metadata['shurjopay_data'] = data
            txn.save()

            return {
                'transaction':  txn,
                'payment_url':  checkout_url,
                'sp_order_id':  data.get('sp_order_id'),
            }

        except Exception as e:
            txn.status = 'failed'
            txn.metadata['error'] = str(e)
            txn.save()
            raise Exception(f"ShurjoPay deposit failed: {str(e)}")

    def process_withdrawal(self, user, amount, payment_method, **kwargs):
        """ShurjoPay withdrawal — manual payout request"""
        self.validate_amount(amount)

        payout = PayoutRequest.objects.create(
            user=user,
            amount=amount,
            fee=self.calculate_fee(amount),
            net_amount=amount - self.calculate_fee(amount),
            payout_method='shurjopay',
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

    def verify_payment(self, order_id, **kwargs):
        """Verify ShurjoPay payment by order ID"""
        try:
            token_data = self._get_token()
            url = f"{self.base_url}/verification/"

            headers = {
                'Authorization': f"{token_data['token_type']} {token_data['token']}",
                'Content-Type':  'application/json',
            }
            payload = {'order_id': order_id}

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            # ShurjoPay returns a list
            result = data[0] if isinstance(data, list) and data else data

            try:
                txn = TxnModel.objects.get(reference_id=result.get('merchant_order_id', order_id))
                sp_code = str(result.get('sp_code', ''))
                if sp_code in ('1000', '1001'):
                    txn.status = 'completed'
                    txn.metadata['verification_data'] = result
                    user = txn.user
                    if hasattr(user, 'balance'):
                        user.balance += txn.net_amount
                        user.save(update_fields=['balance'])
                else:
                    txn.status = 'failed'
                    txn.metadata['verification_data'] = result
                txn.save()
                return txn
            except TxnModel.DoesNotExist:
                return None

        except Exception as e:
            raise Exception(f"ShurjoPay verification failed: {str(e)}")

    def get_payment_url(self, txn, **kwargs):
        return txn.metadata.get('shurjopay_data', {}).get('checkout_url')
