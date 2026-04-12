# admin/language_admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db.models import Count
from ..models.core import Language
import logging
logger = logging.getLogger(__name__)

@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ['code_badge', 'name', 'name_native', 'flag_display',
                    'rtl_badge', 'default_badge', 'active_badge',
                    'coverage_display', 'translations_count', 'created_at']
    list_filter = ['is_active', 'is_default', 'is_rtl']
    search_fields = ['code', 'name', 'name_native']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-is_default', '-is_active', 'name']
    list_per_page = 30

    fieldsets = (
        (_('Core'), {'fields': ('code', 'name', 'name_native', 'flag_emoji', 'locale_code', 'is_active', 'is_default')}),
        (_('RTL / Script'), {'fields': ('is_rtl', 'script_code', 'text_direction', 'font_family')}),
        (_('ISO Codes'), {'fields': ('bcp47_code', 'iso_639_1', 'iso_639_2', 'iso_639_3'), 'classes': ('collapse',)}),
        (_('Translation Providers'), {'fields': ('google_translate_code', 'deepl_code', 'azure_code'), 'classes': ('collapse',)}),
        (_('Plural Rules'), {'fields': ('plural_rule',), 'classes': ('collapse',)}),
        (_('Quality'), {'fields': ('is_machine_translatable', 'requires_review')}),
        (_('Fallback'), {'fields': ('fallback_language',)}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(trans_count=Count('translations'))

    def code_badge(self, obj):
        return format_html('<span style="background:#17a2b8;color:white;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:bold;">{}</span>', obj.code)
    code_badge.short_description = _('Code')
    code_badge.admin_order_field = 'code'

    def flag_display(self, obj):
        return obj.flag_emoji or '🌐'
    flag_display.short_description = _('Flag')

    def rtl_badge(self, obj):
        if obj.is_rtl:
            return format_html('<span style="background:#6f42c1;color:white;padding:2px 6px;border-radius:10px;font-size:11px;">RTL</span>')
        return format_html('<span style="background:#e9ecef;color:#495057;padding:2px 6px;border-radius:10px;font-size:11px;">LTR</span>')
    rtl_badge.short_description = _('Dir')

    def default_badge(self, obj):
        if obj.is_default:
            return format_html('<span style="background:#ffc107;color:#212529;padding:2px 8px;border-radius:12px;font-size:11px;">★ Default</span>')
        return ''
    default_badge.short_description = _('Default')

    def active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="background:#28a745;color:white;padding:2px 8px;border-radius:12px;font-size:11px;">✓ Active</span>')
        return format_html('<span style="background:#dc3545;color:white;padding:2px 8px;border-radius:12px;font-size:11px;">✗ Inactive</span>')
    active_badge.short_description = _('Status')

    def coverage_display(self, obj):
        pct = float(obj.coverage_percent or 0)
        color = '#28a745' if pct >= 90 else ('#ffc107' if pct >= 50 else '#dc3545')
        return format_html(
            '<div style="background:#e9ecef;border-radius:4px;width:80px;height:16px;display:inline-block;overflow:hidden;">'
            '<div style="background:{};height:100%;width:{}%;"></div></div> <span style="font-size:11px;">{:.0f}%</span>',
            color, min(pct, 100), pct
        )
    coverage_display.short_description = _('Coverage')

    def translations_count(self, obj):
        count = getattr(obj, 'trans_count', 0)
        return format_html('<span style="font-size:12px;">{}</span>', count)
    translations_count.short_description = _('Translations')
    translations_count.admin_order_field = 'trans_count'

    actions = ['activate_languages', 'deactivate_languages', 'recalculate_coverage']

    def activate_languages(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'Activated {updated} languages')
    activate_languages.short_description = _('✓ Activate selected')

    def deactivate_languages(self, request, queryset):
        updated = queryset.exclude(is_default=True).update(is_active=False)
        self.message_user(request, f'Deactivated {updated} languages (default kept active)')
    deactivate_languages.short_description = _('✗ Deactivate selected')

    def recalculate_coverage(self, request, queryset):
        for lang in queryset:
            lang.update_coverage()
        self.message_user(request, f'Coverage recalculated for {queryset.count()} languages')
    recalculate_coverage.short_description = _('📊 Recalculate coverage')
