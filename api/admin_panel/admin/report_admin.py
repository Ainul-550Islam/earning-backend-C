# api/admin_panel/admin/report_admin.py
"""Django Admin for Report and insight models."""
from django.contrib import admin
from django.utils.html import format_html
from ..models.core import Report
from ..models.reports import (
    ReportDefinition, ReportSchedule, ReportExport, AdminInsight, DataExport
)


# @admin.register(Report) — registered in admin.py
class ReportAdmin(admin.ModelAdmin):
    list_display = ['title', 'report_type', 'status', 'generated_by', 'generated_at']
    list_filter = ['report_type', 'status']
    search_fields = ['title', 'report_id']
    readonly_fields = ['report_id', 'generated_at', 'created_at', 'updated_at']
    raw_id_fields = ['generated_by']
    date_hierarchy = 'generated_at'


@admin.register(ReportDefinition)
class ReportDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'report_type', 'is_active', 'is_system', 'created_by', 'created_at']
    list_filter = ['report_type', 'is_active', 'is_system']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['created_by']

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.is_system:
            fields += ['name', 'report_type', 'query_config', 'columns']
        return fields


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ['name', 'report', 'cron_expr', 'format', 'is_active', 'last_run_at', 'run_count', 'failure_count']
    list_filter = ['is_active', 'format']
    search_fields = ['name', 'cron_expr']
    readonly_fields = ['last_run_at', 'next_run_at', 'run_count', 'failure_count', 'created_at', 'updated_at']
    raw_id_fields = ['report', 'created_by']


@admin.register(ReportExport)
class ReportExportAdmin(admin.ModelAdmin):
    list_display = ['export_id', 'report', 'format', 'status_badge', 'row_count', 'file_size_human', 'generated_by', 'created_at']
    list_filter = ['status', 'format']
    search_fields = ['title']
    readonly_fields = [
        'export_id', 'status', 'file_path', 'file_url', 'file_size_bytes',
        'row_count', 'error_message', 'expires_at', 'created_at', 'completed_at',
    ]
    raw_id_fields = ['report', 'report_schedule', 'generated_by']
    date_hierarchy = 'created_at'

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {'completed': 'green', 'failed': 'red', 'processing': 'orange', 'pending': 'gray'}
        return format_html(
            '<span style="color:{};">{}</span>',
            colors.get(obj.status, 'black'), obj.status.upper()
        )


@admin.register(AdminInsight)
class AdminInsightAdmin(admin.ModelAdmin):
    list_display = ['title', 'type', 'priority_badge', 'is_read', 'is_dismissed', 'created_at']
    list_filter = ['type', 'priority', 'is_read', 'is_dismissed']
    search_fields = ['title', 'body']
    readonly_fields = ['insight_id', 'generated_by_task', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'

    @admin.display(description='Priority')
    def priority_badge(self, obj):
        colors = {'critical': 'red', 'high': 'orange', 'medium': 'blue', 'low': 'gray'}
        return format_html(
            '<span style="color:{};">{}</span>',
            colors.get(obj.priority, 'black'), obj.priority.upper()
        )

    actions = ['mark_all_read', 'dismiss_selected']

    @admin.action(description='Mark selected insights as read')
    def mark_all_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f'{updated} insight(s) marked as read.')

    @admin.action(description='Dismiss selected insights')
    def dismiss_selected(self, request, queryset):
        updated = queryset.update(is_dismissed=True)
        self.message_user(request, f'{updated} insight(s) dismissed.')


@admin.register(DataExport)
class DataExportAdmin(admin.ModelAdmin):
    list_display = ['export_id', 'model_name', 'format', 'status', 'row_count', 'file_size_human', 'requested_by', 'created_at']
    list_filter = ['status', 'format']
    search_fields = ['model_name', 'label']
    readonly_fields = [
        'export_id', 'status', 'file_path', 'file_url', 'file_size_bytes',
        'row_count', 'error_message', 'task_id', 'expires_at', 'created_at', 'completed_at',
    ]
    raw_id_fields = ['requested_by']
    date_hierarchy = 'created_at'