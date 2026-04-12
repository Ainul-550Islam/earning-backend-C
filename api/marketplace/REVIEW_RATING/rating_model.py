"""
REVIEW_RATING/rating_model.py — Rating Domain Models & Aggregates
==================================================================
Separate model for quick rating lookups without loading full review body.
"""
from django.db import models
from django.db.models import Avg, Count, StdDev
from api.marketplace.models import Product, ProductReview, SellerProfile


class ProductRatingSummary(models.Model):
    """
    Denormalised rating summary for each product (updated via signal/task).
    Avoids computing averages on every API request.
    """
    product         = models.OneToOneField(Product, on_delete=models.CASCADE,
                                           related_name="rating_summary")
    average_rating  = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_reviews   = models.PositiveIntegerField(default=0)
    five_star       = models.PositiveIntegerField(default=0)
    four_star       = models.PositiveIntegerField(default=0)
    three_star      = models.PositiveIntegerField(default=0)
    two_star        = models.PositiveIntegerField(default=0)
    one_star        = models.PositiveIntegerField(default=0)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_product_rating_summary"

    def __str__(self):
        return f"{self.product.name}: {self.average_rating}★ ({self.total_reviews} reviews)"

    @property
    def distribution(self) -> dict:
        return {5: self.five_star, 4: self.four_star, 3: self.three_star,
                2: self.two_star, 1: self.one_star}

    @property
    def recommendation_rate(self) -> float:
        if self.total_reviews == 0:
            return 0.0
        positive = self.five_star + self.four_star
        return round(positive / self.total_reviews * 100, 1)

    def refresh(self):
        """Recalculate from reviews table."""
        qs  = ProductReview.objects.filter(product=self.product, is_approved=True)
        agg = qs.aggregate(avg=Avg("rating"), total=Count("id"))
        dist = {i: qs.filter(rating=i).count() for i in range(1, 6)}
        ProductRatingSummary.objects.filter(pk=self.pk).update(
            average_rating=round(agg["avg"] or 0, 2),
            total_reviews=agg["total"] or 0,
            five_star=dist[5], four_star=dist[4], three_star=dist[3],
            two_star=dist[2],  one_star=dist[1],
        )


def refresh_product_rating(product: Product) -> ProductRatingSummary:
    summary, _ = ProductRatingSummary.objects.get_or_create(product=product)
    summary.refresh()
    summary.refresh_from_db()
    # Also update denormalised fields on Product
    Product.objects.filter(pk=product.pk).update(
        average_rating=summary.average_rating,
        review_count=summary.total_reviews,
    )
    return summary
