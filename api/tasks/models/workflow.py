"""
tasks/models/workflow.py
Workflow models: TaskWorkflow, WorkflowStep, WorkflowInstance, WorkflowLog, WorkflowTrigger
"""
import logging
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError

User = get_user_model()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# TaskWorkflow  –  definition / template
# ─────────────────────────────────────────────

class TaskWorkflow(models.Model):
    """
    Defines a multi-step workflow: an ordered sequence of Celery tasks
    that execute in series (or in parallel, per step config).
    Acts as a reusable template; each execution creates a WorkflowInstance.
    """

    class TriggerType(models.TextChoices):
        MANUAL    = 'manual',    'Manual (API / Admin)'
        CRON      = 'cron',      'Scheduled (Cron)'
        EVENT     = 'event',     'Event-Driven'
        WEBHOOK   = 'webhook',   'Webhook'
        CELERY    = 'celery',    'Triggered by Celery Task'

    class OnFailure(models.TextChoices):
        STOP      = 'stop',      'Stop Workflow'
        CONTINUE  = 'continue',  'Continue Next Step'
        ROLLBACK  = 'rollback',  'Execute Rollback Steps'

    # ── Identity ──────────────────────────────
    name        = models.CharField(max_length=200, unique=True, db_index=True)
    description = models.TextField(blank=True, default='')
    version     = models.PositiveSmallIntegerField(default=1)

    # ── Steps ─────────────────────────────────
    # Stored as JSON for a quick overview; canonical data is in WorkflowStep rows.
    steps = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Ordered list of step descriptors. "
            "WorkflowStep FK rows are the canonical source."
        ),
    )

    # ── Control ───────────────────────────────
    is_active    = models.BooleanField(default=True, db_index=True)
    trigger_type = models.CharField(
        max_length=20,
        choices=TriggerType.choices,
        default=TriggerType.MANUAL,
    )
    on_failure   = models.CharField(
        max_length=20,
        choices=OnFailure.choices,
        default=OnFailure.STOP,
    )

    # Global timeout for the whole workflow (seconds)
    timeout_seconds = models.PositiveIntegerField(
        default=3600,
        validators=[MinValueValidator(1)],
    )

    # Input schema (JSONSchema for validation, optional)
    input_schema = models.JSONField(null=True, blank=True)

    # ── Audit ─────────────────────────────────
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_workflows',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Task Workflow'
        verbose_name_plural = 'Task Workflows'
        ordering            = ['name']

    def __str__(self):
        return f"Workflow: {self.name} v{self.version}"

    @property
    def step_count(self) -> int:
        return self.workflow_steps.count()

    def get_ordered_steps(self):
        return self.workflow_steps.order_by('step_number')


# ─────────────────────────────────────────────
# WorkflowStep  –  one task within a workflow
# ─────────────────────────────────────────────

class WorkflowStep(models.Model):
    """
    An individual step (= one Celery task) within a TaskWorkflow.
    Steps execute in ascending step_number order.
    """

    class OnFailure(models.TextChoices):
        STOP      = 'stop',      'Stop Workflow'
        CONTINUE  = 'continue',  'Skip and Continue'
        RETRY     = 'retry',     'Retry This Step'
        ROLLBACK  = 'rollback',  'Trigger Rollback'

    workflow    = models.ForeignKey(
        TaskWorkflow,
        on_delete=models.CASCADE,
        related_name='workflow_steps',
    )
    step_number = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Execution order (ascending). Must be unique per workflow.",
    )

    # Task to execute
    task_name   = models.CharField(
        max_length=255,
        help_text="Dotted Python path to the Celery task",
    )
    task_params = models.JSONField(
        default=dict,
        blank=True,
        help_text="Keyword args for the task. Can reference output of previous steps using {{step_N.output.key}}.",
    )

    # Step label (for logs / admin)
    label       = models.CharField(max_length=200, blank=True, default='')

    # Failure handling for this step
    on_failure  = models.CharField(
        max_length=20,
        choices=OnFailure.choices,
        default=OnFailure.STOP,
    )
    max_retries = models.PositiveSmallIntegerField(default=0)

    # Timeout for this step only
    timeout_seconds = models.PositiveIntegerField(
        default=300,
        validators=[MinValueValidator(1)],
    )

    # If True, don't wait for this step to finish before starting the next
    is_async    = models.BooleanField(
        default=False,
        help_text="Fire-and-forget: continue to next step without waiting for result",
    )

    # Optional condition (Python expression evaluated against workflow context)
    condition   = models.TextField(
        blank=True,
        default='',
        help_text="Python expression; step is skipped if it evaluates to False",
    )

    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Workflow Step'
        verbose_name_plural = 'Workflow Steps'
        unique_together     = [('workflow', 'step_number')]
        ordering            = ['workflow', 'step_number']

    def __str__(self):
        label = self.label or self.task_name
        return f"{self.workflow.name} → Step {self.step_number}: {label}"


# ─────────────────────────────────────────────
# WorkflowInstance  –  one execution of a workflow
# ─────────────────────────────────────────────

class WorkflowInstance(models.Model):
    """
    A single execution (run) of a TaskWorkflow.
    Created when WorkflowService triggers a workflow.
    """

    class Status(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        RUNNING   = 'running',   'Running'
        SUCCESS   = 'success',   'Success'
        FAILED    = 'failed',    'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
        PARTIAL   = 'partial',   'Partial Success'

    workflow = models.ForeignKey(
        TaskWorkflow,
        on_delete=models.CASCADE,
        related_name='instances',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    # Execution context
    input_data   = models.JSONField(default=dict, blank=True, help_text="Input passed to the workflow")
    context_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Shared context accumulates step outputs during execution",
    )

    # Timing
    started_at   = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    # Current step
    current_step = models.PositiveSmallIntegerField(default=0)
    error        = models.TextField(blank=True, default='')

    # Who / what triggered this instance
    triggered_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='triggered_workflow_instances',
    )
    trigger_type = models.CharField(max_length=20, blank=True, default='manual')
    trigger_ref  = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Reference ID of the trigger (e.g. event ID, cron run ID)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Workflow Instance'
        verbose_name_plural = 'Workflow Instances'
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['workflow', 'status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"Instance #{self.pk}: {self.workflow.name} [{self.status}]"

    # ── Helpers ───────────────────────────────

    def start(self) -> None:
        self.status     = self.Status.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at', 'updated_at'])

    def complete(self, success: bool = True, error: str = '') -> None:
        self.status       = self.Status.SUCCESS if success else self.Status.FAILED
        self.completed_at = timezone.now()
        self.error        = error
        self.save(update_fields=['status', 'completed_at', 'error', 'updated_at'])

    def cancel(self, reason: str = '') -> None:
        self.status       = self.Status.CANCELLED
        self.completed_at = timezone.now()
        self.error        = reason
        self.save(update_fields=['status', 'completed_at', 'error', 'updated_at'])

    def set_context(self, key: str, value) -> None:
        self.context_data[key] = value
        self.save(update_fields=['context_data', 'updated_at'])


# ─────────────────────────────────────────────
# WorkflowLog  –  per-step execution log
# ─────────────────────────────────────────────

class WorkflowLog(models.Model):
    """
    Records the result of each step within a WorkflowInstance.
    """

    class Status(models.TextChoices):
        PENDING  = 'pending',  'Pending'
        RUNNING  = 'running',  'Running'
        SUCCESS  = 'success',  'Success'
        FAILED   = 'failed',   'Failed'
        SKIPPED  = 'skipped',  'Skipped (condition false)'
        TIMEOUT  = 'timeout',  'Timed Out'

    instance    = models.ForeignKey(
        WorkflowInstance,
        on_delete=models.CASCADE,
        related_name='logs',
    )
    step_number = models.PositiveSmallIntegerField()
    task_name   = models.CharField(max_length=255)
    status      = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    # Result
    output      = models.JSONField(null=True, blank=True, help_text="Task return value")
    error       = models.TextField(blank=True, default='')
    duration_seconds = models.FloatField(null=True, blank=True)

    # Celery reference
    celery_task_id = models.CharField(max_length=255, blank=True, default='')
    retry_count    = models.PositiveSmallIntegerField(default=0)

    started_at   = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Workflow Log'
        verbose_name_plural = 'Workflow Logs'
        unique_together     = [('instance', 'step_number')]
        ordering            = ['instance', 'step_number']

    def __str__(self):
        return (
            f"WFLog Instance#{self.instance_id} "
            f"Step {self.step_number} [{self.status}]"
        )


# ─────────────────────────────────────────────
# WorkflowTrigger  –  automated trigger config
# ─────────────────────────────────────────────

class WorkflowTrigger(models.Model):
    """
    Configures how a TaskWorkflow is automatically triggered
    (cron schedule, event name, or webhook endpoint).
    """

    class TriggerType(models.TextChoices):
        CRON    = 'cron',    'Cron Schedule'
        EVENT   = 'event',   'Internal Event'
        MANUAL  = 'manual',  'Manual Only'
        WEBHOOK = 'webhook', 'Incoming Webhook'

    workflow     = models.ForeignKey(
        TaskWorkflow,
        on_delete=models.CASCADE,
        related_name='triggers',
    )
    trigger_type = models.CharField(
        max_length=20,
        choices=TriggerType.choices,
        db_index=True,
    )

    # Configuration varies by trigger_type:
    # cron    → {"cron": "0 0 * * *"}
    # event   → {"event_name": "payment.completed"}
    # webhook → {"secret": "...", "allowed_ips": [...]}
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Trigger-type-specific configuration",
    )

    is_active          = models.BooleanField(default=True, db_index=True)
    last_triggered_at  = models.DateTimeField(null=True, blank=True)
    trigger_count      = models.PositiveIntegerField(default=0)

    description = models.TextField(blank=True, default='')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Workflow Trigger'
        verbose_name_plural = 'Workflow Triggers'
        ordering            = ['workflow', 'trigger_type']

    def __str__(self):
        return f"Trigger: {self.workflow.name} [{self.trigger_type}]"

    def record_trigger(self) -> None:
        self.last_triggered_at  = timezone.now()
        self.trigger_count     += 1
        self.save(update_fields=['last_triggered_at', 'trigger_count', 'updated_at'])
