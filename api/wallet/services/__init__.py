# api/wallet/services/__init__.py
"""
Wallet services package.

Usage:
    from api.wallet.services import WalletService, WithdrawalService, EarningService
    from api.wallet.services.core.WalletService import WalletService
    from api.wallet.services.withdrawal.WithdrawalService import WithdrawalService
    from api.wallet.services.earning.EarningService import EarningService
"""
from .core.WalletService import WalletService
from .core.TransactionService import TransactionService
from .core.BalanceService import BalanceService
from .core.IdempotencyService import IdempotencyService
from .ledger.LedgerService import LedgerService
from .ledger.ReconciliationService import ReconciliationService
from .ledger.LedgerSnapshotService import LedgerSnapshotService
from .withdrawal.WithdrawalService import WithdrawalService
from .withdrawal.WithdrawalLimitService import WithdrawalLimitService
from .withdrawal.WithdrawalFeeService import WithdrawalFeeService
from .withdrawal.WithdrawalBatchService import WithdrawalBatchService
from .earning.EarningService import EarningService
from .earning.EarningCapService import EarningCapService
from .WalletAnalyticsService import WalletAnalyticsService
from .CryptoPayoutService import CryptoPayoutService

__all__ = [
    "CryptoPayoutService",
    "WalletService", "TransactionService", "BalanceService", "IdempotencyService",
    "LedgerService", "ReconciliationService", "LedgerSnapshotService",
    "WithdrawalService", "WithdrawalLimitService", "WithdrawalFeeService", "WithdrawalBatchService",
    "EarningService", "EarningCapService",
    "WalletAnalyticsService",
]


# Re-exports: callers import these names from api.wallet.services,
# the real implementations live in api.wallet.adapters.inbound.
# Imported lazily inside the wrappers to avoid circular imports.
def credit_from_conversion(user, amount, *args, **kwargs):
    """Credit the wallet for a conversion.

    The adapter never raises: on any error it logs and returns a stub
    transaction (id=None). conversion.mark_wallet_credited() would then mark
    the conversion PAID although nothing was credited, so for a positive
    amount a missing transaction is raised here instead (RetryLog path).
    """
    from decimal import Decimal
    from api.wallet.adapters.inbound import credit_from_conversion as _impl
    _tx = _impl(user, amount, *args, **kwargs)
    if Decimal(str(amount)) > 0 and getattr(_tx, "pk", getattr(_tx, "id", None)) is None:
        raise RuntimeError("credit_from_conversion: wallet credit was not created")
    return _tx


def debit_for_reversal(*args, **kwargs):
    from api.wallet.adapters.inbound import debit_for_reversal as _impl
    return _impl(*args, **kwargs)


__all__ += ["credit_from_conversion", "debit_for_reversal"]
