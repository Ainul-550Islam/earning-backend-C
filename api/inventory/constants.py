from decimal import Decimal

# ── Stock Thresholds ──────────────────────────────────────────────────────────
DEFAULT_LOW_STOCK_THRESHOLD = 10
DEFAULT_CRITICAL_STOCK_THRESHOLD = 3
STOCK_RESERVATION_TTL_SECONDS = 600          # 10 min hold during checkout

# ── Code / Voucher ────────────────────────────────────────────────────────────
REDEMPTION_CODE_LENGTH = 16
REDEMPTION_CODE_CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I/O/0/1
MAX_CODES_PER_BATCH_IMPORT = 10_000
CODE_EXPIRY_WARNING_DAYS = 7                  # warn user X days before expiry

# ── Point Values ──────────────────────────────────────────────────────────────
POINTS_TO_CURRENCY_RATE = Decimal("0.01")    # 1 point = $0.01

# ── Delivery ──────────────────────────────────────────────────────────────────
MAX_DELIVERY_RETRY_ATTEMPTS = 3
DELIVERY_RETRY_DELAY_SECONDS = [60, 300, 900]   # 1m, 5m, 15m back-off
DELIVERY_TIMEOUT_SECONDS = 30

# ── Cache ─────────────────────────────────────────────────────────────────────
CACHE_KEY_ITEM_STOCK = "inventory:item:{item_id}:stock"
CACHE_KEY_USER_INVENTORY = "inventory:user:{user_id}:items"
CACHE_TIMEOUT_STOCK = 60                     # 1 minute (hot path)
CACHE_TIMEOUT_USER_INV = 60 * 2             # 2 minutes

# ── Pagination ────────────────────────────────────────────────────────────────
ITEM_PAGE_SIZE = 20
INVENTORY_PAGE_SIZE = 25
CODE_PAGE_SIZE = 50

# ── Task Names ────────────────────────────────────────────────────────────────
TASK_CHECK_LOW_STOCK = "inventory.tasks.check_low_stock_alerts"
TASK_EXPIRE_CODES = "inventory.tasks.expire_redemption_codes"
TASK_RETRY_FAILED_DELIVERIES = "inventory.tasks.retry_failed_deliveries"
TASK_SYNC_STOCK_COUNTS = "inventory.tasks.sync_stock_counts"

# ── Email Templates ───────────────────────────────────────────────────────────
EMAIL_ITEM_DELIVERED = "inventory/emails/item_delivered.html"
EMAIL_ITEM_DELIVERY_FAILED = "inventory/emails/delivery_failed.html"
EMAIL_CODE_EXPIRING_SOON = "inventory/emails/code_expiring.html"
EMAIL_LOW_STOCK_ALERT = "inventory/emails/low_stock_alert.html"

# ── Inventory Limits ──────────────────────────────────────────────────────────
MAX_QUANTITY_PER_USER_PER_ITEM = 5           # prevent hoarding
UNLIMITED_STOCK = -1                          # sentinel value
MAX_BULK_REDEEM = 100                         # max items in one batch redemption

# ── Audit ─────────────────────────────────────────────────────────────────────
STOCK_AUDIT_LOG_RETENTION_DAYS = 365
