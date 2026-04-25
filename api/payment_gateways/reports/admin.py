# api/payment_gateways/reports/admin.py
from django.contrib import admin
from .models import ReconciliationReport

@admin.register(ReconciliationReport)
class ReconciliationReportAdmin(admin.ModelAdmin):
    list_display  = ('report_date', 'created_at')
    ordering      = ('-report_date',)
    readonly_fields = ('report_date', 'data', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
