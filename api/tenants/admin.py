from django.contrib import admin
from .models import Tenant

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "plan", "is_active", "max_users", "created_at"]
    list_filter = ["plan", "is_active"]
    search_fields = ["name", "slug", "domain", "admin_email"]
    readonly_fields = ["id", "api_key", "created_at", "updated_at"]
