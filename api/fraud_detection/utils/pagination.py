# =============================================================================
# fraud_detection/utils/pagination.py — DRY SHIM
# paginate_qs is exported from the main pagination.py module.
# Keep importing from here for backwards compat; source of truth is pagination.py
# =============================================================================
from __future__ import annotations
from typing import Any, Dict


def paginate_qs(qs: Any, request: Any) -> Dict:
    """
    Return pagination metadata for *qs* using query-params from *request*.
    Single implementation — imported by pagination.py for DRY re-export.
    """
    try:
        page      = max(1, int(request.query_params.get("page", 1)))
        page_size = min(100, max(1, int(request.query_params.get("page_size", 20))))
    except (TypeError, ValueError):
        page, page_size = 1, 20

    total     = qs.count()
    start     = (page - 1) * page_size
    end       = start + page_size
    num_pages = (total + page_size - 1) // page_size if total else 0

    return {
        "page":      page,
        "page_size": page_size,
        "total":     total,
        "num_pages": num_pages,
        "slice":     (start, end),
    }
