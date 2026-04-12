# permissions.py — Custom DRF permissions
from rest_framework.permissions import BasePermission, IsAuthenticated
import logging

logger = logging.getLogger(__name__)


class IsTranslator(BasePermission):
    """User is a translator — can add/edit translations but not approve"""
    message = "You must be a Translator to perform this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        return (
            hasattr(request.user, 'profile') and
            getattr(request.user.profile, 'role', '') in ('translator', 'reviewer', 'admin')
        )


class IsReviewer(BasePermission):
    """User can approve/reject translations"""
    message = "You must be a Reviewer to approve translations."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        return (
            hasattr(request.user, 'profile') and
            getattr(request.user.profile, 'role', '') in ('reviewer', 'admin')
        )


class IsLocalizationAdmin(BasePermission):
    """Full localization admin — manage languages, config, seed data"""
    message = "Localization admin access required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)


class IsOwnerOrAdmin(BasePermission):
    """Owner of the object or admin"""
    message = "You don't have permission to access this resource."

    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_staff:
            return True
        user_field = getattr(obj, 'user', None) or getattr(obj, 'created_by', None) or getattr(obj, 'requested_by', None)
        return user_field == request.user


class IsTranslatorForLanguage(BasePermission):
    """Translator assigned to a specific language"""
    message = "You are not assigned to translate this language."

    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_staff:
            return True
        lang = getattr(obj, 'language', None)
        if not lang:
            return True
        # Check if user is assigned to this language
        try:
            from .models.core import UserLanguagePreference
            pref = UserLanguagePreference.objects.filter(user=request.user).first()
            if pref and lang in pref.preferred_languages.all():
                return True
        except Exception as e:
            logger.error(f"IsTranslatorForLanguage check failed: {e}")
        return False


class ReadOnly(BasePermission):
    """Read-only for all authenticated users"""
    def has_permission(self, request, view):
        return request.method in ('GET', 'HEAD', 'OPTIONS')


class IsAdminOrReadOnly(BasePermission):
    """Admin can write, others read-only"""
    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return bool(request.user and request.user.is_staff)


class HasAPIKey(BasePermission):
    """X-API-Key header authentication for server-to-server"""
    message = "Valid API key required."

    def has_permission(self, request, view):
        from django.conf import settings
        api_key = request.META.get('HTTP_X_API_KEY', '')
        valid_keys = getattr(settings, 'LOCALIZATION_API_KEYS', [])
        if api_key and api_key in valid_keys:
            return True
        return bool(request.user and request.user.is_authenticated)


class IsPublicTranslationRequest(BasePermission):
    """Allow GET for public translation endpoints"""
    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return bool(request.user and request.user.is_authenticated)
