"""
Test Verification System

Comprehensive tests for advertiser verification
including document validation and approval workflows.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock
from django.core.files.uploadedfile import SimpleUploadedFile

from ..models.advertiser import Advertiser, AdvertiserProfile, AdvertiserVerification
try:
    from ..services import AdvertiserVerificationService
except ImportError:
    AdvertiserVerificationService = None
try:
    from ..services import AdvertiserService
except ImportError:
    AdvertiserService = None

User = get_user_model()


class VerificationWorkflowTestCase(TestCase):
    """Test cases for complete verification workflow."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.verification_service = AdvertiserVerificationService()
        
        self.valid_advertiser_data = {
            'company_name': 'Test Company',
            'contact_email': 'contact@testcompany.com',
            'contact_phone': '+1234567890',
            'website': 'https://testcompany.com',
            'industry': 'technology',
            'company_size': 'medium',
        }
        
        self.advertiser = self.advertiser_service.create_advertiser(
            self.user, 
            self.valid_advertiser_data
        )
    
    def test_complete_verification_workflow(self):
        """Test complete verification workflow from submission to approval."""
        # Step 1: Submit verification documents
        documents = [
            {
                'document_type': 'business_license',
                'document_number': 'BL123456',
                'expiry_date': '2025-12-31',
                'file': self._create_test_file('license.pdf')
            },
            {
                'document_type': 'tax_id',
                'document_number': 'TAX789012',
                'expiry_date': '2024-12-31',
                'file': self._create_test_file('tax.pdf')
            }
        ]
        
        verification = self.verification_service.submit_verification(
            self.advertiser, 
            documents
        )
        
        self.assertEqual(verification.status, 'pending')
        self.assertEqual(verification.documents.count(), 2)
        self.assertEqual(self.advertiser.verification_status, 'pending')
        
        # Step 2: Approve verification
        approved_verification = self.verification_service.approve_verification(
            verification
        )
        
        self.assertEqual(approved_verification.status, 'approved')
        self.assertEqual(self.advertiser.verification_status, 'verified')
        self.assertIsNotNone(self.advertiser.verified_at)
        
        # Step 3: Check verification history
        history = self.verification_service.get_verification_history(
            self.advertiser
        )
        
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].status, 'approved')
    
    def test_verification_rejection_workflow(self):
        """Test verification rejection workflow."""
        # Submit verification
        documents = [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': self._create_test_file('license.pdf')
        }]
        
        verification = self.verification_service.submit_verification(
            self.advertiser, 
            documents
        )
        
        # Reject verification
        reason = 'Document appears to be altered'
        rejected_verification = self.verification_service.reject_verification(
            verification, 
            reason
        )
        
        self.assertEqual(rejected_verification.status, 'rejected')
        self.assertEqual(rejected_verification.rejection_reason, reason)
        self.assertEqual(self.advertiser.verification_status, 'rejected')
        
        # Step 3: Resubmit verification
        new_documents = [{
            'document_type': 'business_license',
            'document_number': 'BL789012',
            'expiry_date': '2026-12-31',
            'file': self._create_test_file('new_license.pdf')
        }]
        
        resubmitted_verification = self.verification_service.resubmit_verification(
            self.advertiser, 
            new_documents
        )
        
        self.assertEqual(resubmitted_verification.status, 'pending')
        self.assertEqual(self.advertiser.verification_status, 'pending')
        
        # Check verification history
        history = self.verification_service.get_verification_history(
            self.advertiser
        )
        
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].status, 'pending')  # Resubmitted
        self.assertEqual(history[1].status, 'rejected')  # Original
    
    def test_multiple_document_types(self):
        """Test verification with multiple document types."""
        documents = [
            {
                'document_type': 'business_license',
                'document_number': 'BL123456',
                'expiry_date': '2025-12-31',
                'file': self._create_test_file('license.pdf')
            },
            {
                'document_type': 'tax_id',
                'document_number': 'TAX789012',
                'expiry_date': '2024-12-31',
                'file': self._create_test_file('tax.pdf')
            },
            {
                'document_type': 'proof_of_address',
                'document_number': 'POA345678',
                'expiry_date': '2025-06-30',
                'file': self._create_test_file('address.pdf')
            }
        ]
        
        verification = self.verification_service.submit_verification(
            self.advertiser, 
            documents
        )
        
        self.assertEqual(verification.documents.count(), 3)
        
        # Check document types
        document_types = verification.documents.values_list(
            'document_type', 
            flat=True
        )
        
        self.assertIn('business_license', document_types)
        self.assertIn('tax_id', document_types)
        self.assertIn('proof_of_address', document_types)
    
    def test_document_expiry_validation(self):
        """Test document expiry validation during verification."""
        # Submit with expired document
        documents = [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2020-12-31',  # Expired
            'file': self._create_test_file('license.pdf')
        }]
        
        verification = self.verification_service.submit_verification(
            self.advertiser, 
            documents
        )
        
        # Check for expiry warnings
        expiry_warnings = self.verification_service.check_document_expiry(
            verification
        )
        
        self.assertIn('business_license', expiry_warnings)
        self.assertIn('Document has expired', expiry_warnings['business_license'])
    
    def test_verification_document_validation(self):
        """Test document validation during verification."""
        documents = [
            {
                'document_type': 'business_license',
                'document_number': '',  # Missing document number
                'expiry_date': '2025-12-31',
                'file': self._create_test_file('license.pdf')
            },
            {
                'document_type': 'tax_id',
                'document_number': 'TAX789012',
                'expiry_date': 'invalid-date',  # Invalid date
                'file': self._create_test_file('tax.pdf')
            }
        ]
        
        validation_results = []
        for doc in documents:
            is_valid, errors = self.verification_service.validate_document(doc)
            validation_results.append((is_valid, errors))
        
        # First document should be invalid (missing document number)
        self.assertFalse(validation_results[0][0])
        self.assertIn('document_number', validation_results[0][1])
        
        # Second document should be invalid (invalid expiry date)
        self.assertFalse(validation_results[1][0])
        self.assertIn('expiry_date', validation_results[1][1])
    
    def test_verification_status_notifications(self):
        """Test verification status change notifications."""
        documents = [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': self._create_test_file('license.pdf')
        }]
        
        verification = self.verification_service.submit_verification(
            self.advertiser, 
            documents
        )
        
        with patch(
            'api.advertiser_portal.services.advertiser.AdvertiserVerificationService.send_notification'
        ) as mock_send_notification:
            
            # Approve verification
            self.verification_service.approve_verification(verification)
            
            # Check that notification was sent
            mock_send_notification.assert_called()
            
            # Get notification data from mock call
            call_args = mock_send_notification.call_args
            notification_data = call_args[0][1] if call_args else None
            
            if notification_data:
                self.assertEqual(notification_data['type'], 'verification_approved')
                self.assertIn('approved', notification_data['message'])
    
    def test_bulk_verification_processing(self):
        """Test bulk verification processing for admin."""
        # Create multiple advertisers with verifications
        advertisers = []
        verifications = []
        
        for i in range(5):
            user = User.objects.create_user(
                username=f'testuser{i}',
                email=f'test{i}@example.com',
                password='testpass123'
            )
            
            advertiser = self.advertiser_service.create_advertiser(
                user, 
                self.valid_advertiser_data
            )
            advertisers.append(advertiser)
            
            documents = [{
                'document_type': 'business_license',
                'document_number': f'BL12345{i}',
                'expiry_date': '2025-12-31',
                'file': self._create_test_file(f'license{i}.pdf')
            }]
            
            verification = self.verification_service.submit_verification(
                advertiser, 
                documents
            )
            verifications.append(verification)
        
        # Bulk approve all verifications
        approved_count = 0
        for verification in verifications:
            self.verification_service.approve_verification(verification)
            approved_count += 1
        
        self.assertEqual(approved_count, 5)
        
        # Check all advertisers are verified
        for advertiser in advertisers:
            advertiser.refresh_from_db()
            self.assertEqual(advertiser.verification_status, 'verified')
    
    def test_verification_document_types(self):
        """Test supported document types."""
        supported_types = self.verification_service.get_supported_document_types()
        
        expected_types = [
            'business_license',
            'tax_id',
            'proof_of_address',
            'bank_statement',
            'utility_bill',
            'certificate_of_incorporation',
            'passport',
            'driver_license'
        ]
        
        for doc_type in expected_types:
            self.assertIn(doc_type, supported_types)
    
    def test_verification_requirements_by_industry(self):
        """Test verification requirements by industry."""
        # Test technology industry requirements
        tech_requirements = self.verification_service.get_verification_requirements(
            'technology'
        )
        
        self.assertIn('business_license', tech_requirements['required'])
        self.assertIn('tax_id', tech_requirements['required'])
        
        # Test finance industry requirements (stricter)
        finance_requirements = self.verification_service.get_verification_requirements(
            'finance'
        )
        
        self.assertIn('business_license', finance_requirements['required'])
        self.assertIn('tax_id', finance_requirements['required'])
        self.assertIn('bank_statement', finance_requirements['required'])
    
    def test_verification_document_upload(self):
        """Test document upload functionality."""
        # Create test file
        test_file = self._create_test_file('test_document.pdf')
        
        # Test file validation
        is_valid, errors = self.verification_service.validate_file_upload(test_file)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Test invalid file type
        invalid_file = SimpleUploadedFile(
            'test.txt',
            b'This is a text file',
            content_type='text/plain'
        )
        
        is_valid, errors = self.verification_service.validate_file_upload(invalid_file)
        
        self.assertFalse(is_valid)
        self.assertIn('file_type', errors)
    
    def test_verification_expiring_documents(self):
        """Test handling of expiring documents."""
        # Create verification with document expiring soon
        documents = [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': (timezone.now() + timezone.timedelta(days=30)).strftime('%Y-%m-%d'),
            'file': self._create_test_file('license.pdf')
        }]
        
        verification = self.verification_service.submit_verification(
            self.advertiser, 
            documents
        )
        
        # Check for expiring documents
        expiring_documents = self.verification_service.get_expiring_documents(
            verification,
            days_threshold=60
        )
        
        self.assertEqual(len(expiring_documents), 1)
        self.assertEqual(expiring_documents[0]['document_type'], 'business_license')
        self.assertIn('expires_soon', expiring_documents[0])
    
    def test_verification_document_duplicates(self):
        """Test detection of duplicate documents."""
        # Submit first verification
        documents1 = [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': self._create_test_file('license.pdf')
        }]
        
        verification1 = self.verification_service.submit_verification(
            self.advertiser, 
            documents1
        )
        
        # Try to submit same document number again
        documents2 = [{
            'document_type': 'business_license',
            'document_number': 'BL123456',  # Same document number
            'expiry_date': '2025-12-31',
            'file': self._create_test_file('license2.pdf')
        }]
        
        with self.assertRaises(ValueError) as context:
            self.verification_service.submit_verification(
                self.advertiser, 
                documents2
            )
        
        self.assertIn('Document number already exists', str(context.exception))
    
    def test_verification_auto_approval(self):
        """Test automatic approval for trusted documents."""
        # Create verification with trusted document
        documents = [{
            'document_type': 'business_license',
            'document_number': 'TRUSTED123',
            'expiry_date': '2025-12-31',
            'file': self._create_test_file('trusted_license.pdf'),
            'is_trusted': True
        }]
        
        verification = self.verification_service.submit_verification(
            self.advertiser, 
            documents
        )
        
        # Check if auto-approved
        auto_approved = self.verification_service.check_auto_approval(
            verification
        )
        
        if auto_approved:
            self.assertEqual(verification.status, 'approved')
            self.assertEqual(self.advertiser.verification_status, 'verified')
    
    def test_verification_manual_review_required(self):
        """Test manual review requirement detection."""
        # Create verification with suspicious document
        documents = [{
            'document_type': 'business_license',
            'document_number': 'SUSPICIOUS123',
            'expiry_date': '2025-12-31',
            'file': self._create_test_file('suspicious_license.pdf'),
            'requires_manual_review': True
        }]
        
        verification = self.verification_service.submit_verification(
            self.advertiser, 
            documents
        )
        
        # Check if manual review is required
        requires_review = self.verification_service.check_manual_review_required(
            verification
        )
        
        self.assertTrue(requires_review)
        self.assertEqual(verification.status, 'pending')
    
    def test_verification_document_storage(self):
        """Test document storage and retrieval."""
        documents = [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': self._create_test_file('license.pdf')
        }]
        
        verification = self.verification_service.submit_verification(
            self.advertiser, 
            documents
        )
        
        # Test document retrieval
        document = verification.documents.first()
        retrieved_file = self.verification_service.get_document_file(document)
        
        self.assertIsNotNone(retrieved_file)
        self.assertEqual(retrieved_file.name, document.file.name)
    
    def test_verification_audit_trail(self):
        """Test verification audit trail."""
        documents = [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': self._create_test_file('license.pdf')
        }]
        
        verification = self.verification_service.submit_verification(
            self.advertiser, 
            documents
        )
        
        # Approve verification
        self.verification_service.approve_verification(verification)
        
        # Get audit trail
        audit_trail = self.verification_service.get_verification_audit_trail(
            verification
        )
        
        self.assertEqual(len(audit_trail), 2)  # Submitted + Approved
        
        # Check audit entries
        actions = [entry['action'] for entry in audit_trail]
        self.assertIn('submitted', actions)
        self.assertIn('approved', actions)
    
    def test_verification_statistics(self):
        """Test verification statistics reporting."""
        # Create multiple verifications with different statuses
        statuses = ['pending', 'approved', 'rejected', 'pending']
        
        for status in statuses:
            user = User.objects.create_user(
                username=f'user_{status}',
                email=f'{status}@example.com',
                password='testpass123'
            )
            
            advertiser = self.advertiser_service.create_advertiser(
                user, 
                self.valid_advertiser_data
            )
            
            documents = [{
                'document_type': 'business_license',
                'document_number': f'BL{status}123',
                'expiry_date': '2025-12-31',
                'file': self._create_test_file(f'{status}_license.pdf')
            }]
            
            verification = self.verification_service.submit_verification(
                advertiser, 
                documents
            )
            
            if status == 'approved':
                self.verification_service.approve_verification(verification)
            elif status == 'rejected':
                self.verification_service.reject_verification(
                    verification, 
                    'Test rejection'
                )
        
        # Get statistics
        stats = self.verification_service.get_verification_statistics()
        
        self.assertEqual(stats['total'], 4)
        self.assertEqual(stats['pending'], 2)
        self.assertEqual(stats['approved'], 1)
        self.assertEqual(stats['rejected'], 1)
        self.assertIn('approval_rate', stats)
    
    def _create_test_file(self, filename):
        """Create a test file for document upload."""
        return SimpleUploadedFile(
            filename,
            b'PDF file content for testing',
            content_type='application/pdf'
        )


class VerificationSecurityTestCase(TestCase):
    """Test cases for verification security features."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.verification_service = AdvertiserVerificationService()
        
        self.advertiser = self.advertiser_service.create_advertiser(
            self.user, 
            {
                'company_name': 'Test Company',
                'contact_email': 'contact@testcompany.com',
                'contact_phone': '+1234567890',
                'website': 'https://testcompany.com',
                'industry': 'technology',
                'company_size': 'medium',
            }
        )
    
    def test_document_forgery_detection(self):
        """Test document forgery detection."""
        # Create suspicious document
        documents = [{
            'document_type': 'business_license',
            'document_number': 'FORGED123',
            'expiry_date': '2025-12-31',
            'file': self._create_test_file('forged_license.pdf'),
            'metadata': {
                'suspicious_patterns': ['altered_text', 'watermark_removed']
            }
        }]
        
        verification = self.verification_service.submit_verification(
            self.advertiser, 
            documents
        )
        
        # Check for forgery detection
        forgery_check = self.verification_service.check_document_forgery(
            verification
        )
        
        self.assertTrue(forgery_check['is_suspicious'])
        self.assertIn('forgery_detected', forgery_check)
    
    def test_verification_rate_limiting(self):
        """Test verification submission rate limiting."""
        # Submit multiple verifications quickly
        documents = [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': self._create_test_file('license.pdf')
        }]
        
        # First submission should succeed
        verification1 = self.verification_service.submit_verification(
            self.advertiser, 
            documents
        )
        self.assertIsNotNone(verification1)
        
        # Second submission within rate limit should fail
        with self.assertRaises(ValueError) as context:
            self.verification_service.submit_verification(
                self.advertiser, 
                documents
            )
        
        self.assertIn('Rate limit exceeded', str(context.exception))
    
    def test_verification_access_control(self):
        """Test verification access control."""
        documents = [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': self._create_test_file('license.pdf')
        }]
        
        verification = self.verification_service.submit_verification(
            self.advertiser, 
            documents
        )
        
        # Test that only admin can approve
        regular_user = User.objects.create_user(
            username='regularuser',
            email='regular@example.com',
            password='regularpass123'
        )
        
        with self.assertRaises(ValueError) as context:
            self.verification_service.approve_verification(
                verification,
                user=regular_user
            )
        
        self.assertIn('Permission denied', str(context.exception))
    
    def test_verification_data_encryption(self):
        """Test verification data encryption."""
        documents = [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': self._create_test_file('license.pdf')
        }]
        
        verification = self.verification_service.submit_verification(
            self.advertiser, 
            documents
        )
        
        # Check that sensitive data is encrypted
        document = verification.documents.first()
        encrypted_data = self.verification_service.get_encrypted_data(
            document
        )
        
        self.assertIsNotNone(encrypted_data)
        self.assertNotEqual(encrypted_data, document.document_number)
    
    def test_verification_audit_logging(self):
        """Test verification audit logging."""
        documents = [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': self._create_test_file('license.pdf')
        }]
        
        verification = self.verification_service.submit_verification(
            self.advertiser, 
            documents
        )
        
        # Approve verification
        self.verification_service.approve_verification(verification)
        
        # Check audit log
        audit_logs = self.verification_service.get_audit_logs(
            verification
        )
        
        self.assertEqual(len(audit_logs), 2)
        
        # Check log entries contain required fields
        for log in audit_logs:
            self.assertIn('timestamp', log)
            self.assertIn('action', log)
            self.assertIn('user_id', log)
            self.assertIn('ip_address', log)
    
    def _create_test_file(self, filename):
        """Create a test file for document upload."""
        return SimpleUploadedFile(
            filename,
            b'PDF file content for testing',
            content_type='application/pdf'
        )
