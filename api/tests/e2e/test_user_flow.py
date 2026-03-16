"""
End-to-end tests for user journey.
"""

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestUserJourney:
    """Test complete user journey from signup to earning and withdrawal."""
    
    def test_complete_user_flow(self):
        """Test a user's journey: signup, KYC, complete offer, withdraw."""
        from django.test import Client
        client = Client()
        
        # 1. User Registration
        register_data = {
            'email': 'journeyuser@example.com',
            'password': 'journey123',
            'username': 'journeyuser',
            'first_name': 'Journey',
            'last_name': 'User'
        }
        
        response = client.post(reverse('user-register'), register_data, format='json')
        assert response.status_code == 201
        
        # 2. Login
        login_data = {
            'email': 'journeyuser@example.com',
            'password': 'journey123'
        }
        
        response = client.post(reverse('user-login'), login_data, format='json')
        assert response.status_code == 200
        assert 'access' in response.data  # JWT token
        
        # Set the token for future requests
        token = response.data['access']
        client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        
        # 3. Check wallet (should be 0 initially)
        response = client.get(reverse('wallet-detail'))
        assert response.status_code == 200
        assert response.data['balance'] == '0.00'
        
        # 4. Submit KYC
        # ... (simplified: just mark as verified for this test)
        from api.users.models import User
        user = User.objects.get(email='journeyuser@example.com')
        user.is_kyc_verified = True
        user.save()
        
        # 5. Complete an offer (simulate offer completion)
        from api.offerwall.models import Offer
        offer = Offer.objects.create(
            title='Test Offer for Journey',
            reward_amount=10.00,
            currency='USD',
            is_active=True
        )
        
        # Simulate offer completion by calling the completion endpoint
        completion_data = {
            'offer_id': offer.id,
            'proof': 'completion_proof_123'
        }
        
        response = client.post(reverse('offer-complete'), completion_data, format='json')
        assert response.status_code == 200
        
        # 6. Check wallet balance (should be 10.00)
        response = client.get(reverse('wallet-detail'))
        assert response.status_code == 200
        assert response.data['balance'] == '10.00'
        
        # 7. Request withdrawal
        withdrawal_data = {
            'amount': 10.00,
            'currency': 'USD',
            'method': 'paypal',
            'paypal_email': 'journeyuser@example.com'
        }
        
        response = client.post(reverse('withdraw-request'), withdrawal_data, format='json')
        assert response.status_code == 201  # Withdrawal request created
        
        # 8. Check withdrawal status
        withdrawal_id = response.data['id']
        response = client.get(reverse('withdrawal-detail', args=[withdrawal_id]))
        assert response.status_code == 200
        assert response.data['status'] in ['pending', 'processing']
        
        # 9. Logout
        response = client.post(reverse('user-logout'))
        assert response.status_code == 200