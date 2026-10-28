"""
Pagination configuration for Real-time Dashboard Backend.

OWNERSHIP FIX: page_size and max_page_size were hardcoded (20 and 100).
They are now read from app_settings so operators can tune them via
settings.REALTIME_DASHBOARD without touching source code. app_settings
itself falls back to 20 / 100 if the key is absent, so existing
deployments that don't set REALTIME_DASHBOARD are unaffected.

Apply per-viewset:
    class MyViewSet(viewsets.ModelViewSet):
        pagination_class = StandardResultsSetPagination

Or globally in settings.py:
    REST_FRAMEWORK = {
        'DEFAULT_PAGINATION_CLASS':
            'api.realtime_dashboard.pagination.StandardResultsSetPagination',
        'PAGE_SIZE': 20,
    }

Query params:
    ?page=2          → second page
    ?page_size=50    → override page size (capped at max_page_size)
"""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for all realtime_dashboard list endpoints."""

    page_size_query_param = 'page_size'

    # MYPY FIX (v9): django-rest-framework-stubs declares `page: Page |
    # None` on the base class, but DRF's actual runtime source never sets
    # a class-level default — `self.page` only exists as an instance
    # attribute once paginate_queryset() runs. Without this default, the
    # None-check in get_paginated_response() would hit AttributeError
    # instead of the intended RuntimeError on a pre-paginate call.
    page = None

    # Read from app_settings so REALTIME_DASHBOARD in settings.py can
    # override without touching this file.
    #
    # MYPY FIX (v9): DRF types page_size/max_page_size as plain writable
    # class attributes (Optional[int]), so shadowing them with a read-only
    # @property is flagged as an invalid override. The alternative —
    # moving this into get_page_size(), DRF's own extension point — was
    # tried and reverted: test_coverage_gaps.py asserts directly against
    # `pager.page_size` / `pager.max_page_size` as attributes (including
    # under a REALTIME_DASHBOARD override), and get_page_size() only runs
    # during an actual paginate_queryset() call, not on direct attribute
    # access. Keeping the property and silencing the override here is the
    # option that doesn't regress already-tested behavior.
    @property
    def page_size(self):  # type: ignore[override]
        from .app_settings import app_settings
        return app_settings.DEFAULT_PAGE_SIZE

    @property
    def max_page_size(self):  # type: ignore[override]
        from .app_settings import app_settings
        return app_settings.MAX_PAGE_SIZE

    def get_paginated_response(self, data):
        """Wrap paginated data in the app's standard response envelope."""
        # MYPY FIX (v9): self.page is Optional[Page] on the base class —
        # only None before paginate_queryset() runs. DRF never calls
        # get_paginated_response() except after a successful
        # paginate_queryset(), so this narrows an invariant that already
        # holds rather than changing behavior. `if ... raise` instead of
        # `assert` so the check isn't stripped under `python -O`
        # (also sidesteps bandit B101, which flags assert for that reason).
        if self.page is None:
            raise RuntimeError(
                'get_paginated_response() called before paginate_queryset() '
                'populated self.page'
            )
        return Response({
            'success': True,
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })
