# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Dispatch System
constants.py: All event type definitions and status enumerations.

Defines 40+ platform event types across financial, user, ad-network,
and system domains. Used by Subscription and DeliveryLog models.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


# ─────────────────────────────────────────────────────────────────────────────
#  DELIVERY STATUS ENUM
# ─────────────────────────────────────────────────────────────────────────────

class DeliveryStatus(models.TextChoices):
    """
    Ainul Enterprise Engine — Canonical delivery attempt status.
    Tracks every outbound dispatch attempt lifecycle.
    """
    PENDING    = "pending",    _("Pending")
    DISPATCHED = "dispatched", _("Dispatched")
    SUCCESS    = "success",    _("Success")
    FAILED     = "failed",     _("Failed")
    RETRYING   = "retrying",   _("Retrying")
    EXHAUSTED  = "exhausted",  _("Exhausted (Max Retries Reached)")
    CANCELLED  = "cancelled",  _("Cancelled")


# ─────────────────────────────────────────────────────────────────────────────
#  ENDPOINT STATUS ENUM
# ─────────────────────────────────────────────────────────────────────────────

class EndpointStatus(models.TextChoices):
    """
    Ainul Enterprise Engine — Webhook endpoint operational status.
    Controls whether an endpoint receives live dispatches.
    """
    ACTIVE    = "active",    _("Active")
    PAUSED    = "paused",    _("Paused")
    DISABLED  = "disabled",  _("Disabled")
    SUSPENDED = "suspended", _("Suspended (Auto — High Failure Rate)")


# ─────────────────────────────────────────────────────────────────────────────
#  HTTP METHOD CHOICES
# ─────────────────────────────────────────────────────────────────────────────

class HttpMethod(models.TextChoices):
    POST  = "POST",  _("POST")
    PUT   = "PUT",   _("PUT")
    PATCH = "PATCH", _("PATCH")


# ─────────────────────────────────────────────────────────────────────────────
#  PLATFORM EVENT TYPE REGISTRY  (40 event types)
# ─────────────────────────────────────────────────────────────────────────────

class EventType(models.TextChoices):
    """
    Ainul Enterprise Engine — Canonical platform event registry.
    Each event type represents a distinct, subscribable platform action.
    Grouped by domain: financial, user lifecycle, ad-network, fraud, system.
    """

    # ── PAYOUT / FINANCIAL ──────────────────────────────────────────────────
    PAYOUT_SUCCESS          = "payout.success",           _("Payout Success")
    PAYOUT_FAILED           = "payout.failed",            _("Payout Failed")
    PAYOUT_PENDING          = "payout.pending",           _("Payout Pending")
    PAYOUT_REVERSED         = "payout.reversed",          _("Payout Reversed")
    PAYOUT_SCHEDULED        = "payout.scheduled",         _("Payout Scheduled")

    # ── WALLET ───────────────────────────────────────────────────────────────
    WALLET_CREDITED         = "wallet.credited",          _("Wallet Credited")
    WALLET_DEBITED          = "wallet.debited",           _("Wallet Debited")
    WALLET_FROZEN           = "wallet.frozen",            _("Wallet Frozen")
    WALLET_THRESHOLD_HIT    = "wallet.threshold_hit",     _("Wallet Threshold Hit")

    # ── USER LIFECYCLE ────────────────────────────────────────────────────────
    USER_REGISTERED         = "user.registered",          _("User Registered")
    USER_VERIFIED           = "user.verified",            _("User Verified (KYC)")
    USER_SUSPENDED          = "user.suspended",           _("User Suspended")
    USER_DELETED            = "user.deleted",             _("User Deleted")
    USER_PROFILE_UPDATED    = "user.profile_updated",     _("User Profile Updated")
    USER_PASSWORD_CHANGED   = "user.password_changed",    _("User Password Changed")

    # ── OFFER / CPA ───────────────────────────────────────────────────────────
    OFFER_COMPLETED         = "offer.completed",          _("Offer Completed")
    OFFER_CREDITED          = "offer.credited",           _("Offer Credited")
    OFFER_REVERSED          = "offer.reversed",           _("Offer Reversed")
    OFFER_FLAGGED           = "offer.flagged",            _("Offer Flagged — Suspicious")

    # ── AD NETWORK ────────────────────────────────────────────────────────────
    AD_IMPRESSION           = "ad.impression",            _("Ad Impression")
    AD_CLICK                = "ad.click",                 _("Ad Click")
    AD_REWARD_GRANTED       = "ad.reward_granted",        _("Ad Reward Granted")
    AD_NETWORK_CONNECTED    = "ad.network_connected",     _("Ad Network Connected")
    AD_NETWORK_DISCONNECTED = "ad.network_disconnected",  _("Ad Network Disconnected")

    # ── REFERRAL ──────────────────────────────────────────────────────────────
    REFERRAL_SIGNUP         = "referral.signup",          _("Referral Signup")
    REFERRAL_COMMISSION     = "referral.commission",      _("Referral Commission Earned")

    # ── SUBSCRIPTION ──────────────────────────────────────────────────────────
    SUBSCRIPTION_ACTIVATED  = "subscription.activated",   _("Subscription Activated")
    SUBSCRIPTION_CANCELLED  = "subscription.cancelled",   _("Subscription Cancelled")
    SUBSCRIPTION_RENEWED    = "subscription.renewed",     _("Subscription Renewed")
    SUBSCRIPTION_EXPIRED    = "subscription.expired",     _("Subscription Expired")

    # ── FRAUD / SECURITY ──────────────────────────────────────────────────────
    FRAUD_ALERT_RAISED      = "fraud.alert_raised",       _("Fraud Alert Raised")
    FRAUD_ACCOUNT_BLOCKED   = "fraud.account_blocked",    _("Fraud — Account Blocked")
    FRAUD_IP_BLACKLISTED    = "fraud.ip_blacklisted",     _("Fraud — IP Blacklisted")

    # ── KYC ───────────────────────────────────────────────────────────────────
    KYC_SUBMITTED           = "kyc.submitted",            _("KYC Submitted")
    KYC_APPROVED            = "kyc.approved",             _("KYC Approved")
    KYC_REJECTED            = "kyc.rejected",             _("KYC Rejected")

    # ── SYSTEM ────────────────────────────────────────────────────────────────
    SYSTEM_MAINTENANCE_START = "system.maintenance_start", _("System Maintenance Started")
    SYSTEM_MAINTENANCE_END   = "system.maintenance_end",   _("System Maintenance Ended")
    SYSTEM_ALERT             = "system.alert",             _("System Alert")
    WEBHOOK_TEST             = "webhook.test",             _("Webhook Test Ping")


# ─────────────────────────────────────────────────────────────────────────────
#  RETRY CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

MAX_RETRY_ATTEMPTS: int = 5
RETRY_BACKOFF_BASE_SECONDS: int = 60   # 1 min → 2 min → 4 min → 8 min → 16 min
DISPATCH_TIMEOUT_SECONDS: int = 10
SIGNATURE_HEADER: str = "X-Webhook-Signature"
TIMESTAMP_HEADER: str = "X-Webhook-Timestamp"
EVENT_HEADER: str = "X-Webhook-Event"
DELIVERY_ID_HEADER: str = "X-Webhook-Delivery-ID"
