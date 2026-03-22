# api/payment_gateways/services/BkashService.py

import requests
import json
import hashlib
import uuid
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from .PaymentProcessor import PaymentProcessor
from ..models import GatewayTransaction as TxnModel, PayoutRequest


class BkashService(PaymentProcessor):
    """bKash Payment Service Implementation"""
    
    def __init__(self):
        super().__init__('bkash')
        self.base_url = "https://tokenized.sandbox.bka.sh/v1.2.0-beta"
        self.config = self.load_config()
    
    def load_config(self):
        """Load bKash configuration"""
        return {
            'app_key': getattr(settings, 'BKASH_APP_KEY', ''),
            'app_secret': getattr(settings, 'BKASH_APP_SECRET', ''),
            'username': getattr(settings, 'BKASH_USERNAME', ''),
            'password': getattr(settings, 'BKASH_PASSWORD', ''),
            'callback_url': getattr(settings, 'BKASH_CALLBACK_URL', ''),
            'is_sandbox': getattr(settings, 'BKASH_SANDBOX', True)
        }
    
    def get_access_token(self):
        """Get bKash access token"""
        url = f"{self.base_url}/tokenized/checkout/token/grant"
        
        headers = {
            'username': self.config['username'],
            'password': self.config['password'],
            'Content-Type': 'application/json'
        }
        
        payload = {
            'app_key': self.config['app_key'],
            'app_secret': self.config['app_secret']
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get('id_token')
        except Exception as e:
            raise Exception(f"Failed to get bKash token: {str(e)}")
    
    def process_deposit(self, user, amount, payment_method=None, **kwargs):
        """Process bKash deposit"""
        self.validate_amount(amount)
        
        # Create GatewayTransaction
        GatewayTransaction = self.create_GatewayTransaction(
            user=user,
            GatewayTransaction_type='deposit',
            amount=amount,
            payment_method=payment_method,
            metadata=kwargs.get('metadata', {})
        )
        
        try:
            # Get access token
            token = self.get_access_token()
            
            # Create payment
            payment_url = f"{self.base_url}/tokenized/checkout/create"
            
            headers = {
                'Authorization': token,
                'X-APP-Key': self.config['app_key'],
                'Content-Type': 'application/json'
            }
            
            payload = {
                'mode': '0011',
                'payerReference': str(user.id),
                'callbackURL': self.config['callback_url'],
                'amount': str(amount),
                'currency': 'BDT',
                'intent': 'sale',
                'merchantInvoiceNumber': GatewayTransaction.reference_id
            }
            
            response = requests.post(payment_url, json=payload, headers=headers)
            response.raise_for_status()
            payment_data = response.json()
            
            # Update GatewayTransaction with payment ID
            GatewayTransaction.gateway_reference = payment_data.get('paymentID')
            GatewayTransaction.metadata['bkash_payment_data'] = payment_data
            GatewayTransaction.save()
            
            # Return payment URL
            payment_url = payment_data.get('bkashURL')
            return {
                'GatewayTransaction': GatewayTransaction,
                'payment_url': payment_url,
                'payment_id': payment_data.get('paymentID')
            }
            
        except Exception as e:
            GatewayTransaction.status = 'failed'
            GatewayTransaction.metadata['error'] = str(e)
            GatewayTransaction.save()
            raise Exception(f"bKash deposit failed: {str(e)}")
    
    def process_withdrawal(self, user, amount, payment_method, **kwargs):
        """Process bKash withdrawal (P2P)"""
        self.validate_amount(amount)
        
        with db_GatewayTransaction.atomic():
            # Create payout request
            payout = PayoutRequest.objects.create(
                user=user,
                amount=amount,
                fee=self.calculate_fee(amount),
                net_amount=amount - self.calculate_fee(amount),
                payout_method='bkash',
                account_number=payment_method.account_number,
                account_name=payment_method.account_name,
                status='pending',
                reference_id=self.generate_reference_id()
            )
            
            # Create GatewayTransaction record
            GatewayTransaction = self.create_GatewayTransaction(
                user=user,
                GatewayTransaction_type='withdrawal',
                amount=amount,
                payment_method=payment_method,
                metadata={
                    'payout_id': payout.id,
                    **kwargs.get('metadata', {})
                }
            )
            
            # Deduct from user balance
            user.balance -= amount
            user.save()
            
            # Process bKash P2P (in real implementation)
            # This would call bKash P2P API
            
            return {
                'GatewayTransaction': GatewayTransaction,
                'payout': payout,
                'message': 'Withdrawal request submitted successfully'
            }
    
    def verify_payment(self, payment_id, **kwargs):
        """Verify bKash payment"""
        try:
            token = self.get_access_token()
            
            url = f"{self.base_url}/tokenized/checkout/payment/status/{payment_id}"
            
            headers = {
                'Authorization': token,
                'X-APP-Key': self.config['app_key'],
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            verification_data = response.json()
            
            # Find and update GatewayTransaction
            try:
                GatewayTransaction = TxnModel.objects.get(gateway_reference=payment_id)
                
                if verification_data.get('GatewayTransactionStatus') == 'Completed':
                    GatewayTransaction.status = 'completed'
                    GatewayTransaction.completed_at = timezone.now()
                    GatewayTransaction.metadata['verification_data'] = verification_data
                    
                    # Update user balance
                    user = GatewayTransaction.user
                    user.balance += GatewayTransaction.net_amount
                    user.save()
                else:
                    GatewayTransaction.status = 'failed'
                    GatewayTransaction.metadata['verification_data'] = verification_data
                
                GatewayTransaction.save()
                return GatewayTransaction
                
            except GatewayTransaction.DoesNotExist:
                return None
                
        except Exception as e:
            raise Exception(f"Payment verification failed: {str(e)}")
    
    def get_payment_url(self, GatewayTransaction, **kwargs):
        """Get bKash payment URL"""
        # In bKash, payment URL is generated during create payment
        return GatewayTransaction.metadata.get('bkash_payment_data', {}).get('bkashURL')
    
    def execute_payment(self, payment_id):
        """Execute bKash payment (after callback)"""
        try:
            token = self.get_access_token()
            
            url = f"{self.base_url}/tokenized/checkout/execute/{payment_id}"
            
            headers = {
                'Authorization': token,
                'X-APP-Key': self.config['app_key'],
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, headers=headers)
            response.raise_for_status()
            execute_data = response.json()
            
            return execute_data
            
        except Exception as e:
            raise Exception(f"Payment execution failed: {str(e)}")
    
    def search_GatewayTransaction(self, trx_id):
        """Search bKash GatewayTransaction"""
        try:
            token = self.get_access_token()
            
            url = f"{self.base_url}/tokenized/checkout/general/searchGatewayTransaction/{trx_id}"
            
            headers = {
                'Authorization': token,
                'X-APP-Key': self.config['app_key'],
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            raise Exception(f"GatewayTransaction search failed: {str(e)}")