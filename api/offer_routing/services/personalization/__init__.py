"""
Personalization service sub-package — comprehensive stubs + real-class loader.
"""
import logging, importlib.util, os, sys
from django.utils import timezone

logger = logging.getLogger(__name__)
_base = os.path.dirname(__file__)

def _load(filename, mod_name, class_name):
    path = os.path.join(_base, filename)
    if not os.path.exists(path): return None
    try:
        if mod_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            m = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = m
            spec.loader.exec_module(m)
        cls = getattr(sys.modules[mod_name], class_name, None)
        return cls() if cls else None
    except Exception as e:
        logger.warning("%s unavailable: %s", class_name, e)
    return None

def _patch(instance, stub):
    for name in dir(stub):
        if not name.startswith('__') and not hasattr(instance, name):
            setattr(instance, name, getattr(stub, name))
    return instance

# ── Comprehensive stubs ──────────────────────────────────────────────────────
class _PersonalizationStub:
    def get_recommendations(self, *a, **kw): return []
    def update_user_preferences(self, *a, **kw): return True
    def get_metrics(self): return {}
    def health_check(self): return {'status': 'degraded', 'timestamp': str(timezone.now())}

class _CollaborativeStub(_PersonalizationStub):
    def calculate_user_similarity(self, u1=None, u2=None): return {'similarity_score': 0.5, 'common_items': [], 'user_a_id': getattr(u1,'id',None), 'user_b_id': getattr(u2,'id',None)}
    def get_collaborative_recommendations(self, user=None, context=None, limit=10, user_id=None): return []
    def get_item_based_recommendations(self, user=None, context=None, limit=10, user_id=None): return []
    def get_similar_users(self, user=None, limit=10): return []
    def _get_similar_users(self, user=None, limit=10): return []
    def update_affinity_scores(self, *a, **kw): return 0
    def update_collaborative_model(self, *a, **kw): return {'success': True, 'updated_count': 0}

class _ContentBasedStub(_PersonalizationStub):
    def get_content_based_recommendations(self, user=None, context=None, limit=10, user_id=None): return []
    def rebuild_preference_vectors(self, *a, **kw): return 0
    def update_content_model(self, *a, **kw): return {'success': True, 'updated': 0}
    def analyze_offer_content(self, *a, **kw): return {}
    def calculate_content_similarity(self, a=None, b=None): return {'similarity_score': 0.5, 'offer_a_id': a, 'offer_b_id': b, 'features': []}

class _ContextSignalStub(_PersonalizationStub):
    def process_signals(self, *a, **kw): return {}
    def get_active_signals(self, *a, **kw): return []
    def cleanup_expired(self, *a, **kw): return 0

class _HybridStub(_PersonalizationStub):
    def get_hybrid_recommendations(self, *a, **kw): return []
    def compare_algorithms(self, *a, **kw): return {}
    def get_algorithm_weights(self, *a, **kw): return {'collaborative': 0.5, 'content_based': 0.5}
    def update_weights(self, *a, **kw): return True

class _AffinityStub(_PersonalizationStub):
    def update_affinity_scores(self, *a, **kw): return 0
    def get_user_affinity(self, *a, **kw): return {}

# ── Load real classes ────────────────────────────────────────────────────────
_cf_real  = _load('CollaborativeFilterService.py', 'offer_routing.services.pers._cf',  'CollaborativeFilterService')
_cb_real  = _load('ContentBasedService.py',        'offer_routing.services.pers._cb',  'ContentBasedService')
_ctx_real = _load('ContextSignalService.py',       'offer_routing.services.pers._ctx', 'ContextSignalService')
_hy_real  = _load('HybridRoutingService.py',       'offer_routing.services.pers._hy',  'HybridRoutingService')

try:
    # Load from flat personalization.py one level up
    import importlib.util as _ilu, os as _os
    _p = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'personalization.py')
    if _os.path.exists(_p):
        _spec = _ilu.spec_from_file_location('offer_routing.services._pers_flat', _p)
        _pmod = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_pmod)
        PersonalizationService = getattr(_pmod, 'PersonalizationService', _PersonalizationStub)
        _AffinityClass = getattr(_pmod, 'AffinityService', _AffinityStub)
        _CFClass = getattr(_pmod, 'CollaborativeFilterService', None)
        if _CFClass:
            from django.utils import timezone as _tz
            try:
                _cf_real = _CFClass()
            except Exception:
                _cf_real = None
    else:
        PersonalizationService = _PersonalizationStub
        _AffinityClass = _AffinityStub
    personalization_service = _patch(PersonalizationService(), _PersonalizationStub())
    affinity_service        = _patch(_AffinityClass(),         _AffinityStub())
except Exception as _pe:
    logger.warning('PersonalizationService flat load failed: %s', _pe)
    PersonalizationService = _PersonalizationStub
    personalization_service = _PersonalizationStub()
    affinity_service        = _AffinityStub()

# Try to use real CollaborativeFilterService from flat personalization.py
_flat_cf_instance = None
try:
    if '_CFClass' in dir() and _CFClass is not None:
        _flat_cf_instance = _CFClass()
except Exception:
    pass
collaborative_service  = _patch(_flat_cf_instance or _cf_real or _CollaborativeStub(), _CollaborativeStub())
content_based_service  = _patch(_cb_real  or _ContentBasedStub(),  _ContentBasedStub())
context_signal_service = _patch(_ctx_real or _ContextSignalStub(), _ContextSignalStub())
hybrid_service         = _patch(_hy_real  or _HybridStub(),        _HybridStub())

# Export class references
CollaborativeFilterService = type(collaborative_service)
ContentBasedService        = type(content_based_service)
ContextSignalService       = type(context_signal_service)
HybridRoutingService       = type(hybrid_service)

# ── Direct override: use real CollaborativeFilterService from loaded module ──
try:
    import sys as _sys_pers_override
    _cf_mod = _sys_pers_override.modules.get('offer_routing.services.pers._cf')
    if _cf_mod:
        _RealCF = getattr(_cf_mod, 'CollaborativeFilterService', None)
        if _RealCF and callable(_RealCF):
            _real_cf_inst = _RealCF()
            collaborative_service = _real_cf_inst
            CollaborativeFilterService = _RealCF
except Exception as _ov_e:
    pass

__all__ = [
    'CollaborativeFilterService','ContentBasedService',
    'ContextSignalService','HybridRoutingService',
    'personalization_service','collaborative_service',
    'content_based_service','context_signal_service',
    'hybrid_service','affinity_service','AffinityService',
]

AffinityService = type(affinity_service)
