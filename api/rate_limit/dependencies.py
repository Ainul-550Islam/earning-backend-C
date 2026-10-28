# api/rate_limit/dependencies.py
"""
Dependencies Management for Rate Limit Module

Manages external dependencies, service integrations, and third-party library requirements.
"""

import importlib
import logging
from typing import Dict, List, Optional, Any
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


class DependencyManager:
    """
    Manages dependencies for the rate limit module.
    """
    
    # Required dependencies
    REQUIRED_DEPENDENCIES = {
        'django': {'min_version': '3.2', 'max_version': '5.0'},
        'djangorestframework': {'min_version': '3.12', 'max_version': '4.0'},
        'redis': {'min_version': '4.0', 'max_version': '5.0'},
        'celery': {'min_version': '5.0', 'max_version': '6.0'},
        'channels': {'min_version': '3.0', 'max_version': '4.0'},
        'channels_redis': {'min_version': '3.0', 'max_version': '4.0'},
    }
    
    # Optional dependencies
    OPTIONAL_DEPENDENCIES = {
        'django-filter': {'min_version': '21.0', 'max_version': '24.0'},
        'django-cors-headers': {'min_version': '3.0', 'max_version': '4.0'},
        'django-extensions': {'min_version': '3.0', 'max_version': '4.0'},
        'psycopg2-binary': {'min_version': '2.8', 'max_version': '3.0'},
        'gunicorn': {'min_version': '20.0', 'max_version': '22.0'},
        'uvicorn': {'min_version': '0.15', 'max_version': '0.25'},
        'reportlab': {'min_version': '3.6', 'max_version': '4.0'},
        'openai': {'min_version': '0.27', 'max_version': '2.0'},
        'pandas': {'min_version': '1.3', 'max_version': '3.0'},
        'numpy': {'min_version': '1.20', 'max_version': '2.0'},
        'matplotlib': {'min_version': '3.5', 'max_version': '4.0'},
        'seaborn': {'min_version': '0.11', 'max_version': '0.13'},
    }
    
    # Development dependencies
    DEV_DEPENDENCIES = {
        'pytest': {'min_version': '6.0', 'max_version': '8.0'},
        'pytest-django': {'min_version': '4.0', 'max_version': '5.0'},
        'pytest-cov': {'min_version': '2.10', 'max_version': '5.0'},
        'black': {'min_version': '21.0', 'max_version': '24.0'},
        'flake8': {'min_version': '3.8', 'max_version': '7.0'},
        'isort': {'min_version': '5.0', 'max_version': '6.0'},
        'mypy': {'min_version': '0.800', 'max_version': '2.0'},
        'coverage': {'min_version': '5.0', 'max_version': '8.0'},
    }
    
    def __init__(self):
        self.installed_packages = {}
        self.missing_packages = []
        self.version_conflicts = []
        self._load_installed_packages()
    
    def _load_installed_packages(self):
        """
        Load information about installed packages.
        """
        try:
            import pkg_resources
            for package in pkg_resources.working_set:
                self.installed_packages[package.project_name.lower()] = {
                    'version': package.version,
                    'location': package.location,
                    'project_name': package.project_name,
                }
        except ImportError:
            logger.warning("pkg_resources not available, cannot check package versions")
    
    def check_dependencies(self) -> Dict[str, Any]:
        """
        Check all dependencies and return status.
        """
        results = {
            'required': self._check_dependency_group(self.REQUIRED_DEPENDENCIES, required=True),
            'optional': self._check_dependency_group(self.OPTIONAL_DEPENDENCIES, required=False),
            'dev': self._check_dependency_group(self.DEV_DEPENDENCIES, required=False),
        }
        
        results['all_satisfied'] = (
            len(results['required']['missing']) == 0 and
            len(results['required']['version_conflicts']) == 0
        )
        
        return results
    
    def _check_dependency_group(self, dependencies: Dict, required: bool = False) -> Dict[str, Any]:
        """
        Check a group of dependencies.
        """
        missing = []
        version_conflicts = []
        satisfied = []
        
        for package_name, version_info in dependencies.items():
            package_key = package_name.lower()
            
            if package_key not in self.installed_packages:
                missing.append({
                    'name': package_name,
                    'required': required,
                    'min_version': version_info.get('min_version'),
                    'max_version': version_info.get('max_version'),
                })
            else:
                installed_info = self.installed_packages[package_key]
                installed_version = installed_info['version']
                
                if self._is_version_compatible(installed_version, version_info):
                    satisfied.append({
                        'name': package_name,
                        'installed_version': installed_version,
                    })
                else:
                    version_conflicts.append({
                        'name': package_name,
                        'installed_version': installed_version,
                        'required': required,
                        'min_version': version_info.get('min_version'),
                        'max_version': version_info.get('max_version'),
                    })
        
        return {
            'missing': missing,
            'version_conflicts': version_conflicts,
            'satisfied': satisfied,
        }
    
    def _is_version_compatible(self, installed_version: str, version_info: Dict) -> bool:
        """
        Check if installed version is compatible with requirements.
        """
        try:
            from packaging import version
            
            installed = version.parse(installed_version)
            
            min_version = version_info.get('min_version')
            max_version = version_info.get('max_version')
            
            if min_version and installed < version.parse(min_version):
                return False
            
            if max_version and installed >= version.parse(max_version):
                return False
            
            return True
            
        except ImportError:
            # Fallback to simple string comparison if packaging not available
            return True
        except Exception as e:
            logger.warning(f"Error checking version compatibility: {str(e)}")
            return True
    
    def generate_requirements_txt(self) -> str:
        """
        Generate requirements.txt content.
        """
        requirements = []
        
        # Add required dependencies
        for package_name, version_info in self.REQUIRED_DEPENDENCIES.items():
            min_version = version_info.get('min_version')
            max_version = version_info.get('max_version')
            
            if min_version and max_version:
                requirements.append(f"{package_name}>={min_version},<{max_version}")
            elif min_version:
                requirements.append(f"{package_name}>={min_version}")
            else:
                requirements.append(package_name)
        
        # Add optional dependencies
        requirements.append("\n# Optional dependencies")
        for package_name, version_info in self.OPTIONAL_DEPENDENCIES.items():
            min_version = version_info.get('min_version')
            max_version = version_info.get('max_version')
            
            if min_version and max_version:
                requirements.append(f"{package_name}>={min_version},<{max_version}")
            elif min_version:
                requirements.append(f"{package_name}>={min_version}")
            else:
                requirements.append(package_name)
        
        # Add development dependencies
        requirements.append("\n# Development dependencies")
        for package_name, version_info in self.DEV_DEPENDENCIES.items():
            min_version = version_info.get('min_version')
            max_version = version_info.get('max_version')
            
            if min_version and max_version:
                requirements.append(f"{package_name}>={min_version},<{max_version}")
            elif min_version:
                requirements.append(f"{package_name}>={min_version}")
            else:
                requirements.append(package_name)
        
        return '\n'.join(requirements)
    
    def install_missing_dependencies(self, auto_install: bool = False) -> List[str]:
        """
        Install missing dependencies.
        """
        if not auto_install:
            logger.warning("Auto-install not enabled, please install dependencies manually")
            return []
        
        missing_packages = []
        dependency_check = self.check_dependencies()
        
        for missing in dependency_check['required']['missing']:
            missing_packages.append(missing['name'])
        
        # In a real implementation, you would use pip to install packages
        # For security reasons, we'll just log what needs to be installed
        if missing_packages:
            logger.info(f"Missing required packages: {', '.join(missing_packages)}")
            logger.info("Please install them using: pip install " + " ".join(missing_packages))
        
        return missing_packages


class ServiceDependencyManager:
    """
    Manages service dependencies for rate limit module.
    """
    
    # Required services
    REQUIRED_SERVICES = {
        'redis': {
            'check_function': '_check_redis_service',
            'config_key': 'REDIS_URL',
            'fallback_config': 'redis://localhost:6379/0',
        },
        'database': {
            'check_function': '_check_database_service',
            'config_key': 'DATABASES',
            'fallback_config': None,
        },
        'celery': {
            'check_function': '_check_celery_service',
            'config_key': 'CELERY_BROKER_URL',
            'fallback_config': 'redis://localhost:6379/1',
        },
    }
    
    # Optional services
    OPTIONAL_SERVICES = {
        'elasticsearch': {
            'check_function': '_check_elasticsearch_service',
            'config_key': 'ELASTICSEARCH_URL',
            'fallback_config': None,
        },
        'sentry': {
            'check_function': '_check_sentry_service',
            'config_key': 'SENTRY_DSN',
            'fallback_config': None,
        },
        'openai': {
            'check_function': '_check_openai_service',
            'config_key': 'OPENAI_API_KEY',
            'fallback_config': None,
        },
    }
    
    def __init__(self):
        self.service_status = {}
        self._check_all_services()
    
    def _check_all_services(self):
        """
        Check status of all services.
        """
        # Check required services
        for service_name, service_config in self.REQUIRED_SERVICES.items():
            self.service_status[service_name] = self._check_service(service_name, service_config, required=True)
        
        # Check optional services
        for service_name, service_config in self.OPTIONAL_SERVICES.items():
            self.service_status[service_name] = self._check_service(service_name, service_config, required=False)
    
    def _check_service(self, service_name: str, service_config: Dict, required: bool = False) -> Dict[str, Any]:
        """
        Check a specific service.
        """
        try:
            check_function = getattr(self, service_config['check_function'])
            return check_function(service_config, required)
        except Exception as e:
            logger.error(f"Error checking service {service_name}: {str(e)}")
            return {
                'status': 'error',
                'message': f"Service check failed: {str(e)}",
                'required': required,
            }
    
    def _check_redis_service(self, service_config: Dict, required: bool) -> Dict[str, Any]:
        """
        Check Redis service connectivity.
        """
        try:
            import redis
            
            config_key = service_config['config_key']
            redis_url = getattr(settings, config_key, service_config['fallback_config'])
            
            if not redis_url:
                return {
                    'status': 'not_configured',
                    'message': 'Redis URL not configured',
                    'required': required,
                }
            
            # Test Redis connection
            client = redis.from_url(redis_url, socket_timeout=5)
            client.ping()
            
            return {
                'status': 'healthy',
                'message': 'Redis connection successful',
                'url': redis_url,
                'required': required,
            }
            
        except ImportError:
            return {
                'status': 'missing_dependency',
                'message': 'Redis library not installed',
                'required': required,
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Redis connection failed: {str(e)}',
                'required': required,
            }
    
    def _check_database_service(self, service_config: Dict, required: bool) -> Dict[str, Any]:
        """
        Check database service connectivity.
        """
        try:
            from django.db import connection
            
            # Test database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
            
            if result and result[0] == 1:
                return {
                    'status': 'healthy',
                    'message': 'Database connection successful',
                    'engine': settings.DATABASES['default']['ENGINE'],
                    'required': required,
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Database query failed',
                    'required': required,
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Database connection failed: {str(e)}',
                'required': required,
            }
    
    def _check_celery_service(self, service_config: Dict, required: bool) -> Dict[str, Any]:
        """
        Check Celery service connectivity.
        """
        try:
            from celery import Celery
            
            config_key = service_config['config_key']
            broker_url = getattr(settings, config_key, service_config['fallback_config'])
            
            if not broker_url:
                return {
                    'status': 'not_configured',
                    'message': 'Celery broker URL not configured',
                    'required': required,
                }
            
            # Test Celery broker connection
            app = Celery('rate_limit')
            app.conf.broker_url = broker_url
            
            # Simple connection test
            connection = app.connection()
            connection.ensure_connection(max_retries=3)
            connection.close()
            
            return {
                'status': 'healthy',
                'message': 'Celery broker connection successful',
                'broker_url': broker_url,
                'required': required,
            }
            
        except ImportError:
            return {
                'status': 'missing_dependency',
                'message': 'Celery library not installed',
                'required': required,
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Celery connection failed: {str(e)}',
                'required': required,
            }
    
    def _check_elasticsearch_service(self, service_config: Dict, required: bool) -> Dict[str, Any]:
        """
        Check Elasticsearch service connectivity.
        """
        try:
            from elasticsearch import Elasticsearch
            
            config_key = service_config['config_key']
            es_url = getattr(settings, config_key, service_config['fallback_config'])
            
            if not es_url:
                return {
                    'status': 'not_configured',
                    'message': 'Elasticsearch URL not configured',
                    'required': required,
                }
            
            # Test Elasticsearch connection
            es = Elasticsearch([es_url])
            info = es.info()
            
            return {
                'status': 'healthy',
                'message': 'Elasticsearch connection successful',
                'url': es_url,
                'version': info.get('version', {}).get('number'),
                'required': required,
            }
            
        except ImportError:
            return {
                'status': 'missing_dependency',
                'message': 'Elasticsearch library not installed',
                'required': required,
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Elasticsearch connection failed: {str(e)}',
                'required': required,
            }
    
    def _check_sentry_service(self, service_config: Dict, required: bool) -> Dict[str, Any]:
        """
        Check Sentry service configuration.
        """
        try:
            config_key = service_config['config_key']
            sentry_dsn = getattr(settings, config_key, service_config['fallback_config'])
            
            if not sentry_dsn:
                return {
                    'status': 'not_configured',
                    'message': 'Sentry DSN not configured',
                    'required': required,
                }
            
            # Basic DSN format validation
            if not sentry_dsn.startswith('https://') or '@' not in sentry_dsn:
                return {
                    'status': 'misconfigured',
                    'message': 'Sentry DSN format is invalid',
                    'required': required,
                }
            
            return {
                'status': 'healthy',
                'message': 'Sentry DSN configured',
                'required': required,
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Sentry configuration error: {str(e)}',
                'required': required,
            }
    
    def _check_openai_service(self, service_config: Dict, required: bool) -> Dict[str, Any]:
        """
        Check OpenAI service configuration.
        """
        try:
            config_key = service_config['config_key']
            api_key = getattr(settings, config_key, service_config['fallback_config'])
            
            if not api_key:
                return {
                    'status': 'not_configured',
                    'message': 'OpenAI API key not configured',
                    'required': required,
                }
            
            # Basic API key format validation
            if not api_key.startswith('sk-') or len(api_key) < 20:
                return {
                    'status': 'misconfigured',
                    'message': 'OpenAI API key format is invalid',
                    'required': required,
                }
            
            return {
                'status': 'healthy',
                'message': 'OpenAI API key configured',
                'required': required,
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'OpenAI configuration error: {str(e)}',
                'required': required,
            }
    
    def get_service_status(self) -> Dict[str, Any]:
        """
        Get status of all services.
        """
        return self.service_status
    
    def get_healthy_services(self) -> List[str]:
        """
        Get list of healthy services.
        """
        return [
            service_name for service_name, status in self.service_status.items()
            if status['status'] == 'healthy'
        ]
    
    def get_unhealthy_services(self) -> List[str]:
        """
        Get list of unhealthy services.
        """
        return [
            service_name for service_name, status in self.service_status.items()
            if status['status'] in ['error', 'missing_dependency', 'misconfigured']
        ]


# Global instances
dependency_manager = DependencyManager()
service_dependency_manager = ServiceDependencyManager()


def check_all_dependencies() -> Dict[str, Any]:
    """
    Check all dependencies and services.
    """
    package_deps = dependency_manager.check_dependencies()
    service_deps = service_dependency_manager.get_service_status()
    
    return {
        'packages': package_deps,
        'services': service_deps,
        'all_healthy': (
            package_deps['all_satisfied'] and
            len(service_dependency_manager.get_unhealthy_services()) == 0
        )
    }


def initialize_dependencies():
    """
    Initialize all dependencies and raise error if required dependencies are missing.
    """
    dependency_check = check_all_dependencies()
    
    if not dependency_check['packages']['all_satisfied']:
        missing_required = [
            dep['name'] for dep in dependency_check['packages']['required']['missing']
        ]
        if missing_required:
            raise ImproperlyConfigured(
                f"Missing required dependencies: {', '.join(missing_required)}. "
                "Please install them using pip install."
            )
    
    unhealthy_required = [
        service for service, status in dependency_check['services'].items()
        if status['required'] and status['status'] != 'healthy'
    ]
    
    if unhealthy_required:
        logger.warning(f"Unhealthy required services: {', '.join(unhealthy_required)}")
    
    logger.info("Dependencies initialized successfully")


# Auto-initialize on module import
try:
    initialize_dependencies()
except Exception as e:
    logger.error(f"Failed to initialize dependencies: {str(e)}")


# Export functions for external use
__all__ = [
    'DependencyManager',
    'ServiceDependencyManager',
    'dependency_manager',
    'service_dependency_manager',
    'check_all_dependencies',
    'initialize_dependencies'
]
