"""
Messaging URLs — Complete: general messaging + CPA platform messaging.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    MessageAttachmentUploadView, UploadConfirmView, MediaStatusView,
    MessageSearchView, UserSearchView, DeliveryStatusView,
    PresenceView, TranslationView, UnreadCountView,
    DeviceSyncView, HealthCheckView, MentionsView,
)
from .viewsets import (
    InternalChatViewSet, AdminBroadcastViewSet,
    SupportThreadViewSet, UserInboxViewSet,
    MessageReactionViewSet, UserPresenceViewSet, CallSessionViewSet,
    AnnouncementChannelViewSet, ScheduledMessageViewSet,
    MessagePinViewSet, BotConfigViewSet, MessagingWebhookViewSet,
    UserBlockViewSet, MessageSearchViewSet, DeviceTokenViewSet,
    MessageEditHistoryViewSet, DisappearingMessageViewSet,
    UserStoryViewSet, VoiceMessageViewSet, LinkPreviewViewSet,
)
from .viewsets_cpa import (
    CPANotificationViewSet, CPABroadcastViewSet,
    MessageTemplateViewSet, AffiliateThreadViewSet,
)

router = DefaultRouter()

# ── General Messaging ─────────────────────────────────────────────────────────
router.register(r"chats",         InternalChatViewSet,       basename="internalchat")
router.register(r"broadcasts",    AdminBroadcastViewSet,     basename="adminbroadcast")
router.register(r"support",       SupportThreadViewSet,      basename="supportthread")
router.register(r"inbox",         UserInboxViewSet,          basename="userinbox")
router.register(r"reactions",     MessageReactionViewSet,    basename="messagereaction")
router.register(r"presence",      UserPresenceViewSet,       basename="userpresence")
router.register(r"calls",         CallSessionViewSet,        basename="callsession")
router.register(r"channels",      AnnouncementChannelViewSet,basename="channel")
router.register(r"scheduled",     ScheduledMessageViewSet,   basename="scheduledmessage")
router.register(r"pins",          MessagePinViewSet,         basename="messagepin")
router.register(r"bots",          BotConfigViewSet,          basename="botconfig")
router.register(r"webhooks",      MessagingWebhookViewSet,   basename="messagingwebhook")
router.register(r"blocks",        UserBlockViewSet,          basename="userblock")
router.register(r"search-vs",     MessageSearchViewSet,      basename="messagesearch")
router.register(r"device-tokens", DeviceTokenViewSet,        basename="devicetoken")
router.register(r"edit-history",  MessageEditHistoryViewSet, basename="edithistory")
router.register(r"disappearing",  DisappearingMessageViewSet,basename="disappearing")
router.register(r"stories",       UserStoryViewSet,          basename="userstory")
router.register(r"voice",         VoiceMessageViewSet,       basename="voicemessage")
router.register(r"link-previews", LinkPreviewViewSet,        basename="linkpreview")

# ── CPA Platform Messaging ────────────────────────────────────────────────────
router.register(r"notifications",      CPANotificationViewSet, basename="cpanotification")
router.register(r"cpa-broadcasts",     CPABroadcastViewSet,    basename="cpabroadcast")
router.register(r"templates",          MessageTemplateViewSet, basename="messagetemplate")
router.register(r"affiliate-threads",  AffiliateThreadViewSet, basename="affiliatethread")

urlpatterns = [
    # Media
    path("upload/",         MessageAttachmentUploadView.as_view(), name="messaging-upload"),
    path("upload/confirm/", UploadConfirmView.as_view(),           name="messaging-upload-confirm"),
    path("upload/status/",  MediaStatusView.as_view(),             name="messaging-upload-status"),
    # Search
    path("search/",         MessageSearchView.as_view(),           name="messaging-search"),
    path("users/search/",   UserSearchView.as_view(),              name="messaging-user-search"),
    # Utility
    path("delivery/",       DeliveryStatusView.as_view(),          name="messaging-delivery"),
    path("online/",         PresenceView.as_view(),                name="messaging-presence"),
    path("translate/",      TranslationView.as_view(),             name="messaging-translate"),
    path("unread/",         UnreadCountView.as_view(),             name="messaging-unread"),
    path("sync/",           DeviceSyncView.as_view(),              name="messaging-sync"),
    path("health/",         HealthCheckView.as_view(),             name="messaging-health"),
    path("mentions/",       MentionsView.as_view(),                name="messaging-mentions"),
    # ViewSets
    path("",                include(router.urls)),
]
