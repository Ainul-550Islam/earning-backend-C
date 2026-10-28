"""Minimal stand-in for the host project's real tenants.Tenant model."""
from django.db import models


class Tenant(models.Model):
    name = models.CharField(max_length=255, default="test-tenant")

    class Meta:
        app_label = "tenants"

    def __str__(self):
        return self.name
