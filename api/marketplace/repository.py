"""
marketplace/repository.py — Data Access Layer (Repository Pattern)
====================================================================
Thin wrappers over ORM queries. Services call repositories;
repositories never call services.
"""

from __future__ import annotations

from typing import Optional
from django.db.models import QuerySet, Avg, Sum, Count, Q
from django.utils import timezone

from .models import (
    Product, ProductInventory, Category,
    SellerProfile, Order, OrderItem,
    EscrowHolding, Coupon,
)
from .enums import EscrowStatus, OrderStatus, ProductStatus


# ──────────────────────────────────────────────
# ProductRepository
# ──────────────────────────────────────────────
class ProductRepository:

    @staticmethod
    def active(tenant) -> QuerySet:
        return Product.objects.filter(tenant=tenant, status=ProductStatus.ACTIVE)

    @staticmethod
    def by_category(tenant, category_id: int) -> QuerySet:
        return ProductRepository.active(tenant).filter(category_id=category_id)

    @staticmethod
    def search(tenant, query: str) -> QuerySet:
        return ProductRepository.active(tenant).filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(tags__icontains=query)
        )

    @staticmethod
    def featured(tenant, limit: int = 12) -> QuerySet:
        return ProductRepository.active(tenant).filter(is_featured=True)[:limit]

    @staticmethod
    def low_stock(tenant) -> QuerySet:
        return ProductInventory.objects.filter(
            variant__product__tenant=tenant,
            quantity__lte=10,
        ).select_related("variant__product")


# ──────────────────────────────────────────────
# SellerRepository
# ──────────────────────────────────────────────
class SellerRepository:

    @staticmethod
    def get_by_user(user, tenant) -> Optional[SellerProfile]:
        return SellerProfile.objects.filter(user=user, tenant=tenant).first()

    @staticmethod
    def active_sellers(tenant) -> QuerySet:
        return SellerProfile.objects.filter(tenant=tenant, status="active")

    @staticmethod
    def seller_stats(seller: SellerProfile) -> dict:
        items = OrderItem.objects.filter(seller=seller)
        return {
            "total_orders": items.values("order").distinct().count(),
            "total_revenue": items.aggregate(total=Sum("seller_net"))["total"] or 0,
            "avg_rating": seller.average_rating,
            "total_products": seller.products.count(),
        }


# ──────────────────────────────────────────────
# OrderRepository
# ──────────────────────────────────────────────
class OrderRepository:

    @staticmethod
    def for_user(user, tenant) -> QuerySet:
        return Order.objects.filter(user=user, tenant=tenant).order_by("-created_at")

    @staticmethod
    def for_seller(seller: SellerProfile) -> QuerySet:
        order_ids = OrderItem.objects.filter(seller=seller).values_list("order_id", flat=True)
        return Order.objects.filter(pk__in=order_ids).order_by("-created_at")

    @staticmethod
    def pending(tenant) -> QuerySet:
        return Order.objects.filter(tenant=tenant, status=OrderStatus.PENDING)

    @staticmethod
    def delivered_after(tenant, date) -> QuerySet:
        return Order.objects.filter(
            tenant=tenant, status=OrderStatus.DELIVERED, updated_at__gte=date
        )


# ──────────────────────────────────────────────
# EscrowRepository
# ──────────────────────────────────────────────
class EscrowRepository:

    @staticmethod
    def releasable(tenant) -> QuerySet:
        """Escrows past their release_after date and still holding."""
        return EscrowHolding.objects.filter(
            tenant=tenant,
            status=EscrowStatus.HOLDING,
            release_after__lte=timezone.now(),
        ).select_related("seller", "order_item")


# ──────────────────────────────────────────────
# CouponRepository
# ──────────────────────────────────────────────
class CouponRepository:

    @staticmethod
    def valid_public(tenant) -> QuerySet:
        now = timezone.now()
        return Coupon.objects.filter(
            tenant=tenant,
            is_active=True,
            is_public=True,
            valid_from__lte=now,
            valid_until__gte=now,
        )

    @staticmethod
    def get_by_code(tenant, code: str) -> Optional[Coupon]:
        return Coupon.objects.filter(tenant=tenant, code=code).first()
