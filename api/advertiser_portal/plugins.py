"""
Plugin System for Advertiser Portal

This module provides a comprehensive plugin system for extending
the application functionality with third-party plugins.
"""

import os
import sys
import json
import zipfile
import tempfile
import shutil
from typing import Dict, List, Any, Optional, Type
from pathlib import Path
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from datetime import datetime
import importlib.util

from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone

from .hooks import *
from .exceptions import *
from .utils import *
from .constants import *


logger = logging.getLogger(__name__)


@dataclass
class PluginMetadata:
    """Plugin metadata structure."""
    name: str
    version: str
    description: str
    author: str
    email: str
    website: str = ""
    license: str = ""
    requirements: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    min_app_version: str = ""
    max_app_version: str = ""
    plugin_type: str = "extension"  # extension, theme, integration
    category: str = "general"  # analytics, billing, security, etc.
    tags: List[str] = field(default_factory=list)
    install_date: Optional[datetime] = None
    update_date: Optional[datetime] = None
    enabled: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginMetadata':
        """Create metadata from dictionary."""
        return cls(
            name=data.get('name', ''),
            version=data.get('version', '1.0.0'),
            description=data.get('description', ''),
            author=data.get('author', ''),
            email=data.get('email', ''),
            website=data.get('website', ''),
            license=data.get('license', ''),
            requirements=data.get('requirements', []),
            dependencies=data.get('dependencies', []),
            min_app_version=data.get('min_app_version', ''),
            max_app_version=data.get('max_app_version', ''),
            plugin_type=data.get('plugin_type', 'extension'),
            category=data.get('category', 'general'),
            tags=data.get('tags', []),
            install_date=data.get('install_date'),
            update_date=data.get('update_date'),
            enabled=data.get('enabled', True)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'author': self.author,
            'email': self.email,
            'website': self.website,
            'license': self.license,
            'requirements': self.requirements,
            'dependencies': self.dependencies,
            'min_app_version': self.min_app_version,
            'max_app_version': self.max_app_version,
            'plugin_type': self.plugin_type,
            'category': self.category,
            'tags': self.tags,
            'install_date': self.install_date.isoformat() if self.install_date else None,
            'update_date': self.update_date.isoformat() if self.update_date else None,
            'enabled': self.enabled
        }


class PluginInterface(ABC):
    """Interface that all plugins must implement."""
    
    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        pass
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the plugin."""
        pass
    
    @abstractmethod
    def activate(self) -> bool:
        """Activate the plugin."""
        pass
    
    @abstractmethod
    def deactivate(self) -> bool:
        """Deactivate the plugin."""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup plugin resources."""
        pass
    
    @abstractmethod
    def get_hooks(self) -> List[Hook]:
        """Get hooks provided by this plugin."""
        pass
    
    def get_admin_urls(self) -> List[str]:
        """Get admin URL patterns provided by plugin."""
        return []
    
    def get_api_endpoints(self) -> List[str]:
        """Get API endpoints provided by plugin."""
        return []
    
    def get_settings_schema(self) -> Dict[str, Any]:
        """Get settings schema for plugin configuration."""
        return {}
    
    def validate_settings(self, settings: Dict[str, Any]) -> List[str]:
        """Validate plugin settings."""
        return []


class BasePlugin(PluginInterface):
    """Base plugin implementation."""
    
    def __init__(self):
        self.metadata: Optional[PluginMetadata] = None
        self.settings: Dict[str, Any] = {}
        self.hooks: List[Hook] = []
        self.enabled = False
        self.initialized = False
    
    def get_metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        if not self.metadata:
            raise PluginError("Plugin metadata not set")
        return self.metadata
    
    def initialize(self) -> bool:
        """Initialize the plugin."""
        try:
            if self.initialized:
                return True
            
            # Load settings
            self._load_settings()
            
            # Perform initialization
            result = self._do_initialize()
            
            if result:
                self.initialized = True
                logger.info(f"Plugin {self.get_metadata().name} initialized successfully")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to initialize plugin {self.get_metadata().name}: {str(e)}")
            return False
    
    def activate(self) -> bool:
        """Activate the plugin."""
        try:
            if not self.initialized:
                if not self.initialize():
                    return False
            
            # Perform activation
            result = self._do_activate()
            
            if result:
                self.enabled = True
                logger.info(f"Plugin {self.get_metadata().name} activated successfully")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to activate plugin {self.get_metadata().name}: {str(e)}")
            return False
    
    def deactivate(self) -> bool:
        """Deactivate the plugin."""
        try:
            # Perform deactivation
            result = self._do_deactivate()
            
            if result:
                self.enabled = False
                logger.info(f"Plugin {self.get_metadata().name} deactivated successfully")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to deactivate plugin {self.get_metadata().name}: {str(e)}")
            return False
    
    def cleanup(self) -> None:
        """Cleanup plugin resources."""
        try:
            self._do_cleanup()
            logger.info(f"Plugin {self.get_metadata().name} cleaned up successfully")
        except Exception as e:
            logger.error(f"Failed to cleanup plugin {self.get_metadata().name}: {str(e)}")
    
    def get_hooks(self) -> List[Hook]:
        """Get hooks provided by this plugin."""
        return self.hooks
    
    def _load_settings(self) -> None:
        """Load plugin settings."""
        try:
            settings_file = self._get_settings_file_path()
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    self.settings = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load settings for plugin {self.get_metadata().name}: {str(e)}")
    
    def _save_settings(self) -> None:
        """Save plugin settings."""
        try:
            settings_file = self._get_settings_file_path()
            os.makedirs(os.path.dirname(settings_file), exist_ok=True)
            with open(settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save settings for plugin {self.get_metadata().name}: {str(e)}")
    
    def _get_settings_file_path(self) -> str:
        """Get settings file path for this plugin."""
        plugin_dir = self._get_plugin_directory()
        return os.path.join(plugin_dir, 'settings.json')
    
    def _get_plugin_directory(self) -> str:
        """Get plugin directory path."""
        return os.path.join(settings.PLUGIN_DIR, self.get_metadata().name)
    
    def _do_initialize(self) -> bool:
        """Override this method to perform plugin initialization."""
        return True
    
    def _do_activate(self) -> bool:
        """Override this method to perform plugin activation."""
        return True
    
    def _do_deactivate(self) -> bool:
        """Override this method to perform plugin deactivation."""
        return True
    
    def _do_cleanup(self) -> None:
        """Override this method to perform plugin cleanup."""
        pass


class PluginManager:
    """Manager for plugin lifecycle operations."""
    
    def __init__(self):
        self.plugins: Dict[str, PluginInterface] = {}
        self.plugin_dir = getattr(settings, 'PLUGIN_DIR', 'plugins')
        self.installed_plugins_file = os.path.join(self.plugin_dir, 'installed_plugins.json')
        self._ensure_plugin_directory()
        self._load_installed_plugins()
    
    def _ensure_plugin_directory(self):
        """Ensure plugin directory exists."""
        os.makedirs(self.plugin_dir, exist_ok=True)
    
    def _load_installed_plugins(self):
        """Load list of installed plugins."""
        try:
            if os.path.exists(self.installed_plugins_file):
                with open(self.installed_plugins_file, 'r') as f:
                    data = json.load(f)
                    for plugin_data in data.get('plugins', []):
                        plugin_path = plugin_data.get('path')
                        if plugin_path and os.path.exists(plugin_path):
                            self._load_plugin_from_path(plugin_path)
        except Exception as e:
            logger.error(f"Failed to load installed plugins: {str(e)}")
    
    def _load_plugin_from_path(self, plugin_path: str) -> bool:
        """Load plugin from file path."""
        try:
            # Add plugin directory to Python path
            if plugin_path not in sys.path:
                sys.path.insert(0, plugin_path)
            
            # Look for plugin module
            plugin_module = None
            for file in os.listdir(plugin_path):
                if file.endswith('.py') and not file.startswith('_'):
                    module_name = file[:-3]
                    spec = importlib.util.spec_from_file_location(module_name, os.path.join(plugin_path, file))
                    plugin_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(plugin_module)
                    break
            
            if not plugin_module:
                logger.error(f"No plugin module found in {plugin_path}")
                return False
            
            # Find plugin class
            plugin_class = None
            for attr_name in dir(plugin_module):
                attr = getattr(plugin_module, attr_name)
                if (inspect.isclass(attr) and 
                    issubclass(attr, PluginInterface) and 
                    attr != PluginInterface and 
                    attr != BasePlugin):
                    plugin_class = attr
                    break
            
            if not plugin_class:
                logger.error(f"No plugin class found in {plugin_path}")
                return False
            
            # Instantiate plugin
            plugin = plugin_class()
            metadata = plugin.get_metadata()
            
            # Validate metadata
            if not self._validate_plugin_metadata(metadata):
                return False
            
            # Store plugin
            self.plugins[metadata.name] = plugin
            
            logger.info(f"Plugin {metadata.name} loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load plugin from {plugin_path}: {str(e)}")
            return False
    
    def _validate_plugin_metadata(self, metadata: PluginMetadata) -> bool:
        """Validate plugin metadata."""
        if not metadata.name:
            logger.error("Plugin metadata missing name")
            return False
        
        if not metadata.version:
            logger.error("Plugin metadata missing version")
            return False
        
        if not metadata.author:
            logger.error("Plugin metadata missing author")
            return False
        
        # Check version compatibility
        app_version = getattr(settings, 'APP_VERSION', '1.0.0')
        if metadata.min_app_version and not self._is_version_compatible(app_version, metadata.min_app_version):
            logger.error(f"Plugin {metadata.name} requires minimum app version {metadata.min_app_version}, current is {app_version}")
            return False
        
        if metadata.max_app_version and not self._is_version_compatible(metadata.max_app_version, app_version):
            logger.error(f"Plugin {metadata.name} requires maximum app version {metadata.max_app_version}, current is {app_version}")
            return False
        
        return True
    
    def _is_version_compatible(self, required_version: str, current_version: str) -> bool:
        """Check version compatibility."""
        try:
            from packaging import version
            return version.parse(current_version) >= version.parse(required_version)
        except ImportError:
            # Simple version comparison if packaging not available
            return current_version >= required_version
    
    def install_plugin(self, plugin_file: str) -> bool:
        """
        Install plugin from file.
        
        Args:
            plugin_file: Path to plugin file (zip or directory)
            
        Returns:
            True if installed successfully
        """
        try:
            # Create temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                plugin_dir = None
                
                if plugin_file.endswith('.zip'):
                    # Extract zip file
                    with zipfile.ZipFile(plugin_file, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                    
                    # Find plugin directory
                    for item in os.listdir(temp_dir):
                        item_path = os.path.join(temp_dir, item)
                        if os.path.isdir(item_path):
                            plugin_dir = item_path
                            break
                else:
                    # Assume it's a directory
                    plugin_dir = plugin_file
                
                if not plugin_dir:
                    logger.error("No plugin directory found in package")
                    return False
                
                # Load plugin to validate
                if not self._load_plugin_from_path(plugin_dir):
                    return False
                
                # Get plugin metadata
                temp_plugin = list(self.plugins.values())[-1]
                metadata = temp_plugin.get_metadata()
                
                # Check if already installed
                if metadata.name in self.plugins:
                    logger.error(f"Plugin {metadata.name} is already installed")
                    return False
                
                # Install plugin to plugin directory
                install_path = os.path.join(self.plugin_dir, metadata.name)
                if os.path.exists(install_path):
                    shutil.rmtree(install_path)
                
                shutil.copytree(plugin_dir, install_path)
                
                # Load plugin from install path
                self._load_plugin_from_path(install_path)
                
                # Update installed plugins list
                self._update_installed_plugins_list()
                
                logger.info(f"Plugin {metadata.name} installed successfully")
                return True
                
        except Exception as e:
            logger.error(f"Failed to install plugin from {plugin_file}: {str(e)}")
            return False
    
    def uninstall_plugin(self, plugin_name: str) -> bool:
        """
        Uninstall a plugin.
        
        Args:
            plugin_name: Name of plugin to uninstall
            
        Returns:
            True if uninstalled successfully
        """
        try:
            if plugin_name not in self.plugins:
                logger.error(f"Plugin {plugin_name} is not installed")
                return False
            
            plugin = self.plugins[plugin_name]
            
            # Deactivate plugin first
            if plugin.enabled:
                plugin.deactivate()
            
            # Cleanup plugin
            plugin.cleanup()
            
            # Remove plugin directory
            plugin_path = os.path.join(self.plugin_dir, plugin_name)
            if os.path.exists(plugin_path):
                shutil.rmtree(plugin_path)
            
            # Remove from plugins dict
            del self.plugins[plugin_name]
            
            # Update installed plugins list
            self._update_installed_plugins_list()
            
            logger.info(f"Plugin {plugin_name} uninstalled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to uninstall plugin {plugin_name}: {str(e)}")
            return False
    
    def activate_plugin(self, plugin_name: str) -> bool:
        """
        Activate a plugin.
        
        Args:
            plugin_name: Name of plugin to activate
            
        Returns:
            True if activated successfully
        """
        try:
            if plugin_name not in self.plugins:
                logger.error(f"Plugin {plugin_name} is not installed")
                return False
            
            plugin = self.plugins[plugin_name]
            
            if plugin.enabled:
                logger.warning(f"Plugin {plugin_name} is already active")
                return True
            
            if plugin.activate():
                # Register hooks with global hook manager
                for hook in plugin.get_hooks():
                    global_hook_manager.registry.register(hook)
                
                logger.info(f"Plugin {plugin_name} activated successfully")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to activate plugin {plugin_name}: {str(e)}")
            return False
    
    def deactivate_plugin(self, plugin_name: str) -> bool:
        """
        Deactivate a plugin.
        
        Args:
            plugin_name: Name of plugin to deactivate
            
        Returns:
            True if deactivated successfully
        """
        try:
            if plugin_name not in self.plugins:
                logger.error(f"Plugin {plugin_name} is not installed")
                return False
            
            plugin = self.plugins[plugin_name]
            
            if not plugin.enabled:
                logger.warning(f"Plugin {plugin_name} is already inactive")
                return True
            
            if plugin.deactivate():
                # Unregister hooks from global hook manager
                for hook in plugin.get_hooks():
                    global_hook_manager.registry.unregister(hook.name, hook.function)
                
                logger.info(f"Plugin {plugin_name} deactivated successfully")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to deactivate plugin {plugin_name}: {str(e)}")
            return False
    
    def get_plugin(self, plugin_name: str) -> Optional[PluginInterface]:
        """Get a specific plugin."""
        return self.plugins.get(plugin_name)
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all installed plugins."""
        return [
            {
                'name': plugin.get_metadata().name,
                'version': plugin.get_metadata().version,
                'description': plugin.get_metadata().description,
                'author': plugin.get_metadata().author,
                'category': plugin.get_metadata().category,
                'enabled': plugin.enabled,
                'initialized': plugin.initialized,
                'install_date': plugin.get_metadata().install_date,
                'update_date': plugin.get_metadata().update_date
            }
            for plugin in self.plugins.values()
        ]
    
    def get_active_plugins(self) -> List[PluginInterface]:
        """Get all active plugins."""
        return [plugin for plugin in self.plugins.values() if plugin.enabled]
    
    def update_plugin(self, plugin_name: str, update_file: str) -> bool:
        """
        Update a plugin.
        
        Args:
            plugin_name: Name of plugin to update
            update_file: Path to update file
            
        Returns:
            True if updated successfully
        """
        try:
            if plugin_name not in self.plugins:
                logger.error(f"Plugin {plugin_name} is not installed")
                return False
            
            # Deactivate plugin
            was_active = self.plugins[plugin_name].enabled
            if was_active:
                self.deactivate_plugin(plugin_name)
            
            # Backup current plugin
            current_path = os.path.join(self.plugin_dir, plugin_name)
            backup_path = f"{current_path}.backup"
            if os.path.exists(current_path):
                shutil.move(current_path, backup_path)
            
            # Install update
            if self.install_plugin(update_file):
                # Remove backup
                if os.path.exists(backup_path):
                    shutil.rmtree(backup_path)
                
                # Reactivate if it was active
                if was_active:
                    self.activate_plugin(plugin_name)
                
                logger.info(f"Plugin {plugin_name} updated successfully")
                return True
            else:
                # Restore backup
                if os.path.exists(backup_path):
                    shutil.rmtree(current_path)
                    shutil.move(backup_path, current_path)
                
                logger.error(f"Failed to update plugin {plugin_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update plugin {plugin_name}: {str(e)}")
            return False
    
    def _update_installed_plugins_list(self):
        """Update the installed plugins list file."""
        try:
            installed_data = {
                'plugins': [
                    {
                        'name': plugin.get_metadata().name,
                        'version': plugin.get_metadata().version,
                        'path': os.path.join(self.plugin_dir, plugin.get_metadata().name),
                        'install_date': plugin.get_metadata().install_date.isoformat() if plugin.get_metadata().install_date else None,
                        'enabled': plugin.enabled
                    }
                    for plugin in self.plugins.values()
                ],
                'updated_at': timezone.now().isoformat()
            }
            
            with open(self.installed_plugins_file, 'w') as f:
                json.dump(installed_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to update installed plugins list: {str(e)}")
    
    def scan_for_plugins(self) -> int:
        """Scan plugin directory for new plugins."""
        loaded_count = 0
        
        try:
            for item in os.listdir(self.plugin_dir):
                item_path = os.path.join(self.plugin_dir, item)
                
                if os.path.isdir(item_path) and item not in self.plugins:
                    if self._load_plugin_from_path(item_path):
                        loaded_count += 1
            
            if loaded_count > 0:
                self._update_installed_plugins_list()
            
        except Exception as e:
            logger.error(f"Failed to scan for plugins: {str(e)}")
        
        return loaded_count


# Global plugin manager instance
global_plugin_manager = PluginManager()


# Convenience functions
def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager."""
    return global_plugin_manager


def install_plugin(plugin_file: str) -> bool:
    """Install a plugin using the global manager."""
    return global_plugin_manager.install_plugin(plugin_file)


def uninstall_plugin(plugin_name: str) -> bool:
    """Uninstall a plugin using the global manager."""
    return global_plugin_manager.uninstall_plugin(plugin_name)


def activate_plugin(plugin_name: str) -> bool:
    """Activate a plugin using the global manager."""
    return global_plugin_manager.activate_plugin(plugin_name)


def deactivate_plugin(plugin_name: str) -> bool:
    """Deactivate a plugin using the global manager."""
    return global_plugin_manager.deactivate_plugin(plugin_name)


def list_plugins() -> List[Dict[str, Any]]:
    """List all plugins using the global manager."""
    return global_plugin_manager.list_plugins()


# Custom exceptions
class PluginError(Exception):
    """Raised when plugin operation fails."""
    pass


class PluginInstallationError(PluginError):
    """Raised when plugin installation fails."""
    pass


class PluginCompatibilityError(PluginError):
    """Raised when plugin is not compatible."""
    pass
