"""
test_settings_messaging.py
============================
Validates messaging/settings_messaging.py's drop-in setting dicts against
what the actual code reads via getattr(settings, "KEY", ...).

Part 6 audit: MESSAGING_ELASTICSEARCH used to provide "ELASTICSEARCH_HOST",
but both utils/elasticsearch_setup.py and utils/search_engine.py only ever
read settings.ELASTICSEARCH_URL - a user following this template exactly
would end up with Elasticsearch silently, permanently unconfigured, with
no error anywhere. This is a cross-file naming contract that's easy to
drift again if either side changes independently without a test like this.
Place in: messaging/tests/test_settings_messaging.py
"""
from __future__ import annotations
from django.test import TestCase

from ..settings_messaging import (
    MESSAGING_INSTALLED_APPS,
    MESSAGING_REST_FRAMEWORK,
    MESSAGING_MIDDLEWARE,
    MESSAGING_CHANNEL_LAYERS,
    MESSAGING_CACHES,
    MESSAGING_ELASTICSEARCH,
)


class TestMessagingElasticsearchSettingsMatchCodeContract(TestCase):
    """
    Regression tests (Part 6 audit): the actual key names the ES-reading
    code looks for, cross-checked against what this template provides.
    """

    def test_provides_elasticsearch_url_not_host(self):
        self.assertIn("ELASTICSEARCH_URL", MESSAGING_ELASTICSEARCH)
        self.assertNotIn("ELASTICSEARCH_HOST", MESSAGING_ELASTICSEARCH)

    def test_applying_template_actually_configures_get_es_client(self):
        """
        End-to-end proof: merge this template into Django settings exactly
        as the module docstring instructs, then confirm get_es_client()
        (elasticsearch_setup.py) actually picks up the URL - not just that
        the dict has the right key name in isolation.
        """
        from ..utils.elasticsearch_setup import get_es_client
        with self.settings(**MESSAGING_ELASTICSEARCH):
            client = get_es_client()
        self.assertIsNotNone(client)

    def test_search_engine_client_also_configured(self):
        from ..utils import search_engine
        with self.settings(**MESSAGING_ELASTICSEARCH):
            client = search_engine.get_es_client()
        self.assertIsNotNone(client)


class TestMessagingMiddlewareMatchesAppsPyExpectation(TestCase):
    """
    apps.py's ready() warns if these exact dotted paths aren't present in
    settings.MIDDLEWARE - cross-checking against what this template
    actually provides catches the same class of naming-drift bug.
    """

    def test_middleware_list_matches_apps_py_required_list(self):
        required_in_apps_py = [
            "messaging.middleware.InboxUnreadCountMiddleware",
            "messaging.middleware.MessagingRequestTimingMiddleware",
            "messaging.middleware.WebSocketRateLimitMiddleware",
        ]
        for path in required_in_apps_py:
            self.assertIn(path, MESSAGING_MIDDLEWARE)


class TestMessagingRestFrameworkMatchesThrottlingPy(TestCase):
    def test_throttle_scopes_match_throttling_py_scope_attrs(self):
        from .. import throttling
        import inspect
        template_scopes = set(MESSAGING_REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].keys())
        throttle_classes = [
            obj for _, obj in inspect.getmembers(throttling, inspect.isclass)
            if hasattr(obj, "scope") and getattr(obj, "scope", None)
        ]
        used_scopes = {cls.scope for cls in throttle_classes}
        missing_from_template = used_scopes - template_scopes - {"anon", "user"}
        self.assertEqual(
            missing_from_template, set(),
            f"throttling.py declares scope(s) with no matching rate in "
            f"MESSAGING_REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']: {missing_from_template}",
        )

    def test_pagination_class_path_is_importable(self):
        import importlib
        path = MESSAGING_REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"]
        module_path, _, class_name = path.rpartition(".")
        module = importlib.import_module(module_path)
        self.assertTrue(hasattr(module, class_name))

    def test_exception_handler_path_is_importable(self):
        import importlib
        path = MESSAGING_REST_FRAMEWORK["EXCEPTION_HANDLER"]
        module_path, _, func_name = path.rpartition(".")
        module = importlib.import_module(module_path)
        self.assertTrue(hasattr(module, func_name))


class TestMessagingWsAllowedOriginsMatchesRoutingPy(TestCase):
    """MESSAGING_WS_ALLOWED_ORIGINS is documented here but consumed via
    getattr() in routing.messaging_origin_validator - confirm the
    documented default is the type that function actually expects
    (a list it can pass straight to channels' OriginValidator)."""

    def test_default_is_a_list(self):
        from ..settings_messaging import MESSAGING_WS_ALLOWED_ORIGINS
        self.assertIsInstance(MESSAGING_WS_ALLOWED_ORIGINS, list)

    def test_empty_default_falls_through_to_allowed_hosts(self):
        from django.test import override_settings
        from ..routing import messaging_origin_validator

        class _Dummy:
            async def __call__(self, scope, receive, send):
                pass

        with override_settings(MESSAGING_WS_ALLOWED_ORIGINS=[], CORS_ALLOWED_ORIGINS=None,
                                ALLOWED_HOSTS=["example.com"]):
            validator = messaging_origin_validator(_Dummy())
            self.assertEqual(validator.allowed_origins, ["example.com"])


class TestMessagingChannelLayersAndCaches(TestCase):
    def test_channel_layers_has_default_backend(self):
        self.assertIn("default", MESSAGING_CHANNEL_LAYERS)
        self.assertIn("BACKEND", MESSAGING_CHANNEL_LAYERS["default"])

    def test_caches_has_default_backend(self):
        self.assertIn("default", MESSAGING_CACHES)
        self.assertIn("BACKEND", MESSAGING_CACHES["default"])

    def test_installed_apps_includes_messaging_itself(self):
        self.assertIn("messaging", MESSAGING_INSTALLED_APPS)
