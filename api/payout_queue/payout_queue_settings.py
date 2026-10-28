"""
api/payout_queue/payout_queue_settings.py
==========================================
Production settings for api.payout_queue — tailored to your specific project.

HOW TO ADD TO YOUR MAIN SETTINGS
----------------------------------
In your settings/base.py (or settings/production.py), add at the bottom:

    # ── payout_queue integration ─────────────────────────────────────────
    from api.payout_queue.payout_queue_settings import (
        PAYMENT_GATEWAY_CONFIGS,
        PAYOUT_THROTTLE_RATES,
        PAYOUT_WEBHOOK_SECRET,
        PAYOUT_WEBHOOK_URLS,
        PAYOUT_WEBHOOK_TIMEOUT_SECONDS,
        PAYOUT_NOTIFICATION_TASK,
        PAYOUT_KYC_CHECK_ENABLED,
        PAYOUT_FRAUD_CHECK_ENABLED,
        PAYOUT_FRAUD_RISK_THRESHOLD,
        PAYOUT_WALLET_CHECK_ENABLED,
        PAYOUT_AUDIT_LOG_ENABLED,
        PAYOUT_STATS_CACHE_TTL,
        PAYOUT_CELERY_BEAT_ENTRIES,
        PAYOUT_LOGGING_ENTRIES,
    )
    CELERY_BEAT_SCHEDULE.update(PAYOUT_CELERY_BEAT_ENTRIES)
    LOGGING["loggers"].update(PAYOUT_LOGGING_ENTRIES)
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({
        "payout_burst":     PAYOUT_THROTTLE_RATES["burst"],
        "payout_sustained": PAYOUT_THROTTLE_RATES["sustained"],
        "payout_process":   PAYOUT_THROTTLE_RATES["process"],
    })

ENVIRONMENT VARIABLES TO ADD TO YOUR .env
-------------------------------------------
# ── Gateway credentials ──────────────────────────────────────────────────
BKASH_APP_KEY=
BKASH_APP_SECRET=
BKASH_USERNAME=
BKASH_PASSWORD=
BKASH_BASE_URL=https://tokenized.pay.bka.sh/v1.2.0-beta          # prod URL

NAGAD_MERCHANT_ID=
NAGAD_MERCHANT_NUMBER=
NAGAD_PRIVATE_KEY=
NAGAD_PUBLIC_KEY=
NAGAD_BASE_URL=https://api.mynagad.com/api/dfs                     # prod URL

ROCKET_API_KEY=
ROCKET_MERCHANT_NUMBER=
ROCKET_BASE_URL=

BANK_API_KEY=
BANK_BASE_URL=

# ── Payout module ────────────────────────────────────────────────────────
PAYOUT_WEBHOOK_SECRET=          # python -c "import secrets; print(secrets.token_hex(32))"
PAYOUT_WEBHOOK_URLS=            # comma-separated https URLs
PAYOUT_THROTTLE_BURST=60/min
PAYOUT_THROTTLE_SUSTAINED=1000/hour
PAYOUT_THROTTLE_PROCESS=10/min
PAYOUT_WEBHOOK_TIMEOUT_SECONDS=10

# ── Integration flags (all True in production) ────────────────────────────
PAYOUT_KYC_CHECK_ENABLED=True
PAYOUT_FRAUD_CHECK_ENABLED=True
PAYOUT_FRAUD_RISK_THRESHOLD=0.75
PAYOUT_WALLET_CHECK_ENABLED=True
PAYOUT_AUDIT_LOG_ENABLED=True
"""

from __future__ import annotations
import os

def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)

def _env_bool(key: str, default: bool = False) -> bool:
    return _env(key, str(default)).lower() in ("true", "1", "yes")

def _env_list(key: str, default: list = None) -> list:
    raw = _env(key, "").strip()
    if not raw:
        return default or []
    return [u.strip() for u in raw.split(",") if u.strip()]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. PAYMENT GATEWAY CONFIGS
#    Used by: api/payout_queue/processors/bkash.py, nagad.py, rocket.py, bank.py
#
#    NOTE: You also have api.payment_gateways in your project.
#    If api.payment_gateways already stores these credentials in the DB,
#    replace this dict with a loader that reads from your GatewayConfig model:
#
#        from api.payment_gateways.models import GatewayConfig
#        def _load_gateway_config():
#            configs = {}
#            for gw in GatewayConfig.objects.filter(is_active=True):
#                configs[gw.gateway_code] = gw.credentials   # JSONField
#            return configs
#        PAYMENT_GATEWAY_CONFIGS = _load_gateway_config()
#
#    Until you do that, this env-based config is the safe default.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PAYMENT_GATEWAY_CONFIGS = {

    "BKASH": {
        "app_key":    _env("BKASH_APP_KEY"),
        "app_secret": _env("BKASH_APP_SECRET"),
        "username":   _env("BKASH_USERNAME"),
        "password":   _env("BKASH_PASSWORD"),
        "base_url":   _env(
            "BKASH_BASE_URL",
            default="https://tokenized.sandbox.bka.sh/v1.2.0-beta",
        ),
    },

    "NAGAD": {
        "merchant_id":    _env("NAGAD_MERCHANT_ID"),
        "merchant_phone": _env("NAGAD_MERCHANT_NUMBER"),
        "private_key":    _env("NAGAD_PRIVATE_KEY"),
        "public_key":     _env("NAGAD_PUBLIC_KEY"),
        "base_url":       _env(
            "NAGAD_BASE_URL",
            default="http://sandbox.mynagad.com:10080/remote-payment-gateway-1.0/api/dfs",
        ),
    },

    "ROCKET": {
        "api_key":         _env("ROCKET_API_KEY"),
        "merchant_number": _env("ROCKET_MERCHANT_NUMBER"),
        "base_url":        _env("ROCKET_BASE_URL"),
    },

    "BANK": {
        "api_key":  _env("BANK_API_KEY"),
        "base_url": _env("BANK_BASE_URL"),
    },

    "MANUAL": {},
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. CELERY BEAT SCHEDULE ENTRIES
#    Usage: CELERY_BEAT_SCHEDULE.update(PAYOUT_CELERY_BEAT_ENTRIES)
#
#    ⚠ Without this, NONE of the payout periodic tasks will run automatically.
#
#    You have api.tasks in your project. If you manage all beat schedules
#    in one place (a central beat_schedule.py or through django-celery-beat),
#    copy these entries there instead.
#
#    Required Celery queues to add to your worker config:
#      celery -A config worker -Q payout_processing,payout_maintenance,celery
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PAYOUT_CELERY_BEAT_ENTRIES = {

    # Processes all PENDING batches that are due. Runs every 60 seconds.
    "payout-process-due-batches": {
        "task":     "payout_queue.process_due_batches",
        "schedule": 60.0,
        "options":  {"queue": "payout_processing", "expires": 55},
    },

    # Retries RETRYING payout items whose next_retry_at has passed.
    "payout-retry-due-items": {
        "task":     "payout_queue.retry_due_items",
        "schedule": 120.0,
        "options":  {"queue": "payout_processing", "expires": 110},
    },

    # Expires WithdrawalPriority records past their expires_at datetime.
    "payout-expire-priorities": {
        "task":     "payout_queue.expire_withdrawal_priorities",
        "schedule": 300.0,
        "options":  {"queue": "payout_maintenance", "expires": 290},
    },

    # Releases advisory locks on batches stuck in PROCESSING > 1 hour.
    # Guards against worker crashes leaving batches permanently locked.
    "payout-release-stale-locks": {
        "task":     "payout_queue.release_stale_locks",
        "schedule": 900.0,
        "options":  {"queue": "payout_maintenance"},
    },
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. RATE LIMITING / THROTTLING
#    Usage: REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({...})
#
#    You have api.rate_limit in your project. These DRF throttle classes
#    (in api/payout_queue/throttles.py) are per-view, per-user limits
#    enforced at the DRF middleware layer. They complement your api.rate_limit
#    app — both can coexist without conflict.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PAYOUT_THROTTLE_RATES = {
    "burst":     _env("PAYOUT_THROTTLE_BURST",     default="60/min"),
    "sustained": _env("PAYOUT_THROTTLE_SUSTAINED", default="1000/hour"),
    "process":   _env("PAYOUT_THROTTLE_PROCESS",   default="10/min"),
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. WEBHOOK DELIVERY
#    You have api.webhooks in your project.
#
#    OPTION A — Route through your own api.webhooks system:
#      Point PAYOUT_WEBHOOK_URLS to your internal webhook ingestion endpoint.
#      Your webhook app then fans out to registered merchant endpoints.
#      This is the RECOMMENDED approach since you already have a webhook system.
#
#    OPTION B — Deliver directly to external URLs:
#      List merchant endpoints directly in PAYOUT_WEBHOOK_URLS.
#
#    OPTION C — Disable (leave empty):
#      No webhooks are dispatched. Safe for development.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PAYOUT_WEBHOOK_URLS = _env_list(
    "PAYOUT_WEBHOOK_URLS",
    default=[
        # Option A: route through your api.webhooks app
        # "https://your-domain.com/api/webhooks/ingest/payout/",
    ],
)

# HMAC-SHA256 key — receivers verify via X-Payout-Signature header.
# Generate: python -c "import secrets; print(secrets.token_hex(32))"
# NEVER hardcode. Always read from environment.
PAYOUT_WEBHOOK_SECRET = _env("PAYOUT_WEBHOOK_SECRET", default="")

# HTTP timeout for outbound webhook POST calls (seconds)
PAYOUT_WEBHOOK_TIMEOUT_SECONDS = int(_env("PAYOUT_WEBHOOK_TIMEOUT_SECONDS", default="10"))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. NOTIFICATION INTEGRATION → api.notifications
#
#    You have api.notifications. This task is called when a payout batch
#    completes or fails. Create this task in api/notifications/tasks.py:
#
#    @shared_task(name="notifications.send_payout_notification", bind=True)
#    def send_payout_notification(self, *, user_id, event, data):
#        """
#        event: "completed" | "failed"
#        data:  {batch_id, batch_name, gateway, status,
#                success_count, failure_count, net_amount}
#        """
#        from django.contrib.auth import get_user_model
#        from api.notifications.models import Notification
#        User = get_user_model()
#        try:
#            user = User.objects.get(pk=user_id)
#        except User.DoesNotExist:
#            return
#        if event == "completed":
#            Notification.objects.create(
#                user=user,
#                title="Payout Processed",
#                body=(
#                    f"Your payout of {data.get('net_amount','?')} BDT "
#                    f"has been successfully processed."
#                ),
#                notification_type="PAYOUT_SUCCESS",
#                channel="push",
#                metadata=data,
#            )
#        elif event == "failed":
#            Notification.objects.create(
#                user=user,
#                title="Payout Failed",
#                body=(
#                    f"Your payout batch '{data.get('batch_name','?')}' "
#                    f"could not be processed. Please contact support."
#                ),
#                notification_type="PAYOUT_FAILED",
#                channel="push",
#                metadata=data,
#            )
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PAYOUT_NOTIFICATION_TASK = _env(
    "PAYOUT_NOTIFICATION_TASK",
    default="api.notifications.tasks.send_payout_notification",
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. INTEGRATION FLAGS — controls cross-app safety gates
#    All should be True in production.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# api.kyc — verify user KYC before adding to a payout batch.
# Bangladesh Bank BFIU compliance requires KYC for all financial payouts.
# When True: add_payout_items() calls is_user_kyc_verified(user_id) for each item.
PAYOUT_KYC_CHECK_ENABLED = _env_bool("PAYOUT_KYC_CHECK_ENABLED", default=True)

# api.fraud_detection — score each payout before creating the PayoutItem.
# When True: _create_single_payout_item() calls get_payout_risk_score().
PAYOUT_FRAUD_CHECK_ENABLED  = _env_bool("PAYOUT_FRAUD_CHECK_ENABLED",  default=True)
PAYOUT_FRAUD_RISK_THRESHOLD = float(_env("PAYOUT_FRAUD_RISK_THRESHOLD", default="0.75"))

# api.wallet — check platform wallet balance before dispatching a batch.
# When True: _setup_batch_for_processing() calls get_payout_wallet_balance().
PAYOUT_WALLET_CHECK_ENABLED = _env_bool("PAYOUT_WALLET_CHECK_ENABLED", default=True)

# api.audit_logs — write all payout events to the central audit trail.
# When True: signal receivers also write to your AuditLog model.
PAYOUT_AUDIT_LOG_ENABLED = _env_bool("PAYOUT_AUDIT_LOG_ENABLED", default=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. CACHE
#    api.cache manages your caching layer. payout_queue uses Django's default
#    cache framework (django.core.cache.cache). No change needed unless you
#    want payout stats on a dedicated cache backend.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PAYOUT_STATS_CACHE_TTL = int(_env("PAYOUT_STATS_CACHE_TTL", default="300"))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 8. LOGGING
#    Usage: LOGGING["loggers"].update(PAYOUT_LOGGING_ENTRIES)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PAYOUT_LOGGING_ENTRIES = {
    "payout_queue": {
        "handlers":  ["console"],
        "level":     _env("PAYOUT_LOG_LEVEL", default="INFO"),
        "propagate": False,
    },
    "payout_queue.processors": {
        "handlers":  ["console"],
        "level":     _env("PAYOUT_PROCESSOR_LOG_LEVEL", default="WARNING"),
        "propagate": True,
    },
    "payout_queue.models": {
        "handlers":  ["console"],
        "level":     "CRITICAL",
        "propagate": True,
    },
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 9. CROSS-APP INTEGRATION CODE
#    Copy each stub into the indicated file and implement.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ─────────────────────────────────────────────────────────────────────────────
# A. api/kyc/services.py — add this function
# Called by: api/payout_queue/services.py → add_payout_items()
# ─────────────────────────────────────────────────────────────────────────────
#
# def is_user_kyc_verified(user_id) -> bool:
#     """Returns True only if user has passed full KYC verification."""
#     from api.kyc.models import KYCProfile
#     try:
#         profile = KYCProfile.objects.get(user_id=user_id)
#         return profile.status == "VERIFIED" and not profile.is_expired
#     except KYCProfile.DoesNotExist:
#         return False
#
# ─────────────────────────────────────────────────────────────────────────────
# B. api/fraud_detection/services.py — add this function
# Called by: api/payout_queue/services.py → _create_single_payout_item()
# ─────────────────────────────────────────────────────────────────────────────
#
# from decimal import Decimal
# def get_payout_risk_score(user_id, amount: Decimal, account_number: str) -> float:
#     """
#     Returns a risk score between 0.0 (no risk) and 1.0 (high risk).
#     payout_queue blocks if score > PAYOUT_FRAUD_RISK_THRESHOLD (default 0.75).
#     """
#     # Plug in your existing fraud detection logic here.
#     # Examples: velocity checks, device fingerprint, account history, etc.
#     from api.fraud_detection.models import RiskProfile
#     try:
#         profile = RiskProfile.objects.get(user_id=user_id)
#         return profile.calculate_payout_risk(amount=amount, account=account_number)
#     except RiskProfile.DoesNotExist:
#         return 0.0
#
# ─────────────────────────────────────────────────────────────────────────────
# C. api/wallet/services.py — add this function
# Called by: api/payout_queue/services.py → _setup_batch_for_processing()
# ─────────────────────────────────────────────────────────────────────────────
#
# from decimal import Decimal
# def get_payout_wallet_balance(tenant_id) -> Decimal:
#     """
#     Returns current available balance of the tenant's payout wallet.
#     Raises WalletNotFoundError if no payout wallet exists for this tenant.
#     """
#     from api.wallet.models import WalletAccount
#     account = WalletAccount.objects.get(
#         tenant_id=tenant_id,
#         account_type="PAYOUT",
#         is_active=True,
#     )
#     return account.available_balance
#
# def deduct_payout_wallet(tenant_id, amount: Decimal, reference: str) -> None:
#     """
#     Reserve 'amount' from the payout wallet before batch processing.
#     Call this in _setup_batch_for_processing() after acquire_lock().
#     Raises InsufficientFundsError if balance < amount.
#     """
#     from api.wallet.models import WalletAccount, WalletTransaction
#     from django.db import transaction
#     with transaction.atomic():
#         account = WalletAccount.objects.select_for_update().get(
#             tenant_id=tenant_id, account_type="PAYOUT", is_active=True
#         )
#         if account.available_balance < amount:
#             from api.payout_queue.exceptions import InsufficientFundsError
#             raise InsufficientFundsError(
#                 f"Payout wallet balance {account.available_balance} < "
#                 f"batch total {amount}."
#             )
#         account.available_balance -= amount
#         account.save(update_fields=["available_balance", "updated_at"])
#         WalletTransaction.objects.create(
#             account=account,
#             amount=-amount,
#             transaction_type="PAYOUT_RESERVE",
#             reference=reference,
#         )
#
# ─────────────────────────────────────────────────────────────────────────────
# D. api/audit_logs/services.py — add this function
# Called by: api/payout_queue/receivers.py (all signal receivers)
# ─────────────────────────────────────────────────────────────────────────────
#
# def log_payout_event(event_type: str, actor_id, payload: dict) -> None:
#     """
#     Write a payout lifecycle event to the central audit trail.
#     event_type examples: BATCH_COMPLETED, BATCH_FAILED, ITEM_SUCCESS,
#                          ITEM_PERMANENTLY_FAILED, PRIORITY_ASSIGNED
#     """
#     from api.audit_logs.models import AuditLog
#     try:
#         AuditLog.objects.create(
#             event_type=f"PAYOUT_{event_type.upper()}",
#             actor_id=actor_id,
#             module="payout_queue",
#             payload=payload,
#             severity="INFO" if "COMPLETE" in event_type else "WARNING",
#         )
#     except Exception as exc:
#         import logging
#         logging.getLogger("payout_queue").error(
#             "audit_logs write failed: %s", exc
#         )
#
# ─────────────────────────────────────────────────────────────────────────────
# E. Add these calls to api/payout_queue/services.py (3 locations)
# ─────────────────────────────────────────────────────────────────────────────
#
# ① In add_payout_items() — before the items loop:
#
#     from django.conf import settings as _s
#     if getattr(_s, "PAYOUT_KYC_CHECK_ENABLED", False):
#         from api.kyc.services import is_user_kyc_verified
#         for item in items:
#             uid = item.get("user_id")
#             if uid and not is_user_kyc_verified(uid):
#                 raise PayoutQueueError(
#                     f"User pk={uid} has not completed KYC verification."
#                 )
#
# ② In _create_single_payout_item() — after account validation:
#
#     from django.conf import settings as _s
#     if getattr(_s, "PAYOUT_FRAUD_CHECK_ENABLED", False):
#         from api.fraud_detection.services import get_payout_risk_score
#         score = get_payout_risk_score(user_id, gross_amount, account_number)
#         threshold = getattr(_s, "PAYOUT_FRAUD_RISK_THRESHOLD", 0.75)
#         if score > threshold:
#             raise PayoutQueueError(
#                 f"Payout blocked: fraud risk score {score:.2f} exceeds "
#                 f"threshold {threshold} for user={user_id}."
#             )
#
# ③ In _setup_batch_for_processing() — after acquire_lock():
#
#     from django.conf import settings as _s
#     if getattr(_s, "PAYOUT_WALLET_CHECK_ENABLED", False) and batch.tenant_id:
#         from api.wallet.services import deduct_payout_wallet
#         deduct_payout_wallet(
#             tenant_id=batch.tenant_id,
#             amount=batch.total_amount,
#             reference=str(batch.id),
#         )
#
# ─────────────────────────────────────────────────────────────────────────────
# F. Add audit log calls to api/payout_queue/receivers.py
# ─────────────────────────────────────────────────────────────────────────────
#
# In on_payout_batch_completed():
#     from django.conf import settings as _s
#     if getattr(_s, "PAYOUT_AUDIT_LOG_ENABLED", False):
#         from api.audit_logs.services import log_payout_event
#         log_payout_event("BATCH_COMPLETED", batch.created_by_id, _batch_payload(batch))
#
# In on_payout_batch_failed():
#     if getattr(_s, "PAYOUT_AUDIT_LOG_ENABLED", False):
#         from api.audit_logs.services import log_payout_event
#         log_payout_event("BATCH_FAILED", batch.created_by_id, _batch_payload(batch))
#
# In on_payout_item_permanently_failed():
#     if getattr(settings, "PAYOUT_AUDIT_LOG_ENABLED", False):
#         from api.audit_logs.services import log_payout_event
#         log_payout_event("ITEM_FAILED", item.user_id, {
#             "item_id": str(item.id), "batch_id": str(item.batch_id),
#             "error_code": item.error_code, "retry_count": item.retry_count,
#         })

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 10. COPY-PASTE BLOCK FOR settings/base.py
#
#  Add this entire section at the bottom of your settings/base.py.
#  Lines with # are optional but recommended for production.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_SETTINGS_BASE_PY_BLOCK = """
# ─────────────────────────────────────────────────────────────────────────────
# api.payout_queue — add this block to settings/base.py
# ─────────────────────────────────────────────────────────────────────────────

from api.payout_queue.payout_queue_settings import (
    PAYMENT_GATEWAY_CONFIGS,
    PAYOUT_THROTTLE_RATES,
    PAYOUT_WEBHOOK_SECRET,
    PAYOUT_WEBHOOK_URLS,
    PAYOUT_WEBHOOK_TIMEOUT_SECONDS,
    PAYOUT_NOTIFICATION_TASK,
    PAYOUT_KYC_CHECK_ENABLED,
    PAYOUT_FRAUD_CHECK_ENABLED,
    PAYOUT_FRAUD_RISK_THRESHOLD,
    PAYOUT_WALLET_CHECK_ENABLED,
    PAYOUT_AUDIT_LOG_ENABLED,
    PAYOUT_STATS_CACHE_TTL,
    PAYOUT_CELERY_BEAT_ENTRIES,
    PAYOUT_LOGGING_ENTRIES,
)

# Merge payout tasks into your existing beat schedule
CELERY_BEAT_SCHEDULE.update(PAYOUT_CELERY_BEAT_ENTRIES)

# Merge payout loggers into your existing LOGGING config
LOGGING["loggers"].update(PAYOUT_LOGGING_ENTRIES)

# Add payout throttle rates to DRF (payout_ prefix avoids collision)
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({
    "payout_burst":     PAYOUT_THROTTLE_RATES["burst"],
    "payout_sustained": PAYOUT_THROTTLE_RATES["sustained"],
    "payout_process":   PAYOUT_THROTTLE_RATES["process"],
})
"""
