# api/admin_panel/content_security.py
"""Content Security Policy (CSP) headers middleware."""
from django.utils.deprecation import MiddlewareMixin

class AdminCSPMiddleware(MiddlewareMixin):
    """Add CSP headers to admin responses."""
    CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' wss: ws:; "
        "frame-ancestors 'none';"
    )
    def process_response(self, request, response):
        if request.path.startswith('/admin') or request.path.startswith('/api/admin'):
            response['Content-Security-Policy'] = self.CSP
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response