# earning_backend/api/notifications/models/__init__.py
"""
Notifications models package.

Re-exports all models from _models_core.py (renamed from models.py to avoid
Python shadowing the models/ package directory) PLUS all new split models.

Usage:
    from notifications.models import (
        Notification, NotificationTemplate, NotificationPreference,
        DeviceToken, NotificationCampaign, NotificationLog,
        PushDevice, PushDeliveryLog, EmailDeliveryLog, SMSDeliveryLog, InAppMessage,
        NotificationSchedule, NotificationBatch, NotificationQueue, NotificationRetry,
        CampaignSegment, CampaignABTest, CampaignResult,
        NotificationInsight, DeliveryRate, OptOutTracking, NotificationFatigue,
    )
"""

# ---------------------------------------------------------------------------
# Core / legacy models from _models_core.py (formerly models.py)
# ---------------------------------------------------------------------------
from .._models_core import (  # noqa: F401
    Notification,
    NotificationTemplate,
    NotificationPreference,
    DeviceToken,
    NotificationCampaign,
    NotificationAnalytics,
    NotificationRule,
    NotificationFeedback,
    NotificationLog,
    Notice,
    NotificationCategory,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
)

# ---------------------------------------------------------------------------
# New channel models
# ---------------------------------------------------------------------------
from .channel import (  # noqa: F401
    PushDevice,
    PushDeliveryLog,
    EmailDeliveryLog,
    SMSDeliveryLog,
    InAppMessage,
)

# ---------------------------------------------------------------------------
# New schedule models
# ---------------------------------------------------------------------------
from .schedule import (  # noqa: F401
    NotificationSchedule,
    NotificationBatch,
    NotificationQueue as NotificationQueueModel,
    NotificationRetry,
)

# ---------------------------------------------------------------------------
# New campaign models
# ---------------------------------------------------------------------------
from .campaign import (  # noqa: F401
    CampaignSegment,
    CampaignABTest,
    CampaignResult,
    NotificationCampaign as NewNotificationCampaign,
)

# ---------------------------------------------------------------------------
# New analytics models
# ---------------------------------------------------------------------------
from .analytics import (  # noqa: F401
    NotificationInsight,
    DeliveryRate,
    OptOutTracking,
    NotificationFatigue,
)

__all__ = [
    # Core / legacy
    'Notification', 'NotificationTemplate', 'NotificationPreference',
    'DeviceToken', 'NotificationCampaign', 'NotificationAnalytics',
    'NotificationRule', 'NotificationFeedback', 'NotificationLog',
    'Notice', 'NotificationCategory', 'NotificationChannel',
    'NotificationPriority', 'NotificationStatus',
    # Channel
    'PushDevice', 'PushDeliveryLog', 'EmailDeliveryLog',
    'SMSDeliveryLog', 'InAppMessage',
    # Schedule
    'NotificationSchedule', 'NotificationBatch',
    'NotificationQueueModel', 'NotificationRetry',
    # Campaign (new)
    'CampaignSegment', 'CampaignABTest', 'CampaignResult',
    'NewNotificationCampaign',
    # Analytics
    'NotificationInsight', 'DeliveryRate', 'OptOutTracking', 'NotificationFatigue',
]
