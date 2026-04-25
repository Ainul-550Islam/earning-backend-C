"""
Configuration Database Model

This module contains Configuration model and related models
for managing system configuration and settings.
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


class Configuration(AdvertiserPortalBaseModel, AuditModel):
    """
    Main configuration model for managing system settings.
    
    This model stores configuration values for various
    system components and features.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='configurations',
        null=True,
        blank=True,
        help_text="Associated advertiser (null for global config)"
    )
    
    # Configuration Key and Value
    key = models.CharField(
        max_length=255,
        help_text="Configuration key"
    )
    value = models.TextField(
        help_text="Configuration value"
    )
    value_type = models.CharField(
        max_length=50,
        choices=[
            ('string', 'String'),
            ('integer', 'Integer'),
            ('float', 'Float'),
            ('boolean', 'Boolean'),
            ('json', 'JSON'),
            ('encrypted', 'Encrypted')
        ],
        default='string',
        help_text="Type of configuration value"
    )
    
    # Configuration Metadata
    category = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Configuration category"
    )
    subcategory = models.CharField(
        max_length=100,
        blank=True,
        help_text="Configuration subcategory"
    )
    description = models.TextField(
        blank=True,
        help_text="Configuration description"
    )
    
    # Validation and Constraints
    validation_rules = models.JSONField(
        default=dict,
        blank=True,
        help_text="Validation rules for the configuration"
    )
    default_value = models.TextField(
        blank=True,
        help_text="Default value for this configuration"
    )
    
    # Access Control
    is_public = models.BooleanField(
        default=False,
        help_text="Whether configuration is publicly accessible"
    )
    is_readonly = models.BooleanField(
        default=False,
        help_text="Whether configuration is read-only"
    )
    required = models.BooleanField(
        default=False,
        help_text="Whether configuration is required"
    )
    
    # Environment and Versioning
    environment = models.CharField(
        max_length=50,
        choices=[
            ('development', 'Development'),
            ('staging', 'Staging'),
            ('production', 'Production'),
            ('all', 'All Environments')
        ],
        default='all',
        help_text="Environment this configuration applies to"
    )
    version = models.IntegerField(
        default=1,
        help_text="Configuration version"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether configuration is active"
    )
    
    class Meta:
        db_table = 'configurations'
        verbose_name = 'Configuration'
        verbose_name_plural = 'Configurations'
        unique_together = ['advertiser', 'key', 'environment']
        indexes = [
            models.Index(fields=['advertiser', 'category'], name='idx_advertiser_category_196'),
            models.Index(fields=['key'], name='idx_key_197'),
            models.Index(fields=['category', 'subcategory'], name='idx_category_subcategory_198'),
            models.Index(fields=['environment'], name='idx_environment_199'),
            models.Index(fields=['is_active'], name='idx_is_active_200'),
        ]
    
    def __str__(self) -> str:
        advertiser_name = self.advertiser.company_name if self.advertiser else 'Global'
        return f"{self.key} ({advertiser_name})"
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate value based on type
        if self.value_type == 'integer':
            try:
                int(self.value)
            except ValueError:
                raise ValidationError("Value must be an integer")
        elif self.value_type == 'float':
            try:
                float(self.value)
            except ValueError:
                raise ValidationError("Value must be a float")
        elif self.value_type == 'boolean':
            if self.value.lower() not in ['true', 'false', '1', '0']:
                raise ValidationError("Value must be a boolean")
        elif self.value_type == 'json':
            try:
                import json
                json.loads(self.value)
            except json.JSONDecodeError:
                raise ValidationError("Value must be valid JSON")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Encrypt sensitive values
        if self.value_type == 'encrypted':
            self.value = self.encrypt_value(self.value)
        
        # Validate configuration
        self.validate_configuration()
        
        super().save(*args, **kwargs)
    
    def encrypt_value(self, value: str) -> str:
        """Encrypt sensitive configuration value."""
        from cryptography.fernet import Fernet
        from django.conf import settings
        
        try:
            key = getattr(settings, 'ENCRYPTION_KEY', None)
            if key:
                fernet = Fernet(key.encode())
                return fernet.encrypt(value.encode()).decode()
        except Exception:
            pass
        
        return value  # Return as-is if encryption fails
    
    def decrypt_value(self) -> str:
        """Decrypt sensitive configuration value."""
        if self.value_type != 'encrypted':
            return self.value
        
        from cryptography.fernet import Fernet
        from django.conf import settings
        
        try:
            key = getattr(settings, 'ENCRYPTION_KEY', None)
            if key:
                fernet = Fernet(key.encode())
                return fernet.decrypt(self.value.encode()).decode()
        except Exception:
            pass
        
        return self.value  # Return as-is if decryption fails
    
    def validate_configuration(self) -> None:
        """Validate configuration value against rules."""
        if not self.validation_rules:
            return
        
        rules = self.validation_rules
        actual_value = self.get_typed_value()
        
        # Validate min/max for numeric types
        if self.value_type in ['integer', 'float']:
            if 'min_value' in rules and actual_value < rules['min_value']:
                raise ValidationError(f"Value must be at least {rules['min_value']}")
            if 'max_value' in rules and actual_value > rules['max_value']:
                raise ValidationError(f"Value must be at most {rules['max_value']}")
        
        # Validate choices
        if 'choices' in rules:
            choices = rules['choices']
            if actual_value not in choices:
                raise ValidationError(f"Value must be one of: {choices}")
        
        # Validate regex pattern
        if 'pattern' in rules:
            import re
            pattern = rules['pattern']
            if not re.match(pattern, str(actual_value)):
                raise ValidationError(f"Value must match pattern: {pattern}")
        
        # Validate length for string types
        if self.value_type == 'string':
            if 'min_length' in rules and len(actual_value) < rules['min_length']:
                raise ValidationError(f"Value must be at least {rules['min_length']} characters")
            if 'max_length' in rules and len(actual_value) > rules['max_length']:
                raise ValidationError(f"Value must be at most {rules['max_length']} characters")
    
    def get_typed_value(self) -> Any:
        """Get configuration value converted to its type."""
        if self.value_type == 'encrypted':
            value = self.decrypt_value()
        else:
            value = self.value
        
        if self.value_type == 'string':
            return value
        elif self.value_type == 'integer':
            return int(value)
        elif self.value_type == 'float':
            return float(value)
        elif self.value_type == 'boolean':
            return value.lower() in ['true', '1']
        elif self.value_type == 'json':
            import json
            return json.loads(value)
        else:
            return value
    
    def set_value(self, value: Any) -> None:
        """Set configuration value with type conversion."""
        if self.value_type == 'string':
            self.value = str(value)
        elif self.value_type == 'integer':
            self.value = str(int(value))
        elif self.value_type == 'float':
            self.value = str(float(value))
        elif self.value_type == 'boolean':
            self.value = str(bool(value)).lower()
        elif self.value_type == 'json':
            import json
            self.value = json.dumps(value)
        elif self.value_type == 'encrypted':
            self.value = str(value)
        else:
            self.value = str(value)
    
    @classmethod
    def get_config(cls, key: str, advertiser: Optional['Advertiser'] = None,
                   environment: str = 'production', default: Any = None) -> Any:
        """Get configuration value."""
        try:
            config = cls.objects.get(
                key=key,
                advertiser=advertiser,
                environment__in=[environment, 'all'],
                is_active=True
            )
            return config.get_typed_value()
        except cls.DoesNotExist:
            # Try to get global config if advertiser-specific not found
            if advertiser:
                try:
                    config = cls.objects.get(
                        key=key,
                        advertiser__isnull=True,
                        environment__in=[environment, 'all'],
                        is_active=True
                    )
                    return config.get_typed_value()
                except cls.DoesNotExist:
                    pass
            
            return default
    
    @classmethod
    def set_config(cls, key: str, value: Any, advertiser: Optional['Advertiser'] = None,
                   environment: str = 'production', category: str = 'general',
                   description: str = '', value_type: str = 'string',
                   validation_rules: Optional[Dict[str, Any]] = None) -> 'Configuration':
        """Set configuration value."""
        config, created = cls.objects.get_or_create(
            key=key,
            advertiser=advertiser,
            environment=environment,
            defaults={
                'value': str(value),
                'value_type': value_type,
                'category': category,
                'description': description,
                'validation_rules': validation_rules or {}
            }
        )
        
        if not created:
            config.set_value(value)
            config.save(update_fields=['value'])
        
        return config
    
    @classmethod
    def delete_config(cls, key: str, advertiser: Optional['Advertiser'] = None,
                      environment: str = 'production') -> bool:
        """Delete configuration."""
        try:
            config = cls.objects.get(
                key=key,
                advertiser=advertiser,
                environment=environment
            )
            config.delete()
            return True
        except cls.DoesNotExist:
            return False
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary."""
        return {
            'basic_info': {
                'key': self.key,
                'category': self.category,
                'subcategory': self.subcategory,
                'description': self.description,
                'value_type': self.value_type
            },
            'value': {
                'value': self.get_typed_value(),
                'default_value': self.default_value,
                'is_encrypted': self.value_type == 'encrypted'
            },
            'access': {
                'is_public': self.is_public,
                'is_readonly': self.is_readonly,
                'required': self.required
            },
            'environment': {
                'environment': self.environment,
                'version': self.version,
                'is_active': self.is_active
            },
            'validation': {
                'validation_rules': self.validation_rules
            },
            'advertiser': {
                'id': str(self.advertiser.id) if self.advertiser else None,
                'company_name': self.advertiser.company_name if self.advertiser else 'Global'
            }
        }


class FeatureFlag(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing feature flags.
    """
    
    # Basic Information
    name = models.CharField(
        max_length=255,
        help_text="Feature flag name"
    )
    key = models.CharField(
        max_length=100,
        unique=True,
        help_text="Feature flag key"
    )
    description = models.TextField(
        blank=True,
        help_text="Feature description"
    )
    
    # Flag Configuration
    is_enabled = models.BooleanField(
        default=False,
        help_text="Whether feature is enabled"
    )
    rollout_percentage = models.IntegerField(
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Rollout percentage (0-100)"
    )
    
    # Targeting
    target_advertisers = models.ManyToManyField(
        'advertiser_portal.Advertiser',
        blank=True,
        related_name='feature_flags',
        help_text="Target specific advertisers"
    )
    target_users = models.ManyToManyField(settings.AUTH_USER_MODEL,
        blank=True,
        related_name='feature_flags',
        help_text="Target specific users"
    )
    targeting_rules = models.JSONField(
        default=dict,
        blank=True,
        help_text="Advanced targeting rules"
    )
    
    # Environment
    environment = models.CharField(
        max_length=50,
        choices=[
            ('development', 'Development'),
            ('staging', 'Staging'),
            ('production', 'Production'),
            ('all', 'All Environments')
        ],
        default='all',
        help_text="Environment this flag applies to"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether flag is active"
    )
    
    class Meta:
        db_table = 'feature_flags'
        verbose_name = 'Feature Flag'
        verbose_name_plural = 'Feature Flags'
        indexes = [
            models.Index(fields=['key'], name='idx_key_201'),
            models.Index(fields=['is_enabled'], name='idx_is_enabled_202'),
            models.Index(fields=['environment'], name='idx_environment_203'),
            models.Index(fields=['is_active'], name='idx_is_active_204'),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({'Enabled' if self.is_enabled else 'Disabled'})"
    
    def is_enabled_for_user(self, user: 'User', advertiser: Optional['Advertiser'] = None) -> bool:
        """Check if feature is enabled for specific user."""
        if not self.is_active or not self.is_enabled:
            return False
        
        # Check environment
        from django.conf import settings
        current_env = getattr(settings, 'ENVIRONMENT', 'development')
        if self.environment != 'all' and self.environment != current_env:
            return False
        
        # Check advertiser targeting
        if advertiser and self.target_advertisers.exists():
            if not self.target_advertisers.filter(id=advertiser.id).exists():
                return False
        
        # Check user targeting
        if self.target_users.exists():
            if not self.target_users.filter(id=user.id).exists():
                return False
        
        # Check rollout percentage
        if self.rollout_percentage < 100:
            import hashlib
            user_hash = int(hashlib.md5(f"{self.key}:{user.id}".encode()).hexdigest(), 16)
            if (user_hash % 100) >= self.rollout_percentage:
                return False
        
        # Check advanced targeting rules
        if self.targeting_rules:
            if not self._evaluate_targeting_rules(user, advertiser):
                return False
        
        return True
    
    def _evaluate_targeting_rules(self, user: 'User', advertiser: Optional['Advertiser'] = None) -> bool:
        """Evaluate advanced targeting rules."""
        rules = self.targeting_rules
        
        # Check user attributes
        if 'user_attributes' in rules:
            user_rules = rules['user_attributes']
            for attr, expected in user_rules.items():
                if getattr(user, attr, None) != expected:
                    return False
        
        # Check advertiser attributes
        if advertiser and 'advertiser_attributes' in rules:
            adv_rules = rules['advertiser_attributes']
            for attr, expected in adv_rules.items():
                if getattr(advertiser, attr, None) != expected:
                    return False
        
        # Check custom conditions
        if 'custom_conditions' in rules:
            # This would implement custom condition evaluation
            pass
        
        return True
    
    @classmethod
    def is_feature_enabled(cls, key: str, user: 'User', advertiser: Optional['Advertiser'] = None) -> bool:
        """Check if feature is enabled for user."""
        try:
            flag = cls.objects.get(key=key, is_active=True)
            return flag.is_enabled_for_user(user, advertiser)
        except cls.DoesNotExist:
            return False
    
    @classmethod
    def enable_feature(cls, key: str, rollout_percentage: int = 100) -> 'FeatureFlag':
        """Enable feature flag."""
        flag, created = cls.objects.get_or_create(
            key=key,
            defaults={
                'name': key.replace('_', ' ').title(),
                'is_enabled': True,
                'rollout_percentage': rollout_percentage
            }
        )
        
        if not created:
            flag.is_enabled = True
            flag.rollout_percentage = rollout_percentage
            flag.save(update_fields=['is_enabled', 'rollout_percentage'])
        
        return flag
    
    @classmethod
    def disable_feature(cls, key: str) -> bool:
        """Disable feature flag."""
        try:
            flag = cls.objects.get(key=key, is_active=True)
            flag.is_enabled = False
            flag.save(update_fields=['is_enabled'])
            return True
        except cls.DoesNotExist:
            return False


class SystemSetting(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing system-wide settings.
    """
    
    # Basic Information
    key = models.CharField(
        max_length=255,
        unique=True,
        help_text="Setting key"
    )
    name = models.CharField(
        max_length=255,
        help_text="Setting name"
    )
    description = models.TextField(
        blank=True,
        help_text="Setting description"
    )
    
    # Setting Value
    value = models.TextField(
        help_text="Setting value"
    )
    value_type = models.CharField(
        max_length=50,
        choices=[
            ('string', 'String'),
            ('integer', 'Integer'),
            ('float', 'Float'),
            ('boolean', 'Boolean'),
            ('json', 'JSON')
        ],
        default='string',
        help_text="Type of setting value"
    )
    
    # Category and Group
    category = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Setting category"
    )
    group = models.CharField(
        max_length=100,
        blank=True,
        help_text="Setting group"
    )
    
    # UI Configuration
    display_name = models.CharField(
        max_length=255,
        help_text="Display name for UI"
    )
    help_text = models.TextField(
        blank=True,
        help_text="Help text for UI"
    )
    input_type = models.CharField(
        max_length=50,
        choices=[
            ('text', 'Text Input'),
            ('textarea', 'Text Area'),
            ('number', 'Number Input'),
            ('checkbox', 'Checkbox'),
            ('select', 'Select Dropdown'),
            ('multiselect', 'Multi-Select'),
            ('radio', 'Radio Button'),
            ('file', 'File Upload')
        ],
        default='text',
        help_text="Input type for UI"
    )
    
    # Validation
    validation_rules = models.JSONField(
        default=dict,
        blank=True,
        help_text="Validation rules"
    )
    choices = models.JSONField(
        default=list,
        blank=True,
        help_text="Choices for select/radio inputs"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether setting is active"
    )
    is_required = models.BooleanField(
        default=False,
        help_text="Whether setting is required"
    )
    
    class Meta:
        db_table = 'ap_system_settings'
        verbose_name = 'System Setting'
        verbose_name_plural = 'System Settings'
        indexes = [
            models.Index(fields=['category'], name='idx_category_205'),
            models.Index(fields=['group'], name='idx_group_206'),
            models.Index(fields=['is_active'], name='idx_is_active_207'),
        ]
    
    def __str__(self) -> str:
        return self.display_name
    
    def get_typed_value(self) -> Any:
        """Get setting value converted to its type."""
        if self.value_type == 'string':
            return self.value
        elif self.value_type == 'integer':
            return int(self.value)
        elif self.value_type == 'float':
            return float(self.value)
        elif self.value_type == 'boolean':
            return self.value.lower() in ['true', '1']
        elif self.value_type == 'json':
            import json
            return json.loads(self.value)
        else:
            return self.value
    
    def set_value(self, value: Any) -> None:
        """Set setting value with type conversion."""
        if self.value_type == 'string':
            self.value = str(value)
        elif self.value_type == 'integer':
            self.value = str(int(value))
        elif self.value_type == 'float':
            self.value = str(float(value))
        elif self.value_type == 'boolean':
            self.value = str(bool(value)).lower()
        elif self.value_type == 'json':
            import json
            self.value = json.dumps(value)
        else:
            self.value = str(value)
    
    @classmethod
    def get_setting(cls, key: str, default: Any = None) -> Any:
        """Get system setting value."""
        try:
            setting = cls.objects.get(key=key, is_active=True)
            return setting.get_typed_value()
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_setting(cls, key: str, value: Any, name: str = '', description: str = '',
                   category: str = 'general', value_type: str = 'string') -> 'SystemSetting':
        """Set system setting value."""
        setting, created = cls.objects.get_or_create(
            key=key,
            defaults={
                'name': name or key.replace('_', ' ').title(),
                'display_name': name or key.replace('_', ' ').title(),
                'description': description,
                'value': str(value),
                'value_type': value_type,
                'category': category
            }
        )
        
        if not created:
            setting.set_value(value)
            setting.save(update_fields=['value'])
        
        return setting


class ThemeConfiguration(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing UI theme configurations.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='theme_configurations',
        help_text="Associated advertiser"
    )
    name = models.CharField(
        max_length=255,
        help_text="Theme name"
    )
    
    # Theme Colors
    primary_color = models.CharField(
        max_length=7,
        default='#007bff',
        help_text="Primary color (hex)"
    )
    secondary_color = models.CharField(
        max_length=7,
        default='#6c757d',
        help_text="Secondary color (hex)"
    )
    accent_color = models.CharField(
        max_length=7,
        default='#28a745',
        help_text="Accent color (hex)"
    )
    background_color = models.CharField(
        max_length=7,
        default='#ffffff',
        help_text="Background color (hex)"
    )
    text_color = models.CharField(
        max_length=7,
        default='#333333',
        help_text="Text color (hex)"
    )
    
    # Typography
    font_family = models.CharField(
        max_length=100,
        default='Arial, sans-serif',
        help_text="Font family"
    )
    font_size = models.CharField(
        max_length=50,
        default='14px',
        help_text="Base font size"
    )
    
    # Layout
    layout_style = models.CharField(
        max_length=50,
        choices=[
            ('default', 'Default'),
            ('compact', 'Compact'),
            ('spacious', 'Spacious'),
            ('minimal', 'Minimal')
        ],
        default='default',
        help_text="Layout style"
    )
    
    # Custom CSS
    custom_css = models.TextField(
        blank=True,
        help_text="Custom CSS rules"
    )
    
    # Status
    is_active = models.BooleanField(
        default=False,
        help_text="Whether theme is active"
    )
    
    class Meta:
        db_table = 'theme_configurations'
        verbose_name = 'Theme Configuration'
        verbose_name_plural = 'Theme Configurations'
        unique_together = ['advertiser', 'name']
        indexes = [
            models.Index(fields=['advertiser', 'is_active'], name='idx_advertiser_is_active_208'),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.advertiser.company_name})"
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Ensure only one active theme per advertiser
        if self.is_active:
            ThemeConfiguration.objects.filter(
                advertiser=self.advertiser,
                is_active=True
            ).exclude(id=self.id).update(is_active=False)
        
        super().save(*args, **kwargs)
    
    def get_theme_variables(self) -> Dict[str, str]:
        """Get theme variables as CSS variables."""
        return {
            '--primary-color': self.primary_color,
            '--secondary-color': self.secondary_color,
            '--accent-color': self.accent_color,
            '--background-color': self.background_color,
            '--text-color': self.text_color,
            '--font-family': self.font_family,
            '--font-size': self.font_size
        }
