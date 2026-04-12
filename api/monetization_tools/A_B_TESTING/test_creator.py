"""A_B_TESTING/test_creator.py — A/B test creation and configuration."""
from typing import List
from decimal import Decimal


class ABTestCreator:
    """Creates and configures A/B tests for ad units and creatives."""

    @classmethod
    def create(cls, name: str, variants: List[dict], traffic_split: int = 100,
                tenant=None, winner_criteria: str = "ctr",
                min_sample_size: int = 1000, duration_days: int = 14):
        from ..models import ABTest
        return ABTest.objects.create(
            name=name, status="draft", variants=variants,
            traffic_split=traffic_split, winner_criteria=winner_criteria,
            min_sample_size=min_sample_size, duration_days=duration_days,
            tenant=tenant,
        )

    @classmethod
    def start(cls, test_id: int) -> bool:
        from ..models import ABTest
        from django.utils import timezone
        updated = ABTest.objects.filter(
            pk=test_id, status="draft"
        ).update(status="running", started_at=timezone.now())
        return bool(updated)

    @classmethod
    def pause(cls, test_id: int) -> bool:
        from ..models import ABTest
        return bool(ABTest.objects.filter(pk=test_id, status="running").update(status="paused"))

    @classmethod
    def resume(cls, test_id: int) -> bool:
        from ..models import ABTest
        return bool(ABTest.objects.filter(pk=test_id, status="paused").update(status="running"))

    @classmethod
    def validate_variants(cls, variants: List[dict]) -> list:
        errors = []
        if len(variants) < 2:
            errors.append("At least 2 variants required.")
        total_w = sum(v.get("weight", 0) for v in variants)
        if total_w <= 0:
            errors.append("Total variant weight must be > 0.")
        for i, v in enumerate(variants):
            if not v.get("name"):
                errors.append(f"Variant {i+1}: name required.")
        return errors
