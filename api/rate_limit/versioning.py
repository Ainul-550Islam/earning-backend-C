# api/rate_limit/versioning.py
"""
Versioning system for rate limit module.

Provides API versioning and data migration capabilities.
"""

import logging
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
import hashlib
import json

logger = logging.getLogger(__name__)


class Version:
    """Represents a version."""
    
    def __init__(self, version_string: str):
        self.version_string = version_string
        self.parts = self._parse_version(version_string)
        self.major = self.parts[0] if len(self.parts) > 0 else 0
        self.minor = self.parts[1] if len(self.parts) > 1 else 0
        self.patch = self.parts[2] if len(self.parts) > 2 else 0
        self.prerelease = self.parts[3] if len(self.parts) > 3 else None
    
    def _parse_version(self, version_string: str) -> List[Union[int, str]]:
        """Parse version string into parts."""
        parts = []
        
        # Split version and prerelease
        if '-' in version_string:
            version_part, prerelease_part = version_string.split('-', 1)
            parts.append(prerelease_part)
        else:
            version_part = version_string
        
        # Parse version numbers
        version_numbers = version_part.split('.')
        for num in version_numbers:
            try:
                parts.insert(0, int(num))
            except ValueError:
                parts.insert(0, num)
        
        return parts
    
    def __str__(self) -> str:
        return self.version_string
    
    def __repr__(self) -> str:
        return f"Version('{self.version_string}')"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Version):
            return False
        return self.parts == other.parts
    
    def __lt__(self, other) -> bool:
        if not isinstance(other, Version):
            return False
        
        # Compare major, minor, patch
        for i in range(max(len(self.parts), len(other.parts))):
            self_part = self.parts[i] if i < len(self.parts) else 0
            other_part = other.parts[i] if i < len(other.parts) else 0
            
            if isinstance(self_part, int) and isinstance(other_part, int):
                if self_part < other_part:
                    return True
                elif self_part > other_part:
                    return False
            else:
                # String comparison
                if str(self_part) < str(other_part):
                    return True
                elif str(self_part) > str(other_part):
                    return False
        
        return False
    
    def __le__(self, other) -> bool:
        return self == other or self < other
    
    def __gt__(self, other) -> bool:
        return not self <= other
    
    def __ge__(self, other) -> bool:
        return not self < other
    
    def is_compatible(self, other: 'Version') -> bool:
        """Check if versions are compatible (same major version)."""
        return self.major == other.major
    
    def get_hash(self) -> str:
        """Get version hash."""
        return hashlib.md5(self.version_string.encode()).hexdigest()


class Migration:
    """Represents a data migration."""
    
    def __init__(self, from_version: str, to_version: str, migration_func: Callable,
                 description: str = '', rollback_func: Callable = None):
        self.from_version = Version(from_version)
        self.to_version = Version(to_version)
        self.migration_func = migration_func
        self.rollback_func = rollback_func
        self.description = description
        self.applied_at = None
        self.rollback_at = None
    
    def apply(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Apply migration."""
        try:
            logger.info("Applying migration from %s to %s", self.from_version, self.to_version)
            
            result = self.migration_func(context or {})
            
            self.applied_at = timezone.now()
            
            logger.info("Migration applied successfully: %s", self.description)
            
            return {
                'success': True,
                'from_version': str(self.from_version),
                'to_version': str(self.to_version),
                'applied_at': self.applied_at.isoformat(),
                'result': result
            }
            
        except Exception as e:
            logger.error("Migration failed: %s", e, exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'from_version': str(self.from_version),
                'to_version': str(self.to_version)
            }
    
    def rollback(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Rollback migration."""
        try:
            if not self.rollback_func:
                return {
                    'success': False,
                    'error': 'No rollback function available'
                }
            
            logger.info("Rolling back migration from %s to %s", self.to_version, self.from_version)
            
            result = self.rollback_func(context or {})
            
            self.rollback_at = timezone.now()
            
            logger.info("Migration rolled back successfully: %s", self.description)
            
            return {
                'success': True,
                'from_version': str(self.to_version),
                'to_version': str(self.from_version),
                'rollback_at': self.rollback_at.isoformat(),
                'result': result
            }
            
        except Exception as e:
            logger.error("Rollback failed: %s", e, exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'from_version': str(self.to_version),
                'to_version': str(self.from_version)
            }


class APIVersion:
    """Represents an API version."""
    
    def __init__(self, version: str, path: str, deprecated: bool = False,
                 sunset_date: datetime = None, description: str = '',
                 supported_until: datetime = None):
        self.version = Version(version)
        self.path = path
        self.deprecated = deprecated
        self.sunset_date = sunset_date
        self.description = description
        self.supported_until = supported_until
        self.created_at = timezone.now()
    
    def is_supported(self) -> bool:
        """Check if API version is still supported."""
        if self.supported_until:
            return timezone.now() <= self.supported_until
        
        if self.deprecated and self.sunset_date:
            return timezone.now() <= self.sunset_date
        
        return not self.deprecated
    
    def get_status(self) -> str:
        """Get API version status."""
        if not self.is_supported():
            return 'unsupported'
        elif self.deprecated:
            return 'deprecated'
        else:
            return 'supported'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'version': str(self.version),
            'path': self.path,
            'deprecated': self.deprecated,
            'sunset_date': self.sunset_date.isoformat() if self.sunset_date else None,
            'supported_until': self.supported_until.isoformat() if self.supported_until else None,
            'description': self.description,
            'status': self.get_status(),
            'created_at': self.created_at.isoformat()
        }


class VersionManager:
    """
    Manager for versioning and migrations.
    """
    
    def __init__(self):
        self.current_version = Version('1.0.0')
        self.api_versions: Dict[str, APIVersion] = {}
        self.migrations: List[Migration] = []
        self.applied_migrations: List[Migration] = []
        self._initialize_default_versions()
        self._initialize_default_migrations()
    
    def _initialize_default_versions(self):
        """Initialize default API versions."""
        # Current version
        self.register_api_version(APIVersion(
            version='1.0.0',
            path='/api/v1/rate-limit',
            description='Initial rate limiting API'
        ))
        
        # Beta version
        self.register_api_version(APIVersion(
            version='1.1.0-beta',
            path='/api/v1/rate-limit-beta',
            deprecated=False,
            description='Beta features for rate limiting'
        ))
        
        # Legacy version
        self.register_api_version(APIVersion(
            version='0.9.0',
            path='/api/v0/rate-limit',
            deprecated=True,
            sunset_date=timezone.now() + timedelta(days=90),
            description='Legacy rate limiting API'
        ))
    
    def _initialize_default_migrations(self):
        """Initialize default migrations."""
        # Migration from 0.9.0 to 1.0.0
        def migrate_090_to_100(context):
            """Migrate from 0.9.0 to 1.0.0."""
            # Example migration logic
            return {'migrated_records': 0, 'changes': ['field_renames', 'data_transformations']}
        
        def rollback_100_to_090(context):
            """Rollback from 1.0.0 to 0.9.0."""
            return {'rollback_records': 0, 'reverted_changes': ['field_renames', 'data_transformations']}
        
        self.register_migration(Migration(
            from_version='0.9.0',
            to_version='1.0.0',
            migration_func=migrate_090_to_100,
            rollback_func=rollback_100_to_090,
            description='Initial API migration'
        ))
        
        # Migration from 1.0.0 to 1.1.0
        def migrate_100_to_110(context):
            """Migrate from 1.0.0 to 1.1.0."""
            return {'migrated_records': 0, 'changes': ['new_fields', 'updated_validations']}
        
        def rollback_110_to_100(context):
            """Rollback from 1.1.0 to 1.0.0."""
            return {'rollback_records': 0, 'reverted_changes': ['new_fields', 'updated_validations']}
        
        self.register_migration(Migration(
            from_version='1.0.0',
            to_version='1.1.0',
            migration_func=migrate_100_to_110,
            rollback_func=rollback_110_to_100,
            description='Add new features and validations'
        ))
    
    def register_api_version(self, api_version: APIVersion):
        """
        Register an API version.
        
        Args:
            api_version: API version instance
        """
        self.api_versions[str(api_version.version)] = api_version
        logger.info(f"Registered API version: {api_version.version}")
    
    def unregister_api_version(self, version: str):
        """
        Unregister an API version.
        
        Args:
            version: Version string
        """
        if version in self.api_versions:
            del self.api_versions[version]
            logger.info(f"Unregistered API version: {version}")
    
    def get_api_version(self, version: str) -> Optional[APIVersion]:
        """
        Get API version by version string.
        
        Args:
            version: Version string
            
        Returns:
            API version instance or None
        """
        return self.api_versions.get(version)
    
    def get_supported_api_versions(self) -> List[APIVersion]:
        """Get all supported API versions."""
        return [
            version for version in self.api_versions.values()
            if version.is_supported()
        ]
    
    def get_latest_api_version(self) -> Optional[APIVersion]:
        """Get the latest supported API version."""
        supported_versions = self.get_supported_api_versions()
        
        if not supported_versions:
            return None
        
        return max(supported_versions, key=lambda v: v.version)
    
    def register_migration(self, migration: Migration):
        """
        Register a migration.
        
        Args:
            migration: Migration instance
        """
        self.migrations.append(migration)
        self.migrations.sort(key=lambda m: m.to_version)
        logger.info(f"Registered migration: {migration.from_version} -> {migration.to_version}")
    
    def get_migration_path(self, from_version: str, to_version: str) -> List[Migration]:
        """
        Get migration path between versions.
        
        Args:
            from_version: Source version
            to_version: Target version
            
        Returns:
            List of migrations to apply
        """
        from_ver = Version(from_version)
        to_ver = Version(to_version)
        
        if from_ver == to_ver:
            return []
        
        # Find applicable migrations
        path = []
        
        for migration in self.migrations:
            if (migration.from_version >= from_ver and 
                migration.to_version <= to_ver and
                migration.to_version > from_ver):
                path.append(migration)
        
        # Sort by version
        path.sort(key=lambda m: m.to_version)
        
        return path
    
    def apply_migrations(self, from_version: str, to_version: str, 
                       context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Apply migrations between versions.
        
        Args:
            from_version: Source version
            to_version: Target version
            context: Migration context
            
        Returns:
            Migration results
        """
        try:
            migration_path = self.get_migration_path(from_version, to_version)
            
            if not migration_path:
                return {
                    'success': True,
                    'message': 'No migrations needed',
                    'from_version': from_version,
                    'to_version': to_version
                }
            
            results = []
            
            for migration in migration_path:
                result = migration.apply(context)
                results.append(result)
                
                if result['success']:
                    self.applied_migrations.append(migration)
                else:
                    # Rollback applied migrations
                    self._rollback_applied_migrations(migration_path[:len(results)], context)
                    return {
                        'success': False,
                        'error': f"Migration failed: {result.get('error')}",
                        'from_version': from_version,
                        'to_version': to_version,
                        'results': results
                    }
            
            # Update current version
            self.current_version = Version(to_version)
            
            return {
                'success': True,
                'from_version': from_version,
                'to_version': to_version,
                'applied_migrations': len(migration_path),
                'results': results
            }
            
        except Exception as e:
            logger.error("Migration application failed: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'from_version': from_version,
                'to_version': to_version
            }
    
    def _rollback_applied_migrations(self, migrations: List[Migration], context: Dict[str, Any]):
        """Rollback applied migrations."""
        for migration in reversed(migrations):
            try:
                migration.rollback(context)
                self.applied_migrations.remove(migration)
            except Exception as e:
                logger.error("Failed to rollback migration %s -> %s: %s", migration.from_version, migration.to_version, str(e), exc_info=True)
    
    def rollback_to_version(self, target_version: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Rollback to a specific version.
        
        Args:
            target_version: Target version
            context: Rollback context
            
        Returns:
            Rollback results
        """
        try:
            target_ver = Version(target_version)
            
            # Find migrations to rollback
            rollback_migrations = []
            
            for migration in self.applied_migrations:
                if migration.from_version >= target_ver:
                    rollback_migrations.append(migration)
            
            if not rollback_migrations:
                return {
                    'success': True,
                    'message': 'No rollbacks needed',
                    'target_version': target_version
                }
            
            results = []
            
            for migration in reversed(rollback_migrations):
                result = migration.rollback(context)
                results.append(result)
                
                if result['success']:
                    self.applied_migrations.remove(migration)
                else:
                    return {
                        'success': False,
                        'error': f"Rollback failed: {result.get('error')}",
                        'target_version': target_version,
                        'results': results
                    }
            
            # Update current version
            self.current_version = target_ver
            
            return {
                'success': True,
                'target_version': target_version,
                'rolled_back_migrations': len(rollback_migrations),
                'results': results
            }
            
        except Exception as e:
            logger.error("Rollback failed: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'target_version': target_version
            }
    
    def get_version_info(self) -> Dict[str, Any]:
        """Get version information."""
        return {
            'current_version': str(self.current_version),
            'api_versions': {
                version: api_version.to_dict()
                for version, api_version in self.api_versions.items()
            },
            'supported_versions': [
                str(version.version) for version in self.get_supported_api_versions()
            ],
            'latest_version': str(self.get_latest_api_version().version) if self.get_latest_api_version() else None,
            'total_migrations': len(self.migrations),
            'applied_migrations': len(self.applied_migrations),
            'pending_migrations': len(self.migrations) - len(self.applied_migrations)
        }
    
    def check_compatibility(self, client_version: str) -> Dict[str, Any]:
        """
        Check client version compatibility.
        
        Args:
            client_version: Client version string
            
        Returns:
            Compatibility information
        """
        try:
            client_ver = Version(client_version)
            
            # Find closest supported version
            supported_versions = self.get_supported_api_versions()
            compatible_versions = [
                version for version in supported_versions
                if client_ver.is_compatible(version.version)
            ]
            
            if not compatible_versions:
                return {
                    'compatible': False,
                    'client_version': client_version,
                    'message': 'No compatible API version available',
                    'recommended_version': str(self.get_latest_api_version().version) if self.get_latest_api_version() else None
                }
            
            # Get latest compatible version
            latest_compatible = max(compatible_versions, key=lambda v: v.version)
            
            return {
                'compatible': True,
                'client_version': client_version,
                'recommended_version': str(latest_compatible.version),
                'api_path': latest_compatible.path,
                'deprecated': latest_compatible.deprecated,
                'sunset_date': latest_compatible.sunset_date.isoformat() if latest_compatible.sunset_date else None
            }
            
        except Exception as e:
            logger.error("Compatibility check failed: %s", str(e), exc_info=True)
            return {
                'compatible': False,
                'error': str(e),
                'client_version': client_version
            }


# Global version manager instance
version_manager = VersionManager()


# Decorator for API versioning
def api_version(version: str, deprecated: bool = False, sunset_date: datetime = None):
    """
    Decorator for API versioning.
    
    Args:
        version: API version
        deprecated: Whether version is deprecated
        sunset_date: Sunset date for deprecated version
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Add version information to response
            result = func(*args, **kwargs)
            
            if isinstance(result, dict):
                result['_meta'] = {
                    'api_version': version,
                    'deprecated': deprecated,
                    'sunset_date': sunset_date.isoformat() if sunset_date else None
                }
            
            return result
        return wrapper
    return decorator


# Export classes and functions
__all__ = [
    'Version',
    'Migration',
    'APIVersion',
    'VersionManager',
    'version_manager',
    'api_version'
]
