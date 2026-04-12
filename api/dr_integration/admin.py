"""
DR Integration Django Admin — Manage DR operations from Django admin panel.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    DRSystemStatus, DRBackupRecord, DRRestoreRecord,
    DRFailoverEvent, DRAlert, DRDrillRecord
)


@admin.register(DRSystemStatus)
class DRSystemStatusAdmin(admin.ModelAdmin):
    list_display = ['overall_health_colored', 'last_backup_at', 'active_incidents',
                    'active_alerts', 'replication_lag_display', 'synced_at']
    readonly_fields = ['overall_health', 'last_backup_at', 'last_failover_at',
                       'replication_lag_seconds', 'active_incidents', 'active_alerts',
                       'rto_achieved_seconds', 'rpo_achieved_seconds', 'raw_status', 'synced_at']

    def overall_health_colored(self, obj):
        colors = {'healthy': '#27ae60', 'degraded': '#f39c12', 'critical': '#e74c3c', 'unknown': '#95a5a6'}
        color = colors.get(obj.overall_health, '#95a5a6')
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            color, obj.overall_health.upper()
        )
    overall_health_colored.short_description = 'Health'

    def replication_lag_display(self, obj):
        if obj.replication_lag_seconds is None:
            return '—'
        if obj.replication_lag_seconds > 30:
            return format_html('<span style="color:#e74c3c">{:.1f}s ⚠️</span>', obj.replication_lag_seconds)
        return f'{obj.replication_lag_seconds:.1f}s'
    replication_lag_display.short_description = 'Replication Lag'

    def has_add_permission(self, request): return False


@admin.register(DRBackupRecord)
class DRBackupRecordAdmin(admin.ModelAdmin):
    list_display = ['id_short', 'backup_type', 'status_colored', 'size_mb',
                    'is_verified', 'tenant', 'triggered_by', 'created_at']
    list_filter = ['status', 'backup_type', 'is_verified']
    search_fields = ['dr_job_id', 'checksum']
    readonly_fields = ['id', 'dr_job_id', 'checksum', 'created_at']
    actions = ['verify_selected_backups']
    ordering = ['-created_at']

    def id_short(self, obj):
        return str(obj.id)[:12] + '...'
    id_short.short_description = 'ID'

    def status_colored(self, obj):
        colors = {'completed': '#27ae60', 'verified': '#27ae60', 'running': '#3498db',
                  'failed': '#e74c3c', 'pending': '#f39c12'}
        color = colors.get(obj.status, '#95a5a6')
        return format_html('<span style="color:{}">■ {}</span>', color, obj.status)
    status_colored.short_description = 'Status'

    def size_mb(self, obj):
        return f"{obj.size_mb} MB" if obj.size_mb else '—'
    size_mb.short_description = 'Size'

    @admin.action(description='Verify selected backups')
    def verify_selected_backups(self, request, queryset):
        from .services import DRBackupBridge
        bridge = DRBackupBridge()
        verified = 0
        for backup in queryset:
            result = bridge.verify_backup(str(backup.dr_job_id))
            if result.get('verified'):
                backup.is_verified = True
                backup.save()
                verified += 1
        self.message_user(request, f'✅ Verified {verified}/{queryset.count()} backups')


@admin.register(DRRestoreRecord)
class DRRestoreRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'restore_type', 'status', 'target_database',
                    'approval_status', 'requested_by', 'created_at']
    list_filter = ['status', 'restore_type', 'approval_status']
    readonly_fields = ['id', 'dr_request_id', 'created_at']
    ordering = ['-created_at']
    actions = ['approve_restore_requests']

    @admin.action(description='Approve selected restore requests')
    def approve_restore_requests(self, request, queryset):
        count = queryset.filter(approval_status='pending').update(approval_status='approved')
        self.message_user(request, f'✅ Approved {count} restore request(s)')


@admin.register(DRFailoverEvent)
class DRFailoverEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'failover_type', 'status', 'primary_node', 'secondary_node',
                    'rto_achieved_seconds', 'is_drill', 'initiated_at']
    list_filter = ['failover_type', 'status', 'is_drill']
    readonly_fields = ['id', 'dr_failover_id', 'initiated_at', 'completed_at']
    ordering = ['-initiated_at']


@admin.register(DRAlert)
class DRAlertAdmin(admin.ModelAdmin):
    list_display = ['rule_name', 'severity_colored', 'message_short',
                    'is_acknowledged', 'fired_at']
    list_filter = ['severity', 'is_acknowledged']
    search_fields = ['rule_name', 'message']
    readonly_fields = ['id', 'fired_at', 'acknowledged_at']
    ordering = ['-fired_at']
    actions = ['acknowledge_alerts']

    def severity_colored(self, obj):
        colors = {'critical': '#e74c3c', 'error': '#e67e22', 'warning': '#f39c12', 'info': '#3498db'}
        return format_html('<span style="color:{}">■ {}</span>',
                            colors.get(obj.severity,'#95a5a6'), obj.severity.upper())
    severity_colored.short_description = 'Severity'

    def message_short(self, obj):
        return obj.message[:80] + '...' if len(obj.message) > 80 else obj.message
    message_short.short_description = 'Message'

    @admin.action(description='Acknowledge selected alerts')
    def acknowledge_alerts(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_acknowledged=True, acknowledged_by=request.user,
                        acknowledged_at=timezone.now())
        self.message_user(request, f'✅ Acknowledged {queryset.count()} alert(s)')


@admin.register(DRDrillRecord)
class DRDrillRecordAdmin(admin.ModelAdmin):
    list_display = ['name', 'scenario_type', 'status', 'passed_display',
                    'achieved_rto_seconds', 'target_rto_seconds', 'scheduled_at']
    list_filter = ['status', 'scenario_type', 'passed']
    readonly_fields = ['id', 'dr_drill_id', 'created_at'] if hasattr(DRDrillRecord, 'created_at') else ['id', 'dr_drill_id']

    def passed_display(self, obj):
        if obj.passed is None: return '—'
        return format_html('<span style="color:{}">■ {}</span>',
                            '#27ae60' if obj.passed else '#e74c3c',
                            'PASSED' if obj.passed else 'FAILED')
    passed_display.short_description = 'Result'
