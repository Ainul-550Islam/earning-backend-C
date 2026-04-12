# admin/coverage_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.analytics import TranslationCoverage

@admin.register(TranslationCoverage)
class TranslationCoverageAdmin(admin.ModelAdmin):
    list_display = ['language', 'coverage_bar', 'approved_percent', 'total_keys', 'translated_keys', 'missing_keys', 'pending_review_keys', 'machine_translated_keys', 'last_calculated_at']
    ordering = ['-coverage_percent']
    readonly_fields = ['coverage_percent', 'approved_percent', 'total_keys', 'translated_keys', 'approved_keys', 'pending_review_keys', 'machine_translated_keys', 'missing_keys', 'last_calculated_at']

    def coverage_bar(self, obj):
        pct = float(obj.coverage_percent or 0)
        color = '#28a745' if pct >= 90 else ('#ffc107' if pct >= 50 else '#dc3545')
        return format_html(
            '<div style="background:#e9ecef;border-radius:4px;width:100px;height:18px;display:inline-block;overflow:hidden;vertical-align:middle;">'
            '<div style="background:{};height:100%;width:{}%;"></div></div> <strong>{:.1f}%</strong>',
            color, min(pct, 100), pct
        )
    coverage_bar.short_description = 'Coverage'

    actions = ['recalculate_coverage']

    def recalculate_coverage(self, request, queryset):
        for coverage in queryset:
            coverage.recalculate()
        self.message_user(request, f'Recalculated {queryset.count()} coverage records')
    recalculate_coverage.short_description = '📊 Recalculate coverage'
