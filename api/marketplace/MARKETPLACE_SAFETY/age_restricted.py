"""
MARKETPLACE_SAFETY/age_restricted.py — Age Restricted Product Categories
"""
from django.db import models

AGE_RESTRICTED_CATEGORIES = [
    "tobacco","alcohol","adult_content","gambling_equipment",
    "energy_drinks","vaping","fireworks",
]
MINIMUM_AGE = 18


class AgeRestrictedCategory(models.Model):
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                     related_name="age_restricted_categories_tenant")
    category    = models.ForeignKey("marketplace.Category", on_delete=models.CASCADE)
    min_age     = models.PositiveSmallIntegerField(default=MINIMUM_AGE)
    reason      = models.CharField(max_length=200)
    is_active   = models.BooleanField(default=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_age_restricted_category"


def check_age_restriction(product) -> dict:
    if not product.category:
        return {"restricted": False}
    try:
        restriction = AgeRestrictedCategory.objects.get(category=product.category, is_active=True)
        return {"restricted": True, "min_age": restriction.min_age, "reason": restriction.reason}
    except AgeRestrictedCategory.DoesNotExist:
        # Check category slug
        slug = product.category.slug.lower()
        if any(cat in slug for cat in AGE_RESTRICTED_CATEGORIES):
            return {"restricted": True, "min_age": MINIMUM_AGE, "reason": "Age-restricted category"}
        return {"restricted": False}


def verify_user_age(user, required_age: int = MINIMUM_AGE) -> bool:
    from django.utils import timezone
    if not hasattr(user, "date_of_birth") or not user.date_of_birth:
        return False  # cannot verify
    age = (timezone.now().date() - user.date_of_birth).days // 365
    return age >= required_age
