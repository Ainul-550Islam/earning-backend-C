# api/support/models/knowledge_base.py  — WORLD #1
"""Knowledge base models: KBCategory, KBArticle, KBArticleVersion, KBSearch, KBFeedback."""
from django.db import models
from django.conf import settings


class KBCategory(models.Model):
    """Knowledge base article category (supports nesting)."""
    tenant     = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    name       = models.CharField(max_length=100)
    slug       = models.SlugField(unique=True)
    icon       = models.CharField(max_length=10, default='📄')
    description = models.TextField(blank=True, default='')
    parent     = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    sort_order = models.IntegerField(default=0)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support'
        ordering  = ['sort_order', 'name']
        db_table  = 'support_kb_category'

    def __str__(self):
        return self.name


class KBArticle(models.Model):
    """Knowledge base article."""
    STATUS_CHOICES = [('draft','Draft'),('published','Published'),('archived','Archived')]
    tenant     = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True)
    category   = models.ForeignKey(KBCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='articles')
    author     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='kb_articles')
    title      = models.CharField(max_length=300)
    slug       = models.SlugField(unique=True)
    body       = models.TextField()
    summary    = models.TextField(blank=True, default='')
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    is_public  = models.BooleanField(default=True)
    tags       = models.JSONField(default=list)
    views_count = models.IntegerField(default=0)
    helpful_yes = models.IntegerField(default=0)
    helpful_no  = models.IntegerField(default=0)
    search_vector = models.TextField(blank=True, default='', help_text='Computed search text')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'support'
        ordering  = ['-created_at']
        db_table  = 'support_kb_article'

    def __str__(self):
        return self.title


class KBArticleVersion(models.Model):
    """Version history for KB articles."""
    article       = models.ForeignKey(KBArticle, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField()
    body_snapshot = models.TextField()
    changed_by    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    changed_at    = models.DateTimeField(auto_now_add=True)
    diff_summary  = models.CharField(max_length=300, blank=True, default='')

    class Meta:
        app_label       = 'support'
        unique_together = [['article', 'version_number']]
        ordering        = ['-version_number']
        db_table        = 'support_kb_article_version'


class KBSearch(models.Model):
    """Log of KB searches for analytics."""
    query           = models.CharField(max_length=300)
    results_count   = models.IntegerField(default=0)
    clicked_article = models.ForeignKey(KBArticle, on_delete=models.SET_NULL, null=True, blank=True)
    user            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)
    searched_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support'
        ordering  = ['-searched_at']
        db_table  = 'support_kb_search'


class KBFeedback(models.Model):
    """Helpfulness feedback on a KB article."""
    article     = models.ForeignKey(KBArticle, on_delete=models.CASCADE, related_name='feedback_items')
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    is_helpful  = models.BooleanField()
    comment     = models.TextField(blank=True, default='')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support'
        db_table  = 'support_kb_feedback'