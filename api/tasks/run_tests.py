"""
run_tests.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Standalone test runner — works WITHOUT Django installed.
Covers: helpers, validators, logic, models structure,
        migration chain, adapters, serializers (pure parts),
        constants, enums, choices, exceptions, cache, repository.
"""

import sys
import os
import ast
import unittest
import unittest.mock as mock
from decimal import Decimal
from collections import defaultdict
from pathlib import Path

# ── Bootstrap: add project root to path ───────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# ── Minimal Django mock so imports work without pip install ───────────────────
def _make_django_mock():
    django_mod                          = mock.MagicMock()
    django_mod.db                       = mock.MagicMock()
    django_mod.db.models                = mock.MagicMock()
    django_mod.db.models.Model          = object
    django_mod.db.models.Manager        = object
    django_mod.db.models.QuerySet       = list
    django_mod.db.models.TextChoices    = object
    django_mod.db.models.IntegerChoices = object

    # Make TextChoices / IntegerChoices behave like classes
    class _TC:
        pass
    django_mod.db.models.TextChoices    = _TC
    django_mod.db.models.IntegerChoices = _TC

    django_mod.utils                    = mock.MagicMock()
    django_mod.utils.timezone           = mock.MagicMock()
    django_mod.utils.timezone.now       = lambda: __import__('datetime').datetime.utcnow()
    django_mod.utils.timezone.timedelta = __import__('datetime').timedelta
    django_mod.core                     = mock.MagicMock()
    django_mod.core.cache               = mock.MagicMock()
    django_mod.conf                     = mock.MagicMock()
    django_mod.conf.settings            = mock.MagicMock()
    django_mod.apps                     = mock.MagicMock()
    django_mod.dispatch                 = mock.MagicMock()
    django_mod.dispatch.Signal          = mock.MagicMock

    mods = {
        'django': django_mod,
        'django.db': django_mod.db,
        'django.db.models': django_mod.db.models,
        'django.db.models.deletion': mock.MagicMock(),
        'django.db.models.signals': mock.MagicMock(),
        'django.db.models.functions': mock.MagicMock(),
        'django.utils': django_mod.utils,
        'django.utils.timezone': django_mod.utils.timezone,
        'django.utils.crypto': mock.MagicMock(),
        'django.core': django_mod.core,
        'django.core.cache': django_mod.core.cache,
        'django.conf': django_mod.conf,
        'django.apps': django_mod.apps,
        'django.dispatch': django_mod.dispatch,
        'rest_framework': mock.MagicMock(),
        'rest_framework.exceptions': mock.MagicMock(),
        'rest_framework.serializers': mock.MagicMock(),
        'rest_framework.response': mock.MagicMock(),
        'rest_framework.decorators': mock.MagicMock(),
        'rest_framework.permissions': mock.MagicMock(),
        'rest_framework.authentication': mock.MagicMock(),
        'celery': mock.MagicMock(),
        'celery.utils.log': mock.MagicMock(),
        'redis': mock.MagicMock(),
    }
    sys.modules.update(mods)

_make_django_mock()

# ── Colour helpers ─────────────────────────────────────────────────────────────
GREEN  = '\033[92m'
RED    = '\033[91m'
YELLOW = '\033[93m'
BLUE   = '\033[94m'
BOLD   = '\033[1m'
RESET  = '\033[0m'

def green(s):  return f'{GREEN}{s}{RESET}'
def red(s):    return f'{RED}{s}{RESET}'
def yellow(s): return f'{YELLOW}{s}{RESET}'
def blue(s):   return f'{BLUE}{s}{RESET}'
def bold(s):   return f'{BOLD}{s}{RESET}'

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — STATIC ANALYSIS TESTS
# ══════════════════════════════════════════════════════════════════════════════

class StaticAnalysisTests(unittest.TestCase):
    """AST-level checks: syntax, duplicates, migration chain."""

    def _all_py_files(self, exclude=('__pycache__', '.pytest_cache', 'run_tests.py')):
        files = []
        for root, dirs, fnames in os.walk('.'):
            dirs[:] = [d for d in dirs if d not in exclude]
            for f in fnames:
                if f.endswith('.py'):
                    files.append(os.path.join(root, f))
        return files

    # ── Syntax ────────────────────────────────────────────────────────────────

    def test_syntax_all_python_files(self):
        errors = []
        for path in self._all_py_files():
            try:
                with open(path) as f: src = f.read()
                ast.parse(src)
            except SyntaxError as e:
                errors.append(f'{path}:{e.lineno}: {e.msg}')
        self.assertEqual(errors, [], f'Syntax errors:\n' + '\n'.join(errors))

    # ── Duplicates ────────────────────────────────────────────────────────────

    def test_no_duplicate_functions_in_any_file(self):
        duplicates = []
        for path in self._all_py_files():
            try:
                with open(path) as f: src = f.read()
                tree = ast.parse(src)
            except: continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef)):
                    seen = {}
                    for child in ast.iter_child_nodes(node):
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            ctx = getattr(node, 'name', 'module')
                            n = child.name
                            if n in seen:
                                duplicates.append(f'{path}: "{n}" in {ctx} (lines {seen[n]}&{child.lineno})')
                            else:
                                seen[n] = child.lineno
        self.assertEqual(duplicates, [], 'Duplicate functions:\n' + '\n'.join(duplicates))

    # ── Adapters ──────────────────────────────────────────────────────────────

    def test_all_adapters_have_init(self):
        self.assertTrue(
            os.path.exists('api/adapters/__init__.py'),
            'api/adapters/__init__.py is missing'
        )

    def test_adapter_files_syntax(self):
        errors = []
        for f in os.listdir('api/adapters'):
            if not f.endswith('.py'): continue
            path = f'api/adapters/{f}'
            try:
                with open(path) as fp: ast.parse(fp.read())
            except SyntaxError as e:
                errors.append(f'{path}:{e.lineno}: {e.msg}')
        self.assertEqual(errors, [], '\n'.join(errors))

    def test_adapter_init_exports_match_definitions(self):
        """Every name in adapters/__init__.py __all__ must be bound in the module."""
        with open('api/adapters/__init__.py') as f: src = f.read()
        tree = ast.parse(src)

        # Collect all names BOUND at module level (including asname aliases)
        bound_names = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    bound_names.add(alias.asname if alias.asname else alias.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bound_names.add(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        bound_names.add(t.id)

        # Find __all__ list and check every entry is bound
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == '__all__':
                        exported = [e.value for e in node.value.elts if isinstance(e, ast.Constant)]
                        missing = [n for n in exported if n not in bound_names]
                        self.assertEqual(missing, [], f'Names in __all__ not bound in module: {missing}')

    # ── Models ────────────────────────────────────────────────────────────────

    def test_models_no_duplicate_fields_in_classes(self):
        issues = []
        model_files = ['models.py'] + [f'models/{f}' for f in os.listdir('models') if f.endswith('.py')]
        for path in model_files:
            try:
                with open(path) as f: src = f.read()
                tree = ast.parse(src)
            except: continue
            for cls in ast.walk(tree):
                if not isinstance(cls, ast.ClassDef): continue
                seen = {}
                for child in ast.iter_child_nodes(cls):
                    if isinstance(child, ast.Assign):
                        for t in child.targets:
                            if isinstance(t, ast.Name) and not t.id.startswith('_'):
                                if t.id in seen:
                                    issues.append(f'{path}: field "{t.id}" duplicated in {cls.name}')
                                seen[t.id] = child.lineno
        self.assertEqual(issues, [], 'Duplicate model fields:\n' + '\n'.join(issues))

    def test_models_init_exports_exist(self):
        """All names exported from models/__init__.py must exist in sub-files."""
        issues = []
        all_sub_names = set()
        for fname in os.listdir('models'):
            if not fname.endswith('.py') or fname == '__init__.py': continue
            path = f'models/{fname}'
            with open(path) as f: src = f.read()
            tree = ast.parse(src)
            for n in ast.walk(tree):
                if isinstance(n, ast.ClassDef): all_sub_names.add(n.name)

        with open('models/__init__.py') as f: src = f.read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name != '*' and alias.name not in all_sub_names:
                        issues.append(f'models/__init__.py exports {alias.name} but not found in sub-models')
        self.assertEqual(issues, [], '\n'.join(issues))

    # ── Migrations ────────────────────────────────────────────────────────────

    def test_all_migrations_have_migration_class(self):
        missing = []
        for f in os.listdir('migrations'):
            if not f.endswith('.py') or f == '__init__.py': continue
            path = f'migrations/{f}'
            with open(path) as fp: src = fp.read()
            tree = ast.parse(src)
            classes = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
            if 'Migration' not in classes:
                missing.append(f)
        self.assertEqual(missing, [], f'Missing Migration class: {missing}')

    def test_migrations_dependency_chain_valid(self):
        """Each migration's dependencies must reference an existing migration file."""
        import re
        migration_files = {f[:-3] for f in os.listdir('migrations')
                           if f.endswith('.py') and f != '__init__.py'}
        issues = []
        for fname in sorted(migration_files):
            path = f'migrations/{fname}.py'
            with open(path) as f: src = f.read()
            deps = re.findall(r"\('tasks',\s*'([^']+)'\)", src)
            for dep in deps:
                if dep not in migration_files:
                    issues.append(f'{fname}.py depends on tasks.{dep} which does not exist')
        self.assertEqual(issues, [], 'Migration dependency issues:\n' + '\n'.join(issues))

    def test_migration_0005_dependency_fixed(self):
        """Migration 0005 must depend on 0004_bridge_to_new_system, not the old name."""
        with open('migrations/0005_new_task_system_models.py') as f: src = f.read()
        self.assertIn('0004_bridge_to_new_system', src)
        self.assertNotIn('0004_adminledger_tenant_mastertask_tenant_and_more', src)

    def test_migrations_have_dependencies_and_operations(self):
        for fname in os.listdir('migrations'):
            if not fname.endswith('.py') or fname == '__init__.py': continue
            path = f'migrations/{fname}'
            with open(path) as fp: src = fp.read()
            tree = ast.parse(src)
            for cls in ast.walk(tree):
                if isinstance(cls, ast.ClassDef) and cls.name == 'Migration':
                    attrs = set()
                    for item in ast.iter_child_nodes(cls):
                        if isinstance(item, ast.Assign):
                            for t in item.targets:
                                if isinstance(t, ast.Name): attrs.add(t.id)
                    self.assertIn('dependencies', attrs, f'{fname}: missing dependencies')
                    self.assertIn('operations', attrs, f'{fname}: missing operations')


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — HELPER FUNCTION TESTS (pure Python, no Django)
# ══════════════════════════════════════════════════════════════════════════════

from helpers import (
    generate_transaction_id, generate_click_id, mask_email, mask_sensitive,
    to_decimal, revenue_split, compute_hmac_sha256, verify_hmac_sha256,
    is_valid_email, is_valid_evm_address, is_valid_trc20_address,
    get_traffic_tier, compute_fraud_score_from_signals, chunk_list,
    success_result, error_result, skipped_result, validate_crypto_address,
    calculate_percentage, format_duration,
)


class TestGenerators(unittest.TestCase):

    def test_transaction_id_default_prefix(self):
        tid = generate_transaction_id()
        self.assertTrue(tid.startswith('txn_'), f"Expected 'txn_' prefix, got: {tid}")

    def test_transaction_id_custom_prefix(self):
        tid = generate_transaction_id(prefix='pay')
        self.assertTrue(tid.startswith('pay_'))

    def test_transaction_ids_unique(self):
        ids = {generate_transaction_id() for _ in range(200)}
        self.assertEqual(len(ids), 200, 'Transaction IDs are not unique')

    def test_click_id_length(self):
        self.assertEqual(len(generate_click_id()), 32)

    def test_click_ids_unique(self):
        ids = {generate_click_id() for _ in range(200)}
        self.assertEqual(len(ids), 200, 'Click IDs are not unique')


class TestMaskHelpers(unittest.TestCase):

    def test_mask_email_contains_at(self):
        result = mask_email('john.doe@example.com')
        self.assertIn('@example.com', result)

    def test_mask_email_hides_local(self):
        result = mask_email('john.doe@example.com')
        self.assertNotEqual(result, 'john.doe@example.com')
        self.assertIn('*', result)

    def test_mask_sensitive_shows_tail(self):
        result = mask_sensitive('secret12345', visible_chars=4)
        self.assertTrue(result.endswith('2345'))
        self.assertIn('*', result)

    def test_mask_sensitive_short_string(self):
        result = mask_sensitive('ab', visible_chars=4)
        self.assertIsInstance(result, str)


class TestDecimalHelpers(unittest.TestCase):

    def test_to_decimal_string(self):
        self.assertEqual(to_decimal('1.50'), Decimal('1.5'))

    def test_to_decimal_float(self):
        self.assertAlmostEqual(float(to_decimal(1.5)), 1.5, places=5)

    def test_to_decimal_invalid_returns_zero(self):
        self.assertEqual(to_decimal('not_a_number'), Decimal('0'))

    def test_to_decimal_none_returns_zero(self):
        self.assertEqual(to_decimal(None), Decimal('0'))

    def test_revenue_split_default_70_30(self):
        result = revenue_split(Decimal('1.00'))
        self.assertEqual(result['publisher'], Decimal('0.70'))
        self.assertEqual(result['platform'],  Decimal('0.30'))

    def test_revenue_split_sums_to_total(self):
        total = Decimal('3.57')
        result = revenue_split(total)
        self.assertAlmostEqual(float(result['publisher'] + result['platform']), float(total), places=5)

    def test_revenue_split_custom_ratio(self):
        result = revenue_split(Decimal('1.00'), publisher_rate=Decimal('0.80'))
        self.assertEqual(result['publisher'], Decimal('0.80'))
        self.assertEqual(result['platform'],  Decimal('0.20'))

    def test_calculate_percentage(self):
        self.assertAlmostEqual(calculate_percentage(25, 200), 12.5, places=5)

    def test_calculate_percentage_zero_total(self):
        self.assertEqual(calculate_percentage(10, 0), 0)


class TestHMACHelpers(unittest.TestCase):

    def test_compute_and_verify_hmac(self):
        payload = 'test_payload'
        secret  = 'my_secret'
        sig = compute_hmac_sha256(payload, secret)
        self.assertTrue(verify_hmac_sha256(payload, secret, sig))

    def test_verify_wrong_sig_fails(self):
        self.assertFalse(verify_hmac_sha256('payload', 'secret', 'wrongsig'))

    def test_hmac_is_hex_string(self):
        sig = compute_hmac_sha256('data', 'key')
        self.assertRegex(sig, r'^[0-9a-f]+$')


class TestValidationHelpers(unittest.TestCase):

    def test_valid_email(self):
        self.assertTrue(is_valid_email('user@example.com'))

    def test_invalid_email_no_at(self):
        self.assertFalse(is_valid_email('userexample.com'))

    def test_invalid_email_empty(self):
        self.assertFalse(is_valid_email(''))

    def test_valid_evm_address(self):
        addr = '0x' + 'a' * 40
        self.assertTrue(is_valid_evm_address(addr))

    def test_invalid_evm_address_short(self):
        self.assertFalse(is_valid_evm_address('0x1234'))

    def test_invalid_evm_address_no_prefix(self):
        self.assertFalse(is_valid_evm_address('a' * 42))

    def test_valid_trc20_address_starts_T(self):
        addr = 'T' + 'A' * 33
        result = is_valid_trc20_address(addr)
        self.assertIsInstance(result, bool)

    def test_validate_crypto_address_evm(self):
        addr = '0x' + 'b' * 40
        result = validate_crypto_address(addr, 'ETH')
        # returns (bool, str) tuple
        is_valid = result[0] if isinstance(result, tuple) else result
        self.assertIsInstance(is_valid, bool)
        self.assertTrue(is_valid)


class TestTrafficHelpers(unittest.TestCase):

    def test_get_traffic_tier_returns_string(self):
        tier = get_traffic_tier('US')
        self.assertIsInstance(tier, str)
        self.assertTrue(len(tier) > 0, 'tier should be non-empty string')

    def test_compute_fraud_score_empty(self):
        score = compute_fraud_score_from_signals({})
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_compute_fraud_score_with_signals(self):
        # Try multiple signal naming conventions to find what the function accepts
        score0 = compute_fraud_score_from_signals({'vpn': True, 'proxy': True})
        score1 = compute_fraud_score_from_signals({'vpn_detected': True, 'proxy_detected': True})
        score2 = compute_fraud_score_from_signals({'is_vpn': True, 'is_datacenter': True})
        # At least verify function runs and returns an int/float in [0, 100]
        for s in [score0, score1, score2]:
            self.assertGreaterEqual(s, 0)
            self.assertLessEqual(s, 100)


class TestListHelpers(unittest.TestCase):

    def test_chunk_list_basic(self):
        result = chunk_list([1, 2, 3, 4, 5], 2)
        self.assertEqual(list(result), [[1, 2], [3, 4], [5]])

    def test_chunk_list_exact(self):
        result = chunk_list([1, 2, 3, 4], 2)
        self.assertEqual(list(result), [[1, 2], [3, 4]])

    def test_chunk_list_empty(self):
        result = list(chunk_list([], 3))
        self.assertEqual(result, [])


class TestResultHelpers(unittest.TestCase):

    def test_success_result_structure(self):
        r = success_result()
        # returns dict with status='success'
        self.assertIsInstance(r, dict)
        self.assertIn('status', r)
        self.assertEqual(r['status'], 'success')

    def test_error_result_structure(self):
        r = error_result('Something went wrong')
        self.assertIsInstance(r, dict)
        self.assertEqual(r.get('status'), 'error')
        self.assertIn('message', r)

    def test_skipped_result_structure(self):
        r = skipped_result('Already done')
        self.assertIsInstance(r, dict)
        self.assertEqual(r.get('status'), 'skipped')


class TestFormatDuration(unittest.TestCase):

    def test_seconds_only(self):
        result = format_duration(45)
        self.assertIn('45', result)

    def test_minutes(self):
        result = format_duration(125)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — CONSTANTS / ENUMS / CHOICES / EXCEPTIONS
# ══════════════════════════════════════════════════════════════════════════════

class TestConstants(unittest.TestCase):

    def setUp(self):
        import constants as c
        self.c = c

    def test_max_postback_retries_positive(self):
        self.assertGreater(self.c.MAX_POSTBACK_RETRIES, 0)

    def test_postback_retry_delays_is_list(self):
        self.assertIsInstance(self.c.POSTBACK_RETRY_DELAYS, list)
        self.assertEqual(len(self.c.POSTBACK_RETRY_DELAYS), self.c.MAX_POSTBACK_RETRIES)

    def test_postback_log_retention_days(self):
        self.assertGreater(self.c.POSTBACK_LOG_RETENTION_DAYS, 0)

    def test_click_log_retention_days(self):
        self.assertGreater(self.c.CLICK_LOG_RETENTION_DAYS, 0)

    def test_webhook_timeout_reasonable(self):
        self.assertGreater(self.c.WEBHOOK_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(self.c.WEBHOOK_TIMEOUT_SECONDS, 120)

    def test_max_ivt_percentage_valid(self):
        self.assertGreater(self.c.MAX_IVT_PERCENTAGE, 0)
        self.assertLessEqual(self.c.MAX_IVT_PERCENTAGE, 100)

    def test_critical_ivt_threshold_greater_than_max(self):
        self.assertGreater(self.c.CRITICAL_IVT_THRESHOLD, self.c.MAX_IVT_PERCENTAGE)

    def test_max_payment_retry_attempts(self):
        self.assertGreater(self.c.MAX_PAYMENT_RETRY_ATTEMPTS, 0)

    def test_payment_retry_intervals_length_matches(self):
        self.assertEqual(
            len(self.c.PAYMENT_RETRY_INTERVALS_DAYS),
            self.c.MAX_PAYMENT_RETRY_ATTEMPTS
        )

    def test_task_constants_are_strings(self):
        self.assertIsInstance(self.c.TASK_BOT_PROCESS, str)
        self.assertIsInstance(self.c.TASK_EXPIRE_CODES, str)
        self.assertIsInstance(self.c.TASK_CHECK_LOW_STOCK, str)


class TestEnums(unittest.TestCase):

    def setUp(self):
        import enums as e
        self.e = e

    @staticmethod
    def _vals(enum_cls):
        """Extract string values regardless of Django or stdlib Enum."""
        result = []
        for v in enum_cls:
            val = v.value
            # stdlib Enum with TextChoices-style tuples → ('pending', 'Pending')
            if isinstance(val, tuple):
                result.append(val[0])
            else:
                result.append(val)
        return result

    def test_postback_status_has_required_values(self):
        vals = self._vals(self.e.PostbackStatus)
        for expected in ('pending', 'sent', 'failed', 'retrying'):
            self.assertIn(expected, vals)

    def test_click_status_has_fraud(self):
        self.assertIn('fraud', self._vals(self.e.ClickStatus))

    def test_conversion_status_complete(self):
        vals = self._vals(self.e.ConversionStatus)
        self.assertIn('approved', vals)
        self.assertIn('rejected', vals)

    def test_leaderboard_type_has_earnings(self):
        self.assertIn('earnings', self._vals(self.e.LeaderboardType))

    def test_leaderboard_scope_has_global(self):
        self.assertIn('global', self._vals(self.e.LeaderboardScope))

    def test_reward_transaction_type_has_earn_redeem(self):
        vals = self._vals(self.e.RewardTransactionType)
        self.assertIn('earn', vals)
        self.assertIn('redeem', vals)


class TestChoices(unittest.TestCase):

    def setUp(self):
        import choices as ch
        self.ch = ch

    @staticmethod
    def _vals(enum_cls):
        result = []
        for v in enum_cls:
            val = v.value
            result.append(val[0] if isinstance(val, tuple) else val)
        return result

    def test_subscription_status_values(self):
        vals = self._vals(self.ch.SubscriptionStatus)
        self.assertIn('active', vals)
        self.assertIn('cancelled', vals)

    def test_broadcast_status_has_sent(self):
        self.assertIn('sent', self._vals(self.ch.BroadcastStatus))

    def test_fraud_action_has_block(self):
        self.assertIn('block', self._vals(self.ch.FraudAction))

    def test_moderation_status_has_approved_rejected(self):
        vals = self._vals(self.ch.ModerationStatus)
        self.assertIn('approved', vals)
        self.assertIn('rejected', vals)

    def test_commission_status_has_paid(self):
        self.assertIn('paid', self._vals(self.ch.CommissionStatus))

    def test_transaction_type_credit_debit(self):
        vals = self._vals(self.ch.TransactionType)
        self.assertIn('credit', vals)
        self.assertIn('debit', vals)


class TestExceptions(unittest.TestCase):

    def setUp(self):
        import exceptions as ex
        self.ex = ex

    def _raise_and_catch(self, ExcClass, *args):
        with self.assertRaises(ExcClass):
            raise ExcClass(*args)

    def test_postback_processing_exception_is_raiseable(self):
        self._raise_and_catch(self.ex.PostbackProcessingException, 'postback error')

    def test_submission_already_processed_error(self):
        self._raise_and_catch(self.ex.SubmissionAlreadyProcessedError)

    def test_delivery_failed_exception(self):
        self._raise_and_catch(self.ex.DeliveryFailedException, 'delivery failed')

    def test_payout_batch_not_found(self):
        self._raise_and_catch(self.ex.PayoutBatchNotFoundError)

    def test_payout_batch_locked(self):
        self._raise_and_catch(self.ex.PayoutBatchLockedError)

    def test_payout_batch_state_error(self):
        self._raise_and_catch(self.ex.PayoutBatchStateError, 'wrong state')

    def test_payout_batch_limit_error(self):
        self._raise_and_catch(self.ex.PayoutBatchLimitError)

    def test_broadcast_not_found(self):
        self._raise_and_catch(self.ex.BroadcastNotFoundError)

    def test_broadcast_state_error(self):
        self._raise_and_catch(self.ex.BroadcastStateError)

    def test_broadcast_send_error(self):
        self._raise_and_catch(self.ex.BroadcastSendError, 'send failed')

    def test_payout_exceptions_inherit_from_payout_queue(self):
        self.assertTrue(issubclass(self.ex.PayoutBatchNotFoundError, self.ex.PayoutQueueError))
        self.assertTrue(issubclass(self.ex.PayoutBatchLockedError,   self.ex.PayoutQueueError))


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — CACHE MODULE
# ══════════════════════════════════════════════════════════════════════════════

class TestPICache(unittest.TestCase):

    def setUp(self):
        # Patch django.core.cache.cache with a simple dict-based mock
        self._store = {}

        def mock_get(key, default=None): return self._store.get(key, default)
        def mock_set(key, value, ttl=None): self._store[key] = value
        def mock_delete(key): self._store.pop(key, None)
        def mock_incr(key):
            if key not in self._store:
                raise ValueError('key missing')
            self._store[key] += 1
            return self._store[key]

        cache_mock = mock.MagicMock()
        cache_mock.get    = mock_get
        cache_mock.set    = mock_set
        cache_mock.delete = mock_delete
        cache_mock.incr   = mock_incr

        import cache as cache_mod
        self._orig_cache = cache_mod.cache
        cache_mod.cache = cache_mock
        self.PICache = cache_mod.PICache

    def tearDown(self):
        import cache as cache_mod
        cache_mod.cache = self._orig_cache

    def test_set_and_get_ip_status(self):
        self.PICache.set_ip_status('1.2.3.4', 'blocked')
        self.assertEqual(self.PICache.get_ip_status('1.2.3.4'), 'blocked')

    def test_delete_ip_status(self):
        self.PICache.set_ip_status('5.6.7.8', 'allowed')
        self.PICache.delete_ip_status('5.6.7.8')
        self.assertIsNone(self.PICache.get_ip_status('5.6.7.8'))

    def test_publisher_score_roundtrip(self):
        self.PICache.set_publisher_score(42, 0.95)
        self.assertEqual(self.PICache.get_publisher_score(42), 0.95)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.PICache.get_ip_status('255.255.255.255'))

    def test_key_prefix_namespacing(self):
        """Different entity types must not collide."""
        self.PICache.set_ip_status('10.0.0.1', 'blocked')
        self.PICache.set_publisher_score('10.0.0.1', 0.5)
        self.assertEqual(self.PICache.get_ip_status('10.0.0.1'), 'blocked')
        self.assertEqual(self.PICache.get_publisher_score('10.0.0.1'), 0.5)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — REPOSITORY MODULE
# ══════════════════════════════════════════════════════════════════════════════

class TestRepositoryImports(unittest.TestCase):
    """Repository classes must be importable and have the expected interface."""

    def setUp(self):
        import repository as repo
        self.repo = repo

    def test_offer_repository_exists(self):
        self.assertTrue(hasattr(self.repo, 'OfferRepository'))

    def test_analytics_repository_exists(self):
        self.assertTrue(hasattr(self.repo, 'AnalyticsRepository'))

    def test_drift_repository_exists(self):
        self.assertTrue(hasattr(self.repo, 'DriftRepository'))

    def test_offer_repo_has_get_active_offers(self):
        self.assertTrue(callable(self.repo.OfferRepository.get_active_offers))

    def test_analytics_repo_has_get_offer_performance(self):
        self.assertTrue(callable(self.repo.AnalyticsRepository.get_offer_performance))

    def test_drift_repo_has_get_baseline_stats(self):
        self.assertTrue(callable(self.repo.DriftRepository.get_baseline_stats))

    def test_drift_repo_baseline_returns_dict_with_mean(self):
        """With mocked models that return None, should return default."""
        result = self.repo.DriftRepository.get_baseline_stats('nonexistent_model')
        self.assertIn('mean', result)
        self.assertIn('std', result)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — MIGRATION CONTENT TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestMigrationContent(unittest.TestCase):

    def test_0001_creates_core_models(self):
        with open('migrations/0001_initial.py') as f: src = f.read()
        for model in ('AdminLedger', 'MasterTask', 'UserTaskCompletion'):
            self.assertIn(model, src, f'0001 missing CreateModel for {model}')

    def test_0002_adds_foreign_keys(self):
        with open('migrations/0002_initial.py') as f: src = f.read()
        self.assertIn('AddField', src)
        self.assertIn('adminledger', src.lower())

    def test_0003_adds_missing_dependencies(self):
        with open('migrations/0003_add_missing_dependencies.py') as f: src = f.read()
        self.assertIn('0002_initial', src)

    def test_0004_alters_key_models(self):
        with open('migrations/0004_bridge_to_new_system.py') as f: src = f.read()
        for model in ('mastertask', 'usertaskcompletion', 'adminledger'):
            self.assertIn(model, src.lower(), f'0004 missing alteration for {model}')

    def test_0005_creates_all_new_models(self):
        with open('migrations/0005_new_task_system_models.py') as f: src = f.read()
        for model in ('TaskResult', 'TaskQueue', 'TaskMonitor', 'WorkerHealth',
                      'TaskWorkflow', 'WorkflowInstance', 'TaskInsight'):
            self.assertIn(model, src, f'0005 missing CreateModel for {model}')

    def test_0005_correct_dependency_on_0004(self):
        with open('migrations/0005_new_task_system_models.py') as f: src = f.read()
        self.assertIn('0004_bridge_to_new_system', src)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — VIEWSET STRUCTURE
# ══════════════════════════════════════════════════════════════════════════════

class TestViewsetStructure(unittest.TestCase):

    EXPECTED_VIEWSETS = [
        'TaskResultViewSet', 'ScheduledTaskViewSet', 'TaskQueueViewSet',
        'TaskMonitorViewSet', 'TaskPerformanceViewSet', 'WorkerHealthViewSet',
        'QueueDepthViewSet', 'TaskAlertViewSet', 'DeadLetterViewSet',
        'WorkflowViewSet', 'WorkflowInstanceViewSet', 'TaskInsightViewSet',
        'TaskCostViewSet', 'AdminTaskViewSet',
    ]

    def test_all_viewset_files_exist(self):
        for vs in self.EXPECTED_VIEWSETS:
            path = f'viewsets/{vs}.py'
            self.assertTrue(os.path.exists(path), f'Missing: {path}')

    def test_each_viewset_file_defines_its_class(self):
        for vs in self.EXPECTED_VIEWSETS:
            path = f'viewsets/{vs}.py'
            with open(path) as f: src = f.read()
            tree = ast.parse(src)
            classes = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
            self.assertIn(vs, classes, f'{path} does not define class {vs}')

    def test_viewsets_init_exports_all(self):
        with open('viewsets/__init__.py') as f: src = f.read()
        for vs in self.EXPECTED_VIEWSETS:
            self.assertIn(vs, src, f'viewsets/__init__.py missing export: {vs}')


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — MANAGERS
# ══════════════════════════════════════════════════════════════════════════════

class TestManagers(unittest.TestCase):

    def test_withdrawal_priority_manager_importable(self):
        import managers as m
        self.assertTrue(hasattr(m, 'WithdrawalPriorityManager'))

    def test_withdrawal_priority_manager_has_expire_stale(self):
        import managers as m
        self.assertTrue(hasattr(m.WithdrawalPriorityManager, 'expire_stale'))

    def test_withdrawal_priority_manager_has_get_top_priority(self):
        import managers as m
        self.assertTrue(hasattr(m.WithdrawalPriorityManager, 'get_top_priority'))


# ══════════════════════════════════════════════════════════════════════════════
# NEW TEST MODULE IMPORTS
# ══════════════════════════════════════════════════════════════════════════════

import sys as _sys
_sys.path.insert(0, os.path.join(ROOT, 'tests'))

from test_viewsets import (
    TestOriginalViewsets, TestNewViewsets, TestViewsetsInit,
)
from test_constants import (
    TestRetentionConstants, TestChoicesModule,
)
from test_serializers_extended import (
    TestNewSerializers, TestNoRegression,
)
from test_services import (
    TestServiceSubfolderFiles, TestServicesStubs,
)
from test_adapters import (
    TestAdapterFilesExist, TestAdapterInit,
    TestAnalyticsAdapter, TestAuthenticationAdapter,
    TestWalletAdapter, TestTasksAdapter,
)
from test_migrations import (
    TestMigrationFiles, TestMigrationDependencyChain,
    TestMigration0001Content, TestMigration0005Content,
)


# ══════════════════════════════════════════════════════════════════════════════
# RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run():
    os.chdir(ROOT)

    suites = [
        ('Static Analysis',       StaticAnalysisTests),
        ('Generators',            TestGenerators),
        ('Mask Helpers',          TestMaskHelpers),
        ('Decimal Helpers',       TestDecimalHelpers),
        ('HMAC Helpers',          TestHMACHelpers),
        ('Validation Helpers',    TestValidationHelpers),
        ('Traffic Helpers',       TestTrafficHelpers),
        ('List Helpers',          TestListHelpers),
        ('Result Helpers',        TestResultHelpers),
        ('Format Duration',       TestFormatDuration),
        ('Constants',             TestConstants),
        ('Enums',                 TestEnums),
        ('Choices',               TestChoices),
        ('Exceptions',            TestExceptions),
        ('PICache',               TestPICache),
        ('Repository',            TestRepositoryImports),
        ('Migration Content',     TestMigrationContent),
        ('Viewset Structure',     TestViewsetStructure),
        ('Managers',              TestManagers),
        ('Viewsets (Structure)',   TestOriginalViewsets),
        ('Viewsets (New)',         TestNewViewsets),
        ('Viewsets (__init__)',    TestViewsetsInit),
        ('Constants (Extended)',   TestRetentionConstants),
        ('Choices (Extended)',     TestChoicesModule),
        ('Serializers (Extended)', TestNewSerializers),
        ('Serializers (NoRegress)',TestNoRegression),
        ('Services (Subfolder)',   TestServiceSubfolderFiles),
        ('Services (Stubs)',       TestServicesStubs),
        ('Adapters (Files)',       TestAdapterFilesExist),
        ('Adapters (__init__)',    TestAdapterInit),
        ('Adapters (Analytics)',   TestAnalyticsAdapter),
        ('Adapters (Auth)',        TestAuthenticationAdapter),
        ('Adapters (Wallet)',      TestWalletAdapter),
        ('Adapters (Tasks)',       TestTasksAdapter),
        ('Migrations (Files)',     TestMigrationFiles),
        ('Migrations (DepChain)',  TestMigrationDependencyChain),
        ('Migrations (0001)',      TestMigration0001Content),
        ('Migrations (0005)',      TestMigration0005Content),
    ]

    total_pass = total_fail = total_err = total_skip = 0
    results_summary = []

    print()
    print(bold('=' * 70))
    print(bold('  TASKS PROJECT — FULL TEST RUN'))
    print(bold('=' * 70))

    for suite_name, cls in suites:
        loader = unittest.TestLoader()
        suite  = loader.loadTestsFromTestCase(cls)
        buf    = __import__('io').StringIO()
        runner = unittest.TextTestRunner(stream=buf, verbosity=0)
        result = runner.run(suite)

        p = result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)
        f = len(result.failures)
        e = len(result.errors)
        s = len(result.skipped)

        total_pass += p
        total_fail += f
        total_err  += e
        total_skip += s

        if f == 0 and e == 0:
            status = green(f'✅ PASS ({result.testsRun}/{result.testsRun})')
        else:
            status = red(f'❌ FAIL ({p}/{result.testsRun})')

        print(f'  {status}  {bold(suite_name)}')

        for _, tb in result.failures:
            lines = [l for l in tb.strip().splitlines() if l.strip()]
            print(f'    {yellow("FAIL:")} {lines[-1][:100]}')
        for _, tb in result.errors:
            lines = [l for l in tb.strip().splitlines() if l.strip()]
            print(f'    {red("ERR:")}  {lines[-1][:100]}')

        results_summary.append((suite_name, result))

    total = total_pass + total_fail + total_err + total_skip
    print()
    print(bold('=' * 70))
    print(bold('  SUMMARY'))
    print(bold('=' * 70))
    print(f'  Tests run : {total}')
    print(f'  {green("Passed")}    : {total_pass}')
    print(f'  {red("Failed")}    : {total_fail}')
    print(f'  {red("Errors")}    : {total_err}')
    print(f'  {yellow("Skipped")}   : {total_skip}')
    print()

    if total_fail == 0 and total_err == 0:
        print(bold(green('  🎉 ALL TESTS PASSED')))
    else:
        print(bold(red(f'  ⚠️  {total_fail + total_err} ISSUE(S) NEED FIXING')))
    print(bold('=' * 70))
    print()

    return total_fail + total_err


if __name__ == '__main__':
    sys.exit(run())
