# api/wallet/constants.py
from decimal import Decimal
from django.conf import settings

# ── Withdrawal limits ─────────────────────────────────────────
MIN_WITHDRAWAL         = Decimal(str(getattr(settings, "WALLET_MIN_WITHDRAWAL", "50.00")))
MAX_WITHDRAWAL         = Decimal(str(getattr(settings, "WALLET_MAX_WITHDRAWAL", "100000.00")))
MAX_DAILY_WITHDRAWAL   = Decimal(str(getattr(settings, "WALLET_MAX_DAILY_WITHDRAWAL", "50000.00")))
MAX_MONTHLY_WITHDRAWAL = Decimal(str(getattr(settings, "WALLET_MAX_MONTHLY_WITHDRAWAL", "500000.00")))

# ── Fees ──────────────────────────────────────────────────────
DEFAULT_FEE_PERCENT    = Decimal("2.00")
CRYPTO_FEE_PERCENT     = Decimal("1.00")
INSTANT_FEE_PERCENT    = Decimal("1.50")
MIN_FEE_BDT            = Decimal("5.00")

# ── Gateway minimums (BDT) ────────────────────────────────────
GATEWAY_MIN = {
    "bkash":      Decimal("50"),
    "nagad":      Decimal("50"),
    "rocket":     Decimal("50"),
    "upay":       Decimal("50"),
    "bank":       Decimal("500"),
    "card":       Decimal("200"),
    "usdt_trc20": Decimal("10"),
    "usdt_erc20": Decimal("10"),
    "paypal":     Decimal("100"),
    "payoneer":   Decimal("100"),
    "wise":       Decimal("100"),
}

# ── CPAlead-style tier earn bonuses ───────────────────────────
TIER_EARN_BONUS = {
    "FREE":     Decimal("1.00"),
    "BRONZE":   Decimal("1.05"),
    "SILVER":   Decimal("1.10"),
    "GOLD":     Decimal("1.15"),
    "PLATINUM": Decimal("1.20"),
    "DIAMOND":  Decimal("1.30"),
}

# ── Tier withdrawal fee discounts ─────────────────────────────
TIER_FEE_DISCOUNT = {
    "FREE":     Decimal("1.00"),
    "BRONZE":   Decimal("0.90"),
    "SILVER":   Decimal("0.75"),
    "GOLD":     Decimal("0.50"),
    "PLATINUM": Decimal("0.25"),
    "DIAMOND":  Decimal("0.00"),   # Free for Diamond
}

# ── CPAlead 3-level referral rates ────────────────────────────
REFERRAL_RATES = {
    1: Decimal("0.10"),   # Level 1 → 10%
    2: Decimal("0.05"),   # Level 2 → 5%
    3: Decimal("0.02"),   # Level 3 → 2%
}
REFERRAL_DURATION_MONTHS = 6   # CPAlead: 6-month window

# ── CPAlead streak bonuses (days → BDT bonus) ─────────────────
STREAK_BONUSES = {
    7:  Decimal("10"),
    14: Decimal("25"),
    30: Decimal("100"),
    60: Decimal("250"),
    90: Decimal("500"),
}

# ── Daily earning cap defaults ────────────────────────────────
DEFAULT_DAILY_EARN_CAP = Decimal("10000.00")

# ── Idempotency ───────────────────────────────────────────────
IDEMPOTENCY_TTL = 86400   # 24 hours in seconds

# ── CPAlead publisher payout hold ─────────────────────────────
NEW_PUBLISHER_HOLD_DAYS = 30    # New publisher: funds held 30 days

# ── Fraud ─────────────────────────────────────────────────────
FRAUD_BLOCK_SCORE = 85          # Auto-block at score >= 85
VELOCITY_MAX_PER_HOUR = 10      # Max transactions per hour before flag

# ── Binance-style security lock ───────────────────────────────
SECURITY_LOCK_HOURS = 24        # Lock withdrawals 24h after security change

# ── Points (CPAlead virtual currency) ─────────────────────────
POINTS_PER_DOLLAR = 1000        # 1000 points = $1

# ── AML thresholds ────────────────────────────────────────────
AML_STRUCTURING_THRESHOLD = Decimal("9999")   # Near reporting threshold
AML_RAPID_MOVEMENT_24H    = Decimal("100000") # 100k in 24h = flag
AML_ROUND_NUMBER_REPEAT   = 3                 # 3+ round numbers in 7 days = flag

# ── KYC withdrawal limits by level (BDT) ─────────────────────
KYC_LIMITS = {
    0: {"daily": Decimal("500"),      "monthly": Decimal("5000")},
    1: {"daily": Decimal("50000"),    "monthly": Decimal("500000")},
    2: {"daily": Decimal("500000"),   "monthly": Decimal("5000000")},
    3: {"daily": Decimal("9999999"),  "monthly": Decimal("99999999")},
}
