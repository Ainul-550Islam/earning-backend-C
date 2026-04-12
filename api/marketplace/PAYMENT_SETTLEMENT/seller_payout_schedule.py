"""
PAYMENT_SETTLEMENT/seller_payout_schedule.py — Scheduled Payout Configuration
"""
from django.db import models
from django.utils import timezone
from decimal import Decimal


class PayoutSchedule(models.Model):
    FREQUENCY_CHOICES = [
        ("instant",  "Instant (on escrow release)"),
        ("daily",    "Daily"),
        ("weekly",   "Weekly (every Saturday)"),
        ("biweekly", "Bi-weekly"),
        ("monthly",  "Monthly (1st of month)"),
    ]
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                     related_name="payout_schedules_tenant")
    seller      = models.OneToOneField("marketplace.SellerProfile", on_delete=models.CASCADE,
                                        related_name="payout_schedule")
    frequency   = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default="weekly")
    min_payout  = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("100"))
    method      = models.CharField(max_length=20, default="bkash")
    account     = models.CharField(max_length=50, blank=True)
    auto_payout = models.BooleanField(default=True)
    next_payout = models.DateTimeField(null=True, blank=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_payout_schedule"

    def calculate_next_payout_date(self):
        from datetime import timedelta
        now = timezone.now()
        if self.frequency == "instant":
            return now
        if self.frequency == "daily":
            return (now + timedelta(days=1)).replace(hour=9, minute=0, second=0)
        if self.frequency == "weekly":
            days_until_saturday = (5 - now.weekday()) % 7
            return (now + timedelta(days=days_until_saturday)).replace(hour=9, minute=0, second=0)
        if self.frequency == "monthly":
            if now.month == 12:
                return now.replace(year=now.year+1, month=1, day=1, hour=9, minute=0)
            return now.replace(month=now.month+1, day=1, hour=9, minute=0)
        return now + timedelta(days=14)


def get_sellers_due_for_payout(tenant) -> list:
    now = timezone.now()
    return list(
        PayoutSchedule.objects.filter(
            seller__tenant=tenant, is_active=True, auto_payout=True,
            next_payout__lte=now,
        ).select_related("seller")
    )


def process_scheduled_payouts(tenant) -> dict:
    from api.marketplace.PAYMENT_SETTLEMENT.escrow_manager import release_all_due
    result = release_all_due(tenant)
    # Update next payout dates
    for schedule in get_sellers_due_for_payout(tenant):
        schedule.next_payout = schedule.calculate_next_payout_date()
        schedule.save(update_fields=["next_payout"])
    return result
