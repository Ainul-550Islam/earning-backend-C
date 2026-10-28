# api/djoyalty/api_versioning.py
"""
Djoyalty API Versioning -- v1/v2 API version management।
Supports: URL versioning, Header versioning, backwards compatibility।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from rest_framework.versioning import URLPathVersioning, AcceptHeaderVersioning

logger = logging.getLogger(__name__)

# Current and supported versions
CURRENT_VERSION = 'v2'
SUPPORTED_VERSIONS = ['v1', 'v2']
DEPRECATED_VERSIONS = ['v1']  # Still supported but deprecated


class DjoyaltyURLVersioning(URLPathVersioning):
    """
    URL path versioning for Djoyalty API।
    /api/loyalty/v1/customers/ -> v1
    /api/loyalty/v2/customers/ -> v2

    Add to urls.py:
        path('v<int:version>/', include('djoyalty.urls'))
    """
    default_version = CURRENT_VERSION
    allowed_versions = SUPPORTED_VERSIONS
    version_param = 'version'


class DjoyaltyHeaderVersioning(AcceptHeaderVersioning):
    """
    Accept header versioning।
    Accept: application/json; version=v2
    """
    default_version = CURRENT_VERSION
    allowed_versions = SUPPORTED_VERSIONS


class VersionedResponse:
    """
    Build version-appropriate response envelopes।
    v1: simple data dict
    v2: wrapped with metadata + pagination info
    """

    @staticmethod
    def build(data, request=None, version: str = None) -> dict:
        v = version or (
            request.version if request and hasattr(request, 'version') else CURRENT_VERSION
        )

        if v == 'v1':
            # Legacy v1 format
            return data if isinstance(data, dict) else {'data': data}

        # v2 format with metadata
        return {
            'api_version': v,
            'success': True,
            'data': data,
            'meta': {
                'version': v,
                'deprecated': v in DEPRECATED_VERSIONS,
                'upgrade_to': CURRENT_VERSION if v in DEPRECATED_VERSIONS else None,
            },
        }

    @staticmethod
    def add_deprecation_warning(response, version: str):
        """Add deprecation warning header for old API versions."""
        if version in DEPRECATED_VERSIONS:
            response['X-API-Deprecated'] = 'true'
            response['X-API-Upgrade-To'] = CURRENT_VERSION
            response['Sunset'] = 'Sat, 31 Dec 2026 23:59:59 GMT'
        return response


class APIVersionMixin:
    """
    Mixin for ViewSets to handle version-specific behavior।
    Usage:
        class CustomerViewSet(APIVersionMixin, viewsets.ModelViewSet):
            def list(self, request):
                if self.is_v2():
                    return self.list_v2(request)
                return self.list_v1(request)
    """

    def get_api_version(self) -> str:
        return getattr(self.request, 'version', CURRENT_VERSION)

    def is_v1(self) -> bool:
        return self.get_api_version() == 'v1'

    def is_v2(self) -> bool:
        return self.get_api_version() == 'v2'

    def versioned_response(self, data) -> dict:
        return VersionedResponse.build(data, request=self.request)
