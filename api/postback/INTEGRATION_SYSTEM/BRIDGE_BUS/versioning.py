"""
versioning.py – Version management for postback module.

Provides comprehensive versioning functionality including:
- API versioning
- Data versioning
- Compatibility management
- Version migration
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from functools import wraps

from django.utils import timezone
from django.core.cache import cache

from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException

logger = logging.getLogger(__name__)


class VersionType(Enum):
    """Version type enumeration."""
    API = "api"
    DATA = "data"
    SCHEMA = "schema"
    PROTOCOL = "protocol"
    CONFIGURATION = "configuration"


class VersionStatus(Enum):
    """Version status enumeration."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"
    DEVELOPMENT = "development"
    BETA = "beta"
    STABLE = "stable"


@dataclass
class Version:
    """Version data structure."""
    version: str
    version_type: VersionType
    status: VersionStatus
    created_at: datetime = field(default_factory=timezone.now)
    deprecated_at: Optional[datetime] = None
    sunset_at: Optional[datetime] = None
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    compatibility_matrix: Dict[str, List[str]] = field(default_factory=dict)
    
    def __str__(self) -> str:
        return self.version
    
    def __lt__(self, other: 'Version') -> bool:
        """Compare versions."""
        return self._compare_versions(self.version, other.version) < 0
    
    def __gt__(self, other: 'Version') -> bool:
        """Compare versions."""
        return self._compare_versions(self.version, other.version) > 0
    
    def __eq__(self, other: 'Version') -> bool:
        """Compare versions."""
        return self.version == other.version
    
    @staticmethod
    def _compare_versions(v1: str, v2: str) -> int:
        """Compare two version strings."""
        def version_key(v):
            return [int(x) for x in v.split('.')]
        
        v1_parts = version_key(v1)
        v2_parts = version_key(v2)
        
        for i in range(max(len(v1_parts), len(v2_parts))):
            v1_val = v1_parts[i] if i < len(v1_parts) else 0
            v2_val = v2_parts[i] if i < len(v2_parts) else 0
            
            if v1_val < v2_val:
                return -1
            elif v1_val > v2_val:
                return 1
        
        return 0
    
    def is_compatible_with(self, other_version: str) -> bool:
        """Check if compatible with another version."""
        if other_version in self.compatibility_matrix.get('compatible', []):
            return True
        
        if other_version in self.compatibility_matrix.get('incompatible', []):
            return False
        
        # Default compatibility logic
        return self._is_default_compatible(other_version)
    
    def _is_default_compatible(self, other_version: str) -> bool:
        """Default compatibility logic."""
        # Major version changes are incompatible
        v1_parts = [int(x) for x in self.version.split('.')]
        v2_parts = [int(x) for x in other_version.split('.')]
        
        # If major version is different, incompatible
        if v1_parts[0] != v2_parts[0]:
            return False
        
        # If minor version is higher, might be incompatible
        if v2_parts[1] > v1_parts[1]:
            return False
        
        return True


class VersionManager:
    """
    Manager for version control and compatibility.
    
    Handles version registration, compatibility checks,
    and migration management.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.versions: Dict[str, Dict[VersionType, Version]] = {}
        self.current_versions: Dict[VersionType, str] = {}
        self.migration_handlers: Dict[str, Callable] = {}
        self._setup_default_versions()
    
    def _setup_default_versions(self):
        """Setup default versions."""
        default_versions = [
            Version(
                version="1.0.0",
                version_type=VersionType.API,
                status=VersionStatus.SUNSET,
                description="Initial API version",
                compatibility_matrix={
                    'compatible': ['1.0.1', '1.1.0'],
                    'incompatible': ['2.0.0'],
                }
            ),
            Version(
                version="1.1.0",
                version_type=VersionType.API,
                status=VersionStatus.DEPRECATED,
                description="Enhanced API with additional endpoints",
                compatibility_matrix={
                    'compatible': ['1.1.1', '1.2.0'],
                    'incompatible': ['2.0.0'],
                }
            ),
            Version(
                version="2.0.0",
                version_type=VersionType.API,
                status=VersionStatus.ACTIVE,
                description="Current API version with breaking changes",
                compatibility_matrix={
                    'compatible': ['2.0.1', '2.1.0'],
                    'incompatible': ['1.0.0', '1.1.0'],
                }
            ),
            Version(
                version="1.0.0",
                version_type=VersionType.DATA,
                status=VersionStatus.ACTIVE,
                description="Initial data format",
                compatibility_matrix={
                    'compatible': ['1.0.1', '1.1.0'],
                }
            ),
        ]
        
        for version in default_versions:
            self.register_version(version)
        
        # Set current versions
        self.current_versions[VersionType.API] = "2.0.0"
        self.current_versions[VersionType.DATA] = "1.0.0"
    
    def register_version(self, version: Version) -> bool:
        """
        Register a version.
        
        Args:
            version: Version to register
            
        Returns:
            True if registered successfully
        """
        try:
            version_type = version.version_type
            
            if version_type not in self.versions:
                self.versions[version_type] = {}
            
            self.versions[version_type][version.version] = version
            
            self.logger.info(f"Version registered: {version.version} ({version_type.value})")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to register version {version.version}: {str(e)}")
            return False
    
    def unregister_version(self, version: str, version_type: VersionType) -> bool:
        """
        Unregister a version.
        
        Args:
            version: Version string
            version_type: Version type
            
        Returns:
            True if unregistered successfully
        """
        try:
            if version_type in self.versions and version in self.versions[version_type]:
                del self.versions[version_type][version]
                self.logger.info(f"Version unregistered: {version} ({version_type.value})")
                return True
            
            return False
        
        except Exception as e:
            self.logger.error(f"Failed to unregister version {version}: {str(e)}")
            return False
    
    def get_version(self, version: str, version_type: VersionType) -> Optional[Version]:
        """
        Get version by version string and type.
        
        Args:
            version: Version string
            version_type: Version type
            
        Returns:
            Version or None
        """
        return self.versions.get(version_type, {}).get(version)
    
    def get_current_version(self, version_type: VersionType) -> Optional[Version]:
        """
        Get current version for type.
        
        Args:
            version_type: Version type
            
        Returns:
            Current version or None
        """
        current_version_str = self.current_versions.get(version_type)
        if current_version_str:
            return self.get_version(current_version_str, version_type)
        return None
    
    def set_current_version(self, version: str, version_type: VersionType) -> bool:
        """
        Set current version for type.
        
        Args:
            version: Version string
            version_type: Version type
            
        Returns:
            True if set successfully
        """
        if self.get_version(version, version_type):
            self.current_versions[version_type] = version
            self.logger.info(f"Current version set: {version} ({version_type.value})")
            return True
        return False
    
    def get_versions_by_type(self, version_type: VersionType) -> List[Version]:
        """
        Get all versions by type.
        
        Args:
            version_type: Version type
            
        Returns:
            List of versions
        """
        versions = list(self.versions.get(version_type, {}).values())
        return sorted(versions, reverse=True)
    
    def get_versions_by_status(self, status: VersionStatus) -> List[Version]:
        """
        Get all versions by status.
        
        Args:
            status: Version status
            
        Returns:
            List of versions
        """
        versions = []
        for type_versions in self.versions.values():
            for version in type_versions.values():
                if version.status == status:
                    versions.append(version)
        
        return sorted(versions, reverse=True)
    
    def is_compatible(self, version1: str, version2: str, version_type: VersionType) -> bool:
        """
        Check if two versions are compatible.
        
        Args:
            version1: First version
            version2: Second version
            version_type: Version type
            
        Returns:
            True if compatible
        """
        v1_obj = self.get_version(version1, version_type)
        v2_obj = self.get_version(version2, version_type)
        
        if not v1_obj or not v2_obj:
            return False
        
        return v1_obj.is_compatible_with(version2) and v2_obj.is_compatible_with(version1)
    
    def get_compatible_versions(self, version: str, version_type: VersionType) -> List[str]:
        """
        Get compatible versions for a given version.
        
        Args:
            version: Version string
            version_type: Version type
            
        Returns:
            List of compatible versions
        """
        version_obj = self.get_version(version, version_type)
        if not version_obj:
            return []
        
        compatible = []
        for v in self.get_versions_by_type(version_type):
            if v.version != version and version_obj.is_compatible_with(v.version):
                compatible.append(v.version)
        
        return compatible
    
    def migrate_version(self, from_version: str, to_version: str, 
                      version_type: VersionType, data: Any) -> Any:
        """
        Migrate data from one version to another.
        
        Args:
            from_version: Source version
            to_version: Target version
            version_type: Version type
            data: Data to migrate
            
        Returns:
            Migrated data
        """
        migration_key = f"{version_type.value}_{from_version}_to_{to_version}"
        
        if migration_key in self.migration_handlers:
            handler = self.migration_handlers[migration_key]
            return handler(data)
        
        # Default migration logic
        return self._default_migration(data, from_version, to_version, version_type)
    
    def _default_migration(self, data: Any, from_version: str, 
                          to_version: str, version_type: VersionType) -> Any:
        """Default migration logic."""
        # For now, just return data as-is
        # In a real implementation, this would handle version-specific migrations
        self.logger.info(f"Default migration from {from_version} to {to_version} for {version_type.value}")
        return data
    
    def register_migration_handler(self, from_version: str, to_version: str,
                                 version_type: VersionType, handler: Callable):
        """
        Register migration handler.
        
        Args:
            from_version: Source version
            to_version: Target version
            version_type: Version type
            handler: Migration handler function
        """
        migration_key = f"{version_type.value}_{from_version}_to_{to_version}"
        self.migration_handlers[migration_key] = handler
        self.logger.info(f"Migration handler registered: {migration_key}")
    
    def deprecate_version(self, version: str, version_type: VersionType, 
                         sunset_date: datetime = None) -> bool:
        """
        Deprecate a version.
        
        Args:
            version: Version to deprecate
            version_type: Version type
            sunset_date: Optional sunset date
            
        Returns:
            True if deprecated successfully
        """
        version_obj = self.get_version(version, version_type)
        if not version_obj:
            return False
        
        version_obj.status = VersionStatus.DEPRECATED
        version_obj.deprecated_at = timezone.now()
        
        if sunset_date:
            version_obj.sunset_at = sunset_date
        else:
            # Default sunset after 6 months
            version_obj.sunset_at = timezone.now() + timedelta(days=180)
        
        self.logger.info(f"Version deprecated: {version} ({version_type.value})")
        return True
    
    def sunset_version(self, version: str, version_type: VersionType) -> bool:
        """
        Sunset a version.
        
        Args:
            version: Version to sunset
            version_type: Version type
            
        Returns:
            True if sunset successfully
        """
        version_obj = self.get_version(version, version_type)
        if not version_obj:
            return False
        
        version_obj.status = VersionStatus.SUNSET
        version_obj.sunset_at = timezone.now()
        
        self.logger.info(f"Version sunset: {version} ({version_type.value})")
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get version statistics."""
        stats = {
            'total_versions': 0,
            'versions_by_type': {},
            'versions_by_status': {},
            'current_versions': dict(self.current_versions),
            'upcoming_sunset': [],
        }
        
        for version_type, versions in self.versions.items():
            type_name = version_type.value
            stats['versions_by_type'][type_name] = len(versions)
            stats['total_versions'] += len(versions)
            
            for version in versions.values():
                status_name = version.status.value
                if status_name not in stats['versions_by_status']:
                    stats['versions_by_status'][status_name] = 0
                stats['versions_by_status'][status_name] += 1
                
                # Check for upcoming sunset
                if (version.sunset_at and 
                    version.sunset_at > timezone.now() and 
                    version.sunset_at <= timezone.now() + timedelta(days=30)):
                    stats['upcoming_sunset'].append({
                        'version': version.version,
                        'type': type_name,
                        'sunset_date': version.sunset_at.isoformat(),
                    })
        
        return stats


class VersionValidator:
    """
    Validator for version compatibility and requirements.
    
    Handles version validation and compatibility checks.
    """
    
    def __init__(self, version_manager: VersionManager):
        self.version_manager = version_manager
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def validate_version_request(self, version: str, version_type: VersionType,
                               required_version: str = None) -> Dict[str, Any]:
        """
        Validate version request.
        
        Args:
            version: Requested version
            version_type: Version type
            required_version: Required version
            
        Returns:
            Validation result
        """
        result = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'recommended_version': None,
        }
        
        # Check if version exists
        version_obj = self.version_manager.get_version(version, version_type)
        if not version_obj:
            result['valid'] = False
            result['errors'].append(f"Version {version} not found for {version_type.value}")
            return result
        
        # Check if version is active
        if version_obj.status == VersionStatus.SUNSET:
            result['valid'] = False
            result['errors'].append(f"Version {version} is sunset")
            # Recommend current version
            current = self.version_manager.get_current_version(version_type)
            if current:
                result['recommended_version'] = current.version
        
        elif version_obj.status == VersionStatus.DEPRECATED:
            result['warnings'].append(f"Version {version} is deprecated")
            if version_obj.sunset_at:
                result['warnings'].append(f"Version will be sunset on {version_obj.sunset_at.date()}")
            # Recommend current version
            current = self.version_manager.get_current_version(version_type)
            if current:
                result['recommended_version'] = current.version
        
        # Check compatibility with required version
        if required_version:
            if not self.version_manager.is_compatible(version, required_version, version_type):
                result['valid'] = False
                result['errors'].append(f"Version {version} is not compatible with required version {required_version}")
        
        return result
    
    def validate_version_header(self, version_header: str, version_type: VersionType) -> Dict[str, Any]:
        """
        Validate version header.
        
        Args:
            version_header: Version header string
            version_type: Version type
            
        Returns:
            Validation result
        """
        result = {
            'valid': True,
            'version': None,
            'warnings': [],
            'errors': [],
        }
        
        # Parse version header
        try:
            version = self._parse_version_header(version_header)
            result['version'] = version
        except Exception as e:
            result['valid'] = False
            result['errors'].append(f"Invalid version header format: {str(e)}")
            return result
        
        # Validate version
        validation_result = self.validate_version_request(version, version_type)
        result.update(validation_result)
        
        return result
    
    def _parse_version_header(self, header: str) -> str:
        """Parse version header string."""
        # Common header formats:
        # "application/vnd.api+json; version=2.0"
        # "API-Version: 2.0"
        # "version=2.0"
        
        if ';' in header:
            # Content type format
            parts = header.split(';')
            for part in parts:
                if 'version=' in part:
                    return part.split('=')[1].strip()
        elif ':' in header:
            # Header format
            return header.split(':')[1].strip()
        elif '=' in header:
            # Simple format
            return header.split('=')[1].strip()
        else:
            # Just version string
            return header.strip()


# Decorators for version handling
def versioned(version_type: VersionType, min_version: str = None, max_version: str = None):
    """
    Decorator for versioned functions.
    
    Args:
        version_type: Version type
        min_version: Minimum required version
        max_version: Maximum supported version
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get version from request or context
            version = kwargs.get('version') or kwargs.get('api_version')
            
            if not version:
                raise IntegrationException("Version not specified")
            
            # Validate version
            validator = VersionValidator(version_manager)
            validation_result = validator.validate_version_request(version, version_type)
            
            if not validation_result['valid']:
                raise IntegrationException(f"Version validation failed: {', '.join(validation_result['errors'])}")
            
            # Add version to kwargs
            kwargs['_validated_version'] = version
            kwargs['_version_warnings'] = validation_result['warnings']
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Global instances
version_manager = VersionManager()
version_validator = VersionValidator(version_manager)


# Convenience functions
def get_current_version(version_type: VersionType) -> Optional[Version]:
    """Get current version."""
    return version_manager.get_current_version(version_type)


def is_version_compatible(version1: str, version2: str, version_type: VersionType) -> bool:
    """Check version compatibility."""
    return version_manager.is_compatible(version1, version2, version_type)


def migrate_data(data: Any, from_version: str, to_version: str, version_type: VersionType) -> Any:
    """Migrate data between versions."""
    return version_manager.migrate_version(from_version, to_version, version_type, data)


def validate_version(version: str, version_type: VersionType, required_version: str = None) -> Dict[str, Any]:
    """Validate version."""
    return version_validator.validate_version_request(version, version_type, required_version)


def get_version_statistics() -> Dict[str, Any]:
    """Get version statistics."""
    return version_manager.get_statistics()
