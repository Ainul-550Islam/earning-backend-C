"""
api.postback - Enterprise-grade postback processing and analytics module.

This module provides comprehensive postback handling with security, analytics,
and monitoring capabilities for high-volume webhook processing.

Key Features:
- SHA-256 integrity hashing for tamper detection
- Advanced analytics with anomaly detection
- Template management system
- IP whitelist and rate limiting
- Comprehensive audit trails
- Real-time monitoring and alerting

Main Components:
- Models: Core data structures for postback processing
- Services: Business logic and analytics
- Views/ViewSets: REST API endpoints
- Utils: Security and validation utilities
- Management Commands: Maintenance and aggregation tasks
"""


# Version and metadata
__version__ = "2.0.0"
__author__ = "Postback Module Team"
__description__ = "Enterprise-grade postback processing and analytics"

# Public API
__all__ = []