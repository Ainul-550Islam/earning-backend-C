# """
# Fraud Detection Module for Earnify Platform

# This module provides comprehensive fraud detection capabilities including:
# - Multi-account detection
# - VPN/Proxy detection
# - Click fraud detection
# - Device fingerprinting
# - Pattern analysis
# - Automated banning and review systems
# """

# __version__ = "1.0.0"
# __author__ = "Earnify Security Team"

# default_app_config = 'fraud_detection.apps.FraudDetectionConfig'

# # Import main components
# from .detectors import (
#     BaseDetector,
#     MultiAccountDetector,
#     VPNProxyDetector,
#     ClickFraudDetector,
#     DeviceFingerprinter,
#     PatternAnalyzer
# )

# from .services import (
#     FraudScoreCalculator,
#     AutoBanService,
#     ReviewService
# )

# # Import models for convenience
# from .models import (
#     FraudRule,
#     FraudAttempt,
#     FraudPattern,
#     UserRiskProfile,
#     DeviceFingerprint,
#     IPReputation,
#     FraudAlert
# )

# __all__ = [
#     # Detectors
#     'BaseDetector',
#     'MultiAccountDetector',
#     'VPNProxyDetector',
#     'ClickFraudDetector',
#     'DeviceFingerprinter',
#     'PatternAnalyzer',
    
#     # Services
#     'FraudScoreCalculator',
#     'AutoBanService',
#     'ReviewService',
    
#     # Models
#     'FraudRule',
#     'FraudAttempt',
#     'FraudPattern',
#     'UserRiskProfile',
#     'DeviceFingerprint',
#     'IPReputation',
#     'FraudAlert'
# ]
"""
Fraud Detection Module for Earnify Platform
"""

__version__ = "1.0.0"
__author__ = "Earnify Security Team"

default_app_config = 'api.fraud_detection.apps.FraudDetectionConfig'