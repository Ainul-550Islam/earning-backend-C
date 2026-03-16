import datetime

# ── Signature ─────────────────────────────────────────────────────────────────
SIGNATURE_TOLERANCE_SECONDS = 300            # 5 min replay-attack window
SIGNATURE_HEADER = "X-Postback-Signature"
TIMESTAMP_HEADER = "X-Postback-Timestamp"
NONCE_HEADER = "X-Postback-Nonce"
MAX_NONCE_LENGTH = 64

# ── IP Filtering ──────────────────────────────────────────────────────────────
MAX_IP_WHITELIST_ENTRIES = 50
PRIVATE_NETWORK_RANGES = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "::1/128",
]

# ── Deduplication ─────────────────────────────────────────────────────────────
DEDUP_WINDOW_MAP = {
    "1h": datetime.timedelta(hours=1),
    "1d": datetime.timedelta(days=1),
    "7d": datetime.timedelta(days=7),
    "30d": datetime.timedelta(days=30),
    "forever": None,
}
DEDUP_CACHE_PREFIX = "postback:dedup:{network_id}:{lead_id}"
DEDUP_CACHE_TTL = 60 * 60 * 24 * 30   # 30 days in cache

# ── Rate Limiting ─────────────────────────────────────────────────────────────
POSTBACK_RATE_LIMIT_PER_NETWORK = "1000/minute"
POSTBACK_RATE_LIMIT_BURST = "50/second"
POSTBACK_RATE_LIMIT_SUSPICIOUS = "5/minute"   # for suspicious IPs

# ── Retry ─────────────────────────────────────────────────────────────────────
MAX_POSTBACK_PROCESSING_RETRIES = 3
POSTBACK_RETRY_COUNTDOWN_SECONDS = [30, 120, 600]   # 30s, 2m, 10m back-off

# ── Log Retention ────────────────────────────────────────────────────────────
POSTBACK_LOG_RETENTION_DAYS = 90
DUPLICATE_LOG_RETENTION_DAYS = 30

# ── Reward ────────────────────────────────────────────────────────────────────
MAX_PAYOUT_PER_POSTBACK = 10_000         # Safety cap in points
DEFAULT_REWARD_DELAY_SECONDS = 0         # 0 = immediate; >0 = delayed

# ── Cache ─────────────────────────────────────────────────────────────────────
CACHE_KEY_NETWORK_CONFIG = "postback:network:{network_id}:config"
CACHE_KEY_NONCE_USED = "postback:nonce:{nonce}"
CACHE_TIMEOUT_NETWORK = 60 * 10
CACHE_TIMEOUT_NONCE = SIGNATURE_TOLERANCE_SECONDS + 60

# ── Field Names (network-specific mapping defaults) ───────────────────────────
STANDARD_FIELD_LEAD_ID = "lead_id"
STANDARD_FIELD_OFFER_ID = "offer_id"
STANDARD_FIELD_USER_ID = "user_id"
STANDARD_FIELD_PAYOUT = "payout"
STANDARD_FIELD_CURRENCY = "currency"
STANDARD_FIELD_TIMESTAMP = "timestamp"
STANDARD_FIELD_TRANSACTION_ID = "transaction_id"

# ── Postback task names ───────────────────────────────────────────────────────
TASK_PROCESS_POSTBACK = "postback.tasks.process_postback"
TASK_CLEANUP_OLD_LOGS = "postback.tasks.cleanup_old_logs"
TASK_RETRY_FAILED = "postback.tasks.retry_failed_postbacks"
