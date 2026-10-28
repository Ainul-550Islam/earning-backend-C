# =============================================================================
# INTEGRATION_SYSTEM/versioning.py
# =============================================================================
"""
Integration Versioning Management.

Provides version control, compatibility checking, and migration
capabilities for integration configurations and data formats.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from packaging import version

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

from .integ_exceptions import VersionError, VersionCompatibilityError, VersionMigrationError

logger = logging.getLogger(__name__)


class VersionCompatibility(Enum):
    """Version compatibility levels."""
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    DEPRECATED = "deprecated"
    UNKNOWN = "unknown"


@dataclass
class VersionInfo:
    """Version information structure."""
    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build: Optional[str] = None
    
    def __str__(self) -> str:
        """Convert version to string."""
        version_str = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version_str += f"-{self.prerelease}"
        if self.build:
            version_str += f"+{self.build}"
        return version_str
    
    @classmethod
    def from_string(cls, version_str: str) -> 'VersionInfo':
        """Create version from string."""
        try:
            # Parse semantic version
            pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9\-\.]+))?(?:\+([a-zA-Z0-9\-\.]+))?$'
            match = re.match(pattern, version_str)
            
            if not match:
                raise VersionError(f"Invalid version format: {version_str}")
            
            major, minor, patch, prerelease, build = match.groups()
            
            return cls(
                major=int(major),
                minor=int(minor),
                patch=int(patch),
                prerelease=prerelease,
                build=build
            )
            
        except Exception as e:
            raise VersionError(f"Failed to parse version '{version_str}': {e}")
    
    def is_compatible_with(self, other: 'VersionInfo', compatibility_mode: str = 'minor') -> bool:
        """
        Check compatibility with another version.
        
        Args:
            other: Other version to check against
            compatibility_mode: Compatibility mode ('major', 'minor', 'patch')
            
        Returns:
            True if versions are compatible
        """
        if compatibility_mode == 'major':
            return self.major == other.major
        elif compatibility_mode == 'minor':
            return self.major == other.major and self.minor == other.minor
        elif compatibility_mode == 'patch':
            return (
                self.major == other.major and 
                self.minor == other.minor and 
                self.patch == other.patch
            )
        else:
            return False
    
    def is_newer_than(self, other: 'VersionInfo') -> bool:
        """Check if this version is newer than another."""
        if self.major != other.major:
            return self.major > other.major
        if self.minor != other.minor:
            return self.minor > other.minor
        if self.patch != other.patch:
            return self.patch > other.patch
        return False
    
    def is_older_than(self, other: 'VersionInfo') -> bool:
        """Check if this version is older than another."""
        return other.is_newer_than(self)


@dataclass
class VersionedConfig:
    """Versioned configuration structure."""
    version: VersionInfo
    config_data: Dict[str, Any]
    created_at: datetime = field(default_factory=timezone.now)
    updated_at: datetime = field(default_factory=timezone.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    migration_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'version': str(self.version),
            'config_data': self.config_data,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata,
            'migration_history': self.migration_history
        }


@dataclass
class MigrationRule:
    """Migration rule for version upgrades/downgrades."""
    from_version: VersionInfo
    to_version: VersionInfo
    migration_func: Callable[[Dict[str, Any]], Dict[str, Any]]
    description: str
    is_backward_compatible: bool = True
    created_at: datetime = field(default_factory=timezone.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class VersionManager:
    """
    Integration versioning manager.
    
    Provides version control, compatibility checking, and migration
    capabilities for integration configurations.
    """
    
    def __init__(self):
        """Initialize version manager."""
        self.versioned_configs: Dict[str, VersionedConfig] = {}
        self.migration_rules: List[MigrationRule] = []
        self.compatibility_matrix: Dict[Tuple[str, str], VersionCompatibility] = {}
        
        # Configuration
        self.default_compatibility_mode = getattr(settings, 'VERSION_DEFAULT_COMPATIBILITY_MODE', 'minor')
        self.enable_migration_cache = getattr(settings, 'VERSION_ENABLE_MIGRATION_CACHE', True)
        self.migration_cache_ttl = getattr(settings, 'VERSION_MIGRATION_CACHE_TTL', 3600)
        
        logger.info("VersionManager initialized")
    
    def register_version(self, integration_name: str, version: Union[str, VersionInfo],
                       config_data: Dict[str, Any], **kwargs) -> VersionedConfig:
        """
        Register a versioned configuration.
        
        Args:
            integration_name: Integration name
            version: Version string or VersionInfo
            config_data: Configuration data
            **kwargs: Additional parameters
            
        Returns:
            Versioned configuration
        """
        if isinstance(version, str):
            version = VersionInfo.from_string(version)
        
        versioned_config = VersionedConfig(
            version=version,
            config_data=config_data,
            **kwargs
        )
        
        key = f"{integration_name}:{version}"
        self.versioned_configs[key] = versioned_config
        
        logger.info(f"Registered version {version} for integration {integration_name}")
        return versioned_config
    
    def get_version(self, integration_name: str, version: Union[str, VersionInfo]) -> Optional[VersionedConfig]:
        """
        Get versioned configuration.
        
        Args:
            integration_name: Integration name
            version: Version string or VersionInfo
            
        Returns:
            Versioned configuration or None
        """
        if isinstance(version, str):
            version = VersionInfo.from_string(version)
        
        key = f"{integration_name}:{version}"
        return self.versioned_configs.get(key)
    
    def get_latest_version(self, integration_name: str) -> Optional[VersionedConfig]:
        """
        Get latest version for integration.
        
        Args:
            integration_name: Integration name
            
        Returns:
            Latest versioned configuration or None
        """
        integration_versions = [
            config for key, config in self.versioned_configs.items()
            if key.startswith(f"{integration_name}:")
        ]
        
        if not integration_versions:
            return None
        
        # Sort by version (newest first)
        integration_versions.sort(
            key=lambda x: (x.version.major, x.version.minor, x.version.patch),
            reverse=True
        )
        
        return integration_versions[0]
    
    def list_versions(self, integration_name: str) -> List[VersionedConfig]:
        """
        List all versions for integration.
        
        Args:
            integration_name: Integration name
            
        Returns:
            List of versioned configurations
        """
        integration_versions = [
            config for key, config in self.versioned_configs.items()
            if key.startswith(f"{integration_name}:")
        ]
        
        # Sort by version (newest first)
        integration_versions.sort(
            key=lambda x: (x.version.major, x.version.minor, x.version.patch),
            reverse=True
        )
        
        return integration_versions
    
    def check_compatibility(self, integration_name: str, version1: Union[str, VersionInfo],
                          version2: Union[str, VersionInfo]) -> VersionCompatibility:
        """
        Check compatibility between two versions.
        
        Args:
            integration_name: Integration name
            version1: First version
            version2: Second version
            
        Returns:
            Compatibility level
        """
        if isinstance(version1, str):
            version1 = VersionInfo.from_string(version1)
        if isinstance(version2, str):
            version2 = VersionInfo.from_string(version2)
        
        # Check compatibility matrix first
        matrix_key = (str(version1), str(version2))
        if matrix_key in self.compatibility_matrix:
            return self.compatibility_matrix[matrix_key]
        
        # Use default compatibility logic
        if version1.is_compatible_with(version2, self.default_compatibility_mode):
            return VersionCompatibility.COMPATIBLE
        elif version1.is_newer_than(version2):
            return VersionCompatibility.DEPRECATED
        else:
            return VersionCompatibility.INCOMPATIBLE
    
    def register_migration_rule(self, from_version: Union[str, VersionInfo],
                               to_version: Union[str, VersionInfo],
                               migration_func: Callable[[Dict[str, Any]], Dict[str, Any]],
                               description: str, **kwargs) -> None:
        """
        Register a migration rule.
        
        Args:
            from_version: Source version
            to_version: Target version
            migration_func: Migration function
            description: Migration description
            **kwargs: Additional parameters
        """
        if isinstance(from_version, str):
            from_version = VersionInfo.from_string(from_version)
        if isinstance(to_version, str):
            to_version = VersionInfo.from_string(to_version)
        
        migration_rule = MigrationRule(
            from_version=from_version,
            to_version=to_version,
            migration_func=migration_func,
            description=description,
            **kwargs
        )
        
        self.migration_rules.append(migration_rule)
        logger.info(f"Registered migration rule: {from_version} -> {to_version}")
    
    def find_migration_path(self, from_version: Union[str, VersionInfo],
                          to_version: Union[str, VersionInfo]) -> List[MigrationRule]:
        """
        Find migration path between versions.
        
        Args:
            from_version: Source version
            to_version: Target version
            
        Returns:
            List of migration rules
        """
        if isinstance(from_version, str):
            from_version = VersionInfo.from_string(from_version)
        if isinstance(to_version, str):
            to_version = VersionInfo.from_string(to_version)
        
        # Check cache first
        if self.enable_migration_cache:
            cache_key = f"migration_path:{from_version}->{to_version}"
            cached_path = cache.get(cache_key)
            if cached_path:
                return cached_path
        
        # Find direct migration
        direct_rule = self._find_direct_migration(from_version, to_version)
        if direct_rule:
            path = [direct_rule]
            if self.enable_migration_cache:
                cache.set(cache_key, path, self.migration_cache_ttl)
            return path
        
        # Find multi-step migration
        path = self._find_multi_step_migration(from_version, to_version)
        if path:
            if self.enable_migration_cache:
                cache.set(cache_key, path, self.migration_cache_ttl)
            return path
        
        return []
    
    def _find_direct_migration(self, from_version: VersionInfo, to_version: VersionInfo) -> Optional[MigrationRule]:
        """Find direct migration rule."""
        for rule in self.migration_rules:
            if rule.from_version == from_version and rule.to_version == to_version:
                return rule
        return None
    
    def _find_multi_step_migration(self, from_version: VersionInfo, to_version: VersionInfo) -> List[MigrationRule]:
        """Find multi-step migration path using BFS."""
        from collections import deque
        
        queue = deque([(from_version, [])])
        visited = set()
        
        while queue:
            current_version, path = queue.popleft()
            
            if current_version == to_version:
                return path
            
            if current_version in visited:
                continue
            
            visited.add(current_version)
            
            # Find next steps
            for rule in self.migration_rules:
                if rule.from_version == current_version:
                    new_path = path + [rule]
                    queue.append((rule.to_version, new_path))
        
        return []
    
    async def migrate_config(self, integration_name: str, from_version: Union[str, VersionInfo],
                           to_version: Union[str, VersionInfo], config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate configuration data between versions.
        
        Args:
            integration_name: Integration name
            from_version: Source version
            to_version: Target version
            config_data: Configuration data to migrate
            
        Returns:
            Migrated configuration data
        """
        if isinstance(from_version, str):
            from_version = VersionInfo.from_string(from_version)
        if isinstance(to_version, str):
            to_version = VersionInfo.from_string(to_version)
        
        # Find migration path
        migration_path = self.find_migration_path(from_version, to_version)
        
        if not migration_path:
            raise VersionMigrationError(f"No migration path found from {from_version} to {to_version}")
        
        # Apply migrations
        migrated_data = config_data.copy()
        migration_history = []
        
        for rule in migration_path:
            try:
                migrated_data = rule.migration_func(migrated_data)
                
                migration_history.append({
                    'from_version': str(rule.from_version),
                    'to_version': str(rule.to_version),
                    'description': rule.description,
                    'migrated_at': timezone.now().isoformat()
                })
                
                logger.info(f"Applied migration: {rule.from_version} -> {rule.to_version}")
                
            except Exception as e:
                raise VersionMigrationError(f"Migration failed: {rule.from_version} -> {rule.to_version}: {e}")
        
        # Update migration history in target version
        target_config = self.get_version(integration_name, to_version)
        if target_config:
            target_config.migration_history.extend(migration_history)
            target_config.updated_at = timezone.now()
        
        return migrated_data
    
    def register_compatibility(self, version1: Union[str, VersionInfo], version2: Union[str, VersionInfo],
                            compatibility: VersionCompatibility) -> None:
        """
        Register explicit compatibility between versions.
        
        Args:
            version1: First version
            version2: Second version
            compatibility: Compatibility level
        """
        if isinstance(version1, str):
            version1 = VersionInfo.from_string(version1)
        if isinstance(version2, str):
            version2 = VersionInfo.from_string(version2)
        
        matrix_key = (str(version1), str(version2))
        self.compatibility_matrix[matrix_key] = compatibility
        
        logger.info(f"Registered compatibility: {version1} <-> {version2} = {compatibility.value}")
    
    def get_version_statistics(self, integration_name: str) -> Dict[str, Any]:
        """
        Get version statistics for integration.
        
        Args:
            integration_name: Integration name
            
        Returns:
            Version statistics
        """
        versions = self.list_versions(integration_name)
        
        if not versions:
            return {'total_versions': 0}
        
        total_versions = len(versions)
        latest_version = versions[0].version
        oldest_version = versions[-1].version
        
        # Count by major version
        major_counts = {}
        for version_info in versions:
            major = version_info.version.major
            major_counts[major] = major_counts.get(major, 0) + 1
        
        return {
            'total_versions': total_versions,
            'latest_version': str(latest_version),
            'oldest_version': str(oldest_version),
            'major_version_distribution': major_counts,
            'version_range': f"{oldest_version} - {latest_version}",
            'migration_rules_count': len([
                rule for rule in self.migration_rules
                if any(key.startswith(f"{integration_name}:") for key in self.versioned_configs.keys())
            ])
        }
    
    def cleanup_old_versions(self, integration_name: str, keep_count: int = 5) -> int:
        """
        Clean up old versions, keeping only the most recent ones.
        
        Args:
            integration_name: Integration name
            keep_count: Number of versions to keep
            
        Returns:
            Number of versions removed
        """
        versions = self.list_versions(integration_name)
        
        if len(versions) <= keep_count:
            return 0
        
        # Remove oldest versions
        versions_to_remove = versions[keep_count:]
        removed_count = 0
        
        for version_config in versions_to_remove:
            key = f"{integration_name}:{version_config.version}"
            if key in self.versioned_configs:
                del self.versioned_configs[key]
                removed_count += 1
        
        logger.info(f"Cleaned up {removed_count} old versions for {integration_name}")
        return removed_count
    
    def export_versions(self, integration_name: str) -> Dict[str, Any]:
        """
        Export all versions for integration.
        
        Args:
            integration_name: Integration name
            
        Returns:
            Exported version data
        """
        versions = self.list_versions(integration_name)
        
        export_data = {
            'integration_name': integration_name,
            'exported_at': timezone.now().isoformat(),
            'total_versions': len(versions),
            'versions': [version.to_dict() for version in versions],
            'migration_rules': [
                {
                    'from_version': str(rule.from_version),
                    'to_version': str(rule.to_version),
                    'description': rule.description,
                    'is_backward_compatible': rule.is_backward_compatible,
                    'created_at': rule.created_at.isoformat()
                }
                for rule in self.migration_rules
            ]
        }
        
        return export_data
    
    def import_versions(self, export_data: Dict[str, Any]) -> int:
        """
        Import versions from export data.
        
        Args:
            export_data: Exported version data
            
        Returns:
            Number of versions imported
        """
        integration_name = export_data['integration_name']
        imported_count = 0
        
        # Import versions
        for version_data in export_data['versions']:
            version = VersionInfo.from_string(version_data['version'])
            
            versioned_config = VersionedConfig(
                version=version,
                config_data=version_data['config_data'],
                created_at=datetime.fromisoformat(version_data['created_at']),
                updated_at=datetime.fromisoformat(version_data['updated_at']),
                metadata=version_data['metadata'],
                migration_history=version_data['migration_history']
            )
            
            key = f"{integration_name}:{version}"
            self.versioned_configs[key] = versioned_config
            imported_count += 1
        
        logger.info(f"Imported {imported_count} versions for {integration_name}")
        return imported_count


# Global version manager instance
_version_manager = None


def get_version_manager() -> VersionManager:
    """Get global version manager instance."""
    global _version_manager
    if _version_manager is None:
        _version_manager = VersionManager()
    return _version_manager


# Convenience functions
def register_integration_version(integration_name: str, version: str, config_data: Dict[str, Any]) -> VersionedConfig:
    """
    Convenience function for registering integration version.
    
    Args:
        integration_name: Integration name
        version: Version string
        config_data: Configuration data
        
    Returns:
        Versioned configuration
    """
    manager = get_version_manager()
    return manager.register_version(integration_name, version, config_data)


def get_latest_integration_version(integration_name: str) -> Optional[VersionedConfig]:
    """
    Convenience function for getting latest integration version.
    
    Args:
        integration_name: Integration name
        
    Returns:
        Latest versioned configuration or None
    """
    manager = get_version_manager()
    return manager.get_latest_version(integration_name)


async def migrate_integration_config(integration_name: str, from_version: str, to_version: str,
                                  config_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function for migrating integration configuration.
    
    Args:
        integration_name: Integration name
        from_version: Source version
        to_version: Target version
        config_data: Configuration data to migrate
        
    Returns:
        Migrated configuration data
    """
    manager = get_version_manager()
    return await manager.migrate_config(integration_name, from_version, to_version, config_data)


def check_integration_compatibility(integration_name: str, version1: str, version2: str) -> VersionCompatibility:
    """
    Convenience function for checking integration compatibility.
    
    Args:
        integration_name: Integration name
        version1: First version
        version2: Second version
        
    Returns:
        Compatibility level
    """
    manager = get_version_manager()
    return manager.check_compatibility(integration_name, version1, version2)


# Decorator for versioned integrations
def versioned_integration(integration_name: str, version: str):
    """
    Decorator for versioned integration functions.
    
    Args:
        integration_name: Integration name
        version: Version string
    """
    def decorator(func: Callable) -> Callable:
        func._integration_version = {
            'integration_name': integration_name,
            'version': version
        }
        return func
    return decorator


# Utility functions for version parsing
def parse_version(version_str: str) -> VersionInfo:
    """
    Parse version string.
    
    Args:
        version_str: Version string
        
    Returns:
        VersionInfo object
    """
    return VersionInfo.from_string(version_str)


def compare_versions(version1: Union[str, VersionInfo], version2: Union[str, VersionInfo]) -> int:
    """
    Compare two versions.
    
    Args:
        version1: First version
        version2: Second version
        
    Returns:
        -1 if version1 < version2, 0 if equal, 1 if version1 > version2
    """
    if isinstance(version1, str):
        version1 = VersionInfo.from_string(version1)
    if isinstance(version2, str):
        version2 = VersionInfo.from_string(version2)
    
    if version1.is_newer_than(version2):
        return 1
    elif version2.is_newer_than(version1):
        return -1
    else:
        return 0


def is_version_compatible(version1: Union[str, VersionInfo], version2: Union[str, VersionInfo],
                        compatibility_mode: str = 'minor') -> bool:
    """
    Check if two versions are compatible.
    
    Args:
        version1: First version
        version2: Second version
        compatibility_mode: Compatibility mode
        
    Returns:
        True if compatible
    """
    if isinstance(version1, str):
        version1 = VersionInfo.from_string(version1)
    if isinstance(version2, str):
        version2 = VersionInfo.from_string(version2)
    
    return version1.is_compatible_with(version2, compatibility_mode)
