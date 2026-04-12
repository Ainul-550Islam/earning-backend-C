"""
enums.py – All TextChoices and IntegerChoices for Postback Engine.
"""
from django.db import models


# ── Postback / Conversion Status ──────────────────────────────────────────────

class PostbackStatus(models.TextChoices):
    RECEIVED        = "received",       "Received"
    PROCESSING      = "processing",     "Processing"
    VALIDATED       = "validated",      "Validated"
    REWARDED        = "rewarded",       "Rewarded"
    REJECTED        = "rejected",       "Rejected"
    DUPLICATE       = "duplicate",      "Duplicate"
    FAILED          = "failed",         "Failed"
    PENDING_REVIEW  = "pending_review", "Pending Review"
    QUEUED          = "queued",         "Queued"
    RETRYING        = "retrying",       "Retrying"


class ConversionStatus(models.TextChoices):
    PENDING     = "pending",    "Pending"
    APPROVED    = "approved",   "Approved"
    REJECTED    = "rejected",   "Rejected"
    REVERSED    = "reversed",   "Reversed"
    FLAGGED     = "flagged",    "Flagged for Review"
    PAID        = "paid",       "Paid"


class ClickStatus(models.TextChoices):
    VALID       = "valid",      "Valid"
    DUPLICATE   = "duplicate",  "Duplicate"
    EXPIRED     = "expired",    "Expired"
    FRAUD       = "fraud",      "Fraud"
    BOT         = "bot",        "Bot"
    BLOCKED     = "blocked",    "Blocked"


class ImpressionStatus(models.TextChoices):
    RENDERED    = "rendered",   "Rendered"
    VIEWABLE    = "viewable",   "Viewable"
    FRAUD       = "fraud",      "Fraud"
    FILTERED    = "filtered",   "Filtered"


# ── Network ───────────────────────────────────────────────────────────────────

class NetworkType(models.TextChoices):
    CPA         = "cpa",        "CPA Network"
    CPL         = "cpl",        "CPL Network"
    CPI         = "cpi",        "CPI (Mobile Install)"
    CPM         = "cpm",        "CPM Network"
    CPC         = "cpc",        "CPC Network"
    AFFILIATE   = "affiliate",  "Affiliate Network"
    OFFERWALL   = "offerwall",  "Offerwall"
    DIRECT      = "direct",     "Direct Advertiser"
    INTERNAL    = "internal",   "Internal System"
    S2S         = "s2s",        "Server-to-Server"


class NetworkStatus(models.TextChoices):
    ACTIVE      = "active",     "Active"
    INACTIVE    = "inactive",   "Inactive"
    TESTING     = "testing",    "Testing Mode"
    SUSPENDED   = "suspended",  "Suspended"
    DEPRECATED  = "deprecated", "Deprecated"


# ── Security ──────────────────────────────────────────────────────────────────

class SignatureAlgorithm(models.TextChoices):
    HMAC_SHA256 = "hmac_sha256", "HMAC-SHA256"
    HMAC_SHA512 = "hmac_sha512", "HMAC-SHA512"
    HMAC_MD5    = "hmac_md5",    "HMAC-MD5 (Legacy)"
    MD5         = "md5",         "MD5 (Legacy)"
    NONE        = "none",        "No Signature (IP-only)"


class DeduplicationWindow(models.TextChoices):
    HOUR    = "1h",     "1 Hour"
    DAY     = "1d",     "1 Day"
    WEEK    = "7d",     "7 Days"
    MONTH   = "30d",    "30 Days"
    FOREVER = "forever","Forever (No Repeat)"


# ── Rejection / Fraud ─────────────────────────────────────────────────────────

class RejectionReason(models.TextChoices):
    INVALID_SIGNATURE       = "invalid_signature",      "Invalid Signature"
    IP_NOT_WHITELISTED      = "ip_not_whitelisted",     "IP Not Whitelisted"
    DUPLICATE_LEAD          = "duplicate_lead",         "Duplicate Lead"
    MISSING_FIELDS          = "missing_fields",         "Missing Required Fields"
    INVALID_OFFER           = "invalid_offer",          "Invalid Offer ID"
    FRAUD_DETECTED          = "fraud_detected",         "Fraud Detected"
    RATE_LIMITED            = "rate_limited",           "Rate Limited"
    SIGNATURE_EXPIRED       = "signature_expired",      "Signature Expired"
    USER_NOT_FOUND          = "user_not_found",         "User Not Found"
    OFFER_INACTIVE          = "offer_inactive",         "Offer Inactive"
    PAYOUT_LIMIT_EXCEEDED   = "payout_limit_exceeded",  "Payout Limit Exceeded"
    BLACKLISTED             = "blacklisted",            "Blacklisted Source"
    SCHEMA_VALIDATION       = "schema_validation",      "Schema Validation Error"
    INTERNAL_ERROR          = "internal_error",         "Internal Processing Error"
    BOT_DETECTED            = "bot_detected",           "Bot Traffic Detected"
    PROXY_VPN               = "proxy_vpn",              "Proxy/VPN Detected"
    GEO_BLOCKED             = "geo_blocked",            "Geo Restriction"
    VELOCITY_LIMIT          = "velocity_limit",         "Velocity Limit Exceeded"


class FraudType(models.TextChoices):
    CLICK_SPAM          = "click_spam",         "Click Spam"
    CLICK_INJECTION     = "click_injection",    "Click Injection"
    SDK_SPOOFING        = "sdk_spoofing",       "SDK Spoofing"
    INSTALL_HIJACKING   = "install_hijacking",  "Install Hijacking"
    DUPLICATE_IP        = "duplicate_ip",       "Duplicate IP"
    BOT_TRAFFIC         = "bot_traffic",        "Bot Traffic"
    PROXY_VPN           = "proxy_vpn",          "Proxy / VPN"
    MULTI_ACCOUNT       = "multi_account",      "Multi Account"
    VELOCITY_ABUSE      = "velocity_abuse",     "Velocity Abuse"
    GEO_MISMATCH        = "geo_mismatch",       "Geo Mismatch"
    DEVICE_FARM         = "device_farm",        "Device Farm"
    EMULATOR            = "emulator",           "Emulator Detected"
    KNOWN_BAD_IP        = "known_bad_ip",       "Known Bad IP"
    OTHER               = "other",              "Other"


class BlacklistType(models.TextChoices):
    IP          = "ip",         "IP Address"
    CIDR        = "cidr",       "CIDR Range"
    DEVICE_ID   = "device_id",  "Device ID"
    USER_AGENT  = "user_agent", "User Agent"
    FINGERPRINT = "fingerprint","Device Fingerprint"
    CLICK_ID    = "click_id",   "Click ID"


class BlacklistReason(models.TextChoices):
    FRAUD           = "fraud",          "Fraud Detected"
    ABUSE           = "abuse",          "Abuse"
    SPAM            = "spam",           "Spam"
    MANUAL          = "manual",         "Manual Block"
    KNOWN_BAD       = "known_bad",      "Known Bad Actor"
    BOT             = "bot",            "Bot / Crawler"
    VPN_PROXY       = "vpn_proxy",      "VPN / Proxy"


# ── Queue ─────────────────────────────────────────────────────────────────────

class QueueStatus(models.TextChoices):
    PENDING     = "pending",    "Pending"
    PROCESSING  = "processing", "Processing"
    COMPLETED   = "completed",  "Completed"
    FAILED      = "failed",     "Failed"
    DEAD        = "dead",       "Dead Letter"
    CANCELLED   = "cancelled",  "Cancelled"


class QueuePriority(models.IntegerChoices):
    CRITICAL    = 1, "Critical"
    HIGH        = 2, "High"
    NORMAL      = 3, "Normal"
    LOW         = 4, "Low"
    BACKGROUND  = 5, "Background"


# ── Attribution ───────────────────────────────────────────────────────────────

class AttributionModel(models.TextChoices):
    LAST_CLICK      = "last_click",     "Last Click"
    FIRST_CLICK     = "first_click",    "First Click"
    LINEAR          = "linear",         "Linear"
    TIME_DECAY      = "time_decay",     "Time Decay"
    POSITION_BASED  = "position_based", "Position Based (U-Shape)"
    DATA_DRIVEN     = "data_driven",    "Data Driven"


class DeviceType(models.TextChoices):
    DESKTOP     = "desktop",    "Desktop"
    MOBILE      = "mobile",     "Mobile"
    TABLET      = "tablet",     "Tablet"
    TV          = "tv",         "Smart TV"
    UNKNOWN     = "unknown",    "Unknown"
