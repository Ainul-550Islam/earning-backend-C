# api/wallet/managers.py
"""
Custom Django model managers for the wallet app.
Each manager adds domain-specific query methods.
"""
from decimal import Decimal
from django.db import models
from django.utils import timezone


class WalletManager(models.Manager):
    """Custom manager for Wallet model."""

    def active(self):
        return self.filter(is_locked=False)

    def locked(self):
        return self.filter(is_locked=True)

    def with_positive_balance(self):
        return self.filter(current_balance__gt=0)

    def get_or_create_for_user(self, user):
        wallet, created = self.get_or_create(user=user, defaults={"currency": "BDT"})
        return wallet, created

    def high_balance(self, threshold: Decimal = Decimal("10000")):
        return self.filter(current_balance__gte=threshold)

    def inactive_since(self, days: int = 90):
        cutoff = timezone.now() - __import__("datetime").timedelta(days=days)
        return self.filter(
            models.Q(last_activity_at__lt=cutoff) | models.Q(last_activity_at__isnull=True)
        )

    def with_pending_withdrawals(self):
        return self.filter(pending_balance__gt=0)


class WalletTransactionManager(models.Manager):
    """Custom manager for WalletTransaction model."""

    def approved(self):
        return self.filter(status="approved")

    def pending(self):
        return self.filter(status="pending")

    def for_wallet(self, wallet):
        return self.filter(wallet=wallet).select_related(
            "wallet", "wallet__user", "created_by", "approved_by"
        )

    def earnings(self):
        return self.filter(type__in=["earning", "reward", "referral", "bonus", "cpa", "cpi"])

    def withdrawals(self):
        return self.filter(type="withdrawal")

    def today(self):
        return self.filter(created_at__date=timezone.now().date())

    def date_range(self, start, end):
        return self.filter(created_at__date__gte=start, created_at__date__lte=end)

    def reversed_only(self):
        return self.filter(is_reversed=True)

    def by_reference(self, ref_id: str):
        return self.filter(reference_id=ref_id)


class WithdrawalRequestManager(models.Manager):
    """Custom manager for WithdrawalRequest model."""

    def pending(self):
        return self.filter(status="pending").select_related("user", "wallet", "payment_method")

    def approved(self):
        return self.filter(status="approved")

    def completed(self):
        return self.filter(status="completed")

    def failed(self):
        return self.filter(status__in=["rejected", "failed", "cancelled"])

    def today(self):
        return self.filter(created_at__date=timezone.now().date())

    def for_gateway(self, gateway: str):
        return self.filter(payment_method__method_type=gateway)

    def stale_pending(self, hours: int = 24):
        cutoff = timezone.now() - __import__("datetime").timedelta(hours=hours)
        return self.filter(status="pending", created_at__lt=cutoff)

    def by_user(self, user):
        return self.filter(user=user).order_by("-created_at")


class EarningRecordManager(models.Manager):
    """Custom manager for EarningRecord model."""

    def today(self):
        return self.filter(earned_at__date=timezone.now().date())

    def by_source(self, source_type: str):
        return self.filter(source_type=source_type)

    def date_range(self, start, end):
        return self.filter(earned_at__date__gte=start, earned_at__date__lte=end)

    def for_wallet(self, wallet):
        return self.filter(wallet=wallet).order_by("-earned_at")

    def total_for_wallet(self, wallet) -> Decimal:
        result = self.filter(wallet=wallet).aggregate(t=models.Sum("amount"))["t"]
        return result or Decimal("0")

    def top_earners(self, days: int = 30, limit: int = 20):
        from django.db.models import Sum, Count
        cutoff = timezone.now() - __import__("datetime").timedelta(days=days)
        return self.filter(earned_at__gte=cutoff).values(
            "wallet__user__username"
        ).annotate(total=Sum("amount"), count=Count("id")).order_by("-total")[:limit]


class AuditLogManager(models.Manager):
    """Custom manager for AuditLog model (immutable)."""

    def for_wallet(self, wallet_id: int):
        return self.filter(target_type="wallet", target_id=wallet_id)

    def for_user(self, user_id: int):
        return self.filter(performed_by_id=user_id)

    def by_action(self, action: str):
        return self.filter(action=action)

    def recent(self, days: int = 7):
        cutoff = timezone.now() - __import__("datetime").timedelta(days=days)
        return self.filter(created_at__gte=cutoff)
