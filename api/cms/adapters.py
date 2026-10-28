# api.cms.adapters — authoritative alias for cms.adapters
import sys as _sys
try:
    import importlib as _il
    _m = _il.import_module('api.cms.adapters')
    _sys.modules['api.cms.adapters'] = _m  # force alias (not setdefault)
    from api.cms.adapters import *  # noqa
except Exception:
    pass
