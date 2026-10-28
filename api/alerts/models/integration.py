"""
Integration-layer models.

These live under alerts/models/ (rather than alerts/integration/) so Django's
app registry actually discovers them - only models reachable via
`alerts.models` get registered and get tables created for them.
`alerts/integration/versioning.py` imports IntegrationVersion from here.
"""
from django.db import models


class IntegrationVersion(models.Model):
    """
    Integration version model for database storage
    """
    integration_id = models.CharField(max_length=100, db_index=True)
    version = models.CharField(max_length=20)
    config_hash = models.CharField(max_length=64)  # SHA-256 hash
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'alerts'
        db_table = 'integration_version'
        constraints = [
            models.UniqueConstraint(
                fields=['integration_id', 'version'],
                name='unique_integration_version_per_id',
            ),
        ]
        indexes = [
            models.Index(fields=['integration_id', 'is_active'], name='intver_id_active_idx'),
        ]

    def __str__(self):
        return f"{self.integration_id}@{self.version}"
