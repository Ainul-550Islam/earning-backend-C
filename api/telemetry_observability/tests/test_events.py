"""
Tests for events.py — EventBus, Event, EventType, publish_event.
"""
import pytest
from unittest.mock import MagicMock, patch
from ..events import (
    EventBus, Event, EventType, event_bus,
    publish_event, subscribe_to_event,
)


@pytest.fixture(autouse=True)
def reset_event_bus():
    """Reset EventBus singleton subscribers before each test."""
    event_bus.reset()
    yield
    event_bus.reset()


# ── Event ─────────────────────────────────────────────────────────────────────

class TestEvent:
    def test_create_event(self):
        e = Event(EventType.METRIC_RECORDED, {'metric_id': 1})
        assert e.event_type == EventType.METRIC_RECORDED
        assert e.data == {'metric_id': 1}
        assert e.timestamp is not None

    def test_to_dict(self):
        e = Event(EventType.ALERT_TRIGGERED, {'alert_id': 42})
        d = e.to_dict()
        assert d['event_type'] == 'alert_triggered'
        assert d['data']['alert_id'] == 42
        assert 'timestamp' in d
        assert 'metadata' in d

    def test_to_json(self):
        import json
        e = Event(EventType.LOG_RECORDED, {'log_id': 7})
        j = e.to_json()
        parsed = json.loads(j)
        assert parsed['event_type'] == 'log_recorded'

    def test_metadata_defaults_to_empty_dict(self):
        e = Event(EventType.METRIC_RECORDED, {})
        assert e.metadata == {}

    def test_custom_metadata(self):
        e = Event(EventType.METRIC_RECORDED, {}, metadata={'source': 'test'})
        assert e.metadata['source'] == 'test'

    def test_repr(self):
        e = Event(EventType.ALERT_TRIGGERED, {})
        assert 'alert_triggered' in repr(e)


# ── EventBus ──────────────────────────────────────────────────────────────────

class TestEventBus:
    def test_singleton(self):
        bus1 = EventBus()
        bus2 = EventBus()
        assert bus1 is bus2

    def test_module_level_event_bus_is_singleton(self):
        new_bus = EventBus()
        assert new_bus is event_bus

    def test_subscribe_and_publish(self):
        received = []
        event_bus.subscribe(EventType.METRIC_RECORDED, lambda e: received.append(e))
        publish_event(EventType.METRIC_RECORDED, {'id': 1})
        assert len(received) == 1
        assert received[0].event_type == EventType.METRIC_RECORDED

    def test_multiple_subscribers_same_event(self):
        calls = []
        event_bus.subscribe(EventType.LOG_RECORDED, lambda e: calls.append('first'))
        event_bus.subscribe(EventType.LOG_RECORDED, lambda e: calls.append('second'))
        publish_event(EventType.LOG_RECORDED, {})
        assert 'first' in calls
        assert 'second' in calls

    def test_subscriber_only_receives_its_event_type(self):
        metric_calls = []
        log_calls    = []
        event_bus.subscribe(EventType.METRIC_RECORDED, lambda e: metric_calls.append(e))
        event_bus.subscribe(EventType.LOG_RECORDED,    lambda e: log_calls.append(e))
        publish_event(EventType.METRIC_RECORDED, {})
        assert len(metric_calls) == 1
        assert len(log_calls)    == 0

    def test_unsubscribe(self):
        calls = []
        fn = lambda e: calls.append(e)  # noqa: E731
        event_bus.subscribe(EventType.ALERT_TRIGGERED, fn)
        publish_event(EventType.ALERT_TRIGGERED, {})
        event_bus.unsubscribe(EventType.ALERT_TRIGGERED, fn)
        publish_event(EventType.ALERT_TRIGGERED, {})
        assert len(calls) == 1  # only first publish

    def test_unsubscribe_nonexistent_returns_false(self):
        fn = lambda e: None  # noqa: E731
        result = event_bus.unsubscribe(EventType.METRIC_RECORDED, fn)
        assert result is False

    def test_duplicate_subscribe_ignored(self):
        calls = []
        fn = lambda e: calls.append(e)  # noqa: E731
        event_bus.subscribe(EventType.METRIC_RECORDED, fn)
        event_bus.subscribe(EventType.METRIC_RECORDED, fn)  # duplicate
        publish_event(EventType.METRIC_RECORDED, {})
        assert len(calls) == 1  # not called twice

    def test_subscriber_exception_does_not_break_others(self):
        second_calls = []
        def bad_subscriber(e): raise RuntimeError("intentional error")
        event_bus.subscribe(EventType.METRIC_RECORDED, bad_subscriber)
        event_bus.subscribe(EventType.METRIC_RECORDED, lambda e: second_calls.append(e))
        # Should not raise
        publish_event(EventType.METRIC_RECORDED, {})
        assert len(second_calls) == 1

    def test_get_subscriber_count(self):
        event_bus.subscribe(EventType.HEALTH_STATUS_CHANGED, lambda e: None)
        event_bus.subscribe(EventType.HEALTH_STATUS_CHANGED, lambda e: None)
        assert event_bus.get_subscriber_count(EventType.HEALTH_STATUS_CHANGED) == 2

    def test_reset_clears_all_subscribers(self):
        event_bus.subscribe(EventType.METRIC_RECORDED, lambda e: None)
        event_bus.reset()
        assert event_bus.get_subscriber_count(EventType.METRIC_RECORDED) == 0

    def test_publish_with_no_subscribers(self):
        # Should not raise
        publish_event(EventType.DASHBOARD_UPDATED, {'widget_id': 1})

    def test_subscribe_to_event_helper(self):
        calls = []
        subscribe_to_event(EventType.TRACE_STARTED, lambda e: calls.append(e))
        publish_event(EventType.TRACE_STARTED, {})
        assert len(calls) == 1


# ── EventType ─────────────────────────────────────────────────────────────────

class TestEventType:
    def test_all_event_types_have_values(self):
        for et in EventType:
            assert et.value  # non-empty string

    def test_event_types_unique(self):
        values = [et.value for et in EventType]
        assert len(values) == len(set(values))

    def test_known_event_types_exist(self):
        assert EventType.METRIC_RECORDED
        assert EventType.LOG_RECORDED
        assert EventType.TRACE_STARTED
        assert EventType.TRACE_FINISHED
        assert EventType.ALERT_TRIGGERED
        assert EventType.ALERT_ACKNOWLEDGED
        assert EventType.ALERT_RESOLVED
        assert EventType.HEALTH_STATUS_CHANGED
        assert EventType.DASHBOARD_UPDATED
