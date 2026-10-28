# api/support/models/sla.py  — WORLD #1
"""SLA models: SLAPolicy, SLABreach, BusinessHours, Holiday."""
from django.db import models
from django.conf import settings


class SLAPolicy(models.Model):
    """SLA configuration per priority level."""
    tenant               = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    name                 = models.CharField(max_length=100)
    priority_level       = models.CharField(max_length=20, default='medium')
    first_response_hours = models.IntegerField(default=8)
    resolution_hours     = models.IntegerField(default=48)
    business_hours_only  = models.BooleanField(default=True)
    is_active            = models.BooleanField(default=True, db_index=True)
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label       = 'support'
        unique_together = [['tenant', 'priority_level']]
        db_table        = 'support_sla_policy'

    def __str__(self):
        return f'{self.name} [{self.priority_level}]'


class SLABreach(models.Model):
    """Record of a specific SLA breach event."""
    BREACH_TYPES = [('first_response','First Response'),('resolution','Resolution')]
    ticket        = models.ForeignKey('SupportTicket', on_delete=models.CASCADE, related_name='sla_breaches')
    breach_type   = models.CharField(max_length=20, choices=BREACH_TYPES, db_index=True)
    due_at        = models.DateTimeField()
    breached_at   = models.DateTimeField(auto_now_add=True)
    overdue_hours = models.FloatField(default=0.0)
    notified_admin = models.BooleanField(default=False)
    notified_agent = models.BooleanField(default=False)
    resolved      = models.BooleanField(default=False)
    resolved_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'support'
        ordering  = ['-breached_at']
        db_table  = 'support_sla_breach'

    def __str__(self):
        return f'Breach: {self.ticket.ticket_id} — {self.breach_type}'


class BusinessHours(models.Model):
    """Working hours configuration per department/tenant."""
    WEEKDAYS = [(0,'Monday'),(1,'Tuesday'),(2,'Wednesday'),(3,'Thursday'),(4,'Friday'),(5,'Saturday'),(6,'Sunday')]
    tenant      = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    department  = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
    weekday     = models.IntegerField(choices=WEEKDAYS)
    open_time   = models.TimeField()
    close_time  = models.TimeField()
    timezone    = models.CharField(max_length=50, default='Asia/Dhaka')
    is_active   = models.BooleanField(default=True)

    class Meta:
        app_label       = 'support'
        unique_together = [['tenant', 'department', 'weekday']]
        db_table        = 'support_business_hours'


class Holiday(models.Model):
    """Public holidays excluded from SLA calculation."""
    tenant    = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    name      = models.CharField(max_length=100)
    date      = models.DateField(db_index=True)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True, help_text='null=all departments')
    affects_sla = models.BooleanField(default=True)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support'
        ordering  = ['date']
        db_table  = 'support_holiday'

    def __str__(self):
        return f'{self.name} ({self.date})'