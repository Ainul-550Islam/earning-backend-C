# api/payment_gateways/models/__init__.py
# Re-export all models for clean imports

from .core import (
    PaymentGateway, PaymentGatewayMethod, GatewayTransaction,
    PayoutRequest, GatewayConfig, Currency, PaymentGatewayWebhookLog,
    GATEWAY_CHOICES, TRANSACTION_TYPES, TRANSACTION_STATUS,
)
from .deposit import (
    DepositRequest, DepositCallback, DepositVerification, DepositRefund,
)
from .withdrawal import (
    WithdrawalGatewayRequest, WithdrawalGatewayCallback,
    WithdrawalReceipt, WithdrawalFailure,
)
from .gateway_config import (
    GatewayCredential, GatewayWebhookConfig, GatewayLimit,
    GatewayFeeRule, GatewayHealthLog,
)
from .reconciliation import (
    ReconciliationBatch, ReconciliationMismatch,
    GatewayStatement, PaymentAnalytics,
)

__all__ = [
    'PaymentGateway', 'PaymentGatewayMethod', 'GatewayTransaction',
    'PayoutRequest', 'GatewayConfig', 'Currency', 'PaymentGatewayWebhookLog',
    'DepositRequest', 'DepositCallback', 'DepositVerification', 'DepositRefund',
    'WithdrawalGatewayRequest', 'WithdrawalGatewayCallback',
    'WithdrawalReceipt', 'WithdrawalFailure',
    'GatewayCredential', 'GatewayWebhookConfig', 'GatewayLimit',
    'GatewayFeeRule', 'GatewayHealthLog',
    'ReconciliationBatch', 'ReconciliationMismatch',
    'GatewayStatement', 'PaymentAnalytics',
    'GATEWAY_CHOICES', 'TRANSACTION_TYPES', 'TRANSACTION_STATUS',
]

# --- Deterministic model registry -------------------------------------------
# Models in these modules were registered only as a side effect of URL/system-check
# imports, so processes without those imports (makemigrations --skip-checks, shell,
# workers) saw a smaller registry. Import them here so every process sees the same set.
from importlib import import_module as _import_module  # noqa: E402

for _mod in (
    "api.payment_gateways.blacklist.models",
    "api.payment_gateways.bonuses.models",
    "api.payment_gateways.fraud.models",
    "api.payment_gateways.integrations.models",
    "api.payment_gateways.locker.models",
    "api.payment_gateways.notifications.models",
    "api.payment_gateways.offers.models",
    "api.payment_gateways.publisher.models",
    "api.payment_gateways.referral.models",
    "api.payment_gateways.refunds.models",
    "api.payment_gateways.reports.models",
    "api.payment_gateways.schedules.models",
    "api.payment_gateways.smartlink.models",
    "api.payment_gateways.support.models",
    "api.payment_gateways.tracking.models",
):
    _import_module(_mod)
del _import_module, _mod
