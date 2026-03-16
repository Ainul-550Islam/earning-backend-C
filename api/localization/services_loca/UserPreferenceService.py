# api/localization/services_loca/UserPreferenceService.py

import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class UserPreferenceService:
    """Service for managing user language preferences"""
    
    def get_user_preference(self, user):
        """
        Get user's language preference
        Returns a preference object with ui_language attribute
        """
        try:
            if not user or not user.is_authenticated:
                return None
            
            # Try to get from user profile
            if hasattr(user, 'profile'):
                profile = user.profile
                if hasattr(profile, 'language'):
                    return self._create_preference_object(profile.language)
            
            # Try direct user attribute
            if hasattr(user, 'language'):
                return self._create_preference_object(user.language)
            
            # Return default
            return self._create_preference_object(settings.LANGUAGE_CODE)
            
        except Exception as e:
            logger.error(f"Error getting user preference: {e}")
            return self._create_preference_object(settings.LANGUAGE_CODE)
    
    def _create_preference_object(self, language_code):
        """
        Create a preference object with ui_language attribute
        """
        # Try to import Language model (defensive)
        try:
            from ..models import Language
            language = Language.objects.filter(code=language_code).first()
            if language:
                return type('Preference', (), {'ui_language': language})
        except Exception:
            pass
        
        # Return object with string ui_language
        return type('Preference', (), {'ui_language': language_code})
    
    def set_user_preference(self, user, language_code):
        """Set user's language preference"""
        try:
            if not user or not user.is_authenticated:
                return False
            
            if hasattr(user, 'profile'):
                user.profile.language = language_code
                user.profile.save()
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error setting user preference: {e}")
            return False