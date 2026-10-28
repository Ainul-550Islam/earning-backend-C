# services/intelligence/ — this package directory shadows the sibling
# module alerts/services/intelligence.py (Python always prefers a
# same-named package over a same-named .py file in the same parent
# directory), so that flat file is unreachable via a normal
# `import api.alerts.services.intelligence`. We load it manually here and
# re-export its service classes, giving it a proper __package__ so its
# own internal relative imports (`from ..models.intelligence import ...`,
# `from .intelligence.alert_intelligence import AlertIntelligence`)
# resolve exactly as they would if it were imported normally.
#
# FIXED: Replaced silent stub-instance fallback with explicit error logging +
# re-raise (matching services/core/__init__.py's fix). Previously: if root
# services/intelligence.py failed to load, every service name below was
# silently rebound to a bare, method-less instance (type('X', (), {})()) and
# only a warning was logged — any caller doing AlertCorrelationService().correlate(...)
# would get a confusing AttributeError far from the real cause instead of a
# clear failure at startup.

import importlib.util as _ilu
import os as _os
import sys as _sys
import logging as _logging

_logger = _logging.getLogger(__name__)

_root_py = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'intelligence.py')
_mod_name = 'api.alerts.services._intelligence_flatfile'
_spec = _ilu.spec_from_file_location(_mod_name, _root_py)
_mod = _ilu.module_from_spec(_spec)
_mod.__package__ = 'api.alerts.services'  # so `from ..X import Y` / `from .intelligence.Y import Z` resolve correctly
try:
    _sys.modules[_mod_name] = _mod
    _spec.loader.exec_module(_mod)
    AlertCorrelationService = getattr(_mod, 'AlertCorrelationService', None)
    AlertPredictionService = getattr(_mod, 'AlertPredictionService', None)
    AnomalyDetectionService = getattr(_mod, 'AnomalyDetectionService', None)
    NoiseFilterService = getattr(_mod, 'NoiseFilterService', None)
    RootCauseAnalysisService = getattr(_mod, 'RootCauseAnalysisService', None)
    IntelligenceIntegrationService = getattr(_mod, 'IntelligenceIntegrationService', None)
except Exception as _e:
    _sys.modules.pop(_mod_name, None)
    _logger.error(
        'api.alerts.services.intelligence: FAILED to load services/intelligence.py — '
        'intelligence service layer is unavailable. Fix the error below before deploying.\n%s',
        _e,
        exc_info=True,
    )
    raise ImportError(
        f'api.alerts.services.intelligence could not load services/intelligence.py: {_e}'
    ) from _e

# Also expose the AlertIntelligence submodule's class directly from this
# package, since intelligence.py itself delegates to it.
from .alert_intelligence import AlertIntelligence

__all__ = [
    'AlertCorrelationService', 'AlertPredictionService', 'AnomalyDetectionService',
    'NoiseFilterService', 'RootCauseAnalysisService', 'IntelligenceIntegrationService',
    'AlertIntelligence',
]
