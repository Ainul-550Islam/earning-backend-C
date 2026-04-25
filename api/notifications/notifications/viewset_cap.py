# earning_backend/api/notifications/viewset_cap.py
"""
ViewSet CAP (Capacity) — Viewset registry and capacity manager.
Tracks all registered viewsets and their URL prefixes.
"""
import logging
logger = logging.getLogger(__name__)

VIEWSET_REGISTRY = {
    'NotificationViewSet':           {'prefix': 'notifications',    'file': 'viewsets/NotificationViewSet.py'},
    'InAppMessageViewSet':           {'prefix': 'in-app-messages',  'file': 'viewsets/InAppMessageViewSet.py'},
    'PushDeviceViewSet':             {'prefix': 'push-devices',     'file': 'viewsets/PushDeviceViewSet.py'},
    'NotificationCampaignViewSet':   {'prefix': 'campaigns',        'file': 'viewsets/NotificationCampaignViewSet.py'},
    'CampaignABTestViewSet':         {'prefix': 'ab-tests',         'file': 'viewsets/CampaignABTestViewSet.py'},
    'NotificationScheduleViewSet':   {'prefix': 'schedules',        'file': 'viewsets/NotificationScheduleViewSet.py'},
    'NotificationBatchViewSet':      {'prefix': 'batches',          'file': 'viewsets/NotificationBatchViewSet.py'},
    'OptOutViewSet':                 {'prefix': 'opt-outs',         'file': 'viewsets/OptOutViewSet.py'},
    'NotificationInsightViewSet':    {'prefix': 'insights',         'file': 'viewsets/NotificationInsightViewSet.py'},
    'DeliveryRateViewSet':           {'prefix': 'delivery-rates',   'file': 'viewsets/DeliveryRateViewSet.py'},
    'AdminNotificationViewSet':      {'prefix': 'admin',            'file': 'viewsets/AdminNotificationViewSet.py'},
    'NotificationTemplateViewSet':   {'prefix': 'templates',        'file': 'viewsets/NotificationTemplateViewSet.py'},
    'NotificationPreferenceViewSet': {'prefix': 'preferences',      'file': 'viewsets/NotificationPreferenceViewSet.py'},
    'NotificationRuleViewSet':       {'prefix': 'rules',            'file': 'viewsets/NotificationRuleViewSet.py'},
    'NotificationLogViewSet':        {'prefix': 'logs',             'file': 'viewsets/NotificationLogViewSet.py'},
    'NotificationFeedbackViewSet':   {'prefix': 'feedbacks',        'file': 'viewsets/NotificationFeedbackViewSet.py'},
}


def list_viewsets() -> list:
    return list(VIEWSET_REGISTRY.keys())


def get_viewset_prefix(name: str) -> str:
    return VIEWSET_REGISTRY.get(name, {}).get('prefix', '')


def get_all_url_prefixes() -> list:
    return [v['prefix'] for v in VIEWSET_REGISTRY.values()]
