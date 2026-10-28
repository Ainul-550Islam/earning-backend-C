"""
NEW FILE — Centralized request-context extraction.

DRY FIX: This logic was previously duplicated nearly verbatim in:
  - decorators.py        (feature_flag, variant_assignment, track_conversion, flag_value)
  - middleware.py         (FeatureFlagMiddleware)
  - viewsets/feature_flag_viewset.py (check action)
That's 50+ duplicated lines across 4+ call sites. Any future change (e.g.
adding "country" or "plan_tier" to context) had to be made in every copy.
Now there is exactly one implementation.
"""
from typing import Any, Dict, Optional


class ContextExtractor:
    """Builds a flag-evaluation context dictionary from various sources."""

    @staticmethod
    def from_request(request) -> Dict[str, Any]:
        """
        Extract a flag evaluation context from a Django/DRF request.

        Args:
            request: Django HttpRequest or DRF Request

        Returns:
            Context dictionary with user_id, email, username, session_id,
            ip_address and user_agent (any unavailable values are omitted).
        """
        context: Dict[str, Any] = {}

        user = getattr(request, 'user', None)
        if user is not None and getattr(user, 'is_authenticated', False):
            context['user_id'] = str(getattr(user, 'id', '') or '')
            context['email'] = getattr(user, 'email', '') or ''
            context['username'] = getattr(user, 'username', '') or ''

        session = getattr(request, 'session', None)
        if session is not None:
            context['session_id'] = getattr(session, 'session_key', None) or ''

        meta = getattr(request, 'META', {}) or {}
        context['ip_address'] = meta.get('REMOTE_ADDR', '')
        context['user_agent'] = meta.get('HTTP_USER_AGENT', '')

        return context

    @staticmethod
    def from_view_args(args) -> Dict[str, Any]:
        """
        Extract context from decorator *args, where args[0] may be a View
        instance exposing `.request`, or a raw HttpRequest itself.

        This replaces the repeated pattern:
            context = {}
            if args and hasattr(args[0], 'request'):
                request = args[0].request
                context = {...}
        found in every decorator in decorators.py.
        """
        if not args:
            return {}

        candidate = args[0]
        request = getattr(candidate, 'request', None)
        if request is None and hasattr(candidate, 'META'):
            # args[0] is itself an HttpRequest (e.g. function-based view)
            request = candidate

        if request is None:
            return {}

        return ContextExtractor.from_request(request)

    @staticmethod
    def from_query_params(query_params) -> Dict[str, Any]:
        """
        Build a minimal context from explicit query parameters, used by
        endpoints like `/flags/{id}/check/?user_id=...&email=...`.
        """
        return {
            'user_id': query_params.get('user_id', ''),
            'email': query_params.get('email', ''),
            'session_id': query_params.get('session_id', ''),
        }
