# api/payment_gateways/services/NagadService.py

import requests
import json
import hashlib
import uuid
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from .PaymentProcessor import PaymentProcessor
from ..models import GatewayTransaction as TxnModel, PayoutRequest


class NagadService(PaymentProcessor):
    """Nagad Payment Service Implementation"""
    
    def __init__(self):
        super().__init__('nagad')
        self.base_url = "https://api.mynagad.com" if not getattr(settings, 'NAGAD_SANDBOX', True) \
                      else "https://sandbox.mynagad.com"
        self.config = self.load_config()
    
    def load_config(self):
        """Load Nagad configuration"""
        return {
            'merchant_id': getattr(settings, 'NAGAD_MERCHANT_ID', ''),
            'merchant_key': getattr(settings, 'NAGAD_MERCHANT_KEY', ''),
            'callback_url': getattr(settings, 'NAGAD_CALLBACK_URL', ''),
            'is_sandbox': getattr(settings, 'NAGAD_SANDBOX', True)
        }
    
    def generate_signature(self, data, key):
        """Generate Nagad signature"""
        import hmac
        import base64
        
        message = json.dumps(data, separators=(',', ':'))
        signature = hmac.new(
            key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        return base64.b64encode(signature).decode('utf-8')
    
    def process_deposit(self, user, amount, payment_method=None, **kwargs):
        """Process Nagad deposit"""
        self.validate_amount(amount)
        
        # Create txn
        txn = self.create_txn(
            user=user,
            transaction_type='deposit',
            amount=amount,
            payment_method=payment_method,
            metadata=kwargs.get('metadata', {})
        )
        
        try:
            # Step 1: Initialize payment
            init_url = f"{self.base_url}/api/dfs/check-out/initialize/{self.config['merchant_id']}/{txn.reference_id}"
            
            init_data = {
                'accountNumber': user.phone or '',
                'dateTime': datetime.now().strftime('%Y%m%d%H%M%S'),
                'sensitiveData': {
                    'merchantId': self.config['merchant_id'],
                    'datetime': datetime.now().strftime('%Y%m%d%H%M%S'),
                    'orderId': txn.reference_id,
                    'challenge': str(uuid.uuid4())
                },
                'signature': ''  # Will be calculated
            }
            
            # Generate signature
            signature = self.generate_signature(
                init_data['sensitiveData'],
                self.config['merchant_key']
            )
            init_data['signature'] = signature
            
            headers = {
                'Content-Type': 'application/json',
                'X-KM-IP-V4': '127.0.0.1',  # Should be server IP
                'X-KM-Client-Type': 'PC_WEB',
                'X-KM-Api-Version': 'v-0.2.0'
            }
            
            response = requests.post(init_url, json=init_data, headers=headers)
            response.raise_for_status()
            init_response = response.json()
            
            if init_response.get('reason') != 'Success':
                raise Exception(f"Initialization failed: {init_response.get('message')}")
            
            # Step 2: Complete payment
            payment_url = init_response.get('callBackUrl')
            
            payment_data = {
                'merchantCallbackURL': self.config['callback_url'],
                'amount': str(amount),
                'currencyCode': '050',  # BDT currency code
                'merchantAdditionalInfo': {
                    'userId': str(user.id),
                    'GatewayTransactionType': 'deposit'
                }
            }
            
            headers.update({
                'X-KM-Authorization': init_response.get('paymentReferenceId', '')
            })
            
            payment_response = requests.post(payment_url, json=payment_data, headers=headers)
            payment_response.raise_for_status()
            payment_result = payment_response.json()
            
            # Update txn
            txn.gateway_reference = payment_result.get('paymentReferenceId')
            txn.metadata['nagad_payment_data'] = payment_result
            txn.save()
            
            return {
                'transaction': txn,
                'payment_url': payment_result.get('callBackUrl'),
                'payment_reference': payment_result.get('paymentReferenceId')
            }
            
        except Exception as e:
            txn.status = 'failed'
            txn.metadata['error'] = str(e)
            txn.save()
            raise Exception(f"Nagad deposit failed: {str(e)}")
    
    def process_withdrawal(self, user, amount, payment_method, **kwargs):
        """Process Nagad withdrawal"""
        self.validate_amount(amount)
        
        with db_txn.atomic():
            # Create payout request
            payout = PayoutRequest.objects.create(
                user=user,
                amount=amount,
                fee=self.calculate_fee(amount),
                net_amount=amount - self.calculate_fee(amount),
                payout_method='nagad',
                account_number=payment_method.account_number,
                account_name=payment_method.account_name,
                status='pending',
                reference_id=self.generate_reference_id()
            )
            
            # Create txn record
            txn = self.create_txn(
                user=user,
                transaction_type='withdrawal',
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
            
            # In real implementation, call Nagad P2P API
            # For now, mark as processing
            
            return {
                'transaction': txn,
                'payout': payout,
                'message': 'Withdrawal request submitted successfully'
            }
    
    def verify_payment(self, order_id, **kwargs):
        """Verify Nagad payment"""
        try:
            verify_url = f"{self.base_url}/api/dfs/verify/payment/{order_id}"
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.get(verify_url, headers=headers)
            response.raise_for_status()
            verification_data = response.json()
            
            # Find and update txn
            try:
                txn = TxnModel.objects.get(reference_id=order_id)
                
                if verification_data.get('status') == 'Success':
                    txn.status = 'completed'
                    txn.completed_at = timezone.now()
                    txn.gateway_reference = verification_data.get('paymentRefId')
                    txn.metadata['verification_data'] = verification_data
                    
                    # Update user balance
                    user = txn.user
                    user.balance += txn.net_amount
                    user.save()
                else:
                    txn.status = 'failed'
                    txn.metadata['verification_data'] = verification_data
                
                txn.save()
                return txn
                
            except TxnModel.DoesNotExist:
                return None
                
        except Exception as e:
            raise Exception(f"Payment verification failed: {str(e)}")
    
    def get_payment_url(self, txn, **kwargs):
        """Get Nagad payment URL"""
        return txn.metadata.get('nagad_payment_data', {}).get('callBackUrl')
    
    def check_payment_status(self, payment_ref_id):
        """Check payment status using reference ID"""
        try:
            status_url = f"{self.base_url}/api/dfs/check-out/complete/{payment_ref_id}"
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.get(status_url, headers=headers)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            raise Exception(f"Status check failed: {str(e)}")