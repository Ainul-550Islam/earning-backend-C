"""
Fallback service sub-package.

Loads FallbackService from the flat fallback.py module using direct path
loading to avoid the flat-file vs package shadowing issue.
"""
import logging
import importlib.util
import os
import sys

logger = logging.getLogger(__name__)

_flat_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fallback.py')
_mod_name  = 'offer_routing.services._fallback_flat'

try:
    if _mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(_mod_name, _flat_path)
        _flat = importlib.util.module_from_spec(spec)
        sys.modules[_mod_name] = _flat
        spec.loader.exec_module(_flat)
    FallbackService = sys.modules[_mod_name].FallbackService
    fallback_service = FallbackService()
    logger.debug("FallbackService loaded from flat module")
except Exception as _e:
    logger.warning("FallbackService flat load failed (%s) — using stub", _e)

    class FallbackService:
        """Stub FallbackService — real module unavailable."""
        def get_fallback_offers(self, user=None, context=None, limit=10, tenant_id=None, user_id=None, fallback_rules=None, **kwargs):
            return []
        def validate_fallback_rule(self, rule): return {'is_valid': True, 'errors': []}
        def validate_empty_result_handler(self, h): return {'is_valid': True, 'errors': []}
        def health_check(self): return {'status': 'degraded', 'timestamp': __import__('django.utils', fromlist=['timezone']).timezone.now().isoformat()}
        def get_metrics(self): return {}

    fallback_service = FallbackService()


# ── Load real classes from flat service file ─────────────────────────────────
try:
    import importlib.util as _ilu_fal, os as _os_fal
    _flat_fal = _os_fal.path.join(
        _os_fal.path.dirname(_os_fal.path.dirname(__file__)), 'fallback.py')
    if _os_fal.path.exists(_flat_fal):
        _spec_fal = _ilu_fal.spec_from_file_location(
            'offer_routing.services._flat_fal', _flat_fal)
        _pmod_fal = _ilu_fal.module_from_spec(_spec_fal)
        _spec_fal.loader.exec_module(_pmod_fal)
        FallbackService = getattr(_pmod_fal, 'FallbackService', None)
except Exception as _e_fal:
    pass

__all__ = ['FallbackService', 'fallback_service']
