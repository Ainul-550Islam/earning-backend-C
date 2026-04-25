"""
Test Advertiser Service

Comprehensive tests for advertiser service functionality
including CRUD operations, verification, and account management.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock

from ..models.advertiser import Advertiser, AdvertiserProfile, AdvertiserVerification
try:
    from ..services import AdvertiserService
except ImportError:
    AdvertiserService = None
try:
    from ..services import AdvertiserVerificationService
except ImportError:
    AdvertiserVerificationService = None

User = get_user_model()


class AdvertiserServiceTestCase(TestCase):
    """Test cases for AdvertiserService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.service = AdvertiserService()
        self.valid_advertiser_data = {
            'company_name': 'Test Company',
            'contact_email': 'contact@testcompany.com',
            'contact_phone': '+1234567890',
            'website': 'https://testcompany.com',
            'industry': 'technology',
            'company_size': 'medium',
        }
    
    def test_create_advertiser_success(self):
        """Test successful advertiser creation."""
        advertiser = self.service.create_advertiser(self.user, self.valid_advertiser_data)
        
        self.assertIsInstance(advertiser, Advertiser)
        self.assertEqual(advertiser.user, self.user)
        self.assertEqual(advertiser.company_name, 'Test Company')
        self.assertEqual(advertiser.contact_email, 'contact@testcompany.com')
        self.assertEqual(advertiser.status, 'pending')
        self.assertEqual(advertiser.verification_status, 'pending')
        
        # Check that profile was created
        self.assertTrue(hasattr(advertiser, 'profile'))
        self.assertIsInstance(advertiser.profile, AdvertiserProfile)
        
        # Check that wallet was created
        self.assertTrue(hasattr(advertiser, 'wallet'))
    
    def test_create_advertiser_invalid_data(self):
        """Test advertiser creation with invalid data."""
        invalid_data = self.valid_advertiser_data.copy()
        invalid_data['company_name'] = ''  # Empty company name
        
        with self.assertRaises(ValueError) as context:
            self.service.create_advertiser(self.user, invalid_data)
        
        self.assertIn('Company name is required', str(context.exception))
    
    def test_create_advertiser_duplicate_user(self):
        """Test advertiser creation with duplicate user."""
        # Create first advertiser
        self.service.create_advertiser(self.user, self.valid_advertiser_data)
        
        # Try to create second advertiser with same user
        with self.assertRaises(ValueError) as context:
            self.service.create_advertiser(self.user, self.valid_advertiser_data)
        
        self.assertIn('User already has an advertiser account', str(context.exception))
    
    def test_update_advertiser_success(self):
        """Test successful advertiser update."""
        advertiser = self.service.create_advertiser(self.user, self.valid_advertiser_data)
        
        update_data = {
            'company_name': 'Updated Company',
            'contact_phone': '+0987654321',
        }
        
        updated_advertiser = self.service.update_advertiser(advertiser, update_data)
        
        self.assertEqual(updated_advertiser.company_name, 'Updated Company')
        self.assertEqual(updated_advertiser.contact_phone, '+0987654321')
        self.assertEqual(updated_advertiser.contact_email, 'contact@testcompany.com')  # Unchanged
    
    def test_update_advertiser_invalid_data(self):
        """Test advertiser update with invalid data."""
        advertiser = self.service.create_advertiser(self.user, self.valid_advertiser_data)
        
        update_data = {
            'company_name': '',  # Empty company name
        }
        
        with self.assertRaises(ValueError) as context:
            self.service.update_advertiser(advertiser, update_data)
        
        self.assertIn('Company name is required', str(context.exception))
    
    def test_get_advertiser_by_user_success(self):
        """Test getting advertiser by user."""
        advertiser = self.service.create_advertiser(self.user, self.valid_advertiser_data)
        
        retrieved_advertiser = self.service.get_advertiser_by_user(self.user)
        
        self.assertEqual(retrieved_advertiser.id, advertiser.id)
        self.assertEqual(retrieved_advertiser.company_name, 'Test Company')
    
    def test_get_advertiser_by_user_not_found(self):
        """Test getting advertiser by user when not found."""
        new_user = User.objects.create_user(
            username='newuser',
            email='new@example.com',
            password='newpass123'
        )
        
        with self.assertRaises(ValueError) as context:
            self.service.get_advertiser_by_user(new_user)
        
        self.assertIn('Advertiser not found', str(context.exception))
    
    def test_suspend_advertiser_success(self):
        """Test successful advertiser suspension."""
        advertiser = self.service.create_advertiser(self.user, self.valid_advertiser_data)
        
        reason = 'Violation of terms'
        suspended_advertiser = self.service.suspend_advertiser(advertiser, reason)
        
        self.assertEqual(suspended_advertiser.status, 'suspended')
        self.assertEqual(suspended_advertiser.suspended_at, suspended_advertiser.updated_at)
    
    def test_suspend_already_suspended_advertiser(self):
        """Test suspending already suspended advertiser."""
        advertiser = self.service.create_advertiser(self.user, self.valid_advertiser_data)
        self.service.suspend_advertiser(advertiser, 'First suspension')
        
        with self.assertRaises(ValueError) as context:
            self.service.suspend_advertiser(advertiser, 'Second suspension')
        
        self.assertIn('Advertiser is already suspended', str(context.exception))
    
    def test_reactivate_advertiser_success(self):
        """Test successful advertiser reactivation."""
        advertiser = self.service.create_advertiser(self.user, self.valid_advertiser_data)
        self.service.suspend_advertiser(advertiser, 'Test suspension')
        
        reactivated_advertiser = self.service.reactivate_advertiser(advertiser)
        
        self.assertEqual(reactivated_advertiser.status, 'active')
        self.assertEqual(reactivated_advertiser.suspended_at, None)
    
    def test_reactive_active_advertiser(self):
        """Test reactivating already active advertiser."""
        advertiser = self.service.create_advertiser(self.user, self.valid_advertiser_data)
        
        with self.assertRaises(ValueError) as context:
            self.service.reactivate_advertiser(advertiser)
        
        self.assertIn('Advertiser is not suspended', str(context.exception))
    
    def test_delete_advertiser_success(self):
        """Test successful advertiser deletion."""
        advertiser = self.service.create_advertiser(self.user, self.valid_advertiser_data)
        advertiser_id = advertiser.id
        
        self.service.delete_advertiser(advertiser)
        
        with self.assertRaises(Advertiser.DoesNotExist):
            Advertiser.objects.get(id=advertiser_id)
    
    def test_delete_verified_advertiser(self):
        """Test deleting verified advertiser."""
        advertiser = self.service.create_advertiser(self.user, self.valid_advertiser_data)
        advertiser.verification_status = 'verified'
        advertiser.save()
        
        with self.assertRaises(ValueError) as context:
            self.service.delete_advertiser(advertiser)
        
        self.assertIn('Cannot delete verified advertiser', str(context.exception))
    
    def test_get_advertiser_statistics(self):
        """Test getting advertiser statistics."""
        advertiser = self.service.create_advertiser(self.user, self.valid_advertiser_data)
        
        stats = self.service.get_advertiser_statistics(advertiser)
        
        self.assertIn('total_campaigns', stats)
        self.assertIn('active_campaigns', stats)
        self.assertIn('total_offers', stats)
        self.assertIn('active_offers', stats)
        self.assertIn('total_spend', stats)
        self.assertIn('total_conversions', stats)
    
    @patch('api.advertiser_portal.services.advertiser.AdvertiserService.send_notification')
    def test_send_welcome_notification(self, mock_send_notification):
        """Test sending welcome notification."""
        advertiser = self.service.create_advertiser(self.user, self.valid_advertiser_data)
        
        self.service.send_welcome_notification(advertiser)
        
        mock_send_notification.assert_called_once()
    
    def test_validate_advertiser_data_success(self):
        """Test successful advertiser data validation."""
        is_valid, errors = self.service.validate_advertiser_data(self.valid_advertiser_data)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_advertiser_data_missing_required_fields(self):
        """Test advertiser data validation with missing required fields."""
        invalid_data = self.valid_advertiser_data.copy()
        del invalid_data['company_name']
        
        is_valid, errors = self.service.validate_advertiser_data(invalid_data)
        
        self.assertFalse(is_valid)
        self.assertIn('company_name', errors)
    
    def test_validate_advertiser_data_invalid_email(self):
        """Test advertiser data validation with invalid email."""
        invalid_data = self.valid_advertiser_data.copy()
        invalid_data['contact_email'] = 'invalid-email'
        
        is_valid, errors = self.service.validate_advertiser_data(invalid_data)
        
        self.assertFalse(is_valid)
        self.assertIn('contact_email', errors)
    
    def test_validate_advertiser_data_invalid_phone(self):
        """Test advertiser data validation with invalid phone."""
        invalid_data = self.valid_advertiser_data.copy()
        invalid_data['contact_phone'] = 'invalid-phone'
        
        is_valid, errors = self.service.validate_advertiser_data(invalid_data)
        
        self.assertFalse(is_valid)
        self.assertIn('contact_phone', errors)
    
    def test_search_advertisers(self):
        """Test advertiser search functionality."""
        # Create multiple advertisers
        for i in range(5):
            user = User.objects.create_user(
                username=f'testuser{i}',
                email=f'test{i}@example.com',
                password='testpass123'
            )
            data = self.valid_advertiser_data.copy()
            data['company_name'] = f'Company {i}'
            self.service.create_advertiser(user, data)
        
        # Search by company name
        results = self.service.search_advertisers('Company 1')
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].company_name, 'Company 1')
        
        # Search by email
        results = self.service.search_advertisers('test2@example.com')
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].contact_email, 'test2@example.com')
    
    def test_get_advertiser_performance_metrics(self):
        """Test getting advertiser performance metrics."""
        advertiser = self.service.create_advertiser(self.user, self.valid_advertiser_data)
        
        metrics = self.service.get_advertiser_performance_metrics(
            advertiser,
            start_date=timezone.now() - timezone.timedelta(days=30),
            end_date=timezone.now()
        )
        
        self.assertIn('total_impressions', metrics)
        self.assertIn('total_clicks', metrics)
        self.assertIn('total_conversions', metrics)
        self.assertIn('total_spend', metrics)
        self.assertIn('ctr', metrics)
        self.assertIn('cpc', metrics)
        self.assertIn('cpa', metrics)
    
    @patch('api.advertiser_portal.services.advertiser.AdvertiserService.check_compliance')
    def test_check_advertiser_compliance(self, mock_check_compliance):
        """Test advertiser compliance checking."""
        mock_check_compliance.return_value = {
            'compliant': True,
            'issues': []
        }
        
        advertiser = self.service.create_advertiser(self.user, self.valid_advertiser_data)
        
        compliance_result = self.service.check_advertiser_compliance(advertiser)
        
        mock_check_compliance.assert_called_once_with(advertiser)
        self.assertTrue(compliance_result['compliant'])
    
    def test_export_advertiser_data(self):
        """Test exporting advertiser data."""
        advertiser = self.service.create_advertiser(self.user, self.valid_advertiser_data)
        
        export_data = self.service.export_advertiser_data(advertiser)
        
        self.assertIn('advertiser', export_data)
        self.assertIn('profile', export_data)
        self.assertIn('wallet', export_data)
        self.assertIn('campaigns', export_data)
        self.assertIn('offers', export_data)
        self.assertEqual(export_data['advertiser']['company_name'], 'Test Company')


class AdvertiserVerificationServiceTestCase(TestCase):
    """Test cases for AdvertiserVerificationService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium',
        )
        
        self.service = AdvertiserVerificationService()
    
    def test_submit_verification_success(self):
        """Test successful verification submission."""
        documents = [
            {
                'document_type': 'business_license',
                'document_number': 'BL123456',
                'expiry_date': '2025-12-31',
                'file': Mock(name='document_file')
            }
        ]
        
        verification = self.service.submit_verification(self.advertiser, documents)
        
        self.assertIsInstance(verification, AdvertiserVerification)
        self.assertEqual(verification.advertiser, self.advertiser)
        self.assertEqual(verification.status, 'pending')
        self.assertEqual(verification.documents.count(), 1)
    
    def test_submit_verification_no_documents(self):
        """Test verification submission with no documents."""
        with self.assertRaises(ValueError) as context:
            self.service.submit_verification(self.advertiser, [])
        
        self.assertIn('At least one document is required', str(context.exception))
    
    def test_approve_verification_success(self):
        """Test successful verification approval."""
        verification = self.service.submit_verification(self.advertiser, [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': Mock(name='document_file')
        }])
        
        approved_verification = self.service.approve_verification(verification)
        
        self.assertEqual(approved_verification.status, 'approved')
        self.assertIsNotNone(approved_verification.approved_at)
        self.assertEqual(self.advertiser.verification_status, 'verified')
        self.assertIsNotNone(self.advertiser.verified_at)
    
    def test_approve_already_approved_verification(self):
        """Test approving already approved verification."""
        verification = self.service.submit_verification(self.advertiser, [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': Mock(name='document_file')
        }])
        
        self.service.approve_verification(verification)
        
        with self.assertRaises(ValueError) as context:
            self.service.approve_verification(verification)
        
        self.assertIn('Verification is already approved', str(context.exception))
    
    def test_reject_verification_success(self):
        """Test successful verification rejection."""
        verification = self.service.submit_verification(self.advertiser, [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': Mock(name='document_file')
        }])
        
        reason = 'Invalid document'
        rejected_verification = self.service.reject_verification(verification, reason)
        
        self.assertEqual(rejected_verification.status, 'rejected')
        self.assertEqual(rejected_verification.rejection_reason, reason)
        self.assertIsNotNone(rejected_verification.rejected_at)
    
    def test_reject_verification_no_reason(self):
        """Test verification rejection without reason."""
        verification = self.service.submit_verification(self.advertiser, [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': Mock(name='document_file')
        }])
        
        with self.assertRaises(ValueError) as context:
            self.service.reject_verification(verification)
        
        self.assertIn('Rejection reason is required', str(context.exception))
    
    def test_get_pending_verifications(self):
        """Test getting pending verifications."""
        # Create multiple verifications
        for i in range(3):
            user = User.objects.create_user(
                username=f'testuser{i}',
                email=f'test{i}@example.com',
                password='testpass123'
            )
            
            advertiser = Advertiser.objects.create(
                user=user,
                company_name=f'Company {i}',
                contact_email=f'contact{i}@company{i}.com',
                contact_phone='+1234567890',
                website=f'https://company{i}.com',
                industry='technology',
                company_size='medium',
            )
            
            self.service.submit_verification(advertiser, [{
                'document_type': 'business_license',
                'document_number': f'BL12345{i}',
                'expiry_date': '2025-12-31',
                'file': Mock(name=f'document_file_{i}')
            }])
        
        pending_verifications = self.service.get_pending_verifications()
        
        self.assertEqual(len(pending_verifications), 3)
        for verification in pending_verifications:
            self.assertEqual(verification.status, 'pending')
    
    def test_validate_document_success(self):
        """Test successful document validation."""
        document = {
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': Mock(name='document_file')
        }
        
        is_valid, errors = self.service.validate_document(document)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_document_missing_fields(self):
        """Test document validation with missing fields."""
        document = {
            'document_type': 'business_license',
            # Missing document_number, expiry_date, file
        }
        
        is_valid, errors = self.service.validate_document(document)
        
        self.assertFalse(is_valid)
        self.assertIn('document_number', errors)
        self.assertIn('expiry_date', errors)
        self.assertIn('file', errors)
    
    def test_validate_document_invalid_expiry_date(self):
        """Test document validation with invalid expiry date."""
        document = {
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2020-12-31',  # Past date
            'file': Mock(name='document_file')
        }
        
        is_valid, errors = self.service.validate_document(document)
        
        self.assertFalse(is_valid)
        self.assertIn('expiry_date', errors)
    
    @patch('api.advertiser_portal.services.advertiser.AdvertiserVerificationService.send_notification')
    def test_send_verification_status_notification(self, mock_send_notification):
        """Test sending verification status notification."""
        verification = self.service.submit_verification(self.advertiser, [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': Mock(name='document_file')
        }])
        
        self.service.send_verification_status_notification(verification, 'approved')
        
        mock_send_notification.assert_called_once()
    
    def test_get_verification_history(self):
        """Test getting verification history."""
        # Create verification
        verification = self.service.submit_verification(self.advertiser, [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': Mock(name='document_file')
        }])
        
        history = self.service.get_verification_history(self.advertiser)
        
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].id, verification.id)
    
    def test_resubmit_verification_success(self):
        """Test successful verification resubmission."""
        verification = self.service.submit_verification(self.advertiser, [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': Mock(name='document_file')
        }])
        
        # Reject verification first
        self.service.reject_verification(verification, 'Invalid document')
        
        # Resubmit with new documents
        new_documents = [{
            'document_type': 'business_license',
            'document_number': 'BL789012',
            'expiry_date': '2026-12-31',
            'file': Mock(name='new_document_file')
        }]
        
        resubmitted_verification = self.service.resubmit_verification(self.advertiser, new_documents)
        
        self.assertEqual(resubmitted_verification.status, 'pending')
        self.assertEqual(resubmitted_verification.documents.count(), 1)
    
    def test_resubmit_verification_not_rejected(self):
        """Test resubmitting verification that's not rejected."""
        verification = self.service.submit_verification(self.advertiser, [{
            'document_type': 'business_license',
            'document_number': 'BL123456',
            'expiry_date': '2025-12-31',
            'file': Mock(name='document_file')
        }])
        
        new_documents = [{
            'document_type': 'business_license',
            'document_number': 'BL789012',
            'expiry_date': '2026-12-31',
            'file': Mock(name='new_document_file')
        }]
        
        with self.assertRaises(ValueError) as context:
            self.service.resubmit_verification(self.advertiser, new_documents)
        
        self.assertIn('Only rejected verifications can be resubmitted', str(context.exception))
