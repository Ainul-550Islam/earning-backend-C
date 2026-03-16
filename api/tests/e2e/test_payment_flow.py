"""
End-to-end tests for payment flow.
"""

import pytest
from django.urls import reverse
from unittest.mock import patch


@pytest.mark.django_db
class TestPaymentJourney:
    """Test complete payment journey from initiation to wallet update."""
    
    @patch('api.payment_gateways.services.StripePaymentGateway.create_payment_intent')
    def test_payment_deposit_flow(self, mock_stripe):
        """Test user depositing money via payment gateway."""
        from django.test import Client
        client = Client()
        
        # 1. User registration and login
        user_data = {
            'email': 'paymentuser@example.com',
            'password': 'payment123',
            'username': 'paymentuser'
        }
        
        response = client.post(reverse('user-register'), user_data, format='json')
        assert response.status_code == 201
        
        # Login
        response = client.post(reverse('user-login'), {
            'email': 'paymentuser@example.com',
            'password': 'payment123'
        }, format='json')
        
        token = response.data['access']
        client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        
        # 2. Initiate payment
        mock_stripe.return_value = {
            'client_secret': 'secret_123',
            'transaction_id': 'txn_123456'
        }
        
        deposit_data = {
            'amount': 50.00,
            'currency': 'USD',
            'payment_method': 'stripe'
        }
        
        response = client.post(reverse('payment-initiate'), deposit_data, format='json')
        assert response.status_code == 200
        assert 'payment_url' in response.data
        
        # 3. Simulate payment success callback
        callback_data = {
            'transaction_id': 'txn_123456',
            'status': 'success',
            'amount': 50.00
        }
        
        # Note: In reality, this callback would come from Stripe, but we simulate it
        response = client.post(reverse('payment-callback', args=['stripe']), 
                               callback_data, format='json')
        assert response.status_code == 200
        
        # 4. Check wallet balance
        response = client.get(reverse('wallet-detail'))
        assert response.status_code == 200
        assert response.data['balance'] == '50.00'
        
        # 5. Check transaction history
        response = client.get(reverse('transaction-list'))
        assert response.status_code == 200
        assert len(response.data['results']) > 0
        assert any(txn['amount'] == '50.00' for txn in response.data['results'])