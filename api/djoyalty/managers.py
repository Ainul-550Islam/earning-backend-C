# api/djoyalty/managers.py
"""
Djoyalty -- custom Django model managers।

FIXED: querysets.py was an orphan (0 imports anywhere)।
Custom QuerySet methods are now exposed via manager classes here
so they work on model instances: Customer.objects.at_risk_of_churn()

Pattern: LoyaltyManager.from_queryset(LoyaltyQuerySet) -- standard Django
pattern that combines Manager and QuerySet into one class।
"""
from django.db import models
from django.utils import timezone

# ─── Import custom QuerySets from querysets.py ────────────────────────────────
# FIXED: querysets.py had CustomerQuerySet, PointsLedgerQuerySet etc.
# but they were never imported, so .active(), .at_risk_of_churn() etc.
# were unavailable on model managers. Importing here wires them in।
try:
    from .querysets import (
        CustomerQuerySet, PointsLedgerQuerySet,
        RedemptionQuerySet, EarnRuleQuerySet,
        CampaignQuerySet, FraudQuerySet,
    )
    _querysets_loaded = True
except ImportError:
    _querysets_loaded = False
    CustomerQuerySet      = None
    PointsLedgerQuerySet  = None
    RedemptionQuerySet    = None
    EarnRuleQuerySet      = None
    CampaignQuerySet      = None
    FraudQuerySet         = None


# ─── Customer Manager ─────────────────────────────────────────────────────────
if _querysets_loaded and CustomerQuerySet is not None:
    class CustomerManager(models.Manager.from_queryset(CustomerQuerySet)):
        """
        Full customer manager with custom queryset methods।
        Usage: Customer.objects.active().at_risk_of_churn()
        """
        def get_queryset(self):
            return super().get_queryset()
else:
    class CustomerManager(models.Manager):
        def get_queryset(self):
            return super().get_queryset().filter(is_active=True)


# ─── Points Ledger Manager ────────────────────────────────────────────────────
if _querysets_loaded and PointsLedgerQuerySet is not None:
    class PointsLedgerManager(models.Manager.from_queryset(PointsLedgerQuerySet)):
        """
        PointsLedger manager with credits(), debits(), for_source() etc।
        """
        pass
else:
    class PointsLedgerManager(models.Manager):
        pass


# ─── Redemption Manager ───────────────────────────────────────────────────────
if _querysets_loaded and RedemptionQuerySet is not None:
    class RedemptionManager(models.Manager.from_queryset(RedemptionQuerySet)):
        """RedemptionRequest manager with pending(), approved() etc।"""
        pass
else:
    class RedemptionManager(models.Manager):
        pass


# ─── Earn Rule Manager ────────────────────────────────────────────────────────
if _querysets_loaded and EarnRuleQuerySet is not None:
    class EarnRuleManager(models.Manager.from_queryset(EarnRuleQuerySet)):
        """EarnRule manager with active(), by_trigger() etc।"""
        pass
else:
    class EarnRuleManager(models.Manager):
        pass


# ─── Campaign Manager ─────────────────────────────────────────────────────────
if _querysets_loaded and CampaignQuerySet is not None:
    class CampaignManager(models.Manager.from_queryset(CampaignQuerySet)):
        """LoyaltyCampaign manager with live(), upcoming() etc।"""
        pass
else:
    class CampaignManager(models.Manager):
        pass


# ─── Fraud Manager ────────────────────────────────────────────────────────────
if _querysets_loaded and FraudQuerySet is not None:
    class FraudManager(models.Manager.from_queryset(FraudQuerySet)):
        """PointsAbuseLog manager with critical(), recent() etc।"""
        pass
else:
    class FraudManager(models.Manager):
        pass


# ─── Simple managers (no custom queryset needed) ─────────────────────────────

class ActiveManager(models.Manager):
    """Only active records।"""
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class InactiveManager(models.Manager):
    """Only inactive records।"""
    def get_queryset(self):
        return super().get_queryset().filter(is_active=False)


class CustomerRelatedManager(models.Manager):
    """Events/records linked to a customer।"""
    def get_queryset(self):
        return super().get_queryset().filter(customer__isnull=False)


class AnonymousManager(models.Manager):
    """Anonymous records (no customer)।"""
    def get_queryset(self):
        return super().get_queryset().filter(customer__isnull=True)


class FullPriceTxnManager(models.Manager):
    """Non-discount transactions।"""
    def get_queryset(self):
        return super().get_queryset().filter(is_discount=False)


class DiscountTxnManager(models.Manager):
    """Discount transactions।"""
    def get_queryset(self):
        return super().get_queryset().filter(is_discount=True)


class PendingManager(models.Manager):
    """Pending status records।"""
    def get_queryset(self):
        return super().get_queryset().filter(status='pending')


class ActiveCampaignManager(models.Manager):
    """Active campaigns within date range।"""
    def get_queryset(self):
        now = timezone.now()
        return super().get_queryset().filter(
            status='active',
        ).filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=now)
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
        )


class ActiveEarnRuleManager(models.Manager):
    """Active earn rules within validity period।"""
    def get_queryset(self):
        now = timezone.now()
        return super().get_queryset().filter(
            is_active=True,
        ).filter(
            models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=now)
        ).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=now)
        )


class UnprocessedExpiryManager(models.Manager):
    """Unprocessed expiry records that are due।"""
    def get_queryset(self):
        return super().get_queryset().filter(
            is_processed=False,
            expires_at__lte=timezone.now(),
        )


class CurrentTierManager(models.Manager):
    """Only current UserTier records।"""
    def get_queryset(self):
        return super().get_queryset().filter(is_current=True)
