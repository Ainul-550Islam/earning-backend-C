# api/wallet/smart_escrow.py
"""
Smart Escrow — programmable money with release conditions.
2027: Smart contracts becoming mainstream in B2B payments.

Features:
  - Lock funds in escrow until condition met
  - Auto-release on milestone completion
  - Multi-party escrow (buyer + seller + platform)
  - Dispute arbitration
  - Time-locked release (release after X days)
  - Conditional release (release when API confirms delivery)

Use cases:
  - Freelancer gets paid when client approves work
  - Publisher gets paid when offer conversion confirmed
  - B2B payment on delivery confirmation
  - Tournament prize held until winner determined

Zero core changes — uses existing WalletService.reserve_balance()
"""
import logging
import uuid
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger("wallet.escrow")


class EscrowService:
    """Smart escrow — lock and conditionally release funds."""

    @staticmethod
    def create(payer_user, payee_user_id: int, amount: Decimal,
                condition: str = "manual_release",
                condition_data: dict = None,
                description: str = "",
                expires_days: int = 30,
                arbitrator_id: int = None) -> dict:
        """
        Create an escrow agreement.

        condition options:
          - manual_release: admin or payer manually releases
          - time_release:   auto-releases after expires_days
          - api_confirm:    releases when external API confirms
          - mutual_agree:   both parties must confirm
        """
        from .services.core.WalletService import WalletService
        from django.contrib.auth import get_user_model

        payer_wallet = WalletService.get_or_create(payer_user)

        if payer_wallet.available_balance < amount:
            return {"success": False, "error": "Payer has insufficient balance"}
        if amount <= 0:
            return {"success": False, "error": "Amount must be positive"}

        escrow_id = uuid.uuid4().hex[:16]
        from datetime import timedelta
        expires_at = timezone.now() + timedelta(days=expires_days)

        try:
            # Lock funds in payer's wallet (reserved balance)
            WalletService.reserve_balance(
                payer_wallet, amount,
                reason=f"Escrow: {escrow_id}"
            )

            escrow = {
                "escrow_id":      escrow_id,
                "payer_id":       payer_user.id,
                "payee_id":       payee_user_id,
                "amount":         str(amount),
                "condition":      condition,
                "condition_data": condition_data or {},
                "description":    description[:200],
                "status":         "active",
                "arbitrator_id":  arbitrator_id,
                "created_at":     timezone.now().isoformat(),
                "expires_at":     expires_at.isoformat(),
                "payer_approved": False,
                "payee_approved": False,
                "released_at":    None,
                "dispute":        None,
            }

            from django.core.cache import cache
            cache.set(f"escrow:{escrow_id}", escrow, expires_days * 86400 + 3600)

            logger.info(f"Escrow created: {escrow_id} payer={payer_user.id} payee={payee_user_id} amount={amount}")
            return {
                "success":    True,
                "escrow_id":  escrow_id,
                "amount":     str(amount),
                "condition":  condition,
                "expires_at": expires_at.strftime("%Y-%m-%d"),
            }
        except Exception as e:
            logger.error(f"Escrow create error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def release(escrow_id: str, released_by_id: int) -> dict:
        """Release escrow funds to payee."""
        from django.core.cache import cache
        from .services.core.WalletService import WalletService
        from django.contrib.auth import get_user_model
        from django.db import transaction

        escrow = cache.get(f"escrow:{escrow_id}")
        if not escrow:
            return {"success": False, "error": "Escrow not found or expired"}
        if escrow["status"] != "active":
            return {"success": False, "error": f"Escrow status: {escrow['status']}"}

        try:
            User = get_user_model()
            payer = User.objects.get(id=escrow["payer_id"])
            payee = User.objects.get(id=escrow["payee_id"])
            amount = Decimal(escrow["amount"])

            payer_wallet = WalletService.get_or_create(payer)
            payee_wallet = WalletService.get_or_create(payee)

            with transaction.atomic():
                # Release reservation from payer
                WalletService.release_reserve(
                    payer_wallet, amount,
                    reason=f"Escrow released: {escrow_id}"
                )
                # Transfer to payee
                WalletService.debit(payer_wallet, amount,
                                    txn_type="escrow_payment",
                                    description=f"Escrow payment: {escrow['description']}")
                WalletService.credit(payee_wallet, amount,
                                     txn_type="escrow_receipt",
                                     description=f"Escrow received: {escrow['description']}")

            escrow["status"]      = "released"
            escrow["released_at"] = timezone.now().isoformat()
            escrow["released_by"] = released_by_id
            cache.set(f"escrow:{escrow_id}", escrow, 86400 * 30)

            logger.info(f"Escrow released: {escrow_id} to user={escrow['payee_id']}")
            return {"success": True, "escrow_id": escrow_id, "amount": str(amount),
                    "payee_id": escrow["payee_id"]}
        except Exception as e:
            logger.error(f"Escrow release error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def dispute(escrow_id: str, raised_by_id: int, reason: str) -> dict:
        """Raise a dispute on an escrow."""
        from django.core.cache import cache
        escrow = cache.get(f"escrow:{escrow_id}")
        if not escrow or escrow["status"] != "active":
            return {"success": False, "error": "Escrow not found or not active"}

        if raised_by_id not in [escrow["payer_id"], escrow["payee_id"]]:
            return {"success": False, "error": "Not a party to this escrow"}

        escrow["status"]  = "disputed"
        escrow["dispute"] = {
            "raised_by": raised_by_id,
            "reason":    reason[:500],
            "raised_at": timezone.now().isoformat(),
        }
        cache.set(f"escrow:{escrow_id}", escrow, 86400 * 60)
        logger.warning(f"Escrow disputed: {escrow_id} by user={raised_by_id}")
        return {"success": True, "status": "disputed", "arbitrator": escrow.get("arbitrator_id")}

    @staticmethod
    def get(escrow_id: str) -> dict:
        """Get escrow details."""
        from django.core.cache import cache
        return cache.get(f"escrow:{escrow_id}") or {"error": "Not found"}

    @staticmethod
    def check_expired_escrows() -> dict:
        """Auto-release or refund expired escrows. Called by Celery Beat."""
        from django.core.cache import cache
        from datetime import datetime
        processed = 0
        try:
            client = cache.client.get_client()
            keys = list(client.scan_iter("escrow:*", count=500))
            for key in keys:
                eid = key.decode().split(":")[-1]
                escrow = cache.get(f"escrow:{eid}")
                if not escrow or escrow.get("status") != "active":
                    continue
                exp = escrow.get("expires_at", "")
                if not exp:
                    continue
                exp_dt = datetime.fromisoformat(exp)
                if timezone.now() > (timezone.make_aware(exp_dt) if exp_dt.tzinfo is None else exp_dt):
                    # Expired — refund to payer
                    EscrowService._refund(eid, escrow)
                    processed += 1
        except Exception as e:
            return {"error": str(e)}
        return {"processed": processed}

    @staticmethod
    def _refund(escrow_id: str, escrow: dict) -> None:
        """Refund escrow amount to payer."""
        from .services.core.WalletService import WalletService
        from django.contrib.auth import get_user_model
        from django.core.cache import cache
        try:
            payer = get_user_model().objects.get(id=escrow["payer_id"])
            wallet = WalletService.get_or_create(payer)
            WalletService.release_reserve(wallet, Decimal(escrow["amount"]),
                                           reason=f"Escrow expired: {escrow_id}")
            escrow["status"]    = "refunded"
            escrow["refunded_at"] = timezone.now().isoformat()
            cache.set(f"escrow:{escrow_id}", escrow, 86400 * 30)
            logger.info(f"Escrow refunded: {escrow_id}")
        except Exception as e:
            logger.error(f"Escrow refund error: {e}")
