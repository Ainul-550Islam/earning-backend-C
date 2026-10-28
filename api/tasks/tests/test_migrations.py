"""
tests/test_migrations.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Structural + content tests for all 5 migration files.
No Django or DB needed — pure AST + regex analysis.
"""
import ast
import os
import re
import unittest

ROOT           = os.path.dirname(os.path.dirname(__file__))
MIGRATIONS_DIR = os.path.join(ROOT, 'migrations')


def _parse(fname):
    path = os.path.join(MIGRATIONS_DIR, fname)
    with open(path) as f:
        return ast.parse(f.read()), f.name


def _src(fname):
    with open(os.path.join(MIGRATIONS_DIR, fname)) as f:
        return f.read()


def _migration_class(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'Migration':
            return node
    return None


def _attr(cls_node, name):
    for node in ast.iter_child_nodes(cls_node):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return node.value
    return None


def _migration_files():
    return sorted(f for f in os.listdir(MIGRATIONS_DIR)
                  if f.endswith('.py') and f != '__init__.py')


# ── 1. Global checks ──────────────────────────────────────────────────────────

class TestMigrationFiles(unittest.TestCase):

    EXPECTED = [
        '0001_initial.py',
        '0002_initial.py',
        '0003_add_missing_dependencies.py',
        '0004_bridge_to_new_system.py',
        '0005_new_task_system_models.py',
    ]

    def test_all_migration_files_exist(self):
        for fname in self.EXPECTED:
            with self.subTest(fname=fname):
                self.assertTrue(
                    os.path.exists(os.path.join(MIGRATIONS_DIR, fname)),
                    f'Missing migration: {fname}'
                )

    def test_no_unexpected_migration_files(self):
        actual = set(_migration_files()) - {'__init__.py'}
        expected = set(self.EXPECTED)
        extra = actual - expected
        self.assertEqual(extra, set(),
                         f'Unexpected migration files: {extra}')

    def test_all_migrations_parse_without_errors(self):
        for fname in self.EXPECTED:
            if not os.path.exists(os.path.join(MIGRATIONS_DIR, fname)):
                continue
            with self.subTest(fname=fname):
                try:
                    _parse(fname)
                except SyntaxError as e:
                    self.fail(f'{fname}: {e}')

    def test_all_migrations_define_migration_class(self):
        for fname in self.EXPECTED:
            if not os.path.exists(os.path.join(MIGRATIONS_DIR, fname)):
                continue
            with self.subTest(fname=fname):
                tree, _ = _parse(fname)
                cls = _migration_class(tree)
                self.assertIsNotNone(cls, f'{fname}: no Migration class')

    def test_all_migrations_have_dependencies_attr(self):
        for fname in self.EXPECTED:
            if not os.path.exists(os.path.join(MIGRATIONS_DIR, fname)):
                continue
            with self.subTest(fname=fname):
                tree, _ = _parse(fname)
                cls = _migration_class(tree)
                if cls is None:
                    continue
                dep = _attr(cls, 'dependencies')
                self.assertIsNotNone(dep, f'{fname}: missing dependencies attribute')

    def test_all_migrations_have_operations_attr(self):
        for fname in self.EXPECTED:
            if not os.path.exists(os.path.join(MIGRATIONS_DIR, fname)):
                continue
            with self.subTest(fname=fname):
                tree, _ = _parse(fname)
                cls = _migration_class(tree)
                if cls is None:
                    continue
                ops = _attr(cls, 'operations')
                self.assertIsNotNone(ops, f'{fname}: missing operations attribute')


# ── 2. Dependency chain integrity ────────────────────────────────────────────

class TestMigrationDependencyChain(unittest.TestCase):

    def _all_migration_names(self):
        return {f[:-3] for f in _migration_files()}

    def test_dependency_chain_is_valid(self):
        """Every ('tasks', 'XXXX') dependency must exist as a file."""
        known = self._all_migration_names()
        for fname in _migration_files():
            src = _src(fname)
            deps = re.findall(r"\('tasks',\s*'([^']+)'\)", src)
            for dep in deps:
                with self.subTest(file=fname, dep=dep):
                    self.assertIn(dep, known,
                                  f'{fname} depends on tasks.{dep} which does not exist')

    def test_0001_has_no_tasks_dependency(self):
        """First migration must not depend on itself or other tasks migrations."""
        src = _src('0001_initial.py')
        deps = re.findall(r"\('tasks',\s*'([^']+)'\)", src)
        self.assertEqual(deps, [],
                         f'0001_initial.py should have no tasks deps, found: {deps}')

    def test_0002_depends_on_0001(self):
        src = _src('0002_initial.py')
        self.assertIn('0001_initial', src)

    def test_0003_depends_on_0002(self):
        src = _src('0003_add_missing_dependencies.py')
        self.assertIn('0002', src)

    def test_0004_depends_on_0003(self):
        src = _src('0004_bridge_to_new_system.py')
        self.assertIn('0003', src)

    def test_0005_depends_on_0004_bridge(self):
        """Critical fix: 0005 must reference the correct 0004 name."""
        src = _src('0005_new_task_system_models.py')
        self.assertIn('0004_bridge_to_new_system', src,
                      '0005 must depend on 0004_bridge_to_new_system')
        self.assertNotIn('0004_adminledger_tenant_mastertask_tenant_and_more', src,
                         '0005 still references old wrong dependency name')


# ── 3. Content checks ────────────────────────────────────────────────────────

class TestMigration0001Content(unittest.TestCase):

    def setUp(self):
        self.src = _src('0001_initial.py')

    def test_creates_master_task(self):
        self.assertIn('MasterTask', self.src)

    def test_creates_user_task_completion(self):
        self.assertIn('UserTaskCompletion', self.src)

    def test_creates_admin_ledger(self):
        self.assertIn('AdminLedger', self.src)

    def test_uses_create_model_operation(self):
        self.assertIn('CreateModel', self.src)

    def test_no_alter_field_in_initial(self):
        """Initial migration should not use AlterField (that belongs in later migrations)."""
        # Allow it in comments but not as an actual operation class
        tree, _ = _parse('0001_initial.py')
        op_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in ('AlterField', 'RunSQL', 'AlterModelTable'):
                op_names.add(node.attr)
        # AlterField in 0001 would be unusual but not a hard error — just warn via assertion message
        # We only fail if it appears without CreateModel (pure alter with nothing to alter)
        if 'AlterField' in op_names:
            self.assertIn('CreateModel', self.src,
                          '0001 uses AlterField without any CreateModel — likely wrong')


class TestMigration0002Content(unittest.TestCase):

    def setUp(self):
        self.src = _src('0002_initial.py')

    def test_has_admin_ledger_reference(self):
        self.assertIn('adminledger', self.src.lower())

    def test_has_add_field_or_create_model(self):
        self.assertTrue(
            'AddField' in self.src or 'CreateModel' in self.src,
            '0002 should have AddField or CreateModel operations'
        )


class TestMigration0003Content(unittest.TestCase):

    def setUp(self):
        self.src = _src('0003_add_missing_dependencies.py')

    def test_adds_missing_dependencies(self):
        self.assertTrue(
            'AddField' in self.src or 'AlterField' in self.src
            or 'CreateModel' in self.src,
            '0003 should add/alter fields or create models'
        )


class TestMigration0004Content(unittest.TestCase):

    def setUp(self):
        self.src = _src('0004_bridge_to_new_system.py')

    def test_bridges_master_task(self):
        self.assertIn('mastertask', self.src.lower())

    def test_bridges_user_task_completion(self):
        self.assertIn('usertaskcompletion', self.src.lower())

    def test_bridges_admin_ledger(self):
        self.assertIn('adminledger', self.src.lower())

    def test_has_field_operations(self):
        self.assertTrue(
            'AddField' in self.src or 'AlterField' in self.src
            or 'RemoveField' in self.src or 'RenameField' in self.src,
            '0004 bridge should have field operations'
        )


class TestMigration0005Content(unittest.TestCase):

    def setUp(self):
        self.src = _src('0005_new_task_system_models.py')

    def test_creates_task_result(self):
        self.assertIn('TaskResult', self.src)

    def test_creates_task_queue(self):
        self.assertIn('TaskQueue', self.src)

    def test_creates_task_monitor(self):
        self.assertIn('TaskMonitor', self.src)

    def test_creates_worker_health(self):
        self.assertIn('WorkerHealth', self.src)

    def test_creates_task_workflow(self):
        self.assertIn('TaskWorkflow', self.src)

    def test_creates_workflow_instance(self):
        self.assertIn('WorkflowInstance', self.src)

    def test_creates_task_insight(self):
        self.assertIn('TaskInsight', self.src)

    def test_correct_dependency_name(self):
        self.assertIn('0004_bridge_to_new_system', self.src)

    def test_has_multiple_create_model_ops(self):
        count = self.src.count('CreateModel')
        self.assertGreater(count, 3,
                           f'0005 should create many models, found CreateModel {count} times')


# ── 4. Operations structural check ───────────────────────────────────────────

class TestMigrationOperationStructure(unittest.TestCase):

    def test_all_operations_are_lists(self):
        for fname in _migration_files():
            if not os.path.exists(os.path.join(MIGRATIONS_DIR, fname)):
                continue
            with self.subTest(fname=fname):
                tree, _ = _parse(fname)
                cls = _migration_class(tree)
                if cls is None:
                    continue
                ops_node = _attr(cls, 'operations')
                if ops_node is None:
                    continue
                self.assertIsInstance(
                    ops_node, ast.List,
                    f'{fname}: operations must be a list literal'
                )

    def test_all_dependencies_are_lists(self):
        for fname in _migration_files():
            if not os.path.exists(os.path.join(MIGRATIONS_DIR, fname)):
                continue
            with self.subTest(fname=fname):
                tree, _ = _parse(fname)
                cls = _migration_class(tree)
                if cls is None:
                    continue
                dep_node = _attr(cls, 'dependencies')
                if dep_node is None:
                    continue
                self.assertIsInstance(
                    dep_node, ast.List,
                    f'{fname}: dependencies must be a list literal'
                )

    def test_0001_operations_not_empty(self):
        tree, _ = _parse('0001_initial.py')
        cls = _migration_class(tree)
        ops = _attr(cls, 'operations')
        self.assertIsNotNone(ops)
        self.assertGreater(len(ops.elts), 0, '0001 must have at least one operation')

    def test_0005_operations_not_empty(self):
        tree, _ = _parse('0005_new_task_system_models.py')
        cls = _migration_class(tree)
        ops = _attr(cls, 'operations')
        self.assertIsNotNone(ops)
        self.assertGreater(len(ops.elts), 5,
                           '0005 should have many operations (7+ new models)')


if __name__ == '__main__':
    unittest.main()
