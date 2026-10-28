"""
Enhanced Security Tests Package
Comprehensive test suite for all security components
Author: System Security Team
Version: 2.0.0
"""

# Import all test modules for easy discovery
from .test_security_models import *
from .test_middleware import *
from .test_vpn_detector import *
from .test_threat_intel import *
from .test_incident_service import *
from .test_trusted_device import *
from .test_password_policy import *
from .test_security_views import *
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass



__all__ = [
    # Test classes
    'DeviceInfoModelTest',
    'SecurityLogModelTest', 
    'UserBanModelTest',
    'RiskScoreModelTest',
    'ThreatIntelligenceModelTest',
    'SecurityIncidentModelTest',
    'TrustedDeviceModelTest',
    'PasswordHistoryModelTest',
    'SecurityPolicyModelTest',
    'SecurityInsightModelTest',
    
    # Middleware tests
    'SecurityHeadersMiddlewareTest',
    'RateLimitMiddlewareTest',
    'SecurityAuditMiddlewareTest',
    'VPNProxyDetectionMiddlewareTest',
    
    # Service tests
    'VPNDetectorTest',
    'ThreatIntelServiceTest',
    'IncidentServiceTest',
    'TrustedDeviceServiceTest',
    'PasswordHistoryServiceTest',
    'SecurityPolicyServiceTest',
    'SecurityInsightServiceTest',
    
    # View tests
    'DeviceInfoViewSetTest',
    'SecurityLogViewSetTest',
    'UserBanViewSetTest',
    'ThreatIntelligenceViewSetTest',
    'SecurityIncidentViewSetTest',
    'TrustedDeviceViewSetTest',
    'PasswordHistoryViewSetTest',
    'SecurityPolicyViewSetTest',
    'SecurityInsightViewSetTest',
]