"""
Security View Tests
Canonical test definitions have been consolidated in tests/test_security_views.py
This module re-exports all test cases for backwards compatibility.
"""

from .tests.test_security_views import (
    DeviceInfoViewSetTest,
    SecurityLogViewSetTest,
    UserBanViewSetTest,
    RiskScoreViewSetTest,
    ThreatIntelligenceViewSetTest,
    SecurityIncidentViewSetTest,
    TrustedDeviceViewSetTest,
    PasswordHistoryViewSetTest,
    SecurityPolicyViewSetTest,
    SecurityInsightViewSetTest,
    SecurityViewsIntegrationTest,
)

__all__ = [
    'DeviceInfoViewSetTest', 'SecurityLogViewSetTest', 'UserBanViewSetTest',
    'RiskScoreViewSetTest', 'ThreatIntelligenceViewSetTest', 'SecurityIncidentViewSetTest',
    'TrustedDeviceViewSetTest', 'PasswordHistoryViewSetTest', 'SecurityPolicyViewSetTest',
    'SecurityInsightViewSetTest', 'SecurityViewsIntegrationTest',
]