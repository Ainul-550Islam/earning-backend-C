"""
tests/test_adapters.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Structural tests for api/adapters/ — function presence,
signature sanity, and __init__.py export completeness.
"""
import ast
import os
import unittest

ROOT         = os.path.dirname(os.path.dirname(__file__))
ADAPTER_DIR  = os.path.join(ROOT, 'api', 'adapters')
ADAPTER_INIT = os.path.join(ADAPTER_DIR, '__init__.py')


def _parse(path):
    with open(path) as f:
        return ast.parse(f.read())


def _public_funcs(tree):
    """Module-level public functions only."""
    return {
        n.name for n in ast.iter_child_nodes(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not n.name.startswith('_')
    }


def _public_classes(tree):
    return {
        n.name for n in ast.iter_child_nodes(tree)
        if isinstance(n, ast.ClassDef)
        and not n.name.startswith('_')
    }


def _all_adapter_files():
    return [f for f in os.listdir(ADAPTER_DIR)
            if f.endswith('.py') and f not in ('__init__.py', 'tests.py')]


# ── 1. File-level checks ──────────────────────────────────────────────────────

class TestAdapterFilesExist(unittest.TestCase):
    REQUIRED = [
        'admin_panel.py', 'ai_engine.py', 'alerts.py', 'analytics.py',
        'audit_logs.py', 'audit_trail.py', 'authentication.py', 'backup.py',
        'cache.py', 'cms.py', 'compliance.py', 'djoyalty.py', 'engagement.py',
        'fraud_detection.py', 'gamification.py', 'integrations.py', 'kyc.py',
        'localization.py', 'maintenance.py', 'marketplace.py', 'notifications.py',
        'offerwall.py', 'payment_gateways.py', 'postback_engine.py',
        'promotions.py', 'rate_limit.py', 'referral.py', 'reports.py',
        'security.py', 'subscription.py', 'support.py', 'tasks.py',
        'users.py', 'wallet.py',
    ]

    def test_required_files_exist(self):
        for fname in self.REQUIRED:
            with self.subTest(fname=fname):
                self.assertTrue(
                    os.path.exists(os.path.join(ADAPTER_DIR, fname)),
                    f'Missing adapter file: {fname}'
                )

    def test_init_file_exists(self):
        self.assertTrue(os.path.exists(ADAPTER_INIT),
                        'api/adapters/__init__.py is missing')

    def test_no_syntax_errors_in_any_adapter(self):
        for fname in _all_adapter_files():
            path = os.path.join(ADAPTER_DIR, fname)
            with self.subTest(fname=fname):
                try:
                    _parse(path)
                except SyntaxError as e:
                    self.fail(f'{fname}: {e}')

    def test_no_duplicate_functions_in_any_adapter(self):
        for fname in _all_adapter_files():
            path = os.path.join(ADAPTER_DIR, fname)
            try:
                tree = _parse(path)
            except Exception:
                continue
            with self.subTest(fname=fname):
                seen = {}
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name in seen:
                            self.fail(
                                f'{fname}: duplicate function "{node.name}" '
                                f'at lines {seen[node.name]} and {node.lineno}'
                            )
                        seen[node.name] = node.lineno


# ── 2. __init__.py completeness ───────────────────────────────────────────────

class TestAdapterInit(unittest.TestCase):

    def _init_content(self):
        with open(ADAPTER_INIT) as f:
            return f.read()

    def test_init_imports_all_adapter_modules(self):
        content = self._init_content()
        required_modules = [
            'admin_panel', 'ai_engine', 'alerts', 'analytics', 'audit_logs',
            'audit_trail', 'authentication', 'backup', 'cache', 'cms',
            'compliance', 'djoyalty', 'engagement', 'fraud_detection',
            'gamification', 'integrations', 'kyc', 'localization', 'maintenance',
            'marketplace', 'notifications', 'offerwall', 'payment_gateways',
            'postback_engine', 'promotions', 'rate_limit', 'referral',
            'reports', 'security', 'subscription', 'support', 'tasks',
            'users', 'wallet',
        ]
        for mod in required_modules:
            with self.subTest(module=mod):
                self.assertIn(f'.{mod}', content,
                              f'__init__.py does not import from .{mod}')

    def test_init_has_all_list(self):
        content = self._init_content()
        self.assertIn('__all__', content)

    def test_no_name_collisions_in_init(self):
        """Verify no two imports use the same unaliased name."""
        tree    = _parse(ADAPTER_INIT)
        seen    = {}
        issues  = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            for alias in node.names:
                bound_name = alias.asname if alias.asname else alias.name
                if bound_name in seen:
                    issues.append(
                        f'"{bound_name}" imported twice '
                        f'(from .{seen[bound_name]} and .{node.module})'
                    )
                else:
                    seen[bound_name] = node.module or '?'
        self.assertEqual(issues, [], 'Name collisions in adapters/__init__.py:\n' + '\n'.join(issues))

    def test_aliased_payment_gateway_functions(self):
        """payment_gateways names that clash with wallet must be aliased."""
        content = self._init_content()
        self.assertIn('get_gateway_payment_methods', content)
        self.assertIn('get_gateway_transaction_history', content)


# ── 3. Per-adapter function checks ───────────────────────────────────────────

class TestAnalyticsAdapter(unittest.TestCase):
    def setUp(self):
        self.tree = _parse(os.path.join(ADAPTER_DIR, 'analytics.py'))
        self.funcs = _public_funcs(self.tree)

    def test_user_analytics_exists(self):
        self.assertIn('user_analytics', self.funcs)

    def test_revenue_analytics_exists(self):
        self.assertIn('revenue_analytics', self.funcs)

    def test_platform_analytics_exists(self):
        self.assertIn('platform_analytics', self.funcs)

    def test_real_time_analytics_exists(self):
        self.assertIn('real_time_analytics', self.funcs)


class TestAuthenticationAdapter(unittest.TestCase):
    def setUp(self):
        self.tree    = _parse(os.path.join(ADAPTER_DIR, 'authentication.py'))
        self.funcs   = _public_funcs(self.tree)
        self.classes = _public_classes(self.tree)

    def test_custom_token_authentication_class(self):
        self.assertIn('CustomTokenAuthentication', self.classes)

    def test_login_user_exists(self):
        self.assertIn('login_user', self.funcs)

    def test_logout_user_exists(self):
        self.assertIn('logout_user', self.funcs)

    def test_refresh_token_exists(self):
        self.assertIn('refresh_token', self.funcs)


class TestWalletAdapter(unittest.TestCase):
    def setUp(self):
        self.tree  = _parse(os.path.join(ADAPTER_DIR, 'wallet.py'))
        self.funcs = _public_funcs(self.tree)

    def test_get_wallet_balance_exists(self):
        self.assertIn('get_wallet_balance', self.funcs)

    def test_create_withdrawal_request_exists(self):
        self.assertIn('create_withdrawal_request', self.funcs)

    def test_get_withdrawal_history_exists(self):
        self.assertIn('get_withdrawal_history', self.funcs)

    def test_get_wallet_analytics_exists(self):
        self.assertIn('get_wallet_analytics', self.funcs)


class TestNotificationsAdapter(unittest.TestCase):
    def setUp(self):
        self.tree  = _parse(os.path.join(ADAPTER_DIR, 'notifications.py'))
        self.funcs = _public_funcs(self.tree)

    def test_get_notifications_exists(self):
        self.assertIn('get_notifications', self.funcs)

    def test_create_notification_exists(self):
        self.assertIn('create_notification', self.funcs)

    def test_mark_notification_read_exists(self):
        self.assertIn('mark_notification_read', self.funcs)

    def test_notification_settings_exists(self):
        self.assertIn('notification_settings', self.funcs)


class TestFraudDetectionAdapter(unittest.TestCase):
    def setUp(self):
        self.tree  = _parse(os.path.join(ADAPTER_DIR, 'fraud_detection.py'))
        self.funcs = _public_funcs(self.tree)

    def test_fraud_profile_exists(self):
        self.assertIn('fraud_profile', self.funcs)

    def test_fraud_dashboard_exists(self):
        self.assertIn('fraud_dashboard', self.funcs)

    def test_fraud_alerts_exists(self):
        self.assertIn('fraud_alerts', self.funcs)


class TestOfferwallAdapter(unittest.TestCase):
    def setUp(self):
        self.tree  = _parse(os.path.join(ADAPTER_DIR, 'offerwall.py'))
        self.funcs = _public_funcs(self.tree)

    def test_get_offers_exists(self):
        self.assertIn('get_offers', self.funcs)

    def test_get_offer_details_exists(self):
        self.assertIn('get_offer_details', self.funcs)

    def test_start_offer_exists(self):
        self.assertIn('start_offer', self.funcs)

    def test_complete_offer_exists(self):
        self.assertIn('complete_offer', self.funcs)


class TestPaymentGatewaysAdapter(unittest.TestCase):
    def setUp(self):
        self.tree  = _parse(os.path.join(ADAPTER_DIR, 'payment_gateways.py'))
        self.funcs = _public_funcs(self.tree)

    def test_get_payment_methods_exists(self):
        self.assertIn('get_payment_methods', self.funcs)

    def test_create_withdrawal_exists(self):
        self.assertIn('create_withdrawal', self.funcs)

    def test_get_transaction_history_exists(self):
        self.assertIn('get_transaction_history', self.funcs)


class TestTasksAdapter(unittest.TestCase):
    def setUp(self):
        self.tree  = _parse(os.path.join(ADAPTER_DIR, 'tasks.py'))
        self.funcs = _public_funcs(self.tree)

    def test_get_user_tasks_exists(self):
        self.assertIn('get_user_tasks', self.funcs)

    def test_get_task_details_exists(self):
        self.assertIn('get_task_details', self.funcs)

    def test_start_task_exists(self):
        self.assertIn('start_task', self.funcs)

    def test_submit_task_proof_exists(self):
        self.assertIn('submit_task_proof', self.funcs)


class TestGamificationAdapter(unittest.TestCase):
    def setUp(self):
        self.tree  = _parse(os.path.join(ADAPTER_DIR, 'gamification.py'))
        self.funcs = _public_funcs(self.tree)

    def test_get_leaderboard_exists(self):
        self.assertIn('get_leaderboard', self.funcs)

    def test_get_achievements_exists(self):
        self.assertIn('get_achievements', self.funcs)


class TestKYCAdapter(unittest.TestCase):
    def setUp(self):
        self.tree  = _parse(os.path.join(ADAPTER_DIR, 'kyc.py'))
        self.funcs = _public_funcs(self.tree)

    def test_get_kyc_profile_exists(self):
        self.assertIn('get_kyc_profile', self.funcs)

    def test_start_kyc_verification_exists(self):
        self.assertIn('start_kyc_verification', self.funcs)

    def test_upload_kyc_document_exists(self):
        self.assertIn('upload_kyc_document', self.funcs)


class TestReferralAdapter(unittest.TestCase):
    def setUp(self):
        self.tree  = _parse(os.path.join(ADAPTER_DIR, 'referral.py'))
        self.funcs = _public_funcs(self.tree)

    def test_referral_profile_exists(self):
        self.assertIn('referral_profile', self.funcs)

    def test_create_referral_exists(self):
        self.assertIn('create_referral', self.funcs)

    def test_referral_history_exists(self):
        self.assertIn('referral_history', self.funcs)


class TestReportsAdapter(unittest.TestCase):
    def setUp(self):
        self.tree  = _parse(os.path.join(ADAPTER_DIR, 'reports.py'))
        self.funcs = _public_funcs(self.tree)

    def test_get_available_reports_exists(self):
        self.assertIn('get_available_reports', self.funcs)

    def test_generate_report_exists(self):
        self.assertIn('generate_report', self.funcs)

    def test_get_report_history_exists(self):
        self.assertIn('get_report_history', self.funcs)


class TestBackupAdapter(unittest.TestCase):
    def setUp(self):
        self.tree  = _parse(os.path.join(ADAPTER_DIR, 'backup.py'))
        self.funcs = _public_funcs(self.tree)

    def test_get_backup_status_exists(self):
        self.assertIn('get_backup_status', self.funcs)

    def test_create_backup_exists(self):
        self.assertIn('create_backup', self.funcs)

    def test_restore_backup_exists(self):
        self.assertIn('restore_backup', self.funcs)


class TestCMSAdapter(unittest.TestCase):
    def setUp(self):
        self.tree  = _parse(os.path.join(ADAPTER_DIR, 'cms.py'))
        self.funcs = _public_funcs(self.tree)

    def test_get_content_list_exists(self):
        self.assertIn('get_content_list', self.funcs)

    def test_create_content_exists(self):
        self.assertIn('create_content', self.funcs)

    def test_no_duplicate_keyword_arg(self):
        """cms.py body= fix must be in place (no duplicate 'content=' kwarg)."""
        with open(os.path.join(ADAPTER_DIR, 'cms.py')) as f:
            src = f.read()
        # The old bug had two content= in the same .create() call
        # A quick heuristic: count consecutive 'content=' occurrences within 10 lines
        lines = src.splitlines()
        for i, line in enumerate(lines):
            if 'content=content' in line:
                # Next 8 lines should NOT also have 'content='
                nearby = lines[i+1:i+8]
                for nl in nearby:
                    self.assertNotIn(
                        "content=section_data",
                        nl,
                        'cms.py still has duplicate content= kwarg bug'
                    )
                break


class TestAnalyticsAdapterBugFix(unittest.TestCase):
    def test_round_parentheses_fixed(self):
        """analytics.py round(((... bug must be fixed."""
        with open(os.path.join(ADAPTER_DIR, 'analytics.py')) as f:
            src = f.read()
        self.assertNotIn(
            'round(((', src,
            'analytics.py still has triple-paren round() bug'
        )


class TestAdapterRequestSignatures(unittest.TestCase):
    """Every public adapter function should accept 'request' as first param."""

    def _first_param(self, func_node):
        args = func_node.args.args
        if args:
            return args[0].arg
        return None

    def _check_adapter(self, fname):
        path = os.path.join(ADAPTER_DIR, fname)
        if not os.path.exists(path):
            return
        tree = _parse(path)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith('_'):
                    continue
                first = self._first_param(node)
                with self.subTest(file=fname, func=node.name):
                    self.assertEqual(
                        first, 'request',
                        f'{fname}::{node.name} first param should be "request", got "{first}"'
                    )

    def test_analytics_request_params(self):
        self._check_adapter('analytics.py')

    def test_wallet_request_params(self):
        self._check_adapter('wallet.py')

    def test_notifications_request_params(self):
        self._check_adapter('notifications.py')

    def test_tasks_request_params(self):
        self._check_adapter('tasks.py')

    def test_users_request_params(self):
        self._check_adapter('users.py')


if __name__ == '__main__':
    unittest.main()
