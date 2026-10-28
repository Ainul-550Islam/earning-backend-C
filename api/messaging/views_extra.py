"""
views_extra.py
==============
API endpoints for logic that was in utils/services but had no HTTP exposure:
  - E2EEncryptionView        POST /messaging/e2e/keys/
  - E2ESessionInitView       POST /messaging/e2e/session/
  - SpamCheckView            POST /messaging/moderation/spam-check/
  - ToxicityCheckView        POST /messaging/moderation/toxicity/
  - AutoModerateView         POST /messaging/moderation/auto-moderate/
  - DuplicateCheckView       POST /messaging/moderation/duplicate/
  - LanguageDetectView       POST /messaging/translate/detect/
  - OfferCardView            POST /messaging/offers/card/
  - OfferStatsSummaryView    GET  /messaging/offers/stats/
  - PayoutCardView           GET  /messaging/offers/payout/
  - OfferRecommendView       POST /messaging/offers/recommend/
  - PostbackConversionView   POST /messaging/postback/conversion/
  - PostbackAlertView        GET  /messaging/postback/alerts/
  - RateLimitStatusView      GET  /messaging/rate-limit/status/
  - RateLimitBlockView       POST /messaging/rate-limit/block/
  - DeliveryMarkView         POST /messaging/delivery/mark/
  - UnreadClearView          POST /messaging/delivery/clear-unread/
  - PollView                 POST/GET /messaging/polls/
  - BotInteractionView       POST /messaging/bots/interact/     (Part 20)
  - BroadcastSendView        POST /messaging/broadcasts/<id>/send/
  - ScheduledSendNowView     POST /messaging/scheduled/<id>/send-now/
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .openapi import extend_schema, OpenApiTypes

from . import services
from .exceptions import (
    MessagingError, ChatAccessDeniedError, ChatNotFoundError,
    SpamDetectedError, ToxicContentError, RateLimitError,
    UserBlockedError, EncryptionError, DecryptionError, KeyExchangeError,
    PermissionDeniedError, NotParticipantError,
)

logger = logging.getLogger(__name__)

# Centralised helper — previously duplicated in views.py and views_extra.py.
# Now imported from utils.http (Tech Debt fix #3).
from .utils.http import _err  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# E2E Encryption
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class E2EEncryptionKeyView(APIView):
    """
    POST /messaging/e2e/keys/
    Generate and return a fresh Curve25519 identity key pair (public key only).
    Private key is client-held; only public key stored server-side.

    Request:  {}
    Response: { public_key: str, encoded_public_key: str }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from .utils.e2e_encryption import generate_identity_key_pair, encode_key
        try:
            private_key, public_key = generate_identity_key_pair()
            return Response({
                "public_key": public_key.hex(),
                "encoded_public_key": encode_key(public_key),
            }, status=status.HTTP_201_CREATED)
        except Exception as exc:
            logger.error("E2EEncryptionKeyView: %s", exc)
            return _err(exc, 500)


@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class E2ESessionInitView(APIView):
    """
    POST /messaging/e2e/session/
    Perform X3DH key agreement — returns shared secret material
    so the client can initialise a Double Ratchet session.

    Request:  { recipient_identity_pub, recipient_signed_prekey_pub,
                sender_identity_priv, sender_identity_pub,
                recipient_one_time_prekey_pub? }
    Response: { shared_secret_encoded, ephemeral_pub_encoded }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from .utils.e2e_encryption import (
            x3dh_sender, encode_key, decode_key,
        )
        try:
            data = request.data
            required = [
                "sender_identity_priv", "sender_identity_pub",
                "recipient_identity_pub", "recipient_signed_prekey_pub",
            ]
            missing = [k for k in required if not data.get(k)]
            if missing:
                return Response(
                    {"detail": f"Missing: {missing}"}, status=400
                )
            secret, eph_pub = x3dh_sender(
                sender_identity_priv=decode_key(data["sender_identity_priv"]),
                sender_identity_pub=decode_key(data["sender_identity_pub"]),
                recipient_identity_pub=decode_key(data["recipient_identity_pub"]),
                recipient_signed_prekey_pub=decode_key(data["recipient_signed_prekey_pub"]),
                recipient_one_time_prekey_pub=(
                    decode_key(data["recipient_one_time_prekey_pub"])
                    if data.get("recipient_one_time_prekey_pub") else None
                ),
            )
            return Response({
                "shared_secret_encoded": encode_key(secret),
                "ephemeral_pub_encoded": encode_key(eph_pub),
            })
        except Exception as exc:
            logger.error("E2ESessionInitView: %s", exc)
            return _err(exc, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Spam / Moderation
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class SpamCheckView(APIView):
    """
    POST /messaging/moderation/spam-check/
    Run all spam signals against a message candidate before it is sent.

    Request:  { message: str, chat_id?: str }
    Response: { is_spam, is_toxic, spam_score, toxic_score, reasons }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from .utils.spam_detector import analyze_message
        message = request.data.get("message", "")
        if not message:
            return Response({"is_spam": False, "is_toxic": False, "spam_score": 0.0, "reasons": []})
        try:
            result = analyze_message(
                content=message,
                user_id=request.user.pk,
            )
            return Response(result)
        except Exception as exc:
            logger.error("SpamCheckView: %s", exc)
            return _err(exc, 500)


@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class ToxicityCheckView(APIView):
    """
    POST /messaging/moderation/toxicity/
    Check toxicity score of a message via the configured provider.

    Request:  { message: str }
    Response: { is_toxic, toxicity_score, categories }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from .utils.spam_detector import check_toxicity
        message = request.data.get("message", "")
        if not message:
            return Response({"is_toxic": False, "toxicity_score": 0.0, "categories": {}})
        try:
            result = check_toxicity(message)
            return Response(result)
        except Exception as exc:
            logger.error("ToxicityCheckView: %s", exc)
            return _err(exc, 500)


@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class DuplicateCheckView(APIView):
    """
    POST /messaging/moderation/duplicate/
    Check if this message is a near-duplicate of the user's own recent
    messages (flood/repeat detection; scoped to the user, not the chat).

    Request:  { message: str, chat_id?: str }
    Response: { is_duplicate, repeat_count }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from .utils.spam_detector import check_duplicate_message
        message = request.data.get("message", "")
        if not message:
            return Response({"detail": "message required."}, status=400)
        try:
            is_duplicate, count = check_duplicate_message(
                user_id=request.user.pk,
                content=message,
            )
            return Response({"is_duplicate": is_duplicate, "repeat_count": count})
        except Exception as exc:
            logger.error("DuplicateCheckView: %s", exc)
            return _err(exc, 500)


@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class AutoModerateView(APIView):
    """
    POST /messaging/moderation/auto-moderate/   (admin only)
    Decide whether a message should be auto-moderated (held / deleted / flagged).

    Request:  { message_id: str }
    Response: { action, reason, confidence }
    """
    permission_classes = [IsAdminUser]

    def post(self, request: Request) -> Response:
        from .models import ChatMessage
        from .utils.spam_detector import should_auto_moderate
        message_id = request.data.get("message_id")
        if not message_id:
            return Response({"detail": "message_id required."}, status=400)
        try:
            msg = ChatMessage.objects.get(pk=message_id)
        except ChatMessage.DoesNotExist:
            return Response({"detail": "Message not found."}, status=404)
        try:
            should_block, reason = should_auto_moderate(
                content=msg.content, user_id=msg.sender_id,
            )
            return Response({"action": "block" if should_block else "allow", "reason": reason})
        except Exception as exc:
            logger.error("AutoModerateView: %s", exc)
            return _err(exc, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Language Detection
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class LanguageDetectView(APIView):
    """
    POST /messaging/translate/detect/
    Detect the language of a text string.

    Request:  { text: str }
    Response: { language_code, confidence }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from .utils.translator import detect_language
        text = request.data.get("text", "")
        if not text:
            return Response({"detail": "text required."}, status=400)
        try:
            lang_code = detect_language(text)
            return Response({"language_code": lang_code})
        except Exception as exc:
            logger.error("LanguageDetectView: %s", exc)
            return _err(exc, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Offer Context
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class OfferCardView(APIView):
    """
    POST /messaging/offers/card/
    Build a rich offer card payload ready to be sent as a chat message.

    Request:  { offer: { id, name, payout_rate, payout_type, offer_url, ... } }
    Response: { card: { id, name, payout_display, cta_url, banner_url, ... } }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from .utils.offer_context import build_offer_card_message as _build_offer_card
        offer = request.data.get("offer")
        if not offer or not offer.get("id") or not offer.get("name"):
            return Response({"detail": "offer object with id and name required."}, status=400)
        try:
            card = _build_offer_card(
                offer_id=offer.get("id"),
                offer_name=offer.get("name"),
                payout=offer.get("payout_rate", offer.get("payout", "")),
                vertical=offer.get("vertical", ""),
                countries=offer.get("countries"),
                offer_url=offer.get("offer_url", ""),
                preview_url=offer.get("preview_url", ""),
                status=offer.get("status", "active"),
                description=offer.get("description", ""),
            )
            return Response({"card": card})
        except Exception as exc:
            logger.error("OfferCardView: %s", exc)
            return _err(exc, 500)


@extend_schema(
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's response shape isn't "
        "modeled with a serializer (builds its Response(...) directly) - "
        "see the view body for the real contract."
    ),
)
class OfferStatsSummaryView(APIView):
    """
    GET /messaging/offers/stats/
    Return a chat-ready stats summary message for the current user.

    Response: { summary_message: str, stats: { ... } }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from .utils.offer_context import build_stats_summary_message
        try:
            result = build_stats_summary_message(affiliate_id=request.user.pk)
            return Response(result)
        except Exception as exc:
            logger.error("OfferStatsSummaryView: %s", exc)
            return _err(exc, 500)


@extend_schema(
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's response shape isn't "
        "modeled with a serializer (builds its Response(...) directly) - "
        "see the view body for the real contract."
    ),
)
class PayoutCardView(APIView):
    """
    GET /messaging/offers/payout/?payout_id=<id>&amount=<amount>
    Return a chat-ready payout card for a specific payout.

    Response: { payout_card: { payout_id, amount, payment_method, ... } }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from .utils.offer_context import build_payout_card_message
        payout_id = request.query_params.get("payout_id")
        amount = request.query_params.get("amount")
        if not payout_id or not amount:
            return Response({"detail": "payout_id and amount required."}, status=400)
        try:
            result = build_payout_card_message(
                payout_id=payout_id,
                amount=amount,
                payment_method=request.query_params.get("payment_method", ""),
                transaction_id=request.query_params.get("transaction_id", ""),
                status=request.query_params.get("status", "processed"),
                period=request.query_params.get("period", ""),
            )
            return Response({"payout_card": result})
        except Exception as exc:
            logger.error("PayoutCardView: %s", exc)
            return _err(exc, 500)


@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class OfferRecommendView(APIView):
    """
    POST /messaging/offers/recommend/
    Send an offer recommendation message into an affiliate's chat thread.

    Request:  { offer_id: str, offer_name: str, chat_id: str, payout?: str, reason?: str }
    Response: { sent: bool }
    """
    permission_classes = [IsAdminUser]

    def post(self, request: Request) -> Response:
        from .utils.offer_context import send_offer_recommendation_message
        offer_id = request.data.get("offer_id")
        offer_name = request.data.get("offer_name")
        chat_id = request.data.get("chat_id")
        if not all([offer_id, offer_name, chat_id]):
            return Response(
                {"detail": "offer_id, offer_name, chat_id required."}, status=400
            )
        try:
            send_offer_recommendation_message(
                chat_id=chat_id,
                manager_id=request.user.pk,
                offer_id=offer_id,
                offer_name=offer_name,
                payout=request.data.get("payout", ""),
                reason=request.data.get("reason", ""),
            )
            return Response({"sent": True})
        except Exception as exc:
            logger.error("OfferRecommendView: %s", exc)
            return _err(exc, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Postback / Conversion
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class PostbackConversionView(APIView):
    """
    POST /messaging/postback/conversion/
    Notify affiliate of a new conversion via WebSocket + in-app notification.

    Request:  { affiliate_id, offer_id, offer_name, payout_amount, conversion_id }
    Response: { notified: bool }
    """
    permission_classes = [IsAdminUser]

    def post(self, request: Request) -> Response:
        from .utils.postback_tracker import notify_conversion_via_ws
        affiliate_id = request.data.get("affiliate_id")
        offer_id = request.data.get("offer_id")
        offer_name = request.data.get("offer_name")
        payout_amount = request.data.get("payout_amount")
        conversion_id = request.data.get("conversion_id")
        if not all([affiliate_id, offer_id, offer_name, payout_amount, conversion_id]):
            return Response(
                {"detail": "affiliate_id, offer_id, offer_name, payout_amount, conversion_id required."},
                status=400,
            )
        try:
            result = notify_conversion_via_ws(
                affiliate_id=affiliate_id,
                offer_id=offer_id,
                offer_name=offer_name,
                payout_amount=payout_amount,
                conversion_id=conversion_id,
            )
            return Response({"notified": result})
        except Exception as exc:
            logger.error("PostbackConversionView: %s", exc)
            return _err(exc, 500)


@extend_schema(
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's response shape isn't "
        "modeled with a serializer (builds its Response(...) directly) - "
        "see the view body for the real contract."
    ),
)
class PostbackAlertView(APIView):
    """
    GET /messaging/postback/alerts/?affiliate_id=<id>&offer_id=<id>&offer_name=<name>
    Fire an URGENT postback-failed alert (signal) for an affiliate/offer pair.

    Response: { alert_fired: bool }
    """
    permission_classes = [IsAdminUser]

    def get(self, request: Request) -> Response:
        from .utils.postback_tracker import send_postback_failed_alert
        affiliate_id = request.query_params.get("affiliate_id")
        offer_id = request.query_params.get("offer_id")
        offer_name = request.query_params.get("offer_name")
        error_detail = request.query_params.get("error_detail", "")
        if not all([affiliate_id, offer_id, offer_name]):
            return Response(
                {"detail": "affiliate_id, offer_id, offer_name required."}, status=400
            )
        try:
            send_postback_failed_alert(
                affiliate_id=affiliate_id,
                offer_id=offer_id,
                offer_name=offer_name,
                error_detail=error_detail,
            )
            return Response({"alert_fired": True})
        except Exception as exc:
            logger.error("PostbackAlertView: %s", exc)
            return _err(exc, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Rate Limit
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's response shape isn't "
        "modeled with a serializer (builds its Response(...) directly) - "
        "see the view body for the real contract."
    ),
)
class RateLimitStatusView(APIView):
    """
    GET /messaging/rate-limit/status/?action=send_message
    Return current rate limit usage for the authenticated user.

    Response: { action, limit, remaining, window_seconds, is_blocked }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from .utils.rate_limiter import sliding_window_check, is_user_blocked_by_rate_limit
        from .constants import MAX_MESSAGES_PER_MINUTE
        action = request.query_params.get("action", "send_message")
        try:
            allowed, used = sliding_window_check(
                key=f"messages:user:{request.user.pk}",
                limit=MAX_MESSAGES_PER_MINUTE,
                window_seconds=60,
            )
            is_blocked = is_user_blocked_by_rate_limit(request.user.pk)
            return Response({
                "action": action,
                "limit": MAX_MESSAGES_PER_MINUTE,
                "used": used,
                "remaining": max(0, MAX_MESSAGES_PER_MINUTE - used),
                "window_seconds": 60,
                "is_blocked": is_blocked,
                "allowed": allowed,
            })
        except Exception as exc:
            logger.error("RateLimitStatusView: %s", exc)
            return _err(exc, 500)


@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class RateLimitBlockView(APIView):
    """
    POST /messaging/rate-limit/block/   (admin only)
    Temporarily block or unblock a user from all messaging actions.

    Request:  { user_id: int, duration_seconds: int, reason?: str }
             OR { user_id: int, unblock: true }
    Response: { blocked: bool, until?: ISO datetime }
    """
    permission_classes = [IsAdminUser]

    def post(self, request: Request) -> Response:
        from .utils.rate_limiter import block_user_rate_limit, is_user_blocked_by_rate_limit
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"detail": "user_id required."}, status=400)
        try:
            if request.data.get("unblock"):
                # Reset by clearing the block
                from django.core.cache import cache
                cache.delete(f"rate_block:{user_id}")
                return Response({"blocked": False})
            duration = int(request.data.get("duration_seconds", 3600))
            reason = request.data.get("reason", "")
            block_user_rate_limit(
                user_id=user_id,
                duration_seconds=duration,
                reason=reason,
            )
            until = (timezone.now() + timedelta(seconds=duration)).isoformat()
            return Response({"blocked": True, "until": until})
        except Exception as exc:
            logger.error("RateLimitBlockView: %s", exc)
            return _err(exc, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Delivery / Unread
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class DeliveryMarkView(APIView):
    """
    POST /messaging/delivery/mark/
    Mark one or more messages as delivered or read.

    Request:  { message_ids: [str], status: "delivered"|"read" }
    Response: { updated: int }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from .utils.delivery_manager import mark_delivered, mark_read
        message_ids = request.data.get("message_ids", [])
        mark_status = request.data.get("status", "delivered")
        if not message_ids:
            return Response({"detail": "message_ids required."}, status=400)
        if mark_status not in ("delivered", "read"):
            return Response({"detail": "status must be 'delivered' or 'read'."}, status=400)
        fn = mark_read if mark_status == "read" else mark_delivered
        updated = 0
        for mid in message_ids:
            try:
                if fn(message_id=mid, user_id=request.user.pk):
                    updated += 1
            except Exception as exc:
                logger.warning("DeliveryMarkView: %s for %s", exc, mid)
        return Response({"updated": updated})


@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class UnreadClearView(APIView):
    """
    POST /messaging/delivery/clear-unread/
    Clear the unread cache for a specific chat (called after user opens chat).

    Request:  { chat_id: str }
    Response: { cleared: bool }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from .utils.delivery_manager import clear_unread_cache
        chat_id = request.data.get("chat_id")
        if not chat_id:
            return Response({"detail": "chat_id required."}, status=400)
        try:
            clear_unread_cache(user_id=request.user.pk, chat_id=chat_id)
            return Response({"cleared": True})
        except Exception as exc:
            logger.error("UnreadClearView: %s", exc)
            return _err(exc, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Poll
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class PollView(APIView):
    """
    POST /messaging/polls/          — create a poll message
    GET  /messaging/polls/?message_id=<id> — get poll results
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        chat_id = request.data.get("chat_id")
        question = request.data.get("question", "")
        options = request.data.get("options", [])
        multiple_choice = request.data.get("multiple_choice", False)
        if not chat_id or not question or len(options) < 2:
            return Response(
                {"detail": "chat_id, question, and at least 2 options are required."},
                status=400,
            )
        try:
            msg = services.create_poll(
                chat_id=chat_id,
                sender_id=request.user.pk,
                question=question,
                options=options,
                multiple_choice=multiple_choice,
            )
            return Response({
                "message_id": str(msg.id),
                "chat_id": str(msg.chat_id),
                "poll_data": msg.poll_data,
            }, status=status.HTTP_201_CREATED)
        except MessagingError as exc:
            return _err(exc)
        except Exception as exc:
            logger.error("PollView.post: %s", exc)
            return _err(exc, 500)

    def get(self, request: Request) -> Response:
        message_id = request.query_params.get("message_id")
        if not message_id:
            return Response({"detail": "message_id required."}, status=400)
        try:
            results = services.get_poll_results(message_id, request.user.pk)
            return Response(results)
        except MessagingError as exc:
            return _err(exc)
        except Exception as exc:
            logger.error("PollView.get: %s", exc)
            return _err(exc, 500)


@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class PollVoteView(APIView):
    """
    POST /messaging/polls/vote/
    Cast or change a vote on a poll.

    Request:  { message_id: str, option_id: str }
    Response: { voted: bool, option_id: str, total_votes: int }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        message_id = request.data.get("message_id")
        option_id = request.data.get("option_id")
        if not message_id or not option_id:
            return Response({"detail": "message_id and option_id required."}, status=400)
        try:
            vote = services.vote_on_poll(
                message_id=message_id,
                user_id=request.user.pk,
                option_id=option_id,
            )
            results = services.get_poll_results(message_id, request.user.pk)
            return Response({
                "voted": True,
                "option_id": vote.option_id,
                "total_votes": results.get("total_votes", 0),
            })
        except MessagingError as exc:
            return _err(exc)
        except Exception as exc:
            logger.error("PollVoteView: %s", exc)
            return _err(exc, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Part 20 (world-system audit): Bot Interactive Components
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class BotInteractionView(APIView):
    """
    POST /messaging/bots/interact/

    Handle a click on a button / select-menu option that a bot attached to
    one of its messages (ChatMessage.interactive_blocks). This is the
    missing other half of the bot engine: BotConfig could already trigger
    off an inbound message and reply once (process_bot_triggers), but a
    user had no way to act on what the bot sent back - no interactive
    components, no callback. This endpoint is that callback.

    Request:
        {
            "message_id": str,   -- required, the BOT message carrying the block
            "action_id":  str,   -- required, matches a block's action_id
            "value":      str,   -- optional, overrides the block's own value
                                     (e.g. a select-menu's chosen option)
        }

    Response:
        {
            "action_id":             str,
            "value":                 str,
            "resulting_message_id":  str | null   -- set if the owning bot
                                                       had a response_template
                                                       and sent a follow-up
        }

    Same participant check as PollVoteView/PollView - clicking is only
    allowed for members of the chat the bot message lives in, tenant
    isolation included (via ChatParticipant, not a raw tenant_id compare -
    see _assert_chat_participant).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        message_id = request.data.get("message_id")
        action_id = request.data.get("action_id")
        if not message_id or not action_id:
            return Response({"detail": "message_id and action_id required."}, status=400)
        value = request.data.get("value", "")

        try:
            interaction = services.process_bot_interaction(
                message_id=message_id,
                action_id=action_id,
                value=value,
                user_id=request.user.pk,
            )
            return Response({
                "action_id": interaction.action_id,
                "value": interaction.value,
                "resulting_message_id": (
                    str(interaction.resulting_message_id)
                    if interaction.resulting_message_id else None
                ),
            }, status=status.HTTP_200_OK)
        except MessagingError as exc:
            return _err(exc)
        except Exception as exc:
            logger.error("BotInteractionView: %s", exc)
            return _err(exc, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Broadcast Send
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class BroadcastSendView(APIView):
    """
    POST /messaging/broadcasts/<broadcast_id>/send/
    Trigger delivery of a draft broadcast.

    Response: { sent: bool, recipient_count: int }
    """
    permission_classes = [IsAdminUser]

    def post(self, request: Request, broadcast_id: Any) -> Response:
        try:
            result = services.send_broadcast(
                broadcast_id=broadcast_id,
                actor_id=request.user.pk,
            )
            return Response(result)
        except MessagingError as exc:
            return _err(exc)
        except Exception as exc:
            logger.error("BroadcastSendView: %s", exc)
            return _err(exc, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Scheduled Message — Send Now
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class ScheduledSendNowView(APIView):
    """
    POST /messaging/scheduled/<scheduled_id>/send-now/
    Immediately fire a pending scheduled message.

    Response: { message_id: str, content: str }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, scheduled_id: Any) -> Response:
        from .models import ScheduledMessage
        from django.core.exceptions import ValidationError
        try:
            sched = ScheduledMessage.objects.get(pk=scheduled_id)
        except (ScheduledMessage.DoesNotExist, ValidationError, ValueError):
            return Response({"detail": "Scheduled message not found."}, status=404)
        # SECURITY: without this, any authenticated user could force any
        # other user's pending scheduled message to send immediately by
        # id alone - the message would still appear to come from the
        # original sender, making early/malicious firing covert.
        if sched.sender_id != request.user.pk and not request.user.is_staff:
            return Response({"detail": "Access denied."}, status=403)
        try:
            msg = services.send_scheduled_message_now(scheduled_id=scheduled_id)
            return Response({
                "message_id": str(msg.id),
                "content": msg.content,
                "sent_at": msg.created_at.isoformat(),
            })
        except MessagingError as exc:
            return _err(exc)
        except Exception as exc:
            logger.error("ScheduledSendNowView: %s", exc)
            return _err(exc, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Postback Context Injection
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class PostbackContextInjectView(APIView):
    """
    POST /messaging/postback/inject/
    Inject a conversion context system message into the affiliate's
    manager chat (looked up internally via AffiliateConversationThread).

    Request:  { affiliate_id, conversion_data: { conversion_id, offer_id, offer_name, payout_amount } }
    Response: { injected: bool }
    """
    permission_classes = [IsAdminUser]

    def post(self, request: Request) -> Response:
        from .utils.postback_tracker import inject_conversion_context_to_chat
        affiliate_id = request.data.get("affiliate_id")
        conversion_data = request.data.get("conversion_data") or {}
        conversion_id = conversion_data.get("conversion_id")
        offer_id = conversion_data.get("offer_id")
        offer_name = conversion_data.get("offer_name")
        payout_amount = conversion_data.get("payout_amount")
        if not all([affiliate_id, conversion_id, offer_id, offer_name, payout_amount]):
            return Response(
                {
                    "detail": (
                        "affiliate_id required; conversion_data must include "
                        "conversion_id, offer_id, offer_name, payout_amount."
                    )
                },
                status=400,
            )
        try:
            inject_conversion_context_to_chat(
                affiliate_id=affiliate_id,
                conversion_id=conversion_id,
                offer_id=offer_id,
                offer_name=offer_name,
                payout_amount=payout_amount,
                manager_id=request.user.pk,
            )
            return Response({"injected": True})
        except Exception as exc:
            logger.error("PostbackContextInjectView: %s", exc)
            return _err(exc, 500)


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Push Notification Test  (admin only)
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class PushTestView(APIView):
    """
    POST /messaging/push/test/   (admin only)

    Send a test push notification to all registered devices of a user.
    Useful for QA, customer support debugging, and device token verification.

    Previously utils/device_push.py had send_fcm/send_apns/send_webpush/
    send_expo_push but there was no HTTP endpoint to trigger them.

    Request body:
        {
            "user_id":   int,           -- target user
            "title":     str,           -- notification title
            "body":      str,           -- notification body
            "data":      dict,          -- optional extra payload
            "provider":  str            -- optional: "fcm"|"apns"|"webpush"|"expo"|"all"
                                           default: "all"
        }

    Response:
        {
            "results": [
                {
                    "token_id":  str,
                    "provider":  str,
                    "success":   bool,
                    "error":     str | null
                }
            ],
            "sent": int,
            "failed": int
        }
    """
    permission_classes = [IsAdminUser]

    def post(self, request: Request) -> Response:
        from .utils.device_push import send_fcm, send_apns, send_webpush, send_expo_push
        from .models import DeviceToken

        user_id  = request.data.get("user_id")
        title    = request.data.get("title", "Test notification")
        body     = request.data.get("body", "This is a test push from the messaging admin.")
        data     = request.data.get("data", {})
        provider = request.data.get("provider", "all").lower()

        if not user_id:
            return Response({"detail": "user_id required."}, status=400)

        tokens = DeviceToken.objects.filter(
            user_id=user_id,
            is_active=True,
        )
        if provider != "all":
            tokens = tokens.filter(platform=provider)

        if not tokens.exists():
            return Response(
                {
                    "detail": f"No active device tokens found for user {user_id}"
                              + (f" with provider '{provider}'" if provider != "all" else "") + ".",
                    "results": [], "sent": 0, "failed": 0,
                },
                status=404,
            )

        _provider_fn = {
            "android": lambda tok: send_fcm(token=tok.token, title=title, body=body, data=data),
            "ios":     lambda tok: send_apns(token=tok.token, title=title, body=body, data=data),
            "web":     lambda tok: send_webpush(subscription_info=tok.token, title=title, body=body, data=data),
            "expo":    lambda tok: send_expo_push(token=tok.token, title=title, body=body, data=data),
        }

        results = []
        sent    = 0
        failed  = 0

        for tok in tokens:
            plat = (tok.platform or "").lower()
            fn   = _provider_fn.get(plat)
            if not fn:
                results.append({
                    "token_id": str(tok.id),
                    "provider": plat,
                    "success":  False,
                    "error":    f"Unknown platform '{plat}'",
                })
                failed += 1
                continue
            try:
                success = fn(tok)
                results.append({
                    "token_id": str(tok.id),
                    "provider": plat,
                    "success":  bool(success),
                    "error":    None,
                })
                if success:
                    sent += 1
                else:
                    failed += 1
            except Exception as exc:
                logger.error("PushTestView: token=%s error=%s", tok.id, exc)
                results.append({
                    "token_id": str(tok.id),
                    "provider": plat,
                    "success":  False,
                    "error":    str(exc),
                })
                failed += 1

        return Response({"results": results, "sent": sent, "failed": failed})


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Fire Conversion Signal Manually
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class FireConversionSignalView(APIView):
    """
    POST /messaging/postback/fire-signal/   (admin / internal service only)

    Manually fire the conversion_received Django signal.
    This is the HTTP wrapper for utils/postback_tracker.fire_conversion_signal()
    which previously had no API exposure.

    Use cases:
      - Replay a failed conversion notification
      - Trigger from an internal CPA service via HTTP instead of direct signal
      - Testing signal handler chains in staging

    Request body:
        {
            "conversion_id":  str,   -- required
            "affiliate_id":   int,   -- required
            "offer_id":       str,   -- required
            "offer_name":     str,   -- required
            "payout_amount":  str,   -- required  e.g. "12.50"
        }

    Response:
        {
            "fired":          bool,
            "conversion_id":  str,
            "receivers_count": int   -- number of signal receivers notified
        }
    """
    permission_classes = [IsAdminUser]

    def post(self, request: Request) -> Response:
        from .utils.postback_tracker import fire_conversion_signal

        required = ["conversion_id", "affiliate_id", "offer_id", "offer_name", "payout_amount"]
        missing  = [k for k in required if not request.data.get(k)]
        if missing:
            return Response({"detail": f"Missing required fields: {missing}"}, status=400)

        conversion_id = request.data["conversion_id"]
        affiliate_id  = request.data["affiliate_id"]
        offer_id      = request.data["offer_id"]
        offer_name    = request.data["offer_name"]
        payout_amount = request.data["payout_amount"]

        try:
            receivers_count = fire_conversion_signal(
                conversion_id=conversion_id,
                affiliate_id=affiliate_id,
                offer_id=offer_id,
                offer_name=offer_name,
                payout_amount=payout_amount,
            )
            return Response({
                "fired":           True,
                "conversion_id":   conversion_id,
                "receivers_count": receivers_count or 0,
            })
        except Exception as exc:
            logger.error("FireConversionSignalView: %s", exc)
            return _err(exc, 500)


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Voice Transcription Status Polling
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's response shape isn't "
        "modeled with a serializer (builds its Response(...) directly) - "
        "see the view body for the real contract."
    ),
)
class VoiceTranscriptionStatusView(APIView):
    """
    GET /messaging/voice/<message_id>/transcription/

    Poll the transcription status for a voice message.
    Previously voice messages were processed via Celery task (async) but
    there was no endpoint for the client to check when transcription finished.

    The Celery task (process_voice_message_task) writes results to the
    VoiceMessageTranscription model. This view reads that record.

    Response when processing:
        {
            "status":        "processing",
            "message_id":    str,
            "transcript":    null,
            "waveform":      null,
            "duration":      null,
            "language":      null,
            "retry_after":   5        -- seconds before next poll
        }

    Response when complete:
        {
            "status":        "done",
            "message_id":    str,
            "transcript":    str,
            "waveform":      [float, ...],   -- 64-point amplitude array
            "duration":      float,          -- seconds
            "language":      str,            -- detected language code
            "retry_after":   null
        }

    Response when failed:
        {
            "status":        "failed",
            "message_id":    str,
            "error":         str,
            "retry_after":   null
        }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, message_id: str) -> Response:
        from .models import VoiceMessageTranscription, ChatMessage

        # Verify the requesting user has access to this message
        try:
            msg = ChatMessage.objects.select_related("chat").get(pk=message_id)
        except ChatMessage.DoesNotExist:
            return Response({"detail": "Message not found."}, status=404)

        try:
            from . import services as _svc
            _svc._assert_chat_participant(msg.chat, request.user.pk)
        except (ChatAccessDeniedError, NotParticipantError) as exc:
            return Response({"detail": "Access denied."}, status=403)
        except Exception as exc:
            logger.warning(
                "VoiceTranscriptionStatusView: participant check failed "
                "msg=%s user=%s: %s", message_id, request.user.pk, exc
            )
            return Response({"detail": "Access denied."}, status=403)

        # Look up transcription record
        try:
            transcription = VoiceMessageTranscription.objects.filter(
                message_id=message_id
            ).first()
        except Exception as exc:
            logger.error("VoiceTranscriptionStatusView: %s", exc)
            return _err(exc, 500)

        if transcription is None:
            # Task may not have run yet (queued but not started)
            return Response({
                "status":      "processing",
                "message_id":  message_id,
                "transcript":  None,
                "waveform":    None,
                "duration":    None,
                "language":    None,
                "retry_after": 3,
            })

        # Model field name is `error` (see VoiceMessageTranscription.error).
        error_msg = getattr(transcription, "error", None)
        if error_msg:
            return Response({
                "status":      "failed",
                "message_id":  message_id,
                "error":       error_msg,
                "retry_after": None,
            })

        transcript_text = getattr(transcription, "transcribed_text", None)
        is_processing   = getattr(transcription, "is_processing", True)

        if is_processing or not transcript_text:
            return Response({
                "status":      "processing",
                "message_id":  message_id,
                "transcript":  None,
                "waveform":    getattr(transcription, "waveform_data", None),
                "duration":    getattr(transcription, "duration_seconds", None),
                "language":    getattr(transcription, "language", None),
                "retry_after": 5,
            })

        return Response({
            "status":      "done",
            "message_id":  message_id,
            "transcript":  transcript_text,
            "waveform":    getattr(transcription, "waveform_data", None),
            "duration":    getattr(transcription, "duration_seconds", None),
            "language":    getattr(transcription, "language", None),
            "retry_after": None,
        })


# =============================================================================
# ── NEW SECTION: Floating utils → HTTP endpoints ──────────────────────────────
# All functions below existed in utils/ but had zero HTTP exposure.
# =============================================================================

# ─────────────────────────────────────────────────────────────────────────────
# WebRTC Signaling helpers (utils/call_manager.py)
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's response shape isn't "
        "modeled with a serializer (builds its Response(...) directly) - "
        "see the view body for the real contract."
    ),
)
class CallRoomIdView(APIView):
    """
    GET /messaging/calls/room/

    Generate a unique WebRTC room ID.
    Call this before initiating a call to get the room_id that the
    WebSocket URL ws/messaging/call/<room_id>/ uses.

    Previously utils/call_manager.generate_room_id() had 0 HTTP uses.

    Response:
        { "room_id": "a3f9c2b1d4e8f701" }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from .utils.call_manager import generate_room_id
        try:
            return Response({"room_id": generate_room_id()})
        except Exception as exc:
            logger.error("CallRoomIdView: %s", exc)
            return _err(exc, 500)


@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class WebRTCOfferView(APIView):
    """
    POST /messaging/calls/webrtc/offer/

    Build the WebSocket signaling payload for an SDP offer.
    Send the returned payload to the peer via ws/messaging/call/<room_id>/.

    Previously utils/call_manager.build_sdp_offer_payload() had 0 HTTP uses.

    Request:
        { "room_id": str, "callee_id": str|int }

    Response:
        {
            "type":        "call.signal",
            "signal_type": "offer",
            "room_id":     str,
            "caller_id":   str,
            "callee_id":   str
        }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from .utils.call_manager import build_sdp_offer_payload
        room_id   = request.data.get("room_id")
        callee_id = request.data.get("callee_id")
        if not room_id or not callee_id:
            return Response({"detail": "room_id and callee_id required."}, status=400)
        try:
            payload = build_sdp_offer_payload(
                room_id=room_id,
                caller_id=request.user.pk,
                callee_id=callee_id,
            )
            return Response(payload)
        except Exception as exc:
            logger.error("WebRTCOfferView: %s", exc)
            return _err(exc, 500)


@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class WebRTCSdpAnswerView(APIView):
    """
    POST /messaging/calls/webrtc/answer/

    Build the WebSocket signaling payload for an SDP answer.
    Call this after receiving an offer to construct your answer payload.

    Previously utils/call_manager.build_sdp_answer_payload() had 0 HTTP uses.

    Request:
        { "room_id": str, "sdp": str }

    Response:
        { "type": "call.signal", "signal_type": "answer", "room_id": str, "sdp": str }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from .utils.call_manager import build_sdp_answer_payload
        room_id = request.data.get("room_id")
        sdp     = request.data.get("sdp", "")
        if not room_id or not sdp:
            return Response({"detail": "room_id and sdp required."}, status=400)
        try:
            payload = build_sdp_answer_payload(room_id=room_id, sdp=sdp)
            return Response(payload)
        except Exception as exc:
            logger.error("WebRTCSdpAnswerView: %s", exc)
            return _err(exc, 500)


@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class WebRTCIceCandidateView(APIView):
    """
    POST /messaging/calls/webrtc/ice/

    Build the WebSocket signaling payload for an ICE candidate.
    Trickle ICE: call this for every ICE candidate your browser generates.

    Previously utils/call_manager.build_ice_candidate_payload() had 0 HTTP uses.

    Request:
        {
            "room_id":   str,
            "candidate": {
                "candidate":     str,
                "sdpMid":        str,
                "sdpMLineIndex": int
            }
        }

    Response:
        { "type": "call.signal", "signal_type": "ice_candidate", "room_id": str, "candidate": {...} }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from .utils.call_manager import build_ice_candidate_payload
        room_id   = request.data.get("room_id")
        candidate = request.data.get("candidate")
        if not room_id or not candidate:
            return Response({"detail": "room_id and candidate required."}, status=400)
        try:
            payload = build_ice_candidate_payload(room_id=room_id, candidate=candidate)
            return Response(payload)
        except Exception as exc:
            logger.error("WebRTCIceCandidateView: %s", exc)
            return _err(exc, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Multi-device sync helpers (utils/device_sync.py)
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class DeviceBroadcastView(APIView):
    """
    POST /messaging/devices/broadcast/

    Send a WebSocket event to ALL connected devices of a user.
    Used for cross-device sync (e.g. message read on one device → mark
    read on all others instantly).

    Previously utils/device_sync.broadcast_to_all_user_devices() had 0 HTTP uses.

    Request:
        {
            "user_id":    int,
            "event_type": str,   # one of: chat.cross_device.read, chat.cross_device.message
            "data":       dict
        }

    Response:
        { "notified": int }   — number of devices that received the event
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from .utils.device_sync import broadcast_to_all_user_devices

        user_id    = request.data.get("user_id", request.user.pk)
        event_type = request.data.get("event_type")
        data       = request.data.get("data", {})

        # Non-admin users can only broadcast to their own devices
        if str(user_id) != str(request.user.pk) and not request.user.is_staff:
            return Response(
                {"detail": "You can only broadcast to your own devices."},
                status=403,
            )
        if not event_type:
            return Response({"detail": "event_type required."}, status=400)

        # Audit fix (Part 19): event_type went straight to group_send with
        # no validation. Channels' consumer dispatch does getattr(self,
        # event_type.replace(".", "_")) and raises ValueError - crashing
        # the WebSocket connection - for anything that isn't an exact
        # handler name. Since this endpoint lets any authenticated user
        # (or, cross-user, any staff user) choose that string freely, an
        # unrecognized value didn't error out cleanly here - it crashed
        # every one of the target user's *other* connected devices the
        # moment the broadcast landed. Restricted to the handler names
        # ChatConsumer actually defines for its user_devices_{id} group
        # (the one this function broadcasts to), matching this endpoint's
        # documented cross-device-sync purpose - this also closes off
        # using it to spoof unrelated events like chat.message.new with
        # attacker-controlled data to a user's own other sessions.
        ALLOWED_DEVICE_BROADCAST_TYPES = {
            "chat.cross_device.read": "device_sync_read",
            "chat.cross_device.message": "device_sync_message",
        }
        if event_type not in ALLOWED_DEVICE_BROADCAST_TYPES:
            return Response(
                {
                    "detail": f"Unsupported event_type {event_type!r}.",
                    "allowed": sorted(ALLOWED_DEVICE_BROADCAST_TYPES),
                },
                status=400,
            )

        try:
            notified = broadcast_to_all_user_devices(
                user_id=user_id,
                event_type=event_type,
                data=data,
            )
            return Response({"notified": notified})
        except Exception as exc:
            logger.error("DeviceBroadcastView: %s", exc)
            return _err(exc, 500)


@extend_schema(
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's response shape isn't "
        "modeled with a serializer (builds its Response(...) directly) - "
        "see the view body for the real contract."
    ),
)
class AggregatedPresenceView(APIView):
    """
    GET /messaging/devices/presence/?user_id=<id>

    Return a user's effective presence aggregated across ALL their devices.
    A user is ONLINE if ANY of their devices was active within the presence
    timeout window (default: 5 minutes).

    Previously utils/device_sync.get_aggregated_presence() had 0 HTTP uses.
    The existing /messaging/online/ endpoint only calls services.get_presence()
    which checks a single UserPresence row — it does NOT check all devices.

    Query params:
        user_id (optional) — defaults to authenticated user

    Response:
        {
            "status":        "online" | "away" | "offline",
            "device_count":  int,
            "last_seen_at":  ISO datetime | null
        }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from .utils.device_sync import get_aggregated_presence

        user_id = request.query_params.get("user_id", request.user.pk)

        # Non-admin can only check their own aggregated presence
        if str(user_id) != str(request.user.pk) and not request.user.is_staff:
            return Response({"detail": "Access denied."}, status=403)

        try:
            result = get_aggregated_presence(user_id=user_id)
            return Response(result)
        except Exception as exc:
            logger.error("AggregatedPresenceView: %s", exc)
            return _err(exc, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Full text translation (utils/translator.py)
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class TranslateTextView(APIView):
    """
    POST /messaging/translate/text/

    Translate a text string to the target language.
    Tries Google Translate → DeepL → stub (in that order).

    Previously utils/translator.translate_text() had 0 HTTP uses.
    The existing /messaging/translate/ endpoint calls services.translate_message()
    which translates an existing ChatMessage by ID. This endpoint translates
    any arbitrary text string — useful for previewing or client-side translation.

    Request:
        {
            "text":        str,            -- text to translate (max 5000 chars)
            "target_lang": str,            -- ISO 639-1 code, e.g. "bn", "en", "ar"
            "source_lang": str | null      -- optional: detected automatically if omitted
        }

    Response:
        {
            "translated_text":      str,
            "detected_source_lang": str,   -- e.g. "en"
            "target_lang":          str
        }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from .utils.translator import translate_text

        text        = request.data.get("text", "")
        target_lang = request.data.get("target_lang", "")
        source_lang = request.data.get("source_lang")

        if not text:
            return Response({"detail": "text required."}, status=400)
        if not target_lang:
            return Response({"detail": "target_lang required."}, status=400)
        if len(text) > 5000:
            return Response(
                {"detail": "text must be 5000 characters or fewer."},
                status=400,
            )

        try:
            translated, detected_source = translate_text(
                text=text,
                target_lang=target_lang,
                source_lang=source_lang,
            )
            return Response({
                "translated_text":      translated,
                "detected_source_lang": detected_source,
                "target_lang":          target_lang,
            })
        except Exception as exc:
            logger.error("TranslateTextView: %s", exc)
            return _err(exc, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Broadcast create via services (services.create_broadcast)
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description=(
        "Schema generation note: this endpoint's request/response shape "
        "isn't modeled with a serializer (handles raw request.data / builds "
        "its Response(...) directly) - see the view body for the real contract."
    ),
)
class BroadcastCreateView(APIView):
    """
    POST /messaging/broadcasts/create/   (admin only)

    Create a broadcast via services.create_broadcast(), which runs
    full_clean() validation and sets status=DRAFT correctly.

    Previously services.create_broadcast() had 0 HTTP uses.
    AdminBroadcastViewSet.perform_create() bypasses the service and calls
    serializer.save() directly, skipping:
      - full_clean() validation
      - BroadcastStatus.DRAFT enforcement
      - tenant assignment logic

    This view is the correct way to create a broadcast when you need
    those guarantees. AdminBroadcastViewSet (ModelViewSet) can still
    be used for CRUD operations after creation.

    Request:
        {
            "title":           str,            -- required
            "body":            str,            -- required
            "audience_type":   str,            -- default: "ALL_USERS"
            "audience_filter": dict | null,    -- optional filter params
            "scheduled_at":    ISO datetime | null
        }

    Response:
        {
            "id":            str (UUID),
            "title":         str,
            "status":        "DRAFT",
            "audience_type": str,
            "scheduled_at":  ISO datetime | null,
            "created_at":    ISO datetime
        }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        if not request.user.is_staff:
            return Response({"detail": "Admin only."}, status=403)

        title    = request.data.get("title", "").strip()
        body     = request.data.get("body", "").strip()
        if not title or not body:
            return Response({"detail": "title and body required."}, status=400)

        audience_type   = request.data.get("audience_type", "ALL_USERS")
        audience_filter = request.data.get("audience_filter")
        scheduled_at_str = request.data.get("scheduled_at")
        scheduled_at    = None

        if scheduled_at_str:
            from django.utils.dateparse import parse_datetime
            scheduled_at = parse_datetime(scheduled_at_str)
            if not scheduled_at:
                return Response(
                    {"detail": "Invalid scheduled_at datetime format. Use ISO-8601."},
                    status=400,
                )

        try:
            broadcast = services.create_broadcast(
                title=title,
                body=body,
                created_by_id=request.user.pk,
                audience_type=audience_type,
                audience_filter=audience_filter or {},
                scheduled_at=scheduled_at,
            )
            return Response(
                {
                    "id":            str(broadcast.id),
                    "title":         broadcast.title,
                    "status":        broadcast.status,
                    "audience_type": broadcast.audience_type,
                    "scheduled_at":  broadcast.scheduled_at.isoformat() if broadcast.scheduled_at else None,
                    "created_at":    broadcast.created_at.isoformat(),
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as exc:
            logger.error("BroadcastCreateView: %s", exc)
            return _err(exc)
