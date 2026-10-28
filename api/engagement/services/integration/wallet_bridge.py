# engagement/services/integration/wallet_bridge.py
"""
WalletBridge
============
All engagement coin operations route through here.

Engagement coin_balance is a VIRTUAL display cache.
Real money lives in api.wallet (Wallet.current_balance).

Flow:
    engagement action
        → WalletBridge.credit_coins()
            → WalletService.credit(wallet, amount, txn_type="reward")
            → user.coin_balance updated via F() (cache only)
            → WalletTransaction created with full audit trail
            → LedgerEntry created (double-entry accounting)

Why a bridge?
    - Engagement never imports wallet models directly (no coupling)
    - Graceful fallback if wallet app is unavailable (standalone mode)
    - Single place to add idempotency, retry, logging
    - Swap wallet backend without touching engagement code
"""

import logging
from decimal import Decimal
from typing import Optional
import uuid

from django.db import transaction
from django.db.models import F

logger = logging.getLogger("engagement.integration.wallet")


# ─── Engagement coin → wallet transaction type mapping ────────────────────────
COIN_SOURCE_TO_TXN_TYPE = {
    "checkin":       "reward",
    "spin":          "reward",
    "quest":         "reward",
    "achievement":   "reward",
    "battle_pass":   "reward",
    "leaderboard":   "contest_prize",
    "referral":      "referral",
    "shop_purchase": "withdrawal",   # debit
    "auction_bid":   "withdrawal",   # debit, refunded on outbid
    "auction_win":   "withdrawal",   # final debit on win
    "chest_buy":     "withdrawal",   # debit
    "scratch":       "reward",
    "calendar":      "reward",
    "prestige":      "reward",
    "guild":         "reward",
    "challenge":     "reward",
    "admin":         "admin_credit",
}


class WalletBridge:
    """
    Engagement → Wallet bridge.

    All methods are safe to call even if api.wallet is not installed.
    In standalone/test mode (no wallet app), operations fall back to
    direct coin_balance F() updates on the user model.
    """

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _get_wallet(user):
        """Get or create wallet. Returns None in standalone mode."""
        try:
            from api.wallet.services import WalletService
            return WalletService.get_or_create(user)
        except ImportError:
            return None
        except Exception as e:
            logger.warning(f"WalletBridge: cannot get wallet for user={user.pk}: {e}")
            return None

    @staticmethod
    def _txn_type(source: str) -> str:
        return COIN_SOURCE_TO_TXN_TYPE.get(source, "reward")

    @staticmethod
    def _idempotency_key(user_id: int, source: str, ref: str = "") -> str:
        """Deterministic idempotency key — prevents double-crediting."""
        return f"engagement:{source}:{user_id}:{ref}" if ref else ""

    # ── Public API ────────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def credit_coins(
        user,
        amount: Decimal,
        source: str,
        description: str = "",
        reference_id: str = "",
        metadata: dict = None,
        ip_address: str = None,
    ) -> dict:
        """
        Credit engagement coins to user.

        Always:
          1. Updates user.coin_balance cache (F() atomic)
          2. Creates WalletTransaction (if wallet available)
          3. Returns result dict

        Args:
            user:         User instance
            amount:       Coins to award (Decimal / float / int)
            source:       'checkin' | 'spin' | 'quest' | 'achievement' | etc.
            description:  Human-readable reason
            reference_id: Optional dedup key suffix (e.g. checkin pk)
            metadata:     Extra data stored on WalletTransaction
            ip_address:   Request IP for fraud logging

        Returns:
            {
                "success": bool,
                "coins_credited": float,
                "new_coin_balance": float,
                "wallet_txn_id": str | None,
                "mode": "wallet" | "standalone",
            }
        """
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError(f"credit_coins: amount must be positive, got {amount}")

        # ── Step 1: Update coin_balance cache atomically ──────────────────────
        type(user).objects.filter(pk=user.pk).update(
            coin_balance=F("coin_balance") + amount
        )
        user.refresh_from_db(fields=["coin_balance"])
        new_balance = float(user.coin_balance)

        # ── Step 2: Wallet ledger entry ───────────────────────────────────────
        wallet_txn_id = None
        mode = "standalone"

        wallet = WalletBridge._get_wallet(user)
        if wallet is not None:
            try:
                from api.wallet.services import WalletService
                from api.wallet.choices import TransactionType

                txn = WalletService.credit(
                    wallet=wallet,
                    amount=amount,
                    txn_type=WalletBridge._txn_type(source),
                    description=description or f"Engagement: {source}",
                    reference_id=reference_id,
                    reference_type=f"engagement.{source}",
                    metadata=metadata or {"source": source},
                    idempotency_key=WalletBridge._idempotency_key(
                        user.pk, source, reference_id
                    ),
                    ip_address=ip_address,
                )
                wallet_txn_id = str(txn.id)
                mode = "wallet"
                logger.info(
                    f"WalletBridge.credit: user={user.pk} amount={amount} "
                    f"source={source} txn={wallet_txn_id}"
                )
            except Exception as e:
                logger.error(
                    f"WalletBridge.credit WALLET FAILED user={user.pk} "
                    f"source={source}: {e} — coin_balance already updated"
                )

        return {
            "success": True,
            "coins_credited": float(amount),
            "new_coin_balance": new_balance,
            "wallet_txn_id": wallet_txn_id,
            "mode": mode,
        }

    @staticmethod
    @transaction.atomic
    def debit_coins(
        user,
        amount: Decimal,
        source: str,
        description: str = "",
        metadata: dict = None,
        ip_address: str = None,
    ) -> dict:
        """
        Debit engagement coins from user (shop purchase, auction bid, etc.)

        Raises:
            InsufficientCoinsError if user.coin_balance < amount

        Returns:
            {
                "success": bool,
                "coins_debited": float,
                "new_coin_balance": float,
                "wallet_txn_id": str | None,
                "mode": "wallet" | "standalone",
            }
        """
        from api.engagement.exceptions import InsufficientCoinsError

        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError(f"debit_coins: amount must be positive, got {amount}")

        # ── Lock user row for atomic balance check ────────────────────────────
        user_obj = type(user).objects.select_for_update().get(pk=user.pk)
        if user_obj.coin_balance < amount:
            raise InsufficientCoinsError(
                f"Need {amount} coins, have {user_obj.coin_balance}"
            )

        # ── Step 1: Deduct from coin_balance cache ────────────────────────────
        type(user).objects.filter(pk=user.pk).update(
            coin_balance=F("coin_balance") - amount
        )
        user.refresh_from_db(fields=["coin_balance"])
        new_balance = float(user.coin_balance)

        # ── Step 2: Wallet debit ──────────────────────────────────────────────
        wallet_txn_id = None
        mode = "standalone"

        wallet = WalletBridge._get_wallet(user)
        if wallet is not None:
            try:
                from api.wallet.services import WalletService

                txn = WalletService.debit(
                    wallet=wallet,
                    amount=amount,
                    txn_type=WalletBridge._txn_type(source),
                    description=description or f"Engagement: {source}",
                    metadata=metadata or {"source": source},
                    ip_address=ip_address,
                )
                wallet_txn_id = str(txn.id)
                mode = "wallet"
                logger.info(
                    f"WalletBridge.debit: user={user.pk} amount={amount} "
                    f"source={source} txn={wallet_txn_id}"
                )
            except Exception as e:
                logger.error(
                    f"WalletBridge.debit WALLET FAILED user={user.pk} "
                    f"source={source}: {e} — coin_balance already updated"
                )

        return {
            "success": True,
            "coins_debited": float(amount),
            "new_coin_balance": new_balance,
            "wallet_txn_id": wallet_txn_id,
            "mode": mode,
        }

    @staticmethod
    def get_balance(user) -> Decimal:
        """
        Get authoritative balance.
        Prefers wallet.available_balance, falls back to user.coin_balance.
        """
        wallet = WalletBridge._get_wallet(user)
        if wallet is not None:
            try:
                return Decimal(str(wallet.available_balance))
            except Exception:
                pass
        user.refresh_from_db(fields=["coin_balance"])
        return Decimal(str(user.coin_balance))

    @staticmethod
    def sync_balance(user) -> Decimal:
        """
        Sync user.coin_balance from wallet.available_balance.
        Called after external wallet changes (e.g., admin credit).
        """
        wallet = WalletBridge._get_wallet(user)
        if wallet is None:
            return Decimal(str(user.coin_balance))

        try:
            real_balance = Decimal(str(wallet.available_balance))
            type(user).objects.filter(pk=user.pk).update(coin_balance=real_balance)
            user.refresh_from_db(fields=["coin_balance"])
            return real_balance
        except Exception as e:
            logger.error(f"WalletBridge.sync_balance user={user.pk}: {e}")
            return Decimal(str(user.coin_balance))

    @staticmethod
    def refund_coins(
        user,
        amount: Decimal,
        source: str,
        original_txn_id: str = "",
        description: str = "",
    ) -> dict:
        """
        Refund coins to user (auction outbid, cancelled purchase, etc.)
        Wrapper around credit_coins with refund metadata.
        """
        return WalletBridge.credit_coins(
            user=user,
            amount=amount,
            source=source,
            description=description or f"Refund: {source}",
            reference_id=f"refund:{original_txn_id}",
            metadata={"refund": True, "original_txn_id": original_txn_id},
        )

    @staticmethod
    def get_transaction_history(user, limit: int = 50) -> list:
        """
        Get engagement-related wallet transactions for a user.
        Returns list of dicts for API responses.
        """
        try:
            from api.wallet.models import WalletTransaction
            wallet = WalletBridge._get_wallet(user)
            if wallet is None:
                return []
            txns = WalletTransaction.objects.filter(
                wallet=wallet,
                reference_type__startswith="engagement.",
            ).order_by("-created_at")[:limit]
            return [
                {
                    "id": str(t.id),
                    "type": t.type,
                    "amount": float(t.amount),
                    "description": t.description,
                    "source": t.reference_type.replace("engagement.", ""),
                    "created_at": t.created_at.isoformat(),
                }
                for t in txns
            ]
        except Exception as e:
            logger.error(f"WalletBridge.get_transaction_history user={user.pk}: {e}")
            return []
