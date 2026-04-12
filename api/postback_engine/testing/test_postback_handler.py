"""testing/test_postback_handler.py — Postback handler pipeline tests."""
from django.test import TestCase
from unittest.mock import patch, MagicMock

class TestBaseHandlerPipeline(TestCase):
    def setUp(self):
        from api.postback_engine.postback_handlers.cpa_network_handler import get_handler
        self.handler = get_handler("cpalead")

    def _mock_all_steps(self, extra_patches=None):
        steps = [
            "_resolve_network","_parse_raw_payload","_create_raw_log",
            "_validate_security","_validate_schema","_check_fraud_pre",
            "_check_deduplication","_resolve_user","_validate_business",
            "_create_conversion","_dispatch_reward","_post_process",
        ]
        patches = {s: patch.object(self.handler, s) for s in steps}
        if extra_patches:
            patches.update(extra_patches)
        return patches

    def test_valid_payload_returns_result(self):
        mocks = self._mock_all_steps()
        started = [m.__enter__() for m in mocks.values()]
        result = self.handler.execute({}, "GET", "", {}, "1.2.3.4")
        [m.__exit__(None, None, None) for m in mocks.values()]
        self.assertIsNotNone(result)

    def test_network_key(self):
        self.assertEqual(self.handler.network_key, "cpalead")

    def test_handler_has_adapter(self):
        adapter = self.handler.get_adapter()
        self.assertIsNotNone(adapter)
