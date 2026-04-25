# api/payment_gateways/services/PayPalService.py

import requests
import base64
import json
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from django.db import transaction as db_txn
from .PaymentProcessor import PaymentProcessor
from ..models import GatewayTransaction, PayoutRequest


class PayPalService(PaymentProcessor):
    """PayPal Payment Service Implementation"""
    
    def __init__(self):
        super().__init__('paypal')
        self.base_url = "https://api-m.sandbox.paypal.com" if getattr(settings, 'PAYPAL_SANDBOX', True) \
                       else "https://api-m.paypal.com"
        self.config = self.load_config()
        self.access_token = None
    
    def load_config(self):
        """Load PayPal configuration"""
        return {
            'client_id': getattr(settings, 'PAYPAL_CLIENT_ID', ''),
            'client_secret': getattr(settings, 'PAYPAL_CLIENT_SECRET', ''),
            'return_url': getattr(settings, 'PAYPAL_RETURN_URL', ''),
            'cancel_url': getattr(settings, 'PAYPAL_CANCEL_URL', ''),
            'is_sandbox': getattr(settings, 'PAYPAL_SANDBOX', True)
        }
    
    def get_access_token(self):
        """Get PayPal access token"""
        if self.access_token:
            return self.access_token
        
        auth_string = f"{self.config['client_id']}:{self.config['client_secret']}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_auth}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {'grant_type': 'client_credentials'}
        
        try:
            response = requests.post(
                f'{self.base_url}/v1/oauth2/token',
                headers=headers,
                data=data
            )
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data.get('access_token')
            return self.access_token
        except Exception as e:
            raise Exception(f"Failed to get PayPal token: {str(e)}")
    
    def process_deposit(self, user, amount, payment_method=None, **kwargs):
        """Process PayPal deposit"""
        self.validate_amount(amount)
        
        # Create GatewayTransaction
        txn = self.create_GatewayTransaction(
            user=user,
            transaction_type='deposit',
            amount=amount,
            payment_method=payment_method,
            metadata=kwargs.get('metadata', {})
        )
        
        try:
            token = self.get_access_token()
            
            # Create PayPal order
            order_url = f"{self.base_url}/v2/checkout/orders"
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'PayPal-Request-Id': txn.reference_id
            }
            
            order_data = {
                'intent': 'CAPTURE',
                'purchase_units': [{
                    'reference_id': txn.reference_id,
                    'amount': {
                        'currency_code': 'USD',
                        'value': str(amount)
                    },
                    'description': f'Deposit for {user.username}',
                    'custom_id': str(user.id)
                }],
                'payment_source': {
                    'paypal': {
                        'experience_context': {
                            'payment_method_preference': 'IMMEDIATE_PAYMENT_REQUIRED',
                            'brand_name': 'Your Brand Name',
                            'locale': 'en-US',
                            'landing_page': 'LOGIN',
                            'shipping_preference': 'NO_SHIPPING',
                            'user_action': 'PAY_NOW',
                            'return_url': self.config['return_url'],
                            'cancel_url': self.config['cancel_url']
                        }
                    }
                }
            }
            
            response = requests.post(order_url, json=order_data, headers=headers)
            response.raise_for_status()
            order_data = response.json()
            
            # Update GatewayTransaction
            txn.gateway_reference = order_data.get('id')
            txn.metadata['paypal_order'] = order_data
            txn.save()
            
            # Find approval URL
            approval_url = None
            for link in order_data.get('links', []):
                if link.get('rel') == 'approve':
                    approval_url = link.get('href')
                    break
            
            return {
                'transaction': txn,
                'order_id': order_data.get('id'),
                'approval_url': approval_url,
                'status': order_data.get('status')
            }
            
        except Exception as e:
            txn.status = 'failed'
            txn.metadata['error'] = str(e)
            txn.save()
            raise Exception(f"PayPal deposit failed: {str(e)}")
    
    def capture_payment(self, order_id):
        """Capture PayPal payment after approval"""
        try:
            token = self.get_access_token()
            
            capture_url = f"{self.base_url}/v2/checkout/orders/{order_id}/capture"
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'Prefer': 'return=representation'
            }
            
            response = requests.post(capture_url, headers=headers)
            response.raise_for_status()
            capture_data = response.json()
            
            # Find and update GatewayTransaction
            try:
                txn = GatewayTransaction.objects.get(gateway_reference=order_id)
                
                if capture_data.get('status') == 'COMPLETED':
                    txn.status = 'completed'
                    txn.completed_at = timezone.now()
                    txn.metadata['paypal_capture'] = capture_data
                    
                    # Update user balance
                    user = txn.user
                    user.balance += txn.net_amount
                    user.save()
                else:
                    txn.status = 'failed'
                    txn.metadata['paypal_capture'] = capture_data
                
                txn.save()
                return GatewayTransaction
                
            except GatewayTransaction.DoesNotExist:
                return None
                
        except Exception as e:
            raise Exception(f"Payment capture failed: {str(e)}")
    
    def process_withdrawal(self, user, amount, payment_method, **kwargs):
        """Process PayPal withdrawal (Payout)"""
        self.validate_amount(amount)
        
        with db_txn.atomic():
            # Create payout request
            payout = PayoutRequest.objects.create(
                user=user,
                amount=amount,
                fee=self.calculate_fee(amount),
                net_amount=amount - self.calculate_fee(amount),
                payout_method='paypal',
                account_number=payment_method.account_number,
                account_name=payment_method.account_name,
                status='pending',
                reference_id=self.generate_reference_id()
            )
            
            # Create GatewayTransaction record
            txn = self.create_GatewayTransaction(
                user=user,
                transaction_type='withdrawal',
                amount=amount,
                payment_method=payment_method,
                metadata={
                    'payout_id': payout.id,
                    **kwargs.get('metadata', {})
                }
            )
            
            try:
                token = self.get_access_token()
                
                # Create PayPal payout
                payout_url = f"{self.base_url}/v1/payments/payouts"
                
                headers = {
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                }
                
                payout_data = {
                    'sender_batch_header': {
                        'sender_batch_id': txn.reference_id,
                        'email_subject': 'You have a payment',
                        'email_message': f'You have received a payment of ${amount}'
                    },
                    'items': [{
                        'recipient_type': 'EMAIL',
                        'amount': {
                            'value': str(amount),
                            'currency': 'USD'
                        },
                        'receiver': payment_method.account_number,
                        'note': f'Withdrawal for {user.username}',
                        'sender_item_id': str(txn.id)
                    }]
                }
                
                response = requests.post(payout_url, json=payout_data, headers=headers)
                response.raise_for_status()
                payout_response = response.json()
                
                # Update GatewayTransaction and payout
                txn.gateway_reference = payout_response.get('batch_header', {}).get('payout_batch_id')
                txn.metadata['paypal_payout'] = payout_response
                txn.save()
                
                payout.gateway_reference = txn.gateway_reference
                payout.status = 'processing'
                payout.save()
                
                # Deduct from user balance
                user.balance -= amount
                user.save()
                
                return {
                    'transaction': txn,
                    'payout': payout,
                    'batch_id': txn.gateway_reference,
                    'message': 'Payout submitted successfully'
                }
                
            except Exception as e:
                txn.status = 'failed'
                txn.metadata['error'] = str(e)
                txn.save()
                
                payout.status = 'failed'
                payout.save()
                
                raise Exception(f"PayPal withdrawal failed: {str(e)}")
    
    def verify_payment(self, order_id, **kwargs):
        """Verify PayPal payment"""
        try:
            token = self.get_access_token()
            
            order_url = f"{self.base_url}/v2/checkout/orders/{order_id}"
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(order_url, headers=headers)
            response.raise_for_status()
            order_data = response.json()
            
            # Find and update GatewayTransaction
            try:
                txn = GatewayTransaction.objects.get(gateway_reference=order_id)
                txn.metadata['paypal_verification'] = order_data
                txn.save()
                return GatewayTransaction
            except GatewayTransaction.DoesNotExist:
                return None
                
        except Exception as e:
            raise Exception(f"Payment verification failed: {str(e)}")
    
    def get_payment_url(self, GatewayTransaction, **kwargs):
        """Get PayPal payment URL"""
        return GatewayTransaction.metadata.get('paypal_order', {}).get('links', [{}])[0].get('href')
    
    def get_payout_status(self, payout_batch_id):
        """Get PayPal payout status"""
        try:
            token = self.get_access_token()
            
            status_url = f"{self.base_url}/v1/payments/payouts/{payout_batch_id}"
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(status_url, headers=headers)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            raise Exception(f"Payout status check failed: {str(e)}")