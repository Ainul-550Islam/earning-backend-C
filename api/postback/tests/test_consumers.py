"""
test_consumers.py – Tests for consumers.py (Django Channels WebSocket layer).
"""
from django.test import TestCase


class PostbackLogConsumerImportTests(TestCase):

    def test_consumer_module_importable(self):
        import api.postback.consumers  # noqa

    def test_postback_log_consumer_importable(self):
        from api.postback.consumers import PostbackLogConsumer
        self.assertIsNotNone(PostbackLogConsumer)

    def test_postback_analytics_consumer_importable(self):
        from api.postback.consumers import PostbackAnalyticsConsumer
        self.assertIsNotNone(PostbackAnalyticsConsumer)

    def test_postback_log_consumer_has_connect(self):
        from api.postback.consumers import PostbackLogConsumer
        self.assertTrue(hasattr(PostbackLogConsumer, 'connect'))

    def test_postback_log_consumer_has_disconnect(self):
        from api.postback.consumers import PostbackLogConsumer
        self.assertTrue(hasattr(PostbackLogConsumer, 'disconnect'))

    def test_postback_log_consumer_has_receive(self):
        from api.postback.consumers import PostbackLogConsumer
        self.assertTrue(hasattr(PostbackLogConsumer, 'receive'))

    def test_postback_analytics_consumer_has_connect(self):
        from api.postback.consumers import PostbackAnalyticsConsumer
        self.assertTrue(hasattr(PostbackAnalyticsConsumer, 'connect'))

    def test_postback_analytics_consumer_has_disconnect(self):
        from api.postback.consumers import PostbackAnalyticsConsumer
        self.assertTrue(hasattr(PostbackAnalyticsConsumer, 'disconnect'))

    def test_routing_imports_consumers(self):
        from api.postback.routing import websocket_urlpatterns
        self.assertIsInstance(websocket_urlpatterns, list)
        self.assertGreaterEqual(len(websocket_urlpatterns), 2)

    def test_routing_has_logs_pattern(self):
        from api.postback.routing import websocket_urlpatterns
        patterns = [str(p.pattern) for p in websocket_urlpatterns]
        self.assertTrue(any("logs" in p for p in patterns))

    def test_routing_has_analytics_pattern(self):
        from api.postback.routing import websocket_urlpatterns
        patterns = [str(p.pattern) for p in websocket_urlpatterns]
        self.assertTrue(any("analytics" in p for p in patterns))
