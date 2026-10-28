# =============================================================================
# fraud_detection/tests/factories.py
# =============================================================================
"""
Fraud Detection Test Factories.

Factory classes for creating test data for fraud detection models
and services with realistic data generation.
"""

import json
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import factory
from factory import fuzzy
from django.utils import timezone

from api.fraud_detection.models import (
    FraudAttempt, FraudAlert, FraudCase, FraudCaseEvidence, 
    FraudCaseAction, FraudWhitelist, UserRiskProfile, DeviceFingerprint,
    IPReputation, OfferCompletion, FraudPattern, FraudSettings
)
from api.fraud_detection.choices import (
    RuleType, SeverityLevel, ActionOnTrigger,
    FraudAlertType, NotificationType, EvidenceType, CaseStatus,
    WhitelistType, FraudAttemptStatus, FraudAttemptType,
    PatternType, MonitoringLevel, CompletionStatus, AlertPriority
)


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for User model."""
    
    class Meta:
        model = 'auth.User'
        django_get_or_create = ('username',)
    
    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    is_staff = False
    
    @classmethod
    def create_staff(cls, **kwargs):
        """Create a staff user."""
        return cls.create(is_staff=True, **kwargs)


class FraudRuleFactory(factory.django.DjangoModelFactory):
    """Factory for FraudRule model."""
    
    class Meta:
        model = 'fraud_detection.FraudRule'
        django_get_or_create = ('name',)
    
    name = factory.Sequence(lambda n: f"rule_{n}")
    rule_type = fuzzy.FuzzyChoice([choice[0] for choice in RuleType.choices])
    severity = fuzzy.FuzzyChoice([choice[0] for choice in SeverityLevel.choices])
    description = factory.Faker('text', max_nb_chars=200)
    weight = fuzzy.FuzzyInteger(1, 100)
    threshold = fuzzy.FuzzyInteger(1, 100)
    is_active = True
    condition = factory.LazyAttribute(lambda obj: json.dumps({
        'field': 'amount',
        'operator': '>',
        'value': 1000
    }))
    action_on_trigger = fuzzy.FuzzyChoice([choice[0] for choice in ActionOnTrigger.choices])


class FraudAttemptFactory(factory.django.DjangoModelFactory):
    """Factory for FraudAttempt model."""
    
    class Meta:
        model = 'fraud_detection.FraudAttempt'
    
    attempt_id = factory.Sequence(lambda n: f"attempt_{n}")
    user = factory.SubFactory(UserFactory)
    attempt_type = fuzzy.FuzzyChoice([choice[0] for choice in FraudAttemptType.choices])
    description = factory.Faker('text', max_nb_chars=500)
    detected_by = fuzzy.FuzzyChoice(['middleware', 'detector_click_fraud', 'detector_multi_account'])
    fraud_score = fuzzy.FuzzyInteger(0, 100)
    confidence_score = fuzzy.FuzzyInteger(50, 100)
    status = fuzzy.FuzzyChoice([choice[0] for choice in FraudAttemptStatus.choices])
    evidence_data = factory.LazyAttribute(lambda obj: json.dumps({
        'ip_address': factory.Faker('ipv4'),
        'user_agent': factory.Faker('user_agent'),
        'timestamp': timezone.now().isoformat(),
    }))
    amount_involved = fuzzy.FuzzyDecimal(0, 10000, 2)


class FraudAlertFactory(factory.django.DjangoModelFactory):
    """Factory for FraudAlert model."""
    
    class Meta:
        model = 'fraud_detection.FraudAlert'
    
    user = factory.SubFactory(UserFactory)
    alert_type = fuzzy.FuzzyChoice([choice[0] for choice in FraudAlertType.choices])
    priority = fuzzy.FuzzyChoice([choice[0] for choice in AlertPriority.choices])
    title = factory.Faker('sentence', nb_words=6)
    description = factory.Faker('text', max_nb_chars=500)
    data = factory.LazyAttribute(lambda obj: json.dumps({
        'source': 'automated_detection',
        'timestamp': timezone.now().isoformat(),
    }))
    is_resolved = fuzzy.FuzzyChoice([True, False])
    resolved_at = factory.Maybe(
        'is_resolved',
        yes_declaration=factory.LazyFunction(lambda: timezone.now() - timedelta(hours=random.randint(1, 24))),
        no_declaration=None,
    )


class UserRiskProfileFactory(factory.django.DjangoModelFactory):
    """Factory for UserRiskProfile model."""
    
    class Meta:
        model = 'fraud_detection.UserRiskProfile'
        django_get_or_create = ('user',)
    
    user = factory.SubFactory(UserFactory)
    overall_risk_score = fuzzy.FuzzyInteger(0, 100)
    monitoring_level = fuzzy.FuzzyChoice([choice[0] for choice in MonitoringLevel.choices])
    is_flagged = fuzzy.FuzzyChoice([True, False])
    is_restricted = fuzzy.FuzzyChoice([True, False])
    total_fraud_attempts = fuzzy.FuzzyInteger(0, 50)
    confirmed_fraud_attempts = fuzzy.FuzzyInteger(0, 20)
    false_positives = fuzzy.FuzzyInteger(0, 10)
    last_risk_assessment = timezone.now() - timedelta(hours=random.randint(1, 72))


class DeviceFingerprintFactory(factory.django.DjangoModelFactory):
    """Factory for DeviceFingerprint model."""
    
    class Meta:
        model = 'fraud_detection.DeviceFingerprint'
        django_get_or_create = ('device_hash',)
    
    user = factory.SubFactory(UserFactory)
    device_hash = factory.Sequence(lambda n: f"device_hash_{n}")
    device_type = fuzzy.FuzzyChoice(['desktop', 'mobile', 'tablet'])
    trust_score = fuzzy.FuzzyInteger(0, 100)
    user_agent = factory.Faker('user_agent')
    screen_resolution = fuzzy.FuzzyChoice(['1920x1080', '1366x768', '1440x900', '1280x720'])
    timezone = fuzzy.FuzzyChoice(['UTC', 'America/New_York', 'Europe/London', 'Asia/Tokyo'])
    language = fuzzy.FuzzyChoice(['en-US', 'en-GB', 'es-ES', 'fr-FR'])
    platform = fuzzy.FuzzyChoice(['Win32', 'MacIntel', 'Linux x86_64', 'iPhone'])
    browser = fuzzy.FuzzyChoice(['Chrome', 'Firefox', 'Safari', 'Edge'])
    is_vpn = fuzzy.FuzzyChoice([True, False])
    is_proxy = fuzzy.FuzzyChoice([True, False])
    is_tor = fuzzy.FuzzyChoice([True, False])
    last_seen = timezone.now() - timedelta(hours=random.randint(1, 168))


class IPReputationFactory(factory.django.DjangoModelFactory):
    """Factory for IPReputation model."""
    
    class Meta:
        model = 'fraud_detection.IPReputation'
        django_get_or_create = ('ip_address',)
    
    ip_address = factory.Faker('ipv4')
    fraud_score = fuzzy.FuzzyInteger(0, 100)
    spam_score = fuzzy.FuzzyInteger(0, 100)
    malware_score = fuzzy.FuzzyInteger(0, 100)
    total_requests = fuzzy.FuzzyInteger(0, 10000)
    fraud_attempts = fuzzy.FuzzyInteger(0, 100)
    unique_users = fuzzy.FuzzyInteger(0, 50)
    is_blacklisted = fuzzy.FuzzyChoice([True, False])
    blacklist_reason = factory.Maybe(
        'is_blacklisted',
        yes_declaration=factory.Faker('sentence', nb_words=8),
        no_declaration='',
    )
    country = fuzzy.FuzzyChoice(['US', 'GB', 'CA', 'AU', 'DE', 'FR', 'JP', 'CN'])
    region = factory.Faker('state')
    city = factory.Faker('city')
    last_seen = timezone.now() - timedelta(hours=random.randint(1, 72))


class FraudCaseFactory(factory.django.DjangoModelFactory):
    """Factory for FraudCase model."""
    
    class Meta:
        model = 'fraud_detection.FraudCase'
        django_get_or_create = ('case_number',)
    
    user = factory.SubFactory(UserFactory)
    case_number = factory.Sequence(lambda n: f"FC-20240424-{n:03d}")
    title = factory.Faker('sentence', nb_words=8)
    description = factory.Faker('text', max_nb_chars=1000)
    risk_score = fuzzy.FuzzyInteger(0, 100)
    priority = fuzzy.FuzzyChoice(['low', 'medium', 'high', 'critical'])
    status = fuzzy.FuzzyChoice([choice[0] for choice in CaseStatus.choices])
    opened_at = timezone.now() - timedelta(hours=random.randint(1, 168))
    assigned_to = factory.Maybe(
        fuzzy.FuzzyChoice([True, False]),
        yes_declaration=factory.SubFactory(UserFactory, is_staff=True),
        no_declaration=None,
    )
    resolved_at = factory.Maybe(
        fuzzy.FuzzyChoice([True, False]),
        yes_declaration=factory.LazyFunction(lambda: timezone.now() - timedelta(hours=random.randint(1, 24))),
        no_declaration=None,
    )
    resolution_notes = factory.Maybe(
        fuzzy.FuzzyChoice([True, False]),
        yes_declaration=factory.Faker('text', max_nb_chars=500),
        no_declaration='',
    )


class FraudCaseEvidenceFactory(factory.django.DjangoModelFactory):
    """Factory for FraudCaseEvidence model."""
    
    class Meta:
        model = 'fraud_detection.FraudCaseEvidence'
    
    fraud_case = factory.SubFactory(FraudCaseFactory)
    evidence_type = fuzzy.FuzzyChoice([choice[0] for choice in EvidenceType.choices])
    data = factory.LazyAttribute(lambda obj: json.dumps({
        'timestamp': timezone.now().isoformat(),
        'source': 'automated_detection',
        'details': factory.Faker('text', max_nb_chars=300),
    }))
    added_by = fuzzy.FuzzyChoice(['System', 'Admin', 'Investigator'])
    metadata = factory.LazyAttribute(lambda obj: json.dumps({
        'verified': True,
        'confidence': random.uniform(0.7, 1.0),
    }))


class FraudCaseActionFactory(factory.django.DjangoModelFactory):
    """Factory for FraudCaseAction model."""
    
    class Meta:
        model = 'fraud_detection.FraudCaseAction'
    
    fraud_case = factory.SubFactory(FraudCaseFactory)
    action_type = fuzzy.FuzzyChoice([
        'create', 'assign', 'escalate', 'investigate', 'review',
        'resolve', 'close', 'reopen', 'priority_change', 'note'
    ])
    note = factory.Faker('text', max_nb_chars=500)
    performed_by = factory.SubFactory(UserFactory, is_staff=True)
    is_completed = fuzzy.FuzzyChoice([True, False])
    completed_at = factory.Maybe(
        'is_completed',
        yes_declaration=factory.LazyFunction(lambda: timezone.now() - timedelta(minutes=random.randint(1, 1440))),
        no_declaration=None,
    )
    metadata = factory.LazyAttribute(lambda obj: json.dumps({
        'duration_minutes': random.randint(5, 120),
    }))


class FraudWhitelistFactory(factory.django.DjangoModelFactory):
    """Factory for FraudWhitelist model."""
    
    class Meta:
        model = 'fraud_detection.FraudWhitelist'
        django_get_or_create = ('entity_value', 'entity_type')
    
    entity_type = fuzzy.FuzzyChoice([choice[0] for choice in WhitelistType.choices])
    entity_value = factory.LazyAttribute(lambda obj: {
        'user': f"user_{random.randint(1000, 9999)}",
        'ip_address': factory.Faker('ipv4'),
        'device': f"device_{random.randint(1000, 9999)}",
        'domain': f"example{random.randint(1, 100)}.com",
        'email': f"user{random.randint(1000, 9999)}@example.com",
    }.get(obj.entity_type, f"value_{random.randint(1000, 9999)}"))
    reason = factory.Faker('text', max_nb_chars=500)
    is_blacklisted = fuzzy.FuzzyChoice([True, False])
    is_active = True
    expires_at = factory.Maybe(
        fuzzy.FuzzyChoice([True, False]),
        yes_declaration=factory.LazyFunction(lambda: timezone.now() + timedelta(days=random.randint(1, 365))),
        no_declaration=None,
    )
    metadata = factory.LazyAttribute(lambda obj: json.dumps({
        'source': 'manual',
        'confidence': random.uniform(0.8, 1.0),
    }))


class OfferCompletionFactory(factory.django.DjangoModelFactory):
    """Factory for OfferCompletion model."""
    
    class Meta:
        model = 'fraud_detection.OfferCompletion'
    
    user = factory.SubFactory(UserFactory)
    offer_id = factory.Sequence(lambda n: f"offer_{n}")
    reward_amount = fuzzy.FuzzyDecimal(0.01, 100.00, 2)
    status = fuzzy.FuzzyChoice([choice[0] for choice in CompletionStatus.choices])
    tracked_at = timezone.now() - timedelta(hours=random.randint(1, 72))
    completed_at = factory.Maybe(
        fuzzy.FuzzyChoice([True, False]),
        yes_declaration=factory.LazyFunction(lambda: timezone.now() - timedelta(minutes=random.randint(1, 1440))),
        no_declaration=None,
    )


class FraudPatternFactory(factory.django.DjangoModelFactory):
    """Factory for FraudPattern model."""
    
    class Meta:
        model = 'fraud_detection.FraudPattern'
        django_get_or_create = ('pattern_type', 'name')
    
    pattern_type = fuzzy.FuzzyChoice([choice[0] for choice in PatternType.choices])
    name = factory.Sequence(lambda n: f"pattern_{n}")
    description = factory.Faker('text', max_nb_chars=500)
    features = factory.LazyAttribute(lambda obj: [
        f"feature_{i}" for i in range(random.randint(5, 20))
    ])
    is_trained = fuzzy.FuzzyChoice([True, False])
    accuracy_rate = fuzzy.FuzzyFloat(0.5, 1.0)
    occurrence_count = fuzzy.FuzzyInteger(10, 10000)
    last_trained = factory.Maybe(
        fuzzy.FuzzyChoice([True, False]),
        yes_declaration=factory.LazyFunction(lambda: timezone.now() - timedelta(days=random.randint(1, 30))),
        no_declaration=None,
    )
    model_version = factory.Sequence(lambda n: f"v1.{n}")


class FraudSettingsFactory(factory.django.DjangoModelFactory):
    """Factory for FraudSettings model."""
    
    class Meta:
        model = 'fraud_detection.FraudSettings'
        django_get_or_create = ('key',)
    
    key = factory.Sequence(lambda n: f"setting_{n}")
    value = factory.LazyAttribute(lambda obj: json.dumps({
        'enabled': random.choice([True, False]),
        'threshold': random.randint(1, 100),
        'weight': random.randint(1, 10),
    }))
    description = factory.Faker('text', max_nb_chars=200)
    is_active = True


# =============================================================================
# Specialized Factories for Testing
# =============================================================================

class HighRiskUserRiskProfileFactory(UserRiskProfileFactory):
    """Factory for high-risk user profiles."""
    
    overall_risk_score = fuzzy.FuzzyInteger(70, 100)
    is_flagged = True
    monitoring_level = 'strict'


class BlacklistedIPReputationFactory(IPReputationFactory):
    """Factory for blacklisted IP addresses."""
    
    fraud_score = fuzzy.FuzzyInteger(80, 100)
    is_blacklisted = True
    blacklist_reason = factory.Faker('sentence', nb_words=8)


class SuspiciousDeviceFingerprintFactory(DeviceFingerprintFactory):
    """Factory for suspicious device fingerprints."""
    
    trust_score = fuzzy.FuzzyInteger(0, 30)
    is_vpn = fuzzy.FuzzyChoice([True, False])
    is_proxy = fuzzy.FuzzyChoice([True, False])


class CriticalFraudCaseFactory(FraudCaseFactory):
    """Factory for critical fraud cases."""
    
    risk_score = fuzzy.FuzzyInteger(80, 100)
    priority = 'critical'
    status = 'open'


class ConfirmedFraudAttemptFactory(FraudAttemptFactory):
    """Factory for confirmed fraud attempts."""
    
    fraud_score = fuzzy.FuzzyInteger(70, 100)
    confidence_score = fuzzy.FuzzyInteger(85, 100)
    status = 'confirmed'


class CriticalFraudAlertFactory(FraudAlertFactory):
    """Factory for critical fraud alerts."""
    
    priority = 'critical'
    is_resolved = False


# =============================================================================
# Data Generation Helpers
# =============================================================================

class FraudTestDataGenerator:
    """Helper class for generating test data scenarios."""
    
    @staticmethod
    def create_fraud_scenario(user_count: int = 10, days: int = 30) -> Dict[str, Any]:
        """Create a complete fraud scenario with related data."""
        users = UserFactory.create_batch(user_count, is_staff=False)
        staff_user = UserFactory.create_staff()
        
        # Create user risk profiles
        risk_profiles = []
        for user in users:
            if random.random() < 0.3:  # 30% high risk users
                profile = HighRiskUserRiskProfileFactory.create(user=user)
            else:
                profile = UserRiskProfileFactory.create(user=user)
            risk_profiles.append(profile)
        
        # Create fraud attempts
        attempts = []
        for user in users:
            attempt_count = random.randint(0, 5)
            for _ in range(attempt_count):
                if random.random() < 0.4:  # 40% confirmed fraud
                    attempt = ConfirmedFraudAttemptFactory.create(user=user)
                else:
                    attempt = FraudAttemptFactory.create(user=user)
                attempts.append(attempt)
        
        # Create cases for high-risk attempts
        cases = []
        for attempt in attempts:
            if attempt.fraud_score >= 70 and random.random() < 0.8:  # 80% of high-risk attempts become cases
                case = CriticalFraudCaseFactory.create(user=attempt.user)
                case.fraud_attempts.add(attempt)
                cases.append(case)
        
        # Create alerts
        alerts = []
        for attempt in attempts:
            if attempt.fraud_score >= 60 and random.random() < 0.7:  # 70% of medium+ risk attempts create alerts
                alert = CriticalFraudAlertFactory.create(user=attempt.user)
                alerts.append(alert)
        
        return {
            'users': users,
            'staff_user': staff_user,
            'risk_profiles': risk_profiles,
            'attempts': attempts,
            'cases': cases,
            'alerts': alerts,
        }
    
    @staticmethod
    def create_ip_reputation_scenario(ip_count: int = 50) -> Dict[str, Any]:
        """Create IP reputation scenario with mix of clean and risky IPs."""
        # Mix of clean and risky IPs
        clean_ips = IPReputationFactory.create_batch(
            ip_count // 2,
            fraud_score=fuzzy.FuzzyInteger(0, 30),
            is_blacklisted=False
        )
        
        risky_ips = []
        for _ in range(ip_count // 2):
            if random.random() < 0.3:  # 30% blacklisted
                ip = BlacklistedIPReputationFactory.create()
            else:
                ip = IPReputationFactory.create(
                    fraud_score=fuzzy.FuzzyInteger(40, 80)
                )
            risky_ips.append(ip)
        
        return {
            'clean_ips': clean_ips,
            'risky_ips': risky_ips,
            'all_ips': clean_ips + risky_ips,
        }
    
    @staticmethod
    def create_device_fingerprint_scenario(device_count: int = 30) -> Dict[str, Any]:
        """Create device fingerprint scenario with mix of trust levels."""
        # Mix of trusted and suspicious devices
        trusted_devices = DeviceFingerprintFactory.create_batch(
            device_count // 2,
            trust_score=fuzzy.FuzzyInteger(70, 100),
            is_vpn=False,
            is_proxy=False
        )
        
        suspicious_devices = []
        for _ in range(device_count // 2):
            device = SuspiciousDeviceFingerprintFactory.create()
            suspicious_devices.append(device)
        
        return {
            'trusted_devices': trusted_devices,
            'suspicious_devices': suspicious_devices,
            'all_devices': trusted_devices + suspicious_devices,
        }
    
    @staticmethod
    def create_whitelist_scenario(entry_count: int = 20) -> Dict[str, Any]:
        """Create whitelist scenario with both whitelisted and blacklisted entries."""
        whitelisted = FraudWhitelistFactory.create_batch(
            entry_count // 2,
            is_blacklisted=False
        )
        
        blacklisted = FraudWhitelistFactory.create_batch(
            entry_count // 2,
            is_blacklisted=True
        )
        
        return {
            'whitelisted': whitelisted,
            'blacklisted': blacklisted,
            'all_entries': whitelisted + blacklisted,
        }
