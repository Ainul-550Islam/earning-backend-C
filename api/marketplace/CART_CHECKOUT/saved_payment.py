"""
CART_CHECKOUT/saved_payment.py — Saved Payment Methods (tokenized)
"""
from django.db import models
from django.conf import settings


class SavedPaymentMethod(models.Model):
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                     related_name="saved_payments_tenant")
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                     related_name="saved_payment_methods")
    method_type = models.CharField(max_length=20, choices=[
        ("bkash","bKash"),("nagad","Nagad"),("rocket","Rocket"),("card","Card"),
    ])
    display_label  = models.CharField(max_length=50, help_text="e.g. bKash ****1234")
    masked_number  = models.CharField(max_length=20)
    gateway_token  = models.CharField(max_length=500, blank=True, help_text="Stored token from gateway")
    is_default     = models.BooleanField(default=False)
    is_active      = models.BooleanField(default=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_saved_payment_method"

    def __str__(self):
        return f"{self.user.username} | {self.display_label}"

    def save(self, *args, **kwargs):
        if self.is_default:
            SavedPaymentMethod.objects.filter(user=self.user).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


def get_saved_methods(user, tenant) -> list:
    return list(
        SavedPaymentMethod.objects.filter(user=user, tenant=tenant, is_active=True)
        .values("id","method_type","display_label","masked_number","is_default")
    )


def delete_saved_method(user, method_id: int) -> bool:
    deleted, _ = SavedPaymentMethod.objects.filter(pk=method_id, user=user).delete()
    return deleted > 0
