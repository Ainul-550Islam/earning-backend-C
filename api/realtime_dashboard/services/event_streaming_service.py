"""
Event Streaming service for Real-time Dashboard Backend.
"""
from typing import Dict, Any, List

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


class EventStreamingService:
    """
    Service for streaming events to connected WebSocket clients via
    Django Channels channel groups.
    """

    def __init__(self) -> None:
        """Initialize the event streaming service."""
        pass

    def stream_metric_updates(self, metric_ids: List[int]) -> bool:
        """
        Broadcast the current value of each specified metric to all
        clients subscribed to that metric's Channels group
        (`metric_<id>`).

        Args:
            metric_ids: List of RealTimeMetric primary keys to broadcast

        Returns:
            True if at least one metric was found and broadcast
        """
        from ..models.real_time_metric import RealTimeMetric

        metrics = RealTimeMetric.objects.filter(id__in=metric_ids)

        for metric in metrics:
            self._broadcast_event(
                group=f'metric_{metric.id}',
                event={
                    'type': 'metric_update',
                    'data': {
                        'id': metric.id,
                        'name': metric.name,
                        'value': metric.value,
                        'unit': metric.unit,
                        'last_updated': metric.last_updated.isoformat(),
                    }
                }
            )

        return True

    def stream_dashboard_updates(self, dashboard_id: int) -> bool:
        """
        Broadcast a dashboard-updated event to all clients subscribed to
        that dashboard's Channels group (`dashboard_<id>`).

        Args:
            dashboard_id: UserDashboard primary key

        Returns:
            True if the dashboard was found and broadcast
        """
        from ..models.user_dashboard import UserDashboard

        dashboard = UserDashboard.objects.get(id=dashboard_id)

        self._broadcast_event(
            group=f'dashboard_{dashboard.id}',
            event={
                'type': 'dashboard_update',
                'data': {
                    'id': dashboard.id,
                    'name': dashboard.name,
                    'widgets': dashboard.widgets,
                }
            }
        )

        return True

    def _broadcast_event(self, group: str, event: Dict[str, Any]) -> bool:
        """
        Send an event dict to a Channels group via the configured
        channel layer.

        FIXED: was a stub that logged nothing and returned True.
        Now uses channel_layer.group_send() so consumers actually
        receive the event. The `type` key in `event` must match a
        handler method name on the consumer (e.g. 'metric_update'
        → MetricConsumer.metric_update(), 'dashboard_update' →
        DashboardConsumer.dashboard_update()).

        If no channel layer is configured (CHANNEL_LAYERS absent from
        settings, common in unit-test environments) this is a safe no-op.

        Args:
            group: Channel group name to broadcast to
            event: Event dict including a 'type' key

        Returns:
            True always (delivery is fire-and-forget)
        """
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return True

        async_to_sync(channel_layer.group_send)(group, event)
        return True
