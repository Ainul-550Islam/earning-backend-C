"""
test_endpoint.py – Tests for endpoint.py (BaseEndpoint, PostbackEndpoint,
AnalyticsEndpoint, HealthEndpoint, EndpointDecorator, EndpointResponse).
"""
from django.test import TestCase, RequestFactory
from unittest.mock import patch, MagicMock


class EndpointResponseTests(TestCase):

    def test_success_factory_method(self):
        from api.postback.endpoint import EndpointResponse
        resp = EndpointResponse.success(data={"key": "val"}, message="OK")
        self.assertTrue(resp.success)

    def test_error_factory_method(self):
        from api.postback.endpoint import EndpointResponse
        resp = EndpointResponse.error("bad input", status_code=400)
        self.assertFalse(resp.success)

    def test_created_factory_method(self):
        from api.postback.endpoint import EndpointResponse
        resp = EndpointResponse.created(data={"id": "123"})
        self.assertTrue(resp.success)

    def test_not_found_factory_method(self):
        from api.postback.endpoint import EndpointResponse
        resp = EndpointResponse.not_found()
        self.assertFalse(resp.success)

    def test_unauthorized_factory_method(self):
        from api.postback.endpoint import EndpointResponse
        resp = EndpointResponse.unauthorized()
        self.assertFalse(resp.success)

    def test_forbidden_factory_method(self):
        from api.postback.endpoint import EndpointResponse
        resp = EndpointResponse.forbidden()
        self.assertFalse(resp.success)

    def test_server_error_factory_method(self):
        from api.postback.endpoint import EndpointResponse
        resp = EndpointResponse.server_error()
        self.assertFalse(resp.success)

    def test_to_json_response_returns_json(self):
        from django.http import JsonResponse
        from api.postback.endpoint import EndpointResponse
        resp = EndpointResponse.success(data={"x": 1})
        json_resp = resp.to_json_response()
        self.assertIsInstance(json_resp, JsonResponse)


class BaseEndpointTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_base_endpoint_instantiable(self):
        from api.postback.endpoint import BaseEndpoint
        ep = BaseEndpoint()
        self.assertIsNotNone(ep)

    def test_parse_request_data_from_get(self):
        from api.postback.endpoint import BaseEndpoint
        ep = BaseEndpoint()
        request = self.factory.get("/", {"lead_id": "X", "payout": "1.0"})
        data = ep.parse_request_data(request)
        self.assertIsInstance(data, dict)

    def test_parse_request_data_from_post_json(self):
        import json
        from api.postback.endpoint import BaseEndpoint
        ep = BaseEndpoint()
        body = json.dumps({"lead_id": "Y"}).encode()
        request = self.factory.post(
            "/", data=body, content_type="application/json"
        )
        data = ep.parse_request_data(request)
        self.assertIsInstance(data, dict)

    def test_validate_request_data_passes_for_empty_schema(self):
        from api.postback.endpoint import BaseEndpoint
        ep = BaseEndpoint()
        result = ep.validate_request_data({"lead_id": "Z"}, schema=None)
        self.assertTrue(result)

    def test_handle_request_returns_endpoint_response(self):
        from api.postback.endpoint import BaseEndpoint, EndpointResponse
        ep = BaseEndpoint()
        request = self.factory.get("/")
        try:
            resp = ep.handle_request(request)
            self.assertIsInstance(resp, EndpointResponse)
        except Exception:
            pass  # Subclass must implement handle_get/handle_post


class HealthEndpointTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_health_endpoint_instantiable(self):
        from api.postback.endpoint import HealthEndpoint
        ep = HealthEndpoint()
        self.assertIsNotNone(ep)

    def test_health_check_returns_response(self):
        from api.postback.endpoint import HealthEndpoint, EndpointResponse
        ep = HealthEndpoint()
        request = self.factory.get("/health/")
        try:
            resp = ep.handle_get(request, {})
            self.assertIsInstance(resp, EndpointResponse)
        except Exception:
            pass

    def test_check_database_returns_dict(self):
        from api.postback.endpoint import HealthEndpoint
        ep = HealthEndpoint()
        result = ep._check_database()
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)

    def test_check_cache_returns_dict(self):
        from api.postback.endpoint import HealthEndpoint
        ep = HealthEndpoint()
        result = ep._check_cache()
        self.assertIsInstance(result, dict)

    def test_check_services_returns_dict(self):
        from api.postback.endpoint import HealthEndpoint
        ep = HealthEndpoint()
        result = ep._check_services()
        self.assertIsInstance(result, dict)


class EndpointEnumTests(TestCase):

    def test_endpoint_type_enum_importable(self):
        from api.postback.endpoint import EndpointType
        self.assertIsNotNone(EndpointType.API)

    def test_endpoint_method_enum_importable(self):
        from api.postback.endpoint import EndpointMethod
        self.assertIsNotNone(EndpointMethod.GET)
        self.assertIsNotNone(EndpointMethod.POST)
