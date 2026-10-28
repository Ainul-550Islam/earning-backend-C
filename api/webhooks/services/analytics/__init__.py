"""Analytics Services Module

This module contains services for webhook analytics and monitoring.
"""

# BUG FIX: __all__ named these classes but nothing here actually imported
# them, so `from ..services.analytics import HealthMonitorService` (etc.)
# silently resolved to the *submodule* of the same name instead of the
# class inside it (Python's import system falls back to importing a
# same-named submodule when a package doesn't already have that attribute -
# it does not consult __all__ for this). Every caller across admin/, tasks/,
# management commands, and viewsets that then did `HealthMonitorService()`
# was calling a module object, not the class - crashing with "'module'
# object is not callable" every time. Actually importing the classes here
# fixes every one of those call sites without touching them individually.
from .AgingService import AgingService
from .HealthMonitorService import HealthMonitorService
from .RateLimiterService import RateLimiterService
from .WebhookAnalyticsService import WebhookAnalyticsService

# Export all analytics services for easy access
__all__ = [
    'AgingService',
    'WebhookAnalyticsService',
    'RateLimiterService',
    'HealthMonitorService',
]