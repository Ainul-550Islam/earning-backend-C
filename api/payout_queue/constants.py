"""
Payout Queue Constants — All magic numbers in one place.
"""

from decimal import Decimal

# Payout amount limits (BDT)
MIN_PAYOUT_AMOUNT: Decimal = Decimal("10.00")
MAX_PAYOUT_AMOUNT: Decimal = Decimal("500000.00")
MAX_SINGLE_GATEWAY_PAYOUT: Decimal = Decimal("25000.00")   # per-transaction gateway cap

# Fee defaults
DEFAULT_BKASH_FEE_PERCENT: Decimal = Decimal("1.85")
DEFAULT_NAGAD_FEE_PERCENT: Decimal = Decimal("1.50")
DEFAULT_ROCKET_FEE_PERCENT: Decimal = Decimal("1.75")
DEFAULT_BANK_FLAT_FEE: Decimal = Decimal("25.00")
MAX_FEE_AMOUNT: Decimal = Decimal("500.00")

# Batch limits
MAX_BATCH_SIZE: int = 500                 # items per batch
MAX_CONCURRENT_BATCHES: int = 3           # PROCESSING batches at a time
DEFAULT_BATCH_SIZE: int = 100
BATCH_LOCK_TIMEOUT_SECONDS: int = 3600   # 1 hour

# Retry configuration
MAX_RETRY_ATTEMPTS: int = 3
RETRY_BACKOFF_SECONDS: list[int] = [60, 300, 900]   # 1m, 5m, 15m

# Processing timeouts (seconds)
GATEWAY_TIMEOUT_SECONDS: int = 30
BATCH_PROCESSING_TIMEOUT: int = 7200   # 2 hours

# SLA thresholds
PAYOUT_SLA_HOURS: int = 24             # breach after 24h
URGENT_SLA_HOURS: int = 2

# Phone number validation
BKASH_PHONE_REGEX: str = r"^01[3-9]\d{8}$"
NAGAD_PHONE_REGEX: str = r"^01[3-9]\d{8}$"
ROCKET_PHONE_REGEX: str = r"^01[3-9]\d{8}$"

# Field lengths
MAX_ACCOUNT_NUMBER_LENGTH: int = 50
MAX_REFERENCE_LENGTH: int = 255
MAX_NOTE_LENGTH: int = 2000
MAX_ERROR_MESSAGE_LENGTH: int = 4096
MAX_BATCH_NAME_LENGTH: int = 255

# Pagination
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100

# Cache TTL
PAYOUT_STATS_CACHE_TTL: int = 300   # 5 minutes
