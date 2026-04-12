"""
PRODUCT_MANAGEMENT/product_answer.py — Answers to product questions
"""
from django.db import models
from .product_question import ProductQuestion
from django.conf import settings


class ProductAnswer(models.Model):
    question = models.ForeignKey(ProductQuestion, on_delete=models.CASCADE, related_name="answers")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    answer = models.TextField()
    is_seller_answer = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_product_answer"
        ordering = ["created_at"]

    def __str__(self):
        return f"A: {self.answer[:60]}"
