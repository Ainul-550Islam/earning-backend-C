"""api/tasks/tests/test_signals_kb.py — KB Engine tests."""
import pytest
from api.tasks.signals_kb import KBRule, KBEngine, fire_kb_event


class TestKBRule:
    def test_rule_matches_event(self):
        rule = KBRule('test', condition=lambda ctx: True, action=lambda **kw: None, event='task.completed')
        assert rule.matches_event('task.completed') is True
        assert rule.matches_event('user.registered') is False

    def test_rule_matches_any_event(self):
        rule = KBRule('test', condition=lambda ctx: True, action=lambda **kw: None, event=None)
        assert rule.matches_event('anything') is True
        assert rule.matches_event('something_else') is True

    def test_condition_false_no_fire(self):
        fired = []
        rule  = KBRule(
            'test',
            condition=lambda ctx: False,
            action=lambda **kw: fired.append(1),
            async_action=False,
        )
        result = rule.evaluate('task.completed', {})
        assert result is False
        assert fired == []

    def test_condition_true_fires(self):
        fired = []
        rule  = KBRule(
            'test',
            condition=lambda ctx: True,
            action=lambda **kw: fired.append(1),
            action_kwargs_fn=lambda ctx: {},
            async_action=False,
        )
        result = rule.evaluate('task.completed', {'user_id': 1})
        assert result is True
        assert 1 in fired


class TestKBEngine:
    def test_register_rule(self):
        engine = KBEngine()
        rule   = KBRule('test_rule', condition=lambda ctx: True,
                        action=lambda **kw: None, async_action=False)
        engine.register(rule)
        assert any(r.name == 'test_rule' for r in engine._rules)

    def test_fire_returns_summary(self):
        engine = KBEngine()
        result = engine.fire('test.event', {'user_id': 1})
        assert 'fired' in result
        assert 'skipped' in result

    def test_priority_ordering(self):
        execution_order = []
        engine = KBEngine()

        def make_action(n):
            def action(**kw):
                execution_order.append(n)
            return action

        for priority, n in [(30, 'C'), (10, 'A'), (20, 'B')]:
            engine.register(KBRule(
                f'rule_{n}',
                condition=lambda ctx: True,
                action=make_action(n),
                action_kwargs_fn=lambda ctx: {},
                priority=priority,
                async_action=False,
            ))

        engine.fire('test.event', {})
        assert execution_order == ['A', 'B', 'C']

    def test_disable_rule(self):
        fired = []
        engine = KBEngine()
        engine.register(KBRule(
            'disablable',
            condition=lambda ctx: True,
            action=lambda **kw: fired.append(1),
            action_kwargs_fn=lambda ctx: {},
            async_action=False,
        ))
        engine.disable('disablable')
        engine.fire('test.event', {})
        assert fired == []

    def test_unregister_rule(self):
        engine = KBEngine()
        engine.register(KBRule('removable', condition=lambda ctx: True,
                               action=lambda **kw: None, async_action=False))
        removed = engine.unregister('removable')
        assert removed is True
        assert not any(r.name == 'removable' for r in engine._rules)
