# earning_backend/api/notifications/viewsets/__init__.py
"""
Notifications viewsets package — 16 viewsets total (matches plan).
"""
from .NotificationViewSet import NotificationViewSet
from .InAppMessageViewSet import InAppMessageViewSet
from .PushDeviceViewSet import PushDeviceViewSet
from .NotificationCampaignViewSet import NotificationCampaignViewSet
from .CampaignABTestViewSet import CampaignABTestViewSet
from .NotificationScheduleViewSet import NotificationScheduleViewSet
from .NotificationBatchViewSet import NotificationBatchViewSet
from .OptOutViewSet import OptOutViewSet
from .NotificationInsightViewSet import NotificationInsightViewSet
from .DeliveryRateViewSet import DeliveryRateViewSet
from .AdminNotificationViewSet import AdminNotificationViewSet
from .NotificationTemplateViewSet import NotificationTemplateViewSet
from .NotificationPreferenceViewSet import NotificationPreferenceViewSet
from .NotificationRuleViewSet import NotificationRuleViewSet
from .NotificationLogViewSet import NotificationLogViewSet
from .NotificationFeedbackViewSet import NotificationFeedbackViewSet

__all__ = [
    'NotificationViewSet',
    'InAppMessageViewSet',
    'PushDeviceViewSet',
    'NotificationCampaignViewSet',
    'CampaignABTestViewSet',
    'NotificationScheduleViewSet',
    'NotificationBatchViewSet',
    'OptOutViewSet',
    'NotificationInsightViewSet',
    'DeliveryRateViewSet',
    'AdminNotificationViewSet',
    'NotificationTemplateViewSet',
    'NotificationPreferenceViewSet',
    'NotificationRuleViewSet',
    'NotificationLogViewSet',
    'NotificationFeedbackViewSet',
]
