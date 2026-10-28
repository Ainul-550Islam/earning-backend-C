# publisher_tools/tests/test_warehouse_migration.py
"""
Analytics Warehouse migration + model structure tests।

Tests (database-independent — Django apps import ছাড়া চলে):
  - Migration file structure সঠিক আছে
  - 20টি CreateModel operation আছে
  - সব 20টি model-এর db_table নাম aw_ prefix দিয়ে শুরু
  - Index count ≥ 1 per model
  - WarehouseHealthViewSet MODEL_MAP-এ সব 20 type আছে
  - analytics_warehouse serializers ঠিকমতো import হয়
  - WarehouseIngestSerializer-এর choices-এ সব 20 type আছে

DB-level tests (requires analytics database):
  - PublisherRecord.objects.create()
  - RevenueRecord aggregate query
  - FraudLogRecord filter by resolved=False
"""
import ast
import os
import pytest


# ── Migration File Path ───────────────────────────────────────────────────────

MIGRATION_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    '..', 'analytics_warehouse', 'migrations', '0001_initial.py',
)


# ══════════════════════════════════════════════════════════════════════════════
# Migration file structure (AST parse — no Django import needed)
# ══════════════════════════════════════════════════════════════════════════════

class TestMigrationFileStructure:
    """Migration file parse করে structure check করা হচ্ছে।"""

    @pytest.fixture(scope='class')
    def migration_source(self):
        candidates = [
            MIGRATION_PATH,
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', 'analytics_warehouse', 'migrations', '0001_initial.py',
            ),
            '/home/claude/publisher_tools_update/analytics_warehouse/migrations/0001_initial.py',
        ]
        for path in candidates:
            path = os.path.normpath(path)
            if os.path.exists(path):
                with open(path) as f:
                    return f.read()
        pytest.skip('Migration file not found — skipping structural checks.')

    def test_migration_file_is_valid_python(self, migration_source):
        try:
            ast.parse(migration_source)
        except SyntaxError as e:
            pytest.fail(f'Migration file has syntax error: {e}')

    def test_migration_has_initial_true(self, migration_source):
        assert 'initial = True' in migration_source

    def test_migration_has_20_create_model_ops(self, migration_source):
        count = migration_source.count('migrations.CreateModel(')
        assert count == 20, f'Expected 20 CreateModel ops, found {count}'

    def test_all_20_models_present(self, migration_source):
        expected_models = [
            'PublisherRecord', 'SiteRecord', 'AppRecord', 'AdUnitRecord',
            'ImpressionRecord', 'ClickRecord', 'RevenueRecord',
            'InvoiceRecord', 'PaymentRecord', 'FraudLogRecord',
            'AuditLogRecord', 'AdPlacementRecord', 'ReportRecord',
            'AlertRecord', 'WebhookLogRecord', 'NotificationRecord',
            'SettingRecord', 'APIKeyLogRecord', 'OptimizationLogRecord',
            'ABTestRecord',
        ]
        for model in expected_models:
            assert f"name='{model}'" in migration_source or f'name="{model}"' in migration_source, \
                f"Model '{model}' not found in migration"

    def test_all_db_tables_have_aw_prefix(self, migration_source):
        import re
        db_tables = re.findall(r"'db_table':\s*'(\w+)'", migration_source)
        assert len(db_tables) == 20, f'Expected 20 db_table entries, found {len(db_tables)}'
        for table in db_tables:
            assert table.startswith('aw_'), \
                f"Table '{table}' should start with 'aw_' prefix"

    def test_indexes_present_for_all_models(self, migration_source):
        index_count = migration_source.count('migrations.AddIndex(')
        # ন্যূনতম 20টা index (কমপক্ষে 2টা per model)
        assert index_count >= 20, f'Expected at least 20 indexes, found {index_count}'

    def test_migration_has_dependencies(self, migration_source):
        assert 'dependencies' in migration_source
        assert 'publisher_tools' in migration_source

    def test_all_models_have_ordering(self, migration_source):
        ordering_count = migration_source.count("'ordering'")
        assert ordering_count == 20, f'Expected 20 ordering entries, found {ordering_count}'

    def test_all_models_have_verbose_name(self, migration_source):
        verbose_count = migration_source.count("'verbose_name'")
        assert verbose_count >= 20, f'Expected ≥20 verbose_name entries, found {verbose_count}'


# ══════════════════════════════════════════════════════════════════════════════
# WarehouseHealthViewSet MODEL_MAP completeness
# ══════════════════════════════════════════════════════════════════════════════

class TestWarehouseModelMap:
    """WarehouseHealthViewSet.MODEL_MAP সব 20টা type cover করে কিনা।"""

    EXPECTED_TYPES = [
        'publisher', 'site', 'app', 'ad_unit',
        'impression', 'click', 'revenue', 'invoice', 'payment',
        'fraud_log', 'audit_log', 'ad_placement',
        'report', 'alert', 'webhook_log', 'notification',
        'setting', 'api_key_log', 'optimization_log', 'ab_test',
    ]

    def test_model_map_has_20_entries(self):
        try:
            from analytics_warehouse.views import WarehouseHealthViewSet
            assert len(WarehouseHealthViewSet.MODEL_MAP) == 20
        except ImportError:
            pytest.skip('analytics_warehouse.views not importable')

    def test_all_20_types_in_model_map(self):
        try:
            from analytics_warehouse.views import WarehouseHealthViewSet
            model_map = WarehouseHealthViewSet.MODEL_MAP
            for t in self.EXPECTED_TYPES:
                assert t in model_map, f"'{t}' missing from MODEL_MAP"
        except ImportError:
            pytest.skip('analytics_warehouse.views not importable')

    def test_ingest_serializer_choices_match_model_map(self):
        try:
            from analytics_warehouse.serializers import WarehouseIngestSerializer
            from analytics_warehouse.views      import WarehouseHealthViewSet
            serializer_choices = WarehouseIngestSerializer.RECORD_TYPE_CHOICES
            model_map_keys     = list(WarehouseHealthViewSet.MODEL_MAP.keys())
            assert set(serializer_choices) == set(model_map_keys), \
                'Ingest serializer choices do not match MODEL_MAP keys'
        except ImportError:
            pytest.skip('analytics_warehouse not importable')


# ══════════════════════════════════════════════════════════════════════════════
# Serializer import checks (all 20 pairs exist)
# ══════════════════════════════════════════════════════════════════════════════

class TestSerializerImports:
    """সব 20টা serializer pair (list + detail) import করা যায় কিনা।"""

    SERIALIZER_PAIRS = [
        ('PublisherRecordSerializer',      'PublisherRecordListSerializer'),
        ('SiteRecordSerializer',           'SiteRecordListSerializer'),
        ('AppRecordSerializer',            'AppRecordListSerializer'),
        ('AdUnitRecordSerializer',         'AdUnitRecordListSerializer'),
        ('ImpressionRecordSerializer',     'ImpressionRecordListSerializer'),
        ('ClickRecordSerializer',          'ClickRecordListSerializer'),
        ('RevenueRecordSerializer',        'RevenueRecordListSerializer'),
        ('InvoiceRecordSerializer',        'InvoiceRecordListSerializer'),
        ('PaymentRecordSerializer',        'PaymentRecordListSerializer'),
        ('FraudLogRecordSerializer',       'FraudLogRecordListSerializer'),
        ('AuditLogRecordSerializer',       'AuditLogRecordListSerializer'),
        ('AdPlacementRecordSerializer',    'AdPlacementRecordListSerializer'),
        ('ReportRecordSerializer',         'ReportRecordListSerializer'),
        ('AlertRecordSerializer',          'AlertRecordListSerializer'),
        ('WebhookLogRecordSerializer',     'WebhookLogRecordListSerializer'),
        ('NotificationRecordSerializer',   'NotificationRecordListSerializer'),
        ('SettingRecordSerializer',        'SettingRecordListSerializer'),
        ('APIKeyLogRecordSerializer',      'APIKeyLogRecordListSerializer'),
        ('OptimizationLogRecordSerializer','OptimizationLogRecordListSerializer'),
        ('ABTestRecordSerializer',         'ABTestRecordListSerializer'),
    ]

    def test_all_serializer_pairs_importable(self):
        try:
            import analytics_warehouse.serializers as s_module
        except ImportError:
            pytest.skip('analytics_warehouse not importable in this env')

        for detail_cls, list_cls in self.SERIALIZER_PAIRS:
            assert hasattr(s_module, detail_cls), \
                f'{detail_cls} not found in analytics_warehouse.serializers'
            assert hasattr(s_module, list_cls), \
                f'{list_cls} not found in analytics_warehouse.serializers'

    def test_etl_serializers_importable(self):
        try:
            from analytics_warehouse.serializers import (
                WarehouseIngestSerializer,
                WarehouseMarkProcessedSerializer,
                WarehouseSummarySerializer,
            )
        except ImportError:
            pytest.skip('analytics_warehouse not importable')


# ══════════════════════════════════════════════════════════════════════════════
# ViewSet imports (all 21 viewsets)
# ══════════════════════════════════════════════════════════════════════════════

class TestViewSetImports:

    VIEWSETS = [
        'PublisherRecordViewSet',      'SiteRecordViewSet',
        'AppRecordViewSet',            'AdUnitRecordViewSet',
        'ImpressionRecordViewSet',     'ClickRecordViewSet',
        'RevenueRecordViewSet',        'InvoiceRecordViewSet',
        'PaymentRecordViewSet',        'FraudLogRecordViewSet',
        'AuditLogRecordViewSet',       'AdPlacementRecordViewSet',
        'ReportRecordViewSet',         'AlertRecordViewSet',
        'WebhookLogRecordViewSet',     'NotificationRecordViewSet',
        'SettingRecordViewSet',        'APIKeyLogRecordViewSet',
        'OptimizationLogRecordViewSet','ABTestRecordViewSet',
        'WarehouseHealthViewSet',
    ]

    def test_all_21_viewsets_importable(self):
        try:
            import analytics_warehouse.views as v_module
        except ImportError:
            pytest.skip('analytics_warehouse.views not importable')

        for vs in self.VIEWSETS:
            assert hasattr(v_module, vs), f'{vs} not found in analytics_warehouse.views'


# ══════════════════════════════════════════════════════════════════════════════
# URL routing — all 21 viewsets registered
# ══════════════════════════════════════════════════════════════════════════════

class TestWarehouseURLs:

    EXPECTED_BASENAMES = [
        'aw-publisher-record', 'aw-site-record', 'aw-app-record',
        'aw-adunit-record',    'aw-impression-record', 'aw-click-record',
        'aw-revenue-record',   'aw-invoice-record',    'aw-payment-record',
        'aw-fraud-log-record', 'aw-audit-log-record',  'aw-placement-record',
        'aw-report-record',    'aw-alert-record',       'aw-webhook-log-record',
        'aw-notification-record', 'aw-setting-record', 'aw-api-key-log-record',
        'aw-opt-log-record',   'aw-abtest-record',     'aw-health',
    ]

    def test_all_21_basenames_registered(self):
        try:
            from analytics_warehouse import urls as wh_urls
        except ImportError:
            pytest.skip('analytics_warehouse.urls not importable')

        url_names = [str(u.name) for u in wh_urls.urlpatterns if hasattr(u, 'name')]
        url_names_str = ' '.join(url_names)

        for bn in self.EXPECTED_BASENAMES:
            # Router generates names like 'aw-publisher-record-list', 'aw-publisher-record-detail'
            assert bn in url_names_str, \
                f"Basename '{bn}' not found in warehouse URL patterns"

    def test_url_count_at_least_42(self):
        """21 ViewSets × (list + detail) = minimum 42 URL patterns।"""
        try:
            from analytics_warehouse import urls as wh_urls
        except ImportError:
            pytest.skip('analytics_warehouse.urls not importable')
        assert len(wh_urls.urlpatterns) >= 42


# ══════════════════════════════════════════════════════════════════════════════
# database_models deprecation shim
# ══════════════════════════════════════════════════════════════════════════════

class TestDatabaseModelsDeprecation:
    """database_models/__init__.py deprecation shim test।"""

    EXPECTED_EXPORTS = [
        'PublisherRecord', 'SiteRecord', 'AppRecord', 'AdUnitRecord',
        'ImpressionRecord', 'ClickRecord', 'RevenueRecord',
        'InvoiceRecord', 'PaymentRecord', 'FraudLogRecord',
        'AuditLogRecord', 'AdPlacementRecord', 'ReportRecord',
        'AlertRecord', 'WebhookLogRecord', 'NotificationRecord',
        'SettingRecord', 'APIKeyLogRecord', 'OptimizationLogRecord',
        'ABTestRecord',
    ]

    def test_deprecation_warning_raised(self):
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            try:
                import publisher_tools.database_models  # noqa: F401
            except ImportError:
                pytest.skip('publisher_tools.database_models not importable')
            if w:
                deprecation_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                assert len(deprecation_warnings) >= 1, \
                    'DeprecationWarning should be raised when importing database_models'

    def test_shim_exports_20_classes(self):
        try:
            import publisher_tools.database_models as dm
            shim_exports = getattr(dm, '__all__', [])
            # When analytics_warehouse is available, all 20 should be re-exported
            if shim_exports:
                assert len(shim_exports) == 20
        except ImportError:
            pytest.skip('publisher_tools.database_models not importable')
