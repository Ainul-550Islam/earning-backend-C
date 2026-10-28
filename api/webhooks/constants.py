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
# CONSOLIDATION (this audit): was a native TextChoices definition here, a
# 3rd independent copy alongside choices.py and models/constants.py, kept
# manually value-synced. choices.py is now the single owner (see its
# DeliveryStatus docstring and models/constants.py's module docstring for
# the fuller history); re-exported here so `from .constants import
# DeliveryStatus` / `from ..constants import DeliveryStatus` keep working.
from .choices import DeliveryStatus  # noqa: E402,F401


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
# CONSOLIDATION (this audit): was a native definition here missing
# DELETE/GET (present in choices.py's version, confirmed unused anywhere
# via HttpMethod.DELETE/.GET so widening is safe). Re-exported from
# choices.py, which is now the single owner.
from .choices import HttpMethod  # noqa: E402,F401
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

    # ── PAYMENT ────────────────────────────────────────────────────────────
    # NEW DOMAIN (Session 9): confirmed real, not previously registered at
    # all under any name. signals/payment_signals.py fires all 6 of these
    # from real, connected post_save handlers (confirmed via
    # signals/connector.py: connect_payment_signals() is called by
    # connect_all_signals(), itself called from WebhooksConfig.ready() -
    # this wiring was itself the subject of an earlier session's fix, per
    # connector.py's own header comment, so it's live in production, not
    # dormant code).
    #
    # Worth a human double-check this session couldn't fully resolve:
    # "payment" here (6-state gateway-style lifecycle: initiated,
    # succeeded, failed, refunded, disputed, cancelled) reads like a
    # different concept from the existing PAYOUT_* entries above (simpler
    # 5-state lifecycle: success, failed, pending, reversed, scheduled) -
    # money coming into the platform vs. money going out, consistent with
    # api.payment_gateways and api.payout_queue existing as separate apps
    # in the full monorepo - but this session only had signal-handler code
    # to go on, not those apps' own source, so treat this as a well-
    # evidenced inference, not a confirmed product decision.
    PAYMENT_SUCCEEDED       = "payment.succeeded",        _("Payment Succeeded")
    PAYMENT_FAILED          = "payment.failed",           _("Payment Failed")
    PAYMENT_INITIATED       = "payment.initiated",        _("Payment Initiated")
    PAYMENT_CANCELLED       = "payment.cancelled",        _("Payment Cancelled")
    PAYMENT_REFUNDED        = "payment.refunded",         _("Payment Refunded")
    PAYMENT_DISPUTED        = "payment.disputed",         _("Payment Disputed")

    # ── WITHDRAWAL ─────────────────────────────────────────────────────────
    # NEW DOMAIN (Session 9): same standard of evidence as PAYMENT above -
    # signals/withdrawal_signals.py fires all 5 of these from real,
    # connected handlers (connect_withdrawal_signals(), confirmed wired).
    WITHDRAWAL_REQUESTED    = "withdrawal.requested",     _("Withdrawal Requested")
    WITHDRAWAL_APPROVED     = "withdrawal.approved",      _("Withdrawal Approved")
    WITHDRAWAL_REJECTED     = "withdrawal.rejected",      _("Withdrawal Rejected")
    WITHDRAWAL_COMPLETED    = "withdrawal.completed",     _("Withdrawal Completed")
    WITHDRAWAL_FAILED       = "withdrawal.failed",        _("Withdrawal Failed")

    # ── WALLET ───────────────────────────────────────────────────────────────
    WALLET_CREDITED         = "wallet.credited",          _("Wallet Credited")
    WALLET_DEBITED          = "wallet.debited",           _("Wallet Debited")
    WALLET_FROZEN           = "wallet.frozen",            _("Wallet Frozen")
    WALLET_THRESHOLD_HIT    = "wallet.threshold_hit",     _("Wallet Threshold Hit")
    # signals/wallet_signals.py also fires 'wallet.transaction.created',
    # 'wallet.balance.updated', and 'wallet.transaction.failed' - all real
    # and connected (connect_wallet_signals()), but NOT added here: they're
    # 3-segment strings ("wallet.transaction.created" has two dots), which
    # doesn't match this registry's own domain.action convention (every
    # existing entry, and every other addition in this cluster, is exactly
    # 2 segments) or validate_event_type()'s format regex
    # (^[a-z0-9_]+\.[a-z0-9_]+$, which only allows one dot - confirmed
    # empirically these 3 values fail it). Whether the right fix is
    # loosening that regex, renaming these 3 signal emissions to fit the
    # 2-segment convention, or something else is a real design decision,
    # not something to guess at while adding otherwise-straightforward
    # registry entries - flagged in FIXES_APPLIED_SESSION9.md rather than
    # decided here.

    # ── USER LIFECYCLE ────────────────────────────────────────────────────────
    # BUG FIX (Session 9): USER_CREATED was missing from this registry even
    # though 'user.created' is used pervasively as the standard example/test
    # event type throughout this codebase (confirmed: 28+ occurrences in
    # test_integration.py alone, plus many more across the rest of the test
    # suite) - discovered while fixing validate_event_type()'s broken
    # whitelist check (see validators.py and EventType.choices below): fixing
    # that validator to actually enforce the whitelist broke 18 previously-
    # passing tests that submit 'user.created' through WebhookEmitSerializer,
    # confirming it was never a registered event type despite being the
    # de facto standard one used everywhere. Adding it here (rather than
    # rewriting every affected test to use a different, real event type) is
    # the conservative fix - 'user.created' is an unambiguous, self-
    # explanatory event name consistent with this domain's existing style,
    # so treating its absence as the actual gap is a safer inference than
    # guessing that every one of those call sites intended something else.
    USER_CREATED            = "user.created",             _("User Created")
    # Also confirmed missing and also confirmed real: signals/user_signals.py
    # explicitly documents and emits event_type='user.updated' from a real
    # Django post_save signal handler - this isn't just a test-suite
    # convention like USER_CREATED, it's already live in production code
    # dispatch, just never added to this "canonical" registry.
    USER_UPDATED            = "user.updated",              _("User Updated")
    USER_REGISTERED         = "user.registered",          _("User Registered")
    USER_VERIFIED           = "user.verified",            _("User Verified (KYC)")
    USER_SUSPENDED          = "user.suspended",           _("User Suspended")
    USER_DELETED            = "user.deleted",             _("User Deleted")
    USER_PROFILE_UPDATED    = "user.profile_updated",     _("User Profile Updated")
    USER_PASSWORD_CHANGED   = "user.password_changed",    _("User Password Changed")
    # Also confirmed real and connected (connect_user_signals()):
    USER_LOGIN              = "user.login",               _("User Login")
    USER_LOGOUT              = "user.logout",              _("User Logout")
    # user_signals.py also fires 'user.profile.updated' (dot) and
    # 'user.status.changed' - both 3-segment, not added, same reasoning as
    # the wallet.* omissions above. Note this file's existing
    # USER_PROFILE_UPDATED = "user.profile_updated" (underscore) is a
    # different string from the signal's actual 'user.profile.updated'
    # (dot) - unclear whether that's the same bug (a naming-convention
    # mismatch) or two genuinely different things; not resolved here.

    # ── OFFER / CPA ───────────────────────────────────────────────────────────
    OFFER_COMPLETED         = "offer.completed",          _("Offer Completed")
    OFFER_CREDITED          = "offer.credited",           _("Offer Credited")
    OFFER_REVERSED          = "offer.reversed",           _("Offer Reversed")
    OFFER_FLAGGED           = "offer.flagged",            _("Offer Flagged — Suspicious")
    # Also confirmed real and connected (connect_offer_signals()):
    OFFER_CANCELLED         = "offer.cancelled",          _("Offer Cancelled")
    OFFER_EXPIRED           = "offer.expired",             _("Offer Expired")
    OFFER_UPDATED           = "offer.updated",             _("Offer Updated")

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
    # Also confirmed real and connected (connect_fraud_signals()) - these
    # read as a detection lifecycle (detected -> flagged -> cleared),
    # complementary to rather than overlapping with the consequence-
    # focused entries above (an alert being raised or an account being
    # blocked are things that might happen *because of* a detection, not
    # duplicates of the detection itself):
    FRAUD_DETECTED           = "fraud.detected",           _("Fraud Detected")
    FRAUD_FLAGGED             = "fraud.flagged",            _("Fraud Flagged")
    FRAUD_CLEARED             = "fraud.cleared",            _("Fraud Cleared")

    # ── KYC ───────────────────────────────────────────────────────────────────
    KYC_SUBMITTED           = "kyc.submitted",            _("KYC Submitted")
    KYC_APPROVED            = "kyc.approved",             _("KYC Approved")
    KYC_REJECTED            = "kyc.rejected",             _("KYC Rejected")
    # Also confirmed real and connected (connect_kyc_signals()):
    # kyc_signals.py exclusively uses 'verified' terminology throughout
    # (checks instance.status != 'verified', fires event_type='kyc.verified')
    # and never uses 'approved' anywhere in that file - whether KYC_APPROVED
    # above is a distinct step fired elsewhere (e.g. in the api.kyc app
    # itself, outside this session's access) or effectively unused isn't
    # something this session could confirm either way; added verified as
    # its own entry rather than assuming either answer.
    KYC_VERIFIED             = "kyc.verified",             _("KYC Verified")

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

# BUG FIX: management/commands/cleanup_old_logs.py imports this as its
# --days default; it was referenced but never defined anywhere.
WEBHOOK_ANALYTICS_RETENTION_DAYS: int = 90

# ─────────────────────────────────────────────────────────────────────────────
#  COMPATIBILITY RE-EXPORTS
# ─────────────────────────────────────────────────────────────────────────────
# BUG FIX (found via real Django import verification, not just AST syntax
# checking): validators.py, models/replay.py, several services/, serializers/,
# viewsets/, and tasks/ files all do `from .constants import BatchStatus` (or
# ErrorType / FilterOperator / InboundSource / ReplayStatus / WebhookStatus),
# but none of these 6 classes were ever actually defined in this file - they
# only existed in choices.py and (separately, non-identically) in
# models/constants.py. This caused 18+ confirmed ImportError crashes across
# the module. choices.py is re-exported here as the canonical source since
# its classes provide both .CHOICES (uppercase) and .choices (lowercase alias)
# so both usage styles found in the codebase keep working.
from .choices import (  # noqa: E402,F401
    BatchStatus,
    ErrorType,
    FilterOperator,
    InboundSource,
    ReplayStatus,
    WebhookStatus,
)

# Uppercase .CHOICES aliases for the native TextChoices classes still
# defined directly in this file, needed by filters.py (and possibly other
# files) which use the choices.py-style uppercase convention. Assigned
# outside the class bodies to avoid Django's Choices metaclass treating
# "CHOICES = ..." as a new enum member if placed inside the class body.
# (DeliveryStatus/HttpMethod don't need this - they're re-exported directly
# from choices.py above, which already provides .CHOICES natively.)
EndpointStatus.CHOICES = EndpointStatus.choices
EventType.CHOICES = EventType.choices