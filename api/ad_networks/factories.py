"""
api/ad_networks/factories.py
Factory classes for ad networks module
SaaS-ready with tenant support
"""

import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Type
from enum import Enum

from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models

from .models import (
    AdNetwork, OfferCategory, Offer, UserOfferEngagement,
    OfferConversion, OfferReward, UserWallet, OfferClick,
    NetworkHealthCheck, OfferDailyLimit, OfferTag, OfferTagging,
    KnownBadIP, AdNetworkWebhookLog, NetworkAPILog
)
from .choices import (
    OfferStatus, EngagementStatus, ConversionStatus,
    RewardStatus, NetworkStatus, DeviceType, Difficulty
)
from .abstracts import (
    AbstractNetworkClient, AbstractOfferProcessor,
    AbstractFraudDetector, AbstractRewardCalculator
)

logger = logging.getLogger(__name__)
User = get_user_model()


class FactoryType(Enum):
    """Factory types"""
    
    MODEL = "model"
    SERVICE = "service"
    CLIENT = "client"
    PROCESSOR = "processor"
    DETECTOR = "detector"
    CALCULATOR = "calculator"


class BaseFactory:
    """Base factory class"""
    
    def __init__(self, factory_type: FactoryType):
        self.factory_type = factory_type
        self._registry = {}
    
    def register(self, name: str, cls: Type):
        """Register a class"""
        self._registry[name] = cls
        logger.info(f"Registered {self.factory_type.value} class: {name}")
    
    def unregister(self, name: str):
        """Unregister a class"""
        if name in self._registry:
            del self._registry[name]
            logger.info(f"Unregistered {self.factory_type.value} class: {name}")
    
    def create(self, name: str, *args, **kwargs):
        """Create an instance"""
        if name not in self._registry:
            raise ValueError(f"{self.factory_type.value} class '{name}' not registered")
        
        cls = self._registry[name]
        return cls(*args, **kwargs)
    
    def get_registered_classes(self) -> List[str]:
        """Get list of registered classes"""
        return list(self._registry.keys())
    
    def is_registered(self, name: str) -> bool:
        """Check if class is registered"""
        return name in self._registry


class ModelFactory(BaseFactory):
    """Factory for creating model instances"""
    
    def __init__(self):
        super().__init__(FactoryType.MODEL)
    
    def create_ad_network(self, **kwargs) -> AdNetwork:
        """Create AdNetwork instance"""
        defaults = {
            'name': f'Test Network {uuid.uuid4().hex[:8]}',
            'network_type': 'adscend',
            'category': 'survey',
            'description': 'Test network for testing purposes',
            'website': 'https://example.com',
            'base_url': 'https://api.example.com',
            'api_key': 'test_api_key_' + uuid.uuid4().hex,
            'supports_postback': True,
            'supports_webhook': True,
            'supports_offers': True,
            'country_support': 'global',
            'min_payout': Decimal('0.01'),
            'max_payout': Decimal('100.00'),
            'commission_rate': 10.0,
            'rating': 4.5,
            'trust_score': 85.0,
            'priority': 50,
            'is_active': True,
            'is_verified': True,
            'is_testing': False,
            'status': NetworkStatus.ACTIVE,
            'tenant_id': kwargs.get('tenant_id', 'default')
        }
        defaults.update(kwargs)
        
        return AdNetwork.objects.create(**defaults)
    
    def create_offer_category(self, **kwargs) -> OfferCategory:
        """Create OfferCategory instance"""
        defaults = {
            'name': f'Test Category {uuid.uuid4().hex[:8]}',
            'slug': f'test-category-{uuid.uuid4().hex[:8]}',
            'description': 'Test category for testing purposes',
            'icon': 'https://example.com/icon.png',
            'is_active': True,
            'priority': 50
        }
        defaults.update(kwargs)
        
        return OfferCategory.objects.create(**defaults)
    
    def create_offer(self, ad_network: AdNetwork = None, 
                    category: OfferCategory = None, **kwargs) -> Offer:
        """Create Offer instance"""
        if not ad_network:
            ad_network = self.create_ad_network()
        
        if not category:
            category = self.create_offer_category()
        
        defaults = {
            'ad_network': ad_network,
            'category': category,
            'external_id': f'offer_{uuid.uuid4().hex}',
            'title': f'Test Offer {uuid.uuid4().hex[:8]}',
            'description': 'Test offer description',
            'short_description': 'Test offer short description',
            'reward_amount': Decimal('1.00'),
            'reward_currency': 'USD',
            'network_payout': Decimal('0.80'),
            'status': OfferStatus.ACTIVE,
            'countries': ['US', 'GB', 'CA'],
            'platforms': ['android', 'ios', 'web'],
            'device_type': DeviceType.ANY,
            'difficulty': Difficulty.EASY,
            'estimated_time': 5,
            'requirements': 'Complete the task',
            'instructions': 'Follow the instructions',
            'preview_url': 'https://example.com/preview',
            'tracking_url': 'https://example.com/track',
            'is_featured': False,
            'is_hot': False,
            'is_new': True,
            'priority': 50,
            'expires_at': timezone.now() + timedelta(days=30),
            'tenant_id': kwargs.get('tenant_id', 'default')
        }
        defaults.update(kwargs)
        
        return Offer.objects.create(**defaults)
    
    def create_user_engagement(self, user: User = None, offer: Offer = None,
                              **kwargs) -> UserOfferEngagement:
        """Create UserOfferEngagement instance"""
        if not user:
            user = User.objects.create_user(
                username=f'testuser_{uuid.uuid4().hex[:8]}',
                email=f'test_{uuid.uuid4().hex[:8]}@example.com',
                password='testpass123'
            )
        
        if not offer:
            offer = self.create_offer()
        
        defaults = {
            'user': user,
            'offer': offer,
            'status': EngagementStatus.STARTED,
            'ip_address': '192.168.1.1',
            'user_agent': 'Test User Agent',
            'country': 'US',
            'device_info': {'type': 'mobile', 'os': 'Android'},
            'started_at': timezone.now(),
            'tenant_id': kwargs.get('tenant_id', 'default')
        }
        defaults.update(kwargs)
        
        return UserOfferEngagement.objects.create(**defaults)
    
    def create_conversion(self, engagement: UserOfferEngagement = None,
                       **kwargs) -> OfferConversion:
        """Create OfferConversion instance"""
        if not engagement:
            engagement = self.create_user_engagement()
        
        defaults = {
            'engagement': engagement,
            'payout': Decimal('1.00'),
            'currency': 'USD',
            'conversion_status': ConversionStatus.PENDING,
            'fraud_score': 10.0,
            'conversion_data': {'test': 'data'},
            'tenant_id': kwargs.get('tenant_id', 'default')
        }
        defaults.update(kwargs)
        
        return OfferConversion.objects.create(**defaults)
    
    def create_reward(self, user: User = None, offer: Offer = None,
                     engagement: UserOfferEngagement = None, **kwargs) -> OfferReward:
        """Create OfferReward instance"""
        if not user:
            user = User.objects.create_user(
                username=f'testuser_{uuid.uuid4().hex[:8]}',
                email=f'test_{uuid.uuid4().hex[:8]}@example.com',
                password='testpass123'
            )
        
        if not offer:
            offer = self.create_offer()
        
        if not engagement:
            engagement = self.create_user_engagement(user=user, offer=offer)
        
        defaults = {
            'user': user,
            'offer': offer,
            'engagement': engagement,
            'amount': Decimal('1.00'),
            'currency': 'USD',
            'status': RewardStatus.PENDING,
            'reason': 'Test reward',
            'tenant_id': kwargs.get('tenant_id', 'default')
        }
        defaults.update(kwargs)
        
        return OfferReward.objects.create(**defaults)
    
    def create_user_wallet(self, user: User = None, **kwargs) -> UserWallet:
        """Create UserWallet instance"""
        if not user:
            user = User.objects.create_user(
                username=f'testuser_{uuid.uuid4().hex[:8]}',
                email=f'test_{uuid.uuid4().hex[:8]}@example.com',
                password='testpass123'
            )
        
        defaults = {
            'user': user,
            'balance': Decimal('0.00'),
            'total_earned': Decimal('0.00'),
            'currency': 'USD',
            'tenant_id': kwargs.get('tenant_id', 'default')
        }
        defaults.update(kwargs)
        
        return UserWallet.objects.create(**defaults)
    
    def create_offer_click(self, offer: Offer = None, user: User = None,
                         **kwargs) -> OfferClick:
        """Create OfferClick instance"""
        if not offer:
            offer = self.create_offer()
        
        defaults = {
            'offer': offer,
            'user': user,
            'ip_address': '192.168.1.1',
            'user_agent': 'Test User Agent',
            'country': 'US',
            'device': 'mobile',
            'browser': 'chrome',
            'os': 'android',
            'clicked_at': timezone.now(),
            'is_unique': True,
            'is_fraud': False,
            'fraud_score': 5.0,
            'referrer_url': 'https://example.com',
            'session_id': uuid.uuid4().hex,
            'location_data': {'city': 'New York', 'country': 'US'},
            'device_info': {'type': 'mobile', 'os': 'Android'},
            'tenant_id': kwargs.get('tenant_id', 'default')
        }
        defaults.update(kwargs)
        
        return OfferClick.objects.create(**defaults)
    
    def create_network_health_check(self, network: AdNetwork = None,
                                 **kwargs) -> NetworkHealthCheck:
        """Create NetworkHealthCheck instance"""
        if not network:
            network = self.create_ad_network()
        
        defaults = {
            'network': network,
            'is_healthy': True,
            'check_type': 'api_call',
            'endpoint_checked': '/api/health',
            'response_time_ms': 150,
            'status_code': 200,
            'checked_at': timezone.now(),
            'tenant_id': kwargs.get('tenant_id', 'default')
        }
        defaults.update(kwargs)
        
        return NetworkHealthCheck.objects.create(**defaults)
    
    def create_offer_daily_limit(self, user: User = None, offer: Offer = None,
                                 **kwargs) -> OfferDailyLimit:
        """Create OfferDailyLimit instance"""
        if not user:
            user = User.objects.create_user(
                username=f'testuser_{uuid.uuid4().hex[:8]}',
                email=f'test_{uuid.uuid4().hex[:8]}@example.com',
                password='testpass123'
            )
        
        if not offer:
            offer = self.create_offer()
        
        defaults = {
            'user': user,
            'offer': offer,
            'daily_limit': 10,
            'count_today': 0,
            'last_reset_at': timezone.now(),
            'tenant_id': kwargs.get('tenant_id', 'default')
        }
        defaults.update(kwargs)
        
        return OfferDailyLimit.objects.create(**defaults)
    
    def create_offer_tag(self, **kwargs) -> OfferTag:
        """Create OfferTag instance"""
        defaults = {
            'name': f'Test Tag {uuid.uuid4().hex[:8]}',
            'slug': f'test-tag-{uuid.uuid4().hex[:8]}',
            'description': 'Test tag description',
            'color': '#FF0000',
            'is_active': True
        }
        defaults.update(kwargs)
        
        return OfferTag.objects.create(**defaults)
    
    def create_offer_tagging(self, offer: Offer = None, tag: OfferTag = None,
                            **kwargs) -> OfferTagging:
        """Create OfferTagging instance"""
        if not offer:
            offer = self.create_offer()
        
        if not tag:
            tag = self.create_offer_tag()
        
        defaults = {
            'offer': offer,
            'tag': tag,
            'tenant_id': kwargs.get('tenant_id', 'default')
        }
        defaults.update(kwargs)
        
        return OfferTagging.objects.create(**defaults)
    
    def create_known_bad_ip(self, **kwargs) -> KnownBadIP:
        """Create KnownBadIP instance"""
        defaults = {
            'ip_address': f'192.168.1.{uuid.uuid4().hex[:2]}',
            'threat_type': 'malware',
            'confidence_score': 85.0,
            'source': 'test_source',
            'expires_at': timezone.now() + timedelta(days=30),
            'description': 'Test bad IP',
            'first_seen': timezone.now(),
            'last_seen': timezone.now(),
            'is_active': True
        }
        defaults.update(kwargs)
        
        return KnownBadIP.objects.create(**defaults)


class ServiceFactory(BaseFactory):
    """Factory for creating service instances"""
    
    def __init__(self):
        super().__init__(FactoryType.SERVICE)
    
    def create_offer_sync_service(self, tenant_id: str = 'default'):
        """Create OfferSyncService instance"""
        from .services.OfferSyncService import OfferSyncService
        return OfferSyncService(tenant_id=tenant_id)
    
    def create_conversion_service(self, tenant_id: str = 'default'):
        """Create ConversionService instance"""
        from .services.ConversionService import ConversionService
        return ConversionService(tenant_id=tenant_id)
    
    def create_reward_service(self, tenant_id: str = 'default'):
        """Create RewardService instance"""
        from .services.RewardService import RewardService
        return RewardService(tenant_id=tenant_id)
    
    def create_fraud_detection_service(self, tenant_id: str = 'default'):
        """Create FraudDetectionService instance"""
        from .services.FraudDetectionService import FraudDetectionService
        return FraudDetectionService(tenant_id=tenant_id)
    
    def create_network_health_service(self, tenant_id: str = 'default'):
        """Create NetworkHealthService instance"""
        from .services.NetworkHealthService import NetworkHealthService
        return NetworkHealthService(tenant_id=tenant_id)
    
    def create_offer_recommend_service(self, tenant_id: str = 'default'):
        """Create OfferRecommendService instance"""
        from .services.OfferRecommendService import OfferRecommendService
        return OfferRecommendService(tenant_id=tenant_id)


class ClientFactory(BaseFactory):
    """Factory for creating client instances"""
    
    def __init__(self):
        super().__init__(FactoryType.CLIENT)
    
    def create_network_client(self, network_type: str, config: Dict[str, Any],
                           tenant_id: str = 'default'):
        """Create network client instance"""
        if network_type == 'adscend':
            from .clients.AdscendClient import AdscendClient
            return AdscendClient(config, tenant_id)
        elif network_type == 'offertoro':
            from .clients.OffertoroClient import OffertoroClient
            return OffertoroClient(config, tenant_id)
        elif network_type == 'adgem':
            from .clients.AdgemClient import AdgemClient
            return AdgemClient(config, tenant_id)
        else:
            raise ValueError(f"Unknown network type: {network_type}")
    
    def create_external_api_client(self, base_url: str, api_key: str,
                                 tenant_id: str = 'default'):
        """Create ExternalAPIClient instance"""
        from .dependencies import ExternalAPIClient
        return ExternalAPIClient(base_url, api_key, tenant_id)


class ProcessorFactory(BaseFactory):
    """Factory for creating processor instances"""
    
    def __init__(self):
        super().__init__(FactoryType.PROCESSOR)
    
    def create_offer_processor(self, processor_type: str, config: Dict[str, Any],
                             tenant_id: str = 'default'):
        """Create offer processor instance"""
        if processor_type == 'default':
            from .processors.DefaultOfferProcessor import DefaultOfferProcessor
            return DefaultOfferProcessor(config, tenant_id)
        elif processor_type == 'survey':
            from .processors.SurveyOfferProcessor import SurveyOfferProcessor
            return SurveyOfferProcessor(config, tenant_id)
        else:
            raise ValueError(f"Unknown processor type: {processor_type}")


class DetectorFactory(BaseFactory):
    """Factory for creating detector instances"""
    
    def __init__(self):
        super().__init__(FactoryType.DETECTOR)
    
    def create_fraud_detector(self, detector_type: str, config: Dict[str, Any],
                             tenant_id: str = 'default'):
        """Create fraud detector instance"""
        if detector_type == 'basic':
            from .detectors.BasicFraudDetector import BasicFraudDetector
            return BasicFraudDetector(config, tenant_id)
        elif detector_type == 'advanced':
            from .detectors.AdvancedFraudDetector import AdvancedFraudDetector
            return AdvancedFraudDetector(config, tenant_id)
        else:
            raise ValueError(f"Unknown detector type: {detector_type}")


class CalculatorFactory(BaseFactory):
    """Factory for creating calculator instances"""
    
    def __init__(self):
        super().__init__(FactoryType.CALCULATOR)
    
    def create_reward_calculator(self, calculator_type: str, config: Dict[str, Any],
                                tenant_id: str = 'default'):
        """Create reward calculator instance"""
        if calculator_type == 'default':
            from .calculators.DefaultRewardCalculator import DefaultRewardCalculator
            return DefaultRewardCalculator(config, tenant_id)
        elif calculator_type == 'loyalty':
            from .calculators.LoyaltyRewardCalculator import LoyaltyRewardCalculator
            return LoyaltyRewardCalculator(config, tenant_id)
        else:
            raise ValueError(f"Unknown calculator type: {calculator_type}")


class TestDataFactory:
    """Factory for creating test data"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.model_factory = ModelFactory()
        self.service_factory = ServiceFactory()
        self.client_factory = ClientFactory()
        self.processor_factory = ProcessorFactory()
        self.detector_factory = DetectorFactory()
        self.calculator_factory = CalculatorFactory()
    
    def create_test_user(self, **kwargs) -> User:
        """Create test user"""
        defaults = {
            'username': f'testuser_{uuid.uuid4().hex[:8]}',
            'email': f'test_{uuid.uuid4().hex[:8]}@example.com',
            'password': 'testpass123',
            'is_active': True
        }
        defaults.update(kwargs)
        
        return User.objects.create_user(**defaults)
    
    def create_test_network(self, **kwargs) -> AdNetwork:
        """Create test network"""
        return self.model_factory.create_ad_network(
            tenant_id=self.tenant_id, **kwargs
        )
    
    def create_test_offer(self, network: AdNetwork = None, **kwargs) -> Offer:
        """Create test offer"""
        return self.model_factory.create_offer(
            ad_network=network, tenant_id=self.tenant_id, **kwargs
        )
    
    def create_test_engagement(self, user: User = None, offer: Offer = None,
                             **kwargs) -> UserOfferEngagement:
        """Create test engagement"""
        return self.model_factory.create_user_engagement(
            user=user, offer=offer, tenant_id=self.tenant_id, **kwargs
        )
    
    def create_test_conversion(self, engagement: UserOfferEngagement = None,
                             **kwargs) -> OfferConversion:
        """Create test conversion"""
        return self.model_factory.create_conversion(
            engagement=engagement, tenant_id=self.tenant_id, **kwargs
        )
    
    def create_test_reward(self, user: User = None, offer: Offer = None,
                          **kwargs) -> OfferReward:
        """Create test reward"""
        return self.model_factory.create_reward(
            user=user, offer=offer, tenant_id=self.tenant_id, **kwargs
        )
    
    def create_complete_test_flow(self) -> Dict[str, Any]:
        """Create complete test flow"""
        # Create user
        user = self.create_test_user()
        
        # Create network and offer
        network = self.create_test_network()
        offer = self.create_test_offer(network=network)
        
        # Create engagement
        engagement = self.create_test_engagement(user=user, offer=offer)
        
        # Create conversion
        conversion = self.create_test_conversion(engagement=engagement)
        
        # Create reward
        reward = self.create_test_reward(user=user, offer=offer, engagement=engagement)
        
        # Create wallet
        wallet = self.model_factory.create_user_wallet(user=user)
        
        return {
            'user': user,
            'network': network,
            'offer': offer,
            'engagement': engagement,
            'conversion': conversion,
            'reward': reward,
            'wallet': wallet
        }
    
    def create_bulk_test_data(self, count: int = 10) -> Dict[str, List[Any]]:
        """Create bulk test data"""
        data = {
            'users': [],
            'networks': [],
            'offers': [],
            'engagements': [],
            'conversions': [],
            'rewards': []
        }
        
        # Create networks
        for i in range(count):
            network = self.create_test_network(name=f'Test Network {i+1}')
            data['networks'].append(network)
        
        # Create offers
        for network in data['networks']:
            for i in range(3):  # 3 offers per network
                offer = self.create_test_offer(
                    network=network,
                    title=f'Test Offer {i+1} for {network.name}'
                )
                data['offers'].append(offer)
        
        # Create users and engagements
        for i in range(count * 2):  # 2x users
            user = self.create_test_user(username=f'testuser{i+1}')
            data['users'].append(user)
            
            # Create 3-5 engagements per user
            for j in range(3):
                offer = data['offers'][j % len(data['offers'])]
                engagement = self.create_test_engagement(
                    user=user, offer=offer
                )
                data['engagements'].append(engagement)
                
                # Create conversion for some engagements
                if j % 2 == 0:
                    conversion = self.create_test_conversion(
                        engagement=engagement
                    )
                    data['conversions'].append(conversion)
                    
                    # Create reward
                    reward = self.create_test_reward(
                        user=user, offer=offer, engagement=engagement
                    )
                    data['rewards'].append(reward)
        
        return data


# Global factory instances
model_factory = ModelFactory()
service_factory = ServiceFactory()
client_factory = ClientFactory()
processor_factory = ProcessorFactory()
detector_factory = DetectorFactory()
calculator_factory = CalculatorFactory()


# Export all classes and instances
__all__ = [
    # Enums
    'FactoryType',
    
    # Base classes
    'BaseFactory',
    'ModelFactory',
    'ServiceFactory',
    'ClientFactory',
    'ProcessorFactory',
    'DetectorFactory',
    'CalculatorFactory',
    'TestDataFactory',
    
    # Global instances
    'model_factory',
    'service_factory',
    'client_factory',
    'processor_factory',
    'detector_factory',
    'calculator_factory'
]
