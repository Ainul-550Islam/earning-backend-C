# api/security/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class SecurityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.security'
    
    def ready(self):
        try:
            import api.security.signals  # noqa: F401
        except ImportError:
            pass
        
        # Initialize security system after all models are loaded
        self._initialize_security_system()
    
    def _initialize_security_system(self):
        """Initialize security system only after Django is ready"""
        try:
            from django.db import connection
            from django.apps import apps
            
            # Check if we're in a ready state
            if not apps.ready:
                logger.debug("[DEBUG] Django apps not yet ready - will defer security initialization to on_commit()")
                return
            
            # Defer database operations to after connection is ready
            def _do_initialization():
                try:
                    from django.contrib.auth import get_user_model
                    from .models import PasswordPolicy, APIRateLimit
                    
                    User = get_user_model()
                    
                    # Check for default security admin user
                    try:
                        if not User.objects.filter(username='security_admin').exists():
                            logger.debug("Security admin user not found (expected in initial setup)")
                    except Exception as e:
                        logger.debug(f"Could not check security admin user: {e}")
                    
                    # Create default password policy if needed
                    try:
                        if not PasswordPolicy.objects.exists():
                            PasswordPolicy.objects.create(
                                name="Default Password Policy",
                                min_length=8,
                                require_uppercase=True,
                                require_lowercase=True,
                                require_digits=True,
                                require_special_chars=True
                            )
                            logger.info("[OK] Default password policy created")
                    except Exception as e:
                        logger.debug(f"Could not initialize password policy: {e}")
                    
                    # Create default API rate limit if needed
                    try:
                        if not APIRateLimit.objects.exists():
                            APIRateLimit.objects.create(
                                name="Security API Limit",
                                limit_type='ip',
                                limit_period='minute',
                                request_limit=60,
                                is_active=True
                            )
                            logger.info("[OK] Default API rate limit created")
                    except Exception as e:
                        logger.debug(f"Could not initialize API rate limit: {e}")
                    
                    logger.info("[OK] Security system initialized")
                except Exception as e:
                    logger.error(f"Security system initialization error: {e}")
            
            # Use on_commit to ensure database is ready
            connection.on_commit(_do_initialization)
        except Exception as e:
            logger.error(f"Error setting up security initialization: {e}")