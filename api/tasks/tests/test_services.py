"""
tests/test_services.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Structural + interface tests for services/ subfolder
and services.py stub classes — no Django ORM needed.
"""
import ast
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

SERVICES_DIR  = os.path.join(ROOT, 'services')
SERVICES_FILE = os.path.join(ROOT, 'services.py')


def _parse(path):
    with open(path) as f:
        return ast.parse(f.read())


def _classes(tree):
    return {n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}


def _methods(cls_node):
    return {
        n.name for n in ast.iter_child_nodes(cls_node)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


# ── Services subfolder ────────────────────────────────────────────────────────

class TestServiceSubfolderFiles(unittest.TestCase):
    """Every service file in services/ must parse cleanly and define its class."""

    EXPECTED = {
        'DeadLetterService.py':       'DeadLetterService',
        'QueueDepthService.py':       'QueueDepthService',
        'RetryService.py':            'RetryService',
        'TaskAlertService.py':        'TaskAlertService',
        'TaskAnalyticsService.py':    'TaskAnalyticsService',
        'TaskCostService.py':         'TaskCostService',
        'TaskDashboardService.py':    'TaskDashboardService',
        'TaskExportService.py':       'TaskExportService',
        'TaskMonitorService.py':      'TaskMonitorService',
        'WorkerHealthService.py':     'WorkerHealthService',
        'WorkflowService.py':         'WorkflowService',
        'WorkflowStepService.py':     'WorkflowStepService',
    }

    def test_all_service_files_exist(self):
        for fname in self.EXPECTED:
            with self.subTest(fname=fname):
                self.assertTrue(
                    os.path.exists(os.path.join(SERVICES_DIR, fname)),
                    f'Missing service file: {fname}'
                )

    def test_all_service_files_parse(self):
        for fname in self.EXPECTED:
            path = os.path.join(SERVICES_DIR, fname)
            if not os.path.exists(path):
                continue
            with self.subTest(fname=fname):
                try:
                    _parse(path)
                except SyntaxError as e:
                    self.fail(f'{fname} has syntax error: {e}')

    def test_each_service_file_defines_its_class(self):
        for fname, cls_name in self.EXPECTED.items():
            path = os.path.join(SERVICES_DIR, fname)
            if not os.path.exists(path):
                continue
            with self.subTest(cls=cls_name):
                tree    = _parse(path)
                classes = _classes(tree)
                self.assertIn(cls_name, classes,
                              f'{fname} does not define class {cls_name}')

    def test_services_init_exports_all(self):
        init_path = os.path.join(SERVICES_DIR, '__init__.py')
        self.assertTrue(os.path.exists(init_path))
        with open(init_path) as f:
            content = f.read()
        for _, cls_name in self.EXPECTED.items():
            with self.subTest(cls=cls_name):
                self.assertIn(cls_name, content,
                              f'services/__init__.py missing: {cls_name}')


class TestDeadLetterService(unittest.TestCase):
    def _cls(self):
        tree = _parse(os.path.join(SERVICES_DIR, 'DeadLetterService.py'))
        return _classes(tree).get('DeadLetterService')

    def test_class_exists(self):
        self.assertIsNotNone(self._cls())

    def test_has_key_methods(self):
        cls = self._cls()
        if not cls:
            return
        methods = _methods(cls)
        self.assertTrue(
            any(m in methods for m in ('requeue', 'get_dead_letters', 'purge', 'list', 'get_all')),
            f'DeadLetterService missing key methods, has: {methods}'
        )


class TestQueueDepthService(unittest.TestCase):
    def _cls(self):
        tree = _parse(os.path.join(SERVICES_DIR, 'QueueDepthService.py'))
        return _classes(tree).get('QueueDepthService')

    def test_class_exists(self):
        self.assertIsNotNone(self._cls())

    def test_has_snapshot_or_get_method(self):
        cls = self._cls()
        if not cls:
            return
        methods = _methods(cls)
        self.assertTrue(
            any(m in methods for m in ('snapshot', 'get_depth', 'get_queue_depth', 'current')),
            f'QueueDepthService missing snapshot/get methods, has: {methods}'
        )


class TestRetryService(unittest.TestCase):
    def _cls(self):
        tree = _parse(os.path.join(SERVICES_DIR, 'RetryService.py'))
        return _classes(tree).get('RetryService')

    def test_class_exists(self):
        self.assertIsNotNone(self._cls())

    def test_has_retry_method(self):
        cls = self._cls()
        if not cls:
            return
        methods = _methods(cls)
        self.assertTrue(
            any('retry' in m.lower() for m in methods),
            f'RetryService missing retry method, has: {methods}'
        )


class TestTaskAlertService(unittest.TestCase):
    def _cls(self):
        tree = _parse(os.path.join(SERVICES_DIR, 'TaskAlertService.py'))
        return _classes(tree).get('TaskAlertService')

    def test_class_exists(self):
        self.assertIsNotNone(self._cls())

    def test_has_create_or_trigger_method(self):
        cls = self._cls()
        if not cls:
            return
        methods = _methods(cls)
        self.assertTrue(
            any(m in methods for m in ('create_alert', 'trigger', 'send', 'evaluate', 'check')),
            f'TaskAlertService missing alert methods, has: {methods}'
        )


class TestTaskAnalyticsService(unittest.TestCase):
    def _cls(self):
        tree = _parse(os.path.join(SERVICES_DIR, 'TaskAnalyticsService.py'))
        return _classes(tree).get('TaskAnalyticsService')

    def test_class_exists(self):
        self.assertIsNotNone(self._cls())

    def test_has_analytics_method(self):
        cls = self._cls()
        if not cls:
            return
        methods = _methods(cls)
        self.assertTrue(
            len(methods) > 0,
            'TaskAnalyticsService has no methods'
        )


class TestWorkflowService(unittest.TestCase):
    def _cls(self):
        tree = _parse(os.path.join(SERVICES_DIR, 'WorkflowService.py'))
        return _classes(tree).get('WorkflowService')

    def test_class_exists(self):
        self.assertIsNotNone(self._cls())

    def test_has_execute_or_run(self):
        cls = self._cls()
        if not cls:
            return
        methods = _methods(cls)
        self.assertTrue(
            any(m in methods for m in ('execute', 'run', 'start', 'trigger', 'create')),
            f'WorkflowService missing execute/run, has: {methods}'
        )


class TestWorkerHealthService(unittest.TestCase):
    def _cls(self):
        tree = _parse(os.path.join(SERVICES_DIR, 'WorkerHealthService.py'))
        return _classes(tree).get('WorkerHealthService')

    def test_class_exists(self):
        self.assertIsNotNone(self._cls())

    def test_has_check_or_refresh_method(self):
        cls = self._cls()
        if not cls:
            return
        methods = _methods(cls)
        self.assertTrue(
            any(m in methods for m in ('check', 'refresh', 'get_health', 'ping', 'status')),
            f'WorkerHealthService missing health-check method, has: {methods}'
        )


# ── services.py stub classes ──────────────────────────────────────────────────

class TestServicesStubs(unittest.TestCase):
    """
    services.py contains proxy/stub classes for cross-app service delegation.
    Verify they exist, have the expected interface, and are callable.
    """

    EXPECTED_STUBS = [
        'NotificationService', 'FraudDetectionService', 'FraudService',
        'PublisherService', 'SubscriptionService', 'LeaderboardService',
        'EarningService', 'RewardService', 'PostbackService',
        'MediationService', 'ModerationService', 'BotService',
        'SegmentService', 'TrainingService', 'ChurnPredictionService',
        'RecommendationService', 'InsightGenerationService',
        'RevenueSummaryService', 'RevenueGoalService', 'AdPerformanceService',
        'ClickMetricService', 'EngagementScoreService', 'InvoiceService',
        'MaintenanceService', 'SiteService', 'QualityMetricService',
        'ScannerService', 'RuleEngineService', 'DispatchService',
        'VersionCheckService',
    ]

    def setUp(self):
        tree = _parse(SERVICES_FILE)
        self.classes = _classes(tree)

    def test_all_stubs_exist(self):
        for name in self.EXPECTED_STUBS:
            with self.subTest(cls=name):
                self.assertIn(name, self.classes,
                              f'services.py missing stub: {name}')

    def test_notification_service_has_send(self):
        cls = self.classes.get('NotificationService')
        if cls:
            self.assertIn('send', _methods(cls))

    def test_fraud_detection_service_has_scan(self):
        cls = self.classes.get('FraudDetectionService')
        if cls:
            self.assertIn('scan', _methods(cls))

    def test_subscription_service_has_expire_and_renew(self):
        cls = self.classes.get('SubscriptionService')
        if cls:
            methods = _methods(cls)
            self.assertIn('expire_overdue', methods)
            self.assertIn('renew', methods)

    def test_leaderboard_service_has_recalculate(self):
        cls = self.classes.get('LeaderboardService')
        if cls:
            self.assertIn('recalculate', _methods(cls))

    def test_recommendation_service_has_recommend_tasks(self):
        cls = self.classes.get('RecommendationService')
        if cls:
            self.assertIn('recommend_tasks', _methods(cls))

    def test_withdrawal_priority_manager_in_managers(self):
        managers_path = os.path.join(ROOT, 'managers.py')
        tree = _parse(managers_path)
        classes = _classes(tree)
        self.assertIn('WithdrawalPriorityManager', classes)
        cls = classes['WithdrawalPriorityManager']
        methods = _methods(cls)
        self.assertIn('expire_stale', methods)
        self.assertIn('get_top_priority', methods)

    def test_standalone_service_functions_exist(self):
        tree = _parse(SERVICES_FILE)
        top_funcs = {
            n.name for n in ast.iter_child_nodes(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for fn in ('process_postback', 'expire_overdue_subscriptions',
                   'renew_subscription', 'deliver_item'):
            with self.subTest(fn=fn):
                self.assertIn(fn, top_funcs,
                              f'services.py missing top-level function: {fn}')


class TestServicesFileSyntax(unittest.TestCase):
    def test_services_py_no_syntax_error(self):
        try:
            _parse(SERVICES_FILE)
        except SyntaxError as e:
            self.fail(f'services.py syntax error: {e}')

    def test_services_subfolder_init_no_syntax_error(self):
        init_path = os.path.join(SERVICES_DIR, '__init__.py')
        if not os.path.exists(init_path):
            return
        try:
            _parse(init_path)
        except SyntaxError as e:
            self.fail(f'services/__init__.py syntax error: {e}')


if __name__ == '__main__':
    unittest.main()
