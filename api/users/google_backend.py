from social_core.backends.google import GoogleOAuth2

class CustomGoogleOAuth2(GoogleOAuth2):
    name = 'google-oauth2'
    
    def get_redirect_uri(self, state=None):
        return 'https://earning-backend-c-production.up.railway.app/auth/social/complete/google-oauth2/'
    
    def auth_complete_params(self, state=None):
        params = super().auth_complete_params(state)
        params['redirect_uri'] = 'https://earning-backend-c-production.up.railway.app/auth/social/complete/google-oauth2/'
        return params
    
    def auth_params(self, state=None):
        params = super().auth_params(state)
        params['redirect_uri'] = 'https://earning-backend-c-production.up.railway.app/auth/social/complete/google-oauth2/'
        return params
