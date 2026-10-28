# api/wallet/revenue_sharing.py
"""
Revenue Sharing & Advertiser Billing System.

Features:
  - Advertiser deposits funds into a campaign budget
  - Per-conversion billing (CPA/CPI/CPC/CPL)
  - Publisher revenue share (platform takes X%, publisher gets Y%)
  - Real-time campaign budget tracking with auto-pause
  - Invoice generation (monthly/per-campaign)
  - Multi-tier revenue split (platform / publisher / referrer)
  - Fraud-adjusted payouts (chargeback deductions)
  - Admin dashboard: revenue reports, top publishers, top advertisers

Revenue Flow:
  Advertiser deposits $1000 → Campaign budget $1000
  User completes offer (CPA $2) →
      Platform takes 30% = $0.60
      Publisher earns 70% = $1.40
      If 3-level referral active:
          Level-1 referrer: 10% of publisher earn = $0.14
          Level-2 referrer:  5% of publisher earn = $0.07
          Level-3 referrer:  2% of publisher earn = $0.028
"""
import logging
import uuid
from decimal import Decimal, ROUND_DOWN

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

logger = logging.getLogger("wallet.revenue_sharing")

# ── Config ────────────────────────────────────────────────────────
PLATFORM_REVENUE_SHARE   = Decimal(getattr(settings, "PLATFORM_REVENUE_SHARE_PCT", "0.30"))   # 30%
PUBLISHER_REVENUE_SHARE  = Decimal("1") - PLATFORM_REVENUE_SHARE                              # 70%
REFERRAL_L1_PCT          = Decimal(getattr(settings, "REFERRAL_L1_PCT", "0.10"))
REFERRAL_L2_PCT          = Decimal(getattr(settings, "REFERRAL_L2_PCT", "0.05"))
REFERRAL_L3_PCT          = Decimal(getattr(settings, "REFERRAL_L3_PCT", "0.02"))


# ──────────────────────────────────────────────────────────────────
# MODELS
# ──────────────────────────────────────────────────────────────────

class AdvertiserAccount(models.Model):
    """Advertiser with campaign budget."""

    STATUS_ACTIVE   = "active"
    STATUS_PAUSED   = "paused"
    STATUS_SUSPENDED = "suspended"
    STATUS_CHOICES  = [
        (STATUS_ACTIVE,    "Active"),
        (STATUS_PAUSED,    "Paused"),
        (STATUS_SUSPENDED, "Suspended"),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user            = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="advertiser_account",
    )
    company_name    = models.CharField(max_length=200)
    balance         = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    total_deposited = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    total_spent     = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    status          = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    low_balance_alert = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("10"))
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Advertiser Account"

    def __str__(self):
        return f"{self.company_name} (balance={self.balance})"

    @property
    def is_funded(self) -> bool:
        return self.balance > Decimal("0") and self.status == self.STATUS_ACTIVE


class CampaignBudget(models.Model):
    """Per-campaign budget allocation."""

    STATUS_ACTIVE  = "active"
    STATUS_PAUSED  = "paused"
    STATUS_DEPLETED = "depleted"
    STATUS_CHOICES = [
        (STATUS_ACTIVE,   "Active"),
        (STATUS_PAUSED,   "Paused"),
        (STATUS_DEPLETED, "Budget Depleted"),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    advertiser      = models.ForeignKey(AdvertiserAccount, on_delete=models.CASCADE, related_name="campaigns")
    name            = models.CharField(max_length=200)
    offer_type      = models.CharField(max_length=10, default="cpa", help_text="cpa/cpi/cpc/cpl")
    payout_amount   = models.DecimalField(max_digits=14, decimal_places=8, help_text="Per-conversion payout (USD)")
    daily_budget    = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    total_budget    = models.DecimalField(max_digits=14, decimal_places=4)
    spent_today     = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    spent_total     = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    conversions     = models.PositiveIntegerField(default=0)
    status          = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Campaign Budget"
        indexes = [models.Index(fields=["status", "advertiser"])]

    @property
    def remaining_budget(self) -> Decimal:
        return self.total_budget - self.spent_total

    @property
    def can_convert(self) -> bool:
        if self.status != self.STATUS_ACTIVE:
            return False
        if self.remaining_budget < self.payout_amount:
            return False
        if self.daily_budget and self.spent_today >= self.daily_budget:
            return False
        return self.advertiser.is_funded


class RevenueTransaction(models.Model):
    """Every revenue split event (platform earn, publisher earn, referral earn)."""

    TYPE_PLATFORM_FEE   = "platform_fee"
    TYPE_PUBLISHER_EARN = "publisher_earn"
    TYPE_REFERRAL_L1    = "referral_l1"
    TYPE_REFERRAL_L2    = "referral_l2"
    TYPE_REFERRAL_L3    = "referral_l3"
    TYPE_ADVERTISER_CHARGE = "advertiser_charge"
    TYPE_CHOICES = [
        (TYPE_PLATFORM_FEE,      "Platform Fee"),
        (TYPE_PUBLISHER_EARN,    "Publisher Earning"),
        (TYPE_REFERRAL_L1,       "Referral L1"),
        (TYPE_REFERRAL_L2,       "Referral L2"),
        (TYPE_REFERRAL_L3,       "Referral L3"),
        (TYPE_ADVERTISER_CHARGE, "Advertiser Charge"),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign        = models.ForeignKey(CampaignBudget, on_delete=models.SET_NULL, null=True)
    advertiser      = models.ForeignKey(AdvertiserAccount, on_delete=models.SET_NULL, null=True)
    publisher       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="revenue_transactions",
    )
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    gross_amount    = models.DecimalField(max_digits=20, decimal_places=8, help_text="Advertiser charge")
    platform_fee    = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    publisher_net   = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    currency        = models.CharField(max_length=5, default="USD")
    wallet_txn_id   = models.UUIDField(null=True, blank=True)
    offer_type      = models.CharField(max_length=10, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Revenue Transaction"
        indexes = [models.Index(fields=["publisher", "created_at"])]


class AdvertiserInvoice(models.Model):
    """Monthly invoice for advertisers."""

    STATUS_DRAFT = "draft"
    STATUS_SENT  = "sent"
    STATUS_PAID  = "paid"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SENT,  "Sent"),
        (STATUS_PAID,  "Paid"),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    advertiser      = models.ForeignKey(AdvertiserAccount, on_delete=models.CASCADE, related_name="invoices")
    invoice_number  = models.CharField(max_length=30, unique=True)
    period_start    = models.DateField()
    period_end      = models.DateField()
    total_amount    = models.DecimalField(max_digits=20, decimal_places=8)
    conversions     = models.PositiveIntegerField(default=0)
    status          = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    generated_at    = models.DateTimeField(auto_now_add=True)
    paid_at         = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-period_start"]
        verbose_name = "Advertiser Invoice"

    def __str__(self):
        return f"INV-{self.invoice_number} ({self.advertiser.company_name})"


# ──────────────────────────────────────────────────────────────────
# SERVICES
# ──────────────────────────────────────────────────────────────────

class RevenueSharingService:
    """
    Core revenue sharing engine.

    Called by EarningService after a successful conversion.
    """

    @classmethod
    def process_conversion(
        cls,
        campaign: CampaignBudget,
        publisher_user,
        offer_type: str = "cpa",
    ) -> dict:
        """
        Process a single conversion:
          1. Charge advertiser
          2. Credit publisher (net of platform fee)
          3. Credit referrers (L1/L2/L3)
          4. Record RevenueTransaction
          5. Auto-pause campaign if budget depleted

        Returns:
            {success, publisher_net, platform_fee, referral_credits, campaign_status}
        """
        if not campaign.can_convert:
            return {"success": False, "reason": "campaign_inactive_or_no_budget"}

        gross      = campaign.payout_amount
        platform_f = (gross * PLATFORM_REVENUE_SHARE).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        pub_net    = gross - platform_f

        with transaction.atomic():
            # 1. Charge advertiser balance
            AdvertiserAccount.objects.filter(pk=campaign.advertiser_id).update(
                balance=models.F("balance") - gross,
                total_spent=models.F("total_spent") + gross,
            )

            # 2. Update campaign spend
            CampaignBudget.objects.filter(pk=campaign.pk).update(
                spent_total=models.F("spent_total") + gross,
                spent_today=models.F("spent_today") + gross,
                conversions=models.F("conversions") + 1,
            )

            # 3. Credit publisher wallet
            pub_txn_id = cls._credit_wallet(publisher_user, pub_net, "publisher_earn",
                                             f"Campaign: {campaign.name}")

            # 4. Referral chain
            referral_credits = cls._process_referrals(publisher_user, pub_net, campaign.name)

            # 5. Log revenue transaction
            RevenueTransaction.objects.create(
                campaign=campaign,
                advertiser=campaign.advertiser,
                publisher=publisher_user,
                transaction_type=RevenueTransaction.TYPE_PUBLISHER_EARN,
                gross_amount=gross,
                platform_fee=platform_f,
                publisher_net=pub_net,
                offer_type=offer_type,
                wallet_txn_id=pub_txn_id,
            )

            # 6. Auto-pause if budget depleted
            campaign.refresh_from_db()
            if campaign.remaining_budget < campaign.payout_amount:
                CampaignBudget.objects.filter(pk=campaign.pk).update(
                    status=CampaignBudget.STATUS_DEPLETED,
                )
                logger.info(f"Campaign {campaign.id} auto-paused: budget depleted")

        return {
            "success":         True,
            "publisher_net":   str(pub_net),
            "platform_fee":    str(platform_f),
            "gross":           str(gross),
            "referral_credits": referral_credits,
            "campaign_status": campaign.status,
        }

    @classmethod
    def _credit_wallet(cls, user, amount: Decimal, source: str, description: str):
        """Credit user's wallet. Returns transaction UUID or None."""
        try:
            from .services.earning.EarningService import EarningService
            from .models import Wallet
            wallet = Wallet.objects.get(user=user)
            txn = EarningService.add_earning(
                wallet=wallet,
                amount=amount,
                source=source,
                description=description,
            )
            return txn.id if txn else None
        except Exception as e:
            logger.error(f"_credit_wallet failed for user {user.id}: {e}")
            return None

    @classmethod
    def _process_referrals(cls, publisher_user, publisher_net: Decimal, campaign_name: str) -> list:
        """Credit L1/L2/L3 referrers from publisher's earning."""
        credits = []
        try:
            from .models import Wallet
            pcts = [
                (REFERRAL_L1_PCT, "referral_l1", "L1"),
                (REFERRAL_L2_PCT, "referral_l2", "L2"),
                (REFERRAL_L3_PCT, "referral_l3", "L3"),
            ]
            # Walk up referral chain
            current = publisher_user
            for pct, source, level in pcts:
                referred_by = getattr(getattr(current, "wallet", None), "referred_by", None)
                if not referred_by:
                    break
                amount = (publisher_net * pct).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
                if amount > Decimal("0"):
                    txn_id = cls._credit_wallet(
                        referred_by, amount, source,
                        f"Referral {level} commission from {campaign_name}",
                    )
                    credits.append({"level": level, "amount": str(amount), "user_id": referred_by.id})
                current = referred_by
        except Exception as e:
            logger.warning(f"Referral chain processing error: {e}")
        return credits

    @classmethod
    def deposit_advertiser_funds(cls, advertiser: AdvertiserAccount, amount: Decimal,
                                  payment_ref: str = "") -> dict:
        """Top up advertiser balance (after payment gateway confirmation)."""
        with transaction.atomic():
            AdvertiserAccount.objects.filter(pk=advertiser.pk).update(
                balance=models.F("balance") + amount,
                total_deposited=models.F("total_deposited") + amount,
                status=AdvertiserAccount.STATUS_ACTIVE,
            )
        logger.info(f"Advertiser {advertiser.company_name} deposited {amount} ref={payment_ref}")
        return {"success": True, "new_balance": str(advertiser.balance + amount)}

    @classmethod
    def generate_monthly_invoice(cls, advertiser: AdvertiserAccount,
                                  year: int, month: int) -> AdvertiserInvoice:
        """Generate a monthly invoice for an advertiser."""
        import calendar
        from datetime import date
        start = date(year, month, 1)
        end   = date(year, month, calendar.monthrange(year, month)[1])

        txns = RevenueTransaction.objects.filter(
            advertiser=advertiser,
            transaction_type=RevenueTransaction.TYPE_ADVERTISER_CHARGE,
            created_at__date__range=(start, end),
        )
        total       = sum(t.gross_amount for t in txns)
        conversions = txns.count()
        inv_number  = f"{advertiser.id.hex[:8].upper()}-{year}{month:02d}"

        invoice, _ = AdvertiserInvoice.objects.update_or_create(
            invoice_number=inv_number,
            defaults={
                "advertiser":   advertiser,
                "period_start": start,
                "period_end":   end,
                "total_amount": total,
                "conversions":  conversions,
                "status":       AdvertiserInvoice.STATUS_DRAFT,
            },
        )
        return invoice

    @classmethod
    def get_publisher_earnings_summary(cls, publisher_user, days: int = 30) -> dict:
        """Summary stats for a publisher's earnings."""
        since = timezone.now() - timezone.timedelta(days=days)
        txns  = RevenueTransaction.objects.filter(
            publisher=publisher_user,
            created_at__gte=since,
        )
        total_net    = sum(t.publisher_net for t in txns)
        by_type      = {}
        for t in txns:
            by_type[t.offer_type] = by_type.get(t.offer_type, Decimal("0")) + t.publisher_net
        return {
            "period_days":    days,
            "total_net":      str(total_net),
            "conversions":    txns.count(),
            "by_offer_type":  {k: str(v) for k, v in by_type.items()},
        }

    @classmethod
    def reset_daily_campaign_spend(cls):
        """Call via Celery beat at midnight. Resets spent_today for all campaigns."""
        count = CampaignBudget.objects.filter(
            status=CampaignBudget.STATUS_PAUSED,
        ).exclude(
            status=CampaignBudget.STATUS_DEPLETED,
        ).count()
        CampaignBudget.objects.update(spent_today=Decimal("0"))
        # Re-activate paused (daily-budget-exhausted) campaigns
        CampaignBudget.objects.filter(
            status=CampaignBudget.STATUS_PAUSED,
        ).exclude(
            spent_total__gte=models.F("total_budget"),
        ).update(status=CampaignBudget.STATUS_ACTIVE)
        logger.info(f"Daily campaign spend reset. {count} campaigns may re-activate.")
