# api/support/admin/kb_admin.py  — WORLD #1
from django.contrib import admin
from api.support.models import KBCategory, KBArticle, KBArticleVersion

class KBArticleVersionInline(admin.TabularInline):
    model   = KBArticleVersion
    extra   = 0
    fields  = ['version_number','changed_by','diff_summary','changed_at']
    readonly_fields = ['changed_at']

@admin.register(KBCategory)
class KBCategoryAdmin(admin.ModelAdmin):
    list_display  = ['name','slug','icon','parent','sort_order','is_active','article_count']
    list_filter   = ['is_active']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}

    def article_count(self, obj):
        return obj.articles.filter(status='published').count()
    article_count.short_description = 'Articles'

@admin.register(KBArticle)
class KBArticleAdmin(admin.ModelAdmin):
    list_display  = ['title','category','author','status','is_public','views_count','helpful_yes','created_at']
    list_filter   = ['status','is_public','category']
    search_fields = ['title','body','summary']
    readonly_fields = ['views_count','helpful_yes','helpful_no','created_at','updated_at']
    prepopulated_fields = {'slug': ('title',)}
    inlines       = [KBArticleVersionInline]