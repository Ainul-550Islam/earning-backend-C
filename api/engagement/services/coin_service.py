# engagement/services/coin_service.py
import logging
from decimal import Decimal
from django.db import transaction
from django.db.models import F

logger = logging.getLogger(__name__)


class CoinService:

    @staticmethod
    def _direct_add(user, amount: Decimal) -> Decimal:
        type(user).objects.filter(pk=user.pk).update(coin_balance=F("coin_balance") + amount)
        user.refresh_from_db(fields=["coin_balance"])
        return Decimal(str(user.coin_balance))

    @staticmethod
    def _direct_deduct(user, amount: Decimal) -> Decimal:
        from api.engagement.exceptions import InsufficientCoinsError
        locked = type(user).objects.select_for_update().get(pk=user.pk)
        if locked.coin_balance < amount:
            raise InsufficientCoinsError(f"Need {amount}, have {locked.coin_balance}")
        type(user).objects.filter(pk=user.pk).update(coin_balance=F("coin_balance") - amount)
        user.refresh_from_db(fields=["coin_balance"])
        return Decimal(str(user.coin_balance))

    @classmethod
    @transaction.atomic
    def add(cls, user, amount, source="engagement", reference_id="",
            ref_id="", description="", ip_address=None, metadata=None) -> Decimal:
        """Credit coins. Returns new balance."""
        reference_id = reference_id or ref_id
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError(f"amount must be positive, got {amount}")

        try:
            from api.engagement.services.integration.wallet_bridge import WalletBridge
            result = WalletBridge.credit_coins(
                user=user, amount=amount, source=source,
                description=description, reference_id=reference_id,
                metadata=metadata, ip_address=ip_address,
            )
            new_balance = Decimal(str(result["new_coin_balance"]))
        except Exception as e:
            logger.debug(f"WalletBridge unavailable ({e}), using direct update")
            new_balance = cls._direct_add(user, amount)

        try:
            from api.engagement.services.integration.event_bus import EngagementEventBus
            EngagementEventBus.emit_coins_earned(user, amount, source)
        except Exception:
            pass

        try:
            from api.engagement.services.integration.referral_bridge import ReferralBridge
            ReferralBridge.on_coins_earned(user, amount, source=source)
        except Exception:
            pass

        return new_balance

    @classmethod
    @transaction.atomic
    def deduct(cls, user, amount, source="shop_purchase", reference_id="",
               ref_id="", description="", ip_address=None) -> Decimal:
        """Debit coins. Raises InsufficientCoinsError if low balance."""
        reference_id = reference_id or ref_id
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError(f"amount must be positive, got {amount}")

        try:
            from api.engagement.services.integration.wallet_bridge import WalletBridge
            result = WalletBridge.debit_coins(
                user=user, amount=amount, source=source,
                description=description, ip_address=ip_address,
            )
            new_balance = Decimal(str(result["new_coin_balance"]))
        except Exception as e:
            from api.engagement.exceptions import InsufficientCoinsError
            if isinstance(e, InsufficientCoinsError):
                raise
            logger.debug(f"WalletBridge unavailable ({e}), using direct update")
            new_balance = cls._direct_deduct(user, amount)

        try:
            from api.engagement.services.integration.event_bus import EngagementEventBus
            EngagementEventBus.emit_coins_deducted(user, amount, source)
        except Exception:
            pass

        return new_balance

    @classmethod
    def balance(cls, user) -> Decimal:
        try:
            from api.engagement.services.integration.wallet_bridge import WalletBridge
            return WalletBridge.get_balance(user)
        except Exception:
            return Decimal(str(getattr(user, "coin_balance", 0)))

    @classmethod
    def get_balance(cls, user) -> Decimal:
        return cls.balance(user)

    @classmethod
    def refund(cls, user, amount, source="refund", original_ref="") -> Decimal:
        return cls.add(user, amount, source=source,
                       reference_id=f"refund:{original_ref}",
                       description=f"Refund: {source}")
