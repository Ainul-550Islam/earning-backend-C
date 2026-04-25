# earning_backend/api/notifications/models/__init__.py
"""
Notifications models package.

Re-exports all models from _models_core.py (renamed from models.py to avoid
Python shadowing the models/ package directory) PLUS all new split models.

Usage:
    from api.notifications.models import (
        Notification, NotificationTemplate, NotificationPreference,
        DeviceToken, NotificationCampaign, NotificationLog,
        PushDevice, PushDeliveryLog, EmailDeliveryLog, SMSDeliveryLog, InAppMessage,
        NotificationSchedule, NotificationBatch, NotificationQueue, NotificationRetry,
        CampaignSegment, CampaignABTest, CampaignResult,
        NotificationInsight, DeliveryRate, OptOutTracking, NotificationFatigue,
    )
"""

# ---------------------------------------------------------------------------
# Core models from _models_core.py
from .._models_core import (  # noqa: F401
    Notification,
    NotificationTemplate,
    NotificationPreference,
    DeviceToken,
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
# New campaign models — NotificationCampaign lives HERE (single source of truth)
# ---------------------------------------------------------------------------
from .campaign import (  # noqa: F401
    CampaignSegment,
    CampaignABTest,
    CampaignResult,
    NotificationCampaign,
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
    'DeviceToken', 'NotificationAnalytics',
    'NotificationRule', 'NotificationFeedback', 'NotificationLog',
    'Notice', 'NotificationCategory', 'NotificationChannel',
    'NotificationPriority', 'NotificationStatus',
    # Channel
    'PushDevice', 'PushDeliveryLog', 'EmailDeliveryLog',
    'SMSDeliveryLog', 'InAppMessage',
    # Schedule
    'NotificationSchedule', 'NotificationBatch',
    'NotificationQueueModel', 'NotificationRetry',
    # Campaign (single source of truth)
    'NotificationCampaign', 'CampaignSegment', 'CampaignABTest', 'CampaignResult',
    # Analytics
    'NotificationInsight', 'DeliveryRate', 'OptOutTracking', 'NotificationFatigue',
]
