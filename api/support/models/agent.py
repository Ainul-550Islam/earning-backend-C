# api/support/models/agent.py  — WORLD #1
"""Agent management models: SupportAgent, AgentShift, AgentPerformance, AgentSkill, Department, AgentStatus."""
from django.db import models
from django.conf import settings


class Department(models.Model):
    """Support department for routing tickets/chats."""
    ROUTING_CHOICES = [('round_robin','Round Robin'),('least_busy','Least Busy'),('skill_match','Skill Match')]
    tenant        = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    name          = models.CharField(max_length=100)
    slug          = models.SlugField(unique=True)
    routing_rule  = models.CharField(max_length=20, choices=ROUTING_CHOICES, default='least_busy')
    auto_assign   = models.BooleanField(default=True)
    email_address = models.EmailField(blank=True, default='', help_text='Incoming email for this department')
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support'
        db_table  = 'support_department'

    def __str__(self):
        return self.name


class SupportAgent(models.Model):
    """Support agent profile linked to a user."""
    ROLE_CHOICES = [
        ('agent','Agent'),('senior_agent','Senior Agent'),('supervisor','Supervisor'),
        ('manager','Manager'),('account_manager','Account Manager'),
    ]
    user                  = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_agent')
    tenant                = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    department            = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    role                  = models.CharField(max_length=20, choices=ROLE_CHOICES, default='agent')
    is_active             = models.BooleanField(default=True, db_index=True)
    is_available          = models.BooleanField(default=True, db_index=True)
    max_concurrent_chats  = models.IntegerField(default=3)
    max_concurrent_tickets = models.IntegerField(default=10)
    skills                = models.JSONField(default=list, help_text='["payment","kyc"]')
    telegram_chat_id      = models.CharField(max_length=50, blank=True, default='')
    slack_user_id         = models.CharField(max_length=50, blank=True, default='')
    created_at            = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support'
        db_table  = 'support_agent'

    def __str__(self):
        return f'{self.user.username} [{self.role}]'


class AgentShift(models.Model):
    """Working shift schedule for an agent."""
    WEEKDAYS = [(0,'Monday'),(1,'Tuesday'),(2,'Wednesday'),(3,'Thursday'),(4,'Friday'),(5,'Saturday'),(6,'Sunday')]
    agent       = models.ForeignKey(SupportAgent, on_delete=models.CASCADE, related_name='shifts')
    weekday     = models.IntegerField(choices=WEEKDAYS)
    shift_start = models.TimeField()
    shift_end   = models.TimeField()
    timezone    = models.CharField(max_length=50, default='Asia/Dhaka')
    is_active   = models.BooleanField(default=True)

    class Meta:
        app_label       = 'support'
        unique_together = [['agent', 'weekday']]
        db_table        = 'support_agent_shift'


class AgentPerformance(models.Model):
    """Stored performance metrics per agent per period."""
    agent                  = models.ForeignKey(SupportAgent, on_delete=models.CASCADE, related_name='performance_records')
    period                 = models.DateField(db_index=True, help_text='First day of period')
    avg_response_minutes   = models.FloatField(default=0)
    avg_resolution_hours   = models.FloatField(default=0)
    csat_score             = models.FloatField(default=0)
    tickets_resolved       = models.IntegerField(default=0)
    tickets_assigned       = models.IntegerField(default=0)
    chats_handled          = models.IntegerField(default=0)
    sla_breaches_caused    = models.IntegerField(default=0)
    created_at             = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label       = 'support'
        unique_together = [['agent', 'period']]
        ordering        = ['-period']
        db_table        = 'support_agent_performance'


class AgentSkill(models.Model):
    """Skill proficiency for an agent."""
    PROFICIENCY = [(1,'Beginner'),(2,'Basic'),(3,'Intermediate'),(4,'Advanced'),(5,'Expert')]
    agent            = models.ForeignKey(SupportAgent, on_delete=models.CASCADE, related_name='skill_records')
    skill_tag        = models.CharField(max_length=50)
    proficiency_level = models.IntegerField(choices=PROFICIENCY, default=3)

    class Meta:
        app_label       = 'support'
        unique_together = [['agent', 'skill_tag']]
        db_table        = 'support_agent_skill'


class AgentStatus(models.Model):
    """Real-time agent status."""
    STATUS_CHOICES = [('online','Online'),('busy','Busy'),('away','Away'),('offline','Offline')]
    agent         = models.OneToOneField(SupportAgent, on_delete=models.CASCADE, related_name='status')
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline', db_index=True)
    changed_at    = models.DateTimeField(auto_now=True)
    last_seen     = models.DateTimeField(auto_now=True)
    status_message = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        app_label = 'support'
        db_table  = 'support_agent_status'

    def __str__(self):
        return f'{self.agent.user.username} [{self.status}]'