"""
Regression tests for the production-hardening pass (2026-10-03).

Each class pins one fix so it cannot silently regress:
  * migration 0013 data-aware gate
  * no raw exception text in API responses / service error dicts (static guard + live check)
  * SQL identifier helper and its call sites
  * escalation script action is default-deny
  * no database access / threads at import time
  * the eight items previously listed as "NOT fixed" in KNOWN_ISSUES
"""
import ast
import asyncio
import importlib
import os
import stat
import tempfile
import types
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

User = get_user_model()
PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------------------------------
# Migration 0013: data-aware gate
# --------------------------------------------------------------------------------------
class _FakeQS:
    db = 'default'

    def __init__(self, rows):
        self.rows = rows

    def count(self):
        return self.rows

    def filter(self, **kwargs):
        return self


class _FakeManager:
    def __init__(self, rows):
        self.rows = rows

    def using(self, alias):
        return self

    def all(self):
        return _FakeQS(self.rows)

    def filter(self, **kwargs):
        return _FakeQS(self.rows)


class _FakeApps:
    def __init__(self, rows_by_model):
        self.rows_by_model = rows_by_model

    def get_model(self, app_label, name):
        if name not in self.rows_by_model:
            raise LookupError(name)
        return types.SimpleNamespace(_default_manager=_FakeManager(self.rows_by_model[name]))


class LegacyDeletionGateTest(TestCase):
    def setUp(self):
        self.gate = importlib.import_module(
            'api.alerts.migrations.0013_review_required_delete_legacy_models')._confirm_or_abort
        self.schema_editor = types.SimpleNamespace(connection=types.SimpleNamespace(alias='default'))

    def _run(self, rows_by_model, env=None):
        environ = {'CONFIRM_LEGACY_MODEL_DELETION': ''}
        environ.update(env or {})
        with mock.patch.dict(os.environ, environ):
            return self.gate(_FakeApps(rows_by_model), self.schema_editor)

    def test_empty_legacy_tables_pass_without_any_env_var(self):
        self._run({'BackupSchedule': 0, 'Escalation': 0, 'AlertLog': 0})

    def test_missing_models_are_tolerated(self):
        self._run({})

    def test_rows_in_a_legacy_table_abort_the_migration(self):
        with self.assertRaises(RuntimeError) as ctx:
            self._run({'Escalation': 3, 'BackupSchedule': 0})
        self.assertIn('Escalation: 3 row(s)', str(ctx.exception))
        self.assertIn('CONFIRM_LEGACY_MODEL_DELETION=1', str(ctx.exception))

    def test_legacy_fk_columns_on_alert_logs_abort_the_migration(self):
        with self.assertRaises(RuntimeError) as ctx:
            self._run({'AlertLog': 2})
        self.assertIn('AlertLog.', str(ctx.exception))

    def test_explicit_confirmation_allows_deletion(self):
        self._run({'Escalation': 3}, env={'CONFIRM_LEGACY_MODEL_DELETION': '1'})


# --------------------------------------------------------------------------------------
# No raw exception text in client-visible payloads
# --------------------------------------------------------------------------------------
def _names_in(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def find_error_text_leaks():
    """(path, line) of every Response/JsonResponse (non-4xx) or `return {...}` inside an
    `except ... as e` handler whose payload contains the exception (or a value derived from it)."""
    client = ('400', '401', '403', '404', '409', '429', 'BAD_REQUEST', 'NOT_FOUND', 'FORBIDDEN',
              'UNAUTHORIZED', 'CONFLICT')
    leaks = []
    for root, dirs, files in os.walk(PACKAGE_DIR):
        dirs[:] = [d for d in dirs if d not in ('tests', 'docs', 'migrations', '__pycache__')]
        for name in files:
            if not name.endswith('.py'):
                continue
            path = os.path.join(root, name)
            with open(path, encoding='utf-8') as handle:
                tree = ast.parse(handle.read())
            for handler in [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler) and n.name]:
                tainted = {handler.name}
                for assign in ast.walk(handler):
                    if isinstance(assign, ast.Assign) and _names_in(assign.value) & tainted:
                        tainted |= {t.id for t in assign.targets if isinstance(t, ast.Name)}
                for node in ast.walk(handler):
                    if isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Dict) \
                            and ast.unparse(node.func).split('.')[-1] in ('Response', 'JsonResponse'):
                        status_src = next((ast.unparse(k.value) for k in node.keywords if k.arg == 'status'), '')
                        if any(token in status_src for token in client):
                            continue
                        if any(v is not None and _names_in(v) & tainted for v in node.args[0].values):
                            leaks.append((os.path.relpath(path, PACKAGE_DIR), node.lineno))
                    elif isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                        if any(v is not None and _names_in(v) & tainted for v in node.value.values):
                            leaks.append((os.path.relpath(path, PACKAGE_DIR), node.lineno))
    return leaks


class ErrorTextLeakTest(TestCase):
    def test_no_handler_returns_exception_text(self):
        leaks = find_error_text_leaks()
        self.assertEqual(leaks, [], f'raw exception text reaches callers at: {leaks[:10]}')

    def test_live_500_response_is_generic(self):
        from api.alerts.models.core import AlertRule
        admin = User.objects.create_superuser(username='leak_admin', email='leak@example.com', password='x')
        rule = AlertRule.objects.create(
            name='Leak probe', alert_type='server_error', severity='high', threshold_value=80.0,
            time_window_minutes=60, cooldown_minutes=30, created_by=admin, is_active=False)
        client = APIClient()
        client.force_authenticate(user=admin)
        secret = 'SECRET-INTERNAL-DETAIL-9d41'
        with mock.patch.object(AlertRule, 'save', side_effect=RuntimeError(secret)):
            resp = client.post(f'/rules/{rule.id}/activate/')
        self.assertGreaterEqual(resp.status_code, 400)
        self.assertNotIn(secret, resp.content.decode())


# --------------------------------------------------------------------------------------
# SQL identifiers
# --------------------------------------------------------------------------------------
class SqlIdentifierTest(TestCase):
    def test_safe_identifier_accepts_plain_names(self):
        from api.alerts.sql_utils import safe_identifier
        for name in ('alerts_alertrule', 'Table1', '_x', 'col$1'):
            self.assertEqual(safe_identifier(name), name)

    def test_safe_identifier_rejects_injection_attempts(self):
        from api.alerts.sql_utils import safe_identifier
        for name in ('x; DROP TABLE y', 'a b', 'a-b', '1abc', '', 'a"b', "a'b", 'a.b', None, 5):
            with self.assertRaises(ValueError, msg=repr(name)):
                safe_identifier(name)

    def test_quote_identifier_uses_the_connection_quoting(self):
        from api.alerts.sql_utils import quote_identifier
        self.assertEqual(quote_identifier('alerts_alertrule'), connection.ops.quote_name('alerts_alertrule'))
        with self.assertRaises(ValueError):
            quote_identifier('bad name')

    def test_database_fallback_query_builder_rejects_unsafe_input(self):
        from api.alerts.fallback_logic import DatabaseFallbackStrategy
        strategy = DatabaseFallbackStrategy.__new__(DatabaseFallbackStrategy)
        strategy.table_name = 'alerts_alertrule'
        self.assertIn('FROM alerts_alertrule', strategy._build_query({'operation': 'select', 'field': 'id'}))
        for context in ({'field': 'id; DROP TABLE x'}, {'condition': "1=1; DROP TABLE x"},
                        {'condition': "name = 'x' --"}, {'condition': '1=1 /* c */'}):
            with self.assertRaises(ValueError, msg=context):
                strategy._build_query(dict(context, operation='select'))
        strategy.table_name = 'x; DROP TABLE y'
        with self.assertRaises(ValueError):
            strategy._build_query({'operation': 'select'})


# --------------------------------------------------------------------------------------
# Escalation script action: default-deny
# --------------------------------------------------------------------------------------
class ScriptEscalationTest(TestCase):
    def setUp(self):
        from api.alerts.escalation import ScriptEscalationAction
        self.tmpdir = tempfile.mkdtemp(prefix='alerts_scripts_')
        self.script = os.path.join(self.tmpdir, 'ok.sh')
        with open(self.script, 'w') as handle:
            handle.write('#!/bin/sh\nexit 0\n')
        os.chmod(self.script, os.stat(self.script).st_mode | stat.S_IXUSR)
        self.escalation = types.SimpleNamespace(
            id='e1', alert_id=1, current_level=types.SimpleNamespace(value='level_1'))
        self.make = lambda path: ScriptEscalationAction({'script_path': path, 'timeout': 5})

    def _execute(self, path):
        return asyncio.run(self.make(path).execute(self.escalation, {}))

    def test_disabled_by_default(self):
        result = self._execute(self.script)
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Script not permitted')

    def test_allowed_directory_runs_the_script(self):
        with override_settings(ESCALATION_SCRIPT_ALLOWED_DIRS=[self.tmpdir]):
            result = self._execute(self.script)
        self.assertTrue(result['success'], result)

    def test_paths_outside_the_allow_list_are_refused(self):
        with override_settings(ESCALATION_SCRIPT_ALLOWED_DIRS=[self.tmpdir]):
            for path in ('/bin/sh', os.path.join(self.tmpdir, '..', 'ok.sh'), '', None):
                self.assertEqual(self._execute(path)['error'], 'Script not permitted', path)


# --------------------------------------------------------------------------------------
# Startup behaviour
# --------------------------------------------------------------------------------------
class StartupBehaviourTest(TestCase):
    def test_version_manager_does_not_query_the_database_when_constructed(self):
        from api.alerts.integration.versioning import IntegrationVersionManager
        with CaptureQueriesContext(connection) as queries:
            manager = IntegrationVersionManager()
        self.assertEqual(len(queries), 0)
        self.assertEqual(manager.versions, {})  # first use loads lazily without error

    def test_integration_permissions_are_created_by_the_post_migrate_hook(self):
        from api.alerts.apps import _ensure_integration_permissions
        Permission.objects.filter(codename='can_create_integration').delete()
        _ensure_integration_permissions()
        self.assertTrue(Permission.objects.filter(codename='can_create_integration').exists())

    def test_maintenance_commands_are_recognised(self):
        from api.alerts.apps import AlertsConfig
        self.assertIn('migrate', AlertsConfig.MAINTENANCE_COMMANDS)
        self.assertIn('makemigrations', AlertsConfig.MAINTENANCE_COMMANDS)
        self.assertNotIn('runserver', AlertsConfig.MAINTENANCE_COMMANDS)

    def test_background_threads_are_opt_in(self):
        from api.alerts.integration.performance_monitor import IntegrationPerformanceMonitor
        self.assertFalse(hasattr(IntegrationPerformanceMonitor(), 'monitoring_thread'))
        scheduler = importlib.import_module('api.alerts.scheduler')
        with override_settings(TASK_SCHEDULER_CONFIG={'enabled': True}):
            with mock.patch.object(scheduler.TaskScheduler, 'start_scheduler') as start:
                scheduler.initialize_task_scheduler()
        start.assert_not_called()
        with override_settings(TASK_SCHEDULER_CONFIG={'enabled': True, 'auto_start': True}):
            with mock.patch.object(scheduler.TaskScheduler, 'start_scheduler') as start:
                scheduler.initialize_task_scheduler()
        start.assert_called_once()

    def test_health_checks_are_not_started_at_import(self):
        health_check = importlib.import_module('api.alerts.health_check')
        self.assertTrue(callable(health_check.start_health_checks))
        self.assertIsNone(health_check.get_health_check_manager())


# --------------------------------------------------------------------------------------
# The eight items previously listed as "NOT fixed"
# --------------------------------------------------------------------------------------
def _make_rule(name='Hardening rule', **extra):
    from api.alerts.models.core import AlertRule
    return AlertRule.objects.create(
        name=name, alert_type='server_error', severity='high', threshold_value=80.0,
        time_window_minutes=60, cooldown_minutes=30, **extra)


class PreviouslyKnownIssuesTest(TestCase):
    # 1. AlertNoise.effectiveness_score + update_noise_effectiveness
    def test_noise_effectiveness_task_updates_the_stored_score(self):
        from api.alerts.models.intelligence import AlertNoise
        from api.alerts.tasks.intelligence import update_noise_effectiveness
        noise = AlertNoise.objects.create(name='Eff noise', total_processed=100, total_suppressed=25)
        self.assertGreaterEqual(update_noise_effectiveness(), 1)
        noise.refresh_from_db()
        self.assertAlmostEqual(noise.effectiveness_score, 0.25)

    def test_noise_clean_rejects_out_of_range_effectiveness(self):
        from django.core.exceptions import ValidationError
        from api.alerts.models.intelligence import AlertNoise
        noise = AlertNoise(name='Bad eff', effectiveness_score=1.5)
        with self.assertRaises(ValidationError):
            noise.clean()

    # 2. AlertLog.rule related_name='logs'
    def test_rule_logs_reverse_relation_and_analytics(self):
        from api.alerts.models.core import AlertLog
        from api.alerts.services.core import AlertMaintenanceService, AnalyticsService
        rule = _make_rule('Reverse relation rule', is_active=True)
        AlertLog.objects.create(rule=rule, trigger_value=90.0, threshold_value=80.0, message='boom')
        self.assertEqual(rule.logs.count(), 1)
        performance = AnalyticsService.get_rule_performance(days=30)
        self.assertTrue(performance, 'rule analytics should return data now that the relation exists')
        self.assertIsNotNone(AlertMaintenanceService.update_rule_health())

    # 3. performance monitor
    def test_performance_monitor_summary_and_alerts(self):
        from api.alerts.integration.performance_monitor import IntegrationPerformanceMonitor
        monitor = IntegrationPerformanceMonitor()
        monitor.record_metric('system', 'cpu_usage', 99.0)
        monitor.record_timer('integration', 'sync', 7.0)
        monitor.increment_counter('integration', 'calls', 3)
        summary = monitor.get_metrics_summary()
        self.assertNotIn('error', summary)
        self.assertIn('integration', summary['categories'])
        alerts = {a['metric']: a['severity'] for a in monitor.get_performance_alerts()}
        self.assertEqual(alerts.get('system.cpu_usage'), 'critical')
        self.assertEqual(alerts.get('integration.sync_duration'), 'critical')

    # 4. audit logs: enums, strings and JSON-lines file round trip
    def test_audit_log_round_trip_with_enums_and_strings(self):
        from api.alerts.integration.integ_audit_logs import AuditEventType, AuditLogger, AuditSeverity
        with tempfile.TemporaryDirectory() as tmp:
            audit = AuditLogger({'file_path': os.path.join(tmp, 'audit.log'), 'cache_timeout': 0})
            audit.log_event(AuditEventType.RULE_CREATED, AuditSeverity.INFO, 'enum event')
            audit.log_event('user_login', 'HIGH', 'string event', user_id='u1')
            audit.log_event(AuditEventType.INCIDENT_RESOLVED, AuditSeverity.WARNING, 'second enum event')
            with mock.patch('api.alerts.integration.integ_audit_logs.cache') as cache:
                cache.get.return_value = None
                everything = audit.get_entries(limit=10)
                only_login = audit.get_entries(limit=10, event_type=AuditEventType.USER_LOGIN)
                only_high = audit.get_entries(limit=10, severity=AuditSeverity.HIGH)
        self.assertEqual(len(everything), 3)
        self.assertEqual([e['description'] for e in only_login], ['string event'])
        self.assertEqual([e['description'] for e in only_high], ['string event'])

    # 5. sync manager -> registry
    def test_sync_resolution_updates_a_registered_integration(self):
        from api.alerts.integration.integ_registry import integration_registry
        from api.alerts.integration.sync_manager import integration_sync_manager

        class _Dummy:
            def __init__(self, config=None):
                self.config = config or {}

        integration_registry.register_integration('hardening_target', _Dummy, {})
        self.addCleanup(integration_registry.unregister_integration, 'hardening_target')
        result = integration_sync_manager._apply_sync_resolution('hardening_source', 'hardening_target', {'id': 'entity-1'})
        self.assertTrue(result['success'], result)
        self.assertEqual(result['entity_id'], 'entity-1')
        self.assertEqual(integration_registry.get_integration('hardening_target')['config']['last_synced_entity'], 'entity-1')

    # 6. incoming webhook reads the raw body first (covered in test_viewsets_webhooks); here: no 500 on JSON
    def test_incoming_webhook_view_handles_raw_body(self):
        from django.test import Client
        from api.alerts.webhooks import get_webhook_manager
        import hashlib
        import hmac
        import json
        get_webhook_manager().register_webhook('raw_body_hook', {'url': 'https://example.com/h', 'secret': 'raw-secret-123456'})
        self.addCleanup(get_webhook_manager().webhooks.clear)
        body = json.dumps({'event': 'unknown.event', 'data': {}}).encode()
        signature = hmac.new(b'raw-secret-123456', body, hashlib.sha256).hexdigest()
        from api.alerts.webhooks import webhook_endpoint
        from django.test import RequestFactory
        request = RequestFactory().post('/x', data=body, content_type='application/json', HTTP_X_SIGNATURE=signature)
        response = webhook_endpoint(request, webhook_id='raw_body_hook')
        self.assertEqual(response.status_code, 200)

    # 7. create_scheduled_report
    def test_create_scheduled_report_accepts_legacy_and_model_field_names(self):
        from api.alerts.models.reporting import AlertReport
        from api.alerts.tasks.reporting import create_scheduled_report
        self.assertIsNone(create_scheduled_report({}))
        self.assertIsNone(create_scheduled_report(None))
        report_id = create_scheduled_report({'name': 'Weekly (legacy key)', 'report_type': 'weekly'})
        self.assertIsNotNone(report_id)
        self.assertEqual(AlertReport.objects.get(pk=report_id).title, 'Weekly (legacy key)')
        recurring = create_scheduled_report({'title': 'Recurring', 'report_type': 'daily', 'is_recurring': True,
                                             'recurrence_pattern': {'frequency': 'weekly'}})
        report = AlertReport.objects.get(pk=recurring)
        self.assertAlmostEqual((report.next_run - timezone.now()).total_seconds(),
                               timedelta(days=7).total_seconds(), delta=60)


# 8. conftest fixtures (pytest-style)
def test_alert_rule_fixture_builds_a_valid_rule(alert_rule):
    assert alert_rule.pk and alert_rule.cooldown_minutes < alert_rule.time_window_minutes


def test_alert_report_fixture_builds_a_valid_report(alert_report):
    assert alert_report.pk and alert_report.title
