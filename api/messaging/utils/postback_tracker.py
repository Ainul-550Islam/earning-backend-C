"""
Postback Tracker — CPA postback integration with messaging.
When a postback fires, this module:
1. Creates a real-time WS notification for the affiliate
2. Updates conversation context with conversion data
3. Fires the conversion_received signal for messaging notification
"""
from __future__ import annotations
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def notify_conversion_via_ws(
    affiliate_id: Any,
    conversion_id: str,
    offer_id: Any,
    offer_name: str,
    payout_amount: str,
    click_id: str = "",
    metadata: Optional[dict] = None,
) -> bool:
    """
    Real-time WebSocket push when a postback fires.
    Called directly from PostbackView.post() in ad_networks module.
    """
    try:
        from ..utils.notifier import send_websocket_event
        send_websocket_event(
            group_name=f"user_devices_{affiliate_id}",
            event_type="cpa.conversion",
            data={
                "type": "conversion.received",
                "conversion_id": str(conversion_id),
                "offer_id": str(offer_id),
                "offer_name": offer_name,
                "payout_amount": payout_amount,
                "click_id": click_id,
                **(metadata or {}),
            },
        )
        logger.info("notify_conversion_via_ws: affiliate=%s offer=%s amount=%s",
                    affiliate_id, offer_id, payout_amount)
        return True
    except Exception as exc:
        logger.error("notify_conversion_via_ws: %s", exc)
        return False


def fire_conversion_signal(
    affiliate_id: Any,
    conversion_id: str,
    offer_id: Any,
    offer_name: str,
    payout_amount: str,
    tenant=None,
) -> None:
    """
    Fire the messaging conversion_received signal.
    This triggers the receiver which creates a CPANotification.
    """
    try:
        from ..signals_cpa import conversion_received
        conversion_received.send(
            sender=None,
            affiliate_id=affiliate_id,
            conversion_id=conversion_id,
            offer_id=offer_id,
            offer_name=offer_name,
            payout_amount=payout_amount,
            tenant=tenant,
        )
    except Exception as exc:
        logger.error("fire_conversion_signal: %s", exc)


def send_postback_failed_alert(
    affiliate_id: Any,
    offer_id: Any,
    offer_name: str,
    error_detail: str = "",
    tenant=None,
) -> None:
    """Fire postback_failed signal → triggers URGENT notification."""
    try:
        from ..signals_cpa import postback_failed
        postback_failed.send(
            sender=None,
            affiliate_id=affiliate_id,
            offer_id=offer_id,
            offer_name=offer_name,
            error_detail=error_detail,
            tenant=tenant,
        )
    except Exception as exc:
        logger.error("send_postback_failed_alert: %s", exc)


def inject_conversion_context_to_chat(
    affiliate_id: Any,
    conversion_id: str,
    offer_id: Any,
    offer_name: str,
    payout_amount: str,
    manager_id: Optional[Any] = None,
    tenant=None,
) -> None:
    """
    Inject a system message into the affiliate ↔ manager chat
    when a significant conversion happens (e.g., first conversion or high-value).
    """
    try:
        from ..models import AffiliateConversationThread, ChatMessage
        from ..choices import MessageType
        try:
            thread = AffiliateConversationThread.objects.get(affiliate_id=affiliate_id)
            if thread.chat_id:
                ChatMessage.objects.create(
                    chat_id=thread.chat_id,
                    message_type=MessageType.SYSTEM,
                    content=(
                        f"Conversion received on \"{offer_name}\". "
                        f"Payout: {payout_amount}."
                    ),
                    metadata={
                        "event": "conversion",
                        "conversion_id": str(conversion_id),
                        "offer_id": str(offer_id),
                        "offer_name": offer_name,
                        "payout_amount": payout_amount,
                    },
                    tenant=tenant,
                )
        except AffiliateConversationThread.DoesNotExist:
            pass
    except Exception as exc:
        logger.error("inject_conversion_context_to_chat: %s", exc)
