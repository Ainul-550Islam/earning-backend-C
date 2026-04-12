# api/publisher_tools/app_management/app_rating.py
"""App Rating — Store rating tracking."""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class AppRatingSnapshot(TimeStampedModel):
    """App store rating snapshot — daily tracking."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_apprating_tenant", db_index=True)
    app              = models.ForeignKey("publisher_tools.App", on_delete=models.CASCADE, related_name="rating_snapshots", db_index=True)
    date             = models.DateField(db_index=True)
    platform         = models.CharField(max_length=10, choices=[("android","Android"),("ios","iOS")], default="android")
    avg_rating       = models.DecimalField(max_digits=3, decimal_places=2, validators=[MinValueValidator(Decimal("1.0")), MaxValueValidator(Decimal("5.0"))])
    total_reviews    = models.IntegerField(default=0)
    new_reviews_today= models.IntegerField(default=0)
    five_star        = models.IntegerField(default=0)
    four_star        = models.IntegerField(default=0)
    three_star       = models.IntegerField(default=0)
    two_star         = models.IntegerField(default=0)
    one_star         = models.IntegerField(default=0)
    rating_change    = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "publisher_tools_app_rating_snapshots"
        verbose_name = _("App Rating Snapshot")
        unique_together = [["app", "date", "platform"]]
        ordering = ["-date"]

    def __str__(self):
        return f"{self.app.name} — {self.date} — {self.avg_rating} stars ({self.total_reviews} reviews)"
