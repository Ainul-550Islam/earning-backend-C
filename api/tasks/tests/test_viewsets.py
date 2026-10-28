"""
tests/test_viewsets.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tests for all ViewSet classes — structural, method presence,
queryset filtering, and custom action signatures.
"""
import ast
import os
import unittest


VIEWSET_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'viewsets')


def _parse(path):
    with open(path) as f:
        return ast.parse(f.read())


def _get_class(tree, name=None):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if name is None or node.name == name:
                return node
    return None


def _methods(cls_node):
    return {
        n.name for n in ast.iter_child_nodes(cls_node)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _base_names(cls_node):
    return [ast.unparse(b) for b in cls_node.bases]


class TestOriginalViewsets(unittest.TestCase):
    """All original viewsets exist, define their class, and have get_queryset."""

    ORIGINAL = [
        ('TaskResultViewSet.py',      'TaskResultViewSet'),
        ('ScheduledTaskViewSet.py',   'ScheduledTaskViewSet'),
        ('TaskQueueViewSet.py',       'TaskQueueViewSet'),
        ('TaskMonitorViewSet.py',     'TaskMonitorViewSet'),
        ('TaskPerformanceViewSet.py', 'TaskPerformanceViewSet'),
        ('WorkerHealthViewSet.py',    'WorkerHealthViewSet'),
        ('QueueDepthViewSet.py',      'QueueDepthViewSet'),
        ('TaskAlertViewSet.py',       'TaskAlertViewSet'),
        ('DeadLetterViewSet.py',      'DeadLetterViewSet'),
        ('WorkflowViewSet.py',        'WorkflowViewSet'),
        ('WorkflowInstanceViewSet.py','WorkflowInstanceViewSet'),
        ('TaskInsightViewSet.py',     'TaskInsightViewSet'),
        ('TaskCostViewSet.py',        'TaskCostViewSet'),
        ('AdminTaskViewSet.py',       'AdminTaskViewSet'),
    ]

    def _path(self, fname):
        return os.path.join(VIEWSET_DIR, fname)

    def test_all_original_files_exist(self):
        for fname, _ in self.ORIGINAL:
            with self.subTest(fname=fname):
                self.assertTrue(os.path.exists(self._path(fname)),
                                f'Missing viewset file: {fname}')

    def test_all_original_classes_defined(self):
        for fname, cls_name in self.ORIGINAL:
            path = self._path(fname)
            if not os.path.exists(path):
                continue
            with self.subTest(cls=cls_name):
                tree = _parse(path)
                cls  = _get_class(tree, cls_name)
                self.assertIsNotNone(cls, f'{fname} does not define {cls_name}')

    def test_original_viewsets_have_get_queryset(self):
        # AdminTaskViewSet uses ViewSet (action-only), not ModelViewSet
        skip_queryset = {'AdminTaskViewSet'}
        for fname, cls_name in self.ORIGINAL:
            if cls_name in skip_queryset:
                continue
            path = self._path(fname)
            if not os.path.exists(path):
                continue
            with self.subTest(cls=cls_name):
                tree    = _parse(path)
                cls     = _get_class(tree, cls_name)
                if cls is None:
                    continue
                methods = _methods(cls)
                self.assertIn('get_queryset', methods,
                              f'{cls_name} missing get_queryset')

    def test_original_viewsets_inherit_from_drf(self):
        for fname, cls_name in self.ORIGINAL:
            path = self._path(fname)
            if not os.path.exists(path):
                continue
            with self.subTest(cls=cls_name):
                tree  = _parse(path)
                cls   = _get_class(tree, cls_name)
                if cls is None:
                    continue
                bases = _base_names(cls)
                self.assertTrue(
                    any('ViewSet' in b or 'APIView' in b for b in bases),
                    f'{cls_name} does not inherit from a DRF ViewSet: {bases}'
                )

    def test_scheduled_task_has_run_pause_resume(self):
        tree = _parse(self._path('ScheduledTaskViewSet.py'))
        cls  = _get_class(tree, 'ScheduledTaskViewSet')
        self.assertIsNotNone(cls)
        methods = _methods(cls)
        for m in ('run_now', 'pause', 'resume'):
            self.assertIn(m, methods, f'ScheduledTaskViewSet missing action: {m}')

    def test_task_result_has_custom_actions(self):
        tree = _parse(self._path('TaskResultViewSet.py'))
        cls  = _get_class(tree, 'TaskResultViewSet')
        self.assertIsNotNone(cls)
        methods = _methods(cls)
        self.assertTrue(
            any(m in methods for m in ('by_task', 'stats', 'list_by_status')),
            f'TaskResultViewSet missing custom actions, has: {methods}'
        )

    def test_worker_health_viewset_exists_and_correct(self):
        path = self._path('WorkerHealthViewSet.py')
        self.assertTrue(os.path.exists(path))
        tree = _parse(path)
        cls  = _get_class(tree, 'WorkerHealthViewSet')
        self.assertIsNotNone(cls)


class TestNewViewsets(unittest.TestCase):
    """All 9 newly created viewsets have correct structure."""

    NEW = [
        ('DisputeEscalationViewSet.py', 'DisputeEscalationViewSet', ['resolve']),
        ('RateLimitConfigViewSet.py',   'RateLimitConfigViewSet',   ['toggle_active', 'defaults']),
        ('TenantViewSet.py',            'TenantViewSet',            ['usage', 'extend_trial']),
        ('WorkflowLogViewSet.py',       'WorkflowLogViewSet',       ['summary']),
        ('WorkflowTriggerViewSet.py',   'WorkflowTriggerViewSet',   ['fire', 'toggle']),
        ('TaskRetryConfigViewSet.py',   'TaskRetryConfigViewSet',   ['for_task', 'reset_defaults']),
        ('TaskFailureRateViewSet.py',   'TaskFailureRateViewSet',   ['worst_tasks', 'healthy_tasks']),
        ('TaskThroughputViewSet.py',    'TaskThroughputViewSet',    ['averages', 'latest']),
        ('TaskPriorityViewSet.py',      'TaskPriorityViewSet',      ['by_queue', 'boost_priority']),
    ]

    def _path(self, fname):
        return os.path.join(VIEWSET_DIR, fname)

    def test_all_new_files_exist(self):
        for fname, _, _ in self.NEW:
            with self.subTest(fname=fname):
                self.assertTrue(os.path.exists(self._path(fname)))

    def test_new_classes_defined(self):
        for fname, cls_name, _ in self.NEW:
            path = self._path(fname)
            if not os.path.exists(path):
                continue
            with self.subTest(cls=cls_name):
                tree = _parse(path)
                cls  = _get_class(tree, cls_name)
                self.assertIsNotNone(cls, f'{fname} missing class {cls_name}')

    def test_new_viewsets_have_get_queryset(self):
        for fname, cls_name, _ in self.NEW:
            path = self._path(fname)
            if not os.path.exists(path):
                continue
            with self.subTest(cls=cls_name):
                tree    = _parse(path)
                cls     = _get_class(tree, cls_name)
                if cls is None:
                    continue
                self.assertIn('get_queryset', _methods(cls))

    def test_new_viewsets_have_get_serializer_class(self):
        for fname, cls_name, _ in self.NEW:
            path = self._path(fname)
            if not os.path.exists(path):
                continue
            with self.subTest(cls=cls_name):
                tree    = _parse(path)
                cls     = _get_class(tree, cls_name)
                if cls is None:
                    continue
                self.assertIn('get_serializer_class', _methods(cls))

    def test_new_viewsets_custom_actions_exist(self):
        for fname, cls_name, expected_actions in self.NEW:
            path = self._path(fname)
            if not os.path.exists(path):
                continue
            with self.subTest(cls=cls_name):
                tree    = _parse(path)
                cls     = _get_class(tree, cls_name)
                if cls is None:
                    continue
                methods = _methods(cls)
                for action in expected_actions:
                    self.assertIn(action, methods,
                                  f'{cls_name} missing custom action: {action}')

    def test_readonly_viewsets_use_readonly_base(self):
        readonly = [
            ('WorkflowLogViewSet.py',     'WorkflowLogViewSet'),
            ('TaskFailureRateViewSet.py', 'TaskFailureRateViewSet'),
            ('TaskThroughputViewSet.py',  'TaskThroughputViewSet'),
        ]
        for fname, cls_name in readonly:
            path = self._path(fname)
            if not os.path.exists(path):
                continue
            with self.subTest(cls=cls_name):
                tree  = _parse(path)
                cls   = _get_class(tree, cls_name)
                if cls is None:
                    continue
                bases = _base_names(cls)
                self.assertTrue(
                    any('ReadOnly' in b or 'ListRetrieve' in b for b in bases),
                    f'{cls_name} should use ReadOnlyModelViewSet, got: {bases}'
                )

    def test_admin_viewsets_use_is_admin_permission(self):
        admin_vs = [
            'RateLimitConfigViewSet.py',
            'TenantViewSet.py',
            'TaskRetryConfigViewSet.py',
            'TaskPriorityViewSet.py',
        ]
        for fname in admin_vs:
            path = self._path(fname)
            if not os.path.exists(path):
                continue
            with self.subTest(fname=fname):
                with open(path) as f:
                    src = f.read()
                self.assertIn('IsAdminUser', src,
                              f'{fname} should require IsAdminUser permission')


class TestViewsetsInit(unittest.TestCase):
    """viewsets/__init__.py exports all viewsets."""

    ALL_VIEWSETS = [
        # Original
        'TaskResultViewSet', 'ScheduledTaskViewSet', 'TaskQueueViewSet',
        'TaskMonitorViewSet', 'TaskPerformanceViewSet', 'WorkerHealthViewSet',
        'QueueDepthViewSet', 'TaskAlertViewSet', 'DeadLetterViewSet',
        'WorkflowViewSet', 'WorkflowInstanceViewSet', 'TaskInsightViewSet',
        'TaskCostViewSet', 'AdminTaskViewSet',
        # New
        'DisputeEscalationViewSet', 'RateLimitConfigViewSet', 'TenantViewSet',
        'WorkflowLogViewSet', 'WorkflowTriggerViewSet', 'TaskRetryConfigViewSet',
        'TaskFailureRateViewSet', 'TaskThroughputViewSet', 'TaskPriorityViewSet',
    ]

    def test_init_exports_all_viewsets(self):
        init_path = os.path.join(VIEWSET_DIR, '__init__.py')
        self.assertTrue(os.path.exists(init_path))
        with open(init_path) as f:
            content = f.read()
        for vs in self.ALL_VIEWSETS:
            with self.subTest(vs=vs):
                self.assertIn(vs, content,
                              f'viewsets/__init__.py missing export: {vs}')

    def test_no_syntax_errors_in_any_viewset(self):
        for fname in os.listdir(VIEWSET_DIR):
            if not fname.endswith('.py'):
                continue
            path = os.path.join(VIEWSET_DIR, fname)
            with self.subTest(fname=fname):
                try:
                    with open(path) as f:
                        ast.parse(f.read())
                except SyntaxError as e:
                    self.fail(f'Syntax error in {fname}: {e}')


if __name__ == '__main__':
    unittest.main()
