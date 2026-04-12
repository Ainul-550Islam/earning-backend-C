"""
database_models/publisher_model.py
────────────────────────────────────
Publisher model — stores metadata for traffic publishers (sub_id owners).
"""
from django.db import models
import uuid

class Publisher(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sub_id = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_trusted = models.BooleanField(default=False)
    is_blacklisted = models.BooleanField(default=False, db_index=True)
    quality_score = models.IntegerField(default=50, help_text="0-100")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "postback_engine"
        verbose_name = "publisher"
        verbose_name_plural = "publishers"
        ordering = ["-quality_score"]

    def __str__(self):
        return f"{self.name or self.sub_id} (score={self.quality_score})"
