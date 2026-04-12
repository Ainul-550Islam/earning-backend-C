# api/publisher_tools/a_b_testing/test_creator.py
"""A/B Test Creator — Test creation helpers."""
from decimal import Decimal
from typing import Dict, List


def create_floor_price_test(publisher, ad_unit, control_floor: Decimal, test_floor: Decimal, name: str = None):
    from .test_manager import ABTest, ABTestVariant
    test = ABTest.objects.create(
        publisher=publisher, ad_unit=ad_unit,
        name=name or f"Floor Price: ${control_floor} vs ${test_floor}",
        test_type="floor_price",
        hypothesis=f"Increasing floor from ${control_floor} to ${test_floor} will increase eCPM.",
        confidence_level=Decimal("95.00"), min_sample_size=1000,
    )
    ABTestVariant.objects.create(test=test, name="Control", is_control=True, traffic_split=Decimal("50"), config={"floor_price": float(control_floor)})
    ABTestVariant.objects.create(test=test, name="Variant A", is_control=False, traffic_split=Decimal("50"), config={"floor_price": float(test_floor)})
    return test


def create_placement_test(publisher, ad_unit, positions: List[str], name: str = None):
    from .test_manager import ABTest, ABTestVariant
    test = ABTest.objects.create(
        publisher=publisher, ad_unit=ad_unit,
        name=name or f"Position Test: {' vs '.join(positions[:3])}",
        test_type="placement",
        hypothesis="Finding optimal ad placement for maximum revenue.",
        confidence_level=Decimal("95.00"), min_sample_size=1000,
    )
    split = Decimal(str(round(100 / len(positions), 2)))
    for i, position in enumerate(positions):
        ABTestVariant.objects.create(
            test=test, name=f"Position: {position}", is_control=(i == 0),
            traffic_split=split, config={"position": position},
        )
    return test


def create_format_test(publisher, ad_unit, formats: List[str]) -> object:
    from .test_manager import ABTest, ABTestVariant
    test = ABTest.objects.create(
        publisher=publisher, ad_unit=ad_unit,
        name=f"Format Test: {' vs '.join(formats[:3])}",
        test_type="ad_format",
        hypothesis="Testing optimal ad format for maximum revenue.",
        confidence_level=Decimal("95.00"), min_sample_size=1000,
    )
    split = Decimal(str(round(100 / len(formats), 2)))
    for i, fmt in enumerate(formats):
        ABTestVariant.objects.create(test=test, name=f"Format: {fmt}", is_control=(i == 0), traffic_split=split, config={"format": fmt})
    return test
