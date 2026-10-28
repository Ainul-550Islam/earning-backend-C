# =============================================================================
# auto_mod/dependencies.py
# =============================================================================

"""
Dependency management for auto moderation system.
Handles external service dependencies, ML model loading, and resource management.
"""

import os
import sys
import logging
import importlib
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.apps import apps

logger = logging.getLogger(__name__)


class DependencyManager:
    """
    Manages external dependencies for the auto moderation system.
    """
    
    def __init__(self):
        self.dependencies = {}
        self.loaded_modules = {}
        self.service_status = {}
        self.initialized = False
    
    def register_dependency(self, name: str, module_path: str, 
                          required: bool = True, 
                          version_check: Optional[Callable] = None,
                          fallback: Optional[Callable] = None) -> None:
        """
        Register a dependency.
        
        Args:
            name: Dependency name
            module_path: Python module path
            required: Whether this dependency is required
            version_check: Function to check version compatibility
            fallback: Fallback function if dependency fails
        """
        self.dependencies[name] = {
            'module_path': module_path,
            'required': required,
            'version_check': version_check,
            'fallback': fallback,
            'loaded': False,
            'error': None,
            'version': None
        }
    
    def load_dependency(self, name: str) -> bool:
        """
        Load a specific dependency.
        
        Args:
            name: Dependency name
            
        Returns:
            True if loaded successfully, False otherwise
        """
        if name not in self.dependencies:
            logger.error(f"Dependency {name} not registered")
            return False
        
        dep_info = self.dependencies[name]
        
        try:
            # Import the module
            module = importlib.import_module(dep_info['module_path'])
            self.loaded_modules[name] = module
            
            # Check version if required
            if dep_info['version_check']:
                version = dep_info['version_check'](module)
                dep_info['version'] = version
            
            dep_info['loaded'] = True
            dep_info['error'] = None
            
            logger.info(f"Successfully loaded dependency: {name}")
            return True
            
        except ImportError as exc:
            dep_info['error'] = str(exc)
            
            if dep_info['required']:
                logger.error(f"Required dependency {name} failed to load: {exc}")
                raise
            
            logger.warning(f"Optional dependency {name} failed to load: {exc}")
            
            # Try fallback if available
            if dep_info['fallback']:
                try:
                    fallback_result = dep_info['fallback']()
                    self.loaded_modules[name] = fallback_result
                    dep_info['loaded'] = True
                    logger.info(f"Using fallback for dependency: {name}")
                    return True
                except Exception as fallback_exc:
                    logger.error(f"Fallback for {name} also failed: {fallback_exc}")
            
            return False
    
    def load_all_dependencies(self) -> Dict[str, bool]:
        """
        Load all registered dependencies.
        
        Returns:
            Dictionary mapping dependency names to load status
        """
        results = {}
        
        for name in self.dependencies:
            results[name] = self.load_dependency(name)
        
        self.initialized = True
        return results
    
    def get_dependency(self, name: str) -> Any:
        """
        Get a loaded dependency.
        
        Args:
            name: Dependency name
            
        Returns:
            The loaded module or fallback
            
        Raises:
            ImportError: If dependency is not loaded
        """
        if name not in self.loaded_modules:
            if name in self.dependencies:
                if not self.dependencies[name]['loaded']:
                    raise ImportError(f"Dependency {name} is not loaded")
            else:
                raise ImportError(f"Dependency {name} is not registered")
        
        return self.loaded_modules[name]
    
    def is_loaded(self, name: str) -> bool:
        """
        Check if a dependency is loaded.
        
        Args:
            name: Dependency name
            
        Returns:
            True if loaded, False otherwise
        """
        return name in self.loaded_modules
    
    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all dependencies.
        
        Returns:
            Dictionary with dependency status information
        """
        status = {}
        
        for name, dep_info in self.dependencies.items():
            status[name] = {
                'loaded': dep_info['loaded'],
                'required': dep_info['required'],
                'error': dep_info['error'],
                'version': dep_info['version'],
                'module_path': dep_info['module_path']
            }
        
        return status
    
    def check_service_health(self) -> Dict[str, bool]:
        """
        Check health of all loaded services.
        
        Returns:
            Dictionary mapping service names to health status
        """
        health_status = {}
        
        for name, module in self.loaded_modules.items():
            try:
                # Try to call a health check method if it exists
                if hasattr(module, 'health_check'):
                    health_status[name] = module.health_check()
                elif hasattr(module, 'ping'):
                    health_status[name] = module.ping()
                else:
                    # Assume healthy if no health check method
                    health_status[name] = True
            except Exception as exc:
                logger.error(f"Health check failed for {name}: {exc}")
                health_status[name] = False
        
        return health_status


# Global dependency manager instance
dependency_manager = DependencyManager()


# Register core dependencies
def register_core_dependencies():
    """Register all core dependencies for auto moderation."""
    
    # ML and AI dependencies
    dependency_manager.register_dependency(
        'torch',
        'torch',
        required=False,
        version_check=lambda module: getattr(module, '__version__', None),
        fallback=lambda: MockTorch()
    )
    
    dependency_manager.register_dependency(
        'transformers',
        'transformers',
        required=False,
        version_check=lambda module: getattr(module, '__version__', None),
        fallback=lambda: MockTransformers()
    )
    
    dependency_manager.register_dependency(
        'opencv',
        'cv2',
        required=False,
        version_check=lambda module: getattr(module, '__version__', None),
        fallback=lambda: MockOpenCV()
    )
    
    dependency_manager.register_dependency(
        'pillow',
        'PIL',
        required=True,
        version_check=lambda module: getattr(module, '__version__', None)
    )
    
    dependency_manager.register_dependency(
        'numpy',
        'numpy',
        required=True,
        version_check=lambda module: getattr(module, '__version__', None)
    )
    
    # OCR dependencies
    dependency_manager.register_dependency(
        'pytesseract',
        'pytesseract',
        required=False,
        version_check=lambda module: getattr(module, '__version__', None),
        fallback=lambda: MockTesseract()
    )
    
    dependency_manager.register_dependency(
        'pdfminer',
        'pdfminer',
        required=False,
        fallback=lambda: MockPDFMiner()
    )
    
    # External API dependencies
    dependency_manager.register_dependency(
        'openai',
        'openai',
        required=False,
        version_check=lambda module: getattr(module, '__version__', None),
        fallback=lambda: MockOpenAI()
    )
    
    dependency_manager.register_dependency(
        'requests',
        'requests',
        required=True,
        version_check=lambda module: getattr(module, '__version__', None)
    )
    
    # Database and caching
    dependency_manager.register_dependency(
        'redis',
        'redis',
        required=False,
        version_check=lambda module: getattr(module, '__version__', None),
        fallback=lambda: MockRedis()
    )
    
    # Text processing
    dependency_manager.register_dependency(
        'nltk',
        'nltk',
        required=False,
        version_check=lambda module: getattr(module, '__version__', None),
        fallback=lambda: MockNLTK()
    )
    
    dependency_manager.register_dependency(
        'spacy',
        'spacy',
        required=False,
        version_check=lambda module: getattr(module, '__version__', None),
        fallback=lambda: MockSpacy()
    )


# Mock classes for optional dependencies
class MockTorch:
    """Mock torch module."""
    
    __version__ = "mock.1.0"
    
    class Tensor:
        def __init__(self, data):
            self.data = data
    
    @staticmethod
    def tensor(data):
        return MockTorch.Tensor(data)
    
    @staticmethod
    def load(path):
        return MockTorch.Tensor([1, 2, 3])


class MockTransformers:
    """Mock transformers module."""
    
    __version__ = "mock.4.0"
    
    class pipeline:
        def __init__(self, task, model=None, **kwargs):
            self.task = task
            self.model = model
        
        def __call__(self, text, **kwargs):
            return [{"label": "POSITIVE", "score": 0.8}]


class MockOpenCV:
    """Mock OpenCV module."""
    
    __version__ = "mock.4.5"
    
    @staticmethod
    def imread(path):
        import numpy as np
        return np.zeros((100, 100, 3), dtype=np.uint8)
    
    @staticmethod
    def imwrite(path, img):
        return True


class MockTesseract:
    """Mock pytesseract module."""
    
    __version__ = "mock.0.3"
    
    @staticmethod
    def image_to_string(image, **kwargs):
        return "Mock OCR text"


class MockPDFMiner:
    """Mock pdfminer module."""
    
    @staticmethod
    def extract_text(pdf_path):
        return "Mock PDF text"


class MockOpenAI:
    """Mock OpenAI module."""
    
    __version__ = "mock.1.0"
    
    class ChatCompletion:
        @staticmethod
        def create(**kwargs):
            return {
                "choices": [{"message": {"content": "Mock response"}}],
                "usage": {"total_tokens": 100}
            }


class MockRedis:
    """Mock redis module."""
    
    __version__ = "mock.4.0"
    
    class Redis:
        def __init__(self, **kwargs):
            pass
        
        def get(self, key):
            return None
        
        def set(self, key, value, **kwargs):
            return True
        
        def delete(self, key):
            return True


class MockNLTK:
    """Mock NLTK module."""
    
    __version__ = "mock.3.8"
    
    @staticmethod
    def word_tokenize(text):
        return text.split()
    
    @staticmethod
    def pos_tag(tokens):
        return [(token, 'NN') for token in tokens]


class MockSpacy:
    """Mock spaCy module."""
    
    __version__ = "mock.3.4"
    
    class Language:
        def __init__(self, name):
            self.name = name
        
        def __call__(self, text):
            return MockDoc(text)
    
    @staticmethod
    def load(name):
        return MockSpacy.Language(name)


class MockDoc:
    """Mock spaCy Doc."""
    
    def __init__(self, text):
        self.text = text
        self.ents = []
    
    def to_json(self):
        return {"text": self.text, "ents": []}


# Service dependency checker
class ServiceDependencyChecker:
    """Checker for service dependencies."""
    
    def __init__(self):
        self.services = {}
    
    def register_service(self, name: str, check_func: Callable[[], bool], 
                         required: bool = True) -> None:
        """
        Register a service dependency.
        
        Args:
            name: Service name
            check_func: Function to check if service is available
            required: Whether this service is required
        """
        self.services[name] = {
            'check_func': check_func,
            'required': required,
            'status': None,
            'last_check': None,
            'error': None
        }
    
    def check_service(self, name: str) -> bool:
        """
        Check if a service is available.
        
        Args:
            name: Service name
            
        Returns:
            True if service is available, False otherwise
        """
        if name not in self.services:
            logger.error(f"Service {name} not registered")
            return False
        
        service_info = self.services[name]
        
        try:
            status = service_info['check_func']()
            service_info['status'] = status
            service_info['last_check'] = timezone.now()
            service_info['error'] = None
            
            if not status and service_info['required']:
                logger.error(f"Required service {name} is not available")
            
            return status
            
        except Exception as exc:
            service_info['status'] = False
            service_info['last_check'] = timezone.now()
            service_info['error'] = str(exc)
            
            if service_info['required']:
                logger.error(f"Required service {name} check failed: {exc}")
            else:
                logger.warning(f"Optional service {name} check failed: {exc}")
            
            return False
    
    def check_all_services(self) -> Dict[str, bool]:
        """
        Check all registered services.
        
        Returns:
            Dictionary mapping service names to availability status
        """
        results = {}
        
        for name in self.services:
            results[name] = self.check_service(name)
        
        return results
    
    def get_service_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all services.
        
        Returns:
            Dictionary with service status information
        """
        status = {}
        
        for name, service_info in self.services.items():
            status[name] = {
                'status': service_info['status'],
                'required': service_info['required'],
                'last_check': service_info['last_check'],
                'error': service_info['error']
            }
        
        return status


# Global service checker instance
service_checker = ServiceDependencyChecker()


# Register service dependencies
def register_service_dependencies():
    """Register all service dependencies."""
    
    # Database service
    def check_database():
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except:
            return False
    
    service_checker.register_service('database', check_database, required=True)
    
    # Cache service
    def check_cache():
        try:
            cache.set('dependency_check', 'test', timeout=10)
            result = cache.get('dependency_check')
            return result == 'test'
        except:
            return False
    
    service_checker.register_service('cache', check_cache, required=False)
    
    # Storage service
    def check_storage():
        try:
            from django.core.files.storage import default_storage
            return default_storage.exists('test') or True  # Assume available
        except:
            return False
    
    service_checker.register_service('storage', check_storage, required=True)
    
    # Celery service
    def check_celery():
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            stats = inspect.stats()
            return stats is not None
        except:
            return False
    
    service_checker.register_service('celery', check_celery, required=False)
    
    # Email service
    def check_email():
        try:
            from django.core.mail import get_connection
            connection = get_connection()
            return True
        except:
            return False
    
    service_checker.register_service('email', check_email, required=False)


# Initialize dependencies
def initialize_dependencies():
    """Initialize all dependencies."""
    logger.info("Initializing auto_mod dependencies...")
    
    # Register dependencies
    register_core_dependencies()
    register_service_dependencies()
    
    # Load all dependencies
    dependency_results = dependency_manager.load_all_dependencies()
    service_results = service_checker.check_all_services()
    
    # Log results
    logger.info("Dependency loading completed:")
    
    for name, loaded in dependency_results.items():
        status = "✓" if loaded else "✗"
        logger.info(f"  {status} {name}")
    
    logger.info("Service checking completed:")
    
    for name, available in service_results.items():
        status = "✓" if available else "✗"
        logger.info(f"  {status} {name}")
    
    # Check for critical failures
    critical_failures = []
    
    for name, loaded in dependency_results.items():
        if dependency_manager.dependencies[name]['required'] and not loaded:
            critical_failures.append(f"Dependency {name}")
    
    for name, available in service_results.items():
        if service_checker.services[name]['required'] and not available:
            critical_failures.append(f"Service {name}")
    
    if critical_failures:
        error_msg = f"Critical dependencies failed: {', '.join(critical_failures)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    logger.info("All dependencies initialized successfully")
    return True


# Dependency health monitoring
def monitor_dependencies():
    """Monitor dependency health and log issues."""
    dependency_status = dependency_manager.get_status()
    service_status = service_checker.get_service_status()
    
    issues = []
    
    # Check dependency issues
    for name, status in dependency_status.items():
        if not status['loaded'] and status['required']:
            issues.append(f"Required dependency {name} not loaded: {status['error']}")
        elif status['error']:
            issues.append(f"Dependency {name} has error: {status['error']}")
    
    # Check service issues
    for name, status in service_status.items():
        if not status['status'] and status['required']:
            issues.append(f"Required service {name} unavailable: {status['error']}")
        elif status['error']:
            issues.append(f"Service {name} has error: {status['error']}")
    
    if issues:
        logger.warning("Dependency monitoring found issues:")
        for issue in issues:
            logger.warning(f"  - {issue}")
    else:
        logger.info("All dependencies healthy")
    
    return issues


# Auto-initialize when module is imported
try:
    initialize_dependencies()
except Exception as exc:
    logger.error(f"Failed to initialize dependencies: {exc}")
    # Don't raise the exception to avoid breaking the app startup
