"""
CPA Messaging Signals — Business event signals.
Connect your CPA platform events to the messaging system.

Usage in your offer/payout/affiliate modules:

    from messaging.signals_cpa import (
        offer_status_changed,
        conversion_received,
        payout_processed,
        affiliate_status_changed,
    )

    # In your offer approval view:
    offer_status_changed.send(sender=Offer, offer=offer_obj, new_status="approved")
"""
from django.dispatch import Signal

# ── Offer Signals ─────────────────────────────────────────────────────────────

# Fired when an offer's approval status changes.
# kwargs: offer_id, offer_name, affiliate_id, new_status (approved/rejected/paused/reactivated),
#         reason (str, optional), payout (str, optional)
offer_status_changed = Signal()

# Fired when a new offer is published and available to affiliates.
# kwargs: offer_id, offer_name, vertical, payout, countries (list)
new_offer_published = Signal()

# Fired when an offer is expiring soon (e.g., 24h left).
# kwargs: offer_id, offer_name, expires_at, affiliate_ids (list)
offer_expiring_soon = Signal()

# ── Conversion Signals ────────────────────────────────────────────────────────

# Fired when a new conversion/lead is received.
# kwargs: conversion_id, affiliate_id, offer_id, offer_name, payout_amount
conversion_received = Signal()

# Fired when a conversion is approved/rejected/reversed.
# kwargs: conversion_id, affiliate_id, offer_name, payout_amount, new_status, reason
conversion_status_changed = Signal()

# Fired when a postback delivery fails.
# kwargs: affiliate_id, offer_id, offer_name, error_detail
postback_failed = Signal()

# ── Payout Signals ────────────────────────────────────────────────────────────

# Fired when a payout is processed and sent.
# kwargs: payout_id, affiliate_id, amount, payment_method, transaction_id, expected_date
payout_processed = Signal()

# Fired when affiliate balance hits minimum payout threshold.
# kwargs: affiliate_id, current_balance, threshold, next_payout_date
payout_threshold_reached = Signal()

# Fired when a payout is placed on hold.
# kwargs: payout_id, affiliate_id, amount, reason
payout_on_hold = Signal()

# Fired when a payout fails.
# kwargs: payout_id, affiliate_id, amount, error
payout_failed = Signal()

# ── Affiliate Account Signals ─────────────────────────────────────────────────

# Fired when affiliate account status changes.
# kwargs: affiliate_id, affiliate_name, new_status (approved/rejected/suspended/reinstated/banned),
#         reason (str, optional), manager_name (str, optional)
affiliate_status_changed = Signal()

# Fired when an account manager is assigned to an affiliate.
# kwargs: affiliate_id, manager_id, manager_name, manager_email
manager_assigned = Signal()

# Fired when fraud is detected on an affiliate account.
# kwargs: affiliate_id, offer_id, offer_name, details
fraud_detected = Signal()

# ── Performance Signals ───────────────────────────────────────────────────────

# Fired when affiliate reaches a performance milestone.
# kwargs: affiliate_id, milestone_type, milestone_value, reward (optional)
milestone_reached = Signal()

# Fired when affiliate's EPC drops significantly.
# kwargs: affiliate_id, offer_id, offer_name, old_epc, new_epc, drop_percent
epc_dropped = Signal()
