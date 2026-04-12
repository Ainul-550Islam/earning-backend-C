"""Script models."""
from django.db import models
from django.utils import timezone
from ..models import AdvertiserPortalBaseModel


class Script(AdvertiserPortalBaseModel):
    name = models.CharField(max_length=200, unique=True)
    script_type = models.CharField(max_length=30, db_index=True)
    language = models.CharField(max_length=20, default='python')
    is_active = models.BooleanField(default=True)
    timeout_seconds = models.IntegerField(default=300)
    class Meta:
        ordering = ['name']
    def __str__(self):
        return f"Script {self.name}"


class AutomationScript(AdvertiserPortalBaseModel):
    script = models.OneToOneField(Script, on_delete=models.CASCADE, related_name='automation')
    trigger_event = models.CharField(max_length=100, blank=True)
    actions = models.JSONField(default=list)
    is_enabled = models.BooleanField(default=True)
    def __str__(self):
        return f"AutomationScript {self.script_id}"


class DataProcessingScript(AdvertiserPortalBaseModel):
    script = models.OneToOneField(Script, on_delete=models.CASCADE, related_name='data_processing')
    source_table = models.CharField(max_length=200, blank=True)
    batch_size = models.IntegerField(default=1000)
    def __str__(self):
        return f"DataProcessingScript {self.script_id}"


class MaintenanceScript(AdvertiserPortalBaseModel):
    script = models.OneToOneField(Script, on_delete=models.CASCADE, related_name='maintenance')
    maintenance_type = models.CharField(max_length=50)
    def __str__(self):
        return f"MaintenanceScript {self.script_id}"


class DeploymentScript(AdvertiserPortalBaseModel):
    script = models.OneToOneField(Script, on_delete=models.CASCADE, related_name='deployment')
    environment = models.CharField(max_length=20, default='production')
    requires_approval = models.BooleanField(default=True)
    def __str__(self):
        return f"DeploymentScript {self.script_id}"


class ScriptExecution(AdvertiserPortalBaseModel):
    script = models.ForeignKey(Script, on_delete=models.CASCADE, related_name='executions')
    status = models.CharField(max_length=20, default='pending', db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return f"Execution {self.script_id} [{self.status}]"


class ScriptLog(AdvertiserPortalBaseModel):
    execution = models.ForeignKey(ScriptExecution, on_delete=models.CASCADE, related_name='logs')
    level = models.CharField(max_length=10, default='INFO')
    message = models.TextField()
    logged_at = models.DateTimeField(default=timezone.now, db_index=True)
    class Meta:
        ordering = ['logged_at']
    def __str__(self):
        return f"[{self.level}] {self.message[:80]}"


class ScriptSecurity(AdvertiserPortalBaseModel):
    script = models.OneToOneField(Script, on_delete=models.CASCADE, related_name='security')
    allowed_roles = models.JSONField(default=list)
    max_concurrent_runs = models.IntegerField(default=1)
    def __str__(self):
        return f"ScriptSecurity {self.script_id}"
