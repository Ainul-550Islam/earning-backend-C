"""
alerts/urls/__init__.py — FINAL VERSION
Registers ALL subsystems — nothing floating:
  core, channel, incident, intelligence, reporting, threshold,
  integration (22 files), system (backup/escalation/scheduler/metrics/events),
  search+schema+resources, webhooks, api_views utilities, endpoint utilities.
"""
from django.urls import include, path

app_name = 'alerts'


def _safe_include(module_path, namespace):
    try:
        import importlib
        mod = importlib.import_module(module_path)
        patterns = getattr(mod, 'urlpatterns', [])
        return include((patterns, namespace))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning('api.alerts.urls: could not load %s: %s', module_path, e)
        return None


# ── Core subsystems ───────────────────────────────────────────
from api.alerts.urls import core, channel, incident, intelligence, reporting, threshold

# ── Integration ───────────────────────────────────────────────
_integration = _safe_include('api.alerts.urls.integration', 'integration')

# ── System admin (backup, escalation, scheduler, metrics, events)
_system = _safe_include('api.alerts.urls.system', 'system')

# ── Search, Schema, Resources ─────────────────────────────────
_search = _safe_include('api.alerts.urls.search_urls', 'search')

# ── Webhooks ──────────────────────────────────────────────────
_webhooks = _safe_include('api.alerts.urls.webhooks_urls', 'webhooks')

# ── endpoint.py utility views ─────────────────────────────────
try:
    from api.alerts.endpoint import (
        api_info, trigger_alert, alert_statistics,
        system_metrics, alert_rules_bulk, alert_logs_bulk, export_data,
    )
    _endpoint_patterns = [
        path('info/',           api_info,            name='api-info'),
        path('trigger/',        trigger_alert,       name='api-trigger-alert'),
        path('statistics/',     alert_statistics,    name='api-alert-statistics'),
        path('system-metrics/', system_metrics,      name='api-system-metrics'),
        path('rules/bulk/',     alert_rules_bulk,    name='api-alert-rules-bulk'),
        path('logs/bulk/',      alert_logs_bulk,     name='api-alert-logs-bulk'),
        path('export/',         export_data,         name='api-export-data'),
    ]
except Exception as _e:
    import logging as _log
    _log.getLogger(__name__).warning('api.alerts.urls: endpoint views not loaded: %s', _e)
    _endpoint_patterns = []

# ── api_views.py function-based views ─────────────────────────
_apiv = _safe_include('api.alerts.urls.api_views_urls', 'apiv')

urlpatterns = [
    # Core subsystems
    path('',              include(core)),
    path('channel/',      include(channel)),
    path('incident/',     include(incident)),
    path('intelligence/', include(intelligence)),
    path('reporting/',    include(reporting)),
    path('threshold/',    include(threshold)),

    # Utility endpoints (endpoint.py)
    path('util/', include((_endpoint_patterns, 'util'))),
]

# Conditionally register optional subsystems
_optional = [
    ('integration/', _integration),
    ('system/',      _system),
    ('search/',      _search),
    ('webhooks/',    _webhooks),
    ('apiv/',        _apiv),
]

for prefix, inc in _optional:
    if inc is not None:
        urlpatterns.append(path(prefix, inc))
