# engagement/dependencies.py
"""
External dependency management for engagement system.
Handles optional dependencies and feature flags based on available packages.
"""

# ── Core Django Dependencies ──────────────────────────────────────────────────
try:
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from django.core.cache import cache
    from django.db import models
    from django.utils import timezone
    DJANGO_AVAILABLE = True
except ImportError:
    DJANGO_AVAILABLE = False

# ── REST Framework Dependencies ───────────────────────────────────────────────
try:
    from rest_framework import serializers, viewsets, permissions
    from rest_framework.decorators import api_view, permission_classes
    from rest_framework.response import Response
    from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
    REST_FRAMEWORK_AVAILABLE = True
except ImportError:
    REST_FRAMEWORK_AVAILABLE = False

# ── Celery Dependencies ───────────────────────────────────────────────────────
try:
    from celery import shared_task
    from celery.schedules import crontab
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False

# ── Channels Dependencies ───────────────────────────────────────────────────────
try:
    from channels.generic.websocket import AsyncWebsocketConsumer
    from channels.db import database_sync_to_async
    from channels.layers import get_channel_layer
    CHANNELS_AVAILABLE = True
except ImportError:
    CHANNELS_AVAILABLE = False

# ── Redis Dependencies ───────────────────────────────────────────────────────────
try:
    import redis
    from redis.exceptions import ConnectionError, RedisError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# ── PostgreSQL Dependencies ────────────────────────────────────────────────────
try:
    import psycopg2
    from psycopg2.extras import execute_values
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False

# ── Analytics Dependencies ────────────────────────────────────────────────────
try:
    import pandas as pd
    import numpy as np
    from datetime import datetime, timedelta
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

# ── Email Dependencies ────────────────────────────────────────────────────────
try:
    from django.core.mail import send_mail, EmailMultiAlternatives
    from django.template.loader import render_to_string
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# ── Push Notification Dependencies ───────────────────────────────────────────────
try:
    from fcm_django import fcm
    from firebase_admin import messaging
    FCM_AVAILABLE = True
except ImportError:
    FCM_AVAILABLE = False

# ── Image Processing Dependencies ───────────────────────────────────────────────
try:
    from PIL import Image, ImageOps
    from io import BytesIO
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ── File Storage Dependencies ───────────────────────────────────────────────────
try:
    from storages.backends.s3boto3 import S3Boto3Storage
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False

# ── Webhook Dependencies ───────────────────────────────────────────────────────
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# ── Cryptography Dependencies ───────────────────────────────────────────────────
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import secrets
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

# ── API Client Dependencies ────────────────────────────────────────────────────
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# ── Monitoring Dependencies ─────────────────────────────────────────────────────
try:
    import prometheus_client
    from prometheus_client import Counter, Histogram, Gauge
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# ── Logging Dependencies ───────────────────────────────────────────────────────
try:
    import structlog
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False

# ── Testing Dependencies ───────────────────────────────────────────────────────
try:
    import pytest
    from pytest_django import TestCase
    from unittest.mock import Mock, patch
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

# ── Feature Flag Functions ─────────────────────────────────────────────────────

def is_feature_enabled(feature_name):
    """
    Check if a feature is enabled based on available dependencies.
    """
    feature_dependencies = {
        'websockets': CHANNELS_AVAILABLE,
        'real_time_notifications': CHANNELS_AVAILABLE and REDIS_AVAILABLE,
        'background_tasks': CELERY_AVAILABLE,
        'analytics': PANDAS_AVAILABLE,
        'push_notifications': FCM_AVAILABLE,
        'image_processing': PIL_AVAILABLE,
        'cloud_storage': S3_AVAILABLE,
        'webhooks': REQUESTS_AVAILABLE,
        'encryption': CRYPTOGRAPHY_AVAILABLE,
        'monitoring': PROMETHEUS_AVAILABLE,
        'structured_logging': STRUCTLOG_AVAILABLE,
        'api_client': HTTPX_AVAILABLE,
        'postgres_specific': POSTGRESQL_AVAILABLE,
        'email_notifications': EMAIL_AVAILABLE,
    }
    
    return feature_dependencies.get(feature_name, False)


def get_available_features():
    """
    Get list of all available features based on dependencies.
    """
    features = []
    feature_map = {
        'websockets': 'WebSocket Support',
        'real_time_notifications': 'Real-time Notifications',
        'background_tasks': 'Background Task Processing',
        'analytics': 'Analytics & Reporting',
        'push_notifications': 'Push Notifications',
        'image_processing': 'Image Processing',
        'cloud_storage': 'Cloud File Storage',
        'webhooks': 'Webhook Integration',
        'encryption': 'Data Encryption',
        'monitoring': 'Metrics & Monitoring',
        'structured_logging': 'Structured Logging',
        'api_client': 'HTTP API Client',
        'postgres_specific': 'PostgreSQL Features',
        'email_notifications': 'Email Notifications',
    }
    
    for feature, enabled in feature_dependencies.items():
        if enabled:
            features.append({
                'name': feature,
                'label': feature_map.get(feature, feature),
                'enabled': True
            })
    
    return features


def get_missing_dependencies():
    """
    Get list of missing optional dependencies.
    """
    missing = []
    
    dependency_map = {
        'channels': 'Django Channels (WebSockets)',
        'redis': 'Redis (Caching/Sessions)',
        'celery': 'Celery (Background Tasks)',
        'pandas': 'Pandas (Analytics)',
        'fcm-django': 'FCM Django (Push Notifications)',
        'pillow': 'Pillow (Image Processing)',
        'django-storages': 'Django Storages (Cloud Storage)',
        'requests': 'Requests (HTTP Client)',
        'cryptography': 'Cryptography (Encryption)',
        'httpx': 'HTTPX (Async HTTP Client)',
        'prometheus-client': 'Prometheus Client (Metrics)',
        'structlog': 'Structlog (Structured Logging)',
        'pytest-django': 'Pytest Django (Testing)',
        'psycopg2': 'Psycopg2 (PostgreSQL)',
    }
    
    if not CHANNELS_AVAILABLE:
        missing.append(dependency_map['channels'])
    if not REDIS_AVAILABLE:
        missing.append(dependency_map['redis'])
    if not CELERY_AVAILABLE:
        missing.append(dependency_map['celery'])
    if not PANDAS_AVAILABLE:
        missing.append(dependency_map['pandas'])
    if not FCM_AVAILABLE:
        missing.append(dependency_map['fcm-django'])
    if not PIL_AVAILABLE:
        missing.append(dependency_map['pillow'])
    if not S3_AVAILABLE:
        missing.append(dependency_map['django-storages'])
    if not REQUESTS_AVAILABLE:
        missing.append(dependency_map['requests'])
    if not CRYPTOGRAPHY_AVAILABLE:
        missing.append(dependency_map['cryptography'])
    if not HTTPX_AVAILABLE:
        missing.append(dependency_map['httpx'])
    if not PROMETHEUS_AVAILABLE:
        missing.append(dependency_map['prometheus-client'])
    if not STRUCTLOG_AVAILABLE:
        missing.append(dependency_map['structlog'])
    if not PYTEST_AVAILABLE:
        missing.append(dependency_map['pytest-django'])
    if not POSTGRESQL_AVAILABLE:
        missing.append(dependency_map['psycopg2'])
    
    return missing


def check_core_dependencies():
    """
    Check if core dependencies are available.
    """
    core_missing = []
    
    if not DJANGO_AVAILABLE:
        core_missing.append('Django')
    if not REST_FRAMEWORK_AVAILABLE:
        core_missing.append('Django REST Framework')
    
    return core_missing


# ── Dependency Warnings ───────────────────────────────────────────────────────

def log_dependency_warnings():
    """
    Log warnings for missing dependencies.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Check core dependencies
    core_missing = check_core_dependencies()
    if core_missing:
        logger.error(f"Missing core dependencies: {', '.join(core_missing)}")
        return False
    
    # Check optional dependencies
    missing = get_missing_dependencies()
    if missing:
        logger.warning(f"Missing optional dependencies: {', '.join(missing)}")
        logger.info("Some features may be limited or disabled.")
    
    # Log available features
    features = get_available_features()
    if features:
        feature_names = [f['name'] for f in features]
        logger.info(f"Available engagement features: {', '.join(feature_names)}")
    
    return True


# ── Graceful Degradation Decorators ───────────────────────────────────────────

def require_dependency(dependency_name):
    """
    Decorator to require a specific dependency for a function to work.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not is_feature_enabled(dependency_name):
                raise NotImplementedError(f"Feature '{dependency_name}' requires additional dependencies")
            return func(*args, **kwargs)
        return wrapper
    return decorator


def optional_dependency(dependency_name, fallback=None):
    """
    Decorator to make a function work with optional dependencies.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if is_feature_enabled(dependency_name):
                return func(*args, **kwargs)
            elif fallback:
                return fallback(*args, **kwargs)
            else:
                # Silently skip if no fallback provided
                return None
        return wrapper
    return decorator


# ── Dependency Information ─────────────────────────────────────────────────────

def get_dependency_info():
    """
    Get comprehensive dependency information.
    """
    return {
        'core_dependencies': {
            'django': DJANGO_AVAILABLE,
            'rest_framework': REST_FRAMEWORK_AVAILABLE,
        },
        'optional_dependencies': {
            'channels': CHANNELS_AVAILABLE,
            'redis': REDIS_AVAILABLE,
            'celery': CELERY_AVAILABLE,
            'pandas': PANDAS_AVAILABLE,
            'fcm': FCM_AVAILABLE,
            'pillow': PIL_AVAILABLE,
            's3': S3_AVAILABLE,
            'requests': REQUESTS_AVAILABLE,
            'cryptography': CRYPTOGRAPHY_AVAILABLE,
            'httpx': HTTPX_AVAILABLE,
            'prometheus': PROMETHEUS_AVAILABLE,
            'structlog': STRUCTLOG_AVAILABLE,
            'pytest': PYTEST_AVAILABLE,
            'postgresql': POSTGRESQL_AVAILABLE,
            'email': EMAIL_AVAILABLE,
        },
        'features': get_available_features(),
        'missing_dependencies': get_missing_dependencies(),
        'core_missing': check_core_dependencies(),
    }


# Auto-log dependency warnings on import
try:
    log_dependency_warnings()
except Exception:
    # Silently ignore if logging isn't available yet
    pass
