"""TESTS/test_revenue_models.py - Revenue calculator tests."""
from decimal import Decimal
from ..REVENUE_MODELS.cpm_calculator import CPMCalculator
from ..REVENUE_MODELS.cpc_calculator import CPCCalculator
from ..REVENUE_MODELS.revshare_calculator import RevShareCalculator
from ..REVENUE_MODELS.hybrid_model import HybridRevenueModel


class TestCPMCalculator:
    def test_revenue(self):
        assert CPMCalculator.revenue(1000, Decimal("2.00")) == Decimal("2.000000")

    def test_ecpm(self):
        assert CPMCalculator.ecpm(Decimal("2.00"), 1000) == Decimal("2.0000")

    def test_ecpm_zero_impressions(self):
        assert CPMCalculator.ecpm(Decimal("2.00"), 0) == Decimal("0.0000")


class TestCPCCalculator:
    def test_revenue(self):
        assert CPCCalculator.revenue(100, Decimal("0.50")) == Decimal("50.000000")

    def test_to_ecpm(self):
        ecpm = CPCCalculator.to_ecpm(Decimal("0.50"), Decimal("2.00"))
        assert ecpm == Decimal("10.0000")


class TestRevShareCalculator:
    def test_split(self):
        result = RevShareCalculator.split(Decimal("100.00"), Decimal("70.00"))
        assert result["publisher"] == Decimal("70.000000")
        assert result["platform"] == Decimal("30.000000")


class TestHybridModel:
    def test_calculate(self):
        model  = HybridRevenueModel()
        result = model.calculate(1000, Decimal("2.00"), 30, Decimal("0.10"), 5, Decimal("1.00"))
        assert "total" in result
        assert result["total"] > 0
