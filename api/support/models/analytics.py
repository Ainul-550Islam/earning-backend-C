# api/support/models/analytics.py  — WORLD #1
"""Analytics snapshot models: SupportInsight, CSATReport, AgentReport, ChannelReport, TopicCluster."""
from django.db import models
from django.conf import settings


class SupportInsight(models.Model):
    """Daily aggregated support metrics snapshot."""
    tenant                    = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    date                      = models.DateField(db_index=True)
    tickets_created           = models.IntegerField(default=0)
    tickets_resolved          = models.IntegerField(default=0)
    tickets_open              = models.IntegerField(default=0)
    avg_first_response_minutes = models.FloatField(default=0)
    avg_resolution_hours      = models.FloatField(default=0)
    csat_avg                  = models.FloatField(default=0)
    sla_compliance_pct        = models.FloatField(default=0)
    chats_started             = models.IntegerField(default=0)
    created_at                = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label       = 'support'
        unique_together = [['tenant', 'date']]
        ordering        = ['-date']
        db_table        = 'support_insight'


class CSATReport(models.Model):
    """Aggregated CSAT/NPS report for a period."""
    tenant           = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    period           = models.DateField(db_index=True, help_text='Start of period')
    avg_score        = models.FloatField(default=0)
    total_ratings    = models.IntegerField(default=0)
    promoters_count  = models.IntegerField(default=0, help_text='Score 5')
    passives_count   = models.IntegerField(default=0, help_text='Score 3-4')
    detractors_count = models.IntegerField(default=0, help_text='Score 1-2')
    nps              = models.FloatField(default=0, help_text='Net Promoter Score')
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label       = 'support'
        unique_together = [['tenant', 'period']]
        db_table        = 'support_csat_report'


class AgentReport(models.Model):
    """Stored performance report for a single agent."""
    agent      = models.ForeignKey('SupportAgent', on_delete=models.CASCADE, related_name='reports')
    period     = models.DateField(db_index=True)
    metrics    = models.JSONField(default=dict)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label       = 'support'
        unique_together = [['agent', 'period']]
        ordering        = ['-period']
        db_table        = 'support_agent_report'


class ChannelReport(models.Model):
    """Volume and metrics per channel per period."""
    CHANNELS = [('web','Web'),('email','Email'),('chat','Chat'),('telegram','Telegram'),('whatsapp','WhatsApp')]
    tenant          = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    channel         = models.CharField(max_length=20, choices=CHANNELS, db_index=True)
    period          = models.DateField(db_index=True)
    volume          = models.IntegerField(default=0)
    resolution_rate = models.FloatField(default=0)
    avg_response_time = models.FloatField(default=0)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label       = 'support'
        unique_together = [['tenant', 'channel', 'period']]
        db_table        = 'support_channel_report'


class TopicCluster(models.Model):
    """AI-grouped ticket topic clusters for trend analysis."""
    tenant       = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    name         = models.CharField(max_length=200, db_index=True)
    keywords     = models.JSONField(default=list)
    ticket_count = models.IntegerField(default=0)
    trend        = models.CharField(max_length=20, default='stable', choices=[('up','Up'),('down','Down'),('stable','Stable')])
    period       = models.DateField(db_index=True)
    has_kb_article = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label       = 'support'
        unique_together = [['name', 'period']]
        db_table        = 'support_topic_cluster'

    def __str__(self):
        return f'{self.name} ({self.ticket_count} tickets)'