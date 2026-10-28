# api/support/admin/insight_admin.py  — WORLD #1
from django.contrib import admin
from api.support.models import SupportInsight, CSATReport, ChannelReport, TopicCluster

@admin.register(SupportInsight)
class SupportInsightAdmin(admin.ModelAdmin):
    list_display  = ['date','tickets_created','tickets_resolved','avg_first_response_minutes','csat_avg','sla_compliance_pct']
    readonly_fields = list_display + ['created_at']

@admin.register(TopicCluster)
class TopicClusterAdmin(admin.ModelAdmin):
    list_display  = ['name','ticket_count','trend','period','has_kb_article']
    list_filter   = ['trend','has_kb_article']
    readonly_fields = ['created_at']