"""
Pydantic Schemas for Disaster Recovery System (Request/Response)
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from .enums import (
    BackupType, BackupStatus, RestoreStatus, StorageProvider,
    BackupFrequency, FailoverType, FailoverStatus, AlertSeverity,
    IncidentSeverity, IncidentStatus, DrillStatus, DisasterType,
    HealthStatus, ReplicationMode
)


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)

    @property
    def offset(self):
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int


# ──────────────────────────────────────────────────────────────────────────────
# BACKUP SCHEMAS
# ──────────────────────────────────────────────────────────────────────────────

class BackupPolicyCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    description: Optional[str]
    backup_type: BackupType
    frequency: BackupFrequency
    cron_expression: Optional[str]
    retention_days: int = Field(default=30, ge=1, le=3650)
    storage_provider: StorageProvider
    target_database: Optional[str]
    target_path: Optional[str]
    enable_compression: bool = True
    enable_encryption: bool = True
    max_backup_size_gb: Optional[float]
    notification_on_failure: bool = True
    notification_on_success: bool = False
    extra_config: Dict[str, Any] = {}


class BackupPolicyUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]
    retention_days: Optional[int]
    is_active: Optional[bool]
    notification_on_failure: Optional[bool]
    notification_on_success: Optional[bool]
    extra_config: Optional[Dict[str, Any]]


class BackupPolicyResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    backup_type: BackupType
    frequency: BackupFrequency
    cron_expression: Optional[str]
    retention_days: int
    storage_provider: StorageProvider
    target_database: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class BackupJobCreate(BaseModel):
    policy_id: Optional[str]
    backup_type: BackupType
    storage_provider: Optional[StorageProvider]
    target_database: Optional[str]
    tags: Dict[str, str] = {}


class BackupJobResponse(BaseModel):
    id: str
    policy_id: Optional[str]
    backup_type: BackupType
    status: BackupStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    source_size_bytes: Optional[int]
    compressed_size_bytes: Optional[int]
    encrypted: bool
    checksum: Optional[str]
    storage_path: Optional[str]
    error_message: Optional[str]
    retry_count: int
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class StorageLocationCreate(BaseModel):
    name: str
    provider: StorageProvider
    region: Optional[str]
    bucket_or_container: str
    path_prefix: str = "/"
    credentials_ref: Optional[str]
    is_primary: bool = False


class StorageLocationResponse(BaseModel):
    id: str
    name: str
    provider: StorageProvider
    region: Optional[str]
    bucket_or_container: str
    is_primary: bool
    is_active: bool
    total_capacity_gb: Optional[float]
    used_capacity_gb: float
    created_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────────────────────────────────────
# RESTORE SCHEMAS
# ──────────────────────────────────────────────────────────────────────────────

class RestoreRequestCreate(BaseModel):
    backup_job_id: Optional[str]
    restore_type: str = Field(..., pattern="^(full|partial|table|point_in_time)$")
    target_database: Optional[str]
    target_path: Optional[str]
    point_in_time: Optional[datetime]
    notes: Optional[str]

    @validator("point_in_time", always=True)
    def validate_pitr(cls, v, values):
        if values.get("restore_type") == "point_in_time" and not v:
            raise ValueError("point_in_time required for PITR restore")
        return v


class RestoreRequestResponse(BaseModel):
    id: str
    backup_job_id: Optional[str]
    requested_by: str
    status: RestoreStatus
    restore_type: str
    target_database: Optional[str]
    point_in_time: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    bytes_restored: Optional[int]
    error_message: Optional[str]
    approval_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class RestoreVerificationResponse(BaseModel):
    id: str
    restore_request_id: str
    is_passed: bool
    row_count_match: Optional[bool]
    checksum_match: Optional[bool]
    schema_match: Optional[bool]
    sample_data_verified: Optional[bool]
    verified_at: datetime
    verified_by: Optional[str]
    report: Dict[str, Any]

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────────────────────────────────────
# FAILOVER SCHEMAS
# ──────────────────────────────────────────────────────────────────────────────

class FailoverTriggerRequest(BaseModel):
    failover_type: FailoverType
    primary_node: str
    secondary_node: str
    trigger_reason: str
    force: bool = False


class FailoverEventResponse(BaseModel):
    id: str
    failover_type: FailoverType
    status: FailoverStatus
    primary_node: str
    secondary_node: str
    triggered_by: Optional[str]
    trigger_reason: Optional[str]
    initiated_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    rto_achieved_seconds: Optional[float]
    rpo_achieved_seconds: Optional[float]
    error_message: Optional[str]
    timeline: List[Dict[str, Any]]

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────────────────────────────────────
# INCIDENT SCHEMAS
# ──────────────────────────────────────────────────────────────────────────────

class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=500)
    description: Optional[str]
    severity: IncidentSeverity
    disaster_type: Optional[DisasterType]
    affected_systems: List[str] = []
    started_at: datetime
    assigned_to: Optional[str]


class IncidentUpdate(BaseModel):
    status: Optional[IncidentStatus]
    root_cause: Optional[str]
    resolution_steps: Optional[List[str]]
    post_mortem: Optional[str]
    assigned_to: Optional[str]
    action_items: Optional[List[Dict[str, Any]]]


class IncidentResponse(BaseModel):
    id: str
    title: str
    severity: IncidentSeverity
    status: IncidentStatus
    disaster_type: Optional[DisasterType]
    affected_systems: List[str]
    started_at: datetime
    resolved_at: Optional[datetime]
    duration_minutes: Optional[float]
    assigned_to: Optional[str]
    root_cause: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK SCHEMAS
# ──────────────────────────────────────────────────────────────────────────────

class HealthCheckResponse(BaseModel):
    id: str
    checked_at: datetime
    component_name: str
    component_type: Optional[str]
    status: HealthStatus
    response_time_ms: Optional[float]
    cpu_percent: Optional[float]
    memory_percent: Optional[float]
    disk_percent: Optional[float]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class SystemHealthSummary(BaseModel):
    overall_status: HealthStatus
    components: List[HealthCheckResponse]
    last_checked: datetime
    healthy_count: int
    degraded_count: int
    down_count: int


# ──────────────────────────────────────────────────────────────────────────────
# DRILL SCHEMAS
# ──────────────────────────────────────────────────────────────────────────────

class DrillCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=300)
    description: Optional[str]
    scenario_type: DisasterType
    scheduled_at: datetime
    participants: List[str] = []
    target_rto_seconds: int
    target_rpo_seconds: int
    success_criteria: List[Dict[str, Any]] = []


class DrillResponse(BaseModel):
    id: str
    name: str
    scenario_type: Optional[DisasterType]
    status: DrillStatus
    scheduled_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_minutes: Optional[float]
    target_rto_seconds: Optional[int]
    target_rpo_seconds: Optional[int]
    achieved_rto_seconds: Optional[float]
    achieved_rpo_seconds: Optional[float]
    passed: Optional[bool]
    created_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────────────────────────────────────
# SLA SCHEMAS
# ──────────────────────────────────────────────────────────────────────────────

class SLAMonitoringResponse(BaseModel):
    id: str
    service_name: str
    period_start: datetime
    period_end: datetime
    target_uptime_percent: float
    actual_uptime_percent: Optional[float]
    total_downtime_minutes: float
    incident_count: int
    sla_met: Optional[bool]
    created_at: datetime

    class Config:
        from_attributes = True


class RTO_RPO_Response(BaseModel):
    id: str
    incident_id: Optional[str]
    drill_id: Optional[str]
    measured_at: datetime
    rto_target_seconds: int
    rto_actual_seconds: Optional[float]
    rpo_target_seconds: int
    rpo_actual_seconds: Optional[float]
    rto_met: Optional[bool]
    rpo_met: Optional[bool]

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────────────────────────────────────
# AUDIT SCHEMAS
# ──────────────────────────────────────────────────────────────────────────────

class AuditTrailResponse(BaseModel):
    id: str
    timestamp: datetime
    actor_id: str
    actor_type: str
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    ip_address: Optional[str]
    result: str
    error_message: Optional[str]

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────────────────────────────────────
# REPLICATION SCHEMAS
# ──────────────────────────────────────────────────────────────────────────────

class ReplicationLagResponse(BaseModel):
    id: str
    measured_at: datetime
    primary_host: str
    replica_host: str
    lag_seconds: float
    lag_bytes: Optional[int]
    replication_mode: Optional[ReplicationMode]
    is_healthy: bool

    class Config:
        from_attributes = True
