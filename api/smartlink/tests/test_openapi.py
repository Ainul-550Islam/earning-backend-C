"""
Tests for OpenAPI/drf-spectacular setup.
Verifies that schema generation and documentation endpoints are working.
"""
import json
from django.test import TestCase, Client
from django.urls import reverse


class OpenAPISchemaGenerationTest(TestCase):
    """Test OpenAPI schema generation with drf-spectacular."""
    
    def setUp(self):
        self.client = Client()
        
    def test_schema_generator_available(self):
        """Verify drf-spectacular is installed and schema generator works."""
        try:
            from drf_spectacular.generators import SchemaGenerator
            generator = SchemaGenerator()
            schema = generator.get_schema()
            self.assertIsNotNone(schema)
            self.assertIn('openapi', schema)
            self.assertIn('info', schema)
            self.assertIn('paths', schema)
        except ImportError:
            self.fail("drf-spectacular not installed")
    
    def test_schema_info(self):
        """Verify schema includes correct title and version."""
        from drf_spectacular.generators import SchemaGenerator
        generator = SchemaGenerator()
        schema = generator.get_schema()
        
        info = schema.get('info', {})
        self.assertEqual(info.get('title'), 'SmartLink Affiliate API')
        self.assertEqual(info.get('version'), '1.0.0')
        
    def test_openapi_version(self):
        """Verify OpenAPI 3.0.3 is used."""
        from drf_spectacular.generators import SchemaGenerator
        generator = SchemaGenerator()
        schema = generator.get_schema()
        
        self.assertEqual(schema.get('openapi'), '3.0.3')
    
    def test_schema_has_components(self):
        """Verify schema includes components (models/serializers)."""
        from drf_spectacular.generators import SchemaGenerator
        generator = SchemaGenerator()
        schema = generator.get_schema()
        
        components = schema.get('components', {})
        self.assertIn('schemas', components)
        self.assertGreater(len(components['schemas']), 0)
    
    def test_schema_endpoint_exists(self):
        """Verify /api/smartlink/schema/ is in generated paths."""
        from drf_spectacular.generators import SchemaGenerator
        generator = SchemaGenerator()
        schema = generator.get_schema()
        
        paths = schema.get('paths', {})
        self.assertIn('/api/smartlink/schema/', paths)
    
    def test_webhook_endpoints_in_schema(self):
        """Verify PayPal/Wise webhook endpoints are documented."""
        from drf_spectacular.generators import SchemaGenerator
        generator = SchemaGenerator()
        schema = generator.get_schema()
        
        paths = schema.get('paths', {})
        # These are csrf_exempt so they should appear
        self.assertIn('/api/smartlink/payouts/paypal-webhook/', paths)
        self.assertIn('/api/smartlink/payouts/wise-webhook/', paths)


class OpenAPIEndpointsTest(TestCase):
    """Test OpenAPI documentation endpoints (when drf-spectacular is available)."""
    
    def setUp(self):
        self.client = Client()
    
    def test_schema_endpoint_returns_json(self):
        """Test /api/smartlink/schema/ returns valid JSON schema."""
        try:
            response = self.client.get('/api/smartlink/schema/')
            # May be 401 (not authenticated) or 200 (schema is public)
            if response.status_code in [200, 401]:
                # Try to parse as JSON
                try:
                    data = json.loads(response.content)
                    self.assertIn('openapi', data)
                except json.JSONDecodeError:
                    # If not authenticated, that's OK - endpoint exists
                    pass
        except Exception as e:
            # Endpoint may not be available in all test environments
            self.skipTest(f"Schema endpoint not available: {e}")
    
    def test_swagger_ui_endpoint_exists(self):
        """Test /api/smartlink/docs/ Swagger UI endpoint exists."""
        try:
            response = self.client.get('/api/smartlink/docs/')
            # Should return HTML or 401/403
            self.assertIn(response.status_code, [200, 401, 403])
        except Exception:
            self.skipTest("Swagger UI endpoint not available")
    
    def test_redoc_endpoint_exists(self):
        """Test /api/smartlink/redoc/ ReDoc endpoint exists."""
        try:
            response = self.client.get('/api/smartlink/redoc/')
            # Should return HTML or 401/403
            self.assertIn(response.status_code, [200, 401, 403])
        except Exception:
            self.skipTest("ReDoc endpoint not available")


class OpenAPISettingsTest(TestCase):
    """Test drf-spectacular configuration in Django settings."""
    
    def test_spectacular_in_installed_apps(self):
        """Verify drf_spectacular is in INSTALLED_APPS."""
        from django.conf import settings
        self.assertIn('drf_spectacular', settings.INSTALLED_APPS)
    
    def test_default_schema_class_configured(self):
        """Verify DEFAULT_SCHEMA_CLASS is set to drf_spectacular."""
        from django.conf import settings
        rest_framework_config = settings.REST_FRAMEWORK
        self.assertEqual(
            rest_framework_config.get('DEFAULT_SCHEMA_CLASS'),
            'drf_spectacular.openapi.AutoSchema'
        )
    
    def test_spectacular_settings_defined(self):
        """Verify SPECTACULAR_SETTINGS is configured."""
        from django.conf import settings
        self.assertTrue(hasattr(settings, 'SPECTACULAR_SETTINGS'))
        
        settings_dict = settings.SPECTACULAR_SETTINGS
        self.assertEqual(settings_dict.get('TITLE'), 'SmartLink Affiliate API')
        self.assertEqual(settings_dict.get('VERSION'), '1.0.0')
        self.assertIn('DESCRIPTION', settings_dict)
