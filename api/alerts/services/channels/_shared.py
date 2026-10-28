"""
Small shared helpers for api.alerts.services.channels.* service classes.

Kept dependency-free from the other service modules (and from this
package's __init__.py) specifically to avoid circular imports: each
service module does `from ._shared import get_effective_alert_log`.
"""
from types import SimpleNamespace


def get_effective_alert_log(notification):
    """
    Return notification.alert_log if present, otherwise a lightweight
    read-only stand-in exposing the same attributes channel services
    read (rule.name/severity/alert_type, trigger_value, threshold_value,
    triggered_at, resolved_at, source, tags, context).

    notification.alert_log is nullable: synthetic notifications such as
    channel connectivity test pings (see
    services.channel.ChannelRoutingService._send_test_notification)
    aren't tied to a real AlertLog. Every channel service builds its
    message from alert_log.rule.* etc., so rather than special-casing
    "test mode" in eight separate files, callers get a safe stand-in
    with sensible placeholder values and can format it exactly like a
    real alert.
    """
    if notification.alert_log is not None:
        return notification.alert_log

    from django.utils import timezone

    rule = SimpleNamespace(
        name=notification.subject or 'Test Notification',
        severity='info',
        alert_type='test',
    )
    return SimpleNamespace(
        rule=rule,
        trigger_value=None,
        threshold_value=None,
        triggered_at=notification.created_at or timezone.now(),
        resolved_at=None,
        source=None,
        tags=None,
        context=None,
    )
