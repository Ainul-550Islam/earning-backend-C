"""
Repository Layer — Database Operations for Disaster Recovery System
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from .sa_models import (
    BackupJob, BackupPolicy, BackupSnapshot, StorageLocation,
    RestoreRequest, RestoreVerification, PointInTimeLog,
    FailoverEvent, ReplicationLag, HealthCheckLog,
    IncidentReport, RecoveryDrill, RTO_RPO_Metric,
    DR_AuditTrail, SLA_Monitoring
)
from .enums import BackupStatus, RestoreStatus, FailoverStatus, HealthStatus
from .exceptions import BackupNotFoundException, RestoreNotFoundException, FailoverNotFoundException


class BaseRepository:
    def __init__(self, db: Session):
        self.db = db

    def _commit(self):
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise


# ──────────────────────────────────────────────────────────────────────────────
# BACKUP REPOSITORY
# ──────────────────────────────────────────────────────────────────────────────

class BackupRepository(BaseRepository):

    def create_policy(self, data: dict) -> BackupPolicy:
        policy = BackupPolicy(**data)
        self.db.add(policy)
        self._commit()
        self.db.refresh(policy)
        return policy

    def get_policy(self, policy_id: str) -> BackupPolicy:
        policy = self.db.query(BackupPolicy).filter(
            BackupPolicy.id == policy_id
        ).first()
        if not policy:
            from .exceptions import BackupPolicyNotFoundException
            raise BackupPolicyNotFoundException(policy_id)
        return policy

    def list_policies(self, active_only: bool = True) -> List[BackupPolicy]:
        q = self.db.query(BackupPolicy)
        if active_only:
            q = q.filter(BackupPolicy.is_active == True)
        return q.order_by(BackupPolicy.name).all()

    def update_policy(self, policy_id: str, data: dict) -> BackupPolicy:
        policy = self.get_policy(policy_id)
        for k, v in data.items():
            if v is not None:
                setattr(policy, k, v)
        policy.updated_at = datetime.utcnow()
        self._commit()
        return policy

    def create_job(self, data: dict) -> BackupJob:
        job = BackupJob(**data)
        self.db.add(job)
        self._commit()
        self.db.refresh(job)
        return job

    def get_job(self, job_id: str) -> BackupJob:
        job = self.db.query(BackupJob).filter(BackupJob.id == job_id).first()
        if not job:
            raise BackupNotFoundException(job_id)
        return job

    def list_jobs(
        self,
        status: Optional[BackupStatus] = None,
        policy_id: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        q = self.db.query(BackupJob)
        if status:
            q = q.filter(BackupJob.status == status)
        if policy_id:
            q = q.filter(BackupJob.policy_id == policy_id)
        if from_date:
            q = q.filter(BackupJob.created_at >= from_date)
        if to_date:
            q = q.filter(BackupJob.created_at <= to_date)
        total = q.count()
        items = q.order_by(desc(BackupJob.created_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def update_job_status(
        self,
        job_id: str,
        status: BackupStatus,
        extra: dict = None
    ) -> BackupJob:
        job = self.get_job(job_id)
        job.status = status
        if extra:
            for k, v in extra.items():
                setattr(job, k, v)
        job.updated_at = datetime.utcnow()
        self._commit()
        return job

    def get_latest_successful_job(self, database: str = None) -> Optional[BackupJob]:
        q = self.db.query(BackupJob).filter(BackupJob.status == BackupStatus.COMPLETED)
        if database:
            q = q.filter(BackupJob.job_payload["target_database"].astext == database)
        return q.order_by(desc(BackupJob.completed_at)).first()

    def get_jobs_for_cleanup(self, cutoff_date: datetime) -> List[BackupJob]:
        return self.db.query(BackupJob).filter(
            and_(
                BackupJob.status == BackupStatus.COMPLETED,
                BackupJob.created_at < cutoff_date
            )
        ).all()

    def count_by_status(self) -> Dict[str, int]:
        results = self.db.query(
            BackupJob.status, func.count(BackupJob.id)
        ).group_by(BackupJob.status).all()
        return {status.value: count for status, count in results}

    def create_storage_location(self, data: dict) -> StorageLocation:
        loc = StorageLocation(**data)
        self.db.add(loc)
        self._commit()
        self.db.refresh(loc)
        return loc

    def list_storage_locations(self) -> List[StorageLocation]:
        return self.db.query(StorageLocation).filter(
            StorageLocation.is_active == True
        ).all()

    def get_primary_storage(self) -> Optional[StorageLocation]:
        return self.db.query(StorageLocation).filter(
            and_(StorageLocation.is_primary == True, StorageLocation.is_active == True)
        ).first()


# ──────────────────────────────────────────────────────────────────────────────
# RESTORE REPOSITORY
# ──────────────────────────────────────────────────────────────────────────────

class RestoreRepository(BaseRepository):

    def create_request(self, data: dict) -> RestoreRequest:
        req = RestoreRequest(**data)
        self.db.add(req)
        self._commit()
        self.db.refresh(req)
        return req

    def get_request(self, request_id: str) -> RestoreRequest:
        req = self.db.query(RestoreRequest).filter(
            RestoreRequest.id == request_id
        ).first()
        if not req:
            raise RestoreNotFoundException(request_id)
        return req

    def list_requests(
        self,
        status: Optional[RestoreStatus] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        q = self.db.query(RestoreRequest)
        if status:
            q = q.filter(RestoreRequest.status == status)
        total = q.count()
        items = q.order_by(desc(RestoreRequest.created_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def update_request(self, request_id: str, data: dict) -> RestoreRequest:
        req = self.get_request(request_id)
        for k, v in data.items():
            setattr(req, k, v)
        req.updated_at = datetime.utcnow()
        self._commit()
        return req

    def create_verification(self, data: dict) -> RestoreVerification:
        v = RestoreVerification(**data)
        self.db.add(v)
        self._commit()
        self.db.refresh(v)
        return v

    def get_pitr_windows(self, database: str) -> List[PointInTimeLog]:
        return self.db.query(PointInTimeLog).filter(
            and_(
                PointInTimeLog.database_name == database,
                PointInTimeLog.is_available == True
            )
        ).all()


# ──────────────────────────────────────────────────────────────────────────────
# FAILOVER REPOSITORY
# ──────────────────────────────────────────────────────────────────────────────

class FailoverRepository(BaseRepository):

    def create_event(self, data: dict) -> FailoverEvent:
        event = FailoverEvent(**data)
        self.db.add(event)
        self._commit()
        self.db.refresh(event)
        return event

    def get_event(self, event_id: str) -> FailoverEvent:
        event = self.db.query(FailoverEvent).filter(
            FailoverEvent.id == event_id
        ).first()
        if not event:
            raise FailoverNotFoundException(event_id)
        return event

    def list_events(
        self,
        status: Optional[FailoverStatus] = None,
        from_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        q = self.db.query(FailoverEvent)
        if status:
            q = q.filter(FailoverEvent.status == status)
        if from_date:
            q = q.filter(FailoverEvent.initiated_at >= from_date)
        total = q.count()
        items = q.order_by(desc(FailoverEvent.initiated_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def update_event(self, event_id: str, data: dict) -> FailoverEvent:
        event = self.get_event(event_id)
        for k, v in data.items():
            setattr(event, k, v)
        self._commit()
        return event

    def save_replication_lag(self, data: dict) -> ReplicationLag:
        lag = ReplicationLag(**data)
        self.db.add(lag)
        self._commit()
        return lag

    def get_latest_lag(self, primary: str, replica: str) -> Optional[ReplicationLag]:
        return self.db.query(ReplicationLag).filter(
            and_(
                ReplicationLag.primary_host == primary,
                ReplicationLag.replica_host == replica
            )
        ).order_by(desc(ReplicationLag.measured_at)).first()

    def get_avg_lag_last_hour(self, primary: str, replica: str) -> Optional[float]:
        cutoff = datetime.utcnow() - timedelta(hours=1)
        result = self.db.query(func.avg(ReplicationLag.lag_seconds)).filter(
            and_(
                ReplicationLag.primary_host == primary,
                ReplicationLag.replica_host == replica,
                ReplicationLag.measured_at >= cutoff
            )
        ).scalar()
        return result


# ──────────────────────────────────────────────────────────────────────────────
# MONITORING REPOSITORY
# ──────────────────────────────────────────────────────────────────────────────

class MonitoringRepository(BaseRepository):

    def save_health_check(self, data: dict) -> HealthCheckLog:
        log = HealthCheckLog(**data)
        self.db.add(log)
        self._commit()
        return log

    def get_latest_health(self, component: str) -> Optional[HealthCheckLog]:
        return self.db.query(HealthCheckLog).filter(
            HealthCheckLog.component_name == component
        ).order_by(desc(HealthCheckLog.checked_at)).first()

    def get_all_components_latest(self) -> List[HealthCheckLog]:
        subq = self.db.query(
            HealthCheckLog.component_name,
            func.max(HealthCheckLog.checked_at).label("max_time")
        ).group_by(HealthCheckLog.component_name).subquery()
        return self.db.query(HealthCheckLog).join(
            subq,
            and_(
                HealthCheckLog.component_name == subq.c.component_name,
                HealthCheckLog.checked_at == subq.c.max_time
            )
        ).all()

    def get_uptime_percent(
        self, component: str, from_date: datetime, to_date: datetime
    ) -> float:
        total = self.db.query(func.count(HealthCheckLog.id)).filter(
            and_(
                HealthCheckLog.component_name == component,
                HealthCheckLog.checked_at.between(from_date, to_date)
            )
        ).scalar() or 0
        healthy = self.db.query(func.count(HealthCheckLog.id)).filter(
            and_(
                HealthCheckLog.component_name == component,
                HealthCheckLog.checked_at.between(from_date, to_date),
                HealthCheckLog.status == HealthStatus.HEALTHY
            )
        ).scalar() or 0
        if total == 0:
            return 100.0
        return round((healthy / total) * 100, 4)


# ──────────────────────────────────────────────────────────────────────────────
# INCIDENT REPOSITORY
# ──────────────────────────────────────────────────────────────────────────────

class IncidentRepository(BaseRepository):

    def create(self, data: dict) -> IncidentReport:
        incident = IncidentReport(**data)
        self.db.add(incident)
        self._commit()
        self.db.refresh(incident)
        return incident

    def get(self, incident_id: str) -> IncidentReport:
        from .exceptions import DRBaseException
        incident = self.db.query(IncidentReport).filter(
            IncidentReport.id == incident_id
        ).first()
        if not incident:
            raise DRBaseException(f"Incident {incident_id} not found", "INCIDENT_NOT_FOUND")
        return incident

    def list(self, status=None, severity=None, page=1, page_size=50) -> Dict[str, Any]:
        q = self.db.query(IncidentReport)
        if status:
            q = q.filter(IncidentReport.status == status)
        if severity:
            q = q.filter(IncidentReport.severity == severity)
        total = q.count()
        items = q.order_by(desc(IncidentReport.started_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def update(self, incident_id: str, data: dict) -> IncidentReport:
        incident = self.get(incident_id)
        for k, v in data.items():
            if v is not None:
                setattr(incident, k, v)
        incident.updated_at = datetime.utcnow()
        self._commit()
        return incident

    def save_rto_rpo(self, data: dict) -> RTO_RPO_Metric:
        metric = RTO_RPO_Metric(**data)
        self.db.add(metric)
        self._commit()
        return metric


# ──────────────────────────────────────────────────────────────────────────────
# DRILL REPOSITORY
# ──────────────────────────────────────────────────────────────────────────────

class DrillRepository(BaseRepository):

    def create(self, data: dict) -> RecoveryDrill:
        drill = RecoveryDrill(**data)
        self.db.add(drill)
        self._commit()
        self.db.refresh(drill)
        return drill

    def get(self, drill_id: str) -> RecoveryDrill:
        from .exceptions import DrillNotFoundException
        drill = self.db.query(RecoveryDrill).filter(
            RecoveryDrill.id == drill_id
        ).first()
        if not drill:
            raise DrillNotFoundException(drill_id)
        return drill

    def list(self, status=None, page=1, page_size=50) -> Dict[str, Any]:
        q = self.db.query(RecoveryDrill)
        if status:
            q = q.filter(RecoveryDrill.status == status)
        total = q.count()
        items = q.order_by(desc(RecoveryDrill.scheduled_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def update(self, drill_id: str, data: dict) -> RecoveryDrill:
        drill = self.get(drill_id)
        for k, v in data.items():
            if v is not None:
                setattr(drill, k, v)
        drill.updated_at = datetime.utcnow()
        self._commit()
        return drill


# ──────────────────────────────────────────────────────────────────────────────
# AUDIT REPOSITORY
# ──────────────────────────────────────────────────────────────────────────────

class AuditRepository(BaseRepository):

    def log(self, data: dict) -> DR_AuditTrail:
        trail = DR_AuditTrail(**data)
        self.db.add(trail)
        self._commit()
        return trail

    def list(
        self,
        actor_id: str = None,
        resource_type: str = None,
        resource_id: str = None,
        from_date: datetime = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        q = self.db.query(DR_AuditTrail)
        if actor_id:
            q = q.filter(DR_AuditTrail.actor_id == actor_id)
        if resource_type:
            q = q.filter(DR_AuditTrail.resource_type == resource_type)
        if resource_id:
            q = q.filter(DR_AuditTrail.resource_id == resource_id)
        if from_date:
            q = q.filter(DR_AuditTrail.timestamp >= from_date)
        total = q.count()
        items = q.order_by(desc(DR_AuditTrail.timestamp)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return {"items": items, "total": total, "page": page, "page_size": page_size}
