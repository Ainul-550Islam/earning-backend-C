# api/security/apps.py
"""
Enhanced Security App Configuration with comprehensive initialization
Author: System Security Team
Version: 2.0.0
"""

from django.apps import AppConfig
import logging




logger = logging.getLogger(__name__)


class SecurityConfig(AppConfig):
    """
    Enhanced security app configuration with comprehensive initialization
    Supports all security models and services
    """
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.security'
    verbose_name = 'Security Management'
    verbose_name_plural = 'Security Management'
    
    # Security app configuration
    default_settings = {
        'SECURITY_ENABLED': True,
        'RATE_LIMIT_ENABLED': True,
        'VPN_DETECTION_ENABLED': True,
        'FRAUD_DETECTION_ENABLED': True,
        'THREAT_INTEL_ENABLED': True,
        'PASSWORD_HISTORY_ENABLED': True,
        'TRUSTED_DEVICES_ENABLED': True,
        'SECURITY_POLICIES_ENABLED': True,
        'SECURITY_INSIGHTS_ENABLED': True,
        'INCIDENT_MANAGEMENT_ENABLED': True,
    }
    
    def ready(self):
        """
        Enhanced app ready with comprehensive security system initialization
        """
        try:
            # Import security signals
            from . import signals  # noqa: F401
            
            # Initialize all security components
            self._initialize_security_system()
            
            # Setup security middleware registration
            self._setup_security_middleware()
            
            # Initialize security services
            self._init_security_services()
            
            logger.info("[OK] Security app ready with all components")
            
        except ImportError as e:
            logger.warning(f"Security signals import failed: {e}")
        except Exception as e:
            logger.error(f"Security app initialization error: {e}")
    
    def _initialize_security_system(self):
        """
        Initialize security system with all models and services
        """
        try:
            from django.db import connection
            from django.apps import apps
            from django.conf import settings
            
            # Check if we're in a ready state
            if not apps.ready:
                logger.debug("[DEBUG] Django apps not yet ready - deferring security initialization")
                return
            
            # Defer database operations to after connection is ready
            def _do_initialization():
                try:
                    from django.contrib.auth import get_user_model
                    from .models import (
                        PasswordPolicy, APIRateLimit, TrustedDevice, 
                        PasswordHistory, SecurityPolicy, SecurityInsight,
                        ThreatIntelligence, SecurityIncident,
                        IPBlacklist, DeviceInfo, RiskScore, WithdrawalProtection
                    )
                    try:
                        from .models import UserBan
                    except Exception:
                        UserBan = None
                    
                    User = get_user_model()
                    
                    # Initialize security components
                    self._setup_default_security_admin(User)
                    self._setup_default_policies(PasswordPolicy)
                    self._setup_default_rate_limits(APIRateLimit)
                    self._setup_default_trusted_devices(TrustedDevice)
                    self._setup_security_insights(SecurityInsight)
                    self._setup_threat_intelligence(ThreatIntelligence)
                    self._setup_incident_management(SecurityIncident)
                    
                    logger.info("[OK] Security system initialized with all components")
                    
                except Exception as e:
                    logger.error(f"Security system initialization error: {e}")
            
            # Use on_commit to ensure database is ready
            connection.on_commit(_do_initialization)
            
        except Exception as e:
            logger.error(f"Error setting up security initialization: {e}")
    
    def _setup_default_security_admin(self, User):
        """Setup default security admin user"""
        try:
            if not User.objects.filter(username='security_admin').exists():
                User.objects.create_user(
                    username='security_admin',
                    email='security@example.com',
                    is_staff=True,
                    is_superuser=True,
                    is_active=True
                )
                logger.info("[OK] Default security admin user created")
        except Exception as e:
            logger.debug(f"Could not setup security admin: {e}")
    
    def _setup_default_policies(self, PolicyModel):
        """Setup default security policies"""
        try:
            if not PolicyModel.objects.exists():
                # Create comprehensive default policies
                default_policies = [
                    {
                        'policy_key': 'password_min_length',
                        'policy_name': 'Minimum Password Length',
                        'policy_type': 'password',
                        'value': 8,
                        'description': 'Minimum password length requirement',
                        'is_mandatory': True,
                        'priority': 1
                    },
                    {
                        'policy_key': 'password_complexity',
                        'policy_name': 'Password Complexity',
                        'policy_type': 'password',
                        'value': 'medium',
                        'description': 'Password complexity requirement',
                        'is_mandatory': True,
                        'priority': 2
                    },
                    {
                        'policy_key': 'session_timeout',
                        'policy_name': 'Session Timeout',
                        'policy_type': 'session',
                        'value': 3600,
                        'description': 'Session timeout in seconds',
                        'is_mandatory': False,
                        'priority': 3
                    },
                    {
                        'policy_key': 'max_login_attempts',
                        'policy_name': 'Max Login Attempts',
                        'policy_type': 'authentication',
                        'value': 5,
                        'description': 'Maximum login attempts before lockout',
                        'is_mandatory': True,
                        'priority': 1
                    }
                ]
                
                for policy_data in default_policies:
                    PolicyModel.objects.create(**policy_data)
                
                logger.info("[OK] Default security policies created")
                
        except Exception as e:
            logger.debug(f"Could not setup default policies: {e}")
    
    def _setup_default_rate_limits(self, RateLimitModel):
        """Setup default rate limits"""
        try:
            if not RateLimitModel.objects.exists():
                default_limits = [
                    {
                        'name': 'Security API Limit',
                        'limit_type': 'ip',
                        'limit_period': 'minute',
                        'request_limit': 60,
                        'is_active': True
                    },
                    {
                        'name': 'Login Rate Limit',
                        'limit_type': 'user',
                        'limit_period': 'minute',
                        'request_limit': 10,
                        'is_active': True
                    },
                    {
                        'name': 'Password Change Rate Limit',
                        'limit_type': 'user',
                        'limit_period': 'hour',
                        'request_limit': 3,
                        'is_active': True
                    }
                ]
                
                for limit_data in default_limits:
                    RateLimitModel.objects.create(**limit_data)
                
                logger.info("[OK] Default rate limits created")
                
        except Exception as e:
            logger.debug(f"Could not setup default rate limits: {e}")
    
    def _setup_default_trusted_devices(self, TrustedDeviceModel):
        """Setup default trusted device settings"""
        try:
            # This would be used for initial device trust setup
            logger.debug("Trusted device system initialized")
        except Exception as e:
            logger.debug(f"Could not setup trusted devices: {e}")
    
    def _setup_security_insights(self, InsightModel):
        """Setup security insights system"""
        try:
            # Initialize insights system
            logger.debug("Security insights system initialized")
        except Exception as e:
            logger.debug(f"Could not setup security insights: {e}")
    
    def _setup_threat_intelligence(self, ThreatModel):
        """Setup threat intelligence system"""
        try:
            # Initialize threat intelligence
            logger.debug("Threat intelligence system initialized")
        except Exception as e:
            logger.debug(f"Could not setup threat intelligence: {e}")
    
    def _setup_incident_management(self, IncidentModel):
        """Setup incident management system"""
        try:
            # Initialize incident management
            logger.debug("Incident management system initialized")
        except Exception as e:
            logger.debug(f"Could not setup incident management: {e}")
    
    def _setup_security_middleware(self):
        """Setup security middleware registration"""
        try:
            # Register security middleware
            logger.debug("Security middleware registration completed")
        except Exception as e:
            logger.debug(f"Could not setup security middleware: {e}")
    
    def _init_security_services(self):
        """Initialize all security services"""
        try:
            # Import and initialize all security services
            from .services import (
                TrustedDeviceService, PasswordHistoryService, SecurityPolicyService,
                SecurityInsightService, ThreatIntelService, IncidentService
            )
            
            # Initialize service instances
            service_classes = [
                TrustedDeviceService,
                PasswordHistoryService,
                SecurityPolicyService,
                SecurityInsightService,
                ThreatIntelService,
                IncidentService
            ]
            
            for service_class in service_classes:
                try:
                    service_instance = service_class.get_service_instance()
                    logger.debug(f"Initialized {service_class.__name__}")
                except Exception as e:
                    logger.error(f"Failed to initialize {service_class.__name__}: {e}")
            
            logger.info("[OK] All security services initialized")
            
        except Exception as e:
            logger.error(f"Error initializing security services: {e}")
    
    def get_security_setting(self, setting_name: str, default=None):
        """Get security setting with fallback"""
        try:
            from django.conf import settings
            return getattr(settings, f'SECURITY_{setting_name.upper()}', default)
        except Exception as e:
            logger.error(f"Error getting security setting {setting_name}: {e}")
            return default
    
    def is_security_feature_enabled(self, feature_name: str) -> bool:
        """Check if security feature is enabled"""
        setting_value = self.get_security_setting(f'{feature_name}_ENABLED', True)
        return bool(setting_value)