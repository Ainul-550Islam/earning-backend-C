# api/support/models/automation.py  — WORLD #1
"""Automation engine models: Rule, Condition, Action, Log, CannedResponse."""
from django.db import models
from django.conf import settings


class AutomationRule(models.Model):
    """Trigger → Condition → Action automation rule."""
    TRIGGER_CHOICES = [
        ('ticket_created','Ticket Created'),('ticket_updated','Ticket Updated'),
        ('ticket_status_changed','Status Changed'),('reply_received','Reply Received'),
        ('agent_replied','Agent Replied'),('sla_warning','SLA Warning'),
        ('sla_breach','SLA Breach'),('ticket_idle_1h','Idle 1h'),
        ('ticket_idle_24h','Idle 24h'),('ticket_idle_72h','Idle 72h'),
        ('ticket_escalated','Escalated'),('ticket_resolved','Resolved'),('manual','Manual'),
    ]
    tenant           = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    name             = models.CharField(max_length=200)
    description      = models.TextField(blank=True, default='')
    trigger          = models.CharField(max_length=50, choices=TRIGGER_CHOICES, db_index=True)
    conditions_logic = models.CharField(max_length=10, default='AND', choices=[('AND','AND'),('OR','OR')])
    is_active        = models.BooleanField(default=True, db_index=True)
    priority         = models.IntegerField(default=0)
    stop_on_match    = models.BooleanField(default=False)
    run_count        = models.IntegerField(default=0)
    created_by       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'support'
        ordering  = ['priority', 'name']
        db_table  = 'support_automation_rule'

    def __str__(self):
        return f'{self.name} [trigger={self.trigger}]'


class AutomationCondition(models.Model):
    """A single condition within an automation rule."""
    rule     = models.ForeignKey(AutomationRule, on_delete=models.CASCADE, related_name='conditions')
    field    = models.CharField(max_length=100)
    operator = models.CharField(max_length=30)
    value    = models.TextField()

    class Meta:
        app_label = 'support'
        db_table  = 'support_automation_condition'


class AutomationAction(models.Model):
    """An action to execute when rule matches."""
    rule        = models.ForeignKey(AutomationRule, on_delete=models.CASCADE, related_name='actions')
    action_type = models.CharField(max_length=100)
    value       = models.TextField(blank=True, default='')
    order       = models.IntegerField(default=0)

    class Meta:
        app_label = 'support'
        ordering  = ['order']
        db_table  = 'support_automation_action'


class AutomationLog(models.Model):
    """Log of automation rule executions."""
    rule         = models.ForeignKey(AutomationRule, on_delete=models.CASCADE, related_name='logs')
    ticket       = models.ForeignKey('SupportTicket', on_delete=models.CASCADE, related_name='automation_logs')
    triggered_at = models.DateTimeField(auto_now_add=True)
    actions_taken = models.JSONField(default=list)
    success      = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, default='')

    class Meta:
        app_label = 'support'
        ordering  = ['-triggered_at']
        db_table  = 'support_automation_log'


class CannedResponse(models.Model):
    """Pre-written agent reply for quick use."""
    tenant     = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    shortcut_key = models.CharField(max_length=50, unique=True, help_text='/greeting, /payment')
    title      = models.CharField(max_length=200)
    content    = models.TextField()
    category   = models.CharField(max_length=50, blank=True, default='general')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    usage_count = models.IntegerField(default=0)
    is_active  = models.BooleanField(default=True)
    is_global  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support'
        ordering  = ['shortcut_key']
        db_table  = 'support_canned_response'

    def __str__(self):
        return f'{self.shortcut_key} — {self.title}'