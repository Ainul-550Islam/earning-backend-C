"""
MOBILE_MARKETPLACE/app_launch_offer.py — App Launch & First-Open Offers
"""
from django.db import models
from django.utils import timezone
from django.conf import settings


class AppLaunchOffer(models.Model):
    tenant        = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                       related_name="app_launch_offers_tenant")
    name          = models.CharField(max_length=200)
    offer_type    = models.CharField(max_length=20, choices=[
        ("discount_code","Discount Code"),("free_shipping","Free Shipping"),
        ("bonus_points","Bonus Points"),("cashback","Cashback"),
    ])
    value         = models.DecimalField(max_digits=8, decimal_places=2)
    coupon_code   = models.CharField(max_length=50, blank=True)
    banner_image  = models.URLField(blank=True)
    starts_at     = models.DateTimeField()
    ends_at       = models.DateTimeField()
    max_uses      = models.PositiveIntegerField(default=10000)
    used_count    = models.PositiveIntegerField(default=0)
    platform      = models.CharField(max_length=10, default="all",
                                      choices=[("all","All"),("android","Android"),("ios","iOS")])
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_app_launch_offer"

    @property
    def is_live(self) -> bool:
        now = timezone.now()
        return (self.is_active and self.used_count < self.max_uses
                and self.starts_at <= now <= self.ends_at)


class UserAppLaunchClaim(models.Model):
    user   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    offer  = models.ForeignKey(AppLaunchOffer, on_delete=models.CASCADE)
    claimed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_user_launch_claim"
        unique_together = [("user","offer")]


def get_active_launch_offer(tenant, platform: str = "all") -> dict:
    now = timezone.now()
    offer = AppLaunchOffer.objects.filter(
        tenant=tenant, is_active=True,
        starts_at__lte=now, ends_at__gte=now,
        platform__in=[platform, "all"],
    ).order_by("-created_at").first()

    if not offer or not offer.is_live:
        return {}

    return {
        "id":          offer.pk,
        "name":        offer.name,
        "offer_type":  offer.offer_type,
        "value":       str(offer.value),
        "coupon_code": offer.coupon_code,
        "banner_image":offer.banner_image,
        "ends_at":     offer.ends_at.isoformat(),
    }


def claim_offer(user, offer_id: int, tenant) -> dict:
    try:
        offer = AppLaunchOffer.objects.get(pk=offer_id, tenant=tenant)
    except AppLaunchOffer.DoesNotExist:
        return {"success": False, "reason": "Offer not found"}

    if not offer.is_live:
        return {"success": False, "reason": "Offer expired or unavailable"}

    _, created = UserAppLaunchClaim.objects.get_or_create(user=user, offer=offer)
    if not created:
        return {"success": False, "reason": "Already claimed"}

    AppLaunchOffer.objects.filter(pk=offer.pk).update(used_count=models.F("used_count") + 1)
    return {"success": True, "coupon_code": offer.coupon_code, "offer_type": offer.offer_type, "value": str(offer.value)}
