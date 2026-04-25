# earning_backend/api/notifications/serializers/__init__.py
"""
Serializers package.
Imports from _serializers_core.py (renamed from serializers.py to avoid
Python package shadowing) and new model serializers.
"""
import importlib as _imp
_core = _imp.import_module('api.notifications._serializers_core')

# Re-export everything from the monolithic serializers
import sys as _sys
_this = _sys.modules[__name__]
for _name in dir(_core):
    if not _name.startswith('__'):
        setattr(_this, _name, getattr(_core, _name))
del _imp, _core, _sys, _this, _name

# New model serializers
from .new_models_serializers import (  # noqa: F401
    PushDeviceSerializer, RegisterPushDeviceSerializer,
    PushDeliveryLogSerializer, EmailDeliveryLogSerializer,
    SMSDeliveryLogSerializer, InAppMessageSerializer,
    NotificationScheduleSerializer, CreateNotificationScheduleSerializer,
    NotificationBatchSerializer, CreateNotificationBatchSerializer,
    NotificationQueueSerializer, NotificationRetrySerializer,
    CampaignSegmentSerializer, NewNotificationCampaignSerializer,
    CreateNewCampaignSerializer, CampaignABTestSerializer,
    CampaignResultSerializer, NotificationInsightSerializer,
    DeliveryRateSerializer, OptOutTrackingSerializer,
    OptOutRequestSerializer, NotificationFatigueSerializer,
    UserNotificationStatusSerializer,
)
