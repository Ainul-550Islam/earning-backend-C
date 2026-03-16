"""
Integration tests for referral system.
"""

import pytest
from django.urls import reverse

from api.referral.models import Referral, ReferralReward
from api.users.models import User


@pytest.mark.django_db
class TestReferralIntegration:
    """Test referral system integration."""
    
    def test_referral_code_generation(self, authenticated_client):
        """Test that a user gets a referral code upon registration."""
        client, user = authenticated_client
        
        # Check that the user has a referral code
        assert user.referral_code is not None
        assert len(user.referral_code) > 0
    
    def test_referral_signup(self, authenticated_client):
        """Test that a new user can sign up with a referral code."""
        client, referrer = authenticated_client
        
        # Get referrer's code
        referrer_code = referrer.referral_code
        
        # Create a new user using the referral code
        new_user_data = {
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'username': 'newuser',
            'referral_code': referrer_code
        }
        
        url = reverse('user-register')
        response = client.post(url, new_user_data, format='json')
        
        assert response.status_code == 201
        
        # Check that referral record is created
        new_user = User.objects.get(email='newuser@example.com')
        referral = Referral.objects.get(referred=new_user)
        
        assert referral.referrer == referrer
        assert referral.reward_status == 'pending'
    
    def test_referral_reward_on_kyc(self, authenticated_client):
        """Test that referral reward is given when referred user completes KYC."""
        client, referrer = authenticated_client
        
        # Create a referred user
        referred_user = User.objects.create_user(
            email='referred@example.com',
            password='referred123',
            username='referred'
        )
        
        # Create referral record
        referral = Referral.objects.create(
            referrer=referrer,
            referred=referred_user,
            reward_status='pending'
        )
        
        # Simulate KYC verification of referred user
        referred_user.is_kyc_verified = True
        referred_user.save()
        
        # Trigger reward (this might be done by a signal or task)
        from api.referral.services import ReferralService
        ReferralService.process_referral_reward(referral)
        
        referral.refresh()
        assert referral.reward_status == 'rewarded'
        
        # Check that a reward transaction was created
        reward = ReferralReward.objects.get(referral=referral)
        assert reward.amount > 0
        assert reward.currency == 'USD'
    
    def test_referral_dashboard(self, authenticated_client):
        """Test referral dashboard data."""
        client, user = authenticated_client
        
        # Create some referrals
        for i in range(3):
            referred = User.objects.create_user(
                email=f'referred{i}@example.com',
                password='pass123',
                username=f'referred{i}'
            )
            Referral.objects.create(
                referrer=user,
                referred=referred,
                reward_status='rewarded' if i < 2 else 'pending'
            )
        
        url = reverse('referral-dashboard')
        response = client.get(url)
        
        assert response.status_code == 200
        assert response.data['total_referred'] == 3
        assert response.data['total_rewarded'] == 2
        assert 'total_earnings' in response.data