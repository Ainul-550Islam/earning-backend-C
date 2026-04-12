"""
Enums for Disaster Recovery System
"""
from enum import Enum


class BackupType(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    HOT = "hot"
    COLD = "cold"
    SNAPSHOT = "snapshot"


class BackupStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    VERIFYING = "verifying"
    VERIFIED = "verified"


class RestoreStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    VERIFYING = "verifying"


class FailoverStatus(str, Enum):
    STANDBY = "standby"
    TRIGGERED = "triggered"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class FailoverType(str, Enum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    PLANNED = "planned"
    EMERGENCY = "emergency"


class StorageProvider(str, Enum):
    AWS_S3 = "aws_s3"
    AWS_GLACIER = "aws_glacier"
    AZURE_BLOB = "azure_blob"
    GCP = "gcp"
    LOCAL = "local"
    NAS = "nas"
    SAN = "san"
    TAPE = "tape"


class ReplicationMode(str, Enum):
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    SEMI_SYNCHRONOUS = "semi_synchronous"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    DOWN = "down"
    UNKNOWN = "unknown"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class IncidentSeverity(str, Enum):
    SEV1 = "sev1"  # Complete outage
    SEV2 = "sev2"  # Major impact
    SEV3 = "sev3"  # Minor impact
    SEV4 = "sev4"  # Informational


class IncidentStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    CLOSED = "closed"


class DrillStatus(str, Enum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ComplianceFramework(str, Enum):
    GDPR = "gdpr"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    SOC2 = "soc2"
    ISO27001 = "iso27001"


class DisasterType(str, Enum):
    NATURAL_DISASTER = "natural_disaster"
    CYBER_ATTACK = "cyber_attack"
    HARDWARE_FAILURE = "hardware_failure"
    SOFTWARE_FAILURE = "software_failure"
    NETWORK_OUTAGE = "network_outage"
    POWER_OUTAGE = "power_outage"
    DATA_CORRUPTION = "data_corruption"
    ACCIDENTAL_DELETION = "accidental_deletion"
    SECURITY_BREACH = "security_breach"
    REGION_OUTAGE = "region_outage"
    CASCADE_FAILURE = "cascade_failure"


class ClusterMode(str, Enum):
    ACTIVE_ACTIVE = "active_active"
    ACTIVE_PASSIVE = "active_passive"


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    OPSGENIE = "opsgenie"
    SMS = "sms"
    WEBHOOK = "webhook"
    TEAMS = "teams"


class BackupFrequency(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"
