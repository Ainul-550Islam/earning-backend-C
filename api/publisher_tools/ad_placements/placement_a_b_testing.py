# api/publisher_tools/ad_placements/placement_a_b_testing.py
"""Placement A/B Testing — Position and config testing."""
from decimal import Decimal
from typing import List, Dict
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class PlacementABTest(TimeStampedModel):
    """A/B test specifically for placement position/config."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_placementabtest_tenant", db_index=True)
    TEST_TYPES = [
        ("position","Position Test"),("size","Size Test"),
        ("floor_price","Floor Price Test"),("refresh_rate","Refresh Rate Test"),
    ]
    placement_a      = models.ForeignKey("publisher_tools.AdPlacement", on_delete=models.CASCADE, related_name="ab_test_control")
    placement_b      = models.ForeignKey("publisher_tools.AdPlacement", on_delete=models.CASCADE, related_name="ab_test_variant")
    test_type        = models.CharField(max_length=20, choices=TEST_TYPES)
    name             = models.CharField(max_length=200)
    traffic_split_a  = models.IntegerField(default=50)
    traffic_split_b  = models.IntegerField(default=50)
    status           = models.CharField(max_length=20, choices=[("draft","Draft"),("running","Running"),("completed","Completed"),("cancelled","Cancelled")], default="draft")
    winner           = models.CharField(max_length=2, choices=[("A","A"),("B","B")], blank=True)
    winner_reason    = models.CharField(max_length=200, blank=True)
    confidence_pct   = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    start_date       = models.DateTimeField(null=True, blank=True)
    end_date         = models.DateTimeField(null=True, blank=True)
    min_duration_days= models.IntegerField(default=7)
    notes            = models.TextField(blank=True)

    class Meta:
        db_table = "publisher_tools_placement_ab_tests"
        verbose_name = _("Placement A/B Test")
        ordering = ["-created_at"]

    def __str__(self):
        return f"A/B: {self.name} [{self.test_type}] — {self.status}"

    def start(self):
        if self.status == "draft":
            self.status = "running"
            self.start_date = timezone.now()
            self.save()

    def declare_winner(self, winner: str, reason: str = "", confidence: float = None):
        self.winner = winner
        self.winner_reason = reason
        if confidence:
            self.confidence_pct = Decimal(str(confidence))
        self.status = "completed"
        self.end_date = timezone.now()
        self.save()

    @property
    def duration_days(self):
        if self.start_date:
            end = self.end_date or timezone.now()
            return (end - self.start_date).days
        return 0
