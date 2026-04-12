"""Documentation models."""
from django.db import models
from django.utils import timezone
from ..models import AdvertiserPortalBaseModel


class Documentation(AdvertiserPortalBaseModel):
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True)
    content = models.TextField()
    doc_type = models.CharField(max_length=30, db_index=True)
    category = models.CharField(max_length=100, blank=True, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)
    view_count = models.BigIntegerField(default=0)
    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return self.title


class APIDocumentation(AdvertiserPortalBaseModel):
    documentation = models.OneToOneField(Documentation, on_delete=models.CASCADE, related_name='api_doc', null=True, blank=True)
    endpoint_path = models.CharField(max_length=500)
    http_method = models.CharField(max_length=10)
    summary = models.CharField(max_length=300)
    request_schema = models.JSONField(default=dict)
    response_schema = models.JSONField(default=dict)
    version = models.CharField(max_length=10, default='v1')
    class Meta:
        ordering = ['endpoint_path']
    def __str__(self):
        return f"{self.http_method} {self.endpoint_path}"


class UserGuide(AdvertiserPortalBaseModel):
    documentation = models.OneToOneField(Documentation, on_delete=models.CASCADE, related_name='user_guide')
    steps = models.JSONField(default=list)
    difficulty = models.CharField(max_length=20, default='beginner')
    def __str__(self):
        return f"Guide: {self.documentation_id}"


class TechnicalDocumentation(AdvertiserPortalBaseModel):
    documentation = models.OneToOneField(Documentation, on_delete=models.CASCADE, related_name='technical_doc')
    code_examples = models.JSONField(default=list)
    architecture_notes = models.TextField(blank=True)
    def __str__(self):
        return f"TechDoc: {self.documentation_id}"


class DocumentationSearch(AdvertiserPortalBaseModel):
    query = models.CharField(max_length=500, db_index=True)
    results_count = models.IntegerField(default=0)
    searched_at = models.DateTimeField(default=timezone.now, db_index=True)
    class Meta:
        ordering = ['-searched_at']
    def __str__(self):
        return f"Search '{self.query}'"


class DocumentationVersioning(AdvertiserPortalBaseModel):
    documentation = models.ForeignKey(Documentation, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField()
    content_snapshot = models.TextField()
    class Meta:
        ordering = ['-version_number']
    def __str__(self):
        return f"v{self.version_number}"


class DocumentationAnalytics(AdvertiserPortalBaseModel):
    documentation = models.OneToOneField(Documentation, on_delete=models.CASCADE, related_name='analytics')
    total_views = models.BigIntegerField(default=0)
    helpful_ratio = models.FloatField(default=0.0)
    def __str__(self):
        return f"DocAnalytics {self.documentation_id}"
