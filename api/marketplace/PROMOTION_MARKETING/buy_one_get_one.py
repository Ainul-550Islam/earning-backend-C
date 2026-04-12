"""
PROMOTION_MARKETING/buy_one_get_one.py — Buy X Get Y Free / Discounted Promotions
"""
from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone


class BOGOPromotion(models.Model):
    tenant       = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                      related_name="bogo_promotions_tenant")
    name         = models.CharField(max_length=200)
    promo_type   = models.CharField(max_length=20, choices=[
        ("buy_x_get_y_free", "Buy X Get Y Free"),
        ("buy_x_get_y_discount","Buy X Get Y% Off"),
        ("buy_x_pay_for_y", "Buy X Pay for Y"),
    ])
    buy_quantity = models.PositiveSmallIntegerField(default=1, help_text="Required purchase quantity")
    get_quantity = models.PositiveSmallIntegerField(default=1, help_text="Free/discounted quantity")
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("100"),
                                            help_text="100 = fully free")
    applicable_products = models.ManyToManyField("marketplace.Product", blank=True)
    applicable_categories = models.ManyToManyField("marketplace.Category", blank=True)
    starts_at    = models.DateTimeField()
    ends_at      = models.DateTimeField()
    is_active    = models.BooleanField(default=True)
    usage_count  = models.PositiveIntegerField(default=0)
    max_uses     = models.PositiveIntegerField(default=10000)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_bogo_promotion"

    @property
    def is_live(self) -> bool:
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.ends_at and self.usage_count < self.max_uses


def apply_bogo_to_cart(cart) -> dict:
    """Apply BOGO promotion rules to cart and return discount breakdown."""
    tenant = cart.tenant
    now    = timezone.now()
    promos = BOGOPromotion.objects.filter(
        tenant=tenant, is_active=True,
        starts_at__lte=now, ends_at__gte=now,
    ).prefetch_related("applicable_products","applicable_categories")

    total_discount = Decimal("0.00")
    applied = []

    for promo in promos:
        if not promo.is_live:
            continue
        promo_products = set(promo.applicable_products.values_list("pk", flat=True))
        cart_items_eligible = [
            item for item in cart.items.all()
            if item.variant.product_id in promo_products
        ]
        for item in cart_items_eligible:
            sets = item.quantity // promo.buy_quantity
            if sets == 0:
                continue
            free_qty = sets * promo.get_quantity
            discount = item.unit_price * free_qty * promo.discount_percent / 100
            total_discount += discount
            applied.append({
                "promo":    promo.name,
                "product":  item.variant.product.name,
                "free_qty": free_qty,
                "discount": str(discount.quantize(Decimal("0.01"))),
            })

    return {"total_discount": str(total_discount.quantize(Decimal("0.01"))), "applied_promos": applied}
