# engagement/utils/decorators.py
import functools
import logging
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def engagement_endpoint(func):
    """
    Wraps a view function to catch EngagementError subclasses
    and return clean 400 JSON responses, while logging 500s.
    """
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        from ..exceptions import EngagementError
        try:
            return func(request, *args, **kwargs)
        except EngagementError as exc:
            return Response(
                {"success": False, "error": str(exc.detail), "code": exc.default_code},
                status=exc.status_code,
            )
        except Exception as exc:
            logger.exception("Unhandled error in %s: %s", func.__name__, exc)
            return Response(
                {"success": False, "error": "An unexpected error occurred."},
                status=500,
            )
    return wrapper
