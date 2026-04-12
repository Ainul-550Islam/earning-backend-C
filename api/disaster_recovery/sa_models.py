"""
SQLAlchemy Database Models for Disaster Recovery System.

Import from here — NOT from models.py — whenever you need the SA tables:

    from disaster_recovery.sa_models import BackupJob, BackupPolicy, ...
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    Enum as SAEnum, ForeignKey, BigInteger, Index,
)
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from .enums import (
    BackupType, BackupStatus, RestoreStatus, FailoverStatus,
    StorageProvider, ReplicationMode, HealthStatus, AlertSeverity,
    IncidentSeverity, IncidentStatus, DrillStatus, DisasterType,
    BackupFrequency, ComplianceFramework, FailoverType,
)


class Base(DeclarativeBase):
    pass


def generate_uuid() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Backup ────────────────────────────────────────────────────────────────────

class BackupPolicy(Base, TimestampMixin):
    __tablename__ = "backup_policies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text)
    backup_type = Column(SAEnum(BackupType), nullable=False)
    frequency = Column(SAEnum(BackupFrequency), nullable=False)
    cron_expression = Column(String(100))
    retention_days = Column(Integer, nullable=False, default=30)
    storage_provider = Column(SAEnum(StorageProvider), nullable=False)
    target_database = Column(String(200))
    target_path = Column(String(500))
    enable_compression = Column(Boolean, default=True)
    enable_encryption = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    max_backup_size_gb = Column(Float)
    notification_on_failure = Column(Boolean, default=True)
    notification_on_success = Column(Boolean, default=False)
    extra_config = Column(JSONB, default=dict)

    jobs = relationship("BackupJob", back_populates="policy")


class StorageLocation(Base, TimestampMixin):
    __tablename__ = "storage_locations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False)
    provider = Column(SAEnum(StorageProvider), nullable=False)
    region = Column(String(100))
    bucket_or_container = Column(String(300))
    path_prefix = Column(String(500), default="/")
    credentials_ref = Column(String(200))
    is_primary = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    total_capacity_gb = Column(Float)
    used_capacity_gb = Column(Float, default=0.0)
    extra_config = Column(JSONB, default=dict)

    backups = relationship("BackupJob", back_populates="storage_location")


class BackupJob(Base, TimestampMixin):
    __tablename__ = "backup_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    policy_id = Column(String(36), ForeignKey("backup_policies.id"), nullable=True)
    storage_location_id = Column(String(36), ForeignKey("storage_locations.id"))
    backup_type = Column(SAEnum(BackupType), nullable=False)
    status = Column(SAEnum(BackupStatus), nullable=False, default=BackupStatus.PENDING)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)
    source_size_bytes = Column(BigInteger)
    compressed_size_bytes = Column(BigInteger)
    encrypted = Column(Boolean, default=False)
    checksum = Column(String(128))
    storage_path = Column(String(1000))
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    parent_backup_id = Column(String(36), ForeignKey("backup_jobs.id"))
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime)
    tags = Column(JSONB, default=dict)
    # 'metadata' is reserved on DeclarativeBase — alias via column name
    job_payload = Column("metadata", JSONB, default=dict)

    policy = relationship("BackupPolicy", back_populates="jobs")
    storage_location = relationship("StorageLocation", back_populates="backups")
    restore_requests = relationship("RestoreRequest", back_populates="backup_job")
    snapshots = relationship("BackupSnapshot", back_populates="backup_job")

    __table_args__ = (
        Index("ix_backup_jobs_status", "status"),
        Index("ix_backup_jobs_created", "created_at"),
    )


class BackupSnapshot(Base, TimestampMixin):
    __tablename__ = "backup_snapshots"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    backup_job_id = Column(String(36), ForeignKey("backup_jobs.id"), nullable=False)
    snapshot_time = Column(DateTime, nullable=False)
    source_type = Column(String(50))
    source_name = Column(String(200))
    snapshot_id = Column(String(300))
    size_bytes = Column(BigInteger)
    is_consistent = Column(Boolean, default=True)
    lsn = Column(String(100))
    job_payload = Column("metadata", JSONB, default=dict)

    backup_job = relationship("BackupJob", back_populates="snapshots")


# ── Restore ───────────────────────────────────────────────────────────────────

class RestoreRequest(Base, TimestampMixin):
    __tablename__ = "restore_requests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    backup_job_id = Column(String(36), ForeignKey("backup_jobs.id"), nullable=True)
    requested_by = Column(String(200), nullable=False)
    status = Column(SAEnum(RestoreStatus), nullable=False, default=RestoreStatus.PENDING)
    restore_type = Column(String(50))
    target_database = Column(String(200))
    target_path = Column(String(500))
    point_in_time = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)
    bytes_restored = Column(BigInteger)
    error_message = Column(Text)
    rollback_info = Column(JSONB, default=dict)
    approval_status = Column(String(50), default="pending")
    approved_by = Column(String(200))
    notes = Column(Text)
    job_payload = Column("metadata", JSONB, default=dict)

    backup_job = relationship("BackupJob", back_populates="restore_requests")
    verifications = relationship("RestoreVerification", back_populates="restore_request")

    __table_args__ = (Index("ix_restore_requests_status", "status"),)


class PointInTimeLog(Base, TimestampMixin):
    __tablename__ = "point_in_time_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    database_name = Column(String(200), nullable=False)
    earliest_restore_point = Column(DateTime, nullable=False)
    latest_restore_point = Column(DateTime, nullable=False)
    wal_path = Column(String(500))
    is_available = Column(Boolean, default=True)
    base_backup_id = Column(String(36), ForeignKey("backup_jobs.id"))
    job_payload = Column("metadata", JSONB, default=dict)

    __table_args__ = (Index("ix_pitr_database", "database_name"),)


class RestoreVerification(Base, TimestampMixin):
    __tablename__ = "restore_verifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    restore_request_id = Column(String(36), ForeignKey("restore_requests.id"), nullable=False)
    is_passed = Column(Boolean, nullable=False)
    row_count_match = Column(Boolean)
    checksum_match = Column(Boolean)
    schema_match = Column(Boolean)
    sample_data_verified = Column(Boolean)
    verified_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    verified_by = Column(String(200))
    report = Column(JSONB, default=dict)
    error_details = Column(Text)

    restore_request = relationship("RestoreRequest", back_populates="verifications")


# ── High Availability & Failover ──────────────────────────────────────────────

class HealthCheckLog(Base):
    __tablename__ = "health_check_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    checked_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    component_name = Column(String(200), nullable=False)
    component_type = Column(String(100))
    status = Column(SAEnum(HealthStatus), nullable=False)
    response_time_ms = Column(Float)
    cpu_percent = Column(Float)
    memory_percent = Column(Float)
    disk_percent = Column(Float)
    error_message = Column(Text)
    job_payload = Column("metadata", JSONB, default=dict)

    __table_args__ = (
        Index("ix_health_checks_component", "component_name", "checked_at"),
    )


class FailoverEvent(Base, TimestampMixin):
    __tablename__ = "failover_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    failover_type = Column(SAEnum(FailoverType), nullable=False)
    status = Column(SAEnum(FailoverStatus), nullable=False, default=FailoverStatus.TRIGGERED)
    primary_node = Column(String(300), nullable=False)
    secondary_node = Column(String(300), nullable=False)
    triggered_by = Column(String(200))
    trigger_reason = Column(Text)
    initiated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    dns_switched_at = Column(DateTime)
    connections_restored_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)
    data_loss_seconds = Column(Float)
    rto_achieved_seconds = Column(Float)
    rollback_at = Column(DateTime)
    error_message = Column(Text)
    timeline = Column(JSONB, default=list)
    job_payload = Column("metadata", JSONB, default=dict)

    __table_args__ = (Index("ix_failover_events_status", "status"),)


class ReplicationLag(Base):
    __tablename__ = "replication_lags"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    measured_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    primary_host = Column(String(300), nullable=False)
    replica_host = Column(String(300), nullable=False)
    lag_seconds = Column(Float, nullable=False)
    lag_bytes = Column(BigInteger)
    replication_mode = Column(SAEnum(ReplicationMode))
    is_healthy = Column(Boolean, nullable=False)
    job_payload = Column("metadata", JSONB, default=dict)

    __table_args__ = (
        Index("ix_replication_lag_hosts", "primary_host", "replica_host", "measured_at"),
    )


# ── Incidents & Drills ────────────────────────────────────────────────────────

class IncidentReport(Base, TimestampMixin):
    __tablename__ = "incident_reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    severity = Column(SAEnum(IncidentSeverity), nullable=False)
    status = Column(SAEnum(IncidentStatus), nullable=False, default=IncidentStatus.OPEN)
    disaster_type = Column(SAEnum(DisasterType))
    affected_systems = Column(JSONB, default=list)
    started_at = Column(DateTime, nullable=False)
    detected_at = Column(DateTime)
    acknowledged_at = Column(DateTime)
    resolved_at = Column(DateTime)
    closed_at = Column(DateTime)
    duration_minutes = Column(Float)
    impact_description = Column(Text)
    root_cause = Column(Text)
    resolution_steps = Column(JSONB, default=list)
    post_mortem = Column(Text)
    assigned_to = Column(String(200))
    reported_by = Column(String(200))
    users_affected = Column(Integer, default=0)
    revenue_impact_usd = Column(Float)
    action_items = Column(JSONB, default=list)
    tags = Column(JSONB, default=list)
    failover_event_id = Column(String(36), ForeignKey("failover_events.id"))

    rto_rpo_metrics = relationship("RTO_RPO_Metric", back_populates="incident")


class RecoveryDrill(Base, TimestampMixin):
    __tablename__ = "recovery_drills"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(300), nullable=False)
    description = Column(Text)
    scenario_type = Column(SAEnum(DisasterType))
    status = Column(SAEnum(DrillStatus), nullable=False, default=DrillStatus.SCHEDULED)
    scheduled_at = Column(DateTime, nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_minutes = Column(Float)
    planned_by = Column(String(200))
    executed_by = Column(String(200))
    participants = Column(JSONB, default=list)
    target_rto_seconds = Column(Integer)
    target_rpo_seconds = Column(Integer)
    achieved_rto_seconds = Column(Float)
    achieved_rpo_seconds = Column(Float)
    success_criteria = Column(JSONB, default=list)
    results = Column(JSONB, default=dict)
    lessons_learned = Column(Text)
    action_items = Column(JSONB, default=list)
    passed = Column(Boolean)
    report_url = Column(String(500))


class RTO_RPO_Metric(Base, TimestampMixin):
    __tablename__ = "rto_rpo_metrics"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    incident_id = Column(String(36), ForeignKey("incident_reports.id"))
    drill_id = Column(String(36), ForeignKey("recovery_drills.id"))
    measured_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    rto_target_seconds = Column(Integer, nullable=False)
    rto_actual_seconds = Column(Float)
    rpo_target_seconds = Column(Integer, nullable=False)
    rpo_actual_seconds = Column(Float)
    rto_met = Column(Boolean)
    rpo_met = Column(Boolean)
    data_loss_description = Column(Text)
    notes = Column(Text)

    incident = relationship("IncidentReport", back_populates="rto_rpo_metrics")


# ── Audit & Compliance ────────────────────────────────────────────────────────

class DR_AuditTrail(Base):
    __tablename__ = "dr_audit_trails"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    actor_id = Column(String(200), nullable=False)
    actor_type = Column(String(50), default="user")
    action = Column(String(200), nullable=False)
    resource_type = Column(String(100))
    resource_id = Column(String(200))
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    result = Column(String(50), default="success")
    error_message = Column(Text)
    request_id = Column(String(100))
    session_id = Column(String(200))

    __table_args__ = (
        Index("ix_audit_actor", "actor_id", "timestamp"),
        Index("ix_audit_resource", "resource_type", "resource_id"),
    )


class SLA_Monitoring(Base, TimestampMixin):
    __tablename__ = "sla_monitoring"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    service_name = Column(String(200), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    target_uptime_percent = Column(Float, nullable=False, default=99.9)
    actual_uptime_percent = Column(Float)
    total_downtime_minutes = Column(Float, default=0.0)
    incident_count = Column(Integer, default=0)
    sla_met = Column(Boolean)
    credits_due = Column(Float, default=0.0)
    details = Column(JSONB, default=dict)

    __table_args__ = (
        Index("ix_sla_service_period", "service_name", "period_start"),
    )
