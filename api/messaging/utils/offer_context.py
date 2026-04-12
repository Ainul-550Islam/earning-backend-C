"""
Offer Context — Attach rich offer data to messages.
CPAlead shows offer details (payout, GEO, vertical) inside chat messages.
This module builds those rich message payloads.
"""
from __future__ import annotations
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def build_offer_card_message(
    offer_id: Any,
    offer_name: str,
    payout: str = "",
    vertical: str = "",
    countries: list = None,
    offer_url: str = "",
    preview_url: str = "",
    status: str = "active",
    description: str = "",
) -> dict:
    """
    Build a rich offer card payload for a chat message.
    Rendered by the frontend as an offer preview card.

    Usage:
        from messaging.utils.offer_context import build_offer_card_message
        payload = build_offer_card_message(offer_id=42, offer_name="Gaming App", payout="$3.00")
        services.send_chat_message(
            chat_id=chat.id, sender_id=manager.id,
            content=f"Check out this offer: {offer_name}",
            message_type="TEXT",
            metadata={"offer_card": payload},
        )
    """
    return {
        "type": "offer_card",
        "offer_id": str(offer_id),
        "offer_name": offer_name,
        "payout": payout,
        "vertical": vertical,
        "countries": countries or [],
        "offer_url": offer_url,
        "preview_url": preview_url,
        "status": status,
        "description": description[:300],
    }


def build_stats_summary_message(
    affiliate_id: Any,
    period: str = "today",
    clicks: int = 0,
    conversions: int = 0,
    revenue: str = "$0.00",
    epc: str = "$0.00",
    cr: str = "0%",
) -> dict:
    """
    Build a stats summary payload for manager → affiliate messages.
    E.g. weekly performance review sent by account manager.
    """
    return {
        "type": "stats_summary",
        "affiliate_id": str(affiliate_id),
        "period": period,
        "stats": {
            "clicks": clicks,
            "conversions": conversions,
            "revenue": revenue,
            "epc": epc,
            "conversion_rate": cr,
        },
    }


def build_payout_card_message(
    payout_id: Any,
    amount: str,
    payment_method: str = "",
    transaction_id: str = "",
    status: str = "processed",
    period: str = "",
) -> dict:
    """Build a payout summary card for inbox messages."""
    return {
        "type": "payout_card",
        "payout_id": str(payout_id),
        "amount": amount,
        "payment_method": payment_method,
        "transaction_id": transaction_id,
        "status": status,
        "period": period,
    }


def send_offer_recommendation_message(
    chat_id: Any,
    manager_id: Any,
    offer_id: Any,
    offer_name: str,
    payout: str = "",
    reason: str = "",
    tenant=None,
) -> None:
    """
    Manager sends an offer recommendation to affiliate in their chat thread.
    Creates a TEXT message with rich offer_card metadata.
    """
    try:
        from .. import services
        payload = build_offer_card_message(
            offer_id=offer_id,
            offer_name=offer_name,
            payout=payout,
            description=reason,
        )
        services.send_chat_message(
            chat_id=chat_id,
            sender_id=manager_id,
            content=f"I recommend this offer for you: {offer_name}{' — ' + reason if reason else ''}",
            metadata={"offer_card": payload},
            tenant=tenant,
        )
        logger.info("send_offer_recommendation_message: chat=%s offer=%s", chat_id, offer_id)
    except Exception as exc:
        logger.error("send_offer_recommendation_message: %s", exc)
