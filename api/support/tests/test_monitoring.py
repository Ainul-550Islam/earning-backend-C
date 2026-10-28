# api/support/tests/test_monitoring.py
"""Tests for monitoring module."""
from django.test import TestCase


class MonitorTest(TestCase):
    def test_get_health_status(self):
        from api.support.monitoring import monitor
        health = monitor.get_health_status()
        self.assertIn('status', health)
        self.assertIn('checks', health)
        self.assertIn('timestamp', health)
        self.assertIn('database', health['checks'])

    def test_database_is_healthy(self):
        from api.support.monitoring import monitor
        health = monitor.get_health_status()
        self.assertTrue(health['checks']['database']['healthy'])

    def test_get_metrics(self):
        from api.support.monitoring import monitor
        metrics = monitor.get_metrics()
        self.assertIn('timestamp', metrics)
        self.assertIn('tickets', metrics)
        self.assertIn('online_agents', metrics)

    def test_feature_flags_all(self):
        from api.support.feature_flags import get_all
        flags = get_all()
        self.assertIsInstance(flags, dict)
        self.assertIn('SUPPORT_CHAT_ENABLED', flags)

    def test_feature_flag_chat_enabled(self):
        from api.support.feature_flags import chat_enabled, enable, disable, reset
        reset('SUPPORT_CHAT_ENABLED')
        self.assertTrue(chat_enabled())  # Default is True