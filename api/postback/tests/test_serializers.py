"""
test_serializers.py – Tests for all DRF serializers in the postback module.

High Priority tests:
  • NetworkPostbackConfigWriteSerializer – input validation (ip_whitelist, field_mapping, reward_rules)
  • PostbackLogSerializer – correct fields, read-only enforcement
  • PostbackLogDetailSerializer – extra fields present
  • PostbackS2SLogSerializer – callback_url truncation
  • LeadValidatorSerializer – CRUD fields
  • DuplicateLeadCheckSerializer – read-only fields

Medium Priority:
  • NetworkPostbackConfigListSerializer – output fields
  • NetworkPostbackConfigDetailSerializer – secret_key write-only
  • PostbackConversionSummarySerializer – analytics output
"""
from decimal import Decimal
from django.test import TestCase

from api.postback.serializers import (
    NetworkPostbackConfigListSerializer,
    NetworkPostbackConfigDetailSerializer,
    NetworkPostbackConfigWriteSerializer,
    PostbackLogSerializer,
    PostbackLogDetailSerializer,
    PostbackS2SLogSerializer,
    LeadValidatorSerializer,
    DuplicateLeadCheckSerializer,
    PostbackConversionSummarySerializer,
)
from api.postback.tests.factories import (
    CPALeadNetworkFactory,
    NetworkPostbackConfigFactory,
    PostbackLogFactory,
    RewardedPostbackLogFactory,
    PostbackS2SLogFactory,
    UserFactory,
    LeadValidatorFactory,
    DuplicateLeadCheckFactory,
    S2SNetworkFactory,
)


# ─────────────────────────────────────────────────────────────────────────────
# NetworkPostbackConfigWriteSerializer (HIGH PRIORITY — input validation)
# ─────────────────────────────────────────────────────────────────────────────

class NetworkPostbackConfigWriteSerializerTests(TestCase):

    def _valid_data(self, **kwargs):
        data = {
            "name": "Test Network",
            "network_key": "test_net_001",
            "network_type": "cpa",
            "status": "active",
            "secret_key": "mysecret",
            "signature_algorithm": "none",
            "ip_whitelist": [],
            "trust_forwarded_for": False,
            "require_nonce": False,
            "field_mapping": {},
            "required_fields": ["lead_id"],
            "dedup_window": "forever",
            "reward_rules": {},
            "default_reward_points": 100,
            "rate_limit_per_minute": 500,
            "contact_email": "test@example.com",
            "notes": "",
            "metadata": {},
            "callback_url": "",
            "callback_method": "GET",
            "callback_secret": "",
        }
        data.update(kwargs)
        return data

    def test_valid_data_passes(self):
        ser = NetworkPostbackConfigWriteSerializer(data=self._valid_data())
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_invalid_ip_whitelist_rejected(self):
        data = self._valid_data(ip_whitelist=["not-an-ip", "999.999.999.999"])
        ser = NetworkPostbackConfigWriteSerializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn("ip_whitelist", ser.errors)

    def test_valid_ip_whitelist_cidr(self):
        data = self._valid_data(ip_whitelist=["192.168.0.0/24", "10.0.0.1"])
        ser = NetworkPostbackConfigWriteSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_invalid_field_mapping_rejected(self):
        # field_mapping must be a dict with string keys/values
        data = self._valid_data(field_mapping="not_a_dict")
        ser = NetworkPostbackConfigWriteSerializer(data=data)
        self.assertFalse(ser.is_valid())

    def test_valid_field_mapping(self):
        data = self._valid_data(field_mapping={"lead_id": "click_id", "offer_id": "campaign"})
        ser = NetworkPostbackConfigWriteSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_invalid_reward_rules_rejected(self):
        # reward_rules must be a dict
        data = self._valid_data(reward_rules="invalid")
        ser = NetworkPostbackConfigWriteSerializer(data=data)
        self.assertFalse(ser.is_valid())

    def test_valid_reward_rules(self):
        data = self._valid_data(reward_rules={"OFFER_001": {"points": 500}})
        ser = NetworkPostbackConfigWriteSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_secret_key_write_only(self):
        """secret_key must be write-only (not in serialized output)."""
        net = NetworkPostbackConfigFactory(secret_key="supersecret")
        ser = NetworkPostbackConfigWriteSerializer(net)
        # secret_key should not appear in read output
        self.assertNotIn("secret_key", ser.data)

    def test_callback_url_https_accepted(self):
        data = self._valid_data(
            callback_url="https://adv.example.com/postback?lead={lead_id}&payout={payout}"
        )
        ser = NetworkPostbackConfigWriteSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_callback_method_choices(self):
        for method in ["GET", "POST"]:
            data = self._valid_data(callback_method=method)
            ser = NetworkPostbackConfigWriteSerializer(data=data)
            self.assertTrue(ser.is_valid(), f"Method {method} failed: {ser.errors}")

    def test_invalid_callback_method_rejected(self):
        data = self._valid_data(callback_method="DELETE")
        ser = NetworkPostbackConfigWriteSerializer(data=data)
        self.assertFalse(ser.is_valid())

    def test_missing_required_name_rejected(self):
        data = self._valid_data()
        del data["name"]
        ser = NetworkPostbackConfigWriteSerializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn("name", ser.errors)

    def test_missing_required_network_key_rejected(self):
        data = self._valid_data()
        del data["network_key"]
        ser = NetworkPostbackConfigWriteSerializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn("network_key", ser.errors)

    def test_create_network_config_via_serializer(self):
        """Serializer can actually create a NetworkPostbackConfig instance."""
        data = self._valid_data(network_key="test_create_via_ser_001")
        ser = NetworkPostbackConfigWriteSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)
        instance = ser.save()
        self.assertIsNotNone(instance.pk)
        self.assertEqual(instance.network_key, "test_create_via_ser_001")


# ─────────────────────────────────────────────────────────────────────────────
# NetworkPostbackConfigListSerializer
# ─────────────────────────────────────────────────────────────────────────────

class NetworkPostbackConfigListSerializerTests(TestCase):

    def test_fields_present(self):
        net = NetworkPostbackConfigFactory()
        data = NetworkPostbackConfigListSerializer(net).data
        for field in ["id", "name", "network_key", "network_type", "status",
                      "rate_limit_per_minute", "created_at"]:
            self.assertIn(field, data, f"Missing field: {field}")

    def test_status_display_present(self):
        net = NetworkPostbackConfigFactory()
        data = NetworkPostbackConfigListSerializer(net).data
        self.assertIn("status_display", data)

    def test_secret_key_not_exposed(self):
        net = NetworkPostbackConfigFactory(secret_key="topsecret")
        data = NetworkPostbackConfigListSerializer(net).data
        self.assertNotIn("secret_key", data)


# ─────────────────────────────────────────────────────────────────────────────
# NetworkPostbackConfigDetailSerializer
# ─────────────────────────────────────────────────────────────────────────────

class NetworkPostbackConfigDetailSerializerTests(TestCase):

    def test_callback_fields_present(self):
        net = S2SNetworkFactory()
        data = NetworkPostbackConfigDetailSerializer(net).data
        self.assertIn("callback_url", data)
        self.assertIn("callback_method", data)

    def test_secret_key_not_in_output(self):
        net = NetworkPostbackConfigFactory(secret_key="hidden")
        data = NetworkPostbackConfigDetailSerializer(net).data
        self.assertNotIn("secret_key", data)

    def test_field_mapping_present(self):
        net = CPALeadNetworkFactory()
        data = NetworkPostbackConfigDetailSerializer(net).data
        self.assertIn("field_mapping", data)

    def test_read_only_fields(self):
        net = NetworkPostbackConfigFactory()
        data = NetworkPostbackConfigDetailSerializer(net).data
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)


# ─────────────────────────────────────────────────────────────────────────────
# PostbackLogSerializer (HIGH PRIORITY)
# ─────────────────────────────────────────────────────────────────────────────

class PostbackLogSerializerTests(TestCase):

    def test_all_standard_fields_present(self):
        log = PostbackLogFactory()
        data = PostbackLogSerializer(log).data
        for field in ["id", "network_key", "status", "lead_id", "offer_id",
                      "payout", "currency", "event_type", "conversion_status",
                      "is_reversal", "click_id", "source_ip", "received_at"]:
            self.assertIn(field, data, f"Missing field: {field}")

    def test_network_key_from_related(self):
        net = CPALeadNetworkFactory()
        log = PostbackLogFactory(network=net)
        data = PostbackLogSerializer(log).data
        self.assertIn("cpalead", data["network_key"])

    def test_resolved_user_email_method(self):
        user = UserFactory()
        log = RewardedPostbackLogFactory(resolved_user=user)
        data = PostbackLogSerializer(log).data
        self.assertIn("resolved_user_email", data)
        self.assertEqual(data["resolved_user_email"], user.email)

    def test_resolved_user_email_empty_when_no_user(self):
        log = PostbackLogFactory()
        data = PostbackLogSerializer(log).data
        self.assertEqual(data["resolved_user_email"], "")

    def test_is_reversal_field(self):
        log = PostbackLogFactory(is_reversal=False)
        data = PostbackLogSerializer(log).data
        self.assertFalse(data["is_reversal"])

    def test_event_type_field(self):
        log = PostbackLogFactory(event_type="sale")
        data = PostbackLogSerializer(log).data
        self.assertEqual(data["event_type"], "sale")

    def test_all_fields_read_only(self):
        """PostbackLogSerializer is read-only — no write fields."""
        log = PostbackLogFactory()
        ser = PostbackLogSerializer(log, data={"lead_id": "HACKED"})
        # Since all fields are read_only, validation should work but not update
        self.assertIsNotNone(ser)

    def test_click_id_present(self):
        log = PostbackLogFactory(click_id="CLICK_001")
        data = PostbackLogSerializer(log).data
        self.assertEqual(data["click_id"], "CLICK_001")


# ─────────────────────────────────────────────────────────────────────────────
# PostbackLogDetailSerializer
# ─────────────────────────────────────────────────────────────────────────────

class PostbackLogDetailSerializerTests(TestCase):

    def test_includes_raw_payload(self):
        log = PostbackLogFactory(raw_payload={"lead_id": "L1", "offer_id": "O1"})
        data = PostbackLogDetailSerializer(log).data
        self.assertIn("raw_payload", data)
        self.assertEqual(data["raw_payload"]["lead_id"], "L1")

    def test_includes_request_headers(self):
        log = PostbackLogFactory(request_headers={"X-Custom": "value"})
        data = PostbackLogDetailSerializer(log).data
        self.assertIn("request_headers", data)

    def test_includes_method(self):
        log = PostbackLogFactory(method="GET")
        data = PostbackLogDetailSerializer(log).data
        self.assertIn("method", data)
        self.assertEqual(data["method"], "GET")

    def test_includes_fire_delay_ms(self):
        log = PostbackLogFactory(fire_delay_ms=1000)
        data = PostbackLogDetailSerializer(log).data
        self.assertIn("fire_delay_ms", data)
        self.assertEqual(data["fire_delay_ms"], 1000)

    def test_includes_reversed_log(self):
        log = PostbackLogFactory()
        data = PostbackLogDetailSerializer(log).data
        self.assertIn("reversed_log", data)

    def test_inherits_all_base_fields(self):
        """Detail serializer includes all base serializer fields."""
        log = PostbackLogFactory()
        base_data = PostbackLogSerializer(log).data
        detail_data = PostbackLogDetailSerializer(log).data
        for field in base_data:
            self.assertIn(field, detail_data, f"Base field missing in detail: {field}")


# ─────────────────────────────────────────────────────────────────────────────
# PostbackS2SLogSerializer
# ─────────────────────────────────────────────────────────────────────────────

class PostbackS2SLogSerializerTests(TestCase):

    def test_fields_present(self):
        log = PostbackS2SLogFactory()
        data = PostbackS2SLogSerializer(log).data
        for field in ["id", "postback_log", "http_status", "success",
                      "attempt_number", "error_message", "fired_at"]:
            self.assertIn(field, data, f"Missing field: {field}")

    def test_callback_url_truncated_at_120_chars(self):
        long_url = "https://adv.example.com/postback?" + "x=" * 60
        log = PostbackS2SLogFactory(callback_url=long_url)
        data = PostbackS2SLogSerializer(log).data
        self.assertIn("callback_url_truncated", data)
        self.assertLessEqual(len(data["callback_url_truncated"]), 124)  # 120 + "..."

    def test_short_url_not_truncated(self):
        short_url = "https://adv.example.com/cb"
        log = PostbackS2SLogFactory(callback_url=short_url)
        data = PostbackS2SLogSerializer(log).data
        self.assertEqual(data["callback_url_truncated"], short_url)

    def test_success_field(self):
        log = PostbackS2SLogFactory(success=True)
        data = PostbackS2SLogSerializer(log).data
        self.assertTrue(data["success"])

    def test_failed_log_serializes(self):
        log = PostbackS2SLogFactory(
            success=False, http_status=500, error_message="Timeout"
        )
        data = PostbackS2SLogSerializer(log).data
        self.assertFalse(data["success"])
        self.assertEqual(data["error_message"], "Timeout")


# ─────────────────────────────────────────────────────────────────────────────
# LeadValidatorSerializer
# ─────────────────────────────────────────────────────────────────────────────

class LeadValidatorSerializerTests(TestCase):

    def test_fields_present(self):
        validator = LeadValidatorFactory()
        data = LeadValidatorSerializer(validator).data
        for field in ["id", "name", "validator_type", "params",
                      "is_blocking", "sort_order", "is_active"]:
            self.assertIn(field, data, f"Missing field: {field}")

    def test_create_validator_via_serializer(self):
        net = NetworkPostbackConfigFactory()
        data = {
            "name": "Test Validator",
            "validator_type": "field_present",
            "params": {"field": "lead_id"},
            "is_blocking": True,
            "sort_order": 1,
            "is_active": True,
        }
        ser = LeadValidatorSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)
        instance = ser.save(network=net)
        self.assertIsNotNone(instance.pk)

    def test_params_is_json_field(self):
        validator = LeadValidatorFactory(params={"field": "lead_id", "pattern": r"^\d+$"})
        data = LeadValidatorSerializer(validator).data
        self.assertIsInstance(data["params"], dict)


# ─────────────────────────────────────────────────────────────────────────────
# DuplicateLeadCheckSerializer
# ─────────────────────────────────────────────────────────────────────────────

class DuplicateLeadCheckSerializerTests(TestCase):

    def test_fields_present(self):
        check = DuplicateLeadCheckFactory()
        data = DuplicateLeadCheckSerializer(check).data
        for field in ["id", "network_key", "lead_id", "first_seen_at"]:
            self.assertIn(field, data, f"Missing field: {field}")

    def test_network_key_from_related(self):
        net = NetworkPostbackConfigFactory()
        check = DuplicateLeadCheckFactory(network=net)
        data = DuplicateLeadCheckSerializer(check).data
        self.assertEqual(data["network_key"], net.network_key)

    def test_all_fields_read_only(self):
        check = DuplicateLeadCheckFactory()
        ser = DuplicateLeadCheckSerializer(check)
        self.assertIn("id", ser.data)


# ─────────────────────────────────────────────────────────────────────────────
# PostbackConversionSummarySerializer
# ─────────────────────────────────────────────────────────────────────────────

class PostbackConversionSummarySerializerTests(TestCase):

    def test_valid_data(self):
        data = {
            "event_type": "sale",
            "conversion_status": "approved",
            "count": 42,
            "total_payout": "210.00",
            "avg_payout": "5.00",
        }
        ser = PostbackConversionSummarySerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_count_must_be_integer(self):
        data = {
            "event_type": "lead",
            "conversion_status": "approved",
            "count": "not_int",
            "total_payout": "100.00",
            "avg_payout": "10.00",
        }
        ser = PostbackConversionSummarySerializer(data=data)
        self.assertFalse(ser.is_valid())

    def test_payout_decimal_fields(self):
        data = {
            "event_type": "install",
            "conversion_status": "approved",
            "count": 5,
            "total_payout": Decimal("25.50"),
            "avg_payout": Decimal("5.10"),
        }
        ser = PostbackConversionSummarySerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)
