# api.cms.viewsets_new — authoritative alias for cms.viewsets_new
import sys as _sys
try:
    import importlib as _il
    _m = _il.import_module('api.cms.viewsets_new')
    _sys.modules['api.cms.viewsets_new'] = _m  # force alias (not setdefault)
    from api.cms.viewsets_new import *  # noqa
except Exception:
    pass
