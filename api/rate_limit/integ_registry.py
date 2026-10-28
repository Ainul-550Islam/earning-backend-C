# api/rate_limit/integ_registry.py
"""
Integration registry for rate limit module.

Provides centralized registration and management of integrations.
"""

import logging
from typing import Dict, Any, List, Optional, Type, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache

from api.rate_limit.integ_adapter import BaseIntegrationAdapter
from api.rate_limit.integ_constants import IntegrationType, IntegrationStatus

logger = logging.getLogger(__name__)


class IntegrationRegistry:
    """
    Registry for managing integration configurations and metadata.
    """
    
    def __init__(self):
        self.integrations: Dict[str, Dict[str, Any]] = {}
        self.adapters: Dict[str, Type[BaseIntegrationAdapter]] = {}
        self.categories: Dict[str, List[str]] = {}
        self.tags: Dict[str, List[str]] = {}
        self.cache_timeout = 300  # 5 minutes
    
    def register_integration(self, integration_id: str, name: str, adapter_class: Type[BaseIntegrationAdapter],
                           description: str = '', integration_type: str = IntegrationType.CUSTOM,
                           default_config: Dict[str, Any] = None, category: str = 'general',
                           tags: List[str] = None, enabled: bool = True):
        """
        Register an integration.
        
        Args:
            integration_id: Unique integration identifier
            name: Human-readable name
            adapter_class: Adapter class
            description: Integration description
            integration_type: Type of integration
            default_config: Default configuration
            category: Integration category
            tags: Integration tags
            enabled: Whether integration is enabled
        """
        integration_info = {
            'id': integration_id,
            'name': name,
            'adapter_class': adapter_class,
            'description': description,
            'type': integration_type,
            'default_config': default_config or {},
            'category': category,
            'tags': tags or [],
            'enabled': enabled,
            'registered_at': timezone.now(),
            'metadata': {}
        }
        
        self.integrations[integration_id] = integration_info
        
        # Update category mapping
        if category not in self.categories:
            self.categories[category] = []
        
        if integration_id not in self.categories[category]:
            self.categories[category].append(integration_id)
        
        # Update tag mapping
        for tag in tags or []:
            if tag not in self.tags:
                self.tags[tag] = []
            
            if integration_id not in self.tags[tag]:
                self.tags[tag].append(integration_id)
        
        # Register adapter class
        self.adapters[integration_id] = adapter_class
        
        # Cache the registration
        cache_key = f"integration_registry:{integration_id}"
        cache.set(cache_key, integration_info, timeout=self.cache_timeout)
        
        logger.info(f"Registered integration: {integration_id} ({name})")
    
    def unregister_integration(self, integration_id: str):
        """
        Unregister an integration.
        
        Args:
            integration_id: Integration identifier
        """
        if integration_id not in self.integrations:
            logger.warning(f"Integration not found for unregistration: {integration_id}")
            return
        
        integration_info = self.integrations[integration_id]
        
        # Remove from category
        category = integration_info['category']
        if category in self.categories and integration_id in self.categories[category]:
            self.categories[category].remove(integration_id)
        
        # Remove from tags
        for tag in integration_info['tags']:
            if tag in self.tags and integration_id in self.tags[tag]:
                self.tags[tag].remove(integration_id)
        
        # Remove from registry
        del self.integrations[integration_id]
        del self.adapters[integration_id]
        
        # Remove from cache
        cache_key = f"integration_registry:{integration_id}"
        cache.delete(cache_key)
        
        logger.info(f"Unregistered integration: {integration_id}")
    
    def register_adapter(self, integration_id: str, adapter_class: Type[BaseIntegrationAdapter]):
        """
        Register an adapter class for an integration.
        
        Args:
            integration_id: Integration identifier
            adapter_class: Adapter class
        """
        self.adapters[integration_id] = adapter_class
        logger.info(f"Registered adapter for {integration_id}")
    
    def unregister_adapter(self, integration_id: str):
        """
        Unregister an adapter class.
        
        Args:
            integration_id: Integration identifier
        """
        if integration_id in self.adapters:
            del self.adapters[integration_id]
            logger.info(f"Unregistered adapter for {integration_id}")
    
    def get_integration(self, integration_id: str) -> Optional[Dict[str, Any]]:
        """
        Get integration information.
        
        Args:
            integration_id: Integration identifier
            
        Returns:
            Integration information or None
        """
        # Try cache first
        cache_key = f"integration_registry:{integration_id}"
        integration_info = cache.get(cache_key)
        
        if integration_info:
            return integration_info
        
        # Fall back to registry
        return self.integrations.get(integration_id)
    
    def get_adapter(self, integration_id: str) -> Optional[Type[BaseIntegrationAdapter]]:
        """
        Get adapter class for integration.
        
        Args:
            integration_id: Integration identifier
            
        Returns:
            Adapter class or None
        """
        return self.adapters.get(integration_id)
    
    def list_integrations(self, category: str = None, integration_type: str = None,
                         tags: List[str] = None, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """
        List integrations with optional filtering.
        
        Args:
            category: Filter by category
            integration_type: Filter by type
            tags: Filter by tags
            enabled_only: Only return enabled integrations
            
        Returns:
            List of integration information
        """
        integrations = []
        
        for integration_id, integration_info in self.integrations.items():
            # Apply filters
            if category and integration_info['category'] != category:
                continue
            
            if integration_type and integration_info['type'] != integration_type:
                continue
            
            if tags and not any(tag in integration_info['tags'] for tag in tags):
                continue
            
            if enabled_only and not integration_info['enabled']:
                continue
            
            integrations.append(integration_info.copy())
        
        return integrations
    
    def get_categories(self) -> Dict[str, List[str]]:
        """
        Get all categories and their integrations.
        
        Returns:
            Category mapping
        """
        return self.categories.copy()
    
    def get_tags(self) -> Dict[str, List[str]]:
        """
        Get all tags and their integrations.
        
        Returns:
            Tag mapping
        """
        return self.tags.copy()
    
    def get_integrations_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get integrations by category.
        
        Args:
            category: Category name
            
        Returns:
            List of integrations in category
        """
        integration_ids = self.categories.get(category, [])
        return [
            self.integrations[int_id].copy()
            for int_id in integration_ids
            if int_id in self.integrations
        ]
    
    def get_integrations_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """
        Get integrations by tag.
        
        Args:
            tag: Tag name
            
        Returns:
            List of integrations with tag
        """
        integration_ids = self.tags.get(tag, [])
        return [
            self.integrations[int_id].copy()
            for int_id in integration_ids
            if int_id in self.integrations
        ]
    
    def search_integrations(self, query: str) -> List[Dict[str, Any]]:
        """
        Search integrations by name or description.
        
        Args:
            query: Search query
            
        Returns:
            List of matching integrations
        """
        query_lower = query.lower()
        results = []
        
        for integration_id, integration_info in self.integrations.items():
            # Search in name
            if query_lower in integration_info['name'].lower():
                results.append(integration_info.copy())
                continue
            
            # Search in description
            if query_lower in integration_info['description'].lower():
                results.append(integration_info.copy())
                continue
            
            # Search in tags
            if any(query_lower in tag.lower() for tag in integration_info['tags']):
                results.append(integration_info.copy())
                continue
        
        return results
    
    def update_integration(self, integration_id: str, **kwargs):
        """
        Update integration information.
        
        Args:
            integration_id: Integration identifier
            **kwargs: Fields to update
        """
        if integration_id not in self.integrations:
            raise ValueError(f"Integration not found: {integration_id}")
        
        integration_info = self.integrations[integration_id]
        
        # Update fields
        for field, value in kwargs.items():
            if field in integration_info:
                integration_info[field] = value
        
        # Update cache
        cache_key = f"integration_registry:{integration_id}"
        cache.set(cache_key, integration_info, timeout=self.cache_timeout)
        
        logger.info(f"Updated integration: {integration_id}")
    
    def enable_integration(self, integration_id: str):
        """
        Enable an integration.
        
        Args:
            integration_id: Integration identifier
        """
        self.update_integration(integration_id, enabled=True)
    
    def disable_integration(self, integration_id: str):
        """
        Disable an integration.
        
        Args:
            integration_id: Integration identifier
        """
        self.update_integration(integration_id, enabled=False)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get registry statistics.
        
        Returns:
            Registry statistics
        """
        total_integrations = len(self.integrations)
        enabled_integrations = len([
            info for info in self.integrations.values()
            if info['enabled']
        ])
        
        # Count by type
        type_counts = {}
        for integration_info in self.integrations.values():
            int_type = integration_info['type']
            type_counts[int_type] = type_counts.get(int_type, 0) + 1
        
        # Count by category
        category_counts = {}
        for category, integration_ids in self.categories.items():
            category_counts[category] = len(integration_ids)
        
        return {
            'total_integrations': total_integrations,
            'enabled_integrations': enabled_integrations,
            'disabled_integrations': total_integrations - enabled_integrations,
            'type_distribution': type_counts,
            'category_distribution': category_counts,
            'total_categories': len(self.categories),
            'total_tags': len(self.tags),
            'registered_adapters': len(self.adapters)
        }
    
    def validate_integration(self, integration_id: str) -> Dict[str, Any]:
        """
        Validate an integration configuration.
        
        Args:
            integration_id: Integration identifier
            
        Returns:
            Validation result
        """
        try:
            integration_info = self.get_integration(integration_id)
            
            if not integration_info:
                return {
                    'valid': False,
                    'errors': [f'Integration not found: {integration_id}']
                }
            
            errors = []
            warnings = []
            
            # Check required fields
            required_fields = ['id', 'name', 'adapter_class', 'type']
            for field in required_fields:
                if not integration_info.get(field):
                    errors.append(f'Missing required field: {field}')
            
            # Check adapter class
            adapter_class = integration_info.get('adapter_class')
            if adapter_class and not issubclass(adapter_class, BaseIntegrationAdapter):
                errors.append('Adapter class must inherit from BaseIntegrationAdapter')
            
            # Check configuration
            default_config = integration_info.get('default_config', {})
            if not isinstance(default_config, dict):
                errors.append('Default configuration must be a dictionary')
            
            # Check type
            int_type = integration_info.get('type')
            valid_types = [IntegrationType.WEBHOOK, IntegrationType.API, IntegrationType.DATABASE,
                          IntegrationType.MESSAGE_QUEUE, IntegrationType.EMAIL, IntegrationType.SLACK,
                          IntegrationType.CUSTOM]
            
            if int_type not in valid_types:
                warnings.append(f'Unknown integration type: {int_type}')
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings,
                'integration_id': integration_id
            }
            
        except Exception as e:
            return {
                'valid': False,
                'errors': [f'Validation failed: {str(e)}']
            }
    
    def export_registry(self, include_config: bool = False) -> Dict[str, Any]:
        """
        Export registry data.
        
        Args:
            include_config: Whether to include configuration
            
        Returns:
            Export data
        """
        export_data = {
            'export_metadata': {
                'exported_at': timezone.now().isoformat(),
                'total_integrations': len(self.integrations),
                'include_config': include_config
            },
            'integrations': {}
        }
        
        for integration_id, integration_info in self.integrations.items():
            export_info = {
                'id': integration_info['id'],
                'name': integration_info['name'],
                'description': integration_info['description'],
                'type': integration_info['type'],
                'category': integration_info['category'],
                'tags': integration_info['tags'],
                'enabled': integration_info['enabled'],
                'registered_at': integration_info['registered_at'].isoformat()
            }
            
            if include_config:
                export_info['default_config'] = integration_info['default_config']
            
            export_data['integrations'][integration_id] = export_info
        
        return export_data
    
    def import_registry(self, data: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
        """
        Import registry data.
        
        Args:
            data: Import data
            overwrite: Whether to overwrite existing integrations
            
        Returns:
            Import result
        """
        try:
            imported_count = 0
            skipped_count = 0
            errors = []
            
            integrations_data = data.get('integrations', {})
            
            for integration_id, integration_info in integrations_data.items():
                try:
                    # Check if integration already exists
                    if integration_id in self.integrations and not overwrite:
                        skipped_count += 1
                        continue
                    
                    # Reconstruct adapter class (this is simplified)
                    # In a real implementation, you'd need to reconstruct the actual class
                    adapter_class = BaseIntegrationAdapter  # Placeholder
                    
                    # Register integration
                    self.register_integration(
                        integration_id=integration_id,
                        name=integration_info['name'],
                        adapter_class=adapter_class,
                        description=integration_info.get('description', ''),
                        integration_type=integration_info.get('type', IntegrationType.CUSTOM),
                        default_config=integration_info.get('default_config', {}),
                        category=integration_info.get('category', 'imported'),
                        tags=integration_info.get('tags', []),
                        enabled=integration_info.get('enabled', True)
                    )
                    
                    imported_count += 1
                    
                except Exception as e:
                    errors.append(f"Failed to import {integration_id}: {str(e)}")
            
            return {
                'success': True,
                'imported_count': imported_count,
                'skipped_count': skipped_count,
                'errors': errors
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def clear_cache(self):
        """Clear registry cache."""
        cache_keys = cache.keys("integration_registry:*")
        for key in cache_keys:
            cache.delete(key)
        
        logger.info("Cleared integration registry cache")


# Global registry instance
integration_registry = IntegrationRegistry()


# Export classes and functions
__all__ = [
    'IntegrationRegistry',
    'integration_registry'
]
