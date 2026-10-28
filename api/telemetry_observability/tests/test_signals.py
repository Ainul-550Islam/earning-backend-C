"""
Tests for signals.py — verifies EventBus publishes and hooks fire on model save.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.utils import timezone

from ..models.metric_event  import MetricEvent
from ..models.log_entry     import LogEntry
from ..models.trace_span    import TraceSpan
from ..models.alert         import Alert
from ..models.health_status import HealthStatus
from ..events import event_bus, EventType


@pytest.fixture(autouse=True)
def reset_event_bus():
    event_bus.reset()
    yield
    event_bus.reset()


@pytest.mark.django_db
class TestMetricSignal:
    def test_metric_created_publishes_event(self):
        received = []
        event_bus.subscribe(EventType.METRIC_RECORDED, lambda e: received.append(e))
        MetricEvent.objects.create(
            name='cpu', metric_type='gauge', value=80.0, service='svc'
        )
        assert len(received) == 1
        assert received[0].event_type == EventType.METRIC_RECORDED
        assert received[0].data['name'] == 'cpu'

    def test_metric_update_does_not_publish_event(self):
        received = []
        event_bus.subscribe(EventType.METRIC_RECORDED, lambda e: received.append(e))
        m = MetricEvent.objects.create(
            name='cpu', metric_type='gauge', value=80.0, service='svc'
        )
        received.clear()
        m.value = 90.0
        m.save()
        assert len(received) == 0


@pytest.mark.django_db
class TestLogSignal:
    def test_log_created_publishes_event(self):
        received = []
        event_bus.subscribe(EventType.LOG_RECORDED, lambda e: received.append(e))
        LogEntry.objects.create(level='error', message='Test error', service='svc')
        assert len(received) == 1
        assert received[0].data['level'] == 'error'


@pytest.mark.django_db
class TestTraceSignal:
    def test_trace_started_publishes_event(self):
        received = []
        event_bus.subscribe(EventType.TRACE_STARTED, lambda e: received.append(e))
        TraceSpan.objects.create(
            trace_id='t1', span_id='s1',
            operation_name='op', service='svc', start_time=timezone.now(),
        )
        assert len(received) == 1
        assert received[0].data['span_id'] == 's1'

    def test_trace_finished_publishes_event(self):
        finished = []
        event_bus.subscribe(EventType.TRACE_FINISHED, lambda e: finished.append(e))
        span = TraceSpan.objects.create(
            trace_id='t2', span_id='s2',
            operation_name='op', service='svc', start_time=timezone.now(),
        )
        span.end_time    = timezone.now()
        span.duration_ms = 100.0
        span.save()
        assert len(finished) == 1


@pytest.mark.django_db
class TestAlertSignal:
    def test_alert_triggered_publishes_event(self):
        triggered = []
        event_bus.subscribe(EventType.ALERT_TRIGGERED, lambda e: triggered.append(e))
        Alert.objects.create(
            name='test-alert', alert_type='metric', severity='warning',
            status='open', message='Test', service='svc',
        )
        assert len(triggered) == 1
        assert triggered[0].data['severity'] == 'warning'

    def test_alert_resolved_publishes_event(self):
        resolved = []
        event_bus.subscribe(EventType.ALERT_RESOLVED, lambda e: resolved.append(e))
        alert = Alert.objects.create(
            name='res-alert', alert_type='metric', severity='info',
            status='open', message='Test', service='svc',
        )
        alert.resolve()
        assert len(resolved) == 1
        assert resolved[0].data['status'] == 'resolved'

    def test_alert_acknowledged_publishes_event(self):
        acked = []
        event_bus.subscribe(EventType.ALERT_ACKNOWLEDGED, lambda e: acked.append(e))
        alert = Alert.objects.create(
            name='ack-alert', alert_type='metric', severity='warning',
            status='open', message='Test', service='svc',
        )
        alert.acknowledge('ops-team')
        assert len(acked) == 1
        assert acked[0].data['acknowledged_by'] == 'ops-team'


@pytest.mark.django_db
class TestHealthSignal:
    def test_health_changed_publishes_event(self):
        received = []
        event_bus.subscribe(EventType.HEALTH_STATUS_CHANGED, lambda e: received.append(e))
        HealthStatus.objects.create(
            service_name='api-svc', status='healthy', health_score=100,
        )
        assert len(received) == 1
        assert received[0].data['service_name'] == 'api-svc'

    def test_critical_health_triggers_auto_alert(self):
        """Score < 30 + unhealthy → auto-creates critical Alert."""
        HealthStatus.objects.create(
            service_name='dying-svc', status='unhealthy',
            health_score=10, environment='production',
        )
        alerts = Alert.objects.filter(
            service='dying-svc', severity='critical', alert_type='health'
        )
        assert alerts.exists()

    def test_healthy_service_does_not_trigger_auto_alert(self):
        HealthStatus.objects.create(
            service_name='good-svc', status='healthy',
            health_score=100, environment='production',
        )
        alerts = Alert.objects.filter(service='good-svc', alert_type='health')
        assert not alerts.exists()
