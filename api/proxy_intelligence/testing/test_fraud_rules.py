"""Tests for Fraud Rule evaluation."""
from ..database_models.fraud_rule import FraudRuleManager


class TestFraudRuleEvaluation:
    def test_vpn_rule_triggers(self):
        class MockRule:
            condition_type = "vpn_detected"
            condition_value = {}
            action = "block"
            priority = 1
            name = "Block VPN"
            pk = 1

        ctx = {"is_vpn": True, "risk_score": 70}
        result = FraudRuleManager._matches(MockRule(), ctx)
        assert result is True

    def test_vpn_rule_not_triggered_clean(self):
        class MockRule:
            condition_type = "vpn_detected"
            condition_value = {}
            action = "block"
            priority = 1
            name = "Block VPN"
            pk = 1

        ctx = {"is_vpn": False, "risk_score": 10}
        result = FraudRuleManager._matches(MockRule(), ctx)
        assert result is False

    def test_risk_score_rule(self):
        class MockRule:
            condition_type = "ip_risk_score_gt"
            condition_value = {"threshold": 60}
            action = "flag"
            priority = 2
            name = "High Risk"
            pk = 2

        assert FraudRuleManager._matches(MockRule(), {"risk_score": 75}) is True
        assert FraudRuleManager._matches(MockRule(), {"risk_score": 50}) is False

    def test_tor_rule(self):
        class MockRule:
            condition_type = "tor_detected"
            condition_value = {}
            action = "block"
            priority = 1
            name = "Block Tor"
            pk = 3

        assert FraudRuleManager._matches(MockRule(), {"is_tor": True}) is True
        assert FraudRuleManager._matches(MockRule(), {"is_tor": False}) is False
