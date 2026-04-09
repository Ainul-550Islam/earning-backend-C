# api/djoyalty/managers.py
"""
Custom Django Model Managers for Djoyalty।
Query logic models থেকে আলাদা রাখা হয়েছে।
"""

import logging
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Count, Q, F, ExpressionWrapper, DecimalField
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


# ==================== CUSTOMER MANAGERS ====================

class ActiveCustomerManager(models.Manager):
    """শুধু active customers।"""
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class NewsletterCustomerManager(models.Manager):
    """Newsletter subscribers।"""
    def get_queryset(self):
        return super().get_queryset().filter(newsletter=True)


class CustomerWithStatsManager(models.Manager):
    """Customer + aggregated stats সহ।"""
    def get_queryset(self):
        return super().get_queryset().annotate(
            _total_spent=Sum('djoyalty_txn_tenant__value'),
            _txn_count=Count('djoyalty_txn_tenant', distinct=True),
        )

    def with_balance(self):
        """Points balance সহ।"""
        return self.get_queryset().annotate(
            _points_balance=Sum('djoyalty_loyaltypoints_tenant__balance'),
        )


# ==================== TXN MANAGERS ====================

class FullPriceTxnManager(models.Manager):
    """Full price (non-discount) transactions।"""
    def get_queryset(self):
        return super().get_queryset().filter(is_discount=False)


class DiscountedTxnManager(models.Manager):
    """Discounted transactions।"""
    def get_queryset(self):
        return super().get_queryset().filter(is_discount=True)


class SpendingTxnManager(models.Manager):
    """Negative value transactions (spending/deductions)।"""
    def get_queryset(self):
        return super().get_queryset().filter(value__lt=0)


class RecentTxnManager(models.Manager):
    """শেষ ৩০ দিনের transactions।"""
    def get_queryset(self):
        cutoff = timezone.now() - timedelta(days=30)
        return super().get_queryset().filter(timestamp__gte=cutoff)


# ==================== POINTS LEDGER MANAGERS ====================

class CreditLedgerManager(models.Manager):
    """Credit entries — পয়েন্ট যোগ।"""
    def get_queryset(self):
        return super().get_queryset().filter(txn_type='credit')


class DebitLedgerManager(models.Manager):
    """Debit entries — পয়েন্ট কমানো।"""
    def get_queryset(self):
        return super().get_queryset().filter(txn_type='debit')


class ActiveLedgerManager(models.Manager):
    """Expired নয় এমন ledger entries।"""
    def get_queryset(self):
        return super().get_queryset().filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )


class ExpiringLedgerManager(models.Manager):
    """Soon-to-expire পয়েন্ট (৩০ দিনের মধ্যে)।"""
    def get_queryset(self):
        from .constants import POINTS_EXPIRY_WARNING_DAYS
        warning_date = timezone.now() + timedelta(days=POINTS_EXPIRY_WARNING_DAYS)
        return super().get_queryset().filter(
            expires_at__isnull=False,
            expires_at__lte=warning_date,
            expires_at__gt=timezone.now(),
            txn_type='credit',
            remaining_points__gt=0,
        )


class ExpiredLedgerManager(models.Manager):
    """Expired হয়ে যাওয়া ledger entries।"""
    def get_queryset(self):
        return super().get_queryset().filter(
            expires_at__isnull=False,
            expires_at__lte=timezone.now(),
        )


# ==================== EARN RULE MANAGERS ====================

class ActiveEarnRuleManager(models.Manager):
    """Currently active earn rules।"""
    def get_queryset(self):
        now = timezone.now()
        return super().get_queryset().filter(
            is_active=True,
        ).filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=now)
        ).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gte=now)
        )


class TierSpecificEarnRuleManager(models.Manager):
    """Tier-specific earn rules।"""
    def for_tier(self, tier_name):
        return self.get_queryset().filter(
            Q(applicable_tiers__isnull=True) | Q(applicable_tiers__contains=tier_name)
        )


# ==================== REDEMPTION MANAGERS ====================

class PendingRedemptionManager(models.Manager):
    """Pending redemption requests।"""
    def get_queryset(self):
        return super().get_queryset().filter(status='pending')


class ApprovedRedemptionManager(models.Manager):
    """Approved redemptions।"""
    def get_queryset(self):
        return super().get_queryset().filter(status='approved')


class CompletedRedemptionManager(models.Manager):
    """Completed redemptions।"""
    def get_queryset(self):
        return super().get_queryset().filter(status='completed')


# ==================== VOUCHER MANAGERS ====================

class ActiveVoucherManager(models.Manager):
    """Active (unused, non-expired) vouchers।"""
    def get_queryset(self):
        return super().get_queryset().filter(
            status='active',
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )


class ExpiredVoucherManager(models.Manager):
    """Expired vouchers।"""
    def get_queryset(self):
        return super().get_queryset().filter(
            Q(status='expired') | Q(expires_at__lte=timezone.now())
        )


class UsedVoucherManager(models.Manager):
    """Used vouchers।"""
    def get_queryset(self):
        return super().get_queryset().filter(status='used')


# ==================== CAMPAIGN MANAGERS ====================

class ActiveCampaignManager(models.Manager):
    """Currently running campaigns।"""
    def get_queryset(self):
        now = timezone.now()
        return super().get_queryset().filter(
            status='active',
            start_date__lte=now,
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        )


class UpcomingCampaignManager(models.Manager):
    """Future campaigns।"""
    def get_queryset(self):
        return super().get_queryset().filter(
            status__in=['draft', 'active'],
            start_date__gt=timezone.now(),
        )


class EndedCampaignManager(models.Manager):
    """Ended campaigns।"""
    def get_queryset(self):
        return super().get_queryset().filter(
            Q(status='ended') | Q(end_date__lt=timezone.now())
        )


# ==================== TIER MANAGERS ====================

class CurrentTierManager(models.Manager):
    """Customer এর current active tier।"""
    def get_queryset(self):
        return super().get_queryset().filter(is_current=True)


# ==================== STREAK MANAGERS ====================

class ActiveStreakManager(models.Manager):
    """Active (not broken) streaks।"""
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class LongStreakManager(models.Manager):
    """৭+ দিনের streaks।"""
    def get_queryset(self):
        return super().get_queryset().filter(
            current_streak__gte=7,
            is_active=True,
        )


# ==================== CHALLENGE MANAGERS ====================

class ActiveChallengeManager(models.Manager):
    """Active challenges।"""
    def get_queryset(self):
        now = timezone.now()
        return super().get_queryset().filter(
            status='active',
            start_date__lte=now,
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        )


class CompletedChallengeParticipantManager(models.Manager):
    """Completed challenge participants।"""
    def get_queryset(self):
        return super().get_queryset().filter(status='completed')


# ==================== EVENT MANAGERS ====================

class CustomerRelatedEvtManager(models.Manager):
    """Customer-linked events (anonymous নয়)।"""
    def get_queryset(self):
        return super().get_queryset().filter(customer__isnull=False)


class AnonymousEvtManager(models.Manager):
    """Anonymous events।"""
    def get_queryset(self):
        return super().get_queryset().filter(customer__isnull=True)


class RecentEvtManager(models.Manager):
    """শেষ ৭ দিনের events।"""
    def get_queryset(self):
        cutoff = timezone.now() - timedelta(days=7)
        return super().get_queryset().filter(timestamp__gte=cutoff)


# ==================== FRAUD MANAGERS ====================

class HighRiskFraudManager(models.Manager):
    """High/critical risk fraud logs।"""
    def get_queryset(self):
        return super().get_queryset().filter(
            risk_level__in=['high', 'critical']
        )


class UnresolvedFraudManager(models.Manager):
    """Unresolved fraud cases।"""
    def get_queryset(self):
        return super().get_queryset().filter(is_resolved=False)


# ==================== NOTIFICATION MANAGERS ====================

class UnreadNotificationManager(models.Manager):
    """Unread notifications।"""
    def get_queryset(self):
        return super().get_queryset().filter(is_read=False)


class PendingNotificationManager(models.Manager):
    """Pending (not yet sent) notifications।"""
    def get_queryset(self):
        return super().get_queryset().filter(is_sent=False)


# ==================== GIFT CARD MANAGERS ====================

class ActiveGiftCardManager(models.Manager):
    """Active gift cards।"""
    def get_queryset(self):
        return super().get_queryset().filter(
            status='active',
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )


# ==================== TRANSFER MANAGERS ====================

class PendingTransferManager(models.Manager):
    """Pending point transfers।"""
    def get_queryset(self):
        return super().get_queryset().filter(status='pending')


class CompletedTransferManager(models.Manager):
    """Completed transfers।"""
    def get_queryset(self):
        return super().get_queryset().filter(status='completed')
