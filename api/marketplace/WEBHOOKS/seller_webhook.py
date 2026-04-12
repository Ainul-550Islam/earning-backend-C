"""
WEBHOOKS/seller_webhook.py — Seller Event Webhooks
"""
import logging
from .webhook_manager import WebhookDispatcher

logger = logging.getLogger(__name__)


def fire_seller_event(tenant, event: str, seller):
    """Fire a seller-related outbound webhook."""
    if not getattr(tenant, "webhook_url", None):
        return
    data = {
        "seller_id":   seller.pk,
        "store_name":  seller.store_name,
        "store_slug":  seller.store_slug,
        "status":      seller.status,
        "rating":      str(seller.average_rating),
        "total_sales": seller.total_sales,
    }
    try:
        WebhookDispatcher(secret=str(tenant.api_key)).dispatch(tenant.webhook_url, event, data)
        logger.info("[Webhook] %s → seller#%s", event, seller.pk)
    except Exception as e:
        logger.error("[Webhook] seller event failed: %s", e)


def on_seller_verified(seller):
    fire_seller_event(seller.tenant, "seller.verified", seller)


def on_seller_suspended(seller):
    fire_seller_event(seller.tenant, "seller.suspended", seller)


def on_seller_activated(seller):
    fire_seller_event(seller.tenant, "seller.activated", seller)


def on_payout_completed(seller, payout):
    if not getattr(seller.tenant, "webhook_url", None):
        return
    data = {
        "seller_id":     seller.pk,
        "store_name":    seller.store_name,
        "payout_id":     payout.pk,
        "amount":        str(payout.amount),
        "method":        payout.method,
        "status":        payout.status,
        "reference_id":  payout.reference_id,
    }
    try:
        WebhookDispatcher(secret=str(seller.tenant.api_key)).dispatch(
            seller.tenant.webhook_url, "seller.payout_completed", data
        )
    except Exception as e:
        logger.error("[Webhook] payout webhook failed: %s", e)
