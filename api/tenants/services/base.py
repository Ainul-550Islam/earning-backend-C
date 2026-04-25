"""
Base Service Class

This module provides the base service class that all tenant management
services inherit from, providing common functionality and utilities.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class BaseService:
    """
    Base service class for tenant management operations.
    
    Provides common functionality including:
    - Transaction management
    - Error handling and logging
    - Validation utilities
    - Common operations
    """
    
    @staticmethod
    def validate_required_fields(data, required_fields):
        """
        Validate that required fields are present in data.
        
        Args:
            data (dict): Data to validate
            required_fields (list): List of required field names
            
        Raises:
            ValidationError: If required fields are missing
        """
        missing_fields = []
        for field in required_fields:
            if field not in data or data[field] is None or data[field] == '':
                missing_fields.append(field)
        
        if missing_fields:
            raise ValidationError(f"Required fields are missing: {', '.join(missing_fields)}")
    
    @staticmethod
    def validate_email(email):
        """
        Validate email format.
        
        Args:
            email (str): Email to validate
            
        Returns:
            bool: True if valid
            
        Raises:
            ValidationError: If email is invalid
        """
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not email or not re.match(email_pattern, email):
            raise ValidationError("Invalid email address")
        
        return True
    
    @staticmethod
    def validate_phone(phone):
        """
        Validate phone number format.
        
        Args:
            phone (str): Phone number to validate
            
        Returns:
            bool: True if valid
            
        Raises:
            ValidationError: If phone is invalid
        """
        import re
        
        if not phone:
            return True  # Phone is optional
        
        # Remove common phone number formatting
        clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
        
        # Check if phone contains only digits and optional +
        if not re.match(r'^\+?\d{10,15}$', clean_phone):
            raise ValidationError("Invalid phone number format")
        
        return True
    
    @staticmethod
    def validate_url(url):
        """
        Validate URL format.
        
        Args:
            url (str): URL to validate
            
        Returns:
            bool: True if valid
            
        Raises:
            ValidationError: If URL is invalid
        """
        from django.core.validators import URLValidator
        
        if not url:
            return True  # URL is optional
        
        validator = URLValidator()
        try:
            validator(url)
            return True
        except Exception:
            raise ValidationError("Invalid URL format")
    
    @staticmethod
    def validate_slug(slug):
        """
        Validate slug format.
        
        Args:
            slug (str): Slug to validate
            
        Returns:
            bool: True if valid
            
        Raises:
            ValidationError: If slug is invalid
        """
        import re
        
        if not slug:
            raise ValidationError("Slug is required")
        
        # Slug should contain only lowercase letters, numbers, and hyphens
        if not re.match(r'^[a-z0-9-]+$', slug):
            raise ValidationError("Slug can only contain lowercase letters, numbers, and hyphens")
        
        # Slug should not start or end with hyphen
        if slug.startswith('-') or slug.endswith('-'):
            raise ValidationError("Slug cannot start or end with a hyphen")
        
        # Slug should not have consecutive hyphens
        if '--' in slug:
            raise ValidationError("Slug cannot have consecutive hyphens")
        
        return True
    
    @staticmethod
    def sanitize_string(value, max_length=None):
        """
        Sanitize string value.
        
        Args:
            value (str): String to sanitize
            max_length (int): Maximum length (optional)
            
        Returns:
            str: Sanitized string
        """
        if not value:
            return ''
        
        # Strip whitespace
        sanitized = value.strip()
        
        # Limit length if specified
        if max_length and len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized
    
    @staticmethod
    def generate_unique_id(prefix='', length=8):
        """
        Generate a unique identifier.
        
        Args:
            prefix (str): Prefix for the ID
            length (int): Length of random part
            
        Returns:
            str: Generated unique ID
        """
        import uuid
        import random
        import string
        
        # Generate random string
        chars = string.ascii_uppercase + string.digits
        random_part = ''.join(random.choice(chars) for _ in range(length))
        
        # Add prefix if provided
        if prefix:
            return f"{prefix}-{random_part}"
        
        return random_part
    
    @staticmethod
    def format_currency(amount, currency='USD'):
        """
        Format currency amount.
        
        Args:
            amount (float): Amount to format
            currency (str): Currency code
            
        Returns:
            str: Formatted currency string
        """
        try:
            from django.conf import settings
            from django.utils.formats import localize
            
            # Use Django's localization if available
            if hasattr(settings, 'USE_L10N') and settings.USE_L10N:
                return localize(amount, use_l10n=True)
            
            # Fallback formatting
            if currency == 'USD':
                return f"${amount:,.2f}"
            elif currency == 'EUR':
                return f"EUR {amount:,.2f}"
            else:
                return f"{amount:,.2f} {currency}"
                
        except Exception:
            return f"{amount:,.2f} {currency}"
    
    @staticmethod
    def calculate_percentage(value, total, decimal_places=2):
        """
        Calculate percentage.
        
        Args:
            value (float): Value
            total (float): Total
            decimal_places (int): Decimal places
            
        Returns:
            float: Percentage
        """
        if total == 0:
            return 0.0
        
        percentage = (value / total) * 100
        return round(percentage, decimal_places)
    
    @staticmethod
    def get_date_range(period):
        """
        Get date range for a period.
        
        Args:
            period (str): Period ('daily', 'weekly', 'monthly', 'yearly')
            
        Returns:
            tuple: (start_date, end_date)
        """
        from datetime import timedelta
        
        now = timezone.now()
        
        if period == 'daily':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif period == 'weekly':
            # Start of current week (Monday)
            start_date = now - timedelta(days=now.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(weeks=1)
        elif period == 'monthly':
            # Start of current month
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Start of next month
            if now.month == 12:
                end_date = start_date.replace(year=now.year + 1, month=1)
            else:
                end_date = start_date.replace(month=now.month + 1)
        elif period == 'yearly':
            # Start of current year
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            # Start of next year
            end_date = start_date.replace(year=now.year + 1)
        else:
            # Default to monthly
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                end_date = start_date.replace(year=now.year + 1, month=1)
            else:
                end_date = start_date.replace(month=now.month + 1)
        
        return start_date, end_date
    
    @staticmethod
    def create_audit_log(tenant, action, description, user=None, metadata=None):
        """
        Create an audit log entry.
        
        Args:
            tenant (Tenant): Tenant the action relates to
            action (str): Action performed
            description (str): Description of action
            user (User): User who performed action
            metadata (dict): Additional metadata
            
        Returns:
            object: Created audit log entry
        """
        try:
            from ..models.security import TenantAuditLog
            
            audit_log = TenantAuditLog.objects.create(
                tenant=tenant,
                action=action,
                description=description,
                user=user,
                ip_address=BaseService._get_client_ip(),
                user_agent=BaseService._get_user_agent(),
                severity='low',
                metadata=metadata or {}
            )
            
            return audit_log
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {str(e)}")
            return None
    
    @staticmethod
    def create_notification(tenant, title, message, notification_type='system', **kwargs):
        """
        Create a notification.
        
        Args:
            tenant (Tenant): Tenant to create notification for
            title (str): Notification title
            message (str): Notification message
            notification_type (str): Type of notification
            **kwargs: Additional notification fields
            
        Returns:
            object: Created notification
        """
        try:
            from ..models.analytics import TenantNotification
            
            notification = TenantNotification.objects.create(
                tenant=tenant,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=kwargs.get('priority', 'medium'),
                status='pending',
                send_email=kwargs.get('send_email', False),
                metadata=kwargs.get('metadata', {})
            )
            
            return notification
            
        except Exception as e:
            logger.error(f"Failed to create notification: {str(e)}")
            return None
    
    @staticmethod
    def _get_client_ip():
        """
        Get client IP address.
        
        Returns:
            str: Client IP address
        """
        # This would typically get the IP from the request
        # For now, return a placeholder
        return '127.0.0.1'
    
    @staticmethod
    def _get_user_agent():
        """
        Get user agent string.
        
        Returns:
            str: User agent string
        """
        # This would typically get the user agent from the request
        # For now, return a placeholder
        return 'Mozilla/5.0 (compatible; Service/1.0)'
    
    @staticmethod
    def handle_service_error(error, context=""):
        """
        Handle service errors consistently.
        
        Args:
            error (Exception): Error to handle
            context (str): Context where error occurred
            
        Raises:
            ValidationError: With appropriate error message
        """
        error_message = f"Service error"
        if context:
            error_message += f" in {context}"
        
        error_message += f": {str(error)}"
        
        logger.error(error_message)
        
        # Re-raise as ValidationError for consistent error handling
        raise ValidationError(error_message)
    
    @staticmethod
    def paginate_queryset(queryset, page=1, page_size=20):
        """
        Paginate a queryset.
        
        Args:
            queryset: Queryset to paginate
            page (int): Page number
            page_size (int): Number of items per page
            
        Returns:
            dict: Paginated result
        """
        try:
            from django.core.paginator import Paginator
            
            paginator = Paginator(queryset, page_size)
            page_obj = paginator.get_page(page)
            
            return {
                'items': list(page_obj.object_list),
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_items': paginator.count,
                    'total_pages': paginator.num_pages,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous(),
                    'next_page': page + 1 if page_obj.has_next() else None,
                    'previous_page': page - 1 if page_obj.has_previous() else None,
                }
            }
            
        except Exception as e:
            return {
                'items': [],
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_items': 0,
                    'total_pages': 0,
                    'has_next': False,
                    'has_previous': False,
                    'next_page': None,
                    'previous_page': None,
                },
                'error': str(e)
            }
    
    @staticmethod
    def filter_queryset(queryset, filters):
        """
        Apply filters to a queryset.
        
        Args:
            queryset: Queryset to filter
            filters (dict): Filters to apply
            
        Returns:
            Queryset: Filtered queryset
        """
        for field, value in filters.items():
            if value is not None and value != '':
                if hasattr(queryset.model, field):
                    if '__' in field:
                        # Handle related field filters
                        queryset = queryset.filter(**{field: value})
                    else:
                        # Handle direct field filters
                        field_obj = queryset.model._meta.get_field(field)
                        
                        if field_obj.get_internal_type() in ['CharField', 'TextField']:
                            queryset = queryset.filter(**{f"{field}__icontains": value})
                        elif field_obj.get_internal_type() in ['DateTimeField', 'DateField']:
                            queryset = queryset.filter(**{f"{field}__date": value})
                        else:
                            queryset = queryset.filter(**{field: value})
        
        return queryset
    
    @staticmethod
    def sort_queryset(queryset, sort_by, default_sort='-created_at'):
        """
        Sort a queryset.
        
        Args:
            queryset: Queryset to sort
            sort_by (str): Field to sort by
            default_sort (str): Default sort field
            
        Returns:
            Queryset: Sorted queryset
        """
        if not sort_by:
            sort_by = default_sort
        
        # Validate sort field
        if sort_by.startswith('-'):
            field_name = sort_by[1:]
        else:
            field_name = sort_by
        
        if hasattr(queryset.model, field_name):
            return queryset.order_by(sort_by)
        
        return queryset.order_by(default_sort)
