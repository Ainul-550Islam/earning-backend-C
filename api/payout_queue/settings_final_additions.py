"""
payout_queue/settings_final_additions.py  ← v8 FINAL PRODUCTION SETTINGS

INSTRUCTIONS:
    Copy this entire file's contents into your settings/base.py
    (or settings/production.py for production-only settings).

    Then add all UPPER_CASE values to your .env file.
    Run: python manage.py check --deploy
    to verify Django's production checklist passes.

REQUIRED .env entries:
    SENTRY_DSN=https://xxx@oXXX.ingest.sentry.io/XXX
    PAYOUT_ENCRYPTION_KEY=<generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
    BKASH_APP_KEY=
    BKASH_APP_SECRET=
    BKASH_USERNAME=
    BKASH_PASSWORD=
    BKASH_BASE_URL=https://tokenized.pay.bka.sh/v1.2.0-beta
    NAGAD_MERCHANT_ID=
    NAGAD_MERCHANT_NUMBER=
    NAGAD_API_KEY=
    NAGAD_BASE_URL=https://api.mynagad.com
    ROCKET_API_KEY=
    ROCKET_MERCHANT_NUMBER=
    ROCKET_BASE_URL=https://api.rocket.com.bd
    BANK_API_KEY=
    BANK_BASE_URL=
    PAYOUT_WEBHOOK_SECRET=<random 32-char string>
    CELERY_BROKER_URL=redis://localhost:6379/0
    REDIS_URL=redis://localhost:6379/0
"""

import os
from celery.schedules import crontab

# =============================================================================
# 1. SENTRY ERROR TRACKING
# =============================================================================
# Populated from .env. Empty string = Sentry disabled (safe for dev/test).
SENTRY_DSN: str                 = os.environ.get("SENTRY_DSN", "")
SENTRY_ENVIRONMENT: str         = os.environ.get("DJANGO_ENV", "production")
SENTRY_TRACES_RATE: float       = float(os.environ.get("SENTRY_TRACES_RATE", "0.05"))
SENTRY_PROFILES_RATE: float     = float(os.environ.get("SENTRY_PROFILES_RATE", "0.0"))
SENTRY_SEND_PII: bool           = False   # GDPR: never send PII to Sentry
# SENTRY_RELEASE is auto-detected from git HEAD in apps.py.
# Override: SENTRY_RELEASE = "v1.2.3"

# =============================================================================
# 2. PAYOUT QUEUE — FEATURE FLAGS
# =============================================================================
# These can be toggled per environment via .env without code changes.

# KYC gate: BFIU Bangladesh compliance. Set False only in local dev / tests.
PAYOUT_KYC_CHECK_ENABLED: bool      = os.environ.get("PAYOUT_KYC_CHECK_ENABLED", "True").lower() != "false"

# Fraud gate: block payouts if risk score > threshold.
PAYOUT_FRAUD_CHECK_ENABLED: bool    = os.environ.get("PAYOUT_FRAUD_CHECK_ENABLED", "True").lower() != "false"
PAYOUT_FRAUD_RISK_THRESHOLD: float  = float(os.environ.get("PAYOUT_FRAUD_RISK_THRESHOLD", "0.75"))

# Wallet balance gate: deduct from platform wallet before processing.
PAYOUT_WALLET_CHECK_ENABLED: bool   = os.environ.get("PAYOUT_WALLET_CHECK_ENABLED", "True").lower() != "false"

# Audit trail: write to central api.audit_logs on batch/item events.
PAYOUT_AUDIT_LOG_ENABLED: bool      = os.environ.get("PAYOUT_AUDIT_LOG_ENABLED", "True").lower() != "false"

# =============================================================================
# 3. PAYOUT QUEUE — OPERATIONAL LIMITS
# =============================================================================
# These are module-level constants (in constants.py) but documented here
# so ops can tune them without searching the codebase.

# Maximum items per batch (prevents memory exhaustion on large batches)
# DEFAULT: 1000 — configured in constants.py
# PAYOUT_MAX_BATCH_SIZE = 1000

# Maximum concurrent PROCESSING batches (prevents gateway rate-limit floods)
# DEFAULT: 3 — configured in constants.py
# PAYOUT_MAX_CONCURRENT_BATCHES = 3

# Lock timeout: batches locked longer than this are "stuck" and released by beat
# DEFAULT: 3600 seconds (1 hour) — configured in constants.py
# PAYOUT_BATCH_LOCK_TIMEOUT_SECONDS = 3600

# =============================================================================
# 4. FIELD-LEVEL ENCRYPTION  (v8)
# =============================================================================
# Required for encrypting PayoutItem.account_number at rest.
# CRITICAL: Generate this key BEFORE running migration 0007.
# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# WARNING: losing this key means all stored account numbers become unreadable.
# Store in a secrets manager (AWS Secrets Manager, HashiCorp Vault) in production.
PAYOUT_ENCRYPTION_KEY: str = os.environ.get("PAYOUT_ENCRYPTION_KEY", "")
# If empty: account_number stored as plaintext (dev/test only).
# Health check at GET /payout-queue/health/ will report encryption as "degraded"
# if this key is not set.

# =============================================================================
# 5. PAYMENT GATEWAY CREDENTIALS
# =============================================================================
# Never hardcode credentials. All values come from .env / secrets manager.

PAYMENT_GATEWAY_CONFIGS: dict = {
    "BKASH": {
        "app_key":    os.environ.get("BKASH_APP_KEY",    ""),
        "app_secret": os.environ.get("BKASH_APP_SECRET", ""),
        "username":   os.environ.get("BKASH_USERNAME",   ""),
        "password":   os.environ.get("BKASH_PASSWORD",   ""),
        "base_url":   os.environ.get("BKASH_BASE_URL",   "https://tokenized.sandbox.bka.sh/v1.2.0-beta"),
    },
    "NAGAD": {
        "merchant_id":     os.environ.get("NAGAD_MERCHANT_ID",     ""),
        "merchant_number": os.environ.get("NAGAD_MERCHANT_NUMBER", ""),
        "api_key":         os.environ.get("NAGAD_API_KEY",         ""),
        "base_url":        os.environ.get("NAGAD_BASE_URL",        "https://api.mynagad.com"),
    },
    "ROCKET": {
        "api_key":          os.environ.get("ROCKET_API_KEY",          ""),
        "merchant_number":  os.environ.get("ROCKET_MERCHANT_NUMBER",  ""),
        "base_url":         os.environ.get("ROCKET_BASE_URL",         "https://api.rocket.com.bd"),
    },
    "BANK": {
        "api_key":  os.environ.get("BANK_API_KEY",  ""),
        "base_url": os.environ.get("BANK_BASE_URL", ""),
    },
    "MANUAL": {},   # Manual payouts — no credentials needed
}

# =============================================================================
# 6. WEBHOOK DELIVERY
# =============================================================================
# URLs to POST signed payout events to (merchant webhooks, monitoring systems).
# Multiple URLs supported — each event is delivered to all.
# Leave empty to disable webhook delivery.
PAYOUT_WEBHOOK_URLS: list[str] = [
    url.strip()
    for url in os.environ.get("PAYOUT_WEBHOOK_URLS", "").split(",")
    if url.strip()
]

# Secret for HMAC-SHA256 webhook signature (X-Payout-Signature header).
# Generate: python -c "import secrets; print(secrets.token_urlsafe(32))"
PAYOUT_WEBHOOK_SECRET: str         = os.environ.get("PAYOUT_WEBHOOK_SECRET", "")
PAYOUT_WEBHOOK_TIMEOUT_SECONDS: int = int(os.environ.get("PAYOUT_WEBHOOK_TIMEOUT_SECONDS", "10"))

# Optional notification task (Celery task path) for batch completion alerts.
# Task signature: def my_task(user_id, event, data): ...
PAYOUT_NOTIFICATION_TASK: str = os.environ.get("PAYOUT_NOTIFICATION_TASK", "")

# =============================================================================
# 7. CELERY + REDIS
# =============================================================================
CELERY_BROKER_URL:          str = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND:      str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_TASK_SERIALIZER:     str = "json"
CELERY_RESULT_SERIALIZER:   str = "json"
CELERY_ACCEPT_CONTENT:      list = ["json"]
CELERY_TIMEZONE:            str = "Asia/Dhaka"
CELERY_TASK_ACKS_LATE:      bool = True
CELERY_WORKER_PREFETCH_MULTIPLIER: int = 1

CELERY_BEAT_SCHEDULE: dict = {
    # Process PENDING batches that are due — every 60 seconds
    "payout-process-due-batches": {
        "task":     "payout_queue.process_due_batches",
        "schedule": 60.0,
    },
    # Retry RETRYING items whose next_retry_at is past — every 2 minutes
    "payout-retry-due-items": {
        "task":     "payout_queue.retry_due_items",
        "schedule": 120.0,
    },
    # Deactivate expired WithdrawalPriority records — every 5 minutes
    "payout-expire-priorities": {
        "task":     "payout_queue.expire_withdrawal_priorities",
        "schedule": 300.0,
    },
    # Release stuck advisory locks (worker crash recovery) — every 15 minutes
    "payout-release-stale-locks": {
        "task":     "payout_queue.release_stale_locks",
        "schedule": 900.0,
    },
    # v8: Daily reconciliation of completed batches against live gateways — 2 AM
    "payout-reconcile-recent": {
        "task":     "payout_queue.reconcile_recent_batches",
        "schedule": crontab(hour=2, minute=0),
    },
}

# =============================================================================
# 8. DJANGO CACHES (required for batch statistics caching)
# =============================================================================
CACHES: dict = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "payout_queue",
        "TIMEOUT": 300,
    }
}

# =============================================================================
# 9. LOGGING (structured, production-ready)
# =============================================================================
LOGGING: dict = {
    "version":                  1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()":      "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format":  "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style":  "{",
        },
    },
    "handlers": {
        "console": {
            "class":     "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "api.payout_queue": {
            "handlers": ["console"],
            "level":    "INFO",
            "propagate": True,
        },
    },
    "root": {
        "handlers": ["console"],
        "level":    "WARNING",
    },
}

# =============================================================================
# 10. INSTALLED_APPS additions
# =============================================================================
# Ensure this is in your INSTALLED_APPS:
#   "api.payout_queue.apps.PayoutQueueConfig",
# Or simply: "api.payout_queue",
#
# Required third-party apps (add if not already present):
#   "django_filters",      — for DjangoFilterBackend in viewsets
#   "rest_framework",      — for DRF
#
# Optional but strongly recommended:
#   "django_redis",        — for Redis cache backend

# =============================================================================
# 11. MAIN URLS
# =============================================================================
# In your project's urls.py, add:
#   path("api/payout-queue/", include("api.payout_queue.urls")),
#
# Health check will be accessible at:
#   GET /api/payout-queue/health/
