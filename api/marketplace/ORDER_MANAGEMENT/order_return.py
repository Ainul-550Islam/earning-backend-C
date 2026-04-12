"""
ORDER_MANAGEMENT/order_return.py — Order Return & Replacement Management
"""
from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from api.marketplace.models import Order, OrderItem
from api.marketplace.enums import OrderStatus


class ReturnRequest(models.Model):
    RETURN_TYPES = [("return","Return & Refund"),("exchange","Exchange"),("replacement","Replacement")]
    RETURN_REASONS = [
        ("damaged","Damaged in transit"),("defective","Defective product"),
        ("wrong_item","Wrong item received"),("not_as_described","Not as described"),
        ("size_fit","Size/fit issue"),("changed_mind","Changed my mind"),("other","Other"),
    ]
    STATUS_CHOICES = [
        ("requested","Requested"),("approved","Approved"),("rejected","Rejected"),
        ("item_received","Item Received"),("completed","Completed"),
    ]
    tenant       = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                      related_name="return_requests_tenant")
    order_item   = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="return_requests")
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    return_type  = models.CharField(max_length=15, choices=RETURN_TYPES, default="return")
    reason       = models.CharField(max_length=25, choices=RETURN_REASONS)
    description  = models.TextField()
    images       = models.JSONField(default=list, blank=True)
    status       = models.CharField(max_length=15, choices=STATUS_CHOICES, default="requested")
    pickup_address = models.TextField(blank=True)
    replacement_variant_id = models.IntegerField(null=True, blank=True)
    reviewed_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name="reviewed_returns")
    reviewed_at  = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    pickup_scheduled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_return_request"
        ordering  = ["-created_at"]

    def __str__(self):
        return f"Return#{self.pk} | {self.order_item.order.order_number} | {self.return_type}"


def can_request_return(order_item: OrderItem, return_window_days: int = 7) -> dict:
    if order_item.order.status != OrderStatus.DELIVERED:
        return {"eligible": False, "reason": "Order must be delivered to request a return"}
    days_since = (timezone.now() - order_item.order.updated_at).days
    if days_since > return_window_days:
        return {"eligible": False, "reason": f"Return window expired ({return_window_days} days after delivery)"}
    if ReturnRequest.objects.filter(order_item=order_item, status__in=["requested","approved","item_received"]).exists():
        return {"eligible": False, "reason": "A return request already exists for this item"}
    return {"eligible": True, "reason": ""}


@transaction.atomic
def create_return_request(order_item: OrderItem, user, return_type: str,
                           reason: str, description: str, pickup_address: str = "") -> ReturnRequest:
    check = can_request_return(order_item)
    if not check["eligible"]:
        raise ValueError(check["reason"])

    return ReturnRequest.objects.create(
        tenant=order_item.tenant, order_item=order_item, user=user,
        return_type=return_type, reason=reason, description=description,
        pickup_address=pickup_address or order_item.order.shipping_address,
    )


@transaction.atomic
def approve_return(return_req: ReturnRequest, admin_user, pickup_date=None) -> ReturnRequest:
    return_req.status         = "approved"
    return_req.reviewed_by    = admin_user
    return_req.reviewed_at    = timezone.now()
    return_req.pickup_scheduled_at = pickup_date
    return_req.save()

    # Update order item status
    OrderItem.objects.filter(pk=return_req.order_item_id).update(item_status=OrderStatus.RETURNED)
    return return_req


def reject_return(return_req: ReturnRequest, admin_user, reason: str) -> ReturnRequest:
    return_req.status          = "rejected"
    return_req.reviewed_by     = admin_user
    return_req.reviewed_at     = timezone.now()
    return_req.rejection_reason= reason
    return_req.save()
    return return_req


def initiate_return(order: Order, reason: str) -> bool:
    """Legacy helper — initiate return for full order."""
    if order.status != OrderStatus.DELIVERED:
        return False
    order.status = OrderStatus.RETURNED
    order.save(update_fields=["status"])
    return True


def get_return_stats(tenant) -> dict:
    qs = ReturnRequest.objects.filter(tenant=tenant)
    from django.db.models import Count
    by_status = dict(qs.values("status").annotate(c=Count("id")).values_list("status","c"))
    return {
        "total":     qs.count(),
        "by_status": by_status,
        "by_reason": dict(qs.values("reason").annotate(c=Count("id")).values_list("reason","c")),
    }
