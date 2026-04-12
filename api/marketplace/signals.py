"""
marketplace/signals.py — Django Signals
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from .models import (
    Order, OrderItem, ProductReview, EscrowHolding,
    SellerProfile,
)
from .enums import OrderStatus


@receiver(post_save, sender=Order)
def order_status_changed(sender, instance: Order, created, **kwargs):
    """On order delivered → create escrow if not already created."""
    if not created and instance.status == OrderStatus.DELIVERED:
        from .constants import ESCROW_RELEASE_DAYS
        for item in instance.items.all():
            release_after = timezone.now() + timezone.timedelta(days=ESCROW_RELEASE_DAYS)
            EscrowHolding.objects.get_or_create(
                order_item=item,
                defaults={
                    "tenant": instance.tenant,
                    "seller": item.seller,
                    "gross_amount": item.subtotal,
                    "commission_deducted": item.commission_amount,
                    "net_amount": item.seller_net,
                    "release_after": release_after,
                },
            )


@receiver(post_save, sender=ProductReview)
def update_product_rating_on_review(sender, instance: ProductReview, created, **kwargs):
    """Recalculate product average rating after a review is saved."""
    if instance.is_approved:
        from django.db.models import Avg
        product = instance.product
        agg = product.reviews.filter(is_approved=True).aggregate(avg=Avg("rating"))
        avg = agg["avg"] or 0
        count = product.reviews.filter(is_approved=True).count()
        from .models import Product
        Product.objects.filter(pk=product.pk).update(
            average_rating=round(avg, 2),
            review_count=count,
        )


@receiver(post_save, sender=OrderItem)
def update_seller_total_sales(sender, instance: OrderItem, created, **kwargs):
    if created and instance.seller:
        SellerProfile.objects.filter(pk=instance.seller_id).update(
            total_sales=instance.seller.total_sales + 1
        )
