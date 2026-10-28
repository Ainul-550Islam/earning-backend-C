"""
adapters/wallet_bridge.py – Postback → Wallet integration bridge.

এই file টা postback app এর ভেতরে থাকে।
Wallet app এ কোনো code লেখা হয়নি।

Design:
  • Lazy import of wallet services — postback has NO hard dependency on wallet.
  • Wallet app না থাকলেও postback চলবে (warning log হবে শুধু).
  • WalletService.credit() call করে points → BDT convert করে credit করে.
  • WalletService.debit() call করে reversal এ points rollback করে.
  • Idempotency key = postback_log.pk → double-credit কখনো হবে না.
  • সব call try/except wrapped → wallet failure কখনো postback block করবে না.

Wallet app এর public API যা use করা হয়:
    api.wallet.models.Wallet.objects.get_or_create_for_user(user)
    api.wallet.services.core.WalletService.credit(wallet, amount, ...)
    api.wallet.services.core.WalletService.debit(wallet, amount, ...)
"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

# Points থেকে BDT conversion rate
# Example: 100 points = 1 BDT → rate = 0.01
# Admin NetworkPostbackConfig.metadata তে override করা যাবে:
#   metadata = {"points_to_bdt_rate": 0.005}
_DEFAULT_POINTS_TO_BDT = Decimal("0.01")


def credit_wallet_for_postback(*, postback_log) -> bool:
    """
    Credit the user's wallet after a successful postback reward.

    Points → BDT conversion:
        wallet_amount = points_awarded × points_to_bdt_rate

    Args:
        postback_log: PostbackLog instance (must have resolved_user, points_awarded)

    Returns:
        True if wallet credited successfully, False otherwise.
        Never raises.
    """
    user = postback_log.resolved_user
    points = getattr(postback_log, "points_awarded", 0) or 0

    if not user or points <= 0:
        logger.debug(
            "credit_wallet_for_postback: skipping (user=%s points=%d)",
            user, points,
        )
        return False

    try:
        from api.wallet.models import Wallet
        from api.wallet.services.core.WalletService import WalletService
        from api.wallet.choices import TransactionType
    except ImportError:
        logger.warning(
            "WALLET NOT AVAILABLE: api.wallet not installed — "
            "postback %s awarded %d points but wallet NOT credited. "
            "Install wallet app or connect postback_rewarded signal manually.",
            postback_log.pk, points,
        )
        return False

    try:
        # Get or create wallet for user
        wallet, _ = Wallet.objects.get_or_create_for_user(user)

        # Convert points → BDT
        meta = getattr(postback_log.network, "metadata", {}) or {}
        rate = Decimal(str(meta.get("points_to_bdt_rate", _DEFAULT_POINTS_TO_BDT)))
        amount = (Decimal(str(points)) * rate).quantize(Decimal("0.01"))

        if amount <= 0:
            logger.warning(
                "credit_wallet_for_postback: calculated amount is zero "
                "(points=%d rate=%s) — skipping credit for postback %s",
                points, rate, postback_log.pk,
            )
            return False

        # Build metadata for audit trail
        txn_metadata = {
            "source": "postback",
            "postback_log_id": str(postback_log.pk),
            "network_key": postback_log.network.network_key,
            "offer_id": postback_log.offer_id,
            "lead_id": postback_log.lead_id,
            "event_type": getattr(postback_log, "event_type", "unknown"),
            "points_awarded": points,
            "points_to_bdt_rate": str(rate),
        }

        txn = WalletService.credit(
            wallet=wallet,
            amount=amount,
            txn_type=getattr(TransactionType, "EARNING", "earning"),
            description=(
                f"Postback reward: {points} pts "
                f"({postback_log.network.network_key} / "
                f"{postback_log.offer_id})"
            ),
            reference_id=str(postback_log.pk),
            reference_type="postback",
            metadata=txn_metadata,
            idempotency_key=f"postback:{postback_log.pk}",
            ip_address=postback_log.source_ip,
        )

        logger.info(
            "Wallet credited: user=%s amount=%s BDT points=%d "
            "txn=%s postback=%s network=%s",
            user.pk, amount, points, txn.pk,
            postback_log.pk, postback_log.network.network_key,
        )
        return True

    except Exception as exc:
        logger.error(
            "credit_wallet_for_postback FAILED: postback=%s user=%s points=%d: %s",
            postback_log.pk, user.pk, points, exc,
        )
        return False


def debit_wallet_for_reversal(*, reversal_log) -> bool:
    """
    Debit the user's wallet after a chargeback/reversal postback.

    Finds the original PostbackLog and deducts the equivalent BDT amount.

    Args:
        reversal_log: PostbackLog instance with is_reversal=True

    Returns:
        True if wallet debited successfully, False otherwise.
        Never raises.
    """
    user = reversal_log.resolved_user
    original = getattr(reversal_log, "reversed_log", None)

    if not user or not original:
        logger.warning(
            "debit_wallet_for_reversal: missing user or original log "
            "(reversal=%s)", reversal_log.pk,
        )
        return False

    points_to_deduct = getattr(original, "points_awarded", 0) or 0
    if points_to_deduct <= 0:
        logger.info(
            "debit_wallet_for_reversal: original had 0 points — nothing to deduct "
            "(reversal=%s)", reversal_log.pk,
        )
        return True

    try:
        from api.wallet.models import Wallet
        from api.wallet.services.core.WalletService import WalletService
        from api.wallet.choices import TransactionType
    except ImportError:
        logger.warning(
            "WALLET NOT AVAILABLE: cannot debit for reversal %s", reversal_log.pk
        )
        return False

    try:
        wallet, _ = Wallet.objects.get_or_create_for_user(user)

        meta = getattr(original.network, "metadata", {}) or {}
        rate = Decimal(str(meta.get("points_to_bdt_rate", _DEFAULT_POINTS_TO_BDT)))
        amount = (Decimal(str(points_to_deduct)) * rate).quantize(Decimal("0.01"))

        if amount <= Decimal("0"):
            return True

        txn_metadata = {
            "source": "postback_reversal",
            "reversal_log_id": str(reversal_log.pk),
            "original_log_id": str(original.pk),
            "network_key": original.network.network_key,
            "lead_id": original.lead_id,
            "points_deducted": points_to_deduct,
        }

        WalletService.debit(
            wallet=wallet,
            amount=amount,
            txn_type=getattr(TransactionType, "REVERSAL", "reversal"),
            description=(
                f"Postback reversal/chargeback: {points_to_deduct} pts "
                f"({original.network.network_key} / {original.lead_id})"
            ),
            metadata=txn_metadata,
        )

        logger.info(
            "Wallet debited for reversal: user=%s amount=%s BDT "
            "reversal=%s original=%s",
            user.pk, amount, reversal_log.pk, original.pk,
        )
        return True

    except Exception as exc:
        logger.error(
            "debit_wallet_for_reversal FAILED: reversal=%s user=%s: %s",
            reversal_log.pk, user.pk, exc,
        )
        return False
