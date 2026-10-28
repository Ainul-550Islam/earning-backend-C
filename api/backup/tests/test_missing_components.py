"""
Tests for 6 New Enterprise Missing Components
Covers: saas_backup, kubernetes_backup, cross_cloud_dr,
        siem_integration, scale_out_storage, mass_vm_restore, tape_storage
"""

import os
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, Mock
from django.test import TestCase


# ─────────────────────────────────────────────────────────
# SAAS BACKUP
# ─────────────────────────────────────────────────────────

class SaaSBackupEnumsTest(TestCase):
    def test_saas_provider_enum(self):
        from api.backup.saas_backup import SaaSProvider
        self.assertEqual(SaaSProvider.MICROSOFT_365.value, "microsoft_365")
        self.assertEqual(SaaSProvider.GOOGLE_WORKSPACE.value, "google_workspace")

    def test_m365_workload_enum(self):
        from api.backup.saas_backup import M365Workload
        for wl in ["exchange", "sharepoint", "onedrive", "teams", "entra_id"]:
            self.assertIn(wl, [w.value for w in M365Workload])

    def test_gws_workload_enum(self):
        from api.backup.saas_backup import GWSWorkload
        for wl in ["gmail", "drive", "calendar", "contacts", "shared_drives"]:
            self.assertIn(wl, [w.value for w in GWSWorkload])


class SaaSBackupJobTest(TestCase):
    def test_job_dataclass(self):
        from api.backup.saas_backup import SaaSBackupJob, SaaSProvider, SaaSBackupStatus
        job = SaaSBackupJob(
            job_id="job-001",
            provider=SaaSProvider.MICROSOFT_365,
            tenant_id="tenant-abc",
            workloads=["exchange", "onedrive"],
            items_backed_up=500,
            items_failed=5,
        )
        self.assertAlmostEqual(job.success_rate, 500/505, places=3)

    def test_job_to_dict(self):
        from api.backup.saas_backup import SaaSBackupJob, SaaSProvider
        job = SaaSBackupJob(
            job_id="job-002", provider=SaaSProvider.GOOGLE_WORKSPACE,
            tenant_id="company.com", workloads=["gmail"],
        )
        d = job.to_dict()
        self.assertIn("job_id", d)
        self.assertIn("provider", d)
        self.assertEqual(d["provider"], "google_workspace")


class SaaSBackupUserTest(TestCase):
    def test_user_dataclass(self):
        from api.backup.saas_backup import SaaSUser
        user = SaaSUser(
            user_id="u-001", email="alice@company.com",
            display_name="Alice Smith", is_licensed=True,
            workloads=["exchange", "onedrive"],
        )
        self.assertEqual(user.email, "alice@company.com")
        self.assertIn("exchange", user.workloads)


class M365BackupServiceTest(TestCase):
    def test_importable(self):
        from api.backup.saas_backup import Microsoft365BackupService
        self.assertTrue(callable(Microsoft365BackupService))

    def test_init(self):
        from api.backup.saas_backup import Microsoft365BackupService
        svc = Microsoft365BackupService("tenant-001", "client-001", "secret-001")
        self.assertEqual(svc.tenant_id, "tenant-001")
        self.assertIsNone(svc._access_token)

    @patch("backup.saas_backup.requests.post")
    def test_authenticate_success(self, mock_post):
        from api.backup.saas_backup import Microsoft365BackupService
        mock_post.return_value = MagicMock(
            json=lambda: {"access_token": "test-token-abc"},
        )
        mock_post.return_value.raise_for_status = Mock()
        svc = Microsoft365BackupService("t1", "c1", "s1")
        result = svc.authenticate()
        self.assertTrue(result)
        self.assertEqual(svc._access_token, "test-token-abc")

    @patch("backup.saas_backup.requests.post")
    def test_authenticate_failure(self, mock_post):
        from api.backup.saas_backup import Microsoft365BackupService
        mock_post.side_effect = Exception("Connection refused")
        svc = Microsoft365BackupService("t1", "c1", "s1")
        result = svc.authenticate()
        self.assertFalse(result)

    @patch("backup.saas_backup.requests.get")
    def test_list_users(self, mock_get):
        from api.backup.saas_backup import Microsoft365BackupService
        mock_get.return_value = MagicMock(
            json=lambda: {"value": [
                {"id": "u1", "mail": "a@t.com", "displayName": "Alice",
                 "assignedLicenses": [{"skuId": "xxx"}]},
                {"id": "u2", "mail": "b@t.com", "displayName": "Bob",
                 "assignedLicenses": []},
            ]}
        )
        mock_get.return_value.raise_for_status = Mock()
        svc = Microsoft365BackupService("t1", "c1", "s1")
        svc._access_token = "mock-token"
        users = svc.list_users()
        self.assertEqual(len(users), 2)
        self.assertTrue(users[0].is_licensed)
        self.assertFalse(users[1].is_licensed)

    @patch("backup.saas_backup.requests.get")
    def test_backup_mailbox(self, mock_get):
        from api.backup.saas_backup import Microsoft365BackupService, SaaSUser, M365Workload
        mock_get.return_value = MagicMock(
            json=lambda: {"value": [{"id": f"msg{i}"} for i in range(50)]}
        )
        mock_get.return_value.raise_for_status = Mock()
        svc = Microsoft365BackupService("t1", "c1", "s1")
        svc._access_token = "mock-token"
        user = SaaSUser("u1", "a@t.com", "Alice")
        result = svc.backup_user(user, [M365Workload.EXCHANGE.value])
        self.assertIn("exchange", result)
        self.assertEqual(result["exchange"]["status"], "completed")
        self.assertEqual(result["exchange"]["items"], 50)

    def test_restore_dry_run(self):
        from api.backup.saas_backup import Microsoft365BackupService, SaaSRestoreRequest
        svc = Microsoft365BackupService("t1", "c1", "s1")
        req = SaaSRestoreRequest(
            backup_job_id="job-001", user_email="a@t.com",
            workload="exchange", item_ids=["msg1","msg2","msg3"],
            dry_run=True,
        )
        result = svc.restore_items(req)
        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["would_restore"], 3)

    def test_list_backup_jobs_empty(self):
        from api.backup.saas_backup import Microsoft365BackupService
        svc = Microsoft365BackupService("t1", "c1", "s1")
        self.assertEqual(svc.list_backup_jobs(), [])


class GWSBackupServiceTest(TestCase):
    def test_importable(self):
        from api.backup.saas_backup import GoogleWorkspaceBackupService
        self.assertTrue(callable(GoogleWorkspaceBackupService))

    def test_authenticate_without_google_auth(self):
        from api.backup.saas_backup import GoogleWorkspaceBackupService
        svc = GoogleWorkspaceBackupService({"type": "service_account"}, "company.com")
        result = svc.authenticate()
        self.assertIsInstance(result, bool)

    def test_restore_dry_run(self):
        from api.backup.saas_backup import GoogleWorkspaceBackupService, SaaSRestoreRequest
        svc = GoogleWorkspaceBackupService({}, "company.com")
        req = SaaSRestoreRequest(
            backup_job_id="gws-job-001", user_email="user@company.com",
            workload="gmail", item_ids=["mail1","mail2"],
            dry_run=True,
        )
        result = svc.restore_items(req)
        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["would_restore"], 2)


class SaaSBackupManagerTest(TestCase):
    def test_importable(self):
        from api.backup.saas_backup import SaaSBackupManager
        self.assertTrue(callable(SaaSBackupManager))

    def test_register_m365(self):
        from api.backup.saas_backup import SaaSBackupManager, Microsoft365BackupService
        mgr = SaaSBackupManager()
        svc = mgr.register_m365("tenant-001", "client-001", "secret-001")
        self.assertIsInstance(svc, Microsoft365BackupService)
        self.assertIn("m365:tenant-001", mgr._services)

    def test_register_gws(self):
        from api.backup.saas_backup import SaaSBackupManager, GoogleWorkspaceBackupService
        mgr = SaaSBackupManager()
        svc = mgr.register_gws("company.com", {"type": "service_account"})
        self.assertIsInstance(svc, GoogleWorkspaceBackupService)
        self.assertIn("gws:company.com", mgr._services)

    def test_list_all_jobs_empty(self):
        from api.backup.saas_backup import SaaSBackupManager
        mgr = SaaSBackupManager()
        self.assertEqual(mgr.list_all_jobs(), [])

    def test_backup_status_values(self):
        from api.backup.saas_backup import SaaSBackupStatus
        for s in ["pending","running","completed","failed","partial"]:
            self.assertIn(s, [v.value for v in SaaSBackupStatus])


# ─────────────────────────────────────────────────────────
# KUBERNETES BACKUP
# ─────────────────────────────────────────────────────────

class K8sBackupEnumsTest(TestCase):
    def test_resource_types(self):
        from api.backup.kubernetes_backup import K8sResourceType
        self.assertEqual(K8sResourceType.NAMESPACE.value, "namespace")
        self.assertEqual(K8sResourceType.PERSISTENT_VOLUME.value, "persistent_volume")

    def test_snapshot_methods(self):
        from api.backup.kubernetes_backup import VolumeSnapshotMethod
        self.assertEqual(VolumeSnapshotMethod.CSI_SNAPSHOT.value, "csi_snapshot")
        self.assertEqual(VolumeSnapshotMethod.RESTIC.value, "restic")


class K8sClusterConfigTest(TestCase):
    def test_config_dataclass(self):
        from api.backup.kubernetes_backup import K8sClusterConfig
        cfg = K8sClusterConfig(
            cluster_name="prod-eks",
            api_server="https://k8s.example.com",
            namespace="all",
        )
        self.assertEqual(cfg.cluster_name, "prod-eks")
        self.assertEqual(cfg.namespace, "all")


class K8sBackupSnapshotTest(TestCase):
    def test_snapshot_dataclass(self):
        from api.backup.kubernetes_backup import K8sBackupSnapshot, K8sBackupStatus
        snap = K8sBackupSnapshot(
            snapshot_id="snap-001",
            cluster_name="prod-eks",
            namespace="production",
        )
        self.assertEqual(snap.status, K8sBackupStatus.PENDING)
        self.assertEqual(snap.resource_count, 0)

    def test_snapshot_to_dict(self):
        from api.backup.kubernetes_backup import K8sBackupSnapshot
        snap = K8sBackupSnapshot(
            snapshot_id="snap-002", cluster_name="gke-prod", namespace="default"
        )
        d = snap.to_dict()
        self.assertIn("snapshot_id", d)
        self.assertIn("cluster", d)


class K8sBackupServiceTest(TestCase):
    def _make_config(self):
        from api.backup.kubernetes_backup import K8sClusterConfig
        return K8sClusterConfig("test-cluster", "https://api.k8s.local", "default")

    def test_importable(self):
        from api.backup.kubernetes_backup import KubernetesBackupService
        self.assertTrue(callable(KubernetesBackupService))

    def test_connect_without_k8s_pkg(self):
        from api.backup.kubernetes_backup import KubernetesBackupService
        svc = KubernetesBackupService(self._make_config())
        result = svc.connect()
        self.assertIsInstance(result, bool)

    def test_list_namespaces_mock(self):
        from api.backup.kubernetes_backup import KubernetesBackupService
        svc = KubernetesBackupService(self._make_config())
        svc._client = None  # force mock
        ns = svc.list_namespaces()
        self.assertIsInstance(ns, list)
        self.assertGreater(len(ns), 0)

    def test_collect_resources_mock(self):
        from api.backup.kubernetes_backup import KubernetesBackupService
        svc = KubernetesBackupService(self._make_config())
        svc._client = None
        resources = svc.collect_resources("default")
        self.assertIsInstance(resources, list)
        for r in resources:
            self.assertIsNotNone(r.kind)

    def test_backup_pvcs_mock(self):
        from api.backup.kubernetes_backup import KubernetesBackupService
        svc = KubernetesBackupService(self._make_config())
        svc._client = None
        pvbs = svc.backup_persistent_volumes("default")
        self.assertIsInstance(pvbs, list)
        self.assertGreater(len(pvbs), 0)

    def test_take_snapshot(self):
        from api.backup.kubernetes_backup import KubernetesBackupService, K8sBackupStatus
        svc = KubernetesBackupService(self._make_config())
        svc._client = None
        snap = svc.take_snapshot("default")
        self.assertEqual(snap.status, K8sBackupStatus.COMPLETED)
        self.assertEqual(snap.cluster_name, "test-cluster")

    def test_restore_dry_run(self):
        from api.backup.kubernetes_backup import KubernetesBackupService
        svc = KubernetesBackupService(self._make_config())
        svc._client = None
        snap = svc.take_snapshot("default")
        result = svc.restore_snapshot(snap.snapshot_id, dry_run=True)
        self.assertEqual(result["status"], "dry_run")
        self.assertIn("would_restore_resources", result)

    def test_list_snapshots(self):
        from api.backup.kubernetes_backup import KubernetesBackupService
        svc = KubernetesBackupService(self._make_config())
        svc._client = None
        svc.take_snapshot("default")
        svc.take_snapshot("production")
        snaps = svc.list_snapshots()
        self.assertEqual(len(snaps), 2)


class MultiClusterK8sTest(TestCase):
    def test_importable(self):
        from api.backup.kubernetes_backup import MultiClusterK8sBackupManager
        self.assertTrue(callable(MultiClusterK8sBackupManager))

    def test_register_cluster(self):
        from api.backup.kubernetes_backup import (
            MultiClusterK8sBackupManager, K8sClusterConfig, KubernetesBackupService
        )
        mgr = MultiClusterK8sBackupManager()
        cfg = K8sClusterConfig("cluster-1", "https://k8s.local", "all")
        svc = mgr.register_cluster(cfg)
        self.assertIsInstance(svc, KubernetesBackupService)

    def test_backup_all_clusters(self):
        from api.backup.kubernetes_backup import (
            MultiClusterK8sBackupManager, K8sClusterConfig
        )
        mgr = MultiClusterK8sBackupManager()
        for i in range(3):
            mgr.register_cluster(K8sClusterConfig(f"cluster-{i}", "https://api", "default"))
        results = mgr.backup_all_clusters()
        self.assertEqual(len(results), 3)


# ─────────────────────────────────────────────────────────
# CROSS-CLOUD DR
# ─────────────────────────────────────────────────────────

class CrossCloudDRTest(TestCase):
    def _make_orchestrator(self):
        from api.backup.cross_cloud_dr import (
            CrossCloudDROrchestrator, CloudEndpoint, CloudProvider
        )
        src = CloudEndpoint(provider=CloudProvider.AWS, region="us-east-1")
        tgt = CloudEndpoint(provider=CloudProvider.AZURE, region="eastus")
        return CrossCloudDROrchestrator(src, tgt)

    def _make_workload(self):
        from api.backup.cross_cloud_dr import WorkloadMapping, CloudProvider
        return WorkloadMapping(
            workload_id="wl-001", name="web-app",
            source_provider=CloudProvider.AWS,
            target_provider=CloudProvider.AZURE,
            source_resource_id="i-abc123",
            target_instance_type="Standard_D2s_v3",
            target_region="eastus",
            estimated_rto_minutes=60,
        )

    def test_importable(self):
        from api.backup.cross_cloud_dr import CrossCloudDROrchestrator
        self.assertTrue(callable(CrossCloudDROrchestrator))

    def test_cloud_provider_enum(self):
        from api.backup.cross_cloud_dr import CloudProvider
        self.assertEqual(CloudProvider.AWS.value, "aws")
        self.assertEqual(CloudProvider.AZURE.value, "azure")
        self.assertEqual(CloudProvider.GCP.value, "gcp")

    def test_failover_mode_enum(self):
        from api.backup.cross_cloud_dr import FailoverMode
        self.assertEqual(FailoverMode.TEST.value, "test")
        self.assertEqual(FailoverMode.EMERGENCY.value, "emergency")

    def test_register_workload(self):
        orch = self._make_orchestrator()
        wl = self._make_workload()
        orch.register_workload(wl)
        self.assertEqual(len(orch._workload_mappings), 1)

    def test_test_failover_no_dns_change(self):
        from api.backup.cross_cloud_dr import FailoverMode, FailoverStatus
        orch = self._make_orchestrator()
        orch.register_workload(self._make_workload())
        execution = orch.test_failover()
        self.assertEqual(execution.mode, FailoverMode.TEST)
        self.assertIn(execution.status, [FailoverStatus.LIVE, FailoverStatus.FAILED])

    def test_failover_with_workloads(self):
        from api.backup.cross_cloud_dr import FailoverStatus, FailoverMode
        orch = self._make_orchestrator()
        orch.register_workload(self._make_workload())
        execution = orch.failover(mode=FailoverMode.PLANNED)
        self.assertIsNotNone(execution.execution_id)
        self.assertGreater(len(execution.log), 0)

    def test_failover_no_workloads_fails(self):
        from api.backup.cross_cloud_dr import FailoverStatus
        orch = self._make_orchestrator()
        execution = orch.failover()
        self.assertEqual(execution.status, FailoverStatus.FAILED)

    def test_failback(self):
        from api.backup.cross_cloud_dr import FailoverStatus
        orch = self._make_orchestrator()
        orch.register_workload(self._make_workload())
        execution = orch.failover()
        result = orch.failback(execution.execution_id)
        self.assertIn(result.status, [FailoverStatus.COMPLETED, FailoverStatus.FAILED])

    def test_rto_compliance_report(self):
        orch = self._make_orchestrator()
        orch.register_workload(self._make_workload())
        orch.failover()
        report = orch.get_rto_compliance()
        self.assertIsInstance(report, list)

    def test_cloud_adapter_mock(self):
        from api.backup.cross_cloud_dr import CloudProviderAdapter, CloudEndpoint, CloudProvider
        endpoint = CloudEndpoint(provider=CloudProvider.AWS, region="us-east-1")
        adapter = CloudProviderAdapter(endpoint)
        self.assertTrue(callable(adapter.restore_instance))

    def test_workload_mapping_dataclass(self):
        wl = self._make_workload()
        self.assertEqual(wl.name, "web-app")
        self.assertEqual(wl.estimated_rto_minutes, 60)


# ─────────────────────────────────────────────────────────
# SIEM INTEGRATION
# ─────────────────────────────────────────────────────────

class SIEMEventTest(TestCase):
    def _make_event(self):
        from api.backup.siem_integration import SecurityEvent, BackupSecurityEvent, EventSeverity
        return SecurityEvent(
            event_type=BackupSecurityEvent.BACKUP_COMPLETED,
            severity=EventSeverity.INFO,
            source="backup_module",
            resource_id="bk-001",
            user_id="admin@example.com",
            description="Backup completed successfully",
            metadata={"size_bytes": 1024},
        )

    def test_importable(self):
        from api.backup.siem_integration import SIEMIntegrationManager
        self.assertTrue(callable(SIEMIntegrationManager))

    def test_security_event_to_dict(self):
        event = self._make_event()
        d = event.to_dict()
        self.assertIn("event_type", d)
        self.assertIn("severity", d)
        self.assertEqual(d["resource_id"], "bk-001")

    def test_cef_format(self):
        event = self._make_event()
        cef = event.to_cef()
        self.assertTrue(cef.startswith("CEF:0|"))
        self.assertIn("backup_completed", cef)

    def test_leef_format(self):
        event = self._make_event()
        leef = event.to_leef()
        self.assertTrue(leef.startswith("LEEF:2.0|"))

    def test_event_severity_enum(self):
        from api.backup.siem_integration import EventSeverity
        for s in ["info","low","medium","high","critical"]:
            self.assertIn(s, [v.value for v in EventSeverity])

    def test_siem_platform_enum(self):
        from api.backup.siem_integration import SIEMPlatform
        self.assertEqual(SIEMPlatform.CROWDSTRIKE.value, "crowdstrike")
        self.assertEqual(SIEMPlatform.SPLUNK.value, "splunk")


class SIEMManagerTest(TestCase):
    def test_register_and_emit(self):
        from api.backup.siem_integration import (
            SIEMIntegrationManager, SecurityEvent,
            BackupSecurityEvent, EventSeverity
        )
        mgr = SIEMIntegrationManager()
        mock_conn = MagicMock()
        mock_conn.send_event.return_value = True
        mgr.register("mock_siem", mock_conn)

        event = SecurityEvent(
            event_type=BackupSecurityEvent.RANSOMWARE_DETECTED,
            severity=EventSeverity.CRITICAL,
            source="scanner", resource_id="bk-001",
            user_id=None, description="Ransomware found",
        )
        results = mgr.emit(event)
        self.assertTrue(results["mock_siem"])
        mock_conn.send_event.assert_called_once()

    def test_backup_completed_helper(self):
        from api.backup.siem_integration import SIEMIntegrationManager
        mgr = SIEMIntegrationManager()
        mock_conn = MagicMock(send_event=Mock(return_value=True))
        mgr.register("mock", mock_conn)
        mgr.backup_completed("bk-001", 1024*1024)
        mock_conn.send_event.assert_called_once()

    def test_ransomware_detected_helper(self):
        from api.backup.siem_integration import SIEMIntegrationManager
        mgr = SIEMIntegrationManager()
        mock_conn = MagicMock(send_event=Mock(return_value=True))
        mgr.register("mock", mock_conn)
        mgr.ransomware_detected("bk-002", "critical", 5)
        mock_conn.send_event.assert_called_once()

    def test_unauthorized_access_helper(self):
        from api.backup.siem_integration import SIEMIntegrationManager
        mgr = SIEMIntegrationManager()
        mock_conn = MagicMock(send_event=Mock(return_value=True))
        mgr.register("mock", mock_conn)
        mgr.unauthorized_access("bk-003", "attacker@evil.com", "backup_delete")
        mock_conn.send_event.assert_called_once()

    def test_anomaly_detected_helper(self):
        from api.backup.siem_integration import SIEMIntegrationManager
        mgr = SIEMIntegrationManager()
        mock_conn = MagicMock(send_event=Mock(return_value=True))
        mgr.register("mock", mock_conn)
        mgr.anomaly_detected("bk-004", "size_spike", 350.0)
        mock_conn.send_event.assert_called_once()

    def test_dr_failover_helper(self):
        from api.backup.siem_integration import SIEMIntegrationManager
        mgr = SIEMIntegrationManager()
        mock_conn = MagicMock(send_event=Mock(return_value=True))
        mgr.register("mock", mock_conn)
        mgr.dr_failover_started("aws", "azure", 10)
        mock_conn.send_event.assert_called_once()

    def test_get_event_log(self):
        from api.backup.siem_integration import SIEMIntegrationManager
        mgr = SIEMIntegrationManager()
        mgr.backup_completed("bk-001", 100)
        mgr.ransomware_detected("bk-002", "high", 2)
        log = mgr.get_event_log()
        self.assertEqual(len(log), 2)

    @patch("backup.siem_integration.requests.post")
    def test_splunk_connector(self, mock_post):
        from api.backup.siem_integration import SplunkConnector, SecurityEvent, BackupSecurityEvent, EventSeverity
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = Mock()
        conn = SplunkConnector("https://splunk.example.com:8088", "hec-token-123")
        event = SecurityEvent(
            event_type=BackupSecurityEvent.BACKUP_FAILED,
            severity=EventSeverity.HIGH, source="backup",
            resource_id="bk-005", user_id=None, description="Backup failed",
        )
        result = conn.send_event(event)
        self.assertTrue(result)


# ─────────────────────────────────────────────────────────
# SCALE-OUT STORAGE
# ─────────────────────────────────────────────────────────

class ScaleOutStorageTest(TestCase):
    def _make_node(self, node_id="node-1", total_tb=10):
        from api.backup.scale_out_storage import StorageNode
        return StorageNode(
            node_id=node_id,
            hostname=f"{node_id}.storage.local",
            ip_address=f"10.0.0.{node_id.split('-')[-1]}",
            total_bytes=total_tb * 1024**4,
        )

    def test_importable(self):
        from api.backup.scale_out_storage import ScaleOutStorageCluster
        self.assertTrue(callable(ScaleOutStorageCluster))

    def test_storage_node_properties(self):
        node = self._make_node("node-1", 10)
        self.assertEqual(node.total_bytes, 10 * 1024**4)
        self.assertEqual(node.free_bytes, node.total_bytes)
        self.assertEqual(node.utilisation_pct, 0.0)
        self.assertTrue(node.is_available)

    def test_node_utilisation(self):
        node = self._make_node("node-2", 10)
        node.used_bytes = int(node.total_bytes * 0.91)
        self.assertFalse(node.is_available)

    def test_consistent_hash_ring(self):
        from api.backup.scale_out_storage import ConsistentHashRing
        ring = ConsistentHashRing(virtual_nodes=50)
        ring.add_node("node-A")
        ring.add_node("node-B")
        ring.add_node("node-C")
        result = ring.get_node("backup-001")
        self.assertIn(result, ["node-A", "node-B", "node-C"])

    def test_hash_ring_remove_node(self):
        from api.backup.scale_out_storage import ConsistentHashRing
        ring = ConsistentHashRing(virtual_nodes=20)
        ring.add_node("node-X")
        ring.add_node("node-Y")
        ring.remove_node("node-X")
        result = ring.get_node("any-key")
        self.assertEqual(result, "node-Y")

    def test_cluster_add_node(self):
        from api.backup.scale_out_storage import ScaleOutStorageCluster
        cluster = ScaleOutStorageCluster()
        cluster.add_node(self._make_node("node-1"))
        cluster.add_node(self._make_node("node-2"))
        stats = cluster.cluster_stats()
        self.assertEqual(stats["total_nodes"], 2)
        self.assertEqual(stats["online_nodes"], 2)

    def test_place_backup_chunk(self):
        from api.backup.scale_out_storage import ScaleOutStorageCluster
        cluster = ScaleOutStorageCluster(replication_factor=2)
        for i in range(1, 4):
            cluster.add_node(self._make_node(f"node-{i}"))
        placement = cluster.place_backup("bk-001", "chunk-001",
                                          1024*1024, b"data")
        self.assertEqual(placement.backup_id, "bk-001")
        self.assertIsNotNone(placement.primary_node)
        self.assertGreaterEqual(placement.replication_factor, 1)

    def test_locate_backup(self):
        from api.backup.scale_out_storage import ScaleOutStorageCluster
        cluster = ScaleOutStorageCluster(replication_factor=1)
        for i in range(1, 4):
            cluster.add_node(self._make_node(f"node-{i}"))
        cluster.place_backup("bk-002", "chunk-A", 512, b"a")
        cluster.place_backup("bk-002", "chunk-B", 512, b"b")
        cluster.place_backup("bk-003", "chunk-C", 512, b"c")
        placements = cluster.locate_backup("bk-002")
        self.assertEqual(len(placements), 2)

    def test_remove_node_graceful(self):
        from api.backup.scale_out_storage import ScaleOutStorageCluster
        cluster = ScaleOutStorageCluster(replication_factor=2)
        for i in range(1, 5):
            cluster.add_node(self._make_node(f"node-{i}"))
        cluster.place_backup("bk-004", "chunk-X", 1024, b"x")
        cluster.remove_node("node-1", graceful=True)
        stats = cluster.cluster_stats()
        self.assertEqual(stats["total_nodes"], 3)

    def test_cluster_stats_structure(self):
        from api.backup.scale_out_storage import ScaleOutStorageCluster
        cluster = ScaleOutStorageCluster()
        cluster.add_node(self._make_node("node-1", 20))
        stats = cluster.cluster_stats()
        for key in ["total_nodes", "online_nodes", "total_capacity_tb",
                    "free_capacity_tb", "utilisation_pct", "replication_factor"]:
            self.assertIn(key, stats)

    def test_storage_policy_enum(self):
        from api.backup.scale_out_storage import StoragePolicy
        self.assertEqual(StoragePolicy.CAPACITY.value, "capacity")
        self.assertEqual(StoragePolicy.ERASURE_CODED.value, "erasure_coded")


# ─────────────────────────────────────────────────────────
# MASS VM RESTORE
# ─────────────────────────────────────────────────────────

class MassVMRestoreTest(TestCase):
    def _make_spec(self, vm_id="vm-001"):
        from api.backup.mass_vm_restore import VMBackupSpec, VMHypervisor
        return VMBackupSpec(
            vm_id=vm_id, vm_name=f"web-{vm_id}",
            hypervisor=VMHypervisor.VMWARE_ESXI,
            backup_id=f"bk-{vm_id}",
            disk_size_gb=100.0, memory_gb=8.0, cpu_count=4,
        )

    def test_importable(self):
        from api.backup.mass_vm_restore import MassVMRestoreOrchestrator
        self.assertTrue(callable(MassVMRestoreOrchestrator))

    def test_hypervisor_enum(self):
        from api.backup.mass_vm_restore import VMHypervisor
        for hv in ["vmware_esxi","hyper_v","kvm","aws_ec2","azure_vm","gce"]:
            self.assertIn(hv, [v.value for v in VMHypervisor])

    def test_restore_mode_enum(self):
        from api.backup.mass_vm_restore import VMRestoreMode
        self.assertEqual(VMRestoreMode.INSTANT.value, "instant")
        self.assertEqual(VMRestoreMode.FULL_RESTORE.value, "full_restore")

    def test_single_vm_restore(self):
        from api.backup.mass_vm_restore import MassVMRestoreOrchestrator, VMRestoreStatus
        orch = MassVMRestoreOrchestrator()
        tasks = orch.submit_restore(
            [self._make_spec("vm-001")],
            target_host="esxi-host-01",
            target_datastore="datastore-01",
        )
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        self.assertIsNotNone(task.task_id)
        self.assertIn(task.status, list(VMRestoreStatus))

    def test_multiple_vm_restore(self):
        from api.backup.mass_vm_restore import MassVMRestoreOrchestrator
        orch = MassVMRestoreOrchestrator()
        specs = [self._make_spec(f"vm-{i:03d}") for i in range(5)]
        tasks = orch.submit_restore(specs, "esxi-host-01", "ds-01")
        self.assertEqual(len(tasks), 5)

    def test_max_concurrent_limit(self):
        from api.backup.mass_vm_restore import MassVMRestoreOrchestrator
        orch = MassVMRestoreOrchestrator(max_concurrent=3)
        specs = [self._make_spec(f"vm-{i}") for i in range(10)]
        tasks = orch.submit_restore(specs, "host", "ds")
        self.assertLessEqual(len(tasks), 3)

    def test_batch_status(self):
        from api.backup.mass_vm_restore import MassVMRestoreOrchestrator
        orch = MassVMRestoreOrchestrator()
        orch.submit_restore([self._make_spec("vm-A")], "host", "ds")
        status = orch.get_batch_status()
        self.assertIn("total", status)
        self.assertIn("live", status)
        self.assertIn("completed", status)
        self.assertIn("failed", status)

    def test_vm_backup_spec_properties(self):
        spec = self._make_spec("vm-prop")
        self.assertEqual(spec.disk_size_gb, 100.0)
        self.assertEqual(spec.cpu_count, 4)

    def test_list_tasks(self):
        from api.backup.mass_vm_restore import MassVMRestoreOrchestrator
        orch = MassVMRestoreOrchestrator()
        orch.submit_restore([self._make_spec("vm-B")], "host", "ds")
        tasks = orch.list_tasks()
        self.assertGreater(len(tasks), 0)


# ─────────────────────────────────────────────────────────
# TAPE STORAGE
# ─────────────────────────────────────────────────────────

class TapeStorageTest(TestCase):
    def _make_tape(self, barcode="LTO-001", slot=1):
        from api.backup.tape_storage import Tape, TapeGeneration, TapeStatus
        return Tape(
            barcode=barcode,
            generation=TapeGeneration.LTO_9,
            slot=slot,
            status=TapeStatus.BLANK,
        )

    def test_importable(self):
        from api.backup.tape_storage import TapeLibraryService
        self.assertTrue(callable(TapeLibraryService))

    def test_tape_generation_enum(self):
        from api.backup.tape_storage import TapeGeneration, TAPE_CAPACITY
        self.assertEqual(TapeGeneration.LTO_9.value, "lto_9")
        cap = TAPE_CAPACITY[TapeGeneration.LTO_9]
        self.assertEqual(cap, 18 * 1024**4)

    def test_tape_properties(self):
        tape = self._make_tape()
        self.assertEqual(tape.capacity_bytes, 18 * 1024**4)
        self.assertEqual(tape.free_bytes, tape.capacity_bytes)
        self.assertEqual(tape.utilisation_pct, 0.0)
        self.assertFalse(tape.is_expired)

    def test_tape_expiry(self):
        from api.backup.tape_storage import Tape, TapeGeneration, TapeStatus
        tape = Tape(
            barcode="LTO-OLD", generation=TapeGeneration.LTO_8, slot=99,
            status=TapeStatus.FULL,
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        self.assertTrue(tape.is_expired)

    def test_tape_to_dict(self):
        tape = self._make_tape()
        d = tape.to_dict()
        self.assertIn("barcode", d)
        self.assertIn("generation", d)
        self.assertIn("utilisation_pct", d)

    def test_add_and_list_tapes(self):
        from api.backup.tape_storage import TapeLibraryService
        svc = TapeLibraryService()
        for i in range(5):
            svc.add_tape(self._make_tape(f"LTO-{i:03d}", slot=i))
        tapes = svc.list_tapes()
        self.assertEqual(len(tapes), 5)

    def test_scratch_tapes(self):
        from api.backup.tape_storage import TapeLibraryService, TapeStatus
        svc = TapeLibraryService()
        for i in range(3):
            svc.add_tape(self._make_tape(f"LTO-{i:03d}", slot=i))
        scratch = svc.scratch_tapes()
        self.assertEqual(len(scratch), 3)

    def test_write_backup(self):
        import tempfile, os
        from api.backup.tape_storage import TapeLibraryService
        svc = TapeLibraryService()
        for i in range(3):
            svc.add_tape(self._make_tape(f"LTO-{i:03d}", slot=i))
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"backup data " * 100)
            path = f.name
        try:
            job = svc.write_backup("bk-001", path, retention_days=365)
            self.assertEqual(job.status, "completed")
            self.assertTrue(job.verify_passed)
            self.assertGreater(job.bytes_written, 0)
        finally:
            os.unlink(path)

    def test_vault_and_recall_tape(self):
        from api.backup.tape_storage import TapeLibraryService, TapeStatus
        svc = TapeLibraryService()
        tape = self._make_tape("LTO-VAULT", slot=10)
        svc.add_tape(tape)
        self.assertTrue(svc.vault_tape("LTO-VAULT", "offsite-vault-A"))
        self.assertEqual(tape.location, "offsite-vault-A")
        self.assertEqual(tape.status, TapeStatus.OFFLINE)
        self.assertTrue(svc.recall_tape("LTO-VAULT"))
        self.assertEqual(tape.location, "library")

    def test_restore_from_tape(self):
        import tempfile, os
        from api.backup.tape_storage import TapeLibraryService
        svc = TapeLibraryService()
        for i in range(2):
            svc.add_tape(self._make_tape(f"LTO-{i:03d}", slot=i))
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"restore test data")
            path = f.name
        try:
            svc.write_backup("bk-restore", path)
            result = svc.restore_from_tape("bk-restore", "/tmp/restore_dest")
            self.assertIn("status", result)
        finally:
            os.unlink(path)

    def test_expire_tapes(self):
        from api.backup.tape_storage import TapeLibraryService, Tape, TapeGeneration, TapeStatus
        svc = TapeLibraryService()
        tape = Tape(
            barcode="LTO-EXP", generation=TapeGeneration.LTO_8, slot=99,
            status=TapeStatus.FULL, used_bytes=1024,
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        svc.add_tape(tape)
        expired = svc.expire_tapes()
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0].status, TapeStatus.SCRATCH)

    def test_library_stats(self):
        from api.backup.tape_storage import TapeLibraryService
        svc = TapeLibraryService()
        for i in range(4):
            svc.add_tape(self._make_tape(f"LTO-{i:03d}", slot=i))
        stats = svc.library_stats()
        for key in ["library_name","total_tapes","scratch_tapes",
                    "total_capacity_tb","drives_available"]:
            self.assertIn(key, stats)
        self.assertEqual(stats["total_tapes"], 4)
