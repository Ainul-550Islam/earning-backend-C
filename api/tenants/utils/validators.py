"""
Tenant Management Validators

This module contains validation utilities for tenant management operations
including field validation, business rule validation, and data integrity checks.
"""

import re
from datetime import datetime, timedelta
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class TenantValidator:
    """Validator for tenant-related operations."""
    
    @staticmethod
    def validate_tenant_name(name):
        """
        Validate tenant name.
        
        Args:
            name (str): Tenant name to validate
            
        Raises:
            ValidationError: If name is invalid
        """
        if not name or not name.strip():
            raise ValidationError(_('Tenant name is required'))
        
        if len(name.strip()) < 2:
            raise ValidationError(_('Tenant name must be at least 2 characters long'))
        
        if len(name.strip()) > 255:
            raise ValidationError(_('Tenant name cannot exceed 255 characters'))
        
        # Check for invalid characters
        if not re.match(r'^[a-zA-Z0-9\s\-_\.]+$', name.strip()):
            raise ValidationError(_('Tenant name can only contain letters, numbers, spaces, hyphens, underscores, and periods'))
    
    @staticmethod
    def validate_slug(slug):
        """
        Validate tenant slug.
        
        Args:
            slug (str): Slug to validate
            
        Raises:
            ValidationError: If slug is invalid
        """
        if not slug or not slug.strip():
            raise ValidationError(_('Slug is required'))
        
        if len(slug.strip()) < 3:
            raise ValidationError(_('Slug must be at least 3 characters long'))
        
        if len(slug.strip()) > 50:
            raise ValidationError(_('Slug cannot exceed 50 characters'))
        
        # Check for valid slug format
        if not re.match(r'^[a-z0-9\-]+$', slug.strip()):
            raise ValidationError(_('Slug can only contain lowercase letters, numbers, and hyphens'))
        
        # Check for consecutive hyphens
        if '--' in slug.strip():
            raise ValidationError(_('Slug cannot contain consecutive hyphens'))
        
        # Check for leading or trailing hyphens
        if slug.strip().startswith('-') or slug.strip().endswith('-'):
            raise ValidationError(_('Slug cannot start or end with a hyphen'))
    
    @staticmethod
    def validate_domain(domain):
        """
        Validate tenant domain.
        
        Args:
            domain (str): Domain to validate
            
        Raises:
            ValidationError: If domain is invalid
        """
        if not domain:
            return  # Domain is optional
        
        domain = domain.strip().lower()
        
        if len(domain) > 255:
            raise ValidationError(_('Domain cannot exceed 255 characters'))
        
        # Basic domain validation
        domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        if not re.match(domain_pattern, domain):
            raise ValidationError(_('Invalid domain format'))
        
        # Check for reserved domains
        reserved_domains = ['localhost', 'example.com', 'test.com', 'invalid']
        if domain in reserved_domains:
            raise ValidationError(_('Domain is reserved and cannot be used'))
    
    @staticmethod
    def validate_email(email):
        """
        Validate email address.
        
        Args:
            email (str): Email to validate
            
        Raises:
            ValidationError: If email is invalid
        """
        if not email:
            return  # Email is optional
        
        email = email.strip().lower()
        
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValidationError(_('Invalid email format'))
        
        # Check for common email providers (optional)
        # This could be extended based on business requirements
    
    @staticmethod
    def validate_phone(phone):
        """
        Validate phone number.
        
        Args:
            phone (str): Phone number to validate
            
        Raises:
            ValidationError: If phone is invalid
        """
        if not phone:
            return  # Phone is optional
        
        phone = phone.strip()
        
        # Remove common formatting
        clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
        
        # Check if phone contains only digits and optional +
        if not re.match(r'^\+?\d{10,15}$', clean_phone):
            raise ValidationError(_('Invalid phone number format'))
        
        # Check minimum length
        if len(clean_phone) < 10:
            raise ValidationError(_('Phone number must be at least 10 digits'))
    
    @staticmethod
    def validate_plan_limits(tenant, plan):
        """
        Validate if tenant can use a plan.
        
        Args:
            tenant: Tenant instance
            plan: Plan instance
            
        Raises:
            ValidationError: If plan limits cannot be applied
        """
        if not plan or not plan.is_active:
            raise ValidationError(_('Plan is not active'))
        
        # Check if tenant is suspended
        if tenant.is_suspended:
            raise ValidationError(_('Suspended tenants cannot change plans'))
        
        # Check if tenant has overdue invoices
        from ..models.core import TenantInvoice
        overdue_invoices = TenantInvoice.objects.filter(
            tenant=tenant,
            status='overdue'
        ).exists()
        
        if overdue_invoices:
            raise ValidationError(_('Cannot change plan with overdue invoices'))
    
    @staticmethod
    def validate_api_key_permissions(permissions):
        """
        Validate API key permissions.
        
        Args:
            permissions (list): List of permissions to validate
            
        Raises:
            ValidationError: If permissions are invalid
        """
        if not isinstance(permissions, list):
            raise ValidationError(_('Permissions must be a list'))
        
        valid_permissions = [
            'read', 'write', 'delete', 'admin',
            'tenants:read', 'tenants:write', 'tenants:delete',
            'billing:read', 'billing:write',
            'analytics:read',
            'security:read', 'security:write'
        ]
        
        for permission in permissions:
            if permission not in valid_permissions:
                raise ValidationError(_('Invalid permission: {}').format(permission))
    
    @staticmethod
    def validate_rate_limits(per_minute, per_hour, per_day):
        """
        Validate API rate limits.
        
        Args:
            per_minute (int): Rate limit per minute
            per_hour (int): Rate limit per hour
            per_day (int): Rate limit per day
            
        Raises:
            ValidationError: If rate limits are invalid
        """
        if per_minute < 1 or per_minute > 10000:
            raise ValidationError(_('Rate limit per minute must be between 1 and 10000'))
        
        if per_hour < per_minute or per_hour > 100000:
            raise ValidationError(_('Rate limit per hour must be >= per minute and <= 100000'))
        
        if per_day < per_hour or per_day > 1000000:
            raise ValidationError(_('Rate limit per day must be >= per hour and <= 1000000'))
    
    @staticmethod
    def validate_quota_limit(limit_value, quota_type):
        """
        Validate quota limit value.
        
        Args:
            limit_value: Limit value to validate
            quota_type (str): Type of quota
            
        Raises:
            ValidationError: If limit is invalid
        """
        if quota_type == 'numeric':
            if not isinstance(limit_value, (int, float)) or limit_value < 0:
                raise ValidationError(_('Numeric quota limit must be a positive number'))
        
        elif quota_type == 'boolean':
            if not isinstance(limit_value, bool):
                raise ValidationError(_('Boolean quota limit must be True or False'))
        
        elif quota_type == 'text':
            if not isinstance(limit_value, str) or len(limit_value.strip()) == 0:
                raise ValidationError(_('Text quota limit must be a non-empty string'))
    
    @staticmethod
    def validate_commission_settings(commission_type, commission_pct, commission_fixed):
        """
        Validate commission settings.
        
        Args:
            commission_type (str): Type of commission
            commission_pct (float): Commission percentage
            commission_fixed (float): Commission fixed amount
            
        Raises:
            ValidationError: If commission settings are invalid
        """
        valid_types = ['percentage', 'fixed', 'tiered', 'hybrid']
        if commission_type not in valid_types:
            raise ValidationError(_('Invalid commission type'))
        
        if commission_type in ['percentage', 'hybrid']:
            if not isinstance(commission_pct, (int, float)) or commission_pct < 0 or commission_pct > 100:
                raise ValidationError(_('Commission percentage must be between 0 and 100'))
        
        if commission_type in ['fixed', 'hybrid']:
            if not isinstance(commission_fixed, (int, float)) or commission_fixed < 0:
                raise ValidationError(_('Commission fixed amount must be a positive number'))


class BillingValidator:
    """Validator for billing-related operations."""
    
    @staticmethod
    def validate_billing_cycle(billing_cycle):
        """
        Validate billing cycle.
        
        Args:
            billing_cycle (str): Billing cycle to validate
            
        Raises:
            ValidationError: If billing cycle is invalid
        """
        valid_cycles = ['monthly', 'yearly', 'quarterly']
        if billing_cycle not in valid_cycles:
            raise ValidationError(_('Invalid billing cycle'))
    
    @staticmethod
    def validate_payment_method(payment_method):
        """
        Validate payment method.
        
        Args:
            payment_method (str): Payment method to validate
            
        Raises:
            ValidationError: If payment method is invalid
        """
        valid_methods = ['credit_card', 'bank_transfer', 'paypal', 'stripe', 'crypto']
        if payment_method not in valid_methods:
            raise ValidationError(_('Invalid payment method'))
    
    @staticmethod
    def validate_invoice_amounts(subtotal, tax_amount, discount_amount, total_amount):
        """
        Validate invoice amounts.
        
        Args:
            subtotal (float): Subtotal amount
            tax_amount (float): Tax amount
            discount_amount (float): Discount amount
            total_amount (float): Total amount
            
        Raises:
            ValidationError: If amounts are invalid
        """
        if subtotal < 0:
            raise ValidationError(_('Subtotal cannot be negative'))
        
        if tax_amount < 0:
            raise ValidationError(_('Tax amount cannot be negative'))
        
        if discount_amount < 0:
            raise ValidationError(_('Discount amount cannot be negative'))
        
        if total_amount < 0:
            raise ValidationError(_('Total amount cannot be negative'))
        
        # Check if calculations are consistent
        calculated_total = subtotal + tax_amount - discount_amount
        if abs(calculated_total - total_amount) > 0.01:  # Allow for rounding
            raise ValidationError(_('Invoice amounts are inconsistent'))
    
    @staticmethod
    def validate_due_date(issue_date, due_date):
        """
        Validate invoice due date.
        
        Args:
            issue_date (datetime): Issue date
            due_date (datetime): Due date
            
        Raises:
            ValidationError: If due date is invalid
        """
        if due_date < issue_date:
            raise ValidationError(_('Due date cannot be before issue date'))
        
        # Check if due date is too far in the future
        max_days = 365
        if (due_date - issue_date).days > max_days:
            raise ValidationError(_('Due date cannot be more than {} days in the future').format(max_days))


class SecurityValidator:
    """Validator for security-related operations."""
    
    @staticmethod
    def validate_password_strength(password):
        """
        Validate password strength.
        
        Args:
            password (str): Password to validate
            
        Raises:
            ValidationError: If password is too weak
        """
        if not password:
            raise ValidationError(_('Password is required'))
        
        if len(password) < 8:
            raise ValidationError(_('Password must be at least 8 characters long'))
        
        if len(password) > 128:
            raise ValidationError(_('Password cannot exceed 128 characters'))
        
        # Check for complexity
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
        
        complexity_score = sum([has_upper, has_lower, has_digit, has_special])
        
        if complexity_score < 3:
            raise ValidationError(_('Password must contain at least 3 of: uppercase letters, lowercase letters, numbers, special characters'))
    
    @staticmethod
    def validate_api_key_format(api_key):
        """
        Validate API key format.
        
        Args:
            api_key (str): API key to validate
            
        Raises:
            ValidationError: If API key format is invalid
        """
        if not api_key:
            raise ValidationError(_('API key is required'))
        
        # API keys should be at least 32 characters
        if len(api_key) < 32:
            raise ValidationError(_('API key must be at least 32 characters long'))
        
        # API keys should contain only alphanumeric characters
        if not re.match(r'^[a-zA-Z0-9]+$', api_key):
            raise ValidationError(_('API key can only contain alphanumeric characters'))
    
    @staticmethod
    def validate_ip_address(ip_address):
        """
        Validate IP address.
        
        Args:
            ip_address (str): IP address to validate
            
        Raises:
            ValidationError: If IP address is invalid
        """
        if not ip_address:
            raise ValidationError(_('IP address is required'))
        
        import ipaddress
        
        try:
            ipaddress.ip_address(ip_address.strip())
        except ValueError:
            raise ValidationError(_('Invalid IP address format'))
    
    @staticmethod
    def validate_webhook_url(url):
        """
        Validate webhook URL.
        
        Args:
            url (str): Webhook URL to validate
            
        Raises:
            ValidationError: If URL is invalid
        """
        if not url:
            raise ValidationError(_('Webhook URL is required'))
        
        # Must use HTTPS for security
        if not url.startswith('https://'):
            raise ValidationError(_('Webhook URL must use HTTPS'))
        
        # Basic URL validation
        from django.core.validators import URLValidator
        validator = URLValidator()
        
        try:
            validator(url)
        except Exception:
            raise ValidationError(_('Invalid webhook URL format'))
    
    @staticmethod
    def validate_ssl_certificate(cert_data):
        """
        Validate SSL certificate data.
        
        Args:
            cert_data (str): SSL certificate data
            
        Raises:
            ValidationError: If certificate is invalid
        """
        if not cert_data:
            raise ValidationError(_('SSL certificate data is required'))
        
        # Basic validation - check if it looks like a certificate
        if not cert_data.strip().startswith('-----BEGIN CERTIFICATE-----'):
            raise ValidationError(_('Invalid SSL certificate format'))
        
        if not cert_data.strip().endswith('-----END CERTIFICATE-----'):
            raise ValidationError(_('Invalid SSL certificate format'))


class AnalyticsValidator:
    """Validator for analytics-related operations."""
    
    @staticmethod
    def validate_metric_value(value, metric_type):
        """
        Validate metric value based on type.
        
        Args:
            value: Metric value to validate
            metric_type (str): Type of metric
            
        Raises:
            ValidationError: If value is invalid
        """
        if metric_type == 'numeric':
            if not isinstance(value, (int, float)):
                raise ValidationError(_('Numeric metric value must be a number'))
        
        elif metric_type == 'boolean':
            if not isinstance(value, bool):
                raise ValidationError(_('Boolean metric value must be True or False'))
        
        elif metric_type == 'text':
            if not isinstance(value, str):
                raise ValidationError(_('Text metric value must be a string'))
        
        elif metric_type == 'percentage':
            if not isinstance(value, (int, float)) or value < 0 or value > 100:
                raise ValidationError(_('Percentage metric value must be between 0 and 100'))
    
    @staticmethod
    def validate_health_score(score):
        """
        Validate health score.
        
        Args:
            score (float): Health score to validate
            
        Raises:
            ValidationError: If score is invalid
        """
        if not isinstance(score, (int, float)):
            raise ValidationError(_('Health score must be a number'))
        
        if score < 0 or score > 100:
            raise ValidationError(_('Health score must be between 0 and 100'))
    
    @staticmethod
    def validate_feature_flag_rollout(rollout_pct):
        """
        Validate feature flag rollout percentage.
        
        Args:
            rollout_pct (float): Rollout percentage to validate
            
        Raises:
            ValidationError: If rollout percentage is invalid
        """
        if not isinstance(rollout_pct, (int, float)):
            raise ValidationError(_('Rollout percentage must be a number'))
        
        if rollout_pct < 0 or rollout_pct > 100:
            raise ValidationError(_('Rollout percentage must be between 0 and 100'))
    
    @staticmethod
    def validate_date_range(start_date, end_date):
        """
        Validate date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Raises:
            ValidationError: If date range is invalid
        """
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError(_('Start date cannot be after end date'))
            
            # Check if range is too large
            max_days = 365
            if (end_date - start_date).days > max_days:
                raise ValidationError(_('Date range cannot exceed {} days').format(max_days))


class BusinessValidator:
    """Validator for business rule validation."""
    
    @staticmethod
    def validate_tenant_hierarchy(parent_tenant, child_tenant):
        """
        Validate tenant hierarchy relationship.
        
        Args:
            parent_tenant: Parent tenant
            child_tenant: Child tenant
            
        Raises:
            ValidationError: If hierarchy is invalid
        """
        if parent_tenant == child_tenant:
            raise ValidationError(_('Tenant cannot be its own parent'))
        
        # Check for circular references
        current = parent_tenant
        max_depth = 10
        depth = 0
        
        while current and depth < max_depth:
            if current == child_tenant:
                raise ValidationError(_('Circular reference in tenant hierarchy'))
            current = current.parent_tenant
            depth += 1
        
        if depth >= max_depth:
            raise ValidationError(_('Tenant hierarchy too deep'))
    
    @staticmethod
    def validate_plan_upgrade(current_plan, target_plan):
        """
        Validate plan upgrade.
        
        Args:
            current_plan: Current plan
            target_plan: Target plan
            
        Raises:
            ValidationError: If upgrade is invalid
        """
        if current_plan == target_plan:
            raise ValidationError(_('Cannot upgrade to the same plan'))
        
        # Define upgrade hierarchy
        plan_hierarchy = ['basic', 'professional', 'enterprise']
        
        try:
            current_index = plan_hierarchy.index(current_plan.plan_type)
            target_index = plan_hierarchy.index(target_plan.plan_type)
        except ValueError:
            # Handle custom plan types
            pass
        
        # Check if upgrade is allowed
        if target_index < current_index:
            raise ValidationError(_('Cannot downgrade to a lower plan'))
    
    @staticmethod
    def validate_reseller_limits(reseller, new_tenant_count=0):
        """
        Validate reseller tenant limits.
        
        Args:
            reseller: Reseller instance
            new_tenant_count (int): Number of new tenants to add
            
        Raises:
            ValidationError: If limits are exceeded
        """
        current_tenants = ResellerService.get_reseller_tenants(reseller).count()
        total_tenants = current_tenants + new_tenant_count
        
        if total_tenants > reseller.max_tenants:
            raise ValidationError(
                _('Reseller tenant limit exceeded: {} > {}').format(
                    total_tenants, reseller.max_tenants
                )
            )
    
    @staticmethod
    def validate_trial_extension(tenant, extension_days):
        """
        Validate trial extension request.
        
        Args:
            tenant: Tenant instance
            extension_days (int): Number of days to extend
            
        Raises:
            ValidationError: If extension is invalid
        """
        if not tenant.trial_ends_at:
            raise ValidationError(_('Tenant is not in trial period'))
        
        if tenant.trial_ends_at < timezone.now():
            raise ValidationError(_('Trial has already expired'))
        
        if extension_days < 1 or extension_days > 90:
            raise ValidationError(_('Trial extension must be between 1 and 90 days'))
        
        # Check total trial period
        original_trial_days = 14  # Default trial period
        total_trial_days = original_trial_days + extension_days
        
        if total_trial_days > 60:
            raise ValidationError(_('Total trial period cannot exceed 60 days'))


class DataValidator:
    """Validator for data integrity and consistency."""
    
    @staticmethod
    def validate_json_data(data):
        """
        Validate JSON data.
        
        Args:
            data: Data to validate
            
        Raises:
            ValidationError: If data is invalid
        """
        import json
        
        if isinstance(data, str):
            try:
                json.loads(data)
            except json.JSONDecodeError:
                raise ValidationError(_('Invalid JSON format'))
        elif not isinstance(data, (dict, list)):
            raise ValidationError(_('Data must be a dictionary, list, or JSON string'))
    
    @staticmethod
    def validate_metadata(metadata):
        """
        Validate metadata dictionary.
        
        Args:
            metadata (dict): Metadata to validate
            
        Raises:
            ValidationError: If metadata is invalid
        """
        if not isinstance(metadata, dict):
            raise ValidationError(_('Metadata must be a dictionary'))
        
        # Check for nested depth
        max_depth = 5
        def check_depth(obj, current_depth=0):
            if current_depth > max_depth:
                raise ValidationError(_('Metadata nesting too deep'))
            
            if isinstance(obj, dict):
                for value in obj.values():
                    check_depth(value, current_depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    check_depth(item, current_depth + 1)
        
        check_depth(metadata)
    
    @staticmethod
    def validate_file_size(file_size, max_size_mb=10):
        """
        Validate file size.
        
        Args:
            file_size (int): File size in bytes
            max_size_mb (int): Maximum size in MB
            
        Raises:
            ValidationError: If file is too large
        """
        max_size_bytes = max_size_mb * 1024 * 1024
        
        if file_size > max_size_bytes:
            raise ValidationError(
                _('File size exceeds maximum allowed size of {} MB').format(max_size_mb)
            )
    
    @staticmethod
    def validate_file_extension(filename, allowed_extensions):
        """
        Validate file extension.
        
        Args:
            filename (str): File name
            allowed_extensions (list): List of allowed extensions
            
        Raises:
            ValidationError: If extension is not allowed
        """
        if not filename:
            raise ValidationError(_('File name is required'))
        
        extension = filename.lower().split('.')[-1]
        
        if extension not in [ext.lower() for ext in allowed_extensions]:
            raise ValidationError(
                _('File extension .{} is not allowed').format(extension)
            )
