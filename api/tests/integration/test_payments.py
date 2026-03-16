"""
Integration tests for payment gateway functionality.
"""

import pytest
from django.urls import reverse
from unittest.mock import patch
from decimal import Decimal

from api.payment_gateways.models import PaymentTransaction
from api.wallet.models import Wallet, Transaction


@pytest.mark.django_db
class TestPaymentIntegration:
    """Test payment gateway integration."""
    
    def test_payment_initiation(self, authenticated_client, test_wallet):
        """Test that payment initiation creates a transaction record."""
        client, user = authenticated_client
        
        # Data for payment initiation
        data = {
            'amount': 100.00,
            'currency': 'USD',
            'payment_method': 'stripe',
            'return_url': 'https://example.com/return'
        }
        
        url = reverse('payment-initiate')
        response = client.post(url, data, format='json')
        
        assert response.status_code == 200
        assert 'payment_url' in response.data
        assert 'transaction_id' in response.data
        
        # Check that transaction record is created
        transaction = PaymentTransaction.objects.get(user=user)
        assert transaction.amount == Decimal('100.00')
        assert transaction.status == 'pending'
    
    def test_payment_callback_success(self, authenticated_client, test_wallet):
        """Test payment callback for successful payment."""
        client, user = authenticated_client
        
        # First, create a pending transaction
        transaction = PaymentTransaction.objects.create(
            user=user,
            amount=100.00,
            currency='USD',
            gateway='stripe',
            status='pending',
            gateway_transaction_id='txn_123'
        )
        
        # Simulate callback from payment gateway
        callback_data = {
            'transaction_id': transaction.gateway_transaction_id,
            'status': 'success',
            'amount': 100.00,
            'currency': 'USD'
        }
        
        url = reverse('payment-callback', args=['stripe'])
        response = client.post(url, callback_data, format='json')
        
        assert response.status_code == 200
        
        # Refresh transaction and wallet
        transaction.refresh()
        wallet = Wallet.objects.get(user=user)
        
        assert transaction.status == 'completed'
        assert wallet.balance == Decimal('1100.00')  # Initial 1000 + 100
    
    def test_payment_callback_failure(self, authenticated_client, test_wallet):
        """Test payment callback for failed payment."""
        client, user = authenticated_client
        
        transaction = PaymentTransaction.objects.create(
            user=user,
            amount=100.00,
            currency='USD',
            gateway='stripe',
            status='pending',
            gateway_transaction_id='txn_456'
        )
        
        callback_data = {
            'transaction_id': transaction.gateway_transaction_id,
            'status': 'failed',
            'reason': 'Insufficient funds'
        }
        
        url = reverse('payment-callback', args=['stripe'])
        response = client.post(url, callback_data, format='json')
        
        assert response.status_code == 200
        
        transaction.refresh()
        wallet = Wallet.objects.get(user=user)
        
        assert transaction.status == 'failed'
        assert wallet.balance == Decimal('1000.00')  # Unchanged
    
    @patch('api.payment_gateways.services.stripe.PaymentIntent.create')
    def test_payment_gateway_error_handling(self, mock_stripe, authenticated_client):
        """Test error handling when payment gateway fails."""
        mock_stripe.side_effect = Exception("Stripe API error")
        
        client, user = authenticated_client
        
        data = {
            'amount': 100.00,
            'currency': 'USD',
            'payment_method': 'stripe'
        }
        
        url = reverse('payment-initiate')
        response = client.post(url, data, format='json')
        
        assert response.status_code == 500
        assert 'error' in response.data