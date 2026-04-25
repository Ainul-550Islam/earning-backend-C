"""
Tenant Settings ViewSets

This module contains viewsets for tenant settings operations including
configuration management, preferences, and customization.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend

from ..models.core import TenantSettings
from ..serializers.core import TenantSettingsSerializer
from ..viewsets.base import BaseTenantRelatedViewSet


class TenantSettingsViewSet(BaseTenantRelatedViewSet):
    """
    ViewSet for tenant settings operations.
    
    Provides endpoints for:
    - Settings configuration management
    - Preferences updates
    - Feature toggles
    - Settings analytics
    """
    
    queryset = TenantSettings.objects.all()
    serializer_class = TenantSettingsSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['enable_smartlink', 'enable_analytics', 'enable_api_access']
    
    @action(detail=True, methods=['post'])
    def update_preferences(self, request, pk=None):
        """Update tenant preferences."""
        settings = self.get_object()
        preferences = request.data.get('preferences', {})
        
        try:
            # Update preference fields
            for key, value in preferences.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            
            settings.save()
            serializer = self.get_serializer(settings)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def toggle_feature(self, request, pk=None):
        """Toggle a feature setting."""
        settings = self.get_object()
        feature = request.data.get('feature')
        enabled = request.data.get('enabled')
        
        if not feature:
            return Response(
                {'error': 'Feature name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            if hasattr(settings, f'enable_{feature}'):
                setattr(settings, f'enable_{feature}', enabled)
                settings.save()
                
                return Response({
                    'feature': feature,
                    'enabled': enabled,
                    'message': f'Feature {feature} {"enabled" if enabled else "disabled"}'
                })
            else:
                return Response(
                    {'error': f'Feature {feature} not found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def reset_to_defaults(self, request, pk=None):
        """Reset settings to default values."""
        settings = self.get_object()
        
        try:
            # Reset to default values
            settings.enable_smartlink = True
            settings.enable_qr_codes = True
            settings.enable_analytics = True
            settings.enable_api_access = True
            settings.enable_email_notifications = True
            settings.enable_push_notifications = False
            settings.enable_sms_notifications = False
            settings.default_language = 'en'
            settings.default_currency = 'USD'
            settings.default_timezone = 'UTC'
            settings.date_format = 'MM/DD/YYYY'
            settings.time_format = '12h'
            settings.theme = 'light'
            settings.session_timeout_minutes = 120
            settings.password_min_length = 8
            settings.password_require_special_chars = True
            settings.password_require_numbers = True
            settings.password_require_uppercase = True
            settings.password_require_lowercase = True
            settings.two_factor_auth_required = False
            settings.ip_whitelist_enabled = False
            settings.api_rate_limit_per_minute = 100
            settings.api_rate_limit_per_hour = 1000
            settings.api_rate_limit_per_day = 10000
            settings.custom_settings = {}
            
            settings.save()
            
            serializer = self.get_serializer(settings)
            return Response({
                'message': 'Settings reset to defaults',
                'settings': serializer.data
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def update_security_settings(self, request, pk=None):
        """Update security-related settings."""
        settings = self.get_object()
        security_settings = request.data.get('security_settings', {})
        
        try:
            # Update security settings
            if 'password_min_length' in security_settings:
                settings.password_min_length = security_settings['password_min_length']
            
            if 'password_require_special_chars' in security_settings:
                settings.password_require_special_chars = security_settings['password_require_special_chars']
            
            if 'password_require_numbers' in security_settings:
                settings.password_require_numbers = security_settings['password_require_numbers']
            
            if 'password_require_uppercase' in security_settings:
                settings.password_require_uppercase = security_settings['password_require_uppercase']
            
            if 'password_require_lowercase' in security_settings:
                settings.password_require_lowercase = security_settings['password_require_lowercase']
            
            if 'two_factor_auth_required' in security_settings:
                settings.two_factor_auth_required = security_settings['two_factor_auth_required']
            
            if 'ip_whitelist_enabled' in security_settings:
                settings.ip_whitelist_enabled = security_settings['ip_whitelist_enabled']
            
            settings.save()
            serializer = self.get_serializer(settings)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def update_api_settings(self, request, pk=None):
        """Update API-related settings."""
        settings = self.get_object()
        api_settings = request.data.get('api_settings', {})
        
        try:
            # Update API settings
            if 'api_rate_limit_per_minute' in api_settings:
                settings.api_rate_limit_per_minute = api_settings['api_rate_limit_per_minute']
            
            if 'api_rate_limit_per_hour' in api_settings:
                settings.api_rate_limit_per_hour = api_settings['api_rate_limit_per_hour']
            
            if 'api_rate_limit_per_day' in api_settings:
                settings.api_rate_limit_per_day = api_settings['api_rate_limit_per_day']
            
            settings.save()
            serializer = self.get_serializer(settings)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def update_notification_settings(self, request, pk=None):
        """Update notification settings."""
        settings = self.get_object()
        notification_settings = request.data.get('notification_settings', {})
        
        try:
            # Update notification settings
            if 'enable_email_notifications' in notification_settings:
                settings.enable_email_notifications = notification_settings['enable_email_notifications']
            
            if 'enable_push_notifications' in notification_settings:
                settings.enable_push_notifications = notification_settings['enable_push_notifications']
            
            if 'enable_sms_notifications' in notification_settings:
                settings.enable_sms_notifications = notification_settings['enable_sms_notifications']
            
            settings.save()
            serializer = self.get_serializer(settings)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def update_ui_settings(self, request, pk=None):
        """Update UI-related settings."""
        settings = self.get_object()
        ui_settings = request.data.get('ui_settings', {})
        
        try:
            # Update UI settings
            if 'default_language' in ui_settings:
                settings.default_language = ui_settings['default_language']
            
            if 'default_currency' in ui_settings:
                settings.default_currency = ui_settings['default_currency']
            
            if 'default_timezone' in ui_settings:
                settings.default_timezone = ui_settings['default_timezone']
            
            if 'date_format' in ui_settings:
                settings.date_format = ui_settings['date_format']
            
            if 'time_format' in ui_settings:
                settings.time_format = ui_settings['time_format']
            
            if 'theme' in ui_settings:
                settings.theme = ui_settings['theme']
            
            settings.save()
            serializer = self.get_serializer(settings)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def feature_flags(self, request, pk=None):
        """Get all feature flags."""
        settings = self.get_object()
        
        feature_flags = {
            'smartlink': settings.enable_smartlink,
            'qr_codes': settings.enable_qr_codes,
            'analytics': settings.enable_analytics,
            'api_access': settings.enable_api_access,
            'email_notifications': settings.enable_email_notifications,
            'push_notifications': settings.enable_push_notifications,
            'sms_notifications': settings.enable_sms_notifications,
            'two_factor_auth': settings.two_factor_auth_required,
            'ip_whitelist': settings.ip_whitelist_enabled,
        }
        
        return Response(feature_flags)
    
    @action(detail=True, methods=['get'])
    def security_summary(self, request, pk=None):
        """Get security settings summary."""
        settings = self.get_object()
        
        security_summary = {
            'password_policy': {
                'min_length': settings.password_min_length,
                'require_special_chars': settings.password_require_special_chars,
                'require_numbers': settings.password_require_numbers,
                'require_uppercase': settings.password_require_uppercase,
                'require_lowercase': settings.password_require_lowercase,
            },
            'two_factor_auth': {
                'required': settings.two_factor_auth_required,
            },
            'ip_whitelist': {
                'enabled': settings.ip_whitelist_enabled,
            },
            'api_limits': {
                'per_minute': settings.api_rate_limit_per_minute,
                'per_hour': settings.api_rate_limit_per_hour,
                'per_day': settings.api_rate_limit_per_day,
            },
            'session_timeout': settings.session_timeout_minutes,
        }
        
        return Response(security_summary)
    
    @action(detail=True, methods=['get'])
    def notification_preferences(self, request, pk=None):
        """Get notification preferences."""
        settings = self.get_object()
        
        notification_preferences = {
            'email': settings.enable_email_notifications,
            'push': settings.enable_push_notifications,
            'sms': settings.enable_sms_notifications,
        }
        
        return Response(notification_preferences)
    
    @action(detail=True, methods=['get'])
    def ui_preferences(self, request, pk=None):
        """Get UI preferences."""
        settings = self.get_object()
        
        ui_preferences = {
            'language': settings.default_language,
            'currency': settings.default_currency,
            'timezone': settings.default_timezone,
            'date_format': settings.date_format,
            'time_format': settings.time_format,
            'theme': settings.theme,
        }
        
        return Response(ui_preferences)
    
    @action(detail=True, methods=['post'])
    def update_custom_settings(self, request, pk=None):
        """Update custom settings."""
        settings = self.get_object()
        custom_settings = request.data.get('custom_settings', {})
        
        try:
            # Merge with existing custom settings
            current_custom = settings.custom_settings or {}
            current_custom.update(custom_settings)
            settings.custom_settings = current_custom
            settings.save()
            
            return Response({
                'message': 'Custom settings updated',
                'custom_settings': settings.custom_settings
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def get_custom_settings(self, request, pk=None):
        """Get custom settings."""
        settings = self.get_object()
        
        return Response({
            'custom_settings': settings.custom_settings or {}
        })
    
    @action(detail=True, methods=['post'])
    def validate_settings(self, request, pk=None):
        """Validate current settings configuration."""
        settings = self.get_object()
        
        validation_errors = []
        
        try:
            # Validate password policy
            if settings.password_min_length < 6:
                validation_errors.append('Password minimum length should be at least 6')
            
            if settings.password_min_length > 128:
                validation_errors.append('Password minimum length should not exceed 128')
            
            # Validate API rate limits
            if settings.api_rate_limit_per_minute < 1:
                validation_errors.append('API rate limit per minute should be at least 1')
            
            if settings.api_rate_limit_per_hour < settings.api_rate_limit_per_minute:
                validation_errors.append('Hourly rate limit should be at least as high as minute limit')
            
            if settings.api_rate_limit_per_day < settings.api_rate_limit_per_hour:
                validation_errors.append('Daily rate limit should be at least as high as hourly limit')
            
            # Validate session timeout
            if settings.session_timeout_minutes < 5:
                validation_errors.append('Session timeout should be at least 5 minutes')
            
            if settings.session_timeout_minutes > 1440:  # 24 hours
                validation_errors.append('Session timeout should not exceed 24 hours')
            
            return Response({
                'valid': len(validation_errors) == 0,
                'errors': validation_errors
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def settings_templates(self, request):
        """Get available settings templates."""
        templates = {
            'basic': {
                'enable_smartlink': True,
                'enable_qr_codes': True,
                'enable_analytics': True,
                'enable_api_access': True,
                'enable_email_notifications': True,
                'enable_push_notifications': False,
                'enable_sms_notifications': False,
                'default_language': 'en',
                'default_currency': 'USD',
                'default_timezone': 'UTC',
                'theme': 'light',
                'session_timeout_minutes': 120,
                'password_min_length': 8,
                'password_require_special_chars': True,
                'password_require_numbers': True,
                'password_require_uppercase': True,
                'password_require_lowercase': True,
                'two_factor_auth_required': False,
                'ip_whitelist_enabled': False,
                'api_rate_limit_per_minute': 100,
                'api_rate_limit_per_hour': 1000,
                'api_rate_limit_per_day': 10000,
            },
            'enterprise': {
                'enable_smartlink': True,
                'enable_qr_codes': True,
                'enable_analytics': True,
                'enable_api_access': True,
                'enable_email_notifications': True,
                'enable_push_notifications': True,
                'enable_sms_notifications': True,
                'default_language': 'en',
                'default_currency': 'USD',
                'default_timezone': 'UTC',
                'theme': 'light',
                'session_timeout_minutes': 60,
                'password_min_length': 12,
                'password_require_special_chars': True,
                'password_require_numbers': True,
                'password_require_uppercase': True,
                'password_require_lowercase': True,
                'two_factor_auth_required': True,
                'ip_whitelist_enabled': True,
                'api_rate_limit_per_minute': 1000,
                'api_rate_limit_per_hour': 60000,
                'api_rate_limit_per_day': 1000000,
            },
            'high_security': {
                'enable_smartlink': True,
                'enable_qr_codes': False,
                'enable_analytics': True,
                'enable_api_access': True,
                'enable_email_notifications': True,
                'enable_push_notifications': False,
                'enable_sms_notifications': True,
                'default_language': 'en',
                'default_currency': 'USD',
                'default_timezone': 'UTC',
                'theme': 'light',
                'session_timeout_minutes': 30,
                'password_min_length': 16,
                'password_require_special_chars': True,
                'password_require_numbers': True,
                'password_require_uppercase': True,
                'password_require_lowercase': True,
                'two_factor_auth_required': True,
                'ip_whitelist_enabled': True,
                'api_rate_limit_per_minute': 60,
                'api_rate_limit_per_hour': 3600,
                'api_rate_limit_per_day': 86400,
            },
        }
        
        return Response(templates)
    
    @action(detail=True, methods=['post'])
    def apply_template(self, request, pk=None):
        """Apply a settings template."""
        settings = self.get_object()
        template_name = request.data.get('template')
        
        if not template_name:
            return Response(
                {'error': 'Template name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get templates
        from .settings import TenantSettingsViewSet
        templates = TenantSettingsViewSet.settings_templates(None)
        
        if template_name not in templates:
            return Response(
                {'error': f'Template {template_name} not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        template_settings = templates[template_name]
        
        try:
            # Apply template settings
            for field, value in template_settings.items():
                if hasattr(settings, field):
                    setattr(settings, field, value)
            
            settings.save()
            
            serializer = self.get_serializer(settings)
            return Response({
                'message': f'Template {template_name} applied successfully',
                'settings': serializer.data
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
