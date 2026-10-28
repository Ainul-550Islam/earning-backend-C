# api/admin_panel/response_formatter.py
"""Standard API response formatter middleware and mixin."""
from django.utils import timezone


class StandardResponseMiddleware:
    """Wrap all admin API responses in standard format."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Only wrap JSON responses from admin-panel endpoints
        if (request.path.startswith('/api/admin') and
                getattr(response, 'content_type', '').startswith('application/json')):
            import json
            try:
                data = json.loads(response.content)
                if not isinstance(data, dict) or 'success' not in data:
                    wrapped = {
                        'success':   response.status_code < 400,
                        'data':      data,
                        'timestamp': timezone.now().isoformat(),
                        'status':    response.status_code,
                    }
                    response.content = json.dumps(wrapped, default=str)
                    response['Content-Length'] = len(response.content)
            except Exception:
                pass
        return response


def success_response(data=None, message: str = '', status: int = 200, meta: dict = None) -> dict:
    return {
        'success': True, 'data': data, 'message': message,
        'meta': meta or {}, 'timestamp': timezone.now().isoformat(),
    }


def error_response(message: str, errors: list = None, code: str = '', status: int = 400) -> dict:
    return {
        'success': False, 'message': message,
        'errors': errors or [], 'code': code,
        'timestamp': timezone.now().isoformat(),
    }