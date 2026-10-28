# api/support/admin/canned_response_admin.py  — WORLD #1
from django.contrib import admin
from api.support.models import CannedResponse

@admin.register(CannedResponse)
class CannedResponseAdmin(admin.ModelAdmin):
    list_display  = ['shortcut_key','title','category','usage_count','is_active','is_global','created_at']
    list_filter   = ['category','is_active','is_global']
    search_fields = ['shortcut_key','title','content']
    readonly_fields = ['usage_count','created_at']