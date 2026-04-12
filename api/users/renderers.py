"""
api/users/renderers.py
Custom JSON response format — সব response এক format-এ আসবে
"""
import json
from rest_framework.renderers import JSONRenderer


class UserJSONRenderer(JSONRenderer):
    """
    Standard response format:
    {
        "success": true,
        "data": { ... },
        "message": "Profile updated successfully",
        "meta": { "request_id": "...", "timestamp": "..." }
    }
    """
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if renderer_context is None:
            return super().render(data, accepted_media_type, renderer_context)

        response = renderer_context.get('response')
        if response is None:
            return super().render(data, accepted_media_type, renderer_context)

        import uuid
        from django.utils import timezone

        status_code = response.status_code
        success     = 200 <= status_code < 300

        # Error response (exceptions)-এর জন্য
        if not success and isinstance(data, dict) and 'error_code' in data:
            formatted = {
                'success':    False,
                'error':      True,
                'error_code': data.get('error_code'),
                'message':    data.get('message', 'An error occurred.'),
                'data':       None,
            }
        elif not success:
            formatted = {
                'success': False,
                'error':   True,
                'message': data if isinstance(data, str) else 'An error occurred.',
                'data':    data if not isinstance(data, str) else None,
            }
        else:
            # Success response
            formatted = {
                'success': True,
                'data':    data,
                'message': self._extract_message(data),
                'meta': {
                    'request_id': str(uuid.uuid4())[:8],
                    'timestamp':  timezone.now().isoformat(),
                },
            }

        return json.dumps(formatted, ensure_ascii=False).encode(self.charset)

    def _extract_message(self, data):
        """Response data-তে message থাকলে তুলে আনো"""
        if isinstance(data, dict):
            return data.pop('message', None)
        return None
