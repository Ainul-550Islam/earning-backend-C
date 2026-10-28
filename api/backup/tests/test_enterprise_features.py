"""
Tests for Enterprise-Grade Features
Covers: immutable_storage, ransomware_detection, disaster_recovery,
        deduplication, zero_trust, multi_tenancy, continuous_data_protection,
        replication, instant_recovery, ml_anomaly_detection, data_governance,
        reporting_engine, genai_insights, cyber_protect, forensic_backup
"""

import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, Mock
from django.test import TestCase


# ─────────────────────────────────────────────
# IMMUTABLE STORAGE
# ─────────────────────────────────────────────

class ImmutableStorageTest(TestCase):

    def test_import(self):
        from api.backup.immutable_storage import ImmutableStorageManager
        self.assertTrue(callable(ImmutableStorageManager))

    def test_immutability_mode_enum(self):
        from api.backup.immutable_storage import ImmutabilityMode
        self.assertEqual(ImmutabilityMode.COMPLIANCE.value, "compliance")
        self.assertEqual(ImmutabilityMode.GOVERNANCE.value, "governance")
        self.assertEqual(ImmutabilityMode.LOCKED.value, "locked")

    def test_seal_and_verify_backup(self):
        from api.backup.immutable_storage import ImmutableStorageManager, ImmutabilityPolicy, ImmutabilityMode
        mgr = ImmutableStorageManager()
        policy = ImmutabilityPolicy(mode=ImmutabilityMode.COMPLIANCE, retention_days=30)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".sql") as f:
            f.write(b"backup content for sealing")
            path = f.name
        try:
            record = mgr.seal_backup("bk-001", path, policy)
            self.assertIsNotNone(record.content_hash)
            self.assertTrue(mgr.verify_backup("bk-001", path))
        finally:
            os.unlink(path)

    def test_tamper_detection(self):
        from api.backup.immutable_storage import ImmutableStorageManager, ImmutabilityPolicy, ImmutabilityMode
        mgr = ImmutableStorageManager()
        policy = ImmutabilityPolicy(mode=ImmutabilityMode.COMPLIANCE, retention_days=30)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".sql") as f:
            f.write(b"original data")
            path = f.name
        try:
            mgr.seal_backup("bk-tamper", path, policy)
            with open(path, "wb") as f2:
                f2.write(b"TAMPERED DATA")
            self.assertFalse(mgr.verify_backup("bk-tamper", path))
        finally:
            os.unlink(path)

    def test_deletion_blocked_under_compliance(self):
        from api.backup.immutable_storage import ImmutableStorageManager, ImmutabilityPolicy, ImmutabilityMode
        mgr = ImmutableStorageManager()
        policy = ImmutabilityPolicy(mode=ImmutabilityMode.COMPLIANCE, retention_days=365)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x")
            path = f.name
        try:
            mgr.seal_backup("bk-nodelete", path, policy)
            self.assertFalse(mgr.can_delete("bk-nodelete"))
        finally:
            os.unlink(path)

    def test_locked_mode_never_deletable(self):
        from api.backup.immutable_storage import ImmutableStorageManager, ImmutabilityPolicy, ImmutabilityMode
        mgr = ImmutableStorageManager()
        policy = ImmutabilityPolicy(mode=ImmutabilityMode.LOCKED, retention_days=1,
                                    created_at=datetime.utcnow() - timedelta(days=10))
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"locked")
            path = f.name
        try:
            mgr.seal_backup("bk-locked", path, policy)
            self.assertFalse(mgr.can_delete("bk-locked", requester_role="superadmin"))
        finally:
            os.unlink(path)

    def test_list_expiring(self):
        from api.backup.immutable_storage import ImmutableStorageManager, ImmutabilityPolicy, ImmutabilityMode
        mgr = ImmutableStorageManager()
        policy = ImmutabilityPolicy(mode=ImmutabilityMode.GOVERNANCE, retention_days=3)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"expiring")
            path = f.name
        try:
            mgr.seal_backup("bk-exp", path, policy)
            expiring = mgr.list_expiring(days=7)
            self.assertGreater(len(expiring), 0)
        finally:
            os.unlink(path)


# ─────────────────────────────────────────────
# RANSOMWARE DETECTION
# ─────────────────────────────────────────────

class RansomwareDetectionTest(TestCase):

    def test_import(self):
        from api.backup.ransomware_detection import RansomwareScanner
        self.assertTrue(callable(RansomwareScanner))

    def test_clean_file_passes(self):
        from api.backup.ransomware_detection import RansomwareScanner, ThreatLevel
        scanner = RansomwareScanner()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".sql") as f:
            f.write(b"SELECT * FROM users;")
            path = f.name
        try:
            result = scanner.scan_backup("bk-clean", path)
            self.assertEqual(result.threat_level, ThreatLevel.CLEAN)
            self.assertTrue(result.is_safe_to_restore)
        finally:
            os.unlink(path)

    def test_ransomware_extension_detected(self):
        from api.backup.ransomware_detection import RansomwareScanner, ThreatLevel
        scanner = RansomwareScanner()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".locked") as f:
            f.write(b"encrypted data")
            path = f.name
        try:
            indicators = scanner.scan_file(path)
            self.assertTrue(len(indicators) > 0)
        finally:
            os.unlink(path)

    def test_ransom_note_detected(self):
        from api.backup.ransomware_detection import RansomwareScanner
        scanner = RansomwareScanner()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt",
                                          prefix="readme") as f:
            f.write(b"your files have been encrypted pay bitcoin")
            path = f.name
        # Rename to ransom note name
        note_path = os.path.join(os.path.dirname(path), "readme.txt")
        os.rename(path, note_path)
        try:
            indicators = scanner.scan_file(note_path)
            self.assertTrue(len(indicators) > 0)
        finally:
            if os.path.exists(note_path):
                os.unlink(note_path)

    def test_entropy_calculation(self):
        from api.backup.ransomware_detection import calculate_entropy
        low_entropy = calculate_entropy(b"A" * 1000)
        import os as _os
        high_entropy = calculate_entropy(_os.urandom(1000))
        self.assertLess(low_entropy, 1.0)
        self.assertGreater(high_entropy, 6.0)

    def test_threat_intelligence_feed(self):
        from api.backup.ransomware_detection import ThreatIntelligenceFeed
        feed = ThreatIntelligenceFeed()
        feed.add_hash("a" * 64)
        feed.add_extension(".ransomtest")
        scanner = feed.build_scanner()
        self.assertIn(".ransomtest", scanner.ransomware_extensions)


# ─────────────────────────────────────────────
# DISASTER RECOVERY
# ─────────────────────────────────────────────

class DisasterRecoveryTest(TestCase):

    def _make_plan(self):
        from api.backup.disaster_recovery import (
            DRPlan, DRStep, RecoveryObjective, RecoveryType
        )
        return DRPlan(
            plan_id="dr-001",
            name="Main DR Plan",
            recovery_type=RecoveryType.FULL_SITE,
            objectives=[RecoveryObjective("web_app", rpo_minutes=60, rto_minutes=240)],
            steps=[
                DRStep("s1", "Notify Team", action="notify", params={}),
                DRStep("s2", "Start VMs", action="start_vms", params={}, depends_on=["s1"]),
            ],
        )

    def test_import(self):
        from api.backup.disaster_recovery import DROrchestrator
        self.assertTrue(callable(DROrchestrator))

    def test_register_and_get_plan(self):
        from api.backup.disaster_recovery import DROrchestrator
        orch = DROrchestrator()
        plan = self._make_plan()
        orch.register_plan(plan)
        self.assertEqual(orch.get_plan("dr-001").name, "Main DR Plan")

    def test_execute_plan_succeeds(self):
        from api.backup.disaster_recovery import DROrchestrator, DRStatus
        orch = DROrchestrator()
        orch.register_plan(self._make_plan())
        execution = orch.execute_plan("dr-001")
        self.assertEqual(execution.status, DRStatus.COMPLETED)
        self.assertEqual(execution.steps_failed, 0)

    def test_test_plan_marks_tested(self):
        from api.backup.disaster_recovery import DROrchestrator
        orch = DROrchestrator()
        plan = self._make_plan()
        orch.register_plan(plan)
        orch.test_plan("dr-001")
        self.assertIsNotNone(plan.last_tested_at)
        self.assertTrue(plan.test_passed)

    def test_rpo_check(self):
        from api.backup.disaster_recovery import RecoveryObjective, RPOViolationSeverity
        obj = RecoveryObjective("db", rpo_minutes=60, rto_minutes=120)
        old_time = datetime.utcnow() - timedelta(minutes=90)
        self.assertEqual(obj.check_rpo(old_time), RPOViolationSeverity.BREACH)
        recent = datetime.utcnow() - timedelta(minutes=5)
        self.assertEqual(obj.check_rpo(recent), RPOViolationSeverity.NONE)

    def test_cleanroom_create_and_teardown(self):
        from api.backup.disaster_recovery import CleanroomRecovery
        cr = CleanroomRecovery()
        room_id = cr.create_room("forensic-room", ["bk-001", "bk-002"])
        room = cr.get_room(room_id)
        self.assertIsNotNone(room)
        self.assertTrue(room["network_isolated"])
        self.assertTrue(cr.teardown_room(room_id))
        self.assertIsNone(cr.get_room(room_id))


# ─────────────────────────────────────────────
# DEDUPLICATION
# ─────────────────────────────────────────────

class DeduplicationTest(TestCase):

    def test_import(self):
        from api.backup.deduplication import GlobalDeduplicationEngine
        self.assertTrue(callable(GlobalDeduplicationEngine))

    def test_ingest_file_returns_stats(self):
        from api.backup.deduplication import GlobalDeduplicationEngine
        engine = GlobalDeduplicationEngine()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"block_data " * 500)
            path = f.name
        try:
            stats = engine.ingest_file("bk-001", path)
            self.assertIn("total_blocks", stats)
            self.assertIn("new_blocks", stats)
            self.assertGreater(stats["total_blocks"], 0)
        finally:
            os.unlink(path)

    def test_dedup_reduces_stored_bytes(self):
        from api.backup.deduplication import GlobalDeduplicationEngine
        engine = GlobalDeduplicationEngine()
        content = b"repeated content " * 200
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            p1 = f.name
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            p2 = f.name
        try:
            engine.ingest_file("bk-001", p1)
            engine.ingest_file("bk-002", p2)
            self.assertGreater(engine.dedup_ratio, 1.0)
        finally:
            os.unlink(p1)
            os.unlink(p2)

    def test_release_backup_frees_blocks(self):
        from api.backup.deduplication import GlobalDeduplicationEngine
        engine = GlobalDeduplicationEngine()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"unique content for release test " * 100)
            path = f.name
        try:
            engine.ingest_file("bk-release", path)
            freed = engine.release_backup("bk-release")
            self.assertGreater(freed, 0)
        finally:
            os.unlink(path)

    def test_stats(self):
        from api.backup.deduplication import GlobalDeduplicationEngine
        engine = GlobalDeduplicationEngine()
        stats = engine.stats()
        self.assertIn("unique_blocks", stats)
        self.assertIn("dedup_ratio", stats)


# ─────────────────────────────────────────────
# ZERO TRUST
# ─────────────────────────────────────────────

class ZeroTrustTest(TestCase):

    def test_import(self):
        from api.backup.zero_trust import ZeroTrustPolicyEngine
        self.assertTrue(callable(ZeroTrustPolicyEngine))

    def test_normal_access_allowed(self):
        from api.backup.zero_trust import ZeroTrustPolicyEngine, ZeroTrustContext, AccessDecision
        engine = ZeroTrustPolicyEngine()
        ctx = ZeroTrustContext(user_id="u1", resource_id="bk-001",
                               action="backup_view", ip_address="10.0.0.1")
        decision = engine.evaluate(ctx)
        self.assertEqual(decision, AccessDecision.ALLOW)

    def test_sensitive_action_requires_mfa(self):
        from api.backup.zero_trust import ZeroTrustPolicyEngine, ZeroTrustContext, AccessDecision
        engine = ZeroTrustPolicyEngine()
        ctx = ZeroTrustContext(user_id="u1", resource_id="bk-001",
                               action="backup_delete", ip_address="10.0.0.1",
                               mfa_verified=False)
        decision = engine.evaluate(ctx)
        self.assertEqual(decision, AccessDecision.CHALLENGE)

    def test_mfa_verified_allows_sensitive(self):
        from api.backup.zero_trust import ZeroTrustPolicyEngine, ZeroTrustContext, AccessDecision
        engine = ZeroTrustPolicyEngine()
        ctx = ZeroTrustContext(user_id="u1", resource_id="bk-001",
                               action="backup_delete", ip_address="10.0.0.1",
                               mfa_verified=True)
        decision = engine.evaluate(ctx)
        self.assertEqual(decision, AccessDecision.ALLOW)

    def test_blocked_user_denied(self):
        from api.backup.zero_trust import ZeroTrustPolicyEngine, ZeroTrustContext, AccessDecision
        engine = ZeroTrustPolicyEngine()
        engine._blocked_users.add("bad-user")
        ctx = ZeroTrustContext(user_id="bad-user", resource_id="bk-001",
                               action="backup_view", ip_address="1.2.3.4")
        decision = engine.evaluate(ctx)
        self.assertEqual(decision, AccessDecision.DENY)

    def test_mfa_totp_verify(self):
        from api.backup.zero_trust import MFAVerifier
        verifier = MFAVerifier()
        code = verifier.generate_totp()
        self.assertTrue(verifier.verify_totp(code))
        self.assertFalse(verifier.verify_totp("000000"))

    def test_air_gap_manager(self):
        from api.backup.zero_trust import AirGapManager
        mgr = AirGapManager()
        vault_id = mgr.create_air_gap_copy("bk-001", "/backups/bk-001.sql")
        copies = mgr.list_air_gap_copies("bk-001")
        self.assertEqual(len(copies), 1)
        self.assertTrue(copies[0]["network_isolated"])
        copy = mgr.retrieve_copy(vault_id, authorized_by="admin@example.com")
        self.assertIsNotNone(copy)


# ─────────────────────────────────────────────
# MULTI-TENANCY
# ─────────────────────────────────────────────

class MultiTenancyTest(TestCase):

    def test_import(self):
        from api.backup.multi_tenancy import TenantRegistry
        self.assertTrue(callable(TenantRegistry))

    def test_register_and_get_tenant(self):
        from api.backup.multi_tenancy import Tenant, TenantRegistry
        reg = TenantRegistry()
        t = Tenant(tenant_id="t-001", name="Acme Corp")
        reg.register(t)
        self.assertEqual(reg.get("t-001").name, "Acme Corp")

    def test_quota_check(self):
        from api.backup.multi_tenancy import Tenant, TenantRegistry
        reg = TenantRegistry()
        t = Tenant(tenant_id="t-002", name="SmallCo",
                   storage_quota_bytes=1024*1024*100)  # 100 MB
        reg.register(t)
        self.assertTrue(reg.check_quota("t-002", 0, 1024*1024*50))   # 50 MB — OK
        self.assertFalse(reg.check_quota("t-002", 0, 1024*1024*200)) # 200 MB — over

    def test_deactivate_tenant(self):
        from api.backup.multi_tenancy import Tenant, TenantRegistry
        reg = TenantRegistry()
        t = Tenant(tenant_id="t-003", name="OldClient")
        reg.register(t)
        self.assertTrue(reg.deactivate("t-003"))
        self.assertEqual(len(reg.list_active()), 0)


# ─────────────────────────────────────────────
# CONTINUOUS DATA PROTECTION
# ─────────────────────────────────────────────

class CDPTest(TestCase):

    def test_import(self):
        from api.backup.continuous_data_protection import CDPEngine
        self.assertTrue(callable(CDPEngine))

    def test_create_and_start_session(self):
        from api.backup.continuous_data_protection import CDPEngine, CDPStatus
        engine = CDPEngine()
        session = engine.create_session("vol-001", "s3://backup/cdp/")
        engine.start(session.session_id)
        self.assertEqual(session.status, CDPStatus.RUNNING)

    def test_record_write_creates_journal_entry(self):
        from api.backup.continuous_data_protection import CDPEngine
        engine = CDPEngine()
        session = engine.create_session("vol-001", "s3://backup/cdp/")
        engine.start(session.session_id)
        entry = engine.record_write(session.session_id, offset=0, length=4096,
                                     volume_id="vol-001", checksum="abc123")
        self.assertEqual(entry.data_length, 4096)
        self.assertIsNotNone(session.last_sync_at)

    def test_rpo_met_immediately_after_write(self):
        from api.backup.continuous_data_protection import CDPEngine
        engine = CDPEngine()
        session = engine.create_session("vol-001", "s3://backup/", rpo_seconds=60)
        engine.start(session.session_id)
        engine.record_write(session.session_id, 0, 1024, "vol-001", "csum")
        self.assertTrue(session.is_rpo_met)

    def test_pit_restore_returns_correct_entries(self):
        from api.backup.continuous_data_protection import CDPEngine
        engine = CDPEngine()
        session = engine.create_session("vol-001", "s3://backup/")
        engine.start(session.session_id)
        for i in range(5):
            engine.record_write(session.session_id, i*4096, 4096, "vol-001", f"csum{i}")
        target = datetime.utcnow()
        result = engine.restore_to_point_in_time(session.session_id, target)
        self.assertEqual(result["journal_entries"], 5)

    def test_pause_stop(self):
        from api.backup.continuous_data_protection import CDPEngine, CDPStatus
        engine = CDPEngine()
        session = engine.create_session("vol-001", "s3://")
        engine.start(session.session_id)
        engine.pause(session.session_id)
        self.assertEqual(session.status, CDPStatus.PAUSED)
        engine.stop(session.session_id)
        self.assertEqual(session.status, CDPStatus.STOPPED)


# ─────────────────────────────────────────────
# REPLICATION
# ─────────────────────────────────────────────

class ReplicationTest(TestCase):

    def test_import(self):
        from api.backup.replication import ReplicationManager
        self.assertTrue(callable(ReplicationManager))

    def test_register_target(self):
        from api.backup.replication import ReplicationManager, ReplicationTarget
        mgr = ReplicationManager()
        target = ReplicationTarget("t1", "Offsite S3", "s3",
                                   {"bucket": "offsite-backups"})
        mgr.register_target(target)
        self.assertIn("t1", mgr._targets)

    def test_create_and_execute_job(self):
        from api.backup.replication import ReplicationManager, ReplicationTarget, ReplicationStatus
        mgr = ReplicationManager()
        target = ReplicationTarget("t2", "Azure", "azure",
                                   {"container": "backup-replica"})
        mgr.register_target(target)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"backup to replicate")
            path = f.name
        try:
            job = mgr.create_job("bk-001", path, ["t2"])
            result = mgr.execute_job(job.job_id)
            self.assertEqual(result.status, ReplicationStatus.COMPLETED)
        finally:
            os.unlink(path)

    def test_list_jobs(self):
        from api.backup.replication import ReplicationManager, ReplicationTarget
        mgr = ReplicationManager()
        mgr.register_target(ReplicationTarget("t3", "GCS", "gcs", {}))
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"data")
            path = f.name
        try:
            mgr.create_job("bk-002", path, ["t3"])
            jobs = mgr.list_jobs(backup_id="bk-002")
            self.assertEqual(len(jobs), 1)
        finally:
            os.unlink(path)


# ─────────────────────────────────────────────
# INSTANT RECOVERY
# ─────────────────────────────────────────────

class InstantRecoveryTest(TestCase):

    def test_import(self):
        from api.backup.instant_recovery import InstantRecoveryManager
        self.assertTrue(callable(InstantRecoveryManager))

    def test_start_recovery_goes_live(self):
        from api.backup.instant_recovery import InstantRecoveryManager, RecoveryScope, InstantRecoveryStatus
        mgr = InstantRecoveryManager()
        session = mgr.start_recovery("bk-001", RecoveryScope.DATABASE,
                                      target_host="db-host", mount_point="/mnt/recovery")
        self.assertEqual(session.status, InstantRecoveryStatus.LIVE)
        self.assertIsNotNone(session.live_at)
        self.assertIsNotNone(session.time_to_live_seconds)

    def test_migration_and_complete(self):
        from api.backup.instant_recovery import InstantRecoveryManager, RecoveryScope, InstantRecoveryStatus
        mgr = InstantRecoveryManager()
        session = mgr.start_recovery("bk-002", RecoveryScope.FULL_VM,
                                      target_host="vm-host", mount_point="/mnt/vm")
        mgr.start_migration(session.session_id)
        mgr.update_migration_progress(session.session_id, 75.0)
        self.assertEqual(session.migration_progress_pct, 75.0)
        mgr.complete_recovery(session.session_id)
        self.assertEqual(session.status, InstantRecoveryStatus.COMPLETED)

    def test_list_live_sessions(self):
        from api.backup.instant_recovery import InstantRecoveryManager, RecoveryScope
        mgr = InstantRecoveryManager()
        mgr.start_recovery("bk-003", RecoveryScope.FILE, "host", "/mnt/f")
        mgr.start_recovery("bk-004", RecoveryScope.FILE, "host", "/mnt/g")
        self.assertEqual(len(mgr.list_live_sessions()), 2)


# ─────────────────────────────────────────────
# ML ANOMALY DETECTION
# ─────────────────────────────────────────────

class MLAnomalyDetectionTest(TestCase):

    def test_import(self):
        from api.backup.ml_anomaly_detection import BackupAnomalyDetector
        self.assertTrue(callable(BackupAnomalyDetector))

    def _make_sample(self, backup_id="bk-001", size=1024*1024*100,
                      duration=300.0, success=True, entropy=3.0):
        from api.backup.ml_anomaly_detection import BackupMetricSample
        return BackupMetricSample(
            backup_id=backup_id,
            timestamp=datetime.utcnow(),
            size_bytes=size,
            duration_seconds=duration,
            files_changed=100,
            success=success,
            entropy_score=entropy,
            change_rate_pct=5.0,
        )

    def test_no_alerts_without_baseline(self):
        from api.backup.ml_anomaly_detection import BackupAnomalyDetector
        detector = BackupAnomalyDetector()
        alerts = detector.ingest(self._make_sample())
        self.assertEqual(len(alerts), 0)  # no baseline yet

    def test_builds_baseline(self):
        from api.backup.ml_anomaly_detection import BackupAnomalyDetector
        detector = BackupAnomalyDetector(baseline_window=5)
        for i in range(6):
            detector.ingest(self._make_sample(backup_id=f"bk-{i}"))
        self.assertTrue(detector._size_baseline.has_baseline())

    def test_size_spike_detected(self):
        from api.backup.ml_anomaly_detection import BackupAnomalyDetector, AnomalyType
        detector = BackupAnomalyDetector(baseline_window=10)
        normal_size = 1024 * 1024 * 100  # 100 MB
        for i in range(10):
            detector.ingest(self._make_sample(f"bk-{i}", size=normal_size))
        # Inject 10x spike
        alerts = detector.ingest(self._make_sample("bk-spike", size=normal_size * 10))
        spike_alerts = [a for a in alerts if a.anomaly_type == AnomalyType.SIZE_SPIKE]
        self.assertGreater(len(spike_alerts), 0)

    def test_summary(self):
        from api.backup.ml_anomaly_detection import BackupAnomalyDetector
        detector = BackupAnomalyDetector()
        summary = detector.get_summary()
        self.assertIn("total_alerts_24h", summary)
        self.assertIn("size_baseline_mean_gb", summary)

    def test_baseline_model(self):
        from api.backup.ml_anomaly_detection import BaselineModel
        model = BaselineModel(window=5)
        for v in [100, 100, 100, 100, 100]:
            model.add(v)
        self.assertTrue(model.has_baseline())
        self.assertAlmostEqual(model.mean(), 100.0)
        self.assertAlmostEqual(model.z_score(100), 0.0)
        self.assertGreater(abs(model.z_score(500)), 2.0)


# ─────────────────────────────────────────────
# DATA GOVERNANCE
# ─────────────────────────────────────────────

class DataGovernanceTest(TestCase):

    def test_import(self):
        from api.backup.data_governance import DataGovernanceEngine
        self.assertTrue(callable(DataGovernanceEngine))

    def test_default_policies_loaded(self):
        from api.backup.data_governance import DataGovernanceEngine
        engine = DataGovernanceEngine()
        self.assertGreater(len(engine._policies), 0)
        self.assertIn("gdpr-personal", engine._policies)

    def test_classify_backup(self):
        from api.backup.data_governance import DataGovernanceEngine, DataClassification
        engine = DataGovernanceEngine()
        record = engine.classify_backup("bk-001", "gdpr-personal",
                                         metadata={"contains_pii": True})
        self.assertEqual(record.classification, DataClassification.RESTRICTED)
        self.assertTrue(record.contains_pii)

    def test_legal_hold_prevents_deletion(self):
        from api.backup.data_governance import DataGovernanceEngine, LegalHold, LegalHoldStatus
        engine = DataGovernanceEngine()
        hold = LegalHold(hold_id="hold-001", name="Investigation Hold",
                          reason="Legal case", applied_by="legal@example.com",
                          backup_ids=["bk-held"])
        engine.apply_legal_hold(hold)
        allowed, reason = engine.can_delete("bk-held")
        self.assertFalse(allowed)
        self.assertIn("Legal hold", reason)

    def test_release_hold_allows_deletion(self):
        from api.backup.data_governance import DataGovernanceEngine, LegalHold
        engine = DataGovernanceEngine()
        hold = LegalHold(hold_id="hold-002", name="Temp Hold", reason="audit",
                          applied_by="admin", backup_ids=["bk-002"])
        engine.apply_legal_hold(hold)
        engine.release_hold("hold-002", released_by="admin")
        allowed, _ = engine.can_delete("bk-002")
        self.assertTrue(allowed)

    def test_compliance_frameworks_in_policies(self):
        from api.backup.data_governance import DataGovernanceEngine, ComplianceFramework
        engine = DataGovernanceEngine()
        hipaa_policy = engine._policies.get("hipaa-phi")
        self.assertIsNotNone(hipaa_policy)
        self.assertIn(ComplianceFramework.HIPAA, hipaa_policy.frameworks)


# ─────────────────────────────────────────────
# REPORTING ENGINE
# ─────────────────────────────────────────────

class ReportingEngineTest(TestCase):

    def test_import(self):
        from api.backup.reporting_engine import BackupReportingEngine
        self.assertTrue(callable(BackupReportingEngine))

    def _make_definition(self, report_type):
        from api.backup.reporting_engine import ReportDefinition, ReportFormat
        return ReportDefinition(
            report_id=f"rpt-{report_type.value}",
            name=f"Test {report_type.value}",
            report_type=report_type,
            format=ReportFormat.JSON,
            date_range_days=30,
        )

    def test_generate_security_audit_report(self):
        from api.backup.reporting_engine import BackupReportingEngine, ReportType
        engine = BackupReportingEngine()
        report = engine.generate(self._make_definition(ReportType.SECURITY_AUDIT))
        self.assertIsNotNone(report)
        self.assertIn("rows", report.data)
        self.assertGreater(len(report.data["rows"]), 0)

    def test_generate_capacity_forecast_report(self):
        from api.backup.reporting_engine import BackupReportingEngine, ReportType
        engine = BackupReportingEngine()
        report = engine.generate(self._make_definition(ReportType.CAPACITY_FORECAST))
        self.assertIn("rows", report.data)

    def test_report_to_json(self):
        from api.backup.reporting_engine import BackupReportingEngine, ReportType
        import json
        engine = BackupReportingEngine()
        report = engine.generate(self._make_definition(ReportType.SECURITY_AUDIT))
        json_str = report.to_json()
        parsed = json.loads(json_str)
        self.assertIn("report", parsed)

    def test_report_to_html(self):
        from api.backup.reporting_engine import BackupReportingEngine, ReportType
        engine = BackupReportingEngine()
        report = engine.generate(self._make_definition(ReportType.SECURITY_AUDIT))
        html = report.to_html()
        self.assertIn("<table", html)
        self.assertIn("<tr>", html)

    def test_report_enum_values(self):
        from api.backup.reporting_engine import ReportType
        self.assertEqual(ReportType.EXECUTIVE_SUMMARY.value, "executive_summary")
        self.assertEqual(ReportType.COST_ANALYSIS.value, "cost_analysis")


# ─────────────────────────────────────────────
# GENAI INSIGHTS
# ─────────────────────────────────────────────

class GenAIInsightsTest(TestCase):

    def test_import(self):
        from api.backup.genai_insights import GenAIInsightsEngine
        self.assertTrue(callable(GenAIInsightsEngine))

    def test_context_builder(self):
        from api.backup.genai_insights import BackupContextBuilder
        builder = BackupContextBuilder()
        ctx = builder.build(include_stats=False)
        self.assertIsInstance(ctx, dict)

    @patch("backup.genai_insights.requests.post")
    def test_ask_returns_insight_response(self, mock_post):
        from api.backup.genai_insights import GenAIInsightsEngine
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "content": [{"text": '{"answer": "All good.", "confidence": 0.9, "suggested_actions": []}'}],
                "usage": {"output_tokens": 50},
            },
        )
        mock_post.return_value.raise_for_status = Mock()
        engine = GenAIInsightsEngine()
        response = engine.ask("What is the backup health?", extra_context={})
        self.assertEqual(response.answer, "All good.")
        self.assertAlmostEqual(response.confidence, 0.9)

    @patch("backup.genai_insights.requests.post", side_effect=Exception("timeout"))
    def test_ask_handles_api_failure(self, mock_post):
        from api.backup.genai_insights import GenAIInsightsEngine
        engine = GenAIInsightsEngine()
        response = engine.ask("test query")
        self.assertEqual(response.confidence, 0.0)
        self.assertIn("Unable", response.answer)

    def test_insight_query_dataclass(self):
        from api.backup.genai_insights import InsightQuery
        q = InsightQuery(query="How many backups failed?")
        self.assertIsNotNone(q.timestamp)
        self.assertEqual(q.query, "How many backups failed?")


# ─────────────────────────────────────────────
# CYBER PROTECT
# ─────────────────────────────────────────────

class CyberProtectTest(TestCase):

    def test_import(self):
        from api.backup.cyber_protect import CyberProtectionEngine
        self.assertTrue(callable(CyberProtectionEngine))

    def test_assess_healthy_endpoint(self):
        from api.backup.cyber_protect import CyberProtectionEngine, ProtectionStatus
        engine = CyberProtectionEngine()
        report = engine.assess_endpoint(
            endpoint_id="ep-001",
            last_backup_at=datetime.utcnow() - timedelta(hours=1),
            antimalware_last_scan=datetime.utcnow() - timedelta(hours=2),
        )
        self.assertIsNotNone(report)
        self.assertGreater(report.protection_score, 0)

    def test_stale_backup_lowers_score(self):
        from api.backup.cyber_protect import CyberProtectionEngine
        engine = CyberProtectionEngine()
        fresh = engine.assess_endpoint("ep-fresh",
                                        last_backup_at=datetime.utcnow() - timedelta(hours=1))
        stale = engine.assess_endpoint("ep-stale",
                                        last_backup_at=datetime.utcnow() - timedelta(days=5))
        self.assertGreater(fresh.protection_score, stale.protection_score)

    def test_protection_score_range(self):
        from api.backup.cyber_protect import CyberProtectionEngine
        engine = CyberProtectionEngine()
        report = engine.assess_endpoint("ep-002")
        self.assertGreaterEqual(report.protection_score, 0.0)
        self.assertLessEqual(report.protection_score, 100.0)

    def test_patch_manager(self):
        from api.backup.cyber_protect import PatchManager, PatchRecord
        mgr = PatchManager()
        patch = PatchRecord("P001", "Security Update", "KB12345",
                             "backup_agent", "critical",
                             released_at=datetime.utcnow())
        mgr.register_patch(patch)
        self.assertEqual(len(mgr.pending_patches()), 1)
        mgr.apply_patch("P001")
        self.assertEqual(len(mgr.pending_patches()), 0)
        self.assertEqual(len(mgr.applied_patches()), 1)

    def test_vulnerability_severity_enum(self):
        from api.backup.cyber_protect import VulnerabilitySeverity
        self.assertEqual(VulnerabilitySeverity.CRITICAL.value, "critical")
        self.assertEqual(VulnerabilitySeverity.HIGH.value, "high")


# ─────────────────────────────────────────────
# FORENSIC BACKUP
# ─────────────────────────────────────────────

class ForensicBackupTest(TestCase):

    def _make_metadata(self, case_id="CASE-001"):
        from api.backup.forensic_backup import ForensicMetadata
        return ForensicMetadata(
            case_id=case_id,
            examiner_name="Jane Smith",
            examiner_badge="FE-42",
            acquisition_start=datetime.utcnow(),
            source_device="server-01",
        )

    def test_import(self):
        from api.backup.forensic_backup import ForensicAcquisitionEngine
        self.assertTrue(callable(ForensicAcquisitionEngine))

    def test_acquire_file_creates_record(self):
        from api.backup.forensic_backup import ForensicAcquisitionEngine, ForensicImageType
        engine = ForensicAcquisitionEngine()
        with tempfile.NamedTemporaryFile(delete=False) as src:
            src.write(b"evidence data " * 100)
            src_path = src.name
        dest = src_path + ".forensic"
        try:
            record = engine.acquire(src_path, dest,
                                     metadata=self._make_metadata(),
                                     image_type=ForensicImageType.FILE_SYSTEM)
            self.assertIsNotNone(record.record_id)
            self.assertTrue(record.metadata.is_verified)
        finally:
            os.unlink(src_path)
            if os.path.exists(dest):
                os.unlink(dest)

    def test_integrity_verification(self):
        from api.backup.forensic_backup import ForensicAcquisitionEngine, ForensicImageType
        engine = ForensicAcquisitionEngine()
        with tempfile.NamedTemporaryFile(delete=False) as src:
            src.write(b"forensic content")
            src_path = src.name
        dest = src_path + ".img"
        try:
            record = engine.acquire(src_path, dest, metadata=self._make_metadata())
            self.assertTrue(engine.verify_integrity(record.record_id))
        finally:
            os.unlink(src_path)
            if os.path.exists(dest):
                os.unlink(dest)

    def test_chain_of_custody_tracked(self):
        from api.backup.forensic_backup import ForensicAcquisitionEngine, ChainOfCustodyEvent
        engine = ForensicAcquisitionEngine()
        with tempfile.NamedTemporaryFile(delete=False) as src:
            src.write(b"custody test")
            src_path = src.name
        dest = src_path + ".cust"
        try:
            record = engine.acquire(src_path, dest, metadata=self._make_metadata("CASE-002"))
            engine.transfer_custody(record.record_id, "Jane Smith", "Prosecutor",
                                     purpose="Trial evidence")
            events = [e.event for e in record.chain_of_custody]
            self.assertIn(ChainOfCustodyEvent.CREATED, events)
            self.assertIn(ChainOfCustodyEvent.TRANSFERRED, events)
        finally:
            os.unlink(src_path)
            if os.path.exists(dest):
                os.unlink(dest)

    def test_evidence_manifest_structure(self):
        from api.backup.forensic_backup import ForensicAcquisitionEngine
        engine = ForensicAcquisitionEngine()
        with tempfile.NamedTemporaryFile(delete=False) as src:
            src.write(b"manifest test")
            src_path = src.name
        dest = src_path + ".manifest"
        try:
            record = engine.acquire(src_path, dest, metadata=self._make_metadata("CASE-003"))
            manifest = engine.export_manifest(record.record_id)
            self.assertIn("case_id", manifest)
            self.assertIn("integrity_verified", manifest)
            self.assertIn("chain_of_custody", manifest)
        finally:
            os.unlink(src_path)
            if os.path.exists(dest):
                os.unlink(dest)
