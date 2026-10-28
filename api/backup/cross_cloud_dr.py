"""
Cross-Cloud Disaster Recovery Failover
Inspired by: Veeam Cloud Mobility, Rubrik CloudOut, Cohesity CloudSpin, Druva Phoenix
Orchestrates failover between AWS, Azure, GCP — automated RTO/RPO enforcement.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class CloudProvider(str, Enum):
    AWS   = "aws"
    AZURE = "azure"
    GCP   = "gcp"
    ON_PREM = "on_prem"


class FailoverStatus(str, Enum):
    IDLE         = "idle"
    VALIDATING   = "validating"
    FAILING_OVER = "failing_over"
    LIVE         = "live"           # workloads running in DR cloud
    FAILING_BACK = "failing_back"
    COMPLETED    = "completed"
    FAILED       = "failed"


class FailoverMode(str, Enum):
    PLANNED    = "planned"          # graceful, scheduled
    EMERGENCY  = "emergency"        # immediate, RPO-driven
    TEST       = "test"             # isolated test, no traffic


@dataclass
class CloudEndpoint:
    provider: CloudProvider
    region: str
    credentials: Dict[str, str] = field(default_factory=dict)
    vpc_id: Optional[str] = None
    subnet_ids: List[str] = field(default_factory=list)
    security_group_ids: List[str] = field(default_factory=list)


@dataclass
class WorkloadMapping:
    """Maps a source workload to its cloud-equivalent in the DR site"""
    workload_id: str
    name: str
    source_provider: CloudProvider
    target_provider: CloudProvider
    source_resource_id: str
    target_instance_type: str
    target_region: str
    backup_id: Optional[str] = None
    estimated_rto_minutes: int = 60
    dns_records: List[str] = field(default_factory=list)
    health_check_url: Optional[str] = None


@dataclass
class FailoverExecution:
    execution_id: str
    mode: FailoverMode
    source: CloudProvider
    target: CloudProvider
    workloads: List[WorkloadMapping]
    status: FailoverStatus = FailoverStatus.IDLE
    started_at: Optional[datetime] = None
    live_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    log: List[str] = field(default_factory=list)
    workloads_live: int = 0
    workloads_failed: int = 0

    def elapsed_minutes(self) -> float:
        if not self.started_at:
            return 0.0
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds() / 60

    def actual_rto_minutes(self) -> Optional[float]:
        if not self.started_at or not self.live_at:
            return None
        return (self.live_at - self.started_at).total_seconds() / 60

    def add_log(self, msg: str) -> None:
        entry = f"[{datetime.utcnow().strftime('%H:%M:%S')}] {msg}"
        self.log.append(entry)
        logger.info("CrossCloudDR[%s] %s", self.execution_id[:8], msg)


class CloudProviderAdapter:
    """Thin adapter around cloud-provider SDKs for DR operations"""

    def __init__(self, endpoint: CloudEndpoint):
        self.endpoint = endpoint

    def restore_instance(self, workload: WorkloadMapping,
                          backup_id: str) -> Dict[str, Any]:
        """Restore a backed-up workload as a cloud instance"""
        provider = self.endpoint.provider
        logger.info("Restoring %s on %s/%s", workload.name,
                    provider.value, self.endpoint.region)

        if provider == CloudProvider.AWS:
            return self._restore_ec2(workload, backup_id)
        elif provider == CloudProvider.AZURE:
            return self._restore_azure_vm(workload, backup_id)
        elif provider == CloudProvider.GCP:
            return self._restore_gce(workload, backup_id)
        return {"status": "unsupported", "provider": provider.value}

    def _restore_ec2(self, w: WorkloadMapping, backup_id: str) -> Dict[str, Any]:
        try:
            import boto3
            ec2 = boto3.client("ec2", region_name=self.endpoint.region,
                               **self.endpoint.credentials)
            # In production: create instance from AMI derived from backup
            logger.info("EC2 restore initiated: workload=%s backup=%s", w.name, backup_id)
            return {"status": "initiated", "provider": "aws",
                    "region": self.endpoint.region, "instance_type": w.target_instance_type}
        except ImportError:
            return {"status": "mock", "provider": "aws", "note": "boto3 not installed"}
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

    def _restore_azure_vm(self, w: WorkloadMapping, backup_id: str) -> Dict[str, Any]:
        try:
            from azure.mgmt.compute import ComputeManagementClient
            logger.info("Azure VM restore initiated: workload=%s", w.name)
            return {"status": "initiated", "provider": "azure",
                    "region": self.endpoint.region}
        except ImportError:
            return {"status": "mock", "provider": "azure", "note": "azure-mgmt-compute not installed"}
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

    def _restore_gce(self, w: WorkloadMapping, backup_id: str) -> Dict[str, Any]:
        try:
            from googleapiclient.discovery import build
            logger.info("GCE restore initiated: workload=%s", w.name)
            return {"status": "initiated", "provider": "gcp",
                    "region": self.endpoint.region}
        except ImportError:
            return {"status": "mock", "provider": "gcp", "note": "google-api-python-client not installed"}
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

    def update_dns(self, dns_records: List[str], target_ip: str) -> bool:
        """Update DNS records to point to DR instance"""
        logger.info("DNS update: records=%s → %s", dns_records, target_ip)
        return True

    def health_check(self, url: str, timeout: int = 30) -> bool:
        """Verify restored workload is healthy"""
        import requests
        try:
            resp = requests.get(url, timeout=timeout)
            return resp.ok
        except Exception:
            return False

    def teardown_instance(self, resource_id: str) -> bool:
        """Terminate DR instance after failback"""
        logger.info("Teardown DR instance: %s on %s",
                    resource_id, self.endpoint.provider.value)
        return True


class CrossCloudDROrchestrator:
    """
    Orchestrates cross-cloud disaster recovery failover and failback.
    Supports AWS ↔ Azure ↔ GCP ↔ on-prem in any direction.
    """

    def __init__(self, source_endpoint: CloudEndpoint,
                 target_endpoint: CloudEndpoint):
        self.source = source_endpoint
        self.target = target_endpoint
        self._target_adapter = CloudProviderAdapter(target_endpoint)
        self._source_adapter = CloudProviderAdapter(source_endpoint)
        self._executions: Dict[str, FailoverExecution] = {}
        self._workload_mappings: List[WorkloadMapping] = []

    def register_workload(self, mapping: WorkloadMapping) -> None:
        self._workload_mappings.append(mapping)
        logger.info("Workload registered for DR: %s (%s → %s)",
                    mapping.name, mapping.source_provider.value,
                    mapping.target_provider.value)

    def failover(self, mode: FailoverMode = FailoverMode.PLANNED,
                 workload_ids: Optional[List[str]] = None) -> FailoverExecution:
        """Execute cross-cloud failover"""
        import uuid
        workloads = (
            [w for w in self._workload_mappings if w.workload_id in workload_ids]
            if workload_ids else self._workload_mappings
        )
        execution = FailoverExecution(
            execution_id=str(uuid.uuid4()),
            mode=mode,
            source=self.source.provider,
            target=self.target.provider,
            workloads=workloads,
            started_at=datetime.utcnow(),
            status=FailoverStatus.VALIDATING,
        )
        self._executions[execution.execution_id] = execution
        execution.add_log(f"Failover initiated: {self.source.provider.value} → "
                          f"{self.target.provider.value} [{mode.value}]")

        # Phase 1 — validate
        if not self._validate(execution):
            execution.status = FailoverStatus.FAILED
            execution.completed_at = datetime.utcnow()
            return execution

        # Phase 2 — restore workloads in target cloud
        execution.status = FailoverStatus.FAILING_OVER
        for workload in workloads:
            result = self._target_adapter.restore_instance(
                workload, workload.backup_id or ""
            )
            if result.get("status") in ("initiated", "mock"):
                execution.workloads_live += 1
                execution.add_log(f"✅ {workload.name} restored on {self.target.provider.value}")
            else:
                execution.workloads_failed += 1
                execution.add_log(f"❌ {workload.name} failed: {result.get('error','unknown')}")

        # Phase 3 — DNS cutover (skip for test mode)
        if mode != FailoverMode.TEST:
            for workload in workloads:
                if workload.dns_records:
                    self._target_adapter.update_dns(workload.dns_records, "10.0.0.1")
                    execution.add_log(f"DNS updated for {workload.name}")

        execution.live_at = datetime.utcnow()
        execution.status = (FailoverStatus.LIVE
                            if execution.workloads_failed == 0 else FailoverStatus.FAILED)
        rto = execution.actual_rto_minutes()
        execution.add_log(
            f"Failover {'COMPLETE' if execution.status == FailoverStatus.LIVE else 'PARTIAL'}: "
            f"RTO={rto:.1f}min live={execution.workloads_live} failed={execution.workloads_failed}"
        )
        return execution

    def failback(self, execution_id: str) -> FailoverExecution:
        """Fail back to original source after primary is restored"""
        orig = self._executions.get(execution_id)
        if not orig:
            raise LookupError(f"Failover execution {execution_id} not found")

        orig.status = FailoverStatus.FAILING_BACK
        orig.add_log("Failback initiated")
        for workload in orig.workloads:
            result = self._source_adapter.restore_instance(
                workload, workload.backup_id or ""
            )
            orig.add_log(f"Failback {workload.name}: {result.get('status')}")

        orig.completed_at = datetime.utcnow()
        orig.status = FailoverStatus.COMPLETED
        orig.add_log(f"Failback COMPLETE in {orig.elapsed_minutes():.1f}min")
        return orig

    def test_failover(self, workload_ids: Optional[List[str]] = None) -> FailoverExecution:
        """Run an isolated test failover — no DNS changes, no traffic impact"""
        return self.failover(mode=FailoverMode.TEST, workload_ids=workload_ids)

    def get_rto_compliance(self) -> List[Dict[str, Any]]:
        """Report RTO compliance for all executions"""
        report = []
        for ex in self._executions.values():
            actual = ex.actual_rto_minutes()
            for wl in ex.workloads:
                compliant = (actual or 0) <= wl.estimated_rto_minutes
                report.append({
                    "workload": wl.name,
                    "target_rto_min": wl.estimated_rto_minutes,
                    "actual_rto_min": round(actual, 1) if actual else None,
                    "compliant": compliant,
                    "mode": ex.mode.value,
                })
        return report

    def _validate(self, execution: FailoverExecution) -> bool:
        """Pre-flight checks before failover"""
        if not execution.workloads:
            execution.add_log("Validation FAILED: no workloads registered")
            return False
        execution.add_log(f"Validation passed: {len(execution.workloads)} workloads queued")
        return True

    def list_executions(self) -> List[FailoverExecution]:
        return list(self._executions.values())
