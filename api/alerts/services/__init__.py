"""
Alerts Module - Consolidating Services

All business logic is consolidated into 10 services for better maintainability
and to eliminate duplicate code across the module.

Services:
1. AlertProcessingService - Alert processing and escalation
2. SystemHealthService - System health monitoring
3. ConfigurationService - Configuration validation
4. PerformanceService - Performance metrics
5. MaintenanceService - Cleanup and maintenance
6. TestingService - Rule and channel testing
7. EventService - Event handling
8. RegistryService - Service registry and singletons
9. StatisticsService - Statistics and analytics
10. RateLimitingService - Rate limiting

Usage:
    from api.alerts.services import AlertProcessingService
    result = AlertProcessingService.process_pending_alerts()
"""

from api.alerts.services.alert_processing import AlertProcessingService
from api.alerts.services.system_health import SystemHealthService
from api.alerts.services.configuration import ConfigurationService
from api.alerts.services.performance import PerformanceService
from api.alerts.services.maintenance import MaintenanceService
from api.alerts.services.testing import TestingService
from api.alerts.services.event_bus import EventService
from api.alerts.services.registry import RegistryService
from api.alerts.services.statistics import StatisticsService
from api.alerts.services.rate_limiting import RateLimitingService

# Backward-compatible names: celery_tasks.py, endpoint.py, hooks.py, events.py,
# and several tests import these directly from the package root (predates the
# 10-service consolidation above). Kept working rather than removed, per
# no-removal policy — see audit notes on api.alerts.services.core / .channel / .incident.
from api.alerts.services.core import (
    LegacyAlertProcessorService,
    AlertGroupService,
    AnalyticsService,
)
from api.alerts.services.channel import NotificationService
from api.alerts.services.incident.incident_manager import IncidentManager

# ChannelNotificationService was the old name for channel.py's NotificationService;
# no separate implementation exists under that name anywhere in the codebase.
ChannelNotificationService = NotificationService

__all__ = [
    'AlertProcessingService',
    'SystemHealthService',
    'ConfigurationService',
    'PerformanceService',
    'MaintenanceService',
    'TestingService',
    'EventService',
    'RegistryService',
    'StatisticsService',
    'RateLimitingService',
    'LegacyAlertProcessorService',
    'AlertGroupService',
    'AnalyticsService',
    'NotificationService',
    'ChannelNotificationService',
    'IncidentManager',
]
