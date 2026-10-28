# api/wallet/adapters/inbound.py
"""
Inbound Adapter — Single Public API for all 50 external modules.

RULE: Every module that needs wallet must import from HERE only.
      No direct imports from api.wallet.models or api.wallet.services.

Modules covered (from api.zip analysis):
  postback_engine, offerwall, referral, users, tasks, signals,
  admin_panel, cache, cms, fraud_detection, offer_inventory,
  payment_gateways, security, integration_system, decorators,
  permissions, celery_beat_config, apps.py, and 30+ others.

Backward-compat aliases (for existing code that won't change):
  WalletService, TransactionService, WithdrawalService, EarningService
  Wallet, WalletTransaction, WithdrawalRequest, UserPaymentMethod
  credit_from_conversion, debit_for_reversal
"""
import logging
from decimal import Decimal
from typing import Optional, List

logger = logging.getLogger("wallet.adapters.inbound")

# ════════════════════════════════════════════════════════════════
# MODEL SHIMS — other modules do: from api.wallet.adapters.inbound import Wallet
# ════════════════════════════════════════════════════════════════

def _lazy(import_path: str, name: str):
    """Lazy import helper — returns the class/object on demand."""
    def getter():
        parts = import_path.rsplit(".", 1)
        mod = __import__(parts[0], fromlist=[parts[1]])
        return getattr(mod, parts[1])
    return getter


def get_wallet_model():
    from ..models.core import Wallet
    return Wallet

def get_transaction_model():
    from ..models.core import WalletTransaction
    return WalletTransaction

def get_withdrawal_request_model():
    from ..models.withdrawal import WithdrawalRequest
    return WithdrawalRequest

def get_user_payment_method_model():
    from ..models.withdrawal import UserPaymentMethod
    return UserPaymentMethod

def get_wallet_webhook_log_model():
    try:
        from ..models_webhook import WalletWebhookLog
        return WalletWebhookLog
    except Exception:
        return None

def get_wallet_history_model():
    """WalletHistory alias → BalanceHistory (same concept, different name)."""
    from ..models.balance import BalanceHistory
    return BalanceHistory

def get_transaction_alias():
    """Transaction alias → WalletTransaction (used by cms, users, admin_panel)."""
    from ..models.core import WalletTransaction
    return WalletTransaction


# ════════════════════════════════════════════════════════════════
# SERVICE SHIMS — other modules do: from api.wallet.adapters.inbound import WalletService
# ════════════════════════════════════════════════════════════════

def get_wallet_service():
    from ..services.core.WalletService import WalletService
    return WalletService

def get_transaction_service():
    from ..services.core.TransactionService import TransactionService
    return TransactionService

def get_withdrawal_service():
    from ..services.withdrawal.WithdrawalService import WithdrawalService
    return WithdrawalService

def get_earning_service():
    from ..services.earning.EarningService import EarningService
    return EarningService

def get_balance_service():
    from ..services.core.BalanceService import BalanceService
    return BalanceService

def get_reconciliation_service():
    from ..services.ledger.ReconciliationService import ReconciliationService
    return ReconciliationService

def get_payout_service():
    from ..services.earning.PayoutService import PayoutService
    return PayoutService


# ════════════════════════════════════════════════════════════════
# CREDIT / DEBIT — postback_engine, offerwall, services.py
# ════════════════════════════════════════════════════════════════

def credit_from_conversion(
    user,
    amount: Decimal,
    points: int = 0,
    source: str = "postback_engine",
    ref_id: str = "",
    description: str = "",
    offer_id: str = "",
    network_name: str = "",
    country_code: str = "",
    ip_address: str = "",
    idempotency_key: str = "",
):
    """
    Credit wallet from CPA/CPI/CPC conversion.
    Called by: postback_engine, offerwall, services.py, conversion_tracking.

    Returns WalletTransaction instance (has .id and .txn_id).
    Never raises — errors logged, stub returned.
    """
    try:
        user_obj = _resolve_user(user)
        wallet = _get_or_create_wallet(user_obj)
        amount = Decimal(str(amount))
        if amount <= Decimal("0"):
            return _stub_txn()

        from ..choices import TransactionType
        from ..services.core.WalletService import WalletService
        txn_map = {
            "postback_engine": TransactionType.CPA,
            "offerwall":       TransactionType.OFFER_WALL,
            "tasks":           TransactionType.EARNING,
        }
        txn = WalletService.credit(
            wallet=wallet,
            amount=amount,
            txn_type=txn_map.get(source, TransactionType.EARNING),
            description=description or f"{source}: {offer_id or ref_id}",
            reference_id=ref_id,
            reference_type=source,
            country_code=country_code,
            ip_address=ip_address,
            idempotency_key=idempotency_key or f"{source}:{ref_id}",
            metadata={"source": source, "offer_id": offer_id,
                      "network": network_name, "points": points},
            skip_multipliers=False,
        )
        if points > 0:
            _award_points(wallet, points, ref_id)
        logger.info(f"credit_from_conversion: user={user_obj.pk} amount={amount} source={source}")
        return txn
    except Exception as e:
        logger.exception(f"credit_from_conversion FAILED: user={getattr(user,'pk',user)} error={e}")
        return _stub_txn()


def debit_for_reversal(
    user,
    amount: Decimal,
    points: int = 0,
    ref_id: str = "",
    description: str = "Conversion reversal",
    idempotency_key: str = "",
):
    """
    Debit wallet for a conversion reversal.
    Called by: postback_engine.conversion_tracking, postback_handlers.
    Returns WalletTransaction or None on failure.
    """
    try:
        user_obj = _resolve_user(user)
        wallet = _get_wallet(user_obj)
        if wallet is None:
            return None
        amount = Decimal(str(amount))
        if amount <= Decimal("0"):
            return None
        from ..choices import TransactionType
        from ..services.core.WalletService import WalletService
        txn = WalletService.debit(
            wallet=wallet, amount=amount,
            txn_type=TransactionType.REVERSAL,
            description=description, reference_id=ref_id,
            reference_type="reversal",
            idempotency_key=idempotency_key or f"rev:{ref_id}",
            metadata={"points_reversed": points},
        )
        if points > 0:
            _reverse_points(wallet, points, ref_id)
        return txn
    except Exception as e:
        logger.exception(f"debit_for_reversal FAILED: user={getattr(user,'pk',user)} error={e}")
        return None


# ════════════════════════════════════════════════════════════════
# ADD EARNINGS — referral, tasks, offer_inventory, viewsets
# ════════════════════════════════════════════════════════════════

def add_earnings(
    wallet,
    amount: Decimal,
    description: str = "",
    reference_id: str = "",
    country_code: str = "",
    ip_address: str = "",
    metadata: dict = None,
):
    """
    Add earnings to wallet. Thin wrapper over WalletService.credit().
    Called by: referral.services, tasks.signals, offer_inventory, viewsets.
    Returns WalletTransaction.
    """
    try:
        from ..services.core.WalletService import WalletService
        from ..choices import TransactionType
        return WalletService.credit(
            wallet=wallet, amount=Decimal(str(amount)),
            txn_type=TransactionType.EARNING,
            description=description, reference_id=reference_id,
            country_code=country_code, ip_address=ip_address,
            metadata=metadata or {},
        )
    except Exception as e:
        logger.error(f"add_earnings FAILED wallet={getattr(wallet,'pk','?')} error={e}")
        return _stub_txn()


def add_referral_commission(
    wallet,
    amount: Decimal,
    level: int = 1,
    referred_user_id: int = None,
    description: str = "",
    skip_multipliers: bool = True,
):
    """
    Credit referral commission. Called by referral.services.
    skip_multipliers=True because referral service pre-computes the rate.
    """
    try:
        from ..services.core.WalletService import WalletService
        from ..choices import TransactionType
        return WalletService.credit(
            wallet=wallet, amount=Decimal(str(amount)),
            txn_type=TransactionType.REFERRAL,
            description=description or f"Referral L{level} commission",
            reference_id=str(referred_user_id or ""),
            reference_type="referral",
            skip_multipliers=skip_multipliers,
            metadata={"level": level, "referred_user_id": referred_user_id},
        )
    except Exception as e:
        logger.error(f"add_referral_commission FAILED: {e}")
        return _stub_txn()


def deduct_balance(wallet, amount: Decimal, description: str = "", reference_id: str = ""):
    """
    Deduct balance. Alias for WalletService.debit().
    Called by: referral.CommissionClawbackService, services.py.
    """
    try:
        from ..services.core.WalletService import WalletService
        from ..choices import TransactionType
        return WalletService.debit(
            wallet=wallet, amount=Decimal(str(amount)),
            txn_type=TransactionType.ADMIN_DEBIT,
            description=description, reference_id=reference_id,
        )
    except Exception as e:
        logger.error(f"deduct_balance FAILED: {e}")
        return None


# ════════════════════════════════════════════════════════════════
# WALLET MANAGEMENT — users.signals, admin_panel, decorators
# ════════════════════════════════════════════════════════════════

def get_or_create_wallet(user, currency: str = "BDT"):
    """
    Get or create wallet for a user.
    Called by: users.signals, referral, offer_inventory, viewsets.
    Returns (wallet, created) tuple.
    """
    try:
        from ..services.core.WalletService import WalletService
        return WalletService.get_or_create_wallet(user, currency=currency)
    except Exception as e:
        logger.error(f"get_or_create_wallet FAILED user={getattr(user,'pk','?')}: {e}")
        return None, False


def get_wallet_for_user(user):
    """Get existing wallet or None. Used by decorators, permissions."""
    try:
        from ..models.core import Wallet
        return Wallet.objects.filter(user=user).first()
    except Exception:
        return None


def get_wallet_summary(user) -> dict:
    """
    Full wallet summary dict.
    Called by: Login/views_enhanced.py, viewsets, admin_panel.
    Mirrors WalletService.get_wallet_summary() / get_summary().
    """
    try:
        from ..services.core.WalletService import WalletService
        return WalletService.get_wallet_summary(user)
    except Exception:
        try:
            from ..services.core.WalletService import WalletService
            return WalletService.get_summary(user)
        except Exception as e:
            logger.error(f"get_wallet_summary FAILED: {e}")
            return {"balance": "0", "available": "0", "currency": "BDT"}


def approve_withdrawal(txn, approved_by=None):
    """
    Approve a pending withdrawal transaction.
    Called by: referral.INTEGRATION_SYSTEM, services.py.
    """
    try:
        from ..services.core.WalletService import WalletService
        return WalletService.approve_withdrawal(txn, approved_by=approved_by)
    except Exception as e:
        logger.error(f"approve_withdrawal FAILED: {e}")
        return None


def admin_credit(wallet, amount: Decimal, description: str, admin):
    """Admin manual credit. Called by admin_panel, management commands, tests."""
    try:
        from ..services.core.WalletService import WalletService
        return WalletService.admin_credit(wallet, Decimal(str(amount)), description, admin)
    except Exception as e:
        logger.error(f"admin_credit FAILED: {e}")
        return _stub_txn()


def admin_debit(wallet, amount: Decimal, description: str, admin):
    """Admin manual debit. Called by admin_panel, management commands, tests."""
    try:
        from ..services.core.WalletService import WalletService
        return WalletService.admin_debit(wallet, Decimal(str(amount)), description, admin)
    except Exception as e:
        logger.error(f"admin_debit FAILED: {e}")
        return _stub_txn()


def transfer(from_wallet, to_wallet, amount: Decimal, description: str = ""):
    """Wallet-to-wallet transfer. Called by views.py, tests."""
    try:
        from ..services.core.WalletService import WalletService
        return WalletService.transfer(from_wallet, to_wallet, Decimal(str(amount)), description)
    except Exception as e:
        logger.error(f"transfer FAILED: {e}")
        return None


def get_balance(user_id: int) -> dict:
    """Balance dict. Called by payment_gateways.data_bridge, cache.views."""
    try:
        from ..models.core import Wallet
        wallet = Wallet.objects.get(user_id=user_id)
        return {
            "balance": str(wallet.current_balance),
            "available": str(wallet.available_balance),
            "bonus": str(wallet.bonus_balance),
            "currency": wallet.currency,
            "is_locked": wallet.is_locked,
        }
    except Exception:
        return {"balance": "0", "available": "0", "bonus": "0",
                "currency": "BDT", "is_locked": False}


def get_kyc_level(user) -> int:
    """KYC level 0-3. Called by decorators.py, permissions.py."""
    try:
        from ..adapters.outbound import get_user_kyc_level
        uid = user.pk if hasattr(user, "pk") else int(user)
        return get_user_kyc_level(uid)
    except Exception:
        return 0


# ════════════════════════════════════════════════════════════════
# VALIDATORS — security.admin, security.models, models.py
# ════════════════════════════════════════════════════════════════

def get_validators():
    """
    Return validator functions from validators.py.
    Called by: security.admin, security.models, cms/models.py.

    Usage:
        from api.wallet.adapters.inbound import get_validators
        v = get_validators()
        v["safe_ip_address"](ip)
        v["is_valid_ipv4"](ip)
    """
    try:
        from ..validators import safe_ip_address, is_valid_ipv4, is_valid_ipv6
        return {
            "safe_ip_address": safe_ip_address,
            "is_valid_ipv4":   is_valid_ipv4,
            "is_valid_ipv6":   is_valid_ipv6,
        }
    except Exception:
        return {
            "safe_ip_address": lambda ip: ip,
            "is_valid_ipv4":   lambda ip: bool(ip),
            "is_valid_ipv6":   lambda ip: bool(ip),
        }


# Safe to import directly (no Django models needed)
def safe_ip_address(ip: str) -> str:
    try:
        from ..validators import safe_ip_address as _f
        return _f(ip)
    except Exception:
        return ip

def is_valid_ipv4(ip: str) -> bool:
    try:
        from ..validators import is_valid_ipv4 as _f
        return _f(ip)
    except Exception:
        import re
        return bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip or ""))

def is_valid_ipv6(ip: str) -> bool:
    try:
        from ..validators import is_valid_ipv6 as _f
        return _f(ip)
    except Exception:
        return ":" in (ip or "")


# ════════════════════════════════════════════════════════════════
# CELERY BEAT SCHEDULE — celery_beat_config.py, celery_schedule.py
# ════════════════════════════════════════════════════════════════

def get_beat_schedule() -> dict:
    """
    Return wallet Celery beat schedule.
    Called by: celery_beat_config.py as WALLET_BEAT_SCHEDULE.
    """
    try:
        from ..constants import WALLET_BEAT_SCHEDULE
        return WALLET_BEAT_SCHEDULE
    except Exception:
        return {}


# ════════════════════════════════════════════════════════════════
# SIGNALS / APPS INTEGRATION — apps.py, signals.py
# ════════════════════════════════════════════════════════════════

def connect_wallet_signals():
    """
    Connect all wallet signals. Called by apps.py ready().
    Safe to call multiple times (signals check for duplicates).
    """
    try:
        from ..receivers import connect_receivers
        connect_receivers()
    except Exception as e:
        logger.debug(f"connect_receivers skipped: {e}")
    try:
        from ..signals import connect_cpalead_signals
        connect_cpalead_signals()
    except Exception as e:
        logger.debug(f"connect_cpalead_signals skipped: {e}")

def get_plugin_registry():
    """Return wallet plugin registry. Called by apps.py, plugins.py."""
    try:
        from ..registry import wallet_registry
        return wallet_registry
    except Exception:
        return None

def get_websocket_patterns():
    """WebSocket URL patterns. Called by routing.py."""
    try:
        from ..routing import websocket_urlpatterns
        return websocket_urlpatterns
    except Exception:
        return []


# ════════════════════════════════════════════════════════════════
# BACKWARD-COMPAT CLASS ALIASES
# These let old code do: from api.wallet.adapters.inbound import WalletService
# ════════════════════════════════════════════════════════════════

class _LazyProxy:
    """Proxy that loads the real class on first attribute access."""
    def __init__(self, loader):
        object.__setattr__(self, "_loader", loader)
        object.__setattr__(self, "_real", None)

    def _load(self):
        real = object.__getattribute__(self, "_real")
        if real is None:
            loader = object.__getattribute__(self, "_loader")
            real = loader()
            object.__setattr__(self, "_real", real)
        return real

    def __getattr__(self, name):
        return getattr(self._load(), name)

    def __call__(self, *args, **kwargs):
        return self._load()(*args, **kwargs)


# Class-level proxies for old-style imports
WalletService       = _LazyProxy(get_wallet_service)
TransactionService  = _LazyProxy(get_transaction_service)
WithdrawalService   = _LazyProxy(get_withdrawal_service)
EarningService      = _LazyProxy(get_earning_service)
BalanceService      = _LazyProxy(get_balance_service)
ReconciliationService = _LazyProxy(get_reconciliation_service)
PayoutService       = _LazyProxy(get_payout_service)

Wallet              = _LazyProxy(get_wallet_model)
WalletTransaction   = _LazyProxy(get_transaction_model)
Transaction         = _LazyProxy(get_transaction_alias)
WithdrawalRequest   = _LazyProxy(get_withdrawal_request_model)
UserPaymentMethod   = _LazyProxy(get_user_payment_method_model)
WalletWebhookLog    = _LazyProxy(get_wallet_webhook_log_model)
WalletHistory       = _LazyProxy(get_wallet_history_model)


# ════════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ════════════════════════════════════════════════════════════════

def _resolve_user(user):
    if isinstance(user, int):
        from django.contrib.auth import get_user_model
        return get_user_model().objects.get(pk=user)
    return user

def _get_wallet(user):
    try:
        from ..models.core import Wallet as W
        return W.objects.get(user=user)
    except Exception:
        return None

def _get_or_create_wallet(user):
    from ..services.core.WalletService import WalletService
    _res = WalletService.get_or_create_wallet(user)
    wallet = _res[0] if isinstance(_res, tuple) else _res
    return wallet

def _award_points(wallet, points, ref_id):
    try:
        from ..models_cpalead_extra import PointsLedger
        PointsLedger.objects.create(wallet=wallet, user=wallet.user,
                                    points=points, action="conversion", reference_id=ref_id)
    except Exception:
        pass

def _reverse_points(wallet, points, ref_id):
    try:
        from ..models_cpalead_extra import PointsLedger
        PointsLedger.objects.create(wallet=wallet, user=wallet.user,
                                    points=-abs(points), action="reversal", reference_id=ref_id)
    except Exception:
        pass

class _StubTxn:
    pk = None; id = None; txn_id = ""; amount = Decimal("0")
    status = "failed"; type = "unknown"

def _stub_txn():
    return _StubTxn()
