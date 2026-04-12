"""
DATABASE_MODELS/notification_table.py — Notification System Reference
"""
from api.marketplace.MOBILE_MARKETPLACE.push_notification import DeviceToken, PushNotificationService, notify_user
from api.marketplace.MOBILE_MARKETPLACE.in_app_messaging import InAppMessage, get_active_messages, dismiss_message


def notify_order_update(user, order_number: str, status: str):
    """Convenience: send push notification for order status change."""
    return PushNotificationService().send_order_notification(user, order_number, status)


def get_user_notifications(user, tenant) -> list:
    """Get all active in-app messages for a user."""
    return get_active_messages(tenant, user)


def count_unread(user, tenant) -> int:
    return len(get_active_messages(tenant, user))


__all__ = [
    "DeviceToken","InAppMessage","PushNotificationService",
    "notify_user","get_active_messages","dismiss_message",
    "notify_order_update","get_user_notifications","count_unread",
]
