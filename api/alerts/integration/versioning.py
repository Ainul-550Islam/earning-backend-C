"""
Integration Versioning - Version management for integration system
Provides safe versioning with existing alerts architecture
"""
import logging
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone
from django.utils import timezone as django_tz
from django.core.cache import cache
from django.db import models

# Absolute imports to prevent ModuleNotFoundError
from api.alerts.models import AlertLog, AlertRule, Notification, IntegrationVersion
from api.alerts.validators import validate_alert_rule_condition, validate_threshold_value
from api.alerts.integration.integ_constants import (
    CACHE_KEYS,
    CACHE_TIMEOUTS
)

logger = logging.getLogger(__name__)


class IntegrationVersionManager:
    """
    Manages integration versions with safe architectural integration
    """
    
    def __init__(self):
        self._versions = {}
        self._loaded = False

    @property
    def versions(self):
        """In-memory version cache, loaded from the database on first use (never at import)."""
        if not self._loaded:
            self._loaded = True
            self._load_versions_from_db()
        return self._versions

    @versions.setter
    def versions(self, value):
        self._versions = value
    
    def _load_versions_from_db(self):
        """
        Load versions from database
        """
        try:
            versions = IntegrationVersion.objects.filter(is_active=True)
            
            for version in versions:
                self.versions[version.integration_id] = {
                    'version': version.version,
                    'config_hash': version.config_hash,
                    'created_at': version.created_at.isoformat(),
                    'updated_at': version.updated_at.isoformat()
                }
            
            logger.info(f"Loaded {len(self.versions)} integration versions")
            
        except Exception as e:
            logger.error(f"Error loading versions from database: {e}")
    
    def create_version(self, integration_id: str, config: Dict[str, Any], 
                      version: str = None) -> str:
        """
        Create new integration version
        Validates configuration using existing validators
        """
        try:
            # Validate configuration
            validation_result = self._validate_config(config)
            if not validation_result['valid']:
                raise ValueError(f"Invalid configuration: {validation_result['errors']}")
            
            # Generate version if not provided
            if not version:
                version = self._generate_version()
            
            # Generate config hash
            config_hash = self._generate_config_hash(config)
            
            # Check if a version already exists - query the DATABASE, not just the
            # in-memory cache. self.versions is only populated at process start
            # (_load_versions_from_db) and via prior create/rollback calls in THIS
            # process, so a fresh worker/process would see an empty dict here even
            # though a row already exists in the DB, and fall through to
            # .objects.create() below - which raises IntegrityError against the
            # unique constraint. Checking the DB directly is authoritative across
            # processes and restarts.
            existing_version = IntegrationVersion.objects.filter(
                integration_id=integration_id, is_active=True
            ).order_by('-created_at').first()

            if existing_version and existing_version.config_hash == config_hash:
                logger.info(f"Version {existing_version.version} already exists for {integration_id}")
                # Keep memory cache in sync even on the short-circuit path
                self.versions[integration_id] = {
                    'version': existing_version.version,
                    'config_hash': existing_version.config_hash,
                    'created_at': existing_version.created_at.isoformat(),
                    'updated_at': existing_version.updated_at.isoformat()
                }
                return existing_version.version

            # Config actually changed (or no active version yet). If there's a
            # currently active version, deactivate it first so create_version()
            # alone - not just update_version() - keeps "one active version per
            # integration" consistent, and history/rollback/cleanup keep working.
            if existing_version:
                IntegrationVersion.objects.filter(
                    integration_id=integration_id, is_active=True
                ).update(is_active=False)

            # Create version record
            integration_version = IntegrationVersion.objects.create(
                integration_id=integration_id,
                version=version,
                config_hash=config_hash
            )
            
            # Update memory cache
            self.versions[integration_id] = {
                'version': version,
                'config_hash': config_hash,
                'created_at': integration_version.created_at.isoformat(),
                'updated_at': integration_version.updated_at.isoformat()
            }
            
            # Cache version data
            cache.set(f"integration_version:{integration_id}", {
                'version': version,
                'config_hash': config_hash
            }, timeout=CACHE_TIMEOUTS['integration'])
            
            logger.info(f"Created version {version} for {integration_id}")
            return version
            
        except Exception as e:
            logger.error(f"Error creating version for {integration_id}: {e}")
            raise
    
    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate configuration using existing validators
        """
        try:
            errors = []
            
            # Validate webhook configuration if present
            if 'webhook_url' in config:
                from api.alerts.validators import validate_webhook_url
                webhook_validation = validate_webhook_url(config['webhook_url'])
                if not webhook_validation['valid']:
                    errors.extend(webhook_validation['errors'])
            
            # Validate channel configuration if present
            if 'channel_config' in config and 'channel_type' in config:
                from api.alerts.validators import validate_channel_config
                config_validation = validate_channel_config(config['channel_config'], config['channel_type'])
                if not config_validation['valid']:
                    errors.extend(config_validation['errors'])
            
            # Validate threshold if present
            if 'threshold' in config:
                threshold_validation = validate_threshold_value(config['threshold'])
                if not threshold_validation['valid']:
                    errors.extend(threshold_validation['errors'])
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating config: {e}")
            return {
                'valid': False,
                'errors': ['Validation error']
            }
    
    def _generate_version(self) -> str:
        """
        Generate version string
        """
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _generate_config_hash(self, config: Dict[str, Any]) -> str:
        """
        Generate SHA-256 hash of configuration
        """
        import hashlib
        
        # Create canonical representation
        config_string = json.dumps(config, sort_keys=True, separators=(',', ':'))
        
        # Generate SHA-256 hash
        return hashlib.sha256(config_string.encode('utf-8')).hexdigest()
    
    def get_version(self, integration_id: str) -> Optional[Dict[str, Any]]:
        """
        Get version information for integration
        """
        try:
            # Try cache first
            cached_data = cache.get(f"integration_version:{integration_id}")
            if cached_data:
                return cached_data
            
            # Fallback to memory
            return self.versions.get(integration_id)
            
        except Exception as e:
            logger.error(f"Error getting version for {integration_id}: {e}")
            return None
    
    def update_version(self, integration_id: str, config: Dict[str, Any], 
                      version: str = None) -> str:
        """
        Update integration version
        """
        try:
            # Deactivate old version
            IntegrationVersion.objects.filter(
                integration_id=integration_id,
                is_active=True
            ).update(is_active=False)
            
            # Create new version
            new_version = self.create_version(integration_id, config, version)
            
            logger.info(f"Updated {integration_id} to version {new_version}")
            return new_version
            
        except Exception as e:
            logger.error(f"Error updating version for {integration_id}: {e}")
            raise
    
    def delete_version(self, integration_id: str) -> bool:
        """
        Delete integration version
        """
        try:
            # Deactivate version
            IntegrationVersion.objects.filter(
                integration_id=integration_id
            ).update(is_active=False)
            
            # Remove from memory
            if integration_id in self.versions:
                del self.versions[integration_id]
            
            # Remove from cache
            cache.delete(f"integration_version:{integration_id}")
            
            logger.info(f"Deleted version for {integration_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting version for {integration_id}: {e}")
            return False
    
    def compare_versions(self, integration_id: str, config1: Dict[str, Any], 
                        config2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare two configurations
        """
        try:
            hash1 = self._generate_config_hash(config1)
            hash2 = self._generate_config_hash(config2)
            
            if hash1 == hash2:
                return {
                    'identical': True,
                    'hash1': hash1,
                    'hash2': hash2
                }
            else:
                return {
                    'identical': False,
                    'hash1': hash1,
                    'hash2': hash2,
                    'differences': self._find_differences(config1, config2)
                }
                
        except Exception as e:
            logger.error(f"Error comparing versions: {e}")
            return {
                'identical': False,
                'error': 'Operation failed'
            }
    
    def _find_differences(self, config1: Dict[str, Any], config2: Dict[str, Any]) -> List[str]:
        """
        Find differences between two configurations
        """
        differences = []
        
        # Check keys in config1 but not in config2
        for key in config1:
            if key not in config2:
                differences.append(f"Key '{key}' removed")
            elif config1[key] != config2[key]:
                differences.append(f"Key '{key}' changed from {config1[key]} to {config2[key]}")
        
        # Check keys in config2 but not in config1
        for key in config2:
            if key not in config1:
                differences.append(f"Key '{key}' added")
        
        return differences
    
    def get_version_history(self, integration_id: str) -> List[Dict[str, Any]]:
        """
        Get version history for integration
        """
        try:
            versions = IntegrationVersion.objects.filter(
                integration_id=integration_id
            ).order_by('-created_at')
            
            history = []
            for version in versions:
                history.append({
                    'version': version.version,
                    'config_hash': version.config_hash,
                    'created_at': version.created_at.isoformat(),
                    'updated_at': version.updated_at.isoformat(),
                    'is_active': version.is_active
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting version history for {integration_id}: {e}")
            return []
    
    def rollback_version(self, integration_id: str, target_version: str) -> bool:
        """
        Rollback to specific version
        """
        try:
            # Find target version
            target_version_obj = IntegrationVersion.objects.filter(
                integration_id=integration_id,
                version=target_version
            ).first()
            
            if not target_version_obj:
                logger.error(f"Version {target_version} not found for {integration_id}")
                return False
            
            # Deactivate current version
            IntegrationVersion.objects.filter(
                integration_id=integration_id,
                is_active=True
            ).update(is_active=False)
            
            # Activate target version
            target_version_obj.is_active = True
            target_version_obj.save()
            
            # Update memory cache
            self.versions[integration_id] = {
                'version': target_version,
                'config_hash': target_version_obj.config_hash,
                'created_at': target_version_obj.created_at.isoformat(),
                'updated_at': target_version_obj.updated_at.isoformat()
            }
            
            logger.info(f"Rolled back {integration_id} to version {target_version}")
            return True
            
        except Exception as e:
            logger.error(f"Error rolling back {integration_id} to {target_version}: {e}")
            return False
    
    def cleanup_old_versions(self, keep_count: int = 5) -> int:
        """
        Cleanup old versions, keeping only the most recent ones
        """
        try:
            # Get all integration IDs
            integration_ids = IntegrationVersion.objects.values_list(
                'integration_id', flat=True
            ).distinct()
            
            cleaned_count = 0
            
            for integration_id in integration_ids:
                # Get versions for this integration
                versions = IntegrationVersion.objects.filter(
                    integration_id=integration_id
                ).order_by('-created_at')
                
                # Keep only the most recent versions
                if versions.count() > keep_count:
                    old_versions = versions[keep_count:]
                    deleted_count = old_versions.count()
                    
                    # Delete old versions
                    old_versions.delete()
                    cleaned_count += deleted_count
            
            logger.info(f"Cleaned up {cleaned_count} old versions")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old versions: {e}")
            return 0
    
    def get_version_statistics(self) -> Dict[str, Any]:
        """
        Get version statistics
        """
        try:
            total_versions = IntegrationVersion.objects.count()
            active_versions = IntegrationVersion.objects.filter(is_active=True).count()
            unique_integrations = IntegrationVersion.objects.values_list(
                'integration_id', flat=True
            ).distinct().count()
            
            return {
                'total_versions': total_versions,
                'active_versions': active_versions,
                'unique_integrations': unique_integrations,
                'memory_cache_size': len(self.versions),
                'timestamp': django_tz.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting version statistics: {e}")
            return {
                'error': 'Operation failed',
                'timestamp': django_tz.now().isoformat()
            }


# Global version manager instance
integration_version_manager = IntegrationVersionManager()


# Utility functions
def create_integration_version(integration_id: str, config: Dict[str, Any], 
                             version: str = None) -> str:
    """
    Create integration version
    """
    return integration_version_manager.create_version(integration_id, config, version)


def get_integration_version(integration_id: str) -> Optional[Dict[str, Any]]:
    """
    Get integration version
    """
    return integration_version_manager.get_version(integration_id)


def update_integration_version(integration_id: str, config: Dict[str, Any], 
                             version: str = None) -> str:
    """
    Update integration version
    """
    return integration_version_manager.update_version(integration_id, config, version)


def rollback_integration_version(integration_id: str, target_version: str) -> bool:
    """
    Rollback integration version
    """
    return integration_version_manager.rollback_version(integration_id, target_version)


def get_version_statistics() -> Dict[str, Any]:
    """
    Get version statistics
    """
    return integration_version_manager.get_version_statistics()
