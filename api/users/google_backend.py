from social_core.backends.google import GoogleOAuth2

class CustomGoogleOAuth2(GoogleOAuth2):
    def get_redirect_uri(self, state=None):
        return 'https://earning-backend-c-production.up.railway.app/auth/social/complete/google-oauth2/'
