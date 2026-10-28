"""
Disaster Recovery Orchestration
Inspired by: Veeam CDP/Replication, Commvault Cleanroom Recovery, Cohesity recovery orchestration
Provides RPO/RTO management, DR plan execution, and failover orchestration.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class DRStatus(str, Enum):
    IDLE        = "idle"
    TESTING     = "testing"
    FAILING_OVER= "failing_over"
    FAILED_OVER = "failed_over"
    FAILING_BACK= "failing_back"
    COMPLETED   = "completed"
    FAILED      = "failed"


class RecoveryType(str, Enum):
    FULL_SITE        = "full_site"
    PARTIAL          = "partial"
    APPLICATION      = "application"
    DATABASE         = "database"
    CLEANROOM        = "cleanroom"    # Commvault-style isolated recovery
    INSTANT          = "instant"      # Veeam instant recovery


class RPOViolationSeverity(str, Enum):
    NONE     = "none"
    WARNING  = "warning"   # 80–100% of RPO window used
    BREACH   = "breach"    # RPO exceeded


@dataclass
class RecoveryObjective:
    """RPO and RTO targets for a workload"""
    workload_name: str
    rpo_minutes: int        # Recovery Point Objective
    rto_minutes: int        # Recovery Time Objective
    priority: int = 5       # 1 = highest, 10 = lowest

    def check_rpo(self, last_backup_at: datetime) -> RPOViolationSeverity:
        age_minutes = (datetime.utcnow() - last_backup_at).total_seconds() / 60
        if age_minutes > self.rpo_minutes:
            return RPOViolationSeverity.BREACH
        if age_minutes > self.rpo_minutes * 0.8:
            return RPOViolationSeverity.WARNING
        return RPOViolationSeverity.NONE


@dataclass
class DRStep:
    """A single step in a DR runbook"""
    step_id: str
    name: str
    action: str                         # e.g. "start_vm", "run_script", "notify_team"
    params: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 300
    retry_on_failure: bool = True
    max_retries: int = 2
    depends_on: List[str] = field(default_factory=list)   # step_ids

    # Runtime
    status: str = "pending"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class DRPlan:
    """Complete disaster recovery plan / runbook"""
    plan_id: str
    name: str
    recovery_type: RecoveryType
    objectives: List[RecoveryObjective]
    steps: List[DRStep]
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_tested_at: Optional[datetime] = None
    test_passed: Optional[bool] = None

    @property
    def is_tested(self) -> bool:
        if not self.last_tested_at:
            return False
        return (datetime.utcnow() - self.last_tested_at).days <= 30

    @property
    def highest_priority_objective(self) -> Optional[RecoveryObjective]:
        return min(self.objectives, key=lambda o: o.priority) if self.objectives else None


@dataclass
class DRExecution:
    """Tracks a live DR plan execution"""
    execution_id: str
    plan: DRPlan
    status: DRStatus = DRStatus.IDLE
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    is_test: bool = False
    steps_completed: int = 0
    steps_failed: int = 0
    log: List[str] = field(default_factory=list)

    def elapsed_minutes(self) -> float:
        if not self.started_at:
            return 0.0
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds() / 60

    def add_log(self, message: str) -> None:
        entry = f"[{datetime.utcnow().isoformat()}] {message}"
        self.log.append(entry)
        logger.info("DR[%s] %s", self.execution_id[:8], message)


class DROrchestrator:
    """
    Orchestrates disaster recovery plan execution.
    Handles step ordering, retries, timeouts, and status tracking.
    """

    def __init__(self, action_handler: Optional[Callable] = None):
        self._plans: Dict[str, DRPlan] = {}
        self._executions: Dict[str, DRExecution] = {}
        self._action_handler = action_handler or self._default_action_handler

    def register_plan(self, plan: DRPlan) -> None:
        self._plans[plan.plan_id] = plan
        logger.info("DR plan registered: %s (%s)", plan.name, plan.plan_id)

    def get_plan(self, plan_id: str) -> Optional[DRPlan]:
        return self._plans.get(plan_id)

    def list_plans(self) -> List[DRPlan]:
        return list(self._plans.values())

    def execute_plan(self, plan_id: str, is_test: bool = False) -> DRExecution:
        plan = self._plans.get(plan_id)
        if not plan:
            raise LookupError(f"DR plan {plan_id} not found")

        import uuid
        execution = DRExecution(
            execution_id=str(uuid.uuid4()),
            plan=plan,
            is_test=is_test,
            started_at=datetime.utcnow(),
            status=DRStatus.TESTING if is_test else DRStatus.FAILING_OVER,
        )
        self._executions[execution.execution_id] = execution
        execution.add_log(f"{'TEST ' if is_test else ''}DR execution started for plan: {plan.name}")

        ordered_steps = self._resolve_step_order(plan.steps)
        all_passed = True

        for step in ordered_steps:
            success = self._execute_step(step, execution)
            if success:
                execution.steps_completed += 1
            else:
                execution.steps_failed += 1
                all_passed = False
                if not step.retry_on_failure:
                    execution.add_log(f"Critical step {step.name} failed — aborting")
                    break

        execution.completed_at = datetime.utcnow()
        execution.status = DRStatus.COMPLETED if all_passed else DRStatus.FAILED

        if is_test:
            plan.last_tested_at = datetime.utcnow()
            plan.test_passed = all_passed

        execution.add_log(
            f"DR execution {'COMPLETED' if all_passed else 'FAILED'} "
            f"in {execution.elapsed_minutes():.1f} min"
        )
        return execution

    def test_plan(self, plan_id: str) -> DRExecution:
        """Run DR plan in test mode (dry-run in isolated environment)"""
        return self.execute_plan(plan_id, is_test=True)

    def check_rpo_compliance(self) -> List[Dict[str, Any]]:
        """Check RPO compliance across all registered plan objectives"""
        violations = []
        from api.backup.repositories import BackupRepository
        repo = BackupRepository()
        for plan in self._plans.values():
            for obj in plan.objectives:
                recent = repo.get_recent(days=1)
                last_backup = recent.order_by("-created_at").first()
                last_at = last_backup.created_at if last_backup else datetime.min
                severity = obj.check_rpo(last_at)
                if severity != RPOViolationSeverity.NONE:
                    violations.append({
                        "plan": plan.name,
                        "workload": obj.workload_name,
                        "severity": severity.value,
                        "rpo_minutes": obj.rpo_minutes,
                        "last_backup_at": last_at.isoformat(),
                    })
        return violations

    def _resolve_step_order(self, steps: List[DRStep]) -> List[DRStep]:
        """Topological sort respecting depends_on"""
        step_map = {s.step_id: s for s in steps}
        ordered: List[DRStep] = []
        visited: set = set()

        def visit(step_id: str):
            if step_id in visited:
                return
            visited.add(step_id)
            step = step_map.get(step_id)
            if step:
                for dep in step.depends_on:
                    visit(dep)
                ordered.append(step)

        for s in steps:
            visit(s.step_id)
        return ordered

    def _execute_step(self, step: DRStep, execution: DRExecution) -> bool:
        step.started_at = datetime.utcnow()
        step.status = "running"
        execution.add_log(f"Step [{step.step_id}] {step.name} — starting")

        retries = 0
        while retries <= step.max_retries:
            try:
                self._action_handler(step.action, step.params, execution.is_test)
                step.status = "completed"
                step.completed_at = datetime.utcnow()
                execution.add_log(f"Step [{step.step_id}] {step.name} — OK")
                return True
            except Exception as exc:
                retries += 1
                step.error = str(exc)
                if retries <= step.max_retries:
                    execution.add_log(f"Step [{step.step_id}] retry {retries}: {exc}")
                else:
                    step.status = "failed"
                    execution.add_log(f"Step [{step.step_id}] FAILED: {exc}")
                    return False
        return False

    @staticmethod
    def _default_action_handler(action: str, params: Dict, is_test: bool) -> None:
        logger.info("DR action: %s params=%s test=%s", action, params, is_test)
        # In production, dispatch to: VM start, script runner, notification, etc.


class CleanroomRecovery:
    """
    Isolated cleanroom recovery environment (Commvault-style).
    Restores backups into a quarantined network segment for forensic analysis
    or safe recovery after ransomware.
    """

    def __init__(self):
        self._active_rooms: Dict[str, Dict[str, Any]] = {}

    def create_room(self, name: str, backup_ids: List[str]) -> str:
        import uuid
        room_id = str(uuid.uuid4())
        self._active_rooms[room_id] = {
            "name": name,
            "backup_ids": backup_ids,
            "created_at": datetime.utcnow(),
            "status": "provisioning",
            "network": f"10.254.{len(self._active_rooms)}.0/24",
        }
        logger.info("Cleanroom created: %s (%s)", name, room_id)
        return room_id

    def get_room(self, room_id: str) -> Optional[Dict[str, Any]]:
        return self._active_rooms.get(room_id)

    def teardown_room(self, room_id: str) -> bool:
        if room_id in self._active_rooms:
            del self._active_rooms[room_id]
            logger.info("Cleanroom %s torn down", room_id)
            return True
        return False
