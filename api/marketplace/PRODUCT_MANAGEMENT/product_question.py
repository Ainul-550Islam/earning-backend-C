"""
PRODUCT_MANAGEMENT/product_question.py — Q&A on product pages
"""
from django.db import models
from api.marketplace.models import Product
from api.tenants.models import Tenant
from django.conf import settings


class ProductQuestion(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True,
                               related_name="marketplace_product_questions_tenant")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="questions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question = models.TextField()
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_product_question"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Q: {self.question[:60]}"
