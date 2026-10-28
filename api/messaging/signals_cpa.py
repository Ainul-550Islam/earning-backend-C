"""
CPA Messaging Signals — Business event signals.
Connect your CPA platform events to the messaging system.

Audit finding (Part 19): 13 of these 15 signals were flagged as "never
fired" during the audit. Investigation confirmed why: this module has
no Offer/Affiliate/Conversion/Payout model or business logic anywhere
in it (models.py has none) — these signals are, by design, meant to be
fired from your separate offers/affiliates/payouts app(s) elsewhere in
earning_backend, exactly as this docstring already said. That part
isn't a bug here; it can't be fixed from inside this module.

What WAS a bug, fixable here, and fixed: every kwargs comment below was
cross-checked line-by-line against what receivers_cpa.py's @receiver
functions actually read (kwargs.get(...) calls), and two were flat
wrong in a way that would have caused a silent no-op the moment
another app followed this docstring:
  - offer_expiring_soon documented `affiliate_ids` (list, plural) - the
    receiver reads `affiliate_id` (singular). Sending the documented
    key would have hit the receiver's `if not affiliate_id: return`
    guard and silently done nothing, every time.
  - payout_failed documented `error` - the receiver reads `reason`.
    Sending `error=` would have silently fallen back to the receiver's
    generic "Payment processing failed." default instead of showing
    the real failure reason.
Every signal was also missing `tenant` in its documented kwargs even
though every receiver reads it (kwargs.get("tenant")) - added below.

Usage in your offer/payout/affiliate modules (see each signal below
for its exact, receiver-verified kwargs):

    from api.messaging.signals_cpa import (
        offer_status_changed,
        conversion_received,
        payout_processed,
        affiliate_status_changed,
    )

    # In your offer approval view:
    offer_status_changed.send(
        sender=Offer, offer_id=offer.id, offer_name=offer.name,
        affiliate_id=affiliate.id, new_status="approved", tenant=tenant,
    )
"""
from django.dispatch import Signal

# ── Offer Signals ─────────────────────────────────────────────────────────────

# Fired when an offer's approval status changes.
# kwargs: offer_id, offer_name (default "Offer"), affiliate_id,
#         new_status (approved/rejected/paused/reactivated, default ""),
#         reason (str, optional), payout (str, optional), tenant (optional)
offer_status_changed = Signal()

# Fired when a new offer is published and available to affiliates.
# kwargs: offer_id, offer_name (default "New Offer"), vertical (default ""),
#         payout (default ""), countries (list, default []), tenant (optional)
new_offer_published = Signal()

# Fired when an offer is expiring soon (e.g. 24h left). One affiliate per
# send() - loop and send once per affiliate if notifying several.
# kwargs: affiliate_id (SINGULAR - not affiliate_ids), offer_id,
#         offer_name (default "Your Offer"), expires_at (default ""),
#         hours_left (default 24), tenant (optional)
offer_expiring_soon = Signal()

# ── Conversion Signals ────────────────────────────────────────────────────────

# Fired when a new conversion/lead is received. Already wired up and firing
# correctly from utils/postback_tracker.fire_conversion_signal() - shown
# here as the reference example for the other 13 signals in this file.
# kwargs: conversion_id, affiliate_id, offer_name (default "Offer"),
#         payout_amount (default "$0.00"), tenant (optional)
#         (offer_id is accepted for logging/future use but not read by
#         the current notification body)
conversion_received = Signal()

# Fired when a conversion is approved/rejected/reversed.
# kwargs: conversion_id, affiliate_id, offer_name (default "Offer"),
#         payout_amount (default "$0.00"), new_status (default ""),
#         reason (default ""), tenant (optional)
conversion_status_changed = Signal()

# Fired when a postback delivery fails. Already wired up and firing
# correctly from utils/postback_tracker.send_postback_failed_alert().
# kwargs: affiliate_id, offer_id, offer_name (default "Offer"),
#         error_detail (default ""), tenant (optional)
postback_failed = Signal()

# ── Payout Signals ────────────────────────────────────────────────────────────

# Fired when a payout is processed and sent.
# kwargs: payout_id, affiliate_id, amount (default "$0.00"),
#         payment_method (default ""), transaction_id (default ""),
#         expected_date (default ""), tenant (optional)
payout_processed = Signal()

# Fired when affiliate balance hits minimum payout threshold.
# kwargs: affiliate_id, current_balance (default "$0.00"),
#         threshold (default "$0.00"), next_payout_date (default ""),
#         tenant (optional)
payout_threshold_reached = Signal()

# Fired when a payout is placed on hold.
# kwargs: payout_id, affiliate_id, amount (default "$0.00"),
#         reason (default ""), tenant (optional)
payout_on_hold = Signal()

# Fired when a payout fails.
# kwargs: payout_id, affiliate_id, amount (default "$0.00"),
#         reason (NOT "error" - default "Payment processing failed."),
#         retry_at (optional), tenant (optional)
payout_failed = Signal()

# ── Affiliate Account Signals ─────────────────────────────────────────────────

# Fired when affiliate account status changes. Only new_status=="approved"
# and new_status in ("suspended", "banned") currently trigger a
# notification - "rejected"/"reinstated" are accepted but no-op today.
# kwargs: affiliate_id, affiliate_name (default "Affiliate"),
#         new_status (default ""), reason (default "", used by
#         suspended/banned), tenant (optional)
#         when new_status=="approved", also read: manager_name (default ""),
#         welcome_bonus (default "")
#         when new_status is suspended/banned, also read: duration (default "")
affiliate_status_changed = Signal()

# Fired when an account manager is assigned to an affiliate.
# kwargs: affiliate_id, manager_id, manager_name (default "Your Manager"),
#         manager_email (default ""), tenant (optional)
manager_assigned = Signal()

# Fired when fraud is detected on an affiliate account.
# kwargs: affiliate_id, offer_id, offer_name (default "Offer"),
#         details (default ""), tenant (optional)
fraud_detected = Signal()

# ── Performance Signals ───────────────────────────────────────────────────────

# Fired when affiliate reaches a performance milestone.
# kwargs: affiliate_id, milestone_type (default "custom"),
#         milestone_value (default ""), reward (default ""), tenant (optional)
milestone_reached = Signal()

# Fired when affiliate's EPC drops. NOTE: the receiver silently ignores
# this signal entirely when drop_percent < 30 - only send this for drops
# you actually want the affiliate notified about, not every fluctuation.
# kwargs: affiliate_id, offer_id, offer_name (default "Your Offer"),
#         old_epc (default "N/A"), new_epc (default "N/A"), drop_percent
#         (number, e.g. 35 for 35% - default 0, <30 is silently dropped),
#         tenant (optional)
epc_dropped = Signal()
