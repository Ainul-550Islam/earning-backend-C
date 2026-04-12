"""
PAYMENT_SETTLEMENT/escrow_manager.py — Production Escrow Lifecycle Manager
============================================================================
Business Rules:
  1. Money enters Escrow when payment is CONFIRMED
  2. Escrow LOCKED until OrderTracking = 'delivered'
  3. After delivery → 7-day return window starts
  4. No dispute in 7 days → auto-release to SellerPayout
  5. Dispute raised → EscrowStatus = DISPUTED (frozen)
  6. Admin resolves → RELEASED or REFUNDED

State machine:
  HOLDING → on_delivery_confirmed() sets release_after
  HOLDING → RELEASED  (7-day window passes, no dispute)
  HOLDING → DISPUTED  (buyer raises dispute)
  DISPUTED → RELEASED (admin rules seller wins)
  DISPUTED → REFUNDED (admin rules buyer wins)
"""
from __future__ import annotations
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from api.marketplace.models import EscrowHolding, OrderItem, SellerPayout, SellerProfile
from api.marketplace.enums import EscrowStatus, PayoutStatus
from api.marketplace.constants import ESCROW_RELEASE_DAYS
from api.marketplace.exceptions import MarketplaceException

logger = logging.getLogger(__name__)


class EscrowNotReleasableError(MarketplaceException):
    default_detail = "Escrow cannot be released yet: conditions not met."
    default_code   = "escrow_not_releasable"

class EscrowAlreadySettledError(MarketplaceException):
    default_detail = "Escrow has already been settled."
    default_code   = "escrow_already_settled"

class EscrowDisputedError(MarketplaceException):
    default_detail = "Escrow is under dispute. Admin must resolve first."
    default_code   = "escrow_disputed"


class EscrowManager:

    # ── 1. Create when payment confirmed ─────────────────────────────────────
    @classmethod
    @transaction.atomic
    def create_for_order_item(
        cls,
        order_item: OrderItem,
        gross_amount: Decimal,
        commission_amount: Decimal,
    ) -> EscrowHolding:
        if hasattr(order_item, "escrow"):
            return order_item.escrow

        net_amount = gross_amount - commission_amount
        if net_amount < Decimal("0"):
            raise ValueError(f"Net amount negative: {net_amount}")

        # release_after is temporary — updated when delivery confirmed
        escrow = EscrowHolding.objects.create(
            tenant=order_item.tenant,
            order_item=order_item,
            seller=order_item.seller,
            gross_amount=gross_amount,
            commission_deducted=commission_amount,
            net_amount=net_amount,
            status=EscrowStatus.HOLDING,
            release_after=timezone.now() + timezone.timedelta(days=365),  # placeholder
        )
        logger.info("[Escrow] Created #%s | Net: %s BDT", escrow.pk, net_amount)
        return escrow

    # ── 2. Delivery confirmed → start 7-day window ───────────────────────────
    @classmethod
    @transaction.atomic
    def on_delivery_confirmed(cls, order_item: OrderItem) -> EscrowHolding:
        try:
            escrow = EscrowHolding.objects.select_for_update().get(order_item=order_item)
        except EscrowHolding.DoesNotExist:
            raise MarketplaceException("Escrow record not found.")

        if escrow.status != EscrowStatus.HOLDING:
            return escrow

        release_at = timezone.now() + timezone.timedelta(days=ESCROW_RELEASE_DAYS)
        escrow.release_after = release_at
        escrow.save(update_fields=["release_after"])

        logger.info(
            "[Escrow] Delivery confirmed for OrderItem#%s. "
            "7-day window ends: %s",
            order_item.pk, release_at.strftime("%Y-%m-%d"),
        )
        return escrow

    # ── 3. Auto-release ───────────────────────────────────────────────────────
    @classmethod
    @transaction.atomic
    def release(cls, escrow: EscrowHolding, released_by=None) -> SellerPayout:
        # Lock row for concurrent safety
        escrow = EscrowHolding.objects.select_for_update().get(pk=escrow.pk)

        if escrow.status == EscrowStatus.DISPUTED:
            raise EscrowDisputedError()
        if escrow.status != EscrowStatus.HOLDING:
            raise EscrowAlreadySettledError(
                detail=f"Escrow #{escrow.pk} is already '{escrow.status}'."
            )

        now = timezone.now()
        if escrow.release_after > now:
            days_left = (escrow.release_after - now).days
            raise EscrowNotReleasableError(
                detail=f"Return window active. {days_left} day(s) remaining."
            )

        # Block if open dispute exists
        cls._assert_no_open_dispute(escrow)

        escrow.status      = EscrowStatus.RELEASED
        escrow.released_at = now
        escrow.save(update_fields=["status", "released_at"])

        payout = cls._create_payout(escrow, released_by)
        SellerProfile.objects.filter(pk=escrow.seller_id).update(
            total_revenue=escrow.seller.total_revenue + escrow.net_amount
        )

        logger.info("[Escrow] Released #%s → Payout #%s (%s BDT)",
                    escrow.pk, payout.pk, escrow.net_amount)
        return payout

    # ── 4. Freeze for dispute ─────────────────────────────────────────────────
    @classmethod
    @transaction.atomic
    def freeze_for_dispute(cls, escrow: EscrowHolding) -> EscrowHolding:
        escrow = EscrowHolding.objects.select_for_update().get(pk=escrow.pk)
        if escrow.status not in (EscrowStatus.HOLDING,):
            raise EscrowAlreadySettledError(
                detail=f"Cannot freeze: escrow is '{escrow.status}'."
            )
        escrow.status = EscrowStatus.DISPUTED
        escrow.save(update_fields=["status"])
        logger.info("[Escrow] Frozen #%s for dispute", escrow.pk)
        return escrow

    # ── 5. Admin resolution ───────────────────────────────────────────────────
    @classmethod
    @transaction.atomic
    def admin_resolve(cls, escrow: EscrowHolding, decision: str, admin_user, note: str = "") -> EscrowHolding:
        if escrow.status != EscrowStatus.DISPUTED:
            raise MarketplaceException(f"Escrow #{escrow.pk} is not DISPUTED (is '{escrow.status}').")

        now = timezone.now()
        if decision == "release":
            escrow.status      = EscrowStatus.RELEASED
            escrow.released_at = now
            escrow.save(update_fields=["status", "released_at"])
            cls._create_payout(escrow, admin_user)
            logger.info("[Escrow] Admin RELEASED #%s to seller. Note: %s", escrow.pk, note)

        elif decision == "refund":
            escrow.status = EscrowStatus.REFUNDED
            escrow.save(update_fields=["status"])
            cls._process_buyer_refund(escrow, admin_user, note)
            logger.info("[Escrow] Admin REFUNDED #%s to buyer. Note: %s", escrow.pk, note)

        else:
            raise ValueError(f"Invalid decision: '{decision}'. Must be 'release' or 'refund'.")

        return escrow

    # ── Query helpers ─────────────────────────────────────────────────────────
    @classmethod
    def get_releasable(cls, tenant) -> list:
        """All escrows past 7-day window with no open disputes."""
        now = timezone.now()
        candidates = EscrowHolding.objects.filter(
            tenant=tenant,
            status=EscrowStatus.HOLDING,
            release_after__lte=now,
        ).select_related("order_item__order", "seller")

        result = []
        for escrow in candidates:
            try:
                cls._assert_no_open_dispute(escrow)
                result.append(escrow)
            except EscrowDisputedError:
                pass
        return result

    @classmethod
    def summary_for_seller(cls, seller: SellerProfile) -> dict:
        from django.db.models import Sum
        qs = EscrowHolding.objects.filter(seller=seller)
        return {
            s: str(qs.filter(status=s).aggregate(t=Sum("net_amount"))["t"] or 0)
            for s in [EscrowStatus.HOLDING, EscrowStatus.RELEASED,
                      EscrowStatus.DISPUTED, EscrowStatus.REFUNDED]
        }

    # ── Private ───────────────────────────────────────────────────────────────
    @classmethod
    def _assert_no_open_dispute(cls, escrow: EscrowHolding):
        from api.marketplace.DISPUTE_RESOLUTION.dispute_model import Dispute
        from api.marketplace.enums import DisputeStatus
        open_exists = Dispute.objects.filter(
            order=escrow.order_item.order,
            status__in=[DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW, DisputeStatus.ESCALATED],
        ).exists()
        if open_exists:
            raise EscrowDisputedError(detail="Cannot release: order has an open dispute.")

    @classmethod
    def _create_payout(cls, escrow: EscrowHolding, processed_by=None) -> SellerPayout:
        seller = escrow.seller
        return SellerPayout.objects.create(
            tenant=seller.tenant,
            seller=seller,
            amount=escrow.net_amount,
            method="bkash",
            account_number=seller.phone,
            status=PayoutStatus.PENDING,
            balance_before=seller.total_revenue,
            balance_after=seller.total_revenue + escrow.net_amount,
            note=(
                f"Escrow#{escrow.pk} release | "
                f"OrderItem#{escrow.order_item_id} | "
                f"Gross:{escrow.gross_amount} | "
                f"Commission:{escrow.commission_deducted}"
            ),
            processed_by=processed_by,
        )

    @classmethod
    def _process_buyer_refund(cls, escrow: EscrowHolding, admin_user, note: str):
        from api.marketplace.models import RefundRequest, PaymentTransaction
        from api.marketplace.enums import RefundStatus, PaymentStatus, PaymentMethod
        now = timezone.now()

        for refund in RefundRequest.objects.filter(
            order_item=escrow.order_item,
            status__in=["requested", "under_review", "approved"],
        ):
            refund.status          = RefundStatus.PROCESSED
            refund.amount_approved = escrow.gross_amount
            refund.reviewed_by     = admin_user
            refund.reviewed_at     = now
            refund.processed_at    = now
            refund.save()

        # Audit trail
        PaymentTransaction.objects.create(
            tenant=escrow.tenant,
            order=escrow.order_item.order,
            user=escrow.order_item.order.user,
            method=PaymentMethod.BKASH,
            amount=-escrow.gross_amount,
            currency="BDT",
            status=PaymentStatus.REFUNDED,
            gateway_response={"note": note, "admin": str(admin_user)},
            completed_at=now,
            refunded_at=now,
            refunded_amount=escrow.gross_amount,
        )
        # Fire async gateway refund
        try:
            from api.marketplace.tasks import process_gateway_refund
            process_gateway_refund.delay(
                order_item_id=escrow.order_item_id,
                amount=str(escrow.gross_amount),
            )
        except Exception as e:
            logger.error("[Escrow] Could not queue gateway refund: %s", e)


# ── Module-level helpers ──────────────────────────────────────────────────────
def release_all_due(tenant) -> dict:
    """Celery-facing function: release all eligible escrows."""
    result = {"released": 0, "skipped": 0, "errors": []}
    for escrow in EscrowManager.get_releasable(tenant):
        try:
            EscrowManager.release(escrow)
            result["released"] += 1
        except (EscrowNotReleasableError, EscrowDisputedError, EscrowAlreadySettledError) as e:
            result["skipped"] += 1
            logger.debug("[Escrow] Skipped #%s: %s", escrow.pk, e)
        except Exception as e:
            result["errors"].append({"id": escrow.pk, "error": str(e)})
            logger.error("[Escrow] Error releasing #%s: %s", escrow.pk, e)
    logger.info("[Escrow] Batch result: %s", result)
    return result


def get_seller_escrow_balance(seller: SellerProfile) -> Decimal:
    from django.db.models import Sum
    agg = EscrowHolding.objects.filter(
        seller=seller, status=EscrowStatus.HOLDING
    ).aggregate(t=Sum("net_amount"))
    return agg["t"] or Decimal("0.00")
