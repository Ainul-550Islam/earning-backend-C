"""
Mock classes and functions for external services.
"""

from unittest.mock import Mock, MagicMock
import json


class MockPaymentGateway:
    """Mock payment gateway for testing."""
    
    def __init__(self):
        self.payments = {}
        self.refunds = {}
        self.payment_id_counter = 1
    
    def create_payment(self, amount, currency, **kwargs):
        """Mock payment creation."""
        payment_id = f'pay_{self.payment_id_counter}'
        self.payment_id_counter += 1
        
        self.payments[payment_id] = {
            'id': payment_id,
            'amount': amount,
            'currency': currency,
            'status': 'pending',
            'created_at': '2023-01-01T00:00:00Z',
            **kwargs
        }
        
        return {
            'success': True,
            'payment_id': payment_id,
            'payment_url': f'https://mock-payment.com/pay/{payment_id}'
        }
    
    def verify_payment(self, payment_id):
        """Mock payment verification."""
        payment = self.payments.get(payment_id)
        if not payment:
            return {'success': False, 'error': 'Payment not found'}
        
        # Simulate payment success
        payment['status'] = 'completed'
        
        return {
            'success': True,
            'status': 'completed',
            'amount': payment['amount'],
            'currency': payment['currency']
        }
    
    def refund_payment(self, payment_id, amount=None):
        """Mock refund."""
        refund_id = f'ref_{self.payment_id_counter}'
        self.payment_id_counter += 1
        
        payment = self.payments[payment_id]
        refund_amount = amount or payment['amount']
        
        self.refunds[refund_id] = {
            'id': refund_id,
            'payment_id': payment_id,
            'amount': refund_amount,
            'status': 'pending'
        }
        
        return {'success': True, 'refund_id': refund_id}


class MockKYCService:
    """Mock KYC verification service."""
    
    def __init__(self):
        self.verifications = {}
    
    def verify_document(self, document_front, document_back=None, document_type='id_card'):
        """Mock document verification."""
        # Simulate verification process
        verification_id = f'kyc_{len(self.verifications) + 1}'
        
        # Mock result
        result = {
            'verified': True,
            'verification_id': verification_id,
            'score': 0.95,
            'details': {
                'document_valid': True,
                'name_match': True,
                'dob_match': True,
                'expiry_valid': True
            },
            'extracted_data': {
                'full_name': 'John Doe',
                'date_of_birth': '1990-01-01',
                'document_number': 'ABC123456',
                'expiry_date': '2030-12-31'
            }
        }
        
        self.verifications[verification_id] = result
        return result
    
    def check_status(self, verification_id):
        """Check verification status."""
        return self.verifications.get(verification_id, {'error': 'Not found'})


class MockAdNetwork:
    """Mock ad network for offerwalls."""
    
    def __init__(self):
        self.offers = []
        self.conversions = []
    
    def get_offers(self, user_id, country, device_type):
        """Mock fetching offers."""
        # Return mock offers
        return {
            'offers': [
                {
                    'offer_id': 'offer_1',
                    'name': 'Test Offer 1',
                    'description': 'Complete a survey',
                    'reward': 2.50,
                    'currency': 'USD',
                    'requirements': {'min_age': 18},
                    'icon_url': 'https://example.com/icon1.png'
                },
                {
                    'offer_id': 'offer_2',
                    'name': 'Test Offer 2',
                    'description': 'Install an app',
                    'reward': 5.00,
                    'currency': 'USD',
                    'requirements': {'device': 'android'},
                    'icon_url': 'https://example.com/icon2.png'
                }
            ]
        }
    
    def track_conversion(self, offer_id, user_id, transaction_id):
        """Mock conversion tracking."""
        conversion = {
            'offer_id': offer_id,
            'user_id': user_id,
            'transaction_id': transaction_id,
            'converted': True,
            'reward': 2.50,
            'timestamp': '2023-01-01T12:00:00Z'
        }
        
        self.conversions.append(conversion)
        return conversion


class MockFraudDetection:
    """Mock fraud detection service."""
    
    def check_transaction(self, transaction_data):
        """Mock fraud check."""
        # Simple mock: flag high amounts as suspicious
        amount = transaction_data.get('amount', 0)
        
        if amount > 1000:
            return {
                'is_fraud': True,
                'risk_score': 0.85,
                'reasons': ['High amount for new user']
            }
        else:
            return {
                'is_fraud': False,
                'risk_score': 0.05,
                'reasons': []
            }
    
    def check_user_behavior(self, user_id, actions):
        """Mock user behavior analysis."""
        # Flag if too many actions in short time
        if len(actions) > 10:
            return {
                'suspicious': True,
                'score': 0.75,
                'reason': 'Too many actions in short period'
            }
        return {'suspicious': False, 'score': 0.1}


# Singleton instances for convenience
mock_payment_gateway = MockPaymentGateway()
mock_kyc_service = MockKYCService()
mock_ad_network = MockAdNetwork()
mock_fraud_detection = MockFraudDetection()