# fraud_detection/utils/__init__.py
"""
Shared utilities for the fraud_detection app.

Import from here to avoid reaching into sub-modules directly:

    from api.fraud_detection.utils import ok, err, FraudBaseView, FraudAdminView
    from api.fraud_detection.utils import paginate_qs, lazy_repo, lazy_detector
    from api.fraud_detection.utils import cache_append, get_or_none
"""
from .response    import ok, err
from .pagination  import paginate_qs
from .base_views  import FraudBaseView, FraudAdminView
from .helpers     import (
    lazy_repo,
    lazy_detector,
    lazy_service,
    record_stat,
    cache_append,
    get_or_none,
)

__all__ = [
    "ok", "err",
    "paginate_qs",
    "FraudBaseView", "FraudAdminView",
    "lazy_repo", "lazy_detector", "lazy_service", "record_stat",
    "cache_append", "get_or_none",
]
