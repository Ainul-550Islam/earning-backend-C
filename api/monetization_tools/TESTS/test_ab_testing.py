"""TESTS/test_ab_testing.py - A/B testing module tests."""
from ..A_B_TESTING.test_creator import ABTestCreator
from ..A_B_TESTING.multivariate_testing import MultivariateTestBuilder


class TestABTestCreator:
    def test_validate_variants_ok(self):
        variants = [{"name": "A", "weight": 50}, {"name": "B", "weight": 50}]
        errors   = ABTestCreator.validate_variants(variants)
        assert errors == []

    def test_validate_single_variant_fails(self):
        errors = ABTestCreator.validate_variants([{"name": "A", "weight": 100}])
        assert len(errors) > 0

    def test_validate_no_weight_fails(self):
        errors = ABTestCreator.validate_variants([{"name": "A", "weight": 0},
                                                   {"name": "B", "weight": 0}])
        assert len(errors) > 0


class TestMultivariateTestBuilder:
    def test_generate_2x2(self):
        combos = MultivariateTestBuilder.generate_combinations({"c": ["r","b"], "s": ["sm","lg"]})
        assert len(combos) == 4

    def test_generate_3x2(self):
        combos = MultivariateTestBuilder.generate_combinations({"a": [1,2,3], "b": ["x","y"]})
        assert len(combos) == 6

    def test_equal_weights(self):
        combos   = [{"c": "r"}, {"c": "b"}]
        variants = MultivariateTestBuilder.equal_weight_variants(combos)
        assert all(v["weight"] == 50 for v in variants)
