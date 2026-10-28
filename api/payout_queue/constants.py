"""
payout_queue/constants.py  ← FIXED v2

CHANGE: Phone regex consolidation (Point 5 — technical debt).
  Before: BKASH_PHONE_REGEX = NAGAD_PHONE_REGEX = ROCKET_PHONE_REGEX = "^01[3-9]\\d{8}$"
           — three names, one value, no indication they share the same rule.
  After:  BD_MOBILE_REGEX is the canonical constant.
           Gateway-specific names are explicit aliases that remain importable
           from their existing call sites without any changes in processors/*.
           If a gateway ever moves to a different format, change only its alias.
"""

from decimal import Decimal

# ── Payout amount limits (BDT) ────────────────────────────────────────────────
MIN_PAYOUT_AMOUNT: Decimal = Decimal("10.00")
MAX_PAYOUT_AMOUNT: Decimal = Decimal("500000.00")
MAX_SINGLE_GATEWAY_PAYOUT: Decimal = Decimal("25000.00")   # per-transaction gateway cap

# ── Fee defaults ──────────────────────────────────────────────────────────────
DEFAULT_BKASH_FEE_PERCENT: Decimal = Decimal("1.85")
DEFAULT_NAGAD_FEE_PERCENT: Decimal = Decimal("1.50")
DEFAULT_ROCKET_FEE_PERCENT: Decimal = Decimal("1.75")
DEFAULT_BANK_FLAT_FEE: Decimal = Decimal("25.00")
MAX_FEE_AMOUNT: Decimal = Decimal("500.00")

# ── Batch limits ──────────────────────────────────────────────────────────────
MAX_BATCH_SIZE: int = 500                  # items per batch
MAX_CONCURRENT_BATCHES: int = 3            # PROCESSING batches at a time
DEFAULT_BATCH_SIZE: int = 100              # default items when creating batch via API
# (MAX_BATCH_SIZE is the hard ceiling; DEFAULT_BATCH_SIZE is the soft default)
BATCH_LOCK_TIMEOUT_SECONDS: int = 3600    # 1 hour

# ── Retry configuration ───────────────────────────────────────────────────────
MAX_RETRY_ATTEMPTS: int = 3
RETRY_BACKOFF_SECONDS: list[int] = [60, 300, 900]   # 1 min, 5 min, 15 min

# ── Processing timeouts (seconds) ─────────────────────────────────────────────
GATEWAY_TIMEOUT_SECONDS: int = 30
BATCH_PROCESSING_TIMEOUT: int = 7200   # Celery task time_limit for process_batch_async (2 hours)

# ── SLA thresholds ────────────────────────────────────────────────────────────
PAYOUT_SLA_HOURS: int = 24             # SLA breach after 24 h
URGENT_SLA_HOURS: int = 2              # SLA breach for URGENT/CRITICAL items after 2 h

# ── Phone number validation ───────────────────────────────────────────────────
# FIX v2: BD_MOBILE_REGEX is the canonical rule for Bangladesh mobile numbers.
# All three gateway-specific names are aliases pointing to the same pattern.
# Existing import sites (processors/bkash.py etc.) require zero changes.
# To override a gateway's regex independently, assign a new string to its alias.
BD_MOBILE_REGEX: str = r"^01[3-9]\d{8}$"   # Bangladesh: 01X-XXXXXXXX (X in 3-9)
BKASH_PHONE_REGEX:  str = BD_MOBILE_REGEX   # alias — bKash uses same format
NAGAD_PHONE_REGEX:  str = BD_MOBILE_REGEX   # alias — Nagad uses same format
ROCKET_PHONE_REGEX: str = BD_MOBILE_REGEX   # alias — Rocket (DBBL) uses same format

# ── Field lengths ─────────────────────────────────────────────────────────────
MAX_ACCOUNT_NUMBER_LENGTH: int = 50
MAX_REFERENCE_LENGTH: int = 255
MAX_NOTE_LENGTH: int = 2000
MAX_ERROR_MESSAGE_LENGTH: int = 4096
MAX_BATCH_NAME_LENGTH: int = 255

# ── Pagination ────────────────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100

# ── Cache TTL ─────────────────────────────────────────────────────────────────
PAYOUT_STATS_CACHE_TTL: int = 300   # 5 minutes
