# api/wallet/services/CryptoPayoutService.py
"""
CryptoPayoutService — standalone for backward-compatible imports.
from api.wallet.services.CryptoPayoutService import CryptoPayoutService
"""


class CryptoPayoutService:
    """
    USDT TRC-20 / ERC-20 payout service.
    Full implementation delegates to api.wallet.services.CryptoPayoutService
    via lazy import to avoid circular dependencies.
    """

    @staticmethod
    def _get_impl():
        """Lazy import to avoid circular dependency."""
        from api.wallet.services import CryptoPayoutService as _Impl  # noqa
        return _Impl

    @classmethod
    def validate_wallet_address(cls, address: str, currency: str) -> bool:
        try:
            return cls._get_impl().validate_wallet_address(address, currency)
        except Exception:
            import re
            if currency.upper() in ("USDT_TRC20", "TRX"):
                return bool(re.match(r"^T[A-Za-z1-9]{33}$", address or ""))
            return bool(re.match(r"^0x[0-9a-fA-F]{40}$", address or ""))

    @classmethod
    def get_exchange_rate(cls, from_currency: str, to_currency: str) -> float:
        try:
            return cls._get_impl().get_exchange_rate(from_currency, to_currency)
        except Exception:
            return 1.0

    @classmethod
    def create_payout(cls, wallet, amount, currency: str, address: str, **kwargs) -> dict:
        try:
            return cls._get_impl().create_payout(wallet, amount, currency, address, **kwargs)
        except Exception as e:
            raise NotImplementedError(f"CryptoPayoutService.create_payout: {e}")

    @classmethod
    def process_payout(cls, wallet, amount, currency: str, address: str) -> dict:
        return cls.create_payout(wallet, amount, currency, address)

    @classmethod
    def validate_address(cls, currency: str, address: str) -> bool:
        return cls.validate_wallet_address(address, currency)

    @classmethod
    def get_network_fee(cls, currency: str) -> float:
        try:
            return cls._get_impl().get_network_fee(currency)
        except Exception:
            return 0.0


__all__ = ["CryptoPayoutService"]
