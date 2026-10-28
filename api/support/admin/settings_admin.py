# api/support/admin/settings_admin.py  — WORLD #1
from django.contrib import admin
from django.utils.html import format_html
from api.support.models import SupportSettings

@admin.register(SupportSettings)
class SupportSettingsAdmin(admin.ModelAdmin):
    list_display = ['id','support_status_badge','maintenance_badge','chat_enabled','version_display','updated_at']
    readonly_fields = ['updated_at']

    def support_status_badge(self, obj):
        color = 'green' if obj.is_support_online else 'red'
        label = 'Online' if obj.is_support_online else 'Offline'
        return format_html('<span style="color:{};font-weight:bold">● {}</span>', color, label)
    support_status_badge.short_description = 'Support Status'

    def maintenance_badge(self, obj):
        if obj.maintenance_mode:
            return format_html('<span style="color:orange;font-weight:bold">⚠ Maintenance</span>')
        return format_html('<span style="color:green">Normal</span>')
    maintenance_badge.short_description = 'Maintenance'

    def chat_enabled(self, obj):
        return '✅' if obj.chat_widget_enabled else '❌'
    chat_enabled.short_description = 'Chat'

    def version_display(self, obj):
        return f'v{obj.latest_version_name} (code:{obj.latest_version_code})'
    version_display.short_description = 'App Version'

    def has_add_permission(self, request):
        return not SupportSettings.objects.exists()
    def has_delete_permission(self, request, obj=None):
        return False