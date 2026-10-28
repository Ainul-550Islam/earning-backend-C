"""
Messaging URLs — Complete routing: general + CPA + all floating utils exposed.

Includes:
  - All 35 ViewSet router endpoints
  - All existing path() endpoints (views.py + views_extra.py)
  - OpenAPI/Swagger schema endpoints (drf-spectacular, graceful fallback)
  - NEW: WebRTC signaling endpoints (call_manager.py → exposed)
  - NEW: Multi-device broadcast + aggregated presence (device_sync.py → exposed)
  - NEW: Full text translation (translator.translate_text → exposed)
  - NEW: Broadcast create via service (services.create_broadcast → exposed)
  - NEW: Push test, fire conversion signal, voice transcription status

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MIDDLEWARE SETUP — add to settings.py MIDDLEWARE list:

    MIDDLEWARE = [
        # ...existing middleware...
        "messaging.middleware.InboxUnreadCountMiddleware",
        "messaging.middleware.MessagingRequestTimingMiddleware",
        "messaging.middleware.WebSocketRateLimitMiddleware",
    ]

CELERY BEAT — add to settings.py:

    from api.messaging.celery_beat_config import MESSAGING_BEAT_SCHEDULE
    CELERY_BEAT_SCHEDULE = {}
    CELERY_BEAT_SCHEDULE.update(MESSAGING_BEAT_SCHEDULE)

OPENAPI DOCS — add to settings.py:

    INSTALLED_APPS += ["drf_spectacular"]
    REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] = "drf_spectacular.openapi.AutoSchema"
    SPECTACULAR_SETTINGS = {
        "TITLE": "Messaging API",
        "DESCRIPTION": "World-class messaging + CPA platform.",
        "VERSION": "2.0.0",
        "SERVE_INCLUDE_SCHEMA": False,
    }
    # Install: pip install drf-spectacular
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from django.urls import path, include
from rest_framework.routers import SimpleRouter

from .views import (
    MessageAttachmentUploadView, UploadConfirmView, MediaStatusView,
    MessageSearchView, UserSearchView, DeliveryStatusView,
    PresenceView, TranslationView, UnreadCountView,
    DeviceSyncView, HealthCheckView, MentionsView,
)
from .views_extra import (
    # ── E2E Encryption ────────────────────────────────────────────────────────
    E2EEncryptionKeyView, E2ESessionInitView,
    # ── Spam / Moderation ─────────────────────────────────────────────────────
    SpamCheckView, ToxicityCheckView, DuplicateCheckView, AutoModerateView,
    # ── Translation ───────────────────────────────────────────────────────────
    LanguageDetectView,
    # ── Offer Context ─────────────────────────────────────────────────────────
    OfferCardView, OfferStatsSummaryView, PayoutCardView, OfferRecommendView,
    # ── Postback / Conversion ─────────────────────────────────────────────────
    PostbackConversionView, PostbackAlertView, PostbackContextInjectView,
    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RateLimitStatusView, RateLimitBlockView,
    # ── Delivery / Unread ─────────────────────────────────────────────────────
    DeliveryMarkView, UnreadClearView,
    # ── Polls ─────────────────────────────────────────────────────────────────
    PollView, PollVoteView,
    # ── Bot Interactive Components (Part 20) ───────────────────────────────────
    BotInteractionView,
    # ── Broadcasts ────────────────────────────────────────────────────────────
    BroadcastSendView,
    # ── Scheduled ─────────────────────────────────────────────────────────────
    ScheduledSendNowView,
    # ── Push test (admin) ─────────────────────────────────────────────────────
    PushTestView,
    # ── Fire conversion signal (admin) ────────────────────────────────────────
    FireConversionSignalView,
    # ── Voice transcription status poll ──────────────────────────────────────
    VoiceTranscriptionStatusView,
    # ── NEW: WebRTC signaling (call_manager.py → exposed) ────────────────────
    CallRoomIdView,
    WebRTCOfferView,
    WebRTCSdpAnswerView,
    WebRTCIceCandidateView,
    # ── NEW: Multi-device sync (device_sync.py → exposed) ────────────────────
    DeviceBroadcastView,
    AggregatedPresenceView,
    # ── NEW: Full text translation (translator.translate_text → exposed) ──────
    TranslateTextView,
    # ── NEW: Broadcast create via service (services.create_broadcast) ─────────
    BroadcastCreateView,
)
from .viewsets import (
    BotResponseViewSet, BotInteractionViewSet, MessageReportViewSet, MessageSearchIndexViewSet,
    NotificationReadViewSet, PollVoteViewSet, UserDeviceViewSet,
    WebhookDeliveryViewSet,
    AuditLogViewSet, RetentionPolicyViewSet, LegalHoldViewSet,
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

router = SimpleRouter()

# ── General Messaging ─────────────────────────────────────────────────────────
router.register(r"chats",         InternalChatViewSet,        basename="internalchat")
router.register(r"broadcasts",    AdminBroadcastViewSet,      basename="adminbroadcast")
router.register(r"support",       SupportThreadViewSet,       basename="supportthread")
router.register(r"inbox",         UserInboxViewSet,           basename="userinbox")
router.register(r"reactions",     MessageReactionViewSet,     basename="messagereaction")
router.register(r"presence",      UserPresenceViewSet,        basename="userpresence")
router.register(r"calls",         CallSessionViewSet,         basename="callsession")
router.register(r"channels",      AnnouncementChannelViewSet, basename="channel")
router.register(r"scheduled",     ScheduledMessageViewSet,    basename="scheduledmessage")
router.register(r"pins",          MessagePinViewSet,          basename="messagepin")
router.register(r"bots",          BotConfigViewSet,           basename="botconfig")
router.register(r"webhooks",      MessagingWebhookViewSet,    basename="messagingwebhook")
router.register(r"blocks",        UserBlockViewSet,           basename="userblock")
router.register(r"search-vs",     MessageSearchViewSet,       basename="messagesearch")
router.register(r"device-tokens", DeviceTokenViewSet,         basename="devicetoken")
router.register(r"edit-history",  MessageEditHistoryViewSet,  basename="edithistory")
router.register(r"disappearing",  DisappearingMessageViewSet, basename="disappearing")
router.register(r"stories",       UserStoryViewSet,           basename="userstory")
router.register(r"voice",         VoiceMessageViewSet,        basename="voicemessage")
router.register(r"link-previews", LinkPreviewViewSet,         basename="linkpreview")

# ── Previously-missing ViewSets ───────────────────────────────────────────────
router.register(r"bot-responses",       BotResponseViewSet,        basename="bot-response")
router.register(r"bot-interactions",    BotInteractionViewSet,     basename="bot-interaction")
router.register(r"audit-log",           AuditLogViewSet,           basename="audit-log")
router.register(r"retention-policy",    RetentionPolicyViewSet,    basename="retention-policy")
router.register(r"legal-holds",         LegalHoldViewSet,          basename="legal-hold")
router.register(r"reports",             MessageReportViewSet,      basename="message-report")
router.register(r"search-index",        MessageSearchIndexViewSet, basename="search-index")
router.register(r"notification-reads",  NotificationReadViewSet,   basename="notification-read")
router.register(r"poll-votes",          PollVoteViewSet,           basename="poll-vote")
router.register(r"devices",             UserDeviceViewSet,         basename="user-device")
router.register(r"webhook-deliveries",  WebhookDeliveryViewSet,    basename="webhook-delivery")

# ── CPA Platform Messaging ────────────────────────────────────────────────────
router.register(r"notifications",     CPANotificationViewSet, basename="cpanotification")
router.register(r"cpa-broadcasts",    CPABroadcastViewSet,    basename="cpabroadcast")
router.register(r"templates",         MessageTemplateViewSet, basename="messagetemplate")
router.register(r"affiliate-threads", AffiliateThreadViewSet, basename="affiliatethread")


# ── OpenAPI / Swagger — graceful fallback if drf-spectacular not installed ────
def _spectacular_urls():
    try:
        from drf_spectacular.views import (
            SpectacularAPIView,
            SpectacularSwaggerView,
            SpectacularRedocView,
        )
        return [
            path("schema/", SpectacularAPIView.as_view(),       name="messaging-schema"),
            path("docs/",   SpectacularSwaggerView.as_view(url_name="messaging-schema"),
                 name="messaging-swagger-ui"),
            path("redoc/",  SpectacularRedocView.as_view(url_name="messaging-schema"),
                 name="messaging-redoc"),
        ]
    except ImportError:
        import logging
        logging.getLogger(__name__).debug(
            "drf-spectacular not installed — OpenAPI docs disabled. "
            "Run: pip install drf-spectacular"
        )
        return []


urlpatterns = [
    # ── OpenAPI docs (conditional) ───────────────────────────────────────────
    *_spectacular_urls(),

    # ── Media ────────────────────────────────────────────────────────────────
    path("upload/",         MessageAttachmentUploadView.as_view(), name="messaging-upload"),
    path("upload/confirm/", UploadConfirmView.as_view(),           name="messaging-upload-confirm"),
    path("upload/status/",  MediaStatusView.as_view(),             name="messaging-upload-status"),

    # ── Search ───────────────────────────────────────────────────────────────
    path("search/",       MessageSearchView.as_view(),             name="messaging-search"),
    path("users/search/", UserSearchView.as_view(),                name="messaging-user-search"),

    # ── Presence & Utility ───────────────────────────────────────────────────
    path("delivery/",  DeliveryStatusView.as_view(),               name="messaging-delivery"),
    path("online/",    PresenceView.as_view(),                     name="messaging-presence"),
    path("translate/", TranslationView.as_view(),                  name="messaging-translate"),
    path("unread/",    UnreadCountView.as_view(),                  name="messaging-unread"),
    path("sync/",      DeviceSyncView.as_view(),                   name="messaging-sync"),
    path("health/",    HealthCheckView.as_view(),                  name="messaging-health"),
    path("mentions/",  MentionsView.as_view(),                     name="messaging-mentions"),

    # ── E2E Encryption ───────────────────────────────────────────────────────
    path("e2e/keys/",    E2EEncryptionKeyView.as_view(),           name="messaging-e2e-keys"),
    path("e2e/session/", E2ESessionInitView.as_view(),             name="messaging-e2e-session"),

    # ── Moderation / Spam ────────────────────────────────────────────────────
    path("moderation/spam-check/",    SpamCheckView.as_view(),     name="messaging-spam-check"),
    path("moderation/toxicity/",      ToxicityCheckView.as_view(), name="messaging-toxicity"),
    path("moderation/duplicate/",     DuplicateCheckView.as_view(),name="messaging-duplicate"),
    path("moderation/auto-moderate/", AutoModerateView.as_view(),  name="messaging-auto-moderate"),

    # ── Translation ──────────────────────────────────────────────────────────
    path("translate/detect/", LanguageDetectView.as_view(),        name="messaging-lang-detect"),
    # NEW: translate any text string (translate_text was floating)
    path("translate/text/",   TranslateTextView.as_view(),         name="messaging-translate-text"),

    # ── Offer Context ────────────────────────────────────────────────────────
    path("offers/card/",      OfferCardView.as_view(),             name="messaging-offer-card"),
    path("offers/stats/",     OfferStatsSummaryView.as_view(),     name="messaging-offer-stats"),
    path("offers/payout/",    PayoutCardView.as_view(),            name="messaging-offer-payout"),
    path("offers/recommend/", OfferRecommendView.as_view(),        name="messaging-offer-recommend"),

    # ── Postback / Conversion ────────────────────────────────────────────────
    path("postback/conversion/",  PostbackConversionView.as_view(),    name="messaging-postback-conversion"),
    path("postback/alerts/",      PostbackAlertView.as_view(),         name="messaging-postback-alerts"),
    path("postback/inject/",      PostbackContextInjectView.as_view(), name="messaging-postback-inject"),
    path("postback/fire-signal/", FireConversionSignalView.as_view(),  name="messaging-postback-fire-signal"),

    # ── Rate Limiting ────────────────────────────────────────────────────────
    path("rate-limit/status/", RateLimitStatusView.as_view(),     name="messaging-rate-limit-status"),
    path("rate-limit/block/",  RateLimitBlockView.as_view(),      name="messaging-rate-limit-block"),

    # ── Delivery / Unread ────────────────────────────────────────────────────
    path("delivery/mark/",         DeliveryMarkView.as_view(),    name="messaging-delivery-mark"),
    path("delivery/clear-unread/", UnreadClearView.as_view(),     name="messaging-unread-clear"),

    # ── Polls ────────────────────────────────────────────────────────────────
    path("polls/",      PollView.as_view(),                        name="messaging-polls"),
    path("polls/vote/", PollVoteView.as_view(),                    name="messaging-polls-vote"),

    # ── Bot Interactive Components (Part 20) ────────────────────────────────
    path("bots/interact/", BotInteractionView.as_view(),           name="messaging-bots-interact"),

    # ── Broadcast send + create ───────────────────────────────────────────────
    path("broadcasts/<str:broadcast_id>/send/",
         BroadcastSendView.as_view(),      name="messaging-broadcast-send"),
    # NEW: create broadcast via services.create_broadcast (was floating)
    path("broadcasts/create/",
         BroadcastCreateView.as_view(),    name="messaging-broadcast-create"),

    # ── Scheduled Send Now ───────────────────────────────────────────────────
    path("scheduled/<str:scheduled_id>/send-now/",
         ScheduledSendNowView.as_view(),   name="messaging-scheduled-send-now"),

    # ── Push notification test (admin only) ──────────────────────────────────
    path("push/test/",   PushTestView.as_view(),                   name="messaging-push-test"),

    # ── Voice transcription status poll ──────────────────────────────────────
    path("voice/<str:message_id>/transcription/",
         VoiceTranscriptionStatusView.as_view(),
         name="messaging-voice-transcription-status"),

    # ── NEW: WebRTC Signaling (call_manager.py → exposed) ────────────────────
    # GET  /messaging/calls/room/            → generate_room_id()
    path("calls/room/",          CallRoomIdView.as_view(),         name="messaging-call-room-id"),
    # POST /messaging/calls/webrtc/offer/    → build_sdp_offer_payload()
    path("calls/webrtc/offer/",  WebRTCOfferView.as_view(),        name="messaging-webrtc-offer"),
    # POST /messaging/calls/webrtc/answer/   → build_sdp_answer_payload()
    path("calls/webrtc/answer/", WebRTCSdpAnswerView.as_view(),    name="messaging-webrtc-answer"),
    # POST /messaging/calls/webrtc/ice/      → build_ice_candidate_payload()
    path("calls/webrtc/ice/",    WebRTCIceCandidateView.as_view(), name="messaging-webrtc-ice"),

    # ── NEW: Multi-device sync (device_sync.py → exposed) ────────────────────
    # POST /messaging/devices/broadcast/     → broadcast_to_all_user_devices()
    path("devices/broadcast/",   DeviceBroadcastView.as_view(),    name="messaging-device-broadcast"),
    # GET  /messaging/devices/presence/      → get_aggregated_presence()
    path("devices/presence/",    AggregatedPresenceView.as_view(), name="messaging-aggregated-presence"),

    # ── ViewSets ─────────────────────────────────────────────────────────────
    path("", include(router.urls)),
]
