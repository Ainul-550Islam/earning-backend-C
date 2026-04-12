"""
marketplace/tasks.py — Production Celery Tasks
================================================
All async jobs for the marketplace module.

Register in Celery beat schedule (settings.py):
  CELERY_BEAT_SCHEDULE = {
      "marketplace-auto-release-escrow": {
          "task": "marketplace.auto_release_escrow",
          "schedule": crontab(hour="*/1"),     # every hour
      },
      "marketplace-cancel-unpaid-orders": {
          "task": "marketplace.cancel_unpaid_orders",
          "schedule": crontab(minute="*/30"),  # every 30 min
      },
      "marketplace-release-expired-reservations": {
          "task": "marketplace.release_expired_reservations",
          "schedule": crontab(minute="*/15"),  # every 15 min
      },
      "marketplace-sync-seller-stats": {
          "task": "marketplace.sync_seller_stats",
          "schedule": crontab(hour="3"),       # 3 AM daily
      },
      "marketplace-update-product-ratings": {
          "task": "marketplace.update_product_ratings",
          "schedule": crontab(hour="4"),       # 4 AM daily
      },
  }
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from celery import shared_task
except ImportError:
    def shared_task(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator if args and callable(args[0]) else decorator


# ─────────────────────────────────────────────────────────────────────────────
# Escrow
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    name="marketplace.auto_release_escrow",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def auto_release_escrow(self):
    """Release all eligible escrows (7-day window passed, no disputes)."""
    from api.tenants.models import Tenant
    from api.marketplace.PAYMENT_SETTLEMENT.escrow_manager import release_all_due

    total = {"released": 0, "skipped": 0, "errors": []}
    for tenant in Tenant.objects.filter(is_active=True):
        try:
            result = release_all_due(tenant)
            total["released"] += result["released"]
            total["skipped"]  += result["skipped"]
            total["errors"].extend(result["errors"])
        except Exception as e:
            logger.error("[Task] auto_release_escrow tenant#%s: %s", tenant.pk, e)
            try:
                self.retry(exc=e)
            except Exception:
                pass

    logger.info("[Task] auto_release_escrow: %s", total)
    return total


@shared_task(name="marketplace.process_gateway_refund", bind=True, max_retries=5, default_retry_delay=60)
def process_gateway_refund(self, order_item_id: int, amount: str):
    """
    Actually call the payment gateway to refund money to buyer.
    Retries up to 5 times with 60s delay.
    """
    from decimal import Decimal
    from api.marketplace.models import OrderItem, PaymentTransaction
    from api.marketplace.enums import PaymentStatus

    try:
        item  = OrderItem.objects.select_related("order__tenant").get(pk=order_item_id)
        order = item.order

        # Find the original successful transaction
        tx = PaymentTransaction.objects.filter(
            order=order, status=PaymentStatus.SUCCESS
        ).first()

        if not tx:
            logger.warning("[Task] process_gateway_refund: no successful tx for order#%s", order.pk)
            return {"status": "skipped", "reason": "no_transaction"}

        # Call gateway refund API
        from api.marketplace.PAYMENT_SETTLEMENT.payment_gateway import get_gateway
        gateway = get_gateway(tx.method, {})   # credentials loaded from settings
        result  = gateway.refund(
            payment_id=tx.gateway_transaction_id,
            amount=float(Decimal(amount)),
        )
        logger.info("[Task] Gateway refund result for OrderItem#%s: %s", order_item_id, result)
        return result

    except Exception as e:
        logger.error("[Task] process_gateway_refund error: %s", e)
        raise self.retry(exc=e)


# ─────────────────────────────────────────────────────────────────────────────
# Orders
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(name="marketplace.cancel_unpaid_orders", bind=True, max_retries=2)
def cancel_unpaid_orders(self):
    """Auto-cancel orders not paid within 48 hours."""
    from datetime import timedelta
    from django.utils import timezone
    from api.marketplace.models import Order
    from api.marketplace.enums import OrderStatus

    cutoff = timezone.now() - timedelta(hours=48)
    stale  = Order.objects.filter(
        status=OrderStatus.PENDING,
        is_paid=False,
        created_at__lt=cutoff,
    )
    count = stale.count()

    for order in stale.iterator(chunk_size=100):
        try:
            order.cancel(reason="Auto-cancelled: payment timeout (48h)")
            # Release inventory
            for item in order.items.filter(variant__isnull=False):
                from api.marketplace.PRODUCT_MANAGEMENT.product_inventory import release_reservation
                release_reservation(item.variant_id, item.quantity)
        except Exception as e:
            logger.error("[Task] cancel_unpaid_orders order#%s: %s", order.pk, e)

    logger.info("[Task] Cancelled %s unpaid orders", count)
    return {"cancelled": count}


@shared_task(name="marketplace.release_expired_reservations")
def release_expired_reservations():
    """Release inventory reservations for timed-out unpaid orders."""
    from api.tenants.models import Tenant
    from api.marketplace.PRODUCT_MANAGEMENT.product_inventory import InventoryManager

    total = 0
    for tenant in Tenant.objects.filter(is_active=True):
        try:
            released = InventoryManager.release_expired_reservations(tenant)
            total   += released
        except Exception as e:
            logger.error("[Task] release_expired_reservations tenant#%s: %s", tenant.pk, e)

    logger.info("[Task] Released %s expired inventory reservations", total)
    return {"released": total}


# ─────────────────────────────────────────────────────────────────────────────
# Bulk upload
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    name="marketplace.process_bulk_upload",
    bind=True,
    max_retries=1,
    soft_time_limit=1800,    # 30 min soft limit
    time_limit=2100,         # 35 min hard kill
)
def process_bulk_upload(self, job_id: str):
    """
    Process a bulk product upload job.
    Reads rows from cache in batches of 100 — no HTTP timeout.
    """
    logger.info("[Task] process_bulk_upload started: job_id=%s", job_id)
    try:
        from api.marketplace.VENDOR_TOOLS.bulk_upload import process_bulk_upload_job
        process_bulk_upload_job(job_id)
    except Exception as e:
        logger.error("[Task] process_bulk_upload job_id=%s error: %s", job_id, e)
        from django.core.cache import cache
        from api.marketplace.VENDOR_TOOLS.bulk_upload import _job_cache_key
        cache.set(_job_cache_key(job_id), {
            "job_id": job_id, "status": "failed", "error": str(e)
        }, 3600)
        raise self.retry(exc=e, max_retries=1)


# ─────────────────────────────────────────────────────────────────────────────
# Analytics / Stats
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(name="marketplace.update_product_ratings")
def update_product_ratings():
    """Recalculate product average ratings from reviews."""
    from django.db.models import Avg, Count
    from api.marketplace.models import Product, ProductReview

    updated = 0
    for product in Product.objects.filter(reviews__isnull=False).distinct().iterator(chunk_size=500):
        agg = ProductReview.objects.filter(
            product=product, is_approved=True
        ).aggregate(avg=Avg("rating"), count=Count("id"))
        Product.objects.filter(pk=product.pk).update(
            average_rating=round(agg["avg"] or 0, 2),
            review_count=agg["count"] or 0,
        )
        updated += 1

    logger.info("[Task] Updated ratings for %s products", updated)
    return {"updated": updated}


@shared_task(name="marketplace.sync_seller_stats")
def sync_seller_stats():
    """Denormalise seller metrics (total_sales, total_revenue, avg_rating)."""
    from django.db.models import Sum, Count, Avg
    from api.marketplace.models import SellerProfile, OrderItem

    for seller in SellerProfile.objects.filter(status="active").iterator(chunk_size=200):
        agg = OrderItem.objects.filter(seller=seller).aggregate(
            total_items=Count("id"),
            total_revenue=Sum("seller_net"),
        )
        SellerProfile.objects.filter(pk=seller.pk).update(
            total_sales=agg["total_items"] or 0,
            total_revenue=agg["total_revenue"] or 0,
        )

    logger.info("[Task] sync_seller_stats complete")


@shared_task(name="marketplace.notify_low_stock")
def notify_low_stock():
    """Notify sellers of low inventory."""
    from api.marketplace.PRODUCT_MANAGEMENT.product_inventory import get_low_stock_items
    from api.tenants.models import Tenant

    total = 0
    for tenant in Tenant.objects.filter(is_active=True):
        items = get_low_stock_items(tenant, threshold=10)
        for inv in items:
            try:
                seller_email = inv.variant.product.seller.user.email
                logger.info(
                    "[Task][LowStock] %s — %s units left → %s",
                    inv.variant.product.name, inv.quantity, seller_email,
                )
                # TODO: send actual email/push notification
                total += 1
            except Exception as e:
                logger.error("[Task] notify_low_stock item error: %s", e)

    return {"notified": total}


# ─────────────────────────────────────────────────────────────────────────────
# Elasticsearch
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(name="marketplace.index_product_es", bind=True, max_retries=3, default_retry_delay=30)
def index_product_es(self, product_id: int, tenant_id: int):
    """Index a single product to Elasticsearch after save."""
    try:
        from api.marketplace.SEARCH_DISCOVERY.elasticsearch_sync import index_product_async
        index_product_async(product_id, tenant_id)
    except Exception as e:
        logger.error("[Task] index_product_es #%s: %s", product_id, e)
        raise self.retry(exc=e)


@shared_task(name="marketplace.bulk_reindex_es", soft_time_limit=3600)
def bulk_reindex_es(tenant_id: int):
    """Full Elasticsearch reindex for a tenant."""
    from api.tenants.models import Tenant
    from api.marketplace.SEARCH_DISCOVERY.elasticsearch_sync import ElasticsearchSync

    try:
        tenant = Tenant.objects.get(pk=tenant_id)
        result = ElasticsearchSync.bulk_reindex(tenant)
        logger.info("[Task] bulk_reindex_es tenant#%s: %s", tenant_id, result)
        return result
    except Exception as e:
        logger.error("[Task] bulk_reindex_es tenant#%s: %s", tenant_id, e)
        raise
