"""
Views for Telemetry Observability.

Only ping_view.py lives here now — PingView/ReadinessView have no ViewSet
equivalent (they're plain liveness/readiness probes, not CRUD resources).

The rest of this package used to hold a full parallel APIView implementation
(MetricView, LogView, TraceView, AlertView, HealthView, DashboardView,
AnalyticsView) duplicating everything viewsets/ already does. urls.py
registered the DRF router for viewsets/ at the same URL prefix FIRST, so
those 7 views were permanently unreachable — removed as dead code.
"""
from .ping_view import PingView, ReadinessView

__all__ = ['PingView', 'ReadinessView']
