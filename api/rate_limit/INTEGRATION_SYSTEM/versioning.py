"""
Versioning System - Integration Version Management

Version control and compatibility management for integration components,
ensuring backward compatibility and smooth transitions between versions.
"""

import logging
import hashlib
import json
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from django.core.cache import cache
from django.utils import timezone

from .integ_constants import IntegrationStatus
from .integ_exceptions import IntegrationError, VersioningError

logger = logging.getLogger(__name__)


class VersionType(Enum):
    """Types of version changes."""
    MAJOR = "major"      # Breaking changes
    MINOR = "minor"      # New features, backward compatible
    PATCH = "patch"      # Bug fixes, backward compatible
    PRE_RELEASE = "pre_release"  # Pre-release versions
    BUILD = "build"      # Build metadata


class CompatibilityType(Enum):
    """Compatibility types."""
    BACKWARD = "backward"      # New version works with old data
    FORWARD = "forward"        # Old version works with new data
    FULL = "full"             # Both backward and forward compatible
    NONE = "none"             # No compatibility


@dataclass
class Version:
    """Version information."""
    major: int
    minor: int
    patch: int
    pre_release: Optional[str] = None
    build: Optional[str] = None
    
    def __str__(self) -> str:
        """String representation of version."""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre_release:
            version += f"-{self.pre_release}"
        if self.build:
            version += f"+{self.build}"
        return version
    
    def __eq__(self, other) -> bool:
        """Check version equality."""
        if not isinstance(other, Version):
            return False
        return (self.major == other.major and 
                self.minor == other.minor and 
                self.patch == other.patch and
                self.pre_release == other.pre_release and
                self.build == other.build)
    
    def __lt__(self, other) -> bool:
        """Compare versions."""
        if not isinstance(other, Version):
            return NotImplemented
        
        # Compare major version
        if self.major != other.major:
            return self.major < other.major
        
        # Compare minor version
        if self.minor != other.minor:
            return self.minor < other.minor
        
        # Compare patch version
        if self.patch != other.patch:
            return self.patch < other.patch
        
        # Compare pre-release (pre-release versions are lower than release versions)
        if self.pre_release is None and other.pre_release is not None:
            return False
        elif self.pre_release is not None and other.pre_release is None:
            return True
        elif self.pre_release is not None and other.pre_release is not None:
            return self.pre_release < other.pre_release
        
        # Build metadata doesn't affect precedence
        return False
    
    def __le__(self, other) -> bool:
        """Less than or equal comparison."""
        return self == other or self < other
    
    def __gt__(self, other) -> bool:
        """Greater than comparison."""
        return not self <= other
    
    def __ge__(self, other) -> bool:
        """Greater than or equal comparison."""
        return not self < other
    
    @classmethod
    def parse(cls, version_string: str) -> 'Version':
        """Parse version string."""
        try:
            # Split version and build metadata
            if '+' in version_string:
                version_part, build = version_string.split('+', 1)
            else:
                version_part = version_string
                build = None
            
            # Split version and pre-release
            if '-' in version_part:
                version_part, pre_release = version_part.split('-', 1)
            else:
                pre_release = None
            
            # Parse version numbers
            parts = version_part.split('.')
            if len(parts) < 3:
                raise ValueError(f"Invalid version format: {version_string}")
            
            major = int(parts[0])
            minor = int(parts[1])
            patch = int(parts[2])
            
            return cls(
                major=major,
                minor=minor,
                patch=patch,
                pre_release=pre_release,
                build=build
            )
        
        except Exception as e:
            raise VersioningError(f"Failed to parse version '{version_string}': {str(e)}")
    
    def get_version_type(self, old_version: 'Version') -> VersionType:
        """Determine version change type."""
        if self.major > old_version.major:
            return VersionType.MAJOR
        elif self.minor > old_version.minor:
            return VersionType.MINOR
        elif self.patch > old_version.patch:
            return VersionType.PATCH
        elif self.pre_release != old_version.pre_release:
            return VersionType.PRE_RELEASE
        elif self.build != old_version.build:
            return VersionType.BUILD
        else:
            return VersionType.PATCH
    
    def is_compatible(self, other: 'Version', compatibility: CompatibilityType) -> bool:
        """Check version compatibility."""
        if compatibility == CompatibilityType.BACKWARD:
            # New version should work with old data
            return self >= other
        elif compatibility == CompatibilityType.FORWARD:
            # Old version should work with new data
            return other >= self
        elif compatibility == CompatibilityType.FULL:
            # Both directions should work
            return self.major == other.major
        elif compatibility == CompatibilityType.NONE:
            # No compatibility requirements
            return True
        else:
            return False


@dataclass
class VersionedComponent:
    """Versioned component information."""
    name: str
    version: Version
    description: str
    schema_version: Optional[Version] = None
    api_version: Optional[Version] = None
    compatibility: CompatibilityType = CompatibilityType.BACKWARD
    dependencies: Dict[str, Version] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)
    updated_at: datetime = field(default_factory=timezone.now)
    is_active: bool = True
    is_deprecated: bool = False
    deprecation_date: Optional[datetime] = None
    
    def get_hash(self) -> str:
        """Get version hash."""
        version_string = str(self.version)
        return hashlib.md5(version_string.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'version': str(self.version),
            'description': self.description,
            'schema_version': str(self.schema_version) if self.schema_version else None,
            'api_version': str(self.api_version) if self.api_version else None,
            'compatibility': self.compatibility.value,
            'dependencies': {k: str(v) for k, v in self.dependencies.items()},
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_active': self.is_active,
            'is_deprecated': self.is_deprecated,
            'deprecation_date': self.deprecation_date.isoformat() if self.deprecation_date else None,
            'hash': self.get_hash()
        }


@dataclass
class Migration:
    """Migration information."""
    name: str
    from_version: Version
    to_version: Version
    migration_type: VersionType
    description: str
    migration_script: Optional[str] = None
    rollback_script: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    estimated_time: Optional[int] = None  # in seconds
    is_reversible: bool = True
    created_at: datetime = field(default_factory=timezone.now)
    executed_at: Optional[datetime] = None
    is_executed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'from_version': str(self.from_version),
            'to_version': str(self.to_version),
            'migration_type': self.migration_type.value,
            'description': self.description,
            'migration_script': self.migration_script,
            'rollback_script': self.rollback_script,
            'dependencies': self.dependencies,
            'estimated_time': self.estimated_time,
            'is_reversible': self.is_reversible,
            'created_at': self.created_at.isoformat(),
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'is_executed': self.is_executed
        }


class VersionManager:
    """Version management system."""
    
    def __init__(self):
        self.components: Dict[str, List[VersionedComponent]] = {}
        self.migrations: Dict[str, List[Migration]] = {}
        self.current_versions: Dict[str, Version] = {}
        self._lock = None  # For thread safety
    
    def register_component(self, component: VersionedComponent) -> bool:
        """Register a versioned component."""
        try:
            if component.name not in self.components:
                self.components[component.name] = []
            
            # Check if version already exists
            for existing in self.components[component.name]:
                if existing.version == component.version:
                    logger.warning(f"Component version already exists: {component.name}@{component.version}")
                    return False
            
            # Add component
            self.components[component.name].append(component)
            
            # Sort by version
            self.components[component.name].sort(key=lambda c: c.version, reverse=True)
            
            # Update current version if this is the latest
            if (component.name not in self.current_versions or 
                component.version > self.current_versions[component.name]):
                self.current_versions[component.name] = component.version
            
            logger.info(f"Registered component: {component.name}@{component.version}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to register component: {str(e)}")
            return False
    
    def get_component(self, name: str, version: Optional[Version] = None) -> Optional[VersionedComponent]:
        """Get component by name and version."""
        if name not in self.components:
            return None
        
        if version is None:
            # Return latest version
            return self.components[name][0] if self.components[name] else None
        
        # Find specific version
        for component in self.components[name]:
            if component.version == version:
                return component
        
        return None
    
    def get_current_version(self, name: str) -> Optional[Version]:
        """Get current version of component."""
        return self.current_versions.get(name)
    
    def get_available_versions(self, name: str) -> List[Version]:
        """Get all available versions of component."""
        if name not in self.components:
            return []
        
        return [component.version for component in self.components[name]]
    
    def is_version_supported(self, name: str, version: Version) -> bool:
        """Check if version is supported."""
        component = self.get_component(name, version)
        return component is not None and component.is_active and not component.is_deprecated
    
    def get_compatible_versions(self, name: str, version: Version, 
                              compatibility: CompatibilityType = CompatibilityType.BACKWARD) -> List[Version]:
        """Get compatible versions."""
        compatible_versions = []
        
        if name not in self.components:
            return compatible_versions
        
        for component in self.components[name]:
            if component.is_active and not component.is_deprecated:
                if version.is_compatible(component.version, compatibility):
                    compatible_versions.append(component.version)
        
        return sorted(compatible_versions, reverse=True)
    
    def register_migration(self, migration: Migration) -> bool:
        """Register a migration."""
        try:
            if migration.name not in self.migrations:
                self.migrations[migration.name] = []
            
            # Check if migration already exists
            for existing in self.migrations[migration.name]:
                if (existing.from_version == migration.from_version and 
                    existing.to_version == migration.to_version):
                    logger.warning(f"Migration already exists: {migration.name}")
                    return False
            
            # Add migration
            self.migrations[migration.name].append(migration)
            
            # Sort by version
            self.migrations[migration.name].sort(key=lambda m: m.to_version)
            
            logger.info(f"Registered migration: {migration.name} ({migration.from_version} -> {migration.to_version})")
            return True
        
        except Exception as e:
            logger.error(f"Failed to register migration: {str(e)}")
            return False
    
    def get_migration_path(self, name: str, from_version: Version, to_version: Version) -> List[Migration]:
        """Get migration path between versions."""
        if name not in self.migrations:
            return []
        
        path = []
        current_version = from_version
        
        while current_version < to_version:
            next_migration = None
            
            # Find next migration
            for migration in self.migrations[name]:
                if (migration.from_version == current_version and 
                    migration.to_version > current_version and
                    migration.to_version <= to_version):
                    if next_migration is None or migration.to_version < next_migration.to_version:
                        next_migration = migration
            
            if next_migration is None:
                break
            
            path.append(next_migration)
            current_version = next_migration.to_version
        
        return path
    
    def can_migrate(self, name: str, from_version: Version, to_version: Version) -> bool:
        """Check if migration is possible."""
        path = self.get_migration_path(name, from_version, to_version)
        return len(path) > 0
    
    def execute_migration(self, name: str, from_version: Version, to_version: Version) -> bool:
        """Execute migration."""
        try:
            path = self.get_migration_path(name, from_version, to_version)
            
            if not path:
                raise VersioningError(f"No migration path found: {from_version} -> {to_version}")
            
            # Execute migrations in order
            for migration in path:
                if migration.is_executed:
                    continue
                
                # Execute migration script
                if migration.migration_script:
                    # This would execute the actual migration script
                    # For now, we'll just mark it as executed
                    migration.is_executed = True
                    migration.executed_at = timezone.now()
                    
                    logger.info(f"Executed migration: {migration.name}")
                else:
                    logger.warning(f"Migration {migration.name} has no script to execute")
            
            return True
        
        except Exception as e:
            logger.error(f"Migration execution failed: {str(e)}")
            return False
    
    def rollback_migration(self, name: str, from_version: Version, to_version: Version) -> bool:
        """Rollback migration."""
        try:
            path = self.get_migration_path(name, to_version, from_version)
            
            if not path:
                raise VersioningError(f"No rollback path found: {from_version} -> {to_version}")
            
            # Execute rollbacks in reverse order
            for migration in reversed(path):
                if not migration.is_reversible:
                    raise VersioningError(f"Migration {migration.name} is not reversible")
                
                # Execute rollback script
                if migration.rollback_script:
                    # This would execute the actual rollback script
                    # For now, we'll just mark it as not executed
                    migration.is_executed = False
                    migration.executed_at = None
                    
                    logger.info(f"Rolled back migration: {migration.name}")
                else:
                    logger.warning(f"Migration {migration.name} has no rollback script")
            
            return True
        
        except Exception as e:
            logger.error(f"Migration rollback failed: {str(e)}")
            return False
    
    def deprecate_version(self, name: str, version: Version, deprecation_date: Optional[datetime] = None) -> bool:
        """Deprecate a version."""
        component = self.get_component(name, version)
        if not component:
            return False
        
        component.is_deprecated = True
        component.deprecation_date = deprecation_date or timezone.now()
        component.updated_at = timezone.now()
        
        logger.info(f"Deprecated version: {name}@{version}")
        return True
    
    def activate_version(self, name: str, version: Version) -> bool:
        """Activate a version."""
        component = self.get_component(name, version)
        if not component:
            return False
        
        component.is_active = True
        component.is_deprecated = False
        component.deprecation_date = None
        component.updated_at = timezone.now()
        
        logger.info(f"Activated version: {name}@{version}")
        return True
    
    def get_version_statistics(self) -> Dict[str, Any]:
        """Get version statistics."""
        stats = {
            'total_components': len(self.components),
            'total_versions': 0,
            'active_versions': 0,
            'deprecated_versions': 0,
            'total_migrations': 0,
            'executed_migrations': 0,
            'components': {}
        }
        
        for name, versions in self.components.items():
            component_stats = {
                'total_versions': len(versions),
                'active_versions': 0,
                'deprecated_versions': 0,
                'current_version': str(self.current_versions.get(name, 'N/A')),
                'versions': []
            }
            
            for component in versions:
                component_stats['versions'].append({
                    'version': str(component.version),
                    'is_active': component.is_active,
                    'is_deprecated': component.is_deprecated,
                    'created_at': component.created_at.isoformat(),
                    'updated_at': component.updated_at.isoformat()
                })
                
                stats['total_versions'] += 1
                
                if component.is_active:
                    component_stats['active_versions'] += 1
                    stats['active_versions'] += 1
                
                if component.is_deprecated:
                    component_stats['deprecated_versions'] += 1
                    stats['deprecated_versions'] += 1
            
            stats['components'][name] = component_stats
        
        # Migration statistics
        for name, migrations in self.migrations.items():
            stats['total_migrations'] += len(migrations)
            for migration in migrations:
                if migration.is_executed:
                    stats['executed_migrations'] += 1
        
        return stats
    
    def export_version_data(self) -> Dict[str, Any]:
        """Export version data."""
        return {
            'components': {
                name: [component.to_dict() for component in versions]
                for name, versions in self.components.items()
            },
            'migrations': {
                name: [migration.to_dict() for migration in migrations]
                for name, migrations in self.migrations.items()
            },
            'current_versions': {
                name: str(version) for name, version in self.current_versions.items()
            },
            'exported_at': timezone.now().isoformat()
        }
    
    def import_version_data(self, data: Dict[str, Any]) -> int:
        """Import version data."""
        imported_count = 0
        
        try:
            # Import components
            for name, component_data in data.get('components', {}).items():
                for comp_dict in component_data:
                    component = VersionedComponent(
                        name=comp_dict['name'],
                        version=Version.parse(comp_dict['version']),
                        description=comp_dict['description'],
                        schema_version=Version.parse(comp_dict['schema_version']) if comp_dict['schema_version'] else None,
                        api_version=Version.parse(comp_dict['api_version']) if comp_dict['api_version'] else None,
                        compatibility=CompatibilityType(comp_dict['compatibility']),
                        dependencies={k: Version.parse(v) for k, v in comp_dict['dependencies'].items()},
                        metadata=comp_dict['metadata'],
                        created_at=datetime.fromisoformat(comp_dict['created_at']),
                        updated_at=datetime.fromisoformat(comp_dict['updated_at']),
                        is_active=comp_dict['is_active'],
                        is_deprecated=comp_dict['is_deprecated'],
                        deprecation_date=datetime.fromisoformat(comp_dict['deprecation_date']) if comp_dict['deprecation_date'] else None
                    )
                    
                    if self.register_component(component):
                        imported_count += 1
            
            # Import migrations
            for name, migration_data in data.get('migrations', {}).items():
                for mig_dict in migration_data:
                    migration = Migration(
                        name=mig_dict['name'],
                        from_version=Version.parse(mig_dict['from_version']),
                        to_version=Version.parse(mig_dict['to_version']),
                        migration_type=VersionType(mig_dict['migration_type']),
                        description=mig_dict['description'],
                        migration_script=mig_dict['migration_script'],
                        rollback_script=mig_dict['rollback_script'],
                        dependencies=mig_dict['dependencies'],
                        estimated_time=mig_dict['estimated_time'],
                        is_reversible=mig_dict['is_reversible'],
                        created_at=datetime.fromisoformat(mig_dict['created_at']),
                        executed_at=datetime.fromisoformat(mig_dict['executed_at']) if mig_dict['executed_at'] else None,
                        is_executed=mig_dict['is_executed']
                    )
                    
                    if self.register_migration(migration):
                        imported_count += 1
            
            logger.info(f"Imported {imported_count} version items")
            return imported_count
        
        except Exception as e:
            logger.error(f"Failed to import version data: {str(e)}")
            return 0


# Global version manager
version_manager = VersionManager()


# Decorator for version checking
def version_compatible(component_name: str, min_version: str = None, max_version: str = None):
    """Decorator for version compatibility checking."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get current version
            current_version = version_manager.get_current_version(component_name)
            if not current_version:
                raise VersioningError(f"Component not found: {component_name}")
            
            # Check version constraints
            if min_version:
                min_ver = Version.parse(min_version)
                if current_version < min_ver:
                    raise VersioningError(f"Component {component_name} version {current_version} is below minimum {min_ver}")
            
            if max_version:
                max_ver = Version.parse(max_version)
                if current_version > max_ver:
                    raise VersioningError(f"Component {component_name} version {current_version} is above maximum {max_ver}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Convenience functions
def create_version(major: int, minor: int, patch: int, 
                  pre_release: str = None, build: str = None) -> Version:
    """Create version object."""
    return Version(major, minor, patch, pre_release, build)


def get_current_version(component_name: str) -> Optional[Version]:
    """Get current version of component."""
    return version_manager.get_current_version(component_name)


def is_version_supported(component_name: str, version: str) -> bool:
    """Check if version is supported."""
    ver = Version.parse(version)
    return version_manager.is_version_supported(component_name, ver)
