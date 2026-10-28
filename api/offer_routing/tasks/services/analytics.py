"""Task services stub: analytics."""
from celery import shared_task


try:
    from offer_routing.services import analytics_service
except Exception:
    analytics_service = None

# Auto-generated re-exports for task imports
try:
    from offer_routing.services import analytics as RoutingAnalyticsService
except ImportError:
    RoutingAnalyticsService = None
