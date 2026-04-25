"""
Audit Log Models for tracking all user and system activities
"""

from django.db import models
from django.contrib.postgres.operations import BtreeGinExtension
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
import uuid
import json
from django.conf import settings

from core.models import TimeStampedModel

User = get_user_model()

class AuditLogLevel(models.TextChoices):
    """Log severity levels"""
    DEBUG = 'DEBUG', 'Debug'
    INFO = 'INFO', 'Information'
    WARNING = 'WARNING', 'Warning'
    ERROR = 'ERROR', 'Error'
    CRITICAL = 'CRITICAL', 'Critical'
    SECURITY = 'SECURITY', 'Security'


class AuditLogAction(models.TextChoices):
    """Types of audit actions"""
    # User actions
    LOGIN = 'LOGIN', 'User Login'
    LOGOUT = 'LOGOUT', 'User Logout'
    REGISTER = 'REGISTER', 'User Registration'
    PROFILE_UPDATE = 'PROFILE_UPDATE', 'Profile Update'
    PASSWORD_CHANGE = 'PASSWORD_CHANGE', 'Password Change'
    
    # Financial actions
    DEPOSIT = 'DEPOSIT', 'Deposit'
    WITHDRAWAL = 'WITHDRAWAL', 'Withdrawal'
    WALLET_TRANSFER = 'WALLET_TRANSFER', 'Wallet Transfer'
    
    # Offer actions
    OFFER_VIEW = 'OFFER_VIEW', 'Offer View'
    OFFER_CLICK = 'OFFER_CLICK', 'Offer Click'
    OFFER_COMPLETE = 'OFFER_COMPLETE', 'Offer Complete'
    OFFER_REJECT = 'OFFER_REJECT', 'Offer Rejection'
    
    # Admin actions
    USER_BAN = 'USER_BAN', 'User Ban'
    USER_UNBAN = 'USER_UNBAN', 'User Unban'
    MANUAL_CREDIT = 'MANUAL_CREDIT', 'Manual Credit'
    MANUAL_DEBIT = 'MANUAL_DEBIT', 'Manual Debit'
    
    # System actions
    SYSTEM_ALERT = 'SYSTEM_ALERT', 'System Alert'
    BACKUP = 'BACKUP', 'Database Backup'
    MAINTENANCE = 'MAINTENANCE', 'System Maintenance'
    
    # Security actions
    SUSPICIOUS_LOGIN = 'SUSPICIOUS_LOGIN', 'Suspicious Login'
    BRUTE_FORCE_ATTEMPT = 'BRUTE_FORCE_ATTEMPT', 'Brute Force Attempt'
    IP_BLOCK = 'IP_BLOCK', 'IP Blocked'
    
    # KYC actions
    KYC_SUBMIT = 'KYC_SUBMIT', 'KYC Submission'
    KYC_APPROVE = 'KYC_APPROVE', 'KYC Approval'
    KYC_REJECT = 'KYC_REJECT', 'KYC Rejection'
    
    # Referral actions
    REFERRAL_SIGNUP = 'REFERRAL_SIGNUP', 'Referral Signup'
    REFERRAL_BONUS = 'REFERRAL_BONUS', 'Referral Bonus'
    
    # API actions
    API_CALL = 'API_CALL', 'API Call'
    RATE_LIMIT = 'RATE_LIMIT', 'Rate Limit Exceeded'


class AuditLog(models.Model):
    """Main audit log model"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP Address")
    
    # User information
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='audit_logs_auditlog_user')
    anonymous_id = models.CharField(max_length=100, blank=True, null=True)
    user_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    session_id = models.CharField(max_length=100, blank=True, null=True)
    device_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Action details
    action = models.CharField(max_length=50, choices=AuditLogAction.choices, null=True, blank=True)
    level = models.CharField(max_length=10, choices=AuditLogLevel.choices, default=AuditLogLevel.INFO, null=True, blank=True)
    
    # Resource being acted upon
    resource_type = models.CharField(max_length=100, blank=True, null=True)  # e.g., 'User', 'Wallet', 'Offer'
    resource_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Generic foreign key for any model
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.CharField(max_length=100, null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Message and data
    message = models.TextField()
    old_data = models.JSONField(null=True, blank=True)  # Data before change
    new_data = models.JSONField(null=True, blank=True)  # Data after change
    metadata = models.JSONField(default=dict)  # Additional context
    
    # Status and response
    status_code = models.IntegerField(null=True, blank=True)  # HTTP status code
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, null=True)
    stack_trace = models.TextField(blank=True, null=True)
    
    # Request information
    request_method = models.CharField(max_length=10, blank=True, null=True)
    request_path = models.TextField(blank=True, null=True)
    request_params = models.JSONField(null=True, blank=True)
    request_headers = models.JSONField(null=True, blank=True)
    request_body = models.JSONField(null=True, blank=True)
    
    # Response information
    response_body = models.JSONField(null=True, blank=True)
    response_time_ms = models.IntegerField(null=True, blank=True)  # Response time in milliseconds
    
    # Location information
    country = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Relationships
    parent_log = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant'
    )
    correlation_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    # Retention
    retention_days = models.IntegerField(default=365)  # Default 1 year retention
    archived = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'audit_logs'
        indexes = [
            models.Index(fields=['action', 'timestamp'], name='idx_action_timestamp_809'),
            models.Index(fields=['user_id', 'timestamp'], name='idx_user_id_timestamp_810'),
            models.Index(fields=['resource_type', 'resource_id'], name='idx_resource_type_resource_fd0'),
            models.Index(fields=['correlation_id'], name='idx_correlation_id_812'),
            models.Index(fields=['user_ip', 'timestamp'], name='idx_user_ip_timestamp_813'),
            models.Index(fields=['level', 'timestamp'], name='idx_level_timestamp_814'),
            models.Index(fields=['created_at'], name='idx_created_at_815'),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.user} - {self.timestamp}"
    
    def save(self, *args, **kwargs):
        # Compress JSON data if too large
        if self.request_body and len(str(self.request_body)) > 10000:
            self.request_body = {'compressed': True, 'size': len(str(self.request_body))}
        
        if self.response_body and len(str(self.response_body)) > 10000:
            self.response_body = {'compressed': True, 'size': len(str(self.response_body))}
        
        super().save(*args, **kwargs)
    
    def get_changes(self):
        """Extract field changes from old_data and new_data"""
        if not self.old_data or not self.new_data:
            return {}
        
        changes = {}
        all_keys = set(self.old_data.keys()) | set(self.new_data.keys())
        
        for key in all_keys:
            old_value = self.old_data.get(key)
            new_value = self.new_data.get(key)
            
            if old_value != new_value:
                changes[key] = {
                    'old': old_value,
                    'new': new_value,
                    'changed': True
                }
        
        return changes


class AuditLogConfig(models.Model):
    """Configuration for audit logging"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    
    action = models.CharField(max_length=50, unique=True, null=True, blank=True)
    enabled = models.BooleanField(default=True)
    log_level = models.CharField(max_length=10, choices=AuditLogLevel.choices, default=AuditLogLevel.INFO, null=True, blank=True)
    log_request_body = models.BooleanField(default=True)
    log_response_body = models.BooleanField(default=True)
    log_headers = models.BooleanField(default=False)
    retention_days = models.IntegerField(default=365)
    notify_admins = models.BooleanField(default=False)
    notify_users = models.BooleanField(default=False)
    email_template = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        db_table = 'audit_log_configs'
        verbose_name = 'Audit Log Configuration'
        verbose_name_plural = 'Audit Log Configurations'
    
    def __str__(self):
        return f"{self.action} - {'Enabled' if self.enabled else 'Disabled'}"


class AuditLogArchive(models.Model):
    """Archived logs for long-term storage"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    log_data = models.BinaryField()  # Compressed log data
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    total_logs = models.IntegerField()
    compressed_size_mb = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    original_size_mb = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    compression_ratio = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    storage_path = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'audit_log_archives'
    
    def __str__(self):
        return f"Archive {self.start_date} to {self.end_date} - {self.compressed_size_mb}MB"


class AuditDashboard(models.Model):
    """Dashboard configurations for audit logs"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    
    name = models.CharField(max_length=100, unique=True, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    filters = models.JSONField(default=dict)
    columns = models.JSONField(default=list)
    refresh_interval = models.IntegerField(default=300)  # 5 minutes
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'audit_dashboards'
        verbose_name_plural = 'Audit Dashboards'
    
    def __str__(self):
        return self.name


class AuditAlertRule(models.Model):
    """Rules for triggering alerts from audit logs"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    
    name = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    condition = models.JSONField()  # JSON condition for matching logs
    action = models.CharField(max_length=50, choices=[
        ('EMAIL', 'Send Email'),
        ('SMS', 'Send SMS'),
        ('WEBHOOK', 'Call Webhook'),
        ('CREATE_TICKET', 'Create Support Ticket'),
        ('BLOCK_USER', 'Block User'),
        ('FLAG_TRANSACTION', 'Flag Transaction')
    ])
    action_config = models.JSONField()  # Configuration for the action
    severity = models.CharField(max_length=10, choices=AuditLogLevel.choices, default=AuditLogLevel.WARNING, null=True, blank=True)
    enabled = models.BooleanField(default=True)
    cooldown_minutes = models.IntegerField(default=5)
    last_triggered = models.DateTimeField(null=True, blank=True)
    trigger_count = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'audit_alert_rules'
        unique_together = ['name', 'condition']
    
    def __str__(self):
        return f"{self.name} - {self.get_severity_display()}"