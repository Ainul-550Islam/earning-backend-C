"""
api/monetization_tools/schemas.py
====================================
OpenAPI schema customisation for drf-spectacular.
Add to settings: SPECTACULAR_SETTINGS or import in urls.py.
"""

try:
    from drf_spectacular.utils import (
        extend_schema, extend_schema_view, OpenApiParameter,
        OpenApiExample, OpenApiResponse,
    )
    from drf_spectacular.types import OpenApiTypes
    HAS_SPECTACULAR = True
except ImportError:
    HAS_SPECTACULAR = False

    # Graceful no-op decorators if drf-spectacular not installed
    def extend_schema(*args, **kwargs):
        def decorator(func): return func
        return decorator if args and callable(args[0]) else decorator

    def extend_schema_view(**kwargs):
        def decorator(cls): return cls
        return decorator

    class OpenApiParameter:
        pass

    class OpenApiTypes:
        DATE = STR = INT = None


# ---------------------------------------------------------------------------
# Common parameters
# ---------------------------------------------------------------------------

PARAM_START_DATE = OpenApiParameter(
    name='start', location=OpenApiParameter.QUERY,
    description='Start date (YYYY-MM-DD)', required=False,
    type=OpenApiTypes.DATE if HAS_SPECTACULAR else str,
)

PARAM_END_DATE = OpenApiParameter(
    name='end', location=OpenApiParameter.QUERY,
    description='End date (YYYY-MM-DD)', required=False,
    type=OpenApiTypes.DATE if HAS_SPECTACULAR else str,
)

PARAM_PAGE = OpenApiParameter(
    name='page', location=OpenApiParameter.QUERY,
    description='Page number', required=False,
    type=OpenApiTypes.INT if HAS_SPECTACULAR else int,
)

PARAM_PAGE_SIZE = OpenApiParameter(
    name='page_size', location=OpenApiParameter.QUERY,
    description='Results per page (max 100)', required=False,
    type=OpenApiTypes.INT if HAS_SPECTACULAR else int,
)

PARAM_COUNTRY = OpenApiParameter(
    name='country', location=OpenApiParameter.QUERY,
    description='ISO 3166-1 alpha-2 country code', required=False,
    type=OpenApiTypes.STR if HAS_SPECTACULAR else str,
)

PARAM_OFFER_TYPE = OpenApiParameter(
    name='type', location=OpenApiParameter.QUERY,
    description='Offer type filter (survey, app_install, video, ...)', required=False,
    type=OpenApiTypes.STR if HAS_SPECTACULAR else str,
)

PARAM_SCOPE = OpenApiParameter(
    name='scope', location=OpenApiParameter.QUERY,
    description='Leaderboard scope (global, country, weekly, monthly)', required=False,
    type=OpenApiTypes.STR if HAS_SPECTACULAR else str,
)

PARAM_BOARD_TYPE = OpenApiParameter(
    name='type', location=OpenApiParameter.QUERY,
    description='Leaderboard type (earnings, referrals, offers, streak)', required=False,
    type=OpenApiTypes.STR if HAS_SPECTACULAR else str,
)
