"""
api/ad_networks/test_crawlers.py
Test script for ad network crawlers
"""

import logging
from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from unittest.mock import Mock, patch

from .models import AdNetwork, OfferCategory, Offer
from .crawlers import get_crawler, CRAWLER_REGISTRY, OfferCrawler, AdMobCrawler, TapjoyCrawler

logger = logging.getLogger(__name__)


class CrawlerTest(TestCase):
    """Test crawler functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant_id = 'test_tenant'
        
        # Create test ad network
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test AdMob Network',
            network_type='admob',
            category='offerwall',
            api_key='test_api_key',
            publisher_id='test_publisher_id',
            base_url='https://test.admob.com',
            is_active=True
        )
        
        # Create test category
        self.category = OfferCategory.objects.create(
            name='Test Category',
            slug='test-category',
            category_type='offer'
        )
    
    def test_crawler_registry(self):
        """Test crawler registry functionality"""
        logger.info("Testing crawler registry...")
        
        # Test registry has expected crawlers
        self.assertIn('admob', CRAWLER_REGISTRY)
        self.assertIn('tapjoy', CRAWLER_REGISTRY)
        
        # Test get_crawler function
        crawler = get_crawler('admob', self.ad_network)
        self.assertIsInstance(crawler, AdMobCrawler)
        self.assertEqual(crawler.ad_network, self.ad_network)
        
        # Test unknown crawler returns None
        unknown_crawler = get_crawler('unknown', self.ad_network)
        self.assertIsNone(unknown_crawler)
        
        logger.info("Crawler registry test: PASSED")
    
    def test_offer_crawler_base_class(self):
        """Test OfferCrawler base class functionality"""
        logger.info("Testing OfferCrawler base class...")
        
        crawler = OfferCrawler(self.ad_network)
        
        # Test initialization
        self.assertEqual(crawler.ad_network, self.ad_network)
        self.assertEqual(crawler.tenant_id, self.tenant_id)
        self.assertIsNotNone(crawler.session)
        
        # Test validate_offer_data
        valid_data = {
            'external_id': 'test_123',
            'title': 'Test Offer',
            'reward_amount': '5.00',
            'click_url': 'https://example.com'
        }
        
        errors = crawler.validate_offer_data(valid_data)
        self.assertEqual(len(errors), 0)
        
        # Test invalid data
        invalid_data = {
            'external_id': '',  # Missing
            'title': 'Test Offer',
            'reward_amount': '-5.00',  # Negative
            'click_url': 'invalid_url'  # Invalid URL
        }
        
        errors = crawler.validate_offer_data(invalid_data)
        self.assertGreater(len(errors), 0)
        
        logger.info("OfferCrawler base class test: PASSED")
    
    def test_admob_crawler_initialization(self):
        """Test AdMobCrawler initialization"""
        logger.info("Testing AdMobCrawler initialization...")
        
        crawler = AdMobCrawler(self.ad_network)
        
        self.assertEqual(crawler.base_url, "https://developers.google.com/admob/api/v3")
        self.assertEqual(crawler.api_version, "v3")
        self.assertEqual(crawler.tenant_id, self.tenant_id)
        
        logger.info("AdMobCrawler initialization test: PASSED")
    
    def test_admob_crawler_offer_creation(self):
        """Test AdMobCrawler offer creation logic"""
        logger.info("Testing AdMobCrawler offer creation...")
        
        crawler = AdMobCrawler(self.ad_network)
        
        # Mock ad unit data
        ad_unit = {
            'name': 'accounts/pub-123/adUnits/456',
            'displayName': 'Test Game',
            'adFormat': 'rewarded'
        }
        
        offer_data = crawler._create_offer_from_ad_unit(ad_unit)
        
        self.assertIsNotNone(offer_data)
        self.assertEqual(offer_data['external_id'], 'admob_456')
        self.assertIn('Test Game', offer_data['title'])
        self.assertEqual(offer_data['reward_amount'], Decimal('2.00'))  # Rewarded ad amount
        self.assertEqual(offer_data['tenant_id'], self.tenant_id)
        
        logger.info("AdMobCrawler offer creation test: PASSED")
    
    def test_tapjoy_crawler_initialization(self):
        """Test TapjoyCrawler initialization"""
        logger.info("Testing TapjoyCrawler initialization...")
        
        # Create Tapjoy network with secret
        tapjoy_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Tapjoy Network',
            network_type='tapjoy',
            category='offerwall',
            api_key='test_api_key',
            api_secret='test_secret',
            is_active=True
        )
        
        crawler = TapjoyCrawler(tapjoy_network)
        
        self.assertEqual(crawler.base_url, "https://api.tapjoy.com/v4")
        self.assertEqual(crawler.api_key, 'test_api_key')
        self.assertEqual(crawler.api_secret, 'test_secret')
        self.assertEqual(crawler.tenant_id, self.tenant_id)
        
        logger.info("TapjoyCrawler initialization test: PASSED")
    
    def test_tapjoy_crawler_signature_generation(self):
        """Test TapjoyCrawler signature generation"""
        logger.info("Testing TapjoyCrawler signature generation...")
        
        tapjoy_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Tapjoy Network',
            network_type='tapjoy',
            api_key='test_key',
            api_secret='test_secret',
            is_active=True
        )
        
        crawler = TapjoyCrawler(tapjoy_network)
        
        params = {
            'api_key': 'test_key',
            'timestamp': 1234567890,
            'format': 'json'
        }
        
        signature = crawler._generate_signature(params)
        self.assertIsNotNone(signature)
        self.assertEqual(len(signature), 40)  # SHA1 hex length
        
        logger.info("TapjoyCrawler signature generation test: PASSED")
    
    def test_tapjoy_crawler_offer_processing(self):
        """Test TapjoyCrawler offer processing"""
        logger.info("Testing TapjoyCrawler offer processing...")
        
        tapjoy_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Tapjoy Network',
            network_type='tapjoy',
            api_key='test_key',
            api_secret='test_secret',
            is_active=True
        )
        
        crawler = TapjoyCrawler(tapjoy_network)
        
        # Mock Tapjoy offer data
        tapjoy_offer = {
            'id': 'tapjoy_123',
            'name': 'Test Game Install',
            'description': 'Install and play this game',
            'payout': {
                'amount': '0.50',
                'currency': 'USD'
            },
            'click_url': 'https://example.com/click',
            'is_active': True,
            'platforms': ['android', 'ios'],
            'countries': ['US', 'GB'],
            'estimated_time': 15,
            'type': 'app_install'
        }
        
        processed_offer = crawler._process_tapjoy_offer(tapjoy_offer)
        
        self.assertIsNotNone(processed_offer)
        self.assertEqual(processed_offer['external_id'], 'tapjoy_tapjoy_123')
        self.assertEqual(processed_offer['title'], 'Test Game Install')
        self.assertEqual(processed_offer['reward_amount'], Decimal('52.50'))  # 0.50 USD * 105 BDT
        self.assertEqual(processed_offer['reward_currency'], 'BDT')
        self.assertEqual(processed_offer['difficulty'], 'easy')
        self.assertEqual(processed_offer['tenant_id'], self.tenant_id)
        
        logger.info("TapjoyCrawler offer processing test: PASSED")
    
    def test_crawler_save_offer(self):
        """Test crawler save_offer functionality"""
        logger.info("Testing crawler save_offer...")
        
        crawler = OfferCrawler(self.ad_network)
        
        # Test creating new offer
        offer_data = {
            'external_id': 'test_new_123',
            'title': 'New Test Offer',
            'description': 'Test description',
            'reward_amount': Decimal('5.00'),
            'click_url': 'https://example.com',
            'status': 'active'
        }
        
        saved_offer = crawler.save_offer(offer_data)
        self.assertIsNotNone(saved_offer)
        self.assertEqual(saved_offer.external_id, 'test_new_123')
        self.assertEqual(saved_offer.title, 'New Test Offer')
        self.assertEqual(saved_offer.tenant_id, self.tenant_id)
        
        # Test updating existing offer
        updated_data = offer_data.copy()
        updated_data['title'] = 'Updated Test Offer'
        updated_data['reward_amount'] = Decimal('7.00')
        
        updated_offer = crawler.save_offer(updated_data)
        self.assertIsNotNone(updated_offer)
        self.assertEqual(updated_offer.id, saved_offer.id)  # Same record
        self.assertEqual(updated_offer.title, 'Updated Test Offer')
        self.assertEqual(updated_offer.reward_amount, Decimal('7.00'))
        
        logger.info("Crawler save_offer test: PASSED")
    
    def test_crawler_data_cleaning(self):
        """Test crawler data cleaning functionality"""
        logger.info("Testing crawler data cleaning...")
        
        crawler = OfferCrawler(self.ad_network)
        
        # Test cleaning messy data
        messy_data = {
            'title': '  Messy Title  ',
            'description': '  Long description that needs to be cleaned  ',
            'platforms': 'android, ios, web',
            'countries': 'US,GB,CA',
            'tags': 'game, mobile, fun',
            'requirements': None  # Should become empty list
        }
        
        cleaned_data = crawler.clean_offer_data(messy_data)
        
        self.assertEqual(cleaned_data['title'], 'Messy Title')
        self.assertEqual(cleaned_data['description'], 'Long description that needs to be cleaned')
        self.assertEqual(cleaned_data['platforms'], ['android', 'ios', 'web'])
        self.assertEqual(cleaned_data['countries'], ['US', 'GB', 'CA'])
        self.assertEqual(cleaned_data['tags'], ['game', 'mobile', 'fun'])
        self.assertEqual(cleaned_data['requirements'], [])
        
        logger.info("Crawler data cleaning test: PASSED")
    
    @patch('requests.get')
    def test_crawler_api_request(self, mock_get):
        """Test crawler API request functionality"""
        logger.info("Testing crawler API request...")
        
        crawler = OfferCrawler(self.ad_network)
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'success'}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Test GET request
        response = crawler.make_api_request('https://example.com/api')
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)
        
        # Test POST request
        response = crawler.make_api_request('https://example.com/api', method='POST', data={'test': 'data'})
        self.assertIsNotNone(response)
        
        logger.info("Crawler API request test: PASSED")


def run_crawler_tests():
    """Run all crawler tests"""
    logger.info("Starting Crawler Tests...")
    
    test_instance = CrawlerTest()
    test_instance.setUp()
    
    test_methods = [
        test_instance.test_crawler_registry,
        test_instance.test_offer_crawler_base_class,
        test_instance.test_admob_crawler_initialization,
        test_instance.test_admob_crawler_offer_creation,
        test_instance.test_tapjoy_crawler_initialization,
        test_instance.test_tapjoy_crawler_signature_generation,
        test_instance.test_tapjoy_crawler_offer_processing,
        test_instance.test_crawler_save_offer,
        test_instance.test_crawler_data_cleaning,
        test_instance.test_crawler_api_request,
    ]
    
    passed = 0
    failed = 0
    
    for test_method in test_methods:
        try:
            test_method()
            passed += 1
            logger.info(f"Test {test_method.__name__}: PASSED")
        except Exception as e:
            failed += 1
            logger.error(f"Test {test_method.__name__}: FAILED - {str(e)}")
    
    logger.info(f"Crawler Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        logger.info("All crawler tests PASSED!")
    else:
        logger.warning(f"{failed} tests failed. Crawler implementation needs attention.")
    
    return failed == 0


if __name__ == '__main__':
    run_crawler_tests()
