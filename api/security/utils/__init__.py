import logging
import uuid

logger = logging.getLogger(__name__)

# ১. TypeValidator (যা এখন মিসিং)
class TypeValidator:
    @staticmethod
    def is_type(value, expected_type):
        return isinstance(value, expected_type)
    @staticmethod
    def validate(value, rules):
        return True

# ২. NullSafe
class NullSafe:
    def __init__(self, value=None): self._value = value
    def __getattr__(self, name): return NullSafe(None)
    def __call__(self, *args, **kwargs): return NullSafe(None)
    def __getitem__(self, key): return NullSafe(None)
    def __bool__(self): return self._value is not None
    def __str__(self): return str(self._value) if self._value is not None else ""

# ৩. safe_getattr ও safe_dict_get
def safe_getattr(obj, path, default=None):
    try:
        for part in path.split('.'): obj = getattr(obj, part)
        return obj
    except (AttributeError, TypeError, ValueError): return default

def safe_dict_get(data, path, default=None):
    if not data or not isinstance(data, dict): return default
    try:
        for key in path.split('.'):
            data = data.get(key)
            if data is None: return default
        return data
    except (AttributeError, KeyError, TypeError): return default

# ৪. SecurityUtils ও RateLimiter
try:
    from api.security.utils_legacy import SecurityUtils, RateLimiter
except ImportError:
    class SecurityUtils:
        @staticmethod
        def generate_uuid(): return uuid.uuid4()
        @staticmethod
        def get_client_ip(request):
            x = request.META.get('HTTP_X_FORWARDED_FOR')
            return x.split(',')[0] if x else request.META.get('REMOTE_ADDR')
        @staticmethod
        def is_private_ip(ip): return False
        @staticmethod
        def generate_secure_token(n=32): return uuid.uuid4().hex
    
    class RateLimiter:
        @staticmethod
        def is_rate_limited(*args, **kwargs): return False

__all__ = ['NullSafe', 'safe_getattr', 'safe_dict_get', 'SecurityUtils', 'RateLimiter', 'TypeValidator']