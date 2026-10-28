"""
api/support/models/workflow.py
FIXED FILE — TicketWorkflow + AutomationWorkflow models
TicketWorkflow is used by macro_manager.py
"""
from django.db import models
from django.conf import settings


class TicketWorkflow(models.Model):
    """
    Advanced workflow / macro definition.
    Stores multi-step automation as JSON actions.
    Used by macro_manager for one-click agent macros.
    """
    TRIGGER_CHOICES = [
        ('manual',       'Manual (Macro)'),
        ('ticket_created','Ticket Created'),
        ('ticket_updated','Ticket Updated'),
        ('sla_breach',   'SLA Breach'),
        ('idle_24h',     'Idle 24 Hours'),
        ('idle_72h',     'Idle 72 Hours'),
        ('escalated',    'Escalated'),
    ]

    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    trigger     = models.CharField(max_length=50, choices=TRIGGER_CHOICES, default='manual', db_index=True)
    conditions  = models.JSONField(default=list,  help_text='List of condition dicts')
    actions     = models.JSONField(default=list,  help_text='List of action dicts')
    icon        = models.CharField(max_length=10, default='⚡')
    is_active   = models.BooleanField(default=True, db_index=True)
    priority    = models.IntegerField(default=0,  help_text='Lower = runs first')
    stop_on_match = models.BooleanField(default=False)
    run_count   = models.IntegerField(default=0)
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='created_workflows',
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'support'
        db_table  = 'support_ticket_workflow'
        ordering  = ['priority', 'name']
        indexes   = [models.Index(fields=['trigger', 'is_active'])]

    def __str__(self):
        return f'{self.icon} {self.name} [{self.trigger}]'

    def increment_run_count(self):
        TicketWorkflow.objects.filter(pk=self.pk).update(run_count=models.F('run_count') + 1)


class WorkflowExecutionLog(models.Model):
    """Log every workflow execution"""
    workflow    = models.ForeignKey(TicketWorkflow, on_delete=models.CASCADE, related_name='execution_logs')
    ticket      = models.ForeignKey('SupportTicket', on_delete=models.CASCADE, related_name='workflow_logs')
    triggered_by= models.CharField(max_length=100, default='system')
    actions_run = models.JSONField(default=list)
    success     = models.BooleanField(default=True)
    error_msg   = models.TextField(blank=True, default='')
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support'
        db_table  = 'support_workflow_log'
        ordering  = ['-executed_at']

    def __str__(self):
        return f'{self.workflow.name} on {self.ticket.ticket_id}'