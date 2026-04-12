"""testing/test_validators.py — Validation engine tests."""
from django.test import TestCase
from decimal import Decimal

class TestIPValidator(TestCase):
    def setUp(self):
        from api.postback_engine.validation_engines.ip_validator import ip_validator
        self.v = ip_validator

    def test_valid_ipv4(self): self.assertTrue(self.v.validate_format("192.168.1.1"))
    def test_valid_ipv6(self): self.assertTrue(self.v.validate_format("::1"))
    def test_invalid_ip(self): self.assertFalse(self.v.validate_format("not_ip"))
    def test_cidr_in_whitelist(self): self.assertTrue(self.v.is_in_whitelist("10.0.0.5", ["10.0.0.0/8"]))
    def test_not_in_whitelist(self): self.assertFalse(self.v.is_in_whitelist("8.8.8.8", ["192.168.0.0/24"]))
    def test_empty_whitelist_allows_all(self): self.assertTrue(self.v.is_in_whitelist("1.2.3.4", []))

class TestAmountValidator(TestCase):
    def setUp(self):
        from api.postback_engine.validation_engines.amount_validator import amount_validator
        self.v = amount_validator

    def test_valid_string_decimal(self): self.assertEqual(self.v.parse_and_validate("0.50"), Decimal("0.50"))
    def test_comma_separated(self): self.assertEqual(self.v.parse_and_validate("1,000.00"), Decimal("1000.00"))
    def test_invalid_raises(self):
        from api.postback_engine.exceptions import SchemaValidationException
        with self.assertRaises(SchemaValidationException): self.v.parse_and_validate("abc")

class TestStatusValidator(TestCase):
    def setUp(self):
        from api.postback_engine.validation_engines.status_validator import status_validator
        self.v = status_validator

    def test_approved_values(self):
        for s in ["1", "approved", "success", "paid", "confirmed"]:
            self.assertEqual(self.v.normalise(s), "approved", f"Failed for: {s}")

    def test_rejected_values(self):
        for s in ["0", "rejected", "failed", "chargeback", "reversed"]:
            self.assertEqual(self.v.normalise(s), "rejected", f"Failed for: {s}")

    def test_empty_defaults_approved(self): self.assertEqual(self.v.normalise(""), "approved")

class TestParameterValidator(TestCase):
    def setUp(self):
        from api.postback_engine.validation_engines.parameter_validator import parameter_validator
        self.v = parameter_validator

    def test_valid_id_passes(self): self.assertEqual(self.v.validate_id_field("lead_123"), "lead_123")
    def test_currency_uppercased(self): self.assertEqual(self.v.validate_currency("usd"), "USD")
    def test_invalid_currency_raises(self):
        from api.postback_engine.exceptions import SchemaValidationException
        with self.assertRaises(SchemaValidationException): self.v.validate_currency("US")

class TestSchemas(TestCase):
    def test_cpalead_schema_valid_payload(self):
        from api.postback_engine.schemas import validate_postback_payload
        result = validate_postback_payload(
            {"lead_id": "u1", "payout": "0.50", "offer_id": "o1"},
            network_key="cpalead",
        )
        self.assertIsNotNone(result)

    def test_missing_lead_id_raises(self):
        from api.postback_engine.schemas import validate_postback_payload
        from api.postback_engine.exceptions import SchemaValidationException
        with self.assertRaises(SchemaValidationException):
            validate_postback_payload({"payout": "0.50"}, network_key="cpalead")
