from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers
from . import views

app_name = "notifications"

router = DefaultRouter()
router.register(r"notifications", views.NotificationViewSet, basename="notification")
router.register(r"templates", views.NotificationTemplateViewSet, basename="template")
router.register(r"preferences", views.NotificationPreferenceViewSet, basename="preference")
router.register(r"device-tokens", views.DeviceTokenViewSet, basename="device-token")
router.register(r"campaigns", views.NotificationCampaignViewSet, basename="campaign")
router.register(r"rules", views.NotificationRuleViewSet, basename="rule")
router.register(r"notices", views.NoticeViewSet, basename="notice")

notification_router = routers.NestedDefaultRouter(router, r"notifications", lookup="notification")
notification_router.register(r"logs", views.NotificationLogViewSet, basename="notification-logs")
notification_router.register(r"feedbacks", views.NotificationFeedbackViewSet, basename="notification-feedbacks")
notification_router.register(r"replies", views.NotificationReplyViewSet, basename="notification-replies")

campaign_router = routers.NestedDefaultRouter(router, r"campaigns", lookup="campaign")
campaign_router.register(r"notifications", views.AdminNotificationViewSet, basename="campaign-notifications")

urlpatterns = [
    
    path("", views.NotificationViewSet.as_view({"get": "list", "post": "create"}), name="notification-direct-list"),
    path("<int:pk>/", views.NotificationViewSet.as_view({"get": "retrieve", "delete": "destroy"}), name="notification-direct-detail"),
    path("unread-count/", views.UnreadCountView.as_view(), name="unread-count"),
    path("stats/", views.NotificationStatsView.as_view(), name="notification-stats"),

    # Fix 7: top-level logs (frontend calls /notifications/logs/ without parent id)
    path("logs/", views.NotificationLogView.as_view(), name="notification-logs-list"),

    # Fix 13: generateDailyReport — @action on ListAPIView broken, add manual path
    path("analytics/generate/", views.GenerateDailyReportView.as_view(), name="analytics-generate"),
    path("analytics/", views.NotificationAnalyticsView.as_view(), name="analytics"),

    path("", include(router.urls)),
    path("", include(notification_router.urls)),
    path("", include(campaign_router.urls)),
]