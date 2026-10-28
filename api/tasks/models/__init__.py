"""
api/tasks/models/__init__.py
Centralised model imports.
"""

# ── Legacy core models (models.py থেকে) ──────────────────────
from api.tasks.models_base import (
    MasterTask,
    UserTaskCompletion,
    AdminLedger,
    RateLimitConfig,
    TaskLock,
    ProofSubmission,
    ProofAttachment,
    TaskDispute,
    DisputeEscalation,
    TaskEventLog,
    TaskDependency,
    UserTaskDependencyStatus,
    TaskInventory,
    FraudSignal,
)

# ── New system models ─────────────────────────────────────────
from api.tasks.models.core import TaskResult, ScheduledTask

from api.tasks.models.queue import (
    TaskQueue,
    TaskPriority,
    TaskDeadLetterQueue,
    TaskRetryConfig,
)

from api.tasks.models.monitoring import (
    TaskMonitor,
    TaskAlert,
    TaskPerformanceLog,
    WorkerHealth,
    QueueDepth,
)

from api.tasks.models.workflow import (
    TaskWorkflow,
    WorkflowStep,
    WorkflowInstance,
    WorkflowLog,
    WorkflowTrigger,
)

from api.tasks.models.analytics import (
    TaskInsight,
    TaskThroughput,
    TaskFailureRate,
    TaskCostEstimate,
)

__all__ = [
    # legacy
    "MasterTask", "UserTaskCompletion", "AdminLedger", "RateLimitConfig",
    # core
    "TaskResult", "ScheduledTask",
    # queue
    "TaskQueue", "TaskPriority", "TaskDeadLetterQueue", "TaskRetryConfig",
    # monitoring
    "TaskMonitor", "TaskAlert", "TaskPerformanceLog", "WorkerHealth", "QueueDepth",
    # workflow
    "TaskWorkflow", "WorkflowStep", "WorkflowInstance", "WorkflowLog", "WorkflowTrigger",
    # analytics
    "TaskInsight", "TaskThroughput", "TaskFailureRate", "TaskCostEstimate",
]
