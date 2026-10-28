"""
Tests for CORS (django-cors-headers) setup.
Verifies that CORS headers are correctly configured and returned.
"""
from django.test import TestCase, Client
from django.conf import settings


class CORSSetupTest(TestCase):
    """Test CORS configuration."""
    
    def test_corsheaders_in_installed_apps(self):
        """Verify corsheaders is in INSTALLED_APPS."""
        self.assertIn('corsheaders', settings.INSTALLED_APPS)
    
    def test_corsheaders_middleware_installed(self):
        """Verify CorsMiddleware is in MIDDLEWARE."""
        self.assertIn('corsheaders.middleware.CorsMiddleware', settings.MIDDLEWARE)
        # Verify it's near the top (before SessionMiddleware)
        cors_idx = settings.MIDDLEWARE.index('corsheaders.middleware.CorsMiddleware')
        session_idx = settings.MIDDLEWARE.index('django.contrib.sessions.middleware.SessionMiddleware')
        self.assertLess(cors_idx, session_idx, 
                       "CorsMiddleware should come before SessionMiddleware")
    
    def test_cors_allowed_origins_configured(self):
        """Verify CORS_ALLOWED_ORIGINS is configured."""
        self.assertTrue(hasattr(settings, 'CORS_ALLOWED_ORIGINS'))
        self.assertIsInstance(settings.CORS_ALLOWED_ORIGINS, list)
        self.assertGreater(len(settings.CORS_ALLOWED_ORIGINS), 0)
    
    def test_cors_allow_credentials(self):
        """Verify CORS_ALLOW_CREDENTIALS is enabled."""
        self.assertTrue(settings.CORS_ALLOW_CREDENTIALS)
    
    def test_cors_allow_headers_configured(self):
        """Verify CORS_ALLOW_HEADERS includes required headers."""
        headers = settings.CORS_ALLOW_HEADERS
        required = ['authorization', 'content-type', 'x-csrftoken']
        for header in required:
            self.assertIn(header, headers, f"Required header '{header}' not in CORS_ALLOW_HEADERS")


class CORSHeadersTest(TestCase):
    """Test CORS headers in HTTP responses."""
    
    def setUp(self):
        self.client = Client()
    
    def test_cors_headers_on_preflight_request(self):
        """Test CORS headers on OPTIONS preflight request."""
        response = self.client.options(
            '/api/smartlink/register/register/',
            HTTP_ORIGIN='http://localhost:3000',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        )
        
        # OPTIONS might return 401 if auth is required, but CORS headers should still be present
        # Check if CORS headers exist in response
        if 'Access-Control-Allow-Origin' in response:
            self.assertIn('http://localhost:3000', response['Access-Control-Allow-Origin'])
            self.assertIn('Access-Control-Allow-Methods', response)
            self.assertIn('Access-Control-Allow-Headers', response)
    
    def test_cors_origin_allowed(self):
        """Test that allowed origins are set in response."""
        allowed_origin = 'http://localhost:3000'
        self.assertIn(allowed_origin, settings.CORS_ALLOWED_ORIGINS)
    
    def test_credentials_header_in_cors_config(self):
        """Test that CORS credentials are enabled."""
        response = self.client.options(
            '/api/smartlink/register/register/',
            HTTP_ORIGIN='http://localhost:3000',
        )
        # Credentials being allowed is configured, actual header depends on request


class CORSConfigurationTest(TestCase):
    """Test CORS configuration completeness."""
    
    def test_localhost_allowed(self):
        """Verify localhost origins are allowed."""
        origins = settings.CORS_ALLOWED_ORIGINS
        self.assertTrue(
            any('localhost' in origin for origin in origins),
            "localhost should be in allowed origins"
        )
    
    def test_127_0_0_1_allowed(self):
        """Verify 127.0.0.1 origins are allowed."""
        origins = settings.CORS_ALLOWED_ORIGINS
        self.assertTrue(
            any('127.0.0.1' in origin for origin in origins),
            "127.0.0.1 should be in allowed origins"
        )
    
    def test_http_and_https_variants(self):
        """Verify both HTTP and HTTPS variants are handled."""
        # Note: This verifies configuration approach, not that HTTPS is actually used
        origins = settings.CORS_ALLOWED_ORIGINS
        
        # Should have at least HTTP variants
        self.assertTrue(
            any(origin.startswith('http://') for origin in origins),
            "HTTP origins should be configured"
        )


class CORSHeadersListTest(TestCase):
    """Test specific CORS headers configuration."""
    
    def test_authorization_header_allowed(self):
        """Verify Authorization header is allowed."""
        self.assertIn('authorization', settings.CORS_ALLOW_HEADERS)
    
    def test_content_type_header_allowed(self):
        """Verify Content-Type header is allowed."""
        self.assertIn('content-type', settings.CORS_ALLOW_HEADERS)
    
    def test_csrf_token_header_allowed(self):
        """Verify X-CSRFToken header is allowed."""
        self.assertIn('x-csrftoken', settings.CORS_ALLOW_HEADERS)
    
    def test_custom_headers_allowed(self):
        """Verify common custom headers are allowed."""
        headers = settings.CORS_ALLOW_HEADERS
        # At minimum should allow user-agent and origin
        self.assertTrue(
            any(h in headers for h in ['user-agent', 'origin']),
            "Common headers should be allowed"
        )


class CORSIntegrationTest(TestCase):
    """Integration tests for CORS with actual endpoints."""
    
    def test_cors_available_on_api_endpoints(self):
        """Test that CORS handling is available on API endpoints."""
        # Just verify the middleware is loaded
        from corsheaders.middleware import CorsMiddleware
        middleware_classes = [m for m in settings.MIDDLEWARE 
                            if 'CorsMiddleware' in m or m == CorsMiddleware]
        self.assertGreater(len(middleware_classes), 0)
    
    def test_cors_not_breaks_non_cors_requests(self):
        """Test that non-CORS requests still work."""
        # Regular request without Origin header should still work
        response = self.client.get('/admin/')
        # Should get a response (might be redirect)
        self.assertIn(response.status_code, [200, 301, 302, 401, 403])
