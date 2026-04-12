"""
SmartLink Dual Authentication
Supports: JWT Bearer Token + API Key header
"""
import hashlib
import logging
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

logger = logging.getLogger('smartlink.auth')
User = get_user_model()


class SmartLinkJWTAuthentication(JWTAuthentication):
    """
    Standard JWT authentication with Redis token blacklist support.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, token = result

        # Check if token is blacklisted (logout)
        jti = token.get('jti', '')
        if jti and cache.get(f'jwt_blacklist:{jti}'):
            raise AuthenticationFailed('Token has been revoked.')

        return user, token


class APIKeyAuthentication(BaseAuthentication):
    """
    API Key authentication for publisher integrations.
    Header: X-SmartLink-API-Key: <key>
    """
    HEADER = 'HTTP_X_SMARTLINK_API_KEY'
    CACHE_TTL = 300  # 5 minutes

    def authenticate(self, request):
        api_key = request.META.get(self.HEADER, '').strip()
        if not api_key:
            return None

        # Check cache first
        cache_key = f'api_key:{hashlib.sha256(api_key.encode()).hexdigest()}'
        cached_user_id = cache.get(cache_key)

        if cached_user_id:
            try:
                user = User.objects.get(pk=cached_user_id, is_active=True)
                return user, api_key
            except User.DoesNotExist:
                cache.delete(cache_key)

        # DB lookup
        try:
            from ..models.publisher import PublisherAPIKey
            key_obj = PublisherAPIKey.objects.select_related('publisher').get(
                key=api_key,
                is_active=True,
            )
            user = key_obj.publisher
            if not user.is_active:
                raise AuthenticationFailed('Publisher account is inactive.')

            # Update last used
            from django.utils import timezone
            PublisherAPIKey.objects.filter(pk=key_obj.pk).update(last_used_at=timezone.now())

            # Cache
            cache.set(cache_key, user.pk, self.CACHE_TTL)
            return user, api_key

        except Exception:
            raise AuthenticationFailed('Invalid API key.')

    def authenticate_header(self, request):
        return 'X-SmartLink-API-Key'


class PublisherAPIKey:
    """
    API Key model (add to models/publisher.py).
    Defined here for reference.
    """
    pass
