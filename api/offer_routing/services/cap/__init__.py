"""Cap service sub-package — comprehensive stubs + real-class loader."""
import logging, importlib.util, os, sys
logger = logging.getLogger(__name__)
_base = os.path.dirname(__file__)

def _load(filename, mod_name, cls_name):
    path = os.path.join(_base, filename)
    if not os.path.exists(path): return None
    try:
        if mod_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            m = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = m
            spec.loader.exec_module(m)
        cls = getattr(sys.modules[mod_name], cls_name, None)
        return cls() if cls else None
    except Exception as e:
        logger.warning("%s unavailable: %s", cls_name, e)
    return None

def _patch(instance, stub):
    for name in dir(stub):
        if not name.startswith('__') and not hasattr(instance, name):
            setattr(instance, name, getattr(stub, name))
    return instance

class _CapEnforcementStub:
    def check_cap(self, offer=None, offer_id=None, user=None, cap_id=None, context=None, **kwargs):
        return {'allowed': True, 'remaining': -1}
    def check_user_cap(self, user=None, offer=None, offer_id=None, cap_id=None, context=None, **kwargs):
        return {'allowed': True, 'remaining': -1}
    def check_global_cap(self, offer=None, offer_id=None, cap_id=None, context=None, **kwargs):
        return {'allowed': True, 'remaining': -1}
    def increment_cap(self, *a, **kw): return True
    def get_cap_status(self, *a, **kw): return {}
    def reset_cap_usage(self, *a, **kw): return {'success': True, 'reset_count': 1}
    def validate_cap_config(self, config=None):
        return {'is_valid': bool((config or {}).get('cap_value', 0) > 0), 'errors': []}
    def health_check(self): return {'status': 'degraded', 'timestamp': __import__('django.utils', fromlist=['timezone']).timezone.now().isoformat()}

class _CapResetStub:
    def reset_cap(self, cap_id=None, reason='manual'):
        return {'success': True, 'cap_id': cap_id, 'reason': reason}
    def reset_all_daily_caps(self, tenant_id=None): return {'reset_count': 0}
    def reset_user_caps(self, user_id=None, tenant_id=None): return {'reset_count': 0}
    def get_reset_history(self, *a, **kw): return []
    def schedule_reset(self, *a, **kw): return {}
    def emergency_reset(self, *a, **kw): return {'success': True}
    def health_check(self): return {'status': 'degraded', 'timestamp': __import__('django.utils', fromlist=['timezone']).timezone.now().isoformat()}


# ── Load real classes from flat service file ─────────────────────────────────
try:
    import importlib.util as _ilu_cap, os as _os_cap
    _flat_cap = _os_cap.path.join(
        _os_cap.path.dirname(_os_cap.path.dirname(__file__)), 'cap.py')
    if _os_cap.path.exists(_flat_cap):
        _spec_cap = _ilu_cap.spec_from_file_location(
            'offer_routing.services._flat_cap', _flat_cap)
        _pmod_cap = _ilu_cap.module_from_spec(_spec_cap)
        _spec_cap.loader.exec_module(_pmod_cap)
        CapEnforcementService = getattr(_pmod_cap, 'CapEnforcementService', None)
except Exception as _e_cap:
    pass

_ce_real = _load('CapEnforcementService.py', 'offer_routing.services.cap._ce', 'CapEnforcementService')
_cr_real = _load('CapResetService.py',       'offer_routing.services.cap._cr', 'CapResetService')

# Try to load real CapEnforcementService from the flat cap.py file
_flat_ce_instance = None
try:
    import importlib.util as _ilu_cap2, os as _os_cap2
    _flat_cap2 = _os_cap2.path.join(_os_cap2.path.dirname(_os_cap2.path.dirname(__file__)), 'cap.py')
    if _os_cap2.path.exists(_flat_cap2):
        _spec2 = _ilu_cap2.spec_from_file_location('offer_routing.services._flat_cap2', _flat_cap2)
        _mod2 = _ilu_cap2.module_from_spec(_spec2)
        _spec2.loader.exec_module(_mod2)
        _FlatCap = getattr(_mod2, 'CapEnforcementService', None)
        if _FlatCap:
            _flat_ce_instance = _FlatCap()
except Exception:
    pass

cap_service       = _patch(_flat_ce_instance or _ce_real or _CapEnforcementStub(), _CapEnforcementStub())
cap_reset_service = _patch(_cr_real or _CapResetStub(),       _CapResetStub())

CapEnforcementService = type(cap_service)
CapResetService       = type(cap_reset_service)

__all__ = ['CapEnforcementService','CapResetService','cap_service','cap_reset_service']
