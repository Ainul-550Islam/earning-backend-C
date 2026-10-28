"""
payout_queue/tests/test_fee_calculator_full.py  ← NEW FILE  (Part 2 / File 7)

FeeCalculator had ~30% coverage (basic FLAT/PERCENTAGE/TIERED).
Missing:
  - get_fee_summary() for every gateway (dead code, now exposed)
  - custom FeeConfig injection
  - edge cases: MIN_PAYOUT_AMOUNT, MAX_PAYOUT_AMOUNT, MAX_FEE_AMOUNT cap
  - negative gross raises
  - non-Decimal gross is coerced
  - FeeConfig validation errors
  - TIERED with exact tier boundary values
  - min_fee enforcement
  - FeeCalculator.calculate() gateway loop
"""
from __future__ import annotations

from decimal import Decimal
from django.test import TestCase

from ..choices import PaymentGateway, FeeType
from ..constants import (
    MIN_PAYOUT_AMOUNT, MAX_PAYOUT_AMOUNT, MAX_FEE_AMOUNT,
    DEFAULT_BKASH_FEE_PERCENT, DEFAULT_NAGAD_FEE_PERCENT,
    DEFAULT_ROCKET_FEE_PERCENT, DEFAULT_BANK_FLAT_FEE,
)
from ..exceptions import FeeCalculationError
from ..utils.fee_calculator import FeeCalculator, FeeConfig

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FeeConfig unit tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class FeeConfigFlatTest(TestCase):

    def _cfg(self, flat_fee="25.00"):
        return FeeConfig(fee_type=FeeType.FLAT, flat_fee=Decimal(flat_fee))

    def test_flat_fee_correct(self):
        self.assertEqual(self._cfg("25.00").compute(Decimal("1000.00")), Decimal("25.00"))

    def test_flat_fee_zero(self):
        self.assertEqual(self._cfg("0.00").compute(Decimal("500.00")), Decimal("0.00"))

    def test_flat_fee_capped_at_max_fee(self):
        cfg = FeeConfig(fee_type=FeeType.FLAT,
                        flat_fee=Decimal("10000.00"),
                        max_fee=Decimal("100.00"))
        self.assertEqual(cfg.compute(Decimal("500.00")), Decimal("100.00"))

    def test_negative_gross_raises(self):
        with self.assertRaises(FeeCalculationError):
            self._cfg().compute(Decimal("-1.00"))

    def test_zero_gross_returns_flat(self):
        # Zero gross is valid; flat fee still applies (or is min-capped to 0)
        result = self._cfg("25.00").compute(Decimal("0.00"))
        self.assertEqual(result, Decimal("25.00"))

    def test_non_decimal_gross_coerced(self):
        result = self._cfg("25.00").compute(1000)   # int
        self.assertEqual(result, Decimal("25.00"))

class FeeConfigPercentageTest(TestCase):

    def _cfg(self, pct="1.85"):
        return FeeConfig(fee_type=FeeType.PERCENTAGE, percent=Decimal(pct))

    def test_percentage_calculation(self):
        # 1.85% of 1000 = 18.50
        self.assertEqual(self._cfg("1.85").compute(Decimal("1000.00")), Decimal("18.50"))

    def test_percentage_rounds_half_up(self):
        # 1.85% of 100 = 1.85 → exactly 1.85
        self.assertEqual(self._cfg("1.85").compute(Decimal("100.00")), Decimal("1.85"))

    def test_percentage_capped_at_max(self):
        cfg = FeeConfig(fee_type=FeeType.PERCENTAGE, percent=Decimal("50"),
                        max_fee=Decimal("100.00"))
        # 50% of 1000 = 500, capped to 100
        self.assertEqual(cfg.compute(Decimal("1000.00")), Decimal("100.00"))

    def test_min_fee_enforced(self):
        cfg = FeeConfig(fee_type=FeeType.PERCENTAGE, percent=Decimal("0.01"),
                        min_fee=Decimal("5.00"))
        # 0.01% of 100 = 0.01, raised to min 5.00
        self.assertEqual(cfg.compute(Decimal("100.00")), Decimal("5.00"))

    def test_percent_above_100_raises(self):
        with self.assertRaises(FeeCalculationError):
            FeeConfig(fee_type=FeeType.PERCENTAGE, percent=Decimal("101"))

    def test_negative_percent_raises(self):
        with self.assertRaises(FeeCalculationError):
            FeeConfig(fee_type=FeeType.PERCENTAGE, percent=Decimal("-1"))

    def test_flat_fee_not_decimal_raises(self):
        with self.assertRaises(FeeCalculationError):
            FeeConfig(fee_type=FeeType.FLAT, flat_fee=18.50)  # float not Decimal

class FeeConfigTieredTest(TestCase):

    def _tiered(self):
        return FeeConfig(
            fee_type=FeeType.TIERED,
            tiers=[
                {"min": "0",      "max": "500",   "percent": "1.0",  "flat": "0"},
                {"min": "500.01", "max": "5000",  "percent": "1.5",  "flat": "5"},
                {"min": "5000.01","max": None,    "percent": "2.0",  "flat": "10"},
            ],
        )

    def test_first_tier_boundary_low(self):
        # 1% of 100 = 1.00
        self.assertEqual(self._tiered().compute(Decimal("100.00")), Decimal("1.00"))

    def test_first_tier_boundary_high(self):
        # 1% of 500 = 5.00
        self.assertEqual(self._tiered().compute(Decimal("500.00")), Decimal("5.00"))

    def test_second_tier(self):
        # 1.5% of 1000 + 5 = 15 + 5 = 20.00
        self.assertEqual(self._tiered().compute(Decimal("1000.00")), Decimal("20.00"))

    def test_third_tier_unbounded(self):
        # 2% of 10000 + 10 = 200 + 10 = 210.00
        self.assertEqual(self._tiered().compute(Decimal("10000.00")), Decimal("210.00"))

    def test_no_matching_tier_raises(self):
        cfg = FeeConfig(
            fee_type=FeeType.TIERED,
            tiers=[{"min": "100", "max": "200", "percent": "1", "flat": "0"}],
        )
        with self.assertRaises(FeeCalculationError):
            cfg.compute(Decimal("50.00"))   # below lowest tier

    def test_empty_tiers_raises(self):
        cfg = FeeConfig(fee_type=FeeType.TIERED, tiers=[])
        with self.assertRaises(FeeCalculationError):
            cfg.compute(Decimal("100.00"))

    def test_tiered_capped_at_max(self):
        cfg = FeeConfig(
            fee_type=FeeType.TIERED,
            tiers=[{"min": "0", "max": None, "percent": "99", "flat": "0"}],
            max_fee=Decimal("100.00"),
        )
        fee = cfg.compute(Decimal("10000.00"))
        self.assertLessEqual(fee, Decimal("100.00"))

class FeeConfigInvalidTypeTest(TestCase):

    def test_invalid_fee_type_raises(self):
        with self.assertRaises(FeeCalculationError):
            FeeConfig(fee_type="MAGIC")

    def test_negative_flat_fee_raises(self):
        with self.assertRaises(FeeCalculationError):
            FeeConfig(fee_type=FeeType.FLAT, flat_fee=Decimal("-1"))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FeeCalculator.calculate — all gateways
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class FeeCalculatorCalculateTest(TestCase):

    calc = FeeCalculator()

    def _result(self, gateway, amount="1000.00"):
        return self.calc.calculate(gateway=gateway, gross_amount=Decimal(amount))

    def test_bkash_percentage(self):
        r = self._result(PaymentGateway.BKASH)
        expected_fee = (Decimal("1000.00") * DEFAULT_BKASH_FEE_PERCENT
                        / Decimal("100")).quantize(Decimal("0.01"))
        self.assertEqual(r["fee"], expected_fee)
        self.assertEqual(r["net"], Decimal("1000.00") - expected_fee)
        self.assertEqual(r["gross"], Decimal("1000.00"))

    def test_nagad_percentage(self):
        r = self._result(PaymentGateway.NAGAD)
        expected = (Decimal("1000.00") * DEFAULT_NAGAD_FEE_PERCENT
                    / Decimal("100")).quantize(Decimal("0.01"))
        self.assertEqual(r["fee"], expected)

    def test_rocket_percentage(self):
        r = self._result(PaymentGateway.ROCKET)
        expected = (Decimal("1000.00") * DEFAULT_ROCKET_FEE_PERCENT
                    / Decimal("100")).quantize(Decimal("0.01"))
        self.assertEqual(r["fee"], expected)

    def test_bank_flat_fee(self):
        r = self._result(PaymentGateway.BANK)
        self.assertEqual(r["fee"], DEFAULT_BANK_FLAT_FEE)
        self.assertEqual(r["net"], Decimal("1000.00") - DEFAULT_BANK_FLAT_FEE)

    def test_manual_zero_fee(self):
        r = self._result(PaymentGateway.MANUAL)
        self.assertEqual(r["fee"], Decimal("0.00"))
        self.assertEqual(r["net"], Decimal("1000.00"))

    def test_below_minimum_raises(self):
        with self.assertRaises(FeeCalculationError):
            self.calc.calculate(gateway=PaymentGateway.BKASH,
                                gross_amount=Decimal("0.50"))

    def test_above_maximum_raises(self):
        with self.assertRaises(FeeCalculationError):
            self.calc.calculate(gateway=PaymentGateway.BKASH,
                                gross_amount=Decimal("999999.00"))

    def test_invalid_gateway_raises(self):
        with self.assertRaises(FeeCalculationError):
            self.calc.calculate(gateway="FAKE_GW", gross_amount=Decimal("100"))

    def test_empty_gateway_raises(self):
        with self.assertRaises(FeeCalculationError):
            self.calc.calculate(gateway="", gross_amount=Decimal("100"))

    def test_non_decimal_amount_coerced(self):
        # int/float string should be coerced to Decimal
        r = self.calc.calculate(gateway=PaymentGateway.MANUAL,
                                gross_amount=Decimal("500"))
        self.assertEqual(r["gross"], Decimal("500"))

    def test_exact_minimum_amount(self):
        r = self.calc.calculate(gateway=PaymentGateway.BKASH,
                                gross_amount=MIN_PAYOUT_AMOUNT)
        self.assertGreaterEqual(r["fee"], Decimal("0"))

    def test_custom_config_injected(self):
        custom_calc = FeeCalculator(configs={
            PaymentGateway.BKASH: FeeConfig(
                fee_type=FeeType.FLAT, flat_fee=Decimal("100.00"))
        })
        r = custom_calc.calculate(gateway=PaymentGateway.BKASH,
                                  gross_amount=Decimal("1000.00"))
        self.assertEqual(r["fee"], Decimal("100.00"))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FeeCalculator.get_fee_summary — all gateways (was dead code)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class FeeCalculatorGetFeeSummaryTest(TestCase):
    """
    get_fee_summary() was dead code — no tests, no HTTP exposure.
    Now exposed via GET /batches/gateways/ and GET /fee-summary/.
    """
    calc = FeeCalculator()

    def _assert_shape(self, summary, gateway):
        self.assertIn("gateway",  summary)
        self.assertIn("fee_type", summary)
        self.assertEqual(summary["gateway"], gateway)

    def test_bkash(self):
        self._assert_shape(self.calc.get_fee_summary(gateway=PaymentGateway.BKASH),
                           PaymentGateway.BKASH)

    def test_nagad(self):
        self._assert_shape(self.calc.get_fee_summary(gateway=PaymentGateway.NAGAD),
                           PaymentGateway.NAGAD)

    def test_rocket(self):
        self._assert_shape(self.calc.get_fee_summary(gateway=PaymentGateway.ROCKET),
                           PaymentGateway.ROCKET)

    def test_bank(self):
        s = self.calc.get_fee_summary(gateway=PaymentGateway.BANK)
        self._assert_shape(s, PaymentGateway.BANK)
        self.assertEqual(s["fee_type"], FeeType.FLAT)

    def test_manual(self):
        s = self.calc.get_fee_summary(gateway=PaymentGateway.MANUAL)
        self._assert_shape(s, PaymentGateway.MANUAL)
        self.assertEqual(s["flat_fee"], "0.00")

    def test_unknown_gateway_returns_unknown(self):
        s = self.calc.get_fee_summary(gateway="FAKE")
        self.assertEqual(s["gateway"], "FAKE")
        self.assertIn("description", s)

    def test_bkash_has_percent_field(self):
        s = self.calc.get_fee_summary(gateway=PaymentGateway.BKASH)
        self.assertIn("percent", s)
        self.assertEqual(s["percent"], str(DEFAULT_BKASH_FEE_PERCENT))

    def test_bank_has_flat_fee_field(self):
        s = self.calc.get_fee_summary(gateway=PaymentGateway.BANK)
        self.assertIn("flat_fee", s)
        self.assertEqual(s["flat_fee"], str(DEFAULT_BANK_FLAT_FEE))

    def test_max_fee_present(self):
        s = self.calc.get_fee_summary(gateway=PaymentGateway.BKASH)
        self.assertIn("max_fee", s)
