from rest_framework_simplejwt.tokens import RefreshToken


class TokenService:
    
    @staticmethod
    def generate_tokens(user):
        """Generate access and refresh tokens for user"""
        refresh = RefreshToken.for_user(user)
        
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }
    
    @staticmethod
    def revoke_token(token):
        """Revoke/blacklist a token"""
        try:
            token = RefreshToken(token)
            token.blacklist()
            return True
        except Exception:
            return False