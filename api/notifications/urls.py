# earning_backend/api/notifications/urls.py
"""
Notifications URL configuration — full router with all 16 viewsets.
Keeps ALL existing routes + adds new split viewset routes.
"""
from django.urls import path, include
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers
import json as _json

from . import views
from .viewsets import (
    NotificationViewSet,
    InAppMessageViewSet,
    PushDeviceViewSet,
    NotificationCampaignViewSet as NewNotificationCampaignViewSet,
    CampaignABTestViewSet,
    NotificationScheduleViewSet,
    NotificationBatchViewSet,
    OptOutViewSet,
    NotificationInsightViewSet,
    DeliveryRateViewSet,
    AdminNotificationViewSet as NewAdminNotificationViewSet,
    NotificationTemplateViewSet as NewNotificationTemplateViewSet,
    NotificationPreferenceViewSet as NewNotificationPreferenceViewSet,
    NotificationRuleViewSet as NewNotificationRuleViewSet,
    NotificationLogViewSet as NewNotificationLogViewSet,
    NotificationFeedbackViewSet as NewNotificationFeedbackViewSet,
)

app_name = "notifications"

# ---------------------------------------------------------------------------
# Primary router
# ---------------------------------------------------------------------------
router = DefaultRouter()

# --- Existing registrations (DO NOT REMOVE) ---
router.register(r"notifications", views.NotificationViewSet, basename="notification")
router.register(r"templates", views.NotificationTemplateViewSet, basename="template")
router.register(r"preferences", views.NotificationPreferenceViewSet, basename="preference")
router.register(r"device-tokens", views.DeviceTokenViewSet, basename="device-token")
router.register(r"campaigns", views.NotificationCampaignViewSet, basename="campaign")
router.register(r"rules", views.NotificationRuleViewSet, basename="rule")
router.register(r"notices", views.NoticeViewSet, basename="notice")

# --- New split viewsets (16 total) ---
router.register(r"v2/notifications", NotificationViewSet, basename="v2-notification")
router.register(r"v2/in-app-messages", InAppMessageViewSet, basename="v2-in-app-message")
router.register(r"v2/push-devices", PushDeviceViewSet, basename="v2-push-device")
router.register(r"v2/campaigns", NewNotificationCampaignViewSet, basename="v2-campaign")
router.register(r"v2/ab-tests", CampaignABTestViewSet, basename="v2-ab-test")
router.register(r"v2/schedules", NotificationScheduleViewSet, basename="v2-schedule")
router.register(r"v2/batches", NotificationBatchViewSet, basename="v2-batch")
router.register(r"v2/opt-outs", OptOutViewSet, basename="v2-opt-out")
router.register(r"v2/insights", NotificationInsightViewSet, basename="v2-insight")
router.register(r"v2/delivery-rates", DeliveryRateViewSet, basename="v2-delivery-rate")
router.register(r"v2/admin", NewAdminNotificationViewSet, basename="v2-admin")
router.register(r"v2/templates", NewNotificationTemplateViewSet, basename="v2-template")
router.register(r"v2/preferences", NewNotificationPreferenceViewSet, basename="v2-preference")
router.register(r"v2/rules", NewNotificationRuleViewSet, basename="v2-rule")
router.register(r"v2/logs", NewNotificationLogViewSet, basename="v2-log")
router.register(r"v2/feedbacks", NewNotificationFeedbackViewSet, basename="v2-feedback")

# ---------------------------------------------------------------------------
# Nested routers (existing — DO NOT REMOVE)
# ---------------------------------------------------------------------------
notification_router = routers.NestedDefaultRouter(router, r"notifications", lookup="notification")
notification_router.register(r"logs", views.NotificationLogViewSet, basename="notification-logs")
notification_router.register(r"feedbacks", views.NotificationFeedbackViewSet, basename="notification-feedbacks")
notification_router.register(r"replies", views.NotificationReplyViewSet, basename="notification-replies")

campaign_router = routers.NestedDefaultRouter(router, r"campaigns", lookup="campaign")
campaign_router.register(r"notifications", views.AdminNotificationViewSet, basename="campaign-notifications")


# ---------------------------------------------------------------------------
# Webhook views
# ---------------------------------------------------------------------------

@csrf_exempt
def sendgrid_webhook_view(request):
    if request.method != 'POST':
        return HttpResponse(status=405)
    try:
        events = _json.loads(request.body)
        if not isinstance(events, list):
            events = [events]
        from .tasks import process_sendgrid_events_task
        process_sendgrid_events_task.delay(events)
        return HttpResponse(status=200)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=400)


@csrf_exempt
def twilio_sms_webhook_view(request):
    if request.method != 'POST':
        return HttpResponse(status=405)
    try:
        data = {
            k: v[0] if isinstance(v, list) and len(v) == 1 else v
            for k, v in dict(request.POST).items()
        }
        from .tasks import process_twilio_sms_webhook_task
        process_twilio_sms_webhook_task.delay(data)
        return HttpResponse(status=200)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=400)


def one_click_unsubscribe_view(request, token: str):
    try:
        from .tasks import process_one_click_unsubscribe_task
        process_one_click_unsubscribe_task.delay(token)
        return JsonResponse({'success': True, 'message': 'You have been unsubscribed.'})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=400)


def vapid_public_key_view(request):
    """Return VAPID public key for frontend web push subscription."""
    from .services.providers.WebPushProvider import web_push_provider
    return JsonResponse({'vapid_public_key': web_push_provider.get_vapid_public_key()})


# ---------------------------------------------------------------------------
# URL patterns
# ---------------------------------------------------------------------------
# Import new view functions
from .funnel import funnel_service, rfm_service
from .workflow import workflow_engine


def funnel_summary_view(request):
    from django.http import JsonResponse
    if not request.user.is_staff:
        return JsonResponse({'error': 'Staff only'}, status=403)
    channel = request.GET.get('channel')
    days = int(request.GET.get('days', 30))
    return JsonResponse(funnel_service.get_channel_funnel_comparison(days=days))


def workflow_list_view(request):
    from django.http import JsonResponse
    if not request.user.is_staff:
        return JsonResponse({'error': 'Staff only'}, status=403)
    return JsonResponse({'workflows': workflow_engine.list_workflows()})


def rfm_score_view(request):
    from django.http import JsonResponse
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Auth required'}, status=401)
    score = rfm_service.score_user(request.user)
    return JsonResponse(score)


urlpatterns = [
    # ------ Existing direct paths (DO NOT REMOVE) ------
    path("", views.NotificationViewSet.as_view({"get": "list", "post": "create"}), name="notification-list"),
    path("<int:pk>/", views.NotificationViewSet.as_view({"get": "retrieve", "delete": "destroy"}), name="notification-detail"),
    path("unread-count/", views.UnreadCountView.as_view(), name="unread-count"),
    path("stats/", views.NotificationStatsView.as_view(), name="notification-stats"),
    path("logs/", views.NotificationLogView.as_view(), name="notification-logs-list"),
    path("analytics/generate/", views.GenerateDailyReportView.as_view(), name="analytics-generate"),
    path("analytics/", views.NotificationAnalyticsView.as_view(), name="analytics"),

    # ------ New webhook endpoints ------
    path("webhooks/sendgrid/", sendgrid_webhook_view, name="webhook-sendgrid"),
    path("webhooks/twilio/sms/", twilio_sms_webhook_view, name="webhook-twilio-sms"),

    # ------ One-click unsubscribe (RFC 8058) ------
    path("unsubscribe/<str:token>/", one_click_unsubscribe_view, name="one-click-unsubscribe"),

    # ------ VAPID key for web push ------
    path("push/vapid-key/", vapid_public_key_view, name="vapid-public-key"),

    # ------ Router includes ------
    path("", include(router.urls)),
    path("", include(notification_router.urls)),
    path("", include(campaign_router.urls)),
]
