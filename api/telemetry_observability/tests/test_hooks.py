"""
Tests for hooks.py — HookManager, Hook, HookType.
"""
import pytest
from ..hooks import HookManager, Hook, HookType, hook_manager


@pytest.fixture(autouse=True)
def reset_hook_manager():
    """Reset HookManager singleton before each test."""
    hook_manager.reset()
    yield
    hook_manager.reset()


class TestHookManager:
    def test_singleton(self):
        h1 = HookManager()
        h2 = HookManager()
        assert h1 is h2

    def test_module_level_is_singleton(self):
        assert HookManager() is hook_manager

    def test_register_and_run(self):
        calls = []
        hook_manager.register(HookType.AFTER_METRIC_RECORD, lambda ctx: calls.append(ctx))
        hook_manager.run(HookType.AFTER_METRIC_RECORD, {'data': {'id': 1}})
        assert len(calls) == 1
        assert calls[0]['data']['id'] == 1

    def test_register_returns_hook(self):
        fn   = lambda ctx: None  # noqa: E731
        hook = hook_manager.register(HookType.AFTER_LOG_RECORD, fn, name='my_hook')
        assert isinstance(hook, Hook)
        assert hook.name == 'my_hook'

    def test_priority_ordering(self):
        order = []
        hook_manager.register(HookType.AFTER_ALERT_TRIGGER,
                               lambda ctx: order.append('low'),   priority=0)
        hook_manager.register(HookType.AFTER_ALERT_TRIGGER,
                               lambda ctx: order.append('high'),  priority=10)
        hook_manager.register(HookType.AFTER_ALERT_TRIGGER,
                               lambda ctx: order.append('medium'), priority=5)
        hook_manager.run(HookType.AFTER_ALERT_TRIGGER, {})
        assert order == ['high', 'medium', 'low']

    def test_disabled_hook_skipped(self):
        calls = []
        hook = hook_manager.register(HookType.AFTER_METRIC_RECORD,
                                      lambda ctx: calls.append(1), name='skippable')
        hook_manager.disable('skippable')
        hook_manager.run(HookType.AFTER_METRIC_RECORD, {})
        assert len(calls) == 0

    def test_enable_after_disable(self):
        calls = []
        hook_manager.register(HookType.AFTER_METRIC_RECORD,
                               lambda ctx: calls.append(1), name='toggleable')
        hook_manager.disable('toggleable')
        hook_manager.enable('toggleable')
        hook_manager.run(HookType.AFTER_METRIC_RECORD, {})
        assert len(calls) == 1

    def test_unregister_by_name(self):
        calls = []
        hook_manager.register(HookType.AFTER_LOG_RECORD,
                               lambda ctx: calls.append(1), name='to_remove')
        hook_manager.unregister('to_remove')
        hook_manager.run(HookType.AFTER_LOG_RECORD, {})
        assert len(calls) == 0

    def test_unregister_returns_count(self):
        hook_manager.register(HookType.BEFORE_METRIC_RECORD, lambda ctx: None, name='dup')
        hook_manager.register(HookType.AFTER_METRIC_RECORD,  lambda ctx: None, name='dup')
        removed = hook_manager.unregister('dup')
        assert removed == 2

    def test_run_safe_swallows_exception(self):
        second_calls = []
        hook_manager.register(HookType.AFTER_METRIC_RECORD,
                               lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")),
                               name='bad_hook')
        hook_manager.register(HookType.AFTER_METRIC_RECORD,
                               lambda ctx: second_calls.append(1), name='good_hook')
        errors = hook_manager.run_safe(HookType.AFTER_METRIC_RECORD, {})
        assert len(errors) >= 1
        assert len(second_calls) == 1

    def test_run_raises_exception(self):
        hook_manager.register(HookType.BEFORE_ALERT_TRIGGER,
                               lambda ctx: (_ for _ in ()).throw(ValueError("veto")),
                               name='veto_hook')
        with pytest.raises(ValueError):
            hook_manager.run(HookType.BEFORE_ALERT_TRIGGER, {})

    def test_list_hooks_all(self):
        hook_manager.register(HookType.AFTER_METRIC_RECORD, lambda ctx: None, name='h1')
        hook_manager.register(HookType.AFTER_LOG_RECORD,    lambda ctx: None, name='h2')
        hooks = hook_manager.list_hooks()
        names = [h.name for h in hooks]
        assert 'h1' in names
        assert 'h2' in names

    def test_list_hooks_filtered(self):
        hook_manager.register(HookType.AFTER_METRIC_RECORD, lambda ctx: None, name='m1')
        hook_manager.register(HookType.AFTER_LOG_RECORD,    lambda ctx: None, name='l1')
        metric_hooks = hook_manager.list_hooks(HookType.AFTER_METRIC_RECORD)
        assert all(h.hook_type == HookType.AFTER_METRIC_RECORD for h in metric_hooks)

    def test_hook_execution_count_incremented(self):
        hook = hook_manager.register(HookType.AFTER_HEALTH_CHECK,
                                      lambda ctx: None, name='counter_hook')
        hook_manager.run(HookType.AFTER_HEALTH_CHECK, {})
        hook_manager.run(HookType.AFTER_HEALTH_CHECK, {})
        assert hook.execution_count == 2

    def test_last_executed_updated(self):
        hook = hook_manager.register(HookType.AFTER_TRACE_FINISH,
                                      lambda ctx: None, name='ts_hook')
        assert hook.last_executed is None
        hook_manager.run(HookType.AFTER_TRACE_FINISH, {})
        assert hook.last_executed is not None

    def test_reset_clears_all(self):
        hook_manager.register(HookType.AFTER_METRIC_RECORD, lambda ctx: None)
        hook_manager.reset()
        assert hook_manager.list_hooks() == []


class TestHookType:
    def test_all_hook_types_have_values(self):
        for ht in HookType:
            assert ht.value

    def test_known_hook_types_present(self):
        assert HookType.BEFORE_METRIC_RECORD
        assert HookType.AFTER_METRIC_RECORD
        assert HookType.BEFORE_ALERT_TRIGGER
        assert HookType.AFTER_ALERT_TRIGGER
        assert HookType.AFTER_HEALTH_CHECK
