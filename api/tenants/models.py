from django.db import models
import uuid

class Tenant(models.Model):
    PLAN_CHOICES = [
        ("basic", "Basic"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise"),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    domain = models.CharField(max_length=255, unique=True)
    api_key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    logo = models.ImageField(upload_to="tenant_logos/", null=True, blank=True)
    primary_color = models.CharField(max_length=7, default="#007bff")
    secondary_color = models.CharField(max_length=7, default="#6c757d")
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="basic")
    max_users = models.IntegerField(default=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenants"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
