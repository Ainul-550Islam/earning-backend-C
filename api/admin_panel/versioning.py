# api/admin_panel/versioning.py
"""API versioning — supports /api/v1/admin/ and /api/v2/admin/."""
from rest_framework.versioning import URLPathVersioning, AcceptHeaderVersioning

class AdminURLVersioning(URLPathVersioning):
    """Version via URL: /api/v1/admin-panel/ or /api/v2/admin-panel/"""
    default_version = 'v1'
    allowed_versions = ['v1', 'v2']
    version_param = 'version'

class AdminHeaderVersioning(AcceptHeaderVersioning):
    """Version via Accept header: Accept: application/json; version=v2"""
    default_version = 'v1'
    allowed_versions = ['v1', 'v2']

# Version-specific feature flags
VERSION_FEATURES = {
    'v1': {
        'websocket':        True,
        'ai_insights':      True,
        'bulk_operations':  True,
    },
    'v2': {
        'websocket':        True,
        'ai_insights':      True,
        'bulk_operations':  True,
        'graphql':          True,  # Future
        'streaming':        True,  # Future
    },
}

def get_version_features(version: str = 'v1') -> dict:
    return VERSION_FEATURES.get(version, VERSION_FEATURES['v1'])