# api/support/admin/department_admin.py  — WORLD #1
from django.contrib import admin
from api.support.models import Department, BusinessHours

class BusinessHoursInline(admin.TabularInline):
    model = BusinessHours
    extra = 0

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display  = ['name','slug','routing_rule','auto_assign','is_active','email_address']
    list_filter   = ['routing_rule','is_active','auto_assign']
    search_fields = ['name','email_address']
    prepopulated_fields = {'slug': ('name',)}
    inlines       = [BusinessHoursInline]