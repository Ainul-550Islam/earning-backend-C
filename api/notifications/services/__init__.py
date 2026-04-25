# earning_backend/api/notifications/services/__init__.py
"""
Notifications services package.

Exposes all service singletons for easy import throughout the project.
The monolithic service logic lives in _services_core.py (renamed from services.py
to avoid Python shadowing the services/ package directory).

Usage:
    from notifications.services import (
        notification_service, template_service, rule_service,
        analytics_service, preferences_service, device_service,
        feedback_service, notification_dispatcher, fatigue_service,
        opt_out_service, delivery_tracker,
    )
"""

# ---------------------------------------------------------------------------
# 1. Import existing singletons from the monolithic _services_core.py
#    (renamed from services.py to unblock the services/ package directory)
# ---------------------------------------------------------------------------
from .._services_core import (  # noqa: F401
    notification_service,
    template_service,
    rule_service,
    analytics_service,
    preferences_service,
    device_service,
    feedback_service,
)

# ---------------------------------------------------------------------------
# 2. Import new split-service singletons
# ---------------------------------------------------------------------------
from .NotificationDispatcher import notification_dispatcher  # noqa: F401
from .FatigueService import fatigue_service                  # noqa: F401
from .OptOutService import opt_out_service                   # noqa: F401
from .DeliveryTracker import delivery_tracker                # noqa: F401
from .CampaignService import campaign_service                # noqa: F401
from .SegmentService import segment_service                  # noqa: F401
from .ABTestService import ab_test_service                   # noqa: F401
from .NotificationAnalytics import notification_analytics_service  # noqa: F401
from .NotificationQueue import notification_queue_service    # noqa: F401

__all__ = [
    # Existing singletons
    'notification_service',
    'template_service',
    'rule_service',
    'analytics_service',
    'preferences_service',
    'device_service',
    'feedback_service',
    # New singletons
    'notification_dispatcher',
    'fatigue_service',
    'opt_out_service',
    'delivery_tracker',
    'campaign_service',
    'segment_service',
    'ab_test_service',
    'notification_analytics_service',
    'notification_queue_service',
]

from .SmartSendTimeService import smart_send_time_service  # noqa: F401

from .JourneyService import journey_service  # noqa: F401
