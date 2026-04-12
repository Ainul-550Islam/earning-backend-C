"""
marketplace/constants.py — Marketplace Constants
"""

# ── Commission ──────────────────────────────
DEFAULT_COMMISSION_RATE = 10.0          # %
MIN_COMMISSION_RATE = 2.0
MAX_COMMISSION_RATE = 40.0

# ── Escrow ───────────────────────────────────
ESCROW_RELEASE_DAYS = 7                 # Days after delivery to auto-release
ESCROW_DISPUTE_WINDOW_DAYS = 14

# ── Order ────────────────────────────────────
ORDER_CONFIRMATION_TIMEOUT_HOURS = 48   # Auto-cancel if seller doesn't confirm
MAX_ORDER_ITEMS = 50

# ── Cart ─────────────────────────────────────
CART_EXPIRY_DAYS = 30
MAX_CART_ITEMS = 100
ABANDONED_CART_HOURS = 24

# ── Review ───────────────────────────────────
MIN_RATING = 1
MAX_RATING = 5
REVIEW_WINDOW_DAYS = 30                 # Days after delivery to leave review

# ── Coupon ───────────────────────────────────
MAX_COUPON_USES_DEFAULT = 1000
MAX_COUPON_DISCOUNT_PERCENT = 90.0

# ── Inventory ────────────────────────────────
LOW_STOCK_THRESHOLD = 10

# ── Pagination ───────────────────────────────
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# ── Cache TTL (seconds) ──────────────────────
CACHE_PRODUCT_TTL = 300                 # 5 min
CACHE_CATEGORY_TTL = 600               # 10 min
CACHE_SELLER_TTL = 300

# ── Shipping ─────────────────────────────────
FREE_SHIPPING_THRESHOLD = 500.00        # BDT
DEFAULT_SHIPPING_RATE = 60.00           # BDT

# ── KYC ──────────────────────────────────────
KYC_DOCUMENTS_REQUIRED = ["nid_front", "nid_back", "selfie"]

# ── Payout ───────────────────────────────────
MIN_PAYOUT_AMOUNT = 100.00              # BDT
PAYOUT_PROCESSING_DAYS = 3

# ── Tax ──────────────────────────────────────
DEFAULT_VAT_RATE = 0.15                 # 15%
