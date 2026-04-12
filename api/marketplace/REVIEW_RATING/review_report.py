"""
REVIEW_RATING/review_report.py — User Review Abuse Reporting
"""
from django.db import models
from django.conf import settings
from api.marketplace.models import ProductReview


class ReviewReport(models.Model):
    REASONS = [
        ("spam","Spam"),("inappropriate","Inappropriate Content"),
        ("fake","Fake Review"),("offensive","Offensive Language"),
        ("unrelated","Unrelated to Product"),("other","Other"),
    ]
    tenant     = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                    related_name="review_reports_tenant")
    review     = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name="reports")
    reported_by= models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reason     = models.CharField(max_length=20, choices=REASONS)
    details    = models.TextField(blank=True)
    is_resolved= models.BooleanField(default=False)
    resolved_by= models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="resolved_review_reports")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_review_report"
        unique_together = [("review","reported_by")]


def report_review(review_id: int, user, reason: str, details: str = "", tenant=None) -> dict:
    try:
        review = ProductReview.objects.get(pk=review_id)
    except ProductReview.DoesNotExist:
        return {"success": False, "error": "Review not found"}
    if review.user == user:
        return {"success": False, "error": "Cannot report your own review"}
    _, created = ReviewReport.objects.get_or_create(
        review=review, reported_by=user,
        defaults={"reason": reason, "details": details, "tenant": tenant}
    )
    if not created:
        return {"success": False, "error": "Already reported"}
    # Auto-hide if 5+ reports
    count = ReviewReport.objects.filter(review=review).count()
    if count >= 5:
        review.is_approved = False
        review.save(update_fields=["is_approved"])
    return {"success": True, "total_reports": count}


def get_pending_reports(tenant) -> list:
    return list(
        ReviewReport.objects.filter(tenant=tenant, is_resolved=False)
        .select_related("review__product","review__user","reported_by")
        .order_by("-created_at")
    )
