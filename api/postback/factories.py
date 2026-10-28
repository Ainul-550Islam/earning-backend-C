"""
factories.py – Factory classes for postback module.

Provides comprehensive factory functionality including:
- Model factories for testing
- Service factories
- Data factories
- Factory patterns for object creation
"""
import logging
import uuid
from typing import Dict, List, Optional, Any, Union, Type
from datetime import datetime, timedelta
from decimal import Decimal
from random import choice, randint, uniform
from enum import Enum

from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .choices import PostbackStatus, RejectionReason
from .services import PostbackInsightService, TemplateService

logger = logging.getLogger(__name__)
User = get_user_model()


class FactoryType(Enum):
    """Factory type enumeration."""
    MODEL = "model"
    SERVICE = "service"
    DATA = "data"
    SERIALIZER = "serializer"


class BaseFactory:
    """
    Base factory class.
    
    Provides common factory functionality that can be
    extended for specific object creation needs.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._registry = {}
    
    def register(self, name: str, factory_func: callable):
        """
        Register a factory function.
        
        Args:
            name: Factory name
            factory_func: Factory function
        """
        self._registry[name] = factory_func
        self.logger.info(f"Registered factory: {name}")
    
    def create(self, name: str, **kwargs):
        """
        Create object using registered factory.
        
        Args:
            name: Factory name
            **kwargs: Creation parameters
            
        Returns:
            Created object
        """
        if name not in self._registry:
            raise ValueError(f"Factory {name} not registered")
        
        factory_func = self._registry[name]
        return factory_func(**kwargs)
    
    def list_factories(self) -> List[str]:
        """List all registered factories."""
        return list(self._registry.keys())


class ModelFactory(BaseFactory):
    """
    Factory for creating model instances.
    
    Provides specialized functionality for creating
    Django model instances with proper defaults.
    """
    
    def __init__(self):
        super().__init__()
        self._setup_default_factories()
    
    def _setup_default_factories(self):
        """Setup default model factories."""
        self.register('postback_log', self.create_postback_log)
        self.register('postback_insight', self.create_postback_insight)
        self.register('network_config', self.create_network_config)
        self.register('user', self.create_user)
    
    def create_postback_log(self, **kwargs) -> PostbackLog:
        """
        Create PostbackLog instance.
        
        Args:
            **kwargs: Override parameters
            
        Returns:
            PostbackLog instance
        """
        # Get or create network config
        network_config = kwargs.get('network')
        if not network_config:
            network_config = self.create_network_config()
        
        # Get or create user
        user = kwargs.get('resolved_user')
        if not user and kwargs.get('with_user'):
            user = self.create_user()
        
        # Create postback log
        postback_data = {
            'network': network_config,
            'status': kwargs.get('status', PostbackStatus.RECEIVED),
            'raw_payload': kwargs.get('raw_payload', self._generate_payload()),
            'integrity_hash': kwargs.get('integrity_hash', self._generate_hash()),
            'extracted_fields': kwargs.get('extracted_fields', self._generate_extracted_fields()),
            'source_ip': kwargs.get('source_ip', self._generate_ip()),
            'user_agent': kwargs.get('user_agent', self._generate_user_agent()),
            'lead_id': kwargs.get('lead_id', self._generate_lead_id()),
            'offer_id': kwargs.get('offer_id', self._generate_offer_id()),
            'payout': kwargs.get('payout', Decimal(str(round(uniform(0.1, 10.0), 2)))),
            'rejection_reason': kwargs.get('rejection_reason', None),
            'received_at': kwargs.get('received_at', timezone.now()),
        }
        
        if user:
            postback_data['resolved_user'] = user
        
        postback_log = PostbackLog(**postback_data)
        postback_log.save()
        
        return postback_log
    
    def create_postback_insight(self, **kwargs) -> PostbackInsight:
        """
        Create PostbackInsight instance.
        
        Args:
            **kwargs: Override parameters
            
        Returns:
            PostbackInsight instance
        """
        # Get or create network config
        network_config = kwargs.get('network')
        if not network_config:
            network_config = self.create_network_config()
        
        # Create insight
        insight_data = {
            'network': network_config,
            'date': kwargs.get('date', timezone.now().date()),
            'received_count': kwargs.get('received_count', randint(10, 1000)),
            'rewarded_count': kwargs.get('rewarded_count', randint(5, 500)),
            'rejected_count': kwargs.get('rejected_count', randint(1, 100)),
            'health_score': kwargs.get('health_score', uniform(60.0, 100.0)),
            'total_payout': kwargs.get('total_payout', Decimal(str(round(uniform(10.0, 1000.0), 2)))),
            'anomaly_detected': kwargs.get('anomaly_detected', False),
            'anomaly_details': kwargs.get('anomaly_details', {}),
        }
        
        insight = PostbackInsight(**insight_data)
        insight.save()
        
        return insight
    
    def create_network_config(self, **kwargs) -> NetworkPostbackConfig:
        """
        Create NetworkPostbackConfig instance.
        
        Args:
            **kwargs: Override parameters
            
        Returns:
            NetworkPostbackConfig instance
        """
        config_data = {
            'network_key': kwargs.get('network_key', self._generate_network_key()),
            'name': kwargs.get('name', f"Test Network {randint(1, 100)}"),
            'secret_key': kwargs.get('secret_key', self._generate_secret_key()),
            'signature_algorithm': kwargs.get('signature_algorithm', 'hmac_sha256'),
            'is_active': kwargs.get('is_active', True),
            'ip_whitelist': kwargs.get('ip_whitelist', ['192.168.1.1', '10.0.0.1']),
            'required_fields': kwargs.get('required_fields', ['lead_id', 'offer_id']),
            'max_payout': kwargs.get('max_payout', Decimal('50.00')),
            'default_reward_points': kwargs.get('default_reward_points', 100),
            'custom_throttle_rate': kwargs.get('custom_throttle_rate', '100/hour'),
        }
        
        config = NetworkPostbackConfig(**config_data)
        config.save()
        
        return config
    
    def create_user(self, **kwargs) -> User:
        """
        Create User instance.
        
        Args:
            **kwargs: Override parameters
            
        Returns:
            User instance
        """
        user_data = {
            'username': kwargs.get('username', f'testuser_{uuid.uuid4().hex[:8]}'),
            'email': kwargs.get('email', f'testuser_{uuid.uuid4().hex[:8]}@example.com'),
            'first_name': kwargs.get('first_name', 'Test'),
            'last_name': kwargs.get('last_name', 'User'),
            'is_staff': kwargs.get('is_staff', False),
            'is_superuser': kwargs.get('is_superuser', False),
            'is_active': kwargs.get('is_active', True),
        }
        
        if 'password' in kwargs:
            user_data['password'] = kwargs['password']
        else:
            user_data['password'] = 'testpass123'
        
        user = User(**user_data)
        user.set_password(user_data['password'])
        user.save()
        
        return user
    
    def create_batch(self, factory_name: str, count: int, **kwargs) -> List:
        """
        Create batch of objects.
        
        Args:
            factory_name: Factory name
            count: Number of objects to create
            **kwargs: Creation parameters
            
        Returns:
            List of created objects
        """
        objects = []
        
        for i in range(count):
            # Add batch-specific overrides
            batch_kwargs = kwargs.copy()
            batch_kwargs.update({
                f'batch_index': i,
                f'batch_size': count,
            })
            
            obj = self.create(factory_name, **batch_kwargs)
            objects.append(obj)
        
        return objects
    
    # Helper methods
    def _generate_payload(self) -> Dict[str, Any]:
        """Generate sample postback payload."""
        return {
            'network_key': self._generate_network_key(),
            'lead_id': self._generate_lead_id(),
            'offer_id': self._generate_offer_id(),
            'payout': str(round(uniform(0.1, 10.0), 2)),
            'timestamp': timezone.now().isoformat(),
            'custom_field1': f'value_{randint(1, 100)}',
            'custom_field2': f'value_{randint(1, 100)}',
        }
    
    def _generate_hash(self) -> str:
        """Generate sample integrity hash."""
        import hashlib
        return hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    
    def _generate_extracted_fields(self) -> Dict[str, Any]:
        """Generate sample extracted fields."""
        return {
            'campaign_id': f'campaign_{randint(1, 50)}',
            'affiliate_id': f'aff_{randint(1, 100)}',
            'country': choice(['US', 'GB', 'CA', 'AU', 'DE']),
            'device_type': choice(['mobile', 'desktop', 'tablet']),
            'os': choice(['iOS', 'Android', 'Windows', 'macOS', 'Linux']),
        }
    
    def _generate_ip(self) -> str:
        """Generate sample IP address."""
        return f"{randint(1, 255)}.{randint(1, 255)}.{randint(1, 255)}.{randint(1, 255)}"
    
    def _generate_user_agent(self) -> str:
        """Generate sample user agent."""
        agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        ]
        return choice(agents)
    
    def _generate_lead_id(self) -> str:
        """Generate sample lead ID."""
        return f"lead_{uuid.uuid4().hex[:12]}"
    
    def _generate_offer_id(self) -> str:
        """Generate sample offer ID."""
        return f"offer_{randint(1000, 9999)}"
    
    def _generate_network_key(self) -> str:
        """Generate sample network key."""
        return f"test_network_{randint(1, 100)}"
    
    def _generate_secret_key(self) -> str:
        """Generate sample secret key."""
        return uuid.uuid4().hex


class ServiceFactory(BaseFactory):
    """
    Factory for creating service instances.
    
    Provides specialized functionality for creating
    service objects with proper configuration.
    """
    
    def __init__(self):
        super().__init__()
        self._setup_default_factories()
    
    def _setup_default_factories(self):
        """Setup default service factories."""
        self.register('postback_insight_service', self.create_postback_insight_service)
        self.register('template_service', self.create_template_service)
    
    def create_postback_insight_service(self, **kwargs) -> PostbackInsightService:
        """
        Create PostbackInsightService instance.
        
        Args:
            **kwargs: Configuration parameters
            
        Returns:
            PostbackInsightService instance
        """
        config = {
            'cache_timeout': kwargs.get('cache_timeout', 3600),
            'batch_size': kwargs.get('batch_size', 100),
            'enable_analytics': kwargs.get('enable_analytics', True),
        }
        
        return PostbackInsightService(config)
    
    def create_template_service(self, **kwargs) -> TemplateService:
        """
        Create TemplateService instance.
        
        Args:
            **kwargs: Configuration parameters
            
        Returns:
            TemplateService instance
        """
        config = {
            'template_cache_timeout': kwargs.get('template_cache_timeout', 1800),
            'enable_validation': kwargs.get('enable_validation', True),
            'default_template_type': kwargs.get('default_template_type', 'html'),
        }
        
        return TemplateService(config)


class DataFactory(BaseFactory):
    """
    Factory for creating data objects.
    
    Provides specialized functionality for creating
    data structures and test data.
    """
    
    def __init__(self):
        super().__init__()
        self._setup_default_factories()
    
    def _setup_default_factories(self):
        """Setup default data factories."""
        self.register('postback_data', self.create_postback_data)
        self.register('analytics_data', self.create_analytics_data)
        self.register('network_config_data', self.create_network_config_data)
        self.register('user_data', self.create_user_data)
    
    def create_postback_data(self, **kwargs) -> Dict[str, Any]:
        """
        Create postback data dictionary.
        
        Args:
            **kwargs: Override parameters
            
        Returns:
            Postback data dictionary
        """
        return {
            'network_key': kwargs.get('network_key', f"test_network_{randint(1, 100)}"),
            'lead_id': kwargs.get('lead_id', f"lead_{uuid.uuid4().hex[:12]}"),
            'offer_id': kwargs.get('offer_id', f"offer_{randint(1000, 9999)}"),
            'payout': kwargs.get('payout', round(uniform(0.1, 10.0), 2)),
            'timestamp': kwargs.get('timestamp', timezone.now().isoformat()),
            'signature': kwargs.get('signature', uuid.uuid4().hex),
            'custom_fields': kwargs.get('custom_fields', {
                'campaign_id': f'campaign_{randint(1, 50)}',
                'affiliate_id': f'aff_{randint(1, 100)}',
                'country': choice(['US', 'GB', 'CA', 'AU', 'DE']),
                'device_type': choice(['mobile', 'desktop', 'tablet']),
            }),
        }
    
    def create_analytics_data(self, **kwargs) -> Dict[str, Any]:
        """
        Create analytics data dictionary.
        
        Args:
            **kwargs: Override parameters
            
        Returns:
            Analytics data dictionary
        """
        return {
            'network_key': kwargs.get('network_key', f"test_network_{randint(1, 100)}"),
            'date': kwargs.get('date', timezone.now().date().isoformat()),
            'received_count': kwargs.get('received_count', randint(10, 1000)),
            'rewarded_count': kwargs.get('rewarded_count', randint(5, 500)),
            'rejected_count': kwargs.get('rejected_count', randint(1, 100)),
            'health_score': kwargs.get('health_score', round(uniform(60.0, 100.0), 2)),
            'total_payout': kwargs.get('total_payout', round(uniform(10.0, 1000.0), 2)),
            'anomaly_detected': kwargs.get('anomaly_detected', False),
            'anomaly_details': kwargs.get('anomaly_details', {}),
            'metrics': kwargs.get('metrics', {
                'conversion_rate': round(uniform(0.1, 0.9), 3),
                'avg_payout': round(uniform(1.0, 50.0), 2),
                'peak_hour': randint(9, 21),
            }),
        }
    
    def create_network_config_data(self, **kwargs) -> Dict[str, Any]:
        """
        Create network config data dictionary.
        
        Args:
            **kwargs: Override parameters
            
        Returns:
            Network config data dictionary
        """
        return {
            'network_key': kwargs.get('network_key', f"test_network_{randint(1, 100)}"),
            'name': kwargs.get('name', f"Test Network {randint(1, 100)}"),
            'secret_key': kwargs.get('secret_key', uuid.uuid4().hex),
            'signature_algorithm': kwargs.get('signature_algorithm', 'hmac_sha256'),
            'is_active': kwargs.get('is_active', True),
            'ip_whitelist': kwargs.get('ip_whitelist', ['192.168.1.1', '10.0.0.1']),
            'required_fields': kwargs.get('required_fields', ['lead_id', 'offer_id']),
            'max_payout': kwargs.get('max_payout', 50.00),
            'default_reward_points': kwargs.get('default_reward_points', 100),
            'custom_throttle_rate': kwargs.get('custom_throttle_rate', '100/hour'),
        }
    
    def create_user_data(self, **kwargs) -> Dict[str, Any]:
        """
        Create user data dictionary.
        
        Args:
            **kwargs: Override parameters
            
        Returns:
            User data dictionary
        """
        return {
            'username': kwargs.get('username', f'testuser_{uuid.uuid4().hex[:8]}'),
            'email': kwargs.get('email', f'testuser_{uuid.uuid4().hex[:8]}@example.com'),
            'first_name': kwargs.get('first_name', 'Test'),
            'last_name': kwargs.get('last_name', 'User'),
            'is_staff': kwargs.get('is_staff', False),
            'is_superuser': kwargs.get('is_superuser', False),
            'is_active': kwargs.get('is_active', True),
            'profile': kwargs.get('profile', {
                'phone': f"+1{randint(2000000000, 9999999999)}",
                'address': f"{randint(1, 999)} Test St",
                'city': choice(['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix']),
                'country': 'US',
            }),
        }
    
    def create_batch_data(self, factory_name: str, count: int, **kwargs) -> List[Dict[str, Any]]:
        """
        Create batch of data objects.
        
        Args:
            factory_name: Factory name
            count: Number of objects to create
            **kwargs: Creation parameters
            
        Returns:
            List of data dictionaries
        """
        data_objects = []
        
        for i in range(count):
            # Add batch-specific overrides
            batch_kwargs = kwargs.copy()
            batch_kwargs.update({
                'batch_index': i,
                'batch_size': count,
            })
            
            data_obj = self.create(factory_name, **batch_kwargs)
            data_objects.append(data_obj)
        
        return data_objects


class TestDataSet:
    """
    Test data set manager.
    
    Provides functionality for creating and managing
    complete test data sets for testing scenarios.
    """
    
    def __init__(self):
        self.model_factory = ModelFactory()
        self.data_factory = DataFactory()
        self.service_factory = ServiceFactory()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def create_basic_test_set(self, **kwargs) -> Dict[str, Any]:
        """
        Create basic test data set.
        
        Args:
            **kwargs: Configuration parameters
            
        Returns:
            Test data set dictionary
        """
        # Create network config
        network_config = self.model_factory.create_network_config(**kwargs.get('network_config', {}))
        
        # Create users
        user_count = kwargs.get('user_count', 5)
        users = self.model_factory.create_batch('user', user_count)
        
        # Create postback logs
        postback_count = kwargs.get('postback_count', 20)
        postback_logs = []
        
        for i in range(postback_count):
            user = choice(users) if kwargs.get('with_user') else None
            postback_log = self.model_factory.create_postback_log(
                network=network_config,
                resolved_user=user,
                status=choice(list(PostbackStatus)),
            )
            postback_logs.append(postback_log)
        
        # Create insights
        insight_count = kwargs.get('insight_count', 7)
        insights = []
        
        for i in range(insight_count):
            date = timezone.now().date() - timedelta(days=i)
            insight = self.model_factory.create_postback_insight(
                network=network_config,
                date=date,
            )
            insights.append(insight)
        
        return {
            'network_config': network_config,
            'users': users,
            'postback_logs': postback_logs,
            'insights': insights,
            'created_at': timezone.now(),
        }
    
    def create_performance_test_set(self, **kwargs) -> Dict[str, Any]:
        """
        Create performance test data set.
        
        Args:
            **kwargs: Configuration parameters
            
        Returns:
            Performance test data set
        """
        # Create multiple network configs
        network_count = kwargs.get('network_count', 10)
        network_configs = self.model_factory.create_batch('network_config', network_count)
        
        # Create large number of postback logs
        postback_count = kwargs.get('postback_count', 1000)
        postback_logs = []
        
        for i in range(postback_count):
            network_config = choice(network_configs)
            postback_log = self.model_factory.create_postback_log(
                network=network_config,
                status=choice([PostbackStatus.RECEIVED, PostbackStatus.REWARDED]),
            )
            postback_logs.append(postback_log)
        
        # Create insights for each network
        insights = []
        
        for network_config in network_configs:
            for days_back in range(30):
                date = timezone.now().date() - timedelta(days=days_back)
                insight = self.model_factory.create_postback_insight(
                    network=network_config,
                    date=date,
                )
                insights.append(insight)
        
        return {
            'network_configs': network_configs,
            'postback_logs': postback_logs,
            'insights': insights,
            'statistics': {
                'total_networks': len(network_configs),
                'total_postbacks': len(postback_logs),
                'total_insights': len(insights),
                'avg_postbacks_per_network': len(postback_logs) / len(network_configs),
            },
            'created_at': timezone.now(),
        }
    
    def create_edge_case_test_set(self, **kwargs) -> Dict[str, Any]:
        """
        Create edge case test data set.
        
        Args:
            **kwargs: Configuration parameters
            
        Returns:
            Edge case test data set
        """
        # Create network config with special settings
        network_config = self.model_factory.create_network_config(
            max_payout=Decimal('0.01'),  # Very low max payout
            required_fields=['special_field_1', 'special_field_2'],
        )
        
        # Create postback logs with edge cases
        edge_case_postbacks = []
        
        # Postback with very high payout
        high_payout_postback = self.model_factory.create_postback_log(
            network=network_config,
            payout=Decimal('999.99'),
            status=PostbackStatus.REJECTED,
            rejection_reason=RejectionReason.PAYOUT_EXCEEDS_MAXIMUM,
        )
        edge_case_postbacks.append(high_payout_postback)
        
        # Postback with missing required fields
        missing_fields_postback = self.model_factory.create_postback_log(
            network=network_config,
            status=PostbackStatus.REJECTED,
            rejection_reason=RejectionReason.MISSING_REQUIRED_FIELDS,
        )
        edge_case_postbacks.append(missing_fields_postback)
        
        # Postback with duplicate lead ID
        duplicate_lead_id = self._generate_lead_id()
        duplicate_postback_1 = self.model_factory.create_postback_log(
            network=network_config,
            lead_id=duplicate_lead_id,
            status=PostbackStatus.REWARDED,
        )
        duplicate_postback_2 = self.model_factory.create_postback_log(
            network=network_config,
            lead_id=duplicate_lead_id,
            status=PostbackStatus.REJECTED,
            rejection_reason=RejectionReason.DUPLICATE_LEAD,
        )
        edge_case_postbacks.extend([duplicate_postback_1, duplicate_postback_2])
        
        # Create insight with anomaly
        anomaly_insight = self.model_factory.create_postback_insight(
            network=network_config,
            health_score=15.5,  # Very low health score
            anomaly_detected=True,
            anomaly_details={
                'type': 'health_score_decline',
                'description': 'Health score significantly below threshold',
                'severity': 'high',
            },
        )
        
        return {
            'network_config': network_config,
            'edge_case_postbacks': edge_case_postbacks,
            'anomaly_insight': anomaly_insight,
            'test_cases': [
                'high_payout_rejection',
                'missing_fields_rejection',
                'duplicate_lead_rejection',
                'health_score_anomaly',
            ],
            'created_at': timezone.now(),
        }
    
    def _generate_lead_id(self) -> str:
        """Generate lead ID."""
        return f"lead_{uuid.uuid4().hex[:12]}"


# Global factory instances
model_factory = ModelFactory()
data_factory = DataFactory()
service_factory = ServiceFactory()
test_data_set = TestDataSet()


# Convenience functions
def create_postback_log(**kwargs) -> PostbackLog:
    """Create postback log using model factory."""
    return model_factory.create('postback_log', **kwargs)


def create_postback_insight(**kwargs) -> PostbackInsight:
    """Create postback insight using model factory."""
    return model_factory.create('postback_insight', **kwargs)


def create_network_config(**kwargs) -> NetworkPostbackConfig:
    """Create network config using model factory."""
    return model_factory.create('network_config', **kwargs)


def create_user(**kwargs) -> User:
    """Create user using model factory."""
    return model_factory.create('user', **kwargs)


def create_postback_data(**kwargs) -> Dict[str, Any]:
    """Create postback data using data factory."""
    return data_factory.create('postback_data', **kwargs)


def create_basic_test_set(**kwargs) -> Dict[str, Any]:
    """Create basic test data set."""
    return test_data_set.create_basic_test_set(**kwargs)


def create_performance_test_set(**kwargs) -> Dict[str, Any]:
    """Create performance test data set."""
    return test_data_set.create_performance_test_set(**kwargs)


def create_edge_case_test_set(**kwargs) -> Dict[str, Any]:
    """Create edge case test data set."""
    return test_data_set.create_edge_case_test_set(**kwargs)


# Factory registration
def register_model_factory(name: str, factory_func: callable):
    """Register custom model factory."""
    model_factory.register(name, factory_func)


def register_data_factory(name: str, factory_func: callable):
    """Register custom data factory."""
    data_factory.register(name, factory_func)


def register_service_factory(name: str, factory_func: callable):
    """Register custom service factory."""
    service_factory.register(name, factory_func)


# Factory utilities
def list_available_factories() -> Dict[str, List[str]]:
    """List all available factories."""
    return {
        'model': model_factory.list_factories(),
        'data': data_factory.list_factories(),
        'service': service_factory.list_factories(),
    }


def get_factory_statistics() -> Dict[str, Any]:
    """Get factory statistics."""
    return {
        'model_factories': len(model_factory.list_factories()),
        'data_factories': len(data_factory.list_factories()),
        'service_factories': len(service_factory.list_factories()),
        'total_factories': len(model_factory.list_factories()) + 
                           len(data_factory.list_factories()) + 
                           len(service_factory.list_factories()),
    }
