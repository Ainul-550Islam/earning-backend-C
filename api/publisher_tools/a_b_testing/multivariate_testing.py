# api/publisher_tools/a_b_testing/multivariate_testing.py
"""Multivariate Testing — Multiple variable simultaneous testing."""
from decimal import Decimal
from typing import List, Dict


def create_multivariate_test(publisher, ad_unit, variables: Dict[str, List]) -> object:
    """
    Multivariate test create করে।
    variables = {"floor_price": [0.5, 1.0, 2.0], "refresh": [30, 60]}
    Creates all combinations as variants.
    """
    from .test_manager import ABTest, ABTestVariant
    import itertools
    combinations = list(itertools.product(*variables.values()))
    if len(combinations) > 5:
        combinations = combinations[:5]  # Limit to 5 variants
    test = ABTest.objects.create(
        publisher=publisher, ad_unit=ad_unit,
        name=f"Multivariate: {', '.join(variables.keys())}",
        test_type="multivariate",
        hypothesis="Testing multiple variables simultaneously.",
        confidence_level=Decimal("95.00"), min_sample_size=2000,
    )
    split = Decimal(str(round(100 / len(combinations), 2)))
    for i, combo in enumerate(combinations):
        config = dict(zip(variables.keys(), combo))
        ABTestVariant.objects.create(
            test=test, name=f"Combo {i+1}: {config}",
            is_control=(i == 0), traffic_split=split, config=config,
        )
    return test


def analyze_variable_interactions(test) -> List[Dict]:
    """Variable interaction analysis।"""
    variants = list(test.variants.all())
    interactions = []
    for v in variants:
        if v.total_impressions > 100:
            interactions.append({
                "config": v.config, "ecpm": float(v.ecpm),
                "impressions": v.total_impressions, "revenue": float(v.total_revenue),
            })
    return sorted(interactions, key=lambda x: x["ecpm"], reverse=True)
