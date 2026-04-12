"""
signals.py
───────────
Django signals for Postback Engine.
All domain events are represented here as Django signals.
Receivers are registered in receivers.py.
"""
from django.dispatch import Signal

# ═══════════════════════════════════════════════════════════════════════════════
# POSTBACK LIFECYCLE SIGNALS  (Sender: PostbackRawLog)
# ═══════════════════════════════════════════════════════════════════════════════
postback_received           = Signal()   # kwargs: raw_log
postback_validated          = Signal()   # kwargs: raw_log
postback_rewarded           = Signal()   # kwargs: raw_log, conversion
postback_rejected           = Signal()   # kwargs: raw_log, reason, exc
postback_duplicate          = Signal()   # kwargs: raw_log
postback_failed             = Signal()   # kwargs: raw_log, exc
postback_queued             = Signal()   # kwargs: raw_log, queue_item
postback_retry_scheduled    = Signal()   # kwargs: raw_log, retry_log, delay_seconds, attempt
postback_dead_lettered      = Signal()   # kwargs: raw_log, reason

# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSION SIGNALS  (Sender: Conversion)
# ═══════════════════════════════════════════════════════════════════════════════
conversion_created          = Signal()   # kwargs: conversion
conversion_approved         = Signal()   # kwargs: conversion
conversion_rejected         = Signal()   # kwargs: conversion, reason
conversion_reversed         = Signal()   # kwargs: conversion, reason
conversion_credited         = Signal()   # kwargs: conversion, wallet_tx_id
conversion_flagged          = Signal()   # kwargs: conversion, fraud_score, signals

# ═══════════════════════════════════════════════════════════════════════════════
# CLICK SIGNALS  (Sender: ClickLog)
# ═══════════════════════════════════════════════════════════════════════════════
click_tracked               = Signal()   # kwargs: click_log
click_converted             = Signal()   # kwargs: click_log, conversion
click_expired               = Signal()   # kwargs: click_log
click_fraud                 = Signal()   # kwargs: click_log, fraud_type, fraud_score
click_duplicate             = Signal()   # kwargs: click_log

# ═══════════════════════════════════════════════════════════════════════════════
# IMPRESSION SIGNALS  (Sender: Impression)
# ═══════════════════════════════════════════════════════════════════════════════
impression_recorded         = Signal()   # kwargs: impression
impression_viewable         = Signal()   # kwargs: impression, view_time_seconds

# ═══════════════════════════════════════════════════════════════════════════════
# FRAUD SIGNALS  (Sender: FraudAttemptLog)
# ═══════════════════════════════════════════════════════════════════════════════
fraud_detected              = Signal()   # kwargs: fraud_log, raw_log, score
fraud_auto_blocked          = Signal()   # kwargs: ip_address, reason, fraud_score
ip_blacklisted              = Signal()   # kwargs: ip_address, added_by, reason
ip_unblacklisted            = Signal()   # kwargs: ip_address, removed_by

# ═══════════════════════════════════════════════════════════════════════════════
# NETWORK SIGNALS  (Sender: AdNetworkConfig)
# ═══════════════════════════════════════════════════════════════════════════════
network_activated           = Signal()   # kwargs: network
network_deactivated         = Signal()   # kwargs: network
network_secret_rotated      = Signal()   # kwargs: network, rotated_by
network_rate_limited        = Signal()   # kwargs: network, count, limit

# ═══════════════════════════════════════════════════════════════════════════════
# REWARD SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════
reward_dispatched           = Signal()   # kwargs: conversion, user, points, usd
reward_failed               = Signal()   # kwargs: conversion, error, attempt
reward_reversed             = Signal()   # kwargs: conversion, user, points, usd, reason

# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOK SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════
webhook_sent                = Signal()   # kwargs: url, event, status_code, duration_ms
webhook_failed              = Signal()   # kwargs: url, event, error, attempt
webhook_permanently_failed  = Signal()   # kwargs: url, event, conversion_id

# ═══════════════════════════════════════════════════════════════════════════════
# QUEUE SIGNALS  (Sender: PostbackQueue)
# ═══════════════════════════════════════════════════════════════════════════════
queue_dead_lettered         = Signal()   # kwargs: queue_item
queue_item_replayed         = Signal()   # kwargs: queue_item, replayed_by

# ═══════════════════════════════════════════════════════════════════════════════
# ANALYTICS SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════
hourly_stats_computed       = Signal()   # kwargs: network, date, hour, stats
daily_report_generated      = Signal()   # kwargs: date, summary
conversion_anomaly_detected = Signal()   # kwargs: network, deviation_pct, direction
