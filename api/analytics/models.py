from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
from django.conf import settings


class AnalyticsEvent(models.Model):
    """
    Base model for all analytics events
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    EVENT_TYPES = (
        ('user_signup', 'User Signup'),
        ('user_login', 'User Login'),
        ('task_completed', 'Task Completed'),
        ('offer_viewed', 'Offer Viewed'),
        ('offer_completed', 'Offer Completed'),
        ('withdrawal_requested', 'Withdrawal Requested'),
        ('withdrawal_processed', 'Withdrawal Processed'),
        ('referral_joined', 'Referral Joined'),
        ('wallet_deposit', 'Wallet Deposit'),
        ('wallet_withdrawal', 'Wallet Withdrawal'),
        ('page_view', 'Page View'),
        ('button_click', 'Button Click'),
        ('api_call', 'API Call'),
        ('error_occurred', 'Error Occurred'),
        ('notification_sent', 'Notification Sent'),
        ('email_opened', 'Email Opened'),
        ('push_received', 'Push Notification Received'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='analytics_analyticsevent_user')
    session_id = models.CharField(max_length=100, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    device_type = models.CharField(max_length=50, blank=True, null=True)
    browser = models.CharField(max_length=100, blank=True, null=True)
    os = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    referrer = models.URLField(blank=True, null=True)
    
    # Event data
    metadata = models.JSONField(default=dict, blank=True)
    duration = models.FloatField(null=True, blank=True)
    value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    event_time = models.DateTimeField(default=timezone.now)
    
    class Meta:
        indexes = [
            models.Index(fields=['event_type', 'event_time'], name='idx_event_type_event_time_785'),
            models.Index(fields=['user', 'event_time'], name='idx_user_event_time_786'),
            models.Index(fields=['country', 'event_time'], name='idx_country_event_time_787'),
            models.Index(fields=['device_type', 'event_time'], name='idx_device_type_event_time_788'),
            models.Index(fields=['session_id'], name='idx_session_id_789'),
        ]
        ordering = ['-event_time']
    
    def __str__(self):
        return f"{self.event_type} - {self.user} - {self.event_time}"


class UserAnalytics(models.Model):
    """
    Aggregated user analytics data
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    PERIOD_CHOICES = (
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='analytics_useranalytics_user', null=True, blank=True)
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES, null=True, blank=True)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # User activity metrics
    login_count = models.IntegerField(default=0)
    active_days = models.IntegerField(default=0)
    session_duration_avg = models.FloatField(default=0)
    page_views = models.IntegerField(default=0)
    
    # Task metrics
    tasks_completed = models.IntegerField(default=0)
    tasks_attempted = models.IntegerField(default=0)
    task_success_rate = models.FloatField(default=0)
    
    # Offer metrics
    offers_viewed = models.IntegerField(default=0)
    offers_completed = models.IntegerField(default=0)
    offer_conversion_rate = models.FloatField(default=0)
    
    # Earning metrics
    earnings_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    earnings_from_tasks = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    earnings_from_offers = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    earnings_from_referrals = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    
    # Referral metrics
    referrals_sent = models.IntegerField(default=0)
    referrals_joined = models.IntegerField(default=0)
    referrals_active = models.IntegerField(default=0)
    referral_conversion_rate = models.FloatField(default=0)
    
    # Withdrawal metrics
    withdrawals_requested = models.IntegerField(default=0)
    withdrawals_completed = models.IntegerField(default=0)
    withdrawals_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    
    # Device metrics
    device_mobile_count = models.IntegerField(default=0)
    device_desktop_count = models.IntegerField(default=0)
    device_tablet_count = models.IntegerField(default=0)
    
    # Geographical metrics
    locations = ArrayField(models.CharField(max_length=100, null=True, blank=True), default=list, blank=True)
    
    # Additional metrics
    notifications_received = models.IntegerField(default=0)
    notifications_opened = models.IntegerField(default=0)
    support_tickets = models.IntegerField(default=0)
    app_rating = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(5)])
    
    # Retention metrics
    is_retained = models.BooleanField(default=True)
    churn_risk_score = models.FloatField(default=0)
    
    # Calculated fields
    calculated_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        unique_together = ['user', 'period', 'period_start']
        indexes = [
            models.Index(fields=['user', 'period', 'period_start'], name='idx_user_period_period_sta_416'),
            models.Index(fields=['period', 'period_start'], name='idx_period_period_start_791'),
            models.Index(fields=['earnings_total'], name='idx_earnings_total_792'),
        ]
        ordering = ['-period_start']
    
    def __str__(self):
        return f"{self.user} - {self.period} - {self.period_start.date()}"
    
    @property
    def engagement_score(self):
        score = 0.0
        
        if self.login_count > 0:
            score += min(30, (self.login_count / 30) * 30)
        
        if self.tasks_attempted > 0:
            task_score = (self.tasks_completed / self.tasks_attempted) * 30
            score += task_score
        
        if self.earnings_total > Decimal("0"):
            earnings_score = min(20, (float(self.earnings_total) / 1000) * 20)
            score += earnings_score
        
        if self.referrals_sent > 0:
            referral_score = (self.referrals_joined / self.referrals_sent) * 10
            score += referral_score
        
        if self.is_retained:
            score += 10
        
        return round(min(100, score), 2)
    
    @property
    def lifetime_value(self):
        if self.user.date_joined:
            days_since_join = (timezone.now() - self.user.date_joined).days
            if days_since_join > 0:
                daily_value = self.earnings_total / days_since_join
                return round(daily_value * 365, 2)
        return Decimal('0.00')


class RevenueAnalytics(models.Model):
    """
    Aggregated revenue analytics
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    REVENUE_SOURCES = (
        ('offer_completion', 'Offer Completion'),
        ('task_completion', 'Task Completion'),
        ('referral_commission', 'Referral Commission'),
        ('subscription', 'Subscription'),
        ('ads', 'Advertisements'),
        ('sponsorship', 'Sponsorship'),
        ('other', 'Other'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    period = models.CharField(max_length=10, choices=UserAnalytics.PERIOD_CHOICES, null=True, blank=True)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Revenue metrics
    revenue_total = models.DecimalField(max_digits=15, decimal_places=2, default=0, null=True, blank=True)
    revenue_by_source = models.JSONField(default=dict)
    
    # Cost metrics
    cost_total = models.DecimalField(max_digits=15, decimal_places=2, default=0, null=True, blank=True)
    cost_breakdown = models.JSONField(default=dict)
    
    # Profit metrics
    gross_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0, null=True, blank=True)
    net_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0, null=True, blank=True)
    profit_margin = models.FloatField(default=0)
    
    # User metrics
    active_users = models.IntegerField(default=0)
    paying_users = models.IntegerField(default=0)
    conversion_rate = models.FloatField(default=0)
    
    # ARPU/ARPPU
    arpu = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    arppu = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    
    # Withdrawal metrics
    total_withdrawals = models.DecimalField(max_digits=15, decimal_places=2, default=0, null=True, blank=True)
    withdrawal_requests = models.IntegerField(default=0)
    
    # Platform metrics
    platform_fee_earned = models.DecimalField(max_digits=15, decimal_places=2, default=0, null=True, blank=True)
    tax_deducted = models.DecimalField(max_digits=15, decimal_places=2, default=0, null=True, blank=True)
    
    # Calculated fields
    calculated_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        unique_together = ['period', 'period_start']
        indexes = [
            models.Index(fields=['period', 'period_start'], name='idx_period_period_start_793'),
            models.Index(fields=['revenue_total'], name='idx_revenue_total_794'),
            models.Index(fields=['profit_margin'], name='idx_profit_margin_795'),
        ]
        ordering = ['-period_start']
    
    def __str__(self):
        return f"Revenue - {self.period} - {self.period_start.date()}"
    
    def save(self, *args, **kwargs):
        # self.gross_profit = self.revenue_total - self.cost_total
        self.net_profit = self.gross_profit - self.tax_deducted
        
        if self.revenue_total > 0:
            self.profit_margin = (self.net_profit / self.revenue_total) * 100
        
        if self.active_users > 0:
            self.arpu = self.revenue_total / self.active_users
        
        if self.paying_users > 0:
            self.arppu = self.revenue_total / self.paying_users
        
        super().save(*args, **kwargs)


class OfferPerformanceAnalytics(models.Model):
    """
    Analytics for offer performance
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # [OK] সঠিক string reference ব্যবহার করা হয়েছে
    offer = models.ForeignKey(
        'offerwall.Offer',  # [OK] শুধু app_label.ModelName
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_tenant',
        null=True,
        blank=True
    )
    
    period = models.CharField(max_length=10, choices=UserAnalytics.PERIOD_CHOICES, null=True, blank=True)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # View metrics
    impressions = models.IntegerField(default=0)
    unique_views = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    
    # Completion metrics
    completions = models.IntegerField(default=0)
    completion_rate = models.FloatField(default=0)
    
    # Revenue metrics
    revenue_generated = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    cost_per_completion = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    roi = models.FloatField(default=0)
    
    # User metrics
    unique_users_completed = models.IntegerField(default=0)
    avg_completion_time = models.FloatField(default=0)
    
    # Device breakdown
    device_breakdown = models.JSONField(default=dict)
    
    # Geographical breakdown
    country_breakdown = models.JSONField(default=dict)

    # Time metrics
    peak_hours = ArrayField(models.IntegerField(), default=list, blank=True)
    
    # Calculated fields
    calculated_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['offer', 'period', 'period_start'], name='idx_offer_period_period_st_a27'),
            models.Index(fields=['completion_rate'], name='idx_completion_rate_797'),
            models.Index(fields=['roi'], name='idx_roi_798'),
        ]
        ordering = ['-period_start']
    
    def __str__(self):
        if self.offer:
            return f"{self.offer.title} - {self.period} - {self.period_start.date()}"
        return f"Offer Analytics - {self.period} - {self.period_start.date()}"
    
    @property
    def click_through_rate(self):
        if self.impressions > 0:
            return (self.clicks / self.impressions) * 100
        return 0.0
    
    @property
    def engagement_rate(self):
        if self.unique_views > 0:
            return (self.completions / self.unique_views) * 100
        return 0.0


class FunnelAnalytics(models.Model):
    """
    Conversion funnel analytics
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    FUNNEL_TYPES = (
        ('user_signup', 'User Signup'),
        ('offer_completion', 'Offer Completion'),
        ('withdrawal', 'Withdrawal'),
        ('referral', 'Referral'),
        ('premium_upgrade', 'Premium Upgrade'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    funnel_type = models.CharField(max_length=50, choices=FUNNEL_TYPES, null=True, blank=True)
    period = models.CharField(max_length=10, choices=UserAnalytics.PERIOD_CHOICES, null=True, blank=True)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Funnel stages
    stages = models.JSONField(default=dict)
    
    # Conversion metrics
    total_entered = models.IntegerField(default=0)
    total_converted = models.IntegerField(default=0)
    conversion_rate = models.FloatField(default=0)
    
    # Drop-off points
    drop_off_points = models.JSONField(default=dict)
    
    # Time metrics
    avg_time_to_convert = models.FloatField(default=0)
    median_time_to_convert = models.FloatField(default=0)
    
    # User segment breakdown
    segment_breakdown = models.JSONField(default=dict)
    
    # Calculated fields
    calculated_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        unique_together = ['funnel_type', 'period', 'period_start']
        indexes = [
            models.Index(fields=['funnel_type', 'period', 'period_start'], name='idx_funnel_type_period_per_c06'),
            models.Index(fields=['conversion_rate'], name='idx_conversion_rate_800'),
        ]
        ordering = ['-period_start']
    
    def __str__(self):
        return f"{self.funnel_type} - {self.period} - {self.period_start.date()}"


class RetentionAnalytics(models.Model):
    """
    User retention analytics
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    COHORT_TYPES = (
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cohort_type = models.CharField(max_length=10, choices=COHORT_TYPES, null=True, blank=True)
    cohort_date = models.DateField()
    total_users = models.IntegerField(default=0)
    
    # Retention rates
    retention_day_1 = models.FloatField(default=0)
    retention_day_3 = models.FloatField(default=0)
    retention_day_7 = models.FloatField(default=0)
    retention_day_14 = models.FloatField(default=0)
    retention_day_30 = models.FloatField(default=0)
    retention_day_60 = models.FloatField(default=0)
    retention_day_90 = models.FloatField(default=0)
    
    # Activity metrics
    active_users_by_period = models.JSONField(default=dict)
    
    # Revenue metrics
    revenue_by_user = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    ltv = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    
    # Churn metrics
    churned_users = models.IntegerField(default=0)
    churn_rate = models.FloatField(default=0)
    
    # Calculated fields
    calculated_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        unique_together = ['cohort_type', 'cohort_date']
        indexes = [
            models.Index(fields=['cohort_type', 'cohort_date'], name='idx_cohort_type_cohort_dat_9c1'),
            models.Index(fields=['retention_day_7'], name='idx_retention_day_7_802'),
        ]
        ordering = ['-cohort_date']
    
    def __str__(self):
        return f"Cohort {self.cohort_date} - {self.cohort_type}"


class Dashboard(models.Model):
    """
    Dashboard configuration
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    DASHBOARD_TYPES = (
        ('admin', 'Admin Dashboard'),
        ('user', 'User Dashboard'),
        ('realtime', 'Real-time Dashboard'),
        ('financial', 'Financial Dashboard'),
        ('marketing', 'Marketing Dashboard'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, null=True, blank=True)
    dashboard_type = models.CharField(max_length=20, choices=DASHBOARD_TYPES, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    
    # Dashboard configuration
    layout_config = models.JSONField(default=dict)
    widget_configs = models.JSONField(default=list)
    
    # Access control
    is_public = models.BooleanField(default=False)
    # allowed_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='analytics_dashboard_tenant')
    allowed_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='analytics_dashboard_allowed_users')
    allowed_roles = ArrayField(models.CharField(max_length=50, null=True, blank=True), default=list, blank=True)
    
    # Settings
    refresh_interval = models.IntegerField(default=300)
    default_time_range = models.CharField(max_length=50, default='last_7_days', null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='analytics_dashboard_created_by')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Dashboards'
    
    def __str__(self):
        return f"{self.name} ({self.dashboard_type})"


class Report(models.Model):
    """
    Generated reports
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    REPORT_TYPES = (
        ('daily_summary', 'Daily Summary'),
        ('weekly_analytics', 'Weekly Analytics'),
        ('monthly_earnings', 'Monthly Earnings'),
        ('user_activity', 'User Activity'),
        ('revenue_report', 'Revenue Report'),
        ('offer_performance', 'Offer Performance'),
        ('referral_report', 'Referral Report'),
        ('custom', 'Custom Report'),
    )
    
    FORMAT_CHOICES = (
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('html', 'HTML'),
        ('json', 'JSON'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, null=True, blank=True)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES, null=True, blank=True)
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES, null=True, blank=True)
    
    # Report data
    parameters = models.JSONField(default=dict)
    data = models.JSONField(default=dict)

    # File storage
    file = models.FileField(upload_to='reports/%Y/%m/%d/', null=True, blank=True)
    file_size = models.IntegerField(null=True, blank=True)
    file_url = models.URLField(blank=True, null=True)
    
    # Generation info
    generated_at = models.DateTimeField(auto_now_add=True)
    generation_duration = models.FloatField(null=True, blank=True)
    generated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, related_name='%(app_label)s_%(class)s_tenant')
    
    # Status
    status = models.CharField(max_length=20, default='completed', choices=(
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ))
    
    # Delivery
    email_sent = models.BooleanField(default=False)
    email_recipients = ArrayField(models.EmailField(), default=list, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['report_type', 'generated_at'], name='idx_report_type_generated__deb'),
            models.Index(fields=['generated_by', 'generated_at'], name='idx_generated_by_generated_1b0'),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.report_type} - {self.generated_at.date()}"
    
    @property
    def download_url(self):
        if self.file:
            return self.file.url
        return self.file_url


class RealTimeMetric(models.Model):
    """
    Real-time metrics for monitoring
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    METRIC_TYPES = (
        ('active_users', 'Active Users'),
        ('concurrent_tasks', 'Concurrent Tasks'),
        ('revenue_per_minute', 'Revenue Per Minute'),
        ('api_requests', 'API Requests'),
        ('error_rate', 'Error Rate'),
        ('response_time', 'Response Time'),
        ('queue_size', 'Queue Size'),
        ('server_load', 'Server Load'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    metric_type = models.CharField(max_length=50, choices=METRIC_TYPES, null=True, blank=True)
    value = models.FloatField()
    unit = models.CharField(max_length=50, default='count', null=True, blank=True)
    
    # Dimensions
    dimension = models.CharField(max_length=100, blank=True, null=True)
    dimension_value = models.CharField(max_length=200, blank=True, null=True)
    
    # Timestamp
    recorded_at = models.DateTimeField(auto_now_add=True)
    metric_time = models.DateTimeField(default=timezone.now)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['metric_type', 'metric_time'], name='idx_metric_type_metric_tim_672'),
            models.Index(fields=['metric_time'], name='idx_metric_time_806'),
        ]
        ordering = ['-metric_time']
    
    def __str__(self):
        return f"{self.metric_type}: {self.value} {self.unit} at {self.metric_time}"


class AlertRule(models.Model):
    """
    Alert rules for monitoring
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    ALERT_TYPES = (
        ('threshold', 'Threshold Alert'),
        ('anomaly', 'Anomaly Detection'),
        ('pattern', 'Pattern Alert'),
    )
    
    SEVERITY_LEVELS = (
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES, null=True, blank=True)
    
    # Condition configuration
    metric_type = models.CharField(max_length=50, choices=RealTimeMetric.METRIC_TYPES, null=True, blank=True)
    condition = models.CharField(max_length=20, choices=(
        ('greater_than', 'Greater Than'),
        ('less_than', 'Less Than'),
        ('equal_to', 'Equal To'),
        ('not_equal', 'Not Equal'),
        ('in_range', 'In Range'),
        ('out_of_range', 'Out of Range'),
    ))
    threshold_value = models.FloatField()
    threshold_value_2 = models.FloatField(null=True, blank=True)
    
    # Time window
    time_window = models.IntegerField(default=300)
    evaluation_interval = models.IntegerField(default=60)
    
    # Alert settings
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='warning', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    cooldown_period = models.IntegerField(default=300)
    
    # Notification settings
    notify_email = models.BooleanField(default=True)
    notify_slack = models.BooleanField(default=False)
    notify_webhook = models.BooleanField(default=False)
    
    # Recipients
    email_recipients = ArrayField(models.EmailField(), default=list, blank=True)
    slack_webhook = models.URLField(blank=True, null=True)
    webhook_url = models.URLField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.severity})"


class AlertHistory(models.Model):
    """
    History of triggered alerts
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name='%(app_label)s_%(class)s_tenant')
    severity = models.CharField(max_length=20, choices=AlertRule.SEVERITY_LEVELS, null=True, blank=True)
    
    # Alert data
    metric_value = models.FloatField()
    threshold_value = models.FloatField()
    condition_met = models.TextField()
    
    # Resolution
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True)
    resolution_notes = models.TextField(blank=True, null=True)
    
    # Notifications
    email_sent = models.BooleanField(default=False)
    slack_sent = models.BooleanField(default=False)
    webhook_sent = models.BooleanField(default=False)
    
    # Timestamps
    triggered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-triggered_at']
        indexes = [
            models.Index(fields=['rule', 'triggered_at'], name='idx_rule_triggered_at_807'),
            models.Index(fields=['is_resolved', 'triggered_at'], name='idx_is_resolved_triggered__ebb'),
        ]
    
    def __str__(self):
        return f"Alert: {self.rule.name} at {self.triggered_at}"