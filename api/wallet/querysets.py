# api/wallet/querysets.py
"""
Custom QuerySets for all wallet models.
Chainable, reusable query methods for domain-specific filtering.

Usage:
    from .querysets import WalletQuerySet
    class Wallet(models.Model):
        objects = WalletQuerySet.as_manager()
"""
from decimal import Decimal
from django.db import models
from django.db.models import Q, Sum, Count, Avg, F, ExpressionWrapper, DecimalField
from django.utils import timezone
from datetime import timedelta


class WalletQuerySet(models.QuerySet):
    """QuerySet for Wallet model."""

    def active(self):
        """Wallets that are not locked."""
        return self.filter(is_locked=False)

    def locked(self):
        """Locked wallets."""
        return self.filter(is_locked=True)

    def with_balance(self, min_balance: Decimal = Decimal("0.01")):
        """Wallets with balance above threshold."""
        return self.filter(current_balance__gte=min_balance)

    def with_pending(self):
        """Wallets with pending withdrawal balance."""
        return self.filter(pending_balance__gt=0)

    def with_frozen(self):
        """Wallets with frozen balance."""
        return self.filter(frozen_balance__gt=0)

    def high_value(self, threshold: Decimal = Decimal("10000")):
        """High-value wallets above threshold."""
        return self.filter(current_balance__gte=threshold)

    def inactive_since(self, days: int = 90):
        """Wallets inactive for N days."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(
            Q(last_activity_at__lt=cutoff) | Q(last_activity_at__isnull=True)
        )

    def for_currency(self, currency: str):
        return self.filter(currency__iexact=currency)

    def with_auto_withdraw(self):
        """Wallets with auto-withdraw enabled."""
        return self.filter(auto_withdraw=True, auto_withdraw_threshold__isnull=False)

    def eligible_for_auto_withdraw(self):
        """Wallets ready for auto-withdrawal."""
        return self.filter(
            auto_withdraw=True,
            is_locked=False,
        ).filter(
            current_balance__gte=F("auto_withdraw_threshold")
        )

    def with_bonus_expiring_soon(self, hours: int = 48):
        """Wallets with bonus expiring within N hours."""
        deadline = timezone.now() + timedelta(hours=hours)
        return self.filter(
            bonus_balance__gt=0,
            bonus_expires_at__lte=deadline,
            bonus_expires_at__gt=timezone.now(),
        )

    def by_user_tier(self, tier: str):
        """Filter by user tier."""
        return self.filter(user__tier=tier)

    def top_earners(self, limit: int = 100):
        """Top earning wallets by total_earned."""
        return self.order_by("-total_earned")[:limit]

    def annotate_available(self):
        """Annotate with computed available_balance."""
        return self.annotate(
            computed_available=ExpressionWrapper(
                F("current_balance") - F("frozen_balance") - F("reserved_balance"),
                output_field=DecimalField(max_digits=20, decimal_places=8)
            )
        )

    def select_with_user(self):
        """Prefetch user data."""
        return self.select_related("user", "locked_by")

    def liability_total(self) -> dict:
        """Aggregate total liability across all wallets."""
        return self.aggregate(
            current=Sum("current_balance"),
            pending=Sum("pending_balance"),
            frozen=Sum("frozen_balance"),
            bonus=Sum("bonus_balance"),
            reserved=Sum("reserved_balance"),
            total_count=Count("id"),
        )


class WalletTransactionQuerySet(models.QuerySet):
    """QuerySet for WalletTransaction model."""

    def approved(self):
        return self.filter(status="approved")

    def pending(self):
        return self.filter(status="pending")

    def completed(self):
        return self.filter(status__in=["approved", "completed"])

    def rejected(self):
        return self.filter(status="rejected")

    def reversed_only(self):
        return self.filter(is_reversed=True)

    def not_reversed(self):
        return self.filter(is_reversed=False)

    def earnings(self):
        return self.filter(
            type__in=["earning", "reward", "referral", "bonus", "cpa", "cpi", "cpc", "survey"]
        )

    def withdrawals(self):
        return self.filter(type="withdrawal")

    def credits(self):
        """Positive amount transactions."""
        return self.filter(amount__gt=0)

    def debits(self):
        """Negative amount transactions."""
        return self.filter(amount__lt=0)

    def today(self):
        return self.filter(created_at__date=timezone.now().date())

    def this_week(self):
        start = timezone.now() - timedelta(days=7)
        return self.filter(created_at__gte=start)

    def this_month(self):
        now   = timezone.now()
        start = now.replace(day=1, hour=0, minute=0, second=0)
        return self.filter(created_at__gte=start)

    def date_range(self, start, end):
        return self.filter(created_at__date__gte=start, created_at__date__lte=end)

    def for_wallet(self, wallet):
        return self.filter(wallet=wallet)

    def for_user(self, user):
        return self.filter(wallet__user=user)

    def by_reference(self, ref_id: str):
        return self.filter(reference_id=ref_id)

    def by_type(self, txn_type: str):
        return self.filter(type=txn_type)

    def with_relations(self):
        return self.select_related(
            "wallet", "wallet__user", "created_by", "approved_by"
        )

    def total_amount(self) -> Decimal:
        result = self.aggregate(t=Sum("amount"))["t"]
        return result or Decimal("0")

    def by_country(self, country_code: str):
        return self.filter(metadata__country_code=country_code)

    def large_amounts(self, threshold: Decimal = Decimal("10000")):
        return self.filter(amount__gte=threshold)

    def suspicious(self):
        """Transactions flagged as suspicious."""
        return self.filter(metadata__fraud_flagged=True)


class WithdrawalRequestQuerySet(models.QuerySet):
    """QuerySet for WithdrawalRequest model."""

    def pending(self):
        return self.filter(status="pending")

    def approved(self):
        return self.filter(status="approved")

    def completed(self):
        return self.filter(status="completed")

    def rejected(self):
        return self.filter(status="rejected")

    def failed(self):
        return self.filter(status__in=["rejected", "failed", "cancelled"])

    def in_progress(self):
        return self.filter(status__in=["pending", "approved", "processing"])

    def today(self):
        return self.filter(created_at__date=timezone.now().date())

    def date_range(self, start, end):
        return self.filter(created_at__date__gte=start, created_at__date__lte=end)

    def for_gateway(self, gateway: str):
        return self.filter(payment_method__method_type=gateway)

    def for_user(self, user):
        return self.filter(user=user).order_by("-created_at")

    def stale_pending(self, hours: int = 24):
        """Pending withdrawals older than N hours."""
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(status="pending", created_at__lt=cutoff)

    def high_value(self, threshold: Decimal = Decimal("10000")):
        return self.filter(amount__gte=threshold)

    def with_relations(self):
        return self.select_related(
            "user", "wallet", "payment_method", "transaction", "processed_by"
        )

    def total_volume(self) -> Decimal:
        return self.aggregate(t=Sum("amount"))["t"] or Decimal("0")

    def fee_income(self) -> Decimal:
        return self.filter(status="completed").aggregate(t=Sum("fee"))["t"] or Decimal("0")

    def by_priority(self):
        return self.order_by("-priority", "created_at")


class EarningRecordQuerySet(models.QuerySet):
    """QuerySet for EarningRecord model."""

    def today(self):
        return self.filter(earned_at__date=timezone.now().date())

    def this_week(self):
        return self.filter(earned_at__gte=timezone.now() - timedelta(days=7))

    def by_source(self, source_type: str):
        return self.filter(source_type=source_type)

    def by_country(self, country_code: str):
        return self.filter(country_code=country_code.upper())

    def for_wallet(self, wallet):
        return self.filter(wallet=wallet).order_by("-earned_at")

    def date_range(self, start, end):
        return self.filter(earned_at__date__gte=start, earned_at__date__lte=end)

    def total(self) -> Decimal:
        return self.aggregate(t=Sum("amount"))["t"] or Decimal("0")

    def by_offer_type(self, offer_type: str):
        return self.filter(source_type=offer_type)

    def top_earners(self, days: int = 30, limit: int = 20):
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(earned_at__gte=cutoff).values(
            "wallet__user__username"
        ).annotate(total=Sum("amount"), count=Count("id")).order_by("-total")[:limit]


class LedgerEntryQuerySet(models.QuerySet):
    """QuerySet for LedgerEntry model (immutable)."""

    def debits(self):
        return self.filter(entry_type="debit")

    def credits(self):
        return self.filter(entry_type="credit")

    def for_account(self, account: str):
        return self.filter(account=account)

    def for_wallet(self, wallet):
        return self.filter(ledger__wallet=wallet)

    def date_range(self, start, end):
        return self.filter(created_at__date__gte=start, created_at__date__lte=end)

    def total_debits(self) -> Decimal:
        return self.filter(entry_type="debit").aggregate(t=Sum("amount"))["t"] or Decimal("0")

    def total_credits(self) -> Decimal:
        return self.filter(entry_type="credit").aggregate(t=Sum("amount"))["t"] or Decimal("0")

    def is_balanced(self) -> bool:
        return self.total_debits() == self.total_credits()


class BalanceBonusQuerySet(models.QuerySet):
    """QuerySet for BalanceBonus model."""

    def active(self):
        return self.filter(status="active")

    def pending(self):
        return self.filter(status="pending")

    def expired(self):
        return self.filter(status="expired")

    def expiring_soon(self, hours: int = 48):
        deadline = timezone.now() + timedelta(hours=hours)
        return self.filter(
            status="active",
            expires_at__lte=deadline,
            expires_at__gt=timezone.now(),
        )

    def for_wallet(self, wallet):
        return self.filter(wallet=wallet)

    def by_source(self, source: str):
        return self.filter(source=source)

    def total_active(self) -> Decimal:
        return self.filter(status="active").aggregate(t=Sum("amount"))["t"] or Decimal("0")


class AuditLogQuerySet(models.QuerySet):
    """QuerySet for AuditLog model (immutable)."""

    def for_wallet(self, wallet_id: int):
        return self.filter(target_type="wallet", target_id=wallet_id)

    def for_user(self, user_id: int):
        return self.filter(performed_by_id=user_id)

    def by_action(self, action: str):
        return self.filter(action=action)

    def recent(self, days: int = 7):
        return self.filter(created_at__gte=timezone.now() - timedelta(days=days))

    def admin_credits(self):
        return self.filter(action="admin_credit")

    def fraud_events(self):
        return self.filter(action__in=["fraud_detected", "aml_flagged"])

    def security_events(self):
        return self.filter(action__in=["wallet_locked", "security_lock", "withdrawal_blocked"])
