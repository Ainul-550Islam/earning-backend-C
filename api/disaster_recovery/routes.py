"""
FastAPI Routes for Disaster Recovery System
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .dependencies import get_db, get_current_user
from .services import (
    BackupService, RestoreService, FailoverService,
    MonitoringService, IncidentService, DrillService
)
from .schemas import (
    BackupPolicyCreate, BackupPolicyUpdate, BackupPolicyResponse,
    BackupJobCreate, BackupJobResponse,
    StorageLocationCreate, StorageLocationResponse,
    RestoreRequestCreate, RestoreRequestResponse, RestoreVerificationResponse,
    FailoverTriggerRequest, FailoverEventResponse,
    IncidentCreate, IncidentUpdate, IncidentResponse,
    DrillCreate, DrillResponse,
    HealthCheckResponse, SystemHealthSummary,
    SLAMonitoringResponse, RTO_RPO_Response,
    AuditTrailResponse, PaginatedResponse
)
from .enums import BackupStatus, RestoreStatus, FailoverStatus, IncidentSeverity
from .exceptions import EXCEPTION_STATUS_MAP, DRBaseException

router = APIRouter(prefix="/api/v1/dr", tags=["Disaster Recovery"])


def handle_exception(exc: DRBaseException):
    status_code = EXCEPTION_STATUS_MAP.get(type(exc), 500)
    raise HTTPException(status_code=status_code, detail=exc.to_dict())


# ══════════════════════════════════════════════════════════════════════════════
# BACKUP ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

backup_router = APIRouter(prefix="/backups", tags=["Backups"])


@backup_router.post("/policies", response_model=BackupPolicyResponse, status_code=201)
def create_backup_policy(
    payload: BackupPolicyCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Create a new backup policy."""
    try:
        svc = BackupService(db)
        return svc.create_policy(payload.dict(), actor_id=user.id)
    except DRBaseException as e:
        handle_exception(e)


@backup_router.get("/policies", response_model=PaginatedResponse)
def list_backup_policies(
    active_only: bool = True,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """List all backup policies."""
    svc = BackupService(db)
    policies = svc.repo.list_policies(active_only=active_only)
    return PaginatedResponse(
        items=[BackupPolicyResponse.from_orm(p) for p in policies],
        total=len(policies), page=1, page_size=len(policies),
        pages=1
    )


@backup_router.get("/policies/{policy_id}", response_model=BackupPolicyResponse)
def get_backup_policy(
    policy_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Get a specific backup policy."""
    try:
        svc = BackupService(db)
        return svc.repo.get_policy(policy_id)
    except DRBaseException as e:
        handle_exception(e)


@backup_router.patch("/policies/{policy_id}", response_model=BackupPolicyResponse)
def update_backup_policy(
    policy_id: str,
    payload: BackupPolicyUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Update a backup policy."""
    try:
        svc = BackupService(db)
        return svc.repo.update_policy(policy_id, payload.dict(exclude_none=True))
    except DRBaseException as e:
        handle_exception(e)


@backup_router.post("/trigger", response_model=BackupJobResponse, status_code=202)
def trigger_backup(
    payload: BackupJobCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Manually trigger a backup job."""
    try:
        svc = BackupService(db)
        return svc.trigger_backup(
            policy_id=payload.policy_id,
            backup_type=payload.backup_type,
            actor_id=user.id
        )
    except DRBaseException as e:
        handle_exception(e)


@backup_router.get("/jobs", response_model=PaginatedResponse)
def list_backup_jobs(
    status: Optional[BackupStatus] = None,
    policy_id: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """List backup jobs with filters."""
    svc = BackupService(db)
    result = svc.repo.list_jobs(
        status=status, policy_id=policy_id,
        from_date=from_date, to_date=to_date,
        page=page, page_size=page_size
    )
    return PaginatedResponse(
        items=[BackupJobResponse.from_orm(j) for j in result["items"]],
        total=result["total"], page=page,
        page_size=page_size,
        pages=(result["total"] + page_size - 1) // page_size
    )


@backup_router.get("/jobs/{job_id}", response_model=BackupJobResponse)
def get_backup_job(
    job_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Get a specific backup job."""
    try:
        svc = BackupService(db)
        return svc.repo.get_job(job_id)
    except DRBaseException as e:
        handle_exception(e)


@backup_router.post("/jobs/{job_id}/verify")
def verify_backup(
    job_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Verify backup integrity."""
    svc = BackupService(db)
    result = svc.verify_backup(job_id)
    return {"job_id": job_id, "verified": result}


@backup_router.get("/stats")
def get_backup_stats(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Get backup statistics summary."""
    svc = BackupService(db)
    return svc.get_backup_stats()


@backup_router.post("/policies/{policy_id}/cleanup")
def cleanup_old_backups(
    policy_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Clean up expired backups for a policy."""
    svc = BackupService(db)
    count = svc.cleanup_old_backups(policy_id)
    return {"policy_id": policy_id, "cleaned_up": count}


# Storage Locations
@backup_router.post("/storage", response_model=StorageLocationResponse, status_code=201)
def create_storage_location(
    payload: StorageLocationCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    svc = BackupService(db)
    return svc.repo.create_storage_location(payload.dict())


@backup_router.get("/storage", response_model=list)
def list_storage_locations(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    svc = BackupService(db)
    return [StorageLocationResponse.from_orm(s) for s in svc.repo.list_storage_locations()]


router.include_router(backup_router)


# ══════════════════════════════════════════════════════════════════════════════
# RESTORE ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

restore_router = APIRouter(prefix="/restores", tags=["Restores"])


@restore_router.post("", response_model=RestoreRequestResponse, status_code=202)
def request_restore(
    payload: RestoreRequestCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Request a data restore operation."""
    try:
        svc = RestoreService(db)
        return svc.request_restore(payload.dict(), requested_by=user.id)
    except DRBaseException as e:
        handle_exception(e)


@restore_router.post("/{request_id}/approve")
def approve_restore(
    request_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Approve a pending restore request."""
    svc = RestoreService(db)
    return svc.approve_restore(request_id, approver=user.id)


@restore_router.post("/{request_id}/execute", status_code=202)
def execute_restore(
    request_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Execute an approved restore."""
    try:
        svc = RestoreService(db)
        return svc.execute_restore(request_id)
    except DRBaseException as e:
        handle_exception(e)


@restore_router.get("/{request_id}", response_model=RestoreRequestResponse)
def get_restore_request(
    request_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Get restore request details."""
    try:
        svc = RestoreService(db)
        return svc.repo.get_request(request_id)
    except DRBaseException as e:
        handle_exception(e)


@restore_router.get("/{request_id}/verification", response_model=RestoreVerificationResponse)
def get_restore_verification(
    request_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Get verification report for a completed restore."""
    svc = RestoreService(db)
    # Get latest verification for this request
    verifications = svc.repo.db.query(
        __import__("disaster_recovery.models", fromlist=["RestoreVerification"]).RestoreVerification
    ).filter_by(restore_request_id=request_id).all()
    if not verifications:
        raise HTTPException(status_code=404, detail="No verification found")
    return RestoreVerificationResponse.from_orm(verifications[-1])


@restore_router.get("/pitr/{database}/windows")
def get_pitr_windows(
    database: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Get available point-in-time restore windows for a database."""
    svc = RestoreService(db)
    return svc.get_available_restore_points(database)


router.include_router(restore_router)


# ══════════════════════════════════════════════════════════════════════════════
# FAILOVER ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

failover_router = APIRouter(prefix="/failover", tags=["Failover"])


@failover_router.post("/trigger", response_model=FailoverEventResponse, status_code=202)
def trigger_failover(
    payload: FailoverTriggerRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Manually trigger a failover."""
    try:
        svc = FailoverService(db)
        return svc.trigger_failover(
            primary_node=payload.primary_node,
            secondary_node=payload.secondary_node,
            failover_type=payload.failover_type,
            reason=payload.trigger_reason,
            triggered_by=user.id
        )
    except DRBaseException as e:
        handle_exception(e)


@failover_router.get("/events", response_model=PaginatedResponse)
def list_failover_events(
    status: Optional[FailoverStatus] = None,
    from_date: Optional[datetime] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """List failover events."""
    svc = FailoverService(db)
    result = svc.repo.list_events(status=status, from_date=from_date, page=page, page_size=page_size)
    return PaginatedResponse(
        items=[FailoverEventResponse.from_orm(e) for e in result["items"]],
        total=result["total"], page=page, page_size=page_size,
        pages=(result["total"] + page_size - 1) // page_size
    )


@failover_router.get("/events/{event_id}", response_model=FailoverEventResponse)
def get_failover_event(
    event_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Get a specific failover event."""
    try:
        svc = FailoverService(db)
        return svc.repo.get_event(event_id)
    except DRBaseException as e:
        handle_exception(e)


@failover_router.get("/replication/lag")
def get_replication_lag(
    primary: str = Query(...),
    replica: str = Query(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Get current replication lag between nodes."""
    svc = FailoverService(db)
    lag = svc.repo.get_latest_lag(primary, replica)
    if not lag:
        raise HTTPException(status_code=404, detail="No replication lag data found")
    return lag


router.include_router(failover_router)


# ══════════════════════════════════════════════════════════════════════════════
# MONITORING ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

monitoring_router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@monitoring_router.get("/health", response_model=SystemHealthSummary)
def system_health(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Get overall system health summary."""
    svc = MonitoringService(db)
    return svc.get_system_health()


@monitoring_router.get("/health/{component}", response_model=HealthCheckResponse)
def component_health(
    component: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Get health status of a specific component."""
    svc = MonitoringService(db)
    health = svc.repo.get_latest_health(component)
    if not health:
        raise HTTPException(status_code=404, detail=f"No health data for {component}")
    return HealthCheckResponse.from_orm(health)


@monitoring_router.get("/uptime/{component}")
def component_uptime(
    component: str,
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Get uptime percentage for a component over a period."""
    svc = MonitoringService(db)
    uptime = svc.get_uptime(component, days=days)
    return {"component": component, "days": days, "uptime_percent": uptime}


router.include_router(monitoring_router)


# ══════════════════════════════════════════════════════════════════════════════
# INCIDENT ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

incident_router = APIRouter(prefix="/incidents", tags=["Incidents"])


@incident_router.post("", response_model=IncidentResponse, status_code=201)
def create_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Create a new incident report."""
    svc = IncidentService(db)
    return svc.create_incident(payload.dict(), reporter=user.id)


@incident_router.get("", response_model=PaginatedResponse)
def list_incidents(
    status=None,
    severity: Optional[IncidentSeverity] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """List incidents."""
    svc = IncidentService(db)
    result = svc.repo.list(status=status, severity=severity, page=page, page_size=page_size)
    return PaginatedResponse(
        items=[IncidentResponse.from_orm(i) for i in result["items"]],
        total=result["total"], page=page, page_size=page_size,
        pages=(result["total"] + page_size - 1) // page_size
    )


@incident_router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Get a specific incident."""
    try:
        svc = IncidentService(db)
        return svc.repo.get(incident_id)
    except DRBaseException as e:
        handle_exception(e)


@incident_router.patch("/{incident_id}", response_model=IncidentResponse)
def update_incident(
    incident_id: str,
    payload: IncidentUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Update an incident."""
    svc = IncidentService(db)
    return svc.update_incident(incident_id, payload.dict(exclude_none=True), actor=user.id)


@incident_router.post("/{incident_id}/resolve")
def resolve_incident(
    incident_id: str,
    root_cause: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Resolve an incident."""
    svc = IncidentService(db)
    return svc.resolve_incident(incident_id, root_cause=root_cause, actor=user.id)


router.include_router(incident_router)


# ══════════════════════════════════════════════════════════════════════════════
# DR DRILL ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

drill_router = APIRouter(prefix="/drills", tags=["DR Drills"])


@drill_router.post("", response_model=DrillResponse, status_code=201)
def schedule_drill(
    payload: DrillCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Schedule a new DR drill."""
    svc = DrillService(db)
    return svc.schedule_drill(payload.dict(), planned_by=user.id)


@drill_router.get("", response_model=PaginatedResponse)
def list_drills(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """List all DR drills."""
    svc = DrillService(db)
    result = svc.repo.list(page=page, page_size=page_size)
    return PaginatedResponse(
        items=[DrillResponse.from_orm(d) for d in result["items"]],
        total=result["total"], page=page, page_size=page_size,
        pages=(result["total"] + page_size - 1) // page_size
    )


@drill_router.get("/{drill_id}", response_model=DrillResponse)
def get_drill(
    drill_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Get a specific DR drill."""
    try:
        svc = DrillService(db)
        return svc.repo.get(drill_id)
    except DRBaseException as e:
        handle_exception(e)


@drill_router.post("/{drill_id}/start")
def start_drill(
    drill_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Start a scheduled DR drill."""
    svc = DrillService(db)
    return svc.start_drill(drill_id, executor=user.id)


router.include_router(drill_router)
