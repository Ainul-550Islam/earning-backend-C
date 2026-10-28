# =============================================================================
# fraud_detection/constants.py
#
# Shared constants used across models, views, services, and caching layers.
# =============================================================================
from __future__ import annotations

# ---------------------------------------------------------------------------
# Risk Score Thresholds
# ---------------------------------------------------------------------------

RISK_THRESHOLDS = {
    'low':      (0,  30),   # 0–30  : Low risk
    'medium':   (31, 60),   # 31–60 : Medium risk
    'high':     (61, 80),   # 61–80 : High risk
    'critical': (81, 100),  # 81–100: Critical risk — auto-action required
}

# Minimum score to auto-flag a user
AUTO_FLAG_THRESHOLD       = 70
# Minimum score to auto-ban a user
AUTO_BAN_THRESHOLD        = 90
# Score below which a risk profile is considered clean
CLEAN_THRESHOLD           = 25


# ---------------------------------------------------------------------------
# Cache Keys — use .format(**kwargs) to build concrete keys
# ---------------------------------------------------------------------------

CACHE_KEYS = {
    # Per-user risk score (refreshed on every fraud attempt)
    'user_risk_score':        'fraud:risk_score:{user_id}',
    # IP reputation lookup
    'ip_reputation':          'fraud:ip_rep:{ip_address}',
    # Device trust score
    'device_trust':           'fraud:device:{device_hash}',
    # Velocity counters — attempt counts per window
    'velocity_attempts':      'fraud:velocity:attempts:{user_id}:{window}',
    # Detection result cache (short TTL to avoid redundant ML calls)
    'detection_result':       'fraud:detect:{cache_key}',
    # ML model instance (loaded once, cached)
    'ml_model':               'fraud:ml_model:{model_name}',
    # Admin dashboard stats
    'dashboard_stats':        'fraud:dashboard:stats',
    # Fraud settings singleton
    'fraud_settings':         'fraud:settings',
    # Alert count badge
    'unresolved_alert_count': 'fraud:alerts:unresolved',
    # Geo-velocity — last known location per user
    'last_location':          'fraud:geo:{user_id}:last_location',
    # Pattern cache — compiled rule patterns
    'rule_patterns':          'fraud:rules:patterns',
    # Brute-force attempt counter
    'brute_force_attempts':   'fraud:bf:{ip_address}:{action}',
}


# ---------------------------------------------------------------------------
# Cache TTLs (seconds)
# ---------------------------------------------------------------------------

CACHE_TTL = {
    'user_risk_score':        60 * 15,    # 15 minutes
    'ip_reputation':          60 * 60,    # 1 hour
    'device_trust':           60 * 60 * 4, # 4 hours
    'velocity_attempts':      60 * 60,    # 1 hour (rolling window)
    'detection_result':       60 * 5,     # 5 minutes
    'ml_model':               60 * 60 * 6, # 6 hours
    'dashboard_stats':        60 * 5,     # 5 minutes
    'fraud_settings':         60 * 30,    # 30 minutes
    'unresolved_alert_count': 60 * 2,     # 2 minutes
    'last_location':          60 * 60 * 24, # 24 hours
    'rule_patterns':          60 * 60 * 2,  # 2 hours
    'brute_force_attempts':   60 * 15,    # 15 minutes
}


# ---------------------------------------------------------------------------
# Hash / Integrity
# ---------------------------------------------------------------------------

# Truncation length for stored SHA-256 hashes on fraud records
HASH_LENGTH = 64

# Algorithm used for blockchain-style integrity chain
HASH_ALGORITHM = 'sha256'


# ---------------------------------------------------------------------------
# Velocity Windows
# ---------------------------------------------------------------------------

VELOCITY_WINDOWS = {
    'minute': 60,
    'hour':   3600,
    'day':    86400,
    'week':   604800,
}

# Default attempt limits per window (per user)
VELOCITY_LIMITS = {
    'minute': 5,
    'hour':   20,
    'day':    50,
    'week':   100,
}


# ---------------------------------------------------------------------------
# Scoring Weights (used by FraudScoreCalculator)
# ---------------------------------------------------------------------------

SCORING_WEIGHTS = {
    'ip_reputation':   0.25,
    'device_trust':    0.20,
    'velocity':        0.20,
    'behavioral':      0.15,
    'geo_velocity':    0.10,
    'rule_engine':     0.10,
}


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

DEFAULT_PAGE_SIZE     = 20
MAX_PAGE_SIZE         = 200
LARGE_PAGE_SIZE       = 100


# ---------------------------------------------------------------------------
# ML Model
# ---------------------------------------------------------------------------

ML_MODEL_VERSION      = '1.0.0'
ML_FEATURE_COUNT      = 42
ML_FRAUD_PROBABILITY_THRESHOLD = 0.65


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

# Number of hours after which an open case is considered stale
CASE_STALE_HOURS      = 72

# Max number of notifications per user per day (anti-spam)
MAX_NOTIFICATIONS_PER_DAY = 20

# GeoVelocity: impossible travel speed threshold (km/h)
IMPOSSIBLE_SPEED_KMH  = 900


# Alias: api/fraud_detection/logic.py imports this name
FRAUD_SCORE_WEIGHTS = SCORING_WEIGHTS

# ---------------------------------------------------------------------------
# Restored from c9e7666e (dropped in the fraud-detection merge, still imported
# by use_cases, interactors, analytics, monitoring, notifications_push)
# ---------------------------------------------------------------------------
MAX_DEVICES_PER_USER = 5

TIME_THRESHOLDS = {
    'rapid_clicks': 10,          # clicks per minute
    'multiple_sessions': 2,      # simultaneous sessions
    'suspicious_hours': 2,       # hours for pattern detection
    'device_change_hours': 24,   # hours for device change detection
}

DASHBOARD_CONFIG = {
    'max_items_per_page': 50,
    'refresh_interval_seconds': 30,
    'chart_data_points': 100,
    'map_max_markers': 500,
    'timeline_max_events': 200,
}

REALTIME_CONFIG = {
    'websocket_room': 'fraud_monitoring',
    'alert_broadcast_delay': 1,        # seconds
    'max_concurrent_connections': 100,
    'heartbeat_interval': 30,          # seconds
}

NOTIFICATION_CONFIG = {
    'max_retries': 3,
    'retry_delay_seconds': 60,
    'batch_send_size': 100,
    'rate_limit_per_minute': 50,
}
