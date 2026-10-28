# api/cms/models_new/workflow.py
"""
Content Approval Workflow — CMS owns this.
Draft → In Review → Approved → Published → Archived
Rule: এক কাজের জন্য একটাই মালিক।
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class WorkflowState(models.Model):
    STATES = [
        ('draft',     'Draft'),
        ('review',    'In Review'),
        ('approved',  'Approved'),
        ('rejected',  'Rejected'),
        ('published', 'Published'),
        ('archived',  'Archived'),
    ]
    uuid         = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    # Generic FK — works with BlogPost, Page, or any content model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id    = models.PositiveIntegerField()
    content_obj  = GenericForeignKey('content_type', 'object_id')

    state        = models.CharField(max_length=20, choices=STATES,
                                    default='draft', db_index=True)
    assigned_to  = models.ForeignKey(settings.AUTH_USER_MODEL,
                                     on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='workflow_assigned')
    created_by   = models.ForeignKey(settings.AUTH_USER_MODEL,
                                     on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='workflow_created')
    note         = models.TextField(blank=True)
    due_date     = models.DateField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Workflow State"
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['state', 'created_at']),
            models.Index(fields=['assigned_to', 'state']),
        ]

    def __str__(self):
        return f"{self.content_type.model}#{self.object_id} → {self.state}"

    def transition(self, new_state: str, by_user, note: str = '') -> 'WorkflowTransition':
        old_state = self.state
        self.state = new_state
        self.note = note
        self.save(update_fields=['state', 'note', 'updated_at'])
        return WorkflowTransition.objects.create(
            workflow_state=self,
            from_state=old_state,
            to_state=new_state,
            transitioned_by=by_user,
            note=note,
        )

    @property
    def can_publish(self) -> bool:
        return self.state == 'approved'

    @property
    def needs_review(self) -> bool:
        return self.state == 'review'


class WorkflowTransition(models.Model):
    """Immutable history of all state transitions."""
    workflow_state  = models.ForeignKey(WorkflowState, on_delete=models.CASCADE,
                                         related_name='transitions')
    from_state      = models.CharField(max_length=20)
    to_state        = models.CharField(max_length=20)
    transitioned_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                         on_delete=models.SET_NULL, null=True,
                                         related_name='workflow_transitions')
    note            = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Workflow Transition"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.from_state} → {self.to_state} by {self.transitioned_by}"


class WorkflowRule(models.Model):
    """Which content types need approval and who approves."""
    content_type  = models.OneToOneField(ContentType, on_delete=models.CASCADE,
                                          related_name='workflow_rule')
    requires_approval = models.BooleanField(default=True)
    approver_group    = models.CharField(max_length=100, blank=True)
    auto_publish      = models.BooleanField(default=False,
                                             help_text="Auto-publish when approved")
    notify_on_submit  = models.BooleanField(default=True)
    notify_on_approve = models.BooleanField(default=True)
    notify_on_reject  = models.BooleanField(default=True)
    is_active         = models.BooleanField(default=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Workflow Rule"

    def __str__(self):
        return f"{self.content_type.model}: {'requires approval' if self.requires_approval else 'no approval needed'}"
