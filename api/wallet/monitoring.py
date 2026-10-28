# api/wallet/monitoring.py
"""
Monitoring — Prometheus metrics, Sentry, structured logging, performance tracking.
pip install sentry-sdk prometheus-client
"""
import logging
import time
from decimal import Decimal
from functools import wraps
from django.utils import timezone

logger = logging.getLogger("wallet.monitoring")


class WalletMetrics:
    """Prometheus metrics (lazy init — works without prometheus_client)."""
    _ready = False
    _c = {}  # counters
    _h = {}  # histograms
    _g = {}  # gauges

    @classmethod
    def _init(cls):
        if cls._ready:
            return
        try:
            import prometheus_client as prom
            cls._c["txn"]   = prom.Counter("wallet_txn_total", "Transactions", ["type","status"])
            cls._c["wd"]    = prom.Counter("wallet_wd_total", "Withdrawals", ["gateway","status"])
            cls._c["earn"]  = prom.Counter("wallet_earn_total", "Earnings", ["source"])
            cls._c["err"]   = prom.Counter("wallet_err_total", "Errors", ["op","etype"])
            cls._h["amt"]   = prom.Histogram("wallet_txn_amt_bdt","Amount BDT",
                                              buckets=[50,100,500,1000,5000,10000,50000,100000])
            cls._h["dur"]   = prom.Histogram("wallet_op_sec","Duration",["op"])
            cls._g["liab"]  = prom.Gauge("wallet_liability_bdt","Liability BDT")
            cls._g["pend"]  = prom.Gauge("wallet_pending_wd","Pending WD")
            cls._g["lock"]  = prom.Gauge("wallet_locked","Locked wallets")
            cls._ready = True
        except Exception:
            pass

    @classmethod
    def record_transaction(cls, txn_type:str, status:str, amount:Decimal=None):
        cls._init()
        try: cls._c["txn"].labels(type=txn_type, status=status).inc()
        except Exception: pass
        try:
            if amount: cls._h["amt"].observe(float(abs(amount)))
        except Exception: pass

    @classmethod
    def record_withdrawal(cls, gateway:str, status:str):
        cls._init()
        try: cls._c["wd"].labels(gateway=gateway, status=status).inc()
        except Exception: pass

    @classmethod
    def record_earning(cls, source_type:str):
        cls._init()
        try: cls._c["earn"].labels(source=source_type).inc()
        except Exception: pass

    @classmethod
    def record_error(cls, operation:str, error_type:str):
        cls._init()
        try: cls._c["err"].labels(op=operation, etype=error_type).inc()
        except Exception: pass

    @classmethod
    def update_gauges(cls):
        cls._init()
        try:
            from .models.core import Wallet
            from .models.withdrawal import WithdrawalRequest
            from django.db.models import Sum
            liab = Wallet.objects.aggregate(t=Sum("current_balance")+Sum("pending_balance"))["t"] or Decimal("0")
            try: cls._g["liab"].set(float(liab))
            except Exception: pass
            try: cls._g["pend"].set(WithdrawalRequest.objects.filter(status="pending").count())
            except Exception: pass
            try: cls._g["lock"].set(Wallet.objects.filter(is_locked=True).count())
            except Exception: pass
        except Exception as e:
            logger.debug(f"Gauge update: {e}")


class SentryIntegration:
    """Sentry error tracking."""

    @staticmethod
    def capture_exception(exc, context:dict=None, user=None):
        try:
            import sentry_sdk
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("component", "wallet")
                if context:
                    for k, v in context.items(): scope.set_extra(k, str(v))
                if user:
                    scope.user = {"id": user.id, "username": user.username}
                sentry_sdk.capture_exception(exc)
        except ImportError:
            logger.error(f"Wallet error: {exc}")
        except Exception: pass

    @staticmethod
    def capture_message(message:str, level:str="info"):
        try:
            import sentry_sdk
            sentry_sdk.capture_message(message, level=level)
        except Exception: pass

    @staticmethod
    def set_user_context(user):
        try:
            import sentry_sdk
            sentry_sdk.set_user({"id":str(user.id),"username":user.username,"email":user.email})
        except Exception: pass


class WalletLogger:
    """Structured logging for wallet events."""

    @staticmethod
    def log_transaction(txn, extra:dict=None):
        logger.info("wallet.transaction", extra={
            "event":"transaction","txn_id":str(txn.txn_id),"type":txn.type,
            "amount":str(txn.amount),"status":txn.status,"wallet_id":txn.wallet_id,
            "ts":timezone.now().isoformat(),**(extra or {})
        })

    @staticmethod
    def log_withdrawal(wr, extra:dict=None):
        logger.info("wallet.withdrawal", extra={
            "event":"withdrawal","withdrawal_id":str(wr.withdrawal_id),
            "amount":str(wr.amount),"status":wr.status,"user_id":wr.user_id,
            "ts":timezone.now().isoformat(),**(extra or {})
        })

    @staticmethod
    def log_fraud(wallet, score:float, signals:list):
        logger.warning("wallet.fraud", extra={
            "event":"fraud_detected","wallet_id":wallet.id,
            "user_id":wallet.user_id,"score":score,"signals":signals,
            "ts":timezone.now().isoformat()
        })


def monitor_performance(operation:str):
    """Decorator to time and record operation performance."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                return func(*args, **kwargs)
            except Exception as e:
                WalletMetrics.record_error(operation, type(e).__name__)
                raise
            finally:
                elapsed = time.monotonic() - start
                try:
                    WalletMetrics._init()
                    h = WalletMetrics._h.get("dur")
                    if h: h.labels(op=operation).observe(elapsed)
                except Exception: pass
                if elapsed > 1.0:
                    logger.warning(f"SLOW: {operation} {elapsed:.2f}s")
        return wrapper
    return decorator
