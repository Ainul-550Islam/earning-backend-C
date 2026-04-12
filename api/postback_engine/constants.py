"""
constants.py – All system-wide constants for Postback Engine.
"""
import datetime

# ── App Identity ───────────────────────────────────────────────────────────────
APP_LABEL = "postback_engine"
ENGINE_VERSION = "2.0.0"

# ── Signature / Security ───────────────────────────────────────────────────────
SIGNATURE_TOLERANCE_SECONDS = 300           # 5 min replay-attack window
SIGNATURE_HEADER            = "X-Postback-Signature"
TIMESTAMP_HEADER            = "X-Postback-Timestamp"
NONCE_HEADER                = "X-Postback-Nonce"
MAX_NONCE_LENGTH            = 64
MAX_SIGNATURE_LENGTH        = 256
SECRET_KEY_MIN_LENGTH       = 16

# ── IP Filtering ───────────────────────────────────────────────────────────────
MAX_IP_WHITELIST_ENTRIES = 100
PRIVATE_NETWORK_RANGES = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "::1/128",
    "fc00::/7",
]

# ── Deduplication ─────────────────────────────────────────────────────────────
DEDUP_WINDOW_MAP = {
    "1h":     datetime.timedelta(hours=1),
    "1d":     datetime.timedelta(days=1),
    "7d":     datetime.timedelta(days=7),
    "30d":    datetime.timedelta(days=30),
    "forever": None,
}
DEDUP_CACHE_PREFIX  = "pe:dedup:{network_id}:{lead_id}"
DEDUP_CACHE_TTL     = 60 * 60 * 24 * 30    # 30 days in seconds

# ── Rate Limiting ─────────────────────────────────────────────────────────────
POSTBACK_RATE_LIMIT_DEFAULT     = 1000   # per minute per network
POSTBACK_RATE_LIMIT_BURST       = 50     # per second
POSTBACK_RATE_LIMIT_SUSPICIOUS  = 5      # per minute for suspicious IPs
CLICK_RATE_LIMIT_DEFAULT        = 5000   # per minute per network
CONVERSION_RATE_LIMIT_DEFAULT   = 500    # per minute per network

# ── Retry ─────────────────────────────────────────────────────────────────────
MAX_POSTBACK_RETRIES            = 5
POSTBACK_RETRY_DELAYS           = [30, 120, 300, 900, 3600]  # seconds
MAX_WEBHOOK_RETRIES             = 3
WEBHOOK_RETRY_DELAYS            = [60, 300, 900]

# ── Log Retention ─────────────────────────────────────────────────────────────
POSTBACK_LOG_RETENTION_DAYS     = 90
CLICK_LOG_RETENTION_DAYS        = 180
CONVERSION_LOG_RETENTION_DAYS   = 365
FRAUD_LOG_RETENTION_DAYS        = 730   # 2 years
DUPLICATE_LOG_RETENTION_DAYS    = 90
IMPRESSION_RETENTION_DAYS       = 30

# ── Reward / Payout ───────────────────────────────────────────────────────────
MAX_PAYOUT_PER_POSTBACK         = 100_000    # safety cap in points/cents
MAX_PAYOUT_USD_PER_CONVERSION   = 1000.00    # USD safety cap
DEFAULT_REWARD_DELAY_SECONDS    = 0
REWARD_HOLD_PERIOD_HOURS        = 0          # 0 = immediate

# ── Click Tracking ────────────────────────────────────────────────────────────
CLICK_ID_LENGTH                 = 32
CLICK_EXPIRY_HOURS              = 24
MAX_CLICK_IP_PER_HOUR           = 100
MAX_CLICK_DEVICE_PER_HOUR       = 50

# ── Conversion Tracking ───────────────────────────────────────────────────────
CONVERSION_WINDOW_DAYS          = 30
MAX_CONVERSIONS_PER_OFFER_USER  = 1         # default: 1 conversion per offer per user

# ── Fraud Detection ───────────────────────────────────────────────────────────
FRAUD_SCORE_THRESHOLD_FLAG      = 60        # 0-100 score; >= 60 = flag
FRAUD_SCORE_THRESHOLD_BLOCK     = 80        # >= 80 = auto-block
MAX_CONVERSIONS_SAME_IP_HOUR    = 10
MAX_CONVERSIONS_SAME_DEVICE_DAY = 5
BOT_VELOCITY_THRESHOLD          = 100       # clicks per minute = bot
KNOWN_BOT_USER_AGENTS = [
    "Googlebot", "bingbot", "Slurp", "DuckDuckBot", "Baiduspider",
    "YandexBot", "facebookexternalhit", "Twitterbot", "AhrefsBot",
    "MJ12bot", "SemrushBot", "rogerbot", "Screaming Frog",
]

# ── Cache Keys ────────────────────────────────────────────────────────────────
CACHE_KEY_NETWORK_CONFIG    = "pe:network:{network_id}:config"
CACHE_KEY_NONCE_USED        = "pe:nonce:{nonce}"
CACHE_KEY_CLICK             = "pe:click:{click_id}"
CACHE_KEY_DEDUP             = "pe:dedup:{network_id}:{lead_id}"
CACHE_KEY_RATE_LIMIT        = "pe:rate:{network_id}"
CACHE_KEY_IP_BLACKLIST      = "pe:blacklist:ip:{ip}"
CACHE_KEY_HOURLY_STAT       = "pe:stat:hourly:{network_id}:{date}:{hour}"

CACHE_TTL_NETWORK_CONFIG    = 600       # 10 minutes
CACHE_TTL_NONCE             = SIGNATURE_TOLERANCE_SECONDS + 60
CACHE_TTL_CLICK             = CLICK_EXPIRY_HOURS * 3600
CACHE_TTL_BLACKLIST         = 3600      # 1 hour
CACHE_TTL_HOURLY_STAT       = 300       # 5 minutes

# ── Standard Field Names ──────────────────────────────────────────────────────
FIELD_LEAD_ID           = "lead_id"
FIELD_CLICK_ID          = "click_id"
FIELD_OFFER_ID          = "offer_id"
FIELD_USER_ID           = "user_id"
FIELD_SUB_ID            = "sub_id"
FIELD_PAYOUT            = "payout"
FIELD_CURRENCY          = "currency"
FIELD_TIMESTAMP         = "timestamp"
FIELD_TRANSACTION_ID    = "transaction_id"
FIELD_STATUS            = "status"
FIELD_GOAL_ID           = "goal_id"
FIELD_GOAL_VALUE        = "goal_value"
FIELD_ADVERTISER_ID     = "advertiser_id"
FIELD_PUBLISHER_ID      = "publisher_id"
FIELD_CAMPAIGN_ID       = "campaign_id"

# ── Task Names ────────────────────────────────────────────────────────────────
TASK_PROCESS_POSTBACK       = "postback_engine.tasks.process_postback"
TASK_PROCESS_CLICK          = "postback_engine.tasks.process_click"
TASK_PROCESS_CONVERSION     = "postback_engine.tasks.process_conversion"
TASK_CLEANUP_OLD_LOGS       = "postback_engine.tasks.cleanup_old_logs"
TASK_RETRY_FAILED           = "postback_engine.tasks.retry_failed_postbacks"
TASK_UPDATE_HOURLY_STATS    = "postback_engine.tasks.update_hourly_stats"
TASK_SEND_WEBHOOK           = "postback_engine.tasks.send_webhook_notification"
TASK_FRAUD_SCAN             = "postback_engine.tasks.run_fraud_scan"
TASK_FLUSH_CLICK_BUFFER     = "postback_engine.tasks.flush_click_buffer"

# ── Network Adapter Mapping ───────────────────────────────────────────────────
# Maps network_key → adapter module path
NETWORK_ADAPTER_MAP = {
    "cpalead":      "postback_engine.network_adapters.cpalead_adapter",
    "adgate":       "postback_engine.network_adapters.adgate_adapter",
    "offertoro":    "postback_engine.network_adapters.offertoro_adapter",
    "adscend":      "postback_engine.network_adapters.adscend_adapter",
    "revenuewall":  "postback_engine.network_adapters.revenuewall_adapter",
    "applovin":     "postback_engine.network_adapters.applovin_adapter",
    "unity":        "postback_engine.network_adapters.unity_ads_adapter",
    "ironsource":   "postback_engine.network_adapters.ironsource_adapter",
    "admob":        "postback_engine.network_adapters.admob_adapter",
    "facebook":     "postback_engine.network_adapters.facebook_adapter",
    "google":       "postback_engine.network_adapters.google_adapter",
    "tiktok":       "postback_engine.network_adapters.tiktok_adapter",
    "impact":       "postback_engine.network_adapters.impact_adapter",
    "cake":         "postback_engine.network_adapters.cake_adapter",
    "hasoffers":    "postback_engine.network_adapters.hasoffers_adapter",
    "everflow":     "postback_engine.network_adapters.everflow_adapter",
}

# ── Webhook Events ────────────────────────────────────────────────────────────
WEBHOOK_EVENT_CONVERSION        = "conversion.completed"
WEBHOOK_EVENT_CONVERSION_REJECT = "conversion.rejected"
WEBHOOK_EVENT_CLICK             = "click.tracked"
WEBHOOK_EVENT_FRAUD             = "fraud.detected"
WEBHOOK_EVENT_REWARD            = "reward.granted"

# ── Analytics ────────────────────────────────────────────────────────────────
ANALYTICS_BUFFER_SIZE       = 1000  # events to buffer before flush
ANALYTICS_FLUSH_INTERVAL    = 60    # seconds
HOURLY_STAT_AGGREGATION_LAG = 5     # minutes lag for aggregation

# ── Pagination ────────────────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE       = 50
MAX_PAGE_SIZE           = 500
