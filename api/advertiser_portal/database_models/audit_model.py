from django.conf import settings
"""
Audit Database Model

This module contains Audit model and related models
for managing audit trails and compliance logging.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg, F
from django.core.validators import MinValueValidator, MaxValueValidator

from api.advertiser_portal.models_base import (
    AdvertiserPortalBaseModel, StatusModel, AuditModel,
    APIKeyModel, BudgetModel, GeoModel, TrackingModel, ConfigurationModel,
)
from ..enums import *
from ..utils import *
from ..validators import *


class AuditLog(AdvertiserPortalBaseModel):
    """
    Main audit log model for tracking all system changes.
    
    This model stores comprehensive audit information for
    compliance, security, and debugging purposes.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='audit_logs',
        null=True,
        blank=True,
        help_text="Associated advertiser (if applicable)"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text="User who performed the action"
    )
    
    # Action Information
    action = models.CharField(
        max_length=50,
        choices=[
            ('create', 'Create'),
            ('update', 'Update'),
            ('delete', 'Delete'),
            ('view', 'View'),
            ('export', 'Export'),
            ('import', 'Import'),
            ('login', 'Login'),
            ('logout', 'Logout'),
            ('password_change', 'Password Change'),
            ('permission_change', 'Permission Change'),
            ('api_access', 'API Access'),
            ('system_change', 'System Change')
        ],
        db_index=True,
        help_text="Type of action performed"
    )
    
    # Object Information
    object_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Type of object that was acted upon"
    )
    object_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="ID of object that was acted upon"
    )
    object_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name/description of object"
    )
    
    # Change Details
    field_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Name of field that was changed (for updates)"
    )
    old_value = models.TextField(
        blank=True,
        help_text="Previous value (for updates)"
    )
    new_value = models.TextField(
        blank=True,
        help_text="New value (for updates)"
    )
    
    # Additional Details
    description = models.TextField(
        help_text="Description of the action"
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional details in JSON format"
    )
    
    # Request Information
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the request"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string"
    )
    request_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Request ID for tracing"
    )
    session_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Session ID"
    )
    
    # System Information
    application = models.CharField(
        max_length=50,
        default='advertiser_portal',
        help_text="Application name"
    )
    module = models.CharField(
        max_length=100,
        blank=True,
        help_text="Module where action occurred"
    )
    function = models.CharField(
        max_length=100,
        blank=True,
        help_text="Function where action occurred"
    )
    
    # Result Information
    success = models.BooleanField(
        default=True,
        help_text="Whether the action was successful"
    )
    error_code = models.CharField(
        max_length=50,
        blank=True,
        help_text="Error code if action failed"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if action failed"
    )
    
    # Performance Metrics
    duration = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Action duration in milliseconds"
    )
    
    # Compliance Information
    compliance_level = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical')
        ],
        default='medium',
        help_text="Compliance importance level"
    )
    retention_days = models.IntegerField(
        default=365,
        validators=[MinValueValidator(30)],
        help_text="Number of days to retain this log"
    )
    
    # Classification
    sensitivity = models.CharField(
        max_length=20,
        choices=[
            ('public', 'Public'),
            ('internal', 'Internal'),
            ('confidential', 'Confidential'),
            ('restricted', 'Restricted')
        ],
        default='internal',
        help_text="Data sensitivity level"
    )
    
    class Meta:
        db_table = 'ap_audit_logs'
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['advertiser', 'action'], name='idx_advertiser_action_095'),
            models.Index(fields=['user', 'action'], name='idx_user_action_096'),
            models.Index(fields=['object_type', 'object_id'], name='idx_object_type_object_id_097'),
            models.Index(fields=['action', 'created_at'], name='idx_action_created_at_098'),
            models.Index(fields=['ip_address'], name='idx_ip_address_099'),
            models.Index(fields=['success'], name='idx_success_100'),
            models.Index(fields=['compliance_level'], name='idx_compliance_level_101'),
            models.Index(fields=['sensitivity'], name='idx_sensitivity_102'),
            models.Index(fields=['created_at'], name='idx_created_at_103'),
        ]
    
    def __str__(self) -> str:
        return f"{self.action} - {self.object_type} ({self.user.username if self.user else 'System'})"
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate retention period
        if self.retention_days < 30:
            raise ValidationError("Retention period must be at least 30 days")
        
        # Validate duration
        if self.duration is not None and self.duration < 0:
            raise ValidationError("Duration cannot be negative")
    
    @classmethod
    def log_action(cls, action: str, object_type: str, object_id: str, 
                   user: Optional['User'] = None, advertiser: Optional['Advertiser'] = None,
                   description: str = '', old_value: str = '', new_value: str = '',
                   field_name: str = '', details: Optional[Dict[str, Any]] = None,
                   ip_address: str = '', user_agent: str = '', request_id: str = '',
                   session_id: str = '', module: str = '', function: str = '',
                   success: bool = True, error_code: str = '', error_message: str = '',
                   duration: Optional[int] = None, compliance_level: str = 'medium',
                   sensitivity: str = 'internal') -> 'AuditLog':
        """Create an audit log entry."""
        return cls.objects.create(
            advertiser=advertiser,
            user=user,
            action=action,
            object_type=object_type,
            object_id=object_id,
            description=description,
            old_value=old_value,
            new_value=new_value,
            field_name=field_name,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            session_id=session_id,
            module=module,
            function=function,
            success=success,
            error_code=error_code,
            error_message=error_message,
            duration=duration,
            compliance_level=compliance_level,
            sensitivity=sensitivity
        )
    
    @classmethod
    def log_creation(cls, obj: models.Model, user: Optional['User'] = None,
                    description: str = '', details: Optional[Dict[str, Any]] = None,
                    **kwargs) -> 'AuditLog':
        """Log object creation."""
        object_name = str(obj)
        if hasattr(obj, 'name'):
            object_name = obj.name
        elif hasattr(obj, 'company_name'):
            object_name = obj.company_name
        
        return cls.log_action(
            action='create',
            object_type=obj.__class__.__name__,
            object_id=str(obj.pk),
            user=user,
            advertiser=getattr(obj, 'advertiser', None),
            description=description or f"Created {obj.__class__.__name__}",
            object_name=object_name,
            details=details or {},
            **kwargs
        )
    
    @classmethod
    def log_update(cls, obj: models.Model, changed_fields: Dict[str, Any],
                   user: Optional['User'] = None, description: str = '',
                   details: Optional[Dict[str, Any]] = None, **kwargs) -> List['AuditLog']:
        """Log object update."""
        logs = []
        object_name = str(obj)
        if hasattr(obj, 'name'):
            object_name = obj.name
        elif hasattr(obj, 'company_name'):
            object_name = obj.company_name
        
        for field_name, change in changed_fields.items():
            old_value = change.get('old', '')
            new_value = change.get('new', '')
            
            log = cls.log_action(
                action='update',
                object_type=obj.__class__.__name__,
                object_id=str(obj.pk),
                user=user,
                advertiser=getattr(obj, 'advertiser', None),
                description=description or f"Updated {obj.__class__.__name__}",
                field_name=field_name,
                old_value=str(old_value),
                new_value=str(new_value),
                object_name=object_name,
                details=details or {},
                **kwargs
            )
            logs.append(log)
        
        return logs
    
    @classmethod
    def log_deletion(cls, obj: models.Model, user: Optional['User'] = None,
                    description: str = '', details: Optional[Dict[str, Any]] = None,
                    **kwargs) -> 'AuditLog':
        """Log object deletion."""
        object_name = str(obj)
        if hasattr(obj, 'name'):
            object_name = obj.name
        elif hasattr(obj, 'company_name'):
            object_name = obj.company_name
        
        return cls.log_action(
            action='delete',
            object_type=obj.__class__.__name__,
            object_id=str(obj.pk),
            user=user,
            advertiser=getattr(obj, 'advertiser', None),
            description=description or f"Deleted {obj.__class__.__name__}",
            object_name=object_name,
            details=details or {},
            **kwargs
        )
    
    @classmethod
    def log_access(cls, obj: models.Model, user: Optional['User'] = None,
                   description: str = '', details: Optional[Dict[str, Any]] = None,
                   **kwargs) -> 'AuditLog':
        """Log object access."""
        object_name = str(obj)
        if hasattr(obj, 'name'):
            object_name = obj.name
        elif hasattr(obj, 'company_name'):
            object_name = obj.company_name
        
        return cls.log_action(
            action='view',
            object_type=obj.__class__.__name__,
            object_id=str(obj.pk),
            user=user,
            advertiser=getattr(obj, 'advertiser', None),
            description=description or f"Viewed {obj.__class__.__name__}",
            object_name=object_name,
            details=details or {},
            **kwargs
        )
    
    @classmethod
    def log_login(cls, user: 'User', success: bool = True, ip_address: str = '',
                  user_agent: str = '', error_message: str = '', **kwargs) -> 'AuditLog':
        """Log user login."""
        return cls.log_action(
            action='login',
            object_type='User',
            object_id=str(user.pk),
            user=user,
            description=f"User login {'successful' if success else 'failed'}",
            success=success,
            error_message=error_message,
            ip_address=ip_address,
            user_agent=user_agent,
            compliance_level='high',
            **kwargs
        )
    
    @classmethod
    def log_logout(cls, user: 'User', ip_address: str = '', user_agent: str = '',
                   **kwargs) -> 'AuditLog':
        """Log user logout."""
        return cls.log_action(
            action='logout',
            object_type='User',
            object_id=str(user.pk),
            user=user,
            description="User logout",
            ip_address=ip_address,
            user_agent=user_agent,
            compliance_level='medium',
            **kwargs
        )
    
    @classmethod
    def log_api_access(cls, user: Optional['User'], endpoint: str, method: str,
                      success: bool = True, ip_address: str = '', user_agent: str = '',
                      error_message: str = '', duration: Optional[int] = None,
                      **kwargs) -> 'AuditLog':
        """Log API access."""
        return cls.log_action(
            action='api_access',
            object_type='API',
            object_id=endpoint,
            user=user,
            description=f"API {method} {endpoint}",
            success=success,
            error_message=error_message,
            ip_address=ip_address,
            user_agent=user_agent,
            duration=duration,
            details={'method': method, 'endpoint': endpoint},
            compliance_level='high',
            **kwargs
        )
    
    def get_change_summary(self) -> str:
        """Get human-readable change summary."""
        if self.action == 'create':
            return f"Created {self.object_type}: {self.object_name}"
        elif self.action == 'update':
            return f"Updated {self.object_type} {self.field_name}: '{self.old_value}' → '{self.new_value}'"
        elif self.action == 'delete':
            return f"Deleted {self.object_type}: {self.object_name}"
        elif self.action == 'view':
            return f"Viewed {self.object_type}: {self.object_name}"
        else:
            return f"{self.action.title()} {self.object_type}: {self.object_name}"
    
    def get_audit_summary(self) -> Dict[str, Any]:
        """Get comprehensive audit summary."""
        return {
            'basic_info': {
                'id': str(self.id),
                'action': self.action,
                'object_type': self.object_type,
                'object_id': self.object_id,
                'object_name': self.object_name,
                'field_name': self.field_name
            },
            'change': {
                'old_value': self.old_value,
                'new_value': self.new_value,
                'description': self.description
            },
            'user': {
                'id': self.user.id if self.user else None,
                'username': self.user.username if self.user else 'System'
            },
            'advertiser': {
                'id': self.advertiser.id if self.advertiser else None,
                'company_name': self.advertiser.company_name if self.advertiser else None
            },
            'request': {
                'ip_address': str(self.ip_address) if self.ip_address else None,
                'user_agent': self.user_agent,
                'request_id': self.request_id,
                'session_id': self.session_id
            },
            'system': {
                'application': self.application,
                'module': self.module,
                'function': self.function,
                'timestamp': self.created_at.isoformat()
            },
            'result': {
                'success': self.success,
                'error_code': self.error_code,
                'error_message': self.error_message,
                'duration': self.duration
            },
            'compliance': {
                'compliance_level': self.compliance_level,
                'sensitivity': self.sensitivity,
                'retention_days': self.retention_days
            }
        }


class ComplianceReport(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing compliance reports.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='compliance_reports',
        help_text="Associated advertiser"
    )
    report_name = models.CharField(
        max_length=255,
        help_text="Report name"
    )
    report_type = models.CharField(
        max_length=50,
        choices=[
            ('data_access', 'Data Access Report'),
            ('user_activity', 'User Activity Report'),
            ('api_usage', 'API Usage Report'),
            ('security', 'Security Report'),
            ('privacy', 'Privacy Report'),
            ('audit_trail', 'Audit Trail Report'),
            ('custom', 'Custom Report')
        ],
        help_text="Type of compliance report"
    )
    
    # Date Range
    start_date = models.DateField(
        help_text="Report start date"
    )
    end_date = models.DateField(
        help_text="Report end date"
    )
    
    # Report Data
    summary_data = models.JSONField(
        default=dict,
        help_text="Report summary statistics"
    )
    detailed_data = models.JSONField(
        default=dict,
        help_text="Detailed report data"
    )
    findings = models.JSONField(
        default=list,
        help_text="List of compliance findings"
    )
    
    # File Information
    report_file = models.FileField(
        upload_to='compliance_reports/%Y/%m/',
        null=True,
        blank=True,
        help_text="Generated report file"
    )
    file_format = models.CharField(
        max_length=20,
        choices=[
            ('pdf', 'PDF'),
            ('excel', 'Excel'),
            ('csv', 'CSV'),
            ('json', 'JSON')
        ],
        default='pdf',
        help_text="Report file format"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('generating', 'Generating'),
            ('completed', 'Completed'),
            ('failed', 'Failed')
        ],
        default='pending',
        help_text="Report generation status"
    )
    
    # Review Information
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_compliance_reports'
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Review timestamp"
    )
    review_notes = models.TextField(
        blank=True,
        help_text="Review notes"
    )
    
    class Meta:
        db_table = 'compliance_reports'
        verbose_name = 'Compliance Report'
        verbose_name_plural = 'Compliance Reports'
        indexes = [
            models.Index(fields=['advertiser', 'report_type'], name='idx_advertiser_report_type_104'),
            models.Index(fields=['start_date', 'end_date'], name='idx_start_date_end_date_105'),
            models.Index(fields=['status'], name='idx_status_106'),
        ]
    
    def __str__(self) -> str:
        return f"{self.report_name} ({self.advertiser.company_name})"
    
    def generate_report(self) -> bool:
        """Generate the compliance report."""
        try:
            self.status = 'generating'
            self.save(update_fields=['status'])
            
            # Generate report data based on type
            if self.report_type == 'data_access':
                self._generate_data_access_report()
            elif self.report_type == 'user_activity':
                self._generate_user_activity_report()
            elif self.report_type == 'api_usage':
                self._generate_api_usage_report()
            elif self.report_type == 'security':
                self._generate_security_report()
            elif self.report_type == 'privacy':
                self._generate_privacy_report()
            elif self.report_type == 'audit_trail':
                self._generate_audit_trail_report()
            
            self.status = 'completed'
            self.save(update_fields=['status'])
            
            return True
        except Exception as e:
            logger.error(f"Error generating compliance report {self.id}: {str(e)}")
            self.status = 'failed'
            self.save(update_fields=['status'])
            return False
    
    def _generate_data_access_report(self) -> None:
        """Generate data access report."""
        # Get audit logs for data access within date range
        logs = AuditLog.objects.filter(
            advertiser=self.advertiser,
            action__in=['view', 'export'],
            created_at__date__gte=self.start_date,
            created_at__date__lte=self.end_date
        )
        
        summary = {
            'total_access_events': logs.count(),
            'unique_users': logs.values('user').distinct().count(),
            'access_by_type': dict(
                logs.values('action').annotate(count=Count('id')).values_list('action', 'count')
            ),
            'access_by_object_type': dict(
                logs.values('object_type').annotate(count=Count('id')).values_list('object_type', 'count')
            )
        }
        
        self.summary_data = summary
        self.detailed_data = {
            'access_events': [
                {
                    'timestamp': log.created_at.isoformat(),
                    'user': log.user.username if log.user else 'System',
                    'action': log.action,
                    'object_type': log.object_type,
                    'object_id': log.object_id,
                    'ip_address': str(log.ip_address) if log.ip_address else None
                }
                for log in logs
            ]
        }
    
    def _generate_user_activity_report(self) -> None:
        """Generate user activity report."""
        # Get user activity logs
        logs = AuditLog.objects.filter(
            advertiser=self.advertiser,
            created_at__date__gte=self.start_date,
            created_at__date__lte=self.end_date
        )
        
        summary = {
            'total_activities': logs.count(),
            'unique_users': logs.values('user').distinct().count(),
            'activities_by_type': dict(
                logs.values('action').annotate(count=Count('id')).values_list('action', 'count')
            ),
            'activities_by_user': dict(
                logs.values('user__username').annotate(count=Count('id')).values_list('user__username', 'count')
            )
        }
        
        self.summary_data = summary
    
    def _generate_api_usage_report(self) -> None:
        """Generate API usage report."""
        # Get API access logs
        logs = AuditLog.objects.filter(
            advertiser=self.advertiser,
            action='api_access',
            created_at__date__gte=self.start_date,
            created_at__date__lte=self.end_date
        )
        
        summary = {
            'total_api_calls': logs.count(),
            'successful_calls': logs.filter(success=True).count(),
            'failed_calls': logs.filter(success=False).count(),
            'unique_endpoints': logs.values('object_id').distinct().count(),
            'average_duration': logs.aggregate(avg=Avg('duration'))['avg'] or 0
        }
        
        self.summary_data = summary
    
    def _generate_security_report(self) -> None:
        """Generate security report."""
        # Get security-related logs
        logs = AuditLog.objects.filter(
            advertiser=self.advertiser,
            action__in=['login', 'logout', 'password_change'],
            created_at__date__gte=self.start_date,
            created_at__date__lte=self.end_date
        )
        
        summary = {
            'total_security_events': logs.count(),
            'successful_logins': logs.filter(action='login', success=True).count(),
            'failed_logins': logs.filter(action='login', success=False).count(),
            'password_changes': logs.filter(action='password_change').count(),
            'unique_users': logs.values('user').distinct().count()
        }
        
        self.summary_data = summary
    
    def _generate_privacy_report(self) -> None:
        """Generate privacy report."""
        # Get privacy-related logs
        logs = AuditLog.objects.filter(
            advertiser=self.advertiser,
            sensitivity__in=['confidential', 'restricted'],
            created_at__date__gte=self.start_date,
            created_at__date__lte=self.end_date
        )
        
        summary = {
            'total_privacy_events': logs.count(),
            'events_by_sensitivity': dict(
                logs.values('sensitivity').annotate(count=Count('id')).values_list('sensitivity', 'count')
            ),
            'events_by_action': dict(
                logs.values('action').annotate(count=Count('id')).values_list('action', 'count')
            )
        }
        
        self.summary_data = summary
    
    def _generate_audit_trail_report(self) -> None:
        """Generate comprehensive audit trail report."""
        # Get all audit logs
        logs = AuditLog.objects.filter(
            advertiser=self.advertiser,
            created_at__date__gte=self.start_date,
            created_at__date__lte=self.end_date
        )
        
        summary = {
            'total_events': logs.count(),
            'events_by_action': dict(
                logs.values('action').annotate(count=Count('id')).values_list('action', 'count')
            ),
            'events_by_object_type': dict(
                logs.values('object_type').annotate(count=Count('id')).values_list('object_type', 'count')
            ),
            'events_by_compliance_level': dict(
                logs.values('compliance_level').annotate(count=Count('id')).values_list('compliance_level', 'count')
            )
        }
        
        self.summary_data = summary


class RetentionPolicy(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing data retention policies.
    """
    
    # Basic Information
    name = models.CharField(
        max_length=255,
        help_text="Policy name"
    )
    description = models.TextField(
        blank=True,
        help_text="Policy description"
    )
    
    # Policy Configuration
    object_type = models.CharField(
        max_length=100,
        help_text="Type of object this policy applies to"
    )
    retention_days = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of days to retain data"
    )
    retention_action = models.CharField(
        max_length=50,
        choices=[
            ('delete', 'Delete'),
            ('archive', 'Archive'),
            ('anonymize', 'Anonymize'),
            ('flag', 'Flag for Review')
        ],
        default='delete',
        help_text="Action to take when retention period expires"
    )
    
    # Conditions
    conditions = models.JSONField(
        default=dict,
        blank=True,
        help_text="Conditions for applying retention policy"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether policy is active"
    )
    
    class Meta:
        db_table = 'ap_retention_policies'
        verbose_name = 'Retention Policy'
        verbose_name_plural = 'Retention Policies'
        indexes = [
            models.Index(fields=['object_type'], name='idx_object_type_107'),
            models.Index(fields=['is_active'], name='idx_is_active_108'),
        ]
    
    def __str__(self) -> str:
        return self.name
    
    def should_retain(self, obj: models.Model) -> bool:
        """Check if object should be retained based on policy."""
        if not self.is_active:
            return True
        
        # Check if object type matches
        if obj.__class__.__name__ != self.object_type:
            return True
        
        # Check retention period
        created_at = getattr(obj, 'created_at', None)
        if not created_at:
            return True
        
        retention_date = created_at + timezone.timedelta(days=self.retention_days)
        return timezone.now() < retention_date
    
    def apply_retention(self, obj: models.Model) -> bool:
        """Apply retention policy to object."""
        if self.should_retain(obj):
            return False
        
        try:
            if self.retention_action == 'delete':
                obj.delete()
            elif self.retention_action == 'archive':
                # Implement archiving logic
                pass
            elif self.retention_action == 'anonymize':
                # Implement anonymization logic
                pass
            elif self.retention_action == 'flag':
                # Implement flagging logic
                pass
            
            return True
        except Exception:
            return False
