import uuid
from django.db import models

class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    domain = models.CharField(max_length=255, unique=True, blank=True, null=True)
    logo = models.ImageField(upload_to="tenant_logos/", blank=True, null=True)
    primary_color = models.CharField(max_length=7, default="#00f5ff")
    secondary_color = models.CharField(max_length=7, default="#8b00ff")
    is_active = models.BooleanField(default=True)
    plan = models.CharField(max_length=50, default="basic", choices=[("basic","Basic"),("pro","Pro"),("enterprise","Enterprise")])
    max_users = models.IntegerField(default=1000)
    admin_email = models.EmailField()
    support_email = models.EmailField(blank=True)
    api_key = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]
