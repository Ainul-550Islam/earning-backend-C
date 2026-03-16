from django.db import models


class PostbackStatus(models.TextChoices):
    RECEIVED = "received", "Received"
    PROCESSING = "processing", "Processing"
    VALIDATED = "validated", "Validated"
    REWARDED = "rewarded", "Rewarded"
    REJECTED = "rejected", "Rejected"
    DUPLICATE = "duplicate", "Duplicate"
    FAILED = "failed", "Failed"
    PENDING_REVIEW = "pending_review", "Pending Review"


class RejectionReason(models.TextChoices):
    INVALID_SIGNATURE = "invalid_signature", "Invalid Signature"
    IP_NOT_WHITELISTED = "ip_not_whitelisted", "IP Not Whitelisted"
    DUPLICATE_LEAD = "duplicate_lead", "Duplicate Lead"
    MISSING_FIELDS = "missing_fields", "Missing Required Fields"
    INVALID_OFFER = "invalid_offer", "Invalid Offer ID"
    FRAUD_DETECTED = "fraud_detected", "Fraud Detected"
    RATE_LIMITED = "rate_limited", "Rate Limited"
    SIGNATURE_EXPIRED = "signature_expired", "Signature Expired"
    USER_NOT_FOUND = "user_not_found", "User Not Found"
    OFFER_INACTIVE = "offer_inactive", "Offer Inactive"
    PAYOUT_LIMIT_EXCEEDED = "payout_limit_exceeded", "Payout Limit Exceeded"
    BLACKLISTED = "blacklisted", "Blacklisted Source"
    SCHEMA_VALIDATION = "schema_validation", "Schema Validation Error"
    INTERNAL_ERROR = "internal_error", "Internal Processing Error"


class NetworkType(models.TextChoices):
    CPA = "cpa", "CPA Network"
    CPL = "cpl", "CPL Network"
    CPI = "cpi", "CPI Network"
    AFFILIATE = "affiliate", "Affiliate Network"
    DIRECT = "direct", "Direct Advertiser"
    INTERNAL = "internal", "Internal System"


class SignatureAlgorithm(models.TextChoices):
    HMAC_SHA256 = "hmac_sha256", "HMAC-SHA256"
    HMAC_SHA512 = "hmac_sha512", "HMAC-SHA512"
    MD5 = "md5", "MD5 (Legacy)"
    NONE = "none", "No Signature (IP-only)"


class ValidatorStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    TESTING = "testing", "Testing Mode"


class DeduplicationWindow(models.TextChoices):
    HOUR = "1h", "1 Hour"
    DAY = "1d", "1 Day"
    WEEK = "7d", "7 Days"
    MONTH = "30d", "30 Days"
    FOREVER = "forever", "Forever (No Repeat)"
