"""
alerts/services/core/__init__.py
FIXED: Replaced silent _StubSvc fallback with explicit error logging + re-raise.
Previously: if root services/core.py failed to load, all service calls silently returned
fake data (e.g. {'total_alerts': 5}) — impossible to detect in production.
Now: import failure is logged as ERROR and a clear ImportError is raised so the
Django startup process fails loudly instead of serving wrong data silently.
"""
import logging
import os
import sys
import types
import importlib.util as ilu

logger = logging.getLogger(__name__)

# ── Step 1: Import AlertProcessorService from the local alert_processor module ──
from .alert_processor import AlertProcessorService  # noqa: E402

# ── Step 2: Dynamically load the sibling services/core.py (not the package) ────
_root_py = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'core.py')

# Ensure alerts.services is in sys.modules so relative imports in core.py work
if 'alerts' not in sys.modules:
    try:
        import api.alerts as _alerts_pkg  # noqa: F401
    except ImportError:
        pass

if 'api.alerts.services' not in sys.modules:
    _svc_pkg = types.ModuleType('api.alerts.services')
    _svc_pkg.__path__ = [os.path.dirname(os.path.dirname(__file__))]
    _svc_pkg.__package__ = 'api.alerts.services'
    _svc_pkg.__name__ = 'api.alerts.services'
    sys.modules['api.alerts.services'] = _svc_pkg

_spec = ilu.spec_from_file_location(
    'api.alerts.services.core_root', _root_py, submodule_search_locations=[]
)
_root_mod = ilu.module_from_spec(_spec)
_root_mod.__package__ = 'api.alerts.services'
sys.modules['api.alerts.services.core_root'] = _root_mod

try:
    _spec.loader.exec_module(_root_mod)
    AlertGroupService = _root_mod.AlertGroupService
    AnalyticsService = _root_mod.AnalyticsService
    AlertMaintenanceService = _root_mod.AlertMaintenanceService

    # Backward-compat aliases
    LegacyAlertProcessorService = _root_mod.AlertProcessorService
    AlertProcessingService = AlertProcessorService
    AlertEscalationService = _root_mod.AlertMaintenanceService
    AlertAnalyticsService = _root_mod.AnalyticsService

    logger.debug('api.alerts.services.core: root services/core.py loaded successfully')

except Exception as _load_err:
    # CHANGED from v1: raise instead of silently substituting stub data.
    # A broken service layer must be visible at startup, not masked by fake responses.
    logger.error(
        'api.alerts.services.core: FAILED to load services/core.py — '
        'service layer is unavailable. Fix the error below before deploying.\n%s',
        _load_err,
        exc_info=True,
    )
    raise ImportError(
        f'api.alerts.services.core could not load services/core.py: {_load_err}'
    ) from _load_err


__all__ = [
    'AlertProcessorService',
    'AlertGroupService',
    'AnalyticsService',
    'AlertMaintenanceService',
    'AlertProcessingService',
    'LegacyAlertProcessorService',
    'AlertEscalationService',
    'AlertAnalyticsService',
]
