"""api/tasks/tests/test_events.py — Domain event tests."""
import pytest
from decimal import Decimal
from api.tasks.events import (
    TaskCompletedEvent, UserRegisteredEvent, OfferConvertedEvent,
    FraudDetectedEvent, WithdrawalRequestedEvent,
    create_event, EVENT_REGISTRY,
)


class TestDomainEvents:
    def test_task_completed_event_name(self):
        event = TaskCompletedEvent(user_id=1, task_id='T001', reward_amount=Decimal('0.50'))
        assert event.event_name == 'task.completed'
        assert event.user_id == 1

    def test_event_has_id_and_timestamp(self):
        event = TaskCompletedEvent(user_id=1)
        assert len(event.event_id) > 10
        assert event.occurred_at is not None

    def test_unique_event_ids(self):
        ids = {TaskCompletedEvent(user_id=1).event_id for _ in range(100)}
        assert len(ids) == 100

    def test_event_to_dict_decimal_as_string(self):
        event = TaskCompletedEvent(user_id=1, reward_amount=Decimal('1.50'))
        d = event.to_dict()
        assert isinstance(d['reward_amount'], str)
        assert d['reward_amount'] == '1.50'

    def test_user_registered_event(self):
        event = UserRegisteredEvent(user_id=42, username='newuser', email='new@example.com')
        assert event.event_name == 'user.registered'
        assert event.user_id == 42

    def test_fraud_detected_event(self):
        event = FraudDetectedEvent(user_id=99, fraud_score=85, reason='high_velocity')
        assert event.event_name == 'fraud.detected'
        assert event.fraud_score == 85

    def test_offer_converted_event(self):
        event = OfferConvertedEvent(
            user_id=1, offer_id='OFFER_001',
            payout=Decimal('1.50'), status='approved'
        )
        assert event.event_name == 'offer.converted'
        assert event.status == 'approved'

    def test_to_payload_excludes_version(self):
        event   = TaskCompletedEvent(user_id=1)
        payload = event.to_payload()
        assert 'version' not in payload
        assert 'event_name' in payload
        assert 'user_id' in payload


class TestEventFactory:
    def test_create_task_completed(self):
        event = create_event('task.completed', user_id=1, task_id='T001')
        assert isinstance(event, TaskCompletedEvent)
        assert event.user_id == 1

    def test_create_unknown_event(self):
        from api.tasks.events import BaseEvent
        event = create_event('unknown.event')
        assert isinstance(event, BaseEvent)

    def test_all_registry_events_instantiable(self):
        for event_name, klass in EVENT_REGISTRY.items():
            event = klass()
            assert event.event_name == event_name or event.occurred_at



import pytest
from api.tasks.integration.data_bridge import DataBridge
from api.tasks.integration.pipeline import DataPipeline
from decimal import Decimal


class TestDataBridge:
    def test_set_and_get(self):
        DataBridge.set('test:key:123', 'hello', ttl=60)
        assert DataBridge.get('test:key:123') == 'hello'

    def test_get_missing_key(self):
        result = DataBridge.get('nonexistent:key:xyz', default='fallback')
        assert result == 'fallback'

    def test_delete_key(self):
        DataBridge.set('del:test:1', 'value', ttl=60)
        DataBridge.delete('del:test:1')
        assert DataBridge.get('del:test:1') is None

    def test_decimal_serialization(self):
        DataBridge.set('decimal:test', Decimal('1.50'), ttl=60)
        result = DataBridge.get('decimal:test')
        assert result == Decimal('1.50')
        assert isinstance(result, Decimal)

    def test_user_namespace(self):
        DataBridge.set_user(999, 'test_field', 'test_value')
        result = DataBridge.get_user(999, 'test_field')
        assert result == 'test_value'

    def test_offer_namespace(self):
        DataBridge.set_offer('OFFER_001', 'epc', '0.05')
        result = DataBridge.get_offer('OFFER_001', 'epc')
        assert result == '0.05'

    def test_platform_namespace(self):
        DataBridge.set_platform('dau', 1500)
        result = DataBridge.get_platform('dau')
        assert result == 1500

    def test_bulk_set_and_get(self):
        data   = {'a:1': 'val1', 'a:2': 'val2', 'a:3': 'val3'}
        count  = DataBridge.bulk_set(data, ttl=60)
        assert count == 3
        results = DataBridge.bulk_get(['a:1', 'a:2', 'a:3'])
        assert results['a:1'] == 'val1'
        assert results['a:2'] == 'val2'

    def test_exists(self):
        DataBridge.set('exist:test:1', 'yes', ttl=60)
        assert DataBridge.exists('exist:test:1') is True
        assert DataBridge.exists('not:existing:key') is False

    def test_user_view_snapshot(self):
        uid = 7777
        DataBridge.set_user(uid, 'wallet_balance', Decimal('10.50'))
        DataBridge.set_user(uid, 'fraud_score', 5)
        snapshot = DataBridge.get_user_snapshot(uid)
        assert snapshot['user_id'] == uid
        assert 'wallet_balance' in snapshot


class TestDataPipeline:
    def test_build_unknown_pipeline(self):
        pipeline = DataPipeline.build('unknown_pipeline_xyz')
        result   = pipeline.run()
        # Should run with no steps
        assert '_pipeline' in result
        assert '_results' in result

    def test_manual_pipeline(self):
        pipeline = DataPipeline('test_pipeline')
        pipeline.add_step(
            'step1',
            fn=lambda ctx: {'processed': True},
        )
        result = pipeline.run(test_input='hello')
        assert result.get('processed') is True

    def test_pipeline_error_continue(self):
        pipeline = DataPipeline('error_pipeline')
        pipeline.add_step(
            'failing_step',
            fn=lambda ctx: (_ for _ in ()).throw(ValueError('test error')),
            on_error='continue',
        )
        pipeline.add_step(
            'success_step',
            fn=lambda ctx: {'after_error': True},
            on_error='continue',
        )
        result = pipeline.run()
        # Should continue past the error
        assert result.get('after_error') is True

    def test_pipeline_error_stop(self):
        pipeline = DataPipeline('stop_pipeline')
        pipeline.add_step(
            'stopper',
            fn=lambda ctx: 1/0,  # ZeroDivisionError
            on_error='stop',
        )
        pipeline.add_step(
            'never_runs',
            fn=lambda ctx: {'ran': True},
        )
        result = pipeline.run()
        assert result.get('ran') is None   # Should not have run

    def test_dependency_skip_when_dep_fails(self):
        pipeline = DataPipeline('dep_pipeline')
        pipeline.add_step('dep_step', fn=lambda ctx: 1/0, on_error='continue')
        pipeline.add_step('depends_step',
                          fn=lambda ctx: {'ran': True},
                          depends_on=['dep_step'])
        result = pipeline.run()
        # depends_step should be skipped because dep_step failed
        step_result = result['_results'].get('depends_step', {})
        assert step_result.get('skipped') is True
