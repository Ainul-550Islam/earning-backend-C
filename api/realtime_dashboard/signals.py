"""
Django signals for Real-time Dashboard Backend.

WIRED (v1.2.0): EventStreamingService.stream_dashboard_updates() was
defined but NEVER called from anywhere. Added a UserDashboard post_save
receiver so dashboard changes are broadcast to all WebSocket subscribers
in real time, matching the existing pattern for RealTimeMetric.

Signal chain (new):
    UserDashboard.save() → post_save signal
        → dashboard_updated() receiver
            → EventStreamingService().stream_dashboard_updates(dashboard_id)
                → channel_layer.group_send('dashboard_<id>', {...})
                    → DashboardConsumer.dashboard_update() handler
                        → WebSocket client receives the update

Signal chain (existing — unchanged):
    RealTimeMetric.save() → post_save signal
        → real_time_metric_updated() receiver
            → WebSocketManagerService().broadcast_metric_update(instance)
                → WebSocketManager.broadcast_metric_update()
                    → channel_layer.group_send('metric_<id>', {...})
                        → MetricConsumer.metric_update() handler

Imports inside handlers prevent circular imports at module load time.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models.real_time_metric import RealTimeMetric
from .models.user_dashboard import UserDashboard


@receiver(post_save, sender=RealTimeMetric)
def real_time_metric_updated(sender, instance, created, **kwargs):
    """
    Broadcast a metric update whenever a RealTimeMetric is saved.

    Args:
        sender:   Model class (RealTimeMetric)
        instance: The saved RealTimeMetric instance
        created:  True if this is a newly created record
    """
    from .services.websocket_manager_service import WebSocketManagerService
    WebSocketManagerService().broadcast_metric_update(instance)


@receiver(post_save, sender=UserDashboard)
def dashboard_updated(sender, instance, created, **kwargs):
    """
    Broadcast a dashboard update to all subscribed clients whenever a
    UserDashboard is saved.

    WIRED (v1.2.0): EventStreamingService.stream_dashboard_updates() was
    defined in event_streaming_service.py but never connected to any
    signal, task, or view — it was completely floating. Adding this
    receiver makes dashboard changes visible to all WebSocket subscribers
    without polling.

    Only broadcasts on UPDATE (not create) because subscribers connect
    to a specific dashboard_id; a newly created dashboard has no
    subscribers yet.

    Args:
        sender:   Model class (UserDashboard)
        instance: The saved UserDashboard instance
        created:  True if this is a newly created record
    """
    if created:
        # No subscribers yet for a brand-new dashboard.
        return
    try:
        from .services.event_streaming_service import EventStreamingService
        EventStreamingService().stream_dashboard_updates(instance.pk)
    except Exception:
        # Broadcasting failure must never cause the save() to roll back.
        # Log and continue.
        import logging
        logging.getLogger(__name__).exception(
            'dashboard_updated signal: broadcast failed for dashboard_id=%d',
            instance.pk,
        )
