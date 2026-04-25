"""
Test Offer Service

Comprehensive tests for offer service functionality
including CRUD operations, publishing, and moderation.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock

from ..models.offer import AdvertiserOffer, OfferRequirement
from ..models.advertiser import Advertiser, AdvertiserWallet
try:
    from ..services import OfferService
except ImportError:
    OfferService = None
try:
    from ..services import OfferModerationService
except ImportError:
    OfferModerationService = None
try:
    from ..services import AdvertiserService
except ImportError:
    AdvertiserService = None

User = get_user_model()


class OfferServiceTestCase(TestCase):
    """Test cases for OfferService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.offer_service = OfferService()
        
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
        
        self.valid_offer_data = {
            'name': 'Test Offer',
            'description': 'Test offer description',
            'offer_type': 'cpa',
            'payout_amount': 10.00,
            'currency': 'USD',
            'landing_page': 'https://example.com/offer',
            'target_countries': ['US', 'CA', 'UK'],
            'allowed_devices': ['desktop', 'mobile'],
            'tracking_method': 'postback',
            'cookie_duration': 30,
            'status': 'draft',
        }
    
    def test_create_offer_success(self):
        """Test successful offer creation."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        self.assertIsInstance(offer, AdvertiserOffer)
        self.assertEqual(offer.advertiser, self.advertiser)
        self.assertEqual(offer.name, 'Test Offer')
        self.assertEqual(offer.offer_type, 'cpa')
        self.assertEqual(offer.payout_amount, Decimal('10.00'))
        self.assertEqual(offer.status, 'draft')
    
    def test_create_offer_invalid_data(self):
        """Test offer creation with invalid data."""
        invalid_data = self.valid_offer_data.copy()
        invalid_data['name'] = ''  # Empty name
        
        with self.assertRaises(ValueError) as context:
            self.offer_service.create_offer(
                self.advertiser,
                invalid_data
            )
        
        self.assertIn('Offer name is required', str(context.exception))
    
    def test_create_offer_invalid_payout(self):
        """Test offer creation with invalid payout amount."""
        invalid_data = self.valid_offer_data.copy()
        invalid_data['payout_amount'] = -5.00  # Negative payout
        
        with self.assertRaises(ValueError) as context:
            self.offer_service.create_offer(
                self.advertiser,
                invalid_data
            )
        
        self.assertIn('Payout amount must be positive', str(context.exception))
    
    def test_update_offer_success(self):
        """Test successful offer update."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        update_data = {
            'name': 'Updated Offer',
            'payout_amount': 15.00,
            'description': 'Updated description',
        }
        
        updated_offer = self.offer_service.update_offer(
            offer,
            update_data
        )
        
        self.assertEqual(updated_offer.name, 'Updated Offer')
        self.assertEqual(updated_offer.payout_amount, Decimal('15.00'))
        self.assertEqual(updated_offer.description, 'Updated description')
        self.assertEqual(offer.offer_type, 'cpa')  # Unchanged
    
    def test_update_published_offer(self):
        """Test updating published offer."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        # Publish offer
        self.offer_service.publish_offer(offer)
        
        # Try to update critical fields
        update_data = {
            'payout_amount': 20.00,  # Critical field
        }
        
        with self.assertRaises(ValueError) as context:
            self.offer_service.update_offer(
                offer,
                update_data
            )
        
        self.assertIn('Cannot update payout amount on published offer', str(context.exception))
    
    def test_submit_offer_for_review_success(self):
        """Test successful offer submission for review."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        # Add requirements
        self.offer_service.add_requirement(
            offer,
            {
                'requirement_type': 'minimum_age',
                'value': '18',
                'description': 'Users must be 18 or older'
            }
        )
        
        submitted_offer = self.offer_service.submit_for_review(offer)
        
        self.assertEqual(submitted_offer.status, 'pending_review')
        self.assertIsNotNone(submitted_offer.submitted_at)
    
    def test_submit_offer_for_review_no_requirements(self):
        """Test offer submission without requirements."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        with self.assertRaises(ValueError) as context:
            self.offer_service.submit_for_review(offer)
        
        self.assertIn('At least one requirement is required', str(context.exception))
    
    def test_approve_offer_success(self):
        """Test successful offer approval."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        # Add requirements and submit
        self.offer_service.add_requirement(
            offer,
            {
                'requirement_type': 'minimum_age',
                'value': '18',
                'description': 'Users must be 18 or older'
            }
        )
        
        self.offer_service.submit_for_review(offer)
        
        # Approve offer
        approved_offer = self.offer_service.approve_offer(offer)
        
        self.assertEqual(approved_offer.status, 'approved')
        self.assertIsNotNone(approved_offer.approved_at)
    
    def test_reject_offer_success(self):
        """Test successful offer rejection."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        # Add requirements and submit
        self.offer_service.add_requirement(
            offer,
            {
                'requirement_type': 'minimum_age',
                'value': '18',
                'description': 'Users must be 18 or older'
            }
        )
        
        self.offer_service.submit_for_review(offer)
        
        # Reject offer
        reason = 'Landing page not working'
        rejected_offer = self.offer_service.reject_offer(offer, reason)
        
        self.assertEqual(rejected_offer.status, 'rejected')
        self.assertEqual(rejected_offer.rejection_reason, reason)
        self.assertIsNotNone(rejected_offer.rejected_at)
    
    def test_reject_offer_no_reason(self):
        """Test offer rejection without reason."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        # Add requirements and submit
        self.offer_service.add_requirement(
            offer,
            {
                'requirement_type': 'minimum_age',
                'value': '18',
                'description': 'Users must be 18 or older'
            }
        )
        
        self.offer_service.submit_for_review(offer)
        
        with self.assertRaises(ValueError) as context:
            self.offer_service.reject_offer(offer)
        
        self.assertIn('Rejection reason is required', str(context.exception))
    
    def test_publish_offer_success(self):
        """Test successful offer publishing."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        # Add requirements and approve
        self.offer_service.add_requirement(
            offer,
            {
                'requirement_type': 'minimum_age',
                'value': '18',
                'description': 'Users must be 18 or older'
            }
        )
        
        self.offer_service.submit_for_review(offer)
        self.offer_service.approve_offer(offer)
        
        # Publish offer
        published_offer = self.offer_service.publish_offer(offer)
        
        self.assertEqual(published_offer.status, 'active')
        self.assertTrue(published_offer.is_published)
        self.assertIsNotNone(published_offer.published_at)
    
    def test_publish_unapproved_offer(self):
        """Test publishing unapproved offer."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        with self.assertRaises(ValueError) as context:
            self.offer_service.publish_offer(offer)
        
        self.assertIn('Only approved offers can be published', str(context.exception))
    
    def test_pause_offer_success(self):
        """Test successful offer pausing."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        # Add requirements, approve, and publish
        self.offer_service.add_requirement(
            offer,
            {
                'requirement_type': 'minimum_age',
                'value': '18',
                'description': 'Users must be 18 or older'
            }
        )
        
        self.offer_service.submit_for_review(offer)
        self.offer_service.approve_offer(offer)
        self.offer_service.publish_offer(offer)
        
        # Pause offer
        paused_offer = self.offer_service.pause_offer(offer)
        
        self.assertEqual(paused_offer.status, 'paused')
        self.assertTrue(paused_offer.is_published)  # Still published but paused
    
    def test_resume_offer_success(self):
        """Test successful offer resumption."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        # Add requirements, approve, publish, and pause
        self.offer_service.add_requirement(
            offer,
            {
                'requirement_type': 'minimum_age',
                'value': '18',
                'description': 'Users must be 18 or older'
            }
        )
        
        self.offer_service.submit_for_review(offer)
        self.offer_service.approve_offer(offer)
        self.offer_service.publish_offer(offer)
        self.offer_service.pause_offer(offer)
        
        # Resume offer
        resumed_offer = self.offer_service.resume_offer(offer)
        
        self.assertEqual(resumed_offer.status, 'active')
    
    def test_delete_offer_success(self):
        """Test successful offer deletion."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        offer_id = offer.id
        
        self.offer_service.delete_offer(offer)
        
        with self.assertRaises(AdvertiserOffer.DoesNotExist):
            AdvertiserOffer.objects.get(id=offer_id)
    
    def test_delete_published_offer(self):
        """Test deleting published offer."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        # Add requirements, approve, and publish
        self.offer_service.add_requirement(
            offer,
            {
                'requirement_type': 'minimum_age',
                'value': '18',
                'description': 'Users must be 18 or older'
            }
        )
        
        self.offer_service.submit_for_review(offer)
        self.offer_service.approve_offer(offer)
        self.offer_service.publish_offer(offer)
        
        with self.assertRaises(ValueError) as context:
            self.offer_service.delete_offer(offer)
        
        self.assertIn('Cannot delete published offer', str(context.exception))
    
    def test_add_requirement_success(self):
        """Test successful requirement addition."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        requirement_data = {
            'requirement_type': 'minimum_age',
            'value': '18',
            'description': 'Users must be 18 or older'
        }
        
        requirement = self.offer_service.add_requirement(offer, requirement_data)
        
        self.assertIsInstance(requirement, OfferRequirement)
        self.assertEqual(requirement.offer, offer)
        self.assertEqual(requirement.requirement_type, 'minimum_age')
        self.assertEqual(requirement.value, '18')
    
    def test_add_requirement_invalid_type(self):
        """Test adding requirement with invalid type."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        requirement_data = {
            'requirement_type': 'invalid_type',
            'value': '18',
            'description': 'Invalid requirement'
        }
        
        with self.assertRaises(ValueError) as context:
            self.offer_service.add_requirement(offer, requirement_data)
        
        self.assertIn('Invalid requirement type', str(context.exception))
    
    def test_update_requirement_success(self):
        """Test successful requirement update."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        requirement = self.offer_service.add_requirement(
            offer,
            {
                'requirement_type': 'minimum_age',
                'value': '18',
                'description': 'Users must be 18 or older'
            }
        )
        
        update_data = {
            'value': '21',
            'description': 'Users must be 21 or older'
        }
        
        updated_requirement = self.offer_service.update_requirement(
            requirement,
            update_data
        )
        
        self.assertEqual(updated_requirement.value, '21')
        self.assertEqual(updated_requirement.description, 'Users must be 21 or older')
        self.assertEqual(updated_requirement.requirement_type, 'minimum_age')  # Unchanged
    
    def test_remove_requirement_success(self):
        """Test successful requirement removal."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        requirement = self.offer_service.add_requirement(
            offer,
            {
                'requirement_type': 'minimum_age',
                'value': '18',
                'description': 'Users must be 18 or older'
            }
        )
        
        requirement_id = requirement.id
        
        self.offer_service.remove_requirement(requirement)
        
        with self.assertRaises(OfferRequirement.DoesNotExist):
            OfferRequirement.objects.get(id=requirement_id)
    
    def test_get_offer_statistics(self):
        """Test getting offer statistics."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        # Add requirements and publish
        self.offer_service.add_requirement(
            offer,
            {
                'requirement_type': 'minimum_age',
                'value': '18',
                'description': 'Users must be 18 or older'
            }
        )
        
        self.offer_service.submit_for_review(offer)
        self.offer_service.approve_offer(offer)
        self.offer_service.publish_offer(offer)
        
        stats = self.offer_service.get_offer_statistics(offer)
        
        self.assertIn('total_clicks', stats)
        self.assertIn('total_conversions', stats)
        self.assertIn('total_payout', stats)
        self.assertIn('ctr', stats)
        self.assertIn('conversion_rate', stats)
        self.assertIn('epc', stats)
    
    def test_search_offers(self):
        """Test offer search functionality."""
        # Create multiple offers
        for i in range(5):
            data = self.valid_offer_data.copy()
            data['name'] = f'Offer {i}'
            self.offer_service.create_offer(self.advertiser, data)
        
        # Search by name
        results = self.offer_service.search_offers(
            self.advertiser,
            'Offer 1'
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, 'Offer 1')
    
    def test_get_active_offers(self):
        """Test getting active offers."""
        # Create offers
        offers = []
        for i in range(3):
            data = self.valid_offer_data.copy()
            data['name'] = f'Offer {i}'
            offer = self.offer_service.create_offer(self.advertiser, data)
            
            # Add requirements and approve/publish
            self.offer_service.add_requirement(
                offer,
                {
                    'requirement_type': 'minimum_age',
                    'value': '18',
                    'description': 'Users must be 18 or older'
                }
            )
            
            self.offer_service.submit_for_review(offer)
            self.offer_service.approve_offer(offer)
            
            if i < 2:
                self.offer_service.publish_offer(offer)
            
            offers.append(offer)
        
        active_offers = self.offer_service.get_active_offers(self.advertiser)
        
        self.assertEqual(len(active_offers), 2)
        
        for offer in active_offers:
            self.assertEqual(offer.status, 'active')
    
    def test_validate_offer_data_success(self):
        """Test successful offer data validation."""
        is_valid, errors = self.offer_service.validate_offer_data(
            self.valid_offer_data
        )
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_offer_data_invalid_url(self):
        """Test offer data validation with invalid URL."""
        invalid_data = self.valid_offer_data.copy()
        invalid_data['landing_page'] = 'invalid-url'
        
        is_valid, errors = self.offer_service.validate_offer_data(invalid_data)
        
        self.assertFalse(is_valid)
        self.assertIn('landing_page', errors)
    
    def test_validate_offer_data_invalid_countries(self):
        """Test offer data validation with invalid countries."""
        invalid_data = self.valid_offer_data.copy()
        invalid_data['target_countries'] = ['XX', 'YY']  # Invalid country codes
        
        is_valid, errors = self.offer_service.validate_offer_data(invalid_data)
        
        self.assertFalse(is_valid)
        self.assertIn('target_countries', errors)
    
    def test_clone_offer_success(self):
        """Test successful offer cloning."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        # Add requirements
        self.offer_service.add_requirement(
            offer,
            {
                'requirement_type': 'minimum_age',
                'value': '18',
                'description': 'Users must be 18 or older'
            }
        )
        
        # Clone offer
        cloned_offer = self.offer_service.clone_offer(offer)
        
        self.assertEqual(cloned_offer.name, 'Test Offer (Clone)')
        self.assertEqual(cloned_offer.status, 'draft')
        self.assertEqual(cloned_offer.payout_amount, offer.payout_amount)
        
        # Check that requirements were cloned
        self.assertEqual(cloned_offer.requirements.count(), offer.requirements.count())
    
    def test_get_offer_performance(self):
        """Test getting offer performance metrics."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        # Add requirements and publish
        self.offer_service.add_requirement(
            offer,
            {
                'requirement_type': 'minimum_age',
                'value': '18',
                'description': 'Users must be 18 or older'
            }
        )
        
        self.offer_service.submit_for_review(offer)
        self.offer_service.approve_offer(offer)
        self.offer_service.publish_offer(offer)
        
        # Get performance for last 7 days
        performance = self.offer_service.get_offer_performance(
            offer,
            days=7
        )
        
        self.assertIn('daily_breakdown', performance)
        self.assertIn('summary', performance)
        self.assertIn('trends', performance)
        self.assertIn('top_countries', performance)
        self.assertIn('top_devices', performance)
    
    def test_get_offers_by_status(self):
        """Test getting offers by status."""
        # Create offers with different statuses
        statuses = ['draft', 'pending_review', 'approved', 'active']
        
        for status in statuses:
            data = self.valid_offer_data.copy()
            data['name'] = f'Offer {status}'
            offer = self.offer_service.create_offer(self.advertiser, data)
            
            # Add requirements
            self.offer_service.add_requirement(
                offer,
                {
                    'requirement_type': 'minimum_age',
                    'value': '18',
                    'description': 'Users must be 18 or older'
                }
            )
            
            if status in ['pending_review', 'approved', 'active']:
                self.offer_service.submit_for_review(offer)
            
            if status in ['approved', 'active']:
                self.offer_service.approve_offer(offer)
            
            if status == 'active':
                self.offer_service.publish_offer(offer)
        
        # Get offers by status
        draft_offers = self.offer_service.get_offers_by_status(self.advertiser, 'draft')
        pending_offers = self.offer_service.get_offers_by_status(self.advertiser, 'pending_review')
        approved_offers = self.offer_service.get_offers_by_status(self.advertiser, 'approved')
        active_offers = self.offer_service.get_offers_by_status(self.advertiser, 'active')
        
        self.assertEqual(len(draft_offers), 1)
        self.assertEqual(len(pending_offers), 1)
        self.assertEqual(len(approved_offers), 1)
        self.assertEqual(len(active_offers), 1)
    
    def test_export_offer_data(self):
        """Test exporting offer data."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        # Add requirements
        self.offer_service.add_requirement(
            offer,
            {
                'requirement_type': 'minimum_age',
                'value': '18',
                'description': 'Users must be 18 or older'
            }
        )
        
        # Add more requirements
        self.offer_service.add_requirement(
            offer,
            {
                'requirement_type': 'geo_targeting',
                'value': 'US,CA,UK',
                'description': 'Target specific countries'
            }
        )
        
        export_data = self.offer_service.export_offer_data(offer)
        
        self.assertIn('offer', export_data)
        self.assertIn('requirements', export_data)
        self.assertIn('statistics', export_data)
        self.assertIn('performance', export_data)
        
        # Check requirements count
        self.assertEqual(len(export_data['requirements']), 2)
    
    def test_get_supported_requirement_types(self):
        """Test getting supported requirement types."""
        requirement_types = self.offer_service.get_supported_requirement_types()
        
        expected_types = [
            'minimum_age',
            'maximum_age',
            'geo_targeting',
            'device_targeting',
            'traffic_source',
            'custom_parameter',
            'conversion_delay',
            'pixel_placement'
        ]
        
        for req_type in expected_types:
            self.assertIn(req_type, requirement_types)
    
    def test_validate_requirement_data_success(self):
        """Test successful requirement data validation."""
        requirement_data = {
            'requirement_type': 'minimum_age',
            'value': '18',
            'description': 'Users must be 18 or older'
        }
        
        is_valid, errors = self.offer_service.validate_requirement_data(requirement_data)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_requirement_data_invalid_age(self):
        """Test requirement data validation with invalid age."""
        requirement_data = {
            'requirement_type': 'minimum_age',
            'value': 'invalid_age',  # Should be numeric
            'description': 'Users must be 18 or older'
        }
        
        is_valid, errors = self.offer_service.validate_requirement_data(requirement_data)
        
        self.assertFalse(is_valid)
        self.assertIn('value', errors)
    
    def test_validate_requirement_data_missing_description(self):
        """Test requirement data validation with missing description."""
        requirement_data = {
            'requirement_type': 'minimum_age',
            'value': '18',
            # Missing description
        }
        
        is_valid, errors = self.offer_service.validate_requirement_data(requirement_data)
        
        self.assertFalse(is_valid)
        self.assertIn('description', errors)
    
    @patch('api.advertiser_portal.services.offer.OfferService.send_notification')
    def test_send_offer_status_notification(self, mock_send_notification):
        """Test sending offer status notification."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        # Add requirements and submit
        self.offer_service.add_requirement(
            offer,
            {
                'requirement_type': 'minimum_age',
                'value': '18',
                'description': 'Users must be 18 or older'
            }
        )
        
        self.offer_service.submit_for_review(offer)
        
        # Approve offer
        self.offer_service.approve_offer(offer)
        
        # Check that notification was sent
        mock_send_notification.assert_called()
        
        # Get notification data from mock call
        call_args = mock_send_notification.call_args
        notification_data = call_args[0][1] if call_args else None
        
        if notification_data:
            self.assertEqual(notification_data['type'], 'offer_approved')
            self.assertIn('approved', notification_data['message'])
    
    def test_bulk_update_offers(self):
        """Test bulk update of offers."""
        # Create multiple offers
        offers = []
        for i in range(3):
            data = self.valid_offer_data.copy()
            data['name'] = f'Offer {i}'
            offer = self.offer_service.create_offer(self.advertiser, data)
            offers.append(offer)
        
        # Bulk update
        update_data = {
            'description': 'Bulk updated description'
        }
        
        updated_offers = self.offer_service.bulk_update_offers(
            offers,
            update_data
        )
        
        self.assertEqual(len(updated_offers), 3)
        
        for offer in updated_offers:
            self.assertEqual(offer.description, 'Bulk updated description')
    
    def test_bulk_pause_offers(self):
        """Test bulk pause of offers."""
        # Create and publish offers
        offers = []
        for i in range(3):
            data = self.valid_offer_data.copy()
            data['name'] = f'Offer {i}'
            offer = self.offer_service.create_offer(self.advertiser, data)
            
            # Add requirements and approve/publish
            self.offer_service.add_requirement(
                offer,
                {
                    'requirement_type': 'minimum_age',
                    'value': '18',
                    'description': 'Users must be 18 or older'
                }
            )
            
            self.offer_service.submit_for_review(offer)
            self.offer_service.approve_offer(offer)
            self.offer_service.publish_offer(offer)
            
            offers.append(offer)
        
        # Bulk pause
        paused_offers = self.offer_service.bulk_pause_offers(offers)
        
        self.assertEqual(len(paused_offers), 3)
        
        for offer in paused_offers:
            self.assertEqual(offer.status, 'paused')
    
    def test_get_offer_recommendations(self):
        """Test getting offer recommendations."""
        offer = self.offer_service.create_offer(
            self.advertiser,
            self.valid_offer_data
        )
        
        # Add requirements and publish
        self.offer_service.add_requirement(
            offer,
            {
                'requirement_type': 'minimum_age',
                'value': '18',
                'description': 'Users must be 18 or older'
            }
        )
        
        self.offer_service.submit_for_review(offer)
        self.offer_service.approve_offer(offer)
        self.offer_service.publish_offer(offer)
        
        recommendations = self.offer_service.get_offer_recommendations(offer)
        
        self.assertIn('payout_adjustments', recommendations)
        self.assertIn('targeting_suggestions', recommendations)
        self.assertIn('requirement_optimizations', recommendations)
        self.assertIn('performance_improvements', recommendations)
