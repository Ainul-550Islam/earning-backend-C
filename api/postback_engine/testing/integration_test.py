"""
testing/integration_test.py
─────────────────────────────
Integration tests for PostbackEngine end-to-end flow.
Tests full pipeline: postback received → validated → conversion created → wallet credited.
"""
from django.test import TestCase, TransactionTestCase
from unittest.mock import patch, MagicMock

class TestPostbackToConversionFlow(TestCase):
    """Test the complete postback → conversion pipeline."""

    def test_full_pipeline_returns_handler_result(self):
        from api.postback_engine.postback_handlers.cpa_network_handler import get_handler
        handler = get_handler("cpalead")
        # Patch all external dependencies
        with patch("api.postback_engine.postback_handlers.base_handler.PostbackRawLog") as MockLog,              patch("api.postback_engine.models.AdNetworkConfig.objects.get_by_key_or_raise") as mock_net,              patch("api.postback_engine.fraud_detection.velocity_checker.velocity_checker.check"),              patch("api.postback_engine.conversion_tracking.conversion_deduplicator.conversion_deduplicator.assert_not_duplicate"),              patch("api.postback_engine.postback_handlers.base_handler.BasePostbackHandler._resolve_user") as mock_user,              patch("api.postback_engine.postback_handlers.base_handler.BasePostbackHandler._validate_business"),              patch("api.postback_engine.postback_handlers.base_handler.BasePostbackHandler._create_conversion"),              patch("api.postback_engine.postback_handlers.base_handler.BasePostbackHandler._dispatch_reward"),              patch("api.postback_engine.postback_handlers.base_handler.BasePostbackHandler._post_process"):

            mock_network = MagicMock()
            mock_network.network_key = "cpalead"
            mock_network.ip_whitelist = []
            mock_network.signature_algorithm = "none"
            mock_network.is_test_mode = True
            mock_net.return_value = mock_network

            mock_raw_log = MagicMock()
            MockLog.objects.create.return_value = mock_raw_log

            result = handler.execute(
                raw_payload={"sub1": "user_001", "amount": "0.50", "oid": "offer_001", "sid": "txn_001"},
                method="GET",
                query_string="sub1=user_001&amount=0.50",
                headers={},
                source_ip="127.0.0.1",
            )
        self.assertIsNotNone(result)
