"""
Integration tests for KYC verification.
"""

import pytest
from django.urls import reverse
from unittest.mock import patch, MagicMock
from django.core.files.uploadedfile import SimpleUploadedFile

from api.kyc.models import KYCVerification


@pytest.mark.django_db
class TestKYCIntegration:
    """Test KYC verification integration."""
    
    def test_kyc_submission(self, authenticated_client):
        """Test KYC document submission."""
        client, user = authenticated_client
        
        # Create a dummy document
        document = SimpleUploadedFile(
            "id_card.jpg",
            b"file_content",
            content_type="image/jpeg"
        )
        
        data = {
            'document_type': 'id_card',
            'document_number': 'ABC123456',
            'document_front': document,
            'country': 'US'
        }
        
        url = reverse('kyc-submit')
        response = client.post(url, data, format='multipart')
        
        assert response.status_code == 201
        
        # Check KYC record
        kyc = KYCVerification.objects.get(user=user)
        assert kyc.status == 'pending'
        assert kyc.document_type == 'id_card'
    
    @patch('api.kyc.services.KYCService.verify_document')
    def test_kyc_auto_verification(self, mock_verify, authenticated_client):
        """Test automatic KYC verification by third-party service."""
        mock_verify.return_value = {
            'verified': True,
            'score': 0.95,
            'details': {'name_match': True, 'dob_match': True}
        }
        
        client, user = authenticated_client
        
        # Submit KYC
        kyc = KYCVerification.objects.create(
            user=user,
            document_type='id_card',
            document_number='XYZ789',
            status='pending'
        )
        
        # Trigger verification (this might be done by a Celery task)
        from api.kyc.services import KYCService
        result = KYCService.verify_document(kyc)
        
        kyc.refresh()
        assert kyc.status == 'verified'
        assert kyc.verification_score == 0.95
    
    def test_kyc_status_check(self, authenticated_client):
        """Test endpoint to check KYC status."""
        client, user = authenticated_client
        
        KYCVerification.objects.create(
            user=user,
            document_type='passport',
            document_number='P123456',
            status='verified'
        )
        
        url = reverse('kyc-status')
        response = client.get(url)
        
        assert response.status_code == 200
        assert response.data['status'] == 'verified'
    
    def test_kyc_restricts_transaction_when_unverified(self, authenticated_client, test_wallet):
        """Test that unverified users cannot perform transactions above limit."""
        client, user = authenticated_client
        
        # Ensure user is not KYC verified
        user.is_kyc_verified = False
        user.save()
        
        # Try to make a withdrawal above the limit for unverified users
        data = {
            'amount': 500.00,  # Above the limit for unverified
            'currency': 'USD',
            'method': 'bank_transfer'
        }
        
        url = reverse('withdraw-request')
        response = client.post(url, data, format='json')
        
        # Should be forbidden
        assert response.status_code == 403
        assert 'KYC verification required' in response.data['detail']