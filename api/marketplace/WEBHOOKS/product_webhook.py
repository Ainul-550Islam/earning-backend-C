"""WEBHOOKS/product_webhook.py — Product Event Webhooks"""
from .webhook_manager import WebhookDispatcher


def fire_product_event(product, event: str):
    tenant = product.tenant
    if not getattr(tenant, "webhook_url", None):
        return
    data = {
        "product_id": product.pk,
        "name":       product.name,
        "status":     product.status,
        "seller_id":  product.seller_id,
    }
    WebhookDispatcher(secret=str(tenant.api_key)).dispatch(tenant.webhook_url, event, data)


def on_product_approved(product):
    fire_product_event(product, "product.approved")


def on_product_banned(product):
    fire_product_event(product, "product.banned")


def on_product_low_stock(product, stock: int):
    tenant = product.tenant
    if not getattr(tenant,"webhook_url",None):
        return
    data = {"product_id": product.pk, "name": product.name, "stock": stock}
    WebhookDispatcher(secret=str(tenant.api_key)).dispatch(tenant.webhook_url, "product.low_stock", data)
