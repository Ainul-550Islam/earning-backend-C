"""
Integration Versioning Module
Version management for integration system
"""

import logging
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings

from ..models import SecurityLog, SecurityIncident
from ..utils import SecurityUtils
from .integ_constants import *

User = get_user_model()
logger = logging.getLogger('security.integration.versioning')


class IntegrationVersion:
    """Integration version information"""
    
    def __init__(self, version: str, description: str = "", 
                 compatibility: List[str] = None, deprecated: bool = False):
        self.version = version
        self.description = description
        self.compatibility = compatibility or []
        self.deprecated = deprecated
        self.created_at = timezone.now()
        self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'version': self.version,
            'description': self.description,
            'compatibility': self.compatibility,
            'deprecated': self.deprecated,
            'created_at': self.created_at.isoformat(),
            'metadata': self.metadata
        }
    
    def is_compatible_with(self, other_version: str) -> bool:
        """Check if compatible with another version"""
        return other_version in self.compatibility
    
    def __str__(self):
        return f"v{self.version}"


class VersionManager:
    """Manager for integration versions"""
    
    def __init__(self):
        self.versions = {}
        self.current_versions = {}
        self.version_history = {}
        self.compatibility_matrix = {}
        self.migration_rules = {}
        self.enabled = True
    
    def register_version(self, integration_name: str, version: IntegrationVersion):
        """Register integration version"""
        if integration_name not in self.versions:
            self.versions[integration_name] = {}
        
        self.versions[integration_name][version.version] = version
        
        # Add to history
        if integration_name not in self.version_history:
            self.version_history[integration_name] = []
        
        self.version_history[integration_name].append({
            'version': version.version,
            'registered_at': timezone.now(),
            'description': version.description
        })
        
        logger.info(f"Registered version {version.version} for integration: {integration_name}")
    
    def set_current_version(self, integration_name: str, version: str):
        """Set current version for integration"""
        if integration_name in self.versions and version in self.versions[integration_name]:
            self.current_versions[integration_name] = version
            logger.info(f"Set current version {version} for integration: {integration_name}")
        else:
            logger.error(f"Version {version} not found for integration: {integration_name}")
    
    def get_current_version(self, integration_name: str) -> Optional[str]:
        """Get current version for integration"""
        return self.current_versions.get(integration_name)
    
    def get_version(self, integration_name: str, version: str) -> Optional[IntegrationVersion]:
        """Get specific version"""
        return self.versions.get(integration_name, {}).get(version)
    
    def get_all_versions(self, integration_name: str) -> Dict[str, IntegrationVersion]:
        """Get all versions for integration"""
        return self.versions.get(integration_name, {})
    
    def is_version_compatible(self, integration_name: str, version: str) -> bool:
        """Check if version is compatible with current version"""
        current_version = self.get_current_version(integration_name)
        
        if not current_version:
            return True  # No current version, assume compatible
        
        version_obj = self.get_version(integration_name, version)
        if version_obj:
            return version_obj.is_compatible_with(current_version)
        
        return False
    
    def add_compatibility_rule(self, integration_name: str, from_version: str, to_version: str):
        """Add compatibility rule between versions"""
        if integration_name not in self.compatibility_matrix:
            self.compatibility_matrix[integration_name] = {}
        
        if from_version not in self.compatibility_matrix[integration_name]:
            self.compatibility_matrix[integration_name][from_version] = []
        
        if to_version not in self.compatibility_matrix[integration_name][from_version]:
            self.compatibility_matrix[integration_name][from_version].append(to_version)
        
        logger.info(f"Added compatibility rule: {integration_name} {from_version} -> {to_version}")
    
    def get_compatible_versions(self, integration_name: str, version: str) -> List[str]:
        """Get compatible versions for a given version"""
        return self.compatibility_matrix.get(integration_name, {}).get(version, [])
    
    def add_migration_rule(self, integration_name: str, from_version: str, 
                          to_version: str, migration_func: Callable):
        """Add migration rule between versions"""
        if integration_name not in self.migration_rules:
            self.migration_rules[integration_name] = {}
        
        if from_version not in self.migration_rules[integration_name]:
            self.migration_rules[integration_name][from_version] = {}
        
        self.migration_rules[integration_name][from_version][to_version] = migration_func
        
        logger.info(f"Added migration rule: {integration_name} {from_version} -> {to_version}")
    
    def migrate_data(self, integration_name: str, data: Dict[str, Any], 
                    from_version: str, to_version: str) -> Dict[str, Any]:
        """Migrate data from one version to another"""
        migration_func = self.migration_rules.get(integration_name, {}).get(from_version, {}).get(to_version)
        
        if migration_func:
            try:
                return migration_func(data)
            except Exception as e:
                logger.error(f"Error migrating data from {from_version} to {to_version}: {e}")
                return data
        else:
            logger.warning(f"No migration rule found for {integration_name} {from_version} -> {to_version}")
            return data
    
    def get_version_history(self, integration_name: str) -> List[Dict[str, Any]]:
        """Get version history for integration"""
        return self.version_history.get(integration_name, [])
    
    def deprecate_version(self, integration_name: str, version: str):
        """Deprecate a version"""
        version_obj = self.get_version(integration_name, version)
        if version_obj:
            version_obj.deprecated = True
            logger.info(f"Deprecated version {version} for integration: {integration_name}")
    
    def is_version_deprecated(self, integration_name: str, version: str) -> bool:
        """Check if version is deprecated"""
        version_obj = self.get_version(integration_name, version)
        return version_obj.deprecated if version_obj else False
    
    def get_latest_version(self, integration_name: str) -> Optional[str]:
        """Get latest version for integration"""
        versions = self.get_all_versions(integration_name)
        
        if versions:
            # Sort by semantic version
            sorted_versions = sorted(
                versions.keys(),
                key=lambda v: self._parse_version(v),
                reverse=True
            )
            return sorted_versions[0]
        
        return None
    
    def _parse_version(self, version: str) -> tuple:
        """Parse semantic version string"""
        try:
            # Remove 'v' prefix if present
            if version.startswith('v'):
                version = version[1:]
            
            parts = version.split('.')
            return tuple(int(part) for part in parts[:3])
        except ValueError:
            return (0, 0, 0)
    
    def validate_version_format(self, version: str) -> bool:
        """Validate version format"""
        try:
            if version.startswith('v'):
                version = version[1:]
            
            parts = version.split('.')
            if len(parts) < 2 or len(parts) > 4:
                return False
            
            for part in parts[:3]:
                int(part)
            
            return True
        except ValueError:
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get version manager status"""
        return {
            'enabled': self.enabled,
            'total_integrations': len(self.versions),
            'current_versions': self.current_versions,
            'total_versions': sum(len(versions) for versions in self.versions.values()),
            'deprecated_versions': self._get_deprecated_versions_count(),
            'compatibility_rules': sum(len(rules) for rules in self.compatibility_matrix.values()),
            'migration_rules': sum(len(rules) for rules in self.migration_rules.values())
        }
    
    def _get_deprecated_versions_count(self) -> int:
        """Count deprecated versions"""
        count = 0
        for integration_versions in self.versions.values():
            for version in integration_versions.values():
                if version.deprecated:
                    count += 1
        return count
    
    def enable(self):
        """Enable version manager"""
        self.enabled = True
        logger.info("Version manager enabled")
    
    def disable(self):
        """Disable version manager"""
        self.enabled = False
        logger.info("Version manager disabled")
    
    def cleanup_old_versions(self, integration_name: str, keep_count: int = 5):
        """Clean up old versions, keeping only the most recent"""
        versions = self.get_all_versions(integration_name)
        
        if len(versions) <= keep_count:
            return
        
        # Sort by version
        sorted_versions = sorted(
            versions.keys(),
            key=lambda v: self._parse_version(v),
            reverse=True
        )
        
        # Keep only the most recent versions
        versions_to_keep = sorted_versions[:keep_count]
        versions_to_remove = sorted_versions[keep_count:]
        
        for version in versions_to_remove:
            del self.versions[integration_name][version]
            logger.info(f"Removed old version {version} for integration: {integration_name}")


# Global version manager
version_manager = VersionManager()


# Built-in migration functions
def migrate_security_event_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate security event from v1 to v2"""
    migrated = data.copy()
    
    # Rename fields
    if 'event_type' in migrated:
        migrated['type'] = migrated.pop('event_type')
    
    if 'event_timestamp' in migrated:
        migrated['timestamp'] = migrated.pop('event_timestamp')
    
    # Add new fields
    migrated['version'] = '2.0'
    migrated['migrated_at'] = timezone.now().isoformat()
    
    return migrated


def migrate_user_data_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate user data from v1 to v2"""
    migrated = data.copy()
    
    # Flatten nested user object
    if 'user' in migrated and isinstance(migrated['user'], dict):
        user_data = migrated.pop('user')
        migrated.update(user_data)
    
    # Add new fields
    migrated['version'] = '2.0'
    migrated['migrated_at'] = timezone.now().isoformat()
    
    return migrated


def migrate_threat_data_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate threat data from v1 to v2"""
    migrated = data.copy()
    
    # Update threat types
    threat_type_mapping = {
        'malware': 'malicious_software',
        'phishing': 'credential_theft',
        'botnet': 'distributed_attack'
    }
    
    if 'threat_type' in migrated:
        old_type = migrated['threat_type']
        migrated['threat_type'] = threat_type_mapping.get(old_type, old_type)
    
    # Add new fields
    migrated['version'] = '2.0'
    migrated['migrated_at'] = timezone.now().isoformat()
    
    return migrated


# Register built-in migration rules
version_manager.add_migration_rule('security_event', '1.0', '2.0', migrate_security_event_v1_to_v2)
version_manager.add_migration_rule('user_data', '1.0', '2.0', migrate_user_data_v1_to_v2)
version_manager.add_migration_rule('threat_data', '1.0', '2.0', migrate_threat_data_v1_to_v2)


# Create default versions
def create_default_versions():
    """Create default integration versions"""
    
    # Security event versions
    security_event_v1 = IntegrationVersion('1.0', 'Initial security event format')
    security_event_v2 = IntegrationVersion('2.0', 'Enhanced security event format', ['1.0'])
    security_event_v3 = IntegrationVersion('3.0', 'Latest security event format', ['2.0', '1.0'])
    
    version_manager.register_version('security_event', security_event_v1)
    version_manager.register_version('security_event', security_event_v2)
    version_manager.register_version('security_event', security_event_v3)
    version_manager.set_current_version('security_event', '3.0')
    
    # User data versions
    user_data_v1 = IntegrationVersion('1.0', 'Initial user data format')
    user_data_v2 = IntegrationVersion('2.0', 'Enhanced user data format', ['1.0'])
    
    version_manager.register_version('user_data', user_data_v1)
    version_manager.register_version('user_data', user_data_v2)
    version_manager.set_current_version('user_data', '2.0')
    
    # Threat data versions
    threat_data_v1 = IntegrationVersion('1.0', 'Initial threat data format')
    threat_data_v2 = IntegrationVersion('2.0', 'Enhanced threat data format', ['1.0'])
    
    version_manager.register_version('threat_data', threat_data_v1)
    version_manager.register_version('threat_data', threat_data_v2)
    version_manager.set_current_version('threat_data', '2.0')
    
    # Add compatibility rules
    version_manager.add_compatibility_rule('security_event', '1.0', '2.0')
    version_manager.add_compatibility_rule('security_event', '2.0', '3.0')
    version_manager.add_compatibility_rule('security_event', '1.0', '3.0')
    version_manager.add_compatibility_rule('user_data', '1.0', '2.0')
    version_manager.add_compatibility_rule('threat_data', '1.0', '2.0')
    
    # Deprecate old versions
    version_manager.deprecate_version('security_event', '1.0')
    version_manager.deprecate_version('user_data', '1.0')
    version_manager.deprecate_version('threat_data', '1.0')
    
    logger.info("Created default integration versions")


# Initialize default versions
create_default_versions()


# Export symbols
__all__ = [
    'IntegrationVersion',
    'VersionManager',
    'version_manager',
    'migrate_security_event_v1_to_v2',
    'migrate_user_data_v1_to_v2',
    'migrate_threat_data_v1_to_v2',
    'create_default_versions'
]