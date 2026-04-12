"""
Integration tests for KYC verification.
"""

import pytest
from django.urls import reverse
from unittest.mock import patch, MagicMock
from django.core.files.uploadedfile import SimpleUploadedFile

from api.kyc.models import KYCSubmission


@pytest.mark.django_db
class TestKYCIntegration:
    """Test KYC verification integration."""
    
    def test_kyc_submission(self, authenticated_client):
        """Test KYCSubmission multipart creation."""
        client, user = authenticated_client
        
        nid_front = SimpleUploadedFile("nid_front.jpg", b"file_front", content_type="image/jpeg")
        nid_back = SimpleUploadedFile("nid_back.jpg", b"file_back", content_type="image/jpeg")
        selfie_with_note = SimpleUploadedFile("selfie_with_note.jpg", b"file_selfie", content_type="image/jpeg")
        
        data = {
            'document_type': 'nid',
            'document_number': 'ABC123456',
            'nid_front': nid_front,
            'nid_back': nid_back,
            'selfie_with_note': selfie_with_note,
        }
        
        url = reverse('kyc-submit')
        response = client.post(url, data, format='multipart')
        
        assert response.status_code == 201
        
        # Check KYCSubmission record
        submission = KYCSubmission.objects.get(user=user)
        assert submission.status == 'submitted'
        assert submission.verification_progress == 10
        assert submission.document_type == 'nid'
    
    def test_kyc_fraud_check_endpoint(self, authenticated_client):
        """Test fraud-check placeholder updates progress and audit scores."""
        client, user = authenticated_client

        nid_front = SimpleUploadedFile("nid_front.jpg", b"file_front_x", content_type="image/jpeg")
        nid_back = SimpleUploadedFile("nid_back.jpg", b"file_back_x", content_type="image/jpeg")
        selfie_with_note = SimpleUploadedFile("selfie_with_note.jpg", b"file_selfie_x", content_type="image/jpeg")

        submit_url = reverse('kyc-submit')
        submit_data = {
            'document_type': 'passport',
            'document_number': 'XYZ789',
            'nid_front': nid_front,
            'nid_back': nid_back,
            'selfie_with_note': selfie_with_note,
        }
        submit_resp = client.post(submit_url, submit_data, format='multipart')
        assert submit_resp.status_code == 201

        fraud_url = reverse('kyc-fraud-check')
        fraud_resp = client.post(fraud_url, data={}, format='json')
        assert fraud_resp.status_code == 200

        submission = KYCSubmission.objects.get(user=user)
        assert submission.image_clarity_score > 0
        assert submission.document_matching_score > 0
        assert submission.face_liveness_check in ['pending', 'success', 'failure']
        assert 60 <= submission.verification_progress <= 75
    
    def test_kyc_status_check(self, authenticated_client):
        """Test endpoint to check KYC status."""
        client, user = authenticated_client
        
        # Create a verified submission (files required for the model)
        nid_front = SimpleUploadedFile("nid_front.jpg", b"file_front_y", content_type="image/jpeg")
        nid_back = SimpleUploadedFile("nid_back.jpg", b"file_back_y", content_type="image/jpeg")
        selfie_with_note = SimpleUploadedFile("selfie_with_note.jpg", b"file_selfie_y", content_type="image/jpeg")

        submission = KYCSubmission.objects.create(
            user=user,
            document_type='driving_license',
            document_number='P123456',
            nid_front=nid_front,
            nid_back=nid_back,
            selfie_with_note=selfie_with_note,
            status='verified',
            verification_progress=100,
            submitted_at=None,
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