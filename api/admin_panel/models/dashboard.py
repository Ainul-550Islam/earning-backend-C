# api/admin_panel/models/dashboard.py
"""
Dashboard-related models:
  - DashboardWidget
  - DashboardLayout
  - DashboardMetric
  - DashboardAlert
  - QuickAction
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class DashboardWidget(models.Model):
    """
    Individual widget on a user's dashboard.
    Supports drag-and-drop positioning via position JSON.
    """
    WIDGET_TYPE_CHOICES = [
        ('stat_card', 'Stat Card'),
        ('line_chart', 'Line Chart'),
        ('bar_chart', 'Bar Chart'),
        ('pie_chart', 'Pie Chart'),
        ('donut_chart', 'Donut Chart'),
        ('area_chart', 'Area Chart'),
        ('table', 'Data Table'),
        ('recent_activity', 'Recent Activity'),
        ('quick_actions', 'Quick Actions'),
        ('calendar', 'Calendar'),
        ('map', 'Map'),
        ('funnel', 'Funnel Chart'),
        ('gauge', 'Gauge'),
        ('text', 'Text Block'),
        ('custom', 'Custom HTML'),
    ]

    SIZE_CHOICES = [
        ('sm', 'Small (1/4)'),
        ('md', 'Medium (1/2)'),
        ('lg', 'Large (3/4)'),
        ('xl', 'Full Width'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dashboard_widgets',
        verbose_name=_('User'),
    )
    title = models.CharField(max_length=200, verbose_name=_('Title'))
    widget_type = models.CharField(
        max_length=30,
        choices=WIDGET_TYPE_CHOICES,
        default='stat_card',
        verbose_name=_('Widget Type'),
    )
    config = models.JSONField(
        default=dict, blank=True,
        verbose_name=_('Config'),
        help_text=_('Widget-specific configuration (data source, colors, etc.)'),
    )
    position = models.JSONField(
        default=dict, blank=True,
        verbose_name=_('Position'),
        help_text=_('Grid position: {x, y, w, h}'),
    )
    size = models.CharField(
        max_length=5,
        choices=SIZE_CHOICES,
        default='md',
        verbose_name=_('Size'),
    )
    is_visible = models.BooleanField(default=True, verbose_name=_('Is Visible'))
    refresh_interval = models.IntegerField(
        default=300,
        verbose_name=_('Refresh Interval (seconds)'),
        help_text=_('How often to auto-refresh widget data. 0 = manual only.'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Dashboard Widget')
        verbose_name_plural = _('Dashboard Widgets')
        ordering = ['user', 'position']

    def __str__(self):
        return f"{self.title} ({self.widget_type}) — {self.user.username}"


class DashboardLayout(models.Model):
    """
    Saved dashboard layout (grid arrangement) for a user.
    Multiple layouts per user; one can be default.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dashboard_layouts',
        verbose_name=_('User'),
    )
    name = models.CharField(max_length=100, default='Default Layout', verbose_name=_('Name'))
    layout = models.JSONField(
        default=dict, blank=True,
        verbose_name=_('Layout'),
        help_text=_('Full grid layout JSON: list of {widgetId, x, y, w, h}'),
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name=_('Is Default'),
        help_text=_('This layout is loaded by default for this user'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Dashboard Layout')
        verbose_name_plural = _('Dashboard Layouts')
        ordering = ['-is_default', 'name']

    def __str__(self):
        default_str = ' (default)' if self.is_default else ''
        return f"{self.name}{default_str} — {self.user.username}"

    def save(self, *args, **kwargs):
        # Ensure only one default layout per user
        if self.is_default:
            DashboardLayout.objects.filter(
                user=self.user, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class DashboardMetric(models.Model):
    """
    Cached KPI metric value for dashboard display.
    Updated periodically by background tasks.
    """
    PERIOD_CHOICES = [
        ('realtime', 'Real-time'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]

    metric_key = models.CharField(
        max_length=100, db_index=True,
        verbose_name=_('Metric Key'),
        help_text=_('Unique identifier for this metric, e.g. total_users'),
    )
    label = models.CharField(max_length=200, verbose_name=_('Label'))
    value = models.DecimalField(
        max_digits=20, decimal_places=4,
        verbose_name=_('Current Value'),
    )
    previous_value = models.DecimalField(
        max_digits=20, decimal_places=4,
        null=True, blank=True,
        verbose_name=_('Previous Value'),
        help_text=_('Value from the previous period for comparison'),
    )
    unit = models.CharField(
        max_length=20, blank=True,
        verbose_name=_('Unit'),
        help_text=_('e.g. users, BDT, %'),
    )
    period = models.CharField(
        max_length=20,
        choices=PERIOD_CHOICES,
        default='daily',
        verbose_name=_('Period'),
    )
    metadata = models.JSONField(
        default=dict, blank=True,
        verbose_name=_('Metadata'),
        help_text=_('Extra data (chart data, breakdown, etc.)'),
    )
    cached_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Cached At'),
    )

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Dashboard Metric')
        verbose_name_plural = _('Dashboard Metrics')
        unique_together = [('metric_key', 'period')]
        ordering = ['metric_key']

    def __str__(self):
        return f"{self.label}: {self.value} ({self.period})"

    @property
    def change_percentage(self):
        """Calculate percentage change vs previous period."""
        if self.previous_value is None or self.previous_value == 0:
            return None
        try:
            change = ((float(self.value) - float(self.previous_value)) / abs(float(self.previous_value))) * 100
            return round(change, 2)
        except (ZeroDivisionError, TypeError):
            return None

    @property
    def is_stale(self) -> bool:
        """Check if metric data is older than 10 minutes."""
        from datetime import timedelta
        return (timezone.now() - self.cached_at) > timedelta(minutes=10)


class DashboardAlert(models.Model):
    """
    Alert rule that fires when a metric crosses a threshold.
    """
    OPERATOR_CHOICES = [
        ('gt', 'Greater Than'),
        ('gte', 'Greater Than or Equal'),
        ('lt', 'Less Than'),
        ('lte', 'Less Than or Equal'),
        ('eq', 'Equal'),
        ('neq', 'Not Equal'),
    ]

    metric = models.ForeignKey(
        DashboardMetric,
        on_delete=models.CASCADE,
        related_name='alerts',
        verbose_name=_('Metric'),
    )
    label = models.CharField(max_length=200, verbose_name=_('Alert Label'))
    threshold = models.DecimalField(
        max_digits=20, decimal_places=4,
        verbose_name=_('Threshold'),
    )
    operator = models.CharField(
        max_length=5,
        choices=OPERATOR_CHOICES,
        default='gt',
        verbose_name=_('Operator'),
    )
    is_active = models.BooleanField(default=True, verbose_name=_('Is Active'))
    notify_admins = models.BooleanField(
        default=True,
        verbose_name=_('Notify Admins'),
        help_text=_('Send email/notification to admin users when triggered'),
    )
    last_triggered = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_('Last Triggered'),
    )
    trigger_count = models.IntegerField(default=0, verbose_name=_('Trigger Count'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Dashboard Alert')
        verbose_name_plural = _('Dashboard Alerts')
        ordering = ['-is_active', 'label']

    def __str__(self):
        return f"{self.label}: {self.metric.metric_key} {self.operator} {self.threshold}"

    def check_condition(self, current_value) -> bool:
        """Evaluate the alert condition against a current value."""
        try:
            val = float(current_value)
            thresh = float(self.threshold)
            ops = {
                'gt': val > thresh,
                'gte': val >= thresh,
                'lt': val < thresh,
                'lte': val <= thresh,
                'eq': val == thresh,
                'neq': val != thresh,
            }
            return ops.get(self.operator, False)
        except (TypeError, ValueError):
            return False

    def trigger(self):
        """Mark alert as triggered."""
        self.last_triggered = timezone.now()
        self.trigger_count += 1
        self.save(update_fields=['last_triggered', 'trigger_count'])


class QuickAction(models.Model):
    """
    Configurable quick action button on the dashboard.
    Links to admin URLs or API endpoints.
    """
    label = models.CharField(max_length=100, verbose_name=_('Label'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    icon = models.CharField(
        max_length=50, blank=True,
        verbose_name=_('Icon'),
        help_text=_('Icon class name, e.g. "mdi:account-plus" or "heroicon:user"'),
    )
    url = models.CharField(
        max_length=500,
        verbose_name=_('URL or Path'),
        help_text=_('Relative URL or admin path to navigate to'),
    )
    permission_required = models.CharField(
        max_length=100, blank=True,
        verbose_name=_('Permission Required'),
        help_text=_('Django permission codename required to see this action'),
    )
    sort_order = models.IntegerField(default=0, verbose_name=_('Sort Order'))
    is_active = models.BooleanField(default=True, verbose_name=_('Is Active'))
    open_in_new_tab = models.BooleanField(default=False, verbose_name=_('Open in New Tab'))
    color = models.CharField(
        max_length=20, blank=True, default='primary',
        verbose_name=_('Color'),
        help_text=_('Button color: primary, success, danger, warning, info'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Quick Action')
        verbose_name_plural = _('Quick Actions')
        ordering = ['sort_order', 'label']

    def __str__(self):
        return f"QuickAction({self.label})"