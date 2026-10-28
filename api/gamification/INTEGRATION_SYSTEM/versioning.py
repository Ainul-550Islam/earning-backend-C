"""
Version Management — Version control and compatibility management system.

This module provides comprehensive version management capabilities
for handling version compatibility, upgrades, and migrations.
"""

from __future__ import annotations
import threading

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum

from .integ_constants import ErrorCode
from .integ_exceptions import (
    IntegrationError, VersionMismatchError, VersionNotSupportedError,
    ValidationError
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Version Types
# ---------------------------------------------------------------------------

class VersionType(Enum):
    """Version type enumeration."""
    SEMANTIC = "semantic"      # MAJOR.MINOR.PATCH
    DATE_BASED = "date_based"  # YYYY.MM.DD
    SEQUENTIAL = "sequential"  # 1, 2, 3, ...
    CUSTOM = "custom"


class CompatibilityLevel(Enum):
    """Compatibility level enumeration."""
    COMPATIBLE = "compatible"
    BACKWARD_COMPATIBLE = "backward_compatible"
    FORWARD_COMPATIBLE = "forward_compatible"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


class MigrationType(Enum):
    """Migration type enumeration."""
    FORWARD = "forward"
    BACKWARD = "backward"
    BIDIRECTIONAL = "bidirectional"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Version Data Classes
# ---------------------------------------------------------------------------

@dataclass
class Version:
    """Version representation."""
    
    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build: Optional[str] = None
    version_type: VersionType = VersionType.SEMANTIC
    
    def __str__(self) -> str:
        """String representation."""
        version_str = f"{self.major}.{self.minor}.{self.patch}"
        
        if self.prerelease:
            version_str += f"-{self.prerelease}"
        
        if self.build:
            version_str += f"+{self.build}"
        
        return version_str
    
    def __eq__(self, other: Any) -> bool:
        """Equality comparison."""
        if not isinstance(other, Version):
            return False
        
        return (self.major == other.major and
                self.minor == other.minor and
                self.patch == other.patch and
                self.prerelease == other.prerelease and
                self.build == other.build)
    
    def __lt__(self, other: Any) -> bool:
        """Less than comparison."""
        if not isinstance(other, Version):
            return False
        
        if self.major != other.major:
            return self.major < other.major
        
        if self.minor != other.minor:
            return self.minor < other.minor
        
        if self.patch != other.patch:
            return self.patch < other.patch
        
        # Handle prerelease versions
        if self.prerelease and not other.prerelease:
            return True  # Prerelease is less than release
        elif not self.prerelease and other.prerelease:
            return False  # Release is greater than prerelease
        elif self.prerelease and other.prerelease:
            return self.prerelease < other.prerelease
        
        return False
    
    def __le__(self, other: Any) -> bool:
        """Less than or equal comparison."""
        return self == other or self < other
    
    def __gt__(self, other: Any) -> bool:
        """Greater than comparison."""
        return not self <= other
    
    def __ge__(self, other: Any) -> bool:
        """Greater than or equal comparison."""
        return not self < other
    
    @classmethod
    def parse(cls, version_str: str) -> 'Version':
        """Parse version string."""
        # Semantic version pattern
        semantic_pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9\-\.]+))?(?:\+([a-zA-Z0-9\-\.]+))?$'
        match = re.match(semantic_pattern, version_str)
        
        if match:
            major, minor, patch, prerelease, build = match.groups()
            return cls(
                major=int(major),
                minor=int(minor),
                patch=int(patch),
                prerelease=prerelease,
                build=build,
                version_type=VersionType.SEMANTIC
            )
        
        # Date-based version pattern
        date_pattern = r'^(\d{4})\.(\d{2})\.(\d{2})$'
        match = re.match(date_pattern, version_str)
        
        if match:
            year, month, day = match.groups()
            return cls(
                major=int(year),
                minor=int(month),
                patch=int(day),
                version_type=VersionType.DATE_BASED
            )
        
        # Sequential version pattern
        sequential_pattern = r'^(\d+)$'
        match = re.match(sequential_pattern, version_str)
        
        if match:
            number = int(match.group(1))
            return cls(
                major=number,
                minor=0,
                patch=0,
                version_type=VersionType.SEQUENTIAL
            )
        
        raise ValueError(f"Invalid version format: {version_str}")
    
    def next_major(self) -> 'Version':
        """Get next major version."""
        return Version(
            major=self.major + 1,
            minor=0,
            patch=0,
            prerelease=self.prerelease,
            build=self.build,
            version_type=self.version_type
        )
    
    def next_minor(self) -> 'Version':
        """Get next minor version."""
        return Version(
            major=self.major,
            minor=self.minor + 1,
            patch=0,
            prerelease=self.prerelease,
            build=self.build,
            version_type=self.version_type
        )
    
    def next_patch(self) -> 'Version':
        """Get next patch version."""
        return Version(
            major=self.major,
            minor=self.minor,
            patch=self.patch + 1,
            prerelease=self.prerelease,
            build=self.build,
            version_type=self.version_type
        )
    
    def is_prerelease(self) -> bool:
        """Check if version is prerelease."""
        return self.prerelease is not None
    
    def is_stable(self) -> bool:
        """Check if version is stable."""
        return not self.is_prerelease()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "major": self.major,
            "minor": self.minor,
            "patch": self.patch,
            "prerelease": self.prerelease,
            "build": self.build,
            "version_type": self.version_type.value,
            "string": str(self),
            "is_prerelease": self.is_prerelease(),
            "is_stable": self.is_stable()
        }


@dataclass
class VersionConstraint:
    """Version constraint specification."""
    
    constraint_str: str
    min_version: Optional[Version] = None
    max_version: Optional[Version] = None
    excluded_versions: List[Version] = field(default_factory=list)
    preferred_version: Optional[Version] = None
    
    def __str__(self) -> str:
        """String representation."""
        return self.constraint_str
    
    @classmethod
    def parse(cls, constraint_str: str) -> 'VersionConstraint':
        """Parse constraint string."""
        constraint = cls(constraint_str=constraint_str)
        
        # Parse various constraint formats
        # Exact version: "1.2.3"
        exact_pattern = r'^(\d+\.\d+\.\d+(?:-[a-zA-Z0-9\-\.]+)?(?:\+[a-zA-Z0-9\-\.]+)?)$'
        match = re.match(exact_pattern, constraint_str)
        
        if match:
            version = Version.parse(match.group(1))
            constraint.min_version = version
            constraint.max_version = version
            return constraint
        
        # Range: ">=1.2.3,<2.0.0"
        range_pattern = r'^>=(\d+\.\d+\.\d+(?:-[a-zA-Z0-9\-\.]+)?(?:\+[a-zA-Z0-9\-\.]+)?),<(\d+\.\d+\.\d+(?:-[a-zA-Z0-9\-\.]+)?(?:\+[a-zA-Z0-9\-\.]+)?)$'
        match = re.match(range_pattern, constraint_str)
        
        if match:
            constraint.min_version = Version.parse(match.group(1))
            constraint.max_version = Version.parse(match.group(2))
            return constraint
        
        # Minimum: ">=1.2.3"
        min_pattern = r'^>=(\d+\.\d+\.\d+(?:-[a-zA-Z0-9\-\.]+)?(?:\+[a-zA-Z0-9\-\.]+)?)$'
        match = re.match(min_pattern, constraint_str)
        
        if match:
            constraint.min_version = Version.parse(match.group(1))
            return constraint
        
        # Maximum: "<=1.2.3"
        max_pattern = r'^<=(\d+\.\d+\.\d+(?:-[a-zA-Z0-9\-\.]+)?(?:\+[a-zA-Z0-9\-\.]+)?)$'
        match = re.match(max_pattern, constraint_str)
        
        if match:
            constraint.max_version = Version.parse(match.group(1))
            return constraint
        
        # Caret: "^1.2.3" (>=1.2.3,<2.0.0)
        caret_pattern = r'^\^(\d+\.\d+\.\d+(?:-[a-zA-Z0-9\-\.]+)?(?:\+[a-zA-Z0-9\-\.]+)?)$'
        match = re.match(caret_pattern, constraint_str)
        
        if match:
            version = Version.parse(match.group(1))
            constraint.min_version = version
            constraint.max_version = version.next_major()
            return constraint
        
        # Tilde: "~1.2.3" (>=1.2.3,<1.3.0)
        tilde_pattern = r'^~(\d+\.\d+\.\d+(?:-[a-zA-Z0-9\-\.]+)?(?:\+[a-zA-Z0-9\-\.]+)?)$'
        match = re.match(tilde_pattern, constraint_str)
        
        if match:
            version = Version.parse(match.group(1))
            constraint.min_version = version
            constraint.max_version = version.next_minor()
            return constraint
        
        # Wildcard: "1.2.*"
        wildcard_pattern = r'^(\d+)\.(\d+)\.\*$'
        match = re.match(wildcard_pattern, constraint_str)
        
        if match:
            major, minor = match.groups()
            constraint.min_version = Version(int(major), int(minor), 0)
            constraint.max_version = Version(int(major), int(minor) + 1, 0)
            return constraint
        
        raise ValueError(f"Invalid constraint format: {constraint_str}")
    
    def satisfies(self, version: Version) -> bool:
        """Check if version satisfies constraint."""
        # Check minimum version
        if self.min_version and version < self.min_version:
            return False
        
        # Check maximum version
        if self.max_version and version >= self.max_version:
            return False
        
        # Check excluded versions
        for excluded in self.excluded_versions:
            if version == excluded:
                return False
        
        return True
    
    def get_compatible_versions(self, available_versions: List[Version]) -> List[Version]:
        """Get compatible versions from available versions."""
        compatible = [v for v in available_versions if self.satisfies(v)]
        
        # Sort by version (newest first)
        compatible.sort(reverse=True)
        
        return compatible
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "constraint_str": self.constraint_str,
            "min_version": str(self.min_version) if self.min_version else None,
            "max_version": str(self.max_version) if self.max_version else None,
            "excluded_versions": [str(v) for v in self.excluded_versions],
            "preferred_version": str(self.preferred_version) if self.preferred_version else None
        }


@dataclass
class VersionInfo:
    """Version information for a component."""
    
    component_name: str
    current_version: Version
    available_versions: List[Version] = field(default_factory=list)
    supported_versions: List[VersionConstraint] = field(default_factory=list)
    release_date: Optional[datetime] = None
    deprecation_date: Optional[datetime] = None
    end_of_life_date: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_latest_version(self, include_prerelease: bool = False) -> Optional[Version]:
        """Get latest available version."""
        versions = self.available_versions.copy()
        
        if not include_prerelease:
            versions = [v for v in versions if v.is_stable()]
        
        if not versions:
            return None
        
        return max(versions)
    
    def is_version_supported(self, version: Version) -> bool:
        """Check if version is supported."""
        for constraint in self.supported_versions:
            if constraint.satisfies(version):
                return True
        
        return False
    
    def get_compatible_versions(self, version: Version) -> List[Version]:
        """Get versions compatible with given version."""
        compatible = []
        
        for available in self.available_versions:
            # Check bidirectional compatibility
            if (self._are_compatible(version, available) and
                self._are_compatible(available, version)):
                compatible.append(available)
        
        return compatible
    
    def _are_compatible(self, version1: Version, version2: Version) -> bool:
        """Check if two versions are compatible."""
        # Same major version = compatible
        if version1.major == version2.major:
            return True
        
        # Different major versions = incompatible
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "component_name": self.component_name,
            "current_version": str(self.current_version),
            "available_versions": [str(v) for v in self.available_versions],
            "supported_versions": [str(c) for c in self.supported_versions],
            "release_date": self.release_date.isoformat() if self.release_date else None,
            "deprecation_date": self.deprecation_date.isoformat() if self.deprecation_date else None,
            "end_of_life_date": self.end_of_life_date.isoformat() if self.end_of_life_date else None,
            "metadata": self.metadata
        }


# ---------------------------------------------------------------------------
# Abstract Migration Base Class
# ---------------------------------------------------------------------------

class BaseMigration(ABC):
    """Abstract base class for version migrations."""
    
    def __init__(
        self,
        from_version: Version,
        to_version: Version,
        migration_type: MigrationType = MigrationType.FORWARD
    ):
        self.from_version = from_version
        self.to_version = to_version
        self.migration_type = migration_type
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def migrate(self, data: Any) -> Any:
        """Perform migration."""
        pass
    
    @abstractmethod
    def rollback(self, data: Any) -> Any:
        """Rollback migration."""
        pass
    
    @abstractmethod
    def validate_data(self, data: Any) -> List[str]:
        """Validate data before migration."""
        pass
    
    def can_migrate(self, from_version: Version, to_version: Version) -> bool:
        """Check if migration can handle version transition."""
        if self.migration_type == MigrationType.FORWARD:
            return (from_version == self.from_version and to_version == self.to_version)
        elif self.migration_type == MigrationType.BACKWARD:
            return (from_version == self.to_version and to_version == self.from_version)
        elif self.migration_type == MigrationType.BIDIRECTIONAL:
            return ((from_version == self.from_version and to_version == self.to_version) or
                   (from_version == self.to_version and to_version == self.from_version))
        
        return False


# ---------------------------------------------------------------------------
# Version Manager
# ---------------------------------------------------------------------------

class VersionManager:
    """Manager for version control and compatibility."""
    
    def __init__(self):
        self.version_info: Dict[str, VersionInfo] = {}
        self.migrations: Dict[str, List[BaseMigration]] = {}
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()  # Need to import threading
    
    def register_component(self, version_info: VersionInfo) -> None:
        """Register a component version info."""
        with self._lock:
            self.version_info[version_info.component_name] = version_info
            self.logger.info(f"Registered component: {version_info.component_name} v{version_info.current_version}")
    
    def unregister_component(self, component_name: str) -> bool:
        """Unregister a component."""
        with self._lock:
            if component_name in self.version_info:
                del self.version_info[component_name]
                if component_name in self.migrations:
                    del self.migrations[component_name]
                self.logger.info(f"Unregistered component: {component_name}")
                return True
            return False
    
    def get_component_info(self, component_name: str) -> Optional[VersionInfo]:
        """Get component version info."""
        with self._lock:
            return self.version_info.get(component_name)
    
    def register_migration(self, component_name: str, migration: BaseMigration) -> None:
        """Register a migration."""
        with self._lock:
            if component_name not in self.migrations:
                self.migrations[component_name] = []
            
            self.migrations[component_name].append(migration)
            self.logger.info(f"Registered migration: {component_name} {migration.from_version} -> {migration.to_version}")
    
    def check_compatibility(
        self,
        component_name: str,
        version: Version,
        current_version: Optional[Version] = None
    ) -> CompatibilityLevel:
        """Check version compatibility."""
        component_info = self.get_component_info(component_name)
        if not component_info:
            return CompatibilityLevel.UNKNOWN
        
        # Check if version is supported
        if not component_info.is_version_supported(version):
            return CompatibilityLevel.INCOMPATIBLE
        
        if not current_version:
            current_version = component_info.current_version
        
        # Same version
        if version == current_version:
            return CompatibilityLevel.COMPATIBLE
        
        # Newer version
        if version > current_version:
            return CompatibilityLevel.FORWARD_COMPATIBLE
        
        # Older version
        if version < current_version:
            return CompatibilityLevel.BACKWARD_COMPATIBLE
        
        return CompatibilityLevel.UNKNOWN
    
    def get_migration_path(
        self,
        component_name: str,
        from_version: Version,
        to_version: Version
    ) -> List[BaseMigration]:
        """Get migration path between versions."""
        if component_name not in self.migrations:
            return []
        
        migrations = self.migrations[component_name]
        path = []
        
        # Simple path finding (could be improved with graph algorithms)
        current = from_version
        
        while current != to_version:
            found_migration = None
            
            for migration in migrations:
                if migration.can_migrate(current, to_version):
                    found_migration = migration
                    break
            
            if not found_migration:
                # Try step-by-step migration
                for migration in migrations:
                    if migration.can_migrate(current, migration.to_version):
                        found_migration = migration
                        break
            
            if not found_migration:
                break
            
            path.append(found_migration)
            current = found_migration.to_version if current == found_migration.from_version else found_migration.from_version
        
        return path
    
    def migrate_data(
        self,
        component_name: str,
        data: Any,
        from_version: Version,
        to_version: Version
    ) -> Tuple[Any, List[str]]:
        """Migrate data from one version to another."""
        migration_path = self.get_migration_path(component_name, from_version, to_version)
        
        if not migration_path:
            raise VersionNotSupportedError(
                f"No migration path found for {component_name} from {from_version} to {to_version}"
            )
        
        current_data = data
        errors = []
        
        for migration in migration_path:
            try:
                # Validate data before migration
                validation_errors = migration.validate_data(current_data)
                if validation_errors:
                    errors.extend(validation_errors)
                    continue
                
                # Perform migration
                current_data = migration.migrate(current_data)
                
            except Exception as e:
                errors.append(f"Migration failed: {str(e)}")
                break
        
        return current_data, errors
    
    def get_upgrade_path(
        self,
        component_name: str,
        target_version: Version
    ) -> List[Version]:
        """Get upgrade path to target version."""
        component_info = self.get_component_info(component_name)
        if not component_info:
            return []
        
        current_version = component_info.current_version
        if target_version <= current_version:
            return []
        
        # Find available versions between current and target
        upgrade_versions = []
        
        for version in component_info.available_versions:
            if current_version < version <= target_version:
                upgrade_versions.append(version)
        
        upgrade_versions.sort()
        return upgrade_versions
    
    def get_latest_compatible_version(self, component_name: str, current_version: Version) -> Optional[Version]:
        """Get latest compatible version."""
        component_info = self.get_component_info(component_name)
        if not component_info:
            return None
        
        compatible_versions = component_info.get_compatible_versions(current_version)
        
        if not compatible_versions:
            return None
        
        return max(compatible_versions)
    
    def check_for_updates(self, component_name: str) -> Dict[str, Any]:
        """Check for available updates."""
        component_info = self.get_component_info(component_name)
        if not component_info:
            return {"error": f"Component '{component_name}' not found"}
        
        current_version = component_info.current_version
        latest_version = component_info.get_latest_version()
        
        if not latest_version:
            return {"error": "No available versions"}
        
        update_info = {
            "component_name": component_name,
            "current_version": str(current_version),
            "latest_version": str(latest_version),
            "update_available": latest_version > current_version,
            "upgrade_path": self.get_upgrade_path(component_name, latest_version)
        }
        
        # Check deprecation
        if component_info.deprecation_date:
            update_info["deprecated"] = True
            update_info["deprecation_date"] = component_info.deprecation_date.isoformat()
        else:
            update_info["deprecated"] = False
        
        # Check end of life
        if component_info.end_of_life_date:
            update_info["end_of_life"] = True
            update_info["end_of_life_date"] = component_info.end_of_life_date.isoformat()
        else:
            update_info["end_of_life"] = False
        
        return update_info
    
    def get_all_component_status(self) -> Dict[str, Any]:
        """Get status of all components."""
        status = {}
        
        for component_name, component_info in self.version_info.items():
            try:
                latest_version = component_info.get_latest_version()
                update_info = self.check_for_updates(component_name)
                
                status[component_name] = {
                    "current_version": str(component_info.current_version),
                    "latest_version": str(latest_version) if latest_version else None,
                    "update_available": update_info.get("update_available", False),
                    "deprecated": update_info.get("deprecated", False),
                    "end_of_life": update_info.get("end_of_life", False)
                }
                
            except Exception as e:
                status[component_name] = {"error": str(e)}
        
        return {
            "components": status,
            "total_components": len(self.version_info),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global version manager instance
version_manager = VersionManager()


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def parse_version(version_str: str) -> Version:
    """Parse version string."""
    return Version.parse(version_str)


def create_version_constraint(constraint_str: str) -> VersionConstraint:
    """Create version constraint."""
    return VersionConstraint.parse(constraint_str)


def register_component(
    component_name: str,
    current_version: str,
    available_versions: List[str],
    supported_versions: Optional[List[str]] = None
) -> None:
    """Register a component with the version manager."""
    version_info = VersionInfo(
        component_name=component_name,
        current_version=Version.parse(current_version),
        available_versions=[Version.parse(v) for v in available_versions],
        supported_versions=[VersionConstraint.parse(c) for c in supported_versions] if supported_versions else []
    )
    
    version_manager.register_component(version_info)


def check_version_compatibility(component_name: str, version: str) -> CompatibilityLevel:
    """Check version compatibility."""
    return version_manager.check_compatibility(component_name, Version.parse(version))


# Initialize logging
logger.info("Version management module initialized")
