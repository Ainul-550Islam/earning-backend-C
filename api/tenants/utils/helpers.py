"""
Tenant Management Helper Functions

This module contains utility helper functions for tenant management operations
including data processing, formatting, and common operations.
"""

import uuid
import hashlib
import secrets
import string
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.files.base import ContentFile
import json
import csv
import io


class TenantHelper:
    """Helper class for tenant operations."""
    
    @staticmethod
    def generate_unique_slug(name, existing_slugs=None):
        """
        Generate a unique slug from a name.
        
        Args:
            name (str): Name to generate slug from
            existing_slugs (list): List of existing slugs to avoid
            
        Returns:
            str: Unique slug
        """
        import re
        
        # Convert to lowercase and replace spaces with hyphens
        slug = re.sub(r'[^a-z0-9\s-]', '', name.lower())
        slug = re.sub(r'\s+', '-', slug.strip())
        
        # Remove consecutive hyphens
        slug = re.sub(r'-+', '-', slug)
        
        # Ensure it doesn't start or end with hyphen
        slug = slug.strip('-')
        
        # Ensure minimum length
        if len(slug) < 3:
            slug = f"tenant-{slug}"
        
        # Check uniqueness and add suffix if needed
        if existing_slugs and slug in existing_slugs:
            counter = 1
            original_slug = slug
            
            while f"{original_slug}-{counter}" in existing_slugs:
                counter += 1
            
            slug = f"{original_slug}-{counter}"
        
        return slug
    
    @staticmethod
    def generate_api_key(length=32):
        """
        Generate a secure API key.
        
        Args:
            length (int): Length of the API key
            
        Returns:
            str: Generated API key
        """
        alphabet = string.ascii_letters + string.digits
        api_key = ''.join(secrets.choice(alphabet) for _ in range(length))
        
        # Add prefix for identification
        return f"tk_{api_key}"
    
    @staticmethod
    def generate_webhook_secret(length=32):
        """
        Generate a secure webhook secret.
        
        Args:
            length (int): Length of the secret
            
        Returns:
            str: Generated webhook secret
        """
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def hash_password(password):
        """
        Hash a password securely.
        
        Args:
            password (str): Password to hash
            
        Returns:
            str: Hashed password
        """
        from django.contrib.auth.hashers import make_password
        return make_password(password)
    
    @staticmethod
    def verify_password(password, hashed):
        """
        Verify a password against a hash.
        
        Args:
            password (str): Plain password
            hashed (str): Hashed password
            
        Returns:
            bool: True if password matches
        """
        from django.contrib.auth.hashers import check_password
        return check_password(password, hashed)
    
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
            from django.utils.formats import localize
            
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
        now = timezone.now()
        
        if period == 'daily':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif period == 'weekly':
            start_date = now - timedelta(days=now.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(weeks=1)
        elif period == 'monthly':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                end_date = start_date.replace(year=now.year + 1, month=1)
            else:
                end_date = start_date.replace(month=now.month + 1)
        elif period == 'yearly':
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
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
    def format_file_size(size_bytes):
        """
        Format file size in human readable format.
        
        Args:
            size_bytes (int): Size in bytes
            
        Returns:
            str: Formatted size string
        """
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    @staticmethod
    def sanitize_filename(filename):
        """
        Sanitize filename for safe storage.
        
        Args:
            filename (str): Original filename
            
        Returns:
            str: Sanitized filename
        """
        import re
        
        # Remove path separators
        filename = filename.replace('/', '_').replace('\\', '_')
        
        # Remove special characters
        filename = re.sub(r'[^\w\-_\.]', '_', filename)
        
        # Ensure it's not empty
        if not filename:
            filename = 'file'
        
        return filename
    
    @staticmethod
    def generate_invoice_number(tenant_id, date=None):
        """
        Generate invoice number.
        
        Args:
            tenant_id (int): Tenant ID
            date (datetime): Date for invoice (optional)
            
        Returns:
            str: Generated invoice number
        """
        if date is None:
            date = timezone.now()
        
        date_str = date.strftime("%Y%m")
        
        # Get count for this tenant and month
        from ..models.core import TenantInvoice
        count = TenantInvoice.objects.filter(
            tenant_id=tenant_id,
            issue_date__month=date.month,
            issue_date__year=date.year
        ).count()
        
        return f"INV-{tenant_id:04d}-{date_str}-{count + 1:04d}"
    
    @staticmethod
    def calculate_trial_end_date(trial_days=14):
        """
        Calculate trial end date.
        
        Args:
            trial_days (int): Number of trial days
            
        Returns:
            datetime: Trial end date
        """
        return timezone.now() + timedelta(days=trial_days)
    
    @staticmethod
    def is_trial_expired(trial_end_date):
        """
        Check if trial has expired.
        
        Args:
            trial_end_date (datetime): Trial end date
            
        Returns:
            bool: True if expired
        """
        return timezone.now() > trial_end_date
    
    @staticmethod
    def get_trial_days_remaining(trial_end_date):
        """
        Get remaining trial days.
        
        Args:
            trial_end_date (datetime): Trial end date
            
        Returns:
            int: Remaining days
        """
        if timezone.now() > trial_end_date:
            return 0
        
        delta = trial_end_date - timezone.now()
        return max(0, delta.days)


class DataHelper:
    """Helper class for data operations."""
    
    @staticmethod
    def export_to_csv(queryset, fields=None, filename=None):
        """
        Export queryset to CSV.
        
        Args:
            queryset: Django queryset to export
            fields (list): Fields to include (optional)
            filename (str): Filename for export
            
        Returns:
            dict: Export result with file content
        """
        if not queryset.exists():
            return {'success': False, 'message': 'No data to export'}
        
        if not filename:
            filename = f"export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Get model fields if not specified
        if not fields:
            model = queryset.model
            fields = [field.name for field in model._meta.fields]
        
        # Write header
        writer.writerow(fields)
        
        # Write data rows
        for obj in queryset:
            row = []
            for field in fields:
                value = getattr(obj, field, '')
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                elif hasattr(value, '__str__'):
                    value = str(value)
                row.append(value)
            writer.writerow(row)
        
        csv_content = output.getvalue()
        output.close()
        
        return {
            'success': True,
            'filename': filename,
            'content': csv_content,
            'record_count': queryset.count()
        }
    
    @staticmethod
    def export_to_json(queryset, fields=None, filename=None):
        """
        Export queryset to JSON.
        
        Args:
            queryset: Django queryset to export
            fields (list): Fields to include (optional)
            filename (str): Filename for export
            
        Returns:
            dict: Export result with file content
        """
        if not queryset.exists():
            return {'success': False, 'message': 'No data to export'}
        
        if not filename:
            filename = f"export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Get model fields if not specified
        if not fields:
            model = queryset.model
            fields = [field.name for field in model._meta.fields]
        
        # Convert queryset to list of dictionaries
        data = []
        for obj in queryset:
            item = {}
            for field in fields:
                value = getattr(obj, field, '')
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                elif hasattr(value, '__dict__'):
                    # Handle related objects
                    item[field] = str(value)
                else:
                    item[field] = value
            data.append(item)
        
        json_content = json.dumps(data, indent=2, default=str)
        
        return {
            'success': True,
            'filename': filename,
            'content': json_content,
            'record_count': queryset.count()
        }
    
    @staticmethod
    def import_from_csv(csv_content, model_class, field_mapping=None):
        """
        Import data from CSV to model.
        
        Args:
            csv_content (str): CSV content
            model_class: Django model class
            field_mapping (dict): Field mapping (optional)
            
        Returns:
            dict: Import result
        """
        import io
        import csv
        
        if not csv_content:
            return {'success': False, 'message': 'No CSV content provided'}
        
        input_file = io.StringIO(csv_content)
        reader = csv.DictReader(input_file)
        
        created_count = 0
        updated_count = 0
        errors = []
        
        for row_num, row in enumerate(reader, 1):
            try:
                # Map fields if mapping provided
                if field_mapping:
                    mapped_row = {}
                    for csv_field, model_field in field_mapping.items():
                        if csv_field in row:
                            mapped_row[model_field] = row[csv_field]
                    row = mapped_row
                
                # Create or update model instance
                instance, created = model_class.objects.get_or_create(**row)
                
                if created:
                    created_count += 1
                else:
                    # Update existing instance
                    for field, value in row.items():
                        setattr(instance, field, value)
                    instance.save()
                    updated_count += 1
                    
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
        
        return {
            'success': True,
            'created_count': created_count,
            'updated_count': updated_count,
            'error_count': len(errors),
            'errors': errors
        }
    
    @staticmethod
    def import_from_json(json_content, model_class):
        """
        Import data from JSON to model.
        
        Args:
            json_content (str): JSON content
            model_class: Django model class
            
        Returns:
            dict: Import result
        """
        try:
            data = json.loads(json_content)
        except json.JSONDecodeError as e:
            return {'success': False, 'message': f'Invalid JSON: {str(e)}'}
        
        if not isinstance(data, list):
            return {'success': False, 'message': 'JSON must be an array of objects'}
        
        created_count = 0
        updated_count = 0
        errors = []
        
        for item_num, item in enumerate(data, 1):
            try:
                instance, created = model_class.objects.get_or_create(**item)
                
                if created:
                    created_count += 1
                else:
                    # Update existing instance
                    for field, value in item.items():
                        setattr(instance, field, value)
                    instance.save()
                    updated_count += 1
                    
            except Exception as e:
                errors.append(f"Item {item_num}: {str(e)}")
        
        return {
            'success': True,
            'created_count': created_count,
            'updated_count': updated_count,
            'error_count': len(errors),
            'errors': errors
        }
    
    @staticmethod
    def backup_model_data(model_class, start_date=None, end_date=None):
        """
        Backup model data within date range.
        
        Args:
            model_class: Django model class
            start_date (datetime): Start date (optional)
            end_date (datetime): End date (optional)
            
        Returns:
            dict: Backup result
        """
        queryset = model_class.objects.all()
        
        # Apply date filter if model has created_at field
        if hasattr(model_class, 'created_at'):
            if start_date:
                queryset = queryset.filter(created_at__gte=start_date)
            if end_date:
                queryset = queryset.filter(created_at__lte=end_date)
        
        if not queryset.exists():
            return {'success': False, 'message': 'No data to backup'}
        
        # Export to JSON
        export_result = DataHelper.export_to_json(
            queryset,
            filename=f"backup_{model_class.__name__}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        return export_result
    
    @staticmethod
    def restore_model_data(json_content, model_class, overwrite=False):
        """
        Restore model data from JSON backup.
        
        Args:
            json_content (str): JSON backup content
            model_class: Django model class
            overwrite (bool): Whether to overwrite existing data
            
        Returns:
            dict: Restore result
        """
        try:
            data = json.loads(json_content)
        except json.JSONDecodeError as e:
            return {'success': False, 'message': f'Invalid JSON: {str(e)}'}
        
        if not isinstance(data, list):
            return {'success': False, 'message': 'JSON must be an array of objects'}
        
        created_count = 0
        updated_count = 0
        errors = []
        
        for item_num, item in enumerate(data, 1):
            try:
                if overwrite:
                    # Delete existing if it exists
                    if 'id' in item:
                        model_class.objects.filter(id=item['id']).delete()
                    instance = model_class.objects.create(**item)
                    created_count += 1
                else:
                    instance, created = model_class.objects.get_or_create(**item)
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                        
            except Exception as e:
                errors.append(f"Item {item_num}: {str(e)}")
        
        return {
            'success': True,
            'created_count': created_count,
            'updated_count': updated_count,
            'error_count': len(errors),
            'errors': errors
        }


class SecurityHelper:
    """Helper class for security operations."""
    
    @staticmethod
    def generate_secure_token(length=32):
        """
        Generate a secure random token.
        
        Args:
            length (int): Length of the token
            
        Returns:
            str: Generated token
        """
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def hash_data(data, salt=None):
        """
        Hash data with optional salt.
        
        Args:
            data: Data to hash
            salt (str): Salt for hashing
            
        Returns:
            str: Hashed data
        """
        if salt is None:
            salt = settings.SECRET_KEY
        
        combined = f"{salt}{str(data)}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    @staticmethod
    def verify_hash(data, hash_value, salt=None):
        """
        Verify data against hash.
        
        Args:
            data: Original data
            hash_value (str): Hash to verify against
            salt (str): Salt used for hashing
            
        Returns:
            bool: True if hash matches
        """
        computed_hash = SecurityHelper.hash_data(data, salt)
        return computed_hash == hash_value
    
    @staticmethod
    def encrypt_sensitive_data(data):
        """
        Encrypt sensitive data.
        
        Args:
            data: Data to encrypt
            
        Returns:
            str: Encrypted data
        """
        from cryptography.fernet import Fernet
        
        key = settings.SECRET_KEY.encode()
        f = Fernet(key)
        encrypted_data = f.encrypt(str(data).encode())
        
        return encrypted_data.decode()
    
    @staticmethod
    def decrypt_sensitive_data(encrypted_data):
        """
        Decrypt sensitive data.
        
        Args:
            encrypted_data (str): Encrypted data
            
        Returns:
            str: Decrypted data
        """
        from cryptography.fernet import Fernet
        
        key = settings.SECRET_KEY.encode()
        f = Fernet(key)
        decrypted_data = f.decrypt(encrypted_data.encode())
        
        return decrypted_data.decode()
    
    @staticmethod
    def mask_sensitive_info(text, mask_char='*', visible_chars=4):
        """
        Mask sensitive information in text.
        
        Args:
            text (str): Text to mask
            mask_char (str): Character to use for masking
            visible_chars (int): Number of visible characters at start and end
            
        Returns:
            str: Masked text
        """
        if not text or len(text) <= visible_chars * 2:
            return mask_char * len(text) if text else text
        
        start = text[:visible_chars]
        end = text[-visible_chars:]
        middle_length = len(text) - (visible_chars * 2)
        middle = mask_char * middle_length
        
        return f"{start}{middle}{end}"
    
    @staticmethod
    def is_safe_url(url):
        """
        Check if URL is safe for redirect.
        
        Args:
            url (str): URL to check
            
        Returns:
            bool: True if URL is safe
        """
        from django.utils.http import url_has_allowed_host_and_scheme
        
        return url_has_allowed_host_and_scheme(url, allowed_hosts=settings.ALLOWED_HOSTS)
    
    @staticmethod
    def generate_csrf_token():
        """
        Generate CSRF token.
        
        Returns:
            str: CSRF token
        """
        return secrets.token_urlsafe(32)


class NotificationHelper:
    """Helper class for notification operations."""
    
    @staticmethod
    def send_email_notification(tenant, subject, message, to_email=None, template=None, context=None):
        """
        Send email notification to tenant.
        
        Args:
            tenant: Tenant instance
            subject (str): Email subject
            message (str): Email message
            to_email (str): Recipient email (optional)
            template (str): Email template (optional)
            context (dict): Template context (optional)
            
        Returns:
            dict: Send result
        """
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        
        try:
            recipient_email = to_email or tenant.admin_email
            
            if not recipient_email:
                return {'success': False, 'message': 'No recipient email available'}
            
            if template:
                email_body = render_to_string(template, context or {'tenant': tenant})
            else:
                email_body = message
            
            send_mail(
                subject=subject,
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                fail_silently=False
            )
            
            return {'success': True, 'message': 'Email sent successfully'}
            
        except Exception as e:
            return {'success': False, 'message': f'Failed to send email: {str(e)}'}
    
    @staticmethod
    def create_notification(tenant, title, message, notification_type='system', priority='medium', metadata=None):
        """
        Create in-app notification.
        
        Args:
            tenant: Tenant instance
            title (str): Notification title
            message (str): Notification message
            notification_type (str): Type of notification
            priority (str): Priority level
            metadata (dict): Additional metadata
            
        Returns:
            object: Created notification
        """
        from ..models.analytics import TenantNotification
        
        try:
            notification = TenantNotification.objects.create(
                tenant=tenant,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                metadata=metadata or {}
            )
            
            return notification
            
        except Exception as e:
            return None
    
    @staticmethod
    def send_webhook_notification(tenant, event_type, data):
        """
        Send webhook notification.
        
        Args:
            tenant: Tenant instance
            event_type (str): Type of event
            data (dict): Event data
            
        Returns:
            dict: Send result
        """
        from ..models.security import TenantWebhookConfig
        import requests
        
        webhooks = TenantWebhookConfig.objects.filter(
            tenant=tenant,
            is_active=True,
            event_types__contains=[event_type]
        )
        
        results = []
        
        for webhook in webhooks:
            try:
                payload = {
                    'event_type': event_type,
                    'tenant_id': tenant.id,
                    'tenant_name': tenant.name,
                    'timestamp': timezone.now().isoformat(),
                    'data': data
                }
                
                response = requests.post(
                    webhook.url,
                    json=payload,
                    headers={
                        'Content-Type': 'application/json',
                        'X-Webhook-Signature': SecurityHelper.hash_data(payload, webhook.secret)
                    },
                    timeout=30
                )
                
                results.append({
                    'webhook_id': webhook.id,
                    'status_code': response.status_code,
                    'success': response.status_code == 200
                })
                
            except Exception as e:
                results.append({
                    'webhook_id': webhook.id,
                    'error': str(e),
                    'success': False
                })
        
        return {
            'success': True,
            'webhooks_sent': len(results),
            'results': results
        }


class CacheHelper:
    """Helper class for cache operations."""
    
    @staticmethod
    def get_cache_key(prefix, *args):
        """
        Generate cache key.
        
        Args:
            prefix (str): Key prefix
            *args: Additional key components
            
        Returns:
            str: Generated cache key
        """
        key_parts = [prefix] + [str(arg) for arg in args]
        return ':'.join(key_parts)
    
    @staticmethod
    def cache_get(key, default=None):
        """
        Get value from cache.
        
        Args:
            key (str): Cache key
            default: Default value if not found
            
        Returns:
            Cached value or default
        """
        from django.core.cache import cache
        return cache.get(key, default)
    
    @staticmethod
    def cache_set(key, value, timeout=300):
        """
        Set value in cache.
        
        Args:
            key (str): Cache key
            value: Value to cache
            timeout (int): Cache timeout in seconds
            
        Returns:
            bool: True if successful
        """
        from django.core.cache import cache
        return cache.set(key, value, timeout)
    
    @staticmethod
    def cache_delete(key):
        """
        Delete value from cache.
        
        Args:
            key (str): Cache key
            
        Returns:
            bool: True if successful
        """
        from django.core.cache import cache
        return cache.delete(key)
    
    @staticmethod
    def cache_clear():
        """
        Clear all cache.
        
        Returns:
            bool: True if successful
        """
        from django.core.cache import cache
        return cache.clear()
