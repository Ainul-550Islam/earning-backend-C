"""
urls/webhooks_urls.py — NEWLY CREATED
Routes for webhook viewsets (webhooks.py + hooks.py).
"""
from django.urls import path
from api.alerts.viewsets.webhooks_views import WebhookViewSet, OutgoingWebhookViewSet

app_name = 'webhooks'

urlpatterns = [
    # ── Inbound/managed webhooks (webhooks.py) ──────────────────────────
    path('',                    WebhookViewSet.as_view({'get': 'list'}),              name='webhook-list'),
    path('register/',           WebhookViewSet.as_view({'post': 'register'}),         name='webhook-register'),
    path('unregister/',         WebhookViewSet.as_view({'post': 'unregister'}),       name='webhook-unregister'),
    path('get/',                WebhookViewSet.as_view({'get': 'get_webhook'}),       name='webhook-get'),
    path('send/',               WebhookViewSet.as_view({'post': 'send'}),             name='webhook-send'),
    path('test/',               WebhookViewSet.as_view({'post': 'test_webhook'}),     name='webhook-test'),
    path('stats/',              WebhookViewSet.as_view({'get': 'webhook_stats'}),     name='webhook-stats'),
    path('incoming/',           WebhookViewSet.as_view({'post': 'incoming'}),         name='webhook-incoming'),
    path('info/',               WebhookViewSet.as_view({'get': 'webhook_info'}),      name='webhook-info'),

    # ── Outgoing webhooks (hooks.py) ────────────────────────────────────
    path('outgoing/',           OutgoingWebhookViewSet.as_view({'get': 'list'}),      name='outgoing-list'),
    path('outgoing/trigger/',   OutgoingWebhookViewSet.as_view({'post': 'trigger_outgoing'}), name='outgoing-trigger'),
    path('outgoing/log/',       OutgoingWebhookViewSet.as_view({'get': 'event_log'}), name='outgoing-log'),
    path('outgoing/verify/',    OutgoingWebhookViewSet.as_view({'post': 'verify_signature'}), name='outgoing-verify'),
    path('outgoing/status/',    OutgoingWebhookViewSet.as_view({'get': 'delivery_status'}), name='outgoing-status'),
]
