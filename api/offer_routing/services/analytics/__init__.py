"""
analytics service sub-package — loads from flat analytics.py via direct path loading.
"""
import logging, importlib.util, os, sys
logger = logging.getLogger(__name__)
_flat_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'analytics.py')
_mod_name  = 'offer_routing.services._analytics_flat'
try:
    if _mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(_mod_name, _flat_path)
        _flat = importlib.util.module_from_spec(spec)
        sys.modules[_mod_name] = _flat
        spec.loader.exec_module(_flat)
    _flat_mod = sys.modules[_mod_name]
    # Export all public names
    for _k in getattr(_flat_mod, '__all__', [k for k in vars(_flat_mod) if not k.startswith('_')]):
        globals()[_k] = getattr(_flat_mod, _k)
    # Specific known exports
    if hasattr(_flat_mod, 'RoutingAnalyticsService'):
        RoutingAnalyticsService = _flat_mod.RoutingAnalyticsService
    logger.debug("RoutingAnalyticsService loaded from flat module")
except Exception as _e:
    logger.warning("RoutingAnalyticsService flat load failed: %s", _e)
    RoutingAnalyticsService = None

# Singleton
try:
    analytics_service = RoutingAnalyticsService() if RoutingAnalyticsService else None
except Exception as _e:
    import logging; logging.getLogger(__name__).warning("analytics_service creation failed: %s", _e)
    analytics_service = None
