# api/cms/api_versioning.py
"""
API Versioning — supports v1/v2 with deprecation warnings.
Usage in settings.py:
  REST_FRAMEWORK = {
      'DEFAULT_VERSIONING_CLASS': 'cms.api_versioning.CMSAPIVersioning',
      'DEFAULT_VERSION': 'v1',
      'ALLOWED_VERSIONS': ['v1', 'v2'],
  }
"""
import logging
from rest_framework.versioning import URLPathVersioning, AcceptHeaderVersioning
from rest_framework.response import Response

logger = logging.getLogger(__name__)

# Version deprecation schedule
DEPRECATED_VERSIONS = {
    'v1': '2027-01-01',  # v1 deprecated but still supported until 2027
}
CURRENT_VERSION = 'v2'


class CMSAPIVersioning(URLPathVersioning):
    """
    CMS URL-based API versioning.
    URL pattern: /api/v1/cms/... or /api/v2/cms/...
    """
    default_version = 'v1'
    allowed_versions = ['v1', 'v2']
    version_param = 'version'

    def determine_version(self, request, *args, **kwargs):
        version = super().determine_version(request, *args, **kwargs)
        # Add deprecation warning header for old versions
        if version in DEPRECATED_VERSIONS:
            request._deprecation_warning = (
                f"API version {version} is deprecated. "
                f"Please migrate to {CURRENT_VERSION} before {DEPRECATED_VERSIONS[version]}."
            )
        return version


class CMSAcceptVersioning(AcceptHeaderVersioning):
    """
    Accept header versioning: Accept: application/json; version=v2
    """
    default_version = 'v1'
    allowed_versions = ['v1', 'v2']


class VersionedResponseMixin:
    """
    Mixin to add version-specific response formatting and deprecation headers.
    Add to any ViewSet: class MyViewSet(VersionedResponseMixin, viewsets.ViewSet)
    """
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        # Add version to response headers
        version = getattr(request, 'version', 'v1')
        response['X-API-Version'] = version
        response['X-API-Current-Version'] = CURRENT_VERSION
        # Add deprecation warning if applicable
        warning = getattr(request, '_deprecation_warning', None)
        if warning:
            response['Deprecation'] = 'true'
            response['Warning'] = f'299 - "{warning}"'
            response['Sunset'] = DEPRECATED_VERSIONS.get(version, '')
        return response


class RateLimitResponseMixin:
    """
    Mixin to add X-RateLimit headers to all responses.
    Helps clients know their rate limit status.
    """
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        try:
            # Add rate limit headers
            user = request.user
            if user.is_authenticated:
                from api.cms.sanctions import RateLimiter
                # Check remaining requests for this user
                allowed, remaining = RateLimiter.check(
                    f"api_user_{user.id}", limit=1000, window_seconds=3600
                )
                response['X-RateLimit-Limit'] = '1000'
                response['X-RateLimit-Remaining'] = str(remaining)
                response['X-RateLimit-Window'] = '3600'
            else:
                response['X-RateLimit-Limit'] = '100'
                response['X-RateLimit-Window'] = '3600'
        except Exception:
            pass
        return response
