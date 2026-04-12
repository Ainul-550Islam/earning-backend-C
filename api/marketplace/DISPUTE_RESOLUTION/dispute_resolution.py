"""
DISPUTE_RESOLUTION/dispute_resolution.py — Full Dispute Workflow Engine
=========================================================================
Workflow:
  Step 1: Buyer raises dispute           → raise_dispute()
  Step 2: Seller responds (optional)     → seller_respond()
  Step 3: Admin reviews evidence         → admin_escalate() or admin_close()
  Step 4: Admin delivers verdict         → admin_arbitrate()
            verdict = "buyer_wins"  → RefundRequest created → Escrow → REFUNDED
            verdict = "seller_wins" → Escrow → RELEASED
            verdict = "partial"     → Partial RefundRequest + partial Escrow release

IMPORTANT: RefundRequest is ONLY created after DisputeArbitration is settled.
           No refund without admin verdict.

Guards:
  - Buyer can only dispute within DISPUTE_WINDOW_DAYS after delivery
  - One dispute per order item
  - Seller cannot close a dispute (only admin or buyer)
  - Escrow is frozen as soon as dispute is raised
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from api.marketplace.models import (
    Order, OrderItem, RefundRequest, EscrowHolding,
)
from api.marketplace.enums import (
    DisputeStatus, DisputeType, RefundReason, RefundStatus, EscrowStatus,
)
from api.marketplace.exceptions import MarketplaceException
from .dispute_model import Dispute, DisputeMessage, DisputeEvidence, DisputeArbitration

logger = logging.getLogger(__name__)

DISPUTE_WINDOW_DAYS = 14     # buyer can raise dispute within 14 days of delivery


# ─────────────────────────────────────────────────────────────────────────────
# Custom exceptions
# ─────────────────────────────────────────────────────────────────────────────

class DisputeWindowExpired(MarketplaceException):
    default_detail = "Dispute window has expired (14 days after delivery)."
    default_code   = "dispute_window_expired"

class DisputeAlreadyExists(MarketplaceException):
    default_detail = "A dispute already exists for this order item."
    default_code   = "dispute_exists"

class DisputeNotOpen(MarketplaceException):
    default_detail = "Dispute is not in an open state for this action."
    default_code   = "dispute_not_open"

class RefundBeforeArbitration(MarketplaceException):
    default_detail = "Refund cannot be processed before dispute arbitration is complete."
    default_code   = "refund_before_arbitration"


# ─────────────────────────────────────────────────────────────────────────────
# Main service class
# ─────────────────────────────────────────────────────────────────────────────

class DisputeResolutionService:

    # ── Step 1: Buyer raises dispute ──────────────────────────────────────────
    @classmethod
    @transaction.atomic
    def raise_dispute(
        cls,
        order_item: OrderItem,
        buyer,
        dispute_type: str,
        description: str,
        evidence_files: list = None,   # list of uploaded File objects
    ) -> Dispute:
        """
        Buyer initiates a dispute for a delivered order item.

        Guards:
          - Order must be DELIVERED
          - Within 14-day dispute window
          - No existing open dispute for this item
          - Escrow is frozen immediately
        """
        order = order_item.order

        # Guard: order must be delivered
        from api.marketplace.enums import OrderStatus
        if order.status != OrderStatus.DELIVERED:
            raise MarketplaceException(
                "Dispute can only be raised for delivered orders."
            )

        # Guard: dispute window
        if order.updated_at:
            days_since = (timezone.now() - order.updated_at).days
            if days_since > DISPUTE_WINDOW_DAYS:
                raise DisputeWindowExpired()

        # Guard: no duplicate dispute
        if Dispute.objects.filter(
            order_item=order_item,
            status__in=[
                DisputeStatus.OPEN,
                DisputeStatus.UNDER_REVIEW,
                DisputeStatus.ESCALATED,
            ],
        ).exists():
            raise DisputeAlreadyExists()

        # Create dispute
        dispute = Dispute.objects.create(
            tenant=order.tenant,
            order=order,
            order_item=order_item,
            raised_by=buyer,
            against_seller=order_item.seller,
            dispute_type=dispute_type,
            description=description,
            status=DisputeStatus.OPEN,
        )

        # Add buyer's opening message
        DisputeMessage.objects.create(
            tenant=order.tenant,
            dispute=dispute,
            sender=buyer,
            role="buyer",
            body=description,
        )

        # Attach evidence
        if evidence_files:
            for f in evidence_files:
                DisputeEvidence.objects.create(
                    tenant=order.tenant,
                    dispute=dispute,
                    uploader=buyer,
                    role="buyer",
                    file=f,
                )

        # ← FREEZE escrow immediately
        try:
            escrow = EscrowHolding.objects.get(order_item=order_item)
            from api.marketplace.PAYMENT_SETTLEMENT.escrow_manager import EscrowManager
            EscrowManager.freeze_for_dispute(escrow)
        except EscrowHolding.DoesNotExist:
            logger.warning(
                "[Dispute] No escrow found for OrderItem#%s — escrow may not have been created yet.",
                order_item.pk,
            )

        # Notify seller + admin
        cls._notify_dispute_raised(dispute)

        logger.info(
            "[Dispute] Raised: Dispute#%s | OrderItem#%s | type=%s | buyer=%s",
            dispute.pk, order_item.pk, dispute_type, buyer.username,
        )
        return dispute

    # ── Step 2: Seller responds ───────────────────────────────────────────────
    @classmethod
    @transaction.atomic
    def seller_respond(
        cls,
        dispute: Dispute,
        seller_user,
        message: str,
        evidence_files: list = None,
        offer_refund: bool = False,
        refund_percent: float = 100.0,
    ) -> DisputeMessage:
        """
        Seller submits their response.
        If seller voluntarily offers full/partial refund → dispute moves to CLOSED.
        """
        cls._assert_open_or_review(dispute)

        msg = DisputeMessage.objects.create(
            tenant=dispute.tenant,
            dispute=dispute,
            sender=seller_user,
            role="seller",
            body=message,
        )

        if evidence_files:
            for f in evidence_files:
                DisputeEvidence.objects.create(
                    tenant=dispute.tenant,
                    dispute=dispute,
                    uploader=seller_user,
                    role="seller",
                    file=f,
                )

        # Seller voluntarily agrees to refund → admin still creates arbitration
        if offer_refund:
            dispute.status = DisputeStatus.UNDER_REVIEW
            dispute.save(update_fields=["status"])
            cls._add_admin_note(
                dispute,
                f"Seller offered {refund_percent}% refund voluntarily. Awaiting admin approval.",
            )

        logger.info("[Dispute] Seller responded to Dispute#%s", dispute.pk)
        return msg

    # ── Step 3a: Admin escalates ──────────────────────────────────────────────
    @classmethod
    @transaction.atomic
    def admin_escalate(cls, dispute: Dispute, admin_user, note: str = "") -> Dispute:
        """Move dispute to ESCALATED (requires senior review)."""
        cls._assert_open_or_review(dispute)
        dispute.status = DisputeStatus.ESCALATED
        dispute.save(update_fields=["status"])
        cls._add_admin_note(dispute, note or "Dispute escalated for senior review.")
        logger.info("[Dispute] Escalated Dispute#%s by %s", dispute.pk, admin_user)
        return dispute

    # ── Step 3b: Admin delivers verdict ──────────────────────────────────────
    @classmethod
    @transaction.atomic
    def admin_arbitrate(
        cls,
        dispute: Dispute,
        admin_user,
        verdict: str,              # "buyer_wins" | "seller_wins" | "partial"
        reason: str,
        refund_percent: float = 100.0,
    ) -> DisputeArbitration:
        """
        Admin delivers final verdict.
        ONLY this function creates RefundRequest.
        Escrow is resolved via EscrowManager.

        verdict = "buyer_wins"  → full RefundRequest + escrow REFUNDED
        verdict = "seller_wins" → escrow RELEASED to seller
        verdict = "partial"     → partial RefundRequest + rest to seller
        """
        if dispute.status not in (
            DisputeStatus.OPEN,
            DisputeStatus.UNDER_REVIEW,
            DisputeStatus.ESCALATED,
        ):
            raise DisputeNotOpen(detail=f"Cannot arbitrate: dispute is '{dispute.status}'.")

        # Create arbitration record
        arbitration = DisputeArbitration.objects.create(
            tenant=dispute.tenant,
            dispute=dispute,
            admin=admin_user,
            verdict=verdict,
            refund_percent=Decimal(str(refund_percent)),
            reason=reason,
        )

        from api.marketplace.PAYMENT_SETTLEMENT.escrow_manager import EscrowManager

        if verdict == "buyer_wins":
            dispute.status = DisputeStatus.RESOLVED_BUYER
            refund_req = cls._create_refund_from_arbitration(
                dispute, arbitration, admin_user, percent=Decimal("100")
            )
            dispute.refund_request = refund_req
            # Escrow → REFUNDED
            try:
                escrow = EscrowHolding.objects.get(order_item=dispute.order_item)
                EscrowManager.admin_resolve(escrow, "refund", admin_user, note=reason)
            except EscrowHolding.DoesNotExist:
                logger.warning("[Dispute] No escrow to refund for Dispute#%s", dispute.pk)

        elif verdict == "seller_wins":
            dispute.status = DisputeStatus.RESOLVED_SELLER
            # Escrow → RELEASED
            try:
                escrow = EscrowHolding.objects.get(order_item=dispute.order_item)
                EscrowManager.admin_resolve(escrow, "release", admin_user, note=reason)
            except EscrowHolding.DoesNotExist:
                logger.warning("[Dispute] No escrow to release for Dispute#%s", dispute.pk)

        elif verdict == "partial":
            dispute.status = DisputeStatus.RESOLVED_BUYER
            pct = Decimal(str(refund_percent))
            refund_req = cls._create_refund_from_arbitration(
                dispute, arbitration, admin_user, percent=pct
            )
            dispute.refund_request = refund_req
            # Release remaining % to seller via separate payout
            cls._partial_escrow_resolution(dispute, admin_user, pct, reason)

        else:
            raise ValueError(f"Invalid verdict: '{verdict}'")

        dispute.resolution_note = reason
        dispute.resolved_by     = admin_user
        dispute.resolved_at     = timezone.now()
        dispute.save()

        cls._add_admin_note(dispute, f"Verdict: {verdict}. Reason: {reason}")
        cls._notify_verdict(dispute, arbitration)

        logger.info(
            "[Dispute] Arbitrated Dispute#%s → verdict=%s | admin=%s",
            dispute.pk, verdict, admin_user.username,
        )
        return arbitration

    # ── Step 4: Close (no dispute needed) ────────────────────────────────────
    @classmethod
    @transaction.atomic
    def buyer_close(cls, dispute: Dispute, buyer, reason: str = "") -> Dispute:
        """Buyer withdraws the dispute (problem resolved outside system)."""
        cls._assert_open_or_review(dispute)
        dispute.status      = DisputeStatus.CLOSED
        dispute.resolved_at = timezone.now()
        dispute.resolution_note = reason or "Closed by buyer."
        dispute.save()

        # Unfreeze escrow
        try:
            escrow = EscrowHolding.objects.get(
                order_item=dispute.order_item, status=EscrowStatus.DISPUTED
            )
            escrow.status = EscrowStatus.HOLDING
            escrow.save(update_fields=["status"])
        except EscrowHolding.DoesNotExist:
            pass

        logger.info("[Dispute] Closed by buyer: Dispute#%s", dispute.pk)
        return dispute

    # ── Query helpers ─────────────────────────────────────────────────────────
    @classmethod
    def get_for_order(cls, order: Order):
        return Dispute.objects.filter(order=order).order_by("-created_at")

    @classmethod
    def get_pending_admin_review(cls, tenant):
        return Dispute.objects.filter(
            tenant=tenant,
            status__in=[DisputeStatus.UNDER_REVIEW, DisputeStatus.ESCALATED],
        ).select_related("order", "raised_by", "against_seller").order_by("-created_at")

    @classmethod
    def get_open_for_seller(cls, seller):
        return Dispute.objects.filter(
            against_seller=seller,
            status__in=[DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW],
        ).select_related("order", "raised_by")

    @classmethod
    def dispute_stats(cls, tenant) -> dict:
        from django.db.models import Count
        qs = Dispute.objects.filter(tenant=tenant)
        return qs.values("status").annotate(count=Count("id")).order_by()

    # ── Private helpers ───────────────────────────────────────────────────────
    @classmethod
    def _assert_open_or_review(cls, dispute: Dispute):
        if dispute.status not in (
            DisputeStatus.OPEN,
            DisputeStatus.UNDER_REVIEW,
            DisputeStatus.ESCALATED,
        ):
            raise DisputeNotOpen(
                detail=f"Dispute is '{dispute.status}'; no action allowed."
            )

    @classmethod
    def _add_admin_note(cls, dispute: Dispute, note: str):
        """Internal admin-only system message."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            admin = User.objects.filter(is_superuser=True).first()
        except Exception:
            admin = None
        DisputeMessage.objects.create(
            tenant=dispute.tenant,
            dispute=dispute,
            sender=admin,
            role="admin",
            body=note,
            is_internal=True,
        )

    @classmethod
    def _create_refund_from_arbitration(
        cls,
        dispute: Dispute,
        arbitration: DisputeArbitration,
        admin_user,
        percent: Decimal,
    ) -> RefundRequest:
        """
        Create RefundRequest ONLY after arbitration is decided.
        This is the ONLY code path that creates a RefundRequest from a dispute.
        """
        order_item = dispute.order_item
        gross = order_item.subtotal
        refund_amount = (gross * percent / 100).quantize(Decimal("0.01"))

        refund = RefundRequest.objects.create(
            tenant=dispute.tenant,
            order_item=order_item,
            user=dispute.raised_by,
            reason=RefundReason.OTHER,
            description=(
                f"Dispute #{dispute.pk} resolved by admin. "
                f"Verdict: {arbitration.verdict}. Reason: {arbitration.reason}"
            ),
            amount_requested=refund_amount,
            amount_approved=refund_amount,
            status=RefundStatus.APPROVED,
            reviewed_by=admin_user,
            reviewed_at=timezone.now(),
        )

        logger.info(
            "[Dispute] RefundRequest#%s created for Dispute#%s | amount=%s",
            refund.pk, dispute.pk, refund_amount,
        )
        return refund

    @classmethod
    def _partial_escrow_resolution(
        cls,
        dispute: Dispute,
        admin_user,
        buyer_percent: Decimal,
        reason: str,
    ):
        """For partial verdict: refund buyer_percent, release rest to seller."""
        try:
            escrow = EscrowHolding.objects.get(order_item=dispute.order_item)
        except EscrowHolding.DoesNotExist:
            return

        gross      = escrow.gross_amount
        commission = escrow.commission_deducted
        buyer_gets  = (gross * buyer_percent / 100).quantize(Decimal("0.01"))
        seller_gets = max(Decimal("0"), gross - buyer_gets - commission)

        # Refund buyer portion via gateway
        from api.marketplace.models import PaymentTransaction
        from api.marketplace.enums import PaymentStatus, PaymentMethod
        PaymentTransaction.objects.create(
            tenant=escrow.tenant,
            order=escrow.order_item.order,
            user=escrow.order_item.order.user,
            method=PaymentMethod.BKASH,
            amount=-buyer_gets,
            currency="BDT",
            status=PaymentStatus.REFUNDED,
            gateway_response={"type": "partial_dispute_refund", "reason": reason},
            completed_at=timezone.now(),
        )

        # Create partial payout to seller
        if seller_gets > 0:
            from api.marketplace.models import SellerPayout
            from api.marketplace.enums import PayoutStatus
            SellerPayout.objects.create(
                tenant=escrow.tenant,
                seller=escrow.seller,
                amount=seller_gets,
                method="bkash",
                account_number=escrow.seller.phone,
                status=PayoutStatus.PENDING,
                note=f"Partial dispute resolution Dispute#{dispute.pk}",
                processed_by=admin_user,
            )

        # Mark escrow as released (partially)
        escrow.status      = EscrowStatus.RELEASED
        escrow.released_at = timezone.now()
        escrow.net_amount  = seller_gets
        escrow.save(update_fields=["status", "released_at", "net_amount"])

    @classmethod
    def _notify_dispute_raised(cls, dispute: Dispute):
        """Send notifications to seller + admin."""
        try:
            from api.marketplace.events import emit, REFUND_REQUESTED
            emit(REFUND_REQUESTED, dispute=dispute)
        except Exception as e:
            logger.error("[Dispute] Notify failed: %s", e)

    @classmethod
    def _notify_verdict(cls, dispute: Dispute, arbitration: DisputeArbitration):
        """Send verdict notification to buyer and seller."""
        try:
            from api.marketplace.events import emit
            emit("marketplace.dispute.resolved", dispute=dispute, arbitration=arbitration)
        except Exception as e:
            logger.error("[Dispute] Verdict notify failed: %s", e)
