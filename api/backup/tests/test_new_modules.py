"""
Tests for New Module Files (v3 additions)
Covers: schemas, mixins, abstracts, querysets, helpers, search,
        repositories, interactors, plugins, logic, factories,
        context_processors, feature_flags, sanctions, notifications_push
"""

import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, Mock
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model

User = get_user_model()


# ─────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────

class SchemasTest(TestCase):

    def test_create_backup_schema_valid(self):
        from api.backup.schemas import CreateBackupSchema, StorageBackend
        schema = CreateBackupSchema(name="my_backup", storage_backend=StorageBackend.S3)
        self.assertTrue(schema.validate())

    def test_create_backup_schema_empty_name_raises(self):
        from api.backup.schemas import CreateBackupSchema, StorageBackend
        schema = CreateBackupSchema(name="", storage_backend=StorageBackend.LOCAL)
        with self.assertRaises(ValueError):
            schema.validate()

    def test_create_backup_schema_bad_retention_raises(self):
        from api.backup.schemas import CreateBackupSchema, StorageBackend
        schema = CreateBackupSchema(name="ok", storage_backend=StorageBackend.GCS,
                                    retention_days=0)
        with self.assertRaises(ValueError):
            schema.validate()

    def test_backup_response_schema_to_dict(self):
        from api.backup.schemas import BackupResponseSchema, BackupStatus, StorageBackend
        s = BackupResponseSchema(
            id="bk-001", name="test", status=BackupStatus.COMPLETED,
            storage_backend=StorageBackend.S3, size_bytes=1024,
            created_at=datetime.utcnow(), completed_at=datetime.utcnow(),
            retention_days=30,
        )
        d = s.to_dict()
        self.assertEqual(d["status"], "completed")
        self.assertEqual(d["id"], "bk-001")

    def test_storage_location_schema_validation(self):
        from api.backup.schemas import StorageLocationSchema, StorageBackend
        schema = StorageLocationSchema(
            name="prod-s3", backend=StorageBackend.S3,
            config={"bucket_name": "my-bucket", "region": "us-east-1"},
        )
        self.assertTrue(schema.validate())

    def test_storage_location_missing_keys_raises(self):
        from api.backup.schemas import StorageLocationSchema, StorageBackend
        schema = StorageLocationSchema(
            name="bad", backend=StorageBackend.S3, config={}
        )
        with self.assertRaises(ValueError):
            schema.validate()

    def test_backup_stats_schema_empty(self):
        from api.backup.schemas import BackupStatsSchema
        stats = BackupStatsSchema.empty()
        self.assertEqual(stats.total_backups, 0)
        self.assertEqual(stats.success_rate, 0.0)

    def test_enum_values(self):
        from api.backup.schemas import BackupStatus, StorageBackend, CompressionAlgorithm
        self.assertEqual(BackupStatus.COMPLETED.value, "completed")
        self.assertEqual(StorageBackend.AZURE.value, "azure")
        self.assertEqual(CompressionAlgorithm.GZIP.value, "gzip")


# ─────────────────────────────────────────────
# MIXINS
# ─────────────────────────────────────────────

class MixinsTest(TestCase):

    def test_mixins_importable(self):
        from api.backup.mixins import (
            TimestampMixin, SoftDeleteMixin, AuditMixin,
            StatusMixin, SizeMixin, TagsMixin, APIResponseMixin,
        )
        for cls in [TimestampMixin, SoftDeleteMixin, AuditMixin,
                    StatusMixin, SizeMixin, TagsMixin, APIResponseMixin]:
            self.assertTrue(callable(cls))

    def test_api_response_mixin_success(self):
        from api.backup.mixins import APIResponseMixin
        mixin = APIResponseMixin()
        resp = mixin.success_response({"key": "value"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["success"])

    def test_api_response_mixin_error(self):
        from api.backup.mixins import APIResponseMixin
        mixin = APIResponseMixin()
        resp = mixin.error_response("Something went wrong", status_code=400)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data["success"])


# ─────────────────────────────────────────────
# ABSTRACTS
# ─────────────────────────────────────────────

class AbstractsTest(TestCase):

    def test_abstract_backup_service_importable(self):
        from api.backup.abstracts import (
            AbstractBackupService, AbstractNotificationService,
            AbstractEncryptionService, AbstractCompressionService,
            AbstractBackupScheduler, AbstractAuditLogger,
        )
        for cls in [AbstractBackupService, AbstractNotificationService,
                    AbstractEncryptionService, AbstractCompressionService,
                    AbstractBackupScheduler, AbstractAuditLogger]:
            self.assertTrue(callable(cls))

    def test_abstract_compression_ratio(self):
        from api.backup.abstracts import AbstractCompressionService
        import gzip

        class ConcreteCompressor(AbstractCompressionService):
            def compress(self, src, dst):
                with open(src, "rb") as f:
                    data = f.read()
                with gzip.open(dst, "wb") as g:
                    g.write(data)

            def decompress(self, src, dst):
                with gzip.open(src, "rb") as g:
                    data = g.read()
                with open(dst, "wb") as f:
                    f.write(data)

        comp = ConcreteCompressor()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"A" * 10000)
            src = f.name
        dst = src + ".gz"
        try:
            comp.compress(src, dst)
            ratio = comp.get_compression_ratio(src, dst)
            self.assertGreater(ratio, 1.0)
        finally:
            os.unlink(src)
            if os.path.exists(dst):
                os.unlink(dst)


# ─────────────────────────────────────────────
# QUERYSETS
# ─────────────────────────────────────────────

class QuerysetsTest(TestCase):

    def test_querysets_importable(self):
        from api.backup.querysets import (
            BackupQuerySet, BackupScheduleQuerySet, BackupStorageLocationQuerySet
        )
        for cls in [BackupQuerySet, BackupScheduleQuerySet, BackupStorageLocationQuerySet]:
            self.assertTrue(callable(cls))


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

class HelpersTest(TestCase):

    def test_slugify_backup_name(self):
        from api.backup.helpers import slugify_backup_name
        self.assertEqual(slugify_backup_name("My Backup 2026!"), "my-backup-2026")

    def test_generate_backup_filename(self):
        from api.backup.helpers import generate_backup_filename
        name = generate_backup_filename("prod", ".sql")
        self.assertTrue(name.startswith("prod"))
        self.assertTrue(name.endswith(".sql"))

    def test_bytes_to_human(self):
        from api.backup.helpers import bytes_to_human
        self.assertEqual(bytes_to_human(0), "0 B")
        self.assertIn("KB", bytes_to_human(2048))
        self.assertIn("MB", bytes_to_human(1024 ** 2 * 5))
        self.assertIn("GB", bytes_to_human(1024 ** 3 * 2))

    def test_parse_size_string(self):
        from api.backup.helpers import parse_size_string
        self.assertEqual(parse_size_string("100MB"), 100 * 1024 ** 2)
        self.assertEqual(parse_size_string("1GB"), 1024 ** 3)
        with self.assertRaises(ValueError):
            parse_size_string("not a size")

    def test_compute_file_checksum(self):
        from api.backup.helpers import compute_file_checksum
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"checksum test data")
            path = f.name
        try:
            chk = compute_file_checksum(path)
            self.assertEqual(len(chk), 64)  # SHA-256 hex
        finally:
            os.unlink(path)

    def test_parse_duration(self):
        from api.backup.helpers import parse_duration
        from datetime import timedelta
        self.assertEqual(parse_duration("2d"), timedelta(days=2))
        self.assertEqual(parse_duration("4h"), timedelta(hours=4))
        self.assertEqual(parse_duration("30m"), timedelta(minutes=30))
        with self.assertRaises(ValueError):
            parse_duration("bad")

    def test_humanize_duration(self):
        from api.backup.helpers import humanize_duration
        from datetime import timedelta
        self.assertIn("m", humanize_duration(timedelta(minutes=90)))
        self.assertIn("d", humanize_duration(timedelta(days=2, hours=3)))

    def test_deep_merge(self):
        from api.backup.helpers import deep_merge
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        override = {"b": {"c": 99, "e": 5}, "f": 6}
        result = deep_merge(base, override)
        self.assertEqual(result["b"]["c"], 99)
        self.assertEqual(result["b"]["d"], 3)
        self.assertEqual(result["f"], 6)

    def test_mask_sensitive(self):
        from api.backup.helpers import mask_sensitive
        data = {"username": "alice", "password": "secret123", "api_key": "abc"}
        masked = mask_sensitive(data)
        self.assertEqual(masked["username"], "alice")
        self.assertEqual(masked["password"], "***")
        self.assertEqual(masked["api_key"], "***")

    def test_flatten_dict(self):
        from api.backup.helpers import flatten_dict
        nested = {"a": {"b": {"c": 1}}, "d": 2}
        flat = flatten_dict(nested)
        self.assertEqual(flat["a.b.c"], 1)
        self.assertEqual(flat["d"], 2)


# ─────────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────────

class SearchTest(TestCase):

    def test_search_query_dataclass(self):
        from api.backup.search import SearchQuery, SearchFilter
        q = SearchQuery(text="production")
        q.add_filter("status", "completed")
        self.assertEqual(len(q.filters), 1)
        self.assertEqual(q.filters[0].field, "status")

    def test_search_result_pagination(self):
        from api.backup.search import SearchResult, SearchQuery
        result = SearchResult(items=list(range(20)), total_count=100,
                              page=2, page_size=20, query=SearchQuery())
        self.assertEqual(result.total_pages, 5)
        self.assertTrue(result.has_next)
        self.assertTrue(result.has_previous)

    def test_search_filter_operators(self):
        from api.backup.search import SearchFilter
        f = SearchFilter(field="created_at", value="2026-01-01", operator="gte")
        self.assertEqual(f.operator, "gte")

    def test_search_engine_importable(self):
        from api.backup.search import BackupSearchEngine
        self.assertTrue(callable(BackupSearchEngine))


# ─────────────────────────────────────────────
# REPOSITORIES
# ─────────────────────────────────────────────

class RepositoriesTest(TestCase):

    def test_repositories_importable(self):
        from api.backup.repositories import (
            BackupRepository, BackupScheduleRepository, StorageLocationRepository
        )
        for cls in [BackupRepository, BackupScheduleRepository, StorageLocationRepository]:
            self.assertTrue(callable(cls))


# ─────────────────────────────────────────────
# INTERACTORS
# ─────────────────────────────────────────────

class InteractorsTest(TestCase):

    def test_interactors_importable(self):
        from api.backup.interactors import (
            CreateBackupInteractor, DeleteBackupInteractor,
            RestoreBackupInteractor, ListBackupsInteractor,
            GetBackupStatsInteractor, CleanupExpiredBackupsInteractor,
        )
        for cls in [CreateBackupInteractor, DeleteBackupInteractor,
                    RestoreBackupInteractor, ListBackupsInteractor,
                    GetBackupStatsInteractor, CleanupExpiredBackupsInteractor]:
            self.assertTrue(callable(cls))


# ─────────────────────────────────────────────
# PLUGINS
# ─────────────────────────────────────────────

class PluginsTest(TestCase):

    def test_plugin_registry_singleton(self):
        from api.backup.plugins import PluginRegistry
        r1 = PluginRegistry()
        r2 = PluginRegistry()
        self.assertIs(r1, r2)

    def test_metrics_plugin(self):
        from api.backup.plugins import MetricsPlugin
        plugin = MetricsPlugin()
        plugin.setup({})
        plugin.on_backup_start("bk-001", {})
        plugin.on_backup_complete("bk-001", {})
        plugin.on_backup_fail("bk-002", Exception("err"), {})
        counters = plugin.get_counters()
        self.assertEqual(counters["backup_started"], 1)
        self.assertEqual(counters["backup_completed"], 1)
        self.assertEqual(counters["backup_failed"], 1)

    def test_logging_plugin(self):
        from api.backup.plugins import LoggingPlugin
        plugin = LoggingPlugin()
        plugin.setup({"log_level": "DEBUG"})
        plugin.on_backup_complete("bk-001", {"size": 1024})
        plugin.on_backup_fail("bk-002", ValueError("disk full"), {})

    def test_plugin_fire_events(self):
        from api.backup.plugins import PluginRegistry, MetricsPlugin
        registry = PluginRegistry.__new__(PluginRegistry)
        registry._plugins = {}
        plugin = MetricsPlugin()
        plugin.setup({})
        registry._plugins["metrics_plugin"] = plugin
        registry.fire_backup_start("bk-001", {})
        registry.fire_backup_complete("bk-001", {})
        self.assertEqual(plugin.get_counters()["backup_completed"], 1)


# ─────────────────────────────────────────────
# LOGIC
# ─────────────────────────────────────────────

class LogicTest(TestCase):

    def test_should_retain_backup(self):
        from api.backup.logic import should_retain_backup
        now = datetime.utcnow()
        created = now - timedelta(days=10)
        self.assertTrue(should_retain_backup(created, 30, now))
        self.assertFalse(should_retain_backup(created, 5, now))

    def test_calculate_expiry_date(self):
        from api.backup.logic import calculate_expiry_date
        created = datetime(2026, 1, 1)
        expiry = calculate_expiry_date(created, 30)
        self.assertEqual(expiry.day, 31)

    def test_filter_expired_backups(self):
        from api.backup.logic import filter_expired_backups
        now = datetime.utcnow()
        backups = [
            {"id": "1", "created_at": now - timedelta(days=40), "retention_days": 30},
            {"id": "2", "created_at": now - timedelta(days=10), "retention_days": 30},
        ]
        expired = filter_expired_backups(backups, now)
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0]["id"], "1")

    def test_gfs_retention(self):
        from api.backup.logic import apply_gfs_retention
        now = datetime.utcnow()
        backups = [
            {"id": str(i), "created_at": now - timedelta(days=i)}
            for i in range(20)
        ]
        keep, delete = apply_gfs_retention(backups, daily_count=7, weekly_count=4, monthly_count=3)
        self.assertGreater(len(keep), 0)
        self.assertEqual(len(keep) + len(delete), 20)

    def test_estimate_storage_needed(self):
        from api.backup.logic import estimate_storage_needed
        needed = estimate_storage_needed(1024 ** 3, copies=3, compression_ratio=2.5)
        self.assertGreater(needed, 0)
        self.assertLess(needed, 1024 ** 3 * 3)

    def test_check_storage_quota(self):
        from api.backup.logic import check_storage_quota
        result = check_storage_quota(80 * 1024**3, 100 * 1024**3)
        self.assertTrue(result["is_warning"])
        self.assertFalse(result["is_full"])

    def test_compute_backup_integrity_score(self):
        from api.backup.logic import compute_backup_integrity_score
        results = [{"passed": True}, {"passed": True}, {"passed": False}]
        score = compute_backup_integrity_score(results)
        self.assertAlmostEqual(score, 0.6667, places=3)

    def test_summarise_backup_health(self):
        from api.backup.logic import summarise_backup_health
        backups = [
            {"status": "completed", "size_bytes": 1024},
            {"status": "completed", "size_bytes": 2048},
            {"status": "failed", "size_bytes": 0},
        ]
        summary = summarise_backup_health(backups)
        self.assertEqual(summary["total"], 3)
        self.assertAlmostEqual(summary["success_rate"], 0.6667, places=3)


# ─────────────────────────────────────────────
# FACTORIES
# ─────────────────────────────────────────────

class FactoriesTest(TestCase):

    def test_factories_importable(self):
        from api.backup.factories import (
            UserFactory, BackupFactory, BackupScheduleFactory,
            FailedBackupFactory, PendingBackupFactory, ExpiredBackupFactory,
        )
        for cls in [UserFactory, BackupFactory, BackupScheduleFactory,
                    FailedBackupFactory, PendingBackupFactory, ExpiredBackupFactory]:
            self.assertTrue(callable(cls))


# ─────────────────────────────────────────────
# CONTEXT PROCESSORS
# ─────────────────────────────────────────────

class ContextProcessorsTest(TestCase):

    def test_context_processors_importable(self):
        from api.backup.context_processors import (
            backup_status_context, backup_feature_flags_context
        )
        self.assertTrue(callable(backup_status_context))
        self.assertTrue(callable(backup_feature_flags_context))

    def test_context_for_unauthenticated_returns_empty(self):
        from api.backup.context_processors import backup_status_context
        request = MagicMock()
        request.user = MagicMock(is_authenticated=False)
        result = backup_status_context(request)
        self.assertEqual(result, {})

    def test_context_for_non_staff_returns_empty(self):
        from api.backup.context_processors import backup_status_context
        request = MagicMock()
        request.user = MagicMock(is_authenticated=True, is_staff=False)
        result = backup_status_context(request)
        self.assertEqual(result, {})


# ─────────────────────────────────────────────
# FEATURE FLAGS
# ─────────────────────────────────────────────

class FeatureFlagsTest(TestCase):

    def test_feature_flags_importable(self):
        from api.backup.feature_flags import flag_is_active, set_flag, all_flags
        for fn in [flag_is_active, set_flag, all_flags]:
            self.assertTrue(callable(fn))

    def test_default_flags(self):
        from api.backup.feature_flags import flag_is_active
        self.assertIsInstance(flag_is_active("backup_encryption"), bool)

    def test_set_and_get_flag(self):
        from api.backup.feature_flags import set_flag, flag_is_active, clear_flag_cache
        clear_flag_cache("test_custom_flag")
        set_flag("test_custom_flag", True)
        self.assertTrue(flag_is_active("test_custom_flag", default=False))

    def test_require_flag_decorator(self):
        from api.backup.feature_flags import require_flag, FeatureFlagDisabledError, set_flag
        set_flag("disabled_feature", False)

        @require_flag("disabled_feature")
        def guarded():
            return "ok"

        with self.assertRaises(FeatureFlagDisabledError):
            guarded()

    def test_all_flags_returns_dict(self):
        from api.backup.feature_flags import all_flags
        flags = all_flags()
        self.assertIsInstance(flags, dict)
        self.assertIn("backup_encryption", flags)


# ─────────────────────────────────────────────
# SANCTIONS
# ─────────────────────────────────────────────

class SanctionsTest(TestCase):

    def test_rate_limiter_allows_under_limit(self):
        from api.backup.sanctions import BackupRateLimiter
        limiter = BackupRateLimiter(
            overrides={"backup_create": {"limit": 5, "window": 3600}}
        )
        for _ in range(4):
            limiter.check("backup_create", "user-001")

    def test_rate_limiter_blocks_over_limit(self):
        from api.backup.sanctions import BackupRateLimiter, RateLimitExceeded
        limiter = BackupRateLimiter(
            overrides={"backup_create": {"limit": 2, "window": 60}}
        )
        limiter.reset("backup_create", "user-ratelimit")
        from django.core.cache import cache
        cache.set("backup_ratelimit:backup_create:user-ratelimit", 2, 60)
        with self.assertRaises(RateLimitExceeded):
            limiter.check("backup_create", "user-ratelimit")

    def test_quota_enforcer_allows_under_quota(self):
        from api.backup.sanctions import StorageQuotaEnforcer
        enforcer = StorageQuotaEnforcer()
        enforcer._tenant_quotas["t-001"] = 100 * 1024 ** 3
        enforcer.check_quota("t-001", 0, 50 * 1024 ** 3)  # should not raise

    def test_quota_enforcer_blocks_over_quota(self):
        from api.backup.sanctions import StorageQuotaEnforcer, QuotaExceeded
        enforcer = StorageQuotaEnforcer()
        enforcer._tenant_quotas["t-002"] = 10 * 1024 ** 3  # 10 GB
        with self.assertRaises(QuotaExceeded):
            enforcer.check_quota("t-002", 0, 20 * 1024 ** 3)

    def test_operation_checker_blocks_running_backup_delete(self):
        from api.backup.sanctions import OperationSanctionChecker, OperationNotPermitted
        checker = OperationSanctionChecker()
        with self.assertRaises(OperationNotPermitted):
            checker.check_delete_backup({"id": "bk-001", "status": "running"})

    def test_operation_checker_blocks_incomplete_restore(self):
        from api.backup.sanctions import OperationSanctionChecker, OperationNotPermitted
        checker = OperationSanctionChecker()
        with self.assertRaises(OperationNotPermitted):
            checker.check_restore_backup(
                {"id": "bk-001", "status": "failed"}, {}
            )

    def test_sanction_guard_create(self):
        from api.backup.sanctions import BackupSanctionGuard
        guard = BackupSanctionGuard()
        guard.rate_limiter.reset("backup_create", "user-safe")
        guard.guard_create("user-safe", "tenant-safe",
                           current_usage=0, new_size=1024,
                           system_state={"maintenance_mode": False})

    def test_maintenance_mode_blocks_create(self):
        from api.backup.sanctions import BackupSanctionGuard, OperationNotPermitted
        guard = BackupSanctionGuard()
        guard.rate_limiter.reset("backup_create", "user-maint")
        with self.assertRaises(OperationNotPermitted):
            guard.guard_create("user-maint", "t1",
                               current_usage=0, new_size=1024,
                               system_state={"maintenance_mode": True})


# ─────────────────────────────────────────────
# NOTIFICATIONS PUSH
# ─────────────────────────────────────────────

class NotificationsPushTest(TestCase):

    def test_payload_to_dict(self):
        from api.backup.notifications_push import PushNotificationPayload
        payload = PushNotificationPayload(title="Test", body="Body text",
                                          data={"key": "val"})
        d = payload.to_dict()
        self.assertEqual(d["title"], "Test")
        self.assertEqual(d["data"]["key"], "val")

    def test_fcm_backend_importable(self):
        from api.backup.notifications_push import FCMPushBackend
        self.assertTrue(callable(FCMPushBackend))

    @patch("backup.notifications_push.requests.post")
    def test_fcm_send_success(self, mock_post):
        from api.backup.notifications_push import FCMPushBackend, PushNotificationPayload
        mock_post.return_value = MagicMock(
            ok=True, json=lambda: {"success": 1}
        )
        backend = FCMPushBackend(server_key="test-key")
        payload = PushNotificationPayload(title="Backup done", body="bk-001 completed")
        result = backend.send("device-token-123", payload)
        self.assertTrue(result)

    @patch("backup.notifications_push.requests.post")
    def test_push_service_notify_completed(self, mock_post):
        from api.backup.notifications_push import BackupPushNotificationService, FCMPushBackend
        mock_post.return_value = MagicMock(
            ok=True, json=lambda: {"results": [{}]}
        )
        service = BackupPushNotificationService(backend=FCMPushBackend(server_key="key"))
        result = service.notify_backup_completed(
            ["token-001", "token-002"], "prod_backup", "500 MB"
        )
        self.assertIsInstance(result, dict)

    def test_channels_backend_importable(self):
        from api.backup.notifications_push import ChannelsPushBackend
        self.assertTrue(callable(ChannelsPushBackend))
