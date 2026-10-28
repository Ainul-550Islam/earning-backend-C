# api/support/schemas.py
try:
    from drf_spectacular.utils import extend_schema, OpenApiParameter
    from drf_spectacular.types import OpenApiTypes

    TICKET_LIST_PARAMS = [
        OpenApiParameter('status',   OpenApiTypes.STR,  description='Filter by status'),
        OpenApiParameter('priority', OpenApiTypes.STR,  description='Filter by priority'),
        OpenApiParameter('category', OpenApiTypes.STR,  description='Filter by category'),
        OpenApiParameter('search',   OpenApiTypes.STR,  description='Full-text search'),
        OpenApiParameter('escalated',OpenApiTypes.BOOL, description='Escalated only'),
        OpenApiParameter('page',     OpenApiTypes.INT,  description='Page number'),
        OpenApiParameter('per_page', OpenApiTypes.INT,  description='Items per page'),
    ]
except ImportError:
    extend_schema = lambda *a, **kw: (lambda f: f)
    TICKET_LIST_PARAMS = []