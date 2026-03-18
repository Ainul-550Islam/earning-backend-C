from social_core.backends.google import GoogleOAuth2
import logging
logger = logging.getLogger(__name__)

class CustomGoogleOAuth2(GoogleOAuth2):
    def get_redirect_uri(self, state=None):
        uri = 'https://earning-backend-c-production.up.railway.app/auth/social/complete/google-oauth2/'
        logger.warning(f"[OAUTH DEBUG] redirect_uri being sent: {uri}")
        return uri
    
    def auth_complete_params(self, state=None):
        params = super().auth_complete_params(state)
        logger.warning(f"[OAUTH DEBUG] Full token params: {params}")
        return params
