# earning_backend/api/notifications/events.py
"""
Events — Custom Django Signal definitions and EventBus event constants
for the notification system.

Two complementary systems:

1. DJANGO SIGNALS (synchronous, in-process):
   Used for tight coupling within the notifications app itself.
   e.g. notification_sent, notification_failed, notification_read

2. EVENTBUS EVENTS (async, cross-module, Celery-backed):
   Used for loose coupling between modules.
   e.g. task.approved → send notification
   Defined as string constants matching integration_system/integ_constants.py

Usage:
    from api.notifications.events import (
        notification_sent,       # Django Signal
        notification_read,       # Django Signal
        NotifEvents,             # EventBus event name constants
    )

    # Emit a Django signal
    notification_sent.send(sender=Notification, instance=notif, channel='push')

    # Publish to EventBus
    from api.notifications.integration_system.event_bus import event_bus
    event_bus.publish(NotifEvents.SENT, data={'notification_id': notif.pk})
"""

from django.dispatch import Signal


# ---------------------------------------------------------------------------
# Django Signals — Notification lifecycle
# ---------------------------------------------------------------------------

# Fired after a notification is successfully sent to its channel
notification_sent = Signal()
# Provides: instance (Notification), channel (str), result (dict)

# Fired after a notification delivery is confirmed by provider
notification_delivered = Signal()
# Provides: instance (Notification), channel (str), provider (str)

# Fired when a user reads a notification
notification_read = Signal()
# Provides: instance (Notification), user

# Fired when a user clicks a notification's CTA
notification_clicked = Signal()
# Provides: instance (Notification), user, url (str)

# Fired when a notification send fails after all retries
notification_failed = Signal()
# Provides: instance (Notification), channel (str), error (str), attempts (int)

# Fired when a notification is soft-deleted
notification_deleted = Signal()
# Provides: instance (Notification), deleted_by (User)

# Fired when a notification is archived
notification_archived = Signal()
# Provides: instance (Notification)

# Fired when a notification expires (TTL reached)
notification_expired = Signal()
# Provides: instance (Notification)


# ---------------------------------------------------------------------------
# Django Signals — Device / Token lifecycle
# ---------------------------------------------------------------------------

# Fired when a push device token is registered
device_token_registered = Signal()
# Provides: device (DeviceToken), user, is_new (bool)

# Fired when a push device token is deactivated/removed
device_token_deactivated = Signal()
# Provides: device (DeviceToken), reason (str)

# Fired when FCM/APNs reports a token as invalid
push_token_invalid = Signal()
# Provides: token (str), provider (str: 'fcm'|'apns'), device (DeviceToken|None)


# ---------------------------------------------------------------------------
# Django Signals — Campaign lifecycle
# ---------------------------------------------------------------------------

# Fired when a campaign starts processing
campaign_started = Signal()
# Provides: campaign (NotificationCampaign), total_users (int)

# Fired when a campaign finishes
campaign_completed = Signal()
# Provides: campaign (NotificationCampaign), sent_count (int), failed_count (int)

# Fired when a campaign is cancelled
campaign_cancelled = Signal()
# Provides: campaign (NotificationCampaign), cancelled_by (User)

# Fired when A/B test winner is determined
ab_test_winner_determined = Signal()
# Provides: ab_test (CampaignABTest), winner (str: 'a'|'b'), winning_metric (str)


# ---------------------------------------------------------------------------
# Django Signals — User preference / opt-out
# ---------------------------------------------------------------------------

# Fired when user opts out of a channel
user_opted_out = Signal()
# Provides: user, channel (str), reason (str)

# Fired when user re-subscribes
user_resubscribed = Signal()
# Provides: user, channel (str)

# Fired when fatigue threshold is reached
fatigue_threshold_reached = Signal()
# Provides: user, sent_today (int), daily_limit (int)


# ---------------------------------------------------------------------------
# Django Signals — Integration system
# ---------------------------------------------------------------------------

# Fired when an integration event is published
integration_event = Signal()
# Provides: event_type (str), data (dict), user_id (int|None), source_module (str)

# Fired when an integration operation fails
integration_error = Signal()
# Provides: integration (str), error (str), user_id (int|None)

# Fired when a health check status changes
health_status_changed = Signal()
# Provides: service (str), old_status (str), new_status (str)

# Fired when a webhook is received
webhook_received = Signal()
# Provides: provider (str), event_type (str), payload (dict)


# ---------------------------------------------------------------------------
# EventBus event name constants
# ---------------------------------------------------------------------------

class NotifEvents:
    """
    String constants for EventBus event names related to notifications.
    Use these when publishing/subscribing on the EventBus to avoid typos.

    Usage:
        from api.notifications.events import NotifEvents
        from api.notifications.integration_system.event_bus import event_bus

        event_bus.publish(NotifEvents.SENT, data={...})

        @event_bus.subscribe(NotifEvents.SENT)
        def on_sent(event): ...
    """

    # Notification lifecycle
    SENT        = 'notification.sent'
    DELIVERED   = 'notification.delivered'
    READ        = 'notification.read'
    CLICKED     = 'notification.clicked'
    FAILED      = 'notification.failed'
    DELETED     = 'notification.deleted'
    EXPIRED     = 'notification.expired'

    # Campaign
    CAMPAIGN_STARTED   = 'campaign.started'
    CAMPAIGN_COMPLETED = 'campaign.completed'
    CAMPAIGN_CANCELLED = 'campaign.cancelled'
    AB_TEST_WINNER     = 'campaign.ab_test_winner'

    # Device
    DEVICE_REGISTERED   = 'device.registered'
    DEVICE_DEACTIVATED  = 'device.deactivated'
    TOKEN_INVALID       = 'device.token_invalid'

    # User preference
    USER_OPTED_OUT    = 'user.opted_out'
    USER_RESUBSCRIBED = 'user.resubscribed'
    USER_FATIGUED     = 'user.fatigued'

    # System
    HEALTH_DEGRADED  = 'system.health_degraded'
    HEALTH_RESTORED  = 'system.health_restored'
    WEBHOOK_RECEIVED = 'system.webhook_received'

    # Earning site domain events (published by other modules)
    WITHDRAWAL_COMPLETED  = 'withdrawal.completed'
    WITHDRAWAL_REJECTED   = 'withdrawal.rejected'
    TASK_APPROVED         = 'task.approved'
    TASK_REJECTED         = 'task.rejected'
    OFFER_COMPLETED       = 'offer.completed'
    KYC_APPROVED          = 'kyc.approved'
    KYC_REJECTED          = 'kyc.rejected'
    REFERRAL_COMPLETED    = 'referral.completed'
    LEVEL_UP              = 'user.level_up'
    ACHIEVEMENT_UNLOCKED  = 'achievement.unlocked'
    FRAUD_DETECTED        = 'fraud.detected'


# ---------------------------------------------------------------------------
# Signal emitter helpers
# ---------------------------------------------------------------------------

def emit_notification_sent(notification, channel: str, result: dict):
    """Emit notification_sent Django signal."""
    try:
        notification_sent.send(
            sender=notification.__class__,
            instance=notification,
            channel=channel,
            result=result,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).debug(f'emit_notification_sent: {exc}')


def emit_notification_failed(notification, channel: str, error: str, attempts: int = 1):
    """Emit notification_failed Django signal."""
    try:
        notification_failed.send(
            sender=notification.__class__,
            instance=notification,
            channel=channel,
            error=error,
            attempts=attempts,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).debug(f'emit_notification_failed: {exc}')


def emit_push_token_invalid(token: str, provider: str, device=None):
    """Emit push_token_invalid signal — triggers cleanup."""
    try:
        push_token_invalid.send(
            sender=None,
            token=token,
            provider=provider,
            device=device,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).debug(f'emit_push_token_invalid: {exc}')
