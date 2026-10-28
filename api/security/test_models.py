"""
Security Model Tests
Canonical test definitions have been consolidated in tests/test_security_models.py
This module re-exports all test cases for backwards compatibility.
"""

from .tests.test_security_models import (
    DeviceInfoModelTest,
    TrustedDeviceModelTest,
    SecurityLogModelTest,
    UserBanModelTest,
    IPBlacklistModelTest,
    ThreatIntelligenceModelTest,
    SecurityIncidentModelTest,
    PasswordHistoryModelTest,
    SecurityPolicyModelTest,
    SecurityInsightModelTest,
    RiskScoreModelTest,
    GeolocationLogModelTest,
    UserSessionModelTest,
    SessionActivityModelTest,
    TwoFactorMethodModelTest,
    TwoFactorAttemptModelTest,
    TwoFactorRecoveryCodeModelTest,
    CountryModelTest,
    CountryBlockRuleModelTest,
    APIRateLimitModelTest,
    RateLimitLogModelTest,
    ClickTrackerModelTest,
    EnhancedClickTrackerModelTest,
    SecurityModelIntegrationTest,
)

__all__ = [
    'DeviceInfoModelTest', 'TrustedDeviceModelTest', 'SecurityLogModelTest',
    'UserBanModelTest', 'IPBlacklistModelTest', 'ThreatIntelligenceModelTest',
    'SecurityIncidentModelTest', 'PasswordHistoryModelTest', 'SecurityPolicyModelTest',
    'SecurityInsightModelTest', 'RiskScoreModelTest', 'GeolocationLogModelTest',
    'UserSessionModelTest', 'SessionActivityModelTest', 'TwoFactorMethodModelTest',
    'TwoFactorAttemptModelTest', 'TwoFactorRecoveryCodeModelTest', 'CountryModelTest',
    'CountryBlockRuleModelTest', 'APIRateLimitModelTest', 'RateLimitLogModelTest',
    'ClickTrackerModelTest', 'EnhancedClickTrackerModelTest', 'SecurityModelIntegrationTest',
]