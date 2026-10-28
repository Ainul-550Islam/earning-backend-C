# =============================================================================
# fraud_detection/factories.py
# =============================================================================
"""
Factory Classes for Fraud Detection System.

Provides factory pattern implementations for creating fraud detection
objects, test data, and configurations with consistent patterns.
"""

from __future__ import annotations

import logging
import random
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Type
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from django.utils import timezone
from django.contrib.auth import get_user_model
from faker import Faker

from api.fraud_detection.models import (
    FraudCase, FraudAlert, FraudRule, FraudRiskProfile,
    DeviceFingerprint, FraudSuspiciousIP
)
from api.fraud_detection.choices import CaseStatus as FraudCaseStatus, SeverityLevel as FraudSeverity
from api.fraud_detection.schemas import FraudType, DetectionMethod, AlertType
from api.fraud_detection.abstracts import RiskLevel
from api.fraud_detection.constants import RISK_THRESHOLDS


logger = logging.getLogger(__name__)

User = get_user_model()
fake = Faker()


class FactoryType(Enum):
    """Factory types for different object creation."""
    MODEL = "model"
    SERIALIZER = "serializer"
    SERVICE = "service"
    DETECTOR = "detector"
    VALIDATOR = "validator"
    TEST_DATA = "test_data"
    CONFIGURATION = "configuration"


@dataclass
class FactoryConfig:
    """Configuration for factory operations."""
    batch_size: int = 100
    use_faker: bool = True
    random_seed: Optional[int] = None
    locale: str = 'en_US'
    override_defaults: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.override_defaults is None:
            self.override_defaults = {}
        
        if self.random_seed:
            random.seed(self.random_seed)
            fake.seed_instance(self.random_seed)


class BaseFactory:
    """Base factory class for fraud detection objects."""
    
    def __init__(self, config: Optional[FactoryConfig] = None):
        """Initialize factory."""
        self.config = config or FactoryConfig()
        self.faker = fake
        self._setup_factory()
    
    def _setup_factory(self):
        """Setup factory with configuration."""
        if self.config.locale != 'en_US':
            self.faker = Faker(self.config.locale)
        
        if self.config.random_seed:
            self.faker.seed_instance(self.config.random_seed)
    
    def create(self, **kwargs) -> Any:
        """
        Create a single object.
        
        Args:
            **kwargs: Object creation parameters
            
        Returns:
            Created object
        """
        raise NotImplementedError("Subclasses must implement create method")
    
    def create_batch(self, count: int, **kwargs) -> List[Any]:
        """
        Create multiple objects.
        
        Args:
            count: Number of objects to create
            **kwargs: Object creation parameters
            
        Returns:
            List of created objects
        """
        objects = []
        for _ in range(count):
            obj = self.create(**kwargs)
            objects.append(obj)
        return objects
    
    def get_defaults(self) -> Dict[str, Any]:
        """Get default values for object creation."""
        return {}
    
    def merge_defaults(self, **kwargs) -> Dict[str, Any]:
        """Merge defaults with provided kwargs."""
        defaults = self.get_defaults()
        defaults.update(self.config.override_defaults)
        defaults.update(kwargs)
        return defaults


class FraudCaseFactory(BaseFactory):
    """Factory for creating fraud cases."""
    
    def get_defaults(self) -> Dict[str, Any]:
        """Get default fraud case values."""
        return {
            'user_id': self._get_random_user_id(),
            'case_type': random.choice([choice.value for choice in FraudType]),
            'severity': random.choice([choice.value for choice in FraudSeverity]),
            'status': random.choice([choice.value for choice in FraudCaseStatus]),
            'risk_score': random.randint(0, 100),
            'title': self.faker.sentence(),
            'description': self.faker.paragraph(),
            'detection_method': random.choice([choice.value for choice in DetectionMethod]),
            'financial_impact': Decimal(str(random.uniform(0, 10000))),
            'regulatory_impact': random.choice([True, False]),
            'evidence_summary': {
                'transaction_count': random.randint(1, 50),
                'total_amount': str(random.uniform(100, 50000)),
                'suspicious_patterns': random.sample(
                    ['unusual_timing', 'high_velocity', 'location_anomaly', 'device_anomaly'],
                    random.randint(1, 3)
                )
            },
            'metadata': {
                'created_by_factory': True,
                'factory_version': '1.0'
            }
        }
    
    def create(self, **kwargs) -> FraudCase:
        """Create a fraud case."""
        data = self.merge_defaults(**kwargs)
        
        # Convert foreign key fields
        if 'user_id' in data and isinstance(data['user_id'], int):
            try:
                user = User.objects.get(id=data['user_id'])
                data['user'] = user
                del data['user_id']
            except User.DoesNotExist:
                # Create test user if not found
                user = self._create_test_user()
                data['user'] = user
                del data['user_id']
        
        return FraudCase.objects.create(**data)
    
    def create_high_risk_case(self, **kwargs) -> FraudCase:
        """Create a high-risk fraud case."""
        defaults = {
            'severity': FraudSeverity.CRITICAL.value,
            'risk_score': random.randint(80, 100),
            'financial_impact': Decimal(str(random.uniform(10000, 100000))),
            'regulatory_impact': True,
            'status': FraudCaseStatus.ESCALATED.value
        }
        defaults.update(kwargs)
        return self.create(**defaults)
    
    def create_regulatory_case(self, **kwargs) -> FraudCase:
        """Create a regulatory impact fraud case."""
        defaults = {
            'case_type': FraudType.MONEY_LAUNDERING.value,
            'severity': FraudSeverity.CRITICAL.value,
            'risk_score': random.randint(85, 100),
            'financial_impact': Decimal(str(random.uniform(25000, 200000))),
            'regulatory_impact': True,
            'detection_method': DetectionMethod.EXTERNAL_INTELLIGENCE.value
        }
        defaults.update(kwargs)
        return self.create(**defaults)
    
    def _get_random_user_id(self) -> int:
        """Get random user ID."""
        users = User.objects.all()
        if users:
            return random.choice(users).id
        else:
            # Create test user
            user = self._create_test_user()
            return user.id
    
    def _create_test_user(self) -> User:
        """Create a test user."""
        username = f"testuser_{uuid4().hex[:8]}"
        email = f"{username}@example.com"
        
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'first_name': self.faker.first_name(),
                'last_name': self.faker.last_name(),
                'is_active': True
            }
        )
        
        return user


class FraudAlertFactory(BaseFactory):
    """Factory for creating fraud alerts."""
    
    def get_defaults(self) -> Dict[str, Any]:
        """Get default fraud alert values."""
        return {
            'user_id': self._get_random_user_id(),
            'alert_type': random.choice([choice.value for choice in AlertType]),
            'severity_score': random.randint(0, 100),
            'title': self.faker.sentence(),
            'description': self.faker.paragraph(),
            'acknowledged': random.choice([True, False]),
            'resolved': random.choice([True, False]),
            'trigger_data': {
                'transaction_id': str(uuid4()),
                'amount': str(random.uniform(100, 10000)),
                'ip_address': self.faker.ipv4(),
                'device_fingerprint': self.faker.md5()
            },
            'context': {
                'user_agent': self.faker.user_agent(),
                'timestamp': timezone.now().isoformat(),
                'location': {
                    'country': self.faker.country_code(),
                    'city': self.faker.city()
                }
            },
            'metadata': {
                'created_by_factory': True,
                'factory_version': '1.0'
            }
        }
    
    def create(self, **kwargs) -> FraudAlert:
        """Create a fraud alert."""
        data = self.merge_defaults(**kwargs)
        
        # Convert foreign key fields
        if 'user_id' in data and isinstance(data['user_id'], int):
            try:
                user = User.objects.get(id=data['user_id'])
                data['user'] = user
                del data['user_id']
            except User.DoesNotExist:
                user = self._create_test_user()
                data['user'] = user
                del data['user_id']
        
        # Set acknowledged_by and resolved_by if applicable
        if data.get('acknowledged') and not data.get('acknowledged_by'):
            data['acknowledged_by'] = self._get_random_staff_user()
        
        if data.get('resolved') and not data.get('resolved_by'):
            data['resolved_by'] = self._get_random_staff_user()
            data['resolved_at'] = timezone.now()
        
        return FraudAlert.objects.create(**data)
    
    def create_critical_alert(self, **kwargs) -> FraudAlert:
        """Create a critical fraud alert."""
        defaults = {
            'alert_type': AlertType.SUSPICIOUS_ACTIVITY.value,
            'severity_score': random.randint(80, 100),
            'acknowledged': False,
            'resolved': False
        }
        defaults.update(kwargs)
        return self.create(**defaults)
    
    def create_high_priority_alert(self, **kwargs) -> FraudAlert:
        """Create a high priority fraud alert."""
        defaults = {
            'alert_type': AlertType.HIGH_RISK_TRANSACTION.value,
            'severity_score': random.randint(70, 89),
            'acknowledged': False,
            'resolved': False
        }
        defaults.update(kwargs)
        return self.create(**defaults)
    
    def _get_random_user_id(self) -> int:
        """Get random user ID."""
        users = User.objects.all()
        if users:
            return random.choice(users).id
        else:
            user = self._create_test_user()
            return user.id
    
    def _create_test_user(self) -> User:
        """Create a test user."""
        username = f"testuser_{uuid4().hex[:8]}"
        email = f"{username}@example.com"
        
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'first_name': self.faker.first_name(),
                'last_name': self.faker.last_name(),
                'is_active': True
            }
        )
        
        return user
    
    def _get_random_staff_user(self) -> User:
        """Get random staff user."""
        staff_users = User.objects.filter(is_staff=True)
        if staff_users:
            return random.choice(staff_users)
        else:
            # Create staff user
            username = f"staffuser_{uuid4().hex[:8]}"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': f"{username}@example.com",
                    'first_name': self.faker.first_name(),
                    'last_name': self.faker.last_name(),
                    'is_staff': True,
                    'is_active': True
                }
            )
            return user


class FraudRuleFactory(BaseFactory):
    """Factory for creating fraud rules."""
    
    def get_defaults(self) -> Dict[str, Any]:
        """Get default fraud rule values."""
        return {
            'name': f"Rule_{self.faker.word()}_{uuid4().hex[:6]}",
            'description': self.faker.paragraph(),
            'rule_type': random.choice(['amount', 'frequency', 'location', 'device', 'time']),
            'conditions': self._generate_random_conditions(),
            'actions': random.sample(
                ['block_transaction', 'flag_user', 'require_review', 'send_alert'],
                random.randint(1, 3)
            ),
            'priority': random.randint(1, 100),
            'enabled': random.choice([True, False]),
            'risk_score_impact': random.randint(5, 50),
            'confidence_score': round(random.uniform(0.5, 1.0), 2),
            'metadata': {
                'created_by_factory': True,
                'factory_version': '1.0'
            }
        }
    
    def create(self, **kwargs) -> FraudRule:
        """Create a fraud rule."""
        data = self.merge_defaults(**kwargs)
        return FraudRule.objects.create(**data)
    
    def create_high_priority_rule(self, **kwargs) -> FraudRule:
        """Create a high priority fraud rule."""
        defaults = {
            'priority': random.randint(80, 100),
            'risk_score_impact': random.randint(30, 50),
            'enabled': True
        }
        defaults.update(kwargs)
        return self.create(**defaults)
    
    def create_amount_rule(self, min_amount: float = 1000, max_amount: float = 10000, **kwargs) -> FraudRule:
        """Create an amount-based fraud rule."""
        defaults = {
            'name': f"Amount_Rule_{uuid4().hex[:6]}",
            'rule_type': 'amount',
            'conditions': [
                {
                    'field': 'amount',
                    'operator': 'greater_than',
                    'value': min_amount,
                    'weight': 1.0
                },
                {
                    'field': 'amount',
                    'operator': 'less_than',
                    'value': max_amount,
                    'weight': 0.5
                }
            ],
            'actions': ['flag_user', 'require_review']
        }
        defaults.update(kwargs)
        return self.create(**defaults)
    
    def _generate_random_conditions(self) -> List[Dict[str, Any]]:
        """Generate random rule conditions."""
        conditions = []
        
        # Amount condition
        if random.choice([True, False]):
            conditions.append({
                'field': 'amount',
                'operator': random.choice(['greater_than', 'less_than', 'equals']),
                'value': random.uniform(100, 10000),
                'weight': round(random.uniform(0.5, 1.0), 2)
            })
        
        # Frequency condition
        if random.choice([True, False]):
            conditions.append({
                'field': 'transaction_frequency',
                'operator': random.choice(['greater_than', 'equals']),
                'value': random.randint(1, 50),
                'weight': round(random.uniform(0.5, 1.0), 2)
            })
        
        # Location condition
        if random.choice([True, False]):
            conditions.append({
                'field': 'country',
                'operator': random.choice(['in', 'not_in']),
                'value': random.sample(['US', 'CA', 'GB', 'DE', 'FR', 'IT', 'ES'], random.randint(1, 3)),
                'weight': round(random.uniform(0.5, 1.0), 2)
            })
        
        return conditions


class FraudRiskProfileFactory(BaseFactory):
    """Factory for creating fraud risk profiles."""
    
    def get_defaults(self) -> Dict[str, Any]:
        """Get default risk profile values."""
        return {
            'user_id': self._get_random_user_id(),
            'current_risk_score': random.randint(0, 100),
            'previous_risk_score': random.randint(0, 100),
            'risk_level': random.choice([choice.value for choice in RiskLevel]),
            'risk_trend': random.choice(['increasing', 'decreasing', 'stable']),
            'risk_factors': self._generate_random_risk_factors(),
            'behavioral_patterns': self._generate_random_patterns(),
            'transaction_patterns': self._generate_random_patterns(),
            'device_patterns': self._generate_random_patterns(),
            'location_patterns': self._generate_random_patterns(),
            'recommendations': random.sample(
                ['monitor_closely', 'enhanced_verification', 'limit_transactions', 'manual_review'],
                random.randint(1, 3)
            ),
            'monitoring_level': random.choice(['low', 'medium', 'high', 'critical']),
            'next_review_date': timezone.now() + timedelta(days=random.randint(1, 90)),
            'metadata': {
                'created_by_factory': True,
                'factory_version': '1.0'
            }
        }
    
    def create(self, **kwargs) -> FraudRiskProfile:
        """Create a fraud risk profile."""
        data = self.merge_defaults(**kwargs)
        
        # Convert foreign key fields
        if 'user_id' in data and isinstance(data['user_id'], int):
            try:
                user = User.objects.get(id=data['user_id'])
                data['user'] = user
                del data['user_id']
            except User.DoesNotExist:
                user = self._create_test_user()
                data['user'] = user
                del data['user_id']
        
        return FraudRiskProfile.objects.create(**data)
    
    def create_high_risk_profile(self, **kwargs) -> FraudRiskProfile:
        """Create a high-risk profile."""
        defaults = {
            'current_risk_score': random.randint(70, 100),
            'risk_level': RiskLevel.HIGH.value,
            'risk_trend': 'increasing',
            'monitoring_level': 'critical'
        }
        defaults.update(kwargs)
        return self.create(**defaults)
    
    def _get_random_user_id(self) -> int:
        """Get random user ID."""
        users = User.objects.all()
        if users:
            return random.choice(users).id
        else:
            user = self._create_test_user()
            return user.id
    
    def _create_test_user(self) -> User:
        """Create a test user."""
        username = f"testuser_{uuid4().hex[:8]}"
        email = f"{username}@example.com"
        
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'first_name': self.faker.first_name(),
                'last_name': self.faker.last_name(),
                'is_active': True
            }
        )
        
        return user
    
    def _generate_random_risk_factors(self) -> Dict[str, Any]:
        """Generate random risk factors."""
        return {
            'account_age': random.randint(1, 365),
            'transaction_frequency': random.randint(1, 100),
            'average_amount': random.uniform(50, 5000),
            'suspicious_locations': random.randint(0, 10),
            'device_changes': random.randint(0, 5),
            'failed_authentications': random.randint(0, 20)
        }
    
    def _generate_random_patterns(self) -> Dict[str, Any]:
        """Generate random pattern data."""
        return {
            'pattern_type': random.choice(['temporal', 'behavioral', 'transactional']),
            'confidence': round(random.uniform(0.5, 1.0), 2),
            'frequency': random.randint(1, 100),
            'last_seen': (timezone.now() - timedelta(days=random.randint(1, 30))).isoformat()
        }


class TestDataFactory(BaseFactory):
    """Factory for creating comprehensive test data."""
    
    def __init__(self, config: Optional[FactoryConfig] = None):
        """Initialize test data factory."""
        super().__init__(config)
        self.case_factory = FraudCaseFactory(config)
        self.alert_factory = FraudAlertFactory(config)
        self.rule_factory = FraudRuleFactory(config)
        self.profile_factory = FraudRiskProfileFactory(config)
    
    def create_complete_dataset(self, user_count: int = 10, cases_per_user: int = 5) -> Dict[str, Any]:
        """
        Create a complete test dataset.
        
        Args:
            user_count: Number of test users to create
            cases_per_user: Number of fraud cases per user
            
        Returns:
            Created dataset summary
        """
        # Create test users
        users = self._create_test_users(user_count)
        
        # Create fraud cases
        cases = []
        for user in users:
            user_cases = self.case_factory.create_batch(cases_per_user, user=user)
            cases.extend(user_cases)
        
        # Create fraud alerts
        alerts = []
        for case in cases:
            # Create 1-3 alerts per case
            alert_count = random.randint(1, 3)
            case_alerts = self.alert_factory.create_batch(
                alert_count, 
                user=case.user,
                case_id=case.pk
            )
            alerts.extend(case_alerts)
        
        # Create risk profiles
        profiles = []
        for user in users:
            profile = self.profile_factory.create(user=user)
            profiles.append(profile)
        
        # Create fraud rules
        rules = self.rule_factory.create_batch(20)
        
        dataset = {
            'users': users,
            'cases': cases,
            'alerts': alerts,
            'profiles': profiles,
            'rules': rules,
            'summary': {
                'total_users': len(users),
                'total_cases': len(cases),
                'total_alerts': len(alerts),
                'total_profiles': len(profiles),
                'total_rules': len(rules)
            }
        }
        
        logger.info(f"Created complete test dataset: {dataset['summary']}")
        return dataset
    
    def create_scenario_data(self, scenario: str) -> Dict[str, Any]:
        """
        Create scenario-specific test data.
        
        Args:
            scenario: Scenario type
            
        Returns:
            Scenario data
        """
        if scenario == 'high_volume_fraud':
            return self._create_high_volume_scenario()
        elif scenario == 'sophisticated_attack':
            return self._create_sophisticated_attack_scenario()
        elif scenario == 'regulatory_breach':
            return self._create_regulatory_breach_scenario()
        elif scenario == 'money_laundering':
            return self._create_money_laundering_scenario()
        else:
            raise ValueError(f"Unknown scenario: {scenario}")
    
    def _create_test_users(self, count: int) -> List[User]:
        """Create test users."""
        users = []
        for i in range(count):
            username = f"testuser_{i}_{uuid4().hex[:6]}"
            email = f"{username}@example.com"
            
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': self.faker.first_name(),
                    'last_name': self.faker.last_name(),
                    'is_active': True,
                    'is_staff': random.choice([True, False]) if i < 2 else False
                }
            )
            users.append(user)
        
        return users
    
    def _create_high_volume_scenario(self) -> Dict[str, Any]:
        """Create high volume fraud scenario."""
        # Create user with many transactions/cases
        user = self._create_test_users(1)[0]
        
        # Create many cases
        cases = self.case_factory.create_batch(50, user=user)
        
        # Create many alerts
        alerts = []
        for case in cases:
            case_alerts = self.alert_factory.create_batch(
                random.randint(2, 5),
                user=user,
                case_id=case.pk
            )
            alerts.extend(case_alerts)
        
        return {
            'scenario': 'high_volume_fraud',
            'user': user,
            'cases': cases,
            'alerts': alerts,
            'summary': {
                'total_cases': len(cases),
                'total_alerts': len(alerts)
            }
        }
    
    def _create_sophisticated_attack_scenario(self) -> Dict[str, Any]:
        """Create sophisticated attack scenario."""
        user = self._create_test_users(1)[0]
        
        # Create sophisticated cases with high risk scores
        cases = []
        for _ in range(10):
            case = self.case_factory.create_high_risk_case(
                user=user,
                case_type=FraudType.ACCOUNT_TAKEOVER.value,
                severity=FraudSeverity.CRITICAL.value
            )
            cases.append(case)
        
        # Create critical alerts
        alerts = []
        for case in cases:
            alert = self.alert_factory.create_critical_alert(
                user=user,
                case_id=case.pk,
                alert_type=AlertType.SUSPICIOUS_ACTIVITY.value
            )
            alerts.append(alert)
        
        return {
            'scenario': 'sophisticated_attack',
            'user': user,
            'cases': cases,
            'alerts': alerts,
            'summary': {
                'total_cases': len(cases),
                'total_alerts': len(alerts)
            }
        }
    
    def _create_regulatory_breach_scenario(self) -> Dict[str, Any]:
        """Create regulatory breach scenario."""
        user = self._create_test_users(1)[0]
        
        # Create regulatory cases
        cases = []
        for _ in range(5):
            case = self.case_factory.create_regulatory_case(user=user)
            cases.append(case)
        
        return {
            'scenario': 'regulatory_breach',
            'user': user,
            'cases': cases,
            'summary': {
                'total_cases': len(cases)
            }
        }
    
    def _create_money_laundering_scenario(self) -> Dict[str, Any]:
        """Create money laundering scenario."""
        user = self._create_test_users(1)[0]
        
        # Create money laundering cases
        cases = []
        for _ in range(8):
            case = self.case_factory.create(
                user=user,
                case_type=FraudType.MONEY_LAUNDERING.value,
                severity=FraudSeverity.HIGH.value,
                financial_impact=Decimal(str(random.uniform(50000, 500000))),
                regulatory_impact=True
            )
            cases.append(case)
        
        return {
            'scenario': 'money_laundering',
            'user': user,
            'cases': cases,
            'summary': {
                'total_cases': len(cases)
            }
        }


# Factory manager for coordinating multiple factories
class FactoryManager:
    """Manager for coordinating multiple factories."""
    
    def __init__(self, config: Optional[FactoryConfig] = None):
        """Initialize factory manager."""
        self.config = config or FactoryConfig()
        self.factories = {}
        self._register_default_factories()
    
    def _register_default_factories(self):
        """Register default factories."""
        self.factories['case'] = FraudCaseFactory(self.config)
        self.factories['alert'] = FraudAlertFactory(self.config)
        self.factories['rule'] = FraudRuleFactory(self.config)
        self.factories['profile'] = FraudRiskProfileFactory(self.config)
        self.factories['test_data'] = TestDataFactory(self.config)
    
    def register_factory(self, name: str, factory: BaseFactory):
        """Register a factory."""
        self.factories[name] = factory
        logger.info(f"Registered factory: {name}")
    
    def get_factory(self, name: str) -> Optional[BaseFactory]:
        """Get factory by name."""
        return self.factories.get(name)
    
    def create(self, factory_name: str, **kwargs) -> Any:
        """Create object using specified factory."""
        factory = self.get_factory(factory_name)
        if not factory:
            raise ValueError(f"Factory not found: {factory_name}")
        
        return factory.create(**kwargs)
    
    def create_batch(self, factory_name: str, count: int, **kwargs) -> List[Any]:
        """Create batch of objects using specified factory."""
        factory = self.get_factory(factory_name)
        if not factory:
            raise ValueError(f"Factory not found: {factory_name}")
        
        return factory.create_batch(count, **kwargs)


# Global factory instances
default_factory_config = FactoryConfig()
factory_manager = FactoryManager(default_factory_config)

# Convenience functions
def create_fraud_case(**kwargs) -> FraudCase:
    """Create a fraud case using default factory."""
    return factory_manager.create('case', **kwargs)


def create_fraud_alert(**kwargs) -> FraudAlert:
    """Create a fraud alert using default factory."""
    return factory_manager.create('alert', **kwargs)


def create_fraud_rule(**kwargs) -> FraudRule:
    """Create a fraud rule using default factory."""
    return factory_manager.create('rule', **kwargs)


def create_risk_profile(**kwargs) -> FraudRiskProfile:
    """Create a risk profile using default factory."""
    return factory_manager.create('profile', **kwargs)


def create_test_dataset(**kwargs) -> Dict[str, Any]:
    """Create complete test dataset."""
    return factory_manager.factories['test_data'].create_complete_dataset(**kwargs)


def create_scenario(scenario: str) -> Dict[str, Any]:
    """Create scenario-specific test data."""
    return factory_manager.factories['test_data'].create_scenario_data(scenario)


# Export all factories and utilities
__all__ = [
    # Enums and data classes
    'FactoryType',
    'FactoryConfig',
    
    # Base factory
    'BaseFactory',
    
    # Specific factories
    'FraudCaseFactory',
    'FraudAlertFactory',
    'FraudRuleFactory',
    'FraudRiskProfileFactory',
    'TestDataFactory',
    
    # Factory manager
    'FactoryManager',
    
    # Global instances
    'factory_manager',
    'default_factory_config',
    
    # Convenience functions
    'create_fraud_case',
    'create_fraud_alert',
    'create_fraud_rule',
    'create_risk_profile',
    'create_test_dataset',
    'create_scenario',
]
