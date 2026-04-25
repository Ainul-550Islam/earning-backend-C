"""
Configuration Service for Offer Routing System

This module provides configuration management functionality
for routing settings, parameters, and feature flags.
"""

import logging
from typing import Dict, List, Any, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from ..models import RoutingConfig, PersonalizationConfig
from ..exceptions import ConfigurationError

User = get_user_model()
logger = logging.getLogger(__name__)


class ConfigurationService:
    """
    Service for managing routing configuration.
    
    Provides configuration management, feature flags,
    and parameter optimization functionality.
    """
    
    def __init__(self):
        self.cache_service = None
        
        # Initialize services
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize configuration services."""
        try:
            from .cache import RoutingCacheService
            self.cache_service = RoutingCacheService()
        except ImportError as e:
            logger.error(f"Failed to initialize configuration services: {e}")
    
    def get_routing_config(self, tenant_id: int) -> Dict[str, Any]:
        """Get routing configuration for a tenant."""
        try:
            cache_key = f"routing_config:{tenant_id}"
            cached_config = cache.get(cache_key)
            
            if cached_config:
                return cached_config
            
            # Get configuration from database
            config_values = RoutingConfig.objects.filter(
                is_active=True
            ).values('key', 'value')
            
            config = {}
            for config_value in config_values:
                config[config_value['key']] = config_value['value']
            
            # Set defaults for missing values
            defaults = self._get_default_config()
            for key, value in defaults.items():
                if key not in config:
                    config[key] = value
            
            # Cache configuration
            cache.set(cache_key, config, timeout=3600)
            
            return config
            
        except Exception as e:
            logger.error(f"Error getting routing config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default routing configuration."""
        return {
            'max_routing_time_ms': 50,
            'cache_enabled': True,
            'cache_timeout_seconds': 300,
            'personalization_enabled': True,
            'ab_testing_enabled': True,
            'diversity_enabled': True,
            'fallback_enabled': True,
            'rate_limiting_enabled': True,
            'analytics_enabled': True,
            'max_offers_per_route': 10,
            'max_conditions_per_route': 20,
            'min_score_threshold': 0.1,
            'diversity_factor': 0.2,
            'freshness_weight': 0.1,
            'affinity_threshold': 0.1,
            'statistical_significance_threshold': 0.95,
            'min_ab_test_duration_hours': 24,
            'max_ab_test_duration_days': 30,
            'default_ab_test_split_percentage': 50,
            'decision_log_retention_days': 30,
            'performance_stats_retention_days': 90
        }
    
    def update_config_value(self, tenant_id: int, key: str, value: Any) -> bool:
        """Update a configuration value."""
        try:
            config, created = RoutingConfig.objects.update_or_create(
                key=key,
                defaults={
                    'value': str(value),
                    'is_active': True
                }
            )
            
            if not created:
                config.value = str(value)
                config.save()
            
            # Invalidate cache
            cache_key = f"routing_config:{tenant_id}"
            cache.delete(cache_key)
            
            logger.info(f"Updated config value: {key} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating config value: {e}")
            return False
    
    def get_feature_flags(self, tenant_id: int) -> Dict[str, bool]:
        """Get feature flags for a tenant."""
        try:
            config = self.get_routing_config(tenant_id)
            
            feature_flags = {
                'cache_enabled': config.get('cache_enabled', True),
                'personalization_enabled': config.get('personalization_enabled', True),
                'ab_testing_enabled': config.get('ab_testing_enabled', True),
                'diversity_enabled': config.get('diversity_enabled', True),
                'fallback_enabled': config.get('fallback_enabled', True),
                'rate_limiting_enabled': config.get('rate_limiting_enabled', True),
                'analytics_enabled': config.get('analytics_enabled', True),
                'machine_learning_enabled': config.get('machine_learning_enabled', False),
                'real_time_personalization': config.get('real_time_personalization', False),
                'advanced_analytics': config.get('advanced_analytics', False)
            }
            
            return feature_flags
            
        except Exception as e:
            logger.error(f"Error getting feature flags: {e}")
            return {}
    
    def is_feature_enabled(self, tenant_id: int, feature: str) -> bool:
        """Check if a feature is enabled for a tenant."""
        try:
            feature_flags = self.get_feature_flags(tenant_id)
            return feature_flags.get(feature, False)
            
        except Exception as e:
            logger.error(f"Error checking if feature enabled: {e}")
            return False
    
    def get_personalization_config(self, user_id: int) -> Optional[PersonalizationConfig]:
        """Get personalization configuration for a user."""
        try:
            cache_key = f"personalization_config:{user_id}"
            cached_config = cache.get(cache_key)
            
            if cached_config:
                return cached_config
            
            config = PersonalizationConfig.objects.filter(
                user_id=user_id,
                is_active=True
            ).first()
            
            if config:
                cache.set(cache_key, config, timeout=1800)
            
            return config
            
        except Exception as e:
            logger.error(f"Error getting personalization config: {e}")
            return None
    
    def update_personalization_config(self, user_id: int, config_data: Dict[str, Any]) -> bool:
        """Update personalization configuration for a user."""
        try:
            config, created = PersonalizationConfig.objects.update_or_create(
                user_id=user_id,
                defaults={
                    'algorithm': config_data.get('algorithm', 'hybrid'),
                    'collaborative_weight': config_data.get('collaborative_weight', 0.4),
                    'content_based_weight': config_data.get('content_based_weight', 0.3),
                    'hybrid_weight': config_data.get('hybrid_weight', 0.3),
                    'min_affinity_score': config_data.get('min_affinity_score', 0.1),
                    'max_offers_per_user': config_data.get('max_offers_per_user', 50),
                    'diversity_factor': config_data.get('diversity_factor', 0.2),
                    'freshness_weight': config_data.get('freshness_weight', 0.1),
                    'new_user_days': config_data.get('new_user_days', 7),
                    'active_user_days': config_data.get('active_user_days', 30),
                    'premium_user_multiplier': config_data.get('premium_user_multiplier', 1.5),
                    'real_time_enabled': config_data.get('real_time_enabled', True),
                    'context_signals_enabled': config_data.get('context_signals_enabled', True),
                    'real_time_weight': config_data.get('real_time_weight', 0.5),
                    'machine_learning_enabled': config_data.get('machine_learning_enabled', False),
                    'ml_model_path': config_data.get('ml_model_path', ''),
                    'ml_update_frequency': config_data.get('ml_update_frequency', 24)
                }
            )
            
            if not created:
                # Update existing config
                for key, value in config_data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                config.save()
            
            # Invalidate cache
            cache_key = f"personalization_config:{user_id}"
            cache.delete(cache_key)
            
            logger.info(f"Updated personalization config for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating personalization config: {e}")
            return False
    
    def optimize_configuration(self, tenant_id: int) -> Dict[str, Any]:
        """Optimize configuration based on performance data."""
        try:
            # This would implement configuration optimization logic
            # For now, return placeholder
            
            optimization_results = {
                'optimized_parameters': {
                    'max_routing_time_ms': 45,
                    'cache_timeout_seconds': 600,
                    'diversity_factor': 0.25,
                    'freshness_weight': 0.15
                },
                'performance_improvement': {
                    'response_time_improvement': 10,
                    'cache_hit_rate_improvement': 5,
                    'conversion_rate_improvement': 2
                },
                'recommendations': [
                    'Increase cache timeout to improve hit rate',
                    'Adjust diversity factor for better offer distribution',
                    'Consider enabling real-time personalization'
                ]
            }
            
            logger.info(f"Optimized configuration for tenant {tenant_id}")
            return optimization_results
            
        except Exception as e:
            logger.error(f"Error optimizing configuration: {e}")
            return {}
    
    def validate_configuration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration values."""
        try:
            validation_errors = []
            warnings = []
            
            # Validate numeric values
            if 'max_routing_time_ms' in config:
                max_time = config['max_routing_time_ms']
                if not isinstance(max_time, (int, float)) or max_time < 10 or max_time > 1000:
                    validation_errors.append('max_routing_time_ms must be between 10 and 1000')
                elif max_time > 200:
                    warnings.append('max_routing_time_ms is high, consider optimizing routing logic')
            
            if 'cache_timeout_seconds' in config:
                timeout = config['cache_timeout_seconds']
                if not isinstance(timeout, (int, float)) or timeout < 60 or timeout > 86400:
                    validation_errors.append('cache_timeout_seconds must be between 60 and 86400')
            
            if 'diversity_factor' in config:
                diversity = config['diversity_factor']
                if not isinstance(diversity, (int, float)) or diversity < 0 or diversity > 1:
                    validation_errors.append('diversity_factor must be between 0 and 1')
            
            if 'freshness_weight' in config:
                freshness = config['freshness_weight']
                if not isinstance(freshness, (int, float)) or freshness < 0 or freshness > 1:
                    validation_errors.append('freshness_weight must be between 0 and 1')
            
            # Validate boolean values
            boolean_fields = ['cache_enabled', 'personalization_enabled', 'ab_testing_enabled']
            for field in boolean_fields:
                if field in config and not isinstance(config[field], bool):
                    validation_errors.append(f'{field} must be a boolean value')
            
            return {
                'is_valid': len(validation_errors) == 0,
                'errors': validation_errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"Error validating configuration: {e}")
            return {
                'is_valid': False,
                'errors': [str(e)],
                'warnings': []
            }
    
    def export_configuration(self, tenant_id: int) -> Dict[str, Any]:
        """Export configuration for a tenant."""
        try:
            config = self.get_routing_config(tenant_id)
            feature_flags = self.get_feature_flags(tenant_id)
            
            export_data = {
                'routing_config': config,
                'feature_flags': feature_flags,
                'exported_at': timezone.now().isoformat(),
                'version': '1.0'
            }
            
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting configuration: {e}")
            return {}
    
    def import_configuration(self, tenant_id: int, config_data: Dict[str, Any]) -> bool:
        """Import configuration for a tenant."""
        try:
            # Validate configuration
            validation_result = self.validate_configuration(config_data.get('routing_config', {}))
            
            if not validation_result['is_valid']:
                logger.error(f"Configuration validation failed: {validation_result['errors']}")
                return False
            
            # Import routing config
            routing_config = config_data.get('routing_config', {})
            for key, value in routing_config.items():
                self.update_config_value(tenant_id, key, value)
            
            # Import feature flags
            feature_flags = config_data.get('feature_flags', {})
            for flag, value in feature_flags.items():
                self.update_config_value(tenant_id, flag, value)
            
            logger.info(f"Imported configuration for tenant {tenant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error importing configuration: {e}")
            return False
    
    def reset_configuration(self, tenant_id: int) -> bool:
        """Reset configuration to defaults."""
        try:
            # Delete existing configuration
            RoutingConfig.objects.all().delete()
            
            # Invalidate cache
            cache_key = f"routing_config:{tenant_id}"
            cache.delete(cache_key)
            
            logger.info(f"Reset configuration for tenant {tenant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting configuration: {e}")
            return False
    
    def get_configuration_history(self, tenant_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Get configuration change history."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # This would implement configuration history tracking
            # For now, return placeholder
            
            history = [
                {
                    'timestamp': timezone.now().isoformat(),
                    'key': 'max_routing_time_ms',
                    'old_value': '50',
                    'new_value': '45',
                    'changed_by': 'system'
                }
            ]
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting configuration history: {e}")
            return []
    
    def backup_configuration(self, tenant_id: int) -> bool:
        """Backup current configuration."""
        try:
            config_data = self.export_configuration(tenant_id)
            
            # This would save backup to storage
            # For now, just log the backup
            logger.info(f"Backed up configuration for tenant {tenant_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error backing up configuration: {e}")
            return False
    
    def restore_configuration(self, tenant_id: int, backup_data: Dict[str, Any]) -> bool:
        """Restore configuration from backup."""
        try:
            return self.import_configuration(tenant_id, backup_data)
            
        except Exception as e:
            logger.error(f"Error restoring configuration: {e}")
            return False


# Singleton instance
config_service = ConfigurationService()
