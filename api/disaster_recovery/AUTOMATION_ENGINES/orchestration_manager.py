"""Orchestration Manager — Coordinates multiple DR workflows."""
import logging
from datetime import datetime
logger = logging.getLogger(__name__)

class OrchestrationManager:
    def __init__(self, db_session=None):
        self.db = db_session
        self._active_workflows = {}

    def run_failover_workflow(self, primary: str, secondary: str, actor: str = "auto") -> dict:
        from .workflow_engine import WorkflowEngine, WorkflowStep
        from ..services import FailoverService, MonitoringService
        svc = FailoverService(self.db)
        engine = WorkflowEngine("failover")
        context = {"primary": primary, "secondary": secondary, "actor": actor}
        engine.add_step(WorkflowStep("health_check",
            lambda ctx: MonitoringService(self.db).get_system_health()))
        engine.add_step(WorkflowStep("trigger_failover",
            lambda ctx: svc.trigger_failover(ctx["primary"], ctx["secondary"],
                                             __import__("..enums", fromlist=["FailoverType"]).FailoverType.AUTOMATIC,
                                             "orchestrated", ctx["actor"])))
        return engine.execute(context)

    def run_backup_workflow(self, policy_id: str) -> dict:
        from .workflow_engine import WorkflowEngine, WorkflowStep
        from .auto_backup import AutoBackup
        engine = WorkflowEngine("backup")
        context = {"policy_id": policy_id}
        engine.add_step(WorkflowStep("trigger_backup",
            lambda ctx: AutoBackup.run_for_policy(ctx["policy_id"], self.db)))
        return engine.execute(context)
