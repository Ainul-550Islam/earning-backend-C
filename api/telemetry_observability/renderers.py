"""
Custom DRF renderers for Telemetry Observability.

Wired in settings/base.py → REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'].
DRY: standard JSON envelope defined ONCE here — never in individual views.

Every API response has the shape:
  {
    "success": true | false,
    "data":    <payload>,      ← null on error
    "error":   null | {...},   ← null on success
    "meta": {
      "timestamp": "2024-...",
      "version":   "v1",
      "request_id": "..."
    }
  }

Views that use ResponseMixin.success_response() / error_response() already
produce the inner shape; this renderer wraps them uniformly.
"""
import json
import uuid
from datetime import datetime

from rest_framework.renderers import JSONRenderer


class TelemetryJSONRenderer(JSONRenderer):
    """
    Wraps every response in the standard telemetry envelope.
    Pagination wrappers (count, next, previous, results) pass through unchanged.
    """

    charset = 'utf-8'

    # Keys produced by paginators — don't re-wrap these
    _PAGINATION_KEYS = frozenset(['count', 'next', 'previous', 'page', 'pages', 'results'])

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response         = renderer_context.get('response')
        request          = renderer_context.get('request')
        view             = renderer_context.get('view')

        # ── Already a pagination envelope → pass through ──────────────────
        if isinstance(data, dict) and self._PAGINATION_KEYS.issubset(data):
            return super().render(data, accepted_media_type, renderer_context)

        # ── Already a telemetry envelope (from ResponseMixin) → pass through
        if isinstance(data, dict) and 'success' in data and 'data' in data:
            envelope = data
        else:
            # ── Determine success from HTTP status ────────────────────────
            status_code = getattr(response, 'status_code', 200)
            is_success  = 200 <= status_code < 400

            if is_success:
                envelope = {'success': True,  'data': data, 'error': None}
            else:
                envelope = {'success': False, 'data': None, 'error': data}

        # ── Attach meta block ─────────────────────────────────────────────
        envelope['meta'] = {
            'timestamp':  datetime.utcnow().isoformat() + 'Z',
            'version':    getattr(request, 'version', 'v1') if request else 'v1',
            'request_id': str(uuid.uuid4()),
        }

        return super().render(envelope, accepted_media_type, renderer_context)
