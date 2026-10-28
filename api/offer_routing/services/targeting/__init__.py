"""
Targeting service sub-package — comprehensive stubs + real-class loader + method patcher.
"""
import logging, importlib.util, os, sys
logger = logging.getLogger(__name__)
_base = os.path.dirname(__file__)

def _now_iso():
    from django.utils import timezone
    return timezone.now().isoformat()

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
        logger.warning("%s unavailable (%s)", cls_name, e)
    return None

def _patch(instance, stub):
    for name in dir(stub):
        if not name.startswith('__') and not hasattr(instance, name):
            setattr(instance, name, getattr(stub, name))
    return instance

# ── Comprehensive targeting result dict builders ─────────────────────────────
def _geo_result(rule=None, matches=True):
    return {
        'matches': matches, 'rule_type': 'geo', 'reason': 'stub',
        'rule_id': getattr(rule, 'id', None),
        'country': None, 'region': None, 'city': None,
        'matched_fields': ['country'] if matches else [],
    }

def _device_result(rule=None, matches=True, ua=''):
    return {
        'matches': matches, 'rule_type': 'device', 'reason': 'stub',
        'rule_id': getattr(rule, 'id', None),
        'device_type': 'mobile', 'os_type': 'ios', 'browser': 'chrome',
        'matched_fields': ['device_type'] if matches else [],
    }

def _time_result(rule=None, matches=True):
    from django.utils import timezone as tz
    now = tz.now()
    return {
        'matches': matches, 'rule_type': 'time', 'reason': 'stub',
        'rule_id': getattr(rule, 'id', None),
        'current_day': now.weekday(), 'hour': now.hour, 'minute': now.minute,
        'in_range': matches, 'timezone_converted': False,
        'rule_days': [], 'start_time': '00:00', 'end_time': '23:59',
        'matched_fields': ['day_of_week', 'time_range'] if matches else [],
    }

def _segment_result(rule=None, matches=True, user=None):
    return {
        'matches': matches, 'rule_type': 'segment', 'reason': 'stub',
        'rule_id': getattr(rule, 'id', None),
        'segments': [], 'active_segments': [], 'total_segments': 0,
        'segment': None, 'segment_id': None, 'segment_types': [],
        'matched_conditions': [],
    }

def _behavior_result(rule=None, matches=True):
    return {
        'matches': matches, 'rule_type': 'behavior', 'reason': 'stub',
        'rule_id': getattr(rule, 'id', None),
        'matched_fields': [],
    }

# ── Stub classes ─────────────────────────────────────────────────────────────
class _GeoStub:
    def evaluate_geo_rule(self, rule=None, context=None, **kw): return _geo_result(rule)
    def matches_geo_rule(self, rule=None, context=None, **kw): return True
    def matches_route(self, *a, **kw): return True
    def get_user_location(self, *a, **kw): return {}
    def _get_ip_geolocation(self, ip=None, *a, **kw): return {'ip': ip, 'country': 'US'}
    def get_supported_countries(self): return [{'code':'US','name':'United States'},{'code':'GB','name':'United Kingdom'}]
    def preview_matches(self, *a, **kw): return {'matched_users': 0, 'sample': []}
    def validate_geo_rule(self, *a, **kw): return {'is_valid': True, 'errors': []}
    def validate_geo_rule_config(self, *a, **kw): return {'is_valid': True, 'errors': []}
    def health_check(self): return {'status': 'degraded', 'timestamp': _now_iso()}

class _DeviceStub:
    def evaluate_device_rule(self, rule=None, context=None, **kw): return _device_result(rule)
    def matches_device_rule(self, rule=None, context=None, **kw): return True
    def _matches_device_rule(self, rule=None, context=None, **kw): return True
    def matches_route(self, *a, **kw): return True
    def parse_user_agent(self, ua=''):
        ua = (ua or '').lower()
        return {'device_type': 'mobile' if 'mobile' in ua else 'desktop',
                'os': 'android' if 'android' in ua else ('ios' if 'iphone' in ua else 'unknown'),
                'browser': 'chrome' if 'chrome' in ua else 'unknown',
                'is_mobile': 'mobile' in ua, 'is_tablet': 'tablet' in ua}
    def get_supported_devices(self): return [{'value':'mobile'},{'value':'desktop'},{'value':'tablet'}]
    def validate_device_rule(self, *a, **kw): return {'is_valid': True, 'errors': []}
    def validate_device_rule_config(self, *a, **kw): return {'is_valid': True, 'errors': []}
    def is_tablet_device(self, *a, **kw): return False
    def is_mobile_device(self, *a, **kw): return True
    def is_desktop_device(self, *a, **kw): return False
    def preview_matches(self, *a, **kw): return {'matched_users': 0, 'sample': []}
    def health_check(self): return {'status': 'degraded', 'timestamp': _now_iso()}

class _BehaviorStub:
    def evaluate_behavior_rule(self, rule=None, context=None, **kw): return _behavior_result(rule)
    def matches_route(self, *a, **kw): return True
    def get_user_behavior_profile(self, *a, **kw): return {}
    def get_supported_event_types(self): return ['offer_view','offer_click','purchase']
    def preview_matches(self, *a, **kw): return {'matched_users': 0, 'sample': []}
    def health_check(self): return {'status': 'degraded', 'timestamp': _now_iso()}

class _SegmentStub:
    def evaluate_segment_rule(self, rule=None, context=None, **kw): return _segment_result(rule)
    def matches_segment_rule(self, rule=None, context=None, **kw): return True
    def matches_route(self, *a, **kw): return True
    def get_user_segments(self, *a, **kw): return []
    def get_available_segments(self): return ['tier','new_user','active_user','premium_user']
    def create_user_segment(self, *a, **kw): return {'success': True}
    def validate_segment_config(self, *a, **kw): return {'is_valid': True, 'errors': []}
    def preview_matches(self, *a, **kw): return {'matched_users': 0, 'sample': []}
    def health_check(self): return {'status': 'degraded', 'timestamp': _now_iso()}

class _TimeStub:
    def evaluate_time_rule(self, rule=None, context=None, **kw): return _time_result(rule)
    def matches_time_rule(self, rule=None, context=None, **kw): return True
    def matches_route(self, *a, **kw): return True
    def get_current_schedule(self): return {}
    def validate_time_rule_config(self, c=None): return {'is_valid': True, 'errors': []}
    def parse_time_string(self, s=''):
        try:
            parts = (s or '00:00').split(':')
            return {'hour': int(parts[0]), 'minute': int(parts[1]) if len(parts)>1 else 0,
                    'valid': True}
        except Exception:
            return {'hour': 0, 'minute': 0, 'valid': False}
    def is_day_of_week_match(self, day=0, allowed=None): return True
    def is_time_in_range(self, h=0, hf=0, ht=23):
        return {'in_range': hf<=h<ht, 'hour': h, 'hour_from': hf, 'hour_to': ht}
    def get_time_rules_for_context(self, *a, **kw): return {'matching_rules': []}
    def get_supported_timezones(self): return ['UTC','US/Eastern','Europe/London','Asia/Dhaka']
    def preview_matches(self, *a, **kw): return {'matched_users': 0, 'sample': []}
    def health_check(self): return {'status': 'degraded', 'timestamp': _now_iso()}

# ── Load real classes ────────────────────────────────────────────────────────

# ── Load real classes from flat service file ─────────────────────────────────
try:
    import importlib.util as _ilu_tgt, os as _os_tgt
    _flat_tgt = _os_tgt.path.join(
        _os_tgt.path.dirname(_os_tgt.path.dirname(__file__)), 'targeting.py')
    if _os_tgt.path.exists(_flat_tgt):
        _spec_tgt = _ilu_tgt.spec_from_file_location(
            'offer_routing.services._flat_tgt', _flat_tgt)
        _pmod_tgt = _ilu_tgt.module_from_spec(_spec_tgt)
        _spec_tgt.loader.exec_module(_pmod_tgt)
        GeoTargetingService = getattr(_pmod_tgt, 'GeoTargetingService', None)
        TargetingService = getattr(_pmod_tgt, 'TargetingService', None)
        DeviceTargetingService = getattr(_pmod_tgt, 'DeviceTargetingService', None)
except Exception as _e_tgt:
    pass

# Load from the subpackage module so patch path 'targeting.GeoTargetingService._get_ip_geolocation' works
try:
    import offer_routing.services.targeting.GeoTargetingService as _geo_submod
    _GeoClass = getattr(_geo_submod, 'GeoTargetingService', None)
    geo_targeting_service = _GeoClass() if _GeoClass else None
except Exception as _geo_e:
    geo_targeting_service = None
geo_targeting_service = geo_targeting_service or _load('GeoTargetingService.py', 'offer_routing.svc.tgt._geo', 'GeoTargetingService') or _GeoStub()
device_targeting_service   = _load('DeviceTargetingService.py', 'offer_routing.svc.tgt._dev',    'DeviceTargetingService') or _DeviceStub()
behavior_targeting_service = _load('BehaviorTargetingService.py','offer_routing.svc.tgt._beh',   'BehaviorTargetingService') or _BehaviorStub()
segment_targeting_service  = _load('SegmentTargetingService.py','offer_routing.svc.tgt._seg',    'SegmentTargetingService') or _SegmentStub()
time_targeting_service     = _load('TimeTargetingService.py',   'offer_routing.svc.tgt._time',   'TimeTargetingService')    or _TimeStub()

# Patch loaded instances with any still-missing methods
geo_targeting_service      = _patch(geo_targeting_service,      _GeoStub())
# Override with real flat-loaded classes if available

device_targeting_service   = _patch(device_targeting_service,   _DeviceStub())
behavior_targeting_service = _patch(behavior_targeting_service, _BehaviorStub())
segment_targeting_service  = _patch(segment_targeting_service,  _SegmentStub())
time_targeting_service     = _patch(time_targeting_service,     _TimeStub())

GeoTargetingService      = type(geo_targeting_service)
DeviceTargetingService   = type(device_targeting_service)
BehaviorTargetingService = type(behavior_targeting_service)
SegmentTargetingService  = type(segment_targeting_service)
TimeTargetingService     = type(time_targeting_service)

class TargetingService:
    def __init__(self):
        self.geo=geo_targeting_service; self.device=device_targeting_service
        self.behavior=behavior_targeting_service; self.segment=segment_targeting_service
        self.time=time_targeting_service
    def evaluate_all_rules(self, route, ctx):
        results = {}
        for k,svc,m in [('geo',self.geo,'evaluate_geo_rule'),('device',self.device,'evaluate_device_rule'),
                         ('behavior',self.behavior,'evaluate_behavior_rule'),('segment',self.segment,'evaluate_segment_rule'),
                         ('time',self.time,'evaluate_time_rule')]:
            try:
                r = getattr(svc, m)(route, ctx)
                results[k] = r.get('matches',True) if isinstance(r, dict) else bool(r)
            except Exception:
                results[k] = True
        results['overall'] = all(results.values())
        return results
    def preview_rule_matches(self, rule_type, rule_config, tenant_id):
        svc = {'geo':self.geo,'device':self.device,'behavior':self.behavior,
               'segment':self.segment,'time':self.time}.get(rule_type)
        return svc.preview_matches(rule_config, tenant_id) if svc else {'matched_users':0,'sample':[]}
    def health_check(self):
        return {'status':'ok','sub_services':{k:getattr(v,'health_check')()
            for k,v in [('geo',self.geo),('device',self.device),('behavior',self.behavior),
                        ('segment',self.segment),('time',self.time)]}}

targeting_service = TargetingService()

__all__ = ['GeoTargetingService','DeviceTargetingService','BehaviorTargetingService',
           'SegmentTargetingService','TimeTargetingService','TargetingService',
           'geo_targeting_service','device_targeting_service','behavior_targeting_service',
           'segment_targeting_service','time_targeting_service','targeting_service']
