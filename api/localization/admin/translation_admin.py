# admin/translation_admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from ..models.core import Translation, TranslationKey
from ..models.translation import TranslationCache, MissingTranslation, TranslationMemory, TranslationGlossary, TranslationVersion
import logging
logger = logging.getLogger(__name__)


@admin.register(TranslationKey)
class TranslationKeyAdmin(admin.ModelAdmin):
    list_display = ['key', 'category', 'priority_badge', 'is_html', 'is_plural', 'created_at']
    list_filter = ['category', 'is_html', 'is_plural']
    search_fields = ['key', 'description', 'category']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['category', 'key']
    list_per_page = 50

    def priority_badge(self, obj):
        colors = {'critical': '#dc3545', 'high': '#fd7e14', 'normal': '#28a745', 'low': '#6c757d'}
        color = colors.get(obj.priority, '#6c757d')
        return format_html('<span style="background:{};color:white;padding:2px 6px;border-radius:10px;font-size:11px;">{}</span>', color, obj.priority)
    priority_badge.short_description = _('Priority')


@admin.register(Translation)
class TranslationAdmin(admin.ModelAdmin):
    list_display = ['key_display', 'language_badge', 'value_preview', 'approved_badge', 'source_badge', 'quality_badge', 'created_at']
    list_filter = ['language', 'is_approved', 'source']
    search_fields = ['key__key', 'value']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['key', 'language', 'approved_by']
    list_per_page = 50

    def key_display(self, obj):
        key_str = obj.key.key[:40] if obj.key else ''
        return format_html('<code style="font-size:11px;">{}</code>', key_str)
    key_display.short_description = _('Key')

    def language_badge(self, obj):
        code = obj.language.code if obj.language else '?'
        return format_html('<span style="background:#17a2b8;color:white;padding:2px 8px;border-radius:12px;font-size:12px;">{}</span>', code)
    language_badge.short_description = _('Language')

    def value_preview(self, obj):
        val = obj.value[:60] if obj.value else ''
        return val + ('...' if len(obj.value or '') > 60 else '')
    value_preview.short_description = _('Value')

    def approved_badge(self, obj):
        if obj.is_approved:
            return format_html('<span style="color:#28a745;">✓</span>')
        return format_html('<span style="color:#dc3545;">⏳</span>')
    approved_badge.short_description = _('Approved')

    def source_badge(self, obj):
        colors = {'manual': '#17a2b8', 'auto': '#ffc107', 'import': '#6f42c1', 'api': '#20c997', 'memory': '#fd7e14', 'machine': '#e83e8c'}
        color = colors.get(obj.source, '#6c757d')
        return format_html('<span style="background:{};color:white;padding:2px 5px;border-radius:8px;font-size:10px;">{}</span>', color, obj.source)
    source_badge.short_description = _('Source')

    def quality_badge(self, obj):
        colors = {'excellent': '#28a745', 'good': '#17a2b8', 'fair': '#ffc107', 'poor': '#dc3545', 'unreviewed': '#6c757d'}
        color = colors.get(obj.quality_score, '#6c757d')
        return format_html('<span style="background:{};color:white;padding:2px 5px;border-radius:8px;font-size:10px;">{}</span>', color, obj.quality_score or 'unreviewed')
    quality_badge.short_description = _('Quality')

    actions = ['approve_translations', 'mark_for_review']

    def approve_translations(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(is_approved=True, approved_by=request.user, approved_at=timezone.now())
        self.message_user(request, f'Approved {updated} translations')
    approve_translations.short_description = _('✓ Approve selected')

    def mark_for_review(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'Marked {updated} translations for review')
    mark_for_review.short_description = _('⏳ Mark for review')


@admin.register(MissingTranslation)
class MissingTranslationAdmin(admin.ModelAdmin):
    list_display = ['key', 'language_badge', 'occurrence_count', 'priority_badge', 'resolved_badge', 'last_seen_at', 'created_at']
    list_filter = ['language', 'resolved']
    search_fields = ['key', 'request_path']
    readonly_fields = ['occurrence_count', 'last_seen_at', 'created_at', 'updated_at']
    ordering = ['-occurrence_count', '-created_at']

    def language_badge(self, obj):
        code = obj.language.code if obj.language else '?'
        return format_html('<span style="background:#17a2b8;color:white;padding:2px 6px;border-radius:10px;font-size:11px;">{}</span>', code)
    language_badge.short_description = _('Language')

    def priority_badge(self, obj):
        colors = {'critical': '#dc3545', 'high': '#fd7e14', 'normal': '#28a745', 'low': '#6c757d'}
        color = colors.get(obj.priority, '#6c757d')
        return format_html('<span style="background:{};color:white;padding:2px 6px;border-radius:10px;font-size:11px;">{}</span>', color, obj.priority)
    priority_badge.short_description = _('Priority')

    def resolved_badge(self, obj):
        if obj.resolved:
            return format_html('<span style="color:#28a745;">✓ Resolved</span>')
        return format_html('<span style="color:#dc3545;">⚠ Unresolved</span>')
    resolved_badge.short_description = _('Status')

    actions = ['mark_resolved']

    def mark_resolved(self, request, queryset):
        from django.utils import timezone
        queryset.update(resolved=True, resolved_at=timezone.now(), resolved_by=request.user)
        self.message_user(request, f'Marked {queryset.count()} as resolved')
    mark_resolved.short_description = _('✓ Mark as resolved')
