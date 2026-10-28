"""
tests/test_serializers_extended.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Structural tests for all 13 newly added serializers
plus BulletproofSerializer — no Django ORM needed.
"""
import ast
import os
import unittest

SERIALIZERS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'serializers.py')


def _get_serializer_classes():
    with open(SERIALIZERS_PATH) as f:
        src = f.read()
    tree = ast.parse(src)
    result = {}
    for cls in ast.walk(tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        if 'Serializer' not in cls.name:
            continue
        meta = None
        fields_assigned = []
        methods = []
        for node in ast.iter_child_nodes(cls):
            if isinstance(node, ast.ClassDef) and node.name == 'Meta':
                meta = node
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        fields_assigned.append(t.id)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(node.name)
        result[cls.name] = {
            'has_meta': meta is not None,
            'fields_assigned': fields_assigned,
            'methods': methods,
            'meta_node': meta,
        }
    return result


class TestExistingSerializers(unittest.TestCase):
    """Original serializers have not regressed."""

    def setUp(self):
        self.classes = _get_serializer_classes()

    def test_master_task_serializer_exists(self):
        self.assertIn('MasterTaskSerializer', self.classes)

    def test_master_task_serializer_has_meta(self):
        self.assertTrue(self.classes['MasterTaskSerializer']['has_meta'])

    def test_user_task_completion_serializer_exists(self):
        self.assertIn('UserTaskCompletionSerializer', self.classes)

    def test_admin_ledger_serializer_exists(self):
        self.assertIn('AdminLedgerSerializer', self.classes)


class TestNewSerializers(unittest.TestCase):
    """All 13 new serializers exist and are well-formed."""

    NEW = [
        'BulletproofSerializer',
        'DisputeEscalationSerializer',
        'RateLimitConfigSerializer',
        'TaskCategorySerializer',
        'TaskFailureRateSerializer',
        'TaskThroughputSerializer',
        'TenantSerializer',
        'SubscriptionPlanSerializer',
        'WorkflowTriggerSerializer',
        'WorkflowLogSerializer',
        'TaskRetryConfigSerializer',
        'TaskPrioritySerializer',
        'CurrencySerializer',
        'PeriodSerializer',
    ]

    def setUp(self):
        self.classes = _get_serializer_classes()

    def test_all_new_serializers_exist(self):
        for name in self.NEW:
            with self.subTest(serializer=name):
                self.assertIn(name, self.classes, f'Missing serializer: {name}')

    def test_model_serializers_have_meta(self):
        model_serializers = [
            'DisputeEscalationSerializer', 'RateLimitConfigSerializer',
            'TaskFailureRateSerializer', 'TaskThroughputSerializer',
            'TenantSerializer', 'WorkflowTriggerSerializer',
            'WorkflowLogSerializer', 'TaskRetryConfigSerializer',
            'TaskPrioritySerializer',
        ]
        for name in model_serializers:
            if name not in self.classes:
                continue
            with self.subTest(serializer=name):
                self.assertTrue(
                    self.classes[name]['has_meta'],
                    f'{name} is a ModelSerializer but has no Meta class'
                )

    def test_non_model_serializers_have_fields(self):
        non_model = [
            'BulletproofSerializer', 'TaskCategorySerializer',
            'SubscriptionPlanSerializer', 'CurrencySerializer', 'PeriodSerializer',
        ]
        for name in non_model:
            if name not in self.classes:
                continue
            with self.subTest(serializer=name):
                info = self.classes[name]
                has_fields = bool(info['fields_assigned']) or info['has_meta'] or bool(info['methods'])
                self.assertTrue(has_fields, f'{name} has no fields or methods')

    def test_meta_classes_have_fields_attribute(self):
        """ModelSerializers' Meta must declare a fields list."""
        model_serializers = [
            'DisputeEscalationSerializer', 'RateLimitConfigSerializer',
            'TenantSerializer', 'WorkflowLogSerializer', 'WorkflowTriggerSerializer',
            'TaskRetryConfigSerializer', 'TaskPrioritySerializer',
            'TaskFailureRateSerializer', 'TaskThroughputSerializer',
        ]
        for name in model_serializers:
            info = self.classes.get(name)
            if info is None or info['meta_node'] is None:
                continue
            with self.subTest(serializer=name):
                meta = info['meta_node']
                meta_attrs = set()
                for node in ast.iter_child_nodes(meta):
                    if isinstance(node, ast.Assign):
                        for t in node.targets:
                            if isinstance(t, ast.Name):
                                meta_attrs.add(t.id)
                self.assertIn('fields', meta_attrs,
                              f'{name}.Meta must declare fields attribute')

    def test_dispute_escalation_has_key_fields_in_meta(self):
        info = self.classes.get('DisputeEscalationSerializer')
        if info is None or info['meta_node'] is None:
            return
        meta = info['meta_node']
        # Look for fields list literal
        for node in ast.walk(meta):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == 'fields':
                        if isinstance(node.value, ast.List):
                            field_names = [e.value for e in node.value.elts if isinstance(e, ast.Constant)]
                            self.assertIn('escalation_level', field_names)
                            self.assertIn('escalated_at', field_names)

    def test_tenant_serializer_has_name_slug(self):
        info = self.classes.get('TenantSerializer')
        if info is None or info['meta_node'] is None:
            return
        meta = info['meta_node']
        for node in ast.walk(meta):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == 'fields':
                        if isinstance(node.value, ast.List):
                            field_names = [e.value for e in node.value.elts if isinstance(e, ast.Constant)]
                            self.assertIn('name', field_names)
                            self.assertIn('slug', field_names)

    def test_workflow_log_has_step_number_status(self):
        info = self.classes.get('WorkflowLogSerializer')
        if info is None or info['meta_node'] is None:
            return
        meta = info['meta_node']
        for node in ast.walk(meta):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == 'fields':
                        if isinstance(node.value, ast.List):
                            field_names = [e.value for e in node.value.elts if isinstance(e, ast.Constant)]
                            self.assertIn('step_number', field_names)
                            self.assertIn('status', field_names)

    def test_bulletproof_serializer_has_to_representation(self):
        info = self.classes.get('BulletproofSerializer')
        if info is None:
            return
        self.assertIn('to_representation', info['methods'],
                      'BulletproofSerializer must override to_representation')


class TestNoRegression(unittest.TestCase):
    """Ensure serializers.py still parses without errors."""

    def test_serializers_py_no_syntax_error(self):
        try:
            with open(SERIALIZERS_PATH) as f:
                ast.parse(f.read())
        except SyntaxError as e:
            self.fail(f'serializers.py has syntax error: {e}')

    def test_total_serializer_count_increased(self):
        classes = _get_serializer_classes()
        self.assertGreaterEqual(
            len(classes), 27,
            f'Expected >=27 serializers, found {len(classes)}: {list(classes.keys())}'
        )


if __name__ == '__main__':
    unittest.main()
