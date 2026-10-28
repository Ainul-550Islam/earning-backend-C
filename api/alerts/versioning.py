"""
Versioning system for alerts app - API and data version management
"""
from typing import Dict, List, Any, Optional, Tuple
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
import re
import json
import logging

logger = logging.getLogger(__name__)


class Version:
    """Represents a semantic version"""
    
    def __init__(self, version_string: str):
        self.original = version_string
        self.major = 0
        self.minor = 0
        self.patch = 0
        self.prerelease = None
        self.build_metadata = None
        
        self._parse_version(version_string)
    
    def _parse_version(self, version_string: str):
        """Parse version string into components"""
        # Handle semantic versioning (semver)
        semver_pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?)?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?)?$'
        match = re.match(semver_pattern, version_string)
        
        if match:
            self.major = int(match.group(1))
            self.minor = int(match.group(2))
            self.patch = int(match.group(3))
            self.prerelease = match.group(4) or None
            self.build_metadata = match.group(5) or None
        else:
            # Fallback for simple versions
            parts = version_string.split('.')
            try:
                self.major = int(parts[0]) if len(parts) > 0 else 0
                self.minor = int(parts[1]) if len(parts) > 1 else 0
                self.patch = int(parts[2]) if len(parts) > 2 else 0
            except ValueError:
                # Handle non-numeric versions
                self.major = 0
                self.minor = 0
                self.patch = 0
    
    def __str__(self) -> str:
        """Return version string"""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build_metadata:
            version += f"+{self.build_metadata}"
        return version
    
    def __repr__(self) -> str:
        return f"Version('{self.__str__()}')"
    
    def __eq__(self, other) -> bool:
        """Compare versions for equality"""
        if not isinstance(other, Version):
            return False
        return (
            self.major == other.major and
            self.minor == other.minor and
            self.patch == other.patch
        )
    
    def __lt__(self, other) -> bool:
        """Compare versions for less than"""
        if not isinstance(other, Version):
            return NotImplemented
        
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        return self.patch < other.patch
    
    def __le__(self, other) -> bool:
        """Compare versions for less than or equal"""
        if not isinstance(other, Version):
            return NotImplemented
        return self <= other
    
    def __gt__(self, other) -> bool:
        """Compare versions for greater than"""
        if not isinstance(other, Version):
            return NotImplemented
        return self > other
    
    def __ge__(self, other) -> bool:
        """Compare versions for greater than or equal"""
        if not isinstance(other, Version):
            return NotImplemented
        return self >= other
    
    def is_compatible(self, required_version: 'Version') -> bool:
        """Check if this version is compatible with required version"""
        # Semantic versioning compatibility rules
        # Major version must match exactly
        if self.major != required_version.major:
            return False
        
        # Minor version can be greater than or equal
        if self.minor < required_version.minor:
            return False
        
        # Patch version can be greater than or equal
        if self.minor == required_version.minor and self.patch < required_version.patch:
            return False
        
        return True
    
    def get_version_tuple(self) -> Tuple[int, int, int]:
        """Get version as tuple (major, minor, patch)"""
        return (self.major, self.minor, self.patch)


class APIVersion:
    """API version information"""
    
    def __init__(self, version: str, deprecation_date: str = None, sunset_date: str = None):
        self.version = Version(version)
        self.deprecation_date = timezone.datetime.fromisoformat(deprecation_date) if deprecation_date else None
        self.sunset_date = timezone.datetime.fromisoformat(sunset_date) if sunset_date else None
        self.is_deprecated = self.deprecation_date is not None
        self.is_sunset = self.sunset_date is not None
    
    def is_active(self) -> bool:
        """Check if API version is active"""
        now = timezone.now()
        
        if self.is_sunset and now >= self.sunset_date:
            return False
        
        if self.is_deprecated and now >= self.deprecation_date:
            return False
        
        return True
    
    def get_status(self) -> str:
        """Get API version status"""
        if self.is_sunset:
            return "sunset"
        elif self.is_deprecated:
            return "deprecated"
        else:
            return "active"
    
    def get_warnings(self) -> List[str]:
        """Get warnings for this API version"""
        warnings = []
        now = timezone.now()
        
        if self.is_deprecated:
            days_until_sunset = None
            if self.sunset_date:
                days_until_sunset = (self.sunset_date - now).days
            
            warnings.append(
                f"API version {self.version} is deprecated. "
                f"Sunset date: {self.sunset_date.date()}. "
                f"Days until sunset: {days_until_sunset}"
            )
        
        if self.is_sunset:
            warnings.append(
                f"API version {self.version} is sunset. "
                f"Sunset date: {self.sunset_date.date()}"
            )
        
        return warnings


class VersionManager:
    """Manages API and data versions"""
    
    def __init__(self):
        self.current_api_version = None
        self.supported_versions = {}
        self.version_history = []
        self.cache_timeout = 300  # 5 minutes
        
        # Load current version
        self._load_current_version()
        
        # Load supported versions
        self._load_supported_versions()
    
    def _load_current_version(self):
        """Load current API version"""
        version_string = getattr(settings, 'API_VERSION', '1.0.0')
        self.current_api_version = APIVersion(version_string)
    
    def _load_supported_versions(self):
        """Load supported API versions from settings"""
        supported_versions = getattr(settings, 'SUPPORTED_API_VERSIONS', {})
        
        for version_name, version_info in supported_versions.items():
            version_info['version'] = Version(version_info['version'])
            if 'deprecation_date' in version_info:
                version_info['deprecation_date'] = timezone.datetime.fromisoformat(version_info['deprecation_date'])
            if 'sunset_date' in version_info:
                version_info['sunset_date'] = timezone.datetime.fromisoformat(version_info['sunset_date'])
            
            self.supported_versions[version_name] = APIVersion(**version_info)
    
    def get_current_version(self) -> APIVersion:
        """Get current API version"""
        return self.current_api_version
    
    def is_version_supported(self, version: str) -> bool:
        """Check if version is supported"""
        version_obj = Version(version)
        
        for supported_version in self.supported_versions.values():
            if version_obj == supported_version.version:
                return True
        
        return False
    
    def get_compatible_versions(self, version: str) -> List[str]:
        """Get all versions compatible with given version"""
        version_obj = Version(version)
        compatible = []
        
        for version_name, supported_version in self.supported_versions.items():
            if version_obj.is_compatible(supported_version.version):
                compatible.append(version_name)
        
        return compatible
    
    def get_latest_version(self) -> Optional[APIVersion]:
        """Get the latest active version"""
        active_versions = [
            v for v in self.supported_versions.values()
            if v.is_active()
        ]
        
        if not active_versions:
            return None
        
        # Sort by version (newest first)
        active_versions.sort(key=lambda v: v.version, reverse=True)
        return active_versions[0]
    
    def get_version_info(self, version: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a version"""
        version_obj = Version(version)
        
        for version_name, supported_version in self.supported_versions.items():
            if version_obj == supported_version.version:
                return {
                    'name': version_name,
                    'version': str(supported_version.version),
                    'status': supported_version.get_status(),
                    'warnings': supported_version.get_warnings(),
                    'deprecation_date': supported_version.deprecation_date.isoformat() if supported_version.deprecation_date else None,
                    'sunset_date': supported_version.sunset_date.isoformat() if supported_version.sunset_date else None
                }
        
        return None
    
    def check_client_version(self, client_version: str, endpoint: str = None) -> Dict[str, Any]:
        """Check if client version is supported and compatible"""
        cache_key = f"client_version_check_{client_version}_{endpoint or 'default'}"
        
        # Try to get from cache
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        result = {
            'client_version': client_version,
            'is_supported': self.is_version_supported(client_version),
            'is_compatible': False,
            'recommended_version': str(self.current_api_version.version),
            'endpoint': endpoint,
            'checked_at': timezone.now().isoformat()
        }
        
        # Check compatibility
        if result['is_supported']:
            result['is_compatible'] = self.current_api_version.version.is_compatible(Version(client_version))
        
        # Cache result
        cache.set(cache_key, result, self.cache_timeout)
        
        return result
    
    def add_version_to_history(self, version: str, client_info: Dict[str, Any] = None):
        """Add version check to history"""
        history_entry = {
            'version': version,
            'client_info': client_info or {},
            'checked_at': timezone.now().isoformat(),
            'is_supported': self.is_version_supported(version),
            'is_compatible': self.current_api_version.version.is_compatible(Version(version))
        }
        
        self.version_history.append(history_entry)
        
        # Keep only last 1000 entries
        if len(self.version_history) > 1000:
            self.version_history = self.version_history[-1000:]
    
    def get_version_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get version check history"""
        return self.version_history[-limit:]
    
    def get_version_statistics(self) -> Dict[str, Any]:
        """Get version usage statistics"""
        if not self.version_history:
            return {}
        
        total_checks = len(self.version_history)
        supported_count = sum(1 for entry in self.version_history if entry['is_supported'])
        compatible_count = sum(1 for entry in self.version_history if entry['is_compatible'])
        
        # Version distribution
        version_counts = {}
        for entry in self.version_history:
            version = entry['version']
            version_counts[version] = version_counts.get(version, 0) + 1
        
        # Most common versions
        most_common_versions = sorted(
            version_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return {
            'total_checks': total_checks,
            'supported_count': supported_count,
            'compatible_count': compatible_count,
            'unsupported_count': total_checks - supported_count,
            'incompatible_count': total_checks - compatible_count,
            'support_rate': (supported_count / total_checks * 100) if total_checks > 0 else 0,
            'compatibility_rate': (compatible_count / total_checks * 100) if total_checks > 0 else 0,
            'version_distribution': version_counts,
            'most_common_versions': most_common_versions,
            'current_version': str(self.current_api_version.version)
        }


class DataVersioning:
    """Manages data schema versions for backward compatibility"""
    
    def __init__(self):
        self.data_versions = {}
        self.migration_history = []
        self.current_schemas = {}
        
        # Load data versions
        self._load_data_versions()
    
    def _load_data_versions(self):
        """Load data version configurations"""
        data_versions = getattr(settings, 'DATA_VERSIONS', {})
        
        for data_type, version_info in data_versions.items():
            self.data_versions[data_type] = {
                'current_version': version_info.get('current_version', '1.0.0'),
                'supported_versions': version_info.get('supported_versions', ['1.0.0']),
                'migration_required': {},
                'schema_path': version_info.get('schema_path', f'schemas/{data_type}/')
            }
    
    def register_data_version(self, data_type: str, version: str, schema_path: str = None):
        """Register a new data version"""
        if data_type not in self.data_versions:
            self.data_versions[data_type] = {
                'current_version': version,
                'supported_versions': [version],
                'migration_required': {},
                'schema_path': schema_path or f'schemas/{data_type}/'
            }
        else:
            if version not in self.data_versions[data_type]['supported_versions']:
                self.data_versions[data_type]['supported_versions'].append(version)
            
            self.data_versions[data_type]['current_version'] = version
            if schema_path:
                self.data_versions[data_type]['schema_path'] = schema_path
    
    def get_data_version(self, data_type: str) -> Dict[str, Any]:
        """Get current data version information"""
        return self.data_versions.get(data_type, {})
    
    def is_data_version_supported(self, data_type: str, version: str) -> bool:
        """Check if data version is supported"""
        data_info = self.get_data_version(data_type)
        return version in data_info.get('supported_versions', [])
    
    def requires_migration(self, data_type: str, from_version: str, to_version: str) -> bool:
        """Check if migration is required between versions"""
        data_info = self.get_data_version(data_type)
        migration_key = f"{from_version}_to_{to_version}"
        
        return data_info.get('migration_required', {}).get(migration_key, False)
    
    def add_migration_record(self, data_type: str, from_version: str, to_version: str, success: bool, details: str = None):
        """Add migration record to history"""
        migration_record = {
            'data_type': data_type,
            'from_version': from_version,
            'to_version': to_version,
            'success': success,
            'details': details,
            'timestamp': timezone.now().isoformat()
        }
        
        self.migration_history.append(migration_record)
        
        # Keep only last 1000 entries
        if len(self.migration_history) > 1000:
            self.migration_history = self.migration_history[-1000:]
    
    def get_migration_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get migration history"""
        return self.migration_history[-limit:]
    
    def get_migration_statistics(self) -> Dict[str, Any]:
        """Get migration statistics"""
        if not self.migration_history:
            return {}
        
        total_migrations = len(self.migration_history)
        successful_migrations = sum(1 for record in self.migration_history if record['success'])
        failed_migrations = total_migrations - successful_migrations
        
        # Migration by data type
        migration_by_type = {}
        for record in self.migration_history:
            data_type = record['data_type']
            if data_type not in migration_by_type:
                migration_by_type[data_type] = {'total': 0, 'success': 0, 'failed': 0}
            
            migration_by_type[data_type]['total'] += 1
            if record['success']:
                migration_by_type[data_type]['success'] += 1
            else:
                migration_by_type[data_type]['failed'] += 1
        
        return {
            'total_migrations': total_migrations,
            'successful_migrations': successful_migrations,
            'failed_migrations': failed_migrations,
            'success_rate': (successful_migrations / total_migrations * 100) if total_migrations > 0 else 0,
            'migration_by_type': migration_by_type
        }


# Global instances
version_manager = VersionManager()
data_versioning = DataVersioning()


def get_version_manager() -> VersionManager:
    """Get the global version manager"""
    return version_manager


def get_data_versioning() -> DataVersioning:
    """Get the global data versioning manager"""
    return data_versioning


# Decorators for version checking
def require_api_version(min_version: str, max_version: str = None):
    """Decorator to require specific API version range"""
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            # Get client version from request
            client_version = request.META.get('HTTP_X_API_VERSION', '1.0.0')
            
            # Check version
            version_check = version_manager.check_client_version(client_version)
            
            if not version_check['is_supported']:
                from django.http import HttpResponse
                return HttpResponse(
                    json.dumps({
                        'error': 'Unsupported API version',
                        'client_version': client_version,
                        'supported_versions': list(version_manager.supported_versions.keys()),
                        'recommended_version': version_check['recommended_version']
                    }),
                    content_type='application/json',
                    status=400
                )
            
            if not version_check['is_compatible']:
                from django.http import HttpResponse
                return HttpResponse(
                    json.dumps({
                        'error': 'API version not compatible',
                        'client_version': client_version,
                        'current_version': version_check['recommended_version']
                    }),
                    content_type='application/json',
                    status=400
                )
            
            # Check version range
            client_version_obj = Version(client_version)
            min_version_obj = Version(min_version)
            
            if client_version_obj < min_version_obj:
                from django.http import HttpResponse
                return HttpResponse(
                    json.dumps({
                        'error': 'API version too old',
                        'client_version': client_version,
                        'minimum_required': min_version
                    }),
                    content_type='application/json',
                    status=400
                )
            
            if max_version:
                max_version_obj = Version(max_version)
                if client_version_obj > max_version_obj:
                    from django.http import HttpResponse
                    return HttpResponse(
                        json.dumps({
                            'error': 'API version too new',
                            'client_version': client_version,
                            'maximum_supported': max_version
                        }),
                        content_type='application/json',
                        status=400
                    )
            
            # Add version info to request
            request.version_info = version_check
            
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def version_response(response_data: Dict[str, Any], request = None):
    """Add version information to API response"""
    version_info = {}
    
    if request and hasattr(request, 'version_info'):
        version_info = request.version_info
    
    response_data['api_version'] = {
        'current': str(version_manager.current_api_version.version),
        'client': version_info.get('client_version', 'unknown'),
        'is_compatible': version_info.get('is_compatible', True),
        'warnings': version_info.get('warnings', [])
    }
    
    return response_data


# Version validation utility functions
def parse_version(version_string: str) -> Version:
    """Parse version string into Version object"""
    return Version(version_string)


def is_version_compatible(current: str, required: str) -> bool:
    """Check if current version is compatible with required version"""
    current_version_obj = Version(current)
    required_version_obj = Version(required)
    
    return current_version_obj.is_compatible(required_version_obj)


def get_version_difference(version1: str, version2: str) -> str:
    """Get human-readable version difference"""
    v1 = Version(version1)
    v2 = Version(version2)
    
    if v1 == v2:
        return "versions are identical"
    
    if v1 < v2:
        return f"{version2} is newer than {version1}"
    else:
        return f"{version1} is newer than {version2}"
