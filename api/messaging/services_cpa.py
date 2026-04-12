"""
CPA Messaging Services — CPAlead-style business event notification engine.

This module connects business events (offer approved, payout processed,
conversion received) to the messaging system automatically.

Usage from other modules:
    from messaging.services_cpa import (
        notify_offer_approved,
        notify_conversion_received,
        notify_payout_processed,
        send_cpa_broadcast,
    )

Design principles:
- Every business event triggers the right notification automatically
- Non-blocking: all heavy work is offloaded to Celery
- Idempotent: safe to call multiple times (no duplicate messages)
- Auditable: every notification is stored in CPANotification
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F as _F
from django.utils import timezone

from .models import (
    CPANotification, CPABroadcast, MessageTemplate,
    AffiliateConversationThread, InternalChat, ChatParticipant,
    UserInbox,
)
from .choices import (
    CPANotificationType, CPABroadcastAudienceFilter,
    NotificationPriority, MessageTemplateCategory,
    InboxItemType, ParticipantRole,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _create_notification(
    *,
    recipient_id: Any,
    notification_type: str,
    title: str,
    body: str,
    priority: str = "NORMAL",
    object_type: str = "",
    object_id: str = "",
    action_url: str = "",
    action_label: str = "",
    payload: Optional[dict] = None,
    tenant=None,
) -> CPANotification:
    """Create a CPANotification and queue push delivery."""
    notif = CPANotification.objects.create(
        recipient_id=recipient_id,
        notification_type=notification_type,
        title=title,
        body=body,
        priority=priority,
        object_type=object_type,
        object_id=str(object_id),
        action_url=action_url,
        action_label=action_label,
        payload=payload or {},
        tenant=tenant,
    )
    # Queue push delivery based on priority
    from .tasks_cpa import deliver_cpa_notification_task
    deliver_cpa_notification_task.delay(str(notif.id))
    return notif


def _get_affiliate_manager_id(affiliate_id: Any) -> Optional[Any]:
    """
    Get account manager for an affiliate.
    Looks up AffiliateConversationThread or falls back to staff user.
    Integrate with your affiliate management module here.
    """
    try:
        thread = AffiliateConversationThread.objects.get(affiliate_id=affiliate_id)
        return thread.manager_id
    except AffiliateConversationThread.DoesNotExist:
        pass
    # Fallback: use tenant admin or first superuser
    from django.contrib.auth import get_user_model
    User = get_user_model()
    admin = User.objects.filter(is_superuser=True).values_list("pk", flat=True).first()
    return admin


# ---------------------------------------------------------------------------
# Offer Event Notifications
# ---------------------------------------------------------------------------

def notify_offer_approved(
    *,
    affiliate_id: Any,
    offer_id: Any,
    offer_name: str,
    offer_payout: str = "",
    offer_url: str = "",
    tenant=None,
) -> CPANotification:
    """
    Notify affiliate that their offer application was approved.
    Called from your offer approval logic.
    """
    notif = _create_notification(
        recipient_id=affiliate_id,
        notification_type=CPANotificationType.OFFER_APPROVED,
        title=f"Offer Approved: {offer_name}",
        body=(
            f"Congratulations! Your application for \"{offer_name}\" has been approved. "
            f"{'Payout: ' + offer_payout + '. ' if offer_payout else ''}"
            f"You can now start running this offer."
        ),
        priority=NotificationPriority.HIGH,
        object_type="offer",
        object_id=str(offer_id),
        action_url=offer_url or f"/offers/{offer_id}/",
        action_label="View Offer",
        payload={"offer_id": str(offer_id), "offer_name": offer_name, "payout": offer_payout},
        tenant=tenant,
    )
    logger.info("notify_offer_approved: affiliate=%s offer=%s", affiliate_id, offer_id)
    return notif


def notify_offer_rejected(
    *,
    affiliate_id: Any,
    offer_id: Any,
    offer_name: str,
    reason: str = "",
    tenant=None,
) -> CPANotification:
    """Notify affiliate that their offer application was rejected."""
    body = f'Your application for "{offer_name}" was not approved.'
    if reason:
        body += f" Reason: {reason}"
    body += " You may apply for other offers or contact your account manager."

    return _create_notification(
        recipient_id=affiliate_id,
        notification_type=CPANotificationType.OFFER_REJECTED,
        title=f"Offer Application Declined: {offer_name}",
        body=body,
        priority=NotificationPriority.NORMAL,
        object_type="offer",
        object_id=str(offer_id),
        action_url="/offers/",
        action_label="Browse Offers",
        payload={"offer_id": str(offer_id), "offer_name": offer_name, "reason": reason},
        tenant=tenant,
    )


def notify_offer_paused(
    *,
    offer_id: Any,
    offer_name: str,
    reason: str = "Daily cap reached",
    tenant=None,
) -> int:
    """
    Notify ALL affiliates currently running this offer that it's been paused.
    Returns count of notifications sent.
    Called when an offer hits its cap or is manually paused.
    """
    # Get all affiliates running this offer
    # Integrate with your offer/affiliate relationship model
    affiliate_ids = _get_affiliates_running_offer(offer_id)
    count = 0
    for aff_id in affiliate_ids:
        _create_notification(
            recipient_id=aff_id,
            notification_type=CPANotificationType.OFFER_PAUSED,
            title=f"Offer Paused: {offer_name}",
            body=(
                f'"{offer_name}" has been temporarily paused. '
                f'Reason: {reason}. '
                f"Please pause your traffic until the offer is reactivated."
            ),
            priority=NotificationPriority.HIGH,
            object_type="offer",
            object_id=str(offer_id),
            action_url=f"/offers/{offer_id}/",
            action_label="View Offer",
            payload={"offer_id": str(offer_id), "offer_name": offer_name, "reason": reason},
            tenant=tenant,
        )
        count += 1
    logger.info("notify_offer_paused: offer=%s notified %d affiliates", offer_id, count)
    return count


def notify_new_offer_available(
    *,
    offer_id: Any,
    offer_name: str,
    vertical: str = "",
    payout: str = "",
    countries: list = None,
    target_audience: str = "all",
    tenant=None,
) -> int:
    """
    Notify relevant affiliates about a new offer.
    Targets affiliates based on vertical/GEO match.
    """
    affiliate_ids = _get_relevant_affiliates_for_offer(
        vertical=vertical, countries=countries or [], audience=target_audience
    )
    count = 0
    for aff_id in affiliate_ids:
        _create_notification(
            recipient_id=aff_id,
            notification_type=CPANotificationType.NEW_OFFER_AVAILABLE,
            title=f"New Offer Available: {offer_name}",
            body=(
                f"A new offer matching your profile is now available: \"{offer_name}\". "
                f"{'Payout: ' + payout + '. ' if payout else ''}"
                f"{'Geo: ' + ', '.join(countries) + '. ' if countries else ''}"
                f"Apply now to start earning!"
            ),
            priority=NotificationPriority.NORMAL,
            object_type="offer",
            object_id=str(offer_id),
            action_url=f"/offers/{offer_id}/",
            action_label="Apply Now",
            payload={
                "offer_id": str(offer_id),
                "offer_name": offer_name,
                "payout": payout,
                "vertical": vertical,
                "countries": countries or [],
            },
            tenant=tenant,
        )
        count += 1
    logger.info("notify_new_offer_available: offer=%s notified %d affiliates", offer_id, count)
    return count


# ---------------------------------------------------------------------------
# Conversion Event Notifications
# ---------------------------------------------------------------------------

def notify_conversion_received(
    *,
    affiliate_id: Any,
    conversion_id: Any,
    offer_name: str,
    payout_amount: str,
    lead_ip: str = "",
    tenant=None,
) -> CPANotification:
    """
    Real-time notification when a new conversion is received.
    This fires immediately when the postback fires.
    """
    return _create_notification(
        recipient_id=affiliate_id,
        notification_type=CPANotificationType.CONVERSION_RECEIVED,
        title=f"New Conversion: {offer_name}",
        body=f"You earned {payout_amount} from a new conversion on \"{offer_name}\".",
        priority=NotificationPriority.HIGH,
        object_type="conversion",
        object_id=str(conversion_id),
        action_url="/stats/conversions/",
        action_label="View Stats",
        payload={
            "conversion_id": str(conversion_id),
            "offer_name": offer_name,
            "payout_amount": payout_amount,
        },
        tenant=tenant,
    )


def notify_conversion_rejected(
    *,
    affiliate_id: Any,
    conversion_id: Any,
    offer_name: str,
    payout_amount: str,
    reason: str = "",
    tenant=None,
) -> CPANotification:
    """Notify affiliate when a conversion is rejected/reversed."""
    body = f'A conversion on "{offer_name}" (value: {payout_amount}) has been rejected.'
    if reason:
        body += f" Reason: {reason}."

    return _create_notification(
        recipient_id=affiliate_id,
        notification_type=CPANotificationType.CONVERSION_REJECTED,
        title=f"Conversion Rejected: {offer_name}",
        body=body,
        priority=NotificationPriority.HIGH,
        object_type="conversion",
        object_id=str(conversion_id),
        action_url="/stats/conversions/",
        action_label="View Details",
        payload={
            "conversion_id": str(conversion_id),
            "offer_name": offer_name,
            "payout_amount": payout_amount,
            "reason": reason,
        },
        tenant=tenant,
    )


def notify_postback_failed(
    *,
    affiliate_id: Any,
    offer_id: Any,
    offer_name: str,
    error_detail: str = "",
    tenant=None,
) -> CPANotification:
    """Notify affiliate when their postback URL is failing."""
    return _create_notification(
        recipient_id=affiliate_id,
        notification_type=CPANotificationType.POSTBACK_FAILED,
        title=f"Postback Delivery Failed: {offer_name}",
        body=(
            f"We're unable to deliver conversions to your postback URL for \"{offer_name}\". "
            f"{'Error: ' + error_detail + '. ' if error_detail else ''}"
            f"Please check your postback URL settings immediately."
        ),
        priority=NotificationPriority.URGENT,
        object_type="offer",
        object_id=str(offer_id),
        action_url="/account/postback/",
        action_label="Fix Postback",
        payload={"offer_id": str(offer_id), "offer_name": offer_name, "error": error_detail},
        tenant=tenant,
    )


# ---------------------------------------------------------------------------
# Payout Event Notifications
# ---------------------------------------------------------------------------

def notify_payout_processed(
    *,
    affiliate_id: Any,
    payout_id: Any,
    amount: str,
    payment_method: str = "",
    transaction_id: str = "",
    expected_date: str = "",
    tenant=None,
) -> CPANotification:
    """Notify affiliate that their payment has been processed."""
    body = f"Your payout of {amount} has been processed."
    if payment_method:
        body += f" Payment method: {payment_method}."
    if transaction_id:
        body += f" Transaction ID: {transaction_id}."
    if expected_date:
        body += f" Expected arrival: {expected_date}."

    return _create_notification(
        recipient_id=affiliate_id,
        notification_type=CPANotificationType.PAYOUT_PROCESSED,
        title=f"Payment Sent: {amount}",
        body=body,
        priority=NotificationPriority.HIGH,
        object_type="payout",
        object_id=str(payout_id),
        action_url="/account/payments/",
        action_label="View Payment",
        payload={
            "payout_id": str(payout_id),
            "amount": amount,
            "payment_method": payment_method,
            "transaction_id": transaction_id,
        },
        tenant=tenant,
    )


def notify_payout_threshold_met(
    *,
    affiliate_id: Any,
    current_balance: str,
    threshold: str,
    next_payout_date: str = "",
    tenant=None,
) -> CPANotification:
    """Notify affiliate when they hit the minimum payout threshold."""
    return _create_notification(
        recipient_id=affiliate_id,
        notification_type=CPANotificationType.PAYOUT_THRESHOLD_MET,
        title=f"Payout Threshold Reached: {current_balance}",
        body=(
            f"Your balance ({current_balance}) has reached the minimum payout threshold ({threshold}). "
            f"{'Your next payout is scheduled for ' + next_payout_date + '.' if next_payout_date else 'You will receive payment on the next payment cycle.'}"
        ),
        priority=NotificationPriority.NORMAL,
        object_type="payout",
        object_id="",
        action_url="/account/payments/",
        action_label="View Balance",
        payload={"balance": current_balance, "threshold": threshold, "next_date": next_payout_date},
        tenant=tenant,
    )


def notify_payout_pending_reminder(
    *,
    affiliate_id: Any,
    amount: str,
    payout_date: str,
    tenant=None,
) -> CPANotification:
    """Send reminder day before payout. Called by Celery beat task."""
    return _create_notification(
        recipient_id=affiliate_id,
        notification_type=CPANotificationType.PAYOUT_PENDING_REMINDER,
        title=f"Payment Due Tomorrow: {amount}",
        body=f"Your payment of {amount} is scheduled for tomorrow ({payout_date}). Please ensure your payment details are up to date.",
        priority=NotificationPriority.NORMAL,
        object_type="payout",
        object_id="",
        action_url="/account/payment-methods/",
        action_label="Check Payment Details",
        payload={"amount": amount, "payout_date": payout_date},
        tenant=tenant,
    )


def notify_payout_on_hold(
    *,
    affiliate_id: Any,
    payout_id: Any,
    amount: str,
    reason: str = "",
    tenant=None,
) -> CPANotification:
    """Notify affiliate their payout has been put on hold."""
    body = f"Your payout of {amount} has been placed on hold."
    if reason:
        body += f" Reason: {reason}."
    body += " Please contact your account manager for more information."

    return _create_notification(
        recipient_id=affiliate_id,
        notification_type=CPANotificationType.PAYOUT_ON_HOLD,
        title=f"Payout On Hold: {amount}",
        body=body,
        priority=NotificationPriority.URGENT,
        object_type="payout",
        object_id=str(payout_id),
        action_url="/support/",
        action_label="Contact Support",
        payload={"payout_id": str(payout_id), "amount": amount, "reason": reason},
        tenant=tenant,
    )


# ---------------------------------------------------------------------------
# Account Status Notifications
# ---------------------------------------------------------------------------

def notify_affiliate_approved(
    *,
    affiliate_id: Any,
    affiliate_name: str,
    manager_name: str = "",
    welcome_bonus: str = "",
    tenant=None,
) -> CPANotification:
    """Welcome message when affiliate account is approved."""
    body = f"Welcome to the platform, {affiliate_name}! Your affiliate account has been approved."
    if welcome_bonus:
        body += f" As a welcome gift, you have received {welcome_bonus}."
    if manager_name:
        body += f" Your dedicated account manager is {manager_name}."
    body += " Start browsing offers and earning today!"

    notif = _create_notification(
        recipient_id=affiliate_id,
        notification_type=CPANotificationType.AFFILIATE_APPROVED,
        title="Welcome! Your Account is Approved",
        body=body,
        priority=NotificationPriority.HIGH,
        object_type="affiliate",
        object_id=str(affiliate_id),
        action_url="/offers/",
        action_label="Browse Offers",
        payload={
            "affiliate_name": affiliate_name,
            "manager_name": manager_name,
            "welcome_bonus": welcome_bonus,
        },
        tenant=tenant,
    )

    # Also create affiliate ↔ manager conversation thread
    if manager_name:
        _create_affiliate_manager_thread(
            affiliate_id=affiliate_id,
            manager_name=manager_name,
            tenant=tenant,
        )

    return notif


def notify_affiliate_suspended(
    *,
    affiliate_id: Any,
    reason: str = "",
    duration: str = "",
    appeal_url: str = "/appeal/",
    tenant=None,
) -> CPANotification:
    """Notify affiliate their account has been suspended."""
    body = "Your affiliate account has been temporarily suspended."
    if reason:
        body += f" Reason: {reason}."
    if duration:
        body += f" Duration: {duration}."
    body += " You may appeal this decision."

    return _create_notification(
        recipient_id=affiliate_id,
        notification_type=CPANotificationType.AFFILIATE_SUSPENDED,
        title="Account Suspended",
        body=body,
        priority=NotificationPriority.URGENT,
        object_type="affiliate",
        object_id=str(affiliate_id),
        action_url=appeal_url,
        action_label="Appeal Decision",
        payload={"reason": reason, "duration": duration},
        tenant=tenant,
    )


def notify_manager_assigned(
    *,
    affiliate_id: Any,
    manager_id: Any,
    manager_name: str,
    manager_email: str = "",
    tenant=None,
) -> CPANotification:
    """Notify affiliate when a new account manager is assigned."""
    # Update or create affiliate thread
    _ensure_affiliate_manager_thread(
        affiliate_id=affiliate_id,
        manager_id=manager_id,
        tenant=tenant,
    )

    return _create_notification(
        recipient_id=affiliate_id,
        notification_type=CPANotificationType.MANAGER_ASSIGNED,
        title=f"New Account Manager: {manager_name}",
        body=(
            f"Your dedicated account manager is now {manager_name}. "
            f"{'You can reach them at ' + manager_email + '.' if manager_email else ''} "
            f"Feel free to reach out with any questions."
        ),
        priority=NotificationPriority.NORMAL,
        object_type="manager",
        object_id=str(manager_id),
        action_url="/messages/",
        action_label="Send Message",
        payload={"manager_id": str(manager_id), "manager_name": manager_name, "manager_email": manager_email},
        tenant=tenant,
    )


def notify_fraud_alert(
    *,
    affiliate_id: Any,
    offer_id: Any,
    offer_name: str,
    details: str = "",
    tenant=None,
) -> CPANotification:
    """Warn affiliate about suspicious/fraudulent traffic patterns."""
    return _create_notification(
        recipient_id=affiliate_id,
        notification_type=CPANotificationType.FRAUD_ALERT,
        title="Traffic Quality Warning",
        body=(
            f"We've detected unusual traffic patterns on your campaign for \"{offer_name}\". "
            f"{details + ' ' if details else ''}"
            f"Please review your traffic sources immediately to avoid account suspension."
        ),
        priority=NotificationPriority.URGENT,
        object_type="offer",
        object_id=str(offer_id),
        action_url="/account/traffic-quality/",
        action_label="Review Traffic",
        payload={"offer_id": str(offer_id), "offer_name": offer_name, "details": details},
        tenant=tenant,
    )


# ---------------------------------------------------------------------------
# Performance Milestone Notifications
# ---------------------------------------------------------------------------

def notify_milestone_reached(
    *,
    affiliate_id: Any,
    milestone_type: str,
    milestone_value: str,
    reward: str = "",
    tenant=None,
) -> CPANotification:
    """
    Celebrate performance milestones.
    milestone_type: 'first_conversion', 'first_$100', 'first_$1000', 'top_performer', etc.
    """
    MILESTONE_MESSAGES = {
        "first_conversion": "You earned your first conversion! Keep up the great work.",
        "first_100":        "You've crossed $100 in earnings! You're on your way.",
        "first_1000":       "Amazing! You've reached $1,000 in lifetime earnings.",
        "top_performer":    "You're in the top 10% of affiliates this month!",
        "custom":           f"You've reached {milestone_value}!",
    }
    body = MILESTONE_MESSAGES.get(milestone_type, f"You've reached {milestone_value}!")
    if reward:
        body += f" You've been awarded: {reward}."

    return _create_notification(
        recipient_id=affiliate_id,
        notification_type=CPANotificationType.MILESTONE_REACHED,
        title=f"Milestone Reached: {milestone_value}",
        body=body,
        priority=NotificationPriority.HIGH,
        object_type="milestone",
        object_id=milestone_type,
        action_url="/stats/",
        action_label="View Stats",
        payload={
            "milestone_type": milestone_type,
            "milestone_value": milestone_value,
            "reward": reward,
        },
        tenant=tenant,
    )


# ---------------------------------------------------------------------------
# CPA Broadcast Services
# ---------------------------------------------------------------------------

@transaction.atomic
def send_cpa_broadcast(
    *,
    title: str,
    body: str,
    audience_filter: str = "all",
    audience_params: Optional[dict] = None,
    notification_type: str = CPANotificationType.SYSTEM_ANNOUNCEMENT,
    priority: str = "NORMAL",
    send_push: bool = True,
    send_email: bool = False,
    send_inbox: bool = True,
    action_url: str = "",
    action_label: str = "",
    template_id: Optional[Any] = None,
    created_by_id: Optional[Any] = None,
    scheduled_at=None,
    tenant=None,
) -> CPABroadcast:
    """
    Send a targeted broadcast to CPA platform affiliates.
    Audience can be filtered by offer, vertical, GEO, tier, etc.
    """
    broadcast = CPABroadcast.objects.create(
        title=title,
        body=body,
        notification_type=notification_type,
        priority=priority,
        audience_filter=audience_filter,
        audience_params=audience_params or {},
        send_push=send_push,
        send_email=send_email,
        send_inbox=send_inbox,
        action_url=action_url,
        action_label=action_label,
        template_id=template_id,
        created_by_id=created_by_id,
        scheduled_at=scheduled_at,
        status="DRAFT",
        tenant=tenant,
    )

    if not scheduled_at:
        from .tasks_cpa import send_cpa_broadcast_task
        send_cpa_broadcast_task.delay(str(broadcast.id))
    else:
        broadcast.status = "SCHEDULED"
        CPABroadcast.objects.filter(pk=broadcast.pk).update(status="SCHEDULED")

    logger.info("send_cpa_broadcast: id=%s audience=%s", broadcast.id, audience_filter)
    return broadcast


def _resolve_cpa_broadcast_audience(broadcast: CPABroadcast) -> list:
    """
    Resolve the target audience based on broadcast.audience_filter.
    Integrates with your affiliate management system.
    Returns list of user PKs.
    """
    params = broadcast.audience_params or {}

    if broadcast.audience_filter == CPABroadcastAudienceFilter.ALL_AFFILIATES:
        return _get_all_affiliate_ids()

    elif broadcast.audience_filter == CPABroadcastAudienceFilter.BY_OFFER:
        offer_id = params.get("offer_id")
        return _get_affiliates_running_offer(offer_id) if offer_id else []

    elif broadcast.audience_filter == CPABroadcastAudienceFilter.BY_VERTICAL:
        vertical = params.get("vertical", "")
        return _get_affiliates_by_vertical(vertical)

    elif broadcast.audience_filter == CPABroadcastAudienceFilter.BY_COUNTRY:
        country = params.get("country", "")
        return _get_affiliates_by_country(country)

    elif broadcast.audience_filter == CPABroadcastAudienceFilter.BY_MANAGER:
        manager_id = params.get("manager_id")
        if manager_id:
            return list(
                AffiliateConversationThread.objects.filter(manager_id=manager_id)
                .values_list("affiliate_id", flat=True)
            )

    elif broadcast.audience_filter == CPABroadcastAudienceFilter.NEW_AFFILIATES:
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=30)
        return list(User.objects.filter(date_joined__gte=cutoff).values_list("pk", flat=True))

    elif broadcast.audience_filter == CPABroadcastAudienceFilter.BY_TIER:
        tier = params.get("tier", "")
        return _get_affiliates_by_tier(tier)

    return _get_all_affiliate_ids()


# ---------------------------------------------------------------------------
# Message Template Services
# ---------------------------------------------------------------------------

def create_template(
    *,
    name: str,
    body: str,
    subject: str = "",
    category: str = "custom",
    tags: list = None,
    created_by_id: Optional[Any] = None,
    tenant=None,
) -> MessageTemplate:
    return MessageTemplate.objects.create(
        name=name,
        body=body,
        subject=subject,
        category=category,
        tags=tags or [],
        created_by_id=created_by_id,
        tenant=tenant,
    )


def send_from_template(
    *,
    template_id: Any,
    recipient_id: Any,
    context: dict,
    priority: str = "NORMAL",
    tenant=None,
) -> CPANotification:
    """Send a notification using a saved template with variable substitution."""
    try:
        template = MessageTemplate.objects.get(pk=template_id)
    except MessageTemplate.DoesNotExist:
        raise ValueError(f"MessageTemplate {template_id} not found.")

    rendered_subject, rendered_body = template.render(context)

    return _create_notification(
        recipient_id=recipient_id,
        notification_type="system.announcement",
        title=rendered_subject,
        body=rendered_body,
        priority=priority,
        tenant=tenant,
    )


# ---------------------------------------------------------------------------
# Affiliate ↔ Manager Thread Services
# ---------------------------------------------------------------------------

@transaction.atomic
def get_or_create_affiliate_thread(
    *,
    affiliate_id: Any,
    manager_id: Any = None,
    tenant=None,
) -> AffiliateConversationThread:
    """
    Get or create the dedicated conversation thread between an affiliate and manager.
    Creates the underlying InternalChat if it doesn't exist.
    """
    from . import services as msg_services

    try:
        return AffiliateConversationThread.objects.get(affiliate_id=affiliate_id)
    except AffiliateConversationThread.DoesNotExist:
        pass

    # Get or create the underlying chat
    if manager_id:
        chat = msg_services.create_direct_chat(affiliate_id, manager_id)
    else:
        # Create a chat with no manager yet (admin will be assigned later)
        chat = msg_services.create_group_chat(
            creator_id=affiliate_id,
            name=f"Support Thread — {affiliate_id}",
            member_ids=[],
        )

    thread = AffiliateConversationThread.objects.create(
        affiliate_id=affiliate_id,
        manager_id=manager_id,
        chat=chat,
        tenant=tenant,
    )
    logger.info("get_or_create_affiliate_thread: affiliate=%s manager=%s", affiliate_id, manager_id)
    return thread


def reassign_affiliate_manager(
    *,
    affiliate_id: Any,
    new_manager_id: Any,
    notify: bool = True,
    tenant=None,
) -> AffiliateConversationThread:
    """Transfer an affiliate to a new account manager."""
    try:
        thread = AffiliateConversationThread.objects.get(affiliate_id=affiliate_id)
    except AffiliateConversationThread.DoesNotExist:
        thread = get_or_create_affiliate_thread(
            affiliate_id=affiliate_id, manager_id=new_manager_id, tenant=tenant
        )

    old_manager_id = thread.manager_id
    AffiliateConversationThread.objects.filter(pk=thread.pk).update(
        manager_id=new_manager_id
    )
    thread.manager_id = new_manager_id

    if notify:
        try:
            manager = User.objects.get(pk=new_manager_id)
            manager_name = manager.get_full_name() or manager.username
            manager_email = manager.email
        except User.DoesNotExist:
            manager_name = str(new_manager_id)
            manager_email = ""

        notify_manager_assigned(
            affiliate_id=affiliate_id,
            manager_id=new_manager_id,
            manager_name=manager_name,
            manager_email=manager_email,
            tenant=tenant,
        )

    logger.info("reassign_affiliate_manager: affiliate=%s old=%s new=%s",
                affiliate_id, old_manager_id, new_manager_id)
    return thread


# ---------------------------------------------------------------------------
# Notification Read / Analytics Services
# ---------------------------------------------------------------------------

def mark_notification_read(notification_id: Any, user_id: Any) -> bool:
    """Mark a CPA notification as read."""
    updated = CPANotification.objects.filter(
        pk=notification_id, recipient_id=user_id
    ).update(is_read=True, read_at=timezone.now())
    return updated > 0


def mark_all_notifications_read(user_id: Any, notification_type: str = None) -> int:
    """Mark all (or all of a type) notifications as read."""
    qs = CPANotification.objects.filter(recipient_id=user_id, is_read=False)
    if notification_type:
        qs = qs.filter(notification_type=notification_type)
    return qs.update(is_read=True, read_at=timezone.now())


def get_unread_notification_counts(user_id: Any) -> dict:
    """
    Get unread count broken down by category.
    Used for the CPAlead-style smart inbox tab badges.
    """
    from django.db.models import Count, Case, When, IntegerField

    qs = CPANotification.objects.filter(recipient_id=user_id, is_read=False)

    # Group by category
    CATEGORIES = {
        "offers":      ["offer.approved", "offer.rejected", "offer.paused", "offer.new", "offer.expiring"],
        "conversions": ["conversion.received", "conversion.approved", "conversion.rejected", "postback.failed"],
        "payments":    ["payout.processed", "payout.reminder", "payout.threshold", "payout.failed", "payout.hold"],
        "account":     ["affiliate.approved", "affiliate.rejected", "affiliate.suspended",
                        "affiliate.reinstated", "affiliate.banned", "affiliate.manager"],
        "system":      ["system.maintenance", "system.announcement", "api.key_expiring", "terms.updated"],
        "performance": ["milestone.reached", "epc.drop", "fraud.alert"],
    }

    counts = {"total": qs.count()}
    for cat, types in CATEGORIES.items():
        counts[cat] = qs.filter(notification_type__in=types).count()

    return counts


def track_broadcast_open(broadcast_id: Any, user_id: Any) -> bool:
    """Track when a user opens/views a CPA broadcast. Updates open rate analytics."""
    from .models import NotificationRead
    _, created = NotificationRead.objects.get_or_create(
        broadcast_id=broadcast_id,
        user_id=user_id,
    )
    if created:
        CPABroadcast.objects.filter(pk=broadcast_id).update(
            opened_count=_F("opened_count") + 1
        )
    return created


def track_broadcast_click(broadcast_id: Any, user_id: Any) -> bool:
    """Track CTA button click on a broadcast."""
    from .models import NotificationRead
    now = timezone.now()
    updated = NotificationRead.objects.filter(
        broadcast_id=broadcast_id, user_id=user_id, clicked_at__isnull=True
    ).update(clicked_at=now)
    if updated:
        CPABroadcast.objects.filter(pk=broadcast_id).update(
            clicked_count=_F("clicked_count") + 1
        )
    return bool(updated)


# ---------------------------------------------------------------------------
# Stub helpers — integrate with your affiliate management module
# ---------------------------------------------------------------------------

def _get_all_affiliate_ids() -> list:
    """Get all active affiliate user IDs. Integrate with your affiliate model."""
    return list(User.objects.filter(is_active=True).values_list("pk", flat=True))


def _get_affiliates_running_offer(offer_id: Any) -> list:
    """
    Get affiliate IDs currently running a specific offer.
    Integrate with your OfferApplication/AffiliateOffer model.
    Example:
        from api.ad_networks.models import UserOfferEngagement
        return list(UserOfferEngagement.objects.filter(
            offer_id=offer_id, status='approved'
        ).values_list('user_id', flat=True))
    """
    logger.debug("_get_affiliates_running_offer: offer=%s (stub — integrate with your offer model)", offer_id)
    return []


def _get_relevant_affiliates_for_offer(vertical: str, countries: list, audience: str) -> list:
    """
    Get affiliates relevant for a new offer based on their profile.
    Integrate with your affiliate profile model.
    """
    logger.debug("_get_relevant_affiliates_for_offer: vertical=%s countries=%s", vertical, countries)
    return list(User.objects.filter(is_active=True).values_list("pk", flat=True)[:1000])


def _get_affiliates_by_vertical(vertical: str) -> list:
    logger.debug("_get_affiliates_by_vertical: vertical=%s (stub)", vertical)
    return list(User.objects.filter(is_active=True).values_list("pk", flat=True))


def _get_affiliates_by_country(country: str) -> list:
    logger.debug("_get_affiliates_by_country: country=%s (stub)", country)
    return list(User.objects.filter(is_active=True).values_list("pk", flat=True))


def _get_affiliates_by_tier(tier: str) -> list:
    logger.debug("_get_affiliates_by_tier: tier=%s (stub)", tier)
    return list(User.objects.filter(is_active=True).values_list("pk", flat=True))


def _create_affiliate_manager_thread(affiliate_id: Any, manager_name: str, tenant=None) -> None:
    """Create initial welcome DM from manager to affiliate."""
    try:
        manager = User.objects.filter(
            is_staff=True
        ).first()
        if manager:
            get_or_create_affiliate_thread(
                affiliate_id=affiliate_id,
                manager_id=manager.pk,
                tenant=tenant,
            )
    except Exception as exc:
        logger.warning("_create_affiliate_manager_thread: failed: %s", exc)


def _ensure_affiliate_manager_thread(affiliate_id: Any, manager_id: Any, tenant=None) -> None:
    try:
        get_or_create_affiliate_thread(
            affiliate_id=affiliate_id, manager_id=manager_id, tenant=tenant
        )
    except Exception as exc:
        logger.warning("_ensure_affiliate_manager_thread: failed: %s", exc)
