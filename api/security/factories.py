"""
Security Model Factories
Canonical factory definitions have been consolidated in tests/factories.py
This module re-exports all factories for backwards compatibility.
"""

from .tests.factories import (
    UserFactory,
    StaffUserFactory,
    SuperUserFactory,
    DeviceInfoFactory,
    TrustedDeviceFactory,
    SecurityLogFactory,
    UserBanFactory,
    IPBlacklistFactory,
    ThreatIntelligenceFactory,
    SecurityIncidentFactory,
    PasswordHistoryFactory,
    SecurityPolicyFactory,
    SecurityInsightFactory,
    RiskScoreFactory,
    GeolocationLogFactory,
    UserSessionFactory,
    SessionActivityFactory,
    TwoFactorMethodFactory,
    TwoFactorAttemptFactory,
    TwoFactorRecoveryCodeFactory,
    CountryFactory,
    CountryBlockRuleFactory,
    APIRateLimitFactory,
    RateLimitLogFactory,
    ClickTrackerFactory,
    EnhancedClickTrackerFactory,
)

__all__ = [
    'UserFactory', 'StaffUserFactory', 'SuperUserFactory',
    'DeviceInfoFactory', 'TrustedDeviceFactory', 'SecurityLogFactory',
    'UserBanFactory', 'IPBlacklistFactory', 'ThreatIntelligenceFactory',
    'SecurityIncidentFactory', 'PasswordHistoryFactory', 'SecurityPolicyFactory',
    'SecurityInsightFactory', 'RiskScoreFactory', 'GeolocationLogFactory',
    'UserSessionFactory', 'SessionActivityFactory', 'TwoFactorMethodFactory',
    'TwoFactorAttemptFactory', 'TwoFactorRecoveryCodeFactory',
    'CountryFactory', 'CountryBlockRuleFactory', 'APIRateLimitFactory',
    'RateLimitLogFactory', 'ClickTrackerFactory', 'EnhancedClickTrackerFactory',
]