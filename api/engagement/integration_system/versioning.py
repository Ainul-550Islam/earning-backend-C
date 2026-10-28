# engagement/integration_system/versioning.py
"""
Version management system for integrations.
Provides version control, compatibility checking, and migration support.
"""
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
from datetime import datetime, timedelta
from packaging import version as pkg_version

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from .integ_constants import (
    ERROR_CODES, SUCCESS_CODES, DEFAULT_CONFIG, CACHE_KEYS
)

logger = logging.getLogger(__name__)


class VersionType(Enum):
    """Types of version changes."""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    PRE_RELEASE = "pre_release"
    BUILD = "build"


class CompatibilityType(Enum):
    """Compatibility types."""
    BACKWARD = "backward"
    FORWARD = "forward"
    FULL = "full"
    NONE = "none"


class MigrationStatus(Enum):
    """Migration status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class Version:
    """Version information."""
    major: int
    minor: int
    patch: int
    pre_release: Optional[str] = None
    build: Optional[str] = None
    
    def __str__(self) -> str:
        """String representation."""
        version_str = f"{self.major}.{self.minor}.{self.patch}"
        
        if self.pre_release:
            version_str += f"-{self.pre_release}"
        
        if self.build:
            version_str += f"+{self.build}"
        
        return version_str
    
    @classmethod
    def from_string(cls, version_str: str) -> 'Version':
        """Create version from string."""
        try:
            # Parse version string
            parts = version_str.split('+', 1)
            build = parts[1] if len(parts) > 1 else None
            version_part = parts[0]
            
            parts = version_part.split('-', 1)
            pre_release = parts[1] if len(parts) > 1 else None
            version_part = parts[0]
            
            version_numbers = version_part.split('.')
            if len(version_numbers) != 3:
                raise ValueError(f"Invalid version format: {version_str}")
            
            major, minor, patch = map(int, version_numbers)
            
            return cls(
                major=major,
                minor=minor,
                patch=patch,
                pre_release=pre_release,
                build=build
            )
        except Exception as exc:
            raise ValueError(f"Failed to parse version '{version_str}': {exc}")
    
    def __lt__(self, other: 'Version') -> bool:
        """Compare versions."""
        return str(pkg_version.Version(str(self))) < str(pkg_version.Version(str(other)))
    
    def __le__(self, other: 'Version') -> bool:
        """Compare versions."""
        return str(pkg_version.Version(str(self))) <= str(pkg_version.Version(str(other)))
    
    def __gt__(self, other: 'Version') -> bool:
        """Compare versions."""
        return str(pkg_version.Version(str(self))) > str(pkg_version.Version(str(other)))
    
    def __ge__(self, other: 'Version') -> bool:
        """Compare versions."""
        return str(pkg_version.Version(str(self))) >= str(pkg_version.Version(str(other)))
    
    def __eq__(self, other: 'Version') -> bool:
        """Compare versions."""
        return str(pkg_version.Version(str(self))) == str(pkg_version.Version(str(other)))
    
    def get_version_type(self, previous_version: 'Version') -> VersionType:
        """Determine version change type."""
        if self.major > previous_version.major:
            return VersionType.MAJOR
        elif self.minor > previous_version.minor:
            return VersionType.MINOR
        elif self.patch > previous_version.patch:
            return VersionType.PATCH
        elif self.pre_release != previous_version.pre_release:
            return VersionType.PRE_RELEASE
        elif self.build != previous_version.build:
            return VersionType.BUILD
        else:
            return VersionType.PATCH  # Default


@dataclass
class VersionInfo:
    """Version information for integration."""
    integration_id: str
    current_version: Version
    supported_versions: List[Version] = field(default_factory=list)
    deprecated_versions: List[Version] = field(default_factory=list)
    compatibility_rules: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)
    updated_at: datetime = field(default_factory=timezone.now)


@dataclass
class Migration:
    """Migration definition."""
    id: str
    from_version: Version
    to_version: Version
    migration_type: VersionType
    description: str = ""
    migration_script: str = ""
    rollback_script: str = ""
    status: MigrationStatus = MigrationStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    estimated_time: int = 0  # seconds
    risk_level: str = "low"  # low, medium, high, critical
    created_at: datetime = field(default_factory=timezone.now)
    executed_at: Optional[datetime] = None
    executed_by: Optional[str] = None
    rollback_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseVersionManager(ABC):
    """Base version manager class."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def get_version(self, integration_id: str) -> Optional[VersionInfo]:
        """Get version information for integration."""
        pass
    
    @abstractmethod
    def set_version(self, integration_id: str, version: Version, **kwargs) -> bool:
        """Set version for integration."""
        pass
    
    @abstractmethod
    def is_compatible(self, integration_id: str, version: Version) -> bool:
        """Check if version is compatible."""
        pass
    
    @abstractmethod
    def get_migration_path(self, integration_id: str, from_version: Version, to_version: Version) -> List[Migration]:
        """Get migration path between versions."""
        pass


class DefaultVersionManager(BaseVersionManager):
    """Default version manager implementation."""
    
    def __init__(self):
        super().__init__("DefaultVersionManager")
        self._versions: Dict[str, VersionInfo] = {}
        self._migrations: List[Migration] = []
        self._lock = threading.RLock()
    
    def get_version(self, integration_id: str) -> Optional[VersionInfo]:
        """Get version information for integration."""
        with self._lock:
            return self._versions.get(integration_id)
    
    def set_version(self, integration_id: str, version: Version, **kwargs) -> bool:
        """Set version for integration."""
        try:
            with self._lock:
                # Create version info
                version_info = VersionInfo(
                    integration_id=integration_id,
                    current_version=version,
                    supported_versions=kwargs.get('supported_versions', [version]),
                    deprecated_versions=kwargs.get('deprecated_versions', []),
                    compatibility_rules=kwargs.get('compatibility_rules', {}),
                    metadata=kwargs.get('metadata', {}),
                    updated_at=timezone.now()
                )
                
                self._versions[integration_id] = version_info
                
                # Cache version info
                self._cache_version_info(version_info)
                
                self.logger.info(f"Set version {version} for integration {integration_id}")
                return True
                
        except Exception as exc:
            self.logger.error(f"Failed to set version for integration {integration_id}: {exc}")
            return False
    
    def is_compatible(self, integration_id: str, version: Version) -> bool:
        """Check if version is compatible."""
        version_info = self.get_version(integration_id)
        if not version_info:
            return False
        
        # Check if version is in supported versions
        for supported_version in version_info.supported_versions:
            if version == supported_version:
                return True
        
        # Check compatibility rules
        compatibility_rules = version_info.compatibility_rules
        
        # Backward compatibility
        if compatibility_rules.get('backward_compatible', True):
            if version <= version_info.current_version:
                return True
        
        # Forward compatibility
        if compatibility_rules.get('forward_compatible', False):
            if version >= version_info.current_version:
                return True
        
        # Full compatibility
        if compatibility_rules.get('full_compatibility', False):
            return True
        
        return False
    
    def get_migration_path(self, integration_id: str, from_version: Version, to_version: Version) -> List[Migration]:
        """Get migration path between versions."""
        migrations = []
        
        # Get all migrations for this integration
        integration_migrations = [
            m for m in self._migrations 
            if m.from_version <= to_version and m.to_version >= from_version
        ]
        
        # Sort migrations by version
        integration_migrations.sort(key=lambda m: (m.from_version, m.to_version))
        
        # Build migration path
        current_version = from_version
        while current_version < to_version:
            # Find next migration
            next_migration = None
            for migration in integration_migrations:
                if migration.from_version == current_version:
                    next_migration = migration
                    break
            
            if not next_migration:
                # No direct migration found, try to find closest
                for migration in integration_migrations:
                    if migration.from_version > current_version and migration.to_version <= to_version:
                        if not next_migration or migration.from_version < next_migration.from_version:
                            next_migration = migration
            
            if not next_migration:
                break
            
            migrations.append(next_migration)
            current_version = next_migration.to_version
        
        return migrations
    
    def add_migration(self, migration: Migration) -> bool:
        """Add migration."""
        try:
            with self._lock:
                self._migrations.append(migration)
                self.logger.info(f"Added migration {migration.id}: {migration.from_version} -> {migration.to_version}")
                return True
        except Exception as exc:
            self.logger.error(f"Failed to add migration {migration.id}: {exc}")
            return False
    
    def execute_migration(self, migration_id: str, context: Dict[str, Any] = None) -> bool:
        """Execute migration."""
        try:
            migration = self._find_migration(migration_id)
            if not migration:
                raise ValueError(f"Migration {migration_id} not found")
            
            migration.status = MigrationStatus.IN_PROGRESS
            migration.executed_at = timezone.now()
            migration.executed_by = context.get('user', 'system') if context else 'system'
            
            # Execute migration script
            if migration.migration_script:
                self._execute_script(migration.migration_script, context)
            
            migration.status = MigrationStatus.COMPLETED
            self.logger.info(f"Executed migration {migration_id}")
            return True
            
        except Exception as exc:
            migration.status = MigrationStatus.FAILED
            self.logger.error(f"Failed to execute migration {migration_id}: {exc}")
            return False
    
    def rollback_migration(self, migration_id: str, context: Dict[str, Any] = None) -> bool:
        """Rollback migration."""
        try:
            migration = self._find_migration(migration_id)
            if not migration:
                raise ValueError(f"Migration {migration_id} not found")
            
            if migration.status != MigrationStatus.COMPLETED:
                raise ValueError(f"Cannot rollback migration {migration_id} with status {migration.status}")
            
            # Execute rollback script
            if migration.rollback_script:
                self._execute_script(migration.rollback_script, context)
            
            migration.status = MigrationStatus.ROLLED_BACK
            migration.rollback_at = timezone.now()
            
            self.logger.info(f"Rolled back migration {migration_id}")
            return True
            
        except Exception as exc:
            self.logger.error(f"Failed to rollback migration {migration_id}: {exc}")
            return False
    
    def _find_migration(self, migration_id: str) -> Optional[Migration]:
        """Find migration by ID."""
        for migration in self._migrations:
            if migration.id == migration_id:
                return migration
        return None
    
    def _execute_script(self, script: str, context: Dict[str, Any] = None):
        """Execute migration script."""
        # This would execute the migration script
        # For now, just log it
        self.logger.info(f"Executing script: {script}")
    
    def _cache_version_info(self, version_info: VersionInfo):
        """Cache version information."""
        cache_key = CACHE_KEYS['INTEGRATION_CONFIG'].format(integration_id=version_info.integration_id)
        cache.set(cache_key, version_info.__dict__, timeout=3600)  # 1 hour


class CompatibilityChecker:
    """Compatibility checker for versions."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.CompatibilityChecker")
    
    def check_compatibility(self, integration_id: str, version: Version, 
                           version_manager: BaseVersionManager) -> Dict[str, Any]:
        """Check version compatibility."""
        try:
            version_info = version_manager.get_version(integration_id)
            if not version_info:
                return {
                    'compatible': False,
                    'reason': 'Integration not found',
                    'suggestions': []
                }
            
            # Check direct compatibility
            if version_manager.is_compatible(integration_id, version):
                return {
                    'compatible': True,
                    'reason': 'Version is supported',
                    'suggestions': []
                }
            
            # Check if version is deprecated
            if version in version_info.deprecated_versions:
                return {
                    'compatible': False,
                    'reason': 'Version is deprecated',
                    'suggestions': ['Update to a supported version']
                }
            
            # Check if upgrade is needed
            if version < version_info.current_version:
                return {
                    'compatible': False,
                    'reason': 'Version is too old',
                    'suggestions': ['Upgrade to a supported version']
                }
            
            # Check if downgrade is needed
            if version > version_info.current_version:
                return {
                    'compatible': False,
                    'reason': 'Version is too new',
                    'suggestions': ['Downgrade to a supported version']
                }
            
            return {
                'compatible': False,
                'reason': 'Version not supported',
                'suggestions': ['Use a supported version']
            }
            
        except Exception as exc:
            self.logger.error(f"Compatibility check failed: {exc}")
            return {
                'compatible': False,
                'reason': f'Check failed: {exc}',
                'suggestions': []
            }
    
    def get_compatibility_matrix(self, integration_id: str, 
                               version_manager: BaseVersionManager) -> Dict[str, Any]:
        """Get compatibility matrix for integration."""
        try:
            version_info = version_manager.get_version(integration_id)
            if not version_info:
                return {}
            
            matrix = {
                'current_version': str(version_info.current_version),
                'supported_versions': [str(v) for v in version_info.supported_versions],
                'deprecated_versions': [str(v) for v in version_info.deprecated_versions],
                'compatibility_rules': version_info.compatibility_rules,
                'last_updated': version_info.updated_at.isoformat()
            }
            
            return matrix
            
        except Exception as exc:
            self.logger.error(f"Failed to get compatibility matrix: {exc}")
            return {}


class VersionMigrationManager:
    """Manager for version migrations."""
    
    def __init__(self, version_manager: BaseVersionManager):
        self.version_manager = version_manager
        self.logger = logging.getLogger(f"{__name__}.VersionMigrationManager")
    
    def plan_migration(self, integration_id: str, target_version: Version) -> Dict[str, Any]:
        """Plan migration to target version."""
        try:
            version_info = self.version_manager.get_version(integration_id)
            if not version_info:
                raise ValueError(f"Integration {integration_id} not found")
            
            current_version = version_info.current_version
            
            if current_version == target_version:
                return {
                    'migration_needed': False,
                    'reason': 'Already at target version',
                    'migrations': []
                }
            
            # Get migration path
            migrations = self.version_manager.get_migration_path(
                integration_id, current_version, target_version
            )
            
            if not migrations:
                return {
                    'migration_needed': True,
                    'reason': 'No migration path found',
                    'migrations': []
                }
            
            # Calculate total time and risk
            total_time = sum(m.estimated_time for m in migrations)
            max_risk = max(m.risk_level for m in migrations)
            
            return {
                'migration_needed': True,
                'from_version': str(current_version),
                'to_version': str(target_version),
                'migrations': [
                    {
                        'id': m.id,
                        'from_version': str(m.from_version),
                        'to_version': str(m.to_version),
                        'description': m.description,
                        'estimated_time': m.estimated_time,
                        'risk_level': m.risk_level
                    }
                    for m in migrations
                ],
                'total_time': total_time,
                'max_risk': max_risk,
                'migration_count': len(migrations)
            }
            
        except Exception as exc:
            self.logger.error(f"Failed to plan migration: {exc}")
            return {
                'migration_needed': False,
                'reason': f'Planning failed: {exc}',
                'migrations': []
            }
    
    def execute_migration_plan(self, integration_id: str, target_version: Version, 
                              context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute migration plan."""
        try:
            plan = self.plan_migration(integration_id, target_version)
            
            if not plan['migration_needed']:
                return {
                    'success': True,
                    'message': plan['reason'],
                    'executed_migrations': []
                }
            
            executed_migrations = []
            
            for migration_info in plan['migrations']:
                migration_id = migration_info['id']
                
                # Execute migration
                success = self.version_manager.execute_migration(migration_id, context)
                
                if success:
                    executed_migrations.append({
                        'id': migration_id,
                        'status': 'completed',
                        'executed_at': timezone.now().isoformat()
                    })
                else:
                    # Migration failed, rollback previous migrations
                    self._rollback_executed_migrations(executed_migrations, context)
                    
                    return {
                        'success': False,
                        'message': f'Migration {migration_id} failed',
                        'executed_migrations': executed_migrations,
                        'failed_migration': migration_id
                    }
            
            # Update integration version
            self.version_manager.set_version(integration_id, target_version)
            
            return {
                'success': True,
                'message': 'Migration completed successfully',
                'executed_migrations': executed_migrations
            }
            
        except Exception as exc:
            self.logger.error(f"Failed to execute migration plan: {exc}")
            return {
                'success': False,
                'message': f'Execution failed: {exc}',
                'executed_migrations': []
            }
    
    def _rollback_executed_migrations(self, executed_migrations: List[Dict[str, Any]], 
                                   context: Dict[str, Any] = None):
        """Rollback executed migrations."""
        for migration in reversed(executed_migrations):
            try:
                self.version_manager.rollback_migration(migration['id'], context)
                migration['status'] = 'rolled_back'
            except Exception as exc:
                self.logger.error(f"Failed to rollback migration {migration['id']}: {exc}")


class VersionRegistry:
    """Registry for managing versions across integrations."""
    
    def __init__(self):
        self.version_managers: Dict[str, BaseVersionManager] = {}
        self.compatibility_checker = CompatibilityChecker()
        self.logger = logging.getLogger(f"{__name__}.VersionRegistry")
    
    def register_manager(self, integration_type: str, manager: BaseVersionManager):
        """Register version manager for integration type."""
        self.version_managers[integration_type] = manager
        self.logger.info(f"Registered version manager for {integration_type}")
    
    def get_manager(self, integration_type: str) -> Optional[BaseVersionManager]:
        """Get version manager for integration type."""
        return self.version_managers.get(integration_type)
    
    def check_compatibility(self, integration_id: str, integration_type: str, 
                           version: Version) -> Dict[str, Any]:
        """Check compatibility for integration."""
        manager = self.get_manager(integration_type)
        if not manager:
            return {
                'compatible': False,
                'reason': f'No version manager for {integration_type}',
                'suggestions': []
            }
        
        return self.compatibility_checker.check_compatibility(integration_id, version, manager)
    
    def get_compatibility_matrix(self, integration_id: str, integration_type: str) -> Dict[str, Any]:
        """Get compatibility matrix for integration."""
        manager = self.get_manager(integration_type)
        if not manager:
            return {}
        
        return self.compatibility_checker.get_compatibility_matrix(integration_id, manager)
    
    def plan_migration(self, integration_id: str, integration_type: str, 
                      target_version: Version) -> Dict[str, Any]:
        """Plan migration for integration."""
        manager = self.get_manager(integration_type)
        if not manager:
            return {
                'migration_needed': False,
                'reason': f'No version manager for {integration_type}',
                'migrations': []
            }
        
        migration_manager = VersionMigrationManager(manager)
        return migration_manager.plan_migration(integration_id, target_version)
    
    def execute_migration(self, integration_id: str, integration_type: str, 
                         target_version: Version, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute migration for integration."""
        manager = self.get_manager(integration_type)
        if not manager:
            return {
                'success': False,
                'message': f'No version manager for {integration_type}',
                'executed_migrations': []
            }
        
        migration_manager = VersionMigrationManager(manager)
        return migration_manager.execute_migration_plan(integration_id, target_version, context)


# Global version registry instance
version_registry = VersionRegistry()

# Register default version manager
version_registry.register_manager('default', DefaultVersionManager())


# Version utilities
class VersionUtils:
    """Utilities for version management."""
    
    @staticmethod
    def parse_version(version_str: str) -> Version:
        """Parse version string."""
        return Version.from_string(version_str)
    
    @staticmethod
    def compare_versions(version1: Version, version2: Version) -> str:
        """Compare two versions."""
        if version1 < version2:
            return 'less_than'
        elif version1 > version2:
            return 'greater_than'
        else:
            return 'equal'
    
    @staticmethod
    def get_version_difference(version1: Version, version2: Version) -> Dict[str, Any]:
        """Get difference between versions."""
        if version1 == version2:
            return {
                'type': 'none',
                'description': 'Versions are identical'
            }
        
        version_type = version2.get_version_type(version1)
        
        return {
            'type': version_type.value,
            'description': f'Version changed from {version1} to {version2}',
            'breaking_change': version_type in [VersionType.MAJOR],
            'new_features': version_type in [VersionType.MINOR, VersionType.MAJOR],
            'bug_fixes': version_type == VersionType.PATCH
        }
    
    @staticmethod
    def validate_version(version_str: str) -> bool:
        """Validate version string format."""
        try:
            Version.from_string(version_str)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def get_next_version(current_version: Version, version_type: VersionType) -> Version:
        """Get next version based on type."""
        major, minor, patch = current_version.major, current_version.minor, current_version.patch
        
        if version_type == VersionType.MAJOR:
            major += 1
            minor = 0
            patch = 0
        elif version_type == VersionType.MINOR:
            minor += 1
            patch = 0
        elif version_type == VersionType.PATCH:
            patch += 1
        else:
            # For other types, just increment patch
            patch += 1
        
        return Version(major=major, minor=minor, patch=patch)
    
    @staticmethod
    def create_version_info(integration_id: str, version_str: str, **kwargs) -> VersionInfo:
        """Create version info."""
        version = Version.from_string(version_str)
        
        return VersionInfo(
            integration_id=integration_id,
            current_version=version,
            supported_versions=kwargs.get('supported_versions', [version]),
            deprecated_versions=kwargs.get('deprecated_versions', []),
            compatibility_rules=kwargs.get('compatibility_rules', {}),
            metadata=kwargs.get('metadata', {})
        )


# Decorators
def version_compatible(integration_type: str = 'default'):
    """Decorator to check version compatibility."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get integration ID and version from kwargs
            integration_id = kwargs.get('integration_id')
            version_str = kwargs.get('version')
            
            if integration_id and version_str:
                version = VersionUtils.parse_version(version_str)
                compatibility = version_registry.check_compatibility(
                    integration_id, integration_type, version
                )
                
                if not compatibility['compatible']:
                    raise ValueError(f"Version not compatible: {compatibility['reason']}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def version_migration(target_version: str, integration_type: str = 'default'):
    """Decorator to handle version migration."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get integration ID from kwargs
            integration_id = kwargs.get('integration_id')
            
            if integration_id:
                version = VersionUtils.parse_version(target_version)
                
                # Plan migration
                plan = version_registry.plan_migration(
                    integration_id, integration_type, version
                )
                
                if plan['migration_needed']:
                    # Execute migration
                    result = version_registry.execute_migration(
                        integration_id, integration_type, version, kwargs
                    )
                    
                    if not result['success']:
                        raise ValueError(f"Migration failed: {result['message']}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator
