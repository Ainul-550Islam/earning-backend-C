# api/wallet/exceptions.py
from rest_framework.exceptions import APIException
from rest_framework import status


# ── Domain exceptions (non-HTTP) ─────────────────────────────
class WalletError(Exception):
    """Base wallet error."""

class WalletLockedError(WalletError):
    def __init__(self, reason="Wallet is locked"):
        self.reason = reason
        super().__init__(reason)

class InsufficientBalanceError(WalletError):
    def __init__(self, available=0, required=0):
        self.available = available
        self.required  = required
        super().__init__(f"Insufficient. Available: {available}, Required: {required}")

class WithdrawalLimitError(WalletError):
    pass

class DuplicateTransactionError(WalletError):
    pass

class InvalidAmountError(WalletError):
    pass

class FraudError(WalletError):
    pass

class KYCRequiredError(WalletError):
    pass

class GatewayError(WalletError):
    pass

class OptimisticLockError(WalletError):
    pass

class WithdrawalBlockedError(WalletError):
    pass

class EarningCapExceededError(WalletError):
    pass

class SecurityLockError(WalletError):
    pass

class AMLFlaggedError(WalletError):
    pass


# ── API exceptions (HTTP) ─────────────────────────────────────
class WalletAPIError(APIException):
    status_code  = status.HTTP_400_BAD_REQUEST
    default_detail = "Wallet error"
    default_code   = "wallet_error"

class InsufficientBalanceAPIError(WalletAPIError):
    status_code    = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "Insufficient balance"
    default_code   = "insufficient_balance"

class WalletLockedAPIError(WalletAPIError):
    status_code    = status.HTTP_403_FORBIDDEN
    default_detail = "Wallet locked"
    default_code   = "wallet_locked"

class WithdrawalLimitAPIError(WalletAPIError):
    status_code    = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Withdrawal limit exceeded"
    default_code   = "withdrawal_limit_exceeded"

class KYCRequiredAPIError(WalletAPIError):
    status_code    = status.HTTP_403_FORBIDDEN
    default_detail = "KYC verification required"
    default_code   = "kyc_required"

class FraudAPIError(WalletAPIError):
    status_code    = status.HTTP_403_FORBIDDEN
    default_detail = "Transaction blocked — fraud detected"
    default_code   = "fraud_detected"

class SecurityLockAPIError(WalletAPIError):
    status_code    = status.HTTP_403_FORBIDDEN
    default_detail = "Withdrawals locked for security"
    default_code   = "security_lock"
