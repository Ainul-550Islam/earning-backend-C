# api/djoyalty/tests/test_audit_fixes_v4.py
"""
Tests for all 5 audit fixes applied in v4:
  2.3 — LeaderboardService removed from GamificationSerializer
  2.4 — AnalyticsService wrapper covering all analytics modules
  2.5 — is_global replaces tenant__isnull=True in DjoyaltyTenantMixin
  4   — Meta.indexes present on all 33 previously-missing models
  5   — DjoyaltyBaseViewSet on all 53 viewsets
"""
import ast
import os
import inspect
import importlib
from unittest.mock import MagicMock, patch, PropertyMock
from django.test import TestCase, RequestFactory

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 2.3 — LeaderboardService NOT in GamificationSerializer
# ═══════════════════════════════════════════════════════════════════════════════

class TestFix23SerializerNoService(TestCase):
    """GamificationSerializer must NOT import or call LeaderboardService."""

    def _get_serializer_src(self):
        path = os.path.join(BASE, 'serializers', 'GamificationSerializer.py')
        with open(path) as f:
            return f.read()

    def test_leaderboard_service_not_at_top_level_import(self):
        """No top-level 'from ...services... import LeaderboardService'."""
        src = self._get_serializer_src()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom):
                    names = [a.name for a in node.names]
                    self.assertNotIn(
                        'LeaderboardService', names,
                        "LeaderboardService must not be a top-level import in GamificationSerializer"
                    )

    def test_get_my_rank_uses_getattr(self):
        """get_my_rank() must read obj.customer_rank via getattr, not call a service."""
        src = self._get_serializer_src()
        self.assertIn(
            "getattr(obj, 'customer_rank', 0)", src,
            "get_my_rank() must read pre-annotated customer_rank via getattr(obj, 'customer_rank', 0)"
        )

    def test_viewset_owns_rank_annotation(self):
        """GamificationViewSet must have _annotate_customer_rank method."""
        path = os.path.join(BASE, 'viewsets', 'advanced', 'GamificationViewSet.py')
        with open(path) as f:
            src = f.read()
        self.assertIn(
            '_annotate_customer_rank', src,
            "LeaderboardSeasonViewSet must define _annotate_customer_rank()"
        )

    def test_viewset_overrides_list_and_retrieve(self):
        """LeaderboardSeasonViewSet must override list() and retrieve() to inject ranks."""
        path = os.path.join(BASE, 'viewsets', 'advanced', 'GamificationViewSet.py')
        with open(path) as f:
            src = f.read()
        self.assertIn('def list(self, request', src)
        self.assertIn('def retrieve(self, request', src)

    def test_list_calls_annotate(self):
        """list() must call _annotate_customer_rank before serialization."""
        path = os.path.join(BASE, 'viewsets', 'advanced', 'GamificationViewSet.py')
        with open(path) as f:
            src = f.read()
        # Find the list method body and check it calls _annotate_customer_rank
        self.assertIn('_annotate_customer_rank', src.split('def list(')[1][:500],
                      "list() must call _annotate_customer_rank before serializer.data")


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 2.4 — AnalyticsService is the sole gateway
# ═══════════════════════════════════════════════════════════════════════════════

class TestFix24AnalyticsService(TestCase):
    """AnalyticsViewSet must import only AnalyticsService, not raw analytics modules."""

    def _get_viewset_src(self):
        path = os.path.join(BASE, 'viewsets', 'advanced', 'AnalyticsViewSet.py')
        with open(path) as f:
            return f.read()

    def test_no_direct_kpi_tracker_import_in_viewset(self):
        src = self._get_viewset_src()
        self.assertNotIn(
            'from ...kpi_tracker import', src,
            "AnalyticsViewSet must not import kpi_tracker directly (use AnalyticsService)"
        )

    def test_no_direct_ltv_calculator_import_in_viewset(self):
        src = self._get_viewset_src()
        self.assertNotIn(
            'from ...ltv_calculator import', src,
            "AnalyticsViewSet must not import ltv_calculator directly"
        )

    def test_no_direct_cohort_analysis_import_in_viewset(self):
        src = self._get_viewset_src()
        self.assertNotIn(
            'from ...cohort_analysis import', src,
            "AnalyticsViewSet must not import cohort_analysis directly"
        )

    def test_analytics_service_imported_in_viewset(self):
        src = self._get_viewset_src()
        self.assertIn(
            'from ...services.AnalyticsService import AnalyticsService', src,
            "AnalyticsViewSet must import AnalyticsService"
        )

    def test_analytics_service_file_exists(self):
        path = os.path.join(BASE, 'services', 'AnalyticsService.py')
        self.assertTrue(os.path.exists(path), "services/AnalyticsService.py must exist")

    def test_analytics_service_has_required_methods(self):
        path = os.path.join(BASE, 'services', 'AnalyticsService.py')
        with open(path) as f:
            src = f.read()
        for method in [
            'get_kpi_dashboard', 'get_kpi_history', 'get_customer_ltv',
            'get_customer_full_analytics', 'get_cohort_table', 'get_overview',
            'get_points_analytics', 'get_segment_analytics', 'get_campaign_stats',
            'get_report_summary', 'get_report_points', 'get_report_tiers', 'get_report_campaigns',
        ]:
            self.assertIn(
                f'def {method}', src,
                f"AnalyticsService must define {method}()"
            )

    def test_viewset_uses_from_service(self):
        """Every analytics action must use self.from_service(result)."""
        src = self._get_viewset_src()
        self.assertIn('self.from_service(result)', src,
                      "AnalyticsViewSet actions must use self.from_service(result)")


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 2.5 — is_global replaces tenant__isnull=True
# ═══════════════════════════════════════════════════════════════════════════════

class TestFix25IsGlobal(TestCase):
    """DjoyaltyTenantMixin must use is_global=True, not tenant__isnull=True."""

    def _get_mixins_src(self):
        with open(os.path.join(BASE, 'mixins.py')) as f:
            return f.read()

    def _get_abstracts_src(self):
        with open(os.path.join(BASE, 'abstracts.py')) as f:
            return f.read()

    def test_tenant_mixin_has_is_global_field(self):
        src = self._get_abstracts_src()
        self.assertIn('is_global', src,
                      "TenantMixin must define is_global BooleanField")
        self.assertIn('BooleanField', src)

    def test_is_global_defaults_false(self):
        src = self._get_abstracts_src()
        # default=False must appear in the is_global field definition
        tree = ast.parse(src)
        found_default_false = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == 'TenantMixin':
                for item in ast.walk(node):
                    if isinstance(item, ast.Call):
                        func_name = getattr(item.func, 'attr', '') or getattr(item.func, 'id', '')
                        if func_name == 'BooleanField':
                            for kw in item.keywords:
                                if kw.arg == 'default' and isinstance(kw.value, ast.Constant):
                                    if kw.value.value is False:
                                        found_default_false = True
        self.assertTrue(found_default_false,
                        "TenantMixin.is_global must have default=False")

    def test_mixin_filter_uses_is_global_not_isnull(self):
        src = self._get_mixins_src()
        # The live filter logic must NOT have tenant__isnull=True
        # (comments/docstrings may mention it, but not as code)
        lines = src.splitlines()
        code_lines = [l for l in lines if not l.strip().startswith('#')
                      and 'tenant__isnull=True' in l
                      and '"""' not in l and "'''" not in l]
        self.assertEqual(
            len(code_lines), 0,
            f"Live code must not use tenant__isnull=True. Found: {code_lines}"
        )

    def test_mixin_filter_uses_is_global(self):
        src = self._get_mixins_src()
        self.assertIn(
            "Q(is_global=True)", src,
            "DjoyaltyTenantMixin.get_queryset() must use Q(is_global=True)"
        )

    def test_migration_0015_exists(self):
        mig = os.path.join(BASE, 'migrations', '0015_tenant_mixin_is_global.py')
        self.assertTrue(os.path.exists(mig), "Migration 0015 for is_global must exist")

    def test_migration_0015_adds_field(self):
        mig = os.path.join(BASE, 'migrations', '0015_tenant_mixin_is_global.py')
        with open(mig) as f:
            src = f.read()
        self.assertIn('AddField', src, "Migration 0015 must use AddField operations")
        self.assertIn('is_global', src)

    def test_migration_0016_exists(self):
        mig = os.path.join(BASE, 'migrations', '0016_new_meta_indexes.py')
        self.assertTrue(os.path.exists(mig), "Migration 0016 for Meta.indexes must exist")


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 4 — Meta.indexes on all 33 models
# ═══════════════════════════════════════════════════════════════════════════════

class TestFix4MetaIndexes(TestCase):
    """Verify every model that was missing indexes now has them in Meta.indexes."""

    REQUIRED = {
        'models/advanced.py':      ['PointsAlert', 'LoyaltyFraudRule'],
        'models/audit.py':         ['ProductCatalogRule', 'MultiCurrencyRate', 'SystemConfig'],
        'models/campaigns.py':     ['CampaignSegment', 'ReferralPointsRule'],
        'models/cashout.py':       ['CustomerMobileWallet', 'CashoutRate'],
        'models/catalog.py':       ['RewardCatalogCategory', 'SmartLinkClick', 'WebhookSubscription'],
        'models/earn_rules.py':    ['EarnRuleCondition', 'EarnRuleTierMultiplier', 'EarnRuleLog'],
        'models/engagement.py':    ['StreakReward', 'Badge', 'Milestone', 'UserMilestone'],
        'models/family_eco.py':    ['EcoAction', 'CustomerEcoStats', 'CharityCause',
                                    'ExperientialRegistration', 'ReceiptEarnRule'],
        'models/gamification.py':  ['SpinWheelConfig', 'SpinWheelSlice', 'LotteryDraw',
                                    'LeaderboardSeason', 'QuizReward'],
        'models/notifications.py': ['NotificationTemplate', 'NotificationPreference'],
        'models/offerwall.py':     ['OfferWall', 'ContentLock', 'ContentUnlock'],
        'models/redemption.py':    ['RedemptionHistory', 'VoucherRedemption'],
        'models/referral.py':      ['ReferralProgram'],
        'models/social.py':        ['SocialShareReward', 'ReviewReward',
                                    'CustomerReview', 'CustomerSegment'],
        'models/tiers.py':         ['TierBenefit', 'TierConfig'],
    }

    def _model_has_indexes(self, src: str, class_name: str) -> bool:
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, ast.ClassDef) and item.name == 'Meta':
                        for stmt in item.body:
                            if isinstance(stmt, ast.Assign):
                                for t in stmt.targets:
                                    if isinstance(t, ast.Name) and t.id == 'indexes':
                                        return True
        return False

    def test_all_required_models_have_indexes(self):
        missing = []
        for rel_path, models in self.REQUIRED.items():
            full_path = os.path.join(BASE, rel_path)
            if not os.path.exists(full_path):
                missing.append(f"{rel_path} (FILE MISSING)")
                continue
            with open(full_path) as f:
                src = f.read()
            for model in models:
                if not self._model_has_indexes(src, model):
                    missing.append(f"{rel_path}:{model}")

        self.assertEqual(
            missing, [],
            f"These models are still missing Meta.indexes: {missing}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 5 — DjoyaltyBaseViewSet on all viewsets
# ═══════════════════════════════════════════════════════════════════════════════

class TestFix5AllViewsetsInherit(TestCase):
    """Every viewset file must import and use DjoyaltyBaseViewSet."""

    def _get_viewset_files(self):
        vs_dir = os.path.join(BASE, 'viewsets')
        result = []
        for root, dirs, files in os.walk(vs_dir):
            dirs[:] = [d for d in dirs if d not in ['__pycache__']]
            for f in files:
                if f.endswith('.py') and f != '__init__.py':
                    result.append(os.path.join(root, f))
        return result

    def test_all_viewsets_import_djoyalty_base(self):
        missing = []
        for path in self._get_viewset_files():
            with open(path) as f:
                src = f.read()
            if 'DjoyaltyBaseViewSet' not in src:
                missing.append(path.replace(BASE + '/', ''))
        self.assertEqual(
            missing, [],
            f"These viewsets are missing DjoyaltyBaseViewSet: {missing}"
        )

    def test_all_viewset_classes_inherit_base(self):
        """Every class FooViewSet(...) must have DjoyaltyBaseViewSet in its bases."""
        bad = []
        for path in self._get_viewset_files():
            with open(path) as f:
                src = f.read()
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name.endswith('ViewSet'):
                    base_names = []
                    for b in node.bases:
                        base_names.append(getattr(b, 'id', '') or getattr(b, 'attr', ''))
                    if 'DjoyaltyBaseViewSet' not in base_names:
                        bad.append(
                            f"{path.replace(BASE+'/','')}: {node.name}({', '.join(base_names)})"
                        )
        self.assertEqual(bad, [],
                         f"ViewSet classes missing DjoyaltyBaseViewSet in bases: {bad}")

    def test_response_helpers_exist(self):
        """DjoyaltyBaseViewSet depends on DjoyaltyResponse — must exist."""
        path = os.path.join(BASE, 'response_helpers.py')
        self.assertTrue(os.path.exists(path))
        with open(path) as f:
            src = f.read()
        for method in ['ok', 'err', 'not_found', 'forbidden', 'from_service',
                       'from_service_created', 'customer_not_found', 'customer_required']:
            self.assertIn(f'def {method}', src,
                          f"DjoyaltyResponse.{method}() must be defined")

    def test_service_result_exists(self):
        path = os.path.join(BASE, 'service_result.py')
        self.assertTrue(os.path.exists(path))
        with open(path) as f:
            src = f.read()
        for method in ['ok', 'err', 'is_ok']:
            self.assertIn(f'def {method}', src,
                          f"ServiceResult.{method}() must be defined")


# ═══════════════════════════════════════════════════════════════════════════════
# REGRESSION — Feature flags for all gamification features
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeatureFlags(TestCase):
    """All gamification feature flags must be registered."""

    def test_all_gamification_flags_defined(self):
        path = os.path.join(BASE, 'feature_flags.py')
        with open(path) as f:
            src = f.read()
        for flag in ['spin_wheel', 'scratch_card', 'lottery', 'leaderboard', 'quiz']:
            self.assertIn(
                f"'{flag}'", src,
                f"Feature flag '{flag}' must be defined in feature_flags.py"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# REGRESSION — Syntax check all files
# ═══════════════════════════════════════════════════════════════════════════════

class TestSyntaxAll(TestCase):
    """Every .py file in the package must parse without SyntaxError."""

    def test_no_syntax_errors_in_codebase(self):
        errors = []
        for root, dirs, files in os.walk(BASE):
            dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git']]
            for fname in files:
                if not fname.endswith('.py'):
                    continue
                path = os.path.join(root, fname)
                try:
                    with open(path) as f:
                        ast.parse(f.read())
                except SyntaxError as e:
                    errors.append(f"{path.replace(BASE+'/','')}: line {e.lineno} — {e.msg}")
        self.assertEqual(errors, [], f"Syntax errors found: {errors}")
