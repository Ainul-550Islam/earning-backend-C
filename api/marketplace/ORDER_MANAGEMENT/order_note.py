"""ORDER_MANAGEMENT/order_note.py — Order Notes (buyer/seller/admin)"""
from django.db import models
from django.conf import settings
from api.marketplace.models import Order
from api.tenants.models import Tenant


class OrderNote(models.Model):
    tenant      = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True,
                                    related_name="marketplace_order_notes_tenant")
    order       = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="notes")
    author      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, related_name="marketplace_order_notes")
    role        = models.CharField(max_length=10,
                                   choices=[("buyer","Buyer"),("seller","Seller"),("admin","Admin")])
    text        = models.TextField()
    is_internal = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_order_note"
        ordering  = ["created_at"]

    def __str__(self):
        return f"[{self.role}] {self.text[:60]}"


def add_note(order: Order, author, role: str, text: str, internal: bool = False) -> OrderNote:
    return OrderNote.objects.create(
        tenant=order.tenant, order=order, author=author,
        role=role, text=text, is_internal=internal,
    )
