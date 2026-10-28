# api/wallet/adapters/__init__.py
"""
Wallet Adapter Layer — Complete cross-module communication hub.

RULE: All 50 external modules must import from here ONLY.
      No direct api.wallet.models or api.wallet.services imports.

INBOUND  (other modules → wallet): adapters/inbound.py
OUTBOUND (wallet → other modules): adapters/outbound.py
CONTRACTS (shared DTOs):           adapters/contracts.py

Quick reference for calling modules:

  # Model access
  from api.wallet.adapters.inbound import Wallet, WalletTransaction
  from api.wallet.adapters.inbound import WithdrawalRequest, Transaction

  # Service access
  from api.wallet.adapters.inbound import WalletService, TransactionService
  from api.wallet.adapters.inbound import WithdrawalService, EarningService

  # Functions
  from api.wallet.adapters.inbound import (
      credit_from_conversion,    # postback_engine, offerwall
      debit_for_reversal,        # postback_engine, conversion_tracking
      add_earnings,              # referral, tasks, offer_inventory
      add_referral_commission,   # referral.services
      deduct_balance,            # referral.CommissionClawbackService
      get_or_create_wallet,      # users.signals, referral
      get_wallet_summary,        # Login/views, admin_panel
      admin_credit, admin_debit, # admin_panel, management commands
      transfer,                  # views.py, tests
      get_balance,               # payment_gateways.data_bridge, cache
      get_kyc_level,             # decorators.py, permissions.py
      approve_withdrawal,        # referral.INTEGRATION_SYSTEM
  )

  # Validators (security module)
  from api.wallet.adapters.inbound import safe_ip_address, is_valid_ipv4

  # Celery beat schedule
  from api.wallet.adapters.inbound import get_beat_schedule  # WALLET_BEAT_SCHEDULE

  # Signals (apps.py ready())
  from api.wallet.adapters.inbound import connect_wallet_signals
"""
from .inbound import (
    # Models
    Wallet, WalletTransaction, Transaction, WithdrawalRequest,
    UserPaymentMethod, WalletWebhookLog, WalletHistory,
    # Services
    WalletService, TransactionService, WithdrawalService,
    EarningService, BalanceService, ReconciliationService, PayoutService,
    # Credit/debit
    credit_from_conversion, debit_for_reversal,
    add_earnings, add_referral_commission, deduct_balance,
    # Wallet management
    get_or_create_wallet, get_wallet_for_user, get_wallet_summary,
    get_balance, approve_withdrawal, admin_credit, admin_debit, transfer,
    # Auth/permissions
    get_kyc_level,
    # Validators
    safe_ip_address, is_valid_ipv4, is_valid_ipv6, get_validators,
    # Celery
    get_beat_schedule,
    # Signals
    connect_wallet_signals, get_plugin_registry, get_websocket_patterns,
    # Model getters (for isinstance checks)
    get_wallet_model, get_transaction_model, get_withdrawal_request_model,
)

__all__ = [
    # Models
    "Wallet", "WalletTransaction", "Transaction", "WithdrawalRequest",
    "UserPaymentMethod", "WalletWebhookLog", "WalletHistory",
    # Services
    "WalletService", "TransactionService", "WithdrawalService",
    "EarningService", "BalanceService", "ReconciliationService", "PayoutService",
    # Functions
    "credit_from_conversion", "debit_for_reversal",
    "add_earnings", "add_referral_commission", "deduct_balance",
    "get_or_create_wallet", "get_wallet_for_user", "get_wallet_summary",
    "get_balance", "approve_withdrawal", "admin_credit", "admin_debit", "transfer",
    "get_kyc_level",
    "safe_ip_address", "is_valid_ipv4", "is_valid_ipv6", "get_validators",
    "get_beat_schedule",
    "connect_wallet_signals", "get_plugin_registry", "get_websocket_patterns",
    "get_wallet_model", "get_transaction_model", "get_withdrawal_request_model",
]
