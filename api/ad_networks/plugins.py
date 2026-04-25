"""
api/ad_networks/plugins.py
Plugin system for ad networks module
SaaS-ready with tenant support
"""

import logging
import importlib
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
import json

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class PluginType(Enum):
    """Plugin types for ad networks"""
    
    # Network plugins
    NETWORK_SYNC = "network_sync"
    NETWORK_HEALTH = "network_health"
    NETWORK_ANALYTICS = "network_analytics"
    
    # Offer plugins
    OFFER_VALIDATION = "offer_validation"
    OFFER_PROCESSING = "offer_processing"
    OFFER_ANALYTICS = "offer_analytics"
    
    # Conversion plugins
    CONVERSION_VALIDATION = "conversion_validation"
    CONVERSION_PROCESSING = "conversion_processing"
    CONVERSION_ANALYTICS = "conversion_analytics"
    
    # Fraud plugins
    FRAUD_DETECTION = "fraud_detection"
    FRAUD_ANALYSIS = "fraud_analysis"
    FRAUD_PREVENTION = "fraud_prevention"
    
    # Reward plugins
    REWARD_CALCULATION = "reward_calculation"
    REWARD_PROCESSING = "reward_processing"
    REWARD_ANALYTICS = "reward_analytics"
    
    # User plugins
    USER_ANALYTICS = "user_analytics"
    USER_SEGMENTATION = "user_segmentation"
    USER_PERSONALIZATION = "user_personalization"
    
    # Integration plugins
    WEBHOOK_PROCESSING = "webhook_processing"
    API_INTEGRATION = "api_integration"
    DATA_EXPORT = "data_export"
    
    # System plugins
    CACHE_MANAGEMENT = "cache_management"
    LOG_PROCESSING = "log_processing"
    NOTIFICATION_HANDLING = "notification_handling"


class PluginStatus(Enum):
    """Plugin status"""
    
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DISABLED = "disabled"


class Plugin(ABC):
    """Abstract base class for plugins"""
    
    def __init__(self, name: str, version: str, description: str = ""):
        self.name = name
        self.version = version
        self.description = description
        self.status = PluginStatus.INACTIVE
        self.enabled = True
        self.config = {}
        self.last_error = None
        self.init_time = None
        self.execution_count = 0
        self.total_execution_time = 0
        self.id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Generate unique plugin ID"""
        import uuid
        return str(uuid.uuid4())
    
    @abstractmethod
    def get_plugin_type(self) -> PluginType:
        """Get plugin type"""
        pass
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any] = None) -> bool:
        """Initialize plugin"""
        pass
    
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute plugin logic"""
        pass
    
    @abstractmethod
    def cleanup(self) -> bool:
        """Cleanup plugin resources"""
        pass
    
    def enable(self) -> bool:
        """Enable plugin"""
        self.enabled = True
        return True
    
    def disable(self) -> bool:
        """Disable plugin"""
        self.enabled = False
        return True
    
    def get_status(self) -> PluginStatus:
        """Get plugin status"""
        return self.status
    
    def get_config(self) -> Dict[str, Any]:
        """Get plugin configuration"""
        return self.config
    
    def update_config(self, config: Dict[str, Any]) -> bool:
        """Update plugin configuration"""
        try:
            self.config.update(config)
            return True
        except Exception as e:
            logger.error(f"Error updating config for plugin {self.name}: {str(e)}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get plugin statistics"""
        return {
            'id': self.id,
            'name': self.name,
            'version': self.version,
            'type': self.get_plugin_type().value,
            'status': self.status.value,
            'enabled': self.enabled,
            'execution_count': self.execution_count,
            'total_execution_time': self.total_execution_time,
            'average_execution_time': (
                self.total_execution_time / self.execution_count 
                if self.execution_count > 0 else 0
            ),
            'last_error': self.last_error,
            'init_time': self.init_time.isoformat() if self.init_time else None
        }
    
    def _execute_with_timing(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute plugin with timing"""
        import time
        
        start_time = time.time()
        
        try:
            result = self.execute(context)
            self.status = PluginStatus.ACTIVE
            self.last_error = None
            
        except Exception as e:
            logger.error(f"Error executing plugin {self.name}: {str(e)}")
            self.status = PluginStatus.ERROR
            self.last_error = str(e)
            result = {
                'success': False,
                'error': str(e),
                'plugin': self.name
            }
        
        # Update stats
        execution_time = time.time() - start_time
        self.execution_count += 1
        self.total_execution_time += execution_time
        
        # Add timing to result
        if isinstance(result, dict):
            result['execution_time'] = execution_time
            result['plugin'] = self.name
        
        return result


class NetworkSyncPlugin(Plugin):
    """Base class for network sync plugins"""
    
    def get_plugin_type(self) -> PluginType:
        return PluginType.NETWORK_SYNC
    
    @abstractmethod
    def sync_offers(self, network_config: Dict[str, Any]) -> Dict[str, Any]:
        """Sync offers from network"""
        pass
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute network sync"""
        network_config = context.get('network_config', {})
        return self.sync_offers(network_config)


class FraudDetectionPlugin(Plugin):
    """Base class for fraud detection plugins"""
    
    def get_plugin_type(self) -> PluginType:
        return PluginType.FRAUD_DETECTION
    
    @abstractmethod
    def analyze_fraud(self, conversion_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze for fraud"""
        pass
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute fraud analysis"""
        conversion_data = context.get('conversion_data', {})
        return self.analyze_fraud(conversion_data)


class RewardCalculationPlugin(Plugin):
    """Base class for reward calculation plugins"""
    
    def get_plugin_type(self) -> PluginType:
        return PluginType.REWARD_CALCULATION
    
    @abstractmethod
    def calculate_reward(self, offer_data: Dict[str, Any], 
                        user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate reward amount"""
        pass
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute reward calculation"""
        offer_data = context.get('offer_data', {})
        user_data = context.get('user_data', {})
        return self.calculate_reward(offer_data, user_data)


class PluginManager:
    """Manager for plugins"""
    
    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}
        self.plugin_types: Dict[PluginType, List[Plugin]] = {}
        self.plugin_directory = getattr(settings, 'AD_NETWORKS_PLUGIN_DIR', 'ad_networks/plugins')
        self.config_cache_key = 'ad_networks_plugin_configs'
        self.enabled_plugins_cache_key = 'ad_networks_enabled_plugins'
    
    def register_plugin(self, plugin: Plugin) -> bool:
        """Register a plugin"""
        try:
            if plugin.name in self.plugins:
                logger.warning(f"Plugin {plugin.name} already registered")
                return False
            
            # Register plugin
            self.plugins[plugin.name] = plugin
            
            # Register by type
            plugin_type = plugin.get_plugin_type()
            if plugin_type not in self.plugin_types:
                self.plugin_types[plugin_type] = []
            self.plugin_types[plugin_type].append(plugin)
            
            logger.info(f"Registered plugin {plugin.name} ({plugin_type.value})")
            return True
            
        except Exception as e:
            logger.error(f"Error registering plugin {plugin.name}: {str(e)}")
            return False
    
    def unregister_plugin(self, plugin_name: str) -> bool:
        """Unregister a plugin"""
        try:
            if plugin_name not in self.plugins:
                logger.warning(f"Plugin {plugin_name} not found")
                return False
            
            plugin = self.plugins[plugin_name]
            
            # Cleanup plugin
            plugin.cleanup()
            
            # Remove from type registry
            plugin_type = plugin.get_plugin_type()
            if plugin_type in self.plugin_types:
                self.plugin_types[plugin_type].remove(plugin)
            
            # Remove from main registry
            del self.plugins[plugin_name]
            
            logger.info(f"Unregistered plugin {plugin_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error unregistering plugin {plugin_name}: {str(e)}")
            return False
    
    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """Get plugin by name"""
        return self.plugins.get(plugin_name)
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> List[Plugin]:
        """Get plugins by type"""
        return self.plugin_types.get(plugin_type, [])
    
    def get_enabled_plugins(self) -> List[Plugin]:
        """Get all enabled plugins"""
        return [plugin for plugin in self.plugins.values() if plugin.enabled]
    
    def get_active_plugins(self) -> List[Plugin]:
        """Get all active plugins"""
        return [plugin for plugin in self.plugins.values() if plugin.status == PluginStatus.ACTIVE]
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a plugin"""
        plugin = self.get_plugin(plugin_name)
        if plugin:
            return plugin.enable()
        return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a plugin"""
        plugin = self.get_plugin(plugin_name)
        if plugin:
            return plugin.disable()
        return False
    
    def initialize_plugin(self, plugin_name: str, config: Dict[str, Any] = None) -> bool:
        """Initialize a plugin"""
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            logger.error(f"Plugin {plugin_name} not found")
            return False
        
        try:
            success = plugin.initialize(config)
            if success:
                plugin.init_time = timezone.now()
                plugin.status = PluginStatus.ACTIVE
                logger.info(f"Initialized plugin {plugin_name}")
            else:
                plugin.status = PluginStatus.ERROR
                plugin.last_error = "Initialization failed"
                logger.error(f"Failed to initialize plugin {plugin_name}")
            
            return success
            
        except Exception as e:
            plugin.status = PluginStatus.ERROR
            plugin.last_error = str(e)
            logger.error(f"Error initializing plugin {plugin_name}: {str(e)}")
            return False
    
    def execute_plugin(self, plugin_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific plugin"""
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            return {
                'success': False,
                'error': f'Plugin {plugin_name} not found'
            }
        
        if not plugin.enabled:
            return {
                'success': False,
                'error': f'Plugin {plugin_name} is disabled'
            }
        
        return plugin._execute_with_timing(context)
    
    def execute_plugins_by_type(self, plugin_type: PluginType, 
                              context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute all plugins of a specific type"""
        plugins = self.get_plugins_by_type(plugin_type)
        results = []
        
        for plugin in plugins:
            if plugin.enabled:
                result = plugin._execute_with_timing(context)
                results.append(result)
        
        return results
    
    def load_plugins_from_directory(self) -> int:
        """Load plugins from directory"""
        loaded_count = 0
        
        try:
            if not os.path.exists(self.plugin_directory):
                logger.warning(f"Plugin directory {self.plugin_directory} does not exist")
                return 0
            
            # Load plugin files
            for filename in os.listdir(self.plugin_directory):
                if filename.endswith('.py') and not filename.startswith('__'):
                    plugin_name = filename[:-3]  # Remove .py extension
                    
                    try:
                        # Import plugin module
                        module_path = f"{self.plugin_directory.replace('/', '.')}.{plugin_name}"
                        module = importlib.import_module(module_path)
                        
                        # Look for plugin class
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if (isinstance(attr, type) and 
                                issubclass(attr, Plugin) and 
                                attr != Plugin):
                                
                                # Create plugin instance
                                plugin_instance = attr()
                                
                                # Register plugin
                                if self.register_plugin(plugin_instance):
                                    loaded_count += 1
                                    logger.info(f"Loaded plugin {plugin_instance.name}")
                                break
                    
                    except Exception as e:
                        logger.error(f"Error loading plugin {plugin_name}: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error loading plugins from directory: {str(e)}")
        
        return loaded_count
    
    def initialize_all_plugins(self, configs: Dict[str, Dict[str, Any]] = None) -> Dict[str, bool]:
        """Initialize all plugins"""
        results = {}
        
        for plugin_name, plugin in self.plugins.items():
            config = configs.get(plugin_name, {}) if configs else {}
            results[plugin_name] = self.initialize_plugin(plugin_name, config)
        
        return results
    
    def get_plugin_stats(self) -> Dict[str, Any]:
        """Get plugin statistics"""
        stats = {
            'total_plugins': len(self.plugins),
            'enabled_plugins': len(self.get_enabled_plugins()),
            'active_plugins': len(self.get_active_plugins()),
            'plugins_by_type': {},
            'plugins': {}
        }
        
        # Count by type
        for plugin_type, plugins in self.plugin_types.items():
            stats['plugins_by_type'][plugin_type.value] = len(plugins)
        
        # Individual plugin stats
        for plugin in self.plugins.values():
            stats['plugins'][plugin.name] = plugin.get_stats()
        
        return stats
    
    def save_plugin_configs(self, configs: Dict[str, Dict[str, Any]]) -> bool:
        """Save plugin configurations"""
        try:
            cache.set(self.config_cache_key, configs, timeout=86400)  # 24 hours
            return True
        except Exception as e:
            logger.error(f"Error saving plugin configs: {str(e)}")
            return False
    
    def load_plugin_configs(self) -> Dict[str, Dict[str, Any]]:
        """Load plugin configurations"""
        try:
            return cache.get(self.config_cache_key, {})
        except Exception as e:
            logger.error(f"Error loading plugin configs: {str(e)}")
            return {}
    
    def cleanup_all_plugins(self) -> Dict[str, bool]:
        """Cleanup all plugins"""
        results = {}
        
        for plugin_name, plugin in self.plugins.items():
            results[plugin_name] = plugin.cleanup()
        
        return results


# Built-in plugins
class BasicFraudDetectionPlugin(FraudDetectionPlugin):
    """Basic fraud detection plugin"""
    
    def __init__(self):
        super().__init__(
            name="basic_fraud_detection",
            version="1.0.0",
            description="Basic fraud detection using common patterns"
        )
    
    def initialize(self, config: Dict[str, Any] = None) -> bool:
        """Initialize plugin"""
        try:
            self.config = config or {}
            self.threshold = self.config.get('fraud_threshold', 70)
            return True
        except Exception as e:
            logger.error(f"Error initializing fraud detection plugin: {str(e)}")
            return False
    
    def analyze_fraud(self, conversion_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze for fraud"""
        fraud_score = 0
        indicators = []
        
        # Check completion time
        if 'completion_time' in conversion_data:
            completion_time = conversion_data['completion_time']
            if completion_time < 60:  # Less than 1 minute
                fraud_score += 30
                indicators.append("suspiciously_fast_completion")
        
        # Check payout amount
        if 'payout' in conversion_data:
            payout = conversion_data['payout']
            if payout > 100:  # High amount
                fraud_score += 25
                indicators.append("high_payout_amount")
        
        # Check IP address
        if 'ip_address' in conversion_data:
            ip_address = conversion_data['ip_address']
            if self._is_suspicious_ip(ip_address):
                fraud_score += 40
                indicators.append("suspicious_ip_address")
        
        # Determine risk level
        risk_level = "low"
        if fraud_score >= 80:
            risk_level = "high"
        elif fraud_score >= 50:
            risk_level = "medium"
        
        return {
            'success': True,
            'fraud_score': min(fraud_score, 100),
            'risk_level': risk_level,
            'indicators': indicators,
            'is_fraudulent': fraud_score >= self.threshold
        }
    
    def _is_suspicious_ip(self, ip_address: str) -> bool:
        """Check if IP is suspicious"""
        # This would integrate with your IP reputation service
        # For now, just check for common patterns
        suspicious_patterns = [
            r'^10\.',  # Private IP
            r'^192\.168\.',  # Private IP
            r'^172\.(1[6-9]|2[0-9]|3[0-1])\.',  # Private IP
        ]
        
        import re
        for pattern in suspicious_patterns:
            if re.match(pattern, ip_address):
                return True
        
        return False
    
    def cleanup(self) -> bool:
        """Cleanup plugin"""
        return True


class BasicRewardCalculationPlugin(RewardCalculationPlugin):
    """Basic reward calculation plugin"""
    
    def __init__(self):
        super().__init__(
            name="basic_reward_calculation",
            version="1.0.0",
            description="Basic reward calculation with multipliers"
        )
    
    def initialize(self, config: Dict[str, Any] = None) -> bool:
        """Initialize plugin"""
        try:
            self.config = config or {}
            self.default_multiplier = self.config.get('default_multiplier', 1.0)
            return True
        except Exception as e:
            logger.error(f"Error initializing reward calculation plugin: {str(e)}")
            return False
    
    def calculate_reward(self, offer_data: Dict[str, Any], 
                        user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate reward amount"""
        base_amount = offer_data.get('reward_amount', 0)
        multiplier = self.default_multiplier
        
        # Apply user-level multipliers
        if 'loyalty_level' in user_data:
            loyalty_level = user_data['loyalty_level']
            if loyalty_level == 'gold':
                multiplier *= 1.2
            elif loyalty_level == 'silver':
                multiplier *= 1.1
            elif loyalty_level == 'bronze':
                multiplier *= 1.05
        
        # Apply offer-level multipliers
        if 'is_featured' in offer_data and offer_data['is_featured']:
            multiplier *= 1.1
        
        if 'is_hot' in offer_data and offer_data['is_hot']:
            multiplier *= 1.15
        
        final_amount = base_amount * multiplier
        
        return {
            'success': True,
            'base_amount': base_amount,
            'multiplier': multiplier,
            'final_amount': final_amount,
            'bonus_amount': final_amount - base_amount
        }
    
    def cleanup(self) -> bool:
        """Cleanup plugin"""
        return True


# Global plugin manager instance
plugin_manager = PluginManager()

# Initialize built-in plugins
plugin_manager.register_plugin(BasicFraudDetectionPlugin())
plugin_manager.register_plugin(BasicRewardCalculationPlugin())

# Export all classes and functions
__all__ = [
    # Enums
    'PluginType',
    'PluginStatus',
    
    # Classes
    'Plugin',
    'NetworkSyncPlugin',
    'FraudDetectionPlugin',
    'RewardCalculationPlugin',
    'PluginManager',
    
    # Built-in plugins
    'BasicFraudDetectionPlugin',
    'BasicRewardCalculationPlugin',
    
    # Global instance
    'plugin_manager'
]
