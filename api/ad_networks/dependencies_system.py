# api/ad_networks/dependencies.py
# System-Level Dependencies Only

# ============================================================================
# CORE DJANGO DEPENDENCIES
# ============================================================================

# Django Framework
DJANGO_VERSION = ">=4.2.0,<5.0.0"
DJANGO_DEPENDENCIES = [
    f"Django{DJANGO_VERSION}",
    "django-environ>=0.11.0",
    "django-extensions>=3.2.0",
    "django-cors-headers>=4.0.0",
    "django-debug-toolbar>=4.0.0",
]

# ============================================================================
# DATABASE DEPENDENCIES
# ============================================================================

# Database Drivers
DATABASE_DEPENDENCIES = [
    "psycopg2-binary>=2.9.0",  # PostgreSQL
    "mysqlclient>=2.1.0",      # MySQL
    "sqlite3",                  # SQLite (built-in)
]

# Database Tools
DATABASE_TOOLS = [
    "django-db-connection-pool>=1.2.0",
    "django-migrations>=1.0.0",
    "django-reversion>=5.0.0",
]

# ============================================================================
# REST API DEPENDENCIES
# ============================================================================

# Django REST Framework
DRF_VERSION = ">=3.14.0"
DRF_DEPENDENCIES = [
    f"djangorestframework{DRF_VERSION}",
    "djangorestframework-simplejwt>=5.2.0",
    "djangorestframework-filters>=23.0",
    "djangorestframework-guardian>=2.4.0",
    "drf-spectacular>=0.26.0",
    "drf-extra-fields>=3.6.0",
]

# API Documentation
API_DOCS = [
    "drf-yasg>=1.21.0",
    "drf-openapi>=1.2.0",
    "redoc>=3.19.0",
]

# ============================================================================
# TASK QUEUE DEPENDENCIES
# ============================================================================

# Celery
CELERY_VERSION = ">=5.3.0"
CELERY_DEPENDENCIES = [
    f"celery{CELERY_VERSION}",
    "django-celery-beat>=2.5.0",
    "django-celery-results>=2.5.0",
    "celery-redbeat>=2.0.0",
    "kombu>=5.3.0",
]

# Message Brokers
MESSAGE_BROKERS = [
    "redis>=4.5.0",
    "amqp>=5.1.0",
    "pika>=1.3.0",
]

# ============================================================================
# CACHE DEPENDENCIES
# ============================================================================

# Cache Systems
CACHE_DEPENDENCIES = [
    "django-redis>=5.2.0",
    "django-memcached>=1.1.0",
    "django-cacheops>=7.0.0",
    "django-locmemcache>=1.0.0",
]

# Redis
REDIS_DEPENDENCIES = [
    "redis>=4.5.0",
    "hiredis>=2.2.0",
    "redis-py-cluster>=2.1.0",
]

# ============================================================================
# AUTHENTICATION DEPENDENCIES
# ============================================================================

# Authentication
AUTH_DEPENDENCIES = [
    "django-oauth-toolkit>=1.7.0",
    "django-allauth>=0.54.0",
    "django-rest-auth>=0.1.0",
    "social-auth-app-django>=5.2.0",
]

# JWT
JWT_DEPENDENCIES = [
    "PyJWT>=2.8.0",
    "cryptography>=41.0.0",
    "python-jose>=3.3.0",
]

# ============================================================================
# VALIDATION DEPENDENCIES
# ============================================================================

# Validation Libraries
VALIDATION_DEPENDENCIES = [
    "validators>=0.20.0",
    "email-validator>=2.0.0",
    "phone-iso3166>=0.8.0",
    "python-dateutil>=2.8.0",
]

# Schema Validation
SCHEMA_DEPENDENCIES = [
    "jsonschema>=4.17.0",
    "pydantic>=2.0.0",
    "marshmallow>=3.19.0",
]

# ============================================================================
# FILE HANDLING DEPENDENCIES
# ============================================================================

# File Processing
FILE_DEPENDENCIES = [
    "Pillow>=10.0.0",
    "python-magic>=0.4.27",
    "python-docx>=0.8.11",
    "PyPDF2>=3.0.0",
    "openpyxl>=3.1.0",
]

# Storage
STORAGE_DEPENDENCIES = [
    "django-storages>=1.13.0",
    "boto3>=1.26.0",
    "google-cloud-storage>=2.8.0",
    "azure-storage-blob>=12.17.0",
]

# ============================================================================
# MONITORING DEPENDENCIES
# ============================================================================

# Logging
LOGGING_DEPENDENCIES = [
    "structlog>=23.1.0",
    "sentry-sdk>=1.25.0",
    "loguru>=0.7.0",
    "python-json-logger>=2.0.0",
]

# Monitoring
MONITORING_DEPENDENCIES = [
    "django-prometheus>=2.3.0",
    "psutil>=5.9.0",
    "memory-profiler>=0.61.0",
    "py-spy>=0.3.0",
]

# Metrics
METRICS_DEPENDENCIES = [
    "statsd>=4.0.0",
    "graphite-api>=1.1.0",
    "datadog>=0.47.0",
    "newrelic>=9.0.0",
]

# ============================================================================
# TESTING DEPENDENCIES
# ============================================================================

# Testing Framework
TESTING_DEPENDENCIES = [
    "pytest>=7.3.0",
    "pytest-django>=4.5.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.11.0",
    "factory-boy>=3.2.0",
]

# Test Tools
TEST_TOOLS = [
    "faker>=18.9.0",
    "responses>=0.23.0",
    "freezegun>=1.2.0",
    "testfixtures>=7.2.0",
]

# ============================================================================
# SECURITY DEPENDENCIES
# ============================================================================

# Security Libraries
SECURITY_DEPENDENCIES = [
    "cryptography>=41.0.0",
    "bcrypt>=4.0.0",
    "passlib>=1.7.0",
    "django-ratelimit>=4.1.0",
    "django-axes>=6.1.0",
]

# Scanning
SECURITY_SCANNING = [
    "bandit>=1.7.0",
    "safety>=2.3.0",
    "pip-audit>=2.5.0",
    "semgrep>=1.34.0",
]

# ============================================================================
# UTILITIES DEPENDENCIES
# ============================================================================

# Utility Libraries
UTILITY_DEPENDENCIES = [
    "python-dateutil>=2.8.0",
    "pytz>=2023.3",
    "requests>=2.31.0",
    "urllib3>=2.0.0",
    "httpx>=0.24.0",
]

# Data Processing
DATA_PROCESSING = [
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "openpyxl>=3.1.0",
    "xlrd>=2.0.0",
    "xlsxwriter>=3.1.0",
]

# ============================================================================
# DEVELOPMENT DEPENDENCIES
# ============================================================================

# Development Tools
DEV_DEPENDENCIES = [
    "black>=23.7.0",
    "isort>=5.12.0",
    "flake8>=6.0.0",
    "mypy>=1.5.0",
    "pre-commit>=3.3.0",
]

# Code Quality
CODE_QUALITY = [
    "pylint>=2.17.0",
    "bandit>=1.7.0",
    "vulture>=2.7.0",
    "coverage>=7.3.0",
]

# ============================================================================
# DOCUMENTATION DEPENDENCIES
# ============================================================================

# Documentation Tools
DOC_DEPENDENCIES = [
    "Sphinx>=7.1.0",
    "sphinx-rtd-theme>=1.3.0",
    "sphinx-autodoc-typehints>=1.24.0",
    "myst-parser>=2.0.0",
]

# Markdown Tools
MARKDOWN_TOOLS = [
    "markdown>=3.4.0",
    "mkdocs>=1.5.0",
    "mkdocs-material>=9.1.0",
    "mkdocs-mermaid2-plugin>=1.1.0",
]

# ============================================================================
# DEPLOYMENT DEPENDENCIES
# ============================================================================

# Deployment Tools
DEPLOYMENT_DEPENDENCIES = [
    "gunicorn>=21.2.0",
    "uvicorn>=0.22.0",
    "supervisor>=4.2.0",
    "nginx>=1.24.0",
]

# Containerization
CONTAINER_DEPENDENCIES = [
    "docker>=6.1.0",
    "docker-compose>=1.29.0",
    "kubernetes>=27.2.0",
    "helm>=3.12.0",
]

# ============================================================================
# ANALYTICS DEPENDENCIES
# ============================================================================

# Analytics Libraries
ANALYTICS_DEPENDENCIES = [
    "matplotlib>=3.7.0",
    "seaborn>=0.12.0",
    "plotly>=5.15.0",
    "bokeh>=3.2.0",
]

# Data Visualization
DATA_VIZ = [
    "dash>=2.11.0",
    "streamlit>=1.24.0",
    "jupyter>=1.0.0",
    "ipython>=8.14.0",
]

# ============================================================================
# COMMUNICATION DEPENDENCIES
# ============================================================================

# Email
EMAIL_DEPENDENCIES = [
    "django-anymail>=10.2.0",
    "sendgrid>=6.10.0",
    "mailchimp-marketing>=3.0.0",
    "postmark>=3.8.0",
]

# SMS
SMS_DEPENDENCIES = [
    "twilio>=8.8.0",
    "nexmo>=3.0.0",
    "plivo>=3.18.0",
    "messagebird>=9.0.0",
]

# Push Notifications
PUSH_DEPENDENCIES = [
    "pyfcm>=1.5.0",
    "onesignal-sdk>=1.0.0",
    "firebase-admin>=6.0.0",
    "apns2>=0.4.0",
]

# ============================================================================
# MACHINE LEARNING DEPENDENCIES
# ============================================================================

# ML Libraries
ML_DEPENDENCIES = [
    "scikit-learn>=1.3.0",
    "tensorflow>=2.13.0",
    "torch>=2.0.0",
    "xgboost>=1.7.0",
]

# Data Science
DATA_SCIENCE = [
    "jupyter>=1.0.0",
    "ipykernel>=6.24.0",
    "notebook>=7.0.0",
    "nbconvert>=7.7.0",
]

# ============================================================================
# WEBHOOK DEPENDENCIES
# ============================================================================

# Webhook Libraries
WEBHOOK_DEPENDENCIES = [
    "django-webhooks>=1.2.0",
    "svix>=1.7.0",
    "hookdeck>=0.8.0",
    "ngrok>=0.4.0",
]

# Event Streaming
EVENT_DEPENDENCIES = [
    "kafka-python>=2.0.0",
    "pulsar-client>=3.2.0",
    "nats-py>=2.6.0",
    "redis-py>=4.5.0",
]

# ============================================================================
# SEARCH DEPENDENCIES
# ============================================================================

# Search Libraries
SEARCH_DEPENDENCIES = [
    "elasticsearch>=8.8.0",
    "opensearch-py>=2.3.0",
    "algoliasearch>=3.0.0",
    "whoosh>=2.7.0",
]

# Full-text Search
FULLTEXT_DEPENDENCIES = [
    "django-haystack>=3.2.0",
    "django-elasticsearch-dsl>=7.3.0",
    "django-postgres-fulltext-search>=1.1.0",
]

# ============================================================================
# GEOLOCATION DEPENDENCIES
# ============================================================================

# Geolocation Libraries
GEO_DEPENDENCIES = [
    "geopy>=2.3.0",
    "geoip2>=4.7.0",
    "django-countries>=7.5.0",
    "pycountry>=22.3.0",
]

# Mapping
MAPPING_DEPENDENCIES = [
    "folium>=0.14.0",
    "geopandas>=0.13.0",
    "shapely>=2.0.0",
    "cartopy>=0.21.0",
]

# ============================================================================
# COMBINED DEPENDENCY LISTS
# ============================================================================

# Core Dependencies
CORE_DEPENDENCIES = (
    DJANGO_DEPENDENCIES +
    DATABASE_DEPENDENCIES +
    DRF_DEPENDENCIES +
    CELERY_DEPENDENCIES +
    CACHE_DEPENDENCIES +
    AUTH_DEPENDENCIES
)

# Production Dependencies
PRODUCTION_DEPENDENCIES = (
    CORE_DEPENDENCIES +
    MESSAGE_BROKERS +
    REDIS_DEPENDENCIES +
    STORAGE_DEPENDENCIES +
    MONITORING_DEPENDENCIES +
    SECURITY_DEPENDENCIES
)

# Development Dependencies
DEVELOPMENT_DEPENDENCIES = (
    CORE_DEPENDENCIES +
    TESTING_DEPENDENCIES +
    DEV_DEPENDENCIES +
    CODE_QUALITY +
    DOC_DEPENDENCIES
)

# Optional Dependencies
OPTIONAL_DEPENDENCIES = {
    'analytics': ANALYTICS_DEPENDENCIES,
    'ml': ML_DEPENDENCIES,
    'search': SEARCH_DEPENDENCIES,
    'geo': GEO_DEPENDENCIES,
    'webhooks': WEBHOOK_DEPENDENCIES,
    'monitoring': MONITORING_DEPENDENCIES,
    'testing': TESTING_DEPENDENCIES,
    'docs': DOC_DEPENDENCIES,
    'dev': DEV_DEPENDENCIES,
}

# ============================================================================
# DEPENDENCY VALIDATION
# ============================================================================

class DependencyValidator:
    """Validate system dependencies"""
    
    REQUIRED_PACKAGES = [
        'Django',
        'djangorestframework',
        'celery',
        'redis',
        'Pillow',
        'requests',
    ]
    
    OPTIONAL_PACKAGES = [
        'boto3',
        'psycopg2-binary',
        'sentry-sdk',
        'pytest-django',
    ]
    
    @classmethod
    def validate_dependencies(cls):
        """Validate required dependencies"""
        missing_packages = []
        
        for package in cls.REQUIRED_PACKAGES:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        return missing_packages
    
    @classmethod
    def check_optional_dependencies(cls):
        """Check optional dependencies"""
        available_packages = []
        
        for package in cls.OPTIONAL_PACKAGES:
            try:
                __import__(package)
                available_packages.append(package)
            except ImportError:
                pass
        
        return available_packages
    
    @classmethod
    def get_dependency_info(cls):
        """Get dependency information"""
        return {
            'required': cls.REQUIRED_PACKAGES,
            'optional': cls.OPTIONAL_PACKAGES,
            'core': CORE_DEPENDENCIES,
            'production': PRODUCTION_DEPENDENCIES,
            'development': DEVELOPMENT_DEPENDENCIES,
            'optional_groups': OPTIONAL_DEPENDENCIES,
        }

# ============================================================================
# EXPORT DEPENDENCIES
# ============================================================================

__all__ = [
    # Core dependencies
    'CORE_DEPENDENCIES',
    'PRODUCTION_DEPENDENCIES',
    'DEVELOPMENT_DEPENDENCIES',
    'OPTIONAL_DEPENDENCIES',
    
    # Dependency groups
    'DJANGO_DEPENDENCIES',
    'DATABASE_DEPENDENCIES',
    'DRF_DEPENDENCIES',
    'CELERY_DEPENDENCIES',
    'CACHE_DEPENDENCIES',
    'AUTH_DEPENDENCIES',
    
    # Validation
    'DependencyValidator',
]
