"""
DATABASE_MODELS/shipping_table.py — Shipping Table Reference
"""
from api.marketplace.models import OrderTracking
from api.marketplace.SHIPPING_LOGISTICS.shipping_method import ShippingMethod
from api.marketplace.SHIPPING_LOGISTICS.shipping_rate import get_shipping_rate, calculate_shipping_fee
from api.marketplace.SHIPPING_LOGISTICS.shipping_carrier import ShippingCarrier
from api.marketplace.SHIPPING_LOGISTICS.shipping_zone import ShippingZone
from api.marketplace.SHIPPING_LOGISTICS.delivery_partner import DeliveryPartner, DeliveryAssignment
from django.db.models import Count


def pending_shipments(tenant) -> list:
    from api.marketplace.models import Order
    from api.marketplace.enums import OrderStatus
    return list(
        Order.objects.filter(
            tenant=tenant, status=OrderStatus.CONFIRMED
        ).select_related("user").order_by("created_at")
    )


def carrier_performance(tenant) -> list:
    return list(
        DeliveryAssignment.objects.filter(order__tenant=tenant)
        .values("partner__name","status")
        .annotate(count=Count("id"))
        .order_by("partner__name","status")
    )


__all__ = [
    "OrderTracking","ShippingMethod","ShippingCarrier","ShippingZone",
    "DeliveryPartner","DeliveryAssignment",
    "get_shipping_rate","calculate_shipping_fee",
    "pending_shipments","carrier_performance",
]
