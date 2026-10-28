"""
Tests for Real-time Dashboard Backend signals.

Signal: post_save on RealTimeMetric → WebSocketManagerService.broadcast_metric_update()

Patch target fix
----------------
Previous version patched `api.realtime_dashboard.websocket_manager.WebSocketManager`
but the signal now delegates via:
    from .services.websocket_manager_service import WebSocketManagerService
    WebSocketManagerService().broadcast_metric_update(instance)

The correct patch target is therefore the SERVICE class, not the manager.
Patching the manager would no longer intercept the call.
"""
import pytest
from unittest.mock import patch, MagicMock

from api.realtime_dashboard.models.real_time_metric import RealTimeMetric
from .fixtures import create_real_time_metric

# Correct patch target — signals.py imports WebSocketManagerService from here.
_SERVICE_PATH = (
    'api.realtime_dashboard.services.websocket_manager_service.WebSocketManagerService'
)


@pytest.mark.django_db
class TestRealTimeMetricSignal:

    def test_signal_fires_on_update(self):
        """
        Saving an existing RealTimeMetric must call
        WebSocketManagerService().broadcast_metric_update(instance).

        FIXED: old test patched WebSocketManager (wrong class).
        Signal now goes through WebSocketManagerService.
        """
        metric = create_real_time_metric(name='SignalMetric')

        with patch(_SERVICE_PATH) as MockService:
            mock_instance = MagicMock()
            MockService.return_value = mock_instance

            metric.value = 200.0
            metric.save()

            MockService.assert_called_once()
            mock_instance.broadcast_metric_update.assert_called_once_with(metric)

    def test_signal_fires_on_create(self):
        """Creating a new RealTimeMetric also triggers the signal."""
        with patch(_SERVICE_PATH) as MockService:
            mock_instance = MagicMock()
            MockService.return_value = mock_instance

            metric = RealTimeMetric.objects.create(
                name='NewMetric',
                metric_type='gauge',
                status='active',
                value=42.0,
                unit='%',
                metadata={},
                tags=[],
            )

            MockService.assert_called_once()
            mock_instance.broadcast_metric_update.assert_called_once_with(metric)

    def test_signal_fires_on_every_save(self):
        """Each .save() call fires the signal once — not accumulated."""
        metric = create_real_time_metric(name='MultiSave')

        with patch(_SERVICE_PATH) as MockService:
            mock_instance = MagicMock()
            MockService.return_value = mock_instance

            metric.value = 10.0
            metric.save()
            metric.value = 20.0
            metric.save()
            metric.value = 30.0
            metric.save()

            assert mock_instance.broadcast_metric_update.call_count == 3

    def test_signal_passes_correct_instance(self):
        """The signal must pass the exact saved instance to the service."""
        metric = create_real_time_metric(name='InstanceCheck', value=5.0)

        with patch(_SERVICE_PATH) as MockService:
            mock_instance = MagicMock()
            MockService.return_value = mock_instance

            metric.value = 99.9
            metric.save()

            called_with = mock_instance.broadcast_metric_update.call_args[0][0]
            assert called_with.pk == metric.pk
            assert called_with.value == 99.9

    def test_signal_does_not_fire_for_other_models(self):
        """
        post_save on a non-metric model must not trigger
        the metric broadcast signal.
        """
        from api.realtime_dashboard.models.dashboard_widget import DashboardWidget

        with patch(_SERVICE_PATH) as MockService:
            mock_instance = MagicMock()
            MockService.return_value = mock_instance

            DashboardWidget.objects.create(
                name='NoSignalWidget',
                widget_type='chart',
                status='active',
                configuration={},
                metadata={},
                tags=[],
            )

            mock_instance.broadcast_metric_update.assert_not_called()
