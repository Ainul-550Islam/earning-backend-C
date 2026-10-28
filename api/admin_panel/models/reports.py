# api/admin_panel/models/reports.py
"""
Report & insight models:
  - ReportDefinition
  - ReportSchedule
  - ReportExport
  - AdminInsight
  - DataExport
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import uuid


class ReportDefinition(models.Model):
    """
    Reusable report template/definition.
    Stores query config, columns, and default filters.
    CPAlead-style: user earnings report, withdrawal summary, referral stats, etc.
    """
    REPORT_TYPE_CHOICES = [
        ('user', 'User Report'),
        ('payment', 'Payment Report'),
        ('revenue', 'Revenue Report'),
        ('activity', 'Activity Report'),
        ('withdrawal', 'Withdrawal Report'),
        ('referral', 'Referral Report'),
        ('earning', 'Earning Report'),
        ('fraud', 'Fraud Report'),
        ('system', 'System Report'),
        ('custom', 'Custom Report'),
    ]

    name = models.CharField(max_length=200, verbose_name=_('Report Name'))
    report_type = models.CharField(
        max_length=20,
        choices=REPORT_TYPE_CHOICES,
        default='custom',
        verbose_name=_('Report Type'),
    )
    description = models.TextField(blank=True, verbose_name=_('Description'))
    query_config = models.JSONField(
        default=dict, blank=True,
        verbose_name=_('Query Config'),
        help_text=_('Django ORM filter dict or raw SQL config'),
    )
    columns = models.JSONField(
        default=list, blank=True,
        verbose_name=_('Columns'),
        help_text=_('List of column definitions: [{field, label, format}]'),
    )
    filters = models.JSONField(
        default=dict, blank=True,
        verbose_name=_('Default Filters'),
        help_text=_('Default filter values for this report'),
    )
    allowed_formats = models.JSONField(
        default=list, blank=True,
        verbose_name=_('Allowed Formats'),
        help_text=_('Allowed export formats: csv, xlsx, pdf, json'),
    )
    is_active = models.BooleanField(default=True, verbose_name=_('Is Active'))
    is_system = models.BooleanField(
        default=False,
        verbose_name=_('Is System'),
        help_text=_('System reports cannot be deleted'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='report_definitions_created',
        verbose_name=_('Created By'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Report Definition')
        verbose_name_plural = _('Report Definitions')
        ordering = ['report_type', 'name']

    def __str__(self):
        return f"{self.name} ({self.report_type})"

    def delete(self, *args, **kwargs):
        if self.is_system:
            raise PermissionError("System report definitions cannot be deleted.")
        super().delete(*args, **kwargs)


class ReportSchedule(models.Model):
    """
    Scheduled automatic report generation.
    Uses cron expressions. Sends to recipient emails on completion.
    """
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('xlsx', 'Excel'),
        ('pdf', 'PDF'),
        ('json', 'JSON'),
    ]

    report = models.ForeignKey(
        ReportDefinition,
        on_delete=models.CASCADE,
        related_name='schedules',
        verbose_name=_('Report'),
    )
    name = models.CharField(max_length=200, verbose_name=_('Schedule Name'))
    cron_expr = models.CharField(
        max_length=100,
        verbose_name=_('Cron Expression'),
        help_text=_('Standard 5-part cron expression. E.g. "0 8 * * *" = 8 AM daily'),
    )
    recipients = models.JSONField(
        default=list,
        verbose_name=_('Recipients'),
        help_text=_('List of email addresses to send report to'),
    )
    format = models.CharField(
        max_length=10,
        choices=FORMAT_CHOICES,
        default='csv',
        verbose_name=_('Export Format'),
    )
    extra_filters = models.JSONField(
        default=dict, blank=True,
        verbose_name=_('Extra Filters'),
        help_text=_('Additional runtime filters to apply for this schedule'),
    )
    is_active = models.BooleanField(default=True, verbose_name=_('Is Active'))
    last_run_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_('Last Run At'),
    )
    next_run_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_('Next Run At'),
    )
    run_count = models.IntegerField(default=0, verbose_name=_('Run Count'))
    failure_count = models.IntegerField(default=0, verbose_name=_('Failure Count'))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='report_schedules_created',
        verbose_name=_('Created By'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Report Schedule')
        verbose_name_plural = _('Report Schedules')
        ordering = ['-is_active', 'name']

    def __str__(self):
        status = '✅' if self.is_active else '❌'
        return f"{status} {self.name} [{self.cron_expr}] → {self.report.name}"

    def record_run(self, success: bool = True):
        """Update run stats after each execution."""
        self.last_run_at = timezone.now()
        self.run_count += 1
        if not success:
            self.failure_count += 1
        self.save(update_fields=['last_run_at', 'run_count', 'failure_count'])


class ReportExport(models.Model):
    """
    A single generated report export file.
    Linked to a ReportDefinition; downloaded once ready.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('xlsx', 'Excel'),
        ('pdf', 'PDF'),
        ('json', 'JSON'),
    ]

    export_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False,
        verbose_name=_('Export ID'),
    )
    report = models.ForeignKey(
        ReportDefinition,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='exports',
        verbose_name=_('Report Definition'),
    )
    report_schedule = models.ForeignKey(
        ReportSchedule,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='exports',
        verbose_name=_('Report Schedule'),
    )
    title = models.CharField(max_length=300, blank=True, verbose_name=_('Title'))
    file_path = models.CharField(
        max_length=500, blank=True,
        verbose_name=_('File Path'),
    )
    file_url = models.CharField(
        max_length=500, blank=True,
        verbose_name=_('File URL'),
    )
    format = models.CharField(
        max_length=10,
        choices=FORMAT_CHOICES,
        default='csv',
        verbose_name=_('Format'),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_('Status'),
    )
    row_count = models.IntegerField(default=0, verbose_name=_('Row Count'))
    file_size_bytes = models.BigIntegerField(default=0, verbose_name=_('File Size (bytes)'))
    error_message = models.TextField(blank=True, verbose_name=_('Error Message'))
    applied_filters = models.JSONField(
        default=dict, blank=True,
        verbose_name=_('Applied Filters'),
    )
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='report_exports',
        verbose_name=_('Generated By'),
    )
    expires_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_('Expires At'),
        help_text=_('When the download link expires and the file is deleted'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Report Export')
        verbose_name_plural = _('Report Exports')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['generated_by', 'status']),
        ]

    def __str__(self):
        report_name = self.report.name if self.report else 'Custom'
        return f"{report_name} Export [{self.status}] — {self.created_at:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        # Auto-set expiry on completion
        if self.status == 'completed' and not self.expires_at:
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(days=7)
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    @property
    def file_size_human(self) -> str:
        """Human-readable file size."""
        size = self.file_size_bytes
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class AdminInsight(models.Model):
    """
    AI-powered admin insights.
    Generated daily by insight tasks; shown on dashboard.
    CPAlead-style: fraud spikes, earning anomalies, top referrers, withdrawal trends.
    """
    TYPE_CHOICES = [
        ('anomaly', 'Anomaly Detection'),
        ('trend', 'Trend Analysis'),
        ('recommendation', 'Recommendation'),
        ('alert', 'System Alert'),
        ('summary', 'Daily Summary'),
        ('prediction', 'Prediction'),
        ('performance', 'Performance'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    insight_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False,
        verbose_name=_('Insight ID'),
    )
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='summary',
        verbose_name=_('Type'),
    )
    title = models.CharField(max_length=300, verbose_name=_('Title'))
    body = models.TextField(verbose_name=_('Body'))
    data = models.JSONField(
        default=dict, blank=True,
        verbose_name=_('Data'),
        help_text=_('Supporting data/metrics for this insight'),
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium',
        verbose_name=_('Priority'),
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name=_('Is Read'),
    )
    is_dismissed = models.BooleanField(
        default=False,
        verbose_name=_('Is Dismissed'),
    )
    action_url = models.CharField(
        max_length=500, blank=True,
        verbose_name=_('Action URL'),
        help_text=_('Admin URL to navigate to for more details'),
    )
    action_label = models.CharField(
        max_length=100, blank=True,
        verbose_name=_('Action Label'),
        help_text=_('CTA button label, e.g. "View Withdrawals"'),
    )
    expires_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_('Expires At'),
    )
    generated_by_task = models.CharField(
        max_length=200, blank=True,
        verbose_name=_('Generated By Task'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Admin Insight')
        verbose_name_plural = _('Admin Insights')
        ordering = [
            models.Case(
                models.When(priority='critical', then=0),
                models.When(priority='high', then=1),
                models.When(priority='medium', then=2),
                models.When(priority='low', then=3),
                default=4,
                output_field=models.IntegerField(),
            ),
            '-created_at',
        ]

    def __str__(self):
        return f"[{self.priority.upper()}] {self.title} ({self.type})"

    @property
    def is_expired(self) -> bool:
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    @property
    def priority_color(self) -> str:
        """Return color class for UI rendering."""
        colors = {
            'critical': 'danger',
            'high': 'warning',
            'medium': 'info',
            'low': 'secondary',
        }
        return colors.get(self.priority, 'secondary')

    def mark_read(self):
        self.is_read = True
        self.save(update_fields=['is_read'])

    def dismiss(self):
        self.is_dismissed = True
        self.save(update_fields=['is_dismissed'])


class DataExport(models.Model):
    """
    Async data export for any model.
    Admin selects model + filters → background task generates file → download.
    CPAlead-style: export all users, export withdrawals, export earnings, etc.
    """
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    ]

    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('xlsx', 'Excel'),
        ('json', 'JSON'),
    ]

    export_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False,
        verbose_name=_('Export ID'),
    )
    model_name = models.CharField(
        max_length=100, db_index=True,
        verbose_name=_('Model Name'),
        help_text=_('App.ModelName e.g. users.UserProfile'),
    )
    label = models.CharField(
        max_length=200, blank=True,
        verbose_name=_('Label'),
        help_text=_('Human-friendly export label'),
    )
    filters = models.JSONField(
        default=dict, blank=True,
        verbose_name=_('Filters'),
        help_text=_('Django ORM filter kwargs, e.g. {"status": "pending", "created_at__gte": "2024-01-01"}'),
    )
    selected_fields = models.JSONField(
        default=list, blank=True,
        verbose_name=_('Selected Fields'),
        help_text=_('Fields to include. Empty = all fields.'),
    )
    format = models.CharField(
        max_length=10,
        choices=FORMAT_CHOICES,
        default='csv',
        verbose_name=_('Format'),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='queued',
        verbose_name=_('Status'),
    )
    file_path = models.CharField(max_length=500, blank=True, verbose_name=_('File Path'))
    file_url = models.CharField(max_length=500, blank=True, verbose_name=_('File URL'))
    file_size_bytes = models.BigIntegerField(default=0, verbose_name=_('File Size (bytes)'))
    row_count = models.IntegerField(default=0, verbose_name=_('Row Count'))
    error_message = models.TextField(blank=True, verbose_name=_('Error Message'))
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='admin_panel_data_exports',
        verbose_name=_('Requested By'),
    )
    task_id = models.CharField(
        max_length=200, blank=True,
        verbose_name=_('Celery Task ID'),
    )
    expires_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_('Expires At'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Data Export')
        verbose_name_plural = _('Data Exports')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['requested_by', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        by = self.requested_by.username if self.requested_by else 'N/A'
        return f"{self.model_name} Export [{self.status}] by {by}"

    def save(self, *args, **kwargs):
        if self.status == 'ready' and not self.expires_at:
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(days=3)
        if self.status in ('ready', 'failed') and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    @property
    def file_size_human(self) -> str:
        size = self.file_size_bytes
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def mark_processing(self, task_id: str = ''):
        self.status = 'processing'
        self.task_id = task_id
        self.save(update_fields=['status', 'task_id'])

    def mark_ready(self, file_path: str, file_url: str, file_size: int, row_count: int):
        self.status = 'ready'
        self.file_path = file_path
        self.file_url = file_url
        self.file_size_bytes = file_size
        self.row_count = row_count
        self.completed_at = timezone.now()
        self.save()

    def mark_failed(self, error: str):
        self.status = 'failed'
        self.error_message = error
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'completed_at'])