"""
dependencies.py
────────────────
Dependency injection helpers for Postback Engine.
Provides factory functions and DI containers for all major services.
Used by views, tasks, and management commands to get fully-configured instances.
"""
from __future__ import annotations
import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


# ── Service Getters ────────────────────────────────────────────────────────────
# These are thin wrappers that import and return the module-level singletons.
# Centralising imports here makes mocking in tests trivial.

def get_conversion_deduplicator():
    from .conversion_tracking.conversion_deduplicator import conversion_deduplicator
    return conversion_deduplicator


def get_velocity_checker():
    from .fraud_detection.velocity_checker import velocity_checker
    return velocity_checker


def get_fraud_score_calculator():
    from .fraud_detection.fraud_scoring import fraud_score_calculator
    return fraud_score_calculator


def get_click_handler():
    from .postback_handlers.click_handler import click_handler
    return click_handler


def get_conversion_handler():
    from .postback_handlers.conversion_handler import conversion_handler
    return conversion_handler


def get_retry_handler():
    from .postback_handlers.retry_handler import retry_handler
    return retry_handler


def get_queue_manager():
    from .queue_management.queue_manager import queue_manager
    return queue_manager


def get_redis_queue():
    from .queue_management.redis_queue import redis_queue
    return redis_queue


def get_batch_processor():
    from .queue_management.batch_processor import batch_processor
    return batch_processor


def get_webhook_registry():
    from .webhook_manager.webhook_registry import webhook_registry
    return webhook_registry


def get_webhook_delivery():
    from .webhook_manager.webhook_delivery import webhook_delivery
    return webhook_delivery


def get_rate_limiter():
    from .security.rate_limiter import rate_limiter
    return rate_limiter


def get_encryption_manager():
    from .security.encryption_manager import encryption_manager
    return encryption_manager


def get_ip_whitelist_manager():
    from .security.ip_whitelist import ip_whitelist_manager
    return ip_whitelist_manager


def get_signature_validator():
    from .validation_engines.signature_validator import signature_validator
    return signature_validator


def get_parameter_validator():
    from .validation_engines.parameter_validator import parameter_validator
    return parameter_validator


def get_postback_handler(network_key: str):
    """Get the appropriate postback handler for a network key."""
    from .postback_handlers.cpa_network_handler import get_handler
    return get_handler(network_key)


def get_network_adapter(network_key: str):
    """Get the appropriate network adapter for a network key."""
    from .network_adapters.adapters import get_adapter
    return get_adapter(network_key)


# ── Repository Getters ─────────────────────────────────────────────────────────

def get_network_repo():
    from .repository import network_repo
    return network_repo


def get_conversion_repo():
    from .repository import conversion_repo
    return conversion_repo


def get_click_repo():
    from .repository import click_repo
    return click_repo


def get_postback_repo():
    from .repository import postback_repo
    return postback_repo


def get_analytics_repo():
    from .repository import analytics_repo
    return analytics_repo


# ── Analytics Getters ─────────────────────────────────────────────────────────

def get_realtime_dashboard():
    from .analytics_reporting.real_time_dashboard import realtime_dashboard
    return realtime_dashboard


def get_postback_analytics():
    from .analytics_reporting.postback_analytics import postback_analytics
    return postback_analytics


# ── Django-style dependency injection for views ────────────────────────────────

class PostbackEngineDependencies:
    """
    Container for all PostbackEngine dependencies.
    Pass this to views/serializers to avoid scattered imports.

    Usage in a view:
        deps = PostbackEngineDependencies()
        result = deps.postback_handler("cpalead").execute(...)
    """

    @property
    def postback_handler(self):
        from .postback_handlers.cpa_network_handler import get_handler
        return get_handler

    @property
    def conversion_deduplicator(self):
        return get_conversion_deduplicator()

    @property
    def velocity_checker(self):
        return get_velocity_checker()

    @property
    def rate_limiter(self):
        return get_rate_limiter()

    @property
    def queue_manager(self):
        return get_queue_manager()

    @property
    def network_repo(self):
        return get_network_repo()

    @property
    def conversion_repo(self):
        return get_conversion_repo()

    @property
    def realtime_dashboard(self):
        return get_realtime_dashboard()


# Module-level DI container instance
pe_deps = PostbackEngineDependencies()
