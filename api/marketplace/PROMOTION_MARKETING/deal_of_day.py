"""
PROMOTION_MARKETING/deal_of_day.py — Deal of the Day Manager
"""
from django.db import models, transaction
from django.utils import timezone
from decimal import Decimal


class DealOfDay(models.Model):
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                     related_name="deal_of_day_tenant")
    product     = models.ForeignKey("marketplace.Product", on_delete=models.CASCADE)
    variant     = models.ForeignKey("marketplace.ProductVariant", on_delete=models.SET_NULL,
                                     null=True, blank=True)
    deal_price  = models.DecimalField(max_digits=12, decimal_places=2)
    original_price = models.DecimalField(max_digits=12, decimal_places=2)
    max_quantity= models.PositiveIntegerField(default=100, help_text="Limited stock for deal")
    sold_count  = models.PositiveIntegerField(default=0)
    date        = models.DateField()
    starts_at   = models.DateTimeField()
    ends_at     = models.DateTimeField()
    is_active   = models.BooleanField(default=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_deal_of_day"
        unique_together = [("tenant","date")]

    @property
    def discount_percent(self) -> float:
        if self.original_price > 0:
            return round((1 - float(self.deal_price)/float(self.original_price))*100, 1)
        return 0

    @property
    def is_live(self) -> bool:
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.ends_at and self.sold_count < self.max_quantity

    @property
    def remaining(self) -> int:
        return max(0, self.max_quantity - self.sold_count)


def get_todays_deal(tenant):
    today = timezone.now().date()
    now   = timezone.now()
    return DealOfDay.objects.filter(
        tenant=tenant, date=today, is_active=True,
        starts_at__lte=now, ends_at__gte=now,
    ).select_related("product","variant").first()


@transaction.atomic
def create_deal(tenant, product, deal_price: Decimal, starts_at, ends_at,
                max_quantity: int = 100) -> DealOfDay:
    return DealOfDay.objects.create(
        tenant=tenant, product=product,
        deal_price=deal_price, original_price=product.base_price,
        max_quantity=max_quantity, date=starts_at.date(),
        starts_at=starts_at, ends_at=ends_at,
    )
