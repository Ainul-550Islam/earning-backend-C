# admin/timezone_admin.py
from django.contrib import admin
from ..models.core import Timezone

@admin.register(Timezone)
class TimezoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'offset', 'is_dst', 'is_active']
    list_filter = ['is_active', 'is_dst']
    search_fields = ['name', 'code']
    ordering = ['offset_seconds', 'name']
