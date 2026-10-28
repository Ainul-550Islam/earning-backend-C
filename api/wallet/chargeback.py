# api/wallet/chargeback.py
"""
ChargebackService — Handle payment chargebacks and dispute reversals.

A chargeback occurs when a payment gateway reverses a transaction
(user disputes with their bank/card). The wallet must:
  1. Debit the user's wallet for the charged-back amount
  2. Flag the user for review
  3. Optionally block further withdrawals
  4. Log everything for compliance

States: received → under_review → accepted | rejected
"""
import logging
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

logger = logging.getLogger("wallet.chargeback")


class Chargeback(models.Model):
    """
    A single chargeback event received from a payment gateway.
    One chargeback = one reversed transaction.
    """

    STATUS_RECEIVED     = "received"
    STATUS_UNDER_REVIEW = "under_review"
    STATUS_ACCEPTED     = "accepted"   # chargeback upheld, wallet debited
    STATUS_REJECTED     = "rejected"   # chargeback overturned, no debit
    STATUS_CHOICES = [
        (STATUS_RECEIVED,     "Received"),
        (STATUS_UNDER_REVIEW, "Under Review"),
        (STATUS_ACCEPTED,     "Accepted — Wallet Debited"),
        (STATUS_REJECTED,     "Rejected — No Action"),
    ]

    tenant           = models.ForeignKey(
        "tenants.Tenant", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="chargebacks",
    )
    chargeback_id    = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user             = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="chargebacks",
    )
    wallet           = models.ForeignKey(
        "wallet.Wallet", on_delete=models.SET_NULL,
        null=True, related_name="chargebacks",
    )
    original_txn     = models.ForeignKey(
        "wallet.WalletTransaction", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="chargebacks",
    )

    # ── Amount ────────────────────────────────────────────────────
    amount           = models.DecimalField(max_digits=20, decimal_places=8)
    currency         = models.CharField(max_length=10, default="BDT")

    # ── Gateway info ──────────────────────────────────────────────
    gateway          = models.CharField(max_length=40)
    gateway_ref      = models.CharField(max_length=128, blank=True, db_index=True)
    gateway_reason   = models.CharField(max_length=200, blank=True)

    # ── Status ────────────────────────────────────────────────────
    status           = models.CharField(
        max_length=14, choices=STATUS_CHOICES,
        default=STATUS_RECEIVED, db_index=True,
    )
    reviewed_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reviewed_chargebacks",
    )
    review_notes     = models.TextField(blank=True)
    reversal_txn_id  = models.CharField(max_length=64, blank=True)

    received_at      = models.DateTimeField(default=timezone.now)
    resolved_at      = models.DateTimeField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_chargeback"
        ordering  = ["-received_at"]
        indexes   = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["gateway", "gateway_ref"]),
            models.Index(fields=["status", "-received_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"CB-{str(self.chargeback_id)[:8]} | "
            f"{self.gateway} | {self.amount} {self.currency} | {self.status}"
        )


class ChargebackService:
    """Business logic for chargeback lifecycle."""

    @classmethod
    def receive(
        cls,
        gateway: str,
        gateway_ref: str,
        amount: Decimal,
        user,
        wallet,
        currency: str = "BDT",
        gateway_reason: str = "",
        original_txn=None,
    ) -> Chargeback:
        """
        Record a new chargeback received from a gateway webhook.
        Does NOT debit wallet yet — review required first.
        """
        amount = Decimal(str(amount))

        cb = Chargeback.objects.create(
            user=user,
            wallet=wallet,
            original_txn=original_txn,
            amount=amount,
            currency=currency,
            gateway=gateway,
            gateway_ref=gateway_ref,
            gateway_reason=gateway_reason,
            status=Chargeback.STATUS_RECEIVED,
        )
        logger.warning(
            f"Chargeback received: cb={cb.chargeback_id} "
            f"gateway={gateway} ref={gateway_ref} amount={amount} user={user.pk}"
        )

        # Auto-flag user for review
        try:
            from .services_extra import SecurityService
            SecurityService.flag_for_chargeback(user, str(cb.chargeback_id))
        except Exception as e:
            logger.warning(f"Chargeback SecurityService flag failed: {e}")

        return cb

    @classmethod
    def accept(
        cls,
        chargeback_id: str,
        reviewed_by=None,
        notes: str = "",
    ) -> dict:
        """
        Accept the chargeback: debit user's wallet, block withdrawals.
        Called by admin or automated review.
        """
        try:
            cb = Chargeback.objects.select_for_update().get(
                chargeback_id=chargeback_id
            )
        except Chargeback.DoesNotExist:
            raise ValueError(f"Chargeback {chargeback_id} not found")

        if cb.status not in (Chargeback.STATUS_RECEIVED, Chargeback.STATUS_UNDER_REVIEW):
            raise ValueError(f"Chargeback already resolved: {cb.status}")

        with transaction.atomic():
            reversal_txn_id = ""

            if cb.wallet and cb.amount > Decimal("0"):
                try:
                    from .services.core.WalletService import WalletService
                    from .choices import TransactionType
                    txn = WalletService.debit(
                        wallet=cb.wallet,
                        amount=cb.amount,
                        txn_type=TransactionType.CHARGEBACK,
                        description=(
                            f"Chargeback accepted: {cb.gateway} ref={cb.gateway_ref}"
                        ),
                        reference_id=str(cb.chargeback_id),
                        reference_type="chargeback",
                    )
                    reversal_txn_id = str(txn.txn_id)
                except Exception as e:
                    logger.error(f"Chargeback debit failed cb={chargeback_id}: {e}")

            cb.status          = Chargeback.STATUS_ACCEPTED
            cb.reviewed_by     = reviewed_by
            cb.review_notes    = notes
            cb.reversal_txn_id = reversal_txn_id
            cb.resolved_at     = timezone.now()
            cb.save(update_fields=[
                "status", "reviewed_by", "review_notes",
                "reversal_txn_id", "resolved_at", "updated_at",
            ])

            # Block withdrawal
            if cb.wallet:
                try:
                    from .models.withdrawal import WithdrawalBlock
                    from .choices import WithdrawalBlockReason
                    WithdrawalBlock.objects.get_or_create(
                        wallet=cb.wallet,
                        defaults={
                            "reason": WithdrawalBlockReason.CHARGEBACK,
                            "note":   f"Chargeback accepted: {chargeback_id}",
                        },
                    )
                except Exception as e:
                    logger.warning(f"WithdrawalBlock create failed: {e}")

        logger.warning(
            f"Chargeback accepted: cb={chargeback_id} "
            f"debited={cb.amount} txn={reversal_txn_id}"
        )
        return {
            "chargeback_id":  str(cb.chargeback_id),
            "status":         cb.status,
            "amount_debited": str(cb.amount),
            "reversal_txn_id": reversal_txn_id,
        }

    @classmethod
    def reject(
        cls,
        chargeback_id: str,
        reviewed_by=None,
        notes: str = "",
    ) -> Chargeback:
        """Reject the chargeback — no wallet debit, user cleared."""
        try:
            cb = Chargeback.objects.get(chargeback_id=chargeback_id)
        except Chargeback.DoesNotExist:
            raise ValueError(f"Chargeback {chargeback_id} not found")

        cb.status       = Chargeback.STATUS_REJECTED
        cb.reviewed_by  = reviewed_by
        cb.review_notes = notes
        cb.resolved_at  = timezone.now()
        cb.save(update_fields=[
            "status", "reviewed_by", "review_notes", "resolved_at", "updated_at"
        ])
        logger.info(f"Chargeback rejected: cb={chargeback_id} no action taken")
        return cb
