"""
NEW FILE — Version history & rollback model.

Implements Missing Component #7 (Versioning & Rollback): previously a
bad flag config had no automated path back to a known-good state short
of manually re-entering old values.
"""
from django.conf import settings
from django.db import models

from .base import BaseModel
from .feature_flag import FeatureFlag


class FeatureFlagVersion(BaseModel):
    """An immutable snapshot of a FeatureFlag's fields at a point in time."""

    flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    config = models.JSONField(help_text='Full snapshot of flag fields at this version.')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        verbose_name = 'Feature Flag Version'
        verbose_name_plural = 'Feature Flag Versions'
        unique_together = [['flag', 'version_number']]
        ordering = ['-version_number']
        indexes = [
            models.Index(fields=['flag', '-version_number'], name='flagver_flag_ver_idx'),
        ]

    def __str__(self):
        return f"{self.flag.name} v{self.version_number}"
