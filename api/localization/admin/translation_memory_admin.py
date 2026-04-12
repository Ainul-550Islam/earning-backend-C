# admin/translation_memory_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.translation import TranslationMemory

@admin.register(TranslationMemory)
class TranslationMemoryAdmin(admin.ModelAdmin):
    list_display = ['source_preview', 'target_preview', 'source_language', 'target_language', 'domain', 'usage_count', 'quality_rating', 'is_approved', 'created_at']
    list_filter = ['source_language', 'target_language', 'is_approved', 'domain']
    search_fields = ['source_text', 'target_text', 'domain']
    readonly_fields = ['source_hash', 'source_word_count', 'target_word_count', 'usage_count', 'last_used_at', 'created_at', 'updated_at']
    list_per_page = 50

    def source_preview(self, obj):
        return (obj.source_text or '')[:50] + ('...' if len(obj.source_text or '') > 50 else '')
    source_preview.short_description = 'Source'

    def target_preview(self, obj):
        return (obj.target_text or '')[:50] + ('...' if len(obj.target_text or '') > 50 else '')
    target_preview.short_description = 'Target'
